"""Chord (boundary element) forces for every story of the stack.

ASD tension and compression (example §3.3.5-3.3.6, Tables 3.6, 3.8, 3.10)
and drift-level forces (§3.4.1, Tables 3.13A-B). Differential tension per
floor needs the story above, so all stories are computed together.
"""

from __future__ import annotations

from dataclasses import dataclass

from analysis.stack import StoryForces

from .combos import ComboSet
from .inputs import DesignInputs
from .trace import Step, Tracer, fmt

EX = "WoodWorks 5-story example"


@dataclass(frozen=True)
class ChordForces:
    story: int
    d_ft: float
    C_E_lb: float  # strength-level T-C couple M_OT / d
    M_R_ftlb: float  # dead-load resisting moment w_D b^2 / 2
    T_lb: float  # ASD net chord tension (>= 0)
    dT_lb: float  # ASD differential tension delivered at this story's bearing plate
    C_lb: float  # ASD governing chord compression
    C_combo: str
    T_drift_lb: float | None
    dT_drift_lb: float | None
    C_drift_lb: float | None
    steps: tuple[Step, ...]


def _tension(t: Tracer, key: str, label: str, lam_D: float, c_E: float, M_R: float, M_OT: float, d: float,
             cit: str, status) -> float:
    net = t.step(f"{key}.net", f"Net resultant moment ({label})", "M_net",
                 r"M_{net} = \lambda_D M_R - c_E M_{OT}",
                 f"{lam_D:.3f}({fmt(M_R, 0)}) − {c_E:.3f}({fmt(M_OT, 0)})", lam_D * M_R - c_E * M_OT,
                 "ft-lb", cit, status)
    return t.step(f"{key}.T", f"Net chord tension ({label})", "T", r"T = \max(0, -M_{net} / d)",
                  f"max(0, {fmt(-net, 0)} / {fmt(d, 2)})", max(0.0, -net / d), "lb",
                  f"statics; {EX} §3.3.6", "statics")


def chord_forces(inp: DesignInputs, forces: list[StoryForces], combos: ComboSet) -> list[ChordForces]:
    b = inp.b_ft
    rows = []
    for sf in forces:
        s = inp.stories[sf.story - 1]
        t = Tracer(f"S{sf.story}.chord")
        d = sf.d_arm_ft
        C_E = t.step("C_E", "T-C couple from overturning (strength level)", "C_E", r"C_E = M_{OT} / d",
                     f"{fmt(sf.M_OT_ftlb, 0)} / {fmt(d, 2)}", sf.M_OT_ftlb / d, "lb",
                     f"statics; {EX} Table 3.6", "statics")
        M_R = t.step("M_R", "Dead-load resisting moment", "M_R", r"M_R = w_D b^2 / 2",
                     f"{fmt(sf.w_D_plf, 0)}({fmt(b, 2)})² / 2", sf.w_D_plf * b**2 / 2, "ft-lb",
                     f"statics; SDPWS-2021 §4.3.6.4.2; {EX} §3.3.6", "statics")
        tc = combos.tension
        T = _tension(t, "asd", tc.name, tc.D, tc.E, M_R, sf.M_OT_ftlb, d, f"{EX} Table 3.10", "memory")

        Lc = s.chord.chord_length_ft
        P_D = t.step("P_D", "Dead load tributary to chord", "P_D", r"P_D = w_D L_c",
                     f"{fmt(sf.w_D_plf, 0)}({fmt(Lc, 3)})", sf.w_D_plf * Lc, "lb", f"{EX} §3.3.5, Table 3.8",
                     "assumption", note="Chord length includes all posts and the rod gap (example Fig. 3.7)")
        P_L = sf.w_L_plf * Lc
        P_Lr = sf.w_Lr_plf * Lc
        best, best_name = -1.0, ""
        for c in combos.compression:
            val = c.D * P_D + c.E * C_E + c.L * P_L + c.Lr * P_Lr
            t.step(f"C.{c.name.split()[-1]}", f"Chord compression, {c.name}", "C",
                   r"C = \lambda_D P_D + c_E C_E + c_L P_L + c_{Lr} P_{Lr}",
                   f"{c.D:.3f}({fmt(P_D, 0)}) + {c.E:.3f}({fmt(C_E, 0)}) + {c.L:.2f}({fmt(P_L, 0)}) "
                   f"+ {c.Lr:.2f}({fmt(P_Lr, 0)})", val, "lb", f"{EX} §3.3.5, Table 3.8", "memory")
            if val > best:
                best, best_name = val, c.name

        T_d = C_d = None
        if combos.drift_tension is not None:
            dc = combos.drift_tension
            dcit = f"{EX} Table 3.13B" if inp.load_type == "seismic" else "spec-io D6 (wind drift)"
            T_d = _tension(t, "drift", dc.name, dc.D, dc.E, M_R, sf.M_OT_ftlb, d, dcit, "assumption")
            C_d = t.step("C_drift", "Chord compression for drift (lateral only)", "C_δ", r"C_\delta = 1.0 C_E",
                         f"1.0({fmt(C_E, 0)})", C_E, "lb", f"{EX} §3.4.1, Table 3.13A", "assumption",
                         note="Gravity precompression neglected, as in the example")
        rows.append([sf.story, d, C_E, M_R, T, best, best_name, T_d, C_d, t])

    out = []
    for k, (story, d, C_E, M_R, T, C, C_name, T_d, C_d, t) in enumerate(rows):
        above = rows[k + 1] if k + 1 < len(rows) else None
        T_up = above[4] if above else 0.0
        dT = t.step("dT", "Differential tension per floor (ASD)", "ΔT", r"\Delta T_i = \max(0, T_i - T_{i+1})",
                    f"max(0, {fmt(T, 0)} − {fmt(T_up, 0)})", max(0.0, T - T_up), "lb",
                    f"statics; {EX} Table 3.10", "statics")
        dT_d = None
        if T_d is not None:
            Td_up = above[7] if above else 0.0
            dT_d = t.step("dT_drift", "Differential tension per floor (drift)", "ΔT_δ",
                          r"\Delta T_{\delta,i} = \max(0, T_{\delta,i} - T_{\delta,i+1})",
                          f"max(0, {fmt(T_d, 0)} − {fmt(Td_up, 0)})", max(0.0, T_d - Td_up), "lb",
                          f"statics; {EX} Table 3.13B", "statics")
        out.append(ChordForces(story, d, C_E, M_R, T, dT, C, C_name, T_d, dT_d, C_d, tuple(t.steps)))
    return out
