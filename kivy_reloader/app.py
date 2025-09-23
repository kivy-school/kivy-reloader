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

os.environ['KIVY_LOG_MODE'] = 'MIXED'

from kivy.utils import platform

# Import the base app for shared functionality
from .base_app import BaseReloaderApp

# Platform-specific imports and exports
if platform != 'android':
    from .desktop_app import DesktopApp

    App = DesktopApp
else:
    from .android_app import AndroidApp

    App = AndroidApp

# Export all classes for backward compatibility
__all__ = ['App', 'BaseReloaderApp']
