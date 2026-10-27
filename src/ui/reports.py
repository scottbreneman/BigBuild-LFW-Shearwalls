"""Calculation reports for the UI: wraps ``src/report`` (the report builder) for one load case at a time.

The report package only renders a ``DesignResult``; it recomputes nothing. Because the engine runs one load type per
result, a report is produced per load case; "Governing" picks the case with the larger max DCR.
"""

from __future__ import annotations

import re

from report import build_markdown, build_report
from ui.loadcases import LABEL, CaseSet

GOV_AUTO = "Governing (auto)"


def choices(cs: CaseSet) -> list[str]:
    return [GOV_AUTO] + [LABEL[c] for c in cs.cases]


def pick_case(cs: CaseSet, choice: str) -> str:
    if choice != GOV_AUTO:
        for c in cs.cases:
            if LABEL[c] == choice:
                return c
    gov = cs.overall()[1]
    return gov or cs.cases[0]


def file_stem(cs: CaseSet, case: str) -> str:
    name = (cs.inputs[case].project_name or "shearwall").strip()
    return f"{re.sub(r'[^A-Za-z0-9]+', '_', name).strip('_') or 'shearwall'}_{case}"


def html_report(cs: CaseSet, case: str) -> str:
    return build_report(cs.results[case])


def markdown_report(cs: CaseSet, case: str) -> str:
    return build_markdown(cs.results[case])
