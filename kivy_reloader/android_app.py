"""
Android Reloader App

Handles hot reload on Android devices:
- Receives app updates via TCP server
- Uses file hashing to detect changes
- Manages service restarts and compilation
"""

import hashlib
import importlib
import os
import shutil
import socket
import subprocess
import sys
import traceback

import trio
from kivy.app import App as KivyApp
from kivy.base import async_runTouchApp
from kivy.core.window import Window
from kivy.factory import Factory as F
from kivy.lang import Builder
from kivy.logger import Logger
from kivy.utils import platform

try:
    from jnius import autoclass  # type: ignore

    JNIUS_AVAILABLE = True
except ImportError:
    JNIUS_AVAILABLE = False

from .base_app import BaseReloaderApp
from .config import config
from .utils import get_kv_files_paths


class AndroidApp(BaseReloaderApp, KivyApp):
    # ==================== INITIALIZATION ====================
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        main_py_file_path = os.path.join(os.getcwd(), 'main.py')

        if os.path.exists(main_py_file_path):
            self.main_py_hash = self.get_hash_of_file(main_py_file_path)
        else:
            self.main_py_hash = None

        # hot reload
        self.kv_files_hashes = {
            file_name: self.get_hash_of_file(file_name)
            for file_name in get_kv_files_paths()
        }

        # live reload
        self.service_files_hashes = {
            file_name: self.get_hash_of_file(file_name)
            for file_name in config.SERVICE_FILES
        }

        # live reload
        self.full_reload_file_hashes = {
            file_name: self.get_hash_of_file(file_name)
            for file_name in config.FULL_RELOAD_FILES
            if os.path.exists(file_name)
        }

        self.recompile_main()

        self.bind_key(114, self.restart_app_on_android)

    # ==================== APP LIFECYCLE ====================
    async def async_run(self, async_lib='trio'):
        async with trio.open_nursery() as nursery:
            Logger.info('Reloader: Starting Async Kivy app')
            self.nursery = nursery
            self.initialize_server()
            self._run_prepare()
            await async_runTouchApp(async_lib=async_lib)
            self._stop()
            nursery.cancel_scope.cancel()

    def restart_app_on_android(self):
        Logger.info('Restarting the app on smartphone')

        if not JNIUS_AVAILABLE:
            Logger.error('jnius not available for Android restart')
            return

        Intent = autoclass('android.content.Intent')
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        System = autoclass('java.lang.System')

        activity = PythonActivity.mActivity
        intent = Intent(activity.getApplicationContext(), PythonActivity)
        intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        intent.setFlags(Intent.FLAG_ACTIVITY_CLEAR_TASK)
        activity.startActivity(intent)
        System.exit(0)

    # ==================== UTILITY FUNCTIONS ====================
    def bind_key(self, key, callback):
        """
        Reload the app when pressing Ctrl+R from scrcpy
        """

        def _on_keyboard(window, keycode, scancode, codepoint, modifier_keys):
            pressed_modifiers = set(modifier_keys)

            if key == keycode and 'ctrl' in pressed_modifiers:
                return callback()

        Window.bind(on_keyboard=_on_keyboard)

    def get_hash_of_file(self, file_name):
        """
        Returns the hash of the file using md5 hash
        """
        try:
            with open(file_name, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except (FileNotFoundError, PermissionError) as e:
            Logger.warning(f'Unable to hash file {file_name}: {e}')
            return None

    def _unregister_factory_from_module(self, module):
        to_remove = [x for x in F.classes if F.classes[x]['module'] == module]

        # check class name
        for x in F.classes:
            cls = F.classes[x]['cls']
            if not cls:
                continue
            if getattr(cls, '__module__', None) == module:
                to_remove.append(x)

        for name in set(to_remove):
            del F.classes[name]

    def recompile_main(self):
        if platform == 'android':
            files = os.listdir()
            if 'main.pyc' in files and 'main.py' in files:
                Logger.info('Deleting main.pyc')
                os.remove('main.pyc')
                Logger.info('Compiling main.py')
                main_py_path = os.path.join(os.getcwd(), 'main.py')
                subprocess.run(
                    f'python -m compileall {main_py_path}',
                    shell=True,
                    check=True,
                )

    # ==================== HOT RELOAD CORE ====================

    def reload_kv(self, *args):
        """
        Hot reloading kv files on Android
        """
        Logger.info('Reloading kv files')
        main_py_file_path = os.path.join(os.getcwd(), 'main.py')

        # reload the service files
        should_restart_app_on_android = False
        for service_name, file_name in zip(config.SERVICE_NAMES, config.SERVICE_FILES):
            if self.get_hash_of_file(file_name) != self.service_files_hashes[file_name]:
                Logger.info(f'Service {service_name} has been updated')
                if os.path.exists(f'{file_name}c'):
                    # remove the compiled service file
                    os.remove(f'{file_name}c')

                # recopiling the service file
                subprocess.run(
                    f'python -m compileall {file_name}',
                    shell=True,
                    check=True,
                )

                # stop the service
                Logger.info(f'Stopping service {service_name}')
                if not JNIUS_AVAILABLE:
                    Logger.error('jnius not available for service management')
                    continue

                mActivity = autoclass('org.kivy.android.PythonActivity').mActivity
                context = mActivity.getApplicationContext()
                SERVICE_NAME = str(context.getPackageName()) + '.Service' + service_name
                service = autoclass(SERVICE_NAME)
                service.stop(mActivity)
                should_restart_app_on_android = True

        if should_restart_app_on_android:
            self.restart_app_on_android()
            return

        for file_name in config.FULL_RELOAD_FILES:
            if not os.path.exists(file_name):
                Logger.info(f'Reloader: File {file_name} does not exist. Skipping!')
                continue

            if file_name not in self.full_reload_file_hashes:
                self.full_reload_file_hashes[file_name] = self.get_hash_of_file(
                    file_name
                )
                continue

            if (
                self.get_hash_of_file(file_name)
                != self.full_reload_file_hashes[file_name]
            ):
                Logger.info(
                    f'Reloader: File {file_name} has been updated. Restarting app...'
                )
                self.restart_app_on_android()

        if os.path.exists(main_py_file_path):
            if self.get_hash_of_file(main_py_file_path) != self.main_py_hash:
                # `main.py` changed, restarting app
                self.restart_app_on_android()
                return

        # Reload only the kv files that changed
        current_kv_files_hashes = {
            file_name: self.get_hash_of_file(file_name)
            for file_name in get_kv_files_paths()
        }

        if current_kv_files_hashes != self.kv_files_hashes:
            kv_files_that_changed = [
                file_name
                for file_name in current_kv_files_hashes
                if current_kv_files_hashes[file_name]
                != self.kv_files_hashes.get(file_name, None)
            ]

            for file_name in kv_files_that_changed:
                Builder.unload_file(file_name)
                Builder.load_file(file_name)

        self.build_root_and_add_to_window()

    def unload_python_file(self, filename, module):
        if module == 'main':
            return None

        if module in sys.modules:
            full_path = os.path.join(os.getcwd(), filename)
            F.unregister_from_filename(full_path)
            self._unregister_factory_from_module(module)
            return sys.modules[module]

        return None

    def gather_files_to_reload(self, folders, recursive=False):
        files_to_reload = []
        for folder in folders:
            if recursive:
                for root, _, files in os.walk(folder):
                    files_to_reload.extend(
                        os.path.join(root, file)
                        for file in files
                        if file.endswith('.py')
                    )
            else:
                files_to_reload.extend(
                    os.path.join(folder, file)
                    for file in os.listdir(folder)
                    if file.endswith('.py')
                )
        return files_to_reload

    def process_unload_files(self, files):
        modules_to_reload = []
        for filename in files:
            module_name = os.path.relpath(filename).replace(os.path.sep, '.')[:-3]
            to_reload = self.unload_python_file(filename, module_name)
            if to_reload is not None:
                modules_to_reload.append(to_reload)

        return modules_to_reload

    def unload_python_files_on_android(self):
        """
        Optimized version: Process files in batches and avoid redundant operations
        """
        files_to_reload = []

        # Gather files from recursively watched folders
        files_to_reload.extend(
            self.gather_files_to_reload(
                config.WATCHED_FOLDERS_RECURSIVELY, recursive=True
            )
        )

        # Gather files from watched folders
        files_to_reload.extend(self.gather_files_to_reload(config.WATCHED_FOLDERS))

        # Add individual watched files
        files_to_reload.extend(
            os.path.join(os.getcwd(), file) for file in config.WATCHED_FILES
        )

        # Add files that require full reload
        files_to_reload.extend(
            os.path.join(os.getcwd(), file) for file in config.FULL_RELOAD_FILES
        )

        # Process the files and get the modules to reload
        modules_to_reload = self.process_unload_files(files_to_reload)

        # Performance optimization: Only reload if we have modules to reload
        if not modules_to_reload:
            Logger.info('Reloader: No modules to reload, skipping reload step')
            return

        # We need to reload the modules twice, because some modules
        # may depend on other modules, and the order of reloading
        # matters, so the first pass won't reload necessarily
        # on the correct order, on the second pass the
        # references will be updated correctly
        Logger.info(f'Reloader: Reloading {len(modules_to_reload)} modules (2 passes)')
        for pass_num in range(2):
            for module in modules_to_reload:
                try:
                    importlib.reload(module)
                except Exception as e:
                    Logger.warning(
                        f'Failed to reload {module} on pass {pass_num + 1}: {e}'
                    )

    # ==================== NETWORK SERVER ====================
    def initialize_server(self):
        """
        Starts the server
        """
        self.nursery.start_soon(self.start_async_server)

    async def start_async_server(self):
        """
        The android server keeps listening
        expecting the computer to send data to it
        """
        PORT = config.RELOADER_PORT

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                probe.connect(('8.8.8.8', 80))
                ip = probe.getsockname()[0]

            Logger.info(f'Smartphone IP: {ip}')

            await trio.serve_tcp(self.data_receiver, PORT)
        except Exception as e:
            Logger.info(
                'It was not possible to start the server, check if the '
                'phone is connected to the same network as the computer'
            )
            Logger.info(
                'Another possible cause is that the port is already in use'
                ' by another app. Check if the port is free and try again'
            )
            Logger.info(e)

    async def data_receiver(self, data_stream):
        """
        When data is received from the computer
        it is saved in a zip file
        and then unpacked
        and the app is reloaded
        """
        Logger.info('Reloader: ************** SERVER **************')
        Logger.info('Reloader: Server started: receiving data from computer...')

        try:
            zip_file_path = os.path.join(os.getcwd(), 'app_copy.zip')
            with open(zip_file_path, 'wb') as myzip:
                async for data in data_stream:
                    Logger.info('Reloader: Server: received data')
                    Logger.info(f'Reloader: Data size: {len(data)}')
                    Logger.info('Reloader: Server: connection closed')
                    myzip.write(data)

            Logger.info('Reloader: Finished receiving all files from computer')
            Logger.info('Reloader: Unpacking app')

            # first print the size of the zip file
            zip_file_size = os.path.getsize(zip_file_path)
            Logger.info(f'Reloader: Zip file size: {zip_file_size}')

            shutil.unpack_archive(zip_file_path)

            # Deleting the zip file
            os.remove(zip_file_path)

            # Recompiling main.py
            # Logger.info("Recompiling main.py")
            # self.recompile_main()

            Logger.info('Reloader: App updated, restarting app for refresh')
            Logger.info('Reloader: ************** END SERVER **************')

            self.unload_python_files_on_android()
            if self.__module__ != '__main__':
                importlib.reload(importlib.import_module(self.__module__))
            self.reload_kv()

        except Exception as e:
            Logger.info(f'Reloader: Server crashed: {e!r}')
            Logger.info(
                'Full exception:',
                ''.join(traceback.format_exception(*sys.exc_info())),
            )
