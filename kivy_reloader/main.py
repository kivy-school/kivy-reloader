import trio
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.utils import platform

from custom_reloader import BaseApp, Reloader

if platform != "android":
    Window.size = (406, 762)
    Window.always_on_top = True


class MainApp(BaseApp):
    should_send_app_to_phone = True

    def __init__(self, nursery):
        super().__init__()
        self.nursery = nursery

    def build_and_reload(self, initialize_server=True):
        self.reloader = Reloader(initialize_server)
        self.screen_manager = self.reloader.screen_manager
        initial_screen = "Main Screen"
        try:
            self.change_screen(initial_screen)
        except Exception as e:
            print("Error while changing screen: \n")
            print(e)
            return False

        Clock.schedule_once(self.set_window_pos)
        return self.reloader

    def set_window_pos(self, *args):
        if platform != "android":
            Window._set_window_pos(4410, 470)

    def change_screen(self, screen_name, toolbar_title=None):
        # print(f"Changing screen to {screen_name}")
        if screen_name not in self.screen_manager.screen_names:
            screen_object = self.get_screen_object_from_screen_name(screen_name)
            self.screen_manager.add_widget(screen_object)

        self.screen_manager.current = screen_name

    def get_screen_object_from_screen_name(self, screen_name):
        # Parsing module 'my_screen.py' and object 'MyScreen' from screen_name 'My Screen'
        screen_module_in_str = "_".join([i.lower() for i in screen_name.split()])
        screen_object_in_str = "".join(screen_name.split())

        if platform == "android":
            self.unload_python_files_on_android(screen_module_in_str)

        # Importing screen object
        exec(f"from screens.{screen_module_in_str} import {screen_object_in_str}")

        # Instantiating the object
        screen_object = eval(f"{screen_object_in_str}()")

        return screen_object


# Start kivy app as an asynchronous task
async def main() -> None:
    async with trio.open_nursery() as nursery:
        server = MainApp(nursery)
        await server.async_run("trio")
        nursery.cancel_scope.cancel()


try:
    trio.run(main)

except Exception as e:
    print(e)
    print("App crashed, restarting")
    raise
