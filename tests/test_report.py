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
from report import build_document, build_markdown, build_report
from report.model import Figure, StepTable, Table
from report.refs import parse_citation
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
        assert "NOT FOR CONSTRUCTION" in text
        assert "licensed engineer" in text
        assert "WoodWorks five-story example" in text
        assert "2026-10-27" in text
        assert "IBC 2024" in text and "SDPWS 2021" in text and "ASCE 7-22" in text
        assert "not recorded" in text  # git_commit is filled by the caller
    assert "| Load type | Seismic |" in md
    assert "| Load type | seismic |" not in md

    stamped = dataclasses.replace(result, git_commit="fa70149")
    assert "fa70149" in build_report(stamped, DAY)


def test_every_check_appears_in_the_summary(result, html, md):
    for check in result.checks():
        assert check.name in html, check.id
        assert check.name in md, check.id


def test_summary_names_the_governing_check_and_dcr(result, html, md):
    name = result.check(result.governing_check).name
    assert name in html and result.governing_check in html
    assert f"DCR = {result.max_dcr:.2f}" in md
    assert 'class="pass governing"' in html  # governing row is marked


def test_dcr_values_match_the_engine(result):
    doc = build_document(result, DAY)
    table = next(b for s in doc.sections if s.id == "summary" for b in s.blocks
                 if isinstance(b, Table) and b.headers[0] == "Story" and "Demand" in b.headers)
    dcr_col = table.headers.index("DCR")
    rendered = [row[dcr_col] for row in table.rows]
    top_down = [c for st in reversed(result.stories) for c in st.checks]
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
    assert "NEEDS INPUT" in md
    assert "Decision D3" in md
    assert 'class="needs-input"' in html
    assert "could not run until an engineer settles" in md


def test_failing_design_is_reported_as_fail():
    base = inputs()
    r = run_design(dataclasses.replace(
        base, stories=tuple(dataclasses.replace(s, F_lb=s.F_lb * 3) for s in base.stories)), library())
    assert r.status is OverallStatus.FAIL
    md = build_markdown(r, DAY)
    assert "Overall result: FAIL" in md
    assert "FAIL" in md.split("All checks.")[1]
    assert 'class="fail' in build_report(r, DAY)


def test_invalid_input_lists_errors_and_no_checks():
    r = run_design(dataclasses.replace(inputs(), b_ft=-1.0), library())
    assert r.status is OverallStatus.INVALID_INPUT
    md = build_markdown(r, DAY)
    assert "INVALID INPUT" in md
    assert "wall length must be positive" in md
    assert "All checks." not in md
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


def test_carry_rotation_yes_makes_drift_need_input():
    """The engine has no carried-rotation method yet (decision D6): the report must say so, not hide it."""
    r = run_design(dataclasses.replace(inputs(), carry_rotation=True), library())
    md = build_markdown(r, DAY)
    assert "Decision D6" in md
    assert "NEEDS INPUT" in md


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


def test_statics_tables_show_shear_overturning_and_tension_equations(result):
    doc = build_document(result, DAY)
    statics = next(s for s in doc.sections if s.id == "statics")
    tables = [b for b in statics.blocks if isinstance(b, StepTable)]
    ids = {s.id for t in tables for s in t.steps}
    for i in range(1, 6):
        for key in ("statics.V", "statics.M_OT", "chord.C_E", "chord.M_R", "chord.asd.T"):
            assert f"S{i}.{key}" in ids
    latex = {s.equation_latex for t in tables for s in t.steps}
    assert r"V_i = \sum_{j \ge i} F_j" in latex
    assert r"M_{OT,i} = \sum_{j \ge i} F_j (H_j - H_{i-1})" in latex


def test_statics_stories_are_listed_top_down(md):
    order = [md.index(f"### Story {i}: shear, overturning and chord tension") for i in (5, 4, 3, 2, 1)]
    assert order == sorted(order)


# --- equations, references and KaTeX ----------------------------------------------------------


def test_every_calc_step_reaches_the_report(result, html):
    """No step may be dropped: the report prints every step the engine recorded."""
    ids = {s.id for s in result.stack_steps} | {s.id for c in result.checks() for s in c.steps}
    missing = [i for i in ids if f'data-step-id="{i}"' not in html]
    assert not missing, missing[:5]


def test_equations_are_typeset_with_katex_and_keep_a_text_fallback(result, html):
    assert KATEX_JS in html and KATEX_CSS in html
    assert "katex.render" in html
    step = result.step("S1.statics.M_OT")
    assert f'data-tex="{step.equation_latex}"' in html
    assert f">{step.equation_latex}</span>" in html  # LaTeX source is the visible fallback


def test_markdown_equations_use_dollar_math(md):
    assert r"$V_i = \sum_{j \ge i} F_j$" in md


def test_prose_in_an_equation_slot_is_set_as_text(result):
    prose = result.step("S1.framing.flag")
    assert tex_for(prose).startswith(r"\text{")
    assert tex_for(result.step("S1.statics.V")) == result.step("S1.statics.V").equation_latex


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
            ref_col = heads.index("Reference")
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
        assert f"{check.name} ({check.id})" in calc


def test_needs_input_check_has_no_calc_table_but_states_the_decision():
    r = _needs_input_result()
    calc = build_markdown(r, DAY).split("## Step-by-step calculations")[1]
    assert "NEEDS INPUT. Decision D3" in calc
