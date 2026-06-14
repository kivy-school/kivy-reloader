from kivy.properties import ListProperty, ObjectProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout

from kivy_reloader.configurator.status_checks import CheckResult, Status, run_all_checks
from kivy_reloader.lang import Builder

Builder.load_file(__file__)


class StatusRow(BoxLayout):
    icon = StringProperty('')
    label = StringProperty('')
    detail = StringProperty('')
    row_status = StringProperty('ok')


class StatusCard(BoxLayout):
    rows = ListProperty([])
    config_model = ObjectProperty(None, allownone=True)
    os_label = StringProperty('')
    report_status = StringProperty('')  # feedback message after copy/save
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


    def copy_report(self):
        from kivy_reloader.configurator.status_checks import format_report
        text = format_report(self._last_results, self._last_config_path)

        # Try Kivy clipboard first
        try:
            from kivy.core.clipboard import Clipboard
            Clipboard.copy(text)
            self.report_status = 'Copied to clipboard'
            return
        except Exception:
            pass

        # Try xclip/xsel (WSL2/Linux)
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

        # Fall back to file
        self.save_report(text)

    def save_report(self, text: str | None = None):
        from kivy_reloader.configurator.status_checks import format_report
        if text is None:
            text = format_report(self._last_results, self._last_config_path)

        # Try to save to Windows Desktop if on WSL2
        from kivy_reloader.configurator.status_checks import _get_windows_home, detect_os
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
        print(text)  # also prints to command panel

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


def _icon(status: Status) -> str:
    return {'ok': '✓', 'warn': '⚠', 'fail': '✗', 'skip': '—'}[status.value]
