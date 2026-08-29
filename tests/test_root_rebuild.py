#!/usr/bin/env python3
"""
Regression test: hot reload must keep exactly one root widget on the Window.

Verifies that build_root_and_add_to_window()/delayed_build() (shared by the
Android and desktop code paths):
- leave Window with exactly one application root after a reload
- detach the old root and attach the new root exactly once
- do not accumulate duplicate roots across repeated reloads
- do not stack duplicate builds when reloads happen faster than a frame
- preserve unrelated Window children (overlays, popups)
- behave identically on the Android and desktop platform branches

Run via: xvfb-run -a uv run python tests/test_root_rebuild.py
(Linux) or: uv run python tests/test_root_rebuild.py (macOS/Windows)
"""

import os
import sys

os.environ.setdefault('KIVY_NO_ENV_CONFIG', '1')
os.environ.setdefault('KIVY_LOG_MODE', 'PYTHON')

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label

from kivy_reloader import base_app
from kivy_reloader.base_app import BaseReloaderApp

PLATFORMS = ['android', 'linux']  # desktop paths: win / linux / macosx


class ReloadableApp(BaseReloaderApp):
    """Minimal app reusing the production build/attach logic."""

    build_count = 0

    def __init__(self):
        self.root = None

    def build(self):
        ReloadableApp.build_count += 1
        box = BoxLayout()
        box.add_widget(Label(text=f'build {ReloadableApp.build_count}'))
        return box


def flush_clock():
    """Deliver every scheduled Clock event, as one or more frames would."""
    for _ in range(10):
        Clock._process_events()


def clear_window():
    while Window.children:
        Window.remove_widget(Window.children[0])


def fresh_started_app():
    """Simulate initial startup: App._run_prepare() attaches build() result."""
    clear_window()
    app = ReloadableApp()
    app.root = app.build()
    Window.add_widget(app.root)
    assert len(Window.children) == 1
    return app


def check_single_root(platform):
    app = fresh_started_app()
    old_root = app.root

    app.build_root_and_add_to_window()
    flush_clock()

    assert len(Window.children) == 1, Window.children
    assert old_root not in Window.children, 'old root still attached to Window'
    assert Window.children.count(app.root) == 1
    assert app.root is not old_root
    print(f'  [{platform}] exactly one root, old root detached: OK')


def check_repeated_reloads_do_not_accumulate(platform):
    app = fresh_started_app()

    for i in range(5):
        app.build_root_and_add_to_window()
        flush_clock()
        assert len(Window.children) == 1, (
            f'reload {i + 1}: {len(Window.children)} window children'
        )
        assert Window.children.count(app.root) == 1

    print(f'  [{platform}] 5 repeated reloads: no duplicate roots: OK')


def check_rapid_reloads_do_not_stack_builds(platform):
    app = fresh_started_app()
    builds_before = ReloadableApp.build_count

    # Two reloads within the same frame must result in a single rebuild.
    app.build_root_and_add_to_window()
    app.build_root_and_add_to_window()
    flush_clock()

    assert ReloadableApp.build_count == builds_before + 1, (
        f'expected 1 build, got {ReloadableApp.build_count - builds_before}'
    )
    assert len(Window.children) == 1, Window.children
    print(f'  [{platform}] back-to-back reloads schedule a single build: OK')


def check_unrelated_window_children_survive(platform):
    app = fresh_started_app()
    overlay = BoxLayout()
    Window.add_widget(overlay)
    assert len(Window.children) == 2

    app.build_root_and_add_to_window()
    flush_clock()

    assert overlay in Window.children, 'unrelated overlay was removed'
    assert len(Window.children) == 2, Window.children
    assert Window.children.count(app.root) == 1
    print(f'  [{platform}] unrelated Window children preserved: OK')


def check_reload_when_root_not_on_window(platform):
    # If the root was already detached (e.g. error screen replaced it),
    # reload must re-attach the new root instead of duplicating or crashing.
    app = fresh_started_app()
    Window.remove_widget(app.root)
    assert not Window.children

    app.build_root_and_add_to_window()
    flush_clock()

    assert len(Window.children) == 1, Window.children
    assert Window.children[0] is app.root
    print(f'  [{platform}] reload with detached root re-attaches cleanly: OK')


def main():
    failures = 0
    for platform in PLATFORMS:
        base_app.platform = platform
        print(f'Platform branch: {platform}')
        for check in (
            check_single_root,
            check_repeated_reloads_do_not_accumulate,
            check_rapid_reloads_do_not_stack_builds,
            check_unrelated_window_children_survive,
            check_reload_when_root_not_on_window,
        ):
            try:
                check(platform)
            except AssertionError as e:
                failures += 1
                print(f'  [{platform}] FAILED: {e}')

    if failures:
        print(f'\nROOT REBUILD TEST FAILED: {failures} check(s) failed')
        return 1

    print('\nROOT REBUILD TEST PASSED')
    return 0


if __name__ == '__main__':
    sys.exit(main())
