from kivy.factory import Factory as F

from kivy_reloader.app import App
from screens.main_screen import MainScreen


class MainApp(App):
    def build(self):
        screen_manager = F.ScreenManager()
        screen_manager.add_widget(MainScreen(name="Main Screen"))
        return screen_manager

    def something(self):
        print("huashuashduash222")
