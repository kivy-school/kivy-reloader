"""Performance tuning settings card widget."""

import os

from kivy.properties import DictProperty, ObjectProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout

from kivy_reloader.lang import Builder

Builder.load_file(__file__)

# Available render drivers for SDL
RENDER_DRIVERS = [
    {'label': 'Auto (default)', 'value': ''},
    {'label': 'Direct3D', 'value': 'direct3d'},
    {'label': 'OpenGL', 'value': 'opengl'},
    {'label': 'OpenGL ES 2', 'value': 'opengles2'},
    {'label': 'OpenGL ES', 'value': 'opengles'},
    {'label': 'Metal', 'value': 'metal'},
    {'label': 'Software', 'value': 'software'},
]


class PerformanceCard(BoxLayout):
    """Card containing performance tuning settings."""

    config = DictProperty({
        'MAX_SIZE': 0,
        'MAX_FPS': 0,
        'VIDEO_BIT_RATE': '8M',
        'PRINT_FPS': False,
        'RENDER_DRIVER': '',
        'NO_MOUSE_HOVER': True,
        'DISABLE_SCREENSAVER': True,
    })

    root_path = StringProperty(os.getcwd())
    scroll_view = ObjectProperty(None)
    on_config_change = ObjectProperty(None)

    def __init__(self, **kwargs):
        self.config_model = None
        self.render_drivers = RENDER_DRIVERS
        super().__init__(**kwargs)

    def on_kv_post(self, base_widget):
        """Populate widgets with initial configuration values."""
        self.ids.max_size_input.text = str(self.config.get('MAX_SIZE', 0))
        self.ids.max_fps_input.text = str(self.config.get('MAX_FPS', 0))
        self.ids.video_bit_rate_radio.selected_value = self.config.get(
            'VIDEO_BIT_RATE', '8M'
        )
        self.ids.print_fps_switch.active = self.config.get('PRINT_FPS', False)
        self.ids.no_mouse_hover_switch.active = self.config.get('NO_MOUSE_HOVER', True)
        self.ids.disable_screensaver_switch.active = self.config.get(
            'DISABLE_SCREENSAVER', True
        )

        # Set render driver radio
        driver = self.config.get('RENDER_DRIVER', '')
        self.ids.render_driver_radio.selected_value = driver

    def load_from_model(self):
        """Sync UI controls from the backing config model."""
        if not self.config_model:
            return

        new_config = {}
        for key in self.config.keys():
            new_config[key] = self.config_model.get_value(key)
        self.config = new_config

        # Update all fields
        self.ids.max_size_input.text = str(new_config.get('MAX_SIZE', 0))
        self.ids.max_fps_input.text = str(new_config.get('MAX_FPS', 0))
        self.ids.video_bit_rate_radio.selected_value = new_config.get(
            'VIDEO_BIT_RATE', '8M'
        )
        self.ids.print_fps_switch.active = new_config.get('PRINT_FPS', False)
        self.ids.render_driver_radio.selected_value = new_config.get(
            'RENDER_DRIVER', ''
        )
        self.ids.no_mouse_hover_switch.active = new_config.get('NO_MOUSE_HOVER', True)
        self.ids.disable_screensaver_switch.active = new_config.get(
            'DISABLE_SCREENSAVER', True
        )

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

    def on_switch_change(self, key, active):
        self.update_config(key, active)

    def on_video_bit_rate_change(self, value):
        self.update_config('VIDEO_BIT_RATE', value)

    def on_render_driver_change(self, value):
        self.update_config('RENDER_DRIVER', value)
