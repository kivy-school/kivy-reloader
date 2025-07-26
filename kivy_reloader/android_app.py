"""
Android Reloader App

Handles hot reload on Android devices:
- Receives app updates via TCP server
- Uses file hashing to detect changes
- Manages service restarts and compilation
"""

# Standard library imports
import hashlib
import importlib
import os
import shutil
import socket
import subprocess
import sys
import traceback

# Third-party imports
import trio
from kivy.app import App as KivyApp
from kivy.base import async_runTouchApp
from kivy.core.window import Window
from kivy.factory import Factory as F
from kivy.lang import Builder
from kivy.logger import Logger
from kivy.utils import platform

# Android-specific imports (optional dependency)
try:
    from jnius import autoclass  # type: ignore

    JNIUS_AVAILABLE = True
except ImportError:
    JNIUS_AVAILABLE = False

# Local imports
from .base_app import BaseReloaderApp
from .config import config
from .utils import get_kv_files_paths

# Constants
CTRL_R_KEYCODE = 114
MODULE_RELOAD_PASSES = 2
DNS_SERVER_IP = '8.8.8.8'
DNS_SERVER_PORT = 80


class AndroidApp(BaseReloaderApp, KivyApp):
    """Android hot reload app with TCP server and service management"""

    # ==================== INITIALIZATION ====================

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._initialize_file_hashing()
        self._setup_android_environment()
        self._setup_key_bindings()

    def _initialize_file_hashing(self):
        """Initialize file hash tracking for hot reload detection."""
        main_py_file_path = os.path.join(os.getcwd(), 'main.py')

        # Initialize main.py hash
        if os.path.exists(main_py_file_path):
            self.main_py_hash = self.get_hash_of_file(main_py_file_path)
        else:
            self.main_py_hash = None

        # Initialize KV file hashes for hot reload
        self.kv_files_hashes = {
            file_name: self.get_hash_of_file(file_name)
            for file_name in get_kv_files_paths()
        }

        # Initialize service file hashes for live reload
        self.service_files_hashes = {
            file_name: self.get_hash_of_file(file_name)
            for file_name in config.SERVICE_FILES
        }

        # Initialize full reload file hashes
        self.full_reload_file_hashes = {
            file_name: self.get_hash_of_file(file_name)
            for file_name in config.FULL_RELOAD_FILES
            if os.path.exists(file_name)
        }

    def _setup_android_environment(self):
        """Configure Android-specific settings and compilation."""
        self.recompile_main()

    def _setup_key_bindings(self):
        """Setup keyboard shortcuts for manual reload."""
        self.bind_key(CTRL_R_KEYCODE, self.restart_app_on_android)

    # ==================== APP LIFECYCLE ====================

    async def async_run(self, async_lib='trio'):
        """
        Run the Android app asynchronously with TCP server.

        Starts the TCP server for receiving hot reload updates from desktop,
        then runs the main Kivy application loop.
        """
        async with trio.open_nursery() as nursery:
            Logger.info('Reloader: Starting Async Kivy app')
            self.nursery = nursery
            self.initialize_server()
            self._run_prepare()
            await async_runTouchApp(async_lib=async_lib)
            self._stop()
            nursery.cancel_scope.cancel()

    def restart_app_on_android(self):
        """
        Restart the Android application using Android intents.

        Uses the jnius library to interact with Android APIs and restart
        the application cleanly by creating a new intent and clearing tasks.
        """
        Logger.info('Restarting the app on smartphone')

        if not JNIUS_AVAILABLE:
            Logger.error('jnius not available for Android restart')
            return

        try:
            # Get Android classes
            Intent = autoclass('android.content.Intent')
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            System = autoclass('java.lang.System')

            # Create restart intent
            activity = PythonActivity.mActivity
            intent = Intent(activity.getApplicationContext(), PythonActivity)
            intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            intent.setFlags(Intent.FLAG_ACTIVITY_CLEAR_TASK)

            # Start new activity and exit current one
            activity.startActivity(intent)
            System.exit(0)

        except Exception as e:
            Logger.error(f'Failed to restart Android app: {e}')
            raise

    # ==================== UTILITY FUNCTIONS ====================

    def bind_key(self, key, callback):
        """
        Bind a keyboard shortcut for manual reload.

        Enables Ctrl+R functionality when using scrcpy for Android debugging.

        Args:
            key: The keycode to bind (e.g., CTRL_R_KEYCODE)
            callback: The function to call when the key combination is pressed
        """

        def _on_keyboard(window, keycode, scancode, codepoint, modifier_keys):
            pressed_modifiers = set(modifier_keys)

            if key == keycode and 'ctrl' in pressed_modifiers:
                return callback()

        Window.bind(on_keyboard=_on_keyboard)

    def get_hash_of_file(self, file_name):
        """
        Calculate MD5 hash of a file for change detection.

        Args:
            file_name: Path to the file to hash

        Returns:
            MD5 hash string or None if file cannot be read
        """
        try:
            with open(file_name, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except (FileNotFoundError, PermissionError) as e:
            Logger.warning(f'Unable to hash file {file_name}: {e}')
            return None

    def _unregister_factory_from_module(self, module):
        """
        Unregister all Factory classes from a specific module.

        Used during hot reload to clean up widget registrations
        before reloading the module.

        Args:
            module: The module name to unregister classes from
        """
        to_remove = [x for x in F.classes if F.classes[x]['module'] == module]

        # Check class names by module attribute
        for class_name in F.classes:
            cls = F.classes[class_name]['cls']
            if not cls:
                continue
            if getattr(cls, '__module__', None) == module:
                to_remove.append(class_name)

        # Remove all identified classes
        for name in set(to_remove):
            del F.classes[name]

    def recompile_main(self):
        """
        Recompile main.py on Android to ensure latest bytecode.

        Removes existing main.pyc and recompiles main.py to prevent
        Android from using stale bytecode during hot reload.
        """
        if platform != 'android':
            return

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
        Comprehensive hot reload for KV files, services, and Python modules.

        Handles multiple types of reload scenarios:
        - Service file changes (triggers app restart)
        - Full reload files (triggers app restart)
        - Main.py changes (triggers app restart)
        - KV file changes (hot reload)
        """
        Logger.info('Reloading kv files')

        # Check for service updates that require app restart
        if self._check_and_handle_service_updates():
            return

        # Check for full reload file updates
        if self._check_full_reload_files():
            return

        # Check for main.py changes
        if self._check_main_py_changes():
            return

        # Handle KV file hot reload
        self._handle_kv_file_reload()

        # Rebuild the UI
        self.build_root_and_add_to_window()

    def _check_and_handle_service_updates(self):
        """
        Check for service file changes and handle service restarts.

        Returns:
            bool: True if app restart was triggered, False otherwise
        """
        for service_name, file_name in zip(config.SERVICE_NAMES, config.SERVICE_FILES):
            if self.get_hash_of_file(file_name) != self.service_files_hashes[file_name]:
                Logger.info(f'Service {service_name} has been updated')

                # Handle service file recompilation
                self._recompile_service_file(file_name)

                # Stop the service
                if self._stop_android_service(service_name):
                    self.restart_app_on_android()
                    return True

        return False

    def _recompile_service_file(self, file_name):
        """Recompile a service file by removing bytecode and recompiling."""
        compiled_file = f'{file_name}c'
        if os.path.exists(compiled_file):
            os.remove(compiled_file)

        subprocess.run(
            f'python -m compileall {file_name}',
            shell=True,
            check=True,
        )

    def _stop_android_service(self, service_name):
        """
        Stop an Android service.

        Returns:
            bool: True if service was stopped successfully, False otherwise
        """
        Logger.info(f'Stopping service {service_name}')

        if not JNIUS_AVAILABLE:
            Logger.error('jnius not available for service management')
            return False

        try:
            mActivity = autoclass('org.kivy.android.PythonActivity').mActivity
            context = mActivity.getApplicationContext()
            service_class_name = (
                str(context.getPackageName()) + '.Service' + service_name
            )
            service = autoclass(service_class_name)
            service.stop(mActivity)
            return True
        except Exception as e:
            Logger.error(f'Failed to stop service {service_name}: {e}')
            return False

    def _check_full_reload_files(self):
        """
        Check for changes in files that require full app reload.

        Returns:
            bool: True if app restart was triggered, False otherwise
        """
        for file_name in config.FULL_RELOAD_FILES:
            if not os.path.exists(file_name):
                Logger.info(f'Reloader: File {file_name} does not exist. Skipping!')
                continue

            if file_name not in self.full_reload_file_hashes:
                self.full_reload_file_hashes[file_name] = self.get_hash_of_file(
                    file_name
                )
                continue

            current_hash = self.get_hash_of_file(file_name)
            if current_hash != self.full_reload_file_hashes[file_name]:
                Logger.info(
                    f'Reloader: File {file_name} has been updated. Restarting app...'
                )
                self.restart_app_on_android()
                return True

        return False

    def _check_main_py_changes(self):
        """
        Check for main.py changes that require app restart.

        Returns:
            bool: True if app restart was triggered, False otherwise
        """
        main_py_file_path = os.path.join(os.getcwd(), 'main.py')

        if os.path.exists(main_py_file_path):
            current_hash = self.get_hash_of_file(main_py_file_path)
            if current_hash != self.main_py_hash:
                Logger.info('main.py changed, restarting app')
                self.restart_app_on_android()
                return True

        return False

    def _handle_kv_file_reload(self):
        """Handle hot reload of KV files without app restart."""
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
                Logger.info(f'Reloading KV file: {file_name}')
                Builder.unload_file(file_name)
                Builder.load_file(file_name)

            # Update stored hashes
            self.kv_files_hashes = current_kv_files_hashes

    # ==================== PYTHON MODULE MANAGEMENT ====================

    def unload_python_file(self, filename, module):
        """
        Unload a Python file from the module system for hot reload.

        Args:
            filename: The file path to unload
            module: The module name to unload

        Returns:
            The module object if successfully unloaded, None otherwise
        """
        if module == 'main':
            return None

        if module in sys.modules:
            full_path = os.path.join(os.getcwd(), filename)
            F.unregister_from_filename(full_path)
            self._unregister_factory_from_module(module)
            return sys.modules[module]

        return None

    def gather_files_to_reload(self, folders, recursive=False):
        """
        Gather Python files from specified folders for reloading.

        Args:
            folders: List of folder paths to search
            recursive: Whether to search folders recursively

        Returns:
            List of Python file paths to reload
        """
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
        """
        Process a list of files for unloading and collect modules to reload.

        Args:
            files: List of file paths to process

        Returns:
            List of module objects that need to be reloaded
        """
        modules_to_reload = []
        for filename in files:
            module_name = os.path.relpath(filename).replace(os.path.sep, '.')[:-3]
            to_reload = self.unload_python_file(filename, module_name)
            if to_reload is not None:
                modules_to_reload.append(to_reload)

        return modules_to_reload

    def unload_python_files_on_android(self):
        """
        Unload and reload Python files on Android with optimized batch processing.

        Gathers files from various watched locations, unloads them, and performs
        a multi-pass reload to handle module dependencies correctly.
        """
        files_to_reload = self._gather_all_watched_files()
        modules_to_reload = self.process_unload_files(files_to_reload)

        # Performance optimization: Only reload if we have modules to reload
        if not modules_to_reload:
            Logger.info('Reloader: No modules to reload, skipping reload step')
            return

        self._perform_module_reload(modules_to_reload)

    def _gather_all_watched_files(self):
        """Gather all files from all watched locations."""
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

        return files_to_reload

    def _perform_module_reload(self, modules_to_reload):
        """
        Perform multi-pass module reloading to handle dependencies.

        We need multiple passes because module dependencies may require
        a specific loading order that we can't determine in advance.
        """
        Logger.info(
            f'Reloader: Reloading {len(modules_to_reload)} modules '
            f'({MODULE_RELOAD_PASSES} passes)'
        )

        for pass_num in range(MODULE_RELOAD_PASSES):
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
        Initialize and start the TCP server for receiving hot reload updates.

        The server runs in the background to receive file updates from
        the desktop development environment.
        """
        self.nursery.start_soon(self.start_async_server)

    async def start_async_server(self):
        """
        Start the async TCP server to listen for hot reload updates.

        The server listens on the configured port and automatically
        discovers the device's IP address for network communication.
        """
        PORT = config.RELOADER_PORT

        try:
            # Discover device IP address
            device_ip = self._get_device_ip()
            Logger.info(f'Smartphone IP: {device_ip}')

            # Start TCP server
            await trio.serve_tcp(self.data_receiver, PORT)

        except Exception as e:
            self._log_server_startup_error(e)

    def _get_device_ip(self):
        """
        Get the device's IP address by connecting to a remote server.

        Returns:
            str: The device's local IP address
        """
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect((DNS_SERVER_IP, DNS_SERVER_PORT))
            return probe.getsockname()[0]

    def _log_server_startup_error(self, error):
        """Log detailed error information when server fails to start."""
        Logger.info(
            'It was not possible to start the server, check if the '
            'phone is connected to the same network as the computer'
        )
        Logger.info(
            'Another possible cause is that the port is already in use '
            'by another app. Check if the port is free and try again'
        )
        Logger.info(f'Error details: {error}')

    async def data_receiver(self, data_stream):
        """
        Handle incoming data from the desktop development environment.

        Receives a zip file containing the updated application code,
        unpacks it, and triggers a hot reload of the application.

        Args:
            data_stream: The incoming TCP data stream
        """
        Logger.info('Reloader: ************** SERVER **************')
        Logger.info('Reloader: Server started: receiving data from computer...')

        try:
            # Receive and save the zip file
            zip_file_path = await self._receive_zip_file(data_stream)

            # Process the received update
            await self._process_app_update(zip_file_path)

        except Exception as e:
            self._log_server_error(e)

    async def _receive_zip_file(self, data_stream):
        """
        Receive zip file data from the TCP stream.

        Args:
            data_stream: The incoming TCP data stream

        Returns:
            str: Path to the saved zip file
        """
        zip_file_path = os.path.join(os.getcwd(), 'app_copy.zip')

        with open(zip_file_path, 'wb') as zip_file:
            async for data in data_stream:
                Logger.info('Reloader: Server: received data')
                Logger.info(f'Reloader: Data size: {len(data)}')
                Logger.info('Reloader: Server: connection closed')
                zip_file.write(data)

        return zip_file_path

    async def _process_app_update(self, zip_file_path):
        """
        Process the received app update and trigger reload.

        Args:
            zip_file_path: Path to the received zip file
        """
        Logger.info('Reloader: Finished receiving all files from computer')
        Logger.info('Reloader: Unpacking app')

        # Log zip file information
        zip_file_size = os.path.getsize(zip_file_path)
        Logger.info(f'Reloader: Zip file size: {zip_file_size}')

        # Extract the update
        shutil.unpack_archive(zip_file_path)
        os.remove(zip_file_path)

        Logger.info('Reloader: App updated, restarting app for refresh')
        Logger.info('Reloader: ************** END SERVER **************')

        # Trigger hot reload
        self.unload_python_files_on_android()
        if self.__module__ != '__main__':
            importlib.reload(importlib.import_module(self.__module__))
        self.reload_kv()

    def _log_server_error(self, error):
        """Log server error with full traceback."""
        Logger.info(f'Reloader: Server crashed: {error!r}')
        Logger.info(
            'Full exception:',
            ''.join(traceback.format_exception(*sys.exc_info())),
        )
