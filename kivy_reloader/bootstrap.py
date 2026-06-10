import argparse
import os
import shutil
from pathlib import Path

from colorama import Fore, init
import re

from . import __version__ as _kl_version
from .detection import is_apple_m_series

yellow = Fore.YELLOW
green = Fore.GREEN
red = Fore.RED

init(autoreset=True)

base_dir = os.getcwd()
files_in_base_dir = os.listdir(base_dir)

current_file_path = os.path.abspath(__file__)
current_file_dir = os.path.dirname(current_file_path)


def klprint(string):
    # Kivy Logger
    print(f'{green}[KIVY RELOADER]{Fore.RESET} {string}')


def create_settings_file():
    """
    Creates a copy of kivy-reloader.toml in the project folder
    called kivy-reloader.toml, so the user can change the
    settings.

    If the file already exists, it creates a
    kivy-reloader-template.toml file instead.
    """

    # if 'kivy-reloader.toml' in files_in_base_dir:
    if (Path(base_dir) / 'kivy-reloader.toml').exists():
    # if 'kivy-reloader.toml' in files_in_base_dir:
        klprint(
            'kivy-reloader.toml already exists, creating kivy-reloader-template.toml'
        )
        shutil.copyfile(
            os.path.join(current_file_dir, 'kivy-reloader.toml'),
            os.path.join(base_dir, 'kivy-reloader-template.toml'),
        )
    else:
        klprint(
            'kivy-reloader.toml not found, creating it on current working directory'
        )
        shutil.copyfile(
            os.path.join(current_file_dir, 'kivy-reloader.toml'),
            os.path.join(base_dir, 'kivy-reloader.toml'),
        )


def copy_watchdog_recipe():
    project_root = Path.cwd()
    if not (project_root / "buildozer.spec").exists():
        raise RuntimeError(
            "No buildozer.spec found in current directory. "
            "Run kivy-reloader init from your project root with buildozer.spec ."
        )

    watchdog_dst = Path.cwd() / "p4a-recipes" / "watchdog"

    if watchdog_dst.exists() and any(watchdog_dst.iterdir()):
        klprint(f"Already exists, skipping: {watchdog_dst}")
        return

    watchdog_src = Path(__file__).parent / "p4a-recipes" / "watchdog"

    if not watchdog_src.exists():
        klprint(f"watchdog recipe not found at: {watchdog_src}, skipping.")
        return

    shutil.copytree(watchdog_src, watchdog_dst)
    klprint(f"Copied: {watchdog_src} → {watchdog_dst}")
    klprint("(watchdog empty recipe to fix Mac M-series Android build crash)")


def create_buildozer_spec_file():
    """
    Creates a copy of buildozer.spec in the project folder if it doesn't exist
    If it exists, it creates a buildozer_template.spec file
    """
    if 'buildozer.spec' in files_in_base_dir:
        klprint(
            'buildozer.spec found, creating a copy of '
            'buildozer.spec called buildozer_template.spec'
        )
        if 'buildozer_template.spec' not in files_in_base_dir:
            shutil.copyfile(
                os.path.join(current_file_dir, 'buildozer.spec'),
                os.path.join(base_dir, 'buildozer-template.spec'),
            )
    else:
        klprint('buildozer.spec not found, creating it on current working directory')
        shutil.copyfile(
            os.path.join(current_file_dir, 'buildozer.spec'),
            os.path.join(base_dir, 'buildozer.spec'),
        )

UV_INIT_MAIN_PATTERN = re.compile(
    r'^\s*def main\(\):\s*\n\s*print\("Hello from .+?!"\)\s*\n'
    r'if __name__ == "__main__":\s*\n\s*main\(\)\s*$'
)


def _to_class_name(module_name: str) -> str:
    return ''.join(part.capitalize() for part in module_name.split('_'))


def _detect_ksproject():
    """
    Returns (True, module_name) if pyproject.toml has [tool.kivy-school],
    otherwise (False, None).
    """
    pyproject_path = Path.cwd() / 'pyproject.toml'
    if not pyproject_path.exists():
        return False, None
    try:
        import tomlkit
        with open(pyproject_path, 'r', encoding='utf-8') as f:
            data = tomlkit.load(f)
        ks = data.get('tool', {}).get('kivy-school', {})
        if not ks:
            return False, None
        app_name = ks.get('app_name', '')
        if not app_name:
            return False, None
        module_name = app_name.lower().replace('-', '_').replace(' ', '_')
        return True, module_name
    except Exception:
        return False, None


def _scaffold_hello_world_ksproject(module_name: str):
    """
    Scaffold kivy-reloader hello world into an existing ksproject project.
    Targets src/<module_name>/ instead of hello_world/.
    """
    project_root = Path.cwd()
    src_app_dir = project_root / 'src' / module_name
    class_name = _to_class_name(module_name)

    if not src_app_dir.exists():
        klprint(
            f'{red}ksproject source dir not found: src/{module_name}/\n'
            'Run `ksproject init` first, then `kivy-reloader init project`.'
        )
        return

    screens_dir = src_app_dir / 'screens'
    files = {
        screens_dir / '__init__.py': '',
        screens_dir / 'main_screen.py': '''\
from kivy.uix.screenmanager import Screen
from kivy_reloader.lang import Builder

Builder.load_file(__file__)


class MainScreen(Screen):
    pass
''',
        screens_dir / 'main_screen.kv': '''\
<MainScreen>:
    BoxLayout:
        orientation: 'vertical'
        Button:
            text: 'Welcome to Kivy Reloader!'
''',
    }

    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            klprint(f'Already exists, skipping: {path.relative_to(project_root)}')
        else:
            path.write_text(content)
            klprint(f'Created: {path.relative_to(project_root)}')

    # Rewrite app.py to use kivy_reloader base class
    app_py = src_app_dir / 'app.py'
    app_py_content = f'''\
from kivy_reloader.app import App
from {module_name}.screens.main_screen import MainScreen


class {class_name}App(App):
    def build(self):
        return MainScreen()
'''
    if app_py.exists() and 'from kivy_reloader.app import App' in app_py.read_text():
        klprint(f'Already patched, skipping: src/{module_name}/app.py')
    else:
        app_py.write_text(app_py_content)
        action = 'Patched' if app_py.exists() else 'Created'
        klprint(f'{action}: src/{module_name}/app.py')

    # kivy-reloader.toml with ksproject-aware paths
    toml_path = project_root / 'kivy-reloader.toml'
    toml_content = f'''\
[kivy_reloader]
HOT_RELOAD_ON_PHONE = true
FULL_RELOAD_FILES = ["main.py", "src/{module_name}/app.py"]
WATCHED_FOLDERS_RECURSIVELY = ["."]
STREAM_USING = "WIFI"
'''
    if not toml_path.exists():
        toml_path.write_text(toml_content)
        klprint('Created: kivy-reloader.toml')

    # main.py
    main_py = project_root / 'main.py'
    main_content = f'''\
import trio
from {module_name}.app import {class_name}App

app = {class_name}App()
trio.run(app.async_run, "trio")
'''
    if main_py.exists():
        existing = main_py.read_text()
        if UV_INIT_MAIN_PATTERN.match(existing):
            answer = input(
                f'{yellow}[KIVY RELOADER] Detected uv placeholder main.py. Replace it? [y/n]: {Fore.RESET}'
            )
            if answer.strip().lower() == 'y':
                main_py.write_text(main_content)
                klprint(f'{red}Replaced uv placeholder: main.py')
            else:
                klprint('Skipped main.py')
        elif f'from {module_name}.app import' in existing:
            klprint('main.py already configured, skipping.')
        else:
            klprint(f'{red}⚠️  main.py exists. To use Kivy Reloader, replace its contents with:')
            print(f'{red}{main_content}{Fore.RESET}')
    else:
        main_py.write_text(main_content)
        klprint('Created: main.py')


def scaffold_hello_world():
    """
    Scaffolds a hello-world Kivy Reloader project in the current directory.
 
    Creates:
      main.py
      hello_world/__init__.py  (empty)
      hello_world/app.py
      hello_world/screens/__init__.py  (empty)
      hello_world/screens/main_screen.py
      hello_world/screens/main_screen.kv
      kivy-reloader.toml  (project-specific, overwrites any generic one)
 
    Skips any file that already exists so re-running is safe.
    """
    project_root = Path.cwd()
 
    files = {
        project_root / "hello_world" / "__init__.py": "",
        project_root / "hello_world" / "app.py": """\
from kivy_reloader.app import App
from hello_world.screens.main_screen import MainScreen
 
 
class HelloWorldApp(App):
    def build(self):
        return MainScreen()
""",
        project_root / "hello_world" / "screens" / "__init__.py": "",
        project_root / "hello_world" / "screens" / "main_screen.py": """\
from kivy.uix.screenmanager import Screen
from kivy_reloader.lang import Builder
 
Builder.load_file(__file__)
 
 
class MainScreen(Screen):
    def on_nav(self, target):
        print(f"NAV: {target}", flush=True)

""",
        project_root / "hello_world" / "screens" / "main_screen.kv": """\
<MainScreen>:
    BoxLayout:
        orientation: 'vertical'
        Button:
            text: 'Welcome to Kivy Reloader!'
            on_release: root.on_nav(self.text)

""",
        project_root / "kivy-reloader.toml": """\
[kivy_reloader]
HOT_RELOAD_ON_PHONE = true
FULL_RELOAD_FILES = ["main.py", "hello_world/app.py"]
WATCHED_FOLDERS_RECURSIVELY = ["."]
STREAM_USING = "WIFI"
""",
        project_root / "main.py": """\
import trio
from hello_world.app import HelloWorldApp
app = HelloWorldApp()
trio.run(app.async_run, "trio")
""",
    }


    UV_INIT_MAIN_PATTERN = re.compile(
        r'^\s*def main\(\):\s*\n\s*print\("Hello from .+?!"\)\s*\n'
        r'if __name__ == "__main__":\s*\n\s*main\(\)\s*$'
    )
 
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)

        if path.exists():
            if path.name == "main.py" and UV_INIT_MAIN_PATTERN.match(path.read_text()):
                answer = input(f"{yellow}[KIVY RELOADER] Detected uv placeholder main.py. Replace it? [y/n]: {Fore.RESET}")
                if answer.strip().lower() == 'y':
                    path.write_text(content)
                    klprint(f"{red} Replaced uv placeholder: main.py")
                else:
                    klprint(f"Skipped main.py")
            else:
                klprint(f"Already exists, skipping: {path.relative_to(project_root)}")
                if path.name == "main.py":
                    klprint(f"{red}⚠️ To start using Kivy-Reloader, replace main.py contents with:")
                    print(f"{red}{content}{Fore.RESET}")
        else:
            path.write_text(content)                  
            klprint(f"Created: {path.relative_to(project_root)}")

def main():
    parser = argparse.ArgumentParser(description='Kivy Reloader CLI')
    subparsers = parser.add_subparsers(dest='command')

    init_parser = subparsers.add_parser(  # noqa: F841
        'init',
        help='Create the `kivy-reloader.toml` Create the `kivy-reloader.toml` and `buildozer.spec` config files. Pass `project` to also scaffold a hello-world app in the current directory.', 
    )

    initbare_parser = subparsers.add_parser(  # noqa: F841
        'initbare',
        help='Create the `kivy-reloader.toml` configuration file without adding a watchdog local dummy recipe (so Mac M series chips build for Android properly)',
    )

    run_parser = subparsers.add_parser(  # noqa: F841
        'run',
        help='Initializes Kivy Reloader',
    )
    run_parser.add_argument(
        'action',
        nargs='?',
        choices=['build'],
        help='Run a specific action '
        "(e.g. 'build' for non-interactive build and deploy)",
    )

    start_parser = subparsers.add_parser(  # noqa: F841
        'start',
        help='Initializes Kivy Reloader',
    )
    config_parser = subparsers.add_parser(  # noqa: F841
        'config',
        help='Open the (WIP) visual configurator for kivy-reloader.toml',
    )
    config_parser.add_argument(
        '-f',
        '--file',
        dest='config_file',
        help='Path to a kivy-reloader.toml (or a directory containing one).',
    )
    config_parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable verbose debug output for the configurator.',
    )
    init_parser.add_argument(
        'subcommand',
        nargs='?',
        choices=['project'],
        help="Pass 'project' to scaffold a hello-world app in the current directory.",
    )
    args = parser.parse_args()
    klprint(f'Kivy Reloader v{_kl_version}')

    if args.command == 'init':
        create_buildozer_spec_file()
        # if mac m1 chip: , add p4a watchdog recipe
        if is_apple_m_series():
            copy_watchdog_recipe()
        # scaffold hello-world project if requested
        if getattr(args, 'subcommand', None) == 'project':
            scaffold_hello_world()
        create_settings_file() # hello world project takes precedence over the default settings file

    if args.command == 'initbare':
        # make sure there is an init flag that says 'naked' or smth
        # just in case the mac m1 fix breaks for some reason
        create_settings_file()
        create_buildozer_spec_file()

    elif args.command == 'config':
        from .configurator.gui import run_gui  # noqa

        # Setup paths
        project_dir = Path(os.getcwd())
        config_path = project_dir / 'kivy-reloader.toml'

        # Launch the GUI
        run_gui(base=project_dir, config_path=config_path, debug=False)

    elif args.command in {'start', 'run', 'compile'}:
        from .compile_app import debug_and_livestream  # noqa
        from .compile_app import compile_app, start  # noqa

        if getattr(args, 'action', None) == 'build':
            compile_app()
            debug_and_livestream()
        elif getattr(args, 'action', None) == 'debug':
            debug_and_livestream()
        else:
            start()
