import ipaddress
import logging
import os
import re
import subprocess
from fnmatch import fnmatch
from typing import Optional
import time
import platform
import trio
import base64
import socket

from kivy_reloader.config import config

try:
    from colorama import Fore, init
    init(autoreset=True)
    red = Fore.RED
    green = Fore.GREEN
    yellow = Fore.YELLOW
    white = Fore.WHITE
except ImportError:
    # colorama not available on Android
    red = green = yellow = white = ''

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
base_dir = os.getcwd()


def get_auto_reloader_paths():
    """
    Returns a list of paths to watch for changes,
    based on the config.py file
    """

    def create_path_tuples(paths, recursive):
        return [(os.path.join(base_dir, x), {'recursive': recursive}) for x in paths]

    def should_exclude_directory(dir_path):
        """Check if a directory should be excluded based on DO_NOT_WATCH_PATTERNS"""
        dir_name = os.path.basename(dir_path)

        for pattern in config.DO_NOT_WATCH_PATTERNS:
            if pattern.startswith('*') and pattern.endswith('*'):
                substring = pattern.strip('*')
                if substring in dir_path or substring in dir_name:
                    return True
            elif fnmatch(dir_path, pattern):
                return True
            elif fnmatch(dir_name, pattern):
                return True

        return False

    def expand_current_directory():
        """
        Instead of watching '.' recursively, enumerate subdirectories
        and exclude unwanted ones
        """
        directories_to_watch = [(base_dir, {'recursive': False})]  # watch root dir files

        # Get all subdirectories in the current directory
        try:
            for item in os.listdir(base_dir):
                item_path = os.path.join(base_dir, item)
                if os.path.isdir(item_path):
                    # Check if this directory should be excluded
                    if not should_exclude_directory(item_path):
                        directories_to_watch.append((item_path, {'recursive': True}))
        except OSError:
            # Fallback to watching current directory
            directories_to_watch.append((base_dir, {'recursive': True}))

        return directories_to_watch

    missing_files = validate_watched_files()
    if missing_files:
        logging.error(
            f'Found {len(missing_files)} missing files in watched paths: {missing_files}'
        )
        logging.error(
            'Please fix your WATCHED_FILES or FULL_RELOAD_FILES in kivy-reloader.toml'
        )
        raise FileNotFoundError(
            f'Missing files in watched paths: {missing_files}. '
            'Fix your WATCHED_FILES or FULL_RELOAD_FILES in kivy-reloader.toml'
        )

    non_recursive_paths = (
        config.WATCHED_FILES + config.WATCHED_FOLDERS + config.FULL_RELOAD_FILES
    )
    recursive_paths = config.WATCHED_FOLDERS_RECURSIVELY

    # Check if user wants to watch current directory recursively
    if '.' in recursive_paths:
        # Remove '.' from the list and expand it to individual directories
        other_recursive_paths = [p for p in recursive_paths if p != '.']
        expanded_directories = expand_current_directory()
        other_recursive_tuples = create_path_tuples(other_recursive_paths, True)
        recursive_tuples = expanded_directories + other_recursive_tuples

        # IMPORTANT: Remove "." from non_recursive_paths to avoid duplicate watchers
        # when using smart directory expansion
        non_recursive_paths = [p for p in non_recursive_paths if p != '.']
    else:
        recursive_tuples = create_path_tuples(recursive_paths, True)

    from kivy.utils import platform

    if platform == 'win':
        return create_path_tuples(non_recursive_paths, False) + recursive_tuples
    else:
        return create_path_tuples(non_recursive_paths, True) + recursive_tuples


def validate_watched_files():
    """
    Check if all files in WATCHED_FILES and FULL_RELOAD_FILES exist.
    Logs warnings for missing files and filters out invalid entries.
    """
    missing_files = []

    # Check WATCHED_FILES
    for file_path in config.WATCHED_FILES:
        # Skip empty strings and whitespace-only entries
        if not file_path or not file_path.strip():
            logging.warning(
                f'Empty or whitespace-only entry in WATCHED_FILES: "{file_path}". '
                'Remove it'
            )
            missing_files.append(file_path)
            continue

        full_path = os.path.join(base_dir, file_path.strip())
        if not os.path.exists(full_path):
            missing_files.append(file_path)
            logging.warning(f'Watched file does not exist: {file_path}')
        elif os.path.isdir(full_path):
            logging.warning(
                f'WATCHED_FILES entry is a directory, not a file: {file_path}'
            )
            missing_files.append(file_path)

    # Check FULL_RELOAD_FILES
    for file_path in config.FULL_RELOAD_FILES:
        # Skip empty strings and whitespace-only entries
        if not file_path or not file_path.strip():
            logging.warning(
                f'Empty or whitespace-only entry in FULL_RELOAD_FILES: "{file_path}"'
            )
            missing_files.append(file_path)
            continue

        full_path = os.path.join(base_dir, file_path.strip())
        if not os.path.exists(full_path):
            missing_files.append(file_path)
            logging.warning(f'Full reload file does not exist: {file_path}')
        elif os.path.isdir(full_path):
            logging.warning(
                f'FULL_RELOAD_FILES entry is a directory, not a file: {file_path}'
            )
            missing_files.append(file_path)

    if missing_files:
        logging.warning(f'Found {len(missing_files)} invalid/missing files')
    else:
        logging.info('All watched files exist ✓')

    return missing_files


def find_kv_files_in_folder(folder):
    kv_files = []
    for root, _, files in os.walk(os.path.join(base_dir, folder)):
        # Check if the directory path should be excluded
        should_exclude_dir = False
        for pattern in config.DO_NOT_WATCH_PATTERNS:
            if fnmatch(root, f'*{pattern.replace("*", "")}*'):
                should_exclude_dir = True
                break

        if should_exclude_dir:
            continue

        for file in files:
            if file.endswith('.kv'):
                full_path = os.path.join(root, file)

                # Check if the file path should be excluded
                should_exclude_file = False
                for pattern in config.DO_NOT_WATCH_PATTERNS:
                    if fnmatch(full_path, f'*{pattern.replace("*", "")}*'):
                        should_exclude_file = True
                        break

                if not should_exclude_file:
                    kv_files.append(full_path)
    return kv_files


def get_kv_files_paths():
    """
    Given the folders on WATCHED_FOLDERS and WATCHED_FOLDERS_RECURSIVELY,
    returns a list of all the kv files paths
    """
    KV_FILES = []

    for folder in config.WATCHED_FOLDERS:
        for file_name in os.listdir(folder):
            if file_name.endswith('.kv'):
                KV_FILES.append(os.path.join(base_dir, f'{folder}/{file_name}'))

    for folder in config.WATCHED_FOLDERS_RECURSIVELY:
        for file_name in find_kv_files_in_folder(folder):
            KV_FILES.append(file_name)

    # Removing duplicates
    KV_FILES = list(set(KV_FILES))

    return KV_FILES


def get_connected_devices(fetch_wifi_ip: bool = False) -> list[dict[str, str]]:
    """
    Returns a list of connected devices with metadata:
    - serial: device serial (USB or IP)
    - transport: usb or tcpip
    - model: device model name if available
    - wifi_ip: IP address of wlan0 (only fetched if fetch_wifi_ip=True, requires adb shell call per device)
    """
    result = subprocess.run(
        ['adb', 'devices', '-l'], capture_output=True, text=True, check=True
    )
    lines = result.stdout.strip().splitlines()[1:]  # Skip header
    print("get connected devices output", lines)
    devices = []
    for line in lines:
        if not line.strip():
            continue
        parts = line.strip().split()
        serial = parts[0]
        status = parts[1] if len(parts) > 1 else ''
        if status != 'device':
            continue
        transport = 'tcpip' if ':' in serial else 'usb'
        model = next(
            (p.split(':')[1] for p in parts if p.startswith('model:')),
            'unknown',
        )
        logging.info(
            f'Detected device: serial={serial}, transport={transport}, model={model}'
        )
        wifi_ip = get_wifi_ip(serial) if fetch_wifi_ip else None
        devices.append({
            'serial': serial,
            'transport': transport,
            'model': model,
            'wifi_ip': wifi_ip,
        })
    # logging.info(f'Total serials connected: {len(devices)}')
    # unique_physical = {
    #     (d['wifi_ip'], d['model']) for d in devices if d['wifi_ip'] is not None
    # }
    # logging.info(f'Total devices connected: {len(unique_physical)}. WIFI: {fetch_wifi_ip}')
    usb_count = sum(1 for d in devices if d['transport'] == 'usb')
    wifi_count = sum(1 for d in devices if d['transport'] == 'tcpip')
    logging.info(f'Total devices: {len(devices)} (USB: {usb_count}, WIFI: {wifi_count})')
    return devices

# def get_connected_devices() -> list[dict[str, str]]:
#     """
#     Returns a list of connected devices with metadata:
#     - serial: device serial (USB or IP)
#     - transport: usb or tcpip
#     - model: device model name if available
#     - wifi_ip: IP address of wlan0 (if available)
#     """
#     result = subprocess.run(
#         ['adb', 'devices', '-l'], capture_output=True, text=True, check=True
#     )
#     lines = result.stdout.strip().splitlines()[1:]  # Skip header
#     print("get connected devices output", lines)
#     devices = []
#     for line in lines:
#         if not line.strip() or 'device' not in line:
#             continue
#         parts = line.strip().split()
#         serial = parts[0]
#         transport = 'tcpip' if ':' in serial else 'usb'
#         model = next(
#             (p.split(':')[1] for p in parts if p.startswith('model:')),
#             'unknown',
#         )

#         logging.info(
#             f'Detected device: serial={serial}, transport={transport}, model={model}'
#         )
#         wifi_ip = get_wifi_ip(serial)

#         devices.append({
#             'serial': serial,
#             'transport': transport,
#             'model': model,
#             'wifi_ip': wifi_ip,
#         })
#     logging.info(f'Total serials connected: {len(devices)}')
#     unique_physical = {
#         (d['wifi_ip'], d['model']) for d in devices if d['wifi_ip'] is not None
#     }
#     logging.info(f'Total physical devices connected: {len(unique_physical)}')
#     return devices


def get_wifi_ip(serial: str) -> Optional[str]:
    """
    Get Wi-Fi IP address from Android device using intelligent interface detection.

    This function identifies the correct Wi-Fi interface by analyzing interface flags
    and filtering out known mobile/cellular interfaces, making it more reliable than
    hardcoded interface name matching.

    Args:
        serial: Android device serial number

    Returns:
        Wi-Fi IP address as string, or None if not found
    """
    logging.debug(f'Querying Wi-Fi IP for serial: {serial}')

    # time.sleep(3)

    def adb(cmd):
        return subprocess.check_output(["adb"] + cmd).decode().strip()

    try:
        result = subprocess.run(
            ['adb', '-s', serial, 'shell', 'ip', '-f', 'inet', 'addr', 'show'],
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
        result = _parse_ip_output(result.stdout, serial)
        if result is None:
            logging.error(
                f'Could not find WiFi IP for {serial}. '
                f'Is WiFi enabled on the device? '
                f'Check: Settings → WiFi → make sure it\'s ON and connected.'
            )
            logging.error(f'ERROR: Could not find WiFi IP on device {serial}.')
            logging.error(f'Make sure WiFi is enabled and connected on your phone!')
        return result
    except subprocess.CalledProcessError as e:
        logging.warning(f'Primary command failed for {serial}: {e}')
        return _get_wifi_ip_fallback(serial)
    except subprocess.TimeoutExpired:
        logging.warning(f'Timeout querying interfaces on {serial}')
        return _get_wifi_ip_fallback(serial)


def _parse_ip_output(output: str, serial: str) -> Optional[str]:
    """Parse the output from 'ip addr show' command."""
    lines = output.splitlines()

    current_interface = None
    current_flags = ''

    for line in lines:
        line = line.strip()

        # Match interface definition line (e.g., "34: wlan1: <BROADCAST,MULTICAST,UP,LOWER_UP>")
        interface_match = re.match(r'\d+:\s+(\S+):\s+<([^>]*)>', line)
        if interface_match:
            current_interface = interface_match.group(1)
            current_flags = interface_match.group(2)
            continue

        # Match IP address line (e.g., "inet 192.168.1.69/24 brd ...")
        ip_match = re.search(r'inet\s+(\d+\.\d+\.\d+\.\d+)(?:/\d+)?', line)
        if ip_match and current_interface and current_flags:
            ip = ip_match.group(1)

            # Skip loopback
            if ip.startswith('127.'):
                continue

            # Skip known cellular/mobile interfaces
            if _is_cellular_interface(current_interface):
                logging.debug(f'Skipping cellular interface {current_interface}: {ip}')
                continue

            # Look for interfaces that are likely Wi-Fi based on flags and IP
            if _is_wifi_interface(current_interface, current_flags, ip):
                logging.debug(
                    f'Found Wi-Fi IP {ip} on {current_interface} for serial: {serial}'
                )
                return ip

    return None


def _is_cellular_interface(interface_name: str) -> bool:
    """Check if interface name indicates a cellular/mobile connection."""
    cellular_prefixes = [
        'ccmni',  # MediaTek cellular
        'rmnet',  # Qualcomm cellular
        'v4-ccmni',  # IPv4 over cellular
        'v6-ccmni',  # IPv6 over cellular
        'pdp',  # Packet Data Protocol
        'ppp',  # Point-to-Point Protocol
        'usb',  # USB tethering (usually not Wi-Fi)
        'rndis',  # Remote NDIS (USB)
    ]

    interface_lower = interface_name.lower()
    return any(interface_lower.startswith(prefix) for prefix in cellular_prefixes)


def _is_wifi_interface(interface_name: str, flags: str, ip: str) -> bool:
    """
    Determine if an interface is likely Wi-Fi based on name, flags, and IP.

    Wi-Fi interfaces typically have:
    - BROADCAST and MULTICAST flags (for network discovery)
    - UP flag (interface is active)
    - Private IP address (for local network)
    - Interface name suggesting Wi-Fi (wlan, wifi, etc.)
    """
    # Must have these flags for a proper Wi-Fi interface
    required_flags = ['BROADCAST', 'MULTICAST', 'UP']
    if not all(flag in flags for flag in required_flags):
        return False

    # Must be a private IP (not public internet)
    if not _is_private_ip(ip):
        return False

    # Prefer interfaces with Wi-Fi-like names
    wifi_indicators = ['wlan', 'wifi', 'wl']
    interface_lower = interface_name.lower()

    # Strong preference for obvious Wi-Fi interface names
    if any(indicator in interface_lower for indicator in wifi_indicators):
        return True

    # For interfaces without obvious Wi-Fi names, be more conservative
    # Accept only if it's in a common Wi-Fi subnet and not obviously something else
    if _is_common_wifi_subnet(ip) and not _is_cellular_interface(interface_name):
        return True

    return False


def _is_private_ip(ip: str) -> bool:
    """Check if IP address is in private ranges (RFC 1918)."""
    try:
        ip_obj = ipaddress.IPv4Address(ip)
        return ip_obj.is_private
    except ipaddress.AddressValueError:
        return False


def _is_common_wifi_subnet(ip: str) -> bool:
    """Check if IP is in commonly used Wi-Fi subnets."""
    common_wifi_prefixes = [
        '192.168.',  # Most common home/office Wi-Fi
        '10.0.',  # Common in enterprise
        '172.16.',  # Less common but used
    ]
    return any(ip.startswith(prefix) for prefix in common_wifi_prefixes)


def _get_wifi_ip_fallback(serial: str) -> Optional[str]:
    """Fallback method using ifconfig command."""
    logging.debug(f'Trying fallback method for serial: {serial}')

    try:
        result = subprocess.run(
            ['adb', '-s', serial, 'shell', 'ifconfig'],
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )

        return _parse_ifconfig_output(result.stdout, serial)

    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        logging.warning(f'Fallback method failed for {serial}: {e}')
        return None


def _parse_ifconfig_output(output: str, serial: str) -> Optional[str]:
    """Parse ifconfig output to find Wi-Fi IP."""
    lines = output.splitlines()
    current_interface = None

    for line in lines:
        # Interface start line (doesn't start with space)
        if not line.startswith(' ') and line.strip():
            current_interface = line.split()[0] if line.split() else None
            continue

        # IP address line (starts with space, contains inet)
        if not (line.startswith(' ') and 'inet' in line and current_interface):
            continue

        ip = _extract_ip_from_ifconfig_line(line)
        if not ip:
            continue

        wifi_ip = _validate_wifi_ip_ifconfig(ip, current_interface, serial)
        if wifi_ip:
            return wifi_ip

    logging.warning(f'No Wi-Fi IP found for {serial}')
    return None


def _extract_ip_from_ifconfig_line(line: str) -> Optional[str]:
    """Extract IP address from ifconfig line using multiple patterns."""
    ip_patterns = [
        r'inet addr:(\d+\.\d+\.\d+\.\d+)',  # Android/Linux format
        r'inet (\d+\.\d+\.\d+\.\d+)',  # Alternative format
    ]

    for pattern in ip_patterns:
        match = re.search(pattern, line)
        if match:
            return match.group(1)

    return None


def _validate_wifi_ip_ifconfig(ip: str, interface: str, serial: str) -> Optional[str]:
    """Validate if IP and interface represent a Wi-Fi connection."""
    # Skip loopback
    if ip.startswith('127.'):
        return None

    # Skip cellular interfaces
    if _is_cellular_interface(interface):
        return None

    # Accept private IPs on likely Wi-Fi interfaces
    if not _is_private_ip(ip):
        return None

    interface_lower = interface.lower()
    wifi_indicators = ['wlan', 'wifi', 'wl']

    if any(indicator in interface_lower for indicator in wifi_indicators):
        logging.debug(
            f'Fallback found Wi-Fi IP {ip} on {interface} for serial: {serial}'
        )
        return ip

    return None

# def is_adb_listening(host="127.0.0.1", timeout=10.0):
#     end_time = time.time() + timeout

#     while time.time() < end_time:
#         s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#         s.settimeout(0.5)

#         adb_port = getattr(config, "ADB_PORT", 5037)

#         try:
#             logging.info(f'testing {host}:{adb_port}')
#             s.connect((host, adb_port))
#             s.close()
#             return True
#         except (ConnectionRefusedError, socket.timeout, OSError):
#             time.sleep(0.1)
#         finally:
#             s.close()

#     return False

# def adb_forward(port: int):
#     adb_cmd = f"adb forward tcp:{port} tcp:{port}"
#     logging.info(adb_cmd)
#     return os.system(adb_cmd)

# def adb_forward(port: int) -> int:
#     cmd = ["adb", "forward", f"tcp:{port}", f"tcp:{port}"]
#     logging.info(" ".join(cmd))

#     result = subprocess.run(cmd)
#     return result.returncode

def adb_forward(port: int, serial: str = None) -> int:
    if serial:
        cmd = ["adb", "-s", serial, "forward", f"tcp:{port}", f"tcp:{port}"]
    else:
        cmd = ["adb", "forward", f"tcp:{port}", f"tcp:{port}"]
    logging.info(" ".join(cmd))
    try:
        result = subprocess.run(cmd, timeout=10)
        return result.returncode
    except subprocess.TimeoutExpired:
        logging.warning(f"adb forward timed out after 10s")
        return 1

def adb_has_forward(port: int) -> bool:
    pattern = re.compile(rf"tcp:{port}\s+tcp:{port}\b")

    try:
        result = subprocess.run(
            ["cmd.exe", "/c", "adb.exe", "forward", "--list"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        for line in result.stdout.lower().splitlines():
            if pattern.search(line):
                return True

        return False

    except Exception:
        return False


def is_adb_listening(host="127.0.0.1", timeout=10.0) -> bool:
    """
    Check if ADB server is reachable (the port doesn't really work in wsl anymore).
    In WSL, runs adb.exe start-server (idempotent) instead of a raw socket test,
    because the server lives on the Windows host at a dynamic IP.
    assumes that kivy reloader sh install from kivyschool was ran and your windows adb is aliased in wsl.

    you can check with `type adb` in wsl
    """
    if in_wsl():
        try:
            adb_path = get_adb_windows_path()  # your existing helper
            result = subprocess.run(
                ["cmd.exe", "/c", "adb.exe", "start-server"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    # Non-WSL: socket check is fine, host is always 127.0.0.1
    end_time = time.time() + timeout
    adb_port = getattr(config, "ADB_PORT", 5037)
    while time.time() < end_time:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        try:
            s.connect((host, adb_port))
            return True
        except (ConnectionRefusedError, socket.timeout, OSError):
            time.sleep(0.1)
        finally:
            s.close()
    return False

def extract_ip(line):
    match = re.search(r'\b\d+\.\d+\.\d+\.\d+\b', line)
    return match.group(0) if match else None

# def get_wsl_nameservers():
#     if not in_wsl():
#         return []
#     nameservers = []
#     with open("/etc/resolv.conf") as f:
#         for line in f:
#             if line.startswith("nameserver"):
#                 nameservers.append(line.strip())
#     return nameservers

def get_wsl_nameservers():
    """
    Returns the Windows Host IP by checking the default route.
    Fallback to /etc/resolv.conf if routing table is unavailable.
    """
    try:
        if not in_wsl():
            return []
        # Method 1: Get IP from the default gateway (Best for WSL2)
        try:
            # Runs 'ip route show default' and looks for 'via'
            route_output = subprocess.check_output(['ip', 'route', 'show', 'default'], 
                                                stderr=subprocess.DEVNULL).decode()
            parts = route_output.split()
            if "via" in parts:
                return [parts[parts.index("via") + 1]]
        except Exception:
            pass

        # Method 2: Fallback to nameserver in resolv.conf
        try:
            if os.path.exists("/etc/resolv.conf"):
                with open("/etc/resolv.conf", "r") as f:
                    for line in f:
                        if line.strip().startswith("nameserver"):
                            return [line.split()[1].strip()]
        except Exception:
            pass
            
        return ["127.0.0.1"] # Absolute fallback
    except:
        return "NAMESERVERS FAILED"

def get_adb_host_ip() -> str:
    """In WSL2 mirrored networking mode, localhost works directly."""
    if in_wsl():
        try:
            wslconfig = subprocess.check_output(
                ["sh", "-c", "cat /mnt/c/Users/$(cmd.exe /c 'echo %USERNAME%' 2>/dev/null | tr -d '\r')/.wslconfig 2>/dev/null"],
                text=True
            ).strip()
            if re.search(r'networkingMode\s*=\s*mirrored', wslconfig, re.IGNORECASE):
                return "127.0.0.1"
        except Exception:
            pass
        # NAT mode fallback: use eth0 gateway
        try:
            gateway = subprocess.check_output(
                ["sh", "-c", "ip route show dev eth0 | grep default | awk '{print $3}'"],
                text=True
            ).strip()
            if gateway:
                return gateway
        except Exception:
            pass
    return "127.0.0.1"

def get_adb_windows_path():
    """Extract the adb.exe path from the bash alias in .bashrc"""
    bashrc = os.path.expanduser("~/.bashrc")
    try:
        with open(bashrc) as f:
            for line in f:
                # matches: alias adb='/mnt/c/.../adb.exe'
                match = re.search(r"alias adb=['\"](.+?)['\"]", line)
                if match:
                    return match.group(1)
    except FileNotFoundError:
        pass
    
    # Fallback: which adb (catches symlinks/wrappers too)
    try:
        path = subprocess.check_output(["which", "adb"]).decode().strip()
        if path:
            return path
    except Exception:
        pass
    
    return "adb"  # last resort


def in_wsl():
    ans = "wsl2" in platform.release().lower()
    # print("WSL:", ans)
    return ans

async def fix_wsl():
    PORT = int(config.RELOADER_PORT)
    # 1. Trigger the Firewall Fix (UAC)
    print(f"{yellow}Initial connection blocked. Fixing Windows firewall for WSL2. Waiting for you to approve the UAC prompt...")
    await run_wsl_firewall_fix(port=PORT) 
    
    # Wait up to 30 seconds for the rule to actually appear
    rule_found = await wsl_firewall_check_async(PORT)
    if not rule_found:
        print(f"{red}Firewall rule not detected. Please click 'Yes' on UAC!")
        return
    
    print(f"{green}Tunnel reset. Retrying immediately...")
    # Check ADB separately — it should already be up, but wait briefly if not
    if in_wsl() and config.STREAM_USING == "USB":
        host_ip = extract_ip(get_wsl_nameservers()[0])
        print("what is host ip?", host_ip)
        adb_ready = is_adb_listening(host_ip)
    else:
        adb_ready = is_adb_listening()
    if not adb_ready:
        print(f"{yellow}ADB not listening yet, waiting up to 5s...")
        for _ in range(10):
            await trio.sleep(0.5)
            ip_data = subprocess.check_output(["ip", "-o", "-4", "addr", "show", "eth0"]).decode()
            raw_ip = ip_data.split()[3].split('/')[0]
            parts = raw_ip.split('.')
            subnet_range = f"{parts[0]}.{parts[1]}.0.0/20"
            print(f"[*] Detected WSL IP: {raw_ip} -> Using Subnet: {subnet_range}")
            wsl_ip = f"{parts[0]}.{parts[1]}.0.0"
            if is_adb_listening(host = wsl_ip):
                adb_ready = True
                break

    if not adb_ready:
        print(f"{yellow}ADB still not up, proceeding anyway with tunnel reset...")

    print("Removing old forward...")
    with trio.move_on_after(10) as cancel_scope:
        res_remove = await trio.run_process(
            # ["adb.exe", "forward", "--remove", f"tcp:{PORT}"],
            # ["cmd.exe", "/c", "start", "adb.exe", "forward", "--remove", f"tcp:{PORT}"],
            ["cmd.exe", "/c", "adb.exe", "forward", "--remove", f"tcp:{PORT}"],
            check=False,
            capture_stdout=True,
            capture_stderr=True,
        )
        print(f"stdout: {res_remove.stdout.decode().strip()}")
        print(f"stderr: {res_remove.stderr.decode().strip()}")
        if cancel_scope.cancelled_caught:
            print("❌ Timeout: Remove forward took too long.")
        else:
            status = "✅ Success" if res_remove.returncode == 0 else "⚠️  Failed/Not Found"
            print(f"Remove Forward: {status} (Code: {res_remove.returncode})")

    await trio.sleep(0.5)
    print("Re-adding forward...")
    res_add = await trio.run_process(
        # ["adb.exe", "forward", f"tcp:{PORT}", f"tcp:{PORT}"],
        # ["cmd.exe", "/c", "start", "adb.exe", "forward", f"tcp:{PORT}", f"tcp:{PORT}"],
        ["cmd.exe", "/c", "adb.exe", "forward", f"tcp:{PORT}", f"tcp:{PORT}"],
        check=False,
        capture_stdout=True,
        capture_stderr=True
    )

    if res_add.returncode == 0:
        print(f"✅ Add Forward: Success (Port {PORT})")
    else:
        print(f"❌ Add Forward: Failed (Code: {res_add.returncode})")
        print(f"   Reason: {res_add.stderr.decode().strip()}")

    print(f"{green}Tunnel reset complete.")

async def run_wsl_firewall_fix(port=8055):
    try:
        # 1. Get the IP and convert to /20 subnet range
        ip_data = subprocess.check_output(["ip", "-o", "-4", "addr", "show", "eth0"]).decode()
        raw_ip = ip_data.split()[3].split('/')[0]
        parts = raw_ip.split('.')
        subnet_range = f"{parts[0]}.{parts[1]}.0.0/20"
        print(f"[*] Detected WSL IP: {raw_ip} -> Using Subnet: {subnet_range}")

        # Get Windows host gateway (the IP WSL2 uses to reach Windows)
        gateway = subprocess.check_output(
            ["sh", "-c", "ip route show dev eth0 | grep default | awk '{print $3}'"],
            text=True
        ).strip()
        print(f"[*] Windows host gateway: {gateway}")


        rule_name = f"WSL Kivy Surgical {port}"

        # 2. Read current state (no admin needed)
        # check_cmd = [
        #     "powershell.exe", "-NoProfile", "-Command",
        #     f"$aliases = (Get-NetFirewallProfile -Profile Public).DisabledInterfaceAliases;"
        #     f"$rule = Get-NetFirewallRule -DisplayName '{rule_name}' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Enabled;"
        #     f"Write-Output \"ALIASES:$aliases|RULE:$rule\""
        # ]
        # check_cmd = [
        #     "powershell.exe", "-NoProfile", "-Command",
        #     (
        #         f'$aliases = (Get-NetFirewallProfile -Profile Public).DisabledInterfaceAliases;'
        #         f'$rule = Get-NetFirewallRule -DisplayName "{rule_name}" -ErrorAction SilentlyContinue '
        #         f'| Select-Object -ExpandProperty Enabled;'
        #         f'Write-Output "ALIASES:$aliases|RULE:$rule"'
        #     )
        # ]
        # check_cmd = [
        #     "powershell.exe", "-NoProfile", "-Command",
        #     (
        #         f'$aliases = (Get-NetFirewallProfile -Profile Public).DisabledInterfaceAliases;'
        #         f'$rule = Get-NetFirewallRule | Where-Object {{ $_.DisplayName -like "*{port}*" }} '
        #         f'| Select-Object -First 1;'
        #         f'$ruleEnabled = if ($rule) {{ [string]$rule.Enabled }} else {{ "NotFound" }};'
        #         f'Write-Output "ALIASES:$aliases|RULE:$ruleEnabled"'
        #     )
        # ]
        #     check_cmd = [
        #     "powershell.exe", "-NoProfile", "-Command",
        #     (
        #         f'$aliases = (Get-NetFirewallProfile -Profile Public).DisabledInterfaceAliases;'
        #         f'$count = (Get-NetFirewallRule | Measure-Object).Count;'
        #         f'$rule = Get-NetFirewallRule | Where-Object {{ $_.DisplayName -like "*{port}*" }} '
        #         f'| Select-Object -First 1;'
        #         f'$ruleEnabled = if ($rule) {{ [string]$rule.Enabled }} else {{ "NotFound" }};'
        #         f'Write-Output "ALIASES:$aliases|RULE:$ruleEnabled|COUNT:$count"'
        #     )
        # ]

        check_cmd = [
            "powershell.exe", "-NoProfile", "-Command",
            (
                f'$aliases = (Get-NetFirewallProfile -Profile Public).DisabledInterfaceAliases;'
                f'$regPath = "HKLM:\\SYSTEM\\CurrentControlSet\\Services\\SharedAccess\\Parameters\\FirewallPolicy\\FirewallRules";'
                f'$key = Get-Item $regPath;'
                f'$match = $key.Property | Where-Object {{ $key.GetValue($_) -like "*LPort={port}*" }} | Select-Object -First 1;'
                f'$ruleEnabled = if ($match) {{'
                f'  $val = $key.GetValue($match);'
                f'  if ($val -like "*Active=TRUE*") {{ "True" }} else {{ "False" }}'
                f'}} else {{ "NotFound" }};'
                f'Write-Output "ALIASES:$aliases|RULE:$ruleEnabled"'
            )
        ]

        check_result = subprocess.run(check_cmd, capture_output=True, text=True)
        output = check_result.stdout.strip()
        print(f"RAW OUTPUT: {repr(output)}") 

        wsl_allowed = "vEthernet (WSL)" in output
        rule_enabled = "RULE:True" in output

        proxy_result = subprocess.run(
            ["netsh.exe", "interface", "portproxy", "show", "v4tov4"],
            capture_output=True, text=True
        )
        portproxy_exists = any(
            gateway in line and str(port) in line
            for line in proxy_result.stdout.splitlines()
        )

        # 3. Report each case clearly
        print()
        print(f"[Case 1] WSL interface allowed: {'✓ YES' if wsl_allowed else '✗ NO — will fix'}")
        print(f"[Case 2] Port {port} rule enabled: {'✓ YES' if rule_enabled else '✗ NO — will fix'}")
        print(f"[Case 3] Port proxy {gateway}:{port} → 127.0.0.1:{port}: {'✓ YES' if portproxy_exists else '✗ NO — will fix'}")
        print()

        # 4. Nothing to do
        if wsl_allowed and rule_enabled and portproxy_exists:
            print("[✓] All good — nothing to fix!")
            return


        # 5. Build a single script covering only what needs fixing
        ps_parts = []

        # Case 1 fix: allow WSL interface on Public profile
        if not wsl_allowed:
            ps_parts.append(
                "$p = Get-NetFirewallProfile -Profile Public; "
                "$aliases = $p.DisabledInterfaceAliases + 'vEthernet (WSL)'; "
                "Set-NetFirewallProfile -Profile Public -DisabledInterfaceAliases $aliases; "
                "Write-Host '[+] Case 1 fixed: WSL interface now allowed on Public firewall profile.'"
            )

        # Case 2 fix: create inbound port rule
        if not rule_enabled:
            ps_parts.append(
                f"Remove-NetFirewallRule -DisplayName '{rule_name}' -ErrorAction SilentlyContinue; "
                f"New-NetFirewallRule -DisplayName '{rule_name}' "
                f"-Direction Inbound -Action Allow -Protocol TCP "
                f"-LocalPort {port} -RemoteAddress '{subnet_range}' "
                f"-InterfaceAlias 'vEthernet (WSL)'; "
                f"Write-Host '[+] Case 2 fixed: Inbound rule for port {port} created.'"
            )

        # Case 3 fix: portproxy so WSL2 can reach ADB forward on Windows loopback
        if not portproxy_exists:
            ps_parts.append(
                f"netsh interface portproxy delete v4tov4 listenaddress={gateway} listenport={port} 2>$null; "
                f"netsh interface portproxy add v4tov4 listenaddress={gateway} listenport={port} connectaddress=127.0.0.1 connectport={port}; "
                f"Write-Host '[+] Case 3 fixed: Port proxy {gateway}:{port} -> 127.0.0.1:{port} added.'"
            )


        # 6. Fire single UAC prompt with combined script
        combined_script = " ".join(ps_parts)
        encoded_script = base64.b64encode(combined_script.encode('utf-16-le')).decode('utf-8')
        launch_command = (
            f'Start-Process powershell -Verb RunAs '
            f'-ArgumentList "-NoProfile", "-EncodedCommand", "{encoded_script}"'
        )

        print("[*] Triggering single UAC prompt for all required fixes...")
        subprocess.run(["powershell.exe", "-Command", launch_command], check=True)
        print("[+] Done! Check your taskbar for the UAC shield.")

    except subprocess.CalledProcessError as e:
        print(f"[!] Subprocess error: {e}")
    except Exception as e:
        print(f"[!] Failed: {e}")

async def wsl_firewall_check_async(port):
    timeout = 30
    start_time = time.time()
    rule_found = False
    
    while time.time() - start_time < timeout:
        # Use netsh.exe to check from WSL
        check_cmd = ["netsh.exe", "advfirewall", "firewall", "show", "rule", f"name=WSL Kivy Surgical {port}"]
        
        # Using trio.run_process for a clean async check
        try:
            result = await trio.run_process(check_cmd, capture_stdout=True, capture_stderr=True, check=False)
            if result.returncode == 0:
                print(f"{green}Firewall rule detected! Proceeding...")
                rule_found = True
                break
        except Exception as e:
            print(f"{red}Check failed: {e}")

        elapsed = int(time.time() - start_time)
        print(f"{yellow}[{elapsed}s] Rule not found yet. Check UAC prompt...")
        
        # This allows other async tasks to run while we wait for the UAC click
        await trio.sleep(1)
        
    return rule_found

# Example usage and testing
if __name__ == '__main__':
    # Configure logging for testing
    logging.basicConfig(level=logging.DEBUG)

    # Test with your device
    serial = '0084045001'
    wifi_ip = get_wifi_ip(serial)

    if wifi_ip:
        print(f'Wi-Fi IP found: {wifi_ip}')
    else:
        print('No Wi-Fi IP found')
