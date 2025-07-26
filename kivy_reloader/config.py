import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict

import toml

DEFAULTS: Dict[str, Any] = {
    'FULL_RELOAD_FILES': [],
    'WATCHED_FILES': [],
    'WATCHED_FOLDERS': [],
    'WATCHED_FOLDERS_RECURSIVELY': [],
    'DO_NOT_WATCH_PATTERNS': ['*.pyc', '*__pycache__*'],
    'HOT_RELOAD_ON_PHONE': False,
    'STREAM_USING': 'USB',
    'PORT': 5555,
    'ADB_PORT': 5555,
    'RELOADER_PORT': 8050,
    'PHONE_IPS': [],
    'WINDOW_TITLE': 'Kivy Reloader',
    'SHOW_TOUCHES': False,
    'STAY_AWAKE': False,
    'TURN_SCREEN_OFF': False,
    'ALWAYS_ON_TOP': True,
    'WINDOW_X': '1200',
    'WINDOW_Y': '100',
    'WINDOW_WIDTH': '280',
    'SERVICE_FILES': [],
    'SERVICE_NAMES': [],
    'FOLDERS_AND_FILES_TO_EXCLUDE_FROM_PHONE': [
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
        '.dmypy.json',
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
    ],
    'NO_AUDIO': True,
}


@dataclass
class Config:
    """Configuration handler for ``kivy-reloader``."""

    config_file: str = field(
        default_factory=lambda: os.path.join(
            os.getcwd(),
            'kivy-reloader.toml',
        ),
    )
    config: Dict[str, Any] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        if not hasattr(sys, '_MEIPASS'):
            self.load()
        else:
            print(
                'PyInstaller environment detected.'
                'Make sure to turn your kivy_reloader app into a kivy app:'
                'https://kivyschool.com/kivy-reloader/windows/setup-and-how-to-use/'
            )

    def load(self) -> None:
        """Load configuration from ``self.config_file``."""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = toml.load(f)
            self.config = data.get('kivy_reloader', data)
        else:
            raise FileNotFoundError(
                f'Config file not found: {self.config_file}. '
                'Please execute `kivy-reloader init` first.'
            )

    def get(self, key: str, default: Any | None = None) -> Any:
        return self.config.get(key, DEFAULTS.get(key, default))

    def set(self, key: str, value: Any) -> None:
        self.config[key] = value

    def save(self) -> "Config":
        with open(self.config_file, 'w', encoding='utf-8') as f:
            toml.dump({'kivy_reloader': self.config}, f)

        self.load()

        return self

    def __getattr__(self, item: str) -> Any:
        try:
            return self.get(item)
        except KeyError as exc:  # pragma: no cover - defensive
            raise AttributeError(item) from exc


config = Config()
