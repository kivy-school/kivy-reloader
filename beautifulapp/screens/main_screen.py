import os

from kivy.factory import Factory as F

from kivy_reloader.utils import load_kv_path

main_screen_kv = os.path.join('beautifulapp', 'screens', 'main_screen.kv')
load_kv_path(main_screen_kv)


class MainScreen(F.Screen):
    def on_enter(self, *args):
        print('MainScreen on_enter')
