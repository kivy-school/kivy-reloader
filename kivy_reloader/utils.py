import logging
import os
import pathlib
import subprocess
import sys
from fnmatch import fnmatch

from kivy.lang import Builder
from kivy.resources import resource_add_path, resource_find
from kivy.utils import platform

from .config import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
base_dir = os.getcwd()


def load_kv_path(path):
    """
    Loads a kv file from a path
    """
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
        Builder.load_file(kv_path)


def get_auto_reloader_paths():
    """
    Returns a list of paths to watch for changes,
    based on the config.py file
    """

    def create_path_tuples(paths, recursive):
        return [(os.path.join(base_dir, x), {'recursive': recursive}) for x in paths]

    def should_exclude_directory(dir_path):
        """Check if a directory should be excluded based on DO_NOT_WATCH_PATTERNS"""
        dir_name = os.path.basename(dir_path)

        for pattern in config.DO_NOT_WATCH_PATTERNS:
            if pattern.startswith('*') and pattern.endswith('*'):
                substring = pattern.strip('*')
                if substring in dir_path or substring in dir_name:
                    return True
            elif fnmatch(dir_path, pattern):
                return True
            elif fnmatch(dir_name, pattern):
                return True

        return False

    def expand_current_directory():
        """
        Instead of watching '.' recursively, enumerate subdirectories
        and exclude unwanted ones
        """
        directories_to_watch = []

        # Get all subdirectories in the current directory
        try:
            for item in os.listdir(base_dir):
                item_path = os.path.join(base_dir, item)
                if os.path.isdir(item_path):
                    # Check if this directory should be excluded
                    if not should_exclude_directory(item_path):
                        directories_to_watch.append((item_path, {'recursive': True}))
        except OSError:
            # Fallback to watching current directory
            directories_to_watch.append((base_dir, {'recursive': True}))

        return directories_to_watch

    non_recursive_paths = (
        config.WATCHED_FILES + config.WATCHED_FOLDERS + config.FULL_RELOAD_FILES
    )
    recursive_paths = config.WATCHED_FOLDERS_RECURSIVELY

    # Check if user wants to watch current directory recursively
    if '.' in recursive_paths:
        # Remove '.' from the list and expand it to individual directories
        other_recursive_paths = [p for p in recursive_paths if p != '.']
        expanded_directories = expand_current_directory()
        other_recursive_tuples = create_path_tuples(other_recursive_paths, True)
        recursive_tuples = expanded_directories + other_recursive_tuples

        # IMPORTANT: Remove "." from non_recursive_paths to avoid duplicate watchers
        # when using smart directory expansion
        non_recursive_paths = [p for p in non_recursive_paths if p != '.']
    else:
        recursive_tuples = create_path_tuples(recursive_paths, True)

    if platform == 'win':
        return create_path_tuples(non_recursive_paths, False) + recursive_tuples
    else:
        return create_path_tuples(non_recursive_paths, True) + recursive_tuples


def find_kv_files_in_folder(folder):
    kv_files = []
    for root, _, files in os.walk(os.path.join(base_dir, folder)):
        # Check if the directory path should be excluded
        should_exclude_dir = False
        for pattern in config.DO_NOT_WATCH_PATTERNS:
            if fnmatch(root, f'*{pattern.replace("*", "")}*'):
                should_exclude_dir = True
                break

        if should_exclude_dir:
            continue

        for file in files:
            if file.endswith('.kv'):
                full_path = os.path.join(root, file)

                # Check if the file path should be excluded
                should_exclude_file = False
                for pattern in config.DO_NOT_WATCH_PATTERNS:
                    if fnmatch(full_path, f'*{pattern.replace("*", "")}*'):
                        should_exclude_file = True
                        break

                if not should_exclude_file:
                    kv_files.append(full_path)
    return kv_files


def get_kv_files_paths():
    """
    Given the folders on WATCHED_FOLDERS and WATCHED_FOLDERS_RECURSIVELY,
    returns a list of all the kv files paths
    """
    KV_FILES = []

    for folder in config.WATCHED_FOLDERS:
        for file_name in os.listdir(folder):
            if file_name.endswith('.kv'):
                KV_FILES.append(os.path.join(base_dir, f'{folder}/{file_name}'))

    for folder in config.WATCHED_FOLDERS_RECURSIVELY:
        for file_name in find_kv_files_in_folder(folder):
            KV_FILES.append(file_name)

    # Removing duplicates
    KV_FILES = list(set(KV_FILES))

    return KV_FILES


def get_connected_devices() -> list[dict[str, str]]:
    """
    Returns a list of connected devices with metadata:
    - serial: device serial (USB or IP)
    - transport: usb or tcpip
    - model: device model name if available
    - wifi_ip: IP address of wlan0 (if available)
    """
    result = subprocess.run(
        ['adb', 'devices', '-l'], capture_output=True, text=True, check=True
    )
    lines = result.stdout.strip().splitlines()[1:]  # Skip header
    devices = []
    for line in lines:
        if not line.strip() or 'device' not in line:
            continue
        parts = line.strip().split()
        serial = parts[0]
        transport = 'tcpip' if ':' in serial else 'usb'
        model = next(
            (p.split(':')[1] for p in parts if p.startswith('model:')),
            'unknown',
        )

        logging.info(
            f'Detected device: serial={serial}, transport={transport}, model={model}'
        )
        wifi_ip = get_wifi_ip(serial)

        devices.append({
            'serial': serial,
            'transport': transport,
            'model': model,
            'wifi_ip': wifi_ip,
        })
    logging.info(f'Total serials connected: {len(devices)}')
    unique_physical = {
        (d['wifi_ip'], d['model']) for d in devices if d['wifi_ip'] is not None
    }
    logging.info(f'Total physical devices connected: {len(unique_physical)}')
    return devices


def get_wifi_ip(serial: str) -> str | None:
    logging.debug(f'Querying Wi-Fi IP for serial: {serial}')
    try:
        result = subprocess.run(
            [
                'adb',
                '-s',
                serial,
                'shell',
                'ip',
                '-f',
                'inet',
                'addr',
                'show',
                'wlan0',
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        for line in result.stdout.splitlines():
            stripped_line = line.strip()
            if stripped_line.startswith('inet '):
                ip = stripped_line.split()[1].split('/')[0]
                logging.debug(f'Found Wi-Fi IP {ip} for serial: {serial}')
                return ip
    except subprocess.CalledProcessError as e:
        logging.warning(f'Failed to query Wi-Fi IP for {serial}: {e}')
    return None
