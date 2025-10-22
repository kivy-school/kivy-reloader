"""Box-style chip input component with chips displayed in a grid"""

from kivy.properties import ListProperty, StringProperty
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

    def add_value(self, value):
        """Add a new value"""
        value = value.strip()
        if value.endswith('/'):
            value = value[:-1]
        if value and value not in self.values:
            self.values += [value]
            self.text_input.text = ''

    def remove_value(self, value):
        """Remove a value"""
        if value in self.values:
            self.values = [v for v in self.values if v != value]
            self.values = [v for v in self.values if v != value]
