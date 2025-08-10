"""Rich configuration schema used by the GUI configurator.

This module extracts as much semantic information as possible from the
``kivy-reloader.toml`` template (comments, sections, examples, defaults).

Design goals:
* Keep a single authoritative list of fields (``FIELD_DEFS``)
* Preserve ordering & grouping exactly like the template for intuitive UX
* Provide short + long help, examples, enum choices, numeric ranges
* Mark *advanced* options so the GUI can collapse them by default
* Remain backwards-compatible with existing (early) GUI code that only used:
    - ``FieldDef.key``
    - ``FieldDef.default``
    - ``FieldDef.category`` (section grouping)

Forward looking (not all consumed yet):
* ``help_long`` can power tooltips / side panel docs
* ``examples`` enable inline "insert example" actions
* ``enum`` + ``min_value``/``max_value`` drive validation widgets
* Section metadata (title line with emoji, description) for fancy separators
* Potential future: validators, deprecated flags, conflicts, restart requirements
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Optional, Sequence

__all__ = [
    'FieldType',
    'FieldDef',
    'SectionDef',
    'SECTIONS',
    'FIELD_DEFS',
    'FIELD_INDEX',
    'list_fields_by_section',
    'get_field',
]


class FieldType(str, Enum):
    """Primitive field types the GUI currently understands."""

    BOOL = 'bool'
    INT = 'int'
    STR = 'str'
    LIST_STR = 'list[str]'
    LIST_INT = 'list[int]'


@dataclass(frozen=True)
class SectionDef:
    """Logical grouping matching the TOML template separators.

    Attributes:
        id: Stable identifier (used internally)
        title: Human friendly title (displayed header) - can contain emoji
        description: One-sentence guidance / rationale
        order: Ordering weight (ascending)
        header_line: Optional decorative line (e.g. unicode box drawing)
        most_important: Flag to highlight the primary section
    """

    id: str
    title: str
    description: str
    order: int
    header_line: str | None = None
    most_important: bool = False


@dataclass(frozen=True)
class FieldDef:
    key: str
    type: FieldType
    default: Any
    category: str  # Section id (kept name `category` for backwards compat)
    help_short: str = ''  # Compact label / tooltip
    help_long: str = ''  # Rich multi-line markdown style help (optional)
    examples: Sequence[str] | None = None  # One or more example literals
    advanced: bool = False  # Hide behind an "Advanced" toggle initially
    enum: Optional[Iterable[str]] = None  # Allowed string set (if applicable)
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    note: str | None = None  # Extra caution / non normative note
    # Future: restart_required: bool, deprecated: bool, replaced_by: str, etc.

    def as_default_literal(self) -> str:
        """Return a TOML-ish literal string for the default (for tooltips)."""
        val = self.default
        if isinstance(val, str):
            return f'"{val}"'
        return repr(val)


# ---------------------------------------------------------------------------
# Section metadata (ordering identical to template)
# ---------------------------------------------------------------------------
SECTIONS: list[SectionDef] = [
    SectionDef(
        id='Core',
        title='🔥 CORE HOT RELOAD SETTINGS',
        description='Essential options that power the phone hot-reload loop.',
        order=10,
        header_line='🔥 CORE HOT RELOAD SETTINGS (Most Important)',
        most_important=True,
    ),
    SectionDef(
        id='Services',
        title='🛠️ SERVICES & BACKGROUND PROCESSES',
        description=(
            'Configure service modules whose changes may require a full restart.'
        ),
        order=20,
    ),
    SectionDef(
        id='Device',
        title='📱 DEVICE CONNECTION & TARGETING',
        description='Ports & targeting for ADB / multi-device deployments.',
        order=30,
    ),
    SectionDef(
        id='Window',
        title='📺 SCREEN MIRRORING WINDOW',
        description='Desktop mirror window geometry and behavior.',
        order=40,
    ),
    SectionDef(
        id='Display',
        title='🔧 DISPLAY & INTERACTION',
        description='Visual indicators and presentation tweaks.',
        order=50,
    ),
    SectionDef(
        id='Audio',
        title='🎵 AUDIO SETTINGS',
        description='Audio forwarding & quality parameters.',
        order=60,
    ),
    SectionDef(
        id='Performance',
        title='⚙️ PERFORMANCE TUNING',
        description='Resolution / bitrate / driver options for throughput.',
        order=70,
    ),
    SectionDef(
        id='Advanced',
        title='🚀 ADVANCED OPTIONS',
        description='Power features & lifecycle tweaks. Change only if needed.',
        order=80,
    ),
    SectionDef(
        id='Deployment',
        title='📦 DEPLOYMENT EXCLUSIONS',
        description='Exclude bulky / secret / dev-only assets from phone transfer.',
        order=90,
    ),
    SectionDef(
        id='Notifications',
        title='🔔 NOTIFICATIONS',
        description='Desktop notification preferences.',
        order=100,
    ),
]

SECTION_INDEX = {s.id: s for s in SECTIONS}


FIELD_DEFS: list[FieldDef] = [
    # ---------------------------------------------------------------------------
    # 🔥 Core Hot Reload Settings
    # ---------------------------------------------------------------------------
    FieldDef(
        'HOT_RELOAD_ON_PHONE',
        FieldType.BOOL,
        True,
        'Core',
        help_short='Auto push app to phone on save',
        help_long=(
            'If enabled, any change inside watched files/folders triggers a '
            'delta transfer (or full reload when matched) to connected devices.'
        ),
        note='Primary toggle for the live development loop.',
    ),
    FieldDef(
        'STREAM_USING',
        FieldType.STR,
        'USB',
        'Core',
        help_short='Connection method',
        help_long='Choose USB (faster, stable) or WIFI (wireless convenience).',
        enum=['USB', 'WIFI'],
        examples=['"USB"', '"WIFI"'],
    ),
    FieldDef(
        'FULL_RELOAD_FILES',
        FieldType.LIST_STR,
        ['main.py'],
        'Core',
        help_short='Files that force full app restart',
        help_long='Changing these files triggers a complete process restart.',
        examples=['["main.py", "settings.py"]'],
    ),
    FieldDef(
        'WATCHED_FOLDERS_RECURSIVELY',
        FieldType.LIST_STR,
        ['.'],
        'Core',
        help_short='Folders watched recursively',
        help_long='Deep watch - any file change inside triggers a reload.',
        examples=['["screens/", "components/"]', '["."]'],
    ),
    FieldDef(
        'WATCHED_FILES',
        FieldType.LIST_STR,
        [],
        'Core',
        help_short='Individual watched files',
        help_long='Explicit extra single files to watch (non recursive).',
        examples=['["utils.py", "notes/todo.txt"]'],
    ),
    FieldDef(
        'WATCHED_FOLDERS',
        FieldType.LIST_STR,
        [],
        'Core',
        help_short='Shallow watched folders',
        help_long='First-level only changes trigger reload (lighter than recursive).',
        examples=['["assets/", "data/"]'],
    ),
    FieldDef(
        'DO_NOT_WATCH_PATTERNS',
        FieldType.LIST_STR,
        [],
        'Core',
        help_short='Extra ignore patterns',
        help_long=(
            'When these files / folders are modified, they will be ignored by the hot '
            'reloader. User patterns added on top of built-in exclusions '
            '(.git, .venv, *.pyc, …). Use glob fragments; directories should end '
            'with "/"'
        ),
        examples=['["*.tmp", "cache/", "logs/*.log"]'],
    ),
    FieldDef(
        'FOLDERS_AND_FILES_TO_EXCLUDE_FROM_PHONE',
        FieldType.LIST_STR,
        [],
        'Core',
        help_short='Additional deployment exclusions',
        help_long=(
            'When a hot reload is triggered, these files and folders '
            'will not be sent to the connected devices. Remember that '
            'Built-in exclusions are automatically applied (.git, .venv, *.pyc, build/,'
            ' etc.), i.e, these and many other patterns are already excluded by '
            'default, so there is no need to add them here.'
        ),
        examples=['["my_secrets.txt", "local_config/", "*.backup"]'],
    ),
    # ---------------------------------------------------------------------------
    # 🛠️ Android Services
    # ---------------------------------------------------------------------------
    FieldDef(
        'SERVICE_NAMES',
        FieldType.LIST_STR,
        [],
        'Services',
        help_short='Service names for filtering',
        help_long=(
            'Names passed to log filtering for foreground / background services.'
        ),
        examples=['["Backgroundservice", "Databaseservice"]'],
    ),
    FieldDef(
        'SERVICE_FILES',
        FieldType.LIST_STR,
        [],
        'Services',
        help_short='Service files triggering restart',
        help_long=(
            'If modified they request an app restart (similar to FULL_RELOAD_FILES).',
        ),
        examples=['["services/background_service.py", "services/data_sync.py"]'],
    ),
    # ---------------------------------------------------------------------------
    # 📱 Device Connection
    # ---------------------------------------------------------------------------
    FieldDef(
        'PHONE_IPS',
        FieldType.LIST_STR,
        [],
        'Device',
        help_short='Restrict target device IPs',
        help_long=(
            'Empty list = deploy to all connected devices. Add IPs to restrict. '
            'Use 127.0.0.1 for the Android emulator.'
        ),
        examples=['["192.168.1.68", "192.168.1.69"]'],
    ),
    FieldDef(
        'ADB_PORT',
        FieldType.INT,
        5555,
        'Device',
        help_short='ADB TCP/IP port',
        min_value=1,
        max_value=65535,
    ),
    FieldDef(
        'RELOADER_PORT',
        FieldType.INT,
        8050,
        'Device',
        help_short='Internal file transfer port',
        min_value=1,
        max_value=65535,
    ),
    # ---------------------------------------------------------------------------
    # 📺 Screen Mirroring Window Settings
    # ---------------------------------------------------------------------------
    FieldDef(
        'WINDOW_X',
        FieldType.INT,
        1200,
        'Window Position',
        help_short='Window X position',
        help_long='Initial horizontal position of the scrcpy window on the screen.',
    ),
    FieldDef(
        'WINDOW_Y',
        FieldType.INT,
        100,
        'Window Position',
        help_short='Window Y position',
        help_long='Initial vertical position of the scrcpy window on the screen.',
    ),
    FieldDef(
        'WINDOW_WIDTH',
        FieldType.INT,
        280,
        'Window Size',
        help_short='Window width',
        help_long='Initial width of the scrcpy window.',
    ),
    FieldDef(
        'WINDOW_HEIGHT',
        FieldType.INT,
        0,
        'Window Size',
        help_short='Window height (0=auto)',
        help_long=(
            'Initial height of the scrcpy window. If 0, it will be auto-adjusted.'
        ),
    ),
    FieldDef(
        'WINDOW_TITLE',
        FieldType.STR,
        'Kivy Reloader',
        'Window Title',
        help_short='Mirror window title',
    ),
    FieldDef(
        'ALWAYS_ON_TOP',
        FieldType.BOOL,
        True,
        'Window Behavior',
        help_short='Keep window on top',
    ),
    FieldDef(
        'FULLSCREEN',
        FieldType.BOOL,
        False,
        'Window Behavior',
        help_short='Start fullscreen',
        advanced=True,
    ),
    FieldDef(
        'WINDOW_BORDERLESS',
        FieldType.BOOL,
        False,
        'Window Behavior',
        help_short='Hide window decorations',
        advanced=True,
    ),
    # ---------------------------------------------------------------------------
    # 🔧 Display & Interaction
    # ---------------------------------------------------------------------------
    FieldDef(
        'SHOW_TOUCHES',
        FieldType.BOOL,
        False,
        'Display',
        help_short='Show touch indicators',
    ),
    FieldDef(
        'STAY_AWAKE',
        FieldType.BOOL,
        False,
        'Display',
        help_short='Keep device awake',
        advanced=True,
    ),
    FieldDef(
        'TURN_SCREEN_OFF',
        FieldType.BOOL,
        False,
        'Display',
        help_short='Turn device screen off (audio only)',
        advanced=True,
    ),
    FieldDef(
        'DISPLAY_ORIENTATION',
        FieldType.INT,
        0,
        'Display',
        help_short='Rotation degrees',
        examples=['0', '90', '180', '270'],
        advanced=True,
    ),
    FieldDef(
        'CROP_AREA',
        FieldType.STR,
        '',
        'Display',
        help_short='Crop area spec',
        examples=['"1280:720:0:0"'],
        advanced=True,
    ),
    # ---------------------------------------------------------------------------
    # 🎵 Audio
    # ---------------------------------------------------------------------------
    FieldDef(
        'NO_AUDIO', FieldType.BOOL, True, 'Audio', help_short='Disable audio forwarding'
    ),
    FieldDef(
        'AUDIO_SOURCE',
        FieldType.STR,
        'output',
        'Audio',
        help_short='Audio capture source',
        enum=['output', 'mic', 'playback'],
    ),
    FieldDef(
        'NO_AUDIO_PLAYBACK',
        FieldType.BOOL,
        False,
        'Audio',
        help_short='Mute on computer only',
        advanced=True,
    ),
    FieldDef(
        'AUDIO_BIT_RATE',
        FieldType.STR,
        '128K',
        'Audio',
        help_short='Audio bitrate',
        enum=['64K', '128K', '256K'],
        advanced=True,
    ),
    # ---------------------------------------------------------------------------
    # ⚙️ Performance
    # ---------------------------------------------------------------------------
    FieldDef(
        'MAX_SIZE',
        FieldType.INT,
        0,
        'Performance',
        help_short='Max resolution (0=unlimited)',
    ),
    FieldDef(
        'MAX_FPS', FieldType.INT, 0, 'Performance', help_short='Max FPS (0=unlimited)'
    ),
    FieldDef(
        'VIDEO_BIT_RATE',
        FieldType.STR,
        '8M',
        'Performance',
        help_short='Video bitrate',
        enum=['2M', '4M', '8M'],
    ),
    FieldDef(
        'PRINT_FPS',
        FieldType.BOOL,
        False,
        'Performance',
        help_short='Print FPS to console',
        advanced=True,
    ),
    FieldDef(
        'RENDER_DRIVER',
        FieldType.STR,
        '',
        'Performance',
        help_short='SDL render driver (advanced)',
        advanced=True,
    ),
    FieldDef(
        'NO_MOUSE_HOVER',
        FieldType.BOOL,
        True,
        'Performance',
        help_short='Disable mouse hover events',
        advanced=True,
    ),
    FieldDef(
        'DISABLE_SCREENSAVER',
        FieldType.BOOL,
        True,
        'Performance',
        help_short='Prevent screensaver',
        advanced=True,
    ),
    # ---------------------------------------------------------------------------
    # 🚀 Advanced
    # ---------------------------------------------------------------------------
    FieldDef(
        'NO_CONTROL',
        FieldType.BOOL,
        False,
        'Advanced',
        help_short='Read-only mirror (no input)',
        advanced=True,
    ),
    FieldDef(
        'SHORTCUT_MOD',
        FieldType.STR,
        'lalt,lsuper',
        'Advanced',
        help_short='Scrcpy shortcut modifiers',
        examples=['"lalt,lsuper"'],
        advanced=True,
    ),
    FieldDef(
        'KILL_ADB_ON_CLOSE',
        FieldType.BOOL,
        False,
        'Advanced',
        help_short='Kill ADB when closing',
        advanced=True,
    ),
    FieldDef(
        'POWER_OFF_ON_CLOSE',
        FieldType.BOOL,
        False,
        'Advanced',
        help_short='Turn device screen off on close',
        advanced=True,
    ),
    FieldDef(
        'TIME_LIMIT',
        FieldType.INT,
        0,
        'Advanced',
        help_short='Auto-stop after seconds (0=unlimited)',
        advanced=True,
    ),
    FieldDef(
        'SCREEN_OFF_TIMEOUT',
        FieldType.INT,
        0,
        'Advanced',
        help_short='Screen timeout (0=system default)',
        advanced=True,
    ),
    # ---------------------------------------------------------------------------
    # 🎥 Recording
    # ---------------------------------------------------------------------------
    FieldDef(
        'RECORD_SESSION',
        FieldType.BOOL,
        False,
        'Advanced',
        help_short='Enable session recording',
        advanced=True,
    ),
    FieldDef(
        'RECORD_FILE_PATH',
        FieldType.STR,
        'session_recording.mp4',
        'Advanced',
        help_short='Recording output file',
        advanced=True,
    ),
    # ---------------------------------------------------------------------------
    # 🔔 Notifications
    # ---------------------------------------------------------------------------
    FieldDef(
        'SHOW_NOTIFICATIONS',
        FieldType.BOOL,
        True,
        'Notifications',
        help_short='Show desktop notifications',
    ),
]

# For potential later use: quick lookup by key.
FIELD_INDEX = {f.key: f for f in FIELD_DEFS}


# ---------------------------------------------------------------------------
# Utility helpers (small; avoid pulling in more dependencies)
# ---------------------------------------------------------------------------
def list_fields_by_section() -> list[tuple[SectionDef, list[FieldDef]]]:
    """Return fields grouped & sorted by section order then field order.

    The original insertion order of FIELD_DEFS within a section is preserved.
    """

    section_map: dict[str, list[FieldDef]] = {s.id: [] for s in SECTIONS}
    for f in FIELD_DEFS:
        section_map.setdefault(f.category, []).append(f)
    ordered: list[tuple[SectionDef, list[FieldDef]]] = []
    for s in sorted(SECTIONS, key=lambda s: s.order):
        ordered.append((s, section_map.get(s.id, [])))
    return ordered


def get_field(key: str) -> FieldDef | None:
    """Lookup a field by key (safe)."""
    return FIELD_INDEX.get(key)
