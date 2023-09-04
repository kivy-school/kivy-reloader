PHONE_IPS = ["192.168.100.200"]  # The IP address of your phone
STREAM_USING = "USB"  # "USB" or "WIFI"
PORT = 5555

WATCHED_FILES = [
    "main.py"
]  # Add the files you want to watch here, i.e., if they change, the app will be reloaded
WATCHED_FOLDERS_RECURSIVELY = [
    "screens"
]  # Add the folders you want to watch here, i.e., if any file inside them changes, the app will be reloaded
WATCHED_FOLDERS = []  # Watched folders but not recursively

KV_FILES_FOLDERS = ["screens"]  # Add the folders where you have your .kv files here

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
