import argparse
import os
import shutil
from pathlib import Path
from .detection import is_apple_m_series

from colorama import Fore, init


import importlib.util

from . import __version__ as _kl_version

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

    if 'kivy-reloader.toml' in files_in_base_dir:
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
    klprint(f"(watchdog empty recipe to fixe Mac M-series Android build crash)")

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


def main():
    parser = argparse.ArgumentParser(description='Kivy Reloader CLI')
    subparsers = parser.add_subparsers(dest='command')

    init_parser = subparsers.add_parser(  # noqa: F841
        'init',
        help='Create the `kivy-reloader.toml` configuration file.',
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
    args = parser.parse_args()
    klprint(f'Kivy Reloader v{_kl_version}')

    if args.command == 'init':
        create_settings_file()
        create_buildozer_spec_file()
        #if mac m1 chip: , add p4a watchdog recipe
        if is_apple_m_series():
            copy_watchdog_recipe()

    if args.command == 'initbare':
        #make sure there is an init flag that says 'naked' or smth
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
