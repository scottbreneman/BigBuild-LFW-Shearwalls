"""Load the component CSV files into typed records and look them up.

The loader is deliberately strict: a blank ``source``, an unknown
``status``, or a non-numeric value in a numeric column fails the load with
the file name and row number. Lookups refuse ``pending`` records unless the
caller passes ``allow_pending=True``, so a half-filled table cannot feed a
calculation by accident.
"""

from __future__ import annotations

import csv
import dataclasses
import typing
from pathlib import Path
from typing import Iterable, Optional, TypeVar

from .schema import (
    RECORD_TYPES,
    ContinuousRodSystem,
    HoldDown,
    LumberDesignValues,
    LumberSize,
    Nail,
    SheathingPanel,
    ShearWallAssembly,
    SourcedRecord,
    Status,
)

DATA_DIR = Path(__file__).parent / "data"

R = TypeVar("R", bound=SourcedRecord)


class ComponentDataError(ValueError):
    """A CSV row could not be parsed into its record type."""


class UnverifiedComponentError(LookupError):
    """A lookup matched only records whose status is not ``verified``."""


# --------------------------------------------------------------------------
# CSV -> dataclass coercion
# --------------------------------------------------------------------------


def _unwrap_optional(tp):
    """Return (inner_type, is_optional) for Optional[X]; else (tp, False)."""
    origin = typing.get_origin(tp)
    if origin is typing.Union:
        args = [a for a in typing.get_args(tp) if a is not type(None)]
        if len(args) == 1:
            return args[0], True
    return tp, False


def _coerce(value: str, tp, *, where: str):
    inner, optional = _unwrap_optional(tp)
    text = (value or "").strip()
    if text == "":
        if optional:
            return None
        if inner is str:
            return ""
        raise ComponentDataError(f"{where}: required value is blank")
    if inner is str:
        return text
    if inner is Status:
        try:
            return Status(text.lower())
        except ValueError as exc:
            raise ComponentDataError(f"{where}: unknown status {text!r}") from exc
    if inner is int:
        try:
            return int(text)
        except ValueError as exc:
            raise ComponentDataError(f"{where}: expected integer, got {text!r}") from exc
    if inner is float:
        try:
            return float(text)
        except ValueError as exc:
            raise ComponentDataError(f"{where}: expected number, got {text!r}") from exc
    raise ComponentDataError(f"{where}: unsupported field type {tp!r}")


def _resolved_types(record_type) -> dict:
    # get_type_hints resolves the ``from __future__ import annotations`` strings.
    return typing.get_type_hints(record_type)


def read_records(path: Path, record_type: type[R]) -> list[R]:
    """Parse one CSV file into a list of ``record_type`` instances."""
    hints = _resolved_types(record_type)
    field_names = [f.name for f in dataclasses.fields(record_type)]
    records: list[R] = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        missing = [name for name in field_names if name not in (reader.fieldnames or [])]
        if missing:
            raise ComponentDataError(f"{path.name}: missing columns {missing}")
        for line_no, row in enumerate(reader, start=2):
            if all((v or "").strip() == "" for v in row.values()):
                continue  # ignore blank lines
            kwargs = {}
            for name in field_names:
                where = f"{path.name} line {line_no}, column {name}"
                kwargs[name] = _coerce(row.get(name, ""), hints[name], where=where)
            if not kwargs["source_doc"]:
                raise ComponentDataError(f"{path.name} line {line_no}: source_doc must not be blank")
            if kwargs["status"] is Status.VERIFIED and not kwargs["checked_by"]:
                raise ComponentDataError(
                    f"{path.name} line {line_no}: verified rows must name checked_by"
                )
            records.append(record_type(**kwargs))
    return records


# --------------------------------------------------------------------------
# Library
# --------------------------------------------------------------------------


def _select(records: Iterable[R], allow_pending: bool, what: str, **criteria) -> list[R]:
    def matches(rec: R) -> bool:
        return all(getattr(rec, k) == v for k, v in criteria.items())

    hits = [r for r in records if matches(r) and r.status is not Status.SUPERSEDED]
    if not hits:
        raise LookupError(f"no {what} matching {criteria}")
    if allow_pending:
        return hits
    usable = [r for r in hits if r.status in (Status.VERIFIED, Status.MEMORY)]
    if not usable:
        raise UnverifiedComponentError(
            f"{what} matching {criteria} exist but values have not been entered "
            "(status=pending); enter them from the cited source and set status to "
            "verified or memory, or pass allow_pending=True for exploratory work"
        )
    return usable


def _one(hits: list[R], what: str, **criteria) -> R:
    if len(hits) > 1:
        raise LookupError(f"{len(hits)} {what} match {criteria}; refine the lookup")
    return hits[0]


@dataclasses.dataclass
class ComponentLibrary:
    lumber_sizes: list[LumberSize]
    lumber_design_values: list[LumberDesignValues]
    sheathing_panels: list[SheathingPanel]
    nails: list[Nail]
    shear_wall_assemblies: list[ShearWallAssembly]
    holddowns: list[HoldDown]
    continuous_rod_systems: list[ContinuousRodSystem]

    # ---- single-record lookups -------------------------------------------

    def lumber_size(self, nominal: str, *, allow_pending: bool = False) -> LumberSize:
        hits = _select(self.lumber_sizes, allow_pending, "lumber size", nominal=nominal)
        return _one(hits, "lumber sizes", nominal=nominal)

    def lumber_values(
        self,
        species_group: str,
        grade: str,
        size_class: str,
        *,
        allow_pending: bool = False,
    ) -> LumberDesignValues:
        crit = dict(species_group=species_group, grade=grade, size_class=size_class)
        hits = _select(self.lumber_design_values, allow_pending, "lumber design values", **crit)
        return _one(hits, "lumber design value rows", **crit)

    def nail(self, designation: str, *, allow_pending: bool = False) -> Nail:
        hits = _select(self.nails, allow_pending, "nail", designation=designation)
        return _one(hits, "nails", designation=designation)

    def sheathing_panel(
        self,
        panel_type: str,
        panel_grade: str,
        nominal_thickness_label: str,
        *,
        allow_pending: bool = False,
    ) -> SheathingPanel:
        crit = dict(
            panel_type=panel_type,
            panel_grade=panel_grade,
            nominal_thickness_label=nominal_thickness_label,
        )
        hits = _select(self.sheathing_panels, allow_pending, "sheathing panel", **crit)
        return _one(hits, "sheathing panels", **crit)

    def assembly(self, assembly_id: str, *, allow_pending: bool = False) -> ShearWallAssembly:
        hits = _select(
            self.shear_wall_assemblies, allow_pending, "shear wall assembly", assembly_id=assembly_id
        )
        return _one(hits, "shear wall assemblies", assembly_id=assembly_id)

    def holddown(self, model: str, *, allow_pending: bool = False) -> HoldDown:
        hits = _select(self.holddowns, allow_pending, "hold-down", model=model)
        return _one(hits, "hold-downs", model=model)

    def rod_system(self, system_id: str, *, allow_pending: bool = False) -> ContinuousRodSystem:
        hits = _select(
            self.continuous_rod_systems, allow_pending, "continuous rod system", system_id=system_id
        )
        return _one(hits, "continuous rod systems", system_id=system_id)

    # ---- multi-record filters --------------------------------------------

    def assemblies(self, *, allow_pending: bool = False, **criteria) -> list[ShearWallAssembly]:
        """All assemblies matching the given column values (e.g. nail_designation="8d common")."""
        return _select(self.shear_wall_assemblies, allow_pending, "shear wall assemblies", **criteria)

    def holddowns_for_post(self, min_post: str, *, allow_pending: bool = False) -> list[HoldDown]:
        return _select(self.holddowns, allow_pending, "hold-downs", min_post=min_post)

    # ---- bookkeeping -------------------------------------------------------

    def status_counts(self) -> dict[str, dict[str, int]]:
        """Rows per table by status, e.g. {"nails": {"verified": 4, "memory": 0, "pending": 6}}."""
        out = {}
        for name in RECORD_TYPES:
            rows = getattr(self, name)
            out[name] = {s.value: sum(1 for r in rows if r.status is s) for s in Status}
        return out

    def pending(self) -> dict[str, int]:
        """Count of pending rows per table; useful for a fill-in progress report."""
        return {name: counts["pending"] for name, counts in self.status_counts().items()}

    def items_to_verify(self) -> list[SourcedRecord]:
        """Every non-superseded row whose status is not ``verified``.

        This is the component-data half of the report's "Items to verify"
        appendix described in docs/spec-io.md §6.
        """
        out: list[SourcedRecord] = []
        for name in RECORD_TYPES:
            out.extend(
                r for r in getattr(self, name)
                if r.status not in (Status.VERIFIED, Status.SUPERSEDED)
            )
        return out


def load_library(data_dir: Optional[Path] = None) -> ComponentLibrary:
    """Load every table in ``data_dir`` (default: the package's ``data/``)."""
    data_dir = Path(data_dir) if data_dir is not None else DATA_DIR
    tables = {}
    for name, record_type in RECORD_TYPES.items():
        path = data_dir / f"{name}.csv"
        if not path.exists():
            raise FileNotFoundError(f"component table not found: {path}")
        tables[name] = read_records(path, record_type)
    return ComponentLibrary(**tables)
