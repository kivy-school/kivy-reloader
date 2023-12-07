from kivy_reloader import App


class MainApp(App):
    should_send_app_to_phone = False

    def build_and_reload(self):
        from screens.main_screen import MainScreen

        self.screen_manager.add_widget(MainScreen())
        return self.reloader


MainApp()
