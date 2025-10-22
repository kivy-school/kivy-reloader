"""
Design System Styles for Kivy Application
Converted from TypeScript/Tailwind CSS design tokens
All colors are in RGBA format for Kivy compatibility
"""

from kivy.metrics import dp


def hsl_to_rgba(h, s, lightness, a=1.0):
    """Convert HSL values to RGBA for Kivy"""
    s /= 100.0
    lightness /= 100.0

    c = (1 - abs(2 * lightness - 1)) * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = lightness - c / 2

    if 0 <= h < 60:
        r, g, b = c, x, 0
    elif 60 <= h < 120:
        r, g, b = x, c, 0
    elif 120 <= h < 180:
        r, g, b = 0, c, x
    elif 180 <= h < 240:
        r, g, b = 0, x, c
    elif 240 <= h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x

    return (r + m, g + m, b + m, a)


def darken_color(h, s, lightness, amount=10):
    """Darken an HSL color by reducing lightness"""
    return max(0, lightness - amount)


def lighten_color(h, s, lightness, amount=10):
    """Lighten an HSL color by increasing lightness"""
    return min(100, lightness + amount)


def increase_saturation(h, s, lightness, amount=10):
    """Increase saturation for more vibrant colors"""
    return min(100, s + amount)


def generate_interactive_states(h, s, lightness, is_dark_theme=False):
    """
    Generate hover, active, and disabled states for a color.

    Args:
        h, s, lightness: HSL values for the base color
        is_dark_theme: Whether this is for dark theme (affects how we modify colors)

    Returns:
        dict: Contains hover, active, and disabled color variations
    """
    if is_dark_theme:
        # For dark theme: lighten on hover, darken on active
        hover_lightness = lighten_color(h, s, lightness, 8)
        active_lightness = darken_color(h, s, lightness, 5)
        disabled_lightness = darken_color(h, s, lightness, 20)
        disabled_saturation = max(0, s - 30)
    else:
        # For light theme: darken on hover, darken more on active
        hover_lightness = darken_color(h, s, lightness, 5)
        active_lightness = darken_color(h, s, lightness, 10)
        disabled_lightness = lighten_color(h, s, lightness, 20)
        disabled_saturation = max(0, s - 40)

    return {
        'base': hsl_to_rgba(h, s, lightness),
        'hover': hsl_to_rgba(h, s, hover_lightness),
        'active': hsl_to_rgba(h, s, active_lightness),
        'disabled': hsl_to_rgba(h, disabled_saturation, disabled_lightness, 0.6),
    }


class AppTheme:
    """Main theme configuration"""

    # Core layout (using dp for screen independence)
    MAX_WIDTH = dp(1280)
    DEFAULT_PADDING = dp(32)  # 2rem = 32px
    BORDER_RADIUS = dp(10)  # 0.625rem = 10px

    # Border radius variants
    RADIUS = {
        'sm': dp(6),  # calc(var(--radius) - 4px)
        'md': dp(8),  # calc(var(--radius) - 2px)
        'lg': dp(10),  # var(--radius)
    }

    # Animation durations (in seconds for Kivy)
    ANIMATIONS = {'fast': 0.2, 'normal': 0.3, 'slow': 0.5, 'logo_spin': 20.0}


class LightTheme:
    """Light theme colors - all HSL values converted to RGBA"""

    # Base colors
    BACKGROUND = hsl_to_rgba(0, 0, 100)  # Pure white
    FOREGROUND = hsl_to_rgba(222, 47, 11)  # Dark text

    # Card colors
    CARD = hsl_to_rgba(0, 0, 100)  # White
    CARD_FOREGROUND = hsl_to_rgba(222, 47, 11)  # Dark text

    # Popover colors
    POPOVER = hsl_to_rgba(0, 0, 100)  # White
    POPOVER_FOREGROUND = hsl_to_rgba(222, 47, 11)  # Dark text

    # Brand & role colors with interactive states
    PRIMARY = hsl_to_rgba(258, 90, 60)  # Purple
    PRIMARY_FOREGROUND = hsl_to_rgba(210, 40, 98)  # Light text
    PRIMARY_STATES = generate_interactive_states(258, 90, 60, is_dark_theme=False)

    ACCENT = hsl_to_rgba(198, 85, 45)  # Blue
    ACCENT_FOREGROUND = hsl_to_rgba(210, 40, 98)  # Light text
    ACCENT_STATES = generate_interactive_states(198, 85, 45, is_dark_theme=False)

    SECONDARY = hsl_to_rgba(220, 16, 96)  # Light gray
    SECONDARY_FOREGROUND = hsl_to_rgba(222, 47, 11)  # Dark text
    SECONDARY_STATES = generate_interactive_states(220, 16, 96, is_dark_theme=False)

    MUTED = hsl_to_rgba(220, 14, 96)  # Light gray
    MUTED_FOREGROUND = hsl_to_rgba(215, 16, 46)  # Medium gray text
    MUTED_STATES = generate_interactive_states(220, 14, 96, is_dark_theme=False)

    # Status colors with interactive states
    DESTRUCTIVE = hsl_to_rgba(0, 72, 51)  # Red
    DESTRUCTIVE_FOREGROUND = hsl_to_rgba(210, 40, 98)  # Light text
    DESTRUCTIVE_STATES = generate_interactive_states(0, 72, 51, is_dark_theme=False)

    WARNING = hsl_to_rgba(35, 92, 52)  # Orange
    WARNING_FOREGROUND = hsl_to_rgba(240, 10, 6)  # Dark text
    WARNING_STATES = generate_interactive_states(35, 92, 52, is_dark_theme=False)

    SUCCESS = hsl_to_rgba(142, 60, 42)  # Green
    SUCCESS_FOREGROUND = hsl_to_rgba(210, 40, 98)  # Light text
    SUCCESS_STATES = generate_interactive_states(142, 60, 42, is_dark_theme=False)

    # Interactive elements
    BORDER = hsl_to_rgba(214, 32, 91)  # Light gray border
    INPUT = hsl_to_rgba(214, 32, 91)  # Light gray input
    INPUT_STATES = generate_interactive_states(214, 32, 91, is_dark_theme=False)
    RING = hsl_to_rgba(258, 100, 70)  # Purple focus ring

    # Sidebar specific colors
    SIDEBAR = {
        'background': hsl_to_rgba(0, 0, 98),  # Very light gray
        'foreground': hsl_to_rgba(240, 5, 26),  # Dark text
        'primary': hsl_to_rgba(258, 90, 60),  # Purple
        'primary_foreground': hsl_to_rgba(0, 0, 100),  # White
        'primary_states': generate_interactive_states(258, 90, 60, is_dark_theme=False),
        'accent': hsl_to_rgba(240, 5, 96),  # Light accent
        'accent_foreground': hsl_to_rgba(240, 6, 10),  # Dark text
        'accent_states': generate_interactive_states(240, 5, 96, is_dark_theme=False),
        'border': hsl_to_rgba(220, 13, 91),  # Light border
        'ring': hsl_to_rgba(258, 100, 70),  # Purple ring
    }


class DarkTheme:
    """Dark theme colors - all HSL values converted to RGBA"""

    # Base colors
    BACKGROUND = hsl_to_rgba(240, 10, 6)  # Very dark blue-gray
    FOREGROUND = hsl_to_rgba(0, 0, 100)  # White text

    # Card colors
    CARD = hsl_to_rgba(240, 10, 10)  # Dark gray
    CARD_FOREGROUND = hsl_to_rgba(0, 0, 100)  # White text

    # Popover colors
    POPOVER = hsl_to_rgba(240, 10, 10)  # Dark gray
    POPOVER_FOREGROUND = hsl_to_rgba(0, 0, 100)  # White text

    # Brand & role colors with interactive states
    PRIMARY = hsl_to_rgba(258, 90, 66)  # Lighter purple
    PRIMARY_FOREGROUND = hsl_to_rgba(240, 10, 6)  # Dark text
    PRIMARY_STATES = generate_interactive_states(258, 90, 66, is_dark_theme=True)

    ACCENT = hsl_to_rgba(198, 85, 55)  # Lighter blue
    ACCENT_FOREGROUND = hsl_to_rgba(240, 10, 6)  # Dark text
    ACCENT_STATES = generate_interactive_states(198, 85, 55, is_dark_theme=True)

    SECONDARY = hsl_to_rgba(240, 10, 14)  # Dark gray
    SECONDARY_FOREGROUND = hsl_to_rgba(0, 0, 100)  # White text
    SECONDARY_STATES = generate_interactive_states(240, 10, 14, is_dark_theme=True)

    MUTED = hsl_to_rgba(240, 10, 14)  # Dark gray
    MUTED_FOREGROUND = hsl_to_rgba(220, 10, 70)  # Light gray text
    MUTED_STATES = generate_interactive_states(240, 10, 14, is_dark_theme=True)

    # Status colors with interactive states
    DESTRUCTIVE = hsl_to_rgba(0, 72, 62)  # Lighter red
    DESTRUCTIVE_FOREGROUND = hsl_to_rgba(0, 0, 100)  # White text
    DESTRUCTIVE_STATES = generate_interactive_states(0, 72, 62, is_dark_theme=True)

    WARNING = hsl_to_rgba(35, 92, 60)  # Lighter orange
    WARNING_FOREGROUND = hsl_to_rgba(240, 10, 6)  # Dark text
    WARNING_STATES = generate_interactive_states(35, 92, 60, is_dark_theme=True)

    SUCCESS = hsl_to_rgba(142, 60, 48)  # Lighter green
    SUCCESS_FOREGROUND = hsl_to_rgba(240, 10, 6)  # Dark text
    SUCCESS_STATES = generate_interactive_states(142, 60, 48, is_dark_theme=True)

    # Interactive elements
    BORDER = hsl_to_rgba(240, 9, 22)  # Dark border
    INPUT = hsl_to_rgba(240, 9, 22)  # Dark input
    INPUT_STATES = generate_interactive_states(240, 9, 22, is_dark_theme=True)
    RING = hsl_to_rgba(258, 100, 72)  # Purple focus ring

    # Sidebar specific colors
    SIDEBAR = {
        'background': hsl_to_rgba(240, 6, 10),  # Very dark
        'foreground': hsl_to_rgba(240, 5, 95),  # Light text
        'primary': hsl_to_rgba(258, 90, 66),  # Light purple
        'primary_foreground': hsl_to_rgba(0, 0, 0),  # Black
        'primary_states': generate_interactive_states(258, 90, 66, is_dark_theme=True),
        'accent': hsl_to_rgba(240, 4, 16),  # Dark accent
        'accent_foreground': hsl_to_rgba(240, 5, 95),  # Light text
        'accent_states': generate_interactive_states(240, 4, 16, is_dark_theme=True),
        'border': hsl_to_rgba(240, 4, 18),  # Dark border
        'ring': hsl_to_rgba(258, 100, 72),  # Light purple ring
    }


class Shadows:
    """Shadow and elevation effects for Kivy widgets"""

    # Shadow opacity values (Kivy uses RGBA, these are alpha values)
    ELEVATION_1 = 0.08  # Subtle shadow
    ELEVATION_2 = 0.10  # Medium shadow
    ELEVATION_3 = 0.14  # Strong shadow
    GLOW_OPACITY = 0.24  # Glow effect

    # Shadow blur radius (using dp for screen independence)
    BLUR_SMALL = dp(2)
    BLUR_MEDIUM = dp(8)
    BLUR_LARGE = dp(16)
    BLUR_GLOW = dp(32)


class Typography:
    """Font and text styling"""

    # Font families (Kivy will use system defaults if custom fonts not loaded)
    FONT_SANS = ['Inter', 'Roboto', 'Arial', 'sans-serif']

    FONT_MONO = ['JetBrains Mono', 'Consolas', 'Monaco', 'monospace']

    # Font sizes (using dp for screen independence)
    FONT_SIZES = {
        'xs': dp(12),
        'sm': dp(14),
        'base': dp(16),
        'lg': dp(18),
        'xl': dp(20),
        '2xl': dp(24),
        '3xl': dp(30),
        '4xl': dp(36),
    }

    # Font weights
    FONT_WEIGHTS = {
        'light': 'light',
        'normal': 'normal',
        'medium': 'medium',
        'bold': 'bold',
    }


class Components:
    """Pre-configured component styles"""

    # Logo styling (using dp for screen independence)
    LOGO = {
        'size': (dp(96), dp(96)),  # 6em ≈ 96px
        'padding': dp(24),  # 1.5em ≈ 24px
    }

    # Card component
    CARD = {
        'padding': dp(32),  # 2em ≈ 32px
        'margin': dp(16),
    }

    # Container
    CONTAINER = {
        'max_width': dp(1400),  # 2xl breakpoint
        'padding': dp(32),  # 2rem
    }


# Current theme selector (switch between light/dark)
class CurrentTheme:
    """Theme controller - switch between light and dark themes"""

    def __init__(self, dark_mode=False):
        self.dark_mode = dark_mode
        self._theme = DarkTheme if dark_mode else LightTheme

    def get_color(self, color_name):
        """Get color from current theme"""
        return getattr(self._theme, color_name)

    def get_interactive_color(self, color_name, state='base'):
        """
        Get interactive color state from current theme.

        Args:
            color_name: The base color name (e.g., 'PRIMARY', 'ACCENT')
            state: The interaction state ('base', 'hover', 'active', 'disabled')

        Returns:
            RGBA color tuple
        """
        states_attr = f'{color_name}_STATES'
        if hasattr(self._theme, states_attr):
            states = getattr(self._theme, states_attr)
            return states.get(state, states['base'])
        else:
            # Fallback to base color if states don't exist
            return getattr(self._theme, color_name)

    def toggle_theme(self):
        """Toggle between light and dark theme"""
        self.dark_mode = not self.dark_mode
        self._theme = DarkTheme if self.dark_mode else LightTheme

    @property
    def colors(self):
        """Get all colors from current theme"""
        return self._theme


# Global theme instance
theme = CurrentTheme(dark_mode=False)  # Start with light theme


# Utility functions for common operations
def get_shadow_color(base_color, elevation_level=1):
    """Generate shadow color based on elevation level"""
    r, g, b, _ = base_color

    elevation_alpha = {
        1: Shadows.ELEVATION_1,
        2: Shadows.ELEVATION_2,
        3: Shadows.ELEVATION_3,
    }.get(elevation_level, Shadows.ELEVATION_1)

    return (r * 0.1, g * 0.1, b * 0.1, elevation_alpha)  # Dark shadow


def apply_opacity(color, opacity):
    """Apply opacity to any RGBA color"""
    r, g, b, _ = color
    return (r, g, b, opacity)
