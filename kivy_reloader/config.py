import os
from typing import Any, List

import toml
import sys

class Config:
    def __init__(self):
        self.config_file = os.path.join(os.getcwd(), "kivy-reloader.toml")
        self.constants_to_import = [
            "FULL_RELOAD_FILES",
            "WATCHED_FILES",
            "WATCHED_FOLDERS",
            "WATCHED_FOLDERS_RECURSIVELY",
            "DO_NOT_WATCH_PATTERNS",
            "HOT_RELOAD_ON_PHONE",
            "STREAM_USING",
            "PORT",
            "PHONE_IPS",
            "WINDOW_TITLE",
            "SHOW_TOUCHES",
            "STAY_AWAKE",
            "TURN_SCREEN_OFF",
            "ALWAYS_ON_TOP",
            "WINDOW_X",
            "WINDOW_Y",
            "WINDOW_WIDTH",
            "SERVICE_FILES",
            "SERVICE_NAMES",
            "NO_AUDIO",
        ]
        if not hasattr(sys, "_MEIPASS"):
            self._load_config()
        elif hasattr(sys, "_MEIPASS"):
            print("PyInstaller environment detected. Make sure to turn your kivy_reloader app into a kivy app. see: https://kivyschool.com/kivy-reloader/windows/setup-and-how-to-use/")

    def _load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, "r") as f:
                self.config = toml.load(f)["kivy_reloader"]
        else:
            raise FileNotFoundError(
                f"Config file not found: {self.config_file}. Please execute `kivy-reloader init` first."
            )

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def set(self, key: str, value: Any):
        self.config[key] = value

    def save(self):
        with open(self.config_file, "w") as f:
            toml.dump(self.config, f)

        self._load_config()

        return self

    @property
    def WATCHED_FILES(self) -> List[str]:
        return self.get("WATCHED_FILES", [])

    @property
    def WATCHED_FOLDERS(self) -> List[str]:
        return self.get("WATCHED_FOLDERS", [])

    @property
    def WATCHED_FOLDERS_RECURSIVELY(self) -> List[str]:
        return self.get("WATCHED_FOLDERS_RECURSIVELY", [])

    @property
    def DO_NOT_WATCH_PATTERNS(self) -> List[str]:
        return self.get("DO_NOT_WATCH_PATTERNS", ["*.pyc", "*__pycache__*"])

    @property
    def HOT_RELOAD_ON_PHONE(self) -> bool:
        return self.get("HOT_RELOAD_ON_PHONE", False)

    @property
    def STREAM_USING(self) -> str:
        return self.get("STREAM_USING", "")

    @property
    def PORT(self) -> int:
        return self.get("PORT", 5555)

    @property
    def PHONE_IPS(self) -> List[str]:
        return self.get("PHONE_IPS", [])

    @property
    def WINDOW_TITLE(self) -> str:
        return self.get("WINDOW_TITLE", "Kivy Reloader")

    @property
    def SHOW_TOUCHES(self) -> bool:
        return self.get("SHOW_TOUCHES", False)

    @property
    def STAY_AWAKE(self) -> bool:
        return self.get("STAY_AWAKE", False)

    @property
    def TURN_SCREEN_OFF(self) -> bool:
        return self.get("TURN_SCREEN_OFF", False)

    @property
    def ALWAYS_ON_TOP(self) -> bool:
        return self.get("ALWAYS_ON_TOP", True)

    @property
    def WINDOW_X(self) -> str:
        return self.get("WINDOW_X", "1200")

    @property
    def WINDOW_Y(self) -> str:
        return self.get("WINDOW_Y", "100")

    @property
    def WINDOW_WIDTH(self) -> str:
        return self.get("WINDOW_WIDTH", "280")

    @property
    def SERVICE_FILES(self) -> List[str]:
        return self.get("SERVICE_FILES", [])

    @property
    def SERVICE_NAMES(self) -> List[str]:
        return self.get("SERVICE_NAMES", [])

    @property
    def FOLDERS_AND_FILES_TO_EXCLUDE_FROM_PHONE(self) -> List[str]:
        return self.get(
            "FOLDERS_AND_FILES_TO_EXCLUDE_FROM_PHONE",
            [
                "*.pyc",
                "__pycache__",
                ".buildozer",
                ".venv",
                ".vscode",
                ".git",
                ".pytest_cache",
                ".DS_Store",
                ".env",
                ".dmypy.json",
                ".mypy_cache/",
                ".dmypy.json",
                "dmypy.json",
                "env/",
                "ENV/",
                "env.bak/",
                "venv/",
                "venv.bak/",
                "bin",
                "buildozer.spec",
                "poetry.lock",
                "pyproject.toml",
                "temp",
                "tests",
                "app_copy.zip",
                "send_app_to_phone.py",
                ".gitignore",
                "README.md",
            ],
        )

    @property
    def NO_AUDIO(self) -> str:
        return self.get("NO_AUDIO", True)

    @property
    def FULL_RELOAD_FILES(self) -> List[str]:
        return self.get("FULL_RELOAD_FILES", [])


config = Config()
