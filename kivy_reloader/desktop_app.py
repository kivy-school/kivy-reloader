"""
Desktop Reloader App

Handles development on desktop (Windows/Linux/macOS):
- Uses watchdog for file system monitoring
- Manages child processes for hot reload
- Sends app changes to Android via network
"""

import importlib
import inspect
import logging
import os
import subprocess
import sys
import time
import traceback
from fnmatch import fnmatch
from shutil import copytree, ignore_patterns, rmtree

import trio
from kaki.app import App as KakiApp
from kivy.base import EventLoop, async_runTouchApp
from kivy.clock import Clock, mainthread
from kivy.core.window import Window
from kivy.factory import Factory as F
from kivy.lang import Builder
from kivy.logger import Logger
from kivy.utils import platform

try:
    from watchdog.events import (
        FileModifiedEvent,
        FileSystemEventHandler,
        PatternMatchingEventHandler,
    )
    from watchdog.observers import Observer

    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

from .base_app import BaseReloaderApp
from .config import config
from .utils import get_auto_reloader_paths, get_kv_files_paths


def keep_windows_host_alive():
    """
    Windows-specific workaround to keep the host Python process alive.

    This prevents KeyboardInterrupt from being lost when child processes
    are spawned on Windows (since os.spawnv doesn't exist on Windows).

    Without this, when you Ctrl+C, the original process may have already
    exited and cannot send KeyboardInterrupt to child processes.
    """
    Logger.info('Reloader: Keeping Windows host process alive for signal handling')
    try:
        while True:
            time.sleep(10000)
    except KeyboardInterrupt:
        Logger.info('Reloader: Host process received KeyboardInterrupt, exiting')
        sys.exit(0)


# Configure logging for desktop environment
Window.always_on_top = True
logging.getLogger('watchdog').setLevel(logging.ERROR)


class DesktopApp(BaseReloaderApp, KakiApp):
    subprocesses = []

    # ==================== INITIALIZATION ====================
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.built = False
        self.root = None
        self.DEBUG = 1
        self.AUTORELOADER_PATHS: list = get_auto_reloader_paths()
        self.HOT_RELOAD_ON_PHONE: bool = config.HOT_RELOAD_ON_PHONE
        self.KV_FILES: list = get_kv_files_paths()

        # Extract the actual directories being watched for unloading
        self._watched_directories = self._extract_watched_directories()

        self._build()
        if (
            platform == 'win'
        ):  # this is to make sure last spawned process on windows calls
            # for parent Python process to be exited by PID when window
            # is closed normally
            Window.bind(on_request_close=self.on_request_close)
            # https://stackoverflow.com/questions/54501099/how-to-run-a-method-on-the-exit-of-a-kivy-app

    def _extract_watched_directories(self):
        """Extract the actual directories being watched from AUTORELOADER_PATHS"""
        watched_dirs = []
        for path_tuple in self.AUTORELOADER_PATHS:
            path, options = path_tuple
            if options.get('recursive', False):
                # Convert to relative path for consistency with config usage
                rel_path = os.path.relpath(path, os.getcwd())
                watched_dirs.append(rel_path)
        return watched_dirs

    # ==================== APP LIFECYCLE ====================
    def _build(self):
        Logger.info('Reloader: Building the first screen')
        if self.DEBUG:
            Logger.info('Kaki: Debug mode activated')
            self.enable_autoreload()
            self.patch_builder()
            self.listen_for_reload()

        if self.FOREGROUND_LOCK:
            self.prepare_foreground_lock()

        self.state = {}

        self.rebuild(first=True)

        if self.IDLE_DETECTION:
            self.install_idle(timeout=self.IDLE_TIMEOUT)

    async def async_run(self, async_lib='trio'):
        async with trio.open_nursery() as nursery:
            Logger.info('Reloader: Starting Async Kivy app')
            self.nursery = nursery
            self._run_prepare()
            await async_runTouchApp(async_lib=async_lib)
            self._stop()
            nursery.cancel_scope.cancel()

    def _run_prepare(self):
        if not self.built:
            self.load_config()
            self.load_kv(filename=self.kv_file)

        # Check if the window is already created
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
                'Application: No window is created. Terminating application run.'
            )
            return

        self.dispatch('on_start')

    # ==================== PROCESS MANAGEMENT ====================
    def on_request_close(self, *args, **kwargs):
        # if this is a child process, you must stop the initial process,
        # check argv for the PID (only on windows)

        if platform == 'win' and len(sys.argv) > 1:
            killstring = f'taskkill /F /PID {sys.argv[1]}'
            Logger.info(
                'Reloader: Detected request close on Windows. '
                f'Closing original host Python PID: {sys.argv[1]}'
            )
            os.system(killstring)

    def _restart_app(self, mod):
        _has_execv = sys.platform != 'win32'
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
                # children will have the host Python's PID in the argv,
                # these are not needed and must exit to prevent extra
                # python processes
                sys.exit(0)
            else:
                # the main process will have a single arg in argv, but you
                # need to keep it open so you can intercept
                # KeyboardInterrupt
                self.root_window.close()
                keep_windows_host_alive()
        else:
            # linux spawnv
            try:
                os.execv(sys.executable, cmd)
            except OSError:
                os.spawnv(os.P_NOWAIT, sys.executable, cmd)
                os._exit(0)

    # ==================== UI BUILDING ====================

    def listen_for_reload(self):
        """
        Reload the app when pressing F5 or Ctrl+R on desktop
        """

        F5_KEYCODE = 286  # Named constant for F5 key
        CTRL_R_KEYCODE = 114  # Named constant for Ctrl+R key

        def _on_keyboard(window, keycode, scancode, codepoint, modifier_keys):
            pressed_modifiers = set(modifier_keys)

            if keycode == F5_KEYCODE or (
                keycode == CTRL_R_KEYCODE and 'ctrl' in pressed_modifiers
            ):
                return self.rebuild()

        Window.bind(on_keyboard=_on_keyboard)

    def build_root_and_add_to_window(self):
        Logger.info('Reloader: Building root widget and adding to window')
        if self.root is not None:
            self.root.clear_widgets()

            while Window.children:
                Window.remove_widget(Window.children[0])

        Clock.schedule_once(self.delayed_build)

    def delayed_build(self, *args):
        self.root = self.build()

        if self.root:
            if not isinstance(self.root, F.Widget):
                Logger.critical('App.root must be an _instance_ of Widget')
                raise Exception('Invalid instance in App.root')

            Window.add_widget(self.root)

    # ==================== HOT RELOAD CORE ====================
    def unload_python_file(self, filename, module_name):
        if module_name == 'main':
            return

        if module_name in sys.modules:
            full_path = os.path.join(os.getcwd(), filename)
            F.unregister_from_filename(full_path)
            self._unregister_factory_from_module(module_name)
            importlib.reload(sys.modules[module_name])

    def unload_files(self, files):
        for filename in files:
            module_name = os.path.relpath(filename).replace(os.path.sep, '.')[:-3]
            self.unload_python_file(filename, module_name)

    def unload_python_files_on_desktop(self):
        files_to_unload = []

        # Use the actual watched directories instead of raw config
        for folder in self._watched_directories:
            for root, _, files in os.walk(folder):
                files_to_unload.extend(
                    os.path.join(root, file) for file in files if file.endswith('.py')
                )

        # Gather files from watched folders (non-recursive)
        for folder in config.WATCHED_FOLDERS:
            files_to_unload.extend(
                os.path.join(folder, file)
                for file in os.listdir(folder)
                if file.endswith('.py')
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
            real_path = os.path.realpath(path)
            if real_path not in Builder.files:
                Builder.load_file(real_path)
        for name, module in self.CLASSES.items():
            F.register(name, module=module)

    def rebuild(self, dt=None, first=False, *args, **kwargs):
        Logger.info('Reloader: Rebuilding the application')

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
            if platform == 'win' and config.HOT_RELOAD_ON_PHONE:
                Logger.warning(
                    'Reloader: Reloading on Android requires WSL'
                    'installation: https://kivyschool.com/kivy-reloader/windows/wsl2-setup-targeting-android/'
                )
            elif self.HOT_RELOAD_ON_PHONE:
                self.send_app_to_phone()
        except Exception as e:
            Logger.exception('Reloader: Error when building app')
            self.set_error(repr(e), traceback.format_exc())
            if not self.DEBUG and self.RAISE_ERROR:
                raise

    def enable_autoreload(self):
        if platform != 'win':
            super().enable_autoreload()
            return

        if not WATCHDOG_AVAILABLE:
            Logger.warn('Reloader: Unavailable, watchdog is not installed')
            return

        Logger.info('Reloader: Autoreloader activated')
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
            file_observer.schedule(file_handler, dir, **{'recursive': False})

        for path_tuple in self.AUTORELOADER_PATHS:
            path, options = path_tuple

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
        if not isinstance(event, FileModifiedEvent):
            return

        if not os.path.exists(event.src_path):
            return

        for path in config.FULL_RELOAD_FILES:
            full_path = os.path.join(self.get_root_path(), path)
            if fnmatch(event.src_path, full_path):
                Logger.info(f'Reloader: Full reload triggered by {event.src_path}')
                mod = sys.modules[self.__class__.__module__]
                mod_filename = os.path.realpath(mod.__file__)
                self._restart_app(mod_filename)
                break

        for pat in config.DO_NOT_WATCH_PATTERNS:
            if fnmatch(event.src_path, pat):
                return
            if fnmatch(event.src_path, os.path.join(os.getcwd(), pat)):
                return

        Logger.trace(f'Reloader: Event received {event.src_path}')
        if event.src_path.endswith('.py'):
            # source changed, reload it
            try:
                Builder.unload_file(event.src_path)
                self._reload_py(event.src_path)
            except Exception as e:
                self.set_error(repr(e), traceback.format_exc())
                return

        Logger.debug(f'Reloader: Triggered by {event}')
        Clock.unschedule(self.rebuild)
        Clock.schedule_once(self.rebuild, 0.1)

    @mainthread
    def set_error(self, exc, tb=None):
        lbl = F.Label(
            size_hint=(1, None),
            padding_y=150,
            text_size=(Window.width - 100, None),
            text='{}\n\n{}'.format(exc, tb or ''),
        )
        lbl.texture_update()
        lbl.height = lbl.texture_size[1]
        sv = F.ScrollView(
            size_hint=(1, 1),
            pos_hint={'x': 0, 'y': 0},
            do_scroll_x=False,
            scroll_y=0,
        )
        sv.add_widget(lbl)
        while Window.children:
            Window.remove_widget(Window.children[0])
        Window.add_widget(sv)

    @staticmethod
    def clear_temp_folder_and_zip_file(folder, zip_file):
        if os.path.exists(folder):
            rmtree(folder)
        if os.path.exists(zip_file):
            os.remove(zip_file)

    def send_app_to_phone(self):
        # Creating a copy of the files on `temp` folder
        source = os.getcwd()
        destination = os.path.join(os.getcwd(), 'temp')
        zip_file = os.path.join(os.getcwd(), 'app_copy.zip')

        self.clear_temp_folder_and_zip_file(destination, zip_file)

        copytree(
            source,
            destination,
            ignore=ignore_patterns(
                *config.FOLDERS_AND_FILES_TO_EXCLUDE_FROM_PHONE,
            ),
        )

        # Zipping all files inside `temp` folder,
        # except the `temp` folder itself
        subprocess.run(
            f'cd {destination} && zip -r ../app_copy.zip ./* -x ./temp',
            shell=True,
            stdout=subprocess.DEVNULL,
            check=True,
        )

        # Sending the zip file to the phone
        path_of_current_file = inspect.currentframe().f_back
        path_of_send_app = os.path.join(
            os.path.dirname(os.path.abspath(path_of_current_file.f_code.co_filename)),
            'send_app_to_phone.py',
        )
        subprocess.run(f'python {path_of_send_app}', shell=True, check=True)

        # Deleting the temp folder and the zip file
        self.clear_temp_folder_and_zip_file(destination, zip_file)

    def _filename_to_module(self, filename: str):
        rootpath = self.get_root_path()
        if filename.startswith(rootpath):
            filename = filename[len(rootpath) :]

        if platform == 'macosx':
            prefix = os.sep
        else:
            prefix = os.path.sep

        if filename.startswith(prefix):
            filename = filename[1:]
        module = filename[:-3].replace(prefix, '.')
        return module
