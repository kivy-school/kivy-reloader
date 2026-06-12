import logging
import os
import platform as _platform
import re
import shutil
import signal
import subprocess
import sys
from pathlib import Path

import time
from contextlib import suppress
from multiprocessing import Process, Event
from sys import platform as _sys_platform
from threading import Thread
import trio

import readchar
import typer
from colorama import Fore, Style, init

from .config import config
from .utils import get_connected_devices, get_wifi_ip, in_wsl, is_adb_listening, extract_ip, get_wsl_nameservers, get_adb_windows_path, adb_has_forward, adb_forward


def is_ci_environment() -> bool:
    """
    Check if running in a CI/CD environment.

    Returns:
        bool: True if running in CI, False otherwise
    """
    ci_indicators = [
        'CI',  # Generic CI indicator
        'GITHUB_ACTIONS',  # GitHub Actions
        'GITLAB_CI',  # GitLab CI
        'JENKINS_URL',  # Jenkins
        'TRAVIS',  # Travis CI
        'CIRCLECI',  # Circle CI
        'BUILDKITE',  # Buildkite
        'DRONE',  # Drone CI
        'TF_BUILD',  # Azure DevOps
        'BITBUCKET_BUILD_NUMBER',  # Bitbucket Pipelines
    ]

    return any(os.environ.get(var) for var in ci_indicators)


# ── colorama ──────────────────────────────
init(autoreset=True)
green = Fore.GREEN
yellow = Fore.YELLOW
red = Fore.RED

def _read_ksproject_config() -> dict:
    """Read build config from pyproject.toml [tool.kivy-school] section."""
    import tomlkit
    with open('pyproject.toml', 'r', encoding='utf-8') as f:
        data = tomlkit.load(f)
    ks = data.get('tool', {}).get('kivy-school', {})
    android = ks.get('android', {})
    app_name_val = ks.get('app_name', 'App')
    pkg_name = android.get('package_name', f'org.kivy.{app_name_val.lower()}')
    return {
        'app_name': app_name_val,
        'package': pkg_name,
        'apk_path': 'project_dist/gradle/app/build/outputs/apk/debug/app-debug.apk',
    }


def parse_buildozer_spec() -> dict:
    """
    Parses the buildozer.spec file and extracts all relevant configuration values.

    Returns:
        dict: Configuration values from buildozer.spec

    Raises:
        FileNotFoundError: If buildozer.spec file doesn't exist
    """
    config_values = {
        'title': 'UnknownApp',
        'package_name': 'unknown_app',
        'package_domain': 'org.example',
        'version': '0.1',
        'android_archs': 'arm64-v8a',
    }

    try:
        with open('buildozer.spec', 'r', encoding='utf-8') as file:
            for file_line in file:
                stripped_line = file_line.strip()
                if '=' in stripped_line and not stripped_line.startswith('#'):
                    key, value = stripped_line.split('=', 1)
                    key = key.strip()
                    value = value.strip()

                    if key == 'title':
                        config_values['title'] = value
                    elif key == 'package.name':
                        config_values['package_name'] = value
                    elif key == 'package.domain':
                        config_values['package_domain'] = value
                    elif key == 'version' and not key.startswith('version.'):
                        config_values['version'] = value
                    elif key == 'android.archs':
                        config_values['android_archs'] = value.replace(
                            ',', '_'
                        ).replace(' ', '')
    except FileNotFoundError:
        raise FileNotFoundError(
            'buildozer.spec file not found. Please, '
            'run `kivy-reloader init` to generate a default buildozer.spec file.'
        )
    return config_values


def get_app_name() -> str:
    """
    Extracts the application name from the buildozer.spec file.

    Returns:
        str: Application title or 'UnknownApp' if not found
    """
    return parse_buildozer_spec()['title']


def get_apk_path() -> str:
    """
    Constructs the APK file path based on buildozer.spec configuration.

    Returns:
        str: Path to the debug APK file
    """
    spec = parse_buildozer_spec()
    pkg = spec['package_name']
    version = spec['version']
    arch = spec['android_archs']
    return f'bin/{pkg}-{version}-{arch}-debug.apk'


def get_package_name() -> str:
    """
    Constructs the full package name from domain and name in buildozer.spec.

    Returns:
        str: Full package name in format 'domain.name'
    """
    spec = parse_buildozer_spec()
    return f'{spec["package_domain"]}.{spec["package_name"]}'


def _get_platform():
    """
    Determines the current platform string.

    Returns:
        str: Platform identifier (android, ios, win, macosx, linux, or unknown)
    """
    kivy_build = os.environ.get('KIVY_BUILD', '')

    # Priority 1: KIVY_BUILD environment variable
    if kivy_build in {'android', 'ios'}:
        return kivy_build

    # Priority 2: Android-specific environment variables
    android_env_vars = {'P4A_BOOTSTRAP', 'ANDROID_ARGUMENT'}
    if any(var in os.environ for var in android_env_vars):
        return 'android'

    # Priority 3: System platform detection
    platform_map = {'win32': 'win', 'cygwin': 'win', 'darwin': 'macosx'}

    if _sys_platform in platform_map:
        return platform_map[_sys_platform]
    elif _sys_platform.startswith(('linux', 'freebsd')):
        return 'linux'

    return 'unknown'


platform_release = _platform.release().lower()
platform = _get_platform()

if platform in {'linux', 'macosx'}:
    from plyer import notification
else:
    # Mock notification for Windows and other platforms
    class NotificationMock:
        def notify(self, message, title):
            pass

    notification = NotificationMock()

if platform != 'win':
    # ── terminal state capture ────────────────────────────────────────────────────
    try:
        _ORIGINAL_STTY = subprocess.check_output(['stty', '-g']).decode().strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        # No TTY available (CI environment, etc.) - disable terminal restoration
        _ORIGINAL_STTY = None
        logging.debug('No TTY available, terminal restoration disabled')

    def _restore_terminal() -> None:
        """Return terminal to the settings captured at startup."""
        if _ORIGINAL_STTY is not None:
            subprocess.run(['stty', _ORIGINAL_STTY], check=False)

    def _sigint_handler(_sig, _frame) -> None:
        """Handle Ctrl-C: restore terminal, cleanup processes, then exit."""
        logging.info('Received interrupt signal (Ctrl+C)')
        safe_exit(130)

    signal.signal(signal.SIGINT, _sigint_handler)
else:

    def _restore_terminal() -> None:
        """No-op for Windows."""
        pass


def _terminate(proc: subprocess.Popen) -> None:
    with suppress(Exception):
        if proc and proc.poll() is None:
            proc.terminate()

def wait_for_authorization(timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        output = subprocess.check_output(["adb", "devices"]).decode().strip().splitlines()[1:]
        devices = [line.split() for line in output if line.strip()]
        
        authorized_hardware_serials = set()
        for parts in devices:
            # # In wait_for_authorization(), change the final check to:
            # for parts in devices:
            #     if len(parts) < 2:
            #         continue
            #     serial, state = parts[0], parts[1]
            #     if ":" not in serial and state == 'device':  # USB AND authorized state
            #         print(f"Device {serial} is authorized. Proceeding...")
            #         return True
            if len(parts) < 2:
                continue
            serial, state = parts[0], parts[1]
            if state == 'device':
                if ":" in serial:
                    try:
                        hw_serial = subprocess.check_output(
                            ["adb", "-s", serial, "shell", "getprop", "ro.serialno"],
                            stderr=subprocess.DEVNULL, timeout=2
                        ).decode().strip()
                        authorized_hardware_serials.add(hw_serial)
                    except:
                        continue
                else:
                    authorized_hardware_serials.add(serial)  # ← USB serial is authorized directly

        # Now check: any physical USB device authorized?
        for parts in devices:
            if len(parts) < 2:
                continue
            serial, state = parts[0], parts[1]
            if ":" not in serial:  # physical USB
                if serial in authorized_hardware_serials:
                    print(f"Device {serial} is authorized. Proceeding...")
                    return True

        elapsed = time.time() - start
        # serial_list = [parts[0] for parts in devices if len(parts) >= 2 and ":" not in parts[0]]
        # print(f"[+{elapsed:0.2f}s] waiting for authorization on {','.join(serial_list)}...")
        state_list = [f"{parts[0]}({parts[1]})" for parts in devices if len(parts) >= 2 and ":" not in parts[0]]
        print(f"[+{elapsed:0.2f}s] waiting for authorization on {','.join(state_list)}...")
        if elapsed > 10:
            print("  No prompt on your phone? Unplug and replug the USB cable.")
        if elapsed > 20:
            print("  Still no prompt? Settings → Developer Options → Revoke USB debugging authorizations, then replug.")
        time.sleep(1)
    
    return False

# PARTIALLY WORKED SCRCPY HANGED/HUNG
# def wait_for_authorization(timeout=30):
#     start = time.time()
#     while time.time() - start < timeout:
#         output = subprocess.check_output(["adb", "devices"]).decode().strip().splitlines()[1:]
#         devices = [line.split() for line in output if line.strip()]
        
#         # 1. Collect all authorized hardware serials
#         authorized_hardware_serials = set()
#         for serial, state in devices:
#             if state == 'device':
#                 # If it's an IP, get the underlying hardware serial
#                 if ":" in serial:
#                     try:
#                         hw_serial = subprocess.check_output(
#                             ["adb", "-s", serial, "shell", "getprop", "ro.serialno"],
#                             stderr=subprocess.DEVNULL, timeout=2
#                         ).decode().strip()
#                         authorized_hardware_serials.add(hw_serial)
#                         print("hw serial list", hw_serial)

#                     except: continue
#                 else:
#                     authorized_hardware_serials.add(serial)

#         # 2. Check if our "Target" USB device is already covered
#         # Even if the USB shows as 'unauthorized', if its serial is in 
#         # authorized_hardware_serials (via IP), we are good to go.
#         serial_list = []
#         for serial, state in devices:
#             if ":" not in serial: # Physical USB
#                 if serial in authorized_hardware_serials:
#                     print(f"Device {serial} is authorized (via TCP/IP). Proceeding...")
#                     return True
#                 else:
#                     serial_list.append(serial)

#         adb_devices = subprocess.check_output(
#                             ["adb", "devices", "-l"],
#                             stderr=subprocess.DEVNULL, timeout=2
#                         ).decode().strip()
#         print("adb devices -l", adb_devices)


#         elapsed = time.time() - start
#         print(f"[+{elapsed:0.2f}s] waiting for authorization on {','.join(serial_list)}...")
#         time.sleep(1)
    
#     return False


# def wait_for_authorization(timeout=30):
#     import time, subprocess, logging

#     def adb(cmd):
#         return subprocess.check_output(["adb"] + cmd).decode().strip()

#     start = time.time()
#     usb_serial = None

#     while time.time() - start < timeout:
#         devices_full = adb(["devices", "-l"])
#         print("\n=== adb devices -l ===")
#         print(devices_full)
#         print("======================\n")

#         # FIX: accept any non-header line
#         lines = [
#             l for l in devices_full.splitlines()
#             if l.strip() and not l.startswith("List of devices")
#         ]

#         if not lines:
#             print("No devices detected.")
#             return False

#         parsed = []
#         for l in lines:
#             parts = l.split()
#             serial = parts[0]
#             state = parts[1]
#             parsed.append((serial, state))

#         usb_devices = [s for s, st in parsed if ":" not in s]

#         if usb_devices and usb_serial is None:
#             usb_serial = usb_devices[0]
#             print(f"Captured USB serial: {usb_serial}")

#         for serial, state in parsed:
#             if "unauthorized" in state:
#                 elapsed = time.time() - start
#                 print(f"[+{elapsed:0.2f}s] waiting for authorization on {serial}...")
#                 devices_full = adb(["devices", "-l"])
#                 print("\n=== adb devices -l ===")
#                 print(devices_full)
#                 print("======================\n")
#                 time.sleep(0.5)
#                 break
#         else:
#             for serial, state in parsed:
#                 if state == "device":
#                     print(f"Authorized device: {serial}")
#                     return True

#         time.sleep(0.5)

#     logging.error("Device did not authorize in time.")
#     print("Please tap 'Allow USB debugging' on your phone.")
#     return False


# def wait_for_authorization(timeout=30):
#     import time, subprocess, logging

#     def adb(cmd):
#         return subprocess.check_output(["adb"] + cmd).decode().strip()

#     start = time.time()
#     usb_serial = None

#     while time.time() - start < timeout:
#         # Full device list for debugging
#         devices_full = adb(["devices", "-l"])
#         print("\n=== adb devices -l ===")
#         print(devices_full)
#         print("======================\n")

#         # Parse devices
#         lines = [l for l in devices_full.splitlines() if "\t" in l]

#         if not lines:
#             print("No devices detected.")
#             return False

#         # Extract serial + state
#         parsed = []
#         for l in lines:
#             serial, state = l.split("\t", 1)
#             parsed.append((serial.strip(), state.strip()))

#         # 1. Capture USB serial FIRST (before TCP/IP)
#         # USB devices have no ":" in the serial
#         usb_devices = [s for s, st in parsed if ":" not in s]

#         if usb_devices and usb_serial is None:
#             usb_serial = usb_devices[0]
#             print(f"Captured USB serial: {usb_serial}")

#         # 2. Check for unauthorized state
#         for serial, state in parsed:
#             if "unauthorized" in state:
#                 elapsed = time.time() - start
#                 print(f"[+{elapsed:0.2f}s] waiting for authorization on {serial}...")
#                 time.sleep(0.5)
#                 break
#         else:
#             # No unauthorized devices → check for authorized
#             for serial, state in parsed:
#                 if state == "device":
#                     print(f"Authorized device: {serial}")
#                     return True

#         time.sleep(0.5)

#     logging.error("Device did not authorize in time.")
#     print("Please tap 'Allow USB debugging' on your phone.")
#     return False



# def wait_for_authorization(timeout=30):
#     import time, subprocess, datetime

#     start = time.time()
#     while time.time() - start < timeout:
#         out = subprocess.check_output(["adb", "devices"]).decode().strip()

#         # No devices at all → exit immediately
#         if "unauthorized" not in out and "device" not in out:
#             print("No devices detected during authorization wait.")
#             return False
#         now = datetime.datetime.now()

#         # print("time timeout!", now)
#         elapsed = time.time() - start
#         print(f"[+{elapsed:0.2f}s] waiting for authorization...")

#         for line in out.splitlines():
#             if "unauthorized" in line:
#                 # Still waiting for user to tap "Allow"
#                 time.sleep(0.5)
#                 break

#             # # Match ANY whitespace before "device"
#             # if line.strip().endswith("device"):
#             #     return True
#             if "device" in line:
#                 return True

#         time.sleep(0.5)
#         logging.error(f"Device did not authorize in time. ({elapsed:0.2f}s)")
#         print("Please tap 'Allow USB debugging' on your phone.")
#         devices_full = subprocess.check_output(["adb", "devices", "-l"]).decode().strip()
#         print("\n=== adb devices -l ===")
#         print(devices_full)
#         print("======================\n")

#     return False


def validate_devices_connected() -> list:
    """
    Validates that devices are connected and returns them.

    Returns:
        list: Connected devices

    Raises:
        SystemExit: If no devices are connected
    """

    wait_for_authorization()

    if config.STREAM_USING == "WIFI":
        fetch_wifi_ip =True
    else:
        fetch_wifi_ip= False

    devices = get_connected_devices(fetch_wifi_ip)


    if not devices:
        logging.error('No connected devices found.')
        print(
            f'{red}No devices connected. Please connect a device and try again.'
            f'{Style.RESET_ALL}'
        )
        print(f'{yellow}Make sure:')
        print('  • USB debugging is enabled on your device')
        print('  • Device is properly connected via USB or WiFi')
        print(f'  • Device is turned on.{Style.RESET_ALL}')
        sys.exit(1)

    logging.info(f'Found {len(devices)} connected device(s)')
    return devices

def wait_for_ip_authorization(ip_with_port: str, timeout=30) -> bool:
    import time
    start = time.time()
    while time.time() - start < timeout:
        result = subprocess.run(['adb', 'devices'], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if ip_with_port in line and 'device' in line and 'unauthorized' not in line:
                logging.info(f'{ip_with_port} authorized!')
                return True
        logging.info(f'Waiting for authorization. Tap on phone for {ip_with_port}...')
        time.sleep(1)
    elapsed = time.time() - start
    logging.error(f'[+{elapsed:0.2f}s] Authorization timed out for {ip_with_port}')
    return False


def terminate_processes(*processes) -> None:
    """
    Safely terminates multiple processes with timeout handling.

    Args:
        *processes: Variable number of Process objects to terminate
    """
    for proc in processes:
        if proc and proc.is_alive():
            logging.info(f'Terminating process {proc.name}')
            proc.terminate()

            # Give process time to terminate gracefully
            try:
                proc.join(timeout=3.0)
            except Exception:
                logging.warning(f'Force killing process {proc.name}')
                proc.kill()


def safe_exit(exit_code: int = 0) -> None:
    """
    Safely exits the application with proper cleanup.

    Args:
        exit_code: Exit code to use (0 for success, non-zero for error)
    """
    logging.info('Shutting down application...')

    # Clean up global processes
    cleanup_processes(logcat_proc, filter_proc)

    # Restore terminal state
    _restore_terminal()

    logging.info('Application shutdown complete')
    sys.exit(exit_code)


logcat_proc: subprocess.Popen | None = None
filter_proc: subprocess.Popen | None = None

app = typer.Typer()
try:
    app_name = get_app_name()
    package = get_package_name()
    apk_path = get_apk_path()
except FileNotFoundError:
    try:
        _ksp = _read_ksproject_config()
        app_name = _ksp['app_name']
        package = _ksp['package']
        apk_path = _ksp['apk_path']
    except Exception:
        app_name = 'App'
        package = ''
        apk_path = ''

compiler_options = [
    'Compile, debug and livestream',
    'Debug and livestream',
    'Create aab',
    'Restart adb server (fix phone connection issues)',
]

selected_option = compiler_options[0]

navigation_stack = []  # To keep track of the navigation stack


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)


def notify(title: str, message: str) -> None:
    """
    Send a notification to the user's desktop.
    No support for Windows yet.
    """
    # Check if notifications are enabled
    if not config.SHOW_NOTIFICATIONS:
        return

    try:
        if platform in {'linux', 'macosx'} and 'microsoft' not in platform_release:
            notification.notify(message=message, title=title)
    except Exception as e:
        logging.error(f'Failed to send notification: {e}')
        print(e)


def select_option(option: str, app_name: str) -> None:
    """
    1. Compile and deploy the app to the device
    2. Debug and livestream the app
    3. Create aab
    4. Restart adb server
    """

    if in_wsl() and config.STREAM_USING == "USB":
        start_nodaemon_adb_server()
    #     # fix wsl
    #     trio.run(fix_wsl)
    #     # check for auth
    #     wait_for_authorization()

    try:
        buildozer_compiled = Event()
        if option == '1':
            compile_app(buildozer_compiled)
            logging.info(f"debug_and_livestream RAN!!A")
            debug_and_livestream(buildozer_compiled)
        elif option == '2':
            buildozer_compiled.set()
            logging.info(f"debug_and_livestream RAN!!B")
            debug_and_livestream(buildozer_compiled)
        elif option == '3':
            create_aab()
        elif option == '4':
            restart_adb_server()

    except subprocess.CalledProcessError as e:
        logging.error(f'An error occurred during compilation: {e}')


def validate_compilation_environment() -> None:
    """
    Validates that the current platform supports buildozer compilation.

    Raises:
        SystemExit: If running on Windows platform
    """
    if platform == 'win':
        logging.error('Windows can not run buildozer')
        logging.error('Please, use WSL2')
        print(
            f'{red}Please, follow Kivy School tutorial: {yellow}https://kivyschool.com/kivy-reloader/'
        )
        sys.exit(0)


def run_buildozer_compilation() -> float:
    """
    Executes buildozer compilation process with timing and notifications.

    Returns:
        float: Compilation time in seconds

    Raises:
        subprocess.CalledProcessError: If buildozer compilation fails
    """
    logging.info('Starting compilation')

    notify(
        f'Compiling {app_name}',
        f'Compilation started at {time.strftime("%H:%M:%S")}',
    )

    start_time = time.time()
    subprocess.run(['buildozer', '-v', 'android', 'debug'], check=True)
    end_time = time.time()

    compilation_time = round(end_time - start_time, 2)

    notify(
        f'Compiled {app_name} successfully',
        f'Compilation finished in {compilation_time} seconds',
    )
    logging.info('Finished compilation')

    return compilation_time


def filter_target_devices(devices: list) -> dict:
    """
    Filters and deduplicates devices based on physical device mapping.

    Prioritizes USB devices when STREAM_USING is "USB" and TCP/IP devices
    when STREAM_USING is "WIFI" for the same physical device.

    Args:
        devices: List of connected device dictionaries

    Returns:
        dict: Mapping of device info tuples to selected device dictionaries
    """
    physical_map = {}

    for device in devices:
        key = (device['wifi_ip'], device['model'])
        existing = physical_map.get(key)

        if not existing:
            physical_map[key] = device
        elif config.STREAM_USING == 'USB' and device['transport'] == 'usb':
            physical_map[key] = device
        elif config.STREAM_USING == 'WIFI' and device['transport'] == 'tcpip':
            physical_map[key] = device

    return physical_map

def deploy_app_to_devices(target_devices, apk_file_path, package_name, activity_class='org.kivy.android.PythonActivity', is_ksproject=False):
    for device in target_devices.values():
        logging.info(f'Installing APK on {device["model"]} | ({device["serial"]})')

        # Prepare WSL-safe install path once so the signature-mismatch retry can reuse it
        win_path = None
        win_apk_path = None
        win_temp = None
        if in_wsl():
            adb_path = get_adb_windows_path()
            win_path = subprocess.check_output(['wslpath', '-w', adb_path]).decode().strip()
            win_user = os.environ.get('WINDOWS_USERNAME') or subprocess.check_output(
                ['cmd.exe', '/c', 'echo %USERNAME%'], text=True
            ).strip()
            win_temp = f'/mnt/c/Users/{win_user}/AppData/Local/Temp/kivy_install.apk'
            subprocess.run(['cp', apk_file_path, win_temp], check=True)
            win_apk_path = subprocess.check_output(['wslpath', '-w', win_temp]).decode().strip()

        def _do_install(serial, reinstall=True):
            flags = ['-r'] if reinstall else []
            if win_path:
                return subprocess.run(
                    ['cmd.exe', '/c', win_path, '-s', serial, 'install'] + flags + [win_apk_path],
                    timeout=120, capture_output=True, text=True,
                )
            return subprocess.run(
                ['adb', '-s', serial, 'install'] + flags + [apk_file_path],
                check=False, timeout=120, capture_output=True, text=True,
            )

        try:
            print("in wsl or not?", in_wsl())
            if is_ksproject:
                # Force-stop old process so it releases port 8050 before new APK installs
                logging.info(f'Force-stopping old app on {device["model"]} | ({device["serial"]})')
                subprocess.run(
                    ['adb', '-s', device['serial'], 'shell', 'am', 'force-stop', package_name],
                    timeout=10
                )
                # Uninstall first to clear extracted Python asset cache on Android
                subprocess.run(
                    ['adb', '-s', device['serial'], 'uninstall', package_name],
                    timeout=30, capture_output=True
                )
                result = _do_install(device['serial'], reinstall=False)
            else:
                result = _do_install(device['serial'], reinstall=True)

            if win_temp:
                subprocess.run(['rm', '-f', win_temp], check=False)

            logging.info(f'Install stdout: {result.stdout.strip()}')
            logging.info(f'Install stderr: {result.stderr.strip()}')
            # ── signature mismatch detection (safety net if uninstall failed) ──
            if 'INSTALL_FAILED_UPDATE_INCOMPATIBLE' in result.stdout + result.stderr:
                logging.warning(f'Signature mismatch on {device["serial"]} — uninstalling old version')
                print(f'{yellow}⚠️  Signature mismatch on {device["model"]}. Uninstalling old version...{Style.RESET_ALL}')
                subprocess.run(
                    ['adb', '-s', device['serial'], 'uninstall', package_name],
                    timeout=30, capture_output=True
                )
                result = _do_install(device['serial'], reinstall=False)
                logging.info(f'Retry stdout: {result.stdout.strip()}')
            # ─────────────────────────────────────────────────────────────────

            if 'Success' not in result.stdout + result.stderr:
                logging.error(f'Install failed: {result.stdout} {result.stderr}')
                return

            logging.info(f'Starting app on {device["model"]} | ({device["serial"]})')
            try:
                subprocess.run([
                    'adb', '-s', device['serial'], 'shell', 'am', 'start',
                    '-n', f'{package_name}/{activity_class}',
                ], timeout=60)
            except subprocess.TimeoutExpired:
                logging.warning('am start timed out - app may still have launched, continuing...')


        except subprocess.TimeoutExpired:
            logging.error(f'adb install TIMED OUT after 120s for {device["serial"]}')
            return
        except subprocess.CalledProcessError as e:
            logging.error(f'adb install FAILED: {e.stderr}')
            return


# worked? unsure
# def deploy_app_to_devices(
#     target_devices: dict, apk_file_path: str, package_name: str
# ) -> None:
#     """
#     Installs APK and starts the application on target devices.

#     Args:
#         target_devices: Dictionary of filtered target devices
#         apk_file_path: Path to the APK file to install
#         package_name: Full package name for the application

#     Raises:
#         subprocess.CalledProcessError: If ADB commands fail
#     """
#     for device in target_devices.values():
#         logging.info(f'Installing APK on {device["model"]} | ({device["serial"]})')
#         subprocess.run(
#             ['adb', '-s', device['serial'], 'install', '-r', apk_file_path], check=True
#         )

#         logging.info(f'Starting app on {device["model"]} | ({device["serial"]})')
#         subprocess.run(
#             [
#                 'adb',
#                 '-s',
#                 device['serial'],
#                 'shell',
#                 'am',
#                 'start',
#                 '-n',
#                 f'{package_name}/org.kivy.android.PythonActivity',
#             ],
#             check=True,
#         )

def _clear_ksproject_cache() -> None:
    if not Path('pyproject.toml').exists():
        print(f'{red}pyproject.toml not found. Run kivy-reloader from your project root (the folder containing pyproject.toml).{Fore.RESET}')
        return
    root = Path('pyproject.toml').resolve().parent
    for rel in [
        'project_dist/gradle/app/src/main/assets/site-packages',
        'project_dist/gradle/site_packages',
    ]:
        path = root / rel
        if path.exists():
            shutil.rmtree(path)
            logging.info(f'Cleared ksproject cache: {path}')

def _gradle_clean() -> None:
    gradle_dir = Path('project_dist/gradle')
    gradlew = gradle_dir / 'gradlew'
    if not gradlew.exists():
        return
    logging.info('Running gradle clean')
    subprocess.run(['./gradlew', 'clean'], cwd=str(gradle_dir), check=False)


def run_ksproject_build() -> float:
    """Run ksproject android build instead of buildozer."""
    _clear_ksproject_cache()
    _gradle_clean()
    print(f'{yellow}Started compiling {app_name} with ksproject')
    notify(f'Compiling {app_name}', f'Compilation started at {time.strftime("%H:%M:%S")}')
    start_time = time.time()
    subprocess.run(['ksproject', 'android', 'build', 'debug'], check=True)
    compilation_time = round(time.time() - start_time, 2)
    print(f'{green}Compiled {app_name} successfully in {compilation_time}s')
    notify(f'Compiled {app_name} successfully', f'Compilation finished in {compilation_time} seconds')
    return compilation_time


def compile_app(buildozer_compiled: Event = None):
    """
    Orchestrates the complete app compilation and deployment process.

    This function coordinates platform validation, buildozer compilation,
    device filtering, and app deployment to connected Android devices.
    """
    # Step 1: Validate environment
    validate_compilation_environment()

    # detect ksproject and use it as the build backend if present
    _is_ksp = False
    try:
        import tomlkit
        with open('pyproject.toml', 'r', encoding='utf-8') as _f:
            _is_ksp = bool(tomlkit.load(_f).get('tool', {}).get('kivy-school', {}))
    except Exception:
        pass

    if _is_ksp:
        run_ksproject_build()
    else:
        # Step 2: Compile using buildozer
        run_buildozer_compilation()

    # Step 3: Get and filter target devices
    logging.info("compile app wait for auth")
    wait_for_authorization()
    if config.STREAM_USING == "WIFI":
        fetch_wifi_ip =True
    else:
        fetch_wifi_ip= False

    devices = get_connected_devices(fetch_wifi_ip)
    if not devices:
        logging.error('No connected devices found. APK will not be installed.')
        return

    target_devices = filter_target_devices(devices)

    # Step 4: Deploy to devices
    deploy_app_to_devices(
        target_devices, apk_path, package,
        activity_class='.MainActivity' if _is_ksp else 'org.kivy.android.PythonActivity',
        is_ksproject=_is_ksp,
    )

    buildozer_compiled.set()


def debug_and_livestream(buildozer_compiled: Event = None) -> None:
    """
    Executes `adb logcat` and `scrcpy` in parallel.
    Validates devices once at the start instead of in each subprocess.

    In CI environments, this function gracefully exits without device validation.
    """
    # Wait up to 30 seconds
    if not buildozer_compiled.wait(timeout=30):
        logging.error("Did not get buildozer completion")
        return
    logging.info(f"DEBUG RAN!0000!, {is_ci_environment()}")
    # Skip device operations in CI environments
    if is_ci_environment():
        logging.info('CI environment detected, skipping debug and livestream')
        return

    # Early validation - exit immediately if no devices
    validate_devices_connected()

    logging.info(f"DEBUG RAN!0000!")

    try:
        logging.info(f"DEBUG RAN!!")
        adb_logcat_ready = Event()
        adb_logcat = Process(target=debug, args=(adb_logcat_ready,))
        logging.info(f"LIVESTREAM RAN!!")
        scrcpy = Process(target=livestream, args=(adb_logcat_ready,))

        adb_logcat.start()
        scrcpy.start()
        # Wait for processes and handle termination
        try:
            adb_logcat.join()
            scrcpy.join()
        except KeyboardInterrupt:
            logging.info('Terminating processes due to user interrupt')
            terminate_processes(adb_logcat, scrcpy)

    except Exception as e:
        logging.error(f'Error in debug_and_livestream: {e}')
        sys.exit(1)


def debug(adb_logcat_ready: Event = None):
    """
    Debugging based on the streaming method.
    """
    logging.info(f"stream using? {config.STREAM_USING}")
    # clear auth to check again
    if config.STREAM_USING == 'USB':
        # if is_adb_listening():
        # Don't restart if server already reachable
        # if in_wsl():
        #     # host_ip = extract_ip(get_wsl_nameservers()[0])
        #     host_ip = get_wsl_host_ip()
        #     print("what is host ip", host_ip)
        #     listen_state = is_adb_listening(host=host_ip)
        # else:
        #     listen_state = is_adb_listening()
        # if listen_state:
        #     pass
        # else:
        #     start_adb_server()
        start_adb_server()
        clear_logcat()
        run_logcat(adb_logcat_ready = adb_logcat_ready)
    elif config.STREAM_USING == 'WIFI':
        debug_on_wifi(adb_logcat_ready)

def restart_adb_server():
    connection = True
    if in_wsl():
        connection = False
        kill_windows_adb()
    kill_adb_server(disconnect=connection)
    start_adb_server()
    sys.exit(0)

def kill_windows_adb():
    """Kill any orphaned adb.exe processes on the Windows side (WSL only)."""
    result = subprocess.run(
        ["tasklist.exe", "/FI", "IMAGENAME eq adb.exe", "/NH"],
        capture_output=True, text=True
    )
    print(f"[kill_windows_adb] tasklist output: {result.stdout.strip()}")
    if "adb.exe" in result.stdout:
        print("[kill_windows_adb] Found adb.exe, killing...")
        kill_result = subprocess.run(
            ["taskkill.exe", "/F", "/IM", "adb.exe"],
            capture_output=True, text=True
        )
        print(f"[kill_windows_adb] taskkill result: {kill_result.stdout.strip()} {kill_result.stderr.strip()}")
        time.sleep(0.5)
    else:
        print("[kill_windows_adb] No adb.exe found on Windows, skipping kill.")

def kill_adb_server(disconnect: bool = True):
    logging.info('Restarting adb server')
    if in_wsl():
        kill_windows_adb()
    try:
        if disconnect:
            subprocess.run(['adb', 'disconnect'], check=True, timeout=5)
        subprocess.run(['adb', 'kill-server'], check=True, timeout=5)
    except subprocess.TimeoutExpired:
        logging.warning('adb kill-server timed out, assuming server is already gone')
    except FileNotFoundError:
        print(
            f'{red}Please, install `scrcpy`: {yellow}https://github.com/Genymobile/scrcpy{Fore.RESET}'
        )

def start_adb_server():
    logging.info('Starting adb server')
    try:
        subprocess.run(['adb', 'start-server'], check=True)
    except FileNotFoundError:
        logging.error('adb not found')
        print(
            f'{red}Please, install `scrcpy`: {yellow}https://github.com/Genymobile/scrcpy{Fore.RESET}'
        )

def get_wsl_host_ip() -> str:
    """With mirrored networking, Windows host is localhost. 
    Fall back to nameserver parsing for NAT mode."""
    try:
        wslconfig_path = "/mnt/c/Users/" + os.environ.get("WINDOWS_USERNAME", "") + "/.wslconfig"
        # Try current user from environment
        import pathlib
        for candidate in pathlib.Path("/mnt/c/Users").iterdir():
            wslconfig = candidate / ".wslconfig"
            if wslconfig.exists() and "mirrored" in wslconfig.read_text().lower():
                return "127.0.0.1"
    except Exception:
        pass
    # NAT mode fallback
    nameservers = get_wsl_nameservers()
    return extract_ip(nameservers[0]) if nameservers else "127.0.0.1"

def adb_nodaemon_check():
    answer = False
    # Query Windows processes from WSL
    result = subprocess.run(
        ["cmd.exe", "/c", "wmic process where \"name='adb.exe'\" get CommandLine"],
        capture_output=True,
        text=True,
        timeout=5,
    )

    cmdlines = result.stdout.lower()
    # logging.info(f"logginf for now{cmdlines}")

    # Look for the special flags
    if "-a" in cmdlines and "nodaemon" in cmdlines and "server" in cmdlines:
        answer = True
    return answer

def start_nodaemon_adb_server():
    # this should only run in wsl tbh, so assume in wsb
    host_ip = get_wsl_host_ip()
    print("host ip resolved to:", host_ip)
    part1 = False
    part2 = False

    # part 1: check if adb is in nodaemon mode:
    part1 = adb_nodaemon_check()

    logging.info(f'adb in nodaemon server mode: {part1}')

    part2 = is_adb_listening(host=host_ip)
    logging.info(f'adb alive/listening: {part2}')

    # 1 -> and no 2 what does that mean (adb is in nodaemon mode but also not on SOMEHOW?)? restart server
    # 2 -> but not in nodaemon mode, immediately > restart server
    # 1 and 2 > do nothing
    if part1 and part2:
        wait_for_authorization() #wait for auth at the most
        pass


    # if is_adb_listening(host=host_ip):
    #     logging.info('adb server already running, skipping restart')
    #     wait_for_authorization()
    #     return True

    # logging.info('Starting fresh adb server')
    # kill_adb_server(disconnect=False)
    # wait_for_authorization()
    
    # now we're NOT in nodaemon and server is off, restart server
    try:
        adb_path = get_adb_windows_path()
        win_path = subprocess.check_output(["wslpath", "-w", adb_path]).decode().strip()
        cmd = ["cmd.exe", "/c", f"{win_path} -a -P {config.WIN_ADB_PORT} nodaemon server"]
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logging.info(f'started new adb server {" ".join(cmd)}')

        for _ in range(10):
            if is_adb_listening(host=host_ip):
                logging.info('adb server is up')
                # return True
                break
            time.sleep(0.5)
        # now also forward if usb mode
        logging.info(f'if check {config.STREAM_USING.lower().replace(" ", "")}, {config.STREAM_USING.lower().replace(" ", "") == "usb"}')
        PORT = config.RELOADER_PORT
        if config.STREAM_USING.lower().replace(" ", "") == "usb":
            wait_for_authorization()
            if not adb_has_forward(PORT):
                #no port forward means we forward now:
                adb_forward(PORT)
            else:
                logging.info(f'adb forwarded: {adb_has_forward(PORT)} config.RELOADER_PORT: {PORT}')
        return True

    except FileNotFoundError:
        logging.error('adb not found')

# WORKED ON WIN10
# def start_nodaemon_adb_server():
#     # Don't restart if server already reachable
#     host_ip = extract_ip(get_wsl_nameservers()[0])
#     print("what is host ip?", host_ip,get_wsl_nameservers(), type(get_wsl_nameservers()))
#     if is_adb_listening(host=host_ip):
#         logging.info('adb server already running, skipping restart')
#         wait_for_authorization()
#         return True
#     logging.info('Starting adb server')
#     kill_adb_server(disconnect = False)
#     try:
#         adb_port = getattr(config, "ADB_PORT", 5037)
#         adb_path = get_adb_windows_path()
#         # Convert /mnt/c/... to C:\... for cmd.exe
#         win_path = subprocess.check_output(["wslpath", "-w", adb_path]).decode().strip()
#         # cmd = ["cmd.exe", "/c", f"{win_path} -a -P {adb_port} nodaemon server"]
#         # cmd = ["cmd.exe", "/c", "start", f"{win_path} -a -P {adb_port} nodaemon server"]
#         cmd = ["cmd.exe", "/c", f"{win_path} -a -P {adb_port} nodaemon server"]
#         subprocess.Popen(
#             cmd,
#             stdout=subprocess.DEVNULL,  # don't buffer, just discard
#             stderr=subprocess.DEVNULL
#         )
#         logging.info(f'started new adb server {" ".join(cmd)}')

#         # Wait for it to actually bind
#         for _ in range(10):
#             if is_adb_listening(host=host_ip):
#                 logging.info('adb server is up')
#                 return True
#             time.sleep(0.5)
#     except FileNotFoundError:
#         logging.error('adb not found')
#         print(
#             f'{red}Please, install `scrcpy`: {yellow}https://github.com/Genymobile/scrcpy{Fore.RESET}'
#         )
#     # for _ in range(5): # Give it 5 seconds to bind
#     #     if is_adb_listening(host=host_ip):
#     #         # logging.info('adb server is up and listening')
#     #         wait_for_authorization()
#     #         return True
#     #     logging.debug("Server not ready yet, retrying...")
#     #     time.sleep(1)
#     # else:
#     #     logging.error('adb server never came up')
#     #     return False
    

# def start_nodaemon_adb_server():
#     logging.info('Starting adb server')
#     kill_adb_server(disconnect = False)
#     try:
#         adb_port = getattr(config, "ADB_PORT", 5037)
#         cmd = ["adb", "-a", "-P", str(adb_port), "nodaemon", "server"]
#         subprocess.Popen(
#             cmd,
#             stdout=subprocess.DEVNULL,  # don't buffer, just discard
#             stderr=subprocess.DEVNULL
#         )
#         logging.info(f'started new adb server {" ".join(cmd)}')
#     except FileNotFoundError:
#         logging.error('adb not found')
#         print(
#             f'{red}Please, install `scrcpy`: {yellow}https://github.com/Genymobile/scrcpy{Fore.RESET}'
#         )
#     host_ip = extract_ip(get_wsl_nameservers()[0])
#     print("whawwwwwwt", host_ip)
#     if not is_adb_listening(host = host_ip):
#         logging.error('adb server never came up')
#         return False
#     # logging.info('adb server is up and listening')
#     wait_for_authorization()
#     return True

def clear_device_logcat(device: dict) -> None:
    """
    Clears logcat for a specific device.

    Args:
        device: Device dictionary containing serial, model, and transport info

    Raises:
        subprocess.CalledProcessError: If adb logcat command fails
    """
    logging.debug(
        'Clearing logcat for '
        f'serial={device["serial"]} ({device["transport"]}, {device["model"]})'
    )
    subprocess.run(['adb', '-s', device['serial'], 'logcat', '-c'], check=True)
    logging.info(
        'Logcat cleared for '
        f'device {device["model"]} ({device["serial"]}) ({device["transport"]})'
    )


def clear_logcat():
    """
    Clears logcat for all connected devices, filtering duplicates by physical device.

    Uses the same device filtering logic as other functions to ensure
    logcat is cleared only once per physical device.
    """
    logging.info('Clearing logcat')

    try:
        if config.STREAM_USING == "WIFI":
            fetch_wifi_ip =True
        else:
            fetch_wifi_ip= False
        # wait_for_authorization()
        devices = get_connected_devices(fetch_wifi_ip)
        # Reuse existing device filtering logic
        filtered_devices = filter_target_devices(devices)
        logging.debug(f'Estimated physical devices connected: {len(filtered_devices)}')

        # Clear logcat for each filtered device
        for device in filtered_devices.values():
            clear_device_logcat(device)

    except FileNotFoundError:
        logging.error('adb not found')
        print(
            f'{red}Please, install `scrcpy`: {yellow}https://github.com/Genymobile/scrcpy{Fore.RESET}'
        )


def determine_wifi_targets(devices: list) -> tuple[list, list]:
    """
    Determines target USB devices and TCP/IP IPs based on configuration.

    Args:
        devices: List of connected device dictionaries

    Returns:
        tuple: (target_usb_devices, target_tcpip_ips)
    """

    logging.info(f"device list unfiltered, {str(devices)}")

    for d in devices:
        logging.info(f"RAW DEVICE: {repr(d)} keys={list(d.keys())}")


    # 1. Start from all USB and all TCP/IP devices
    usb_devices = [d for d in devices if d.get('transport') == 'usb']
    tcpip_devices = [d for d in devices if d.get('transport') == 'tcpip' and d.get('wifi_ip')]

    # 2. Normalize PHONE_IPS into a list of strings (or empty list)
    phone_ips_raw = getattr(config, "PHONE_IPS", None)
    if isinstance(phone_ips_raw, str):
        phone_ips = [ip.strip() for ip in phone_ips_raw.split(",") if ip.strip()]
    elif phone_ips_raw:
        phone_ips = list(phone_ips_raw)
    else:
        phone_ips = []

    if not phone_ips:
        # No filtering → use all USB devices, all known TCP/IP IPs
        target_usb_devices = usb_devices
        target_tcpip_ips = [d['wifi_ip'] for d in tcpip_devices]
    else:
        # Filter by PHONE_IPS
        target_usb_devices = [
            d for d in usb_devices
            if d.get('wifi_ip') in phone_ips or d.get('wifi_ip') is None
        ]
        target_tcpip_ips = [
            d['wifi_ip'] for d in tcpip_devices
            if d['wifi_ip'] in phone_ips
        ]

    logging.info(
        f"device list filtered, usb={target_usb_devices!r}, tcpip_ips={target_tcpip_ips!r}"
    )
    return target_usb_devices, target_tcpip_ips


# def determine_wifi_targets(devices: list) -> tuple[list, list]:
#     """
#     Determines target USB devices and TCP/IP IPs based on configuration.

#     Args:
#         devices: List of connected device dictionaries

#     Returns:
#         tuple: (target_usb_devices, target_tcpip_ips)
#     """

#     logging.info(f"device list unfiltered, {str(devices)}")

#     for d in devices:
#         logging.info(f"RAW DEVICE: {repr(d)} keys={list(d.keys())}")


#     if not config.PHONE_IPS:
#         target_usb_devices = [d for d in devices if d['transport'] == 'usb']
#         target_tcpip_ips = [
#             d['wifi_ip'] for d in devices if d['transport'] == 'tcpip' and d['wifi_ip']
#         ]
#     else:
#         target_usb_devices = [
#             d
#             for d in devices
#             if d['transport'] == 'usb' and d['wifi_ip'] in config.PHONE_IPS
#         ]
#         target_tcpip_ips = [
#             ip
#             for ip in config.PHONE_IPS
#             if any(d['wifi_ip'] == ip and d['transport'] == 'tcpip' for d in devices)
#         ]

#     logging.info(f"device list filtered, {str(target_usb_devices)}, {str(target_tcpip_ips)}")

#     return target_usb_devices, target_tcpip_ips


def wait_for_adb_online(serial: str = None, timeout: float = 10.0) -> bool:
    try:
        # This blocks natively until the state is 'device'
        # We use a timeout at the subprocess level to avoid hanging forever
        cmd = ["adb"]
        if serial != None:
            cmd += ["-s", serial]
        cmd.append("wait-for-device")
        subprocess.run(
            cmd,
            timeout=timeout,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return False


# def wait_for_adb_online(serial: str, timeout: float = 10.0) -> bool:
#     import subprocess, time

#     start = time.time()
#     while time.time() - start < timeout:
#         try:
#             state = subprocess.check_output(
#                 ["adb", "-s", serial, "get-state"],
#                 stderr=subprocess.DEVNULL
#             ).decode().strip()

#             if state == "device":
#                 return True

#         except Exception:
#             pass

#         # tiny wait to avoid hammering adb
#         time.sleep(0.1)

#     return False


def enable_tcpip_for_devices(usb_devices: list) -> list:
    converted_ips = []

    for device in usb_devices:
        usb_serial = device['serial']
        logging.info(f'Enabling tcpip mode for {device["model"]} ({usb_serial})')
        
        tcpip_command = ['adb', '-s', usb_serial, 'tcpip', f'{config.ADB_PORT}']
        logging.info(f"Running command: {' '.join(tcpip_command)}")
        subprocess.run(tcpip_command, check=True)

        # Wait for ADB to restart after tcpip
        if not wait_for_adb_online(usb_serial):
            logging.error(f"ADB did not come back online after tcpip for {usb_serial}")
            return []
        logging.info(f"wait_for_adb_online passed, {usb_serial}")

        # wait_for_ip_authorization(usb_serial)

        # # Raw check what ip addr returns
        # raw = subprocess.run(
        #     ['adb', '-s', usb_serial, 'shell', 'ip', '-f', 'inet', 'addr', 'show'],
        #     capture_output=True, text=True
        # )
        # logging.info(f'Raw ip addr stdout: {repr(raw.stdout[:200])}')
        # logging.info(f'Raw ip addr stderr: {repr(raw.stderr[:200])}')

        # Now it's safe to query WiFi IP
        if not device['wifi_ip']:
            device['wifi_ip'] = get_wifi_ip(usb_serial)
        
        if not device['wifi_ip']:
            print(f'{red}Cannot switch to WiFi mode - phone WiFi is off or not connected.')
            print(f'{yellow}Please enable WiFi on your phone and try again.')
            return converted_ips  # bail out early

        ip_with_port = f'{device["wifi_ip"]}:{config.ADB_PORT}'
        logging.info(f'Connecting to {ip_with_port}')

        try:
            subprocess.run(['adb', 'connect', ip_with_port])
            logging.info('Please tap Allow on your phone...')
            authorized = wait_for_ip_authorization(ip_with_port, timeout=30)
            
            if not authorized:
                logging.error(f'Failed to authorize {ip_with_port}')
                continue

            # Validate it's the same physical device
            try:
                wifi_serial = subprocess.check_output(
                    ['adb', '-s', ip_with_port, 'shell', 'getprop', 'ro.serialno'],
                    stderr=subprocess.DEVNULL
                ).decode().strip()

                if wifi_serial != usb_serial:
                    logging.error(f'Wrong device! Expected {usb_serial}, got {wifi_serial}')
                    continue

                logging.info(f'Device identity confirmed: {wifi_serial}')
            except Exception as e:
                logging.warning(f'Could not verify device serial: {e}')

            converted_ips.append(device['wifi_ip'])

        except FileNotFoundError:
            logging.error('adb not found')
            print(f'{red}Please, install `scrcpy`: {yellow}https://github.com/Genymobile/scrcpy{Fore.RESET}')

    return converted_ips


# def enable_tcpip_for_devices(usb_devices: list) -> list:
#     """
#     Enables TCP/IP mode for USB devices and connects to them.

#     Args:
#         usb_devices: List of USB device dictionaries

#     Returns:
#         list: IP addresses of devices successfully converted to TCP/IP

#     Raises:
#         subprocess.CalledProcessError: If ADB commands fail
#     """
#     converted_ips = []

#     for device in usb_devices:
#         logging.info(f'Enabling tcpip mode for {device["model"]} ({device["serial"]})')
#         tcpip_command = ['adb', '-s', device['serial'], 'tcpip', f'{config.ADB_PORT}']
#         logging.info(f"Running command: {' '.join(tcpip_command)}")
#         subprocess.run(
#             tcpip_command, check=True
#         )

#         if not device['wifi_ip']:
#             device['wifi_ip'] = get_wifi_ip(device['serial'])

#         ip_with_port = f'{device["wifi_ip"]}:{config.ADB_PORT}'
#         logging.info(f'Connecting to {ip_with_port}')

#         try:
#             subprocess.run(['adb', 'connect', ip_with_port])  # no check=True, auth fails first
#             logging.info('Please tap Allow on your phone...')
#             authorized = wait_for_ip_authorization(ip_with_port, timeout=30)
#             if authorized:
#                 converted_ips.append(device['wifi_ip'])
#             else:
#                 logging.error(f'Failed to authorize {ip_with_port}')
#         except FileNotFoundError:
#             logging.error('adb not found')
#             print(
#                 f'{red}Please, install `scrcpy`: {yellow}https://github.com/Genymobile/scrcpy{Fore.RESET}'
#             )

#     return converted_ips


def start_logcat_for_ips(ip_addresses: list) -> None:
    """
    Starts logcat processes for each IP address in separate threads.

    Args:
        ip_addresses: List of IP addresses to start logcat for
    """
    for ip in ip_addresses:
        thread = Thread(target=run_logcat, args=(ip,))
        thread.start()


def debug_on_wifi(adb_logcat_ready: Event = None):
    """
    Orchestrates WiFi debugging by enabling TCP/IP mode and starting logcat.

    This function coordinates device targeting, TCP/IP conversion, and
    logcat thread management for WiFi-based debugging.
    """
    logging.info('Switching ADB to TCP/IP mode...')
    # wait_for_authorization()
    if config.STREAM_USING == "WIFI":
        fetch_wifi_ip =True
    else:
        fetch_wifi_ip= False
    devices = get_connected_devices(fetch_wifi_ip)
    logging.debug(f'Connected devices: {devices}')

    # Step 1: Determine target devices and IPs
    target_usb_devices, target_tcpip_ips = determine_wifi_targets(devices)
    
    logging.info(f"# Step 2: Convert USB devices to TCP/IP and get their IPs {str(target_usb_devices)}, {str(target_tcpip_ips)}")
    converted_ips = enable_tcpip_for_devices(target_usb_devices)

    # Step 3: Combine existing TCP/IP IPs with newly converted ones
    all_target_ips = target_tcpip_ips + [
        ip for ip in converted_ips if ip not in target_tcpip_ips
    ]

    if adb_logcat_ready is not None and all_target_ips:
        adb_logcat_ready.set()  # set AFTER auth, before logcat starts

    # Step 4: Start logcat for all target IPs
    start_logcat_for_ips(all_target_ips)


def handle_logcat_connection(ip: str) -> None:
    """
    Handles ADB connection to a specific IP address for logcat.

    Args:
        ip: IP address to connect to

    Raises:
        subprocess.CalledProcessError: If ADB connection fails
    """
    try:
        subprocess.run(['adb', 'connect', f'{ip}:{config.ADB_PORT}'], check=True)
    except FileNotFoundError:
        logging.error('adb not found')
        print(
            f'{red}Please, install `scrcpy`: {yellow}https://github.com/Genymobile/scrcpy{Fore.RESET}'
        )


def build_logcat_command(ip: str = None) -> list:
    """
    Builds the logcat command based on IP or connected devices.

    Args:
        ip: Optional IP address for TCP/IP connection

    Returns:
        list: Command array for logcat or empty list if multiple devices
    """
    if ip:
        return ['adb', '-s', f'{ip}:{config.ADB_PORT}', 'logcat']

    # wait_for_authorization()
    # Handle USB/local device connection
    if config.STREAM_USING == "WIFI":
        fetch_wifi_ip =True
    else:
        fetch_wifi_ip= False
    connected = get_connected_devices(fetch_wifi_ip)

    if not connected:
        logging.error('No devices connected.')
        return []

    # Prefer USB if available
    serial = next(
        (d['serial'] for d in connected if d['transport'] == 'usb'),
        connected[0]['serial'],  # fallback
    )
    return ['adb', '-s', serial, 'logcat']


def build_filter_command() -> list:
    """
    Builds platform-specific filter command for logcat output.

    Returns:
        list: Filter command array based on current platform
    """
    if platform == 'win':
        services = [f'{SERVICE_NAME}:V' for SERVICE_NAME in config.SERVICE_NAMES]
        return ['-v', 'time', '-s', 'python:V'] + services + ['*:S']
    else:
        services = '|'.join(config.SERVICE_NAMES)
        watch = 'I python' if not services else f'I python|{services}'
        return ['grep', '-E', watch]


def start_logcat_processes(logcat_cmd: list, filter_cmd: list) -> tuple:
    """
    Starts logcat and filter processes based on platform.

    Args:
        logcat_cmd: Command array for logcat
        filter_cmd: Command array for filtering

    Returns:
        tuple: (logcat_process, filter_process) - filter_process may be None on Windows

    Raises:
        subprocess.CalledProcessError: If process creation fails
    """
    global logcat_proc, filter_proc

    try:
        if platform == 'win':
            logcat_proc = subprocess.Popen(logcat_cmd + filter_cmd)
            filter_proc = None
        else:
            logcat_proc = subprocess.Popen(logcat_cmd, stdout=subprocess.PIPE)
            filter_proc = subprocess.Popen(filter_cmd, stdin=logcat_proc.stdout)

        return logcat_proc, filter_proc

    except FileNotFoundError:
        logging.error('adb not found')
        print(
            f'{red}Please, install `scrcpy`: {yellow}https://github.com/Genymobile/scrcpy{Fore.RESET}'
        )
        return None, None


def run_logcat(IP=None, adb_logcat_ready: Event = None, *args):
    """
    Orchestrates logcat execution with connection, command building,
    and process management.

    Args:
        IP: Optional IP address for WiFi debugging
        *args: Additional arguments (unused but kept for compatibility)
    """
    logging.info('Preparing to run logcat')

    # Step 1: Handle connection if IP is provided
    if IP:
        handle_logcat_connection(IP)

    # Step 2: Build logcat command
    logcat_cmd = build_logcat_command(IP)
    if not logcat_cmd:
        return

    # Step 3: Build filter command
    filter_cmd = build_filter_command()

    # Step 4: Start processes
    # logging.info('Starting logcat')
    # start_logcat_processes(logcat_cmd, filter_cmd)
    # adb_logcat_ready.set()
    logging.info('Starting logcat')
    logcat_proc, filter_proc = start_logcat_processes(logcat_cmd, filter_cmd)

    # Signal ready BEFORE blocking on wait
    if adb_logcat_ready is not None:
        adb_logcat_ready.set()

    # Now block waiting for processes
    if logcat_proc:
        logcat_proc.wait()


def livestream(adb_logcat_ready: Event = None):
    """
    Handles the livestream process.
    """
    # # clear auth to check again
    # if config.STREAM_USING == 'WIFI':
    #     logging.info('Waiting for WiFi authorization before starting scrcpy...')
    #     # wait_for_authorization()   # blocks until event is set
    # wait for adb logcat before running
    
    # Wait up to 30 seconds
    if not adb_logcat_ready.wait(timeout=30):
        logging.error("Logcat did not become ready in time")
        return

    try:
        import psutil
        for proc in psutil.process_iter():
            try:
                if proc.name() == 'scrcpy':
                    logging.info('scrcpy already running')
                    return
            except psutil.NoSuchProcess:
                logging.error('Error while trying to find scrcpy process')
    except ImportError:
        pass

    start_scrcpy()


def add_window_options(scrcpy_cmd: list) -> None:
    """Add window configuration options to scrcpy command."""
    scrcpy_cmd.extend(['--window-x', str(config.WINDOW_X)])
    scrcpy_cmd.extend(['--window-y', str(config.WINDOW_Y)])
    scrcpy_cmd.extend(['--window-width', str(config.WINDOW_WIDTH)])

    if config.WINDOW_HEIGHT > 0:
        scrcpy_cmd.extend(['--window-height', str(config.WINDOW_HEIGHT)])

    if config.WINDOW_TITLE:
        scrcpy_cmd.append(f'--window-title={config.WINDOW_TITLE}')


def add_display_options(scrcpy_cmd: list) -> None:
    """Add display configuration options to scrcpy command."""
    if config.FULLSCREEN:
        scrcpy_cmd.append('--fullscreen')
    if config.WINDOW_BORDERLESS:
        scrcpy_cmd.append('--window-borderless')
    if config.ALWAYS_ON_TOP:
        scrcpy_cmd.append('--always-on-top')
    if config.DISPLAY_ORIENTATION != 0:
        scrcpy_cmd.extend(['--display-orientation', str(config.DISPLAY_ORIENTATION)])
    if config.CROP_AREA:
        scrcpy_cmd.extend(['--crop', config.CROP_AREA])


def add_performance_options(scrcpy_cmd: list) -> None:
    """Add performance and quality options to scrcpy command."""
    if config.MAX_SIZE > 0:
        scrcpy_cmd.extend(['--max-size', str(config.MAX_SIZE)])
    if config.MAX_FPS > 0:
        scrcpy_cmd.extend(['--max-fps', str(config.MAX_FPS)])
    if config.VIDEO_BIT_RATE != '8M':
        scrcpy_cmd.extend(['--video-bit-rate', config.VIDEO_BIT_RATE])
    if config.PRINT_FPS:
        scrcpy_cmd.append('--print-fps')

    # Performance optimizations (especially important for VMs/VirtualBox)
    if config.RENDER_DRIVER:
        print('aisuhdauisdhiuashduis')
        scrcpy_cmd.extend(['--render-driver', config.RENDER_DRIVER])
    if config.NO_MOUSE_HOVER:
        scrcpy_cmd.append('--no-mouse-hover')
    if config.DISABLE_SCREENSAVER:
        scrcpy_cmd.append('--disable-screensaver')


def add_audio_options(scrcpy_cmd: list) -> None:
    """Add audio configuration options to scrcpy command."""
    if config.NO_AUDIO:
        scrcpy_cmd.append('--no-audio')
    elif config.NO_AUDIO_PLAYBACK:
        scrcpy_cmd.append('--no-audio-playback')

    if not config.NO_AUDIO:
        if config.AUDIO_SOURCE != 'output':
            scrcpy_cmd.extend(['--audio-source', config.AUDIO_SOURCE])
        if config.AUDIO_BIT_RATE != '128K':
            scrcpy_cmd.extend(['--audio-bit-rate', config.AUDIO_BIT_RATE])


def add_control_options(scrcpy_cmd: list) -> None:
    """Add device control options to scrcpy command."""
    if config.TURN_SCREEN_OFF:
        scrcpy_cmd.append('--turn-screen-off')
    if config.STAY_AWAKE:
        scrcpy_cmd.append('--stay-awake')
    if config.SHOW_TOUCHES:
        scrcpy_cmd.append('--show-touches')
    if config.NO_CONTROL:
        scrcpy_cmd.append('--no-control')


def add_advanced_options(scrcpy_cmd: list) -> None:
    """Add advanced configuration options to scrcpy command."""
    if config.KILL_ADB_ON_CLOSE:
        scrcpy_cmd.append('--kill-adb-on-close')
    if config.POWER_OFF_ON_CLOSE:
        scrcpy_cmd.append('--power-off-on-close')
    if config.TIME_LIMIT > 0:
        scrcpy_cmd.extend(['--time-limit', str(config.TIME_LIMIT)])
    if config.SCREEN_OFF_TIMEOUT > 0:
        scrcpy_cmd.extend(['--screen-off-timeout', str(config.SCREEN_OFF_TIMEOUT)])
    if config.SHORTCUT_MOD != 'lalt,lsuper':
        scrcpy_cmd.extend(['--shortcut-mod', config.SHORTCUT_MOD])


def add_recording_options(scrcpy_cmd: list) -> None:
    """Add recording options to scrcpy command."""
    if config.RECORD_SESSION and config.RECORD_FILE_PATH:
        scrcpy_cmd.extend(['--record', config.RECORD_FILE_PATH])


def add_connection_options(scrcpy_cmd: list) -> None:
    """Add connection method options to scrcpy command."""
    if config.STREAM_USING == 'USB':
        scrcpy_cmd.append('-d')
    elif config.STREAM_USING == 'WIFI':
        scrcpy_cmd.append('-e')


def build_scrcpy_command() -> list:
    """
    Builds the scrcpy command with all configuration options.

    Returns:
        list: Complete scrcpy command array with all configured options
    """
    scrcpy_cmd = ['scrcpy']

    # Add configuration options in logical groups
    add_window_options(scrcpy_cmd)
    add_display_options(scrcpy_cmd)
    add_performance_options(scrcpy_cmd)
    add_audio_options(scrcpy_cmd)
    add_control_options(scrcpy_cmd)
    add_advanced_options(scrcpy_cmd)
    add_recording_options(scrcpy_cmd)
    add_connection_options(scrcpy_cmd) 

    return scrcpy_cmd


def execute_scrcpy_process(command: list) -> subprocess.Popen:
    """
    Executes the scrcpy process and waits for completion.

    Args:
        command: Complete scrcpy command array

    Returns:
        subprocess.Popen: The scrcpy process object

    Raises:
        FileNotFoundError: If scrcpy executable is not found
    """
    try:
        scrcpy_proc = subprocess.Popen(command, stdin=subprocess.DEVNULL)
        scrcpy_proc.wait()
        return scrcpy_proc
    except FileNotFoundError:
        logging.error('scrcpy not found')
        print(
            f'{red}Please, install `scrcpy`: {yellow}https://github.com/Genymobile/scrcpy{Fore.RESET}'
        )
        raise


def cleanup_processes(*processes: subprocess.Popen) -> None:
    """
    Performs cleanup operations including terminal restoration and process termination.

    Args:
        *processes: Variable number of process objects to terminate
    """
    _restore_terminal()
    for proc in processes:
        if proc is not None:
            _terminate(proc)


def start_scrcpy():
    """
    Orchestrates scrcpy screen mirroring with command building, execution, and cleanup.

    This function coordinates command construction, process execution, and proper
    cleanup of resources.
    """
    logging.info('Starting scrcpy')

    # Step 1: Build scrcpy command
    scrcpy_cmd = build_scrcpy_command()
    logging.info(f'scrcpy command: {scrcpy_cmd}')
    # import time

    # # after enabling tcpip
    # time.sleep(1)


    # Step 2: Execute scrcpy process with cleanup
    scrcpy_proc = None
    try:
        scrcpy_proc = execute_scrcpy_process(scrcpy_cmd)
    finally:
        cleanup_processes(filter_proc, logcat_proc, scrcpy_proc)


def create_aab():
    """
    Creates an Android App Bundle (AAB) for production release.

    Uses buildozer to compile the app in release mode with proper timing
    and notifications. Exits the application after completion.

    Raises:
        subprocess.CalledProcessError: If buildozer compilation fails
    """
    print(f'{yellow} Started creating aab')
    notify(
        f'Compile production: {app_name}',
        f'Compilation started at {time.strftime("%H:%M:%S")}',
    )

    start_time = time.time()
    try:
        subprocess.run(['buildozer', '-v', 'android', 'release'], check=True)
    except subprocess.CalledProcessError as e:
        logging.error(f'AAB compilation failed: {e}')
        print(f'{red} Failed to create AAB')
        sys.exit(1)

    end_time = time.time()
    compilation_time = round(end_time - start_time, 2)

    notify(
        f'Compiled {app_name} successfully',
        f'Compilation finished in {compilation_time} seconds',
    )
    print(f'{green} Finished compilation')
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
        option_text = f'[{green}x{Style.RESET_ALL}] {green}'
    else:
        option_text = '[ ] '

    option_text = f'{option_text}{option}{Style.RESET_ALL}'
    typer.echo(option_text)


def render_option_menu(current_selection: str) -> None:
    """
    Renders the option menu with the current selection highlighted.

    Args:
        current_selection: Currently selected option string
    """
    #typer.clear()
    typer.echo('\nSelect one of the 4 options below:\n')

    development_options = compiler_options[:2]
    production_option = compiler_options[2]
    fix_option = compiler_options[3]

    # Render Development section
    typer.echo(f'🛠️  {yellow}Development{Style.RESET_ALL} ')
    for option in development_options:
        highlight_selected_option(option)

    # Render Production section
    typer.echo(f'\n📦 {yellow}Production{Style.RESET_ALL} ')
    highlight_selected_option(production_option)

    # Render Fix section
    typer.echo(f'\n🔄 {yellow}Fix{Style.RESET_ALL}')
    highlight_selected_option(fix_option)
    typer.echo('')


def handle_keyboard_input() -> str:
    """
    Captures and returns a keyboard input from the user.

    Returns:
        str: The pressed key
    """
    return readchar.readkey()


def update_selected_option(key: str, current_option: str) -> str:
    """
    Updates the selected option based on keyboard input.

    Args:
        key: The pressed key
        current_option: Currently selected option

    Returns:
        str: New selected option after navigation
    """
    if key == readchar.key.DOWN:
        selected_index = compiler_options.index(current_option)
        next_index = (selected_index + 1) % len(compiler_options)
        return compiler_options[next_index]
    elif key == readchar.key.UP:
        selected_index = compiler_options.index(current_option)
        prev_index = (selected_index - 1) % len(compiler_options)
        return compiler_options[prev_index]

    return current_option


def execute_selected_option(option: str) -> None:
    """
    Executes the action associated with the selected option.

    Args:
        option: The selected option string
    """
    #typer.clear()
    print(f'{yellow} Selected option: {green}{option}')
    option_index = str(compiler_options.index(option) + 1)
    #typer.clear()
    select_option(option_index, app_name)


def start():
    """
    Orchestrates the interactive menu system with rendering, input handling,
    and navigation.

    This function coordinates menu display, keyboard input processing,
    option navigation, and action execution in a clean event loop.
    """
    global selected_option

    navigate_compiler_options()

    while True:
        # Step 1: Render the current menu state
        render_option_menu(selected_option)

        # Step 2: Get user input
        key = handle_keyboard_input()

        # Step 3: Handle navigation keys
        if key in {readchar.key.DOWN, readchar.key.UP}:
            selected_option = update_selected_option(key, selected_option)
            continue

        # Step 4: Handle exit keys
        elif key in {readchar.key.LEFT, 'q', readchar.key.ESC * 2}:
            sys.exit()

        # Step 5: Handle selection keys
        elif key in {'\n', readchar.key.RIGHT, readchar.key.ENTER}:
            execute_selected_option(selected_option)
            break
