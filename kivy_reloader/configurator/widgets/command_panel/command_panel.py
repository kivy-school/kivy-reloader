from datetime import datetime
from kivy.properties import BooleanProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy_reloader.configurator.event_bus import EventBus
from kivy_reloader.lang import Builder

Builder.load_file(__file__)


class CommandPanel(BoxLayout):
    is_expanded = BooleanProperty(True)
    active_tab = StringProperty('terminal')
    current_command = StringProperty('')
    output_log = StringProperty('')
    logcat_log = StringProperty('')

    def on_kv_post(self, base_widget):
        EventBus.on('terminal_log', self._on_terminal_log)
        EventBus.on('terminal_output', self._on_terminal_output)
        EventBus.on('logcat_line', self._on_logcat_line)

    def _on_terminal_log(self, command='', **kwargs):
        self.log(command)

    def _on_terminal_output(self, output='', **kwargs):
        if output.strip():
            self.output_log = (self.output_log + '\n' + output.strip()).strip()

    def _on_logcat_line(self, line='', **kwargs):
        if line:
            self.logcat_log = (self.logcat_log + '\n' + line).lstrip('\n')

    def log(self, command, output=''):
        self.current_command = command
        ts = datetime.now().strftime('%H:%M:%S')
        entry = f'[{ts}] $ {command}'
        if output:
            entry += f'\n{output}'
        self.output_log = (self.output_log + '\n' + entry).strip()

    def switch_tab(self, tab):
        self.active_tab = tab

    def copy_log(self):
        from kivy.core.clipboard import Clipboard
        text = self.logcat_log if self.active_tab == 'logcat' else self.output_log
        Clipboard.copy(text)

    def copy_command(self):
        from kivy.core.clipboard import Clipboard
        Clipboard.copy(self.current_command)

    def toggle(self):
        self.is_expanded = not self.is_expanded
