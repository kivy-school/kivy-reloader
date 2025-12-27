"""Notifications settings card widget."""

import os

from kivy.properties import DictProperty, ObjectProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout

from kivy_reloader.lang import Builder

Builder.load_file(__file__)


class NotificationsCard(BoxLayout):
    """Card containing notification settings."""

    config = DictProperty({
        'SHOW_NOTIFICATIONS': True,
    })

    root_path = StringProperty(os.getcwd())
    scroll_view = ObjectProperty(None)
    on_config_change = ObjectProperty(None)

    def __init__(self, **kwargs):
        self.config_model = None
        super().__init__(**kwargs)

    def on_kv_post(self, base_widget):
        """Populate widgets with initial configuration values."""
        self.ids.show_notifications_switch.active = self.config.get(
            'SHOW_NOTIFICATIONS', True
        )

    def load_from_model(self):
        """Sync UI controls from the backing config model."""
        if not self.config_model:
            return

        new_config = {}
        for key in self.config.keys():
            new_config[key] = self.config_model.get_value(key)
        self.config = new_config

        self.ids.show_notifications_switch.active = new_config.get(
            'SHOW_NOTIFICATIONS', True
        )

    def update_config(self, key, value):
        new_config = self.config.copy()
        new_config[key] = value
        self.config = new_config

        if self.config_model:
            self.config_model.set_value(key, value)

        if self.on_config_change:
            self.on_config_change(self.config)

    def on_switch_change(self, key, active):
        self.update_config(key, active)
