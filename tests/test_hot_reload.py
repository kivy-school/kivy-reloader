#!/usr/bin/env python3
"""
Hot-reload test: scaffold hello world, start in dev mode (DesktopApp),
modify a watched file, verify the app rebuilds automatically.

Run via: xvfb-run -a uv run python tests/test_hot_reload.py
"""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

STARTUP_MARKER = "Starting Async Kivy app"
RELOAD_MARKER = "Rebuilding the application"
TIMEOUT_STARTUP = 30
TIMEOUT_RELOAD = 20


def main():
    with tempfile.TemporaryDirectory(prefix="kivy_hot_reload_") as tmpdir:
        tmppath = Path(tmpdir)
        print(f"Scaffolding in {tmpdir}...")

        original_dir = os.getcwd()
        os.chdir(tmpdir)
        try:
            from kivy_reloader.bootstrap import scaffold_hello_world
            scaffold_hello_world()
        finally:
            os.chdir(original_dir)

        env = {
            **os.environ,
            # No RELOADER_STATUS=PROD → uses DesktopApp with hot-reload
            "KIVY_NO_ENV_CONFIG": "1",
            "KIVY_LOG_MODE": "PYTHON",
        }

        proc = subprocess.Popen(
            ["uv", "run", "python", "main.py"],
            cwd=tmpdir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        # Phase 1: wait for startup
        started = False
        deadline = time.monotonic() + TIMEOUT_STARTUP
        try:
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    break
                line = proc.stdout.readline()
                if line:
                    print(line, end="", flush=True)
                    if STARTUP_MARKER in line:
                        started = True
                        break
        except Exception as e:
            print(f"Error during startup: {e}")

        if not started:
            proc.terminate()
            proc.wait(timeout=5)
            print(f"\nHOT-RELOAD TEST FAILED: '{STARTUP_MARKER}' not found within {TIMEOUT_STARTUP}s")
            return 1

        # Give watchdog a moment to register file watches
        time.sleep(1.5)

        # Phase 2: modify a watched .kv file
        kv_file = tmppath / "hello_world" / "screens" / "main_screen.kv"
        kv_file.write_text(kv_file.read_text() + "\n# hot-reload-trigger\n")
        print(f"\nModified: {kv_file.name}")

        # Phase 3: wait for reload
        reloaded = False
        deadline = time.monotonic() + TIMEOUT_RELOAD
        try:
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    break
                line = proc.stdout.readline()
                if line:
                    print(line, end="", flush=True)
                    if RELOAD_MARKER in line:
                        reloaded = True
                        break
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    if reloaded:
        print(f"\nHOT-RELOAD TEST PASSED: detected '{RELOAD_MARKER}'")
        return 0

    print(f"\nHOT-RELOAD TEST FAILED: '{RELOAD_MARKER}' not found within {TIMEOUT_RELOAD}s")
    return 1


if __name__ == "__main__":
    sys.exit(main())
