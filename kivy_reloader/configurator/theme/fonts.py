"""
Font and typography management for the Kivy application.
Handles loading font styles into Kivy's global_idmap for KV file accessibility.
"""

from kivy.lang import global_idmap

from kivy_reloader.configurator.styles import AppTheme, Typography


def load_font_styles():
    """
    Loads the application's font styles into Kivy's global_idmap.
    This makes the font sizes and other typography values accessible in KV files.

    Usage in KV files:
        Label:
            font_size: font_size_lg
            font_name: font_sans

        Button:
            font_size: font_size_base
    """

    # Font styles for global_idmap
    font_styles = {
        # Font sizes
        'font_size_xs': Typography.FONT_SIZES['xs'],
        'font_size_sm': Typography.FONT_SIZES['sm'],
        'font_size_base': Typography.FONT_SIZES['base'],
        'font_size_lg': Typography.FONT_SIZES['lg'],
        'font_size_xl': Typography.FONT_SIZES['xl'],
        'font_size_2xl': Typography.FONT_SIZES['2xl'],
        'font_size_3xl': Typography.FONT_SIZES['3xl'],
        'font_size_4xl': Typography.FONT_SIZES['4xl'],
        # Font families (first available font will be used)
        'font_sans': Typography.FONT_SANS[1],  # Inter or fallback
        'font_mono': Typography.FONT_MONO[1],  # JetBrains Mono or fallback
        # Common spacing and sizing values
        'default_padding': AppTheme.DEFAULT_PADDING,
        'border_radius': AppTheme.BORDER_RADIUS,
        'border_radius_sm': AppTheme.RADIUS['sm'],
        'border_radius_md': AppTheme.RADIUS['md'],
        'border_radius_lg': AppTheme.RADIUS['lg'],
        # Animation durations
        'anim_fast': AppTheme.ANIMATIONS['fast'],
        'anim_normal': AppTheme.ANIMATIONS['normal'],
        'anim_slow': AppTheme.ANIMATIONS['slow'],
    }

    # Update the global_idmap with the font styles
    global_idmap.update(font_styles)
