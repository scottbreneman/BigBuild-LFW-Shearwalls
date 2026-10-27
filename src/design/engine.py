"""Design engine: inputs in, a fully traced ``DesignResult`` out.

``run_design`` is pure (no UI imports, no I/O beyond loading the component
library) so the Streamlit app can call it on every input change.
"""

from __future__ import annotations

from typing import Callable

from analysis.stack import stack_forces
from analysis.tributary import resolve_tributary

from .checks import Context
from .checks.compression import check_compression
from .checks.drift import check_drift
from .checks.shear import check_aspect, check_framing_3x, check_shear
from .checks.tiedown import check_holddown, check_plate_bearing, check_plate_bending, check_rod
from .chords import chord_forces
from .combos import combos_for
from .components import ComponentLibrary
from .inputs import DesignInputs, GenericHoldDown, validate
from .library import cite, default_library
from .result import DesignResult, NeedsInputItem, OverallStatus, StoryResult, summarize
from .trace import CheckResult, CheckStatus, NeedsEngineerInput

Check = Callable[[Context, int], CheckResult]

_CATEGORY = {
    check_shear: ("shear", "Sheathing shear"),
    check_framing_3x: ("detailing", "Framing detailing"),
    check_aspect: ("aspect", "Aspect ratio"),
    check_compression: ("compression", "Chord compression"),
    check_holddown: ("holddown", "Hold-down tension"),
    check_rod: ("rod", "Tie-down rod tension"),
    check_plate_bearing: ("plate_bearing", "Bearing plate bearing"),
    check_plate_bending: ("plate_bending", "Bearing plate bending"),
    check_drift: ("drift", "Story drift"),
}
_SLUG = {"shear": "shear", "detailing": "framing", "aspect": "aspect", "compression": "comp",
         "holddown": "holddown", "rod": "rod", "plate_bearing": "plate_brg", "plate_bending": "plate_bend",
         "drift": "drift"}


def checks_for_story(ctx: Context, i: int) -> list[Check]:
    tiedown = [check_holddown] if isinstance(ctx.story(i).tiedown, GenericHoldDown) else \
        [check_rod, check_plate_bearing, check_plate_bending]
    return [check_shear, check_framing_3x, check_aspect, check_compression, *tiedown, check_drift]


def _run(fn: Check, ctx: Context, i: int) -> CheckResult:
    try:
        return fn(ctx, i)
    except NeedsEngineerInput as exc:
        cat, name = _CATEGORY[fn]
        return CheckResult(f"S{i}.{_SLUG[cat]}", f"{name}, story {i}", i, cat, CheckStatus.NEEDS_INPUT,
                           message=exc.message, decision=exc.decision)


def run_design(inp: DesignInputs, lib: ComponentLibrary | None = None) -> DesignResult:
    errors = validate(inp)
    if errors:
        return DesignResult(inputs=inp, load_type=inp.load_type, input_errors=tuple(errors),
                            status=OverallStatus.INVALID_INPUT)
    inp, trib_steps = resolve_tributary(inp)  # F_lb from tributary width where given (D9)
    lib = lib or default_library()
    combos = combos_for(inp)
    forces = stack_forces(inp)
    chords = chord_forces(inp, forces, combos)
    ctx = Context(inp, lib, combos, tuple(forces), tuple(chords))

    stories = []
    for i in range(1, len(inp.stories) + 1):
        results = [_run(fn, ctx, i) for fn in checks_for_story(ctx, i)]
        gov, dcr, st = summarize(results)
        stories.append(StoryResult(i, tuple(results), gov, dcr, st))

    all_checks = [c for s in stories for c in s.checks]
    gov, dcr, st = summarize(all_checks)
    stack_steps = tuple(combos.steps) + trib_steps + tuple(s for f in forces for s in f.steps) + \
        tuple(s for c in chords for s in c.steps)
    seen, unverified = set(), []
    for step in [*stack_steps, *(s for c in all_checks for s in c.steps)]:
        if step.status != "verified" and step.status != "statics" and step.id not in seen:
            seen.add(step.id)
            unverified.append(step)
    return DesignResult(
        inputs=inp,
        load_type=inp.load_type,
        stories=tuple(stories),
        stack_steps=stack_steps,
        governing_story=next((s.story for s in stories if s.governing_id == gov), None),
        governing_check=gov,
        max_dcr=dcr,
        status=st,
        needs_input=tuple(NeedsInputItem(c.id, c.decision, c.message) for c in all_checks
                          if c.status is CheckStatus.NEEDS_INPUT),
        unverified_steps=tuple(unverified),
        component_items_to_verify=tuple(f"{r.status.value}: {cite(r)}" for r in lib.items_to_verify()
                                        if r.status.value == "memory"),
    )
