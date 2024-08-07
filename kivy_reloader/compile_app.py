import logging
import os
import platform as _platform
import subprocess
import sys
import time
from multiprocessing import Process
from sys import platform as _sys_platform
from threading import Thread

import psutil
import readchar
import typer
from colorama import Fore, Style, init

from .config import config


def get_app_name():
    """
    Extracts the application name from the 'buildozer.spec' file.
    """
    with open("buildozer.spec", "r") as file:
        for line in file:
            if line.startswith("title"):
                return line.split("=")[1].strip()
    return "UnknownApp"


def _get_platform():
    kivy_build = os.environ.get("KIVY_BUILD", "")
    if kivy_build in {"android", "ios"}:
        return kivy_build
    elif "P4A_BOOTSTRAP" in os.environ:
        return "android"
    elif "ANDROID_ARGUMENT" in os.environ:
        return "android"
    elif _sys_platform in ("win32", "cygwin"):
        return "win"
    elif _sys_platform == "darwin":
        return "macosx"
    elif _sys_platform.startswith("linux"):
        return "linux"
    elif _sys_platform.startswith("freebsd"):
        return "linux"
    return "unknown"


platform_release = _platform.release().lower()
platform = _get_platform()

if platform in ["linux", "macosx"]:
    from plyer import notification

green = Fore.GREEN
yellow = Fore.YELLOW
red = Fore.RED
init(autoreset=True)

app = typer.Typer()
app_name = get_app_name()

compiler_options = [
    "Compile, debug and livestream",
    "Debug and livestream",
    "Create aab",
    "Restart adb server (fix phone connection issues)",
]

selected_option = compiler_options[0]

navigation_stack = []  # To keep track of the navigation stack


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def notify(title: str, message: str) -> None:
    """
    Send a notification to the user's desktop.
    No support for Windows yet.
    """
    try:
        if platform in ["linux", "macosx"] and "microsoft" not in platform_release:
            notification.notify(message=message, title=title)
    except Exception as e:
        logging.error(f"Failed to send notification: {e}")
        print(e)


def select_option(option: int, app_name: str) -> None:
    """
    1. Compile and deploy the app to the device
    2. Debug and livestream the app
    3. Create aab
    4. Restart adb server
    """
    try:
        if option == "1":
            compile_app()
            debug_and_livestream()
        elif option == "2":
            debug_and_livestream()
        elif option == "3":
            create_aab()
        elif option == "4":
            restart_adb_server()

    except subprocess.CalledProcessError as e:
        logging.error(f"An error occurred during compilation: {e}")


def compile_app():
    """
    Uses `buildozer` to compile the app for Android.
    Notifies the user about the compilation status.
    """
    if platform == "win":
        logging.error("Windows can not run buildozer")
        logging.error("Please, use WSL2")
        print(
            f"{red}Please, follow Kivy School tutorial: {yellow}https://kivyschool.com/kivy-reloader/"
        )
        sys.exit(0)

    logging.info("Starting compilation")

    notify(
        f"Compiling {app_name}",
        f"Compilation started at {time.strftime('%H:%M:%S')}",
    )
    t1 = time.time()
    subprocess.run(["buildozer", "-v", "android", "debug", "deploy", "run"], check=True)
    t2 = time.time()
    notify(
        f"Compiled {app_name} successfully",
        f"Compilation finished in {round(t2 - t1, 2)} seconds",
    )
    logging.info("Finished compilation")


def debug_and_livestream() -> None:
    """
    Executes `adb logcat` and `scrcpy` in parallel.
    """
    try:
        adb_logcat = Process(target=debug)
        scrcpy = Process(target=livestream)

        adb_logcat.start()
        scrcpy.start()
    except KeyboardInterrupt:
        logging.info("Terminating processes")
        adb_logcat.terminate()
        scrcpy.terminate()
        sys.exit(0)


def debug():
    """
    Debugging based on the streaming method.
    """
    if config.STREAM_USING == "USB":
        start_adb_server()
        clear_logcat()
        run_logcat()
    elif config.STREAM_USING == "WIFI":
        debug_on_wifi()


def restart_adb_server():
    kill_adb_server()
    start_adb_server()
    sys.exit(0)


def kill_adb_server():
    logging.info("Restarting adb server")
    try:
        subprocess.run(["adb", "disconnect"])
        subprocess.run(["adb", "kill-server"])
    except FileNotFoundError:
        print(
            f"{red}Please, install `scrcpy`: {yellow}https://github.com/Genymobile/scrcpy{Fore.RESET}"
        )


def start_adb_server():
    logging.info("Starting adb server")
    try:
        subprocess.run(["adb", "start-server"])
    except FileNotFoundError:
        logging.error("adb not found")
        print(
            f"{red}Please, install `scrcpy`: {yellow}https://github.com/Genymobile/scrcpy{Fore.RESET}"
        )


def clear_logcat():
    """
    Clears the logcat.
    """
    logging.info("Clearing logcat")
    try:
        subprocess.run(["adb", "logcat", "-c"])
    except FileNotFoundError:
        logging.error("adb not found")
        print(
            f"{red}Please, install `scrcpy`: {yellow}https://github.com/Genymobile/scrcpy{Fore.RESET}"
        )


def debug_on_wifi():
    """
    Debugging over WiFi.
    """
    subprocess.run(["adb", "tcpip", f"{config.PORT}"])

    for IP in config.PHONE_IPS:
        # start each logcat on a thread
        t = Thread(target=run_logcat, args=(IP,))
        t.start()


def run_logcat(IP=None, *args):
    """
    Runs logcat for debugging.
    """

    if platform == "win":
        watch = '"I python"'
        findstr_services = " ".join(
            [f"/c:{SERVICE_NAME}" for SERVICE_NAME in config.SERVICE_NAMES]
        )
        logcat_command = f"adb logcat | findstr /r /c:{watch} {findstr_services}"
    else:
        watch = "'I python"
        for service in config.SERVICE_NAMES:
            watch += f"\|{service}"
        else:
            watch += "'"
        logcat_command = f"adb logcat | grep {watch}"

    if IP:
        try:
            subprocess.run(["adb", "connect", f"{IP}:{config.PORT}"])
        except FileNotFoundError:
            logging.error("adb not found")
            print(
                f"{red}Please, install `scrcpy`: {yellow}https://github.com/Genymobile/scrcpy{Fore.RESET}"
            )
        logcat_command.replace("adb", f"adb -s {IP}:{config.PORT}")

    logging.info("Starting logcat")
    try:
        subprocess.run(logcat_command, shell=True)
    except FileNotFoundError:
        logging.error("adb not found")
        print(
            f"{red}Please, install `scrcpy`: {yellow}https://github.com/Genymobile/scrcpy{Fore.RESET}"
        )


def livestream():
    """
    Handles the livestream process.
    """
    if config.STREAM_USING == "WIFI":
        time.sleep(3)

    for proc in psutil.process_iter():
        try:
            if proc.name() == "scrcpy":
                logging.info("scrcpy already running")
                return
        except psutil.NoSuchProcess:
            logging.error("Error while trying to find scrcpy process")

    start_scrcpy()


def start_scrcpy():
    """
    Starts the scrcpy process for screen mirroring.
    """
    logging.info("Starting scrcpy")
    command = [
        "scrcpy",
        "--window-x",
        config.WINDOW_X,
        "--window-y",
        config.WINDOW_Y,
        "--window-width",
        config.WINDOW_WIDTH,
    ]

    command.append("--no-mouse-hover")

    if config.ALWAYS_ON_TOP:
        command.append("--always-on-top")
    if config.TURN_SCREEN_OFF:
        command.append("--turn-screen-off")
    if config.STAY_AWAKE:
        command.append("--stay-awake")
    if config.SHOW_TOUCHES:
        command.append("--show-touches")
    if config.WINDOW_TITLE:
        command.append(f"--window-title='{config.WINDOW_TITLE}'")
    if config.NO_AUDIO:
        command.append("--no-audio")

    if config.STREAM_USING == "USB":
        command.append("-d")
    elif config.STREAM_USING == "WIFI":
        command.append("-e")

    try:
        subprocess.run(command)
    except FileNotFoundError:
        logging.error("scrcpy not found")
        print(
            f"{red}Please, install `scrcpy`: {yellow}https://github.com/Genymobile/scrcpy{Fore.RESET}"
        )


def create_aab():
    print(f"{yellow} Started creating aab")
    notify(
        f"Compile production: {app_name}",
        f"Compilation started at {time.strftime('%H:%M:%S')}",
    )
    t1 = time.time()
    os.system("buildozer -v android release")
    t2 = time.time()
    notify(
        f"Compiled {app_name} successfully",
        f"Compilation finished in {round(t2 - t1, 2)} seconds",
    )
    print(f"{green} Finished compilation")
    sys.exit(0)


def navigate_back():
    if navigation_stack:
        previous_navigation = navigation_stack.pop()
        previous_navigation()


def navigate_compiler_options():
    # Push the current navigation to the stack for backward navigation
    navigation_stack.append(compiler_options)


def highlight_selected_option(option: str):
    if option == selected_option:
        option_text = f"[{green}x{Style.RESET_ALL}] {green}"
    else:
        option_text = f"[ ] "

    option_text = f"{option_text}{option}{Style.RESET_ALL}"
    typer.echo(option_text)


def start():
    """
    Entry point for the script. Prompts the user to choose an option.
    """
    global selected_option

    navigate_compiler_options()

    typer.clear()
    typer.echo(f"\nSelect one of the 4 options below:\n")

    development_options = compiler_options[:2]
    production_option = compiler_options[2]
    fix_option = compiler_options[3]

    typer.echo(f"🛠️  {yellow}Development{Style.RESET_ALL} ")
    for option in development_options:
        highlight_selected_option(option)

    typer.echo(f"\n📦 {yellow}Production{Style.RESET_ALL} ")
    highlight_selected_option(production_option)

    typer.echo(f"\n🔄 {yellow}Fix{Style.RESET_ALL}")
    highlight_selected_option(fix_option)
    typer.echo("")

    while True:
        key = readchar.readkey()

        if key == readchar.key.DOWN:
            selected_index = compiler_options.index(selected_option)
            next_index = (selected_index + 1) % len(compiler_options)
            selected_option = compiler_options[next_index]
            typer.clear()
            start()
            break
        elif key == readchar.key.UP:
            selected_index = compiler_options.index(selected_option)
            prev_index = (selected_index - 1) % len(compiler_options)
            selected_option = compiler_options[prev_index]
            typer.clear()
            start()
            break
        # left key, q, ESC
        elif key == readchar.key.LEFT or key == "q" or key == readchar.key.ESC * 2:
            exit()
        elif key in ["\n", readchar.key.RIGHT, readchar.key.ENTER]:
            typer.clear()
            print(f"{yellow} Selected option: {green}{selected_option}")
            option = str(compiler_options.index(selected_option) + 1)
            typer.clear()
            select_option(option, app_name)
            break
