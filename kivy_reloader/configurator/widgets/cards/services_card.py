"""Services settings card widget."""

import os
from pathlib import Path

from kivy.properties import DictProperty, ObjectProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout

from kivy_reloader.lang import Builder

Builder.load_file(__file__)


class ServicesCard(BoxLayout):
    """Card containing Android services related settings."""

    config = DictProperty({
        'SERVICE_NAMES': [],
        'SERVICE_FILES': [],
    })

    root_path = StringProperty(os.getcwd())
    scroll_view = ObjectProperty(None)

    # Optional callback fired when configuration changes
    on_config_change = ObjectProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.config_model = None

    def on_kv_post(self, base_widget):
        """Populate widgets with initial configuration values."""
        picker = self.ids.service_files_picker
        picker.root_path = self.root_path
        picker.scroll_view = self.scroll_view
        picker.initial_selection = self.config.get('SERVICE_FILES', [])
        picker.bind(selected_files=self.on_service_files_picker_change)

        chip_input = self.ids.service_names_input
        chip_input.values = self.config.get('SERVICE_NAMES', [])[:]
        chip_input.bind(
            values=lambda instance, values: self.on_service_names_change(values)
        )

    def load_from_model(self):
        """Sync UI controls from the backing config model."""
        if not self.config_model:
            return

        new_config = {}
        for key in self.config.keys():
            new_config[key] = self.config_model.get_value(key)
        self.config = new_config

        # Update chip input
        chip_input = self.ids.service_names_input
        chip_input.values = new_config.get('SERVICE_NAMES', [])[:]

        # Update file picker
        picker = self.ids.service_files_picker
        picker.initial_selection = new_config.get('SERVICE_FILES', [])
        if picker.container and picker.container.selection_controller:
            picker.container.selection_controller.set_initial_selection(
                picker.initial_selection
            )
            if picker.container.tree_container.children:
                picker.container._sync_all_nodes()
        picker._update_selected_text()

    def update_config(self, key, value):
        new_config = self.config.copy()
        new_config[key] = value
        self.config = new_config

        if self.config_model:
            self.config_model.set_value(key, value)

        if self.on_config_change:
            self.on_config_change(self.config)

    def on_service_names_change(self, values):
        self.update_config('SERVICE_NAMES', values)

    def on_service_files_picker_change(self, instance, selected_files):
        root = Path(self.root_path)
        relative_files = []

        for file_path in selected_files:
            try:
                rel_path = Path(file_path).relative_to(root)
                relative_files.append(str(rel_path))
            except ValueError:
                relative_files.append(file_path)

        self.update_config('SERVICE_FILES', relative_files)
