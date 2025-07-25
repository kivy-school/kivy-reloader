import trio
from colorama import Fore, init

from kivy_reloader.config import config
from kivy_reloader.utils import get_connected_devices

red = Fore.RED
green = Fore.GREEN
yellow = Fore.YELLOW
white = Fore.WHITE
init(autoreset=True)


async def connect_to_server(IP):
    try:
        PORT = config.RELOADER_PORT
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
        return

    unique_physical = {
        (d['wifi_ip'], d['model']) for d in devices if d['wifi_ip'] is not None
    }
    for device in unique_physical:
        IP = device[0]
        client_socket = await connect_to_server(IP)
        if not client_socket:
            print(f"{yellow}Couldn't connect to smartphone: {IP}")
            return
        print(f'{yellow} Phone connected successfully: {IP}')
        print(f'\n{green}Sending app to smartphone...')
        CHUNK_SIZE = 4096
        with open(
            'app_copy.zip',
            'rb',
        ) as myzip:
            for chunk in iter(lambda: myzip.read(CHUNK_SIZE), b''):
                print('Sending chunk')
                await client_socket.send_all(chunk)
        print(green + 'Finished sending app!')
    print('\n')
    print(yellow + f'Sent app to {len(unique_physical)} smartphone(s)')
    print('*' * 50)


trio.run(send_app)
