"""The verification worklist reflects the source and the library, and stays honest as they change."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import verification_worklist as wl  # noqa: E402


@pytest.fixture(scope="module")
def sites():
    """Scanned sites with the run-time citation and priority filled in, as the report builds them."""
    found, _ = wl.scan_source(ROOT / "src")
    wl.add_runtime_facts(found, "example")
    return found


@pytest.fixture(scope="module")
def text():
    return wl.build("example")


def test_every_site_points_at_a_real_line(sites):
    assert sites
    for s in sites:
        line = (ROOT / s.file).read_text(encoding="utf-8").splitlines()[s.line - 1]
        assert ".step(" in line or "step(" in line, (s.file, s.line, line)
        assert s.status in wl.UNVERIFIED


def test_only_unverified_statuses_are_listed(sites):
    assert {s.status for s in sites} <= set(wl.UNVERIFIED)


def test_a_verified_step_drops_off_the_list(tmp_path):
    """Verifying something must shrink the list; this is what re-running the tool shows."""
    src = tmp_path / "src"
    (src / "design").mkdir(parents=True)
    (src / "design" / "x.py").write_text(
        't.step("a", "A", "a", "eq", "sub", 1.0, "lb", "NDS-2024 Table 4.3.1", "memory")\n'
        't.step("b", "B", "b", "eq", "sub", 2.0, "lb", "NDS-2024 Table 4.3.1", "verified")\n'
        't.step("c", "C", "c", "eq", "sub", 3.0, "lb", "statics", "statics")\n', encoding="utf-8")
    found, totals = wl.scan_source(src)
    assert [s.key for s in found] == ["a"]
    assert found[0].file.endswith("x.py")
    assert totals["verified"] == 1 and totals["statics"] == 1 and totals["memory"] == 1


def test_steps_taking_their_status_from_a_component_row_are_not_listed(tmp_path):
    """Those inherit the library row's status, so the row is the thing to verify, not the step."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "y.py").write_text(
        't.step("Fc", "Reference compression", "F_c", "table", s, v, "psi", vcit, vst)\n', encoding="utf-8")
    found, totals = wl.scan_source(src)
    assert found == [] and totals == {}


def test_runtime_join_never_crosses_the_seismic_and_wind_paths(sites):
    """A wind step must not inherit a seismic citation: that would cite the wrong provision."""
    by_name = {s.name: s for s in sites if s.name}
    wind = by_name.get("ASD wind factor on W")
    assert wind is not None
    assert "2.4.1" in wind.shown_citation
    assert "12.4.2.2" not in wind.shown_citation  # the seismic vertical-acceleration section


def test_identify_names_a_row_from_its_leading_columns():
    row = {"panel_type": "OSB", "panel_grade": "Structural I", "nominal_thickness_label": "15/32",
           "nominal_thickness_in": "0.46875", "source_doc": "SDPWS 2021", "status": "pending"}
    assert wl._identify(row) == "OSB · Structural I · 15/32"
    assert wl._identify({"designation": "6d common", "pennyweight": "6d", "source_doc": "NDS"}) == "6d common"
    assert wl._identify({"source_doc": "x", "status": "pending"}) == "(row)"


def test_library_scan_counts_verified_and_pending():
    rows = wl.scan_library(ROOT / "src" / "design" / "components" / "data")
    assert rows, "no component CSVs found"
    assert any(r.verified for r in rows.values())
    for name, r in rows.items():
        assert all(status != "verified" for _, status, _ in r.pending), name


def test_report_has_progress_priorities_and_both_halves(text):
    assert "# Verification worklist" in text
    assert "## Progress" in text
    assert "## Calculation steps" in text
    assert "## Component library rows" in text
    assert "**governs**" in text  # priority marking survived the run
    assert "tools/verification_worklist.py" in text  # says how to regenerate


def test_every_listed_step_shows_a_place_to_edit(text, sites):
    for s in sites:
        assert f"`{s.file}:{s.line}`" in text, s


def test_markdown_tables_are_rectangular(text):
    block = []
    for line in text.splitlines() + [""]:
        if line.startswith("|"):
            block.append(line)
            continue
        if block:
            assert len({row.count("|") for row in block}) == 1, block[0]
            block = []
