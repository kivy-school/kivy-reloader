from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Status(Enum):
    OK = 'ok'
    WARN = 'warn'
    FAIL = 'fail'
    SKIP = 'skip'


@dataclass
class CheckResult:
    name: str
    status: Status
    detail: str


def detect_os() -> str:
    if sys.platform == 'darwin':
        return 'macos'
    if sys.platform == 'win32':
        return 'windows'
    try:
        version = Path('/proc/version').read_text().lower()
        if 'microsoft' in version:
            return 'wsl2'
    except Exception:
        pass
    return 'linux'


def _run(cmd: list[str], timeout: int = 5) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as e:
        return -1, str(e)


def _get_windows_home() -> Path | None:
    """Resolve Windows user home from WSL2 (checks USERPROFILE then /mnt/c/Users)."""
    userprofile = os.environ.get('USERPROFILE', '')
    if userprofile:
        p = userprofile.replace('\\', '/')
        if len(p) >= 2 and p[1] == ':':
            drive = p[0].lower()
            p = f'/mnt/{drive}' + p[2:]
        candidate = Path(p)
        if candidate.exists():
            return candidate

    users = Path('/mnt/c/Users')
    if users.exists():
        skip = {'Public', 'Default', 'Default User', 'All Users', 'desktop.ini'}
        for d in sorted(users.iterdir()):
            if d.is_dir() and d.name not in skip:
                return d
    return None


def _find_toml(config_path: Path | None = None) -> Path | None:
    if config_path and config_path.exists():
        return config_path
    for p in [Path.cwd(), *Path.cwd().parents]:
        t = p / 'kivy-reloader.toml'
        if t.exists():
            return t
        if p == p.parent:
            break
    return None


def _read_stream_using(config_path: Path | None = None) -> str | None:
    t = _find_toml(config_path)
    if not t:
        return None
    try:
        import tomlkit
        data = tomlkit.loads(t.read_text())
        val = data.get('kivy_reloader', {}).get('STREAM_USING')
        return str(val) if val is not None else None
    except Exception:
        return None


def _read_reloader_port(config_path: Path | None = None) -> int:
    t = _find_toml(config_path)
    if not t:
        return 8050
    try:
        import tomlkit
        data = tomlkit.loads(t.read_text())
        return int(data.get('kivy_reloader', {}).get('RELOADER_PORT', 8050))
    except Exception:
        return 8050


# ── WSL2 environment ──────────────────────────────────────────────────────────

def check_display() -> CheckResult:
    val = os.environ.get('DISPLAY', '')
    if val:
        return CheckResult('DISPLAY env', Status.OK, val)
    return CheckResult('DISPLAY env', Status.FAIL,
                       'Not set — VcXsrv/X11 may not be running')


def check_wsl2_networking() -> CheckResult:
    win_home = _get_windows_home()
    if not win_home:
        return CheckResult('WSL2 mirrored networking', Status.WARN,
                           'Could not find Windows home dir (/mnt/c/Users/*)')
    wslconfig = win_home / '.wslconfig'
    if not wslconfig.exists():
        return CheckResult('WSL2 mirrored networking', Status.WARN,
                           f'{wslconfig} not found — NAT mode (WiFi streaming may fail)')
    content = wslconfig.read_text().lower().replace(' ', '')
    if 'networkingmode=mirrored' in content:
        return CheckResult('WSL2 mirrored networking', Status.OK,
                           f'mirrored ✓  ({wslconfig})')
    return CheckResult('WSL2 mirrored networking', Status.WARN,
                       f'networkingMode not mirrored in {wslconfig}')


def check_adb_port_conflict() -> CheckResult:
    rc, out = _run(['ss', '-tlnp'])
    if rc != 0:
        rc, out = _run(['netstat', '-tlnp'])
    if '5037' not in out:
        return CheckResult('ADB port 5037', Status.OK, 'Port 5037 free')
    if 'adb' in out:
        return CheckResult('ADB port 5037', Status.OK, 'adb holding port 5037')
    return CheckResult('ADB port 5037', Status.WARN,
                       'Port 5037 held by unknown process — may conflict with Windows adb')


def check_xclip() -> CheckResult:
    for tool in ('xclip', 'xsel'):
        p = shutil.which(tool)
        if p:
            return CheckResult('xclip/xsel', Status.OK, p)
    return CheckResult('xclip/xsel', Status.WARN,
                       'Neither found — sudo apt install xclip')


def check_wsl2_adb_nodaemon() -> CheckResult:
    try:
        result = subprocess.run(
            ['cmd.exe', '/c', 'wmic process where "name=\'adb.exe\'" get CommandLine'],
            capture_output=True, text=True, timeout=5,
        )
        cmdlines = result.stdout.lower()
        if '-a' in cmdlines and 'nodaemon' in cmdlines and 'server' in cmdlines:
            return CheckResult('ADB nodaemon mode', Status.OK, 'adb.exe running as nodaemon server ✓')
        return CheckResult('ADB nodaemon mode', Status.WARN,
                           'Not in nodaemon mode — kivy-reloader will restart it on next run')
    except Exception as e:
        return CheckResult('ADB nodaemon mode', Status.FAIL, str(e))


def check_wsl2_adb_listening() -> CheckResult:
    try:
        result = subprocess.run(
            ['cmd.exe', '/c', 'adb.exe', 'start-server'],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return CheckResult('ADB server listening', Status.OK, 'adb.exe start-server OK ✓')
        return CheckResult('ADB server listening', Status.WARN,
                           (result.stdout + result.stderr).strip() or 'non-zero exit')
    except subprocess.TimeoutExpired:
        return CheckResult('ADB server listening', Status.FAIL, 'timed out — adb.exe not found?')
    except Exception as e:
        return CheckResult('ADB server listening', Status.FAIL, str(e))


def check_wsl2_adb_forward(config_path: Path | None = None) -> CheckResult:
    port = _read_reloader_port(config_path)
    pattern = re.compile(rf'tcp:{port}\s+tcp:{port}\b')
    try:
        result = subprocess.run(
            ['cmd.exe', '/c', 'adb.exe', 'forward', '--list'],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.lower().splitlines():
            if pattern.search(line):
                return CheckResult('ADB port forward', Status.OK, f'tcp:{port} → tcp:{port} ✓')
        return CheckResult('ADB port forward', Status.WARN,
                           f'tcp:{port} not forwarded — run: adb forward tcp:{port} tcp:{port}')
    except Exception as e:
        return CheckResult('ADB port forward', Status.FAIL, str(e))


# ── ADB + device ──────────────────────────────────────────────────────────────

def check_adb() -> CheckResult:
    path = shutil.which('adb')
    if not path:
        return CheckResult('adb in PATH', Status.FAIL,
                           'Not found — install android-platform-tools')
    rc, out = _run(['adb', 'version'])
    ver = out.split('\n')[0] if out else '?'
    return CheckResult('adb in PATH', Status.OK, f'{path}  ({ver})')


def check_adb_device() -> CheckResult:
    rc, out = _run(['adb', 'devices'])
    if rc != 0:
        return CheckResult('ADB device', Status.FAIL, 'adb devices failed')
    lines = [l for l in out.splitlines()[1:] if l.strip()]
    if not lines:
        return CheckResult('ADB device', Status.FAIL, 'No devices connected')
    unauthorized = [l for l in lines if 'unauthorized' in l]
    if unauthorized:
        return CheckResult('ADB device', Status.WARN,
                           f'{len(unauthorized)} device(s) unauthorized — allow USB debugging on phone')
    devices = [l.split('\t')[0] for l in lines if 'device' in l]
    return CheckResult('ADB device', Status.OK, '  '.join(devices))


def get_connected_devices() -> list[dict]:
    """Return one dict per ADB device with serial, name, connection type and status."""
    rc, out = _run(['adb', 'devices', '-l'])
    if rc != 0:
        return []
    results = []
    for line in out.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        serial, state = parts[0], parts[1]
        conn = 'WIFI' if re.match(r'\d+\.\d+\.\d+\.\d+:\d+', serial) else 'USB'
        if state == 'device':
            dev_status, detail = 'ok', 'authorized'
            _, model = _run(['adb', '-s', serial, 'shell', 'getprop', 'ro.product.model'], timeout=4)
            name = model.strip() or serial
        elif state == 'unauthorized':
            dev_status, detail = 'warn', 'unauthorized — tap Allow on phone'
            name = 'Unknown (could be old connection)'
        elif state == 'offline':
            dev_status, detail = 'fail', 'offline'
            name = 'Unknown (could be old connection)'
        else:
            dev_status, detail = 'warn', state
            name = 'Unknown'
        results.append({
            'serial': serial,
            'name': name,
            'connection': conn,
            'device_status': dev_status,
            'status_detail': detail,
        })
    return results


# ── Project config ────────────────────────────────────────────────────────────

def check_toml(config_path: Path | None = None) -> CheckResult:
    t = _find_toml(config_path)
    if t:
        return CheckResult('kivy-reloader.toml', Status.OK, str(t))
    return CheckResult('kivy-reloader.toml', Status.FAIL,
                       'Not found — run: uv run kivy-reloader init project')


def check_stream_using(config_path: Path | None = None) -> CheckResult:
    val = _read_stream_using(config_path)
    if val is None:
        return CheckResult('STREAM_USING', Status.WARN, 'toml missing or unreadable')
    return CheckResult('STREAM_USING', Status.OK if val in ('WIFI', 'USB') else Status.WARN, val)


# ── Connectivity ──────────────────────────────────────────────────────────────

def check_wifi_ip(config_path: Path | None = None) -> CheckResult:
    su = _read_stream_using(config_path)
    if su != 'WIFI':
        return CheckResult('Device WiFi IP', Status.SKIP, f'STREAM_USING={su}')
    rc, out = _run(['adb', 'shell', 'ip', 'route', 'get', '8.8.8.8'], timeout=8)
    if rc != 0:
        return CheckResult('Device WiFi IP', Status.FAIL, 'adb shell failed')
    import re
    m = re.search(r'src\s+(\d+\.\d+\.\d+\.\d+)', out)
    if m:
        return CheckResult('Device WiFi IP', Status.OK, m.group(1))
    return CheckResult('Device WiFi IP', Status.WARN, f'Could not parse IP: {out[:80]}')


def check_port_reachable(config_path: Path | None = None) -> CheckResult:
    su = _read_stream_using(config_path)
    if su != 'WIFI':
        return CheckResult('Port 8050 reachable', Status.SKIP, f'STREAM_USING={su}')
    rc, out = _run(['adb', 'shell', 'ip', 'route', 'get', '8.8.8.8'], timeout=8)
    import re
    m = re.search(r'src\s+(\d+\.\d+\.\d+\.\d+)', out)
    if not m:
        return CheckResult('Port 8050 reachable', Status.WARN, 'Could not determine device IP')
    ip = m.group(1)
    try:
        s = socket.create_connection((ip, 8050), timeout=3)
        s.close()
        return CheckResult('Port 8050 reachable', Status.OK, f'{ip}:8050 open')
    except OSError:
        return CheckResult('Port 8050 reachable', Status.WARN,
                           f'{ip}:8050 not reachable — is the app running on phone?')


# ── Build tools ───────────────────────────────────────────────────────────────

def check_java() -> CheckResult:
    rc, out = _run(['java', '-version'])
    if rc != 0 or not out:
        return CheckResult('Java 17', Status.FAIL, 'java not found — install openjdk-17')
    first = out.split('\n')[0]
    if '17' in first:
        return CheckResult('Java 17', Status.OK, first)
    return CheckResult('Java 17', Status.WARN, f'Expected 17, got: {first}')


# ── macOS ─────────────────────────────────────────────────────────────────────

def check_homebrew() -> CheckResult:
    path = shutil.which('brew')
    if path:
        return CheckResult('Homebrew', Status.OK, path)
    return CheckResult('Homebrew', Status.FAIL, 'brew not found')


def check_brew_adb() -> CheckResult:
    rc, out = _run(['brew', 'list', 'android-platform-tools'])
    if rc == 0:
        return CheckResult('android-platform-tools (brew)', Status.OK, 'installed')
    return CheckResult('android-platform-tools (brew)', Status.FAIL,
                       'brew install android-platform-tools')


# ── entry point ───────────────────────────────────────────────────────────────

def run_all_checks(config_path: Path | None = None) -> list[CheckResult]:
    os_name = detect_os()
    results: list[CheckResult] = []

    # 1. OS-specific environment first (most likely to cause all other failures)
    if os_name == 'wsl2':
        results += [
            check_wsl2_networking(),
            check_display(),
            check_adb_port_conflict(),
            check_xclip(),
        ]
    elif os_name == 'linux':
        results += [check_display(), check_xclip()]
    elif os_name == 'macos':
        results += [check_homebrew(), check_brew_adb()]

    # 2. ADB + device
    if os_name == 'wsl2':
        results += [
            check_wsl2_adb_nodaemon(),
            check_wsl2_adb_listening(),
            check_wsl2_adb_forward(config_path),
        ]
    results += [check_adb(), check_adb_device()]

    # 3. Project config
    results += [check_toml(config_path), check_stream_using(config_path)]

    # 4. Connectivity (skips automatically if not WIFI mode)
    results += [check_wifi_ip(config_path), check_port_reachable(config_path)]

    # 5. Build tools
    results += [check_java()]

    return results


def format_report(results: list[CheckResult], config_path: Path | None = None) -> str:
    import platform
    from datetime import datetime

    try:
        import kivy
        kivy_ver = kivy.__version__
    except Exception:
        kivy_ver = '?'
    try:
        from kivy_reloader import __version__ as kr_ver
    except Exception:
        kr_ver = '?'

    lines = [
        '=== Kivy Reloader Diagnostic Report ===',
        f'Date:            {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
        f'OS:              {detect_os().upper()}  ({platform.platform()})',
        f'Python:          {sys.version.split()[0]}',
        f'Kivy:            {kivy_ver}',
        f'kivy-reloader:   {kr_ver}',
        f'Config:          {config_path or "not found"}',
        '',
        '--- Checks ---',
    ]
    for r in results:
        icon = {'ok': '✓', 'warn': '⚠', 'fail': '✗', 'skip': '—'}[r.status.value]
        lines.append(f'{icon}  {r.name}')
        lines.append(f'   {r.detail}')
    lines += ['', '=== End of Report ===']
    return '\n'.join(lines)
