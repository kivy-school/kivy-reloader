# kivy-reloader
Hot reload your Kivy app on multiple phones and computer in real-time.

This tool allows you to instantly update your Kivy app on multiple devices simultaneously by pressing `Ctrl+S`, saving your precious development time and effort. 

https://github.com/kivy-school/kivy-reloader/assets/23220309/9a7c33b4-3020-4b82-ba7d-b16c7cc90355

# Prerequisites
Install `scrcpy` on your operating system: [Linux](https://github.com/Genymobile/scrcpy/blob/master/doc/linux.md), [Windows](https://github.com/Genymobile/scrcpy/blob/master/doc/windows.md) or [macOS](https://github.com/Genymobile/scrcpy/blob/master/doc/macos.md). You will be able to control your device from your computer.

Install `kivy`: choose your operating system on [Kivy School Tutorial](https://kivyschool.com/installation/).

# Installing the project

Clone this project, open the folder on terminal and type: 
1) `poetry shell`
2) `poetry install`

# Configure the constants
Open the file `constants.py` and put the IP of your phone on the `PHONE_IPS` constant. You can find the IP of your Android phone on: Settings > About phone > Status > IP Address.

![image](https://github.com/kivy-school/kivy-reloader/assets/23220309/afd354fc-1894-4d99-b09d-8ef11ab4d763)

# How to use:
1) Connect your phone to the computer using a USB cable.
2) Run on the terminal `python compile_app.py`, type `1` and press enter. Buildozer will compile the app and deploy on your phone.
![image](https://github.com/kivy-school/kivy-reloader/assets/23220309/81f6689e-e8bb-4fe5-a91c-dd88f187616f)
3) Once the app is on your phone, run `python main.py` and the hot reload will be already working. Just press `Ctrl+S` in any file inside `screens` folder or `main.py` and your app will be updated on computer and phone at the same time.
