"""
Desktop Reloader App

Handles development on desktop (Windows/Linux/macOS):
- Uses watchdog for file system monitoring
- Manages child processes for hot reload
- Sends app changes to Android via network
"""

# Standard library imports
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

# Third-party imports
import trio
from kaki.app import App as KakiApp
from kivy.base import EventLoop, async_runTouchApp
from kivy.clock import Clock, mainthread
from kivy.core.window import Window
from kivy.factory import Factory as F
from kivy.lang import Builder
from kivy.logger import Logger
from kivy.utils import platform

# Watchdog imports (optional dependency)
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

# Local imports
from .base_app import BaseReloaderApp
from .config import config
from .utils import get_auto_reloader_paths, get_connected_devices, get_kv_files_paths

# Constants
F5_KEYCODE = 286
CTRL_R_KEYCODE = 114
WINDOWS_SLEEP_DURATION = 10000


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
            time.sleep(WINDOWS_SLEEP_DURATION)
    except KeyboardInterrupt:
        Logger.info('Reloader: Host process received KeyboardInterrupt, exiting')
        sys.exit(0)


def _configure_desktop_environment():
    """Configure desktop-specific settings"""
    Window.always_on_top = True
    logging.getLogger('watchdog').setLevel(logging.ERROR)


def _extract_watched_directories_from_paths(autoreloader_paths):
    """Extract recursive directories from autoreloader paths"""
    watched_dirs = []
    for path_tuple in autoreloader_paths:
        path, options = path_tuple
        if options.get('recursive', False):
            rel_path = os.path.relpath(path, os.getcwd())
            watched_dirs.append(rel_path)
    return watched_dirs


# Configure desktop environment
_configure_desktop_environment()


class DesktopApp(BaseReloaderApp, KakiApp):
    """Desktop development app with hot reload capabilities"""

    subprocesses = []

    # ==================== INITIALIZATION ====================

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._initialize_app_state()
        self._setup_autoreloader()
        self._setup_windows_event_handling()
        self._build()

    def _initialize_app_state(self):
        """Initialize basic app state variables"""
        self.built = False
        self.root = None
        self.DEBUG = 1
        self.state = {}

    def _setup_autoreloader(self):
        """Configure autoreloader paths and settings"""
        self.AUTORELOADER_PATHS = get_auto_reloader_paths()
        self.HOT_RELOAD_ON_PHONE = config.HOT_RELOAD_ON_PHONE
        self.KV_FILES = get_kv_files_paths()
        self._watched_directories = _extract_watched_directories_from_paths(
            self.AUTORELOADER_PATHS
        )

    def _setup_windows_event_handling(self):
        """Setup Windows-specific process management"""
        if platform == 'win':
            # Ensure last spawned process on Windows calls for parent Python
            # process to be exited by PID when window is closed normally
            # https://stackoverflow.com/questions/54501099/how-to-run-a-method-on-the-exit-of-a-kivy-app
            Window.bind(on_request_close=self.on_request_close)

    # ==================== APP LIFECYCLE ====================

    def _build(self):
        """Build the initial application"""
        Logger.info('Reloader: Building the first screen')

        if self.DEBUG:
            Logger.info('Kaki: Debug mode activated')
            self.enable_autoreload()
            self.patch_builder()
            self.listen_for_reload()

        if self.FOREGROUND_LOCK:
            self.prepare_foreground_lock()

        self.rebuild(first=True)

        if self.IDLE_DETECTION:
            self.install_idle(timeout=self.IDLE_TIMEOUT)

    async def async_run(self, async_lib='trio'):
        """Run the app asynchronously using trio"""
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
        """
        Handle window close request.

        On Windows, if this is a child process, terminate the original host process
        by its PID (passed as command line argument).
        """
        if platform == 'win' and len(sys.argv) > 1:
            parent_pid = sys.argv[1]
            killstring = f'taskkill /F /PID {parent_pid}'
            Logger.info(
                'Reloader: Detected request close on Windows. '
                f'Closing original host Python PID: {parent_pid}'
            )
            os.system(killstring)

    def _restart_app(self, mod):
        """
        Restart the application with hot reload support.

        On Windows: Uses subprocess.Popen due to lack of os.execv support
        On Unix/Linux: Uses os.execv for cleaner process replacement
        """
        _has_execv = sys.platform != 'win32'
        original_argv = sys.argv
        cmd = [sys.executable] + original_argv

        if not _has_execv:
            self._restart_app_windows(cmd)
        else:
            self._restart_app_unix(cmd)

    def _restart_app_windows(self, cmd):
        """Handle Windows-specific app restart logic"""
        # Terminate existing child processes
        for process in self.subprocesses:
            process.terminate()
            process.wait()

        # Add parent PID to command arguments if not already present
        if len(sys.argv) <= 1:
            cmd.append(str(os.getpid()))

        # Spawn new process
        new_process = subprocess.Popen(cmd, shell=False)
        self.subprocesses.append(new_process)

        if len(sys.argv) > 1:
            # Child processes should exit to prevent accumulation
            sys.exit(0)
        else:
            # Main process: close window and keep alive for signal handling
            self.root_window.close()
            keep_windows_host_alive()

    def _restart_app_unix(self, cmd):
        """Handle Unix/Linux app restart logic"""
        try:
            os.execv(sys.executable, cmd)
        except OSError:
            os.spawnv(os.P_NOWAIT, sys.executable, cmd)
            os._exit(0)

    # ==================== UI BUILDING ====================

    def listen_for_reload(self):
        """
        Set up keyboard shortcuts for manual reload.

        Binds F5 and Ctrl+R to trigger app rebuild for development workflow.
        """

        def _on_keyboard(window, keycode, scancode, codepoint, modifier_keys):
            pressed_modifiers = set(modifier_keys)

            if keycode == F5_KEYCODE or (
                keycode == CTRL_R_KEYCODE and 'ctrl' in pressed_modifiers
            ):
                return self.rebuild()

        Window.bind(on_keyboard=_on_keyboard)

    def build_root_and_add_to_window(self):
        """
        Clear existing widgets and rebuild the root widget.

        This method handles the UI teardown and rebuilding process,
        ensuring clean widget hierarchy during hot reload.
        """
        Logger.info('Reloader: Building root widget and adding to window')

        # Clear existing root widget
        if self.root is not None:
            self.root.clear_widgets()

        # Remove all children from window
        while Window.children:
            Window.remove_widget(Window.children[0])

        # Schedule delayed build to ensure proper cleanup
        Clock.schedule_once(self.delayed_build)

    def delayed_build(self, *args):
        """
        Build and validate the root widget, then add it to the window.

        This method is called with a slight delay to ensure proper
        widget cleanup before rebuilding.
        """
        self.root = self.build()

        if self.root:
            if not isinstance(self.root, F.Widget):
                Logger.critical('App.root must be an _instance_ of Widget')
                raise Exception('Invalid instance in App.root')

            Window.add_widget(self.root)

    # ==================== HOT RELOAD CORE ====================

    def unload_python_file(self, filename, module_name):
        """
        Unload a specific Python file from the module system.

        Handles factory unregistration and module reloading for hot reload.
        Skips the 'main' module to prevent application termination.
        """
        if module_name == 'main':
            return

        if module_name in sys.modules:
            full_path = os.path.join(os.getcwd(), filename)
            F.unregister_from_filename(full_path)
            self._unregister_factory_from_module(module_name)
            importlib.reload(sys.modules[module_name])

    def unload_files(self, files):
        """Process a list of files for unloading during hot reload."""
        for filename in files:
            module_name = os.path.relpath(filename).replace(os.path.sep, '.')[:-3]
            self.unload_python_file(filename, module_name)

    def unload_python_files_on_desktop(self):
        """
        Gather and unload all Python files from watched locations.

        Collects files from:
        - Recursive watched directories
        - Non-recursive watched folders
        - Individual watched files
        - Files requiring full reload
        """
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
        """Load KV files and register widget classes for the application."""
        for path in self.KV_FILES:
            real_path = os.path.realpath(path)
            if real_path not in Builder.files:
                Builder.load_file(real_path)
        for name, module in self.CLASSES.items():
            F.register(name, module=module)

    def rebuild(self, dt=None, first=False, *args, **kwargs):
        """
        Rebuild the application with hot reload support.

        Args:
            dt: Delta time (unused, for Clock compatibility)
            first: Whether this is the initial build
            *args, **kwargs: Additional arguments
        """
        Logger.info('Reloader: Rebuilding the application')

        try:
            if not first:
                self._perform_hot_reload()

            self.build_root_and_add_to_window()
            self.apply_state(self.state)  # TODO: Implement state persistence

            # Handle Android hot reload if enabled
            self._handle_android_reload()

        except Exception as e:
            Logger.exception('Reloader: Error when building app')
            self.set_error(repr(e), traceback.format_exc())
            if not self.DEBUG and self.RAISE_ERROR:
                raise

    def _perform_hot_reload(self):
        """Execute the hot reload sequence for desktop development."""
        self.unload_app_dependencies()
        self.unload_python_files_on_desktop()
        importlib.reload(importlib.import_module(self.__module__))
        Builder.rulectx = {}
        self.load_app_dependencies()

    def _handle_android_reload(self):
        """Handle Android hot reload if configured and available."""
        if not self.HOT_RELOAD_ON_PHONE:
            return

        # Check if any devices are connected before processing
        connected_devices = get_connected_devices()
        if not connected_devices:
            Logger.warning('Reloader: No devices connected, skipping app transfer')
            Logger.warning(
                'Reloader: Connect your Android device via USB and enable USB debugging.'
            )
            Logger.warning('Reloader: Make sure your device is turned on and unlocked.')
            Logger.warning(
                'Change HOT_RELOAD_ON_PHONE to False in config.py to disable this log.'
            )
            return

        Logger.info(f'Reloader: Sending app to {len(connected_devices)} device(s)')
        self.send_app_to_phone()

    # ==================== FILE WATCHING & AUTORELOAD ====================

    def enable_autoreload(self):
        """
        Enable automatic reloading when files change.

        On Windows: Uses watchdog for file system monitoring
        On other platforms: Delegates to parent class implementation
        """
        if platform != 'win':
            super().enable_autoreload()
            return

        if not WATCHDOG_AVAILABLE:
            Logger.warn('Reloader: Unavailable, watchdog is not installed')
            return

        Logger.info('Reloader: Autoreloader activated')
        self._setup_watchdog_observers()

    def _setup_watchdog_observers(self):
        """Configure watchdog observers for file and folder monitoring."""
        rootpath = self.get_root_path()

        # Create handlers
        folder_handler = FileSystemEventHandler()
        file_handler = PatternMatchingEventHandler()

        # Bind dispatch methods
        folder_handler.dispatch = self._reload_from_watchdog
        file_handler.dispatch = self._reload_from_watchdog

        # Create observers
        folder_observer = Observer()
        file_observer = Observer()

        # Setup file patterns to watch
        patterns = [
            os.path.abspath(os.path.join(rootpath, path))
            for path in config.WATCHED_FILES + config.FULL_RELOAD_FILES
        ]
        file_handler._patterns = patterns

        # Watch directories containing individual files
        dirs_to_watch_from_watched_files = list(
            set([os.path.dirname(path) for path in patterns])
        )

        for directory in dirs_to_watch_from_watched_files:
            file_observer.schedule(file_handler, directory, **{'recursive': False})

        # Watch configured directories
        for path_tuple in self.AUTORELOADER_PATHS:
            path, options = path_tuple

            # Skip if not a directory
            if not os.path.isdir(os.path.join(rootpath, path)):
                continue

            folder_observer.schedule(
                folder_handler, os.path.join(rootpath, path), **options
            )

        # Start observers
        file_observer.start()
        folder_observer.start()

    @mainthread
    def _reload_from_watchdog(self, event):
        """
        Handle file system events from watchdog.

        Processes file modification events and triggers appropriate reload actions:
        - Full app restart for FULL_RELOAD_FILES
        - Hot reload for other Python files
        """
        if not isinstance(event, FileModifiedEvent):
            return

        if not os.path.exists(event.src_path):
            return

        # Check for full reload trigger files
        if self._should_trigger_full_reload(event.src_path):
            return

        # Skip ignored patterns
        if self._should_ignore_file(event.src_path):
            return

        Logger.trace(f'Reloader: Event received {event.src_path}')

        # Handle Python file changes
        if event.src_path.endswith('.py'):
            try:
                Builder.unload_file(event.src_path)
                self._reload_py(event.src_path)
            except Exception as e:
                self.set_error(repr(e), traceback.format_exc())
                return

        # Schedule rebuild
        Logger.debug(f'Reloader: Triggered by {event}')
        Clock.unschedule(self.rebuild)
        Clock.schedule_once(self.rebuild, 0.1)

    def _should_trigger_full_reload(self, file_path):
        """Check if the file should trigger a full application restart."""
        for path in config.FULL_RELOAD_FILES:
            full_path = os.path.join(self.get_root_path(), path)
            if fnmatch(file_path, full_path):
                Logger.info(f'Reloader: Full reload triggered by {file_path}')
                mod = sys.modules[self.__class__.__module__]
                mod_filename = os.path.realpath(mod.__file__)
                self._restart_app(mod_filename)
                return True
        return False

    def _should_ignore_file(self, file_path):
        """Check if the file should be ignored based on DO_NOT_WATCH_PATTERNS."""
        for pattern in config.DO_NOT_WATCH_PATTERNS:
            if fnmatch(file_path, pattern):
                return True
            if fnmatch(file_path, os.path.join(os.getcwd(), pattern)):
                return True
        return False

    # ==================== ERROR HANDLING & UTILITIES ====================

    @mainthread
    def set_error(self, exc, tb=None):
        """
        Display error information in the application window.

        Creates a scrollable label with exception details when errors occur
        during hot reload or application building.
        """
        error_text = '{}\n\n{}'.format(exc, tb or '')

        # Create error label
        error_label = F.Label(
            size_hint=(1, None),
            padding_y=150,
            text_size=(Window.width - 100, None),
            text=error_text,
        )
        error_label.texture_update()
        error_label.height = error_label.texture_size[1]

        # Create scrollable container
        scroll_view = F.ScrollView(
            size_hint=(1, 1),
            pos_hint={'x': 0, 'y': 0},
            do_scroll_x=False,
            scroll_y=0,
        )
        scroll_view.add_widget(error_label)

        # Clear window and display error
        while Window.children:
            Window.remove_widget(Window.children[0])
        Window.add_widget(scroll_view)

    # ==================== ANDROID COMMUNICATION ====================

    @staticmethod
    def clear_temp_folder_and_zip_file(folder, zip_file):
        """Clean up temporary files and folders used for Android deployment."""
        if os.path.exists(folder):
            rmtree(folder)
        if os.path.exists(zip_file):
            os.remove(zip_file)

    def send_app_to_phone(self):
        """
        Package and send the application to an Android device.

        Creates a temporary copy of the project, zips it (excluding specified
        files/folders), and transfers it to the connected Android device.
        """
        source = os.getcwd()
        destination = os.path.join(os.getcwd(), 'temp')
        zip_file = os.path.join(os.getcwd(), 'app_copy.zip')

        # Clean up any existing temp files
        self.clear_temp_folder_and_zip_file(destination, zip_file)

        # Create project copy excluding specified patterns
        copytree(
            source,
            destination,
            ignore=ignore_patterns(
                *config.FOLDERS_AND_FILES_TO_EXCLUDE_FROM_PHONE,
            ),
        )

        # Create zip archive
        self._create_app_archive(destination)

        # Send to Android device
        self._transfer_to_android()

        # Clean up temporary files
        self.clear_temp_folder_and_zip_file(destination, zip_file)

    @staticmethod
    def _create_app_archive(temp_directory):
        """Create a zip archive of the application files."""
        subprocess.run(
            f'cd {temp_directory} && zip -r ../app_copy.zip ./* -x ./temp',
            shell=True,
            stdout=subprocess.DEVNULL,
            check=True,
        )

    @staticmethod
    def _transfer_to_android():
        """Transfer the zipped application to the Android device."""
        # Get path to send_app_to_phone.py script
        current_frame = inspect.currentframe().f_back
        current_file_path = os.path.abspath(current_frame.f_code.co_filename)
        script_directory = os.path.dirname(current_file_path)
        send_app_script = os.path.join(script_directory, 'send_app_to_phone.py')

        subprocess.run(f'python {send_app_script}', shell=True, check=True)

    def _filename_to_module(self, filename: str):
        """
        Convert a file path to a module name.

        Transforms filesystem paths into Python module notation,
        handling platform-specific path separators correctly.

        Args:
            filename: The file path to convert

        Returns:
            The module name in dot notation (e.g., 'package.module')
        """
        rootpath = self.get_root_path()

        # Remove root path prefix if present
        if filename.startswith(rootpath):
            filename = filename[len(rootpath) :]

        # Handle platform-specific path separators
        if platform == 'macosx':
            prefix = os.sep
        else:
            prefix = os.path.sep

        # Remove leading separator
        if filename.startswith(prefix):
            filename = filename[1:]

        # Convert to module notation (remove .py extension and replace separators)
        module = filename[:-3].replace(prefix, '.')
        return module
