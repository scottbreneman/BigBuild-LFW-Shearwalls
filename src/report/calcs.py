"""Equations with their code references (once per check) and the step-by-step calculations (every story)."""

from __future__ import annotations

import re

from design.result import DesignResult
from design.trace import CheckResult, CheckStatus, Step

from .model import Paragraph, Section, StepTable, Subheading, story_order
from .numfmt import dcr, with_unit
from .steps import is_combo, is_statics, local_id

_CATEGORY_TITLE = {
    "detailing": "Framing detailing: 3x framing requirement",
    "shear": "Sheathing shear: unit shear, nominal and allowable capacity",
    "aspect": "Wall aspect ratio",
    "compression": "Chord compression: post capacity and demand",
    "holddown": "Hold-down tension",
    "rod": "Tie-down rod tension",
    "plate_bearing": "Bearing plate: wood bearing capacity",
    "plate_bending": "Bearing plate: steel bending capacity",
    "drift": "Story drift",
}
CHECK_STATUS_LABEL = {  # the app's words for a check result (src/ui/app.py)
    CheckStatus.PASS: "pass", CheckStatus.FAIL: "FAIL", CheckStatus.NEEDS_INPUT: "needs input",
    CheckStatus.INFO: "info", CheckStatus.NOT_APPLICABLE: "n/a",
}


CATEGORY_ORDER = tuple(_CATEGORY_TITLE)  # display order: detailing first, then capacity checks, drift last

_STORY_SUFFIX = re.compile(r",\s*story\s*\d+\s*$", re.IGNORECASE)


def check_name(check: CheckResult) -> str:
    """Check name without its story suffix; the story is already a column or heading."""
    return _STORY_SUFFIX.sub("", check.name)


def ordered_checks(checks) -> list[CheckResult]:
    """Checks in report order within a story."""
    rank = {c: i for i, c in enumerate(CATEGORY_ORDER)}
    return sorted(checks, key=lambda c: rank.get(c.category, len(rank)))


def _check_steps(check: CheckResult) -> list[Step]:
    """A check's own steps: the statics and combination steps it reuses are shown in the statics section."""
    return [s for s in check.steps if not is_statics(s) and not is_combo(s)]


def build_equations(result: DesignResult) -> Section:
    """One table per check type: each equation with the code section and equation number it cites."""
    blocks: list = [Paragraph(
        "Each equation is listed once with the references recorded in the calculation. The code reference is the "
        "SDPWS, NDS, ASCE 7 or AISC section, equation or table the step cites; the example reference is the "
        "WoodWorks five-story example. Where the cited code section has no equation or table number recorded, or no "
        "code reference is recorded at all, the entry is flagged so an engineer can supply it. The report only prints "
        "what the calculation recorded; it does not add references of its own.")]

    by_category: dict[str, dict[str, Step]] = {}
    for story in story_order(len(result.stories)):
        for check in ordered_checks(result.stories[story - 1].checks):
            table = by_category.setdefault(check.category, {})
            for step in _check_steps(check):
                table.setdefault(local_id(step.id), step)

    for category, title in _CATEGORY_TITLE.items():
        steps = by_category.get(category)
        if steps:
            blocks.append(Subheading(title))
            blocks.append(StepTable(tuple(steps.values()), mode="catalog"))
    return Section("equations", "Equations and code references", tuple(blocks))


def build_calculations(result: DesignResult) -> Section:
    """Every check of every story, with demand, capacity, DCR and the substituted calculation."""
    blocks: list = [Paragraph(
        "Each check lists its steps in order: the equation, the values substituted into it, the result, the "
        "reference and the source status. Shear, overturning and chord tension are in the statics section and are "
        "referred to here by symbol.")]
    for story in story_order(len(result.stories)):
        blocks.append(Subheading(f"Story {story}"))
        shown: set[str] = set()
        for check in ordered_checks(result.stories[story - 1].checks):
            blocks.append(Paragraph(_check_line(check)))
            steps = [s for s in _check_steps(check) if s.id not in shown]
            shown.update(s.id for s in steps)
            if steps:
                blocks.append(StepTable(tuple(steps)))
    return Section("calculations", "Step-by-step calculations", tuple(blocks))


def _check_line(check: CheckResult) -> str:
    head = f"{check_name(check)} ({check.id}): {CHECK_STATUS_LABEL[check.status]}"
    if check.status is CheckStatus.NEEDS_INPUT:
        return f"{head}. Decision {check.decision}: {check.message}" if check.decision else f"{head}. {check.message}"
    if check.dcr is not None:
        return (f"{head}. Demand {with_unit(check.demand, check.demand_unit)}, capacity "
                f"{with_unit(check.capacity, check.capacity_unit)}, DCR = {dcr(check.dcr)}.")
    return f"{head}. {check.message}".rstrip()

