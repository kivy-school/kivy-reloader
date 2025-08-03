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
import json
import os
import socket
import sys
import traceback
import zipfile
from fnmatch import fnmatch
from pathlib import Path

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

from kivy_reloader import tree_formatter

# Local imports
from .base_app import BaseReloaderApp
from .config import config
from .tree_formatter import format_file_tree
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
            import py_compile

            try:
                Logger.info(f'Reloader: Compiling main.py: {main_py_path}')
                py_compile.compile(main_py_path, doraise=True)
            except py_compile.PyCompileError as e:
                Logger.error(f'Failed to compile main.py: {e}')

    # ==================== HOT RELOAD CORE ====================

    def reload_app(self, *args):
        """
        Reloads the whole application:
        - KV files, services, and Python modules.

        Handles multiple types of reload scenarios:
        - Service file changes (triggers app restart)
        - Full reload files (triggers app restart)
        - Main.py changes (triggers app restart)
        - KV file changes (hot reload)
        """
        Logger.info('Reloading app')

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

        import py_compile

        try:
            Logger.info(f'Reloader: Recompiling service file: {file_name}')
            py_compile.compile(file_name, doraise=True)
        except py_compile.PyCompileError as e:
            Logger.error(f'Failed to compile {file_name}: {e}')

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
        if self.main_py_hash is None:
            Logger.info('main.py hash not initialized, skipping check')
            if os.path.exists(main_py_file_path):
                self.main_py_hash = self.get_hash_of_file(main_py_file_path)
            return False

        if os.path.exists(main_py_file_path):
            current_hash = self.get_hash_of_file(main_py_file_path)
            if current_hash != self.main_py_hash:
                Logger.info('main.py changed, restarting app')
                Logger.info(
                    'current_hash: %s, previous_hash: %s',
                    current_hash,
                    self.main_py_hash,
                )
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
        Process the received app update (delta or full) and trigger reload.

        Args:
            zip_file_path: Path to the received zip file
        """
        Logger.info('Reloader: Finished receiving all files from computer')
        Logger.info('Reloader: Processing app update')

        # Log zip file information and extract
        zip_file_size = os.path.getsize(zip_file_path)

        # Check if this is a delta or full transfer
        transfer_type = self._detect_transfer_type(zip_file_path)

        # Log transfer metadata
        self._log_transfer_metadata(zip_file_path, transfer_type)

        if transfer_type == 'delta':
            self._process_delta_update(zip_file_path)
        else:
            # Full transfer - extract everything and handle deletions
            self._process_full_update(zip_file_path)

        os.remove(zip_file_path)

        Logger.info('Reloader: App updated, triggering hot reload')
        Logger.info('Reloader: ************** END SERVER **************')

        # Trigger hot reload
        self.unload_python_files_on_android()
        if self.__module__ != '__main__':
            importlib.reload(importlib.import_module(self.__module__))

        self.reload_app()

    def _detect_transfer_type(self, zip_file_path):
        """
        Detect if the received archive is a delta or full transfer.

        Args:
            zip_file_path: Path to the zip file

        Returns:
            str: 'delta' or 'full'
        """
        try:
            with zipfile.ZipFile(zip_file_path, 'r') as zip_file:
                if '_delta_metadata.json' in zip_file.namelist():
                    metadata_content = zip_file.read('_delta_metadata.json')
                    metadata = json.loads(metadata_content.decode('utf-8'))
                    return metadata.get('type', 'full')
        except (zipfile.BadZipFile, json.JSONDecodeError, KeyError):
            Logger.warning('Could not detect transfer type, assuming full transfer')

        return 'full'

    def _log_transfer_metadata(self, zip_file_path, transfer_type):
        """Log detailed information about the transfer metadata."""
        try:
            with zipfile.ZipFile(zip_file_path, 'r') as zip_file:
                if '_delta_metadata.json' in zip_file.namelist():
                    metadata_content = zip_file.read('_delta_metadata.json')
                    metadata = json.loads(metadata_content.decode('utf-8'))

                    if transfer_type == 'delta':
                        changed_files = metadata.get('files', [])
                        deleted_files = metadata.get('deleted_files', [])

                        Logger.info(
                            f'Android: Received {transfer_type} transfer - '
                            f'{len(changed_files)} changed, '
                            f'{len(deleted_files)} deleted files'
                        )

                        # Log changed files as tree
                        if changed_files:
                            Logger.info(
                                format_file_tree(
                                    changed_files, 'Android: Changed files'
                                )
                            )

                        # Log deleted files as tree
                        if deleted_files:
                            Logger.info(
                                format_file_tree(
                                    deleted_files, 'Android: Files to delete'
                                )
                            )
                    else:
                        all_files = metadata.get('files', [])
                        Logger.info(
                            f'Android: Received {transfer_type} transfer '
                            f'with {len(all_files)} files'
                        )

                        # Log complete project state from desktop
                        if all_files:
                            Logger.info(
                                format_file_tree(
                                    all_files, 'Android: Complete project from desktop'
                                )
                            )
                else:
                    # Legacy transfer without metadata
                    file_count = len(zip_file.namelist())
                    Logger.info(
                        f'Android: Received {transfer_type} transfer '
                        f'with {file_count} files'
                    )
        except Exception as e:
            Logger.warning(f'Android: Failed to read transfer metadata: {e}')

    def _process_delta_update(self, zip_file_path):
        """
        Process a delta update by extracting only changed files.

        Args:
            zip_file_path: Path to the delta zip file
        """
        with zipfile.ZipFile(zip_file_path, 'r') as zip_file:
            # Read metadata
            metadata_content = zip_file.read('_delta_metadata.json')
            metadata = json.loads(metadata_content.decode('utf-8'))

            Logger.info(f'Delta metadata: {metadata}')

            changed_files = metadata.get('files', [])
            deleted_files = metadata.get('deleted_files', [])

            Logger.info(
                f'Delta update: {len(changed_files)} changed, '
                f'{len(deleted_files)} deleted'
            )

            # Extract changed files
            for file_path in changed_files:
                if file_path in zip_file.namelist():
                    # Extract to current directory
                    zip_file.extract(file_path, os.getcwd())
                    Logger.debug(f'Updated: {file_path}')
                else:
                    Logger.warning(f'File not found in zip: {file_path}')
                    Logger.warning(f'Current zip_file contents: {zip_file.namelist()}')
                    Logger.warning(f'Current changed_files: {changed_files}\n')

            # Delete removed files
            for file_path in deleted_files:
                full_path = os.path.join(os.getcwd(), file_path)
                if os.path.exists(full_path):
                    os.remove(full_path)
                    Logger.debug(f'Deleted: {file_path}')

    def _process_full_update(self, zip_file_path):
        """
        Process a full update by synchronizing Android file system with desktop state.

        Full update process:
        1. Scan current Android file system
        2. Extract new files from desktop
        3. Delete files that no longer exist on desktop

        Args:
            zip_file_path: Path to the ZIP file containing new desktop state
        """
        # Step 1: Snapshot current Android file system
        files_on_android_before = self._get_current_project_files()
        Logger.info('Full update: Scanning current Android file system')
        Logger.info(
            tree_formatter.format_file_tree(
                files_on_android_before, 'Android: Files currently on device'
            )
        )

        # Step 2: Extract new desktop state
        with zipfile.ZipFile(zip_file_path, 'r') as zip_file:
            # Get list of files that should exist after update (new desktop state)
            new_desktop_state = set()
            for file_info in zip_file.filelist:
                if not file_info.filename.startswith('_delta_metadata.json'):
                    new_desktop_state.add(file_info.filename)

            # Extract all files (overwrites existing + adds new)
            zip_file.extractall(os.getcwd())
            Logger.info(
                f'Full update: Extracted {len(new_desktop_state)} files from desktop'
            )

            # Step 3: Clean up obsolete files
            # Files to delete = files that exist on Android but not in new desktop state
            obsolete_files = files_on_android_before - new_desktop_state

            if obsolete_files:
                Logger.info(
                    tree_formatter.format_file_tree(
                        obsolete_files, 'Android: Obsolete files to delete'
                    )
                )

                # Delete obsolete files
                deleted_count = 0
                for file_path in obsolete_files:
                    full_path = os.path.join(os.getcwd(), file_path)
                    if os.path.exists(full_path):
                        try:
                            os.remove(full_path)
                            deleted_count += 1
                            Logger.debug(f'Deleted obsolete file: {file_path}')
                        except OSError as e:
                            Logger.warning(f'Failed to delete {file_path}: {e}')

                Logger.info(f'Full update: Deleted {deleted_count} obsolete files')
            else:
                Logger.info('Full update: No obsolete files to delete')

    def _get_current_project_files(self):
        """
        Get current project files using same exclusion logic as delta transfer.

        Returns:
            set: Set of relative file paths that are part of the project
        """
        exclude_patterns = config.FOLDERS_AND_FILES_TO_EXCLUDE_FROM_PHONE + [
            '.kivy',
            'libpybundle.version',
            'p4a_env_vars.txt',
            '_delta_metadata.json',
        ]
        project_files = set()

        for root, dirs, files in os.walk(os.getcwd()):
            # Convert to relative path
            rel_root = os.path.relpath(root, os.getcwd())
            if rel_root == '.':
                rel_root = ''

            # Filter directories based on exclude patterns
            dirs[:] = [
                d
                for d in dirs
                if not self._should_exclude_path(
                    os.path.join(rel_root, d) if rel_root else d, exclude_patterns
                )
            ]

            for file in files:
                if rel_root:
                    rel_path = os.path.join(rel_root, file).replace('\\', '/')
                else:
                    rel_path = file

                if not self._should_exclude_path(rel_path, exclude_patterns):
                    project_files.add(rel_path)

        return project_files

    def _should_exclude_path(self, rel_path, exclude_patterns):
        """Check if a path should be excluded using fnmatch patterns."""
        path_str = rel_path.replace('\\', '/')
        rel_path_obj = Path(rel_path)

        for pattern in exclude_patterns:
            # Handle directory patterns (ending with /)
            if pattern.endswith('/'):
                clean_pattern = pattern.rstrip('/')
                if fnmatch(path_str, f'{clean_pattern}/*') or path_str == clean_pattern:
                    return True
            # Handle file patterns
            elif fnmatch(path_str, pattern) or fnmatch(rel_path_obj.name, pattern):
                return True

        return False

    def _log_server_error(self, error):
        """Log server error with full traceback."""
        Logger.info(f'Reloader: Server crashed: {error!r}')
        Logger.info(
            'Full exception:',
            ''.join(traceback.format_exception(*sys.exc_info())),
        )
