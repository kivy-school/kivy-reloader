from kivy_reloader.app import App


class MainApp(App):
    def build(self):
        from .screens.main_screen import MainScreen

        return MainScreen(name="Main Screen")


app = MainApp()