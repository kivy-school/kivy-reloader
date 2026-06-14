"""Deployment exclusions settings card widget."""

import os
import threading

from kivy.properties import DictProperty, ObjectProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout

from kivy_reloader.configurator.widgets.cards.core_card import BUILTIN_EXCLUSIONS
from kivy_reloader.lang import Builder

Builder.load_file(__file__)


class DeploymentCard(BoxLayout):
    """Card showing deployment exclusion information.

    Note: The actual deployment exclusions are configured in the Core card.
    This card provides additional information about built-in exclusions.
    """

    config = DictProperty({
        'FOLDERS_AND_FILES_TO_EXCLUDE_FROM_PHONE': [],
    })

    root_path = StringProperty(os.getcwd())
    scroll_view = ObjectProperty(None)
    on_config_change = ObjectProperty(None)
    build_status = StringProperty('')
    recipe_name = StringProperty('')


    # Expose builtin exclusions to KV
    builtin_exclusions = BUILTIN_EXCLUSIONS

    def __init__(self, **kwargs):
        self.config_model = None
        super().__init__(**kwargs)

    def on_kv_post(self, base_widget):
        """Populate widgets with initial configuration values."""
        self.ids.exclude_from_phone_input.values = (
            self.config.get('FOLDERS_AND_FILES_TO_EXCLUDE_FROM_PHONE', []) or []
        )
        self.ids.exclude_from_phone_input.bind(
            values=lambda instance, values: self.on_exclusions_change(values)
        )

    def load_from_model(self):
        """Sync UI controls from the backing config model."""
        if not self.config_model:
            return

        new_config = {}
        for key in self.config.keys():
            new_config[key] = self.config_model.get_value(key)
        self.config = new_config

        self.ids.exclude_from_phone_input.values = (
            new_config.get('FOLDERS_AND_FILES_TO_EXCLUDE_FROM_PHONE', []) or []
        )

    def update_config(self, key, value):
        new_config = self.config.copy()
        new_config[key] = value
        self.config = new_config

        if self.config_model:
            self.config_model.set_value(key, value)

        if self.on_config_change:
            self.on_config_change(self.config)
    
    def clean_recipe(self):
        import glob, shutil, threading
        recipe = self.recipe_name.strip()
        if not recipe:
            self.build_status = 'Enter a recipe name first'
            return
        pattern = f'.buildozer/android/platform/build-*/build/other_builds/{recipe}'
        paths = glob.glob(pattern)
        if not paths:
            self.build_status = f'No cache found for: {recipe} — check recipe name'
            return
        self.build_status = f'Cleaning {recipe}...'
        def _clean():
            for p in paths:
                shutil.rmtree(p, ignore_errors=True)
            from kivy.clock import Clock
            Clock.schedule_once(lambda dt: setattr(self, 'build_status', f'Cleaned {recipe} build cache'))
        threading.Thread(target=_clean, daemon=True).start()

    def clean_all(self):
        import subprocess, threading
        from pathlib import Path
        self.build_status = 'Running buildozer android clean...'
        def _clean():
            r = subprocess.run(
                ['buildozer', 'android', 'clean'],
                capture_output=True, text=True, timeout=120,
                cwd=str(Path.cwd()),
            )
            from kivy.clock import Clock
            if r.returncode == 0:
                Clock.schedule_once(lambda dt: setattr(self, 'build_status', 'Done — platform rebuilt, downloads preserved'))
            else:
                msg = (r.stdout + r.stderr).strip()[-100:]
                Clock.schedule_once(lambda dt: setattr(self, 'build_status', f'Failed: {msg}'))
        threading.Thread(target=_clean, daemon=True).start()

    def list_recipes(self):
        import subprocess, threading
        from pathlib import Path
        self.build_status = 'Fetching recipes...'
        def _list():
            r = subprocess.run(
                ['buildozer', 'android', 'p4a', '--', 'recipes'],
                capture_output=True, text=True, timeout=30,
                cwd=str(Path.cwd()),
            )
            output = (r.stdout + r.stderr).strip()[:300] or 'No output'
            from kivy.clock import Clock
            Clock.schedule_once(lambda dt: setattr(self, 'build_status', output))
        threading.Thread(target=_list, daemon=True).start()


    def on_exclusions_change(self, values):
        self.update_config('FOLDERS_AND_FILES_TO_EXCLUDE_FROM_PHONE', values)
