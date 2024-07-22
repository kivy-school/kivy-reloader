# Kivy Reloader

Hot reload your Kivy app on multiple phones and computer in real-time.

This tool allows you to instantly update your Kivy app on multiple devices simultaneously by pressing `Ctrl+S`, saving your precious development time and effort.

![image](https://github.com/user-attachments/assets/4863801d-3822-4365-8c6b-7043e4563d70)

---

### I am too impatient to read the tutorial, I want to see it working RIGHT NOW!

Clone this project, open the folder on terminal and type:

1. `poetry shell`
2. `poetry install`
3. Update the `kivy-reloader.toml` file with your phone IP.
4. `adb install bin/kivy_super_reloader-0.1-armeabi-v7a_arm64-v8a-debug.apk`
5. `python main.py`
6. Keep calm and enjoy the Kivy Reloader! 😄

---

## How to use

Instead of importing from `kivy.app`, import from `kivy_reloader.app`.
Start the app within an async event loop using `trio`.

On this tutorial we are going to show 3 possible different structures of your beautiful app.

### Beautiful App structure 0:

Suppose your beautiful app has only one file:

```
├── main.py
```

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

Start your app with `python main.py`.

### Beautiful App structure 1:

Suppose your beautiful app has this tree structure:

```
.
├── main.py
└── screens
    ├── main_screen.kv
    └── main_screen.py
```

```python
import trio

from kivy_reloader.app import App

class MainApp(App):
    def build(self):
        from screens.main_screen import MainScreen

        return MainScreen(name="Main Screen")

app = MainApp()
trio.run(app.async_run, "trio")
```

Start your app with `python main.py`.

### Beautiful App structure 2:

Suppose your beautiful app has this tree structure (recommended):

```
.
├── beautifulapp
│ ├── __init__.py
│ └── screens
│ ├── main_screen.kv
│ └── main_screen.py
├── main.py
```

`main.py`:

```python
import trio

from beautifulapp import app

trio.run(app.async_run, "trio")
```

`beautifulapp/__init__.py`:

```python
from kivy_reloader.app import App


class MainApp(App):
    def build(self):
        from .screens.main_screen import MainScreen

        return MainScreen(name="Main Screen")


app = MainApp()
```

Start your app with `python main.py`.

# Prerequisites

Install `scrcpy` on your operating system: [Linux](https://github.com/Genymobile/scrcpy/blob/master/doc/linux.md), [Windows](https://github.com/Genymobile/scrcpy/blob/master/doc/windows.md) or [macOS](https://github.com/Genymobile/scrcpy/blob/master/doc/macos.md). You will be able to control your device from your computer.

Install `kivy`: choose your operating system on [Kivy School Tutorial](https://kivyschool.com/installation/).

# How to install:

I recommend you to use `poetry` to install `kivy-reloader`.

## Option 1) Using poetry - recommended

`poetry add kivy-reloader`

## Option 2) Using pip

`pip install kivy-reloader`

---

# Configure Kivy Reloader

After installing `kivy-reloader`, on the project folder, type on the terminal `kivy-reloader init`.
This is going to create two files on your project folder: `kivy-reloader.toml` and `buildozer.spec`.

# Configure the `kivy-reloader.toml` file:

The first time you run `kivy-reloader init`, you will see on the terminal:

![image](https://github.com/user-attachments/assets/b88091bf-4979-44e9-b8b3-a29a7fbc110d)

This is the `kivy-reloader.toml` that has been created on your project folder.

![image](https://github.com/user-attachments/assets/afab6aad-3e13-4505-bd59-bc9a95e23459)

Every line has an explanation above. The most important constants on this file are:

1. **PHONE_IPS**: Put the IP of your phone here.
   You can find the IP of your Android phone on: **Settings > About phone > Status > IP Address**.
   ![image](https://github.com/kivy-school/kivy-reloader/assets/23220309/afd354fc-1894-4d99-b09d-8ef11ab4d763)
2. **HOT_RELOAD_ON_PHONE**: Set it to `True` to hot heload on your phone when you press `Ctrl+S`
3. **WATCHED_FOLDERS_RECURSIVELY**: This is a list of folder names, for example `["screens", "components"]`. If _any_ file inside these folders change, your Kivy app will reload.
4. **WATCHED_KV_FOLDERS_RECURSIVELY**: This is a list of folder names, for example `["screens", "components"]`. This is where the Reloader will find your `.kv` files to reload them every time you press `Ctrl+S`.

The `kivy-reloader init` also creates a file called `buildozer.spec` on your project folder. It has the minimal `buildozer.spec` that you can use to make your app work with Kivy Reloader.

---

# How to compile and hot reload on Android:

1. Connect your phone to the computer using a USB cable.
2. [Enable developer options](https://developer.android.com/studio/debug/dev-options#enable) and [enable USB debugging](https://developer.android.com/studio/debug/dev-options#debugging) on your phone.
3. Create a script `compile.py` with the following code:

```python
from kivy_reloader import compile_app

compile_app.start()
```

3. Run on the terminal `python compile.py`.
   ![image](https://github.com/user-attachments/assets/3ae3823b-b2ca-4e3f-a487-a6c4bfddef34)

4. You can change the selected option by using UP ↑ / DOWN ↓ arrows and press ENTER. Choose the first option and Buildozer will compile the app and deploy on your phone. Once the app is on your phone, run `python main.py` and the hot reload will be already working. Just press `Ctrl+S` in any file inside `screens` folder or `main.py` and your app will be updated on computer and phone at the same time.

---

### Do you want to test directly from this repo?

Clone this project, open the folder on terminal and type:

1. `poetry shell`
2. `poetry install`
3. Update the `kivy-reloader.toml` file with your phone IP.
4. `python main.py`
5. `python compile.py` and press enter.
6. Wait the compilation to finish on your phone.
7. Enjoy the Kivy Reloader!
