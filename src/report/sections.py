"""Build the report ``Document`` from a ``DesignResult`` (docs/spec-io.md §6).

Built so far: header, inputs (spec §6 items 1-2) and the DCR summary (item 5).
The assumptions/decisions, step-by-step calculations, stack graphic and
items-to-verify sections are added by later steps; they read the same
``DesignResult`` and slot into ``build_document`` in spec order.

Nothing here recomputes engineering values: every number comes from the
``DesignResult`` or its ``DesignInputs`` (docs/design-engine.md).
"""

from __future__ import annotations

from datetime import date

from design.inputs import GenericHoldDown, RodSystem, StoryInput
from design.result import DesignResult, OverallStatus
from design.trace import CheckResult, CheckStatus

from .model import Document, Paragraph, Section, Table

DISCLAIMER = (
    "PROTOTYPE - NOT FOR CONSTRUCTION. Results from this hackathon prototype have not been validated "
    "and need review by a licensed engineer before any project use."
)

_CHECK_STATUS_LABEL = {
    CheckStatus.PASS: "PASS",
    CheckStatus.FAIL: "FAIL",
    CheckStatus.NEEDS_INPUT: "NEEDS INPUT",
    CheckStatus.INFO: "INFO",
    CheckStatus.NOT_APPLICABLE: "N/A",
}
_CHECK_STATUS_CLASS = {
    CheckStatus.PASS: "pass",
    CheckStatus.FAIL: "fail",
    CheckStatus.NEEDS_INPUT: "needs-input",
    CheckStatus.INFO: "info",
    CheckStatus.NOT_APPLICABLE: "info",
}
_OVERALL_LABEL = {
    OverallStatus.PASS: "PASS",
    OverallStatus.FAIL: "FAIL",
    OverallStatus.INCOMPLETE: "INCOMPLETE (a check needs engineer input)",
    OverallStatus.INVALID_INPUT: "INVALID INPUT (no checks were run)",
}
_OVERALL_CLASS = {
    OverallStatus.PASS: "pass",
    OverallStatus.FAIL: "fail",
    OverallStatus.INCOMPLETE: "needs-input",
    OverallStatus.INVALID_INPUT: "fail",
}


def num(x: float | None) -> str:
    """Report number format: enough digits to read small ratios and large forces alike."""
    if x is None:
        return "-"
    if x == float("inf"):
        return "inf"
    a = abs(x)
    if a >= 1000:
        return f"{x:,.0f}"
    if a >= 10:
        return f"{x:,.1f}"
    return f"{x:,.3f}"


def inum(x: float) -> str:
    """Input value: shown as entered, with padding zeros dropped (10.0 -> 10, 1/32 -> 0.03125)."""
    return f"{x:,.5f}".rstrip("0").rstrip(".")


def _ratio(x: float) -> str:
    """A drift ratio such as 0.0025 shown as '1/400 (0.0025)'."""
    return f"1/{1 / x:,.0f} ({x:.4f})" if x > 0 else str(x)


def _with_unit(x: float | None, unit: str) -> str:
    return "-" if x is None else f"{num(x)} {unit}".rstrip()


def _dcr(x: float | None) -> str:
    if x is None:
        return "-"
    return "inf" if x == float("inf") else f"{x:.2f}"


def build_document(result: DesignResult, generated: date | None = None) -> Document:
    """Assemble the report content. ``generated`` defaults to today's date."""
    generated = generated or date.today()
    inp = result.inputs
    name = inp.project_name.strip()
    title = f"Wood shear wall design report - {name}" if name else "Wood shear wall design report"
    sections = [
        _header(result, generated),
        _inputs(result),
        _summary(result),
    ]
    return Document(title=title, banner=DISCLAIMER, sections=tuple(sections))


# --- 1. header ---------------------------------------------------------------


def _header(result: DesignResult, generated: date) -> Section:
    rows = (
        ("Project", result.inputs.project_name.strip() or "(not named)"),
        ("Report date", generated.isoformat()),
        ("Load type", result.load_type),
        ("Load level", "ASD (allowable stress design)"),
        ("Editions", ", ".join(result.editions)),
        ("App git commit", result.git_commit or "not recorded"),
    )
    return Section("header", "Report information", (Table(("Item", "Value"), rows),))


# --- 2. inputs ---------------------------------------------------------------


def _inputs(result: DesignResult) -> Section:
    inp = result.inputs
    general: list[tuple[str, str, str]] = [("Load type", inp.load_type, "")]
    general.append(("Wall length, b", inum(inp.b_ft), "ft"))
    optional = (
        ("Design spectral acceleration, S_DS", inp.S_DS, inum, ""),
        ("Deflection amplification factor, C_d", inp.C_d, inum, ""),
        ("Seismic importance factor, I_e", inp.I_e, inum, ""),
        ("Risk category", inp.risk_category, str, ""),
        ("Seismic design category", inp.sdc, str, ""),
        ("End post width for default lever arm, d_post", inp.d_post_in, inum, "in"),
        ("Wind drift limit, story drift / story height", inp.wind_drift_limit_ratio, _ratio, ""),
    )
    for label, value, fmt_value, unit in optional:
        if value is not None:  # only inputs the user supplied; seismic and wind need different sets
            general.append((label, fmt_value(value), unit))
    general.append(("Net roof uplift on wall (strength level)", inum(inp.roof_uplift_plf), "plf"))
    general.append(("Wood bearing amplification factor", inum(inp.wood_bearing_factor), ""))
    general.append(("Rotation carried from stories below (D6)", "yes" if inp.carry_rotation else "no", ""))

    loads = Table(
        ("Story", "Height h (ft)", "Story force F (lb)", "Dead w_D (plf)", "Wall w_wall (plf)",
         "Live w_L (plf)", "Roof live w_Lr (plf)"),
        tuple((str(i), inum(s.h_ft), inum(s.F_lb), inum(s.w_D_plf), inum(s.w_wall_plf), inum(s.w_L_plf),
               inum(s.w_Lr_plf)) for i, s in enumerate(inp.stories, start=1)),
        caption="Story heights and loads. Story 1 is the bottom wall. F is the strength-level force "
                "applied at the top of the story; w are line loads delivered at the top of the story.",
        align_right=(1, 2, 3, 4, 5, 6),
    )
    walls = Table(
        ("Story", "Wall assembly", "Sides", "Panel", "End posts", "Chord length (ft)", "Lever arm d (ft)",
         "Tie-down"),
        tuple((str(i), s.assembly_id, str(s.sides), s.panel_type, _posts(s), inum(s.chord.chord_length_ft),
               inum(s.chord.d_arm_ft) if s.chord.d_arm_ft is not None else "default (D2)", _tiedown(s))
              for i, s in enumerate(inp.stories, start=1)),
        caption="Wall assembly, end posts and tie-down by story.",
        align_right=(5, 6),
    )
    return Section("inputs", "Inputs", (
        Table(("Input", "Value", "Unit"), tuple(general), align_right=(1,)),
        loads,
        walls,
    ))


def _posts(s: StoryInput) -> str:
    c = s.chord
    return f"{c.n_posts} x {c.post_nominal}, {c.species_group} {c.grade}"


def _tiedown(s: StoryInput) -> str:
    t = s.tiedown
    if isinstance(t, RodSystem):
        return (f"Rod {t.system_id}; plate {inum(t.plate_width_in)} x {inum(t.plate_length_in)} x "
                f"{inum(t.plate_thickness_in)} in, Fy {t.plate_Fy_psi / 1000:g} ksi; slack "
                f"{inum(t.slack_in)} in, take-up {inum(t.takeup_elongation_in)} in")
    if isinstance(t, GenericHoldDown):
        if t.model:
            return f"Hold-down {t.model}"
        if t.T_allow_lb is not None:
            return f"Hold-down, T_allow = {inum(t.T_allow_lb)} lb"
        return "Hold-down (not specified)"
    return type(t).__name__


# --- 5. summary --------------------------------------------------------------


def _summary(result: DesignResult) -> Section:
    status = result.status
    blocks: list = [Paragraph(f"Overall result: {_OVERALL_LABEL[status]}.")]

    if status is OverallStatus.INVALID_INPUT:
        blocks.append(Paragraph("The inputs failed validation, so no checks were run. Fix these and run again."))
        blocks.append(Table(("Field", "Problem"), tuple((e.field, e.message) for e in result.input_errors)))
        return Section("summary", "Summary of results", tuple(blocks))

    if result.governing_check:
        blocks.append(Paragraph(
            f"Governing check: {result.check(result.governing_check).name} "
            f"({result.governing_check}), "
            f"DCR = {_dcr(result.max_dcr)} (demand / capacity; a value above 1.00 fails)."))
    n_steps = len({st.id for st in (*result.stack_steps, *(x for c in result.checks() for x in c.steps))})
    n_memory = sum(1 for s in result.unverified_steps if s.status == "memory")
    n_assumed = sum(1 for s in result.unverified_steps if s.status == "assumption")
    blocks.append(Paragraph(
        f"Calculation steps: {n_steps} total; {n_memory} from memory and not yet checked against the source, "
        f"{n_assumed} resting on a team assumption. Component library rows still unverified: "
        f"{len(result.component_items_to_verify)}."))
    if result.needs_input:
        blocks.append(Paragraph(
            f"{len(result.needs_input)} check(s) could not run until an engineer settles the decision named "
            "in the Note column."))

    blocks.append(Table(
        ("Story", "Governing check", "Max DCR", "Status"),
        tuple((str(s.story), _check_label(result, s.governing_id), _dcr(s.max_dcr), _OVERALL_LABEL[s.status].split(" (")[0])
              for s in result.stories),
        caption="Controlling check in each story.",
        row_classes=tuple(_OVERALL_CLASS[s.status] for s in result.stories),
        align_right=(2,),
    ))

    checks = result.checks()
    blocks.append(Table(
        ("Story", "Check", "Demand", "Capacity", "DCR", "Status", "Note"),
        tuple(_check_row(c) for c in checks),
        caption="All checks. DCR = demand / capacity. The governing check is marked.",
        row_classes=tuple(_row_class(c, result.governing_check) for c in checks),
        align_right=(2, 3, 4),
    ))
    return Section("summary", "Summary of results", tuple(blocks))


def _check_label(result: DesignResult, check_id: str | None) -> str:
    return f"{result.check(check_id).name} ({check_id})" if check_id else "-"


def _check_row(c: CheckResult) -> tuple[str, ...]:
    note = c.message
    if c.status is CheckStatus.NEEDS_INPUT and c.decision:
        note = f"Decision {c.decision}: {c.message}"
    return (
        str(c.story), c.name,
        _with_unit(c.demand, c.demand_unit), _with_unit(c.capacity, c.capacity_unit), _dcr(c.dcr),
        _CHECK_STATUS_LABEL[c.status], note,
    )


def _row_class(c: CheckResult, governing_id: str | None) -> str:
    cls = _CHECK_STATUS_CLASS[c.status]
    return f"{cls} governing" if c.id == governing_id else cls
