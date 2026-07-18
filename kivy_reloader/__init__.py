from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version('kivy-reloader')
except PackageNotFoundError:
    __version__ = 'unknown'
