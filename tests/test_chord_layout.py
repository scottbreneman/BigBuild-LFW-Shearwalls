"""Example chord layout rule: chord length and lever arm from the post count (example Figs. 3.7-3.8)."""

import dataclasses

import pytest

from analysis.stack import example_layout
from design.engine import run_design
from woodworks_example import inputs, library

# Example Table 3.9 post counts, Table 3.8 chord lengths, Table 3.6 lever arms (story 1 = "3rd").
N = [16, 13, 10, 7, 6]
LC = [2.500, 2.125, 1.750, 1.375, 1.250]
D = [26.97, 27.18, 27.40, 27.65, 27.75]


@pytest.mark.parametrize("n,lc,d", list(zip(N, LC, D)))
def test_rule_reproduces_example_geometry(n, lc, d):
    _, _, got_lc, got_d = example_layout(n, 1.5, 6.0, 3, 29.0)
    assert got_lc == pytest.approx(lc)
    assert got_d == pytest.approx(d, abs=0.006)


def test_all_outboard_when_few_posts():
    x_t, x_c, lc, _ = example_layout(2, 1.5, 6.0, 3, 29.0)
    assert x_t == 6.0 and x_c == 1.5 and lc == pytest.approx(0.75)


def test_layout_rule_run_matches_given_geometry():
    given = run_design(inputs(), library())
    inp = inputs()
    inp = dataclasses.replace(inp, stories=tuple(
        dataclasses.replace(s, chord=dataclasses.replace(s.chord, layout="example", chord_length_ft=None,
                                                          d_arm_ft=None)) for s in inp.stories))
    rule = run_design(inp, library())
    assert rule.status == given.status
    for i in range(1, 6):
        for c in ("comp", "rod", "drift"):
            assert rule.check(f"S{i}.{c}").demand == pytest.approx(given.check(f"S{i}.{c}").demand, rel=0.003)
        assert rule.step(f"S{i}.statics.d").status == "assumption"
