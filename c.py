import time

from b import build

build()
time.sleep(5)
import importlib

import a

importlib.reload(a)

build()
