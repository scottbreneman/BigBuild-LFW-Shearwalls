"""Flexible-diaphragm tributary distribution of story forces to this wall (decision D9).

For each story with a ``TributarySpec`` the story force F_i on the wall is
computed instead of typed in:

    w_x    = V_x / L                      (story force spread uniformly, D9c)
    t      = s_left / 2 + s_right / 2     (tributary width of the wall line, D9a)
    F_line = w_x t
    F_i    = F_line b / Σb_line           (share by wall length, D9b)

Forces stay at strength level (E_h or W); the design checks apply the load
combinations as before. Steps use the ``S{i}.statics.trib`` prefix so the
report tabulates them with the other per-story statics.
"""

from __future__ import annotations

from dataclasses import replace

from design.inputs import DesignInputs
from design.trace import Step, Tracer, fmt

_CITE = "spec-io D9; diaphragm flexibility per ASCE 7-22 §12.3.1"


def resolve_tributary(inp: DesignInputs) -> tuple[DesignInputs, tuple[Step, ...]]:
    """Inputs with F_lb filled from each story's tributary spec, and the steps behind them."""
    if not any(s.tributary for s in inp.stories):
        return inp, ()
    b = inp.b_ft
    stories, steps = [], []
    for i, s in enumerate(inp.stories, start=1):
        tr = s.tributary
        if tr is None:
            stories.append(s)
            continue
        t = Tracer(f"S{i}.statics.trib")
        w = t.step("w", "Story force per unit length of diaphragm (D9c)", "w_x", r"w_x = V_x / L",
                   f"{fmt(tr.V_story_lb, 0)} lb / {fmt(tr.L_ft, 2)} ft", tr.V_story_lb / tr.L_ft, "plf",
                   "spec-io D9", "assumption", note="Story force spread uniformly along L; no torsion")
        width = t.step("t", "Tributary width of the wall line (D9a)", "t",
                       r"t = s_{left} / 2 + s_{right} / 2",
                       f"{fmt(tr.span_left_ft, 2)}/2 + {fmt(tr.span_right_ft, 2)}/2 ft",
                       (tr.span_left_ft + tr.span_right_ft) / 2, "ft", _CITE, "assumption",
                       note="Diaphragm idealized as flexible, simply spanning between wall lines")
        F_line = t.step("F_line", "Force on the wall line", "F_line", r"F_{line} = w_x t",
                        f"{fmt(w, 1)} plf ({fmt(width, 2)} ft)", w * width, "lb", "statics", "statics")
        line = tr.line_length_ft if tr.line_length_ft is not None else b
        F = t.step("F", "Story force on this wall (D9b)", "F", r"F_i = F_{line} b / \sum b_{line}",
                   f"{fmt(F_line, 0)} lb ({fmt(b, 2)} ft / {fmt(line, 2)} ft)", F_line * b / line, "lb",
                   "spec-io D9", "assumption", note="Line force shared among its walls by length")
        steps.extend(t.steps)
        stories.append(replace(s, F_lb=F))
    return replace(inp, stories=tuple(stories)), tuple(steps)
