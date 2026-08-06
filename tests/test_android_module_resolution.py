import sys
from types import ModuleType

from kivy_reloader.utils import (
    include_dependent_modules,
    module_name_for_file,
)


def test_resolves_project_root_layout(monkeypatch, tmp_path):
    source_file = tmp_path / 'baby_lights' / 'uix' / 'shader.py'
    source_file.parent.mkdir(parents=True)
    source_file.touch()

    module = ModuleType('baby_lights.uix.shader')
    module.__file__ = str(source_file)
    monkeypatch.setitem(sys.modules, 'baby_lights.uix.shader', module)
    monkeypatch.chdir(tmp_path)

    assert (
        module_name_for_file('baby_lights/uix/shader.py', 'baby_lights')
        == 'baby_lights.uix.shader'
    )


def test_resolves_package_root_layout(monkeypatch, tmp_path):
    package_root = tmp_path / 'site-packages' / 'baby_lights'
    source_file = package_root / 'uix' / 'shader.py'
    source_file.parent.mkdir(parents=True)
    source_file.touch()

    module = ModuleType('baby_lights.uix.shader')
    module.__file__ = str(source_file)
    monkeypatch.setitem(sys.modules, 'baby_lights.uix.shader', module)
    monkeypatch.chdir(package_root)

    assert module_name_for_file('uix/shader.py', 'baby_lights') == (
        'baby_lights.uix.shader'
    )


def test_includes_modules_with_from_import_references(monkeypatch):
    changed_module = ModuleType('baby_lights.uix.shader')
    dependent_module = ModuleType('baby_lights.screens.shader_screen')
    unrelated_module = ModuleType('other_package.screen')
    shader_canvas = type(
        'ShaderCanvas',
        (),
        {'__module__': 'baby_lights.uix.shader'},
    )
    dependent_module.ShaderCanvas = shader_canvas
    unrelated_module.ShaderCanvas = shader_canvas

    monkeypatch.setitem(sys.modules, changed_module.__name__, changed_module)
    monkeypatch.setitem(sys.modules, dependent_module.__name__, dependent_module)
    monkeypatch.setitem(sys.modules, unrelated_module.__name__, unrelated_module)

    modules = include_dependent_modules([changed_module], 'baby_lights')

    assert modules == [changed_module, dependent_module]
