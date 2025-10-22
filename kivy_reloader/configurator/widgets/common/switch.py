"""Custom Switch component matching the design"""

from kivy.properties import BooleanProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout

from kivy_reloader.lang import Builder

Builder.load_file(__file__)


class CustomSwitch(BoxLayout):
    """Toggle switch with label and description"""

    title = StringProperty()
    description = StringProperty()
    active = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def on_active(self, instance, value):
        """Event fired when active state changes

        This is called automatically when the active property changes.
        In KV files, you can bind to this with: on_active: your_handler(self.active)
        """
        pass

    def toggle(self):
        """Toggle the switch state"""
        self.active = not self.active
