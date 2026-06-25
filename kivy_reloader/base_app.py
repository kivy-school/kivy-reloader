"""
Base Reloader App

Contains shared functionality between Desktop and Android apps.
"""

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.factory import Factory as F
from kivy.lang import Builder
from kivy.logger import Logger
from kivy.utils import platform


class BaseReloaderApp:
    """
    Base class containing shared functionality between Desktop and Android apps
    """

    def _unregister_factory_from_module(self, module_name):
        """Unregister all Factory classes from a specific module"""
        to_remove = [x for x in F.classes if F.classes[x]['module'] == module_name]

        # check class name
        for x in F.classes:
            cls = F.classes[x]['cls']
            if not cls:
                continue
            if getattr(cls, '__module__', None) == module_name:
                to_remove.append(x)

        for name in set(to_remove):
            del F.classes[name]

    def build_root_and_add_to_window(self):
        """Common UI building logic for both platforms"""
        Logger.info('Reloader: Building root widget and adding to window')
        if self.root is not None:
            self.root.clear_widgets()

            # Handle window children removal differently per platform
            if platform == 'android':
                if Window.children:
                    Window.remove_widget(Window.children[0])
            else:
                while Window.children:
                    Window.remove_widget(Window.children[0])

        Clock.schedule_once(self.delayed_build)

    def delayed_build(self, *args):
        """Common delayed build logic for both platforms"""
        # Unload any KV files that build() loaded last time.
        # Handles the standard Kivy pattern of calling Builder.load_file inside build()
        # without requiring users to change their code.
        """
        First call: _build_kv_files doesn't exist → no unloading → build() runs → records which files it loaded. Every subsequent reload: unloads exactly those files → build() re-loads them fresh. Zero files from outside build() are touched.
        """
        for f in getattr(self, '_build_kv_files', []):
            Builder.unload_file(f)

        files_before = set(Builder.files)
        self.root = self.build()
        self._build_kv_files = set(Builder.files) - files_before

        if self.root:
            if not isinstance(self.root, F.Widget):
                Logger.critical('App.root must be an _instance_ of Widget')
                raise Exception('Invalid instance in App.root')

            Window.add_widget(self.root)
