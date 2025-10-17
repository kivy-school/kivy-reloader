from configurator.screens.core import CoreScreen
from configurator.theme import load_theme
from kivy.core.window import Window

from kivy_reloader.app import App

load_theme()
Window.size = (1100, 600)


class ConfiguratorUI(App):
    def build(self):
        self.ui = CoreScreen()
        return self.ui
