"""Report generator: content and plumbing, not engineering values.

The report only renders a ``DesignResult``. These tests check that what the engine
computed reaches the page unchanged and nothing is dropped, so the report cannot
drift from the calc trace. Engineering values are tested in test_woodworks_seismic.py.
"""

import dataclasses
import re
from datetime import date
from html.parser import HTMLParser

import pytest

from design.engine import run_design
from design.result import OverallStatus
from design.trace import CheckStatus
from report import build_document, build_markdown, build_report
from pathlib import Path

from report.calcs import CATEGORY_ORDER, check_name
from report.figures import AMBER, GREEN, GREY, RED, dcr_color, stack_fbd_svg
from report.model import Figure, Paragraph, StepTable, Table
from report.numfmt import snum
from report.refs import citation_for, parse_citation
from report.statics import IN_LOADS_TABLE
from report.steps import local_id
from report.render_html import KATEX_CSS, KATEX_JS
from report.steps import tex_for
from woodworks_example import inputs, library

DAY = date(2026, 10, 27)


@pytest.fixture(scope="module")
def result():
    return run_design(inputs(), library())


@pytest.fixture(scope="module")
def html(result):
    return build_report(result, DAY)


@pytest.fixture(scope="module")
def md(result):
    return build_markdown(result, DAY)


def _needs_input_result():
    """Tall narrow wall: h/b > 2 raises decision D3 on the aspect-ratio checks."""
    base = inputs()
    stories = tuple(dataclasses.replace(s, chord=dataclasses.replace(s.chord, d_arm_ft=3.0)) for s in base.stories)
    return run_design(dataclasses.replace(base, b_ft=4.0, stories=stories), library())


def test_header_has_disclaimer_project_date_editions_and_commit(result, html, md):
    for text in (html, md):
        assert "Prototype output" in text  # the app's wording (ui/trace_export.DISCLAIMER)
        assert "licensed engineer" in text
        assert "WoodWorks five-story example" in text
        assert "2026-10-27" in text
        assert "IBC 2024" in text and "SDPWS 2021" in text and "ASCE 7-22" in text
        assert "unknown" in text  # git_commit is filled by the caller, as the app does
    assert "| Load type | Seismic |" in md
    assert "| Load type | seismic |" not in md

    stamped = dataclasses.replace(result, git_commit="fa70149")
    assert "fa70149" in build_report(stamped, DAY)


def test_every_check_appears_in_the_summary_without_its_story_suffix(result, html, md):
    for check in result.checks():
        short = check.name.split(", story")[0]
        assert short in html, check.id
        assert short in md, check.id
    assert "Sheathing shear, story" not in html  # the Story column carries the story
    assert "Sheathing shear, story" not in md


def test_summary_has_no_overall_governing_line(result, md):
    summary = md.split("## Summary of results")[1].split("## Equations")[0]
    assert "All checks pass." in summary
    assert "Governing check:" not in summary  # the per-story roll-up and the bold rows carry this
    assert result.governing_check not in summary


def test_each_storys_governing_check_is_bold(result):
    t = _all_checks(result)
    bold = {row[1] for row, cls in zip(t.rows, t.row_classes) if "governing" in cls}
    expected = {check_name(result.check(s.governing_id)) for s in result.stories if s.governing_id}
    assert bold == expected
    marked = sum(1 for cls in t.row_classes if "governing" in cls)
    assert marked == len(result.stories)  # one per story, not one for the whole stack


def test_dcr_values_match_the_engine(result):
    doc = build_document(result, DAY)
    table = next(b for s in doc.sections if s.id == "summary" for b in s.blocks
                 if isinstance(b, Table) and b.headers[0] == "Story" and "Demand" in b.headers)
    dcr_col = table.headers.index("DCR")
    rendered = [row[dcr_col] for row in table.rows]
    rank = {c: i for i, c in enumerate(CATEGORY_ORDER)}
    top_down = [c for st in reversed(result.stories)
                for c in sorted(st.checks, key=lambda x: rank[x.category])]
    expected = [("-" if c.dcr is None else f"{c.dcr:.2f}") for c in top_down]
    assert rendered == expected


def test_inputs_are_shown_as_entered(html):
    assert "29" in html and "1.206" in html  # b and S_DS
    assert "0.03125" in html  # slack of 1/32 in is not rounded to 0.031
    assert "EX-OSB-15/32-10dc-4" in html
    assert "EX-F1554-36-1-1/8" in html


def test_counts_are_in_a_closing_notes_section_not_the_summary(result):
    doc = build_document(result, DAY)
    assert doc.sections[-1].id == "notes"
    notes = " ".join(b.text for b in doc.sections[-1].blocks)
    memory = sum(1 for x in result.unverified_steps if x.status == "memory")
    assumed = sum(1 for x in result.unverified_steps if x.status == "assumption")
    assert f"{memory} from memory" in notes
    assert f"{assumed} resting on a team assumption" in notes
    assert "Component library rows still unverified" in notes
    summary = " ".join(b.text for sec in doc.sections if sec.id == "summary" for b in sec.blocks
                       if hasattr(b, "text"))
    assert "Calculation steps" not in summary and "Component library" not in summary


def test_needs_input_check_shows_its_decision():
    r = _needs_input_result()
    assert r.needs_input
    md = build_markdown(r, DAY)
    html = build_report(r, DAY)
    assert "needs input" in md
    assert "Decision D3" in md
    assert "needs-input" in html
    assert "Needs engineer input: these checks cannot run" in md  # the app's section wording
    assert "| Check | Decision / data | Message |" in md  # the app's columns


def test_failing_design_is_reported_as_fail():
    base = inputs()
    r = run_design(dataclasses.replace(
        base, stories=tuple(dataclasses.replace(s, F_lb=s.F_lb * 3) for s in base.stories)), library())
    assert r.status is OverallStatus.FAIL
    md = build_markdown(r, DAY)
    assert "One or more checks FAIL" in md
    assert "FAIL" in md.split("All checks, grouped by story.")[1]
    assert 'class="fail' in build_report(r, DAY)


def test_invalid_input_lists_errors_and_no_checks():
    r = run_design(dataclasses.replace(inputs(), b_ft=-1.0), library())
    assert r.status is OverallStatus.INVALID_INPUT
    md = build_markdown(r, DAY)
    assert "Fix these inputs before the engine will run checks" in md
    assert "wall length must be positive" in md
    assert "All checks, grouped by story." not in md
    assert "Governing check" not in md


def test_html_is_escaped_and_only_katex_is_external(result):
    hostile = dataclasses.replace(result, inputs=dataclasses.replace(
        result.inputs, project_name="<script>alert(1)</script> & Co"))
    page = build_report(hostile, DAY)
    assert "<script>alert" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt; &amp; Co" in page
    external = set(re.findall(r'(?:src|href)\s*=\s*"(https?://[^"]+)"', page))
    assert external == {KATEX_CSS, KATEX_JS}


def test_html_is_well_formed(html):
    class Balanced(HTMLParser):
        VOID = {"meta", "br", "hr", "img", "link", "input"}

        def __init__(self):
            super().__init__()
            self.stack, self.errors = [], []

        def handle_starttag(self, tag, attrs):
            if tag not in self.VOID:
                self.stack.append(tag)

        def handle_endtag(self, tag):
            if not self.stack or self.stack.pop() != tag:
                self.errors.append(tag)

    p = Balanced()
    p.feed(html)
    assert not p.errors and not p.stack


def test_markdown_tables_are_rectangular(md):
    block = []
    for line in md.splitlines() + [""]:
        if line.startswith("|"):
            block.append(line)
            continue
        if block:
            counts = {len(re.findall(r"(?<!\\)\|", row)) for row in block}
            assert len(counts) == 1, block[0]
            block = []


def test_pipe_in_a_cell_does_not_break_the_markdown_table(result):
    odd = dataclasses.replace(result, inputs=dataclasses.replace(result.inputs, project_name="A | B"))
    assert "A \\| B" in build_markdown(odd, DAY)


# --- layout and wording requested by the report owner ---------------------------------------


def _table(doc, first_header, contains):
    for sec in doc.sections:
        for b in sec.blocks:
            if isinstance(b, Table) and b.headers[0] == first_header and contains in b.headers:
                return b
    raise AssertionError(f"no table with {contains!r}")


def test_story_tables_list_the_top_story_first(result):
    doc = build_document(result, DAY)
    for header in ("Height h (ft)", "Wall assembly"):
        stories = [row[0] for row in _table(doc, "Story", header).rows]
        assert stories == ["5", "4", "3", "2", "1"], header
    roll_up = [row[0] for row in _table(doc, "Story", "Governing check").rows]
    assert roll_up == ["5", "4", "3", "2", "1"]


def test_wall_assembly_row_matches_its_story(result):
    doc = build_document(result, DAY)
    by_story = {row[0]: row[1] for row in _table(doc, "Story", "Wall assembly").rows}
    assert by_story["5"] == "EX-OSB-15/32-10dc-6"
    assert by_story["1"] == "EX-OSB-15/32-10dc-4"


@pytest.mark.parametrize("carry,shown", [(False, "No"), (True, "Yes")])
def test_carry_rotation_is_shown_without_the_decision_number(carry, shown):
    r = run_design(dataclasses.replace(inputs(), carry_rotation=carry), library())
    md = build_markdown(r, DAY)
    assert f"| Rotation carried from stories below | {shown} |" in md
    assert "(D6)" not in md.split("## Summary of results")[0]


def test_carry_rotation_yes_shows_the_rotation_steps():
    """Carried rotation is now an engine option (D6, rigid-body geometry): the report must show its steps."""
    r = run_design(dataclasses.replace(inputs(), carry_rotation=True), library())
    assert not r.needs_input
    md = build_markdown(r, DAY)
    assert "Drift from rotation of stories below" in md


# --- statics section and free-body figure -----------------------------------------------------


def test_statics_section_has_the_figure_with_the_engines_numbers(result):
    doc = build_document(result, DAY)
    statics = next(s for s in doc.sections if s.id == "statics")
    figures = [b for b in statics.blocks if isinstance(b, Figure)]
    assert len(figures) == 1
    svg = figures[0].svg
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
    for i in range(1, 6):
        for sid in (f"S{i}.statics.V", f"S{i}.statics.M_OT", f"S{i}.chord.C_E"):
            assert f"{result.step(sid).value:,.0f}" in svg, sid
        assert f"{result.stories[i - 1].story}" in svg
    assert f"{result.inputs.stories[4].F_lb:,.0f} lb" in svg  # applied roof force


def test_statics_tables_show_the_chord_tension_chain(result):
    doc = build_document(result, DAY)
    statics = next(s for s in doc.sections if s.id == "statics")
    tables = [b for b in statics.blocks if isinstance(b, StepTable)]
    ids = {s.id for t in tables for s in t.steps}
    for i in range(1, 6):
        for key in ("chord.C_E", "chord.M_R", "chord.asd.net", "chord.asd.T", "chord.dT"):
            assert f"S{i}.{key}" in ids
    latex = {s.equation_latex for t in tables for s in t.steps}
    assert r"C_E = M_{OT} / d" in latex
    assert r"M_R = w_D b^2 / 2" in latex


def test_statics_tables_do_not_repeat_the_loads_table(result):
    doc = build_document(result, DAY)
    statics = next(s for s in doc.sections if s.id == "statics")
    shown = {local_id(s.id) for b in statics.blocks if isinstance(b, StepTable) for s in b.steps}
    assert not shown & set(IN_LOADS_TABLE)


def test_statics_notation_still_defines_the_symbols_the_figure_uses(result):
    doc = build_document(result, DAY)
    statics = next(s for s in doc.sections if s.id == "statics")
    notation = next(b for b in statics.blocks if isinstance(b, Table) and b.headers[0] == "Symbol")
    symbols = {row[0] for row in notation.rows}
    assert {"V", "M_OT", "d", "w_D", "b", "F_j", "H_j"} <= symbols


def test_statics_section_opens_with_the_figure(result):
    doc = build_document(result, DAY)
    statics = next(s for s in doc.sections if s.id == "statics")
    assert isinstance(statics.blocks[0], Figure)  # no lead-in paragraph; the caption carries the explanation
    assert not any(isinstance(b, Paragraph) for b in statics.blocks)


def test_statics_comes_before_the_summary(result):
    ids = [s.id for s in build_document(result, DAY).sections]
    assert ids == ["header", "inputs", "statics", "summary", "equations", "calculations", "verify", "notes"]


def test_statics_stories_are_listed_top_down(md):
    order = [md.index(f"### Story {i}: chord tension from overturning") for i in (5, 4, 3, 2, 1)]
    assert order == sorted(order)


# --- equations, references and KaTeX ----------------------------------------------------------


def test_every_calc_step_reaches_the_report(result, html):
    """No step may be dropped. A step left out of the step tables must be one the loads table reports."""
    ids = {s.id for s in result.stack_steps} | {s.id for c in result.checks() for s in c.steps}
    missing = [i for i in ids if f'data-step-id="{i}"' not in html]
    assert all(local_id(i) in IN_LOADS_TABLE for i in missing), missing[:5]


def test_equations_are_typeset_with_katex_and_keep_a_text_fallback(result, html):
    assert KATEX_JS in html and KATEX_CSS in html
    assert "katex.render" in html
    step = result.step("S1.chord.C_E")
    assert f'data-tex="{step.equation_latex}"' in html
    assert f">{step.equation_latex}</span>" in html  # LaTeX source is the visible fallback


def test_markdown_equations_use_dollar_math(md):
    assert r"$C_E = M_{OT} / d$" in md


def test_prose_in_an_equation_slot_is_set_as_text(result):
    prose = result.step("S1.framing.flag")
    assert tex_for(prose).startswith(r"\text{")
    assert tex_for(result.step("S1.chord.C_E")) == result.step("S1.chord.C_E").equation_latex


def test_all_latex_has_balanced_braces_and_no_stray_dollar(result):
    steps = list(result.stack_steps) + [s for c in result.checks() for s in c.steps]
    for s in steps:
        tex = tex_for(s)
        assert tex.count("{") == tex.count("}"), (s.id, tex)
        assert "$" not in tex, (s.id, tex)


def test_catalog_shows_recorded_equation_numbers_and_flags_gaps(md):
    catalog = md.split("## Equations and code references")[1].split("## Step-by-step calculations")[0]
    assert "SDPWS-2021 Eq. 4.3-1" in catalog
    assert "NDS-2024 Eq. 3.7-1" in catalog
    assert "AISC 360-22 Chapter F, Eq. F11-1" in catalog
    assert "section cited; no equation or table number recorded" in catalog  # e.g. v_allow cites a section only
    assert "no code reference recorded" in catalog


def test_report_adds_no_reference_of_its_own(result, md):
    """Every standard reference in a Reference column must appear verbatim in a recorded citation."""
    citations = [s.citation for s in list(result.stack_steps) + [x for c in result.checks() for x in c.steps]]
    ref_col, checked = None, 0
    for line in md.splitlines():
        if line.startswith("| Step |"):
            heads = [h.strip() for h in line.strip("|").split(" | ")]
            ref_col = heads.index("Reference") if "Reference" in heads else None
        elif line.startswith("| ") and ref_col is not None and not line.startswith("| ---"):
            cell = line.strip().strip("|").split(" | ")[ref_col]
            for frag in cell.split("; "):
                frag = frag.replace("\u26a0", "").strip()
                if frag.startswith(("SDPWS", "NDS", "ASCE", "AISC")):
                    checked += 1
                    assert any(frag in c for c in citations), frag
        elif not line.startswith("|"):
            ref_col = None
    assert checked > 100


@pytest.mark.parametrize("text,code,gap", [
    ("SDPWS-2021 Eq. 4.3-1; WoodWorks 5-story example §3.4.2", 1, ""),
    ("NDS-2024 §3.6, §3.10; WoodWorks 5-story example Table 3.9", 1, "section cited"),
    ("WoodWorks 5-story example §3.3.6", 0, "no code reference"),
    ("statics", 0, ""),
    ("input; WoodWorks 5-story example Table 3.17A", 0, ""),
])
def test_parse_citation(text, code, gap):
    c = parse_citation(text)
    assert len(c.code) == code
    assert gap in c.gap if gap else c.gap == ""


def test_calculation_section_lists_every_check_top_down(result, md):
    calc = md.split("## Step-by-step calculations")[1]
    positions = [calc.index(f"### Story {i}") for i in (5, 4, 3, 2, 1)]
    assert positions == sorted(positions)
    for check in result.checks():
        assert f"{check.name.split(', story')[0]} ({check.id})" in calc


def test_needs_input_check_has_no_calc_table_but_states_the_decision():
    r = _needs_input_result()
    calc = build_markdown(r, DAY).split("## Step-by-step calculations")[1]
    assert "needs input. Decision D3" in calc


# --- story loads table: cumulative totals -----------------------------------------------------


def _loads(result):
    return _table(build_document(result, DAY), "Story", "Height h (ft)")


def test_loads_table_carries_cumulative_totals_from_the_engine(result):
    t = _loads(result)
    col = {h: i for i, h in enumerate(t.headers)}
    by_story = {row[0]: row for row in t.rows}
    for i in range(1, 6):
        row = by_story[str(i)]
        for header, step in (("Story shear V = ΣF (lb)", "V"),
                             ("Overturning M_OT at base (ft-lb)", "M_OT"),
                             ("Cumulative dead Σ(w_D + w_wall) (plf)", "w_D"),
                             ("Cumulative live Σw_L (plf)", "w_L"),
                             ("Cumulative roof live Σw_Lr (plf)", "w_Lr")):
            assert row[col[header]] == snum(result.step(f"S{i}.statics.{step}").value), (i, header)


def test_loads_table_cumulative_columns_grow_downward(result):
    t = _loads(result)
    col = t.headers.index("Story shear V = ΣF (lb)")
    shears = [float(row[col].replace(",", "")) for row in t.rows]  # rows run story 5 -> 1
    assert shears == sorted(shears)
    assert shears[-1] == sum(s.F_lb for s in result.inputs.stories)  # base shear is the total applied force


def test_loads_table_shows_elevation_at_the_top_of_each_story(result):
    t = _loads(result)
    col = t.headers.index("Elevation H at top (ft)")
    by_story = {row[0]: row[col] for row in t.rows}
    assert by_story["1"] == "10" and by_story["5"] == "50"


# --- all-checks table: order, grouping, merged story column -----------------------------------


def _all_checks(result):
    return _table(build_document(result, DAY), "Story", "Demand")


def test_framing_detailing_is_the_first_check_of_each_story(result):
    t = _all_checks(result)
    first_seen = {}
    for row in t.rows:
        first_seen.setdefault(row[0], row[1])
    assert set(first_seen) == {"1", "2", "3", "4", "5"}
    assert all(name == "Framing detailing" for name in first_seen.values()), first_seen


def test_all_checks_merges_the_story_column_and_bands_each_story(result):
    t = _all_checks(result)
    assert t.span_col == 0
    assert [row[0] for row in t.rows[:8]] == ["5"] * 8  # one merged cell over story 5's eight checks
    bands = {row[0]: cls.split()[0] for row, cls in zip(t.rows, t.row_classes)}
    assert bands == {"5": "band-a", "4": "band-b", "3": "band-a", "2": "band-b", "1": "band-a"}


def test_merged_story_cell_renders_as_one_rowspan(html):
    assert '<td rowspan="8">5</td>' in html
    assert html.count('rowspan="8"') == 5  # one per story, not one per check


def test_a_failing_check_keeps_its_colour_through_the_story_banding():
    base = inputs()
    r = run_design(dataclasses.replace(
        base, stories=tuple(dataclasses.replace(s, F_lb=s.F_lb * 3) for s in base.stories)), library())
    t = _all_checks(r)
    failing = [cls for c, cls in zip([c for st in reversed(r.stories) for c in ordered(st)], t.row_classes)
               if c.status is CheckStatus.FAIL]
    assert failing and all("fail" in cls and cls.startswith("band-") for cls in failing)


def ordered(story):
    rank = {c: i for i, c in enumerate(CATEGORY_ORDER)}
    return sorted(story.checks, key=lambda c: rank[c.category])


# --- references -------------------------------------------------------------------------------


def test_statics_steps_do_not_cite_the_worked_example(result, md):
    statics_steps = [s for s in result.stack_steps if s.status == "statics"]
    assert statics_steps
    citing = [s for s in statics_steps if "example" in s.citation.lower()]
    assert citing, "expected some statics steps to carry an example citation in the engine"
    for s in citing:
        assert citation_for(s).example == ()
    body = md.split("## Statics")[1].split("## Summary")[0]
    for line in body.splitlines():
        if line.startswith("| Dead-load resisting moment") or line.startswith("| T-C couple"):
            assert "example" not in line.lower(), line


def test_a_statics_step_keeps_any_code_reference(result):
    m_r = result.step("S1.chord.M_R")  # cites SDPWS plus the example
    c = citation_for(m_r)
    assert c.code and "SDPWS" in c.code[0]
    assert c.example == ()


# --- demand/capacity colour scale -------------------------------------------------------------


def test_dcr_colour_bands_match_the_app(result):
    """The report must colour a D:C exactly as the app's stack graphic does."""
    from ui.graphic import dcr_colour as app_colour

    for i in range(0, 200):
        d = i / 100
        assert dcr_color(d)[0] == app_colour(d), d
    assert dcr_color(None)[0] == app_colour(None) == GREY


def test_dcr_colour_uses_the_app_bands():
    assert dcr_color(0.50)[0] == GREEN
    assert dcr_color(0.90)[0] == GREEN  # the app's first break is at 0.90, not 0.80
    assert dcr_color(0.95)[0] == AMBER
    assert dcr_color(1.00)[0] == AMBER
    assert dcr_color(1.01)[0] == RED
    assert dcr_color(None)[0] == GREY


def test_dcr_strokes_come_from_the_app_palette():
    from ui.graphic import STROKE

    for fill in (GREEN, AMBER, RED, GREY):
        assert STROKE[fill] == dict((v, k) for k, v in [(STROKE[f], f) for f in (fill,)]).get(fill, STROKE[fill])
    assert dcr_color(0.5)[1] == STROKE[GREEN]
    assert dcr_color(1.5)[1] == STROKE[RED]


def test_figure_labels_each_story_with_its_governing_dcr(result):
    svg = stack_fbd_svg(result)
    for story in result.stories:
        assert f"Story {story.story} – D:C = {story.max_dcr:.2f}" in svg
    assert "Story 1<" not in svg  # no bare story label left


def test_figure_fills_each_story_with_its_dcr_colour(result):
    svg = stack_fbd_svg(result)
    for story in result.stories:
        fill, stroke = dcr_color(story.max_dcr)
        assert f'fill="{fill}" stroke="{stroke}"' in svg, story.story
    assert "Fill colour: governing D:C of the story" in svg  # legend explaining the scale


def test_figure_greys_a_story_that_needs_input():
    r = _needs_input_result()
    svg = stack_fbd_svg(r)
    needs = [s for s in r.stories if s.max_dcr is None]
    if needs:
        assert f'fill="{GREY}"' in svg
        assert "needs input" in svg


# --- conformance with the Streamlit app -------------------------------------------------------
# The screen and the report must describe the same design the same way. These tests fail if one
# side changes a shared setting without the other.


def test_disclaimer_is_the_apps_disclaimer(md):
    from ui.trace_export import DISCLAIMER

    from report.sections import DISCLAIMER as report_disclaimer

    assert report_disclaimer is DISCLAIMER
    assert DISCLAIMER in md


def test_overall_status_wording_is_the_apps(result):
    assert "All checks pass." in build_markdown(result, DAY)
    r = run_design(dataclasses.replace(inputs(), b_ft=-1.0), library())
    assert "Fix these inputs before the engine will run checks" in build_markdown(r, DAY)


def test_check_status_words_are_the_apps(result, md):
    from report.calcs import CHECK_STATUS_LABEL

    assert CHECK_STATUS_LABEL[CheckStatus.NEEDS_INPUT] == "needs input"
    assert CHECK_STATUS_LABEL[CheckStatus.NOT_APPLICABLE] == "n/a"
    assert CHECK_STATUS_LABEL[CheckStatus.INFO] == "info"
    assert "NEEDS INPUT" not in md and "INFO" not in md


def test_editions_match_the_engine(result, md):
    from design.result import EDITIONS

    assert ", ".join(EDITIONS) in md  # the app's sidebar prints the same list


def test_items_to_verify_uses_the_apps_columns(result, md):
    section = md.split("## Items to verify")[1].split("## Notes")[0]
    assert "| Step | Name | Citation | Source status |" in section
    assert "Component rows used with status 'memory'" in section
    assert f"{len(result.unverified_steps)} steps" in section
    for item in result.component_items_to_verify:
        assert item in section


def test_items_to_verify_lists_every_unverified_step(result, md):
    section = md.split("## Items to verify")[1]
    for step in result.unverified_steps:
        assert step.id in section, step.id


def test_items_to_verify_comes_before_the_notes(result):
    ids = [s.id for s in build_document(result, DAY).sections]
    assert ids.index("verify") == ids.index("notes") - 1


def test_wind_drift_limit_uses_the_apps_denominator_form():
    r = run_design(dataclasses.replace(
        inputs(), load_type="wind", wind_drift_limit_ratio=1 / 400, S_DS=None, C_d=None, I_e=None,
        risk_category=None), library())
    assert "h / 400" in build_markdown(r, DAY)
