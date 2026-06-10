from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version('kivy-reloader')
except PackageNotFoundError:
    __version__ = 'unknown'
