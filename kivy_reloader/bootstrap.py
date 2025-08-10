import argparse
import os
import shutil

from colorama import Fore, init

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

    elif args.command == 'config':
        from .configurator import launch_configurator  # noqa

        launch_configurator(
            config_file=getattr(args, 'config_file', None),
            debug=getattr(args, 'debug', False),
        )

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
