from functools import partial
from typing import List


class ServiceHandler:
    def __init__(self):
        self.active_services = []

    def start_service(self, service_name: str, permissions: List[str] = [], *args):
        print("Starting service", service_name)

        if service_name in self.active_services:
            print("Service already active, ignoring")
            return

        try:
            from android.permissions import Permission, request_permissions

            if permissions:
                java_permissions = [
                    getattr(Permission, permission) for permission in permissions
                ]
                print(f"Requesting {service_name} permissions", java_permissions)

                request_permissions(
                    java_permissions,
                    partial(self.callback_start_service, service_name),
                )
            else:
                print("No permissions needed")
                self.callback_start_service(service_name, [], [])
        except Exception as e:
            print(e)

    def stop_service(self, service_name: str):
        print("Stopping service", service_name)

        if service_name not in self.active_services:
            print("Service not active, ignoring")
            return

        from jnius import autoclass

        mActivity = autoclass("org.kivy.android.PythonActivity").mActivity

        context = mActivity.getApplicationContext()
        SERVICE_NAME = f"{context.getPackageName()}.Service{service_name}"
        self.service = autoclass(SERVICE_NAME)

        self.service.stop(mActivity)
        print("Service stopped")
        self.active_services.remove(service_name)

    def callback_start_service(self, service_name, permissions, results):
        print("Callback start service", service_name, permissions, results)

        from jnius import autoclass

        mActivity = autoclass("org.kivy.android.PythonActivity").mActivity

        context = mActivity.getApplicationContext()
        SERVICE_NAME = f"{context.getPackageName()}.Service{service_name}"
        self.service = autoclass(SERVICE_NAME)

        argument = ""
        self.service.start(mActivity, "small_icon", "title", "content", argument)
        print("Service started")
        self.active_services.append(service_name)
