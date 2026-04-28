import sys
import os
import logging
import trio
from colorama import Fore, init
import subprocess
import time
import base64

from kivy_reloader.config import config
from kivy_reloader.utils import get_connected_devices, in_wsl

red = Fore.RED
green = Fore.GREEN
yellow = Fore.YELLOW
white = Fore.WHITE
init(autoreset=True)


async def connect_to_server(IP):
    try:
        print("what", config.RELOADER_PORT)
        PORT = int(config.RELOADER_PORT)
        print(f'Connecting to IP: {green}{IP}{white} and PORT: {green}{PORT}')
        with trio.move_on_after(1):
            client_socket = await trio.open_tcp_stream(IP, PORT)
            return client_socket
    except Exception as e:
        print(f'{red}Error: {e}')
        return None

async def send_app():
    print('*' * 50)
    print(green + 'Connecting to smartphone...')

    devices = get_connected_devices()
    if not devices:
        print(f'{yellow}No connected devices found.')
        return 1

    def run_ps(script):
        """Run PowerShell from WSL using Base64 encoding to avoid quoting issues."""
        # Ensure no leading/trailing whitespace in the script before encoding
        clean_script = script.strip()
        # PowerShell expects UTF-16LE for encoded commands
        encoded_script = base64.b64encode(script.encode('utf-16-le')).decode()
        
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-EncodedCommand", encoded_script],
            capture_output=True,
            text=True
        )
        
        output = result.stdout.strip()
        logging.info(f"PS Command: '{script}'")
        logging.info(f"PS Output: '{output}'")
        return output

    
    # def run_ps(script):
    #     """Run PowerShell from WSL and return stdout."""
    #     # Wrap the script in double quotes so PowerShell doesn't split it on spaces
    #     result = subprocess.run(
    #         ["powershell.exe", "-NoProfile", "-Command", f'"{script}"'],
    #         capture_output=True,
    #         text=True
    #     )
    #     # Add this to see what WSL thinks is happening
    #     rule_name="ADB WSL Dynamic Ports"
    #     debug_cmd = f"powershell.exe -Command \"Get-NetFirewallRule -Name '{rule_name}'\""

    #     logging.info(f"DEBUG COMMAND: {debug_cmd}")
    #     return result.stdout.strip()

    # def run_ps(script):
    #     """Run PowerShell from WSL and return stdout."""
    #     result = subprocess.run(
    #         ["powershell.exe", "-NoProfile", "-Command", script],
    #         capture_output=True,
    #         text=True
    #     )
    #     # Add this to see what WSL thinks is happening
    #     rule_name="ADB WSL Dynamic Ports"
    #     debug_cmd = f"powershell.exe -Command \"Get-NetFirewallRule -Name '{rule_name}'\""

    #     logging.info(f"DEBUG COMMAND: {debug_cmd}")

    #     return result.stdout.strip()

    def ensure_firewall_rule(rule_name, port_range, timeout_time = 30):
# $rule = Get-NetFirewallRule -Name "{rule_name}" -PolicyStore ActiveStore -ErrorAction SilentlyContinue
        ps_check2 = fr'''
$rule = Get-NetFirewallRule -Name "{rule_name}" -PolicyStore PersistentStore -ErrorAction SilentlyContinue        
Write-Output $rule
Write-Output "Type: $($rule.GetType().Name)"
Write-Output "Rule: $($rule.Name)"
'''
        ps_check = fr'''
# Specify the PolicyStore to ensure WSL can see the Admin-created rule
$rule = Get-NetFirewallRule -Name "{rule_name}" -PolicyStore ActiveStore -ErrorAction SilentlyContinue
if (-not $rule) {{
    $rule = Get-NetFirewallRule -Name "{rule_name}" -PolicyStore PersistentStore -ErrorAction SilentlyContinue
}}

if (-not $rule) {{
    Write-Output "MISSING"
    exit
}}

$port = ($rule | Get-NetFirewallPortFilter).LocalPort
if ($port) {{
    Write-Output ([string]$port)
}} else {{
    Write-Output "FOUND_BUT_NO_PORT"
}}
'''



#         ps_check = fr'''
# $rule = Get-NetFirewallRule -Name "{rule_name}" -ErrorAction SilentlyContinue
# if (-not $rule) {{
#     Write-Output "MISSING"
#     exit
# }}
# $port = ($rule | Get-NetFirewallPortFilter).LocalPort
# if ($port) {{
#     Write-Output ([string]$port)
# }} else {{
#     Write-Output "FOUND_BUT_NO_PORT"
# }}
# '''


#         ps_check = fr'''
# $rule = Get-NetFirewallRule -Name '{rule_name}' -ErrorAction SilentlyContinue
# if (-not $rule) {{
#     Write-Output "MISSING"
#     exit
# }}
# # Explicitly expand the property and convert to string
# $port = ($rule | Get-NetFirewallPortFilter).LocalPort
# if ($port) {{
#     Write-Output ([string]$port)
# }} else {{
#     Write-Output "FOUND_BUT_NO_PORT"
# }}
# '''

        # kinda worked but didn't
#         ps_check = fr'''
# $rule = Get-NetFirewallRule -Name '{rule_name}' -ErrorAction SilentlyContinue
# if (-not $rule) {{
#     Write-Output "MISSING"
#     exit
# }}
# $port = $rule | Get-NetFirewallPortFilter
# Write-Output $port.LocalPort
# '''

#         ps_check = fr'''
#     $rule = Get-NetFirewallRule -Name "{rule_name}" -ErrorAction SilentlyContinue
#     if (-not $rule) {{
#         Write-Output "MISSING"
#         exit
#     }}
#     $port = $rule | Get-NetFirewallPortFilter
#     Write-Output $port.LocalPort
# '''

        result = run_ps(ps_check2)
        result = run_ps(ps_check)
        
        if result == "MISSING":
            print(f"{red}[Firewall] Rule '{rule_name}' missing → creating new one. Please accept on Windows Powershell")
            # Use a here-string passed as encoded command to avoid quoting hell
#             create_script = f'''
# New-NetFirewallRule -DisplayName "{rule_name}" -Direction Inbound -LocalPort {port_range} -Protocol TCP -Action Allow -RemoteAddress 172.16.0.0/12
# '''
#             # Updated create_script with explicit -Name
#             create_script = f'''
# if (-not (Get-NetFirewallRule -Name "{rule_name}" -ErrorAction SilentlyContinue)) {{
#     New-NetFirewallRule -Name "{rule_name}" -Name "{rule_name}" -Direction Inbound -LocalPort {port_range} -Protocol TCP -Action Allow -RemoteAddress 172.16.0.0/12
# }}
# '''
            create_script = f'''
if (-not (Get-NetFirewallRule -Name "{rule_name}" -ErrorAction SilentlyContinue)) {{
    New-NetFirewallRule -Name "{rule_name}" `
        -DisplayName "{rule_name}" `
        -Direction Inbound -LocalPort {port_range} -Protocol TCP `
        -Action Allow -RemoteAddress 172.16.0.0/12
}}
'''


            encoded = __import__('base64').b64encode(
                create_script.encode('utf-16-le')
            ).decode()
            subprocess.run([
                "powershell.exe", "-Command",
                f'Start-Process powershell -Verb RunAs -ArgumentList "-EncodedCommand {encoded}"'
            ])
        else:
            existing_ports = result
            if port_range in existing_ports:
                print(f"[Firewall] Rule '{rule_name}' already includes {port_range}")
                return True
            print(f"[Firewall] Rule exists but missing {port_range} → widening")
            new_ports = existing_ports + "," + port_range
            widen_script = f'''
Set-NetFirewallRule -Name "{rule_name}" -LocalPort "{new_ports}"
'''

            encoded = __import__('base64').b64encode(
                widen_script.encode('utf-16-le')
            ).decode()
            subprocess.run([
                "powershell.exe", "-Command",
                f'Start-Process powershell -Verb RunAs -ArgumentList "-EncodedCommand {encoded}"'
            ])
        for _ in range(timeout_time):
            check = run_ps(ps_check)
            logging.info(f"WHAT IS PS CHECK SAYING IN TIMEOUT? {str(check)}")
            if check != "MISSING" and port_range in check:
                print(f"[Firewall] Rule '{rule_name}' verified")
                return True
            time.sleep(1)
        print(f"{red}[Firewall] ERROR: Rule '{rule_name}' did not appear within timeout {timeout_time}")
        return False

    # Set up ADB port forwarding if USB mode
    if config.STREAM_USING == "USB":
        if in_wsl:
            # in wsl, so check if the correct powershell firewall rule is set in windows with a timeout
            ensure_firewall_rule(
                rule_name="ADB WSL Dynamic Ports",
                port_range=str(config.RELOADER_PORT)
            )
        PORT = config.RELOADER_PORT
        adb_cmd = f"adb forward tcp:{PORT} tcp:{PORT}"
        logging.info(adb_cmd)
        os.system(adb_cmd)
        unique_physical = set(zip(config.PHONE_IPS, (d["model"] for d in devices)))
    else:
        unique_physical = {
            (d['wifi_ip'], d['model']) for d in devices if d['wifi_ip'] is not None
        }

    acked_count = 0
 
    def check_adb_context():
        import subprocess
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

    # check_adb_context()

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

        print(green + f'Finished sending app! ({total_bytes} bytes in {chunks_sent} chunks)')

        # # 3. SAFE WRITE SHUTDOWN (USB + Wi‑Fi)
        # import socket
        # try:
        #     client_socket.socket.shutdown(socket.SHUT_WR)
        #     print(f"{green}Write side shutdown (FIN sent).")
        # except Exception as e:
        #     print(f"{yellow}Warning: shutdown(SHUT_WR) failed: {e}")

        # 4. Wait for OK
        timeout = 10
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
