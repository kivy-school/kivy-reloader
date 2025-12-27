"""Help popup showing keyboard shortcuts and version info."""

from kivy.properties import StringProperty
from kivy.uix.modalview import ModalView

from kivy_reloader import __version__
from kivy_reloader.lang import Builder

Builder.load_file(__file__)


class HelpPopup(ModalView):
    """A styled help popup showing keyboard shortcuts and version info."""

    version = StringProperty(__version__)
