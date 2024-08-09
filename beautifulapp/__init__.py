from kivy.factory import Factory as F

from beautifulapp.screens.main_screen import MainScreen
from kivy_reloader.app import App


class MainApp(App):
    def build(self):
        screen_manager = F.ScreenManager()
        screen_manager.add_widget(MainScreen(name="Main Screen"))
        return screen_manager
