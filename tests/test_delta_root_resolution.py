import sys
from types import ModuleType

from kivy_reloader.utils import resolve_delta_root


def test_flat_buildozer_layout_resolves_to_project_root(monkeypatch, tmp_path):
    """main.py at the project root: entry point dir == project root == cwd."""
    main_file = tmp_path / 'main.py'
    main_file.touch()

    main_mod = ModuleType('__main__')
    main_mod.__file__ = str(main_file)
    monkeypatch.setitem(sys.modules, '__main__', main_mod)
    monkeypatch.chdir(tmp_path)

    assert resolve_delta_root(['.'], str(tmp_path)) == str(tmp_path.resolve())


def test_ksproject_src_layout_resolves_to_package_directory(monkeypatch, tmp_path):
    """`python -m hello_world_reloader`: entry point lives under src/<package>,
    so the delta root must be the package directory, not the project root."""
    project_root = tmp_path
    package_dir = project_root / 'src' / 'hello_world_reloader'
    package_dir.mkdir(parents=True)
    main_file = package_dir / '__main__.py'
    main_file.touch()

    main_mod = ModuleType('hello_world_reloader.__main__')
    main_mod.__file__ = str(main_file)
    monkeypatch.setitem(sys.modules, '__main__', main_mod)
    monkeypatch.chdir(project_root)

    assert resolve_delta_root(['.'], str(project_root)) == str(package_dir.resolve())


def test_explicit_watched_folder_is_used_as_is(monkeypatch, tmp_path):
    """An explicit WATCHED_FOLDERS_RECURSIVELY entry always wins, regardless
    of any entry-point detection."""
    watched_dir = tmp_path / 'app_src'
    watched_dir.mkdir()

    # Even with a __main__ pointing elsewhere, the explicit folder is used.
    other_file = tmp_path / 'other' / '__main__.py'
    other_file.parent.mkdir()
    other_file.touch()
    main_mod = ModuleType('__main__')
    main_mod.__file__ = str(other_file)
    monkeypatch.setitem(sys.modules, '__main__', main_mod)

    assert resolve_delta_root(['app_src'], str(tmp_path)) == str(watched_dir.resolve())


def test_non_src_explicit_watch_does_not_descend_to_source_package(tmp_path):
    watched_dir = tmp_path / 'app_src'
    (watched_dir / 'demo_app').mkdir(parents=True)

    resolved = resolve_delta_root(
        ['app_src'],
        str(tmp_path),
        source_package='demo_app',
    )

    assert resolved == str(watched_dir.resolve())


def test_ksproject_src_watch_descends_to_source_package(monkeypatch, tmp_path):
    """A ksproject desktop run starts at project/main.py and watches ``src``.

    Android extracts into the package directory, so transfer paths must be
    relative to ``src/<package>`` rather than carrying the package prefix and
    creating ``<package>/<package>/app.kv`` on the device.
    """
    (tmp_path / 'main.py').touch()
    package_dir = tmp_path / 'src' / 'hello_world_reloader'
    package_dir.mkdir(parents=True)
    (package_dir / '__main__.py').touch()
    (package_dir / 'app.kv').write_text('<IntroScreen>:\n')

    main_mod = ModuleType('__main__')
    main_mod.__file__ = str(tmp_path / 'main.py')
    monkeypatch.setitem(sys.modules, '__main__', main_mod)
    monkeypatch.chdir(tmp_path)

    resolved = resolve_delta_root(
        ['src'],
        str(tmp_path),
        source_package='hello_world_reloader',
    )

    assert resolved == str(package_dir.resolve())


def test_defaults_to_dot_when_watched_folders_empty(monkeypatch, tmp_path):
    monkeypatch.delitem(sys.modules, '__main__', raising=False)

    assert resolve_delta_root([], str(tmp_path)) == str(tmp_path)


def test_falls_back_to_cwd_when_main_has_no_file(monkeypatch, tmp_path):
    """Interactive sessions / frozen entry points without __file__ must not crash."""
    main_mod = ModuleType('__main__')
    monkeypatch.setitem(sys.modules, '__main__', main_mod)

    assert resolve_delta_root(['.'], str(tmp_path)) == str(tmp_path)


def test_falls_back_to_cwd_when_entry_dir_missing(monkeypatch, tmp_path):
    """If the resolved entry-point directory no longer exists on disk, fall
    back to cwd instead of pointing the archive at a non-existent path."""
    missing_file = tmp_path / 'deleted_pkg' / '__main__.py'
    main_mod = ModuleType('some_pkg.__main__')
    main_mod.__file__ = str(missing_file)
    monkeypatch.setitem(sys.modules, '__main__', main_mod)

    assert resolve_delta_root(['.'], str(tmp_path)) == str(tmp_path)
