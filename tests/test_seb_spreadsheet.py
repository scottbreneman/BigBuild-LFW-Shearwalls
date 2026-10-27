"""Cross-check the engine against the local SEB (Malone-Breneman) shear wall spreadsheet.

The spreadsheet is private and git-ignored; this module reads every expected
value from the local copy at run time and skips when the file is absent
(set SEB_XLSX to its path). See tests/seb_spreadsheet.py for the cell map.

- "5 Story 2025 Example Wall": the WoodWorks wall with unrounded intermediates;
  every mapped quantity must agree within 0.5 %.
- Both sheets: the SDPWS Commentary 4-term deflection components (G_v t_v,
  V_n, e_n, panel shear and nail slip terms) must agree within 0.5 %.
- "SDPWS 5 story example": an independent short wall with no dead load and failing
  drift; every quantity must agree except the named known differences, and the
  drift pass/fail must agree story by story.

This is a regression cross-check against another implementation, not
engineering validation.
"""

from pathlib import Path

import pytest

pytest.importorskip("openpyxl")

import seb_spreadsheet as seb  # noqa: E402
from design.components import load_library  # noqa: E402
from design.engine import run_design  # noqa: E402
from design.trace import CheckStatus  # noqa: E402

PATH = seb.workbook_path()
pytestmark = pytest.mark.skipif(PATH is None, reason="SEB spreadsheet not available locally (set SEB_XLSX)")
TOL = 0.005
EXAMPLE, SHORT_WALL = seb.SHEETS


@pytest.fixture(scope="module")
def wb():
    return seb.load(PATH)


@pytest.fixture(scope="module")
def runs(wb, tmp_path_factory):
    lib = load_library(seb.component_dir(wb, Path(tmp_path_factory.mktemp("seb_components"))))
    out = {}
    for sheet in seb.SHEETS:
        reason = seb.unsupported(wb, sheet)
        out[sheet] = None if reason else {
            run: run_design(seb.inputs_from_sheet(wb, sheet, run), lib) for run in ("design", "drift", "4-term")}
    return out


def compare(wb, runs, sheet):
    """Return (unexplained mismatches, known mismatches) as readable strings."""
    if runs[sheet] is None:
        pytest.skip(seb.unsupported(wb, sheet))
    ws = wb[sheet]
    bad, known = [], []
    for i in range(1, seb.N + 1):
        for p in [*seb.pairs(i), *seb.four_term_pairs(i)]:
            cell = ws[p.cell].value
            eng = seb.engine_value(runs[sheet][p.run], p)
            if eng is None:
                if cell not in (None, 0, 0.0):
                    bad.append(f"S{i} {p.label}: engine has no value, sheet {p.cell} = {cell}")
                continue
            ref = p.scale * float(cell)
            rel = abs(eng - ref) / abs(ref) if abs(ref) > 1e-6 else abs(eng - ref)
            if rel > TOL:
                msg = f"S{i} {p.label}: engine {eng:.5g} vs {p.cell} {ref:.5g} ({100 * rel:.2f} %)"
                reason = seb.known_reason(wb, sheet, i, p)
                (known if reason else bad).append(msg + (f" [{reason}]" if reason else ""))
    return bad, known


def test_example_wall_matches_every_mapped_quantity(wb, runs):
    bad, known = compare(wb, runs, EXAMPLE)
    assert not bad and not known, "\n".join(bad + known)


def test_short_wall_matches_except_known_differences(wb, runs):
    bad, known = compare(wb, runs, SHORT_WALL)
    assert not bad, "\n".join(bad)
    # Keep the known list honest: if one disappears, update seb_spreadsheet.py.
    assert known, "no known differences left; remove the stale known_difference entries"


def test_short_wall_drift_pass_fail_agrees(wb, runs):
    if runs[SHORT_WALL] is None:
        pytest.skip(seb.unsupported(wb, SHORT_WALL))
    ws = wb[SHORT_WALL]
    res = runs[SHORT_WALL]["drift"]
    for i in range(1, seb.N + 1):
        sheet_fails = ws[f"R{seb.row(222, i)}"].value > ws[f"S{seb.row(222, i)}"].value
        engine_fails = res.check(f"S{i}.drift").status is CheckStatus.FAIL
        assert engine_fails == sheet_fails, f"story {i}: engine fail={engine_fails}, sheet fail={sheet_fails}"


def test_strength_checks_agree_on_pass_fail(wb, runs):
    for sheet in seb.SHEETS:
        if runs[sheet] is None:
            continue
        ws, res = wb[sheet], runs[sheet]["design"]
        for i in range(1, seb.N + 1):
            for check, cell in (("shear", "J39"), ("comp", "F62"), ("rod", "J85")):
                col, top = cell[0], int(cell[1:])
                sheet_fails = ws[f"{col}{seb.row(top, i)}"].value > 1.0
                engine_fails = res.check(f"S{i}.{check}").status is CheckStatus.FAIL
                assert engine_fails == sheet_fails, f"{sheet} story {i} {check}"
