"""Design result returned to the UI and the report (docs/spec-io.md §5)."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from enum import Enum

from .inputs import DesignInputs, InputError
from .trace import CheckResult, CheckStatus, Step

EDITIONS = ("IBC 2024", "SDPWS 2021", "NDS 2024", "ASCE 7-22", "AISC 360-22")


class OverallStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    INCOMPLETE = "incomplete"  # no failures, but at least one check needs engineer input
    INVALID_INPUT = "invalid_input"


@dataclass(frozen=True)
class StoryResult:
    story: int
    checks: tuple[CheckResult, ...]
    governing_id: str | None
    max_dcr: float | None
    status: OverallStatus


@dataclass(frozen=True)
class NeedsInputItem:
    check_id: str
    decision: str
    message: str


@dataclass(frozen=True)
class DesignResult:
    inputs: DesignInputs
    load_type: str
    editions: tuple[str, ...] = EDITIONS
    input_errors: tuple[InputError, ...] = ()
    stories: tuple[StoryResult, ...] = ()
    stack_steps: tuple[Step, ...] = ()
    governing_story: int | None = None
    governing_check: str | None = None
    max_dcr: float | None = None
    status: OverallStatus = OverallStatus.INVALID_INPUT
    needs_input: tuple[NeedsInputItem, ...] = ()
    unverified_steps: tuple[Step, ...] = ()
    component_items_to_verify: tuple[str, ...] = ()
    git_commit: str = ""  # filled by the caller

    def checks(self) -> list[CheckResult]:
        return [c for s in self.stories for c in s.checks]

    def check(self, check_id: str) -> CheckResult:
        for c in self.checks():
            if c.id == check_id:
                return c
        raise KeyError(check_id)

    def step(self, step_id: str) -> Step:
        for c in self.checks():
            for s in c.steps:
                if s.id == step_id:
                    return s
        for s in self.stack_steps:
            if s.id == step_id:
                return s
        raise KeyError(step_id)

    def to_dict(self) -> dict:
        """JSON-safe dict (enums become their values, tuples become lists)."""
        return _plain(dataclasses.asdict(self))


def _plain(x):
    if isinstance(x, Enum):
        return x.value
    if isinstance(x, dict):
        return {k: _plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_plain(v) for v in x]
    if isinstance(x, float) and x == float("inf"):
        return None
    return x


def summarize(checks: list[CheckResult]) -> tuple[str | None, float | None, OverallStatus]:
    rated = [c for c in checks if c.status in (CheckStatus.PASS, CheckStatus.FAIL) and c.dcr is not None]
    gov = max(rated, key=lambda c: c.dcr) if rated else None
    if any(c.status is CheckStatus.FAIL for c in checks):
        st = OverallStatus.FAIL
    elif any(c.status is CheckStatus.NEEDS_INPUT for c in checks):
        st = OverallStatus.INCOMPLETE
    else:
        st = OverallStatus.PASS
    return (gov.id if gov else None), (gov.dcr if gov else None), st
