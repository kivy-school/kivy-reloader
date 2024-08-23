import os

from kivy.lang import Builder
from kivy.utils import platform

from .config import config

base_dir = os.getcwd()


def load_kv_path(path):
    """
    Loads a kv file from a path
    """
    kv_path = os.path.join(base_dir, path)
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
        return [(os.path.join(base_dir, x), {"recursive": recursive}) for x in paths]

    non_recursive_paths = (
        config.WATCHED_FILES + config.WATCHED_FOLDERS + config.FULL_RELOAD_FILES
    )
    recursive_paths = config.WATCHED_FOLDERS_RECURSIVELY
    if platform == 'win':
        return create_path_tuples(non_recursive_paths, False) + create_path_tuples(
            recursive_paths, True
        )
    else:
        return create_path_tuples(non_recursive_paths, True) + create_path_tuples(
            recursive_paths, True
        )




def find_kv_files_in_folder(folder):
    kv_files = []
    for root, _, files in os.walk(os.path.join(base_dir, folder)):
        for file in files:
            if file.endswith(".kv"):
                kv_files.append(os.path.join(root, file))
    return kv_files


def get_kv_files_paths():
    """
    Given the folders on WATCHED_FOLDERS and WATCHED_FOLDERS_RECURSIVELY,
    returns a list of all the kv files paths
    """
    KV_FILES = []

    for folder in config.WATCHED_FOLDERS:
        for file_name in os.listdir(folder):
            if file_name.endswith(".kv"):
                KV_FILES.append(os.path.join(base_dir, f"{folder}/{file_name}"))

    for folder in config.WATCHED_FOLDERS_RECURSIVELY:
        for file_name in find_kv_files_in_folder(folder):
            KV_FILES.append(file_name)

    # Removing duplicates
    KV_FILES = list(set(KV_FILES))

    return KV_FILES
