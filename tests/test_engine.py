"""Engine behaviour: the result contract, input validation and NEEDS_INPUT handling.

These tests check plumbing, not engineering values (see test_woodworks_seismic.py).
"""

import dataclasses
import json

from design.engine import run_design
from design.inputs import GenericHoldDown, validate
from design.result import OverallStatus
from design.trace import CheckStatus, Tracer
from woodworks_example import inputs, library


def _with_story(inp, k, **changes):
    stories = list(inp.stories)
    stories[k] = dataclasses.replace(stories[k], **changes)
    return dataclasses.replace(inp, stories=tuple(stories))


def test_tracer_result_and_worst_source():
    t = Tracer("x")
    t.step("a", "a", "a", "", "", 1.0, "", "statics", "statics")
    t.step("b", "b", "b", "", "", 2.0, "", "SDPWS", "memory")
    r = t.result("x", "x", 1, "shear", demand=50.0, capacity=40.0, demand_unit="plf")
    assert r.status is CheckStatus.FAIL and r.dcr == 1.25 and not r.passed
    assert r.worst_source == "memory"


def test_validation_blocks_the_run():
    bad = inputs(b_ft=-1.0, S_DS=None)
    fields = {e.field for e in validate(bad)}
    assert {"b_ft", "S_DS"} <= fields
    r = run_design(bad, library())
    assert r.status is OverallStatus.INVALID_INPUT and r.stories == ()


def test_pending_production_library_gives_needs_input_not_a_crash():
    # Every production row is pending until the engineers fill the tables.
    inp = inputs()
    for k in range(5):
        inp = _with_story(inp, k, assembly_id="WSP-S1-15/32-10dc-4")
    r = run_design(inp)
    assert r.status is OverallStatus.INCOMPLETE
    assert r.needs_input
    assert all(item.decision for item in r.needs_input)
    shear = r.check("S1.shear")
    assert shear.status is CheckStatus.NEEDS_INPUT and "pending" in shear.message


def test_generic_holddown_path():
    inp = inputs()
    for k in range(5):
        inp = _with_story(inp, k, tiedown=GenericHoldDown(T_allow_lb=12_000, delta_a_in=0.2))
    r = run_design(inp, library())
    hd1 = r.check("S1.holddown")
    assert hd1.status is CheckStatus.FAIL  # 15.7 k > 12 k
    assert r.check("S5.holddown").status is CheckStatus.PASS
    assert r.check("S1.drift").status is CheckStatus.PASS
    assert r.status is OverallStatus.FAIL and r.governing_check == "S1.holddown"
    assert not any(c.category.startswith("plate") for c in r.checks())


def test_aspect_ratio_over_2_needs_engineer_decision_d3():
    inp = inputs(b_ft=4.0, d_post_in=5.25)
    for k in range(5):
        inp = _with_story(inp, k, chord=dataclasses.replace(inp.stories[k].chord, d_arm_ft=None))
    r = run_design(inp, library())
    asp = r.check("S1.aspect")
    assert asp.status is CheckStatus.NEEDS_INPUT and asp.decision == "D3"


def test_missing_size_factor_is_reported():
    inp = inputs()
    inp = _with_story(inp, 0, chord=dataclasses.replace(inp.stories[0].chord, post_nominal="2x6"))
    r = run_design(inp, library())
    assert r.check("S1.comp").status is CheckStatus.NEEDS_INPUT


def test_wind_runs_with_explicit_gaps():
    r = run_design(inputs(load_type="wind"), library())
    assert r.check("S1.shear").status is CheckStatus.NEEDS_INPUT  # no wind column in the example rows
    assert r.check("S1.drift").decision == "D6"  # no wind drift limit given
    r2 = run_design(inputs(load_type="wind", wind_drift_limit_ratio=1 / 400), library())
    d1 = r2.check("S1.drift")
    assert d1.status in (CheckStatus.PASS, CheckStatus.FAIL)
    assert d1.capacity == 0.0025 * 120
    assert d1.demand == r2.step("S1.drift.delta_sw").value  # no C_d / I_e for wind
    assert r.check("S1.comp").status in (CheckStatus.PASS, CheckStatus.FAIL)
    # 0.6D + 0.6W with the example's seismic forces taken as W.
    assert r.step("S5.chord.asd.T").value >= 0


def test_to_dict_is_json_and_lists_unverified_steps():
    r = run_design(inputs(), library())
    d = json.loads(json.dumps(r.to_dict()))
    assert d["status"] == "pass"
    assert d["stories"][0]["checks"][0]["status"] == "pass"
    assert r.unverified_steps and all(s.status in ("memory", "assumption") for s in r.unverified_steps)
    assert len({s.id for s in r.unverified_steps}) == len(r.unverified_steps)
    assert r.component_items_to_verify  # fixture rows are 'memory'
