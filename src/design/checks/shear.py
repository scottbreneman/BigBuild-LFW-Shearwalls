"""Sheathing shear, 3x-framing detailing flag and aspect ratio (example §3.3, §3.3.4, Table 3.5)."""

from __future__ import annotations

from .. import factors as fx
from ..library import cite, lookup, status, value
from ..trace import CheckResult, CheckStatus, NeedsEngineerInput, Tracer, fmt
from . import Context


def _asd_allowable(ctx: Context, i: int, t: Tracer) -> tuple[float, float]:
    """Return (v_n per side, v_allow) and record the steps."""
    s = ctx.story(i)
    asm = lookup(ctx.lib.assembly, s.assembly_id)
    seismic = ctx.inp.load_type == "seismic"
    col = "v_seismic_nominal_plf" if seismic else "v_wind_nominal_plf"
    vn = value(asm, col, s.assembly_id)
    t.step("v_n", f"Nominal unit shear, {ctx.inp.load_type} ({s.assembly_id})", "v_n", "v_n = table",
           f"v_n = {fmt(vn, 0)} plf", vn, "plf", cite(asm), status(asm))
    om = fx.OMEGA_SEISMIC if seismic else fx.OMEGA_WIND
    mult = fx.TWO_SIDED_MULTIPLIER.value if s.sides == 2 else 1.0
    v_allow = t.step("v_allow", "ASD allowable unit shear", "v_allow", r"v_{allow} = n_{sides} v_n / \Omega",
                     f"{mult:g}({fmt(vn, 0)}) / {om.value}", mult * vn / om.value, "plf",
                     om.citation + ("; " + fx.TWO_SIDED_MULTIPLIER.citation if s.sides == 2 else ""), om.status)
    return vn, v_allow


def _v_asd(ctx: Context, i: int, t: Tracer) -> float:
    sf, c = ctx.sf(i), ctx.combos.shear
    return t.step("v", "ASD unit shear demand", "v", r"v = c_E V / b",
                  f"{c.E}({fmt(sf.V_lb, 0)} lb) / {fmt(ctx.inp.b_ft, 2)} ft", c.E * sf.V_lb / ctx.inp.b_ft, "plf",
                  "statics; WoodWorks 5-story example Table 3.5", "statics")


def check_shear(ctx: Context, i: int) -> CheckResult:
    t = Tracer(f"S{i}.shear")
    t.extend(ctx.combos.steps[:1])
    v = _v_asd(ctx, i, t)
    _, v_allow = _asd_allowable(ctx, i, t)
    return t.result(f"S{i}.shear", f"Sheathing shear, story {i}", i, "shear",
                    demand=v, capacity=v_allow, demand_unit="plf")


def check_framing_3x(ctx: Context, i: int) -> CheckResult:
    """Detailing flag: 3x framing at abutting panel edges (SDPWS §4.3.7.1 item 5 as quoted in the example)."""
    s = ctx.story(i)
    t = Tracer(f"S{i}.framing")
    asm = lookup(ctx.lib.assembly, s.assembly_id)
    v = _v_asd(ctx, i, t)
    om = fx.OMEGA_SEISMIC if ctx.inp.load_type == "seismic" else fx.OMEGA_WIND
    v_req = t.step("v_req", "Required nominal unit shear per side", "v_req", r"v_{req} = \Omega v / n_{sides}",
                   f"{om.value}({fmt(v, 0)}) / {s.sides}", om.value * v / s.sides, "plf", om.citation, om.status)
    reasons = []
    if asm.nail_designation.startswith("10d") and asm.edge_nail_spacing_in <= fx.FRAMING_3X_10D_SPACING_IN.value:
        reasons.append(f"10d nails at {asm.edge_nail_spacing_in:g} in. o.c.")
    if ctx.inp.sdc in ("D", "E", "F") and v_req > fx.FRAMING_3X_NOMINAL_PLF.value:
        reasons.append(f"required nominal shear {fmt(v_req, 0)} plf > 980 plf in SDC {ctx.inp.sdc}")
    t.step("flag", "3x framing at abutting panel edges", "", "SDPWS §4.3.7.1 item 5",
           "; ".join(reasons) or "no trigger", "required" if reasons else "not required", "",
           fx.FRAMING_3X_NOMINAL_PLF.citation, "memory")
    msg = ("3x nominal framing (or non-abutting panel edges) required: " + "; ".join(reasons)) if reasons \
        else "3x framing not triggered"
    return CheckResult(f"S{i}.framing", f"Framing detailing, story {i}", i, "detailing", CheckStatus.INFO,
                       message=msg, steps=tuple(t.steps))


def check_aspect(ctx: Context, i: int) -> CheckResult:
    s = ctx.story(i)
    t = Tracer(f"S{i}.aspect")
    lim = fx.ASPECT_RATIO_NO_REDUCTION
    r = t.step("h_b", "Aspect ratio", "h/b", "h / b", f"{fmt(s.h_ft, 2)} / {fmt(ctx.inp.b_ft, 2)}",
               s.h_ft / ctx.inp.b_ft, "", "statics", "statics")
    t.step("limit", "Aspect ratio without capacity adjustment", "(h/b)_lim", "h/b ≤ 2.0", "", lim.value, "",
           lim.citation, lim.status)
    if r > lim.value:
        raise NeedsEngineerInput("D3", f"h/b = {r:.2f} > 2.0; capacity adjustment and 3.5 limit "
                                       "(SDPWS-2021 §4.3.3-4.3.4) not yet entered")
    return t.result(f"S{i}.aspect", f"Aspect ratio, story {i}", i, "aspect", demand=r, capacity=lim.value,
                    demand_unit="")
