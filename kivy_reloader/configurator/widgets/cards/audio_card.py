"""Audio settings card widget."""

import os

from kivy.properties import DictProperty, ObjectProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout

from kivy_reloader.lang import Builder

Builder.load_file(__file__)


class AudioCard(BoxLayout):
    """Card containing audio forwarding settings."""

    config = DictProperty({
        'NO_AUDIO': True,
        'AUDIO_SOURCE': 'output',
        'NO_AUDIO_PLAYBACK': False,
        'AUDIO_BIT_RATE': '128K',
    })

    root_path = StringProperty(os.getcwd())
    scroll_view = ObjectProperty(None)
    on_config_change = ObjectProperty(None)

    def __init__(self, **kwargs):
        self.config_model = None
        super().__init__(**kwargs)

    def on_kv_post(self, base_widget):
        """Populate widgets with initial configuration values."""
        self.ids.no_audio_switch.active = self.config.get('NO_AUDIO', True)
        self.ids.audio_source_radio.selected_value = self.config.get(
            'AUDIO_SOURCE', 'output'
        )
        self.ids.no_audio_playback_switch.active = self.config.get(
            'NO_AUDIO_PLAYBACK', False
        )
        self.ids.audio_bit_rate_radio.selected_value = self.config.get(
            'AUDIO_BIT_RATE', '128K'
        )

        # Update visual state
        self._update_audio_controls_state()

    def load_from_model(self):
        """Sync UI controls from the backing config model."""
        if not self.config_model:
            return

        new_config = {}
        for key in self.config.keys():
            new_config[key] = self.config_model.get_value(key)
        self.config = new_config

        # Update all fields
        self.ids.no_audio_switch.active = new_config.get('NO_AUDIO', True)
        self.ids.audio_source_radio.selected_value = new_config.get(
            'AUDIO_SOURCE', 'output'
        )
        self.ids.no_audio_playback_switch.active = new_config.get(
            'NO_AUDIO_PLAYBACK', False
        )
        self.ids.audio_bit_rate_radio.selected_value = new_config.get(
            'AUDIO_BIT_RATE', '128K'
        )

        self._update_audio_controls_state()

    def update_config(self, key, value):
        new_config = self.config.copy()
        new_config[key] = value
        self.config = new_config

        if self.config_model:
            self.config_model.set_value(key, value)

        if self.on_config_change:
            self.on_config_change(self.config)

    def on_no_audio_change(self, active):
        self.update_config('NO_AUDIO', active)
        self._update_audio_controls_state()

    def _update_audio_controls_state(self):
        """Update the visual state of audio controls based on NO_AUDIO setting."""
        disabled = self.config.get('NO_AUDIO', True)
        opacity = 0.4 if disabled else 1.0

        # Apply dimming to audio controls container
        self.ids.audio_controls_container.opacity = opacity
        self.ids.audio_controls_container.disabled = disabled

    def on_audio_source_change(self, value):
        self.update_config('AUDIO_SOURCE', value)

    def on_no_audio_playback_change(self, active):
        self.update_config('NO_AUDIO_PLAYBACK', active)

    def on_audio_bit_rate_change(self, value):
        self.update_config('AUDIO_BIT_RATE', value)
