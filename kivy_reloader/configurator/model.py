"""In-memory editable model for the configurator.

Phase 2 introduces a thin model layer that wraps raw loaded values into
FieldState objects, tracking current value, default, unsaved flag, and
basic validity.

This remains intentionally simple; later phases can extend with:
- validation hooks per FieldDef
- error messaging, dependency rules
- change listeners / signals
- serialization strategies (atomic write, comments preservation)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List

from .schema import FIELD_DEFS, FIELD_INDEX, FieldDef, FieldType


@dataclass
class FieldState:
    field: FieldDef
    value: Any
    original: Any
    default: Any
    unsaved: bool = False
    valid: bool = True
    error: str | None = None

    def set(self, new_value: Any) -> None:
        """Assign a new value (no complex validation yet)."""
        # Basic casting for primitive types to keep UI forgiving.
        casted = self._coerce(new_value)
        self.value = casted
        self.unsaved = casted != self.original
        self._revalidate()

    def reset(self) -> None:
        self.set(self.default)

    def _revalidate(self) -> None:
        """Very shallow validation placeholder."""
        self.valid = True
        self.error = None
        # Enum constraint
        if self.field.enum and isinstance(self.value, str):
            if self.value not in self.field.enum:
                self.valid = False
                self.error = f'Must be one of: {", ".join(self.field.enum)}'
                return
        # Int bounds
        if self.field.type == FieldType.INT and isinstance(self.value, int):
            lo = self.field.min_value
            hi = self.field.max_value
            too_low = lo is not None and self.value < lo
            too_high = hi is not None and self.value > hi
            if too_low or too_high:
                self.valid = False
                self.error = 'Out of allowed range'

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
    def __init__(self, loaded: Dict[str, Any]):
        self.states: Dict[str, FieldState] = {}
        for fd in FIELD_DEFS:
            cur = loaded.get(fd.key, fd.default)
            self.states[fd.key] = FieldState(
                field=fd, value=cur, original=cur, default=fd.default
            )
        # Unknown keys captured separately
        self.unknown: Dict[str, Any] = {
            k: v for k, v in loaded.items() if k not in FIELD_INDEX
        }

    # --- Query helpers ---
    def iter(self) -> Iterable[FieldState]:  # preserve schema order
        for fd in FIELD_DEFS:
            yield self.states[fd.key]

    def unsaved_states(self) -> List[FieldState]:
        return [s for s in self.iter() if s.unsaved]

    def is_unsaved(self) -> bool:
        return any(s.unsaved for s in self.iter())

    def is_valid(self) -> bool:
        return all(s.valid for s in self.iter())

    def as_dict(self) -> Dict[str, Any]:
        return {k: st.value for k, st in self.states.items()}

    # --- Mutations ---
    def set_value(self, key: str, value: Any) -> None:
        st = self.states.get(key)
        if not st:
            return
        st.set(value)

    def reset_field(self, key: str) -> None:
        st = self.states.get(key)
        if st:
            st.reset()

    def reset_all(self) -> None:
        for st in self.iter():
            st.set(st.original)


__all__ = [
    'FieldState',
    'ConfigModel',
]
