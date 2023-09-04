import trio
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.utils import platform

from custom_reloader import BaseApp, RootScreen

if platform != "android":
    Window.size = (406, 762)
    Window._set_window_pos(500, 100)
    Window.always_on_top = True


# fmt: off
kv = Builder.load_string("""
<RootScreen>:
    screen_manager: screen_manager.__self__
    ScreenManager:
        id: screen_manager
"""
)
# fmt: on


class MainApp(BaseApp):
    should_send_app_to_phone = True

    def __init__(self, nursery):
        super().__init__()
        self.nursery = nursery

    def build_and_reload(self):
        self.root_screen = RootScreen()
        self.screen_manager = self.root_screen.screen_manager
        initial_screen = "Main Screen"
        try:
            self.change_screen(initial_screen)
        except Exception as e:
            print("Error while changing screen: \n")
            print(e)
            return False
        return self.root_screen

    def change_screen(self, screen_name, toolbar_title=None):
        if screen_name not in self.screen_manager.screen_names:
            screen_object = self.get_screen_object_from_screen_name(screen_name)
            # print("Screen object: ", screen_object)
            self.screen_manager.add_widget(screen_object)
            # print("Screen names: ", self.screen_manager.screen_names)

        self.screen_manager.current = screen_name

    def get_screen_object_from_screen_name(self, screen_name):
        # Parsing module 'my_screen.py' and object 'MyScreen' from screen_name 'My Screen'
        screen_module_in_str = "_".join([i.lower() for i in screen_name.split()])
        screen_object_in_str = "".join(screen_name.split())

        # Importing screen object
        exec(f"from screens.{screen_module_in_str} import {screen_object_in_str}")

        # Instantiating the object
        screen_object = eval(f"{screen_object_in_str}()")

        return screen_object

    def restart(self):
        print("Restarting the app on smartphone")

        from jnius import autoclass

        Intent = autoclass("android.content.Intent")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        System = autoclass("java.lang.System")

        activity = PythonActivity.mActivity
        intent = Intent(activity.getApplicationContext(), PythonActivity)
        intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        intent.setFlags(Intent.FLAG_ACTIVITY_CLEAR_TASK)
        activity.startActivity(intent)
        System.exit(0)


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
