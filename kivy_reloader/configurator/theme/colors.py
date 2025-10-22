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
            background_color: primary_color
            color: primary_active_color if self.state == 'down' else primary_color

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
        # Brand colors with interactive states
        'primary_color': colors.PRIMARY,
        'primary_foreground_color': colors.PRIMARY_FOREGROUND,
        'primary_hover_color': colors.PRIMARY_STATES['hover'],
        'primary_active_color': colors.PRIMARY_STATES['active'],
        'primary_disabled_color': colors.PRIMARY_STATES['disabled'],
        'accent_color': colors.ACCENT,
        'accent_foreground_color': colors.ACCENT_FOREGROUND,
        'accent_hover_color': colors.ACCENT_STATES['hover'],
        'accent_active_color': colors.ACCENT_STATES['active'],
        'accent_disabled_color': colors.ACCENT_STATES['disabled'],
        'secondary_color': colors.SECONDARY,
        'secondary_foreground_color': colors.SECONDARY_FOREGROUND,
        'secondary_hover_color': colors.SECONDARY_STATES['hover'],
        'secondary_active_color': colors.SECONDARY_STATES['active'],
        'secondary_disabled_color': colors.SECONDARY_STATES['disabled'],
        # Status colors with interactive states
        'destructive_color': colors.DESTRUCTIVE,
        'destructive_foreground_color': colors.DESTRUCTIVE_FOREGROUND,
        'destructive_hover_color': colors.DESTRUCTIVE_STATES['hover'],
        'destructive_active_color': colors.DESTRUCTIVE_STATES['active'],
        'destructive_disabled_color': colors.DESTRUCTIVE_STATES['disabled'],
        'warning_color': colors.WARNING,
        'warning_foreground_color': colors.WARNING_FOREGROUND,
        'warning_hover_color': colors.WARNING_STATES['hover'],
        'warning_active_color': colors.WARNING_STATES['active'],
        'warning_disabled_color': colors.WARNING_STATES['disabled'],
        'success_color': colors.SUCCESS,
        'success_foreground_color': colors.SUCCESS_FOREGROUND,
        'success_hover_color': colors.SUCCESS_STATES['hover'],
        'success_active_color': colors.SUCCESS_STATES['active'],
        'success_disabled_color': colors.SUCCESS_STATES['disabled'],
        # UI element colors
        'card_color': colors.CARD,
        'card_foreground_color': colors.CARD_FOREGROUND,
        'muted_color': colors.MUTED,
        'muted_foreground_color': colors.MUTED_FOREGROUND,
        'muted_hover_color': colors.MUTED_STATES['hover'],
        'muted_active_color': colors.MUTED_STATES['active'],
        'muted_disabled_color': colors.MUTED_STATES['disabled'],
        'border_color': colors.BORDER,
        'input_color': colors.INPUT,
        'input_hover_color': colors.INPUT_STATES['hover'],
        'input_active_color': colors.INPUT_STATES['active'],
        'input_disabled_color': colors.INPUT_STATES['disabled'],
        'ring_color': colors.RING,
        # Popover colors
        'popover_color': colors.POPOVER,
        'popover_foreground_color': colors.POPOVER_FOREGROUND,
        # Sidebar colors with interactive states
        'sidebar_background_color': colors.SIDEBAR['background'],
        'sidebar_foreground_color': colors.SIDEBAR['foreground'],
        'sidebar_primary_color': colors.SIDEBAR['primary'],
        'sidebar_primary_foreground_color': colors.SIDEBAR['primary_foreground'],
        'sidebar_primary_hover_color': colors.SIDEBAR['primary_states']['hover'],
        'sidebar_primary_active_color': colors.SIDEBAR['primary_states']['active'],
        'sidebar_primary_disabled_color': colors.SIDEBAR['primary_states']['disabled'],
        'sidebar_accent_color': colors.SIDEBAR['accent'],
        'sidebar_accent_foreground_color': colors.SIDEBAR['accent_foreground'],
        'sidebar_accent_hover_color': colors.SIDEBAR['accent_states']['hover'],
        'sidebar_accent_active_color': colors.SIDEBAR['accent_states']['active'],
        'sidebar_accent_disabled_color': colors.SIDEBAR['accent_states']['disabled'],
        'sidebar_border_color': colors.SIDEBAR['border'],
        'sidebar_ring_color': colors.SIDEBAR['ring'],
        # Additional convenient color names
        'white': (1, 1, 1, 1),
        'black': (0, 0, 0, 1),
        'transparent': (0, 0, 0, 0),
    }

    # Update the global_idmap with the color palette
    global_idmap.update(color_palette)
