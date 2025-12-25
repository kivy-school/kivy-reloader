from kivy.core.window import Window

from kivy_reloader.app import App
from kivy_reloader.configurator.screens.core import CoreScreen
from kivy_reloader.configurator.theme import load_theme

load_theme()
Window.size = (1100, 600)


class ConfiguratorUI(App):
    def build(self):
        self.ui = CoreScreen()
        return self.ui
