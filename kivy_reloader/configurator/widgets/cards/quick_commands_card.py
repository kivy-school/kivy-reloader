import subprocess
import sys
from kivy.properties import ListProperty, ObjectProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout

from kivy_reloader.configurator.command_history import get_top, record
from kivy_reloader.lang import Builder

Builder.load_file(__file__)

_PERIODS = {'1 day': 1, '1 week': 7, '1 month': 30}

_DEFAULT_COMMANDS = [
    {'label': 'Compile + deploy', 'command': 'uv run kivy-reloader run build'},
    {'label': 'Hot reload', 'command': 'uv run kivy-reloader run'},
]


class CommandButton(BoxLayout):
    label = StringProperty('')
    command = StringProperty('')
    count = StringProperty('')

    def run(self):
        record(self.label, self.command)
        import threading
        from kivy_reloader.compile_app import select_option
        from kivy_reloader import config

        _OPTION_MAP = {
            'uv run kivy-reloader run build': '1',
            'uv run kivy-reloader run':       '2',
        }

        option = _OPTION_MAP.get(self.command)
        if option:
            app_name = getattr(config, 'APP_NAME', '')
            threading.Thread(
                target=select_option,
                args=(option, app_name),
                daemon=True,
            ).start()
        else:
            subprocess.Popen(
                self.command.split(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )


class QuickCommandsCard(BoxLayout):
    commands = ListProperty([])
    active_period = StringProperty('1 week')
    config_model = ObjectProperty(None, allownone=True)

    def load_from_model(self):
        pass

    def on_kv_post(self, base_widget):
        self.refresh()

    def set_period(self, period: str):
        self.active_period = period
        self.refresh()

    def refresh(self):
        days = _PERIODS[self.active_period]
        top = get_top(n=8, days=days)
        history_cmds = {item['command'] for item in top}
        pinned = [c for c in _DEFAULT_COMMANDS if c['command'] not in history_cmds]
        self.commands = top + pinned

    
    def reset_history(self):
        from kivy_reloader.configurator.command_history import _HISTORY_FILE
        if _HISTORY_FILE.exists():
            _HISTORY_FILE.unlink()
        self.refresh()

    def on_commands(self, instance, commands):
        lst = self.ids.get('command_list')
        if not lst:
            return
        lst.clear_widgets()
        for item in commands:
            btn = CommandButton(
                label=item['label'],
                command=item['command'],
                count=f"×{item['count']}" if item.get('count') else '',
            )
            lst.add_widget(btn)
