from kivy.factory import Factory as F

from kivy_reloader.utils import load_kv_path

load_kv_path("beautifulapp/screens/main_screen.kv")


class MainScreen(F.Screen):
    def on_enter(self, *args):
        print("MainScreen on_enter")
