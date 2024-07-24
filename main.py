import trio

from beautifulapp import app

trio.run(app.async_run, "trio")
