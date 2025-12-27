"""Chip input component for entering multiple values"""

from kivy.properties import ListProperty, ObjectProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout

from kivy_reloader.lang import Builder

Builder.load_file(__file__)


class Chip(BoxLayout):
    """Individual chip/badge widget"""

    text = StringProperty()
    on_remove = ObjectProperty(None)

    def remove(self):
        """Remove this chip"""
        if self.on_remove:
            self.on_remove(self.text)


class ChipInput(BoxLayout):
    """Input field that shows values as chips/badges"""

    values = ListProperty([])
    placeholder = StringProperty('Enter value and press Enter')

    def __init__(self, **kwargs):
        self.register_event_type('on_values')
        super().__init__(**kwargs)
        self.chips = []

    def on_values(self, *args):
        """Event fired when values change"""
        self._rebuild_chips()

    def on_kv_post(self, base_widget):
        """Setup after KV is loaded"""
        self._rebuild_chips()

    def _rebuild_chips(self):
        """Rebuild all chip widgets"""
        container = self.chips_container
        container.clear_widgets()
        self.chips = []

        for value in self.values:
            chip = Chip(text=value, on_remove=self.remove_value)
            container.add_widget(chip)
            self.chips.append(chip)

    def add_value(self, value):
        """Add a new value"""
        value = value.strip()
        if value and value not in self.values:
            self.values += [value]

            # Clear input
            self.text_input.text = ''

    def remove_value(self, value):
        """Remove a value"""
        if value in self.values:
            self.values = [v for v in self.values if v != value]
            self.values = [v for v in self.values if v != value]
