"""Application toolbar with action buttons"""

from kivy.properties import BooleanProperty, ObjectProperty
from kivy.uix.boxlayout import BoxLayout

from kivy_reloader.configurator.widgets.common.gradient import GLGradient
from kivy_reloader.lang import Builder

Builder.load_file(__file__)


class Toolbar(BoxLayout):
    """Top toolbar with action buttons"""

    # Callback properties for button actions
    on_apply_reload = ObjectProperty(None)
    on_save = ObjectProperty(None)
    on_restore = ObjectProperty(None)
    on_export = ObjectProperty(None)
    on_import = ObjectProperty(None)
    on_help = ObjectProperty(None)
    on_toggle_sidebar = ObjectProperty(None)
    is_sidebar_visible = BooleanProperty(True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Create gradient texture: purple (258, 90%, 60%) to cyan (198, 85%, 45%)
        # Convert HSL to RGB:
        # Purple: rgb(128, 26, 230) ≈ (0.5, 0.1, 0.9)
        # Cyan: rgb(17, 175, 214) ≈ (0.067, 0.686, 0.84)
        self.gradient_texture = GLGradient.diagonal(
            start_color=(0.5, 0.1, 0.9, 1.0),  # Purple (primary)
            end_color=(0.067, 0.686, 0.84, 1.0),  # Cyan (accent)
            size=(512, 512),
        )

    def handle_apply_reload(self):
        """Handle Apply & Reload button"""
        if self.on_apply_reload:
            self.on_apply_reload()

    def handle_save(self):
        """Handle Save button"""
        if self.on_save:
            self.on_save()

    def handle_restore(self):
        """Handle Restore button"""
        if self.on_restore:
            self.on_restore()

    def handle_export(self):
        """Handle Export button"""
        if self.on_export:
            self.on_export()

    def handle_import(self):
        """Handle Import button"""
        if self.on_import:
            self.on_import()

    def handle_help(self):
        """Handle Help button"""
        if self.on_help:
            self.on_help()

    def handle_toggle_sidebar(self):
        """Handle sidebar toggle"""
        if self.on_toggle_sidebar:
            self.on_toggle_sidebar()
