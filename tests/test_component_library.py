"""Data-plumbing checks for the component library.

These tests verify that the CSV tables parse, that every row is cited, that
cross-references between tables resolve, and that unverified rows cannot be
looked up by accident. They do NOT validate any design value against a
standard; that is the engineer's job when a row is set to ``verified``.
"""

import csv
from pathlib import Path

import pytest

from design.components import (
    ComponentDataError,
    Status,
    UnverifiedComponentError,
    load_library,
    read_records,
)
from design.components.loader import DATA_DIR
from design.components.schema import RECORD_TYPES, LumberSize


@pytest.fixture(scope="module")
def lib():
    return load_library()


# --------------------------------------------------------------------------
# Loading and integrity
# --------------------------------------------------------------------------


def test_every_table_loads(lib):
    for name in RECORD_TYPES:
        assert len(getattr(lib, name)) > 0, f"{name} is empty"


def test_every_row_has_a_source_and_known_status(lib):
    for name in RECORD_TYPES:
        for rec in getattr(lib, name):
            assert rec.source.strip(), f"{name}: blank source on {rec}"
            assert isinstance(rec.status, Status)


def test_csv_columns_match_dataclass_fields():
    """A column added to a dataclass must be added to its CSV, and vice versa."""
    import dataclasses

    for name, rt in RECORD_TYPES.items():
        with (DATA_DIR / f"{name}.csv").open(newline="", encoding="utf-8") as fh:
            header = next(csv.reader(fh))
        assert set(header) == {f.name for f in dataclasses.fields(rt)}, name


def test_assembly_nail_designations_resolve(lib):
    nail_keys = {n.designation for n in lib.nails}
    for asm in lib.shear_wall_assemblies:
        assert asm.nail_designation in nail_keys, asm.assembly_id


def test_assembly_thickness_matches_a_sheathing_panel(lib):
    labels = {p.nominal_thickness_label for p in lib.sheathing_panels}
    for asm in lib.shear_wall_assemblies:
        assert asm.min_nominal_panel_thickness_label in labels, asm.assembly_id


def test_assembly_ids_are_unique(lib):
    ids = [a.assembly_id for a in lib.shear_wall_assemblies]
    assert len(ids) == len(set(ids))


def test_holddown_models_are_unique(lib):
    models = [h.model for h in lib.holddowns]
    assert len(models) == len(set(models))


# --------------------------------------------------------------------------
# Verification gate
# --------------------------------------------------------------------------


def test_pending_rows_are_refused_by_default(lib):
    pending = [n for n in lib.nails if n.status is Status.PENDING]
    if not pending:
        pytest.skip("no pending nails left to test against")
    with pytest.raises(UnverifiedComponentError):
        lib.nail(pending[0].designation)
    assert lib.nail(pending[0].designation, allow_pending=True) is pending[0]


def test_pending_report_counts_every_table(lib):
    report = lib.pending()
    assert set(report) == set(RECORD_TYPES)


# --------------------------------------------------------------------------
# Parsing errors are loud and located
# --------------------------------------------------------------------------


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "lumber_sizes.csv"
    p.write_text(text, encoding="utf-8")
    return p


HEADER = "nominal,thickness_in,width_in,source,status,notes\n"


def test_blank_source_is_rejected(tmp_path):
    p = _write(tmp_path, HEADER + "2x4,1.5,3.5,,pending,\n")
    with pytest.raises(ComponentDataError, match="line 2"):
        read_records(p, LumberSize)


def test_unknown_status_is_rejected(tmp_path):
    p = _write(tmp_path, HEADER + "2x4,1.5,3.5,NDS,maybe,\n")
    with pytest.raises(ComponentDataError, match="status"):
        read_records(p, LumberSize)


def test_non_numeric_value_is_rejected(tmp_path):
    p = _write(tmp_path, HEADER + "2x4,one and a half,3.5,NDS,pending,\n")
    with pytest.raises(ComponentDataError, match="thickness_in"):
        read_records(p, LumberSize)


def test_missing_column_is_rejected(tmp_path):
    p = _write(tmp_path, "nominal,thickness_in,source,status,notes\n2x4,1.5,NDS,pending,\n")
    with pytest.raises(ComponentDataError, match="missing columns"):
        read_records(p, LumberSize)


def test_blank_lines_are_ignored(tmp_path):
    p = _write(tmp_path, HEADER + "\n2x4,1.5,3.5,NDS,pending,\n,,,,,\n")
    assert len(read_records(p, LumberSize)) == 1


# --------------------------------------------------------------------------
# Geometry helpers (plain rectangle properties, not design provisions)
# --------------------------------------------------------------------------


def test_lumber_section_properties_are_rectangle_formulas():
    s = LumberSize(nominal="2x6", thickness_in=1.5, width_in=5.5, source="test", status=Status.VERIFIED)
    assert s.area_in2 == pytest.approx(8.25)
    assert s.Sx_in3 == pytest.approx(1.5 * 5.5**2 / 6)
    assert s.Ix_in4 == pytest.approx(1.5 * 5.5**3 / 12)
    assert s.Sy_in3 == pytest.approx(5.5 * 1.5**2 / 6)
    assert s.Iy_in4 == pytest.approx(5.5 * 1.5**3 / 12)
