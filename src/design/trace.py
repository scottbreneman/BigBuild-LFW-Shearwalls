"""Calc-trace contract shared by the engine, the UI and the report.

Every check returns a ``CheckResult`` holding the list of ``Step`` objects
that produced it (docs/spec-io.md §2). The screen and the report read the
same steps, so what the engineer sees is what the report prints.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

SourceStatus = Literal["statics", "verified", "memory", "assumption"]

# Higher number = less trust; used to report the weakest source behind a check.
_TRUST_RANK = {"statics": 0, "verified": 0, "assumption": 1, "memory": 2}


class CheckStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    NEEDS_INPUT = "needs_input"  # an engineer decision or component data is missing
    INFO = "info"  # reported value with no pass/fail criterion
    NOT_APPLICABLE = "not_applicable"


class NeedsEngineerInput(Exception):
    """A provision or data value is not settled; the check cannot run.

    ``decision`` names the spec-io decision (``"D3"``) or the missing data,
    so the screen can show it beside the check.
    """

    def __init__(self, decision: str, message: str):
        super().__init__(f"{decision}: {message}")
        self.decision = decision
        self.message = message


@dataclass(frozen=True)
class Step:
    id: str  # "S2.shear.v"
    name: str  # "Unit shear demand"
    symbol: str  # "v"
    equation_latex: str  # "v = 0.7 V / b"
    substitution: str  # "v = 0.7 (18,526 lb) / 29.0 ft"
    value: float | str
    unit: str  # "plf"
    citation: str  # "SDPWS-2021 §4.1.4.1" or "statics"
    status: SourceStatus
    note: str = ""


@dataclass(frozen=True)
class CheckResult:
    id: str  # "S2.shear"
    name: str  # "Shear in story 2"
    story: int
    category: str  # shear | aspect | compression | holddown | rod | plate_bearing | plate_bending | drift | detailing
    status: CheckStatus
    demand: float | None = None
    capacity: float | None = None
    dcr: float | None = None
    demand_unit: str = ""
    capacity_unit: str = ""
    message: str = ""
    decision: str = ""  # set when status is NEEDS_INPUT
    steps: tuple[Step, ...] = field(default_factory=tuple)

    @property
    def passed(self) -> bool:
        return self.status is CheckStatus.PASS

    @property
    def worst_source(self) -> SourceStatus | None:
        if not self.steps:
            return None
        return max(self.steps, key=lambda s: _TRUST_RANK[s.status]).status


def fmt(x: float, nd: int = 1) -> str:
    """Number formatting for substitution strings: thousands separators, fixed decimals."""
    return f"{x:,.{nd}f}"


class Tracer:
    """Collects steps while a check runs; ``step`` returns the value so code reads like the hand calc."""

    def __init__(self, prefix: str):
        self.prefix = prefix
        self.steps: list[Step] = []

    def step(
        self,
        key: str,
        name: str,
        symbol: str,
        equation: str,
        substitution: str,
        value,
        unit: str,
        citation: str,
        status: SourceStatus,
        note: str = "",
    ):
        self.steps.append(
            Step(f"{self.prefix}.{key}", name, symbol, equation, substitution, value, unit, citation, status, note)
        )
        return value

    def extend(self, steps) -> None:
        self.steps.extend(steps)

    def result(self, check_id: str, name: str, story: int, category: str, *, demand, capacity,
               demand_unit: str, capacity_unit: str = "", message: str = "") -> CheckResult:
        """Build a PASS/FAIL result from demand and capacity (DCR = demand / capacity)."""
        dcr = demand / capacity if capacity else float("inf")
        status = CheckStatus.PASS if dcr <= 1.0 else CheckStatus.FAIL
        return CheckResult(
            id=check_id, name=name, story=story, category=category, status=status,
            demand=demand, capacity=capacity, dcr=dcr, demand_unit=demand_unit,
            capacity_unit=capacity_unit or demand_unit, message=message, steps=tuple(self.steps),
        )
