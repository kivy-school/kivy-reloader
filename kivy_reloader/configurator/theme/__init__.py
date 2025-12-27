"""
Theme initialization for the Kivy application.
Loads all theme components (colors, fonts, icons) into Kivy's global_idmap.
"""

from .colors import load_color_palette
from .fonts import load_font_styles
from .icons import load_icons


def load_theme(dark_mode=False):
    """
    Loads the application's theme by loading the color palette, font styles, and icons.
    This makes all theme values accessible in KV files.

    Args:
        dark_mode (bool): Whether to load dark theme colors

    Usage:
        # In your main.py or app initialization
        from theme import load_theme
        load_theme()  # Load light theme
        # or
        load_theme(dark_mode=True)  # Load dark theme
    """
    load_color_palette(dark_mode)
    load_font_styles()
    load_icons()


def toggle_theme():
    """
    Toggle between light and dark theme and reload all theme values.
    Returns the new theme state.

    Returns:
        bool: True if now in dark mode, False if in light mode
    """
    # Simple state management - in a real app you might want to store this
    # in app settings or a more sophisticated state manager
    current_theme_file = '.current_theme'

    # Read current theme state
    try:
        with open(current_theme_file, 'r', encoding='utf-8') as f:
            is_dark = f.read().strip() == 'dark'
    except FileNotFoundError:
        is_dark = False

    # Toggle theme
    new_theme = not is_dark

    # Save new theme state
    with open(current_theme_file, 'w', encoding='utf-8') as f:
        f.write('dark' if new_theme else 'light')

    # Update the global theme instance (import here to avoid circular imports)
    from ..styles import theme

    theme.dark_mode = new_theme
    theme.toggle_theme()

    # Load new theme
    load_theme(dark_mode=new_theme)

    return new_theme
