"""Configuration loading/saving/validation for configurator GUI.

This module provides:
* TOML reading and writing using the toml package
* Atomic writes with backup (.bak created before save)
* Field validation against schema (type, enum, range checks)
* Merge with defaults from schema definitions
* Backup management (timestamped backups in .kivy-reloader/backups/)
"""

from __future__ import annotations

import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import toml

from .schema import FieldType

__all__ = [
    'load_config_values',
    'save_config_values',
    'validate_field',
    'merge_with_defaults',
    'create_backup',
    'cleanup_old_backups',
    'ConfigValidationError',
]


class ConfigValidationError(Exception):
    """Raised when a config value fails validation."""

    def __init__(self, key: str, value: Any, reason: str):
        self.key = key
        self.value = value
        self.reason = reason
        super().__init__(f'Validation error for "{key}": {reason}')


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_config_values(config_path: Path) -> Dict[str, Any]:
    """Load configuration values from TOML file.

    Reads the ``[kivy_reloader]`` section and returns a flat dict.
    Returns empty dict if file doesn't exist or can't be parsed.

    Args:
        config_path: Path to the kivy-reloader.toml file

    Returns:
        Dict mapping config keys to their values
    """
    if not config_path.exists():
        return {}

    try:
        with config_path.open('r', encoding='utf-8') as f:
            data = toml.load(f)
    except Exception as e:  # pragma: no cover
        print(f'[WARNING] Failed to parse {config_path}: {e}')
        return {}

    return data.get('kivy_reloader', {}) if isinstance(data, dict) else {}


# ---------------------------------------------------------------------------
# Saving
# ---------------------------------------------------------------------------


def save_config_values(
    config_path: Path,
    values: Dict[str, Any],
    create_backup: bool = True,
    backup_dir: Optional[Path] = None,
) -> None:
    """Save configuration values to TOML file atomically.

    Writes to a temporary file first, then renames atomically. Optionally
    creates a .bak backup before overwriting.

    Args:
        config_path: Path to the kivy-reloader.toml file
        values: Dict of config key->value pairs
        create_backup: Whether to create .bak file before overwriting
        backup_dir: Optional directory for timestamped backups

    Raises:
        IOError: If file operations fail
    """
    # Create backup if requested and file exists
    if create_backup and config_path.exists():
        bak_path = config_path.with_suffix('.toml.bak')
        shutil.copy2(config_path, bak_path)

        # Also create timestamped backup if backup_dir provided
        if backup_dir:
            _create_timestamped_backup(config_path, backup_dir)

    # Read existing file to preserve structure/comments if possible
    # (though toml library doesn't preserve comments, we keep other sections)
    if config_path.exists():
        try:
            with config_path.open('r', encoding='utf-8') as f:
                existing_data = toml.load(f)
        except Exception:  # pragma: no cover
            existing_data = {}
    else:
        existing_data = {}

    # Update the kivy_reloader section
    existing_data['kivy_reloader'] = values

    # Atomic write: write to temp file, then rename
    temp_fd, temp_path = tempfile.mkstemp(
        suffix='.toml', prefix='.tmp_', dir=config_path.parent
    )
    try:
        with open(temp_fd, 'w', encoding='utf-8') as f:
            toml.dump(existing_data, f)

        # Atomic rename (overwrites on POSIX, near-atomic on Windows)
        shutil.move(temp_path, config_path)
    except Exception:  # pragma: no cover
        # Cleanup temp file if something failed
        try:
            Path(temp_path).unlink(missing_ok=True)
        except Exception:
            pass
        raise


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate_bool(value: Any) -> tuple[bool, Optional[str]]:
    """Validate boolean field."""
    if not isinstance(value, bool):
        return False, f'Expected boolean, got {type(value).__name__}'
    return True, None


def _validate_int(
    value: Any, min_value: Optional[int], max_value: Optional[int]
) -> tuple[bool, Optional[str]]:
    """Validate integer field with optional range checks."""
    if not isinstance(value, int) or isinstance(value, bool):
        return False, f'Expected integer, got {type(value).__name__}'

    if min_value is not None and value < min_value:
        return False, f'Value {value} < minimum {min_value}'
    if max_value is not None and value > max_value:
        return False, f'Value {value} > maximum {max_value}'

    return True, None


def _validate_str(value: Any, enum: Optional[Any]) -> tuple[bool, Optional[str]]:
    """Validate string field with optional enum constraint."""
    if not isinstance(value, str):
        return False, f'Expected string, got {type(value).__name__}'

    if enum is not None and value not in enum:
        allowed = ', '.join(f'"{v}"' for v in enum)
        return False, f'Value "{value}" not in allowed set: {allowed}'

    return True, None


def _validate_list_str(value: Any) -> tuple[bool, Optional[str]]:
    """Validate list of strings."""
    if not isinstance(value, list):
        return False, f'Expected list, got {type(value).__name__}'
    if not all(isinstance(item, str) for item in value):
        return False, 'All list items must be strings'
    return True, None


def _validate_list_int(value: Any) -> tuple[bool, Optional[str]]:
    """Validate list of integers."""
    if not isinstance(value, list):
        return False, f'Expected list, got {type(value).__name__}'
    for item in value:
        if not isinstance(item, int) or isinstance(item, bool):
            return False, 'All list items must be integers'
    return True, None


def validate_field(field_def, value: Any) -> tuple[bool, Optional[str]]:
    """Validate a single config value against its field definition.

    Args:
        field_def: FieldDef instance from schema
        value: The value to validate

    Returns:
        Tuple of (is_valid, error_message). error_message is None if valid.
    """
    validators = {
        FieldType.BOOL: _validate_bool,
        FieldType.INT: lambda v: _validate_int(
            v, field_def.min_value, field_def.max_value
        ),
        FieldType.STR: lambda v: _validate_str(v, field_def.enum),
        FieldType.LIST_STR: _validate_list_str,
        FieldType.LIST_INT: _validate_list_int,
    }

    validator = validators.get(field_def.type)
    if validator is None:
        return False, f'Unknown field type: {field_def.type}'

    return validator(value)


# ---------------------------------------------------------------------------
# Defaults & Merging
# ---------------------------------------------------------------------------


def merge_with_defaults(
    user_values: Dict[str, Any], field_defs: List
) -> Dict[str, Any]:
    """Merge user config values with schema defaults.

    For any key not present in user_values, use the default from field_defs.
    User values are validated but preserved even if they differ from defaults.

    Args:
        user_values: Dict from load_config_values()
        field_defs: List of FieldDef instances (FIELD_DEFS from schema)

    Returns:
        Complete config dict with all fields populated
    """
    merged = {}
    for field_def in field_defs:
        if field_def.key in user_values:
            merged[field_def.key] = user_values[field_def.key]
        else:
            merged[field_def.key] = field_def.default
    return merged


# ---------------------------------------------------------------------------
# Backup Management
# ---------------------------------------------------------------------------


def _create_timestamped_backup(config_path: Path, backup_dir: Path) -> Path:
    """Create a timestamped backup in the backup directory.

    Args:
        config_path: The config file to backup
        backup_dir: Directory to store backups (e.g., .kivy-reloader/backups/)

    Returns:
        Path to the created backup file
    """
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = backup_dir / f'config_backup_{timestamp}.toml'

    shutil.copy2(config_path, backup_path)
    return backup_path


def create_backup(
    config_path: Path, backup_dir: Path, max_backups: int = 10
) -> Optional[Path]:
    """Create a timestamped backup and cleanup old ones.

    Args:
        config_path: Path to config file to backup
        backup_dir: Directory for backups (e.g., .kivy-reloader/backups/)
        max_backups: Maximum number of backups to keep (oldest deleted first)

    Returns:
        Path to created backup, or None if config_path doesn't exist
    """
    if not config_path.exists():
        return None

    backup_path = _create_timestamped_backup(config_path, backup_dir)
    cleanup_old_backups(backup_dir, keep=max_backups)
    return backup_path


def cleanup_old_backups(backup_dir: Path, keep: int = 10) -> None:
    """Remove old backup files, keeping only the most recent N.

    Args:
        backup_dir: Directory containing backup files
        keep: Number of most recent backups to retain
    """
    if not backup_dir.exists():
        return

    # Find all backup files (matching our naming pattern)
    backups = sorted(
        backup_dir.glob('config_backup_*.toml'),
        key=lambda p: p.stat().st_mtime,
        reverse=True,  # Newest first
    )

    # Delete old backups beyond the keep limit
    for old_backup in backups[keep:]:
        try:
            old_backup.unlink()
        except Exception:  # pragma: no cover
            pass  # Best effort cleanup
