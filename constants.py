# The IP address of your phone; You can hot-reload how many phones you want.
# use "127.0.0.1" if you are using an emulator.
PHONE_IPS = ["192.168.1.65"]


# You can stream using "USB" or "WIFI"
STREAM_USING = "USB"


# The port where the server will be listening
PORT = 5555


# Add the files you want to watch here, i.e., if they change, the app will be reloaded
WATCHED_FILES = ["main.py"]


# Add the folders you want to watch recursively here, i.e., if any file inside them changes, the app will be reloaded
WATCHED_FOLDERS_RECURSIVELY = ["screens"]


# Watched folders but not recursively, i.e., just the files inside the first level of the folder
WATCHED_FOLDERS = []


# Add the folders where you have your .kv files here
KV_FILES_FOLDERS = ["screens"]


# If you want to exclude some files or folders, from being copied to the phone, add them here
FOLDERS_AND_FILES_TO_EXCLUDE_FROM_PHONE = [
    "*.pyc",
    "__pycache__",
    ".buildozer",
    ".venv",
    ".vscode",
    ".git",
    ".pytest_cache",
    ".DS_Store",
    ".env",
    ".dmypy.json",
    ".mypy_cache/",
    ".dmypy.json",
    "dmypy.json",
    "env/",
    "ENV/",
    "env.bak/",
    "venv/",
    "venv.bak/",
    "bin",
    "buildozer.spec",
    "poetry.lock",
    "pyproject.toml",
    "temp",
    "tests",
    "app_copy.zip",
    "send_app_to_phone.py",
    ".gitignore",
    "README.md",
]

assert (
    len(WATCHED_FILES) + len(WATCHED_FOLDERS) + len(WATCHED_FOLDERS_RECURSIVELY) > 0
), "No files or folders to watch"
