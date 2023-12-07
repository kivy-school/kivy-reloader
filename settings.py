# The IP address of your phone; You can hot-reload how many phones you want.
# use "127.0.0.1" if you are using an emulator.
PHONE_IPS = ["192.168.1.65"]


# You can stream using "USB" or "WIFI"
# If your USB cable is connected, use "USB", otherwise use "WIFI"
# To use WIFI, you need connect your phone to the same network as your computer
STREAM_USING = "USB"


# The port where the server will be listening
# It can be any port
PORT = 5555


# Add the python files you want to watch here, i.e., if they change, the app will be reloaded
WATCHED_FILES = ["main.py"]


# Add the folders you want to watch recursively here, i.e., if **ANY FILE** inside them changes, the app will be reloaded
WATCHED_FOLDERS_RECURSIVELY = ["screens"]


# Watched folders but not recursively, i.e., **ANY FILE** inside the first level of the folder
WATCHED_FOLDERS = []

# Add the folders where you have your .kv files here
# If you don't put them here, the .kv files won't be reloaded
# this is recursive, i.e., it will watch all folders inside the folders you put here
WATCHED_KV_FOLDERS_RECURSIVELY = ["screens"]


# Add the folders where you have your .kv files here
# If you don't put them here, the .kv files won't be reloaded
# this is not recursive, i.e., it will only watch the first level of the folders you put here
WATCHED_KV_FOLDERS = []


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