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

CLIENT_ID = "Ov23lisOd7Mj47PzCmiM"

CREDENTIALS_PATH = Path.home() / ".config" / "kivy-reloader" / "credentials.toml"

_DEVICE_CODE_URL = "https://github.com/login/device/code"
_TOKEN_URL = "https://github.com/login/oauth/access_token"


def get_stored_token() -> str | None:
    """Return access token if stored and not expired. No network calls."""
    if not CREDENTIALS_PATH.exists():
        return None
    try:
        doc = tomlkit.parse(CREDENTIALS_PATH.read_text(encoding="utf-8"))
        gh = doc.get("github", {})
        token = gh.get("token")
        expires_at = gh.get("expires_at")
        if not token:
            return None
        if expires_at and time.time() > float(expires_at) - 300:
            return None  # expired or within 5-min buffer
        return token
    except Exception:
        return None


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
        print(f"[github_auth] {msg}")
        if on_status:
            Clock.schedule_once(lambda dt: on_status(msg))

    try:
        token = _try_silent_refresh() or _run_device_flow(status)
        print(f"[github_auth] auth succeeded, token prefix={token[:8]}...")
        Clock.schedule_once(lambda dt: on_token(token))
    except Exception as e:
        msg = str(e)
        print(f"[github_auth] auth failed: {msg}")
        Clock.schedule_once(lambda dt: on_error(msg))


def _try_silent_refresh() -> str | None:
    """Use stored refresh_token to get a new access_token silently."""
    if not CREDENTIALS_PATH.exists():
        print("[github_auth] no credentials file, skipping refresh")
        return None
    try:
        doc = tomlkit.parse(CREDENTIALS_PATH.read_text(encoding="utf-8"))
        gh = doc.get("github", {})
        refresh_token = gh.get("refresh_token")
        refresh_expires_at = gh.get("refresh_expires_at")
        if not refresh_token:
            print("[github_auth] no refresh_token stored")
            return None
        if refresh_expires_at and time.time() > float(refresh_expires_at) - 300:
            print("[github_auth] refresh_token expired")
            return None
        print("[github_auth] trying silent refresh...")
        r = requests.post(
            _TOKEN_URL,
            data={
                "client_id": CLIENT_ID,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            headers={"Accept": "application/json"},
            timeout=15,
        )
        print(f"[github_auth] refresh status={r.status_code} body={r.text}")
        r.raise_for_status()
        data = r.json()
        if "access_token" not in data:
            print("[github_auth] refresh failed, falling back to device flow")
            return None
        _store_token_response(data)
        return data["access_token"]
    except Exception as e:
        print(f"[github_auth] refresh error: {e}, falling back to device flow")
        return None


def _copy_to_clipboard(text: str) -> None:
    """Best-effort clipboard copy. Works on Windows, WSL, and Linux."""
    import subprocess
    try:
        # WSL / Windows
        subprocess.run(['clip.exe'], input=text.encode(), check=True,
                       capture_output=True)
        return
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    try:
        # Linux with xclip
        subprocess.run(['xclip', '-selection', 'clipboard'],
                       input=text.encode(), check=True, capture_output=True)
        return
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    try:
        # Linux with xsel
        subprocess.run(['xsel', '--clipboard', '--input'],
                       input=text.encode(), check=True, capture_output=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass  # clipboard unavailable — user reads from button


def _run_device_flow(status) -> str:
    """Device flow: open browser, poll until user authorizes. Returns access_token."""
    import webbrowser

    status("Connecting to GitHub...")
    r = requests.post(
        _DEVICE_CODE_URL,
        data={"client_id": CLIENT_ID, "scope": "repo,workflow"},
        headers={"Accept": "application/json"},
        timeout=15,
    )
    print(f"[github_auth] device code status={r.status_code} body={r.text}")
    r.raise_for_status()
    data = r.json()

    if "error" in data:
        raise RuntimeError(data.get("error_description", data["error"]))

    device_code = data["device_code"]
    user_code = data["user_code"]
    verification_uri = data["verification_uri"]
    expires_in = int(data.get("expires_in", 900))
    interval = int(data.get("interval", 5))

    _copy_to_clipboard(user_code)
    status(f"Code: {user_code} (copied) — paste in browser")
    print(f"[github_auth] opening browser: {verification_uri}")
    webbrowser.open(verification_uri)

    deadline = time.time() + expires_in
    while time.time() < deadline:
        time.sleep(interval)
        r = requests.post(
            _TOKEN_URL,
            data={
                "client_id": CLIENT_ID,
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
            headers={"Accept": "application/json"},
            timeout=15,
        )
        poll_data = r.json()
        print(f"[github_auth] poll body={poll_data}")

        error = poll_data.get("error")
        if error == "authorization_pending":
            continue
        if error == "slow_down":
            interval += 5
            continue
        if error == "expired_token":
            raise RuntimeError("Authorization expired — try again")
        if error == "access_denied":
            raise RuntimeError("Access denied by user")
        if error:
            raise RuntimeError(poll_data.get("error_description", error))

        if "access_token" in poll_data:
            _store_token_response(poll_data)
            return poll_data["access_token"]

    raise RuntimeError("Authorization timed out")


def clear_token() -> None:
    """Remove all stored credentials (force re-auth on next build)."""
    if CREDENTIALS_PATH.exists():
        CREDENTIALS_PATH.unlink()
        print("[github_auth] credentials cleared")


def _store_token_response(data: dict) -> None:
    """Persist access_token, refresh_token, and expiry timestamps."""
    CREDENTIALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if CREDENTIALS_PATH.exists():
        doc = tomlkit.parse(CREDENTIALS_PATH.read_text(encoding="utf-8"))
    else:
        doc = tomlkit.document()
    if "github" not in doc:
        doc.add("github", tomlkit.table())

    doc["github"]["token"] = data["access_token"]

    expires_in = data.get("expires_in")
    if expires_in:
        doc["github"]["expires_at"] = str(time.time() + int(expires_in))

    refresh_token = data.get("refresh_token")
    if refresh_token:
        doc["github"]["refresh_token"] = refresh_token

    refresh_expires_in = data.get("refresh_token_expires_in")
    if refresh_expires_in:
        doc["github"]["refresh_expires_at"] = str(time.time() + int(refresh_expires_in))

    CREDENTIALS_PATH.write_text(tomlkit.dumps(doc), encoding="utf-8")
    print(f"[github_auth] credentials saved to {CREDENTIALS_PATH}")
