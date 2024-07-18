import trio

from beautifulapp import app

trio.run(app.main)
