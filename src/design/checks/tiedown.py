"""Overturning restraint: generic hold-down or continuous rod with bearing plates
(example §3.3.6, Tables 3.10-3.12)."""

from __future__ import annotations

import math

from .. import factors as fx
from ..inputs import GenericHoldDown, RodSystem
from ..library import cite, lookup, status, value
from ..trace import CheckResult, CheckStatus, Tracer, fmt
from . import Context
from .compression import chord_posts

EX = "WoodWorks 5-story example"


def _tension_steps(ctx: Context, i: int, t: Tracer) -> float:
    ch = ctx.ch(i)
    t.extend(s for s in ch.steps if ".asd." in s.id or s.id.endswith(("C_E", "M_R")))
    return ch.T_lb


def check_holddown(ctx: Context, i: int) -> CheckResult:
    s = ctx.story(i)
    hd: GenericHoldDown = s.tiedown
    t = Tracer(f"S{i}.holddown")
    T = _tension_steps(ctx, i, t)
    if hd.model is not None:
        rec = lookup(ctx.lib.holddown, hd.model)
        col = ("allowable_tension_DF_SP_lb" if s.chord.species_group in ("Douglas Fir-Larch", "Southern Pine")
               else "allowable_tension_SPF_HF_lb")
        T_allow = t.step("T_allow", f"Hold-down allowable tension ({hd.model})", "T_allow", "catalog", "",
                         value(rec, col, hd.model), "lb", cite(rec), status(rec),
                         note="Confirm the manufacturer's load-duration basis")
    else:
        T_allow = t.step("T_allow", "Hold-down allowable tension (user input)", "T_allow", "given", "",
                         hd.T_allow_lb, "lb", "input; product evaluation report", "assumption")
    return t.result(f"S{i}.holddown", f"Hold-down tension, story {i}", i, "holddown",
                    demand=T, capacity=T_allow, demand_unit="lb")


def _rod(ctx: Context, i: int):
    rs: RodSystem = ctx.story(i).tiedown
    return rs, lookup(ctx.lib.rod_system, rs.system_id)


def check_rod(ctx: Context, i: int) -> CheckResult:
    t = Tracer(f"S{i}.rod")
    T = _tension_steps(ctx, i, t)
    rs, rec = _rod(ctx, i)
    allow = t.step("T_allow", f"Rod allowable tension ({rs.system_id})", "R_n/Ω", "catalog", "",
                   value(rec, "rod_allowable_tension_lb", rs.system_id), "lb", cite(rec), status(rec))
    return t.result(f"S{i}.rod", f"Tie-down rod tension, story {i}", i, "rod", demand=T, capacity=allow,
                    demand_unit="lb")


def bearing_area(t: Tracer, rs: RodSystem, d_rod: float) -> float:
    if rs.bearing_hole_in is not None:
        hole = t.step("hole", "Hole in wood plate (given)", "d_h", "given", "", rs.bearing_hole_in, "in",
                      "input; plate specification", "assumption")
    else:
        hole = t.step("hole", "Hole in wood plate", "d_h", r"d_h = d_{rod} + 3/16",
                      f"{d_rod:.4f} + 0.1875", d_rod + fx.BEARING_AREA_HOLE_OVERSIZE_IN.value, "in",
                      fx.BEARING_AREA_HOLE_OVERSIZE_IN.citation, fx.BEARING_AREA_HOLE_OVERSIZE_IN.status)
    return t.step("A_brg", "Net bearing area", "A_brg", r"A_{brg} = W L - \pi d_h^2 / 4",
                  f"({rs.plate_width_in})({rs.plate_length_in}) − π({hole:.4f})²/4",
                  rs.plate_width_in * rs.plate_length_in - math.pi * hole**2 / 4, "in²", f"{EX} §3.3.6", "statics")


def check_plate_bearing(ctx: Context, i: int) -> CheckResult:
    ch = ctx.ch(i)
    t = Tracer(f"S{i}.plate_brg")
    rs, rec = _rod(ctx, i)
    A = bearing_area(t, rs, rec.rod_diameter_in)
    p = chord_posts(ctx, ctx.story(i).chord)
    Fcp = t.step("Fc_perp", "Reference compression perpendicular (plates)", "F_c⊥", "table", "",
                 value(p.values, "Fc_perp_psi", "Fc_perp"), "psi", cite(p.values), status(p.values),
                 note="Plates taken as the same species and grade as the chord posts")
    lb = rs.plate_length_in
    if lb < 6.0:
        Cb = t.step("C_b", "Bearing area factor", "C_b", r"C_b = (l_b + 0.375) / l_b", f"({lb} + 0.375) / {lb}",
                    (lb + 0.375) / lb, "", f"NDS-2024 §3.10.4; {EX} §3.3.6", "memory")
    else:
        Cb = t.step("C_b", "Bearing area factor", "C_b", "l_b ≥ 6 in.", "", 1.0, "", "NDS-2024 §3.10.4", "memory")
    Fp = t.step("Fcperp_p", "Adjusted bearing stress", "F'_c⊥", r"F'_{c\perp} = F_{c\perp} C_M C_t C_i C_b",
                f"{fmt(Fcp, 0)}(1.0)(1.0)(1.0)({Cb:.3f})", Fcp * fx.C_M.value * fx.C_t.value * fx.C_i.value * Cb,
                "psi", "NDS-2024 Table 4.3.1", "memory")
    cap = t.step("P_brg", "Allowable bearing", "P_brg", r"F'_{c\perp} A_{brg}", f"{fmt(Fp, 0)}({A:.2f})", Fp * A,
                 "lb", f"{EX} Table 3.12", "memory")
    t.extend(s for s in ch.steps if s.id.endswith(".dT"))
    return t.result(f"S{i}.plate_brg", f"Bearing plate bearing, story {i}", i, "plate_bearing",
                    demand=ch.dT_lb, capacity=cap, demand_unit="lb")


def check_plate_bending(ctx: Context, i: int) -> CheckResult:
    ch = ctx.ch(i)
    t = Tracer(f"S{i}.plate_bend")
    rs, rec = _rod(ctx, i)
    d_rod = rec.rod_diameter_in
    A = bearing_area(t, rs, d_rod)
    w, L, th = rs.plate_width_in, rs.plate_length_in, rs.plate_thickness_in
    f = t.step("f", "Uniform bearing pressure on plate", "f", r"f = \Delta T / A_{brg}",
               f"{fmt(ch.dT_lb, 0)} / {A:.2f}", ch.dT_lb / A, "psi", f"{EX} §3.3.6", "statics")
    M = t.step("M", "Plate bending moment (cantilever from rod)", "M", r"M = f W (L/2)^2 / 2",
               f"{fmt(f, 0)}({w})({L / 2:.3f})² / 2", f * w * (L / 2) ** 2 / 2, "in-lb", f"{EX} §3.3.6", "memory")
    hole = d_rod + fx.STEEL_PLATE_HOLE_OVERSIZE_IN.value
    Z = t.step("Z", "Net plastic section modulus", "Z", r"Z = (W - d_h) t^2 / 4",
               f"({w} − {hole:.4f})({th})² / 4", (w - hole) * th**2 / 4, "in³",
               fx.STEEL_PLATE_HOLE_OVERSIZE_IN.citation, fx.STEEL_PLATE_HOLE_OVERSIZE_IN.status,
               note="Z governs over 1.6 S for a rectangle (example: 'by inspection')")
    om = fx.OMEGA_STEEL_FLEXURE
    cap = t.step("M_allow", "Allowable plate moment", "M_n/Ω", r"M_n / \Omega = F_y Z / 1.67",
                 f"{fmt(rs.plate_Fy_psi, 0)}({Z:.4f}) / {om.value}", rs.plate_Fy_psi * Z / om.value, "in-lb",
                 om.citation, om.status)
    if ch.dT_lb == 0:
        return CheckResult(f"S{i}.plate_bend", f"Bearing plate bending, story {i}", i, "plate_bending",
                           CheckStatus.PASS, 0.0, cap, 0.0, "in-lb", "in-lb", "no uplift at this plate",
                           steps=tuple(t.steps))
    return t.result(f"S{i}.plate_bend", f"Bearing plate bending, story {i}", i, "plate_bending",
                    demand=M, capacity=cap, demand_unit="in-lb")
