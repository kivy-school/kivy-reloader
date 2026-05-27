import sys
import os
import logging
import trio
from colorama import Fore, init
import subprocess

import socket

from kivy_reloader.config import config
from kivy_reloader.utils import get_connected_devices, in_wsl, fix_wsl, get_adb_host_ip

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

    while (trio.current_time() - start_time) < timeout:
        try:
            print(f'Connecting to IP: {green}{IP}{white} and PORT: {green}{PORT}')
            # Attempt the connection with a 5s window
            with trio.move_on_after(5) as cancel_scope:
                client_socket = await trio.open_tcp_stream(IP, PORT)
                return client_socket # SUCCESS: Return the socket
            
            # If we reached here, the connection timed out
            print(f"{yellow}Connection timed out. Checking Firewall/ADB...")

            if in_wsl() and config.STREAM_USING == "USB" and UAC_count < 1:
                await fix_wsl()
                UAC_count += 1

        except Exception as e:
            print(f'{red}Attempt failed: {e}. Retrying in 2s...')
        
        await trio.sleep(2) # Wait before the next full attempt

    print(f"{red}Global timeout reached in {timeout}s. Could not connect to {IP}")
    return None


# async def connect_to_server(IP):
#     try:
#         print("what", config.RELOADER_PORT)
#         PORT = int(config.RELOADER_PORT)
#         print(f'Connecting to IP: {green}{IP}{white} and PORT: {green}{PORT}')
#         with trio.move_on_after(10):
#             client_socket = await trio.open_tcp_stream(IP, PORT)
#             return client_socket
#     except Exception as e:
#         print(f'{red}Error: {e}')
#         return None

def wsl_network_dead(timeout=1.0):
    """
    Returns True if WSL2 networking is dead (Windows 10 adapter vanished).
    """
    try:
        # 1. Get default gateway (Windows host)
        route = subprocess.check_output(
            ["sh", "-c", "ip route | grep default | awk '{print $3}'"],
            stderr=subprocess.DEVNULL
        ).decode().strip()

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
            return True   # Timeout or no route — networking dead
    except Exception:
        return True  # Any failure → treat as dead



# async def run_wsl_firewall_fix(port=8055):
#     try:
#         # 1. Get the IP and convert to /20 subnet range
#         ip_data = subprocess.check_output(["ip", "-o", "-4", "addr", "show", "eth0"]).decode()
#         raw_ip = ip_data.split()[3].split('/')[0]
#         parts = raw_ip.split('.')
#         subnet_range = f"{parts[0]}.{parts[1]}.0.0/20"

#         print(f"[*] Detected WSL IP: {raw_ip} -> Using Subnet: {subnet_range}")

#         rule_name = f"WSL Kivy Surgical {port}"

#         # 2. Check if the firewall profile already allows WSL interface
#         check_cmd = [
#             "powershell.exe", "-NoProfile", "-Command",
#             "(Get-NetFirewallProfile -Profile Public).DisabledInterfaceAliases"
#         ]
#         check_result = subprocess.run(check_cmd, capture_output=True, text=True)
#         disabled_aliases = check_result.stdout.strip()

#         if "vEthernet (WSL)" in disabled_aliases:
#             print("[✓] WSL interface is already allowed on the Public firewall profile. No changes needed.")
#         else:
#             print("[!] WSL interface is NOT allowed. Applying profile fix... (Windows will complain in Win 10)")
#             profile_fix = (
#                 "$p = Get-NetFirewallProfile -Profile Public;"
#                 "$aliases = $p.DisabledInterfaceAliases + 'vEthernet (WSL)';"
#                 "Set-NetFirewallProfile -Profile Public -DisabledInterfaceAliases $aliases"
#             )
#             encoded_profile_fix = base64.b64encode(profile_fix.encode('utf-16-le')).decode('utf-8')
#             launch_profile_fix = (
#                 f'Start-Process powershell -Verb RunAs '
#                 f'-ArgumentList "-NoProfile", "-EncodedCommand", "{encoded_profile_fix}"'
#             )
#             subprocess.run(["powershell.exe", "-Command", launch_profile_fix], check=True)
#             print("[+] WSL interface allowed on Public firewall profile. Check taskbar for UAC prompt.")

#         # 3. Check if the inbound port rule already exists and is enabled
#         check_rule_cmd = [
#             "powershell.exe", "-NoProfile", "-Command",
#             f"Get-NetFirewallRule -DisplayName '{rule_name}' -ErrorAction SilentlyContinue"
#             " | Select-Object -ExpandProperty Enabled"
#         ]
#         rule_result = subprocess.run(check_rule_cmd, capture_output=True, text=True)
#         rule_enabled = rule_result.stdout.strip().lower() == "true"

#         if rule_enabled:
#             print(f"[✓] Firewall rule '{rule_name}' already exists and is enabled. No changes needed.")
#             return

#         print(f"[!] Rule '{rule_name}' not found or disabled. Requesting admin prompt to apply fix...")

#         # 4. Build and encode the rule creation script
#         ps_script = (
#             f"Remove-NetFirewallRule -DisplayName '{rule_name}' -ErrorAction SilentlyContinue; "
#             f"New-NetFirewallRule -DisplayName '{rule_name}' "
#             f"-Direction Inbound -Action Allow -Protocol TCP "
#             f"-LocalPort {port} -RemoteAddress '{subnet_range}' "
#             f"-InterfaceAlias 'vEthernet (WSL)'"
#         )
#         encoded_script = base64.b64encode(ps_script.encode('utf-16-le')).decode('utf-8')
#         launch_command = (
#             f'Start-Process powershell -Verb RunAs '
#             f'-ArgumentList "-NoProfile", "-EncodedCommand", "{encoded_script}"'
#         )

#         print(f"[*] Triggering Windows UAC prompt for port {port}...")
#         subprocess.run(["powershell.exe", "-Command", launch_command], check=True)
#         print("[+] Firewall rule applied. Check your taskbar for the UAC shield!")

#     except subprocess.CalledProcessError as e:
#         print(f"[!] Subprocess error: {e}")
#     except Exception as e:
#         print(f"[!] Failed: {e}")

# async def run_wsl_firewall_fix(port=8055):
#     try:
#         # 1. Get the IP but convert it to the /20 subnet range 
#         # This matches your working manual command
#         ip_data = subprocess.check_output(["ip", "-o", "-4", "addr", "show", "eth0"]).decode()
#         # Extracts '172.28.x.x'
#         raw_ip = ip_data.split()[3].split('/')[0]
#         # Logic to get the base subnet (e.g., 172.28.0.0/20)
#         # For WSL2 on Win10, the first two octets are usually stable enough
#         parts = raw_ip.split('.')
#         subnet_range = f"{parts[0]}.{parts[1]}.0.0/20"
        
#         print(f"[*] Detected WSL IP: {raw_ip} -> Using Subnet: {subnet_range}")

#         # 2. The PowerShell commands (Note the change to -RemoteAddress)
#         ps_script = f"""
#         Remove-NetFirewallRule -DisplayName 'WSL Kivy Surgical {port}' -ErrorAction SilentlyContinue
#         New-NetFirewallRule -DisplayName 'WSL Kivy Surgical {port}' `
#             -Direction Inbound -Action Allow -Protocol TCP `
#             -LocalPort {port} -RemoteAddress '{subnet_range}' `
#             -InterfaceAlias 'vEthernet (WSL)'
#         """

#         # 3. Encode for Windows
#         encoded_script = base64.b64encode(ps_script.encode('utf-16-le')).decode('utf-8')

#         # 4. Trigger the UAC Admin prompt
#         launch_command = f'Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile", "-EncodedCommand", "{encoded_script}"'
        
#         print(f"[*] Triggering Windows UAC prompt for port {port}...")
#         subprocess.run(["powershell.exe", "-Command", launch_command], check=True)
        
#         print("[+] Check your taskbar for the UAC shield!")

#     except Exception as e:
#         print(f"[!] Failed: {e}")



def check_adb_context():
    try:
        # Check which binary is being called
        which_adb = subprocess.check_output(["which", "adb"]).decode().strip()
        # Check the version and path reported by ADB itself
        version_info = subprocess.check_output(["adb", "version"]).decode().strip()
        print(f"--- ADB DEBUG INFO ---")
        print(f"Python is calling: {which_adb}")
        print(f"{version_info}")
        print(f"----------------------")
    except Exception as e:
        print(f"ADB check failed: {e}")


async def send_app():
    print('*' * 50)
    print(green + 'Connecting to smartphone...')

    devices = get_connected_devices()
    if not devices:
        print(f'{yellow}No connected devices found.')
        return 1

    # Set up ADB port forwarding if USB mode
    if config.STREAM_USING == "USB":
        PORT = config.RELOADER_PORT
        
        adb_cmd = f"adb forward tcp:{PORT} tcp:{PORT}"
        logging.info(adb_cmd)
        os.system(adb_cmd)
        # unique_physical = set(zip(config.PHONE_IPS, (d["model"] for d in devices)))
        host_ip = get_adb_host_ip()
        unique_physical = {(host_ip, d["model"]) for d in devices}
    else:
        unique_physical = {
            (d['wifi_ip'], d['model']) for d in devices if d['wifi_ip'] is not None
        }

    acked_count = 0

    # check_adb_context()

    for device in unique_physical:
        IP = device[0]

        client_socket = await connect_to_server(IP)
        # WORKS
        # if not client_socket and config.STREAM_USING == "USB" and in_wsl():
        #     # in wsl, so check if the correct powershell firewall rule is set in windows with a timeout
        #     run_wsl_firewall_fix(port=PORT)
        #     print(f"{yellow}Attempted to fix windows firewall for wsl2 connection to phone.")
        #     continue

        # if not client_socket and config.STREAM_USING == "USB" and in_wsl():

        #     # if wsl_network_dead():
        #     #     print(f"{red}WSL2 networking is down. Please run: wsl --shutdown")
            
        #     print(f"{yellow}Initial connection blocked. Fixing Windows firewall for WSL2. Waiting for you to approve the UAC prompt...")
        #     await run_wsl_firewall_fix(port=PORT)
            
        #     # Wait up to 30 seconds for the rule to actually appear
        #     rule_found = await wsl_firewall_check_async(PORT)

        #     # rule_found = True
            
        #     if rule_found:
        #         # RETRY the connection now that the gate is open
        #         print(f"{green}Retrying connection to smartphone...")
        #         client_socket = await connect_to_server(IP)
        #     else:
        #         print(f"{red}Timed out waiting for firewall rule. Did you click 'Yes'?")
        #         # Maybe exit or handle failure here
            
        #     continue

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
        header = f"{zip_size}\n".encode()
        await client_socket.send_all(header)
        print(f'DEBUG: Sent header with size {zip_size}')

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

                # ADD THIS:
                if chunks_sent % 10 == 0:
                    mb_sent = total_bytes / (1024 * 1024)
                    mb_total = zip_size / (1024 * 1024)
                    print(f'\r{green}Sent {mb_sent:.1f} / {mb_total:.1f} MB ({chunks_sent} chunks)', end='', flush=True)

        print(green + f'Finished sending app! ({total_bytes} bytes in {chunks_sent} chunks)')

        # # 3. SAFE WRITE SHUTDOWN (USB + Wi‑Fi)
        # import socket
        # try:
        #     client_socket.socket.shutdown(socket.SHUT_WR)
        #     print(f"{green}Write side shutdown (FIN sent).")
        # except Exception as e:
        #     print(f"{yellow}Warning: shutdown(SHUT_WR) failed: {e}")

        # 4. Wait for OK
        min_speed_bytes_per_sec = 0.5 * 1024 * 1024  # 1 MB/s
        timeout = (zip_size / min_speed_bytes_per_sec) + 30
        print(f'{yellow}Waiting ({timeout} seconds) for ACK from smartphone {IP}...')
        ack_ok = False

        try:
            import datetime
            with trio.move_on_after(timeout):
                while True:
                    data = await client_socket.receive_some(16)
                    now = datetime.datetime.now()
                    print(f'RECEIVED: {data!r} at {now}')

                    if data == b'OK':
                        ack_ok = True
                        break

                    if data == b'':
                        await trio.sleep(0.1)
                        continue

        except Exception as e:
            print(f'{red}Error while waiting for ACK: {e}')

        import datetime
        formatted_time = datetime.datetime.now().strftime("%m-%d %H:%M:%S.%f")[:-3]

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


#THIS WORKED START
# async def send_app():
#     print('*' * 50)
#     print(green + 'Connecting to smartphone...')

#     devices = get_connected_devices()
#     if not devices:
#         print(f'{yellow}No connected devices found.')
#         return 1

#     # Set up ADB port forwarding if USB mode
#     if config.STREAM_USING == "USB":
#         PORT = config.RELOADER_PORT
#         os.system(f"adb forward tcp:{PORT} tcp:{PORT}")
#         unique_physical = set(zip(config.PHONE_IPS, (d["model"] for d in devices)))
#     else:
#         unique_physical = {
#             (d['wifi_ip'], d['model']) for d in devices if d['wifi_ip'] is not None
#         }

#     acked_count = 0

#     for device in unique_physical:
#         IP = device[0]

#         client_socket = await connect_to_server(IP)
#         if not client_socket:
#             print(f"{yellow}Couldn't connect to smartphone: {IP}")
#             continue

#         print(f'{yellow} Phone connected successfully: {IP}')
#         print(f'\n{green}Sending app to smartphone...')

#         CHUNK_SIZE = 256 * 1024
#         total_bytes = 0
#         chunks_sent = 0

#         zip_path = 'app_copy.zip'
#         zip_size = os.path.getsize(zip_path) if os.path.exists(zip_path) else 'FILE NOT FOUND'
#         print(f'DEBUG: Opening zip at {os.path.abspath(zip_path)}, size={zip_size}')
#         print(f'DEBUG: Sent {total_bytes} bytes in {chunks_sent} chunks')

#         with open(zip_path, 'rb') as myzip:
#             print(f'DEBUG: file position after open = {myzip.tell()}')
#             print(f'DEBUG: first 4 bytes = {myzip.read(4).hex()}')  # should be 504b0304 for zip
#             myzip.seek(0)  # reset
#             while True:
#                 chunk = myzip.read(CHUNK_SIZE)
#                 if not chunk:
#                     break

#                 try:
#                     await client_socket.send_all(chunk)
#                     chunks_sent += 1
#                     total_bytes += len(chunk)
#                     # print(f'DEBUG: sent chunk {chunks_sent}, {len(chunk)} bytes')
#                 except Exception as e:
#                     print(f'DEBUG: send_all FAILED on chunk {chunks_sent}: {e}')
#                     raise

#                 # await client_socket.send_all(chunk)
#                 # chunks_sent += 1
#                 # total_bytes += len(chunk)

#         print(green + 'Finished sending app!')

#         # ⭐ SAFE WRITE SHUTDOWN (USB + Wi‑Fi compatible)
#         import socket
#         try:
#             # This sends FIN immediately without killing the USB tunnel
#             client_socket.socket.shutdown(socket.SHUT_WR)
#             print(f"{green}Write side shutdown (FIN sent).")
#         except Exception as e:
#             print(f"{yellow}Warning: shutdown(SHUT_WR) failed: {e}")

#         # ⭐ DO NOT SEND EOF — USB ADB will kill the tunnel
#         # await client_socket.send_eof()  # <-- removed

#         # ⭐ Wait for OK
#         timeout = 10
#         # Wait for ACK from phone confirming update applied
#         print(f'{yellow}Waiting ({timeout} seconds) for ACK from smartphone {IP}...')
#         ack_ok = False

#         try:
#             import datetime

#             # Get current time
#             now = datetime.datetime.now()
#             with trio.move_on_after(timeout):
#                 while True:
#                     data = await client_socket.receive_some(16)
#                     print(f'RECEIVED: {data!r} at {datetime.datetime.now()}')

#                     if data == b'OK':
#                         ack_ok = True
#                         break

#                     # If connection closed (b''), just wait for timeout
#                     if data == b'':
#                         await trio.sleep(0.1)
#                         continue

#         except Exception as e:
#             print(f'{red}Error while waiting for ACK: {e}')

#         import datetime

#         # Get current time
#         now = datetime.datetime.now()

#         # Format: Month-Day Hour:Minute:Second.Milliseconds
#         formatted_time = now.strftime("%m-%d %H:%M:%S.%f")[:-3]

#         if ack_ok:
#             print(f'{green}ACK received from {IP}, {formatted_time}')
#             acked_count += 1
#         else:
#             print(f'{yellow}No ACK received from {IP}, {formatted_time}')

#         # Close socket gracefully
#         try:
#             await client_socket.aclose()
#         except Exception:
#             pass

#     print('\n')
#     print(yellow + f'Sent app to {len(unique_physical)} smartphone(s)')
#     if acked_count:
#         print(green + f'ACK confirmed on {acked_count} smartphone(s)')
#     else:
#         print(red + 'No ACKs received')
#     print('*' * 50)

#     return 0 if acked_count > 0 else 1
#THIS WORKED END


# async def send_app():
#     print('*' * 50)
#     print(green + 'Connecting to smartphone...')

#     devices = get_connected_devices()
#     if not devices:
#         print(f'{yellow}No connected devices found.')
#         return 1

#     # Set up ADB port forwarding if USB mode
#     if config.STREAM_USING == "USB":
#         PORT = config.RELOADER_PORT
#         os.system(f"adb forward tcp:{PORT} tcp:{PORT}")
#         # unique_physical = {("127.0.0.1", d['model']) for d in devices}
#         unique_physical = set(zip(config.PHONE_IPS, (d["model"] for d in devices)))


#         # # Get Windows host IP from WSL
#         # def get_windows_host_ip():
#         #     with open("/etc/resolv.conf") as f:
#         #         for line in f:
#         #             if line.startswith("nameserver"):
#         #                 return line.split()[1]
#         #     return "127.0.0.1"  # fallback

#         # windows_ip = get_windows_host_ip()

#         # unique_physical = {(windows_ip, d['model']) for d in devices}
#     else:
#         unique_physical = {
#             (d['wifi_ip'], d['model']) for d in devices if d['wifi_ip'] is not None
#         }

#     acked_count = 0

#     for device in unique_physical:
#         IP = device[0]

#         client_socket = await connect_to_server(IP)
#         if not client_socket:
#             print(f"{yellow}Couldn't connect to smartphone: {IP}")
#             continue

#         print(f'{yellow} Phone connected successfully: {IP}')
#         print(f'\n{green}Sending app to smartphone...')

#         CHUNK_SIZE = 256 * 1024  # 64KB chunks for better throughput
#         total_bytes = 0
#         chunks_sent = 0

#         zip_path = 'app_copy.zip'
#         zip_size = os.path.getsize(zip_path) if os.path.exists(zip_path) else 'FILE NOT FOUND'
#         print(f'DEBUG: Opening zip at {os.path.abspath(zip_path)}, size={zip_size}')
#         print(f'DEBUG: Sent {total_bytes} bytes in {chunks_sent} chunks')

#         with open('app_copy.zip', 'rb') as myzip:
#             print(f'DEBUG: file position after open = {myzip.tell()}')
#             print(f'DEBUG: first 4 bytes = {myzip.read(4).hex()}')  # should be 504b0304 for zip
#             myzip.seek(0)  # reset
#             while True:
#                 chunk = myzip.read(CHUNK_SIZE)
#                 if not chunk:
#                     break

#                 try:
#                     await client_socket.send_all(chunk)
#                     chunks_sent += 1
#                     total_bytes += len(chunk)
#                     print(f'DEBUG: sent chunk {chunks_sent}, {len(chunk)} bytes')
#                 except Exception as e:
#                     print(f'DEBUG: send_all FAILED on chunk {chunks_sent}: {e}')
#                     raise

#                 # chunks_sent += 1
#                 # await client_socket.send_all(chunk)
#                 # total_bytes += len(chunk)

#                 # # Less frequent progress updates to reduce I/O overhead
#                 # if chunks_sent % 10 == 0:
#                 #     mb_sent = total_bytes / (1024 * 1024)
#                 #     print(f'\rSent {mb_sent:.1f} MB', end='', flush=True)

#         print()  # New line after completion

#         # Signal that we're done sending
#         try:
#             await client_socket.send_eof()
#         except Exception as e:
#             print(f'{yellow}Warning: failed to half-close send to {IP}: {e}')

#         print(green + 'Finished sending app!')

#         timeout = 10
#         # Wait for ACK from phone confirming update applied
#         print(f'{yellow}Waiting ({timeout} seconds) for ACK from smartphone {IP}...')
#         ack_ok = False
#         try:
#             import datetime

#             # Get current time
#             now = datetime.datetime.now()
#             with trio.move_on_after(timeout):
#                 while True:
#                     data = await client_socket.receive_some(16)
#                     print(f'RECEIVED: {data!r} at {datetime.datetime.now()}')

#                     if data == b'OK':
#                         ack_ok = True
#                         break

#                     # If connection closed (b''), just wait for timeout
#                     if data == b'':
#                         await trio.sleep(0.1)
#                         continue

#                 # while True:
#                 #     data = await client_socket.receive_some(16)
#                 #     print(f'RECEIVED: {data!r} at {datetime.datetime.now()}')
#                 #     if not data:
#                 #         break
#                 #     if data.startswith(b'OK'):
#                 #         ack_ok = True
#                 #         break
#             # with trio.move_on_after(timeout):  # wait up to timeout seconds for device to process
#             #     data = await client_socket.receive_some(16)
                
#             #     import datetime

#             #     # Get current time
#             #     now = datetime.datetime.now()

#             #     # Format: Month-Day Hour:Minute:Second.Milliseconds
#             #     formatted_time = now.strftime("%m-%d %H:%M:%S.%f")[:-3]
#             #     print('WHAT IS THE DATA?', data, formatted_time)
                
#             #     if data and data.startswith(b'OK'):
#             #         ack_ok = True
#         except Exception as e:
#             print(f'{red}Error while waiting for ACK: {e}')

#         if ack_ok:
#             print(f'{green}ACK received from {IP}')
#             acked_count += 1
#         else:
#             print(f'{yellow}No ACK received from {IP} (device may be busy/minimized)')

#         # Close socket gracefully
#         try:
#             await client_socket.aclose()
#         except Exception:
#             pass

#     print('\n')
#     print(yellow + f'Sent app to {len(unique_physical)} smartphone(s)')
#     if acked_count:
#         print(green + f'ACK confirmed on {acked_count} smartphone(s)')
#     else:
#         print(red + 'No ACKs received')
#     print('*' * 50)

#     # Exit code: 0 if at least one device acknowledged; 1 otherwise
#     return 0 if acked_count > 0 else 1


if __name__ == '__main__':
    exit_code = trio.run(send_app)
    sys.exit(exit_code)
