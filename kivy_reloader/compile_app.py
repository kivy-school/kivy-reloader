import logging
import os
import platform as _platform
import signal
import subprocess
import sys
import time
from contextlib import suppress
from multiprocessing import Process
from sys import platform as _sys_platform
from threading import Thread

import psutil
import readchar
import typer
from colorama import Fore, Style, init

from .config import config
from .utils import get_connected_devices, get_wifi_ip

# ── colorama ──────────────────────────────
init(autoreset=True)
green = Fore.GREEN
yellow = Fore.YELLOW
red = Fore.RED


def get_app_name():
    """
    Extracts the application name from the 'buildozer.spec' file.
    """
    with open("buildozer.spec", "r") as file:
        for line in file:
            if line.startswith("title"):
                return line.split("=")[1].strip()
    return "UnknownApp"


def get_apk_path():
    pkg = ""
    version = ""
    archs = ""
    with open("buildozer.spec", 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith("package.name"):
                pkg = line.split("=", 1)[1].strip()
            elif line.startswith("version") and not line.startswith("version."):
                version = line.split("=", 1)[1].strip()
            elif line.startswith("android.archs"):
                archs = line.split("=", 1)[1].strip().replace(",", "_").replace(" ", "")
    arch = archs if archs else "arm64-v8a"
    return f"bin/{pkg}-{version}-{arch}-debug.apk"


def get_package_name():
    domain = "org.test"
    name = "UnknownApp"
    with open("buildozer.spec", "r", encoding='utf-8') as file:
        for line in file:
            if line.startswith("package.domain"):
                domain = line.split("=")[1].strip()
            elif line.startswith("package.name"):
                name = line.split("=")[1].strip()
    return f"{domain}.{name}"


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

if platform != "win":
    # ── terminal state capture ────────────────────────────────────────────────────
    _ORIGINAL_STTY = subprocess.check_output(["stty", "-g"]).decode().strip()

    def _restore_terminal() -> None:
        """Return terminal to the settings captured at startup."""
        subprocess.run(["stty", _ORIGINAL_STTY], check=False)

    def _sigint_handler(_sig, _frame) -> None:
        """Handle Ctrl-C: restore terminal, then exit."""
        _restore_terminal()
        sys.exit(130)

    signal.signal(signal.SIGINT, _sigint_handler)
else:

    def _restore_terminal() -> None:
        """No-op for Windows."""
        pass


def _terminate(proc: subprocess.Popen) -> None:
    with suppress(Exception):
        if proc and proc.poll() is None:
            proc.terminate()


logcat_proc: subprocess.Popen | None = None
filter_proc: subprocess.Popen | None = None

app = typer.Typer()
app_name = get_app_name()
package = get_package_name()
apk_path = get_apk_path()

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


def select_option(option: str, app_name: str) -> None:
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

    # Step 1: Compile using buildozer
    t1 = time.time()
    subprocess.run(["buildozer", "-v", "android", "debug"], check=True)
    t2 = time.time()
    notify(
        f"Compiled {app_name} successfully",
        f"Compilation finished in {round(t2 - t1, 2)} seconds",
    )
    logging.info("Finished compilation")

    # Step 2: Select target serial
    devices = get_connected_devices()
    if not devices:
        logging.error("No connected devices found. APK will not be installed.")
        return

    physical_map = {}
    for d in devices:
        key = (d["wifi_ip"], d["model"])
        existing = physical_map.get(key)
        if not existing:
            physical_map[key] = d
        elif config.STREAM_USING == "USB" and d["transport"] == "usb":
            physical_map[key] = d
        elif config.STREAM_USING == "WIFI" and d["transport"] == "tcpip":
            physical_map[key] = d

    # Step 3: Install the APK on each device
    for device in physical_map.values():
        logging.info(f"Installing APK on {device['model']} | ({device['serial']})")
        subprocess.run(
            ["adb", "-s", device["serial"], "install", "-r", apk_path], check=True
        )
        logging.info(f"Starting app on {device['model']} | ({device['serial']})")
        subprocess.run(
            [
                "adb",
                "-s",
                device["serial"],
                "shell",
                "am",
                "start",
                "-n",
                f"{package}/org.kivy.android.PythonActivity",
            ],
            check=True,
        )


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
    If multiple serials point to the same device, clears only once per device.
    """
    logging.info("Clearing logcat")
    try:
        devices = get_connected_devices()
        if not devices:
            logging.error("No connected devices found. Logcat will not be cleared.")
            return

        # Group by (wifi_ip, model) = physical device
        physical_map = {}
        for d in devices:
            key = (d["wifi_ip"], d["model"])
            existing = physical_map.get(key)

            if not existing:
                physical_map[key] = d
            else:
                if config.STREAM_USING == "USB" and d["transport"] == "usb":
                    physical_map[key] = d
                elif config.STREAM_USING == "WIFI" and d["transport"] == "tcpip":
                    physical_map[key] = d

        logging.debug(f"Estimated physical devices connected: {len(physical_map)}")

        for d in physical_map.values():
            logging.debug(
                f"Clearing logcat for serial={d['serial']} ({d['transport']}, {d['model']})"
            )
            subprocess.run(["adb", "-s", d["serial"], "logcat", "-c"], check=True)
            logging.info(
                f"Logcat cleared for device {d['model']} ({d['serial']}) ({d['transport']})"
            )
    except FileNotFoundError:
        logging.error("adb not found")
        print(
            f"{red}Please, install `scrcpy`: {yellow}https://github.com/Genymobile/scrcpy{Fore.RESET}"
        )


def debug_on_wifi():
    """
    Debugging over WiFi.
    If config.PHONE_IPS is empty, operate on all connected devices.
    If not empty, operate only on devices whose wifi_ip is in config.PHONE_IPS.
    """
    logging.info("Switching ADB to TCP/IP mode...")
    devices = get_connected_devices()
    logging.debug(f"Connected devices: {devices}")

    # Determine targets
    if not config.PHONE_IPS:
        target_usb_devices = [d for d in devices if d["transport"] == "usb"]
        target_tcpip_ips = [
            d["wifi_ip"] for d in devices if d["transport"] == "tcpip" and d["wifi_ip"]
        ]
    else:
        target_usb_devices = [
            d
            for d in devices
            if d["transport"] == "usb" and d["wifi_ip"] in config.PHONE_IPS
        ]
        target_tcpip_ips = [
            ip
            for ip in config.PHONE_IPS
            if any(d["wifi_ip"] == ip and d["transport"] == "tcpip" for d in devices)
        ]

    for d in target_usb_devices:
        logging.info(f"Enabling tcpip mode for {d['model']} ({d['serial']})")
        subprocess.run(["adb", "-s", d["serial"], "tcpip", f"{config.ADB_PORT}"], check=True)

        if not d["wifi_ip"]:
            d["wifi_ip"] = get_wifi_ip(d["serial"])

        ip_with_port = f"{d['wifi_ip']}:{config.ADB_PORT}"
        logging.info(f"Connecting to {ip_with_port}")
        try:
            subprocess.run(["adb", "connect", ip_with_port], check=True)
        except FileNotFoundError:
            logging.error("adb not found")
            print(
                f"{red}Please, install `scrcpy`: {yellow}https://github.com/Genymobile/scrcpy{Fore.RESET}"
            )

        # Now the device is in tcpip mode, we can run logcat
        # but we need to add it to the list of target_tcpip_ips
        if d["wifi_ip"] not in target_tcpip_ips:
            target_tcpip_ips.append(d["wifi_ip"])

    for ip in target_tcpip_ips:
        # start each logcat on a thread
        t = Thread(target=run_logcat, args=(ip,))
        t.start()


def run_logcat(IP=None, *args):
    """
    Runs logcat for debugging.
    """
    global logcat_proc, filter_proc

    LOGCAT_CMD = ["adb", "logcat"]

    if platform == "win":
        watch = "I python"
        findstr_services = [
            f"/c:{SERVICE_NAME}" for SERVICE_NAME in config.SERVICE_NAMES
        ]
        FINDSTR_CMD = ["findstr", "/c:" + watch] + findstr_services

    else:
        services = "|".join(config.SERVICE_NAMES)
        watch = "I python" if not services else f"I python|{services}"
        GREP_CMD = ["grep", "-E", watch]

    if IP:
        try:
            subprocess.run(["adb", "connect", f"{IP}:{config.PORT}"])
        except FileNotFoundError:
            logging.error("adb not found")
            print(
                f"{red}Please, install `scrcpy`: {yellow}https://github.com/Genymobile/scrcpy{Fore.RESET}"
            )
        LOGCAT_CMD[:1] = ["adb", "-s", f"{IP}:{config.PORT}"]

    logging.info("Starting logcat")
    try:
        logcat_proc = subprocess.Popen(LOGCAT_CMD, stdout=subprocess.PIPE)
        filter_proc = subprocess.Popen(
            FINDSTR_CMD if platform == "win" else GREP_CMD, stdin=logcat_proc.stdout
        )

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
    global logcat_proc, filter_proc

    logging.info("Starting scrcpy")
    SCRCPY_CMD = [
        "scrcpy",
        "--window-x",
        config.WINDOW_X,
        "--window-y",
        config.WINDOW_Y,
        "--window-width",
        config.WINDOW_WIDTH,
    ]

    SCRCPY_CMD.append("--no-mouse-hover")

    if config.ALWAYS_ON_TOP:
        SCRCPY_CMD.append("--always-on-top")
    if config.TURN_SCREEN_OFF:
        SCRCPY_CMD.append("--turn-screen-off")
    if config.STAY_AWAKE:
        SCRCPY_CMD.append("--stay-awake")
    if config.SHOW_TOUCHES:
        SCRCPY_CMD.append("--show-touches")
    if config.WINDOW_TITLE:
        SCRCPY_CMD.append(f"--window-title='{config.WINDOW_TITLE}'")
    if config.NO_AUDIO:
        SCRCPY_CMD.append("--no-audio")

    if config.STREAM_USING == "USB":
        SCRCPY_CMD.append("-d")
    elif config.STREAM_USING == "WIFI":
        SCRCPY_CMD.append("-e")

    try:
        scrcpy_proc = subprocess.Popen(SCRCPY_CMD, stdin=subprocess.DEVNULL)
        scrcpy_proc.wait()
    except FileNotFoundError:
        logging.error("scrcpy not found")
        print(
            f"{red}Please, install `scrcpy`: {yellow}https://github.com/Genymobile/scrcpy{Fore.RESET}"
        )
    finally:
        _restore_terminal()
        _terminate(filter_proc)
        _terminate(logcat_proc)
        _terminate(scrcpy_proc)


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
