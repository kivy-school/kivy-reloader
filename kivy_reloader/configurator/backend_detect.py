"""Detect whether the current project builds with buildozer or ksproject."""

from __future__ import annotations

from pathlib import Path


def detect_backend(base: Path | None = None) -> str:
    """Return 'ksproject' if pyproject.toml has a [tool.kivy-school] section, else 'buildozer'."""
    base = base or Path.cwd()
    pyproject = base / 'pyproject.toml'
    text = pyproject.read_text() if pyproject.exists() else ''
    return 'ksproject' if '[tool.kivy-school]' in text else 'buildozer'
