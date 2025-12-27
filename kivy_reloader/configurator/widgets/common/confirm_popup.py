"""Reusable confirmation popup component."""

from kivy.properties import BooleanProperty, ObjectProperty, StringProperty
from kivy.uix.modalview import ModalView

from kivy_reloader.lang import Builder

Builder.load_file(__file__)


class ConfirmPopup(ModalView):
    """A styled confirmation popup with title, message, and confirm/cancel buttons.

    Usage:
        popup = ConfirmPopup(
            title='Exit Application',
            message='Are you sure you want to exit?',
            confirm_text='Exit',
            cancel_text='Cancel',
            on_confirm=lambda: App.get_running_app().stop(),
        )
        popup.open()
    """

    title = StringProperty('Confirm')
    message = StringProperty('Are you sure?')
    confirm_text = StringProperty('Confirm')
    cancel_text = StringProperty('Cancel')
    is_destructive = BooleanProperty(False)

    # Callbacks
    on_confirm_callback = ObjectProperty(None, allownone=True)
    on_cancel_callback = ObjectProperty(None, allownone=True)

    def __init__(self, on_confirm=None, on_cancel=None, **kwargs):
        self.on_confirm_callback = on_confirm
        self.on_cancel_callback = on_cancel
        super().__init__(**kwargs)

    def do_confirm(self):
        """Handle confirm button press."""
        self.dismiss()
        if self.on_confirm_callback:
            self.on_confirm_callback()

    def do_cancel(self):
        """Handle cancel button press."""
        self.dismiss()
        if self.on_cancel_callback:
            self.on_cancel_callback()
