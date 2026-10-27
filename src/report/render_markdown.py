"""Render a report ``Document`` as Markdown (same content as the HTML report).

Equations are written as ``$...$`` LaTeX, which GitHub and most Markdown viewers typeset.
"""

from __future__ import annotations

from design.trace import Step

from .model import Document, Figure, Paragraph, StepTable, Subheading, Table
from .refs import reference_text
from .steps import result_text, tex_for


def render_markdown(doc: Document) -> str:
    lines = [f"# {doc.title}", "", f"> **{doc.banner}**", ""]
    for section in doc.sections:
        lines += [f"## {section.title}", ""]
        for block in section.blocks:
            lines += _block(block)
    return "\n".join(lines).rstrip() + "\n"


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _block(block) -> list[str]:
    if isinstance(block, Paragraph):
        return [block.text, ""]
    if isinstance(block, Subheading):
        return [f"### {block.text}", ""]
    if isinstance(block, Figure):
        return [f"*{block.caption}*" if block.caption else "", f"*{block.markdown_note}*", ""]
    if isinstance(block, StepTable):
        return _step_table(block)
    return _table(block)


def _table(t: Table) -> list[str]:
    lines: list[str] = []
    if t.caption:
        lines += [f"*{t.caption}*", ""]
    lines.append("| " + " | ".join(_cell(h) for h in t.headers) + " |")
    lines.append("| " + " | ".join("---:" if j in t.align_right else "---" for j in range(len(t.headers))) + " |")
    for row in t.rows:
        lines.append("| " + " | ".join(_cell(c) for c in row) + " |")
    lines.append("")
    return lines


def _equation(step: Step) -> str:
    if not step.equation_latex:
        return ""
    return "$" + tex_for(step).replace("|", "\\vert ") + "$"


def _step_table(t: StepTable) -> list[str]:
    lines: list[str] = []
    if t.caption:
        lines += [f"*{t.caption}*", ""]
    if t.mode == "catalog":
        heads = ("Step", "Equation", "Reference", "Source status")
    else:
        heads = ("Step", "Equation", "Substitution", "Result", "Reference", "Source status")
    lines.append("| " + " | ".join(heads) + " |")
    lines.append("| " + " | ".join("---" for _ in heads) + " |")
    for s in t.steps:
        name = f"{s.name} ({s.symbol})" if s.symbol else s.name
        if t.mode == "catalog":
            cells = (name, _equation(s), reference_text(s), s.status)
        else:
            cells = (name, _equation(s), s.substitution, result_text(s), reference_text(s), s.status)
        lines.append("| " + " | ".join(_cell(c) for c in cells) + " |")
    lines.append("")
    return lines
