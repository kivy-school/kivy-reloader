from kivy.app import runTouchApp
from kivy.uix.button import Button

from kivy_reloader import App


class MainApp(App):
    should_send_app_to_phone = True

    def build_and_reload(self, initialize_server=None, *args):
        print("a")
        from screens.main_screen import MainScreen

        main_screen = MainScreen(name="Main Screen")
        if "Main Screen" not in self.screen_manager.screen_names:
            print("ADDING MAIN SCREEN")
            self.screen_manager.add_widget(main_screen)
        return self.reloader


MainApp()


# runTouchApp(Button(text="Hello World"))
