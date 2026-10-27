"""Load-combination coefficients applied to unfactored stack effects.

Forms follow the WoodWorks five-story example (§3.3.1, §3.3.5, §3.3.6,
§3.4.1, §4.5), which cites ASCE 7-22. They are transcribed, not yet checked
by an engineer against ASCE 7-22, so they carry status ``memory``.
"""

from __future__ import annotations

from dataclasses import dataclass

from .inputs import DesignInputs
from .trace import Step, Tracer

EX = "WoodWorks 5-story example"


@dataclass(frozen=True)
class Combo:
    name: str
    D: float = 0.0  # dead
    E: float = 0.0  # lateral effect: E_h for seismic, W for wind
    L: float = 0.0
    Lr: float = 0.0


@dataclass(frozen=True)
class ComboSet:
    shear: Combo  # unit shear for the capacity check
    compression: tuple[Combo, ...]  # chord compression; the largest governs
    tension: Combo  # chord tension (dead load resisting)
    drift_shear: Combo | None  # drift-level shear and chord compression
    drift_tension: Combo | None
    steps: tuple[Step, ...]


def combos_for(inp: DesignInputs) -> ComboSet:
    t = Tracer("combo")
    if inp.load_type == "seismic":
        sds = inp.S_DS
        cit = f"ASCE 7-22 §2.4.5, §12.4.2.2 (E_v = 0.2 S_DS D); {EX} §3.3.1"
        t.step("shear", "ASD seismic factor on E_h", "c_E", "0.7 E_h", "0.7", 0.7, "", cit, "memory")
        d8 = t.step("comp8.D", "Dead-load factor, ASD combo 8", "λ_D8", "1.0 + 0.7(0.2 S_DS)",
                    f"1.0 + 0.7(0.2)({sds:.3f})", 1.0 + 0.14 * sds, "", f"{cit}; §3.3.5", "memory")
        d9 = t.step("comp9.D", "Dead-load factor, ASD combo 9", "λ_D9", "1.0 + 0.525(0.2 S_DS)",
                    f"1.0 + 0.525(0.2)({sds:.3f})", 1.0 + 0.105 * sds, "", cit, "memory",
                    note="combo 9 also carries 0.525 E_h + 0.75 L")
        d10 = t.step("tens.D", "Dead-load factor, ASD combo 10", "λ_D10", "0.6 − 0.7(0.2 S_DS)",
                     f"0.6 − 0.7(0.2)({sds:.3f})", 0.6 - 0.14 * sds, "", f"{cit}; §3.3.6", "memory")
        dd = t.step("drift.D", "Dead-load factor for drift tension", "λ_Dδ", "0.9 − 0.2 S_DS",
                    f"0.9 − 0.2({sds:.3f})", 0.9 - 0.2 * sds, "",
                    f"ASCE 7-22 §2.3.6 combo 7; {EX} §3.4.1", "assumption",
                    note="Example authors' choice in place of the §12.8.6.1 drift combination, "
                         "to maximize chord tension for drift")
        t.step("drift.E", "Drift-level factor on E_h", "c_Eδ", "1.0 E_h", "1.0", 1.0, "",
               f"ASCE 7-22 §12.8.6.1; {EX} §3.4.1", "memory")
        return ComboSet(
            shear=Combo("ASD 0.7E_h", E=0.7),
            compression=(Combo("ASD combo 8", D=d8, E=0.7), Combo("ASD combo 9", D=d9, E=0.525, L=0.75)),
            tension=Combo("ASD combo 10", D=d10, E=0.7),
            drift_shear=Combo("drift 1.0E_h", E=1.0),
            drift_tension=Combo("0.9D − E_v + E_h", D=dd, E=1.0),
            steps=tuple(t.steps),
        )

    cit = f"ASCE 7-22 §2.4.1; {EX} §4.5"
    t.step("shear", "ASD wind factor on W", "c_W", "0.6 W", "0.6", 0.6, "", cit, "memory")
    t.step("comp", "Wind compression combinations", "", "5a: 1.0D + 0.6W;  6a: 1.0D + 0.75L + 0.75(0.6W) + 0.75L_r",
           "", "5a, 6a", "", cit, "memory")
    t.step("tens", "Wind tension combination", "", "7a: 0.6D + 0.6W", "", "7a", "", cit, "memory")
    t.step("drift", "Wind drift load level", "", "v: 1.0W;  tension: 0.6D + 1.0W", "", "1.0W", "",
           f"spec-io D6 (owner decision); {EX} §4.6 adopts no wind drift criterion", "assumption",
           note="Checked against the user-supplied drift limit; ASCE 7-22 sets no mandatory wind drift limit")
    return ComboSet(
        shear=Combo("ASD 0.6W", E=0.6),
        compression=(Combo("ASD combo 5a", D=1.0, E=0.6), Combo("ASD combo 6a", D=1.0, E=0.45, L=0.75, Lr=0.75)),
        tension=Combo("ASD combo 7a", D=0.6, E=0.6),
        drift_shear=Combo("drift 1.0W", E=1.0),
        drift_tension=Combo("0.6D + 1.0W", D=0.6, E=1.0),
        steps=tuple(t.steps),
    )
