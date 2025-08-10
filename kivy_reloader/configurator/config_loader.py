"""Configuration loading helper for configurator GUI.

Uses stdlib ``tomllib`` when available (Python 3.11+) with fallback to
``toml`` if installed. Returns a flat dict of key->value from the
``[kivy_reloader]`` section. Missing file returns empty dict.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

try:  # Python 3.11+
    import tomllib as _toml  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    try:
        import toml as _toml  # type: ignore
    except ModuleNotFoundError:  # pragma: no cover
        _toml = None  # type: ignore


def load_config_values(config_path: Path) -> Dict[str, Any]:
    if not config_path.exists() or _toml is None:
        return {}
    try:
        with config_path.open('rb') as f:  # tomllib requires bytes
            data = _toml.load(f)  # type: ignore
    except Exception:  # pragma: no cover - any parse error -> empty
        return {}
    section = data.get('kivy_reloader', {}) if isinstance(data, dict) else {}
    clean: Dict[str, Any] = {}
    for k, v in section.items():
        clean[k] = v
    return clean
