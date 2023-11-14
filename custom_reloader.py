import importlib
import os
import shutil
import subprocess
import sys
from shutil import copytree, ignore_patterns, rmtree

import trio
from kivy.app import App
from kivy.factory import Factory as F
from kivy.lang import Builder
from kivy.utils import platform

# fmt: off
kv = Builder.load_string("""
<Reloader>:
    screen_manager: screen_manager
    ScreenManager:
        id: screen_manager
"""
)
# fmt: on


class Reloader(F.Screen):
    def __init__(self, initialize_server=True):
        super().__init__()
        self.app = App.get_running_app()
        if initialize_server and platform == "android":
            self.initialize_server()
            self.recompile_main()

    def recompile_main(self):
        if platform == "android":
            files = os.listdir()
            if "main.pyc" in files and "main.py" in files:
                print("Deleting main.pyc")
                os.remove("main.pyc")
                print("Compiling main.py")
                main_py_path = os.path.join(os.getcwd(), "main.py")
                subprocess.run(f"python -m compileall {main_py_path}", shell=True)

    def initialize_server(self):
        self.app.nursery.start_soon(self.start_async_server)

    async def start_async_server(self):
        import socket

        try:
            PORT = 8050
            self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.s.connect(("8.8.8.8", 80))

            IP = self.s.getsockname()[0]
            print(f"Smartphone IP: {IP}")

            await trio.serve_tcp(self.data_receiver, PORT)
        except Exception as e:
            print(
                "It was not possible to start the server, check if the phone is connected to the same network as the computer"
            )
            print(
                "Another possible cause is that the port is already in use by another app. Check if the port is free and try again"
            )
            print(e)

    async def data_receiver(self, data_stream):
        print("************** SERVER **************")
        print("Server started: receiving data from computer...")

        try:
            zip_file_path = os.path.join(os.getcwd(), "app_copy.zip")
            with open(zip_file_path, "wb") as myzip:
                async for data in data_stream:
                    print(f"Server: received data")
                    print(f"Data size: {len(data)}")
                    print(f"Server: connection closed")
                    myzip.write(data)

            print("Finished receiving all files from computer")
            print("Unpacking app")

            # first print the size of the zip file
            zip_file_size = os.path.getsize(zip_file_path)
            print(f"Zip file size: {zip_file_size}")

            shutil.unpack_archive(zip_file_path)

            # Deleting the zip file
            os.remove(zip_file_path)

            # Recompiling main.py
            # print("Recompiling main.py")
            # self.recompile_main()

            print("App updated, restarting app for refresh")
            print("************** END SERVER **************")
            self.app.reload_kv()
        except Exception as e:
            print(f"Server: crashed: {e!r}")


if platform != "android":
    import logging

    from kaki.app import App
    from kivy.logger import Logger

    from constants import FOLDERS_AND_FILES_TO_EXCLUDE_FROM_PHONE
    from utils import get_auto_reloader_paths, get_kv_files_paths

    logging.getLogger("watchdog").setLevel(logging.ERROR)

    # Desktop BaseApp
    class BaseApp(App):
        DEBUG = 1
        should_send_app_to_phone = True
        AUTORELOADER_PATHS = get_auto_reloader_paths()
        KV_FILES = get_kv_files_paths()

        def build_app(self):
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
                if self.should_send_app_to_phone:
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
                    *FOLDERS_AND_FILES_TO_EXCLUDE_FROM_PHONE,
                ),
            )

            # Zipping all files inside `temp` folder, except the `temp` folder itself
            subprocess.run(
                f"cd {destination} && zip -r ../app_copy.zip ./* -x ./temp",
                shell=True,
                stdout=subprocess.DEVNULL,
            )

            # Sending the zip file to the phone
            subprocess.run("python send_app_to_phone.py", shell=True)

            # Deleting the temp folder and the zip file
            self.clear_temp_folder_and_zip_file(destination, zip_file)

        def _filename_to_module(self, filename):
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

    from utils import get_kv_files_paths

    class BaseApp(App):
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

            return self.build_and_reload()

        def restart_app_on_android(self):
            print("Restarting the app on smartphone")

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
            Returns the hash of the file
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
            main_py_file_path = os.path.join(os.getcwd(), "main.py")

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
            root = self.build_and_reload(initialize_server=False)
            self.root.add_widget(root)
            root.do_layout()

        def unload_python_files_on_android(self, screen_module_in_str):
            if f"screens.{screen_module_in_str}" in sys.modules:
                # Module already imported, reloading
                filename = os.path.join(
                    os.getcwd(), "screens", f"{screen_module_in_str}.py"
                )
                F.unregister_from_filename(filename)
                module = f"screens.{screen_module_in_str}"
                self._unregister_factory_from_module(module)
                importlib.reload(sys.modules[module])
