"""Deflection options (decision D6): no take-up device, cumulative chord deformation,
4-term deflection, and rotation carried up from lower stories.

The 4-term components are also cross-checked cell by cell against the local SEB
spreadsheet in test_seb_spreadsheet.py.
"""

import dataclasses

import pytest

from design.components import load_library
from design.engine import run_design
from design.inputs import validate
from design.trace import CheckStatus
from woodworks_example import COMPONENTS_DIR, inputs, library

STORIES = range(1, 6)


def approx(expected, digits):
    return pytest.approx(expected, rel=0.01, abs=0.6 * 10**-digits)


def no_takeup(inp, shrinkage_in=0.190):
    """Example Table 3.17B: no take-up device; shrinkage 0.190 in. per level from example Table 2.1."""
    return dataclasses.replace(inp, stories=tuple(
        dataclasses.replace(s, tiedown=dataclasses.replace(s.tiedown, takeup_device=False, shrinkage_in=shrinkage_in))
        for s in inp.stories))


def test_default_is_unchanged_by_shrinkage_when_takeup_present():
    base = run_design(inputs(), library())
    inp = inputs()
    inp = dataclasses.replace(inp, stories=tuple(
        dataclasses.replace(s, tiedown=dataclasses.replace(s.tiedown, shrinkage_in=0.190)) for s in inp.stories))
    r = run_design(inp, library())
    for i in STORIES:
        assert r.check(f"S{i}.drift").demand == base.check(f"S{i}.drift").demand
        assert r.step(f"S{i}.drift.shrinkage").value == 0.0  # compensated by the take-up device


def test_table_3_17B_per_level_without_takeup_p48():
    r = run_design(no_takeup(inputs()), library())
    got = [r.step(f"S{i}.drift.delta_a").value for i in STORIES]
    # The example prints 0.466 for the 4th level, but its own components
    # (0.096 + 0.190 + 0.100 + 0.032 = 0.418, x b/d) and its cumulative column
    # (0.87 = 0.427 + 0.446) both give 0.446; 0.466 is a typo in the example.
    assert got == [approx(e, 3) for e in [0.427, 0.446, 0.408, 0.334, 0.266]]
    for i in STORIES:
        ids = {s.id for s in r.check(f"S{i}.drift").steps}
        assert f"S{i}.drift.shrinkage" in ids
        assert f"S{i}.drift.slack" not in ids and f"S{i}.drift.takeup" not in ids


def test_table_3_17B_cumulative_without_restraint_each_level_p48():
    r = run_design(dataclasses.replace(no_takeup(inputs()), restraint_each_level=False), library())
    got = [r.step("S1.drift.delta_a").value] + [r.step(f"S{i}.drift.delta_a_cum").value for i in range(2, 6)]
    assert got == [approx(e, 2) for e in [0.43, 0.87, 1.28, 1.62, 1.88]]
    # The cumulative value drives the anchorage term.
    d3 = r.step("S5.drift.d3").value
    assert d3 == pytest.approx(10 * got[4] / 29.0)


def test_four_term_needs_panel_rigidity_data():
    r = run_design(inputs(deflection_method="4-term"), library())
    drift = r.check("S1.drift")
    assert drift.status is CheckStatus.NEEDS_INPUT and "Gvtv_lb_per_in" in drift.message


def test_four_term_formula(tmp_path):
    """Wire check with a synthetic G_v t_v (not a design value) and the example's 10d slip equation."""
    for f in COMPONENTS_DIR.glob("*.csv"):
        text = f.read_text(encoding="utf-8")
        if f.name == "sheathing_panels.csv":
            lines = text.splitlines()
            head = lines[0].split(",")
            row = lines[1].split(",")
            row[head.index("Gvtv_lb_per_in")] = "50000"
            text = "\r\n".join([lines[0], ",".join(row)]) + "\r\n"
        (tmp_path / f.name).write_text(text, encoding="utf-8")
    r = run_design(inputs(deflection_method="4-term"), load_library(tmp_path))
    v = r.step("S5.drift.v").value  # roof: 6 in. edge nailing, one side, not Structural I
    Vn = v * 6 / 12
    en = 1.2 * (Vn / 769) ** 3.276
    assert r.step("S5.drift.V_n").value == pytest.approx(Vn)
    assert r.step("S5.drift.e_n").value == pytest.approx(en)
    assert r.step("S5.drift.d2").value == pytest.approx(v * 10 / 50000 + 0.75 * 10 * en)
    # Two-sided bottom story: rigidity doubles, nail load halves.
    v1 = r.step("S1.drift.v").value
    assert r.step("S1.drift.Gvtv").value == 100000
    assert r.step("S1.drift.V_n").value == pytest.approx(v1 / 2 * 4 / 12)


def test_rotation_carried_up_rigid_body_geometry():
    base = run_design(inputs(), library())
    r = run_design(inputs(carry_rotation=True), library())
    assert r.check("S1.drift").demand == base.check("S1.drift").demand
    b, h = 29.0, 10.0
    theta = []
    for k in STORIES:
        da = base.step(f"S{k}.drift.delta_a").value
        db = base.step(f"S{k}.drift.d1").value
        theta.append(da / (12 * b) + 1.5 * db / (12 * h))
    for i in range(2, 6):
        below = 12 * h * sum(theta[: i - 1])
        assert r.step(f"S{i}.drift.delta_below").value == pytest.approx(below)
        own = base.step(f"S{i}.drift.delta_sw").value
        assert r.check(f"S{i}.drift").demand == pytest.approx(4.0 * (own + below))
    # Hand check, story 2: θ_1 = 0.2888/(12·29) + 1.5(0.00215)/120 ≈ 8.57e-4 rad -> Δ_below ≈ 0.103 in.
    assert r.step("S2.drift.delta_below").value == approx(0.103, 3)


def test_rotation_and_cumulative_are_exclusive():
    inp = inputs(carry_rotation=True, restraint_each_level=False)
    assert any(e.field == "carry_rotation" for e in validate(inp))
