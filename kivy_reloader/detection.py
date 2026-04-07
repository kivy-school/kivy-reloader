import platform
import subprocess
import shutil
import importlib.util
from pathlib import Path


def is_apple_m_series() -> bool:
    """
    Detect Apple M-series chip reliably, even when running under Rosetta 2.

    Root cause of the common bug:
      Under Rosetta, `sysctl -n hw.optional.arm64` returns an EMPTY STRING
      instead of "1", so a naive == "1" check silently fails.

    Fix: accept both "1" and "" as valid when returncode is 0.
      - returncode=0, stdout="1" → native ARM64 process
      - returncode=0, stdout=""  → Rosetta (stdout suppressed)
      - returncode=1             → Intel Mac, key doesn't exist at all
    """
    if platform.system() != "Darwin":
        return False

    # Primary: hw.optional.arm64 key only EXISTS on Apple Silicon
    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.optional.arm64"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return True
    except FileNotFoundError:
        pass

    # Fallback: if this process is running under Rosetta, we're on Apple Silicon
    try:
        result = subprocess.run(
            ["sysctl", "-n", "sysctl.proc_translated"],
            capture_output=True, text=True
        )
        if result.returncode == 0 and result.stdout.strip() == "1":
            return True
    except FileNotFoundError:
        pass

    # Last resort: brand string (can be empty under some Rosetta configs)
    try:
        result = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            capture_output=True, text=True
        )
        if "Apple M" in result.stdout:
            return True
    except FileNotFoundError:
        pass

    return False


def copy_watchdog_recipe():
    """
    Copies p4a's built-in watchdog recipe into ./p4a-recipes/watchdog/
    so it can be overridden locally. Requires buildozer.spec to have:
        p4a.local_recipes = ./p4a-recipes
    """
    spec = importlib.util.find_spec("pythonforandroid")
    if spec is None:
        raise RuntimeError("pythonforandroid is not installed. Run: pip install python-for-android")

    p4a_root = Path(spec.origin).parent
    watchdog_src = p4a_root / "recipes" / "watchdog"

    if not watchdog_src.exists():
        raise RuntimeError(f"watchdog recipe not found at: {watchdog_src}")

    watchdog_dst = Path.cwd() / "p4a-recipes" / "watchdog"

    if watchdog_dst.exists():
        print(f"Already exists, skipping: {watchdog_dst}")
        return

    shutil.copytree(watchdog_src, watchdog_dst)
    print(f"Copied: {watchdog_src} → {watchdog_dst}")
    print("Make sure buildozer.spec has: p4a.local_recipes = ./p4a-recipes")


if __name__ == "__main__":
    copy_watchdog_recipe()