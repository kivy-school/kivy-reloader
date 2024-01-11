import os
import sys

from colorama import Fore, init
from kivy.lang import Builder

yellow = Fore.YELLOW
green = Fore.GREEN
red = Fore.RED

init(autoreset=True)

script_path = os.path.abspath(sys.argv[0])
base_dir = (
    os.path.dirname(script_path) if not os.path.isdir(script_path) else script_path
)


def create_settings_file():
    """
    Creates a copy of constants.py in the project folder called settings.py
    so the user can change the constants. If the file already exists,
    it creates a settings_template.py file
    """
    import shutil

    files_in_base_dir = os.listdir(base_dir)
    if (
        "settings.py" in files_in_base_dir
        and "settings_template.py" not in files_in_base_dir
    ):
        shutil.copyfile(
            os.path.join(current_file_dir, "constants.py"),
            os.path.join(base_dir, "settings_template.py"),
        )
    else:
        klprint("settings.py not found, creating a copy ofaaa constants.py")
        shutil.copyfile(
            os.path.join(current_file_dir, "constants.py"),
            os.path.join(base_dir, "settings.py"),
        )


def create_buildozer_spec_file():
    """
    Creates a copy of buildozer.spec in the project folder if it doesn't exist
    If it exists, it creates a buildozer_template.spec file
    """
    import shutil

    files_in_base_dir = os.listdir(base_dir)
    if "buildozer.spec" not in files_in_base_dir:
        print("buildozer.spec not found, creating a copy of buildozer.spec")
        shutil.copyfile(
            os.path.join(current_file_dir, "buildozer.spec"),
            os.path.join(base_dir, "buildozer.spec"),
        )
    else:
        print(
            "buildozer.spec found, creating a copy of buildozer.spec called buildozer_template.spec"
        )
        if "buildozer_template.spec" not in files_in_base_dir:
            shutil.copyfile(
                os.path.join(current_file_dir, "buildozer.spec"),
                os.path.join(base_dir, "buildozer_template.spec"),
            )


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
    based on the constants.py file
    """
    return (
        [(os.path.join(base_dir, x), {"recursive": True}) for x in WATCHED_FILES]
        + [
            (os.path.join(base_dir, x), {"recursive": True})
            for x in WATCHED_FOLDERS_RECURSIVELY
        ]
        + [(os.path.join(base_dir, x), {"recursive": False}) for x in WATCHED_FOLDERS]
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
    Given the folders on WATCHED_KV_FOLDERS and WATCHED_KV_FOLDERS_RECURSIVELY,
    returns a list of all the kv files paths
    """
    KV_FILES = []

    for folder in WATCHED_KV_FOLDERS:
        for kv_file in os.listdir(folder):
            if kv_file.endswith(".kv"):
                KV_FILES.append(os.path.join(base_dir, f"{folder}/{kv_file}"))

    for folder in WATCHED_KV_FOLDERS_RECURSIVELY:
        for kv_file in find_kv_files_in_folder(folder):
            KV_FILES.append(kv_file)

    # Removing duplicates
    KV_FILES = list(set(KV_FILES))

    return KV_FILES


from kivy.utils import platform

if platform not in ["android", "ios"]:
    current_file_path = os.path.abspath(__file__)
    current_file_dir = os.path.dirname(current_file_path)

    def klprint(string):
        print(f"{green}[KIVY RELOADER]{Fore.RESET} {string}")

    files_in_base_dir = os.listdir(base_dir)
    if "settings.py" in files_in_base_dir:
        # klprint("`settings.py` found, importing constants from there")
        constants_to_import = [
            "WATCHED_FILES",
            "WATCHED_FOLDERS",
            "WATCHED_FOLDERS_RECURSIVELY",
            "WATCHED_KV_FOLDERS",
            "WATCHED_KV_FOLDERS_RECURSIVELY",
            "HOT_RELOAD_ON_PHONE",
            "STREAM_USING",
            "PORT",
            "PHONE_IPS",
            "WINDOW_TITLE",
            "SHOW_TOUCHES",
            "STAY_AWAKE",
            "TURN_SCREEN_OFF",
            "ALWAYS_ON_TOP",
            "WINDOW_X",
            "WINDOW_Y",
            "WINDOW_WIDTH",
        ]
        for constant in constants_to_import:
            try:
                exec(f"from settings import {constant}")
            except ImportError:
                exec(f"from .constants import {constant}")

        klprint(f"HOT_RELOAD_ON_PHONE: {HOT_RELOAD_ON_PHONE}")
        klprint(f"PHONE_IPS: {PHONE_IPS}")
        klprint(f"STREAM_USING: {STREAM_USING}")

    else:
        # Create a copy of constants.py in the project folder called settings.py
        # so the user can change the constants
        klprint("`settings.py` not found in the project folder")

        import shutil

        # then let's copy the file constants.py to the project folder
        # but rename it to settings.py
        source_path = os.path.join(current_file_dir, "constants.py")
        destination_path = os.path.join(base_dir, "settings.py")

        # check if the user has already chosen to not create the settings.py file
        with open(os.path.join(current_file_dir, ".kivy_reloader"), "r") as f:
            if f.read() == "DONT_ASK_USER_TO_CREATE_SETTINGS_FILE":
                klprint(f"The user has chosen to not create the `settings.py` file.")
                klprint(
                    f"If you want to create the `settings.py` file, type the following command in the terminal:"
                )
                print(f"from kivy_reloader.utils import create_settings_file")
                print(f"create_settings_file()")
                klprint("Then be happy :)")
            else:
                # ask user consent to create the settings.py file
                klprint("The `settings.py` file will be created in the project folder.")
                klprint(
                    "This file will help you to customize the constants used by kivy-reloader."
                )
                user_input = input(
                    f"{yellow} Do you want to create a settings.py file? {red}[Y/n]\n{Fore.RESET}"
                )
                if user_input.lower() in ["", "y", "ye", "yes", "yeah"]:
                    shutil.copyfile(
                        source_path,
                        destination_path,
                    )
                # if the user doesn't want to create the settings.py file
                # save his choice in a file called .kivy_reloader
                # so we don't ask him again
                with open(os.path.join(current_file_dir, ".kivy_reloader"), "w") as f:
                    f.write("DONT_ASK_USER_TO_CREATE_SETTINGS_FILE")

        from .constants import (
            ALWAYS_ON_TOP,
            HOT_RELOAD_ON_PHONE,
            PHONE_IPS,
            PORT,
            SHOW_TOUCHES,
            STAY_AWAKE,
            STREAM_USING,
            TURN_SCREEN_OFF,
            WATCHED_FILES,
            WATCHED_FOLDERS,
            WATCHED_FOLDERS_RECURSIVELY,
            WATCHED_KV_FOLDERS,
            WATCHED_KV_FOLDERS_RECURSIVELY,
            WINDOW_TITLE,
            WINDOW_WIDTH,
            WINDOW_X,
            WINDOW_Y,
        )

    if not "buildozer.spec" in files_in_base_dir:
        klprint("buildozer.spec not found, creating a copy of buildozer.spec")

        import shutil

        source_path = os.path.join(current_file_dir, "buildozer.spec")
        destination_path = os.path.join(base_dir, "buildozer.spec")

        # check if the user has already chosen to not create the buildozer.spec file
        with open(os.path.join(current_file_dir, ".kivy_reloader"), "r") as f:
            if f.read() == "DONT_ASK_USER_TO_CREATE_BUILDOZER_SPEC_FILE":
                klprint(f"The user has chosen to not create the `buildozer.spec` file.")
                klprint(
                    f"If you want to create the `buildozer.spec` file, type the following command in the terminal:"
                )
                print(f"from kivy_reloader.utils import create_buildozer_spec_file")
                print(f"create_buildozer_spec_file()")
                klprint("Then be happy :)")
                klprint(
                    "Remember, if you call this function and you already have a buildozer.spec file, it will create a buildozer_template.spec file"
                )

            else:
                # ask user consent to create the buildozer.spec file
                klprint(
                    "The `buildozer.spec` file will be created in the project folder."
                )
                klprint(
                    "This file will help you to to compile your app and send it to your phone."
                )
                user_input = input(
                    f"{yellow} Do you want to create a buildozer.spec file? {red}[Y/n]\n{Fore.RESET}"
                )
                if user_input.lower() in ["", "y", "ye", "yes", "yeah"]:
                    shutil.copyfile(
                        source_path,
                        destination_path,
                    )
                # if the user doesn't want to create the buildozer.spec file
                # save his choice in a file called .kivy_reloader
                # so we don't ask him again
                with open(os.path.join(current_file_dir, ".kivy_reloader"), "w") as f:
                    f.write("DONT_ASK_USER_TO_CREATE_BUILDOZER_SPEC_FILE")
    else:
        # check if the user has already chosen to not create the buildozer.spec file
        with open(os.path.join(current_file_dir, ".kivy_reloader"), "r") as f:
            if f.read() != "DONT_ASK_USER_TO_CREATE_BUILDOZER_SPEC_FILE":
                klprint(
                    "buildozer.spec already found. Do you want to create a buildozer_template.spec file?"
                )
                klprint(
                    "This file already has all the settings needed for kivy-reloader to work on your phone"
                )

                user_input = input(
                    f"{yellow} Do you want to create a buildozer_template.spec file? {red}[Y/n]\n{Fore.RESET}"
                )
                if user_input.lower() in ["", "y", "ye", "yes", "yeah"]:
                    import shutil

                    source_path = os.path.join(current_file_dir, "buildozer.spec")
                    destination_path = os.path.join(base_dir, "buildozer_template.spec")
                    shutil.copyfile(
                        source_path,
                        destination_path,
                    )

                # if the user doesn't want to create the buildozer.spec file
                # save his choice in a file called .kivy_reloader
                # so we don't ask him again
                with open(os.path.join(current_file_dir, ".kivy_reloader"), "w") as f:
                    f.write("DONT_ASK_USER_TO_CREATE_BUILDOZER_SPEC_FILE")
else:
    # only import these 5 constants: WATCHED_FILES, WATCHED_FOLDERS, WATCHED_FOLDERS_RECURSIVELY
    # WATCHED_KV_FOLDERS, WATCHED_KV_FOLDERS_RECURSIVELY
    # because the other constants are not needed on the phone
    current_file_path = os.path.abspath(__file__)
    current_file_dir = os.path.dirname(current_file_path)
    files_in_base_dir = os.listdir(base_dir)

    if "settings.py" in files_in_base_dir:
        constants_to_import = [
            "WATCHED_FILES",
            "WATCHED_FOLDERS",
            "WATCHED_FOLDERS_RECURSIVELY",
            "WATCHED_KV_FOLDERS",
            "WATCHED_KV_FOLDERS_RECURSIVELY",
        ]

        for constant in constants_to_import:
            try:
                exec(f"from settings import {constant}")
            except ImportError:
                exec(f"from .constants import {constant}")
    else:
        from .constants import (
            WATCHED_FILES,
            WATCHED_FOLDERS,
            WATCHED_FOLDERS_RECURSIVELY,
            WATCHED_KV_FOLDERS,
            WATCHED_KV_FOLDERS_RECURSIVELY,
        )
