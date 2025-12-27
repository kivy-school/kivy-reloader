"""Advanced options settings card widget."""

import os

from kivy.properties import DictProperty, ObjectProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout

from kivy_reloader.lang import Builder

Builder.load_file(__file__)


class AdvancedCard(BoxLayout):
    """Card containing advanced power features and lifecycle settings."""

    config = DictProperty({
        'NO_CONTROL': False,
        'SHORTCUT_MOD': 'lalt,lsuper',
        'KILL_ADB_ON_CLOSE': False,
        'POWER_OFF_ON_CLOSE': False,
        'TIME_LIMIT': 0,
        'SCREEN_OFF_TIMEOUT': 0,
        'RECORD_SESSION': False,
        'RECORD_FILE_PATH': 'session_recording.mp4',
    })

    root_path = StringProperty(os.getcwd())
    scroll_view = ObjectProperty(None)
    on_config_change = ObjectProperty(None)

    def __init__(self, **kwargs):
        self.config_model = None
        super().__init__(**kwargs)

    def on_kv_post(self, base_widget):
        """Populate widgets with initial configuration values."""
        self.ids.no_control_switch.active = self.config.get('NO_CONTROL', False)
        self.ids.shortcut_mod_input.text = self.config.get(
            'SHORTCUT_MOD', 'lalt,lsuper'
        )
        self.ids.kill_adb_switch.active = self.config.get('KILL_ADB_ON_CLOSE', False)
        self.ids.power_off_switch.active = self.config.get('POWER_OFF_ON_CLOSE', False)
        self.ids.time_limit_input.text = str(self.config.get('TIME_LIMIT', 0))
        self.ids.screen_off_timeout_input.text = str(
            self.config.get('SCREEN_OFF_TIMEOUT', 0)
        )
        self.ids.record_session_switch.active = self.config.get('RECORD_SESSION', False)
        self.ids.record_file_path_input.text = self.config.get(
            'RECORD_FILE_PATH', 'session_recording.mp4'
        )

        self._update_recording_controls_state()

    def load_from_model(self):
        """Sync UI controls from the backing config model."""
        if not self.config_model:
            return

        new_config = {}
        for key in self.config.keys():
            new_config[key] = self.config_model.get_value(key)
        self.config = new_config

        # Update all fields
        self.ids.no_control_switch.active = new_config.get('NO_CONTROL', False)
        self.ids.shortcut_mod_input.text = new_config.get('SHORTCUT_MOD', 'lalt,lsuper')
        self.ids.kill_adb_switch.active = new_config.get('KILL_ADB_ON_CLOSE', False)
        self.ids.power_off_switch.active = new_config.get('POWER_OFF_ON_CLOSE', False)
        self.ids.time_limit_input.text = str(new_config.get('TIME_LIMIT', 0))
        self.ids.screen_off_timeout_input.text = str(
            new_config.get('SCREEN_OFF_TIMEOUT', 0)
        )
        self.ids.record_session_switch.active = new_config.get('RECORD_SESSION', False)
        self.ids.record_file_path_input.text = new_config.get(
            'RECORD_FILE_PATH', 'session_recording.mp4'
        )

        self._update_recording_controls_state()

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

    def on_text_field_change(self, key, text):
        self.update_config(key, text)

    def on_int_field_change(self, key, text, default=0):
        try:
            value = int(text) if text else default
            self.update_config(key, value)
        except ValueError:
            pass

    def on_record_session_change(self, active):
        self.update_config('RECORD_SESSION', active)
        self._update_recording_controls_state()

    def _update_recording_controls_state(self):
        """Update the visual state of recording file path based on RECORD_SESSION setting."""
        enabled = self.config.get('RECORD_SESSION', False)
        opacity = 1.0 if enabled else 0.4

        self.ids.record_file_container.opacity = opacity
        self.ids.record_file_container.disabled = not enabled
