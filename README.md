# kivy-reloader

Hot reload your Kivy app on multiple phones and computer in real-time.

This tool allows you to instantly update your Kivy app on multiple devices simultaneously by pressing `Ctrl+S`, saving your precious development time and effort.

## How to use

```python
from kivy_reloader import App

class MainApp(App):
    def build_and_reload(self):
        from screens.main_screen import MainScreen

        return MainScreen(name="Main Screen")

MainApp()
```

https://github.com/kivy-school/kivy-reloader/assets/23220309/f1459d7e-ca53-4ed6-b4d1-980cdae4ce16

# Prerequisites

Install `scrcpy` on your operating system: [Linux](https://github.com/Genymobile/scrcpy/blob/master/doc/linux.md), [Windows](https://github.com/Genymobile/scrcpy/blob/master/doc/windows.md) or [macOS](https://github.com/Genymobile/scrcpy/blob/master/doc/macos.md). You will be able to control your device from your computer.

Install `kivy`: choose your operating system on [Kivy School Tutorial](https://kivyschool.com/installation/).

# How to install:

I recommend you to use `poetry` to install `kivy-reloader`.

## Option 1) Using poetry - recommended

`poetry add kivy-reloader`

## Option 2) Using pip

`pip install kivy-reloader`

--------------------------------------------------

# Configure the constants

The first time you run `from kivy_reloader import App`, you will be prompted on the terminal:

![image](https://github.com/kivy-school/kivy-reloader/assets/23220309/bf414b93-c5e5-421f-bba6-4a08b7bf7ccb)

Just press enter. This will create a file called `settings.py` on your project folder.

![image](https://github.com/kivy-school/kivy-reloader/assets/23220309/adad51b4-c005-448f-a1b6-930abea2e0e5)

Every line has an explanation above. The most important constants on this file are:
1) **PHONE_IPS**: Put the IP of your phone here. You can find the IP of your Android phone on: Settings > About phone > Status > IP Address.
![image](https://github.com/kivy-school/kivy-reloader/assets/23220309/afd354fc-1894-4d99-b09d-8ef11ab4d763)
2) **HOT_RELOAD_ON_PHONE**: Set it to True to hot heload on your phone when you press `Ctrl+S`
3) **WATCHED_FOLDERS_RECURSIVELY**: This is a list of folder names, for example `["screens", "components"]. If _any_ file inside these folders change, your Kivy app will reload.
4) **WATCHED_KV_FOLDERS_RECURSIVELY**: This is a list of folder names, for example `["screens", "components"]`. This is where the Reloader will find your `.kv` files to reload them every time you press `Ctrl+S`.

Open the file `settings.py` and explore the other constants.

This message will also appear for you on the first time you use Kivy Reloader.

![image](https://github.com/kivy-school/kivy-reloader/assets/23220309/eda33c70-b75e-4e5d-a1d2-a69925c3cabc)

Just press enter. This will create a file called `buildozer.spec` on your project folder.

--------------------------------------------------

# How to use:

1. Connect your phone to the computer using a USB cable.
2. Create a script `compile.py` with the following code:
```python
from kivy_reloader import compile_app

compile_app.start()
```
3. Run on the terminal `python compile.py`, type `1` and press enter. Buildozer will compile the app and deploy on your phone.
   ![image](https://github.com/kivy-school/kivy-reloader/assets/23220309/81f6689e-e8bb-4fe5-a91c-dd88f187616f)
4. Once the app is on your phone, run `python main.py` and the hot reload will be already working. Just press `Ctrl+S` in any file inside `screens` folder or `main.py` and your app will be updated on computer and phone at the same time.

--------------------------------------------------

### Do you want to test directly from this repo?

Clone this project, open the folder on terminal and type:

1. `poetry shell`
2. `poetry install`
3. Update `settings.py` with your phone IP, and set **HOT_RELOAD_ON_PHONE** to True.
4. `python main.py`
5. `python compile.py` and press 1, enter.
6. Wait the compilation to finish on your phone.
7. Enjoy the Kivy Reloader!
