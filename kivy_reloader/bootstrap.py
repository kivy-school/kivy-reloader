import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

from . import __version__ as _kl_version

_enable_inspector = False
if '-m' in sys.argv:
    _m_idx = sys.argv.index('-m')
    if _m_idx + 1 < len(sys.argv) and sys.argv[_m_idx + 1] == 'inspector':
        _enable_inspector = True
        sys.argv.pop(_m_idx + 1)
        sys.argv.pop(_m_idx)

try:
    from colorama import Fore, init
except ModuleNotFoundError:

    class Fore:
        YELLOW = ''
        GREEN = ''
        RED = ''
        RESET = ''

    def init(*args, **kwargs):
        return None


yellow = Fore.YELLOW
green = Fore.GREEN
red = Fore.RED

init(autoreset=True)

base_dir = os.getcwd()
files_in_base_dir = os.listdir(base_dir)

current_file_path = os.path.abspath(__file__)
current_file_dir = os.path.dirname(current_file_path)

_DESKTOP_EXTRA_IMPORTS = {'colorama', 'plyer', 'psutil', 'readchar', 'typer'}
_DESKTOP_EXTRA_HINT = (
    'This command requires the optional desktop dependencies. '
    'Install them with `pip install "kivy-reloader[desktop]"` or '
    '`uv add "kivy-reloader[desktop]"`.'
)


def klprint(string):
    # Kivy Logger
    print(f'{green}[KIVY RELOADER]{Fore.RESET} {string}')


def _raise_missing_desktop_extra(command: str, missing_module: str) -> None:
    raise SystemExit(
        f'`kivy-reloader {command}` requires the optional desktop dependencies. '
        f'Missing dependency: {missing_module}. {_DESKTOP_EXTRA_HINT}'
    )


def _log_command_history(command: str) -> None:
    """Log a CLI command invocation to the project-local history file."""
    history_path = Path(base_dir) / '.kivy-reloader' / 'command_history.json'
    history = []
    if history_path.exists():
        try:
            history = json.loads(history_path.read_text())
        except Exception:
            pass
    history.append({'command': command, 'timestamp': datetime.now().isoformat()})
    history = history[-1000:]
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(json.dumps(history, indent=2))


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
        template_path = Path(base_dir) / 'kivy-reloader-template.toml'
        if template_path.exists():
            klprint('kivy-reloader-template.toml already exists, skipping')
        else:
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

# ── Shared scaffold templates ──────────────────────────────────────────────────

MAIN_SCREEN_PY = """\
from kivy.uix.screenmanager import Screen
from kivy_reloader.lang import Builder

Builder.load_file(__file__)


class MainScreen(Screen):
    def on_nav(self, target):
        print(f"NAV: {target}", flush=True)
"""

MAIN_SCREEN_KV = """\
<MainScreen>:
    BoxLayout:
        orientation: 'vertical'
        Button:
            text: 'Welcome to Kivy Reloader!'
            on_release: root.on_nav(self.text)
"""


def _app_py(module_name: str, class_name: str) -> str:
    return f"""\
from kivy_reloader.app import App
from {module_name}.screens.main_screen import MainScreen


class {class_name}App(App):
    def build(self):
        return MainScreen()

def main():
    {class_name}App().run()
"""


def _main_py(module_name: str, class_name: str) -> str:
    return f"""\
from {module_name}.app import main

if __name__ == "__main__":
    main()
"""


def _toml(full_reload_app_path: str) -> str:
    return f"""\
[kivy_reloader]
HOT_RELOAD_ON_PHONE = true
FULL_RELOAD_FILES = ["main.py", "{full_reload_app_path}/app.py"]
WATCHED_FOLDERS_RECURSIVELY = ["."]
STREAM_USING = "WIFI"
PERSISTENT_FLIGHTDECK = true
"""


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


def _scaffold_hello_world_ksproject(module_name: str):  # noqa:PLR0914
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
        screens_dir / 'main_screen.py': """\
from kivy.uix.boxlayout import BoxLayout
from kivy_reloader.lang import Builder

Builder.load_file(__file__)


class MainScreen(BoxLayout):
    def on_button_click(self):
        self.ids.subtitle_label.text = "Explore the power of Python + KVLang!"
        self.ids.action_btn.text = "Ready to Build!"
""",
        screens_dir / 'main_screen.kv': """\
<MainScreen>:
    orientation: 'vertical'
    padding: dp(24)
    spacing: dp(20)

    # Background Canvas
    canvas.before:
        Color:
            rgba: (0.10, 0.11, 0.13, 1) # Dark Slate Gray
        Rectangle:
            pos: self.pos
            size: self.size

    # Header / Welcome Section
    BoxLayout:
        orientation: 'vertical'
        size_hint_y: 0.3
        spacing: dp(8)

        Label:
            text: "Welcome to Kivy"
            font_size: '28sp'
            bold: True
            color: (1, 1, 1, 1)
            halign: 'center'
            valign: 'middle'

        Label:
            id: subtitle_label
            text: "Your journey into cross-platform UI begins here."
            font_size: '14sp'
            color: (0.7, 0.7, 0.7, 1)
            halign: 'center'
            text_size: self.width, None

    # Feature Card (Visual Centerpiece)
    BoxLayout:
        orientation: 'vertical'
        size_hint_y: 0.4
        padding: dp(16)
        spacing: dp(12)
        canvas.before:
            Color:
                rgba: (0.16, 0.18, 0.21, 1) # Lighter card background
            RoundedRectangle:
                pos: self.pos
                size: self.size
                radius: [12]

        Label:
            text: "Why Kivy?"
            font_size: '18sp'
            bold: True
            color: (0.29, 0.69, 0.31, 1) # Fresh Green Accent
            size_hint_y: None
            height: self.texture_size[1]
            halign: 'left'
            text_size: self.width, None

        Label:
            text: "• Fast & GPU Accelerated\\n• Same code for Android, iOS, Windows, & Mac\\n• Declarative UI with KVLang\\n• Open Source & Flexible"
            font_size: '14sp'
            color: (0.85, 0.85, 0.85, 1)
            line_height: 1.3
            valign: 'top'
            text_size: self.width, self.height

    # Action Section (Button)
    BoxLayout:
        size_hint_y: 0.3
        gravity: 'center'
        padding: [0, dp(40), 0, 0]
        Button:
            id: action_btn
            text: "Get Started"
            font_size: '16sp'
            bold: True
            size_hint: (1, None)
            height: dp(50)
            background_color: (0, 0, 0, 0) # Remove default background to style with canvas
            color: (1, 1, 1, 1)
            on_press: root.on_button_click()
            canvas.before:
                Color:
                    rgba: (0.29, 0.69, 0.31, 1) if self.state == 'normal' else (0.22, 0.53, 0.24, 1)
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [25] # Perfect pill-shaped button
""",
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
    app_py_content = f"""\
from kivy_reloader.app import App
from {module_name}.screens.main_screen import MainScreen


class {class_name}App(App):
    def build(self):
        return MainScreen()


def main():
    import trio
    {class_name}App().run()
"""

    if app_py.exists() and 'from kivy_reloader.app import App' in app_py.read_text():
        klprint(f'Already patched, skipping: src/{module_name}/app.py')
    else:
        app_py.write_text(app_py_content)
        action = 'Patched' if app_py.exists() else 'Created'
        klprint(f'{action}: src/{module_name}/app.py')

    # Fix __init__.py — ksproject default calls `from .app import main` which doesn't exist
    init_py = src_app_dir / '__init__.py'
    init_content = """\
def main(*args) -> None:
    from .app import main
    main()
"""

    if not init_py.exists() or init_py.read_text() != init_content:
        init_py.write_text(init_content)
        klprint(f'Updated: src/{module_name}/__init__.py')
    else:
        klprint(f'Already correct, skipping: src/{module_name}/__init__.py')

    # Fix __main__.py entry point
    main_module_py = src_app_dir / '__main__.py'
    main_module_content = """\
from .app import main

if __name__ == "__main__":
    main()
"""

    if not main_module_py.exists() or main_module_py.read_text() != main_module_content:
        main_module_py.write_text(main_module_content)
        klprint(f'Updated: src/{module_name}/__main__.py')
    else:
        klprint(f'Already correct, skipping: src/{module_name}/__main__.py')

    # Remove stale app.kv generated by ksproject init (belongs to the old app.py we just replaced)
    app_kv = src_app_dir / 'app.kv'
    if app_kv.exists():
        app_kv.unlink()
        klprint(f'Removed stale: src/{module_name}/app.kv')

    # kivy-reloader.toml with ksproject-aware paths at project root (next to pyproject.toml)
    # WATCHED_FOLDERS_RECURSIVELY points at the src package so delta zip paths
    # are relative to src/{module_name}/ — Android extracts them correctly into
    # site-packages/{module_name}/ without a stray src/{module_name}/ prefix.
    toml_path = project_root / 'kivy-reloader.toml'
    toml_content = f"""\
[kivy_reloader]
HOT_RELOAD_ON_PHONE = true
FULL_RELOAD_FILES = ["src/{module_name}/app.py"]
WATCHED_FOLDERS_RECURSIVELY = ["src/{module_name}"]
STREAM_USING = "WIFI"
"""
    if not toml_path.exists():
        toml_path.write_text(toml_content)
        klprint('Created: kivy-reloader.toml')
    else:
        klprint('Already exists, skipping: kivy-reloader.toml')
    # main.py
    main_py = project_root / 'main.py'
    main_content = f"""\
from {module_name}.app import main

main()
"""

    if main_py.exists():
        existing = main_py.read_text()
        if UV_INIT_MAIN_PATTERN.match(existing):
            if sys.stdin.isatty():
                answer = input(
                    f'{yellow}[KIVY RELOADER] Detected uv placeholder main.py. Replace it? [y/n]: {Fore.RESET}'
                )
            else:
                answer = 'y'
            if answer.strip().lower() == 'y':
                main_py.write_text(main_content)
                klprint(f'{red}Replaced uv placeholder: main.py')
            else:
                klprint('Skipped main.py')
        elif f'from {module_name}.app import' in existing:
            klprint('main.py already configured, skipping.')
        else:
            klprint(
                f'{red}⚠️  main.py exists. To use Kivy Reloader, replace its contents with:'
            )
            print(f'{red}{main_content}{Fore.RESET}')
    else:
        main_py.write_text(main_content)
        klprint('Created: main.py')


def scaffold_hello_world():
    """
    Scaffolds a hello-world Kivy Reloader project in the current directory.
    If a ksproject pyproject.toml is detected, scaffolds into src/<module>/ instead.
    Skips any file that already exists so re-running is safe.
    """
    is_ksp, module_name = _detect_ksproject()
    if is_ksp:
        klprint(
            f'ksproject detected (module: {module_name}) — scaffolding into src/{module_name}/'
        )
        _scaffold_hello_world_ksproject(module_name)
        return

    project_root = Path.cwd()
    files = {
        project_root / 'hello_world' / '__init__.py': '',
        project_root / 'hello_world' / 'app.py': _app_py('hello_world', 'HelloWorld'),
        project_root / 'hello_world' / 'screens' / '__init__.py': '',
        project_root / 'hello_world' / 'screens' / 'main_screen.py': MAIN_SCREEN_PY,
        project_root / 'hello_world' / 'screens' / 'main_screen.kv': MAIN_SCREEN_KV,
        project_root / 'kivy-reloader.toml': _toml('hello_world'),
        project_root / 'main.py': _main_py('hello_world', 'HelloWorld'),
    }

    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.name == 'main.py' and UV_INIT_MAIN_PATTERN.match(path.read_text()):
                if sys.stdin.isatty():
                    answer = input(
                        f'{yellow}[KIVY RELOADER] Detected uv placeholder main.py. Replace it? [y/n]: {Fore.RESET}'
                    )
                else:
                    answer = 'y'
                if answer.strip().lower() == 'y':
                    path.write_text(content)
                    klprint(f'{red} Replaced uv placeholder: main.py')
                else:
                    klprint('Skipped main.py')
            else:
                klprint(f'Already exists, skipping: {path.relative_to(project_root)}')
                if path.name == 'main.py':
                    klprint(
                        f'{red}⚠️ To start using Kivy-Reloader, replace main.py contents with:'
                    )
                    print(f'{red}{content}{Fore.RESET}')
        else:
            path.write_text(content)
            klprint(f'Created: {path.relative_to(project_root)}')


def smoke():
    """Bootstrap a fresh hello world in a temp dir, run headlessly, verify it starts."""
    import subprocess
    import tempfile
    import time
    from pathlib import Path

    TARGET = 'HELLO_WORLD_STARTED'
    TIMEOUT = 30

    SMOKE_APP_PY = (
        _app_py('hello_world', 'HelloWorld')
        + """\

    def on_start(self):
        print("HELLO_WORLD_STARTED", flush=True)
        from kivy.clock import Clock
        Clock.schedule_once(lambda dt: self.stop(), 1.0)
"""
    )

    with tempfile.TemporaryDirectory(prefix='kivy_smoke_') as tmpdir:
        klprint(f'Bootstrapping hello world in {tmpdir}...')
        original_dir = os.getcwd()
        os.chdir(tmpdir)
        try:
            scaffold_hello_world()
        finally:
            os.chdir(original_dir)

        (Path(tmpdir) / 'hello_world' / 'app.py').write_text(SMOKE_APP_PY)

        if not (Path(tmpdir) / 'main.py').exists():
            klprint(f'{red}SMOKE FAILED: bootstrap did not create main.py')
            return 1

        klprint('Bootstrap OK, running app headlessly...')
        env = {
            **os.environ,
            'RELOADER_STATUS': 'PROD',
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

    if found:
        klprint(f'{green}SMOKE TEST PASSED')
        return 0
    klprint(f"{red}SMOKE TEST FAILED: '{TARGET}' not found within {TIMEOUT}s")
    return 1


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

    smoke_parser = subparsers.add_parser(  # noqa: F841
        'smoke',
        help='Bootstrap a fresh hello world in a temp dir and run a headless smoke test.',
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
        is_ksp, _ = _detect_ksproject()
        if not is_ksp:
            create_buildozer_spec_file()
        if getattr(args, 'subcommand', None) == 'project':
            scaffold_hello_world()
        create_settings_file()  # hello world project takes precedence over the default settings file

    if args.command == 'initbare':
        # make sure there is an init flag that says 'naked' or smth
        # just in case the mac m1 fix breaks for some reason
        create_settings_file()
        create_buildozer_spec_file()

    elif args.command == 'config':
        if _enable_inspector:
            sys.argv = [sys.argv[0], '-m', 'inspector']
        from .configurator.gui import run_gui  # noqa

        # Setup paths
        project_dir = Path(os.getcwd())
        config_path = project_dir / 'kivy-reloader.toml'

        # Launch the GUI
        run_gui(base=project_dir, config_path=config_path, debug=False)

    elif args.command in {'start', 'run', 'compile'}:
        try:
            from .compile_app import debug_and_livestream  # noqa
            from .compile_app import compile_app, start  # noqa
        except ModuleNotFoundError as exc:
            if exc.name not in _DESKTOP_EXTRA_IMPORTS:
                raise
            _raise_missing_desktop_extra(args.command, exc.name)

        if getattr(args, 'action', None) == 'build':
            from threading import Event

            from .compile_app import compile_app, debug_and_livestream

            buildozer_compiled = Event()
            compile_app(buildozer_compiled)
            debug_and_livestream(buildozer_compiled)

        elif getattr(args, 'action', None) == 'debug':
            from .compile_app import debug_and_livestream

            debug_and_livestream()
        else:
            from .launcher import _should_launch_flightdeck

            if _should_launch_flightdeck():
                from .configurator.gui import run_gui

                project_dir = Path(os.getcwd())
                config_path = project_dir / 'kivy-reloader.toml'
                run_gui(base=project_dir, config_path=config_path)
            else:
                from .compile_app import start

                start()

    elif args.command == 'smoke':
        sys.exit(smoke())
