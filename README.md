# Kivy Reloader

> *Hot reload your Kivy app on multiple Android phones, emulators and computer at the same time, in real‑time.*

<p align="center">
  <img src="https://kivyschool.com/kivy-reloader/assets/kivy-reloader.gif" alt="Kivy Reloader Demo" width="720" />
</p>

This tool allows you to instantly update your Kivy app on multiple devices simultaneously by pressing <kbd>Ctrl</kbd> + <kbd>S</kbd>, without having to restart / recompile every time you make a change, saving your precious development time and effort.
It uses **[Kaki]** (file watching via `watchdog`) under the hood and a small **Trio** server on-device to receive file updates.

Check out the [📚 Kivy School tutorial](https://kivyschool.com/kivy-reloader/) to learn how to use this tool, or follow the documentation below.

- 📚 Full docs: **[https://kivyschool.com/kivy-reloader/](https://kivyschool.com/kivy-reloader/)**
- Install: [https://kivyschool.com/kivy-reloader/installation/](https://kivyschool.com/kivy-reloader/installation/)
- How to use: [https://kivyschool.com/kivy-reloader/how-to-use/](https://kivyschool.com/kivy-reloader/how-to-use/)

---

## Quickstart

### 1) Install the toolchain + helpers

Pick your OS and run the one‑liners below. These scripts set up the Android toolchain, `uv`, Buildozer deps, scrcpy, bundletool, etc.

#### Linux

```bash
curl -LsSf https://kivyschool.com/kivy-android-ubuntu.sh | bash
```

#### macOS

> After installing Homebrew, **close & reopen** the terminal so `brew` is in PATH.

```bash
# Install Homebrew (if needed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# System deps + OpenJDK 17 and symlink so macOS tools can find it
brew install android-platform-tools openjdk@17 autoconf automake libtool pkg-config cmake openssl
sudo ln -sfn /opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk \
  /Library/Java/JavaVirtualMachines/openjdk-17.jdk

# Kivy Reloader setup
curl -LsSf https://kivyschool.com/kivy-android-macos.sh | sh
```

#### Windows

Run **PowerShell as Administrator**:

```powershell
# Base setup (scrcpy + adb init)
powershell -ExecutionPolicy ByPass -c "irm https://kivyschool.com/kivy-android-windows.ps1 | iex"

# Install WSL2 + Ubuntu 24.04
wsl --install -d Ubuntu-24.04
```

Then, inside the new **Ubuntu** terminal:

```bash
curl -LsSf https://kivyschool.com/kivy-android-wsl2.sh | bash
```

---

### 2) Create a tiny demo project (pick one)

#### Beginner (single file)

```bash
mkdir kivyschool-hello
cd kivyschool-hello
uv init
uv add kivy-reloader
```

Project tree:

```
kivyschool-hello
├── main.py
├── pyproject.toml
├── README.md
└── uv.lock
```

`main.py`

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

#### Advanced (recommended package structure)

```bash
mkdir -p kivyschool-hello/hello_world/screens
cd kivyschool-hello
uv init
uv add kivy-reloader
```

Project tree:

```
kivyschool-hello
├── hello_world
│   ├── app.py
│   └── screens
│       ├── main_screen.py
│       └── main_screen.kv
├── main.py
├── pyproject.toml
├── README.md
└── uv.lock
```

`main.py`

```python
import trio
from hello_world import HelloWorldApp

app = HelloWorldApp()
trio.run(app.async_run, "trio")
```

`hello_world/app.py`

```python
from kivy_reloader.app import App
from hello_world.screens.main_screen import MainScreen

class HelloWorldApp(App):
    def build(self):
        return MainScreen()
```

`hello_world/screens/main_screen.kv`

```yaml
<MainScreen>:
    BoxLayout:
        orientation: 'vertical'
        Button:
            text: 'Welcome to Kivy Reloader!'
```

`hello_world/screens/main_screen.py`

```python
from kivy.uix.screenmanager import Screen
from kivy_reloader.utils import load_kv_path

load_kv_path(__file__)

class MainScreen(Screen):
    pass
```

---

### 3) Initialize Kivy Reloader in your project

```bash
uv run kivy-reloader init
```

This creates **`kivy-reloader.toml`** (config) and a minimal **`buildozer.spec`**.

<p align="center">
  <img src="https://kivyschool.com/kivy-reloader/assets/kivy-reloader-init.png" alt="kivy-reloader init" width="720" />
</p>

**Minimal config example:**

```toml
[kivy_reloader]
HOT_RELOAD_ON_PHONE = true
FULL_RELOAD_FILES = ["main.py"]
WATCHED_FOLDERS_RECURSIVELY = ["."]
STREAM_USING = "USB"  # or "WIFI" (requires initial cable setup)
```

---

## Usage

### Step 1 — Run on your computer

```bash
uv run main.py
```

This starts your app and the reloader background watcher.

### Step 2 — Deploy to Android

```bash
uv run kivy-reloader run
```

<p align="center">
  <img src="https://kivyschool.com/kivy-reloader/assets/kivy-reloader-run.png" alt="kivy-reloader run" width="720" />
</p>

Select the first option to build + install the APK via Buildozer. Once running on your phone, hot reload is already active.

### Step 3 — Develop with hot reload ♻️

When you save a watched file:

* If it matches **`FULL_RELOAD_FILES`** → the app **restarts** on computer and device(s).
* If it's inside **`WATCHED_FOLDERS_RECURSIVELY`**, **`WATCHED_FOLDERS`** or named in **`WATCHED_FILES`** → the app **hot reloads**.
* With **`HOT_RELOAD_ON_PHONE = false`** only your desktop app reloads/restarts.

---

## How it works (high level)

* Watches files using **watchdog** (via **Kaki**).
* On change, syncs files and signals your app(s) to reload.
* An on‑device Trio server receives files during development for instant updates.

---

## Contribution

Have ideas or found a bug? Please open an **[issue](https://github.com/kivy-school/kivy-reloader/issues)** or a **[pull request](https://github.com/kivy-school/kivy-reloader/pulls)**.

## Need help?

Come say hi in the **[Kivy Discord](https://chat.kivy.org/)** support channels — we're happy to help!

<!-- link notes -->

[Kaki]: https://github.com/tito/kaki
