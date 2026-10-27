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
    ComponentLibrary,
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
            assert rec.source_doc.strip(), f"{name}: blank source_doc on {rec}"
            assert isinstance(rec.status, Status)


def test_verified_rows_name_a_checker(lib):
    for name in RECORD_TYPES:
        for rec in getattr(lib, name):
            if rec.status is Status.VERIFIED:
                assert rec.checked_by.strip(), f"{name}: verified row without checked_by: {rec}"


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


def test_memory_rows_are_usable_but_flagged():
    row = LumberSize(nominal="2x4", thickness_in=1.5, width_in=3.5,
                     source_doc="NDS 2024 Supplement", table="Table 1B", page="",
                     status=Status.MEMORY, entered_by="VL")
    lib = ComponentLibrary(lumber_sizes=[row], lumber_design_values=[], sheathing_panels=[],
                           nails=[], shear_wall_assemblies=[], holddowns=[],
                           continuous_rod_systems=[])
    assert lib.lumber_size("2x4") is row  # memory rows are returned without allow_pending
    assert lib.items_to_verify() == [row]  # ...but listed for verification


def test_pending_report_counts_every_table(lib):
    report = lib.pending()
    assert set(report) == set(RECORD_TYPES)
    counts = lib.status_counts()
    assert set(counts) == set(RECORD_TYPES)
    assert all(set(c) == {s.value for s in Status} for c in counts.values())


def test_items_to_verify_excludes_verified_and_superseded(lib):
    for rec in lib.items_to_verify():
        assert rec.status in (Status.PENDING, Status.MEMORY)


# --------------------------------------------------------------------------
# Parsing errors are loud and located
# --------------------------------------------------------------------------


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "lumber_sizes.csv"
    p.write_text(text, encoding="utf-8")
    return p


HEADER = "nominal,thickness_in,width_in,source_doc,table,page,status,entered_by,checked_by,notes\n"


def test_blank_source_is_rejected(tmp_path):
    p = _write(tmp_path, HEADER + "2x4,1.5,3.5,,,,pending,,,\n")
    with pytest.raises(ComponentDataError, match="line 2"):
        read_records(p, LumberSize)


def test_unknown_status_is_rejected(tmp_path):
    p = _write(tmp_path, HEADER + "2x4,1.5,3.5,NDS,,,maybe,,,\n")
    with pytest.raises(ComponentDataError, match="status"):
        read_records(p, LumberSize)


def test_non_numeric_value_is_rejected(tmp_path):
    p = _write(tmp_path, HEADER + "2x4,one and a half,3.5,NDS,,,pending,,,\n")
    with pytest.raises(ComponentDataError, match="thickness_in"):
        read_records(p, LumberSize)


def test_missing_column_is_rejected(tmp_path):
    p = _write(tmp_path, "nominal,thickness_in,source_doc,table,page,status,entered_by,checked_by,notes\n2x4,1.5,NDS,,,pending,,,\n")
    with pytest.raises(ComponentDataError, match="missing columns"):
        read_records(p, LumberSize)


def test_verified_without_checker_is_rejected(tmp_path):
    p = _write(tmp_path, HEADER + "2x4,1.5,3.5,NDS,Table 1B,12,verified,VL,,\n")
    with pytest.raises(ComponentDataError, match="checked_by"):
        read_records(p, LumberSize)


def test_blank_lines_are_ignored(tmp_path):
    p = _write(tmp_path, HEADER + "\n2x4,1.5,3.5,NDS,,,pending,,,\n,,,,,,,,,\n")
    assert len(read_records(p, LumberSize)) == 1


# --------------------------------------------------------------------------
# Geometry helpers (plain rectangle properties, not design provisions)
# --------------------------------------------------------------------------


def test_lumber_section_properties_are_rectangle_formulas():
    s = LumberSize(nominal="2x6", thickness_in=1.5, width_in=5.5, source_doc="test", table="",
                   page="", status=Status.VERIFIED, checked_by="test")
    assert s.area_in2 == pytest.approx(8.25)
    assert s.Sx_in3 == pytest.approx(1.5 * 5.5**2 / 6)
    assert s.Ix_in4 == pytest.approx(1.5 * 5.5**3 / 12)
    assert s.Sy_in3 == pytest.approx(5.5 * 1.5**2 / 6)
    assert s.Iy_in4 == pytest.approx(5.5 * 1.5**3 / 12)


def test_computed_section_properties_match_table_1b(lib):
    """Computed rectangle properties agree with the Table 1B values entered on each row
    (to the table's printed precision)."""
    for s in lib.lumber_sizes:
        pairs = [
            (s.area_in2, s.table_area_in2),
            (s.Sx_in3, s.table_Sxx_in3),
            (s.Ix_in4, s.table_Ixx_in4),
            (s.Sy_in3, s.table_Syy_in3),
            (s.Iy_in4, s.table_Iyy_in4),
        ]
        for computed, tabulated in pairs:
            if tabulated is not None:
                assert computed == pytest.approx(tabulated, rel=5e-3), s.nominal


# --------------------------------------------------------------------------
# Size factors (NDS Supplement Table 4A) and lumber-value lookups
# --------------------------------------------------------------------------


def test_size_factor_lookup_maps_grade_and_nominal_to_table_labels(lib):
    sf = lib.size_factor("No.1", "2x4")
    assert sf.grade_group.startswith("Select Structural") and sf.width_label == '2", 3", & 4"'
    assert lib.size_factor("No.2", "2x6").width_label == '6"'
    assert lib.size_factor("Select Structural", "2x8").width_label == '8"'
    assert lib.size_factor("Stud", "2x6").width_label == '5" & 6"'


def test_size_factor_matches_engine_hardcoded_value(lib):
    """design/factors.py hard-codes C_F(Fc) = 1.15 for DF-L No.1 2x4; the table row must agree."""
    assert lib.size_factor("No.1", "2x4").CF_Fc == pytest.approx(1.15)


def test_size_factor_unknown_grade_is_a_lookup_error(lib):
    with pytest.raises(LookupError):
        lib.size_factor("Dense Select Structural", "2x4")


def test_size_factors_table_is_optional(tmp_path):
    """A data directory without size_factors.csv (e.g. the WoodWorks fixture) still loads."""
    import shutil

    for name in RECORD_TYPES:
        if name != "size_factors":
            shutil.copy(DATA_DIR / f"{name}.csv", tmp_path / f"{name}.csv")
    assert load_library(tmp_path).size_factors == []


def test_lumber_values_present_for_every_grade_and_size_in_scope(lib):
    dim = '2"-4" thick, 2" & wider'
    for species in ("Douglas Fir-Larch", "Spruce-Pine-Fir"):
        for grade in ("Select Structural", "No.1", "No.2", "No.3", "Stud"):
            v = lib.lumber_values(species, grade, dim)
            assert v.E_psi and v.Fc_psi and v.specific_gravity, (species, grade)
    for size_class in ('2" - 4" wide', '5" - 6" wide', '8" wide'):
        for grade in ("Select Structural", "No.1", "No.2", "No.3", "Stud"):
            v = lib.lumber_values("Southern Pine", grade, size_class)
            assert v.E_psi and v.Fc_psi and v.specific_gravity == 0.55, (size_class, grade)


def test_lumber_values_agree_with_woodworks_fixture_row(lib):
    """The teammates' answer-key fixture transcribed DF-L No.1 from the example; Table 4A must agree."""
    fixture = Path(__file__).parent / "fixtures" / "woodworks_components" / "lumber_design_values.csv"
    with fixture.open(newline="", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["species_group"] == "Douglas Fir-Larch" and r["grade"] == "No.1"]
    assert rows, "fixture row not found"
    table = lib.lumber_values("Douglas Fir-Larch", "No.1", '2"-4" thick, 2" & wider')
    for col in ("Fb_psi", "Ft_psi", "Fv_psi", "Fc_perp_psi", "Fc_psi", "E_psi", "Emin_psi"):
        assert float(rows[0][col]) == pytest.approx(getattr(table, col)), col
