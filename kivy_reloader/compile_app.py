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


def validate_devices_connected() -> list:
    """
    Validates that devices are connected and returns them.

    Returns:
        list: Connected devices

    Raises:
        SystemExit: If no devices are connected
    """
    devices = get_connected_devices()
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
app_name = get_app_name()
package = get_package_name()
apk_path = get_apk_path()

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
    try:
        if option == '1':
            compile_app()
            debug_and_livestream()
        elif option == '2':
            debug_and_livestream()
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


def deploy_app_to_devices(
    target_devices: dict, apk_file_path: str, package_name: str
) -> None:
    """
    Installs APK and starts the application on target devices.

    Args:
        target_devices: Dictionary of filtered target devices
        apk_file_path: Path to the APK file to install
        package_name: Full package name for the application

    Raises:
        subprocess.CalledProcessError: If ADB commands fail
    """
    for device in target_devices.values():
        logging.info(f'Installing APK on {device["model"]} | ({device["serial"]})')
        subprocess.run(
            ['adb', '-s', device['serial'], 'install', '-r', apk_file_path], check=True
        )

        logging.info(f'Starting app on {device["model"]} | ({device["serial"]})')
        subprocess.run(
            [
                'adb',
                '-s',
                device['serial'],
                'shell',
                'am',
                'start',
                '-n',
                f'{package_name}/org.kivy.android.PythonActivity',
            ],
            check=True,
        )


def compile_app():
    """
    Orchestrates the complete app compilation and deployment process.

    This function coordinates platform validation, buildozer compilation,
    device filtering, and app deployment to connected Android devices.
    """
    # Step 1: Validate environment
    validate_compilation_environment()

    # Step 2: Compile using buildozer
    run_buildozer_compilation()

    # Step 3: Get and filter target devices
    devices = get_connected_devices()
    if not devices:
        logging.error('No connected devices found. APK will not be installed.')
        return

    target_devices = filter_target_devices(devices)

    # Step 4: Deploy to devices
    deploy_app_to_devices(target_devices, apk_path, package)


def debug_and_livestream() -> None:
    """
    Executes `adb logcat` and `scrcpy` in parallel.
    Validates devices once at the start instead of in each subprocess.

    In CI environments, this function gracefully exits without device validation.
    """
    # Skip device operations in CI environments
    if is_ci_environment():
        logging.info('CI environment detected, skipping debug and livestream')
        return

    # Early validation - exit immediately if no devices
    validate_devices_connected()

    try:
        adb_logcat = Process(target=debug)
        scrcpy = Process(target=livestream)

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


def debug():
    """
    Debugging based on the streaming method.
    """
    if config.STREAM_USING == 'USB':
        start_adb_server()
        clear_logcat()
        run_logcat()
    elif config.STREAM_USING == 'WIFI':
        debug_on_wifi()


def restart_adb_server():
    kill_adb_server()
    start_adb_server()
    sys.exit(0)


def kill_adb_server():
    logging.info('Restarting adb server')
    try:
        subprocess.run(['adb', 'disconnect'], check=True)
        subprocess.run(['adb', 'kill-server'], check=True)
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
        devices = get_connected_devices()
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
    if not config.PHONE_IPS:
        target_usb_devices = [d for d in devices if d['transport'] == 'usb']
        target_tcpip_ips = [
            d['wifi_ip'] for d in devices if d['transport'] == 'tcpip' and d['wifi_ip']
        ]
    else:
        target_usb_devices = [
            d
            for d in devices
            if d['transport'] == 'usb' and d['wifi_ip'] in config.PHONE_IPS
        ]
        target_tcpip_ips = [
            ip
            for ip in config.PHONE_IPS
            if any(d['wifi_ip'] == ip and d['transport'] == 'tcpip' for d in devices)
        ]

    return target_usb_devices, target_tcpip_ips


def enable_tcpip_for_devices(usb_devices: list) -> list:
    """
    Enables TCP/IP mode for USB devices and connects to them.

    Args:
        usb_devices: List of USB device dictionaries

    Returns:
        list: IP addresses of devices successfully converted to TCP/IP

    Raises:
        subprocess.CalledProcessError: If ADB commands fail
    """
    converted_ips = []

    for device in usb_devices:
        logging.info(f'Enabling tcpip mode for {device["model"]} ({device["serial"]})')
        subprocess.run(
            ['adb', '-s', device['serial'], 'tcpip', f'{config.ADB_PORT}'], check=True
        )

        if not device['wifi_ip']:
            device['wifi_ip'] = get_wifi_ip(device['serial'])

        ip_with_port = f'{device["wifi_ip"]}:{config.ADB_PORT}'
        logging.info(f'Connecting to {ip_with_port}')

        try:
            subprocess.run(['adb', 'connect', ip_with_port], check=True)
            converted_ips.append(device['wifi_ip'])
        except FileNotFoundError:
            logging.error('adb not found')
            print(
                f'{red}Please, install `scrcpy`: {yellow}https://github.com/Genymobile/scrcpy{Fore.RESET}'
            )

    return converted_ips


def start_logcat_for_ips(ip_addresses: list) -> None:
    """
    Starts logcat processes for each IP address in separate threads.

    Args:
        ip_addresses: List of IP addresses to start logcat for
    """
    for ip in ip_addresses:
        thread = Thread(target=run_logcat, args=(ip,))
        thread.start()


def debug_on_wifi():
    """
    Orchestrates WiFi debugging by enabling TCP/IP mode and starting logcat.

    This function coordinates device targeting, TCP/IP conversion, and
    logcat thread management for WiFi-based debugging.
    """
    logging.info('Switching ADB to TCP/IP mode...')
    devices = get_connected_devices()
    logging.debug(f'Connected devices: {devices}')

    # Step 1: Determine target devices and IPs
    target_usb_devices, target_tcpip_ips = determine_wifi_targets(devices)

    # Step 2: Convert USB devices to TCP/IP and get their IPs
    converted_ips = enable_tcpip_for_devices(target_usb_devices)

    # Step 3: Combine existing TCP/IP IPs with newly converted ones
    all_target_ips = target_tcpip_ips + [
        ip for ip in converted_ips if ip not in target_tcpip_ips
    ]

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

    # Handle USB/local device connection
    connected = get_connected_devices()

    unique_devices = {
        (d['wifi_ip'], d['model']) for d in connected if d['wifi_ip'] != 'unknown'
    }

    if len(unique_devices) == 1:
        # Prefer USB if available
        serial = next(
            (d['serial'] for d in connected if d['transport'] == 'usb'),
            connected[0]['serial'],  # fallback
        )
        return ['adb', '-s', serial, 'logcat']
    else:
        logging.error('Multiple devices connected. Specify IP or disambiguate.')
        return []


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


def run_logcat(IP=None, *args):
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
    logging.info('Starting logcat')
    start_logcat_processes(logcat_cmd, filter_cmd)


def livestream():
    """
    Handles the livestream process.
    """
    if config.STREAM_USING == 'WIFI':
        time.sleep(3)

    for proc in psutil.process_iter():
        try:
            if proc.name() == 'scrcpy':
                logging.info('scrcpy already running')
                return
        except psutil.NoSuchProcess:
            logging.error('Error while trying to find scrcpy process')

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
    typer.clear()
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
    typer.clear()
    print(f'{yellow} Selected option: {green}{option}')
    option_index = str(compiler_options.index(option) + 1)
    typer.clear()
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
