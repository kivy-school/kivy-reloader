from datetime import datetime
from kivy.properties import BooleanProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy_reloader.configurator.event_bus import EventBus
from kivy_reloader.lang import Builder

Builder.load_file(__file__)


class CommandPanel(BoxLayout):
    is_expanded = BooleanProperty(True)
    current_command = StringProperty('')
    output_log = StringProperty('')

    def on_kv_post(self, base_widget):
        EventBus.on('terminal_log', self._on_terminal_log)
        EventBus.on('terminal_output', self._on_terminal_output)

    def _on_terminal_log(self, command='', **kwargs):
        self.log(command)

    def _on_terminal_output(self, output='', **kwargs):
        if output.strip():
            self.output_log = (self.output_log + '\n' + output.strip()).strip()

    def log(self, command, output=''):
        self.current_command = command
        ts = datetime.now().strftime('%H:%M:%S')
        entry = f'[{ts}] $ {command}'
        if output:
            entry += f'\n{output}'
        self.output_log = (self.output_log + '\n' + entry).strip()

    def copy_command(self):
        from kivy.core.clipboard import Clipboard
        Clipboard.copy(self.current_command)

    def copy_log(self):
        from kivy.core.clipboard import Clipboard
        Clipboard.copy(self.output_log)

    def toggle(self):
        self.is_expanded = not self.is_expanded
