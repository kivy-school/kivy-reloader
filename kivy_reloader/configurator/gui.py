"""GUI launcher for the configurator.

This module provides the run_gui function that initializes the Kivy app
with a ConfigModel and launches the configurator interface.
"""
from __future__ import annotations

import json
from pathlib import Path

import trio

from kivy.clock import Clock
from kivy.core.window import Window 
from kivy.app import App
from kivy_reloader.configurator.config_loader import merge_with_defaults
from kivy_reloader.configurator.model import ConfigModel
from kivy_reloader.configurator.schema import FIELD_DEFS
from kivy_reloader.configurator.screens.core import CoreScreen
from kivy_reloader.configurator.theme import load_theme

def _prefs_path(base: Path) -> Path:
    return base / '.kivy-reloader' / 'prefs.json'
def _load_prefs(base: Path) -> dict:
    path = _prefs_path(base)
    if path.exists():
        try:
          return json.loads(path.read_text())
        except Exception:
            pass
    return {}

def _save_prefs(base: Path, prefs: dict) -> None:
    path = _prefs_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(prefs, indent=2)) 

def run_gui(
    base: Path,
    config_path: Path,
    debug: bool = False,
) -> None:
    """Run the GUI configurator.

    Args:
        base: Base directory of the project
        config_path: Path to the config file (kivy-reloader.toml)
        debug: Enable debug mode
    """
    prefs = _load_prefs(base)
    dark_mode = prefs.get('dark_mode', False)
    # Load theme colors/fonts into global_idmap
    load_theme(dark_mode=dark_mode) 

    # Create backup directory
    backup_dir = base / '.kivy-reloader' / 'backups'

    def create_config_model() -> ConfigModel:
        """Load configuration from disk or defaults for each build."""
        if config_path.exists():
            return ConfigModel.from_file(config_path, backup_dir=backup_dir)

        defaults = merge_with_defaults({}, FIELD_DEFS)
        return ConfigModel(defaults, config_path=config_path, backup_dir=backup_dir)

    # Create and run the Kivy app
    class ConfiguratorGUI(App):
        DEBUG = False
        RAISE_ERROR = True
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self._dark_mode = dark_mode
            self._base = base 
        def build(self):
            config_model = create_config_model()
            self.core_screen = CoreScreen()
            self.core_screen.config_model = config_model
            pyproject = base / 'pyproject.toml'
            text = pyproject.read_text() if pyproject.exists() else ''
            backend = 'ksproject' if '[tool.kivy-school]' in text else 'buildozer'
            self.title = f'Kivy Flightdeck [{backend}]' # 🛩️ for dev, ✈️ for prod
            return self.core_screen

        def on_start(self):
            Clock.schedule_once(
                lambda dt: setattr(self.core_screen.toolbar, 'is_dark_mode', self._dark_mode),
                0,
                )
        def toggle_dark_mode(self, current_screen):
            self._dark_mode = not self._dark_mode
            _save_prefs(self._base, {**_load_prefs(self._base), 'dark_mode': self._dark_mode})
            load_theme(dark_mode=self._dark_mode)
            config_model = current_screen.config_model
            Window.unbind(on_keyboard=current_screen._on_keyboard)
            Window.remove_widget(current_screen)
            new_screen = CoreScreen()
            new_screen.config_model = config_model
            self.core_screen = new_screen
            Window.add_widget(new_screen)
            Clock.schedule_once(
                lambda dt: setattr(new_screen.toolbar, 'is_dark_mode', self._dark_mode),
                0,
            ) 

    app = ConfiguratorGUI()
    trio.run(app.async_run, 'trio')


if __name__ == '__main__':
    from pathlib import Path
    run_gui(base=Path.cwd(), config_path=Path.cwd() / 'kivy-reloader.toml')
