#!/usr/bin/env python3
"""
Smoke test: bootstrap a fresh hello world in a temp dir, run it headlessly,
verify HELLO_WORLD_STARTED appears, then clean up.
Run via: xvfb-run -a uv run python tests/test_smoke.py
"""

import os
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

from kivy_reloader.bootstrap import scaffold_hello_world

TARGET = 'HELLO_WORLD_STARTED'
TIMEOUT = 30


def main():
    with tempfile.TemporaryDirectory(
        prefix='kivy_smoke_', ignore_cleanup_errors=True
    ) as tmpdir:
        print(f'Bootstrapping hello world in {tmpdir}...')

        original_dir = os.getcwd()
        os.chdir(tmpdir)
        try:
            scaffold_hello_world()
        finally:
            os.chdir(original_dir)

        if not os.path.exists(os.path.join(tmpdir, 'main.py')):
            print('SMOKE TEST FAILED: bootstrap did not create main.py')
            return 1

        # Patch app.py to print the sentinel and self-stop
        (Path(tmpdir) / 'hello_world' / 'app.py').write_text(
            textwrap.dedent("""\
            from kivy_reloader.app import App
            from hello_world.screens.main_screen import MainScreen

            class HelloWorldApp(App):
                def build(self):
                    return MainScreen()
                def on_start(self):
                    print("HELLO_WORLD_STARTED", flush=True)
                    from kivy.clock import Clock
                    Clock.schedule_once(lambda dt: self.stop(), 1.0)

            def main():
                HelloWorldApp().run()
        """)
        )

        print('Bootstrap OK, running app...')

        env = {
            **os.environ,
            'RELOADER_STATUS': 'PROD',
            'KIVY_SMOKE_TEST': '1',
            'KIVY_NO_ENV_CONFIG': '1',
            'KIVY_LOG_MODE': 'PYTHON',
        }

        proc = subprocess.Popen(
            [sys.executable, 'main.py'],
            cwd=tmpdir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        found = False
        deadline = time.monotonic() + TIMEOUT

        try:
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    break
                line = proc.stdout.readline()
                if line:
                    print(line, end='', flush=True)
                    if TARGET in line:
                        found = True
                        break
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            time.sleep(0.5)  # Windows needs time to release SDL2 file handles

    if found:
        print(f"\nSMOKE TEST PASSED: detected '{TARGET}'")
        return 0

    print(f"\nSMOKE TEST FAILED: '{TARGET}' not found within {TIMEOUT}s")
    return 1


if __name__ == '__main__':
    sys.exit(main())
