from kivy.uix.screenmanager import ScreenManager

from kivy_reloader.app import App

from .screens.main_screen import MainScreen


class MainApp(App):
    def build(self):
        screen_manager = ScreenManager()
        screen_manager.add_widget(MainScreen(name="Main Screen"))
        return screen_manager

    def something(self):
        print("huashuashduash222")
