import subprocess
from kivy.properties import BooleanProperty, ListProperty, ObjectProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy_reloader.configurator.command_history import get_top, record
from kivy_reloader.configurator.event_bus import EventBus
from kivy_reloader.lang import Builder

Builder.load_file(__file__)

_PERIODS = {'1 day': 1, '1 week': 7, '1 month': 30}

_STATIC_COMMANDS = [
    {'label': 'Compile + deploy', 'command': 'uv run kivy-reloader run build'},
    {'label': 'Hot reload', 'command': 'uv run kivy-reloader run'},
]

def _stream_proc_output(proc):
    from kivy.clock import Clock
    try:
        for line in proc.stdout:
            line = line.rstrip('\n')
            if line:
                Clock.schedule_once(lambda dt, l=line: EventBus.emit('logcat_line', line=l))
    except Exception:
        pass


class CommandButton(BoxLayout):
    label = StringProperty('')
    command = StringProperty('')
    count = StringProperty('')
    display_command = StringProperty('')
    card_action_handler = ObjectProperty(None, allownone=True)

    def run(self):
        record(self.label, self.command)
        EventBus.emit('terminal_log', command=self.command)
        if self.command.startswith('__') and self.command.endswith('__') and self.card_action_handler:
            self.card_action_handler(self.command)
            return

        # Config setter (recorded as SET:KEY:VALUE)
        if self.command.startswith('SET:'):
            parts = self.command.split(':', 2)
            if len(parts) == 3:
                EventBus.emit('set_config', key=parts[1], value=parts[2])
            return


        import threading
        from kivy_reloader.compile_app import select_option
        from kivy_reloader import config

        _OPTION_MAP = {
            'uv run kivy-reloader run build': '1',
            'uv run kivy-reloader run':       '2',
        }

        option = _OPTION_MAP.get(self.command)
        if option:
            threading.Thread(
                target=select_option,
                args=(option, getattr(config, 'APP_NAME', '')),
                daemon=True,
            ).start()
        else:
            proc = subprocess.Popen(
                self.command.split(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
                text=True,
                encoding='utf-8',
                errors='replace',
            )
            threading.Thread(target=_stream_proc_output, args=(proc,), daemon=True).start()


class QuickCommandsCard(BoxLayout):
    commands = ListProperty([])
    active_period = StringProperty('1 week')
    config_model = ObjectProperty(None, allownone=True)
    hot_reload_on_phone = BooleanProperty(True)
    stream_using = StringProperty('WIFI')
    target_ip = StringProperty('')
    recipe_name = StringProperty('')
    screen_size = StringProperty('')
    screen_dpi = StringProperty('')

    def load_from_model(self):
        if not self.config_model:
            return
        self.hot_reload_on_phone = bool(self.config_model.get_value('HOT_RELOAD_ON_PHONE'))
        self.stream_using = str(self.config_model.get_value('STREAM_USING') or 'WIFI')
        self.target_ip = str(self.config_model.get_value('TARGET_IP') or '')
        self.screen_size = str(self.config_model.get_value('SCREEN_SIZE') or '')
        self.screen_dpi = str(self.config_model.get_value('SCREEN_DPI') or '')


    def _save(self, key, value):
        if self.config_model:
            self.config_model.set_value(key, value)
            self.config_model.save(create_backup=False)

    def toggle_hot_reload(self):
        self.hot_reload_on_phone = not self.hot_reload_on_phone
        self._save('HOT_RELOAD_ON_PHONE', self.hot_reload_on_phone)

    def set_stream_using(self, value):
        self.stream_using = value
        self._save('STREAM_USING', value)
        record(f'Stream: {value}', f'SET:STREAM_USING:{value}')

    def set_screen_size(self, value):
        self.screen_size = value
        self._save('SCREEN_SIZE', value)

    def set_screen_dpi(self, value):
        self.screen_dpi = value
        self._save('SCREEN_DPI', value)

    def set_target_ip(self, text):
        text = text.strip()
        if text != self.target_ip:
            self.target_ip = text
            self._save('TARGET_IP', text)

    def on_kv_post(self, base_widget):
        EventBus.on('card_registered', lambda **kw: self.refresh())
        EventBus.on('set_config', self._on_set_config)
        self.refresh()


    def set_period(self, period: str):
        self.active_period = period
        self.refresh()

    def refresh(self):
        days = _PERIODS[self.active_period]
        top = get_top(n=8, days=days)
        history_cmds = {item['command'] for item in top}
        static = [c for c in _STATIC_COMMANDS if c['command'] not in history_cmds]
        card_actions = []
        for card in EventBus.get_cards().values():
            for qa in getattr(card, 'quick_actions', []):
                if qa['command'] not in history_cmds:
                    card_actions.append(qa)
        self.commands = top + static + card_actions

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
                display_command=item.get('display', ''),
                count=f"×{item['count']}" if item.get('count') else '',
                card_action_handler=self._handle_card_action,
            )
            lst.add_widget(btn)



    def _handle_card_action(self, action):
        for card in EventBus.get_cards().values():
            for qa in getattr(card, 'quick_actions', []):
                if qa.get('command') == action:
                    fn = getattr(card, qa['fn'], None)
                    if fn:
                        kwargs = {}
                        if qa.get('needs_input') == 'recipe':
                            kwargs['recipe_override'] = self.recipe_name.strip()
                        fn(**kwargs)
                    return

    def _on_set_config(self, key, value, **kwargs):
        # normalize booleans stored as strings
        if value in ('True', 'true'): value = True
        elif value in ('False', 'false'): value = False
        prop = key.lower()
        if hasattr(self, prop):
            setattr(self, prop, prop_val := value)
        self._save(key, value)
