"""
Base Reloader App

Contains shared functionality between Desktop and Android apps.
"""

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.factory import Factory as F
from kivy.lang import Builder
from kivy.logger import Logger


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
        """Rebuild the root widget and attach exactly one instance to Window.

        Only the previously built root (self.root) is removed, so unrelated
        Window children (overlays, popups, etc.) survive a hot reload.
        """
        Logger.info('Reloader: Building root widget and adding to window')

        old_root = self.root

        # Cancel any build left over from a previous reload: without this,
        # two rapid reloads would both run delayed_build() and attach two
        # roots to the Window.
        Clock.unschedule(self.delayed_build)

        # Never remove Window.children[0]: it is not guaranteed to be the
        # app root (e.g. ksproject/src-package layouts on Android), which
        # leaves the old root attached and duplicates the UI. Remove the
        # exact previous root instead.
        if old_root is not None and old_root in Window.children:
            Window.remove_widget(old_root)

        Clock.schedule_once(self.delayed_build)

    def delayed_build(self, *args):
        """Build the root widget and add it to the Window.

        Unloads the KV files that build() loaded last time, handling the
        standard Kivy pattern of calling Builder.load_file() inside build()
        without requiring users to change their code. The file list is
        cleared before rebuilding so a build() failure keeps the stale rules
        unloadable on the next reload instead of losing track of them.
        """
        build_kv_files = getattr(self, '_build_kv_files', set())
        self._build_kv_files = set()
        for f in build_kv_files:
            Builder.unload_file(f)

        files_before = set(Builder.files)
        self.root = self.build()
        self._build_kv_files = set(Builder.files) - files_before

        if self.root:
            if not isinstance(self.root, F.Widget):
                Logger.critical('App.root must be an _instance_ of Widget')
                raise Exception('Invalid instance in App.root')

            if self.root not in Window.children:
                Window.add_widget(self.root)
