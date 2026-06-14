import json
import time
from pathlib import Path

_HISTORY_FILE = Path.home() / '.kivy-reloader-history.json'


def record(label: str, command: str):
    entries = _load()
    entries.append({'label': label, 'command': command, 'ts': time.time()})
    _HISTORY_FILE.write_text(json.dumps(entries, indent=2))


def get_top(n: int = 5, days: float | None = None) -> list[dict]:
    entries = _load()
    if days is not None:
        cutoff = time.time() - days * 86400
        entries = [e for e in entries if e['ts'] >= cutoff]
    counts: dict[str, dict] = {}
    for e in entries:
        key = e['command']
        if key not in counts:
            counts[key] = {'label': e['label'], 'command': key, 'count': 0}
        counts[key]['count'] += 1
    return sorted(counts.values(), key=lambda x: x['count'], reverse=True)[:n]


def _load() -> list[dict]:
    if not _HISTORY_FILE.exists():
        return []
    try:
        return json.loads(_HISTORY_FILE.read_text())
    except Exception:
        return []
