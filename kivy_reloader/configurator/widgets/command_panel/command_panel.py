from kivy.properties import BooleanProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout

from kivy_reloader.lang import Builder

Builder.load_file(__file__)


class CommandPanel(BoxLayout):
    is_expanded = BooleanProperty(True)
    current_command = StringProperty('')
    output_log = StringProperty('')

    def log(self, command, output=''):
        self.current_command = command
        entry = f'$ {command}'
        if output:
            entry += f'\n{output}'
        self.output_log = (self.output_log + '\n' + entry).strip()

    def toggle(self):
        self.is_expanded = not self.is_expanded
