"""Chord compression posts: NDS column stability and bearing (example §3.3.5, Tables 3.8-3.9)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .. import factors as fx
from ..components.schema import LumberDesignValues, LumberSize
from ..inputs import ChordSpec
from ..library import cite, lookup, status, value
from ..trace import CheckResult, Tracer, fmt
from . import Context

EX = "WoodWorks 5-story example"


@dataclass(frozen=True)
class Posts:
    size: LumberSize
    values: LumberDesignValues
    n: int

    @property
    def area_in2(self) -> float:
        return self.n * self.size.area_in2


def chord_posts(ctx: Context, chord: ChordSpec) -> Posts:
    size = lookup(ctx.lib.lumber_size, chord.post_nominal)
    vals = lookup(ctx.lib.lumber_values, chord.species_group, chord.grade, chord.size_class)
    return Posts(size, vals, chord.n_posts)


def _size_factor_Fc(ctx: Context, chord: ChordSpec) -> fx.Factor:
    """C_F for F_c: the library's NDS Table 4A row when there is one, else the example's value in factors.py."""
    if ctx.lib.size_factors:
        try:
            rec = ctx.lib.size_factor(chord.grade, chord.post_nominal)
        except LookupError:
            rec = None
        if rec is not None:
            return fx.Factor(value(rec, "CF_Fc", f"{chord.grade} {chord.post_nominal}"), cite(rec), status(rec))
    return fx.size_factor_Fc(chord.species_group, chord.grade, chord.post_nominal)


def check_compression(ctx: Context, i: int) -> CheckResult:
    s, ch = ctx.story(i), ctx.ch(i)
    c = s.chord
    t = Tracer(f"S{i}.comp")
    p = chord_posts(ctx, c)
    vcit, vst = cite(p.values), status(p.values)
    scit, sst = cite(p.size), status(p.size)
    Fc = t.step("Fc", "Reference compression parallel to grain", "F_c", "table",
                f"{c.species_group} {c.grade}", value(p.values, "Fc_psi", "Fc"), "psi", vcit, vst)
    Fcp = t.step("Fc_perp", "Reference compression perpendicular to grain", "F_c⊥", "table", "",
                 value(p.values, "Fc_perp_psi", "Fc_perp"), "psi", vcit, vst)
    Emin = t.step("Emin", "Reference E_min", "E_min", "table", "", value(p.values, "Emin_psi", "Emin"), "psi",
                  vcit, vst)
    if c.d_out_of_plane_in is not None:
        d = t.step("d", "Post depth across wall", "d", "given", "", c.d_out_of_plane_in, "in", "input", "assumption")
    else:
        d = t.step("d", "Post depth across wall", "d", "d = dressed width", f"{c.post_nominal}: {p.size.width_in}",
                   p.size.width_in, "in", scit, sst,
                   note=f"In-plane axis braced by sheathing (l_2 = 0), out-of-plane governs; {EX} §3.3.5")
    lu = t.step("l_u", "Unbraced length", "l_1", r"l_1 = 12h - t_{top} - t_{bot}",
                f"12({fmt(s.h_ft, 2)}) − {c.top_plates_in} − {c.bottom_plate_in}",
                12 * s.h_ft - c.top_plates_in - c.bottom_plate_in, "in", f"{EX} §3.3.5", "assumption")
    le = t.step("l_e", "Effective length", "l_e", r"l_e = K_e l_1", f"{fx.K_e.value}({fmt(lu, 1)})",
                fx.K_e.value * lu, "in", fx.K_e.citation, fx.K_e.status)
    sl = t.step("le_d", "Slenderness ratio", "l_e/d", "l_e / d", f"{fmt(le, 1)} / {d}", le / d, "", "statics",
                "statics")
    CF = _size_factor_Fc(ctx, c)
    t.step("C_F", "Size factor for F_c", "C_F", "table", f"{c.grade} {c.post_nominal}", CF.value, "", CF.citation,
           CF.status)
    CD, CM, Ct, Ci = fx.C_D_LATERAL, fx.C_M, fx.C_t, fx.C_i
    for f, sym in ((CD, "C_D"), (CM, "C_M"), (Ct, "C_t"), (Ci, "C_i")):
        t.step(sym, f"Adjustment factor {sym}", sym, "", "", f.value, "", f.citation, f.status)
    Emin_p = t.step("Emin_p", "Adjusted E'_min", "E'_min", r"E'_{min} = E_{min} C_M C_t C_i",
                    f"{fmt(Emin, 0)}({CM.value})({Ct.value})({Ci.value})", Emin * CM.value * Ct.value * Ci.value,
                    "psi", "NDS-2024 Table 4.3.1", "memory")
    FcE = t.step("FcE", "Critical buckling design value", "F_cE", r"F_{cE} = 0.822 E'_{min} / (l_e/d)^2",
                 f"0.822({fmt(Emin_p, 0)}) / {sl:.1f}²", 0.822 * Emin_p / sl**2, "psi", "NDS-2024 §3.7.1", "memory")
    Fcs = t.step("Fc_star", "F_c* (all factors except C_P)", "F_c*", r"F_c^* = F_c C_D C_M C_t C_F C_i",
                 f"{fmt(Fc, 0)}({CD.value})({CM.value})({Ct.value})({CF.value})({Ci.value})",
                 Fc * CD.value * CM.value * Ct.value * CF.value * Ci.value, "psi", "NDS-2024 Table 4.3.1", "memory")
    cc = fx.C_SAWN.value
    r = FcE / Fcs
    a = (1 + r) / (2 * cc)
    CP = t.step("C_P", "Column stability factor", "C_P",
                r"C_P = \frac{1 + F_{cE}/F_c^*}{2c} - \sqrt{\left(\frac{1 + F_{cE}/F_c^*}{2c}\right)^2 - \frac{F_{cE}/F_c^*}{c}}",
                f"F_cE/F_c* = {r:.3f}, c = {cc}", a - math.sqrt(a * a - r / cc), "",
                f"NDS-2024 Eq. 3.7-1; {fx.C_SAWN.citation}", "memory")
    Fcp_ = t.step("Fc_p", "Adjusted compression parallel", "F'_c", r"F'_c = F_c^* C_P", f"{fmt(Fcs, 0)}({CP:.3f})",
                  Fcs * CP, "psi", "NDS-2024 Table 4.3.1", "memory")
    Fperp_ = t.step("Fcperp_p", "Adjusted compression perpendicular", "F'_c⊥", r"F'_{c\perp} = F_{c\perp} C_M C_t C_i",
                    f"{fmt(Fcp, 0)}({CM.value})({Ct.value})({Ci.value})", Fcp * CM.value * Ct.value * Ci.value, "psi",
                    "NDS-2024 Table 4.3.1", "memory", note=f"C_b not applied to post bearing, as in {EX} §3.3.5")
    A = t.step("A", "Total post area", "A", r"A = n A_{post}", f"{p.n}({p.size.area_in2:.2f})", p.area_in2, "in²",
               scit, sst)
    f_allow = min(Fcp_, Fperp_)
    P_allow = t.step("P_allow", "Allowable chord compression", "P_allow", r"P_{allow} = \min(F'_c, F'_{c\perp}) A",
                     f"min({fmt(Fcp_, 0)}, {fmt(Fperp_, 0)})({A:.2f})", f_allow * A, "lb",
                     f"NDS-2024 §3.6, §3.10; {EX} Table 3.9", "memory",
                     note="Posts act individually (no composite action), as in the example")
    t.extend(s for s in ch.steps if ".C." in s.id or s.id.endswith(("C_E", "P_D")))
    t.step("C", f"Governing chord compression ({ch.C_combo})", "C", "max over combinations", "", ch.C_lb, "lb",
           f"{EX} Table 3.8", "memory")
    return t.result(f"S{i}.comp", f"Chord compression, story {i}", i, "compression",
                    demand=ch.C_lb, capacity=P_allow, demand_unit="lb")
