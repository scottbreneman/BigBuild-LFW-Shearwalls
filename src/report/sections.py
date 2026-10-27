"""Build the report ``Document`` from a ``DesignResult`` (docs/spec-io.md §6).

Section order: report information, inputs, summary of results, statics (free-body
figure, shear and overturning), equations with code references, step-by-step
calculations, and notes. Assumptions/decisions and the items-to-verify appendix
are added by later steps; they read the same ``DesignResult``.

Nothing here recomputes engineering values: every number comes from the
``DesignResult`` or its ``DesignInputs`` (docs/design-engine.md).
"""

from __future__ import annotations

from datetime import date

from design.inputs import GenericHoldDown, RodSystem, StoryInput
from design.result import DesignResult, OverallStatus
from design.trace import CheckResult, CheckStatus

from .calcs import CHECK_STATUS_LABEL as _CHECK_STATUS_LABEL
from .calcs import build_calculations, build_equations, check_name, ordered_checks
from .model import Document, Paragraph, Section, Subheading, Table, story_order
from .numfmt import dcr, inum, ratio, snum, with_unit
from .statics import build_statics

# Wording, status labels and the demand/capacity scale follow the Streamlit app, so the screen and
# the report say the same thing about the same design.
from ui.trace_export import DISCLAIMER  # noqa: E402

_CHECK_STATUS_CLASS = {
    CheckStatus.PASS: "pass",
    CheckStatus.FAIL: "fail",
    CheckStatus.NEEDS_INPUT: "needs-input",
    CheckStatus.INFO: "info",
    CheckStatus.NOT_APPLICABLE: "info",
}
_OVERALL_LABEL = {  # the app's result banners (src/ui/app.py)
    OverallStatus.PASS: "All checks pass",
    OverallStatus.FAIL: "One or more checks FAIL",
    OverallStatus.INCOMPLETE: "Incomplete: some checks need engineer input or component data",
    OverallStatus.INVALID_INPUT: "Fix these inputs before the engine will run checks",
}
_STORY_LABEL = {  # short form for the per-story roll-up
    OverallStatus.PASS: "pass", OverallStatus.FAIL: "FAIL",
    OverallStatus.INCOMPLETE: "incomplete", OverallStatus.INVALID_INPUT: "invalid input",
}
_OVERALL_CLASS = {
    OverallStatus.PASS: "pass",
    OverallStatus.FAIL: "fail",
    OverallStatus.INCOMPLETE: "needs-input",
    OverallStatus.INVALID_INPUT: "fail",
}


def build_document(result: DesignResult, generated: date | None = None) -> Document:
    """Assemble the report content. ``generated`` defaults to today's date."""
    generated = generated or date.today()
    name = result.inputs.project_name.strip()
    title = f"Wood shear wall design report - {name}" if name else "Wood shear wall design report"
    sections = [_header(result, generated), _inputs(result)]
    if result.status is OverallStatus.INVALID_INPUT:
        sections.append(_summary(result))
    else:
        sections += [build_statics(result), _summary(result), build_equations(result),
                     build_calculations(result), _items_to_verify(result), _notes(result)]
    return Document(title=title, banner=DISCLAIMER, sections=tuple(sections))


def _cap(text: str) -> str:
    """First letter capitalized: 'seismic' -> 'Seismic'."""
    return text[:1].upper() + text[1:]


# --- header ------------------------------------------------------------------


def _header(result: DesignResult, generated: date) -> Section:
    rows = (
        ("Project", result.inputs.project_name.strip() or "(not named)"),
        ("Report date", generated.isoformat()),
        ("Load type", _cap(result.load_type)),
        ("Load level", "ASD (allowable stress design)"),
        ("Editions", ", ".join(result.editions)),
        ("App git commit", result.git_commit or "unknown"),
    )
    return Section("header", "Report information", (Table(("Item", "Value"), rows),))


# --- inputs ------------------------------------------------------------------


def _inputs(result: DesignResult) -> Section:
    inp = result.inputs
    general: list[tuple[str, str, str]] = [("Load type", _cap(inp.load_type), ""),
                                           ("Wall length, b", inum(inp.b_ft), "ft")]
    optional = (
        ("Design spectral acceleration, S_DS", inp.S_DS, inum, ""),
        ("Deflection amplification factor, C_d", inp.C_d, inum, ""),
        ("Seismic importance factor, I_e", inp.I_e, inum, ""),
        ("Risk category", inp.risk_category, str, ""),
        ("Seismic design category", inp.sdc, str, ""),
        ("End post width for default lever arm, d_post", inp.d_post_in, inum, "in"),
        ("Wind drift limit, h / ___", inp.wind_drift_limit_ratio, ratio, ""),
    )
    for label, value, fmt_value, unit in optional:
        if value is not None:  # only inputs the user supplied; seismic and wind need different sets
            general.append((label, fmt_value(value), unit))
    general.append(("Net roof uplift on wall (strength level)", inum(inp.roof_uplift_plf), "plf"))
    general.append(("Wood bearing amplification factor", inum(inp.wood_bearing_factor), ""))
    general.append(("Rotation carried from stories below", "Yes" if inp.carry_rotation else "No", ""))

    order = story_order(len(inp.stories))
    loads = _loads_table(result, order)
    walls = Table(
        ("Story", "Wall assembly", "Sides", "Panel", "End posts", "Chord length (ft)", "Lever arm d (ft)",
         "Tie-down"),
        tuple((str(i), s.assembly_id, str(s.sides), s.panel_type, _posts(s), inum(s.chord.chord_length_ft),
               inum(s.chord.d_arm_ft) if s.chord.d_arm_ft is not None else "default (D2)", _tiedown(s))
              for i, s in ((i, inp.stories[i - 1]) for i in order)),
        caption="Wall assembly, end posts and tie-down by story.",
        align_right=(5, 6),
    )
    return Section("inputs", "Inputs", (
        Table(("Input", "Value", "Unit"), tuple(general), align_right=(1,)),
        loads,
        walls,
    ))


def _loads_table(result: DesignResult, order: list[int]) -> Table:
    """Story loads, each with the cumulative value at the base of that story.

    The cumulative columns are read from the statics steps, not recomputed here; the elevation H
    is the running sum of the input story heights.
    """
    inp = result.inputs
    elevation, running = {}, 0.0
    for i, st in enumerate(inp.stories, start=1):
        running += st.h_ft
        elevation[i] = running

    def cum(story: int, key: str) -> str:
        try:
            return snum(result.step(f"S{story}.statics.{key}").value)
        except KeyError:  # no statics steps (invalid input)
            return "-"

    headers = ("Story", "Height h (ft)", "Elevation H at top (ft)", "Story force F (lb)",
               "Story shear V = ΣF (lb)", "Overturning M_OT at base (ft-lb)", "Dead w_D (plf)",
               "Wall w_wall (plf)", "Cumulative dead Σ(w_D + w_wall) (plf)", "Live w_L (plf)",
               "Cumulative live Σw_L (plf)", "Roof live w_Lr (plf)", "Cumulative roof live Σw_Lr (plf)")
    rows = []
    for i in order:
        st = inp.stories[i - 1]
        rows.append((str(i), inum(st.h_ft), inum(elevation[i]), inum(st.F_lb), cum(i, "V"), cum(i, "M_OT"),
                     inum(st.w_D_plf), inum(st.w_wall_plf), cum(i, "w_D"), inum(st.w_L_plf), cum(i, "w_L"),
                     inum(st.w_Lr_plf), cum(i, "w_Lr")))
    return Table(
        headers, tuple(rows),
        caption="Story heights and loads, with the cumulative value at the base of each story. Story 1 is the "
                "bottom wall. F is the strength-level force applied at the top of the story; w are line loads "
                "delivered at the top of the story. The cumulative columns come from the statics calculation.",
        align_right=tuple(range(1, len(headers))),
    )


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


# --- summary -----------------------------------------------------------------


def _summary(result: DesignResult) -> Section:
    status = result.status
    blocks: list = [Paragraph(f"{_OVERALL_LABEL[status]}.")]

    if status is OverallStatus.INVALID_INPUT:
        blocks.append(Paragraph("No checks were run."))
        blocks.append(Table(("Field", "Problem"), tuple((e.field, e.message) for e in result.input_errors)))
        return Section("summary", "Summary of results", tuple(blocks))

    if result.needs_input:
        blocks.append(Paragraph("Needs engineer input: these checks cannot run until the decision or the "
                                "component data below is settled."))
        blocks.append(Table(
            ("Check", "Decision / data", "Message"),
            tuple((n.check_id, n.decision, n.message) for n in result.needs_input),
            row_classes=tuple("needs-input" for _ in result.needs_input),
        ))

    stories = [result.stories[i - 1] for i in story_order(len(result.stories))]
    blocks.append(Table(
        ("Story", "Governing check", "Max DCR", "Status"),
        tuple((str(s.story), _check_label(result, s.governing_id), dcr(s.max_dcr),
               _STORY_LABEL[s.status]) for s in stories),
        caption="Controlling check in each story.",
        row_classes=tuple(_OVERALL_CLASS[s.status] for s in stories),
        align_right=(2,),
    ))

    governing = {s.governing_id for s in stories if s.governing_id}  # the governing check of each story
    checks, bands = [], []
    for n, story in enumerate(stories):
        for c in ordered_checks(story.checks):
            checks.append(c)
            bands.append("band-a" if n % 2 == 0 else "band-b")
    blocks.append(Table(
        ("Story", "Check", "Demand", "Capacity", "DCR", "Status", "Note"),
        tuple(_check_row(c) for c in checks),
        caption="All checks, grouped by story. DCR = demand / capacity. The governing check of each story is "
                "in bold; a failing or incomplete check keeps its own colour through the story banding.",
        row_classes=tuple(f"{band} {_row_class(c, governing)}".strip()
                          for c, band in zip(checks, bands)),
        align_right=(2, 3, 4),
        span_col=0,
    ))
    return Section("summary", "Summary of results", tuple(blocks))


def _check_label(result: DesignResult, check_id: str | None) -> str:
    return check_name(result.check(check_id)) if check_id else "-"


def _check_row(c: CheckResult) -> tuple[str, ...]:
    note = c.message
    if c.status is CheckStatus.NEEDS_INPUT and c.decision:
        note = f"Decision {c.decision}: {c.message}"
    return (
        str(c.story), check_name(c),
        with_unit(c.demand, c.demand_unit), with_unit(c.capacity, c.capacity_unit), dcr(c.dcr),
        _CHECK_STATUS_LABEL[c.status], note,
    )


def _row_class(c: CheckResult, governing_ids: set[str]) -> str:
    cls = _CHECK_STATUS_CLASS[c.status] if c.status in (CheckStatus.FAIL, CheckStatus.NEEDS_INPUT) else ""
    return f"{cls} governing".strip() if c.id in governing_ids else cls


# --- items to verify ---------------------------------------------------------


def _items_to_verify(result: DesignResult) -> Section:
    """Every value an engineer still has to close out (docs/spec-io.md §6 item 7).

    Same content as the app's "Items to verify" tab: component rows used at status ``memory``,
    then the calculation steps whose source is not ``verified``.
    """
    blocks: list = [Paragraph(
        "Every value below carries a source status that is not 'verified'. An engineer reads the cited section, "
        "then either marks the value verified or corrects it. 'memory' was recalled and not yet checked against "
        "the source; 'assumption' is a team decision.")]

    blocks.append(Subheading("Component rows used with status 'memory'"))
    if result.component_items_to_verify:
        blocks.append(Table(("Component row",), tuple((x,) for x in result.component_items_to_verify)))
    else:
        blocks.append(Paragraph("None."))

    blocks.append(Subheading("Calculation steps not verified"))
    steps = result.unverified_steps
    if steps:
        by_status: dict[str, int] = {}
        for st in steps:
            by_status[st.status] = by_status.get(st.status, 0) + 1
        counts = ", ".join(f"{n} {k}" for k, n in sorted(by_status.items()))
        blocks.append(Paragraph(f"{len(steps)} steps: {counts}."))
        blocks.append(Table(
            ("Step", "Name", "Citation", "Source status"),
            tuple((st.id, st.name, st.citation, st.status) for st in steps),
        ))
    else:
        blocks.append(Paragraph("None."))
    return Section("verify", "Items to verify", tuple(blocks))


# --- notes -------------------------------------------------------------------


def _notes(result: DesignResult) -> Section:
    """Bookkeeping that does not bear on the design itself, kept at the very end."""
    ids = {s.id for s in (*result.stack_steps, *(x for c in result.checks() for x in c.steps))}
    n_memory = sum(1 for s in result.unverified_steps if s.status == "memory")
    n_assumed = sum(1 for s in result.unverified_steps if s.status == "assumption")
    return Section("notes", "Notes", (
        Paragraph(f"Calculation steps: {len(ids)} total; {n_memory} from memory and not yet checked against the "
                  f"source, {n_assumed} resting on a team assumption."),
        Paragraph(f"Component library rows still unverified: {len(result.component_items_to_verify)}."),
    ))
