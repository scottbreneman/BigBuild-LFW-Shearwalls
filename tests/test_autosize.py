"""Auto-size: lightest preferred option that passes each strength check (drift reported, not driven)."""

import dataclasses

import pytest

from design.autosize import NO_PASS, OK, _evaluate, autosize
from design.checks.compression import check_compression
from design.checks.shear import check_shear
from design.checks.tiedown import check_rod
from design.preferences import MaterialPreferences
from design.trace import CheckStatus
from woodworks_example import inputs, library

LIB = library()
PREFS = MaterialPreferences(name="example", min_posts=2, max_posts=16)
STORIES = range(1, 6)


@pytest.fixture(scope="module")
def sized():
    return autosize(inputs(), LIB, PREFS)


def test_every_strength_check_passes(sized):
    for i in STORIES:
        for c in ("shear", "comp", "rod"):
            assert sized.result.check(f"S{i}.{c}").status is CheckStatus.PASS, f"S{i}.{c}"
        assert sized.stories[i - 1].status == OK


def test_inputs_unchanged_until_applied(sized):
    assert sized.before.inputs == inputs()  # the design of the unchanged inputs
    assert sized.proposed != inputs()
    assert sized.proposed.stories[0].chord.layout == "example"


def test_nailing_is_the_lightest_passing_option(sized):
    opts = PREFS.assembly_options(LIB)
    for i in STORIES:
        s = sized.proposed.stories[i - 1]
        k = next(k for k, (a, n) in enumerate(opts) if a.assembly_id == s.assembly_id and n == s.sides)
        for a, n in opts[:k]:  # every lighter option fails
            trial = _with(sized.proposed, i, assembly_id=a.assembly_id, sides=n)
            assert _evaluate(trial, LIB, i, check_shear).status is CheckStatus.FAIL


def test_one_fewer_post_fails(sized):
    for i in STORIES:
        c = sized.proposed.stories[i - 1].chord
        if c.n_posts > PREFS.min_posts:
            trial = _with(sized.proposed, i, chord=dataclasses.replace(c, n_posts=c.n_posts - 1))
            assert _evaluate(trial, LIB, i, check_compression).status is CheckStatus.FAIL


def test_next_lighter_rod_fails(sized):
    opts = [r for r in PREFS.rod_options(LIB) if r.rod_allowable_tension_lb is not None]
    for i in STORIES:
        td = sized.proposed.stories[i - 1].tiedown
        k = [r.system_id for r in opts].index(td.system_id)
        if k:
            trial = _with(sized.proposed, i, tiedown=dataclasses.replace(td, system_id=opts[k - 1].system_id))
            assert _evaluate(trial, LIB, i, check_rod).status is CheckStatus.FAIL


def test_drift_is_reported_not_driven(sized):
    for p in sized.stories:
        assert "drift" in p.dcr_after or any("drift" in n for n in p.notes)


def test_too_small_preferred_list_reports_no_passing_option():
    prefs = MaterialPreferences(assemblies=("EX-OSB-15/32-10dc-6",), sides=(1,), rods=("EX-F1554-36-5/8",))
    sized = autosize(inputs(), LIB, prefs)
    bottom = sized.stories[0]
    assert bottom.status == NO_PASS
    assert any("passes shear" in n for n in bottom.notes) and any("passes tension" in n for n in bottom.notes)
    assert sized.result.check("S1.shear").status is CheckStatus.FAIL


def _with(inp, i, **changes):
    stories = list(inp.stories)
    stories[i - 1] = dataclasses.replace(stories[i - 1], **changes)
    return dataclasses.replace(inp, stories=tuple(stories))
