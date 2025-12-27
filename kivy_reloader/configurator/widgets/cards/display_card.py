"""Display and interaction settings card widget."""

import os

from kivy.properties import DictProperty, ObjectProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout

from kivy_reloader.lang import Builder

Builder.load_file(__file__)


class DisplayCard(BoxLayout):
    """Card containing display and interaction settings."""

    config = DictProperty({
        'SHOW_TOUCHES': False,
        'STAY_AWAKE': False,
        'TURN_SCREEN_OFF': False,
        'DISPLAY_ORIENTATION': 0,
        'CROP_AREA': '',
    })

    root_path = StringProperty(os.getcwd())
    scroll_view = ObjectProperty(None)
    on_config_change = ObjectProperty(None)

    def __init__(self, **kwargs):
        self.config_model = None
        super().__init__(**kwargs)

    def on_kv_post(self, base_widget):
        """Populate widgets with initial configuration values."""
        self.ids.show_touches_switch.active = self.config.get('SHOW_TOUCHES', False)
        self.ids.stay_awake_switch.active = self.config.get('STAY_AWAKE', False)
        self.ids.turn_screen_off_switch.active = self.config.get(
            'TURN_SCREEN_OFF', False
        )
        self.ids.crop_area_input.text = self.config.get('CROP_AREA', '')

        # Set orientation radio
        orientation = self.config.get('DISPLAY_ORIENTATION', 0)
        self.ids.orientation_radio.selected_value = str(orientation)

    def load_from_model(self):
        """Sync UI controls from the backing config model."""
        if not self.config_model:
            return

        new_config = {}
        for key in self.config.keys():
            new_config[key] = self.config_model.get_value(key)
        self.config = new_config

        # Update all fields
        self.ids.show_touches_switch.active = new_config.get('SHOW_TOUCHES', False)
        self.ids.stay_awake_switch.active = new_config.get('STAY_AWAKE', False)
        self.ids.turn_screen_off_switch.active = new_config.get(
            'TURN_SCREEN_OFF', False
        )
        self.ids.crop_area_input.text = new_config.get('CROP_AREA', '')
        orientation = new_config.get('DISPLAY_ORIENTATION', 0)
        self.ids.orientation_radio.selected_value = str(orientation)

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

    def on_orientation_change(self, value):
        try:
            self.update_config('DISPLAY_ORIENTATION', int(value))
        except ValueError:
            pass

    def on_crop_area_change(self, text):
        """Validate and update crop area. Format: width:height:x:y or empty."""
        text = text.strip()

        # Empty is valid
        if not text:
            self.update_config('CROP_AREA', '')
            return

        # Validate format: width:height:x:y
        if self._validate_crop_area(text):
            self.update_config('CROP_AREA', text)
        # If invalid, don't update config (keep old value)

    def _validate_crop_area(self, text):
        """Check if crop area matches format width:height:x:y with valid integers."""
        parts = text.split(':')
        if len(parts) != 4:
            return False

        try:
            for part in parts:
                val = int(part)
                if val < 0:
                    return False
            return True
        except ValueError:
            return False
