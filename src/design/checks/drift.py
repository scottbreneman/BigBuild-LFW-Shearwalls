"""Shear wall deflection and story drift (example §3.4, Tables 3.13-3.19).

By default each story is analysed floor to floor with the SDPWS 3-term
equation and no rotation carried up from lower stories, as in the example
(§3.4.4, "Multi-Story Shear Wall Effects"). Options (decision D6):

- ``deflection_method="4-term"``: SDPWS Commentary Eq. C4.3.4-1 with panel
  shear rigidity G_v t_v and nail slip e_n (example §3.4.2).
- ``RodSystem(takeup_device=False, shrinkage_in=...)``: shrinkage counted and
  take-up slack/elongation dropped (example §3.4.3, Table 3.17B).
- ``restraint_each_level=False``: no tie-down bearing restraint at every floor,
  so chord deformation accumulates up the building (Table 3.17B, cumulative).
- ``carry_rotation=True``: each story also rotates with the stories below,
  rigid body from their anchorage deformation plus chord bending (owner
  decision, rigid-body geometry).
"""

from __future__ import annotations

from dataclasses import dataclass

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
    if rs.takeup_device:
        parts.append(t.step("slack", "Take-up device slack", "Δ_slack", "given", "", rs.slack_in, "in",
                            f"input; {EX} Table 3.17A", "assumption"))
        parts.append(t.step("takeup", "Take-up device elongation", "Δ_tu", "given", "", rs.takeup_elongation_in, "in",
                            "input; manufacturer data", "assumption"))
        if rs.shrinkage_in:
            t.step("shrinkage", "Shrinkage (compensated by take-up device)", "Δ_sh", "not counted", "", 0.0, "in",
                   f"{EX} §3.4.3", "assumption")
    else:
        parts.append(t.step("shrinkage", "Shrinkage (no take-up device)", "Δ_sh", "given", "", rs.shrinkage_in, "in",
                            f"input; {EX} §2.3, Table 3.17B", "assumption",
                            note="Without a take-up device, slack and device elongation do not apply (example §3.4.3)"))
    tot = sum(parts)
    b, d = ctx.inp.b_ft, ch.d_ft
    return t.step("delta_a", "Total vertical chord deformation at wall ends", "Δ_a",
                  r"\Delta_a = (\Delta_t + \Delta_c) b / d",
                  f"{tot:.4f}({fmt(b, 2)}) / {fmt(d, 2)}", tot * b / d, "in", f"{EX} §3.4.3, Fig. 3.9", "memory")


def _shear_term(ctx: Context, i: int, t: Tracer, v: float) -> float:
    """δ_v: the 3-term G_a term, or the 4-term panel shear plus nail slip."""
    inp, s = ctx.inp, ctx.story(i)
    h = s.h_ft
    asm = lookup(ctx.lib.assembly, s.assembly_id)
    if inp.deflection_method == "3-term":
        col = "Ga_osb_kips_per_in" if s.panel_type == "OSB" else "Ga_plywood_kips_per_in"
        Ga1 = value(asm, col, s.assembly_id)
        Ga = t.step("Ga", "Apparent shear stiffness", "G_a", r"G_a = n_{sides} G_{a,table}", f"{s.sides}({Ga1})",
                    s.sides * Ga1, "kips/in", cite(asm), status(asm),
                    note="Two sides summed, as in example Table 3.18" if s.sides == 2 else "")
        return t.step("d2", "Shear and nail-slip term", "δ_v", r"v h / (1000 G_a)", f"{fmt(v, 0)}({h}) / (1000({Ga}))",
                      v * h / (1000 * Ga), "in", f"SDPWS-2021 Eq. 4.3-1; {EX} §3.4.2, Table 3.18", "memory")

    cit = f"SDPWS-2021 Commentary Eq. C4.3.4-1; {EX} §3.4.2"
    label = f"{s.panel_type} {asm.panel_grade} {asm.min_nominal_panel_thickness_label}"
    panel = lookup(ctx.lib.sheathing_panel, s.panel_type, asm.panel_grade, asm.min_nominal_panel_thickness_label)
    Gt1 = value(panel, "Gvtv_lb_per_in", label)
    Gt = t.step("Gvtv", f"Panel shear rigidity ({label})", "G_v t_v", r"n_{sides} (G_v t_v)_{table}",
                f"{s.sides}({fmt(Gt1, 0)})", s.sides * Gt1, "lb/in", cite(panel), status(panel))
    nail = lookup(ctx.lib.nail, asm.nail_designation)
    wet = inp.framing_moisture
    den = value(nail, f"slip_den_{wet}", asm.nail_designation)
    exp = value(nail, f"slip_exp_{wet}", asm.nail_designation)
    sp = asm.edge_nail_spacing_in
    Vn = t.step("V_n", "Load per edge nail (per side)", "V_n", r"V_n = (v / n_{sides}) s / 12",
                f"({fmt(v, 0)} / {s.sides})({sp:g}) / 12", v / s.sides * sp / 12, "lb", "statics", "statics")
    if nail.slip_max_load_lb is not None and Vn > nail.slip_max_load_lb:
        raise NeedsEngineerInput("D6", f"nail load {Vn:.0f} lb exceeds the slip equation range "
                                       f"({nail.slip_max_load_lb:.0f} lb) for {asm.nail_designation}")
    struct1 = asm.panel_grade == "Structural I"
    kf = 1.0 if struct1 else fx.SLIP_NOT_STRUCTURAL_I.value
    en = t.step("e_n", f"Nail slip ({wet} framing)", "e_n", r"e_n = k (V_n / den)^{exp}",
                f"{kf}({Vn:.1f} / {den:g})^{exp:g}", kf * (Vn / den) ** exp, "in",
                cite(nail) + ("" if struct1 else f"; {fx.SLIP_NOT_STRUCTURAL_I.citation}"),
                status(nail) if struct1 else "memory")
    dv_s = t.step("d2_shear", "Panel shear term", "δ_vs", r"v h / (G_v t_v)", f"{fmt(v, 0)}({h}) / {fmt(Gt, 0)}",
                  v * h / Gt, "in", cit, "memory")
    c = fx.FOUR_TERM_SLIP_COEFF.value
    dv_n = t.step("d2_slip", "Nail slip term", "δ_vn", r"0.75 h e_n", f"{c}({h})({en:.5f})", c * h * en, "in",
                  cit, "memory")
    return t.step("d2", "Shear and nail-slip terms (4-term)", "δ_v", r"\delta_{vs} + \delta_{vn}",
                  f"{dv_s:.4f} + {dv_n:.4f}", dv_s + dv_n, "in", cit, "memory")


@dataclass(frozen=True)
class StoryDeflection:
    delta_b: float  # chord bending term, in.
    delta_a_level: float  # this level's vertical chord deformation at the wall ends, in.
    delta_a_ends: float  # value used in the anchorage term (cumulative without restraint at each level), in.
    delta_sw: float  # the story's own shear wall deflection, in.
    steps: tuple


def story_deflection(ctx: Context, i: int) -> StoryDeflection:
    """The story's own deflection (floor to floor), memoised for rotation carried up."""
    key = ("deflection", i)
    if key in ctx.cache:
        return ctx.cache[key]
    inp, s, sf = ctx.inp, ctx.story(i), ctx.sf(i)
    wind = inp.load_type == "wind"
    t = Tracer(f"S{i}.drift")
    b, h = inp.b_ft, s.h_ft
    v = t.step("v", "Drift-level unit shear", "v_δ", r"v = 1.0 V / b", f"{fmt(sf.V_lb, 0)} / {fmt(b, 2)}",
               ctx.combos.drift_shear.E * sf.V_lb / b, "plf",
               "spec-io D6 (wind, 1.0W)" if wind else f"{EX} Table 3.13C", "assumption" if wind else "memory")
    p = chord_posts(ctx, s.chord)
    E = t.step("E", "Chord modulus of elasticity", "E", "table", "", value(p.values, "E_psi", "E"), "psi",
               cite(p.values), status(p.values))
    A = t.step("A", "Chord post area", "A", r"n A_{post}", f"{p.n}({p.size.area_in2:.2f})", p.area_in2, "in²",
               cite(p.size), status(p.size))
    t2 = _shear_term(ctx, i, t, v)
    da_level = da = _delta_a(ctx, i, t)
    if not inp.restraint_each_level and i > 1:
        lower = [story_deflection(ctx, k).delta_a_level for k in range(1, i)]
        da = t.step("delta_a_cum", "Cumulative chord deformation (no restraint at each level)", "Δ_a,cum",
                    r"\Delta_{a,cum,i} = \sum_{k \le i} \Delta_{a,k}",
                    " + ".join(f"{x:.4f}" for x in [*lower, da_level]), sum(lower) + da_level, "in",
                    f"{EX} §3.4.3, Table 3.17B", "assumption",
                    note="Used in the anchorage term in place of the level value")
    cit =f"SDPWS-2021 Eq. 4.3-1; {EX} §3.4.2, Table 3.18"
    t1 = t.step("d1", "Bending term", "δ_b", r"8 v h^3 / (E A b)",
                f"8({fmt(v, 0)})({h})³ / ({fmt(E, 0)}({A:.2f})({b}))", 8 * v * h**3 / (E * A * b), "in", cit, "memory")
    t3 = t.step("d3", "Anchorage rotation term", "δ_a", r"h \Delta_a / b", f"{h}({da:.4f}) / {b}", h * da / b, "in",
                cit, "memory")
    dsw = t.step("delta_sw", "Shear wall deflection", "δ_sw", r"\delta_{sw} = \delta_b + \delta_v + \delta_a",
                 f"{t1:.4f} + {t2:.4f} + {t3:.4f}", t1 + t2 + t3, "in",
                 cit if inp.deflection_method == "3-term" else "SDPWS-2021 Commentary Eq. C4.3.4-1", "memory",
                 note="The story's own deflection, floor to floor")
    out = StoryDeflection(t1, da_level, da, dsw, tuple(t.steps))
    ctx.cache[key] = out
    return out


def _rotation_below(ctx: Context, i: int, t: Tracer) -> float:
    """Δ_below = 12 h_i Σ θ_k over stories k below i (rigid-body anchorage rotation + chord bending)."""
    b, h = ctx.inp.b_ft, ctx.story(i).h_ft
    k15 = fx.CANTILEVER_ROTATION.value
    total = 0.0
    for k in range(1, i):
        dk, hk = story_deflection(ctx, k), ctx.story(k).h_ft
        th_a = dk.delta_a_level / (12 * b)
        th_b = k15 * dk.delta_b / (12 * hk)
        total += t.step(f"theta_{k}", f"Rotation at top of story {k}", f"θ_{k}",
                        r"\theta_k = \Delta_{a,k} / (12 b) + 1.5 \delta_{b,k} / (12 h_k)",
                        f"{dk.delta_a_level:.4f} / (12·{fmt(b, 2)}) + 1.5({dk.delta_b:.5f}) / (12·{hk})",
                        th_a + th_b, "rad", "statics; owner decision D6 (rigid-body geometry)", "assumption",
                        note="Stories above rotate rigidly with the top of story k")
    return t.step("delta_below", "Drift from rotation of stories below", "Δ_below", r"12 h_i \sum_{k<i} \theta_k",
                  f"12({h})({total:.6f})", 12 * h * total, "in", "statics; owner decision D6", "assumption")


def check_drift(ctx: Context, i: int) -> CheckResult:
    inp, s, ch = ctx.inp, ctx.story(i), ctx.ch(i)
    wind = inp.load_type == "wind"
    if wind and inp.wind_drift_limit_ratio is None:
        raise NeedsEngineerInput("D6", "enter the wind drift limit (wind_drift_limit_ratio, e.g. 1/400)")
    own = story_deflection(ctx, i)
    t = Tracer(f"S{i}.drift")
    t.extend(x for x in ch.steps if "drift" in x.id or x.id.endswith(("C_E", "M_R")))
    t.extend(own.steps)
    h = s.h_ft
    de = own.delta_sw
    if inp.carry_rotation and i > 1:
        below = _rotation_below(ctx, i, t)
        de = t.step("delta_story", "Story deflection incl. rotation below", "δ_e", r"\delta_{sw} + \Delta_{below}",
                    f"{own.delta_sw:.4f} + {below:.4f}", own.delta_sw + below, "in", "statics", "statics")
    if wind:
        r = inp.wind_drift_limit_ratio
        allow = t.step("drift_allow", "Allowable wind story drift (user limit)", "Δ_allow",
                       r"\Delta_{allow} = r h", f"{r:.5f}(12)({h})", r * 12 * h, "in",
                       "user input; spec-io C4/D6 (ASCE 7-22 App. C commentary, non-mandatory)", "assumption")
        return t.result(f"S{i}.drift", f"Story drift (wind), story {i}", i, "drift", demand=de,
                        capacity=allow, demand_unit="in")
    Dx = t.step("drift", "Design story drift", "Δ", r"\Delta = C_d \delta_{e} / I_e",
                f"{inp.C_d}({de:.4f}) / {inp.I_e}", inp.C_d * de / inp.I_e, "in",
                f"ASCE 7-22 Eq. 12.8-16; {EX} §3.4.5", "memory")
    if inp.risk_category not in ("I", "II"):
        raise NeedsEngineerInput("drift limit", f"allowable drift for Risk Category {inp.risk_category} not entered")
    lim = fx.DRIFT_LIMIT_RC_I_II
    allow = t.step("drift_allow", "Allowable story drift", "Δ_a", r"\Delta_a = 0.020 h_{sx}", f"0.020(12)({h})",
                   lim.value * 12 * h, "in", lim.citation, lim.status)
    return t.result(f"S{i}.drift", f"Story drift, story {i}", i, "drift", demand=Dx, capacity=allow,
                    demand_unit="in")
