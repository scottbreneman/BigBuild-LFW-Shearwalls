"""Statics section: free-body figure, notation, load-combination factors and the
shear / overturning / tension calculations story by story (docs/spec-io.md A1, A6-A9, A15)."""

from __future__ import annotations

from design.result import DesignResult
from design.trace import Step

from .figures import stack_fbd_svg
from .model import Figure, Paragraph, Section, StepTable, Subheading, Table, story_order
from .steps import is_combo, is_statics, local_id

# Order of the statics steps inside one story's table.
_ORDER = ("statics.V", "statics.M_up", "statics.M_OT", "statics.w_D", "statics.d", "chord.C_E", "chord.M_R",
          "chord.asd.net", "chord.asd.T", "chord.dT")

_NOTATION = (
    ("F_j", "Strength-level lateral force applied at the top of story j", "lb"),
    ("H_j", "Elevation of the top of story j above the base of story 1", "ft"),
    ("b", "Wall length", "ft"),
    ("d", "Chord lever arm", "ft"),
)


def story_statics_steps(result: DesignResult, story: int) -> list[Step]:
    prefix = f"S{story}."
    found = {local_id(s.id): s for s in result.stack_steps if s.id.startswith(prefix) and is_statics(s)}
    ordered = [found.pop(k) for k in _ORDER if k in found]
    return ordered + list(found.values())  # w_L, w_Lr and anything added later, after the main sequence


def build_statics(result: DesignResult) -> Section:
    n = len(result.inputs.stories)
    blocks: list = [
        Paragraph(
            "Free-body statics of the wall stack. Each story is cut at its base. Applying the story forces F above "
            "the cut gives the story shear V = ΣF and the overturning moment M_OT = ΣF·(H − H_base). "
            "The moment is resisted by a tension-compression couple at the wall ends, C_E = M_OT / d, less the "
            "dead-load resisting moment M_R. Forces F are strength level; the ASD combination factors below convert "
            "them for the net tension."),
        Figure(stack_fbd_svg(result),
               caption="Free-body diagram of the stack. Red arrows are the applied story forces F; dashed lines are the "
                       "story cuts; green arrows are the base reactions of story 1: shear V, and the chord tension (T) "
                       "and compression (C) couple that resists overturning."),
    ]

    seen: dict[str, tuple[str, str, str]] = {sym: (sym, meaning, unit) for sym, meaning, unit in _NOTATION}
    notation_steps = [s for st in range(1, n + 1) for s in story_statics_steps(result, st)]
    notation_steps += [s for s in result.stack_steps if is_combo(s)]
    for s in notation_steps:
        seen.setdefault(s.symbol, (s.symbol, s.name, s.unit))
    blocks.append(Table(("Symbol", "Meaning", "Unit"), tuple(seen.values()), caption="Notation.", symbol_cols=(0,)))

    combos = tuple(s for s in result.stack_steps if is_combo(s))
    if combos:
        blocks.append(Subheading("Load combination factors"))
        blocks.append(StepTable(combos, caption="Factors applied to the strength-level force E_h and to the dead load."))

    for i in story_order(n):
        steps = story_statics_steps(result, i)
        if steps:
            blocks.append(Subheading(f"Story {i}: shear, overturning and chord tension"))
            blocks.append(StepTable(tuple(steps)))
    return Section("statics", "Statics: shear and overturning", tuple(blocks))
