"""Adapter between the component library and the checks.

Lookups that fail (missing row, ``pending`` row, blank value) raise
``NeedsEngineerInput`` so the affected check reports NEEDS_INPUT instead of
stopping the whole run. Each record's citation and status flow into the
steps that use it.
"""

from __future__ import annotations

from typing import Callable, TypeVar

from .components import ComponentLibrary, load_library
from .components.schema import SourcedRecord
from .trace import NeedsEngineerInput, SourceStatus

R = TypeVar("R", bound=SourcedRecord)

_default: ComponentLibrary | None = None


def default_library() -> ComponentLibrary:
    global _default
    if _default is None:
        _default = load_library()
    return _default


def lookup(fn: Callable[..., R], *args, **kwargs) -> R:
    try:
        return fn(*args, **kwargs)
    except LookupError as exc:  # includes UnverifiedComponentError
        raise NeedsEngineerInput("component data", str(exc)) from exc


def value(rec: SourcedRecord, field: str, what: str) -> float:
    v = getattr(rec, field)
    if v is None:
        raise NeedsEngineerInput("component data", f"{what}: '{field}' is blank in {cite(rec)}")
    return v


def cite(rec: SourcedRecord) -> str:
    parts = [rec.source_doc, rec.table]
    if rec.page:
        parts.append(f"p. {rec.page}")
    return ", ".join(p for p in parts if p)


def status(rec: SourcedRecord) -> SourceStatus:
    # Lookups only return verified or memory rows.
    return "verified" if rec.status.value == "verified" else "memory"
