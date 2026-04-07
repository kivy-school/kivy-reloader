# from pythonforandroid.recipe import PythonRecipe


# class WatchdogRecipe(PythonRecipe):
#     version = "3.0.0"
#     url = "https://pypi.python.org/packages/source/w/watchdog/watchdog-{version}.tar.gz"
#     name = "watchdog"

#     # Don't build the native FSEvents/inotify extensions
#     # Android uses the pure-Python polling observer
#     call_hostpython_via_targetpython = False
#     install_in_hostpython = False

#     def get_recipe_env(self, arch):
#         env = super().get_recipe_env(arch)
#         # Force pure Python build, skip C extensions
#         env["DISABLE_INOTIFY"] = "1"
#         env["DISABLE_FSEVENTS"] = "1"
#         return env


# recipe = WatchdogRecipe()

# from pythonforandroid.recipe import PythonRecipe


# class WatchdogRecipe(PythonRecipe):
#     version = "6.0.0"
#     url = "https://pypi.python.org/packages/source/w/watchdog/watchdog-{version}.tar.gz"
#     name = "watchdog"

#     def build_arch(self, arch):
#         print("=== WATCHDOG DUMMY RECIPE RUNNING ===")
#         pass  # watchdog is only needed on the host, not on Android

#     def install_python_package(self, arch, name=None, env=None, is_dir=None):
#         print("=== WATCHDOG DUMMY RECIPE - SKIPPING PIP INSTALL ===")
#         pass

#     def install_libraries(self, arch):
#         pass

#     def postbuild_arch(self, arch):
#         pass


# recipe = WatchdogRecipe()


from pythonforandroid.recipe import PythonRecipe


class WatchdogRecipe(PythonRecipe):
    version = "6.0.0"
    url = "https://pypi.python.org/packages/source/w/watchdog/watchdog-{version}.tar.gz"
    name = "watchdog"

    def should_build(self, arch):
        # watchdog is a host-only file watcher, not needed on Android
        return False


recipe = WatchdogRecipe()