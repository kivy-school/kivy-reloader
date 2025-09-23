"""Configurator package (WIP).

This module exposes ``launch_configurator`` used by the
``kivy-reloader config`` CLI command. The actual GUI code lives in
``gui.py`` so that this file stays light (path resolution + meta dir
setup) and can be imported without requiring Kivy.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Tuple


def _resolve_paths(
    project_dir: Optional[str],
    config_filename: str,
    config_file: Optional[str],
) -> Tuple[Path, Path, Path]:
    """Return (base_dir, config_path, meta_dir)."""
    if config_file:
        cf = Path(config_file).expanduser().resolve()
        if cf.is_dir():
            base = cf
            config_path = base / config_filename
        else:
            base = cf.parent
            config_path = cf
        return base, config_path, base / '.kivy-reloader'

    base = Path(project_dir or os.getcwd()).resolve()
    return base, base / config_filename, base / '.kivy-reloader'


def launch_configurator(
    project_dir: Optional[str] = None,
    config_filename: str = 'kivy-reloader.toml',
    config_file: Optional[str] = None,
    debug: bool = False,
) -> None:
    """Launch the visual configurator (delegates to ``gui.run_gui``).

    Performs only filesystem preparation here; GUI heavy imports are done
    lazily inside ``gui.run_gui``.
    """

    base, config_path, meta_dir = _resolve_paths(
        project_dir, config_filename, config_file
    )

    # Ensure meta directory exists.
    try:
        meta_dir.mkdir(exist_ok=True)
    except Exception as exc:  # pragma: no cover
        print(f'[KIVY RELOADER] Warning: could not create {meta_dir}: {exc}')

    if not config_path.exists():
        print(
            f"[KIVY RELOADER] Config file '{config_path.name}' not found in {base}. "
            "Run 'kivy-reloader init' first to generate it."
        )

    from .gui import run_gui  # local import to keep Kivy optional until needed

    run_gui(base=base, config_path=config_path, debug=debug)
