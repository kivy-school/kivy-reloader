import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Union

import toml


class ConfigurationError(Exception):
    """Raised when there's an error with configuration loading or validation."""

    pass


class Config:  # noqa: PLR0904
    """
    Configuration manager for Kivy Reloader.

    Handles loading, validation, and access to configuration settings
    from the kivy-reloader.toml file.

    Note: This class has many properties by design as it serves as a comprehensive
    configuration interface. The PLR0904 warning is suppressed as the high number
    of public methods is expected and justified for a configuration manager.
    """

    # Constants
    MAX_PORT_NUMBER = 65535
    MIN_PORT_NUMBER = 1

    # Default exclusion patterns for phone deployment
    DEFAULT_EXCLUSIONS = [
        '*.pyc',
        '__pycache__',
        '.buildozer',
        '.venv',
        '.vscode',
        '.git',
        '.pytest_cache',
        '.DS_Store',
        '.env',
        '.dmypy.json',
        '.mypy_cache/',
        'dmypy.json',
        'env/',
        'ENV/',
        'env.bak/',
        'venv/',
        'venv.bak/',
        'bin',
        'buildozer.spec',
        'poetry.lock',
        'pyproject.toml',
        'temp',
        'tests',
        'app_copy.zip',
        'send_app_to_phone.py',
        '.gitignore',
        'README.md',
    ]

    def __init__(self, config_path: Union[str, Path] = None):
        """
        Initialize configuration manager.

        Args:
            config_path: Optional path to config file. Defaults to current directory.
        """
        self.config_file = self._determine_config_path(config_path)
        self.config: Dict[str, Any] = {}

        # Initialize configuration if not in PyInstaller environment
        if not self._is_pyinstaller_environment():
            self._load_and_validate_config()
        else:
            self._handle_pyinstaller_environment()

    @staticmethod
    def _determine_config_path(config_path: Union[str, Path] = None) -> Path:
        """
        Determines the configuration file path.

        Args:
            config_path: Optional custom config path

        Returns:
            Path: Resolved path to configuration file
        """
        if config_path:
            return Path(config_path)
        return Path.cwd() / 'kivy-reloader.toml'

    @staticmethod
    def _is_pyinstaller_environment() -> bool:
        """Check if running in PyInstaller environment."""
        return hasattr(sys, '_MEIPASS')

    @staticmethod
    def _handle_pyinstaller_environment() -> None:
        """Handle PyInstaller environment with helpful message."""
        logging.warning('PyInstaller environment detected')
        print(
            'PyInstaller environment detected. '
            'Make sure to turn your kivy_reloader app into a kivy app: '
            'Replace "from kivy_reloader.app" with "from kivy.app" in your code.'
        )

    def _load_and_validate_config(self) -> None:
        """Load and validate configuration from file."""
        try:
            self._load_config()
            self._validate_config()
        except FileNotFoundError as e:
            raise ConfigurationError(
                f'Config file not found: {self.config_file}. '
                'Please execute `kivy-reloader init` first.'
            ) from e
        except Exception as e:
            raise ConfigurationError(f'Failed to load configuration: {e}') from e

    def _load_config(self) -> None:
        """Load configuration from TOML file."""
        if not self.config_file.exists():
            raise FileNotFoundError(f'Config file not found: {self.config_file}')

        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config_data = toml.load(f)
                self.config = config_data.get('kivy_reloader', {})
        except toml.TomlDecodeError as e:
            raise ConfigurationError(f'Invalid TOML syntax in config file: {e}') from e
        except Exception as e:
            raise ConfigurationError(f'Failed to read config file: {e}') from e

    def _validate_config(self) -> None:
        """Validate configuration values."""
        # Validate streaming method
        stream_using = self.config.get('STREAM_USING', 'USB')
        if stream_using not in {'USB', 'WIFI'}:
            logging.warning(f'Invalid STREAM_USING value: {stream_using}. Using USB.')
            self.config['STREAM_USING'] = 'USB'

        # Validate port numbers
        for port_key in ('ADB_PORT', 'RELOADER_PORT'):
            port = self.config.get(port_key)
            if port is not None and not (
                self.MIN_PORT_NUMBER <= port <= self.MAX_PORT_NUMBER
            ):
                logging.warning(f'Invalid {port_key}: {port}. Using default.')
                self.config.pop(port_key, None)

        # Validate window dimensions
        for dimension in ('WINDOW_X', 'WINDOW_Y', 'WINDOW_WIDTH', 'WINDOW_HEIGHT'):
            value = self.config.get(dimension)
            if value is not None and not isinstance(value, (int, str)):
                logging.warning(f'Invalid {dimension}: {value}. Using default.')
                self.config.pop(dimension, None)

        # Validate display orientation
        orientation = self.config.get('DISPLAY_ORIENTATION')
        if orientation is not None and orientation not in {0, 90, 180, 270}:
            logging.warning(f'Invalid DISPLAY_ORIENTATION: {orientation}. Using 0.')
            logging.warning('Valid values are 0, 90, 180, or 270 degrees.')
            self.config['DISPLAY_ORIENTATION'] = 0

        # Validate audio source
        audio_source = self.config.get('AUDIO_SOURCE', 'output')
        valid_audio_sources = {
            'output',
            'playback',
            'mic',
            'mic-unprocessed',
            'mic-camcorder',
            'mic-voice-recognition',
            'mic-voice-communication',
            'voice-call',
            'voice-call-uplink',
            'voice-call-downlink',
            'voice-performance',
        }
        if audio_source not in valid_audio_sources:
            logging.warning(f'Invalid AUDIO_SOURCE: {audio_source}. Using output.')
            self.config['AUDIO_SOURCE'] = 'output'

        # Validate time limits
        for time_key in ('TIME_LIMIT', 'SCREEN_OFF_TIMEOUT'):
            value = self.config.get(time_key)
            if value is not None and (not isinstance(value, int) or value < 0):
                logging.warning(f'Invalid {time_key}: {value}. Using 0.')
                self.config[time_key] = 0

        # Validate performance settings
        for perf_key in ('MAX_SIZE', 'MAX_FPS'):
            value = self.config.get(perf_key)
            if value is not None and (not isinstance(value, int) or value < 0):
                logging.warning(f'Invalid {perf_key}: {value}. Using 0.')
                self.config[perf_key] = 0

        # Validate render driver
        render_driver = self.config.get('RENDER_DRIVER', '')
        valid_drivers = {
            'direct3d',
            'direct3d11',
            'direct3d12',
            'opengl',
            'opengles2',
            'opengles',
            'metal',
            'vulkan',
            'gpu',
            'software',
        }
        if render_driver and render_driver not in valid_drivers:
            logging.warning(f'Invalid RENDER_DRIVER: {render_driver}.')
            logging.warning(f'Valid values: {", ".join(valid_drivers)}')
            self.config['RENDER_DRIVER'] = ''

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        return self.config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Set configuration value.

        Args:
            key: Configuration key
            value: Configuration value
        """
        self.config[key] = value

    def save(self) -> 'Config':
        """
        Save configuration to file and reload.

        Returns:
            Self for method chaining

        Raises:
            ConfigurationError: If save operation fails
        """
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                toml.dump({'kivy_reloader': self.config}, f)
            self._load_config()
            return self
        except Exception as e:
            raise ConfigurationError(f'Failed to save configuration: {e}') from e

    # === File Watching Properties ===

    @property
    def WATCHED_FILES(self) -> List[str]:
        """Files to watch for changes."""
        return self.get('WATCHED_FILES', [])

    @property
    def WATCHED_FOLDERS(self) -> List[str]:
        """Folders to watch for changes (non-recursive)."""
        return self.get('WATCHED_FOLDERS', [])

    @property
    def WATCHED_FOLDERS_RECURSIVELY(self) -> List[str]:
        """Folders to watch for changes (recursive)."""
        return self.get('WATCHED_FOLDERS_RECURSIVELY', [])

    @property
    def DO_NOT_WATCH_PATTERNS(self) -> List[str]:
        """Patterns to exclude from watching."""
        return self.get(
            'DO_NOT_WATCH_PATTERNS',
            [
                '*.pyc',
                '*__pycache__*',
                '*.buildozer*',
                '*.venv*',
                '*.git*',
                '*bin*',
                '*dist*',
                '*build*',
                '*.pytest_cache*',
                '*.vscode*',
                '*.idea*',
                '*node_modules*',
                '*.mypy_cache*',
                'kivy_reloader',
            ],
        )

    @property
    def FULL_RELOAD_FILES(self) -> List[str]:
        """Files that trigger a full app reload when changed."""
        return self.get('FULL_RELOAD_FILES', [])

    # === Reload & Connection Properties ===

    @property
    def HOT_RELOAD_ON_PHONE(self) -> bool:
        """Enable hot reload functionality on phone."""
        return self.get('HOT_RELOAD_ON_PHONE', False)

    @property
    def STREAM_USING(self) -> str:
        """Connection method: 'USB' or 'WIFI'."""
        return self.get('STREAM_USING', 'USB')

    @property
    def ADB_PORT(self) -> int:
        """ADB TCP/IP port number."""
        return self.get('ADB_PORT', 5555)

    @property
    def RELOADER_PORT(self) -> int:
        """Reloader service port number."""
        return self.get('RELOADER_PORT', 8050)

    @property
    def PHONE_IPS(self) -> List[str]:
        """List of phone IP addresses for WiFi connections."""
        return self.get('PHONE_IPS', [])

    # === Window & Display Properties ===

    @property
    def WINDOW_TITLE(self) -> str:
        """Window title for scrcpy."""
        return self.get('WINDOW_TITLE', 'Kivy Reloader')

    @property
    def WINDOW_X(self) -> int:
        """Window X position."""
        value = self.get('WINDOW_X', 1200)
        return int(value) if isinstance(value, (int, str)) else 1200

    @property
    def WINDOW_Y(self) -> int:
        """Window Y position."""
        value = self.get('WINDOW_Y', 100)
        return int(value) if isinstance(value, (int, str)) else 100

    @property
    def WINDOW_WIDTH(self) -> int:
        """Window width."""
        value = self.get('WINDOW_WIDTH', 280)
        return int(value) if isinstance(value, (int, str)) else 280

    @property
    def WINDOW_HEIGHT(self) -> int:
        """Window height."""
        value = self.get('WINDOW_HEIGHT', 0)
        return int(value) if isinstance(value, (int, str)) else 0

    @property
    def FULLSCREEN(self) -> bool:
        """Start scrcpy in fullscreen mode."""
        return self.get('FULLSCREEN', False)

    @property
    def WINDOW_BORDERLESS(self) -> bool:
        """Disable window decorations (borderless window)."""
        return self.get('WINDOW_BORDERLESS', False)

    @property
    def SHOW_TOUCHES(self) -> bool:
        """Show touch indicators in scrcpy."""
        return self.get('SHOW_TOUCHES', False)

    @property
    def STAY_AWAKE(self) -> bool:
        """Keep device screen awake."""
        return self.get('STAY_AWAKE', False)

    @property
    def TURN_SCREEN_OFF(self) -> bool:
        """Turn off device screen during mirroring."""
        return self.get('TURN_SCREEN_OFF', False)

    @property
    def ALWAYS_ON_TOP(self) -> bool:
        """Keep scrcpy window always on top."""
        return self.get('ALWAYS_ON_TOP', True)

    @property
    def DISPLAY_ORIENTATION(self) -> int:
        """Set initial display orientation (0, 90, 180, 270)."""
        return self.get('DISPLAY_ORIENTATION', 0)

    @property
    def CROP_AREA(self) -> str:
        """Crop device screen. Format: 'width:height:x:y' or empty for no crop."""
        return self.get('CROP_AREA', '')

    # === Performance & Quality Properties ===

    @property
    def MAX_SIZE(self) -> int:
        """Maximum video resolution (0 = unlimited)."""
        return self.get('MAX_SIZE', 0)

    @property
    def MAX_FPS(self) -> int:
        """Maximum frame rate (0 = unlimited)."""
        return self.get('MAX_FPS', 0)

    @property
    def VIDEO_BIT_RATE(self) -> str:
        """Video bit rate (e.g., '8M', '4M', '2M')."""
        return self.get('VIDEO_BIT_RATE', '8M')

    @property
    def PRINT_FPS(self) -> bool:
        """Print framerate logs to console."""
        return self.get('PRINT_FPS', False)

    @property
    def RENDER_DRIVER(self) -> str:
        """SDL render driver. Use 'software' for VMs, or 'opengl'/'direct3d'/'metal'."""
        return self.get('RENDER_DRIVER', '')

    @property
    def NO_MOUSE_HOVER(self) -> bool:
        """Disable mouse hover events (improves performance)."""
        return self.get('NO_MOUSE_HOVER', True)

    @property
    def DISABLE_SCREENSAVER(self) -> bool:
        """Disable screensaver during mirroring (prevents interruptions)."""
        return self.get('DISABLE_SCREENSAVER', True)

    # === Audio Properties ===

    @property
    def NO_AUDIO(self) -> bool:
        """Disable audio forwarding."""
        return self.get('NO_AUDIO', True)

    @property
    def NO_AUDIO_PLAYBACK(self) -> bool:
        """Disable audio playback on computer (but keep device audio)."""
        return self.get('NO_AUDIO_PLAYBACK', False)

    @property
    def AUDIO_SOURCE(self) -> str:
        """Audio source: output, playback, mic, mic-unprocessed, etc."""
        return self.get('AUDIO_SOURCE', 'output')

    @property
    def AUDIO_BIT_RATE(self) -> str:
        """Audio bit rate (e.g., '128K', '64K')."""
        return self.get('AUDIO_BIT_RATE', '128K')

    # === Control & Interaction Properties ===

    @property
    def NO_CONTROL(self) -> bool:
        """Disable device control (read-only mirror)."""
        return self.get('NO_CONTROL', False)

    @property
    def SHORTCUT_MOD(self) -> str:
        """Shortcut modifier keys (e.g., 'lalt,lsuper')."""
        return self.get('SHORTCUT_MOD', 'lalt,lsuper')

    # === Advanced Properties ===

    @property
    def KILL_ADB_ON_CLOSE(self) -> bool:
        """Kill ADB when scrcpy terminates."""
        return self.get('KILL_ADB_ON_CLOSE', False)

    @property
    def POWER_OFF_ON_CLOSE(self) -> bool:
        """Turn device screen off when closing scrcpy."""
        return self.get('POWER_OFF_ON_CLOSE', False)

    @property
    def TIME_LIMIT(self) -> int:
        """Maximum mirroring time in seconds (0 = unlimited)."""
        return self.get('TIME_LIMIT', 0)

    @property
    def SCREEN_OFF_TIMEOUT(self) -> int:
        """Screen off timeout in seconds (0 = no change)."""
        return self.get('SCREEN_OFF_TIMEOUT', 0)

    @property
    def RECORD_SESSION(self) -> bool:
        """Enable session recording."""
        return self.get('RECORD_SESSION', False)

    @property
    def RECORD_FILE_PATH(self) -> str:
        """Path for recorded session file."""
        return self.get('RECORD_FILE_PATH', 'session_recording.mp4')

    # === Service Properties ===

    @property
    def SERVICE_FILES(self) -> List[str]:
        """Service files to watch."""
        return self.get('SERVICE_FILES', [])

    @property
    def SERVICE_NAMES(self) -> List[str]:
        """Service names for logging filters."""
        return self.get('SERVICE_NAMES', [])

    # === Deployment Properties ===

    @property
    def FOLDERS_AND_FILES_TO_EXCLUDE_FROM_PHONE(self) -> List[str]:
        """Files and folders to exclude when deploying to phone."""
        return self.get(
            'FOLDERS_AND_FILES_TO_EXCLUDE_FROM_PHONE', self.DEFAULT_EXCLUSIONS
        )


# Global configuration instance
config = Config()
