from __future__ import annotations

import hashlib
import socket
from pathlib import Path


def _should_launch_flightdeck() -> bool:
    try:
        import tomlkit
        t = Path.cwd() / 'kivy-reloader.toml'
        if not t.exists():
            return False
        data = tomlkit.loads(t.read_text())
        return bool(data.get('kivy_reloader', {}).get('PERSISTENT_FLIGHTDECK', True))
    except Exception:
        return False


def _acquire_flightdeck_lock(cwd: Path) -> socket.socket | None:
    tag = int(hashlib.md5(str(cwd).encode()).hexdigest()[:4], 16)
    port = 49152 + (tag % 16383)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(('127.0.0.1', port))
        s.listen(1)
        return s
    except OSError:
        s.close()
        return None


def launch_or_run(app_factory):
    """Read PERSISTENT_FLIGHTDECK from toml; open FlightDeck or run the app."""
    if _should_launch_flightdeck():
        from kivy_reloader.configurator.gui import run_gui
        run_gui(base=Path.cwd(), config_path=Path.cwd() / 'kivy-reloader.toml')
    else:
        import trio
        app = app_factory()
        trio.run(app.async_run, 'trio')

def _is_flightdeck_running(cwd: Path) -> bool:
    tag = int(hashlib.md5(str(cwd).encode()).hexdigest()[:4], 16)
    port = 49152 + (tag % 16383)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.1)
    try:
        s.connect(('127.0.0.1', port))
        s.close()
        return True
    except OSError:
        return False
