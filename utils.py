import os

from kivy.lang import Builder

from constants import (
    WATCHED_FILES,
    WATCHED_FOLDERS,
    WATCHED_FOLDERS_RECURSIVELY,
    WATCHED_KV_FOLDERS,
    WATCHED_KV_FOLDERS_RECURSIVELY,
)


def load_kv_path(path):
    """
    Loads a kv file from a path
    """
    kv_path = os.path.join(os.getcwd(), path)
    if kv_path in Builder.files:
        Builder.unload_file(kv_path)

    if kv_path not in Builder.files:
        Builder.load_file(kv_path)


def get_auto_reloader_paths():
    """
    Returns a list of paths to watch for changes,
    based on the constants.py file
    """
    return (
        [(os.path.join(os.getcwd(), x), {"recursive": False}) for x in WATCHED_FILES]
        + [
            (os.path.join(os.getcwd(), x), {"recursive": True})
            for x in WATCHED_FOLDERS_RECURSIVELY
        ]
        + [
            (os.path.join(os.getcwd(), x), {"recursive": False})
            for x in WATCHED_FOLDERS
        ]
    )


def find_kv_files_in_folder(folder):
    kv_files = []
    for root, _, files in os.walk(os.path.join(os.getcwd(), folder)):
        for file in files:
            if file.endswith(".kv"):
                kv_files.append(os.path.join(root, file))
    return kv_files


def get_kv_files_paths():
    """
    Given the folders on WATCHED_KV_FOLDERS and WATCHED_KV_FOLDERS_RECURSIVELY,
    returns a list of all the kv files paths
    """
    KV_FILES = []

    for folder in WATCHED_KV_FOLDERS:
        for kv_file in os.listdir(folder):
            if kv_file.endswith(".kv"):
                KV_FILES.append(os.path.join(os.getcwd(), f"{folder}/{kv_file}"))

    for folder in WATCHED_KV_FOLDERS_RECURSIVELY:
        for kv_file in find_kv_files_in_folder(folder):
            KV_FILES.append(kv_file)

    # Removing duplicates
    KV_FILES = list(set(KV_FILES))

    return KV_FILES
