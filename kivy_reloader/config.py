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
        for dimension in ('WINDOW_X', 'WINDOW_Y', 'WINDOW_WIDTH'):
            value = self.config.get(dimension)
            if value is not None and not isinstance(value, (int, str)):
                logging.warning(f'Invalid {dimension}: {value}. Using default.')
                self.config.pop(dimension, None)

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
        return self.get('DO_NOT_WATCH_PATTERNS', ['*.pyc', '*__pycache__*'])

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
    def NO_AUDIO(self) -> bool:
        """Disable audio in scrcpy."""
        return self.get('NO_AUDIO', True)

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
