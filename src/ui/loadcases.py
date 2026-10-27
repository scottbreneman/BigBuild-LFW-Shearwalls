"""Run the engine once per load case and combine the results (presentation-side envelope).

The engine designs one load type per run. Here the seismic and wind cases are run separately and, for every check,
the larger demand/capacity ratio is reported with the case that produced it. No design provisions are applied here.
If the calc builder prefers, this envelope can move into ``src/design/``.
"""

from __future__ import annotations

from dataclasses import dataclass

from design.engine import run_design
from design.inputs import DesignInputs
from design.result import DesignResult, OverallStatus
from design.trace import CheckResult, CheckStatus

LABEL = {"seismic": "Seismic", "wind": "Wind"}
SHORT = {"seismic": "S", "wind": "W"}
ORDER = ("seismic", "wind")  # ties go to seismic


@dataclass(frozen=True)
class CaseSet:
    inputs: dict[str, DesignInputs]
    results: dict[str, DesignResult]

    @property
    def cases(self) -> list[str]:
        return [c for c in ORDER if c in self.results]

    @property
    def valid(self) -> bool:
        return bool(self.results) and all(r.status is not OverallStatus.INVALID_INPUT for r in self.results.values())

    @property
    def primary(self) -> DesignInputs | None:
        """Inputs used for geometry (heights, wall length): the first active case."""
        c = self.cases
        return self.inputs[c[0]] if c else None

    def invalid(self) -> dict[str, tuple]:
        return {c: r.input_errors for c, r in self.results.items() if r.status is OverallStatus.INVALID_INPUT}

    @property
    def status(self) -> OverallStatus:
        sts = [r.status for r in self.results.values()]
        if not sts or OverallStatus.INVALID_INPUT in sts:
            return OverallStatus.INVALID_INPUT
        if OverallStatus.FAIL in sts:
            return OverallStatus.FAIL
        if OverallStatus.INCOMPLETE in sts:
            return OverallStatus.INCOMPLETE
        return OverallStatus.PASS

    # ---- story-level envelope
    def story_dcr(self, i: int) -> tuple[float | None, str | None]:
        best, case = None, None
        for c in self.cases:
            d = self.results[c].stories[i - 1].max_dcr
            if d is not None and (best is None or d > best):
                best, case = d, c
        return best, case

    def story_status(self, i: int) -> OverallStatus:
        sts = [self.results[c].stories[i - 1].status for c in self.cases]
        if OverallStatus.FAIL in sts:
            return OverallStatus.FAIL
        if OverallStatus.INCOMPLETE in sts:
            return OverallStatus.INCOMPLETE
        return OverallStatus.PASS

    def story_governing_check(self, i: int) -> str | None:
        _, case = self.story_dcr(i)
        return None if case is None else self.results[case].stories[i - 1].governing_id

    def overall(self) -> tuple[float | None, str | None, int | None, str | None]:
        """(max DCR, case, story, check id)."""
        best = (None, None, None, None)
        for c in self.cases:
            r = self.results[c]
            if r.max_dcr is not None and (best[0] is None or r.max_dcr > best[0]):
                best = (r.max_dcr, c, r.governing_story, r.governing_check)
        return best

    # ---- check-level envelope
    def check(self, i: int, categories: tuple[str, ...]) -> tuple[str | None, CheckResult | None]:
        """Worst rated check among ``categories`` over all cases, else a needs-input one, else None."""
        rated, needs = [], []
        for c in self.cases:
            for ck in self.results[c].stories[i - 1].checks:
                if ck.category not in categories:
                    continue
                if ck.status in (CheckStatus.PASS, CheckStatus.FAIL) and ck.dcr is not None:
                    rated.append((ck.dcr, -ORDER.index(c), c, ck))
                elif ck.status is CheckStatus.NEEDS_INPUT:
                    needs.append((c, ck))
        if rated:
            _, _, c, ck = max(rated, key=lambda t: (t[0], t[1]))
            return c, ck
        if needs:
            return needs[0]
        for c in self.cases:
            for ck in self.results[c].stories[i - 1].checks:
                if ck.category in categories:
                    return c, ck
        return None, None

    def both(self, i: int, categories: tuple[str, ...]) -> dict[str, float | None]:
        out = {}
        for c in self.cases:
            ds = [ck.dcr for ck in self.results[c].stories[i - 1].checks
                  if ck.category in categories and ck.status in (CheckStatus.PASS, CheckStatus.FAIL) and ck.dcr is not None]
            out[c] = max(ds) if ds else None
        return out

    def num(self, case: str, step_id: str):
        try:
            v = self.results[case].step(step_id).value
            return v if isinstance(v, (int, float)) else None
        except KeyError:
            return None


def run_cases(inputs: dict[str, DesignInputs], lib) -> CaseSet:
    return CaseSet(inputs=inputs, results={lt: run_design(inp, lib) for lt, inp in inputs.items()})
