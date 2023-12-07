from kivy_reloader import App
from screens.main_screen import MainScreen


class MainApp(App):
    should_send_app_to_phone = False

    def build_and_reload(self):
        self.screen_manager.add_widget(MainScreen())
        return self.reloader


MainApp()
