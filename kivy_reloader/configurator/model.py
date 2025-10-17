"""In-memory editable model for the configurator.

This module provides a rich data model layer that wraps configuration values
with state tracking, validation, and persistence operations:

- FieldState: Tracks individual field value, original, default, dirty flag, validation
- ConfigModel: Main model class with save/load/import/export/reset operations
- Observable pattern ready (can add listeners in future)
- Full integration with config_loader for validation and atomic saves

Features:
* Automatic dirty tracking (value != original)
* Per-field validation using schema rules
* Save with automatic backups
* Import/export from other TOML files
* Restore to defaults (per-field or all)
* Type coercion for user-friendly input handling
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from kivy_reloader.configurator import config_loader
from kivy_reloader.configurator.schema import (
    FIELD_DEFS,
    FIELD_INDEX,
    FieldDef,
    FieldType,
)


@dataclass
class FieldState:
    """State wrapper for a single configuration field.

    Tracks current value, original (loaded from file), default (from schema),
    and validation state. Provides dirty tracking and type coercion.
    """

    field: FieldDef
    value: Any
    original: Any
    default: Any
    unsaved: bool = False
    valid: bool = True
    error: str | None = None

    def set(self, new_value: Any) -> None:
        """Assign a new value with automatic validation.

        Coerces types for user-friendly input (e.g., string -> int).
        Updates dirty flag and runs validation.
        """
        casted = self._coerce(new_value)
        self.value = casted
        self.unsaved = casted != self.original
        self._revalidate()

    def reset_to_original(self) -> None:
        """Reset to the value loaded from file."""
        self.set(self.original)

    def reset_to_default(self) -> None:
        """Reset to the schema default value."""
        self.set(self.default)

    def _revalidate(self) -> None:
        """Validate current value using config_loader validation."""
        is_valid, error_msg = config_loader.validate_field(self.field, self.value)
        self.valid = is_valid
        self.error = error_msg

    def _coerce(self, raw: Any) -> Any:  # noqa: C901 - kept explicit but low branch
        t = self.field.type

        def bool_cast(v: Any) -> bool:
            if isinstance(v, bool):
                return v
            if isinstance(v, str):
                return v.strip().lower() in {'1', 'true', 'yes', 'on'}
            return bool(v)

        def int_cast(v: Any) -> int:
            if isinstance(v, int):
                return v
            try:
                return int(v)  # type: ignore[arg-type]
            except Exception:  # pragma: no cover
                return self.default

        def str_cast(v: Any) -> str:
            return str(v)

        def list_str_cast(v: Any) -> list[str]:
            if isinstance(v, list):
                return [str(x) for x in v]
            if isinstance(v, str):
                return [s.strip() for s in v.split(',') if s.strip()] if v else []
            return []

        def list_int_cast(v: Any) -> list[int]:
            seq: list[Any]
            if isinstance(v, list):
                seq = v
            elif isinstance(v, str):
                seq = [tok.strip() for tok in v.split(',') if tok.strip()]
            else:
                seq = []
            out: list[int] = []
            for elem in seq:
                try:
                    out.append(int(elem))
                except Exception:
                    continue
            return out

        dispatch = {
            FieldType.BOOL: bool_cast,
            FieldType.INT: int_cast,
            FieldType.STR: str_cast,
            FieldType.LIST_STR: list_str_cast,
            FieldType.LIST_INT: list_int_cast,
        }
        caster = dispatch.get(t)
        return caster(raw) if caster else raw


class ConfigModel:
    """Main configuration model with persistence and state management.

    This class wraps all configuration fields with state tracking and provides
    high-level operations like save, load, import, export, and reset.

    Attributes:
        states: Dict of field_key -> FieldState
        unknown: Unknown keys from TOML (preserved on save)
        config_path: Path to the config file
        backup_dir: Path to backup directory (e.g., .kivy-reloader/backups/)
    """

    def __init__(
        self,
        loaded: Dict[str, Any],
        config_path: Optional[Path] = None,
        backup_dir: Optional[Path] = None,
    ):
        """Initialize model from loaded config values.

        Args:
            loaded: Dict of config key->value pairs from config_loader
            config_path: Path to kivy-reloader.toml (needed for save)
            backup_dir: Directory for timestamped backups
        """
        self.config_path = config_path
        self.backup_dir = backup_dir
        self.states: Dict[str, FieldState] = {}

        # Create FieldState for each known field from schema
        for fd in FIELD_DEFS:
            cur = loaded.get(fd.key, fd.default)
            self.states[fd.key] = FieldState(
                field=fd, value=cur, original=cur, default=fd.default
            )

        # Preserve unknown keys (not in schema) for round-trip saving
        self.unknown: Dict[str, Any] = {
            k: v for k, v in loaded.items() if k not in FIELD_INDEX
        }

    # --- Query helpers ---

    def iter_fields(self) -> Iterable[FieldState]:
        """Iterate all fields in schema order."""
        for fd in FIELD_DEFS:
            yield self.states[fd.key]

    def get_state(self, key: str) -> Optional[FieldState]:
        """Get FieldState for a specific key."""
        return self.states.get(key)

    def get_value(self, key: str) -> Any:
        """Get current value for a field."""
        state = self.states.get(key)
        return state.value if state else None

    def unsaved_states(self) -> List[FieldState]:
        """Get list of fields with unsaved changes."""
        return [s for s in self.iter_fields() if s.unsaved]

    def invalid_states(self) -> List[FieldState]:
        """Get list of fields with validation errors."""
        return [s for s in self.iter_fields() if not s.valid]

    def is_dirty(self) -> bool:
        """Check if any field has unsaved changes."""
        return any(s.unsaved for s in self.iter_fields())

    def is_valid(self) -> bool:
        """Check if all fields pass validation."""
        return all(s.valid for s in self.iter_fields())

    def as_dict(self) -> Dict[str, Any]:
        """Export current values as a dict (for saving)."""
        result = {k: st.value for k, st in self.states.items()}
        # Include unknown keys for round-trip preservation
        result.update(self.unknown)
        return result

    # --- Mutations ---

    def set_value(self, key: str, value: Any) -> bool:
        """Set value for a field.

        Args:
            key: Field key
            value: New value (will be coerced and validated)

        Returns:
            True if field exists and was updated, False otherwise
        """
        st = self.states.get(key)
        if not st:
            return False
        st.set(value)
        return True

    def reset_field(self, key: str, to_default: bool = False) -> bool:
        """Reset a single field.

        Args:
            key: Field key
            to_default: If True, reset to schema default; else to original

        Returns:
            True if field was reset, False if not found
        """
        st = self.states.get(key)
        if not st:
            return False
        if to_default:
            st.reset_to_default()
        else:
            st.reset_to_original()
        return True

    def reset_all(self, to_defaults: bool = False) -> None:
        """Reset all fields.

        Args:
            to_defaults: If True, reset to schema defaults; else to originals
        """
        for st in self.iter_fields():
            if to_defaults:
                st.reset_to_default()
            else:
                st.reset_to_original()

    # --- Persistence ---

    def save(self, create_backup: bool = True) -> None:
        """Save current values to config file.

        Performs atomic write with optional backup. Updates 'original' values
        after successful save so dirty flags reset.

        Args:
            create_backup: Whether to create .bak and timestamped backups

        Raises:
            RuntimeError: If config_path not set or save fails
        """
        if not self.config_path:
            raise RuntimeError('config_path not set, cannot save')

        if not self.is_valid():
            invalid = self.invalid_states()
            errors = [f'{s.field.key}: {s.error}' for s in invalid]
            raise config_loader.ConfigValidationError(
                key='multiple',
                value=None,
                reason='Cannot save with validation errors:\n' + '\n'.join(errors),
            )

        config_loader.save_config_values(
            config_path=self.config_path,
            values=self.as_dict(),
            create_backup=create_backup,
            backup_dir=self.backup_dir,
        )

        # Update originals after successful save
        for st in self.iter_fields():
            st.original = st.value
            st.unsaved = False

    def reload(self) -> None:
        """Reload config from disk, discarding unsaved changes.

        Raises:
            RuntimeError: If config_path not set
        """
        if not self.config_path:
            raise RuntimeError('config_path not set, cannot reload')

        loaded = config_loader.load_config_values(self.config_path)
        merged = config_loader.merge_with_defaults(loaded, FIELD_DEFS)

        # Update all states with reloaded values
        for fd in FIELD_DEFS:
            new_val = merged[fd.key]
            st = self.states[fd.key]
            st.value = new_val
            st.original = new_val
            st.unsaved = False
            st._revalidate()

    def export_to_file(self, export_path: Path) -> None:
        """Export current config to another TOML file.

        Args:
            export_path: Path where config should be exported

        Raises:
            IOError: If write fails
        """
        config_loader.save_config_values(
            config_path=export_path,
            values=self.as_dict(),
            create_backup=False,
        )

    def import_from_file(self, import_path: Path, merge: bool = True) -> None:
        """Import config values from another TOML file.

        Args:
            import_path: Path to TOML file to import from
            merge: If True, merge with current; if False, replace all

        Raises:
            FileNotFoundError: If import_path doesn't exist
        """
        if not import_path.exists():
            raise FileNotFoundError(f'Import file not found: {import_path}')

        imported = config_loader.load_config_values(import_path)

        if merge:
            # Update only keys present in imported file
            for key, value in imported.items():
                if key in self.states:
                    self.states[key].set(value)
                else:
                    # Unknown key, add to unknown dict
                    self.unknown[key] = value
        else:
            # Replace all: reset to defaults first, then apply imported
            self.reset_all(to_defaults=True)
            for key, value in imported.items():
                if key in self.states:
                    self.states[key].set(value)
                else:
                    self.unknown[key] = value

    @classmethod
    def from_file(
        cls, config_path: Path, backup_dir: Optional[Path] = None
    ) -> ConfigModel:
        """Create ConfigModel by loading from a file.

        Args:
            config_path: Path to kivy-reloader.toml
            backup_dir: Optional backup directory path

        Returns:
            ConfigModel instance with loaded values
        """
        loaded = config_loader.load_config_values(config_path)
        merged = config_loader.merge_with_defaults(loaded, FIELD_DEFS)
        return cls(merged, config_path=config_path, backup_dir=backup_dir)


__all__ = [
    'FieldState',
    'ConfigModel',
]
