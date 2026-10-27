"""Split a step's citation into code references and example references, and flag gaps.

The report shows only what the calculation recorded. It never adds a section or
equation number of its own (AGENTS.md: do not invent provisions). Where a step
cites a code section but no equation or table number, the report says so, so an
engineer can supply the number in the check that produced the step.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

CODE_PREFIXES = ("SDPWS", "NDS", "ASCE", "AISC", "IBC")
_BASIS_PREFIXES = ("statics", "definition", "input", "spec-io", "manufacturer")

GAP_SECTION_ONLY = "section cited; no equation or table number recorded"
GAP_NO_CODE = "no code reference recorded"


def example_label(fragment: str) -> str:
    """'WoodWorks 5-story example §3.3' stays as is; a bare 'Table 3.6' gets an 'Example:' label."""
    return fragment if "example" in fragment.lower() or "woodworks" in fragment.lower() else f"Example: {fragment}"


@dataclass(frozen=True)
class Citation:
    code: tuple[str, ...]  # SDPWS / NDS / ASCE / AISC / IBC references, as recorded
    example: tuple[str, ...]  # WoodWorks example and other non-code references
    basis: tuple[str, ...]  # statics, definition, input
    gap: str = ""  # "" when nothing is missing


def _fragments(text: str) -> list[str]:
    """Split on ';' outside parentheses."""
    out, cur, depth = [], [], 0
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch == ";" and depth == 0:
            out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    out.append("".join(cur).strip())
    return [f for f in out if f]


def parse_citation(text: str) -> Citation:
    code, example, basis = [], [], []
    for frag in _fragments(text):
        low = frag.lower()
        if frag.startswith(CODE_PREFIXES):
            code.append(frag)
        elif low.startswith(_BASIS_PREFIXES):
            basis.append(frag)
        else:
            example.append(frag)
    gap = ""
    if code:
        if not any(re.search(r"\b(Eq\.|Table|Equation)", f) for f in code):
            gap = GAP_SECTION_ONLY
    elif not basis:
        gap = GAP_NO_CODE
    return Citation(tuple(code), tuple(example), tuple(basis), gap)


def reference_text(text: str) -> str:
    """One-line reference for Markdown: code references first, then the example, then any gap flag."""
    c = parse_citation(text)
    parts = list(c.code)
    parts += [example_label(e) for e in c.example]
    parts += [b.capitalize() if b == "statics" else b for b in c.basis]
    line = "; ".join(parts)
    return f"{line}; \u26a0 {c.gap}" if c.gap else line
