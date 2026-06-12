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
        return
    
    # Resolve to canonical path — avoids symlink/relative mismatches on Android
    kv_path = str(pathlib.Path(kv_path).resolve())    

    logging.info(f'[load_kv_path] kv_path={kv_path}')
    logging.info(f'[load_kv_path] Builder.files={Builder.files}')
    logging.info(f'[load_kv_path] already_loaded={kv_path in Builder.files}')


    # First try exact match
    unloaded = False
    for existing in list(Builder.files):
        if str(pathlib.Path(existing).resolve()) == kv_path:
            logging.info(f'[load_kv_path] UNLOADING (exact): {existing}')
            Builder.unload_file(existing)
            unloaded = True
            break

    # If no exact match, the KV may have been loaded from a different root
    # (e.g. site-packages on Android while hot reload delivers to CWD).
    # Use sys.modules to find the module that owns this KV and unload its copy.
    if not unloaded:
        try:
            base_resolved = str(pathlib.Path(base_dir).resolve())
            rel_kv = str(pathlib.Path(kv_path).relative_to(base_resolved))
            # 'hello_world/screens/main_screen.kv' -> 'hello_world.screens.main_screen'
            kv_module_suffix = rel_kv.replace(os.sep, '.')[:-3]  # strip .kv
        except ValueError:
            kv_module_suffix = None

        if kv_module_suffix:
            for mod_name, mod in list(sys.modules.items()):
                if mod_name == kv_module_suffix or mod_name.endswith('.' + kv_module_suffix):
                    mod_file = getattr(mod, '__file__', None) or ''
                    mod_kv = mod_file.replace('.pyc', '.kv').replace('.py', '.kv')
                    if mod_kv in Builder.files:
                        logging.info(f'[load_kv_path] UNLOADING (module {mod_name}): {mod_kv}')
                        Builder.unload_file(mod_kv)
                        break

    if kv_path not in Builder.files:
        filename = resource_find(path) or path

        kwargs['filename'] = kv_path  # store resolved path, not resource_find result
        with open(filename, 'r', encoding=encoding) as fd:
            data = fd.read()
            return Builder.load_string(data, **kwargs)


Builder.load_file = load_kv_path
