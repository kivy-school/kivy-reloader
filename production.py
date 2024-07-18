# needs to be renamed to `main.py`

import trio

from beautifulapp import app


async def main():
    async with trio.open_nursery() as nursery:
        app.nursery = nursery
        await app.async_run("trio")


trio.run(main)
