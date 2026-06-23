<<<<<<< HEAD
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version('kivy-reloader')
except PackageNotFoundError:
    __version__ = 'unknown'
=======
__version__ = '0.8.7'
>>>>>>> main
