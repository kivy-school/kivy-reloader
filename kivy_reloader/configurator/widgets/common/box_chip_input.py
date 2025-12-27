"""Box-style chip input component with chips displayed in a grid"""

import re

from kivy.clock import Clock
from kivy.properties import ListProperty, ObjectProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout

from kivy_reloader.lang import Builder

Builder.load_file(__file__)


class EditableChip(BoxLayout):
    """Individual chip/badge widget with remove button"""

    __events__ = ('on_remove',)

    text = StringProperty('')

    def on_remove(self):
        """Event fired when remove button is pressed"""


class BoxChipInput(BoxLayout):
    """Input field with chips displayed in a grid box below"""

    values = ListProperty([])
    placeholder = StringProperty('Enter value and press Enter')
    error_text = StringProperty('')

    # Optional callable: validator(value) -> (is_valid, error_message)
    validator = ObjectProperty(None, allownone=True)

    # Optional callable: transformer(value) -> transformed_value
    transformer = ObjectProperty(None, allownone=True)

    def add_value(self, value):
        """Add a new value with optional validation and transformation"""
        value = value.strip()
        if value.endswith('/'):
            value = value[:-1]

        if not value:
            return

        # Apply transformer if provided (e.g., capitalize service names)
        if self.transformer:
            value = self.transformer(value)

        # Apply validator if provided (e.g., validate IP address)
        if self.validator:
            is_valid, error_msg = self.validator(value)
            if not is_valid:
                self.error_text = error_msg
                self._clear_error_after_delay()
                return

        # Ensure values is a list (handles None case)
        current_values = self.values if self.values is not None else []
        if value not in current_values:
            self.values = current_values + [value]
            self.text_input.text = ''
            self.error_text = ''

    def _clear_error_after_delay(self):
        """Clear error message after 3 seconds"""
        Clock.schedule_once(lambda dt: setattr(self, 'error_text', ''), 3)

    def remove_value(self, value):
        """Remove a value"""
        current_values = self.values if self.values is not None else []
        if value in current_values:
            self.values = [v for v in current_values if v != value]

    @staticmethod
    def validate_ip_address(value):
        """Validate IPv4 address format. Returns (is_valid, error_message)."""
        # IPv4 pattern
        pattern = r'^((25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])\.){3}(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])$'
        if re.match(pattern, value):
            return (True, '')
        return (False, f"Invalid IP address: '{value}'. Use format like 192.168.1.68")

    @staticmethod
    def transform_service_name(value):
        """Transform service name: first letter uppercase, rest lowercase."""
        if value:
            return value[0].upper() + value[1:].lower()
        return value
