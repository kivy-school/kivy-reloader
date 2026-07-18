"""Deployment exclusions settings card widget."""

import os
import shutil
import subprocess
import threading
from pathlib import Path

from kivy.properties import DictProperty, ObjectProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout

from kivy_reloader.configurator.backend_detect import detect_backend
from kivy_reloader.configurator.event_bus import EventBus
from kivy_reloader.configurator.widgets.cards.core_card import BUILTIN_EXCLUSIONS
from kivy_reloader.lang import Builder

Builder.load_file(__file__)


_QUICK_ACTIONS_BUILDOZER = [
    {
        'label': 'Full clean (keep downloads)',
        'fn': 'clean_all',
        'command': '__full_clean__',
        'display': 'buildozer android clean',
    },
    {
        'label': 'App clean (redownload + rebuild)',
        'fn': 'app_clean',
        'command': '__app_clean__',
        'display': 'buildozer appclean',
    },
    {
        'label': 'Clean recipe',
        'fn': 'clean_recipe',
        'command': '__clean_recipe__',
        'display': 'rm -rf .buildozer/.../other_builds/<recipe>',
        'needs_input': 'recipe',
    },
]
_QUICK_ACTIONS_KSPROJECT = [
    {
        'label': 'Full clean (keep downloads)',
        'fn': 'clean_all',
        'command': '__full_clean__',
        'display': 'clear ksproject site-packages cache + gradle clean',
    },
    {
        'label': 'App clean (rebuild gradle project)',
        'fn': 'app_clean',
        'command': '__app_clean__',
        'display': 'rm -rf project_dist/gradle',
    },
]


class DeploymentCard(BoxLayout):
    """Card showing deployment exclusion information.

    Note: The actual deployment exclusions are configured in the Core card.
    This card provides additional information about built-in exclusions.
    """

    section_name = 'Deployment'
    config = DictProperty({
        'FOLDERS_AND_FILES_TO_EXCLUDE_FROM_PHONE': [],
    })

    root_path = StringProperty(os.getcwd())
    scroll_view = ObjectProperty(None)
    on_config_change = ObjectProperty(None)
    build_status = StringProperty('')
    recipe_name = StringProperty('')
    backend = StringProperty('buildozer')

    # Expose builtin exclusions to KV
    builtin_exclusions = BUILTIN_EXCLUSIONS

    def __init__(self, **kwargs):
        self.config_model = None
        self._active_procs: list[subprocess.Popen] = []
        self.backend = detect_backend()
        self.quick_actions = (
            _QUICK_ACTIONS_KSPROJECT
            if self.backend == 'ksproject'
            else _QUICK_ACTIONS_BUILDOZER
        )
        super().__init__(**kwargs)

    def on_kv_post(self, base_widget):
        """Populate widgets with initial configuration values."""
        EventBus.register_card(self.section_name, self)
        self.ids.exclude_from_phone_input.values = (
            self.config.get('FOLDERS_AND_FILES_TO_EXCLUDE_FROM_PHONE', []) or []
        )
        self.ids.exclude_from_phone_input.bind(
            values=lambda instance, values: self.on_exclusions_change(values)
        )
        from kivy.app import App

        app = App.get_running_app()
        if app:
            app.bind(on_stop=self._on_app_stop)

    def _on_app_stop(self, *args):
        for proc in list(self._active_procs):
            try:
                proc.terminate()
            except Exception:
                pass
        self._active_procs.clear()

    def _run(self, cmd_list, *, timeout, success_msg, fail_prefix):
        proc = subprocess.Popen(
            cmd_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(Path.cwd()),
        )
        self._active_procs.append(proc)
        try:
            output, _ = proc.communicate(timeout=timeout)
            output = output.strip() or 'Done'
            msg = (
                success_msg
                if proc.returncode == 0
                else f'{fail_prefix}: {output[-100:]}'
            )
        except subprocess.TimeoutExpired:
            proc.terminate()
            output = msg = 'Timed out'
        finally:
            if proc in self._active_procs:
                self._active_procs.remove(proc)
        from kivy.clock import Clock

        Clock.schedule_once(lambda dt: setattr(self, 'build_status', msg))
        EventBus.emit('terminal_output', output=output)

    def load_from_model(self):
        """Sync UI controls from the backing config model."""
        if not self.config_model:
            return

        new_config = {k: self.config_model.get_value(k) for k in self.config}
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

    def clean_recipe(self, recipe_override=''):
        import glob
        import shutil

        recipe = (recipe_override or self.recipe_name).strip()
        if not recipe:
            self.build_status = 'Enter a recipe name first'
            return
        pattern = f'.buildozer/android/platform/build-*/build/other_builds/{recipe}'
        paths = glob.glob(pattern)
        if not paths:
            self.build_status = f'No cache found for: {recipe}'
            return
        self.build_status = f'Cleaning {recipe}...'
        EventBus.emit('terminal_log', command=f'rm -rf {pattern}')

        def _clean():
            for p in paths:
                shutil.rmtree(p, ignore_errors=True)
            msg = f'Cleaned {recipe} build cache'
            from kivy.clock import Clock

            Clock.schedule_once(lambda dt: setattr(self, 'build_status', msg))
            EventBus.emit('terminal_output', output=msg)

        threading.Thread(target=_clean, daemon=True).start()

    def clean_all(self):
        if self.backend == 'ksproject':
            self.build_status = (
                'Clearing ksproject site-packages cache + gradle clean...'
            )
            EventBus.emit(
                'terminal_log',
                command='ksproject full clean (site-packages + gradlew clean)',
            )
            threading.Thread(target=self._ksproject_clean_all, daemon=True).start()
            return
        self.build_status = 'Running buildozer android clean...'
        EventBus.emit('terminal_log', command='buildozer android clean')
        threading.Thread(
            target=self._run,
            args=(['buildozer', 'android', 'clean'],),
            kwargs={
                'timeout': 120,
                'success_msg': 'Done — platform rebuilt, downloads preserved',
                'fail_prefix': 'Failed',
            },
            daemon=True,
        ).start()

    def _ksproject_clean_all(self):
        from kivy_reloader.compile_app import _clear_ksproject_cache, _gradle_clean

        try:
            _clear_ksproject_cache()
            _gradle_clean()
            msg = 'Done — site-packages cache cleared, gradle cleaned'
        except Exception as exc:
            msg = f'Failed: {exc}'
        from kivy.clock import Clock

        Clock.schedule_once(lambda dt: setattr(self, 'build_status', msg))
        EventBus.emit('terminal_output', output=msg)

    def app_clean(self):
        if self.backend == 'ksproject':
            self.build_status = (
                'Removing project_dist/gradle (full rebuild on next compile)...'
            )
            EventBus.emit('terminal_log', command='rm -rf project_dist/gradle')
            threading.Thread(target=self._ksproject_app_clean, daemon=True).start()
            return
        self.build_status = 'Running buildozer appclean (re-downloads SDK)...'
        EventBus.emit('terminal_log', command='buildozer appclean')
        threading.Thread(
            target=self._run,
            args=(['buildozer', 'appclean'],),
            kwargs={
                'timeout': 300,
                'success_msg': 'Done — full rebuild on next compile',
                'fail_prefix': 'Failed',
            },
            daemon=True,
        ).start()

    def _ksproject_app_clean(self):
        try:
            shutil.rmtree('project_dist/gradle', ignore_errors=True)
            msg = 'Done — project_dist/gradle removed, will regenerate on next compile'
        except Exception as exc:
            msg = f'Failed: {exc}'
        from kivy.clock import Clock

        Clock.schedule_once(lambda dt: setattr(self, 'build_status', msg))
        EventBus.emit('terminal_output', output=msg)

    def list_recipes(self):
        self.build_status = 'Fetching recipes...'

        def _list():
            self._run(
                ['buildozer', 'android', 'p4a', '--', 'recipes'],
                timeout=30,
                success_msg='',
                fail_prefix='Failed',
            )

        threading.Thread(target=_list, daemon=True).start()

    def on_exclusions_change(self, values):
        self.update_config('FOLDERS_AND_FILES_TO_EXCLUDE_FROM_PHONE', values)
