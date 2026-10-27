"""Calculation report generator (docs/spec-io.md §6).

    from design.engine import run_design
    from report import build_report, build_markdown

    result = run_design(inputs)          # the report only renders this; it recomputes nothing
    html = build_report(result)          # one self-contained HTML file, prints to PDF from the browser
    md = build_markdown(result)          # same content as Markdown

Pass ``result`` after setting ``git_commit`` (``dataclasses.replace(result, git_commit=...)``)
so the header names the commit of the app that produced it.
"""

from __future__ import annotations

from datetime import date

from design.result import DesignResult

from .model import Document
from .render_html import render_html
from .render_markdown import render_markdown
from .sections import build_document

__all__ = ["build_document", "build_markdown", "build_report", "Document"]


def build_report(result: DesignResult, generated: date | None = None) -> str:
    """The report as a self-contained HTML string."""
    return render_html(build_document(result, generated))


def build_markdown(result: DesignResult, generated: date | None = None) -> str:
    """The report as Markdown."""
    return render_markdown(build_document(result, generated))
