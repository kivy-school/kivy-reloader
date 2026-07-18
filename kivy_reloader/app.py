"""
Kivy Reloader Application Classes

This module provides hot reload functionality for Kivy applications across
different platforms.

Architecture:
- DesktopApp: Handles development on desktop (Windows/Linux/macOS)
  - Uses watchdog for file system monitoring
  - Manages child processes for hot reload
  - Sends app changes to Android via network

- AndroidApp: Handles hot reload on Android devices
  - Receives app updates via TCP server
  - Uses file hashing to detect changes
  - Manages service restarts and compilation

Key Features:
- Hot reload of .kv files and Python modules
- Cross-platform desktop development
- Network-based Android deployment
- Service management for Android
- Smart file watching with exclusion patterns
"""

import os
import sys
import warnings

os.environ['KIVY_LOG_MODE'] = 'MIXED'

# for pyinstaller              #for nuitka
if hasattr(sys, '_MEIPASS') or '__compiled__' in dir(sys.modules[__name__]):
    os.environ['RELOADER_STATUS'] = 'PROD'

_DESKTOP_EXTRA_HINT = (
    'Desktop hot reload requires the optional desktop dependencies. '
    'Install them with `pip install "kivy-reloader[desktop]"` or '
    '`uv add "kivy-reloader[desktop]"`.'
)

_KIVY_RUNTIME_HINT = (
    'Kivy is not installed. Install it with '
    '`pip install "kivy-reloader[desktop]"` or '
    '`uv add "kivy-reloader[desktop]"` for desktop usage, or ensure your app '
    'installs `kivy` separately.'
)


def _warn_missing_desktop_extra(missing_module: str) -> None:
    warnings.warn(
        f'{_DESKTOP_EXTRA_HINT} Missing dependency: {missing_module}. '
        'Falling back to the plain Kivy App.',
        RuntimeWarning,
        stacklevel=2,
    )


class _MissingKivyApp:
    def __init__(self, *args, **kwargs):
        raise ModuleNotFoundError(_KIVY_RUNTIME_HINT)


try:
    from kivy.app import App as KivyApp
    from kivy.utils import platform
except ModuleNotFoundError as exc:
    if exc.name != 'kivy':
        raise
    BaseReloaderApp = object
    App = _MissingKivyApp
else:
    from .base_app import BaseReloaderApp

    if os.environ.get('RELOADER_STATUS') == 'PROD':
        App = KivyApp
    elif platform == 'android':
        from .android_app import AndroidApp

        App = AndroidApp
    elif platform in {'win', 'linux', 'macosx'}:
        try:
            from .desktop_app import DesktopApp
        except ModuleNotFoundError as exc:
            if exc.name not in {'kaki', 'watchdog'}:
                raise
            _warn_missing_desktop_extra(exc.name)
            App = KivyApp
        else:
            App = DesktopApp
    else:
        App = KivyApp


# Export all classes for backward compatibility
__all__ = ['App', 'BaseReloaderApp']
