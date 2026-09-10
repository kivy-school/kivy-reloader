"""GitHub Device Flow auth for Flightdeck.

Flow: click button → browser opens to pre-filled auth page → user clicks Authorize → done.
No client_secret. No localhost server. No code typing.

Requires a GitHub OAuth App (not GitHub App):
  - Register at github.com/settings/applications/new
  - "Expire user access tokens": ON (refresh tokens handled automatically)
  - No callback URL or special settings needed for device flow
"""

import threading
import time
from pathlib import Path

import requests
import tomlkit

CLIENT_ID = 'Ov23lisOd7Mj47PzCmiM'

CREDENTIALS_PATH = Path.home() / '.config' / 'kivy-reloader' / 'credentials.toml'
_KR_SERVICE = 'kivy-reloader'

_DEVICE_CODE_URL = 'https://github.com/login/device/code'
_TOKEN_URL = 'https://github.com/login/oauth/access_token'


def _kr_get(key: str) -> str | None:
    try:
        import keyring

        return keyring.get_password(_KR_SERVICE, key)
    except Exception:
        return None


def _kr_set(key: str, value: str) -> bool:
    try:
        import keyring

        keyring.set_password(_KR_SERVICE, key, value)
        return True
    except Exception:
        return False


def _kr_delete(key: str) -> None:
    try:
        import keyring

        keyring.delete_password(_KR_SERVICE, key)
    except Exception:
        pass


def get_stored_token() -> str | None:
    """Return access token if stored and not expired. No network calls."""
    # Check expiry from toml first (timestamps are not sensitive)
    expires_at = None
    if CREDENTIALS_PATH.exists():
        try:
            doc = tomlkit.parse(CREDENTIALS_PATH.read_text(encoding='utf-8'))
            expires_at = doc.get('github', {}).get('expires_at')
        except Exception:
            pass
    if expires_at and time.time() > float(expires_at) - 300:
        return None  # expired or within 5-min buffer

    # Try keyring first, fall back to toml
    token = _kr_get('access_token') or (
        tomlkit
        .parse(CREDENTIALS_PATH.read_text(encoding='utf-8'))
        .get('github', {})
        .get('token')
        if CREDENTIALS_PATH.exists()
        else None
    )
    return token or None


def ensure_auth(on_token, on_error, on_status=None) -> None:
    """
    Non-blocking. Silently refreshes if possible, otherwise opens device flow.

    on_token(token: str)  — called on main thread when auth succeeds
    on_error(msg: str)    — called on main thread on failure
    on_status(msg: str)   — called on main thread with UI status updates
    """
    threading.Thread(
        target=_ensure_auth_thread,
        args=(on_token, on_error, on_status),
        daemon=True,
    ).start()


def _ensure_auth_thread(on_token, on_error, on_status):
    from kivy.clock import Clock

    def status(msg):
        print(f'[github_auth] {msg}')
        if on_status:
            Clock.schedule_once(lambda dt: on_status(msg))

    try:
        token = _try_silent_refresh() or _run_device_flow(status)
        print(f'[github_auth] auth succeeded, token prefix={token[:8]}...')
        Clock.schedule_once(lambda dt: on_token(token))
    except Exception as e:
        msg = str(e)
        print(f'[github_auth] auth failed: {msg}')
        Clock.schedule_once(lambda dt: on_error(msg))


def _try_silent_refresh() -> str | None:
    """Use stored refresh_token to get a new access_token silently."""
    # Check expiry from toml (timestamps not sensitive)
    refresh_expires_at = None
    if CREDENTIALS_PATH.exists():
        try:
            doc = tomlkit.parse(CREDENTIALS_PATH.read_text(encoding='utf-8'))
            refresh_expires_at = doc.get('github', {}).get('refresh_expires_at')
        except Exception:
            pass
    if refresh_expires_at and time.time() > float(refresh_expires_at) - 300:
        print('[github_auth] refresh_token expired')
        return None

    # Try keyring first, fall back to toml
    refresh_token = _kr_get('refresh_token')
    if not refresh_token and CREDENTIALS_PATH.exists():
        try:
            doc = tomlkit.parse(CREDENTIALS_PATH.read_text(encoding='utf-8'))
            refresh_token = doc.get('github', {}).get('refresh_token')
        except Exception:
            pass
    if not refresh_token:
        print('[github_auth] no refresh_token stored')
        return None
    try:
        print('[github_auth] trying silent refresh...')
        r = requests.post(
            _TOKEN_URL,
            data={
                'client_id': CLIENT_ID,
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token,
            },
            headers={'Accept': 'application/json'},
            timeout=15,
        )
        print(f'[github_auth] refresh status={r.status_code} body={r.text}')
        r.raise_for_status()
        data = r.json()
        if 'access_token' not in data:
            print('[github_auth] refresh failed, falling back to device flow')
            return None
        _store_token_response(data)
        return data['access_token']
    except Exception as e:
        print(f'[github_auth] refresh error: {e}, falling back to device flow')
        return None


def _copy_to_clipboard(text: str) -> None:
    """Best-effort clipboard copy. Works on Windows, WSL, and Linux."""
    import subprocess

    try:
        # WSL / Windows
        subprocess.run(
            ['clip.exe'], input=text.encode(), check=True, capture_output=True
        )
        return
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    try:
        # Linux with xclip
        subprocess.run(
            ['xclip', '-selection', 'clipboard'],
            input=text.encode(),
            check=True,
            capture_output=True,
        )
        return
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    try:
        # Linux with xsel
        subprocess.run(
            ['xsel', '--clipboard', '--input'],
            input=text.encode(),
            check=True,
            capture_output=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass  # clipboard unavailable — user reads from button


def _open_browser(url: str) -> None:
    """Open URL in default browser. In WSL, webbrowser.open() → xdg-open → no browser.
    Register cmd.exe as a GenericBrowser so webbrowser handles it uniformly."""
    import sys
    import webbrowser

    if sys.platform == 'linux':
        try:
            with open('/proc/version', encoding='utf-8') as _f:
                _is_wsl = 'microsoft' in _f.read().lower()
        except OSError:
            _is_wsl = False
        if _is_wsl:
            webbrowser.GenericBrowser(['cmd.exe', '/c', 'start', '%s']).open(url)
            return
    webbrowser.open(url)


def _run_device_flow(status) -> str:
    """Device flow: open browser, poll until user authorizes. Returns access_token."""

    status('Connecting to GitHub...')
    r = requests.post(
        _DEVICE_CODE_URL,
        data={'client_id': CLIENT_ID, 'scope': 'repo,workflow'},
        headers={'Accept': 'application/json'},
        timeout=15,
    )
    print(f'[github_auth] device code status={r.status_code} body={r.text}')
    r.raise_for_status()
    data = r.json()

    if 'error' in data:
        raise RuntimeError(data.get('error_description', data['error']))

    device_code = data['device_code']
    user_code = data['user_code']
    verification_uri = data['verification_uri']
    expires_in = int(data.get('expires_in', 900))
    interval = int(data.get('interval', 5))

    _copy_to_clipboard(user_code)
    status(f'Code: {user_code} (copied) — paste in browser')
    print(f'[github_auth] opening browser: {verification_uri}')
    _open_browser(verification_uri)

    deadline = time.time() + expires_in
    while time.time() < deadline:
        time.sleep(interval)
        r = requests.post(
            _TOKEN_URL,
            data={
                'client_id': CLIENT_ID,
                'device_code': device_code,
                'grant_type': 'urn:ietf:params:oauth:grant-type:device_code',
            },
            headers={'Accept': 'application/json'},
            timeout=15,
        )
        poll_data = r.json()
        print(f'[github_auth] poll body={poll_data}')

        error = poll_data.get('error')
        if error == 'authorization_pending':
            continue
        if error == 'slow_down':
            interval += 5
            continue
        if error == 'expired_token':
            raise RuntimeError('Authorization expired — try again')
        if error == 'access_denied':
            raise RuntimeError('Access denied by user')
        if error:
            raise RuntimeError(poll_data.get('error_description', error))

        if 'access_token' in poll_data:
            _store_token_response(poll_data)
            return poll_data['access_token']

    raise RuntimeError('Authorization timed out')


def clear_token() -> None:
    """Remove all stored credentials (force re-auth on next build)."""
    _kr_delete('access_token')
    _kr_delete('refresh_token')
    if CREDENTIALS_PATH.exists():
        CREDENTIALS_PATH.unlink()
        print('[github_auth] credentials cleared')


def _store_token_response(data: dict) -> None:
    """Persist access_token + refresh_token in keyring (with toml fallback).
    Timestamps (expires_at, refresh_expires_at) always go to toml — not sensitive.
    """
    CREDENTIALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if CREDENTIALS_PATH.exists():
        doc = tomlkit.parse(CREDENTIALS_PATH.read_text(encoding='utf-8'))
    else:
        doc = tomlkit.document()
    if 'github' not in doc:
        doc.add('github', tomlkit.table())

    access_token = data['access_token']
    # Try keyring; fall back to toml if unavailable
    if not _kr_set('access_token', access_token):
        doc['github']['token'] = access_token
    else:
        # Remove plaintext token if it previously existed
        doc['github'].pop('token', None)

    refresh_token = data.get('refresh_token')
    if refresh_token:
        if not _kr_set('refresh_token', refresh_token):
            doc['github']['refresh_token'] = refresh_token
        else:
            doc['github'].pop('refresh_token', None)

    expires_in = data.get('expires_in')
    if expires_in:
        doc['github']['expires_at'] = str(time.time() + int(expires_in))

    refresh_expires_in = data.get('refresh_token_expires_in')
    if refresh_expires_in:
        doc['github']['refresh_expires_at'] = str(time.time() + int(refresh_expires_in))

    CREDENTIALS_PATH.write_text(tomlkit.dumps(doc), encoding='utf-8')
    print(
        f'[github_auth] credentials saved (keyring={"ok" if _kr_get("access_token") else "fallback→toml"})'
    )
