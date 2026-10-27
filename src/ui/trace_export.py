"""Interim Markdown / JSON export of a DesignResult.

The report builder (docs/spec-io.md section 6) owns the real report; this keeps the calc trace downloadable
from the UI until that module is merged.
"""

from __future__ import annotations

import json

from design.result import DesignResult

DISCLAIMER = "Prototype output. Needs review by a licensed engineer before any project use."


def _num(v) -> str:
    return f"{v:,.3f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)


def result_to_markdown(res: DesignResult) -> str:
    inp = res.inputs
    L = [f"# Shear wall stack calculation: {inp.project_name or 'untitled'}", "",
         f"_{DISCLAIMER}_", "",
         f"- Load type: **{res.load_type}**   - Editions: {', '.join(res.editions)}",
         f"- Git commit: `{res.git_commit or 'unknown'}`",
         f"- Overall: **{res.status.value}**" +
         (f" (governing: {res.governing_check}, DCR {res.max_dcr:.3f})" if res.max_dcr is not None else ""), ""]
    if res.input_errors:
        L += ["## Input errors", *[f"- `{e.field}`: {e.message}" for e in res.input_errors], ""]
    L += ["## Summary by story", "", "| Story | Status | Governing check | Max DCR |", "|---|---|---|---|"]
    for s in res.stories:
        L.append(f"| {s.story} | {s.status.value} | {s.governing_id or '-'} | "
                 f"{'-' if s.max_dcr is None else f'{s.max_dcr:.3f}'} |")
    L += ["", "## Needs engineer input", *([f"- {n.check_id} ({n.decision}): {n.message}" for n in res.needs_input]
                                         or ["- none"]), ""]

    def steps_table(steps):
        rows = ["| Step | Symbol | Equation | Substitution | Value | Citation | Status |", "|---|---|---|---|---|---|---|"]
        for st in steps:
            rows.append(f"| {st.id} | {st.symbol} | `{st.equation_latex}` | {st.substitution} | "
                        f"{_num(st.value)} {st.unit} | {st.citation} | {st.status} |")
        return rows

    if res.stack_steps:
        L += ["## Stack: load combinations, story forces, chord forces", "", *steps_table(res.stack_steps), ""]
    for s in res.stories:
        L += [f"## Story {s.story}", ""]
        for c in s.checks:
            dcr = "" if c.dcr is None else f", DCR {c.dcr:.3f}"
            L += [f"### {c.name} ({c.id}): {c.status.value}{dcr}", ""]
            if c.message:
                L += [f"> {c.message}", ""]
            if c.steps:
                L += [*steps_table(c.steps), ""]
    L += ["## Items to verify", "",
          f"- Calculation steps whose source is not verified: {len(res.unverified_steps)}",
          *[f"- Component data: {x}" for x in res.component_items_to_verify], ""]
    return "\n".join(L)


def result_to_json(res: DesignResult) -> str:
    return json.dumps(res.to_dict(), indent=2, default=str)
