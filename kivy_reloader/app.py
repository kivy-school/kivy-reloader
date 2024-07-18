import os
import subprocess

import trio
from kivy.factory import Factory as F
from kivy.lang import Builder
from kivy.logger import Logger
from kivy.utils import platform

from .config import config
from .utils import get_kv_files_paths


class Reloader(F.Screen):
    pass


# fmt: off
kv = Builder.load_string("""
<Reloader>:
    screen_manager: screen_manager
    ScreenManager:
        id: screen_manager
"""
)
# fmt: on

if platform != "android":
    import inspect
    import logging
    from shutil import copytree, ignore_patterns, rmtree

    from kaki.app import App
    from kivy.core.window import Window

    from .utils import get_auto_reloader_paths

    Window.always_on_top = True
    logging.getLogger("watchdog").setLevel(logging.ERROR)

    # from .constants import FOLDERS_AND_FILES_TO_EXCLUDE_FROM_PHONE

    # Desktop BaseApp
    class App(App):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            self.DEBUG = 1
            self.AUTORELOADER_PATHS: list = get_auto_reloader_paths()
            self.HOT_RELOAD_ON_PHONE: bool = config.HOT_RELOAD_ON_PHONE
            self.KV_FILES: list = get_kv_files_paths()

        async def main(self) -> None:
            """
            Starts the async Kivy app
            """
            async with trio.open_nursery() as nursery:
                Logger.info("Reloader: Starting Async Kivy app")
                server = self
                server.nursery = nursery
                await server.async_run("trio")

        def build_app(self):
            """
            Used internally by Kaki
            """
            return self.build_and_reload()

        def build_and_reload(self):
            pass

        def rebuild(self, *args, **kwargs):
            Logger.debug("Reloader: Rebuild the application")
            first = kwargs.get("first", False)
            try:
                if not first:
                    self.unload_app_dependencies()

                Builder.rulectx = {}

                self.load_app_dependencies()
                self.set_widget(None)
                self.approot = self.build_app()
                self.set_widget(self.approot)
                self.apply_state(self.state)
                if self.HOT_RELOAD_ON_PHONE:
                    self.send_app_to_phone()
            except Exception as e:
                import traceback

                Logger.exception("Reloader: Error when building app")
                self.set_error(repr(e), traceback.format_exc())
                if not self.DEBUG and self.RAISE_ERROR:
                    raise

        def clear_temp_folder_and_zip_file(self, folder, zip_file):
            if os.path.exists(folder):
                rmtree(folder)
            if os.path.exists(zip_file):
                os.remove(zip_file)

        def send_app_to_phone(self):
            # Creating a copy of the files on `temp` folder
            source = os.getcwd()
            destination = os.path.join(os.getcwd(), "temp")
            zip_file = os.path.join(os.getcwd(), "app_copy.zip")

            self.clear_temp_folder_and_zip_file(destination, zip_file)

            copytree(
                source,
                destination,
                ignore=ignore_patterns(
                    *config.FOLDERS_AND_FILES_TO_EXCLUDE_FROM_PHONE,
                ),
            )

            # Zipping all files inside `temp` folder, except the `temp` folder itself
            subprocess.run(
                f"cd {destination} && zip -r ../app_copy.zip ./* -x ./temp",
                shell=True,
                stdout=subprocess.DEVNULL,
            )

            # Sending the zip file to the phone
            path_of_current_file = inspect.currentframe().f_back
            path_of_send_app = os.path.join(
                os.path.dirname(
                    os.path.abspath(path_of_current_file.f_code.co_filename)
                ),
                "send_app_to_phone.py",
            )
            subprocess.run(f"python {path_of_send_app}", shell=True)

            # Deleting the temp folder and the zip file
            self.clear_temp_folder_and_zip_file(destination, zip_file)

        def _filename_to_module(self, filename: str):
            rootpath = self.get_root_path()
            if filename.startswith(rootpath):
                filename = filename[len(rootpath) :]

            if platform == "macosx":
                prefix = os.sep
            else:
                prefix = os.path.sep

            if filename.startswith(prefix):
                filename = filename[1:]
            module = filename[:-3].replace(prefix, ".")
            return module

else:
    # Android BaseApp
    import hashlib
    import importlib
    import shutil
    import sys

    from kivy.app import App

    class App(App):
        async def main(self) -> None:
            async with trio.open_nursery() as nursery:
                Logger.info("Starting Async Kivy app - Kivy Reloader")
                server = self
                server.nursery = nursery
                await server.async_run("trio")

        def build(self):
            main_py_file_path = os.path.join(os.getcwd(), "main.py")
            if os.path.exists(main_py_file_path):
                self.main_py_hash = self.get_hash_of_file(main_py_file_path)
            else:
                self.main_py_hash = None
            self.kv_files_hashes = {
                file_name: self.get_hash_of_file(file_name)
                for file_name in get_kv_files_paths()
            }
            self.service_files_hashes = {
                file_name: self.get_hash_of_file(file_name)
                for file_name in config.SERVICE_FILES
            }
            self.initialize_server()
            self.recompile_main()

            return self.build_and_reload()

        def build_and_reload(self):
            pass

        def restart_app_on_android(self):
            Logger.info("Restarting the app on smartphone")

            from jnius import autoclass

            Intent = autoclass("android.content.Intent")
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            System = autoclass("java.lang.System")

            activity = PythonActivity.mActivity
            intent = Intent(activity.getApplicationContext(), PythonActivity)
            intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            intent.setFlags(Intent.FLAG_ACTIVITY_CLEAR_TASK)
            activity.startActivity(intent)
            System.exit(0)

        def get_hash_of_file(self, file_name):
            """
            Returns the hash of the file using md5 hash
            """
            with open(file_name, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()

        def _unregister_factory_from_module(self, module):
            to_remove = [x for x in F.classes if F.classes[x]["module"] == module]

            # check class name
            for x in F.classes:
                cls = F.classes[x]["cls"]
                if not cls:
                    continue
                if getattr(cls, "__module__", None) == module:
                    to_remove.append(x)

            for name in set(to_remove):
                del F.classes[name]

        def reload_kv(self, *args):
            """
            Hot reloading kv files on Android
            """
            Logger.info("Reloading kv files")
            main_py_file_path = os.path.join(os.getcwd(), "main.py")

            # reload the service files
            should_restart_app_on_android = False
            for service_name, file_name in zip(
                config.SERVICE_NAMES, config.SERVICE_FILES
            ):
                if (
                    self.get_hash_of_file(file_name)
                    != self.service_files_hashes[file_name]
                ):
                    Logger.info(f"Service {service_name} has been updated")
                    if os.path.exists(f"{file_name}c"):
                        # remove the compiled service file
                        os.remove(f"{file_name}c")

                    # recopiling the service file
                    subprocess.run(f"python -m compileall {file_name}", shell=True)

                    # stop the service
                    Logger.info(f"Stopping service {service_name}")
                    from jnius import autoclass

                    mActivity = autoclass("org.kivy.android.PythonActivity").mActivity
                    context = mActivity.getApplicationContext()
                    SERVICE_NAME = (
                        str(context.getPackageName()) + ".Service" + service_name
                    )
                    service = autoclass(SERVICE_NAME)
                    service.stop(mActivity)
                    should_restart_app_on_android = True

            if should_restart_app_on_android:
                self.restart_app_on_android()
                return

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

            self.root.clear_widgets()
            root = self.build_and_reload()
            root.do_layout()
            self.root.add_widget(root)

        def unload_python_file(self, filename, module):
            if module in sys.modules:
                full_path = os.path.join(os.getcwd(), filename)
                F.unregister_from_filename(full_path)
                self._unregister_factory_from_module(module)
                importlib.reload(sys.modules[module])

        def unload_python_files_on_android(self):
            for folder in config.WATCHED_FOLDERS_RECURSIVELY:
                for root, _, files in os.walk(folder):
                    for file in files:
                        if file.endswith(".py"):
                            filename = os.path.join(root, file)
                            module = filename.replace("/", ".")[:-3]
                            self.unload_python_file(filename, module)

            for folder in config.WATCHED_FOLDERS:
                for file in os.listdir(folder):
                    if file.endswith(".py"):
                        filename = os.path.join(folder, file)
                        module = filename.replace("/", ".")[:-3]
                        self.unload_python_file(filename, module)

            for file in config.WATCHED_FILES:
                filename = os.path.join(os.getcwd(), file)
                module = filename.replace("/", ".")[:-3]
                self.unload_python_file(filename, module)

        def recompile_main(self):
            if platform == "android":
                files = os.listdir()
                if "main.pyc" in files and "main.py" in files:
                    Logger.info("Deleting main.pyc")
                    os.remove("main.pyc")
                    Logger.info("Compiling main.py")
                    main_py_path = os.path.join(os.getcwd(), "main.py")
                    subprocess.run(f"python -m compileall {main_py_path}", shell=True)

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
            import socket

            try:
                PORT = 8050
                self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.s.connect(("8.8.8.8", 80))

                IP = self.s.getsockname()[0]
                Logger.info(f"Smartphone IP: {IP}")

                await trio.serve_tcp(self.data_receiver, PORT)
            except Exception as e:
                Logger.info(
                    "It was not possible to start the server, check if the phone is connected to the same network as the computer"
                )
                Logger.info(
                    "Another possible cause is that the port is already in use by another app. Check if the port is free and try again"
                )
                Logger.info(e)

        async def data_receiver(self, data_stream):
            """
            When data is received from the computer
            it is saved in a zip file
            and then unpacked
            and the app is reloaded
            """
            Logger.info("Reloader: ************** SERVER **************")
            Logger.info("Reloader: Server started: receiving data from computer...")

            try:
                zip_file_path = os.path.join(os.getcwd(), "app_copy.zip")
                with open(zip_file_path, "wb") as myzip:
                    async for data in data_stream:
                        Logger.info("Reloader: Server: received data")
                        Logger.info(f"Reloader: Data size: {len(data)}")
                        Logger.info("Reloader: Server: connection closed")
                        myzip.write(data)

                Logger.info("Reloader: Finished receiving all files from computer")
                Logger.info("Reloader: Unpacking app")

                # first print the size of the zip file
                zip_file_size = os.path.getsize(zip_file_path)
                Logger.info(f"Reloader: Zip file size: {zip_file_size}")

                shutil.unpack_archive(zip_file_path)

                # Deleting the zip file
                os.remove(zip_file_path)

                # Recompiling main.py
                # Logger.info("Recompiling main.py")
                # self.recompile_main()

                Logger.info("Reloader: App updated, restarting app for refresh")
                Logger.info("Reloader: ************** END SERVER **************")
                self.unload_python_files_on_android()
                self.reload_kv()
            except Exception as e:
                import traceback

                Logger.info(f"Reloader: Server crashed: {e!r}")
                Logger.info(
                    "Full exception:",
                    "".join(traceback.format_exception(*sys.exc_info())),
                )