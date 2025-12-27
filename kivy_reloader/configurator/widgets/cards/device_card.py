"""Device connection settings card widget."""

import os

from kivy.properties import DictProperty, ObjectProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout

from kivy_reloader.configurator.widgets.common import BoxChipInput
from kivy_reloader.lang import Builder

Builder.load_file(__file__)

MAX_PORT_NUMBER = 65535


class DeviceCard(BoxLayout):
    """Card containing device connection and targeting settings."""

    config = DictProperty({
        'PHONE_IPS': [],
        'ADB_PORT': 5555,
        'RELOADER_PORT': 8050,
    })

    root_path = StringProperty(os.getcwd())
    scroll_view = ObjectProperty(None)
    on_config_change = ObjectProperty(None)

    def __init__(self, **kwargs):
        self.config_model = None
        super().__init__(**kwargs)

    def on_kv_post(self, base_widget):
        """Populate widgets with initial configuration values."""

        # Setup BoxChipInput for PHONE_IPS with IP validation
        chip_input = self.ids.phone_ips_input
        chip_input.values = self.config.get('PHONE_IPS', []) or []
        chip_input.validator = BoxChipInput.validate_ip_address
        chip_input.bind(
            values=lambda instance, values: self.on_phone_ips_change(values)
        )

        # Setup TextFields
        self.ids.adb_port_input.text = str(self.config.get('ADB_PORT', 5555))
        self.ids.reloader_port_input.text = str(self.config.get('RELOADER_PORT', 8050))

    def load_from_model(self):
        """Sync UI controls from the backing config model."""
        if not self.config_model:
            return

        new_config = {}
        for key in self.config.keys():
            new_config[key] = self.config_model.get_value(key)
        self.config = new_config

        # Update chip input
        self.ids.phone_ips_input.values = new_config.get('PHONE_IPS', []) or []

        # Update text fields
        self.ids.adb_port_input.text = str(new_config.get('ADB_PORT', 5555))
        self.ids.reloader_port_input.text = str(new_config.get('RELOADER_PORT', 8050))

    def update_config(self, key, value):
        new_config = self.config.copy()
        new_config[key] = value
        self.config = new_config

        if self.config_model:
            self.config_model.set_value(key, value)

        if self.on_config_change:
            self.on_config_change(self.config)

    def on_phone_ips_change(self, values):
        self.update_config('PHONE_IPS', values)

    def _validate_port(self, text, default, field_id):
        """Validate port number and show error in UI if invalid."""
        field = self.ids.get(field_id)
        if not text:
            if field:
                field.error_text = ''
            return default

        try:
            value = int(text)
            if value < 1:
                if field:
                    field.error_text = 'Port must be at least 1'
                return None
            if value > MAX_PORT_NUMBER:
                if field:
                    field.error_text = f'Port {value} exceeds maximum {MAX_PORT_NUMBER}'
                return None
            if field:
                field.error_text = ''
            return value
        except ValueError:
            if field:
                field.error_text = 'Invalid port number'
            return None

    def on_adb_port_change(self, text):
        value = self._validate_port(text, 5555, 'adb_port_input')
        if value is not None:
            self.update_config('ADB_PORT', value)

    def on_reloader_port_change(self, text):
        value = self._validate_port(text, 8050, 'reloader_port_input')
        if value is not None:
            self.update_config('RELOADER_PORT', value)
