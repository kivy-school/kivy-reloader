"""
Color theme management for the Kivy application.
Handles loading colors into Kivy's global_idmap for KV file accessibility.
"""

from kivy.lang import global_idmap

from kivy_reloader.configurator.styles import DarkTheme, LightTheme


def load_color_palette(dark_mode=False):
    """
    Loads the application's color palette into Kivy's global_idmap.
    This makes the colors accessible globally within KV files.

    Usage in KV files:
        Label:
            color: primary_color
        Button:
            background_color: accent_color
            color: accent_foreground_color

    Args:
        dark_mode (bool): Whether to load dark theme colors
    """
    # Select theme colors
    colors = DarkTheme if dark_mode else LightTheme

    # Create color palette for global_idmap
    color_palette = {
        # Base colors
        'background_color': colors.BACKGROUND,
        'foreground_color': colors.FOREGROUND,
        # Brand colors
        'primary_color': colors.PRIMARY,
        'primary_foreground_color': colors.PRIMARY_FOREGROUND,
        'accent_color': colors.ACCENT,
        'accent_foreground_color': colors.ACCENT_FOREGROUND,
        'secondary_color': colors.SECONDARY,
        'secondary_foreground_color': colors.SECONDARY_FOREGROUND,
        # Status colors
        'destructive_color': colors.DESTRUCTIVE,
        'destructive_foreground_color': colors.DESTRUCTIVE_FOREGROUND,
        'warning_color': colors.WARNING,
        'warning_foreground_color': colors.WARNING_FOREGROUND,
        'success_color': colors.SUCCESS,
        'success_foreground_color': colors.SUCCESS_FOREGROUND,
        # UI element colors
        'card_color': colors.CARD,
        'card_foreground_color': colors.CARD_FOREGROUND,
        'muted_color': colors.MUTED,
        'muted_foreground_color': colors.MUTED_FOREGROUND,
        'border_color': colors.BORDER,
        'input_color': colors.INPUT,
        'ring_color': colors.RING,
        # Popover colors
        'popover_color': colors.POPOVER,
        'popover_foreground_color': colors.POPOVER_FOREGROUND,
        # Sidebar colors
        'sidebar_background_color': colors.SIDEBAR['background'],
        'sidebar_foreground_color': colors.SIDEBAR['foreground'],
        'sidebar_primary_color': colors.SIDEBAR['primary'],
        'sidebar_primary_foreground_color': colors.SIDEBAR['primary_foreground'],
        'sidebar_accent_color': colors.SIDEBAR['accent'],
        'sidebar_accent_foreground_color': colors.SIDEBAR['accent_foreground'],
        'sidebar_border_color': colors.SIDEBAR['border'],
        'sidebar_ring_color': colors.SIDEBAR['ring'],
        # Additional convenient color names
        'white': (1, 1, 1, 1),
        'black': (0, 0, 0, 1),
        'transparent': (0, 0, 0, 0),
    }

    # Update the global_idmap with the color palette
    global_idmap.update(color_palette)
