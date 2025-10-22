from kivy.metrics import dp
from kivy.properties import ListProperty, ObjectProperty
from kivy.uix.textinput import TextInput

from kivy_reloader.lang import Builder

Builder.load_file(__file__)


class TextField(TextInput):
    radius: list | tuple = ListProperty([dp(8)])
    texture = ObjectProperty(None, allownone=True)
    texture_size = ListProperty([0, 0])
    texture_size = ListProperty([0, 0])
