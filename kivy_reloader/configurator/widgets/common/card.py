"""Card component for grouping content"""

from kivy.properties import StringProperty
from kivy.uix.boxlayout import BoxLayout

from kivy_reloader.lang import Builder

Builder.load_file(__file__)


class Card(BoxLayout):
    """Card container with title, description, and content area"""

    title = StringProperty()
    description = StringProperty()
    description = StringProperty()
