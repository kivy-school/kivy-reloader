import datetime
import os
import socket
import subprocess
import sys

import trio
from colorama import Fore, init

from kivy_reloader.config import config
from kivy_reloader.utils import (
    adb_forward,
    fix_wsl,
    get_adb_host_ip,
    get_connected_devices,
    in_wsl,
)

red = Fore.RED
green = Fore.GREEN
yellow = Fore.YELLOW
white = Fore.WHITE
init(autoreset=True)


async def connect_to_server(IP):
    PORT = int(config.RELOADER_PORT)
    timeout = 60  # Total time we are willing to wait for a success
    start_time = trio.current_time()
    UAC_count = 0
    attempt_count = 0

    print(
        f'Connecting to {green}{IP}{white}:{green}{PORT}{white}...', end='', flush=True
    )

    while (trio.current_time() - start_time) < timeout:
        try:
            # Attempt the connection with a 5s window
            with trio.move_on_after(5):
                client_socket = await trio.open_tcp_stream(IP, PORT)
                print(f' {green}connected!')
                return client_socket  # SUCCESS: Return the socket

            attempt_count += 1
            print(
                f'\r{yellow}Connecting to {IP}:{PORT}... attempt {attempt_count}. ',
                end='',
                flush=True,
            )
            # If we reached here, the connection timed out
            print(f'{yellow}Connection timed out. Checking Firewall/ADB...')

            if in_wsl() and config.STREAM_USING == 'USB' and UAC_count < 1:
                await fix_wsl()
                UAC_count += 1

        except Exception:
            attempt_count += 1
            print(
                f'\r{yellow}Connecting to {IP}:{PORT}... attempt {attempt_count}',
                end='',
                flush=True,
            )

        await trio.sleep(2)  # Wait before the next full attempt

    print(
        f'\n{red}Could not connect to {IP} after {attempt_count} attempts in  ({timeout}s)'
    )
    return None


def wsl_network_dead(timeout=1.0):
    """
    Returns True if WSL2 networking is dead (Windows 10 adapter vanished).
    """
    try:
        # 1. Get default gateway (Windows host)
        route = (
            subprocess
            .check_output(
                ['sh', '-c', "ip route | grep default | awk '{print $3}'"],
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )

        if not route:
            return True  # No gateway at all → WSL networking dead

        # 2. Try connecting to the gateway on any port (TCP SYN)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            s.connect((route, 53))  # DNS port is always closed but reachable
            s.close()
            return False  # Gateway reachable → networking alive
        except ConnectionRefusedError:
            return False  # Host reachable, port just closed — networking alive
        except Exception:
            return True  # Timeout or no route — networking dead
    except Exception:
        return True  # Any failure → treat as dead


def check_adb_context():
    try:
        # Check which binary is being called
        which_adb = subprocess.check_output(['which', 'adb']).decode().strip()
        # Check the version and path reported by ADB itself
        version_info = subprocess.check_output(['adb', 'version']).decode().strip()
        print('--- ADB DEBUG INFO ---')
        print(f'Python is calling: {which_adb}')
        print(f'{version_info}')
        print('----------------------')
    except Exception as e:
        print(f'ADB check failed: {e}')


async def send_app():  # noqa:PLR0914
    print('*' * 50)
    print(green + 'Connecting to smartphone...')

    fetch_wifi = config.STREAM_USING == 'WIFI'
    devices = get_connected_devices(fetch_wifi_ip=fetch_wifi)

    if not devices:
        print(f'{yellow}No connected devices found.')
        return 1

    if config.STREAM_USING == 'USB':
        PORT = config.RELOADER_PORT
        usb_devices = [d for d in devices if d['transport'] == 'usb']
        for d in usb_devices:
            adb_forward(PORT, serial=d['serial'])
        host_ip = get_adb_host_ip()
        unique_physical = {(host_ip, d['model']) for d in usb_devices}
    else:
        unique_physical = {
            (d['wifi_ip'], d['model']) for d in devices if d['wifi_ip'] is not None
        }

    acked_count = 0

    for device in unique_physical:
        IP = device[0]

        client_socket = await connect_to_server(IP)

        if not client_socket:
            print(f"{yellow}Couldn't connect to smartphone: {IP}")
            continue

        print(f'{yellow} Phone connected successfully: {IP}')
        print(f'\n{green}Sending app to smartphone...')

        zip_path = 'app_copy.zip'
        if not os.path.exists(zip_path):
            print(f'{red}Zip file not found: {os.path.abspath(zip_path)}')
            await client_socket.aclose()
            continue

        zip_size = os.path.getsize(zip_path)
        print(f'DEBUG: Opening zip at {os.path.abspath(zip_path)}, size={zip_size}')

        # 1. Send header: "<size>\n"
        header = f'{zip_size}\n'.encode()
        await client_socket.send_all(header)
        print(f'DEBUG: Sent header with size {zip_size}')

        # 1b. Send file tree flag (1 byte: b'\x01' = print, b'\x00' = skip)
        print_tree = getattr(config, 'PRINT_FILE_TREE', False)
        await client_socket.send_all(b'\x01' if print_tree else b'\x00')
        print(f'DEBUG: Sent file tree flag: {print_tree}')

        # 2. Send ZIP contents
        CHUNK_SIZE = 256 * 1024
        total_bytes = 0
        chunks_sent = 0

        with open(zip_path, 'rb') as myzip:
            while True:
                chunk = myzip.read(CHUNK_SIZE)
                if not chunk:
                    break

                await client_socket.send_all(chunk)
                chunks_sent += 1
                total_bytes += len(chunk)

                if chunks_sent % 10 == 0:
                    mb_sent = total_bytes / (1024 * 1024)
                    mb_total = zip_size / (1024 * 1024)
                    print(
                        f'\r{green}Sent {mb_sent:.1f} / {mb_total:.1f} MB ({chunks_sent} chunks)',
                        end='',
                        flush=True,
                    )

        print(
            green
            + f'Finished sending app! ({total_bytes} bytes in {chunks_sent} chunks)'
        )

        # 3. Wait for OK
        min_speed_bytes_per_sec = 0.5 * 1024 * 1024  # 1 MB/s
        timeout = (zip_size / min_speed_bytes_per_sec) + 30
        print(f'{yellow}Waiting ({timeout} seconds) for ACK from smartphone {IP}...')
        ack_ok = False

        start_wait = trio.current_time()
        try:
            with trio.move_on_after(timeout):
                while True:
                    data = await client_socket.receive_some(16)
                    now = datetime.datetime.now()
                    remaining = max(0, timeout - (trio.current_time() - start_wait))
                    print(f'RECEIVED: {data!r} at {now} (timeout in {remaining:.0f}s)')

                    if data == b'OK':
                        ack_ok = True
                        break

                    if data == b'':
                        await trio.sleep(10)
                        continue

        except Exception as e:
            print(f'{red}Error while waiting for ACK: {e}')

        formatted_time = datetime.datetime.now().strftime('%m-%d %H:%M:%S.%f')[:-3]

        if ack_ok:
            print(f'{green}ACK received from {IP}, {formatted_time}')
            acked_count += 1
        else:
            print(f'{yellow}No ACK received from {IP}, {formatted_time}')

        # Close socket gracefully
        try:
            await client_socket.aclose()
        except Exception:
            pass

    print('\n')
    print(yellow + f'Sent app to {len(unique_physical)} smartphone(s)')
    if acked_count:
        print(green + f'ACK confirmed on {acked_count} smartphone(s)')
    else:
        print(red + 'No ACKs received')
    print('*' * 50)

    return 0 if acked_count > 0 else 1


if __name__ == '__main__':
    exit_code = trio.run(send_app)
    sys.exit(exit_code)
