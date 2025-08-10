"""GUI layer for the configurator (initial placeholder).

Contains the minimal Kivy App used in the very first incremental step.
Later this file will evolve (or be split) into multiple modules for
widgets, controllers, and KV definitions.
"""

from __future__ import annotations

from pathlib import Path

from kivy.app import App
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ObjectProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView

from .config_loader import load_config_values
from .model import ConfigModel


class _Root(BoxLayout):
    pass


class _ConfiguratorApp(App):
    title = 'Kivy Reloader Configurator (Preview)'
    config_path: Path = ObjectProperty()
    debug: bool = BooleanProperty(False)
    missing_config: bool = BooleanProperty(False)

    def on_start(self):
        # ESC closes window
        Window.bind(on_key_down=self._on_key_down)

    def _on_key_down(self, _window, keycode, *_):
        ESCAPE_KEY = 27
        if keycode == ESCAPE_KEY:
            self.stop()
            return True
        return False

    def build(self):
        root = _Root(orientation='vertical', padding=dp(12), spacing=dp(8))

        header = Label(
            text='[b]Kivy Reloader Configurator[/b]',
            markup=True,
            font_size=dp(18),
            size_hint_y=None,
            height=dp(34),
            halign='center',
        )
        root.add_widget(header)

        body_box = BoxLayout(orientation='vertical', spacing=dp(8), size_hint_y=None)
        body_box.bind(minimum_height=body_box.setter('height'))

        # Load current raw values + create model
        raw_values = load_config_values(self.config_path)
        model = ConfigModel(raw_values)

        if self.missing_config:
            body_box.add_widget(
                Label(
                    text=(
                        '[color=ff5555]Config file not found.[/color]\n'
                        "Run 'kivy-reloader init' to generate kivy-reloader.toml.\n"
                        f'Expected path: [i]{self.config_path}[/i]'
                    ),
                    markup=True,
                    halign='center',
                )
            )
        else:
            body_box.add_widget(
                Label(
                    text=(
                        f'[b]Loaded {len(raw_values)} keys; '
                        f'{len(model.unknown)} unknown[/b]'
                    ),
                    markup=True,
                    size_hint_y=None,
                    height=dp(24),
                    halign='center',
                )
            )
            grid = GridLayout(
                cols=4, spacing=dp(4), padding=(0, 0, 0, dp(4)), size_hint_y=None
            )
            grid.bind(minimum_height=grid.setter('height'))
            grid.add_widget(Label(text='[b]Key[/b]', markup=True))
            grid.add_widget(Label(text='[b]Current[/b]', markup=True))
            grid.add_widget(Label(text='[b]Default[/b]', markup=True))
            grid.add_widget(Label(text='[b]Unsaved[/b]', markup=True))
            for st in model.iter():
                grid.add_widget(
                    Label(
                        text=st.field.key,
                        halign='left',
                        size_hint_y=None,
                        height=dp(22),
                    )
                )
                grid.add_widget(
                    Label(
                        text=str(st.value),
                        halign='left',
                        size_hint_y=None,
                        height=dp(22),
                    )
                )
                same = st.value == st.default
                default_color = '55ff55' if same else 'ffaa55'
                grid.add_widget(
                    Label(
                        text=f'[color={default_color}]{st.default}[/color]',
                        markup=True,
                        halign='left',
                        size_hint_y=None,
                        height=dp(22),
                    )
                )
                unsaved_mark = '●' if st.unsaved else ''
                grid.add_widget(
                    Label(
                        text=f'[color=ff5555]{unsaved_mark}[/color]',
                        markup=True,
                        halign='center',
                        size_hint_y=None,
                        height=dp(22),
                    )
                )
            body_box.add_widget(grid)

        if self.debug:
            body_box.add_widget(
                Label(
                    text='[color=888888]Debug mode active[/color]',
                    markup=True,
                    font_size=dp(12),
                    halign='center',
                )
            )

        scroll = ScrollView()
        scroll.add_widget(body_box)
        root.add_widget(scroll)

        btn_bar = BoxLayout(
            orientation='horizontal', size_hint_y=None, height=dp(40), spacing=dp(8)
        )
        btn_bar.add_widget(
            Button(text='Close (Esc)', on_release=lambda *_: self.stop())
        )
        root.add_widget(btn_bar)
        return root


def run_gui(base: Path, config_path: Path, debug: bool = False) -> None:  # noqa: D401
    configurator = _ConfiguratorApp()
    configurator.config_path = config_path
    configurator.debug = debug
    configurator.missing_config = not config_path.exists()

    # Adjust default window size before run (do not override user-changed size)
    if Window.size == (800, 600):  # typical default
        Window.size = (640, 420)

    configurator.run()
