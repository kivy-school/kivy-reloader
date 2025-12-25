"""GUI launcher for the configurator.

This module provides the run_gui function that initializes the Kivy app
with a ConfigModel and launches the configurator interface.
"""

from __future__ import annotations

from pathlib import Path

import trio

from kivy_reloader.app import App
from kivy_reloader.configurator.config_loader import merge_with_defaults
from kivy_reloader.configurator.model import ConfigModel
from kivy_reloader.configurator.schema import FIELD_DEFS
from kivy_reloader.configurator.screens.core import CoreScreen
from kivy_reloader.configurator.theme import load_theme


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
    # Load theme colors/fonts into global_idmap
    load_theme()

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
        def build(self):
            config_model = create_config_model()
            self.core_screen = CoreScreen()
            self.core_screen.config_model = config_model
            return self.core_screen

    app = ConfiguratorGUI()
    trio.run(app.async_run, 'trio')
