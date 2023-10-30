import os
import time
from multiprocessing import Process
from threading import Thread

import psutil
from colorama import Fore, init
from icecream import ic
from kivy.utils import platform

from constants import PHONE_IPS, PORT, STREAM_USING

if platform in ["linux", "macosx"]:
    from plyer import notification

red = Fore.RED
green = Fore.GREEN
yellow = Fore.YELLOW
init(autoreset=True)

app_name = (
    [
        line
        for line in open("buildozer.spec", "r").readlines()
        if line.startswith("title")
    ][0]
    .split("=")[1]
    .strip()
)


class Compilation:
    @classmethod
    def start(cls, option):
        """
        Starts the compilation process
        """
        if option == "1":
            print(f"{yellow} Starting compilation")
            t1 = time.time()
            cls.notify_that_compilation_started()
            os.system("buildozer -v android debug deploy run")
            t2 = time.time()
            cls.notify_that_compilation_finished(t2 - t1)
            print(f"{green} Finished compilation")
            cls.debug_and_livestream()
        else:
            cls.debug_and_livestream()

    def notify_that_compilation_started():
        """
        Notifies the user that the compilation started
        """
        if platform in ["linux", "macosx"]:
            notification.notify(
                message=f"Compilation started at {time.strftime('%H:%M:%S')}",
                title=f"Compiling {app_name}",
            )

    def notify_that_compilation_finished(time):
        """
        Notifies the user that the compilation finished
        """
        if platform in ["linux", "macosx"]:
            notification.notify(
                message=f"Compilation finished in {round(time, 2)} seconds",
                title=f"Compiled {app_name}",
            )

    @classmethod
    def debug_and_livestream(cls):
        proc = Process(target=cls.debug)
        proc2 = Process(target=cls.livestream)
        proc.start()
        proc2.start()
        while True:
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                proc.terminate()
                proc2.terminate()
                break

    @classmethod
    def debug_on_usb(cls):
        ic()
        os.system("adb logcat | grep 'I python'")

    @classmethod
    def debug_on_wifi(cls):
        ic()
        os.system(f"adb tcpip {PORT}")

        def start_logcat(IP, PORT):
            print(f"Connecting to {IP}")
            os.system(f"adb connect {IP}")
            print("Connected")

            print("Starting logcat")
            os.system(f"adb -s {IP}:{PORT} logcat | grep 'I python'")
            print("Finished logcat")

        for IP in PHONE_IPS:
            # start each logcat on a thread
            t = Thread(target=start_logcat, args=(IP, PORT))
            t.start()

    @classmethod
    def debug(cls):
        os.system("adb disconnect")
        os.system("adb kill-server")
        os.system("adb start-server")

        print("Clearing logcat")
        os.system("adb logcat -c")
        print("Logcat cleared")

        if STREAM_USING == "USB":
            cls.debug_on_usb()
            return
        elif STREAM_USING == "WIFI":
            cls.debug_on_wifi()
            return

    def livestream():
        if STREAM_USING == "WIFI":
            time.sleep(3)

        for proc in psutil.process_iter():
            try:
                if proc.name() == "scrcpy":
                    print("yes")
                    break
            except psutil.NoSuchProcess:
                print("error")
        else:
            print("Starting scrcpy")
            command = "scrcpy --window-x 1200 --window-y 100 --window-width 280 --always-on-top"
            if STREAM_USING == "USB":
                os.system(f"{command} -d")
            elif STREAM_USING == "WIFI":
                os.system(f"{command} -e")


if __name__ == "__main__":
    print(f"{yellow} Choose an option:")
    option = input("1 - Compile, debug and livestream\n2 - Debug and livestream\n")
    Compilation.start(option)
