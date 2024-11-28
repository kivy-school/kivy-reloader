import os

os.environ["KIVY_LOG_MODE"] = "MIXED"

import importlib
import subprocess
import sys

import trio
from kivy.base import async_runTouchApp
from kivy.core.window import Window
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


def infiniteloop():
    """
    This is unironically required to keep the original host python process open on windows. This is because os.spawnv does not exist on Windows and so exiting the host early means that KeyboardInterrupt will not be caught by child processes. (for example, u have a reloader open, you ctrl s to reload/start a new (child) process, then the old process closes. when you ctrl+c the original process does not exist to send KeyboardInterrupt to the children whereas in linux spawnv children get access to the parent's env and also recieve ctrl+c KeyboardInterrupts).

    You need to keep the host open so that when KeyboardInterrupt happens, it also gets sent to the child.
    """
    import time

    while True:
        time.sleep(10000)


if platform != "android":
    import inspect
    import logging
    from fnmatch import fnmatch
    from shutil import copytree, ignore_patterns, rmtree

    from kaki.app import App
    from kivy.clock import Clock, mainthread
    from kivy.core.window import Window

    from .utils import get_auto_reloader_paths

    Window.always_on_top = True
    logging.getLogger("watchdog").setLevel(logging.ERROR)

    # Desktop BaseApp
    class App(App):
        subprocesses = []

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.built = False
            self.root = None
            self.DEBUG = 1
            self.AUTORELOADER_PATHS: list = get_auto_reloader_paths()
            self.HOT_RELOAD_ON_PHONE: bool = config.HOT_RELOAD_ON_PHONE
            self.KV_FILES: list = get_kv_files_paths()
            self._build()
            if (
                platform == "win"
            ):  # this is to make sure last spawned process on windows calls for parent Python process to be exited by PID when window is closed normally
                Window.bind(on_request_close=self.on_request_close)
                # https://stackoverflow.com/questions/54501099/how-to-run-a-method-on-the-exit-of-a-kivy-app

        def on_request_close(self, *args, **kwargs):
            # if this is a child process, you must stop the initial process, check argv for the PID
            # only on windows

            if platform == "win" and len(sys.argv) > 1:
                killstring = f"taskkill /F /PID {sys.argv[1]}"
                Logger.info(
                    f"Reloader: Detected request close on Windows. Closing original host Python PID: {sys.argv[1]}"
                )
                os.system(killstring)

        def _restart_app(self, mod):
            _has_execv = sys.platform != "win32"
            original_argv = sys.argv
            cmd = [sys.executable] + original_argv
            if not _has_execv:
                for p in self.subprocesses:
                    p.terminate()
                    p.wait()
                if len(sys.argv) <= 1:
                    cmd.append(str(os.getpid()))
                p = subprocess.Popen(cmd, shell=False)
                self.subprocesses.append(p)
                if len(sys.argv) > 1:
                    # children will have the host Python's PID in the argv, these are not needed and must exit to prevent extra python processes
                    sys.exit(0)
                else:
                    # the main process will have a single arg in argv, but u need to keep it open so you can intercept KeyboardInterrupt
                    self.root_window.close()
                    infiniteloop()
            else:
                # linux spawnv
                try:
                    os.execv(sys.executable, cmd)
                except OSError:
                    os.spawnv(os.P_NOWAIT, sys.executable, cmd)
                    os._exit(0)

        def _build(self):
            Logger.info("Reloader: Building the first screen")
            if self.DEBUG:
                Logger.info("Kaki: Debug mode activated")
                self.enable_autoreload()
                self.patch_builder()
                self.listen_for_reload()

            if self.FOREGROUND_LOCK:
                self.prepare_foreground_lock()

            self.state = {}

            self.rebuild(first=True)

            if self.IDLE_DETECTION:
                self.install_idle(timeout=self.IDLE_TIMEOUT)

        def listen_for_reload(self):
            """
            Reload the app when pressing F5 or Ctrl+R on desktop
            """

            def _on_keyboard(window, keycode, scancode, codepoint, modifier_keys):
                pressed_modifiers = set(modifier_keys)

                if keycode == 286 or (keycode == 114 and "ctrl" in pressed_modifiers):
                    return self.rebuild()

            Window.bind(on_keyboard=_on_keyboard)

        def build_root_and_add_to_window(self):
            Logger.info("Reloader: Building root widget and adding to window")
            if self.root is not None:
                self.root.clear_widgets()

                while Window.children:
                    Window.remove_widget(Window.children[0])

            Clock.schedule_once(self.delayed_build)

        def delayed_build(self, *args):
            self.root = self.build()

            if self.root:
                if not isinstance(self.root, F.Widget):
                    Logger.critical("App.root must be an _instance_ of Widget")
                    raise Exception("Invalid instance in App.root")

                Window.add_widget(self.root)

        def _run_prepare(self):
            if not self.built:
                self.load_config()
                self.load_kv(filename=self.kv_file)

            # Check if the window is already created
            from kivy.base import EventLoop

            window = EventLoop.window
            if window:
                self._app_window = window
                window.set_title(self.get_application_name())
                icon = self.get_application_icon()
                if icon:
                    window.set_icon(icon)
                self._install_settings_keys(window)
            else:
                Logger.critical(
                    "Application: No window is created." " Terminating application run."
                )
                return

            self.dispatch("on_start")

        async def async_run(self, async_lib="trio"):
            async with trio.open_nursery() as nursery:
                Logger.info("Reloader: Starting Async Kivy app")
                self.nursery = nursery
                self._run_prepare()
                await async_runTouchApp(async_lib=async_lib)
                self._stop()
                nursery.cancel_scope.cancel()

        def unload_python_file(self, filename, module_name):
            if module_name == "main":
                return

            if module_name in sys.modules:
                full_path = os.path.join(os.getcwd(), filename)
                F.unregister_from_filename(full_path)
                self._unregister_factory_from_module(module_name)
                importlib.reload(sys.modules[module_name])

        def unload_files(self, files):
            for filename in files:
                module_name = os.path.relpath(filename).replace(os.path.sep, ".")[:-3]
                self.unload_python_file(filename, module_name)

        def unload_python_files_on_desktop(self):
            files_to_unload = []

            # Gather files from recursively watched folders
            for folder in config.WATCHED_FOLDERS_RECURSIVELY:
                for root, _, files in os.walk(folder):
                    files_to_unload.extend(
                        os.path.join(root, file)
                        for file in files
                        if file.endswith(".py")
                    )

            # Gather files from watched folders
            for folder in config.WATCHED_FOLDERS:
                files_to_unload.extend(
                    os.path.join(folder, file)
                    for file in os.listdir(folder)
                    if file.endswith(".py")
                )

            # Gather individual watched files
            files_to_unload.extend(
                os.path.join(os.getcwd(), file) for file in config.WATCHED_FILES
            )

            # Gather files that require full reload
            files_to_unload.extend(
                os.path.join(os.getcwd(), file) for file in config.FULL_RELOAD_FILES
            )

            # Process all gathered files
            self.unload_files(files_to_unload)

        def load_app_dependencies(self):
            for path in self.KV_FILES:
                path = os.path.realpath(path)
                if path not in Builder.files:
                    Builder.load_file(path)
            for name, module in self.CLASSES.items():
                F.register(name, module=module)

        def rebuild(self, dt=None, first=False, *args, **kwargs):
            Logger.info("Reloader: Rebuilding the application")

            try:
                if not first:
                    self.unload_app_dependencies()
                    self.unload_python_files_on_desktop()
                    importlib.reload(importlib.import_module(self.__module__))
                    Builder.rulectx = {}
                    self.load_app_dependencies()

                self.build_root_and_add_to_window()

                self.apply_state(self.state)  # TODO
                # can't hot reload on windows directly -- need WSL
                if platform == "win":
                    Logger.warning(
                        "Reloader: Reloading on Android requires WSL installation: https://kivyschool.com/kivy-reloader-WindowsWSL/"
                    )
                elif self.HOT_RELOAD_ON_PHONE:
                    self.send_app_to_phone()
            except Exception as e:
                import traceback

                Logger.exception("Reloader: Error when building app")
                self.set_error(repr(e), traceback.format_exc())
                if not self.DEBUG and self.RAISE_ERROR:
                    raise

        def enable_autoreload(self):
            if platform != "win":
                super().enable_autoreload()
                return

            try:
                from watchdog.events import (
                    FileSystemEventHandler,
                    PatternMatchingEventHandler,
                )
                from watchdog.observers import Observer
            except ImportError:
                Logger.warn("Reloader: Unavailable, watchdog is not installed")
                return

            Logger.info("Reloader: Autoreloader activated")
            rootpath = self.get_root_path()
            folder_handler = FileSystemEventHandler()
            file_handler = PatternMatchingEventHandler()

            folder_handler.dispatch = self._reload_from_watchdog
            file_handler.dispatch = self._reload_from_watchdog

            folder_observer = Observer()
            file_observer = Observer()

            patterns = [
                os.path.abspath(os.path.join(rootpath, path))
                for path in config.WATCHED_FILES + config.FULL_RELOAD_FILES
            ]
            file_handler._patterns = patterns

            dirs_to_watch_from_watched_files = list(
                set([os.path.dirname(path) for path in patterns])
            )

            for dir in dirs_to_watch_from_watched_files:
                file_observer.schedule(file_handler, dir, **{"recursive": False})

            for path in self.AUTORELOADER_PATHS:
                path, options = path

                # continue if it is not a directory
                if not os.path.isdir(os.path.join(rootpath, path)):
                    continue

                folder_observer.schedule(
                    folder_handler, os.path.join(rootpath, path), **options
                )

            file_observer.start()
            folder_observer.start()

        @mainthread
        def _reload_from_watchdog(self, event):
            from watchdog.events import FileModifiedEvent

            if not isinstance(event, FileModifiedEvent):
                return

            if not os.path.exists(event.src_path):
                return

            for path in config.FULL_RELOAD_FILES:
                full_path = os.path.join(self.get_root_path(), path)
                if fnmatch(event.src_path, full_path):
                    Logger.info(f"Reloader: Full reload triggered by {event.src_path}")
                    mod = sys.modules[self.__class__.__module__]
                    mod_filename = os.path.realpath(mod.__file__)
                    self._restart_app(mod_filename)
                    break

            for pat in config.DO_NOT_WATCH_PATTERNS:
                if fnmatch(event.src_path, pat):
                    return
                if fnmatch(event.src_path, os.path.join(os.getcwd(), pat)):
                    return

            Logger.trace(f"Reloader: Event received {event.src_path}")
            if event.src_path.endswith(".py"):
                # source changed, reload it
                try:
                    Builder.unload_file(event.src_path)
                    self._reload_py(event.src_path)
                except Exception as e:
                    import traceback

                    self.set_error(repr(e), traceback.format_exc())
                    return

            Logger.debug(f"Reloader: Triggered by {event}")
            Clock.unschedule(self.rebuild)
            Clock.schedule_once(self.rebuild, 0.1)

        @mainthread
        def set_error(self, exc, tb=None):
            lbl = F.Label(
                size_hint=(1, None),
                padding_y=150,
                text_size=(Window.width - 100, None),
                text="{}\n\n{}".format(exc, tb or ""),
            )
            lbl.texture_update()
            lbl.height = lbl.texture_size[1]
            sv = F.ScrollView(
                size_hint=(1, 1),
                pos_hint={"x": 0, "y": 0},
                do_scroll_x=False,
                scroll_y=0,
            )
            sv.add_widget(lbl)
            while Window.children:
                Window.remove_widget(Window.children[0])
            Window.add_widget(sv)

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
    import shutil

    from kivy.app import App
    from kivy.clock import Clock

    class App(App):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            main_py_file_path = os.path.join(os.getcwd(), "main.py")

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

        def bind_key(self, key, callback):
            """
            Reload the app when pressing Ctrl+R from scrcpy
            """

            def _on_keyboard(window, keycode, scancode, codepoint, modifier_keys):
                pressed_modifiers = set(modifier_keys)

                if key == keycode and "ctrl" in pressed_modifiers:
                    return callback()

            Window.bind(on_keyboard=_on_keyboard)

        async def async_run(self, async_lib="trio"):
            async with trio.open_nursery() as nursery:
                Logger.info("Reloader: Starting Async Kivy app")
                self.nursery = nursery
                self.initialize_server()
                self._run_prepare()
                await async_runTouchApp(async_lib=async_lib)
                self._stop()
                nursery.cancel_scope.cancel()

        def restart_app_on_android(self):
            Logger.info("Restarting the app on smartphone")

            from jnius import autoclass  # type: ignore

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
                    from jnius import autoclass  # type: ignore

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

            for file_name in config.FULL_RELOAD_FILES:
                if not os.path.exists(file_name):
                    Logger.info(
                        f"Reloader: File {file_name} does not exist. Skipping..."
                    )
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
                        f"Reloader: File {file_name} has been updated. Restarting app..."
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

        def build_root_and_add_to_window(self):
            Logger.info("Reloader: Building root widget and adding to window")
            if self.root is not None:
                self.root.clear_widgets()
                Window.remove_widget(Window.children[0])

            Clock.schedule_once(self.delayed_build)

        def delayed_build(self, *args):
            self.root = self.build()

            if self.root:
                if not isinstance(self.root, F.Widget):
                    Logger.critical("App.root must be an _instance_ of Widget")
                    raise Exception("Invalid instance in App.root")

                Window.add_widget(self.root)

        def unload_python_file(self, filename, module):
            if module == "main":
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
                            if file.endswith(".py")
                        )
                else:
                    files_to_reload.extend(
                        os.path.join(folder, file)
                        for file in os.listdir(folder)
                        if file.endswith(".py")
                    )
            return files_to_reload

        def process_unload_files(self, files):
            modules_to_reload = []
            for filename in files:
                module_name = os.path.relpath(filename).replace(os.path.sep, ".")[:-3]
                to_reload = self.unload_python_file(filename, module_name)
                if to_reload is not None:
                    modules_to_reload.append(to_reload)

            return modules_to_reload

        def unload_python_files_on_android(self):
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

            # We need to reload the modules twice, because some modules
            # may depend on other modules, and the order of reloading
            # matters, so the first pass won't reload necessarily
            # on the correct order, on the second pass the
            # references will be updated correctly
            for _ in range(2):
                for module in modules_to_reload:
                    importlib.reload(module)

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
                if self.__module__ != "__main__":
                    importlib.reload(importlib.import_module(self.__module__))
                self.reload_kv()

            except Exception as e:
                import traceback

                Logger.info(f"Reloader: Server crashed: {e!r}")
                Logger.info(
                    "Full exception:",
                    "".join(traceback.format_exception(*sys.exc_info())),
                )
