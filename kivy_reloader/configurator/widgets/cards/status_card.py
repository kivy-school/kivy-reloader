import threading

from kivy.properties import ListProperty, ObjectProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout

from kivy_reloader.configurator.status_checks import Status, run_all_checks
from kivy_reloader.lang import Builder

Builder.load_file(__file__)


class StatusRow(BoxLayout):
    icon = StringProperty('')
    label = StringProperty('')
    detail = StringProperty('')
    row_status = StringProperty('ok')


class DeviceRow(BoxLayout):
    serial = StringProperty('')
    name = StringProperty('')
    connection = StringProperty('USB')
    device_status = StringProperty('ok')
    status_detail = StringProperty('')

    def recheck(self):
        import threading

        from kivy.clock import Clock

        from kivy_reloader.configurator.status_checks import _run

        def _check():
            rc, out = _run(['adb', '-s', self.serial, 'get-state'], timeout=5)
            state = ('ok', out.strip() or 'device') if rc == 0 else ('fail', out.strip() or 'unreachable')
            Clock.schedule_once(lambda dt: setattr(self, 'device_status', state[0]))
            Clock.schedule_once(lambda dt: setattr(self, 'status_detail', state[1]))
        threading.Thread(target=_check, daemon=True).start()


class StatusCard(BoxLayout):
    rows = ListProperty([])
    devices = ListProperty([])
    config_model = ObjectProperty(None, allownone=True)
    os_label = StringProperty('')
    report_status = StringProperty('')
    _last_results = []
    _last_config_path = None

    def load_from_model(self):
        pass

    def on_kv_post(self, base_widget):
        from kivy_reloader.configurator.status_checks import detect_os
        self.os_label = detect_os().upper()
        self.refresh()

    def refresh(self):
        config_path = None
        if self.config_model and self.config_model.config_path:
            config_path = self.config_model.config_path
        self._last_config_path = config_path
        self._last_results = run_all_checks(config_path=config_path)
        self.report_status = ''
        self.rows = [
            {
                'icon': _icon(r.status),
                'label': r.name,
                'detail': r.detail,
                'row_status': r.status.value,
            }
            for r in self._last_results
        ]
        self.refresh_devices()

    def refresh_devices(self):
        from kivy_reloader.configurator.status_checks import get_connected_devices

        def _fetch():
            devs = get_connected_devices()
            from kivy.clock import Clock
            Clock.schedule_once(lambda dt: setattr(self, 'devices', devs))
        threading.Thread(target=_fetch, daemon=True).start()

    def on_devices(self, instance, devices):
        lst = self.ids.get('device_list')
        if not lst:
            return
        lst.clear_widgets()
        for d in devices:
            lst.add_widget(DeviceRow(
                serial=d['serial'],
                name=d['name'],
                connection=d['connection'],
                device_status=d['device_status'],
                status_detail=d['status_detail'],
            ))

    def copy_report(self):
        from kivy_reloader.configurator.status_checks import format_report
        text = format_report(self._last_results, self._last_config_path)
        try:
            from kivy.core.clipboard import Clipboard
            Clipboard.copy(text)
            self.report_status = 'Copied to clipboard'
            return
        except Exception:
            pass
        for tool, args in [
            ('xclip', ['xclip', '-selection', 'clipboard']),
            ('xsel', ['xsel', '--clipboard', '--input']),
        ]:
            import shutil
            if shutil.which(tool):
                try:
                    import subprocess
                    p = subprocess.Popen(args, stdin=subprocess.PIPE)
                    p.communicate(input=text.encode())
                    self.report_status = f'Copied via {tool}'
                    return
                except Exception:
                    pass
        self.save_report(text)

    def save_report(self, text: str | None = None):
        from kivy_reloader.configurator.status_checks import format_report
        if text is None:
            text = format_report(self._last_results, self._last_config_path)
        from kivy_reloader.configurator.status_checks import (  # noqa: PLC2701
            _get_windows_home,
            detect_os,
        )
        save_path = None
        if detect_os() == 'wsl2':
            win_home = _get_windows_home()
            if win_home:
                save_path = win_home / 'Desktop' / 'kivy-reloader-diag.txt'
        if save_path is None:
            from pathlib import Path
            save_path = Path.home() / 'kivy-reloader-diag.txt'
        save_path.write_text(text)
        self.report_status = f'Saved to {save_path}'
        print(text)

    def on_rows(self, instance, rows):
        lst = self.ids.get('row_list')
        if not lst:
            return
        lst.clear_widgets()
        for r in rows:
            lst.add_widget(StatusRow(
                icon=r['icon'],
                label=r['label'],
                detail=r['detail'],
                row_status=r['row_status'],
            ))

    def reset_reloader_state(self):
        from pathlib import Path
        base = self.config_model.config_path.parent if (self.config_model and self.config_model.config_path) else Path.cwd()
        state_file = base / '.kivy_reloader_state.json'
        if state_file.exists():
            state_file.unlink()
            self.report_status = 'Reloader state reset ✓'
        else:
            self.report_status = 'State file not found (already clean)'


def _icon(status: Status) -> str:
    return {'ok': '✓', 'warn': '⚠', 'fail': '✗', 'skip': '—'}[status.value]
