"""Render a report ``Document`` as Markdown (same content as the HTML report)."""

from __future__ import annotations

from .model import Document, Paragraph, Table


def render_markdown(doc: Document) -> str:
    lines = [f"# {doc.title}", "", f"> **{doc.banner}**", ""]
    for section in doc.sections:
        lines += [f"## {section.title}", ""]
        for block in section.blocks:
            lines += _paragraph(block) if isinstance(block, Paragraph) else _table(block)
    return "\n".join(lines).rstrip() + "\n"


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _paragraph(p: Paragraph) -> list[str]:
    return [p.text, ""]


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
