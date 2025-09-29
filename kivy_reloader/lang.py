import logging
import os
import pathlib
import sys

from kivy.lang import Builder
from kivy.resources import resource_add_path, resource_find

base_dir = os.getcwd()


def load_kv_path(path: str, encoding='utf8', **kwargs):
    """
    Load a .kv file safely for hot reloading (prevents duplicate loading warnings).

    This is a simple wrapper around Kivy's Builder.load_file() that:
    1. Unloads the file first if it was already loaded
    2. Then loads it fresh

    This prevents Kivy from showing "file loaded twice" warnings during hot reload.

    Args:
        path: Path to the .kv file to load. Can be:
            - Direct .kv file path: 'my_widget.kv'
            - Python file path: 'my_widget.py' (auto-converts to 'my_widget.kv')
            - Compiled file path: 'my_widget.pyc' (auto-converts to 'my_widget.kv')

    Common Usage:
        Most developers place .kv files alongside .py files with the same name.
        Instead of manually constructing paths, you can use `__file__`:

        project/
        ├── widgets/
        │   ├── my_button.py    ← load_kv_path(__file__)
        │   └── my_button.kv    ← Gets loaded automatically

        load_kv_path('my_widget.kv')    # Direct path
        load_kv_path(__file__)          # Same-named .kv file (common pattern)
    """
    if path.endswith('.pyc'):
        path = path.replace('.pyc', '.kv')
    elif path.endswith('.py'):
        path = path.replace('.py', '.kv')

    if hasattr(sys, '_MEIPASS'):
        resource_add_path(sys._MEIPASS)
        test_path = pathlib.Path(path)
        try:
            # look with extra root path appended to sys._MEIP0ASS
            if str(test_path.parent) != '.':
                meipass_path = pathlib.Path(sys._MEIPASS) / test_path.parent
            resource_add_path(meipass_path)
            logging.info(f'resource_find {meipass_path}, {test_path.name}')
            kv_path = resource_find(test_path.name)
        except Exception:
            # last resort: do a naive search with resource find
            kv_path = resource_find(path)
            logging.info(
                f'kv path might be a duplicate, please double check {path}, {kv_path}'
            )

    else:
        kv_path = os.path.join(base_dir, path)
    if kv_path is None:
        logging.error(f'failed to load kv path: {path}')
    if kv_path in Builder.files:
        Builder.unload_file(kv_path)

    if kv_path not in Builder.files:
        filename = resource_find(path) or path

        kwargs['filename'] = filename
        with open(filename, 'r', encoding=encoding) as fd:
            data = fd.read()
            return Builder.load_string(data, **kwargs)


Builder.load_file = load_kv_path
