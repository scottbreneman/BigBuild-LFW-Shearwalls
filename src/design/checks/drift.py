"""Shear wall deflection and story drift (example §3.4, Tables 3.13-3.19).

Each story is analysed floor to floor, with no rotation carried up from
lower stories (example §3.4.4, "Multi-Story Shear Wall Effects").
"""

from __future__ import annotations

from .. import factors as fx
from ..inputs import GenericHoldDown, RodSystem
from ..library import cite, lookup, status, value
from ..trace import CheckResult, NeedsEngineerInput, Tracer, fmt
from . import Context
from .compression import chord_posts
from .tiedown import bearing_area

EX = "WoodWorks 5-story example"


def wood_crushing(fc: float, Fc_perp: float) -> tuple[float, str]:
    """Perpendicular-to-grain deformation (in.) under a metal plate, example Fig. 3.10 Eqs. 1-3."""
    F02 = fx.FC_PERP_002_RATIO.value * Fc_perp
    if fc <= F02:
        return 0.02 * fc / F02, "Eq. 1"
    if fc <= Fc_perp:
        return 0.04 - 0.02 * (Fc_perp - fc) / (Fc_perp - F02), "Eq. 2"
    return 0.04 * (fc / Fc_perp) ** 3, "Eq. 3"


def sheathing_crushing(fc: float) -> tuple[float, str]:
    """Floor-sheathing crushing (in.), APA points 210 psi -> 0.02 in., 360 psi -> 0.04 in. (example §3.4.3)."""
    f02, f04 = fx.SHEATHING_FC_002_PSI.value, fx.SHEATHING_FC_004_PSI.value
    if fc <= f02:
        return 0.02 * fc / f02, "Eq. 1"
    if fc <= f04:
        return 0.04 - 0.02 * (f04 - fc) / (f04 - f02), "Eq. 2 (sheathing)"
    raise NeedsEngineerInput("D6", f"sheathing bearing stress {fc:.0f} psi exceeds 360 psi; the example gives "
                                   "no sheathing crushing equation beyond that point")


def _crush_step(t: Tracer, key: str, name: str, C: float, A: float, fn, factor: float, *args) -> float:
    fc = C / A
    delta, eq = fn(fc, *args)
    return t.step(key, name, "Δ_c", r"\Delta = k \cdot \Delta(f_c),\ f_c = C / A",
                  f"f_c = {fmt(C, 0)} / {A:.2f} = {fc:.0f} psi → {eq}: {delta:.4f} × {factor}", delta * factor,
                  "in", fx.FC_PERP_002_RATIO.citation if fn is wood_crushing else fx.SHEATHING_FC_002_PSI.citation,
                  "memory")


def _delta_a(ctx: Context, i: int, t: Tracer) -> float:
    s, ch = ctx.story(i), ctx.ch(i)
    td = s.tiedown
    if isinstance(td, GenericHoldDown):
        if td.delta_a_in is None:
            raise NeedsEngineerInput("D6", "give delta_a_in for the generic hold-down to compute drift")
        return t.step("delta_a", "Total vertical chord deformation (user input)", "Δ_a", "given", "", td.delta_a_in,
                      "in", "input; product data", "assumption")
    rs: RodSystem = td
    rec = lookup(ctx.lib.rod_system, rs.system_id)
    p = chord_posts(ctx, s.chord)
    Fcp = value(p.values, "Fc_perp_psi", "Fc_perp")
    k = ctx.inp.wood_bearing_factor
    t.step("k_wood", "Wood-to-wood bearing deformation factor", "k", "", "", k, "", f"{EX} §3.4.3", "assumption",
           note="Engineer-of-record judgement; the example uses 1.75 for parallel-to-perpendicular bearing")
    C = ch.C_drift_lb
    parts = [_crush_step(t, "crush_bot", "Crushing: posts on bottom plate", C, p.area_in2, wood_crushing, k, Fcp)]
    if i > 1:
        below = chord_posts(ctx, ctx.story(i - 1).chord)
        d_out = s.chord.d_out_of_plane_in or p.size.width_in
        sp = fx.SHEATHING_SPREAD_IN
        A_sh = t.step("A_sh", "Sheathing bearing area", "A_sh", r"A_{sh} = A_{posts} + s \cdot d",
                      f"{p.area_in2:.2f} + {sp.value}({d_out})", p.area_in2 + sp.value * d_out, "in²",
                      sp.citation, sp.status,
                      note="Post bearing area spread 45° through the plates (3 in. each side), as in example "
                           "Table 3.14 and the SEB spreadsheet")
        parts.append(_crush_step(t, "crush_sh", "Crushing: floor sheathing", C, A_sh, sheathing_crushing, 1.0))
        parts.append(_crush_step(t, "crush_top", "Crushing: top plate on posts below", C, below.area_in2,
                                 wood_crushing, k, Fcp))
    else:
        t.step("crush_note", "Bottom story bears on podium/foundation", "", "", "", "no sheathing or top-plate crushing",
               "", f"{EX} §3.4.3", "assumption")

    Ae = value(rec, "rod_net_area_in2", rs.system_id)
    L = 12 * (rs.rod_length_ft or s.h_ft)
    Es = fx.E_STEEL_PSI.value
    parts.append(t.step("rod", "Rod elongation", "Δ_rod", r"\Delta_{rod} = T_\delta L / (A_e E)",
                        f"{fmt(ch.T_drift_lb, 0)}({L:.1f}) / ({Ae}({fmt(Es, 0)}))", ch.T_drift_lb * L / (Ae * Es),
                        "in", f"{cite(rec)}; {EX} Table 3.15", status(rec)))
    A_brg = bearing_area(t, rs, rec.rod_diameter_in)
    parts.append(_crush_step(t, "crush_plate", "Crushing under bearing plate", ch.dT_drift_lb, A_brg, wood_crushing,
                             1.0, Fcp))
    parts.append(t.step("slack", "Take-up device slack", "Δ_slack", "given", "", rs.slack_in, "in",
                        f"input; {EX} Table 3.17A", "assumption"))
    parts.append(t.step("takeup", "Take-up device elongation", "Δ_tu", "given", "", rs.takeup_elongation_in, "in",
                        "input; manufacturer data", "assumption"))
    tot = sum(parts)
    b, d = ctx.inp.b_ft, ch.d_ft
    return t.step("delta_a", "Total vertical chord deformation at wall ends", "Δ_a", r"\Delta_a = (\Delta_t + \Delta_c) b / d",
                  f"{tot:.4f}({fmt(b, 2)}) / {fmt(d, 2)}", tot * b / d, "in", f"{EX} §3.4.3, Fig. 3.9", "memory")


def check_drift(ctx: Context, i: int) -> CheckResult:
    inp, s, sf, ch = ctx.inp, ctx.story(i), ctx.sf(i), ctx.ch(i)
    wind = inp.load_type == "wind"
    if wind and inp.wind_drift_limit_ratio is None:
        raise NeedsEngineerInput("D6", "enter the wind drift limit (wind_drift_limit_ratio, e.g. 1/400)")
    if inp.carry_rotation:
        raise NeedsEngineerInput("D6", "rotation carried up from lower stories is not in the example; "
                                       "method not entered")
    t = Tracer(f"S{i}.drift")
    t.extend(x for x in ch.steps if "drift" in x.id or x.id.endswith(("C_E", "M_R")))
    b, h = inp.b_ft, s.h_ft
    v = t.step("v", "Drift-level unit shear", "v_δ", r"v = 1.0 V / b", f"{fmt(sf.V_lb, 0)} / {fmt(b, 2)}",
               ctx.combos.drift_shear.E * sf.V_lb / b, "plf",
               "spec-io D6 (wind, 1.0W)" if wind else f"{EX} Table 3.13C", "assumption" if wind else "memory")
    p = chord_posts(ctx, s.chord)
    E = t.step("E", "Chord modulus of elasticity", "E", "table", "", value(p.values, "E_psi", "E"), "psi",
               cite(p.values), status(p.values))
    A = t.step("A", "Chord post area", "A", r"n A_{post}", f"{p.n}({p.size.area_in2:.2f})", p.area_in2, "in²",
               cite(p.size), status(p.size))
    asm = lookup(ctx.lib.assembly, s.assembly_id)
    col = "Ga_osb_kips_per_in" if s.panel_type == "OSB" else "Ga_plywood_kips_per_in"
    Ga1 = value(asm, col, s.assembly_id)
    Ga = t.step("Ga", "Apparent shear stiffness", "G_a", r"G_a = n_{sides} G_{a,table}", f"{s.sides}({Ga1})",
                s.sides * Ga1, "kips/in", cite(asm), status(asm),
                note="Two sides summed, as in example Table 3.18" if s.sides == 2 else "")
    da = _delta_a(ctx, i, t)
    cit = f"SDPWS-2021 Eq. 4.3-1; {EX} §3.4.2, Table 3.18"
    t1 = t.step("d1", "Bending term", "δ_b", r"8 v h^3 / (E A b)", f"8({fmt(v, 0)})({h})³ / ({fmt(E, 0)}({A:.2f})({b}))",
                8 * v * h**3 / (E * A * b), "in", cit, "memory")
    t2 = t.step("d2", "Shear and nail-slip term", "δ_v", r"v h / (1000 G_a)", f"{fmt(v, 0)}({h}) / (1000({Ga}))",
                v * h / (1000 * Ga), "in", cit, "memory")
    t3 = t.step("d3", "Anchorage rotation term", "δ_a", r"h \Delta_a / b", f"{h}({da:.4f}) / {b}", h * da / b, "in",
                cit, "memory")
    dsw = t.step("delta_sw", "Shear wall deflection", "δ_sw", r"\delta_{sw} = \delta_b + \delta_v + \delta_a",
                 f"{t1:.4f} + {t2:.4f} + {t3:.4f}", t1 + t2 + t3, "in", cit, "memory",
                 note="Used as the elastic story drift δ_e (floor-to-floor analysis)")
    if wind:
        r = inp.wind_drift_limit_ratio
        allow = t.step("drift_allow", "Allowable wind story drift (user limit)", "Δ_allow",
                       r"\Delta_{allow} = r h", f"{r:.5f}(12)({h})", r * 12 * h, "in",
                       "user input; spec-io C4/D6 (ASCE 7-22 App. C commentary, non-mandatory)", "assumption")
        return t.result(f"S{i}.drift", f"Story drift (wind), story {i}", i, "drift", demand=dsw,
                        capacity=allow, demand_unit="in")
    Dx = t.step("drift", "Design story drift", "Δ", r"\Delta = C_d \delta_{e} / I_e", f"{inp.C_d}({dsw:.4f}) / {inp.I_e}",
                inp.C_d * dsw / inp.I_e, "in", f"ASCE 7-22 Eq. 12.8-16; {EX} §3.4.5", "memory")
    if inp.risk_category not in ("I", "II"):
        raise NeedsEngineerInput("drift limit", f"allowable drift for Risk Category {inp.risk_category} not entered")
    lim = fx.DRIFT_LIMIT_RC_I_II
    allow = t.step("drift_allow", "Allowable story drift", "Δ_a", r"\Delta_a = 0.020 h_{sx}", f"0.020(12)({h})",
                   lim.value * 12 * h, "in", lim.citation, lim.status)
    return t.result(f"S{i}.drift", f"Story drift, story {i}", i, "drift", demand=Dx, capacity=allow,
                    demand_unit="in")
