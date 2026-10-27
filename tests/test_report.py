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
from report.model import Table
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
    expected = [("-" if c.dcr is None else f"{c.dcr:.2f}") for c in result.checks()]
    assert rendered == expected


def test_inputs_are_shown_as_entered(html):
    assert "29" in html and "1.206" in html  # b and S_DS
    assert "0.03125" in html  # slack of 1/32 in is not rounded to 0.031
    assert "EX-OSB-15/32-10dc-4" in html
    assert "EX-F1554-36-1-1/8" in html


def test_counts_use_the_engines_unverified_list(result, md):
    memory = sum(1 for s in result.unverified_steps if s.status == "memory")
    assumed = sum(1 for s in result.unverified_steps if s.status == "assumption")
    assert f"{memory} from memory" in md
    assert f"{assumed} resting on a team assumption" in md


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


def test_html_is_escaped_and_self_contained(result):
    hostile = dataclasses.replace(result, inputs=dataclasses.replace(
        result.inputs, project_name="<script>alert(1)</script> & Co"))
    page = build_report(hostile, DAY)
    assert "<script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt; &amp; Co" in page
    assert not re.search(r'(src|href)\s*=\s*"https?://', page)  # no external assets
    assert "<link" not in page


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
