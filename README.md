# Kivy Reloader

<p align="center">
  <a href="https://www.youtube.com/watch?v=WLAI01e-8OQ">
    <img src="https://img.youtube.com/vi/WLAI01e-8OQ/hqdefault.jpg" alt="Kivy Reloader Showcase" style="max-width: 100%; width: 90%; height: auto;">
  </a>
</p>

Hot reload your Kivy app on multiple Android phones, emulators and computer at the same time, in real-time.

This tool allows you to instantly update your Kivy app on multiple devices simultaneously by pressing <kbd>Ctrl</kbd> + <kbd>S</kbd>, without having to restart / recompile every time you make a change, saving your precious development time and effort.

Check out the [Kivy School tutorial](https://kivyschool.com/kivy-reloader/) to learn how to use this tool, or follow the documentation below.

![kivy-reloader](https://github.com/user-attachments/assets/3f02a18b-b541-415c-80b2-5564893cf8ea)
![image](https://github.com/user-attachments/assets/4863801d-3822-4365-8c6b-7043e4563d70)

---

### I am too impatient to read the tutorial, I want to see it working RIGHT NOW!

Clone this project, open the folder on terminal and type:

1. `git clone https://github.com/kivy-school/kivy-reloader`
2. `cd kivy-reloader`
3. `poetry shell`
4. `poetry install`
5. Update the `kivy-reloader.toml` file with your phone IP and make sure `HOT_RELOAD_ON_PHONE` is set to `true`.
6. `adb install bin/kivy_super_reloader-0.1-armeabi-v7a_arm64-v8a-debug.apk`
7. `python main.py`

Keep calm and enjoy the Kivy Reloader! 😄

---

# Tutorial

## Prerequisites

You must have followed our [installation guide](https://kivyschool.com/kivy-installation/) and you must have the basic tools installed and know how to use them:

- Poetry
- Pyenv
- Git
- Scrcpy

  ### Install Scrcpy

  You must install `scrcpy` on your computer. It comes with [adb](https://developer.android.com/tools/adb), so you don't need to install it separately.

  - Install `scrcpy` on your operating system: [Linux](https://github.com/Genymobile/scrcpy/blob/master/doc/linux.md), [Windows](https://github.com/Genymobile/scrcpy/blob/master/doc/windows.md) or [macOS](https://github.com/Genymobile/scrcpy/blob/master/doc/macos.md). You will be able to control your device from your computer.

---

## How it works

Kivy Reloader is using `Kaki` under the hood, which uses `watchdog` to watch for file changes.
You configure on `kivy-reloader.toml` the folders / files you want to watch for changes.
When a change is detected on any of these files or folders, Kivy Reloader updates and reloads your app on all the devices you have configured (they need to be connected to the same network).

---

## How to setup

I recommend you to use `poetry` to install `kivy-reloader`.

#### 1. Start the Poetry Wizard

Start a poetry project with the following command and follow the wizard instructions.

```
poetry init
```

After the wizard is finished, the `pyproject.toml` file will be created in the project directory.

#### 2. Activate the virtual environment

Type `poetry shell` on the terminal and press enter.

```
poetry shell
```

#### 3. Install the dependencies

Install the dependencies by typing `poetry add kivy-reloader` on the terminal and press enter.

```
poetry add kivy-reloader
```

---

## Configure Kivy Reloader

After installing `kivy-reloader`, on the project folder, type on the terminal `kivy-reloader init`.

```
kivy-reloader init
```

This is going to create two files on your project folder: `kivy-reloader.toml` and `buildozer.spec`.
The first time you run `kivy-reloader init`, you will see on the terminal:

![image](https://github.com/user-attachments/assets/b88091bf-4979-44e9-b8b3-a29a7fbc110d)

This is the `kivy-reloader.toml` file that has been created on your project folder.

![image](https://github.com/user-attachments/assets/0c686c32-7aa8-4123-812b-8ea5d2e6f0cb)

#### Configure the `kivy-reloader.toml` file:

Every line has an explanation above. The most important constants on this file are:

1. **PHONE_IPS**: Put the IP of your phone here.
   You can find the IP of your Android phone on: **Settings > About phone > Status > IP Address**.
   ![image](https://github.com/kivy-school/kivy-reloader/assets/23220309/afd354fc-1894-4d99-b09d-8ef11ab4d763)
2. **HOT_RELOAD_ON_PHONE**: Set it to `true` to hot heload on your phone when you press `Ctrl+S`
3. **FULL_RELOAD_FILES**: This is a list of file names that will trigger a live reload (your Kivy app will restart) when they change.
4. **WATCHED_FOLDERS_RECURSIVELY**: This is a list of folder names, for example `["screens", "components"]`. If _any_ file inside these folders change, your Kivy app will hot reload.

The `kivy-reloader init` also creates a file called `buildozer.spec` on your project folder. It has the minimal `buildozer.spec` that you can use to make your app work with Kivy Reloader.

---

## How to use

Instead of importing from `kivy.app`, import from `kivy_reloader.app`.
Start the app within an async event loop using `trio`.

On this tutorial we are going to show 3 possible different structures of your beautiful app.

### Beautiful App structure 0 (beginner example):

If you are a super beginner in Kivy and just want to have a single file with a Kivy app.

```
├── main.py
```

Create a file `main.py` and paste this code:

```python
import trio
from kivy.lang import Builder

from kivy_reloader.app import App

kv = """
Button:
    text: "Hello World"
"""


class MainApp(App):
    def build(self):
        return Builder.load_string(kv)


app = MainApp()
trio.run(app.async_run, "trio")
```

### Beautiful App structure 1 (intermediate example):

- Create a file called `main.py`, a file called `app.py` and a folder called `screens`.

- Inside the `screens` folder, create two files: `main_screen.kv` and `main_screen.py`.

```
.
├── main.py
├── app.py
└── screens
    ├── main_screen.kv
    └── main_screen.py
```

`main.py`

```python
import trio

from app import MainApp

app = MainApp()
trio.run(app.async_run, "trio")
```

`app.py`

```python
from kivy_reloader.app import App
from screens.main_screen import MainScreen

class MainApp(App):
    def build(self):
        return MainScreen()
```

`screens/main_screen.kv`

```yaml
<MainScreen>:
    BoxLayout:
        orientation: "vertical"
        Button:
            text: "Welcome to Kivy Reloader!"
```

`screens/main_screen.py`

```python
import os

from kivy.uix.screenmanager import Screen

from kivy_reloader.utils import load_kv_path

main_screen_kv = os.path.join("screens", "main_screen.kv")
load_kv_path(main_screen_kv)


class MainScreen(Screen):
    pass
```

### Beautiful App structure 2 (advanced example):

This is the recommended way of structuring your app.

- Create a file called `main.py` and a folder called `beautifulapp`.
- Inside the `beautifulapp` folder, create a file called `__init__.py`.
- Inside the `beautifulapp` folder, create a folder called `screens`.
- Inside the `screens` folder, create two files: `main_screen.kv` and `main_screen.py`.

```
.
├── beautifulapp
│   ├── __init__.py
│   └── screens
│       ├── main_screen.kv
│       └── main_screen.py
├── main.py
```

`main.py`:

```python
import trio

from beautifulapp import MainApp

app = MainApp()
trio.run(app.async_run, "trio")
```

`beautifulapp/__init__.py`:

```python
from beautifulapp.screens.main_screen import MainScreen
from kivy_reloader.app import App


class MainApp(App):
    def build(self):
        return MainScreen()
```

`beautifulapp/screens/main_screen.kv`

```yaml
<MainScreen>:
    BoxLayout:
        orientation: "vertical"
        Button:
            text: "Welcome to Kivy Reloader!"
```

`beautifulapp/screens/main_screen.py`

```python
import os

from kivy.uix.screenmanager import Screen

from kivy_reloader.utils import load_kv_path

main_screen_kv = os.path.join("beautifulapp", "screens", "main_screen.kv")
load_kv_path(main_screen_kv)


class MainScreen(Screen):
    pass
```

---

## Run your app

Type `python main.py` on the terminal and your app will start. You can see the logs on the terminal.
When you change any file (from the watched folders you specified on the `kivy-reloader.toml` file), your app will reload.

---

## How to compile and hot reload on Android:

1. Connect your phone to the computer using a USB cable.
2. [Enable developer options](https://developer.android.com/studio/debug/dev-options#enable) and [enable USB debugging](https://developer.android.com/studio/debug/dev-options#debugging) on your phone.
3. On the terminal, type `kivy-reloader run`:

```
kivy-reloader run
```

![kivy-reloader cli](https://github.com/user-attachments/assets/20d8de57-cef3-4f6a-a31e-081b878144d5)

This is a CLI application that will:

- 1. Compile your app (generate `.apk` file) and deploy it on your phone.
- 2. Start `scrcpy` to mirror your phone screen on your computer and show the logs from your app on the terminal using logcat.
- 3. Create a `.aab` file that will be used to deploy your app on Google Play Store.
- 4. Restart the adb server for you if needed.

You can easily control the CLI application using <kbd>↑</kbd> or <kbd>↓</kbd> arrows, and press <kbd>ENTER ↵</kbd> or <kbd>→</kbd> to select the option you want.

4. Choose the first option and Buildozer will compile the app (create a .apk file) and deploy it on your phone. Once the app is on your phone, run `python main.py` and the hot reload will be already working.

Just press <kbd>Ctrl</kbd> + <kbd>S</kbd> in any file inside `screens` folder or `main.py` and your app will be updated on computer and phone at the same time. (assuming you have configured the `kivy-reloader.toml` file correctly).

## Contribution

If you have any idea or suggestion, please open an issue or a pull request.

## Do you need help?

If you need help with Kivy Reloader, you can ask on [Kivy Discord](https://chat.kivy.org/) support channels. We'll be happy to help you.
