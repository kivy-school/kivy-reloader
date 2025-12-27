"""Core settings card widget"""

import os
from pathlib import Path

from kivy.properties import DictProperty, ObjectProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout

from kivy_reloader.configurator.widgets.common import CustomSwitch, RadioGroup
from kivy_reloader.configurator.widgets.common.box_chip_input import BoxChipInput
from kivy_reloader.configurator.widgets.common.card import Card
from kivy_reloader.configurator.widgets.common.chip_input import ChipInput
from kivy_reloader.configurator.widgets.picker import (
    DropdownPicker,
    FolderOnlyDropdownPicker,
)
from kivy_reloader.lang import Builder

Builder.load_file(__file__)

# Built-in exclusions that are always applied
BUILTIN_EXCLUSIONS = [
    '*.bak',
    '*.db',
    '*.egg-info',
    '*.log',
    '*.npy',
    '*.orig',
    '*.pyc',
    '*.sqlite',
    '.DS_Store',
    '.buildozer',
    '.dmypy.json',
    '.env',
    '.git',
    '.github',
    '.gitignore',
    '.ipynb_checkpoints',
    '.mypy_cache',
    '.nomedia',
    '.pytest_cache',
    '.python-version',
    '.venv',
    '.vscode',
    'ENV',
    'README.md',
    '_python_bundle',
    'app_copy.zip',
    'bin',
    'build',
    'buildozer.spec',
    'coverage',
    'dist',
    'dmypy.json',
    'docs',
    'env',
    'env.bak',
    'examples',
    'htmlcov',
    'node_modules',
    'poetry.lock',
    'private.version',
    'pyproject.toml',
    'screenshots',
    'temp',
    'tests',
    'uv.lock',
    'venv',
    'venv.bak',
]


class CoreCard(BoxLayout):
    """Card containing all core hot reload settings"""

    # Default configuration (kept for backwards compatibility)
    config = DictProperty({
        'HOT_RELOAD_ON_PHONE': True,
        'STREAM_USING': 'USB',
        'FULL_RELOAD_FILES': ['main.py'],
        'WATCHED_FOLDERS_RECURSIVELY': ['.'],
        'WATCHED_FILES': [],
        'WATCHED_FOLDERS': [],
        'DO_NOT_WATCH_PATTERNS': [],
        'FOLDERS_AND_FILES_TO_EXCLUDE_FROM_PHONE': [],
    })

    # Path to use as root for file picker (defaults to current working directory)
    root_path = StringProperty(os.getcwd())

    # Reference to the ScrollView (passed from parent screen)
    scroll_view = ObjectProperty(None)

    # Expose builtin exclusions to KV
    builtin_exclusions = BUILTIN_EXCLUSIONS

    on_config_change = ObjectProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.config_model = None  # Will be set by CoreScreen

    def on_kv_post(self, base_widget):
        """Called after KV is loaded - setup pickers with root path"""
        # Setup file picker (FULL_RELOAD_FILES)
        self.ids.full_reload_picker.root_path = self.root_path
        self.ids.full_reload_picker.scroll_view = self.scroll_view
        self.ids.full_reload_picker.initial_selection = self.config.get(
            'FULL_RELOAD_FILES', []
        )
        self.ids.full_reload_picker.bind(
            selected_files=self.on_full_reload_picker_change
        )

        # Setup watched files picker (WATCHED_FILES)
        self.ids.watched_files_picker.root_path = self.root_path
        self.ids.watched_files_picker.scroll_view = self.scroll_view
        self.ids.watched_files_picker.initial_selection = self.config.get(
            'WATCHED_FILES', []
        )
        self.ids.watched_files_picker.bind(
            selected_files=self.on_watched_files_picker_change
        )

        # Setup folder picker (WATCHED_FOLDERS_RECURSIVELY)
        self.ids.watched_folders_picker.root_path = self.root_path
        self.ids.watched_folders_picker.scroll_view = self.scroll_view
        self.ids.watched_folders_picker.initial_selection = self.config.get(
            'WATCHED_FOLDERS_RECURSIVELY', ['.']
        )
        # Bind using a custom callback that gets folders
        self.ids.watched_folders_picker.bind(
            selected_files=self.on_watched_folders_picker_change
        )

        # Setup shallow watched folders picker (WATCHED_FOLDERS)
        self.ids.shallow_watched_folders_picker.root_path = self.root_path
        self.ids.shallow_watched_folders_picker.scroll_view = self.scroll_view
        self.ids.shallow_watched_folders_picker.initial_selection = self.config.get(
            'WATCHED_FOLDERS', []
        )
        self.ids.shallow_watched_folders_picker.bind(
            selected_files=self.on_shallow_watched_folders_picker_change
        )

        # Setup BoxChipInput widgets with initial values
        self.ids.ignore_patterns_input.values = (
            self.config.get('DO_NOT_WATCH_PATTERNS', []) or []
        )
        self.ids.exclude_from_phone_input.values = (
            self.config.get('FOLDERS_AND_FILES_TO_EXCLUDE_FROM_PHONE', []) or []
        )

        # Bind callbacks
        self.ids.ignore_patterns_input.bind(
            values=lambda i, v: self.on_ignore_patterns_change(v)
        )
        self.ids.exclude_from_phone_input.bind(
            values=lambda i, v: self.on_exclude_from_phone_change(v)
        )

    def on_full_reload_picker_change(self, instance, selected_files):
        """Handle when files are selected in the full reload picker"""
        # Convert absolute paths to relative paths
        root = Path(self.root_path)
        relative_files = []

        for file_path in selected_files:
            try:
                rel_path = Path(file_path).relative_to(root)
                # Use forward slashes for cross-platform compatibility
                relative_files.append(rel_path.as_posix())
            except ValueError:
                # If file is not relative to root, use absolute path
                relative_files.append(file_path)

        # Update config
        self.update_config('FULL_RELOAD_FILES', relative_files)

    def on_watched_files_picker_change(self, instance, selected_files):
        """Handle when files are selected in the watched files picker"""
        # Convert absolute paths to relative paths
        root = Path(self.root_path)
        relative_files = []

        for file_path in selected_files:
            try:
                rel_path = Path(file_path).relative_to(root)
                # Use forward slashes for cross-platform compatibility
                relative_files.append(rel_path.as_posix())
            except ValueError:
                # If file is not relative to root, use absolute path
                relative_files.append(file_path)

        # Update config
        self.update_config('WATCHED_FILES', relative_files)

    def on_watched_folders_picker_change(self, instance, selected_files):
        """Handle when folders are selected in the folder picker"""
        # Get folders in config format (with special ['.'] case)
        folders = instance.get_selected_folders_for_config()

        # Update config
        self.update_config('WATCHED_FOLDERS_RECURSIVELY', folders)

    def on_shallow_watched_folders_picker_change(self, instance, selected_files):
        """Handle when folders are selected in the shallow watched folders picker"""
        # Get folders in config format (with special ['.'] case)
        folders = instance.get_selected_folders_for_config()

        # Update config
        self.update_config('WATCHED_FOLDERS', folders)

    def load_from_model(self):
        """Load values from the config model into the UI"""
        if not self.config_model:
            return

        # Update the config dict from model
        new_config = {}
        for key in self.config.keys():
            value = self.config_model.get_value(key)
            new_config[key] = value

        # Force property change notification by creating a new dict
        self.config = new_config

        # Update full reload picker's initial selection
        full_reload_picker = self.ids.full_reload_picker
        full_reload_picker.initial_selection = new_config.get('FULL_RELOAD_FILES', [])

        # If picker already has a container (opened before), update controller
        if (
            full_reload_picker.container
            and full_reload_picker.container.selection_controller
        ):
            full_reload_picker.container.selection_controller.set_initial_selection(
                full_reload_picker.initial_selection
            )
            # Sync the root folder if it's been created
            if full_reload_picker.container.tree_container.children:
                full_reload_picker.container._sync_all_nodes()

        # Update the selected_text display
        full_reload_picker._update_selected_text()

        # Update watched files picker's initial selection
        watched_files_picker = self.ids.watched_files_picker
        watched_files_picker.initial_selection = new_config.get('WATCHED_FILES', [])

        # If picker already has a container (opened before), update controller
        if (
            watched_files_picker.container
            and watched_files_picker.container.selection_controller
        ):
            watched_files_picker.container.selection_controller.set_initial_selection(
                watched_files_picker.initial_selection
            )
            # Sync the root folder if it's been created
            if watched_files_picker.container.tree_container.children:
                watched_files_picker.container._sync_all_nodes()

        # Update the selected_text display
        watched_files_picker._update_selected_text()

        # Update folder picker's initial selection
        folder_picker = self.ids.watched_folders_picker
        folder_picker.initial_selection = new_config.get(
            'WATCHED_FOLDERS_RECURSIVELY', ['.']
        )

        # If folder picker already has a container (opened before), update controller
        if folder_picker.container and folder_picker.container.selection_controller:
            folder_picker.container.selection_controller.set_initial_selection(
                folder_picker.initial_selection
            )
            # Sync the root folder if it's been created
            if folder_picker.container.tree_container.children:
                folder_picker.container._sync_all_nodes()

        # Update the selected_text display
        folder_picker._update_selected_text()

        # Update shallow watched folders picker's initial selection
        shallow_folder_picker = self.ids.shallow_watched_folders_picker
        shallow_folder_picker.initial_selection = new_config.get('WATCHED_FOLDERS', [])

        # If picker already has a container (opened before), update controller
        if (
            shallow_folder_picker.container
            and shallow_folder_picker.container.selection_controller
        ):
            shallow_folder_picker.container.selection_controller.set_initial_selection(
                shallow_folder_picker.initial_selection
            )
            # Sync the root folder if it's been created
            if shallow_folder_picker.container.tree_container.children:
                shallow_folder_picker.container._sync_all_nodes()

        # Update the selected_text display
        shallow_folder_picker._update_selected_text()

        # Update BoxChipInput widgets
        self.ids.ignore_patterns_input.values = (
            new_config.get('DO_NOT_WATCH_PATTERNS', []) or []
        )
        self.ids.exclude_from_phone_input.values = (
            new_config.get('FOLDERS_AND_FILES_TO_EXCLUDE_FROM_PHONE', []) or []
        )

    def update_config(self, key, value):
        """Update a configuration value in both dict and model"""
        # Update local dict
        new_config = self.config.copy()
        new_config[key] = value
        self.config = new_config

        # Update model if available
        if self.config_model:
            self.config_model.set_value(key, value)

        # Call callback if set
        if self.on_config_change:
            self.on_config_change(self.config)

    def on_hot_reload_change(self, value):
        """Handle hot reload toggle"""
        self.update_config('HOT_RELOAD_ON_PHONE', value)

    def on_stream_change(self, value):
        """Handle stream method change"""
        self.update_config('STREAM_USING', value)

    def on_full_reload_files_change(self, values):
        """Handle full reload files change"""
        self.update_config('FULL_RELOAD_FILES', values)

    def on_watched_folders_recursively_change(self, values):
        """Handle watched folders recursively change"""
        self.update_config('WATCHED_FOLDERS_RECURSIVELY', values)

    def on_watched_files_change(self, values):
        """Handle watched files change"""
        self.update_config('WATCHED_FILES', values)

    def on_watched_folders_change(self, values):
        """Handle watched folders change"""
        self.update_config('WATCHED_FOLDERS', values)

    def on_ignore_patterns_change(self, values):
        """Handle ignore patterns change"""
        self.update_config('DO_NOT_WATCH_PATTERNS', values)

    def on_exclude_from_phone_change(self, values):
        """Handle exclude from phone change"""
        self.update_config('FOLDERS_AND_FILES_TO_EXCLUDE_FROM_PHONE', values)
