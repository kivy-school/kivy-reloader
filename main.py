from kivy_reloader import App


class MainApp(App):
    def build_and_reload(self, initialize_server=False, *args):
        from screens.main_screen import MainScreen

        return MainScreen(name="Main Screen")


MainApp()
