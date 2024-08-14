import sys


def capture_locals(func):
    def wrapper(*args, **kwargs):
        frame = None

        def trace_func(frame_inner, event, arg):
            nonlocal frame
            if event == "return":
                frame = frame_inner
            return trace_func

        # Set the trace function
        sys.settrace(trace_func)

        # Execute the original function
        result = func(*args, **kwargs)

        # Disable the trace
        sys.settrace(None)

        # Get the local variables from the frame
        if frame:
            local_vars = frame.f_locals
            print(f"Locals in {func.__name__}: {local_vars}")
            breakpoint()

        return result

    return wrapper


from kivy.factory import Factory as F

from beautifulapp.screens.main_screen import MainScreen


class Person:
    @capture_locals
    def method(self):
        sm = F.ScreenManager()
        sm.add_widget(MainScreen())
        # return a + b


# Instantiate the class and call the method
person = Person()
person.method()
