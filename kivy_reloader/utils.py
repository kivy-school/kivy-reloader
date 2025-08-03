import ipaddress
import logging
import os
import pathlib
import re
import subprocess
import sys
from fnmatch import fnmatch
from typing import Optional

from kivy.lang import Builder
from kivy.resources import resource_add_path, resource_find
from kivy.utils import platform

from kivy_reloader.config import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
base_dir = os.getcwd()


def load_kv_path(path):
    """
    Loads a kv file from a path
    """
    if path.endswith('.pyc'):
        path = path.replace('.pyc', '.kv')
    elif path.endswith('.py'):
        path = path.replace('.py', '.kv')

    if hasattr(sys, '_MEIPASS'):
        resource_add_path(sys._MEIPASS)
        test_path = pathlib.Path(path)
        try:
            # look with extra root path appended to sys._MEIP0ASS
            if str(test_path.parent) != '.':
                meipass_path = pathlib.Path(sys._MEIPASS) / test_path.parent
            resource_add_path(meipass_path)
            logging.info(f'resource_find {meipass_path}, {test_path.name}')
            kv_path = resource_find(test_path.name)
        except Exception:
            # last resort: do a naive search with resource find
            kv_path = resource_find(path)
            logging.info(
                f'kv path might be a duplicate, please double check {path}, {kv_path}'
            )

    else:
        kv_path = os.path.join(base_dir, path)
    if kv_path is None:
        logging.error(f'failed to load kv path: {path}')
    if kv_path in Builder.files:
        Builder.unload_file(kv_path)

    if kv_path not in Builder.files:
        Builder.load_file(kv_path)


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
        directories_to_watch = []

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

    if platform == 'win':
        return create_path_tuples(non_recursive_paths, False) + recursive_tuples
    else:
        return create_path_tuples(non_recursive_paths, True) + recursive_tuples


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


def get_connected_devices() -> list[dict[str, str]]:
    """
    Returns a list of connected devices with metadata:
    - serial: device serial (USB or IP)
    - transport: usb or tcpip
    - model: device model name if available
    - wifi_ip: IP address of wlan0 (if available)
    """
    result = subprocess.run(
        ['adb', 'devices', '-l'], capture_output=True, text=True, check=True
    )
    lines = result.stdout.strip().splitlines()[1:]  # Skip header
    devices = []
    for line in lines:
        if not line.strip() or 'device' not in line:
            continue
        parts = line.strip().split()
        serial = parts[0]
        transport = 'tcpip' if ':' in serial else 'usb'
        model = next(
            (p.split(':')[1] for p in parts if p.startswith('model:')),
            'unknown',
        )

        logging.info(
            f'Detected device: serial={serial}, transport={transport}, model={model}'
        )
        wifi_ip = get_wifi_ip(serial)

        devices.append({
            'serial': serial,
            'transport': transport,
            'model': model,
            'wifi_ip': wifi_ip,
        })
    logging.info(f'Total serials connected: {len(devices)}')
    unique_physical = {
        (d['wifi_ip'], d['model']) for d in devices if d['wifi_ip'] is not None
    }
    logging.info(f'Total physical devices connected: {len(unique_physical)}')
    return devices


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

    try:
        result = subprocess.run(
            ['adb', '-s', serial, 'shell', 'ip', '-f', 'inet', 'addr', 'show'],
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )

        return _parse_ip_output(result.stdout, serial)

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
