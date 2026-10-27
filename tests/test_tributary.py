"""Flexible-diaphragm tributary distribution (decision D9, analysis/tributary.py).

Expected values are hand calculations of the D9 equations, not reference-example
values: the WoodWorks example supplies story forces on the wall directly.
"""

import dataclasses

import pytest

from analysis.tributary import resolve_tributary
from design.engine import run_design
from design.inputs import TributarySpec, validate
from woodworks_example import inputs, library


def _with_trib(inp, specs):
    """Attach one TributarySpec (or None) per story, bottom first."""
    stories = tuple(dataclasses.replace(s, tributary=t) for s, t in zip(inp.stories, specs))
    return dataclasses.replace(inp, stories=stories)


def test_no_tributary_leaves_inputs_unchanged():
    inp = inputs()
    out, steps = resolve_tributary(inp)
    assert out is inp and steps == ()


def test_interior_line_equal_spans():
    # V = 60,000 lb over L = 120 ft -> w = 500 plf; t = 30/2 + 30/2 = 30 ft -> F_line = 15,000 lb.
    # b = 29 ft alone on its line -> F = 15,000 lb.
    inp = inputs()
    spec = TributarySpec(V_story_lb=60_000, L_ft=120, span_left_ft=30, span_right_ft=30)
    out, steps = resolve_tributary(_with_trib(inp, [spec] + [None] * (len(inp.stories) - 1)))
    assert out.stories[0].F_lb == pytest.approx(15_000)
    by_id = {s.id: s for s in steps}
    assert by_id["S1.statics.trib.w"].value == pytest.approx(500)
    assert by_id["S1.statics.trib.t"].value == pytest.approx(30)
    assert by_id["S1.statics.trib.F_line"].value == pytest.approx(15_000)


def test_unequal_spans_and_shared_line():
    # w = 48,000 / 96 = 500 plf; t = 24/2 + 40/2 = 32 ft -> F_line = 16,000 lb.
    # Line has 29 + 11 = 40 ft of wall -> F = 16,000 (29/40) = 11,600 lb.
    inp = inputs()
    spec = TributarySpec(V_story_lb=48_000, L_ft=96, span_left_ft=24, span_right_ft=40, line_length_ft=40)
    out, _ = resolve_tributary(_with_trib(inp, [spec] * len(inp.stories)))
    assert inp.b_ft == 29
    assert all(s.F_lb == pytest.approx(11_600) for s in out.stories)


def test_edge_line_takes_half_a_span():
    # Building edge: t = 0/2 + 50/2 = 25 ft; w = 20,000 / 100 = 200 plf -> F = 5,000 lb.
    inp = inputs()
    spec = TributarySpec(V_story_lb=20_000, L_ft=100, span_left_ft=0, span_right_ft=50)
    out, _ = resolve_tributary(_with_trib(inp, [spec] + [None] * (len(inp.stories) - 1)))
    assert out.stories[0].F_lb == pytest.approx(5_000)
    assert out.stories[1].F_lb == inp.stories[1].F_lb  # stories without a spec keep their typed F


def test_engine_uses_and_reports_tributary_forces():
    # Feed each story the tributary spec that reproduces its example force: results must not change.
    inp = inputs()
    specs = [TributarySpec(V_story_lb=s.F_lb * 4, L_ft=100, span_left_ft=25, span_right_ft=25)
             for s in inp.stories]
    base = run_design(inp, library())
    trib = run_design(_with_trib(inp, specs), library())
    assert trib.status == base.status and trib.max_dcr == pytest.approx(base.max_dcr)
    assert [s.F_lb for s in trib.inputs.stories] == pytest.approx([s.F_lb for s in inp.stories])
    ids = {s.id for s in trib.unverified_steps}
    assert {"S1.statics.trib.w", "S1.statics.trib.t", "S1.statics.trib.F"} <= ids  # listed under Items to verify
    assert "S1.statics.trib.F_line" not in ids  # plain statics


@pytest.mark.parametrize("spec, field", [
    (TributarySpec(V_story_lb=-1, L_ft=100, span_left_ft=10, span_right_ft=10), "stories[1].tributary.V_story_lb"),
    (TributarySpec(V_story_lb=1, L_ft=0, span_left_ft=10, span_right_ft=10), "stories[1].tributary.L_ft"),
    (TributarySpec(V_story_lb=1, L_ft=100, span_left_ft=0, span_right_ft=0), "stories[1].tributary"),
    (TributarySpec(V_story_lb=1, L_ft=10, span_left_ft=30, span_right_ft=30), "stories[1].tributary"),
    (TributarySpec(V_story_lb=1, L_ft=100, span_left_ft=10, span_right_ft=10, line_length_ft=5),
     "stories[1].tributary.line_length_ft"),
])
def test_validation(spec, field):
    inp = inputs()
    bad = _with_trib(inp, [spec] + [None] * (len(inp.stories) - 1))
    assert field in {e.field for e in validate(bad)}


def test_form_and_saved_file_round_trip():
    # Story table -> inputs -> story table, and inputs -> JSON -> inputs, both keep the tributary spec.
    from ui import forms, io
    inp = inputs()
    specs = [TributarySpec(V_story_lb=40_000, L_ft=100, span_left_ft=20, span_right_ft=30, line_length_ft=40)]
    case = _with_trib(inp, specs + [None] * (len(inp.stories) - 1))
    loads, chords, ties = forms.frames_from_inputs(case)
    assert loads.at[1, "trib_V_seismic_lb"] == 40_000 and loads.at[2, "trib_L_ft"] == 0
    g = forms.global_values_from_inputs(case) | {"load_type": "seismic"}
    rebuilt = forms.build_inputs(g, loads, chords, ties)
    assert rebuilt.stories[0].tributary == specs[0] and rebuilt.stories[1].tributary is None
    assert io.inputs_from_json(io.inputs_to_json(case)).stories[0].tributary == specs[0]


def test_tributary_force_alone_starts_a_load_case():
    # Typed F all zero, tributary V_x given for wind on story 1: the wind case runs on the tributary force.
    from ui import forms
    inp = inputs()
    loads, chords, ties = forms.frames_from_inputs(inp)
    loads["F_seismic_lb"] = 0.0
    loads.loc[1, ["trib_V_wind_lb", "trib_L_ft", "trib_span_left_ft", "trib_span_right_ft"]] = [10_000, 100, 50, 50]
    g = forms.global_values_from_inputs(inp)
    cases = forms.build_cases(g, loads, chords, ties)
    assert list(cases) == ["wind"]
    r = run_design(cases["wind"], library())
    assert r.inputs.stories[0].F_lb == pytest.approx(5_000)  # 100 plf x 50 ft
