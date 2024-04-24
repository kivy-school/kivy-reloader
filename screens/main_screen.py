from kivy.factory import Factory as F

from kivy_reloader.utils import load_kv_path

load_kv_path("screens/main_screen.kv")


class MainScreen(F.Screen):
    osc_server = F.ObjectProperty(allow_none=True)
    music_lyrics = F.StringProperty()

    def on_enter(self, *args):
        print("MainScreen on_enter")

    def start_service(self):
        print("MainScreen start_service")

        from services import ServiceHandler

        self.service_handler = ServiceHandler()
        self.service_handler.start_service("Helloworld")

    def stop_service(self):
        print("MainScreen stop_service")

        self.service_handler.stop_service("Helloworld")

    def start_osc(self):
        print("MainScreen start_osc")

        from oscpy.client import OSCClient
        from oscpy.server import OSCThreadServer as OSCServer

        if not self.osc_server:
            self.osc_app_server = OSCServer(encoding="utf8")
            self.osc_app_server.listen(address=b"localhost", port=3000, default=True)
            print("OSC Server started", self.osc_app_server)

            # Now let's create channels to receive messages
            self.osc_app_server.bind("/music-position", self.update_music_position)
            self.osc_app_server.bind("/music-lyrics", self.update_music_lyrics)

        self.osc_app_client = OSCClient("localhost", 3005, encoding="utf8")
        print("OSC Client started", self.osc_app_client)

    def play_music(self):
        print("MainScreen play_music")
        self.osc_app_client.send_message("/play-music", ["anything?"])

    def update_music_position(self, position):
        print("music_position", position)
        self.slider.value = position

    def update_music_lyrics(self, lyrics):
        print("update_music_lyrics", lyrics)
        self.music_lyrics += lyrics
