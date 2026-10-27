"""Auto-size: propose the lightest preferred materials that pass the strength checks.

For each story, in order:

1. nailing assembly and sheathed sides, by ascending n·v_n, until sheathing shear passes;
2. chord posts (preferred lumber × post size × count, example layout rule) by
   ascending post capacity, until chord compression passes;
3. the story's tie-down (rod system or hold-down) by ascending allowable tension,
   until tension passes. Bearing plates stay as entered.

With several load cases (e.g. seismic and wind on the same wall), a candidate is
accepted only if it passes in every case. Drift is not driven (owner decision).
The full design of the proposed inputs is returned, so drift and plate results
are reported alongside. Nothing changes until the caller applies the proposal.
"""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass
from typing import Callable

from analysis.stack import stack_forces

from .checks import Context
from .checks.compression import check_compression
from .checks.shear import check_shear
from .checks.tiedown import check_holddown, check_rod
from .chords import chord_forces
from .combos import combos_for
from .components import ComponentLibrary
from .engine import run_design
from .inputs import ChordSpec, DesignInputs, GenericHoldDown, RodSystem, StoryInput, validate
from .preferences import MaterialPreferences
from .result import DesignResult
from .trace import CheckResult, CheckStatus, NeedsEngineerInput

OK, NO_PASS, NEEDS = "ok", "no passing preferred option", "needs input"


@dataclass(frozen=True)
class Change:
    field: str
    current: str
    proposed: str


@dataclass(frozen=True)
class StoryProposal:
    story: int
    changes: tuple[Change, ...]
    dcr_before: dict  # check category -> DCR (None when not computed)
    dcr_after: dict
    status: str  # OK | NO_PASS | NEEDS
    notes: tuple[str, ...]


@dataclass(frozen=True)
class AutosizeResult:
    proposed_cases: dict  # load type -> proposed DesignInputs
    stories: tuple[StoryProposal, ...]
    before_cases: dict  # load type -> DesignResult of the unchanged inputs
    result_cases: dict  # load type -> DesignResult of the proposal (drift and plates reported, not driven)

    # single-case conveniences (the first case)
    @property
    def proposed(self) -> DesignInputs:
        return next(iter(self.proposed_cases.values()))

    @property
    def before(self) -> DesignResult:
        return next(iter(self.before_cases.values()))

    @property
    def result(self) -> DesignResult:
        return next(iter(self.result_cases.values()))


# --------------------------------------------------------------------------
# single-check evaluation
# --------------------------------------------------------------------------

def _evaluate(inp: DesignInputs, lib: ComponentLibrary, i: int, check: Callable) -> CheckResult | None:
    """Run one check for story ``i``; None if the inputs are invalid or the check needs input."""
    if validate(inp):
        return None
    combos = combos_for(inp)
    forces = stack_forces(inp)
    ctx = Context(inp, lib, combos, tuple(forces), tuple(chord_forces(inp, forces, combos)))
    try:
        return check(ctx, i)
    except NeedsEngineerInput:
        return None


def _with_story(inp: DesignInputs, i: int, **changes) -> DesignInputs:
    stories = list(inp.stories)
    stories[i - 1] = dataclasses.replace(stories[i - 1], **changes)
    return dataclasses.replace(inp, stories=tuple(stories))


def _passes(c: CheckResult | None) -> bool:
    return c is not None and c.status is CheckStatus.PASS


def _first(cases: dict) -> DesignInputs:
    return next(iter(cases.values()))


def _trial(cases: dict, i: int, **changes) -> dict:
    return {k: _with_story(v, i, **changes) for k, v in cases.items()}


def _evaluate_all(cases: dict, lib: ComponentLibrary, i: int, check: Callable) -> list | None:
    """The check in every case, or None if any case cannot be evaluated."""
    out = [_evaluate(v, lib, i, check) for v in cases.values()]
    return None if any(c is None for c in out) else out


def size_fits(size_class: str, nominal: str) -> bool:
    """Width-specific grade rows ('2" - 4" wide', '8" wide') apply only to matching nominal widths."""
    if "wide" not in size_class:
        return True
    width = float(nominal.split("x")[-1])
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", size_class)]
    return min(nums) <= width <= max(nums)


# --------------------------------------------------------------------------
# per-story steps
# --------------------------------------------------------------------------

def _size_nailing(cases, lib, prefs, i, notes):
    s = _first(cases).stories[i - 1]
    panel = prefs.panel_types[0] if prefs.panel_types else s.panel_type
    best = None
    for asm, n in prefs.assembly_options(lib):
        if asm.v_n_plf is None:
            continue
        trial = _trial(cases, i, assembly_id=asm.assembly_id, sides=n, panel_type=panel)
        cs = _evaluate_all(trial, lib, i, check_shear)
        if cs is None:
            continue
        best = trial
        if all(_passes(c) for c in cs):
            return trial, OK
    if best is None:
        notes.append("no preferred assembly has a nominal shear value; nailing kept")
        return cases, NEEDS
    notes.append("no preferred assembly passes shear; strongest preferred option proposed")
    return best, NO_PASS


def _chord(base: ChordSpec, lumber, size, n: int) -> ChordSpec:
    return dataclasses.replace(base, n_posts=n, post_nominal=size.nominal, species_group=lumber.species_group,
                               grade=lumber.grade, size_class=lumber.size_class, layout="example",
                               post_thickness_in=size.thickness_in, chord_length_ft=None, d_arm_ft=None)


def _size_posts(cases, lib, prefs, i, notes):
    base = _first(cases).stories[i - 1].chord
    sizes = {s.nominal: s for s in lib.lumber_sizes}
    winners, strongest = [], None
    for lumber in prefs.lumber_options(lib):
        for nominal in prefs.post_size_options(lib):
            if not size_fits(lumber.size_class, nominal):
                continue
            for n in range(prefs.min_posts, prefs.max_posts + 1):
                trial = _trial(cases, i, chord=_chord(base, lumber, sizes[nominal], n))
                cs = _evaluate_all(trial, lib, i, check_compression)
                if cs is None:
                    break  # this lumber/size cannot be evaluated (data missing or chord too long)
                cap = min(c.capacity for c in cs)
                if strongest is None or cap > strongest[0]:
                    strongest = (cap, trial)
                if all(_passes(c) for c in cs):
                    winners.append((cap, n, trial))
                    break
    if winners:
        return min(winners, key=lambda w: (w[0], w[1]))[2], OK
    if strongest is None:
        notes.append("no preferred lumber and post size could be evaluated (missing data); posts kept")
        return cases, NEEDS
    notes.append("no preferred post option passes compression; strongest preferred option proposed")
    return strongest[1], NO_PASS


def _size_tiedown(cases, lib, prefs, i, notes):
    s = _first(cases).stories[i - 1]
    td = s.tiedown
    if isinstance(td, RodSystem):
        options = [(r.rod_allowable_tension_lb, dataclasses.replace(td, system_id=r.system_id))
                   for r in prefs.rod_options(lib) if r.rod_allowable_tension_lb is not None]
        check, what = check_rod, "rod"
    else:
        col = "allowable_tension_DF_SP_lb" if s.chord.species_group in ("Douglas Fir-Larch", "Southern Pine") \
            else "allowable_tension_SPF_HF_lb"
        options = [(getattr(h, col), GenericHoldDown(model=h.model, delta_a_in=td.delta_a_in))
                   for h in prefs.holddown_options(lib, s.chord.species_group) if getattr(h, col) is not None]
        check, what = check_holddown, "hold-down"
    best = None
    for _, tiedown in options:
        trial = _trial(cases, i, tiedown=tiedown)
        cs = _evaluate_all(trial, lib, i, check)
        if cs is None:
            continue
        best = trial
        if all(_passes(c) for c in cs):
            return trial, OK
    if best is None:
        notes.append(f"no preferred {what} has an allowable tension; tie-down kept")
        return cases, NEEDS
    notes.append(f"no preferred {what} passes tension; strongest preferred option proposed")
    return best, NO_PASS


# --------------------------------------------------------------------------
# public entry point
# --------------------------------------------------------------------------

def _describe(s: StoryInput) -> dict[str, str]:
    c, t = s.chord, s.tiedown
    tie = t.system_id if isinstance(t, RodSystem) else (t.model or f"T_allow {t.T_allow_lb:g} lb")
    layout = "layout rule" if c.layout == "example" else f"L_c {c.chord_length_ft:g} ft"
    return {"Nailing": f"{s.assembly_id} × {s.sides} side(s), {s.panel_type}",
            "Posts": f"({c.n_posts}) {c.post_nominal} {c.species_group} {c.grade}, {layout}",
            "Tie-down": tie}


_CATS = (("shear", "shear"), ("comp", "compression"), ("rod", "rod"), ("holddown", "holddown"),
         ("drift", "drift"))


def _dcrs(results: dict, i: int) -> dict:
    """Per check category, the largest DCR over the load cases (None if a case needs input)."""
    out = {}
    for suffix, cat in _CATS:
        vals = []
        for res in results.values():
            try:
                c = res.check(f"S{i}.{suffix}")
            except KeyError:
                continue
            vals.append(c.dcr if c.status in (CheckStatus.PASS, CheckStatus.FAIL) else None)
        if vals:
            out[cat] = None if any(v is None for v in vals) else max(vals)
    return out


def autosize(inp: DesignInputs, lib: ComponentLibrary, prefs: MaterialPreferences) -> AutosizeResult:
    """Auto-size one load case."""
    return autosize_cases({inp.load_type: inp}, lib, prefs)


def autosize_cases(cases: dict, lib: ComponentLibrary, prefs: MaterialPreferences) -> AutosizeResult:
    """Auto-size a wall checked for several load cases with the same structure (e.g. seismic and wind)."""
    before = {k: run_design(v, lib) for k, v in cases.items()}
    cur = dict(cases)
    first = _first(cases)
    statuses, all_notes = [], []
    for i in range(1, len(first.stories) + 1):
        notes: list[str] = []
        worst = OK
        for step in (_size_nailing, _size_posts, _size_tiedown):
            cur, st = step(cur, lib, prefs, i, notes)
            if st == NO_PASS or (st == NEEDS and worst == OK):
                worst = st
        statuses.append(worst)
        all_notes.append(notes)
    result = {k: run_design(v, lib) for k, v in cur.items()}
    stories = []
    for i, (st, notes) in enumerate(zip(statuses, all_notes), start=1):
        old, new = _describe(first.stories[i - 1]), _describe(_first(cur).stories[i - 1])
        changes = tuple(Change(k, old[k], new[k]) for k in old if old[k] != new[k])
        drift = _dcrs(result, i).get("drift")
        if drift is not None and drift > 1.0:
            notes.append(f"story drift DCR {drift:.2f} > 1.0: drift is not auto-sized; adjust by hand")
        for case, res in result.items():
            try:
                dc = res.check(f"S{i}.drift")
            except KeyError:
                continue
            if dc.status is CheckStatus.NEEDS_INPUT:
                notes.append(f"{case} drift needs input with the proposed selection: {dc.message}")
        stories.append(StoryProposal(i, changes, _dcrs(before, i), _dcrs(result, i), st, tuple(notes)))
    return AutosizeResult(cur, tuple(stories), before, result)
