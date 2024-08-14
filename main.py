import trio

from beautifulapp import MainApp

app = MainApp()

trio.run(app.async_run, "trio")
