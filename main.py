from kivy_reloader import App


class MainApp(App):
    should_send_app_to_phone = True

    def build_and_reload(self, initialize_server=None, *args):
        from screens.main_screen import MainScreen

        return MainScreen(name="Main Screen")


MainApp()
