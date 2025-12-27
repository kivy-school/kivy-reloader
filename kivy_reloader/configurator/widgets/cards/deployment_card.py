"""Deployment exclusions settings card widget."""

import os

from kivy.properties import DictProperty, ObjectProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout

from kivy_reloader.configurator.widgets.cards.core_card import BUILTIN_EXCLUSIONS
from kivy_reloader.lang import Builder

Builder.load_file(__file__)


class DeploymentCard(BoxLayout):
    """Card showing deployment exclusion information.

    Note: The actual deployment exclusions are configured in the Core card.
    This card provides additional information about built-in exclusions.
    """

    config = DictProperty({
        'FOLDERS_AND_FILES_TO_EXCLUDE_FROM_PHONE': [],
    })

    root_path = StringProperty(os.getcwd())
    scroll_view = ObjectProperty(None)
    on_config_change = ObjectProperty(None)

    # Expose builtin exclusions to KV
    builtin_exclusions = BUILTIN_EXCLUSIONS

    def __init__(self, **kwargs):
        self.config_model = None
        super().__init__(**kwargs)

    def on_kv_post(self, base_widget):
        """Populate widgets with initial configuration values."""
        self.ids.exclude_from_phone_input.values = (
            self.config.get('FOLDERS_AND_FILES_TO_EXCLUDE_FROM_PHONE', []) or []
        )
        self.ids.exclude_from_phone_input.bind(
            values=lambda instance, values: self.on_exclusions_change(values)
        )

    def load_from_model(self):
        """Sync UI controls from the backing config model."""
        if not self.config_model:
            return

        new_config = {}
        for key in self.config.keys():
            new_config[key] = self.config_model.get_value(key)
        self.config = new_config

        self.ids.exclude_from_phone_input.values = (
            new_config.get('FOLDERS_AND_FILES_TO_EXCLUDE_FROM_PHONE', []) or []
        )

    def update_config(self, key, value):
        new_config = self.config.copy()
        new_config[key] = value
        self.config = new_config

        if self.config_model:
            self.config_model.set_value(key, value)

        if self.on_config_change:
            self.on_config_change(self.config)

    def on_exclusions_change(self, values):
        self.update_config('FOLDERS_AND_FILES_TO_EXCLUDE_FROM_PHONE', values)
