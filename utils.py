import os

from kivy.lang import Builder


def load_kv_path(path):
    """
    Loads a kv file from a path
    """
    kv_path = os.path.join(os.getcwd(), path)
    if kv_path not in Builder.files:
        Builder.load_file(kv_path)
