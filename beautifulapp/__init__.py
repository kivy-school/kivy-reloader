# from kivy_reloader.app import App


# class MainApp(App):
#     def build(self):
#         #     return self.build_and_reload()

#         # def build_and_reload(self):
#         from .screens.main_screen import MainScreen

#         return MainScreen(name="Main Screen")


# app = MainApp()
from kivy_reloader.app import App


class MainApp(App):
    def build(self):
        print("executing build!!!")
        from kivy.factory import Factory as F

        from .screens.main_screen import MainScreen

        screen_manager = F.ScreenManager()
        screen_manager.add_widget(MainScreen(name="Main Screen"))

        return screen_manager


app = MainApp()
