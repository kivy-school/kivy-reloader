# import trio

# # from beautifulapp import app
# from beautifulapp import MainApp

# app = MainApp()


# trio.run(app.async_run, "trio")
# # import trio
# # from kivy.lang import Builder

# # from kivy_reloader.app import App

# # kv = """
# # Button:
# #     text: "Hello World 6"
# #     on_release: print('hello world')
# # """


# # class MainApp(App):
# #     def build(self):
# #         return Builder.load_string(kv)


# app = MainApp()
# trio.run(app.async_run, "trio")

import trio

from app import MainApp

app = MainApp()
trio.run(app.async_run, "trio")
