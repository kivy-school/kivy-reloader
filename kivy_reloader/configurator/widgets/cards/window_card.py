"""Window settings card widget."""

import os

from kivy.properties import DictProperty, ObjectProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout

from kivy_reloader.lang import Builder

Builder.load_file(__file__)


class WindowCard(BoxLayout):
    """Card containing screen mirroring window settings."""

    config = DictProperty({
        'WINDOW_X': 1200,
        'WINDOW_Y': 100,
        'WINDOW_WIDTH': 280,
        'WINDOW_HEIGHT': 0,
        'WINDOW_TITLE': 'Kivy Reloader',
        'ALWAYS_ON_TOP': True,
        'FULLSCREEN': False,
        'WINDOW_BORDERLESS': False,
    })

    root_path = StringProperty(os.getcwd())
    scroll_view = ObjectProperty(None)
    on_config_change = ObjectProperty(None)

    def __init__(self, **kwargs):
        self.config_model = None
        super().__init__(**kwargs)

    def on_kv_post(self, base_widget):
        """Populate widgets with initial configuration values."""
        # Position fields
        self.ids.window_x_input.text = str(self.config.get('WINDOW_X', 1200))
        self.ids.window_y_input.text = str(self.config.get('WINDOW_Y', 100))

        # Size fields
        self.ids.window_width_input.text = str(self.config.get('WINDOW_WIDTH', 280))
        self.ids.window_height_input.text = str(self.config.get('WINDOW_HEIGHT', 0))

        # Title field
        self.ids.window_title_input.text = self.config.get(
            'WINDOW_TITLE', 'Kivy Reloader'
        )

        # Behavior switches
        self.ids.always_on_top_switch.active = self.config.get('ALWAYS_ON_TOP', True)
        self.ids.fullscreen_switch.active = self.config.get('FULLSCREEN', False)
        self.ids.borderless_switch.active = self.config.get('WINDOW_BORDERLESS', False)

    def load_from_model(self):
        """Sync UI controls from the backing config model."""
        if not self.config_model:
            return

        new_config = {}
        for key in self.config.keys():
            new_config[key] = self.config_model.get_value(key)
        self.config = new_config

        # Update all fields
        self.ids.window_x_input.text = str(new_config.get('WINDOW_X', 1200))
        self.ids.window_y_input.text = str(new_config.get('WINDOW_Y', 100))
        self.ids.window_width_input.text = str(new_config.get('WINDOW_WIDTH', 280))
        self.ids.window_height_input.text = str(new_config.get('WINDOW_HEIGHT', 0))
        self.ids.window_title_input.text = new_config.get(
            'WINDOW_TITLE', 'Kivy Reloader'
        )
        self.ids.always_on_top_switch.active = new_config.get('ALWAYS_ON_TOP', True)
        self.ids.fullscreen_switch.active = new_config.get('FULLSCREEN', False)
        self.ids.borderless_switch.active = new_config.get('WINDOW_BORDERLESS', False)

    def update_config(self, key, value):
        new_config = self.config.copy()
        new_config[key] = value
        self.config = new_config

        if self.config_model:
            self.config_model.set_value(key, value)

        if self.on_config_change:
            self.on_config_change(self.config)

    def on_int_field_change(self, key, text, default=0):
        try:
            value = int(text) if text else default
            self.update_config(key, value)
        except ValueError:
            pass

    def on_text_field_change(self, key, text):
        self.update_config(key, text)

    def on_switch_change(self, key, active):
        self.update_config(key, active)
