"""Trigger GitHub Actions APK build, poll status, download, and adb install."""

import threading
import time
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Callable

import requests

DOWNLOAD_PATH = Path.home() / ".config" / "kivy-reloader" / "builds"
RUN_APPEAR_TIMEOUT_S = 120
RUN_APPEAR_POLL_S = 5
BUILD_POLL_S = 15


def trigger_build(
    token: str,
    repo_name: str,
    workflow_file: str,
    on_status: Callable[[str], None],
    on_done: Callable[[str | None], None],
) -> None:
    """
    Non-blocking entry point. Starts a daemon thread.

    on_status(message) ��� called from thread; wiring in core.py routes to main thread
    on_done(apk_path)  — called with path on success, None on failure
    """
    threading.Thread(
        target=_run,
        args=(token, repo_name, workflow_file, on_status, on_done),
        daemon=True,
    ).start()


def _run(token, repo_name, workflow_file, on_status, on_done):
    try:
        from github import Github  # lazy import — optional dep

        g = Github(token)
        repo = g.get_repo(repo_name)
        workflow = repo.get_workflow(workflow_file)

        on_status("Triggering build...")
        workflow.create_dispatch("main")

        on_status("Waiting for run to start...")
        run = _wait_for_run(repo, RUN_APPEAR_TIMEOUT_S, RUN_APPEAR_POLL_S)
        if run is None:
            on_status("Build didn't start — check GitHub Actions tab")
            on_done(None)
            return

        start = time.time()
        while run.status != "completed":
            time.sleep(BUILD_POLL_S)
            run.update()
            elapsed = int(time.time() - start)
            m, s = divmod(elapsed, 60)
            on_status(f"Building... ({m}:{s:02d})")

        if run.conclusion != "success":
            on_status(f"Build {run.conclusion} — check GitHub Actions for logs")
            on_done(None)
            return

        on_status("Downloading APK...")
        artifacts = list(run.get_artifacts())
        if not artifacts:
            on_status("No artifacts found — check upload-artifact step in workflow")
            on_done(None)
            return

        artifact = artifacts[0]
        r = requests.get(
            artifact.archive_download_url,
            headers={"Authorization": f"Bearer {token}"},
            allow_redirects=True,
            timeout=120,
        )
        r.raise_for_status()

        DOWNLOAD_PATH.mkdir(parents=True, exist_ok=True)
        apk_path = None
        with zipfile.ZipFile(BytesIO(r.content)) as z:
            apk_names = [n for n in z.namelist() if n.endswith(".apk")]
            if not apk_names:
                on_status("No APK in artifact ZIP")
                on_done(None)
                return
            apk_path = DOWNLOAD_PATH / apk_names[0]
            apk_path.write_bytes(z.read(apk_names[0]))

        on_status("Installing on device...")
        _adb_install(apk_path, on_status, on_done)

    except Exception as e:
        on_status(f"Error: {e}")
        on_done(None)


def _adb_install(apk_path, on_status, on_done):
    # Delegates entirely to compile_app.install_apk_from_path — same chain as
    # the regular compile+install flow, just with the buildozer build step skipped.
    # On success, fires debug_and_livestream (logcat + scrcpy) the same way
    # compile_app() does after a local build.
    from threading import Event

    from kivy_reloader.compile_app import debug_and_livestream, install_apk_from_path

    ok = install_apk_from_path(apk_path, status_callback=on_status)
    on_done(str(apk_path) if ok else None)

    if ok:
        already_installed = Event()
        already_installed.set()  # APK is on device — skip the wait
        debug_and_livestream(already_installed)


def _wait_for_run(repo, timeout_s: int, poll_s: int):
    """Wait for a new run to appear after workflow_dispatch."""
    existing_ids = {r.id for r in list(repo.get_workflow_runs(branch="main"))[:5]}
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        time.sleep(poll_s)
        for run in list(repo.get_workflow_runs(branch="main"))[:5]:
            if run.id not in existing_ids and run.status in {"queued", "in_progress"}:
                return run
    return None
