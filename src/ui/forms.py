"""Story tables <-> ``DesignInputs`` (UI side only; no design logic).

Three editable tables share the story number as their index:
loads and nailing, chord posts, and tie-downs.
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from design.inputs import ChordSpec, DesignInputs, GenericHoldDown, RodSystem, StoryInput, TributarySpec

# Tributary inputs (decision D9): on for a story when trib_L_ft > 0; the engine then computes F for both cases.
TRIB_COLS = ["trib_V_seismic_lb", "trib_V_wind_lb", "trib_L_ft", "trib_span_left_ft", "trib_span_right_ft",
             "trib_line_length_ft"]
LOAD_COLS = ["h_ft", "F_seismic_lb", "F_wind_lb", "w_D_plf", "w_wall_plf", "w_L_plf", "w_Lr_plf", "assembly_id", "sides",
             "panel_type", *TRIB_COLS]
V_COL = {"seismic": "trib_V_seismic_lb", "wind": "trib_V_wind_lb"}
CHORD_COLS = ["n_posts", "post_nominal", "species_group", "grade", "size_class", "chord_length_ft",
              "d_arm_ft", "d_out_of_plane_in", "top_plates_in", "bottom_plate_in"]
TIE_COLS = ["kind", "system_id", "plate_width_in", "plate_length_in", "plate_thickness_in", "plate_Fy_psi",
            "slack_in", "takeup_elongation_in", "rod_length_ft", "bearing_hole_in", "takeup_device", "shrinkage_in",
            "model", "T_allow_lb", "delta_a_in"]
ROD, HOLDDOWN = "Rod system", "Hold-down"

GLOBAL_DEFAULTS: dict[str, Any] = dict(
    project_name="", b_ft=20.0, S_DS=0.0, C_d=0.0, I_e=0.0, risk_category="II", sdc="",
    d_post_in=0.0, roof_uplift_plf=0.0, wind_drift_denominator=0.0, wood_bearing_factor=1.75, carry_rotation=False,
    deflection_method="3-term", framing_moisture="dry", restraint_each_level=True,
)


def _none(x):
    """NaN / None / blank -> None."""
    if x is None:
        return None
    if isinstance(x, float) and math.isnan(x):
        return None
    if isinstance(x, str) and not x.strip():
        return None
    try:
        if pd.isna(x):
            return None
    except (TypeError, ValueError):
        pass
    return x


def _f(x, default: float = 0.0) -> float:
    v = _none(x)
    return default if v is None else float(v)


def _opt(x):
    v = _none(x)
    return None if v is None else float(v)


def _pos_or_none(x):
    v = _opt(x)
    return v if v and v > 0 else None


SEISMIC_KEYS = ("S_DS", "C_d", "I_e", "risk_category", "sdc")
WIND_KEYS = ("roof_uplift_plf", "wind_drift_denominator")


def global_values_from_inputs(inp: DesignInputs) -> dict[str, Any]:
    return dict(
        project_name=inp.project_name, b_ft=inp.b_ft, S_DS=inp.S_DS or 0.0,
        C_d=inp.C_d or 0.0, I_e=inp.I_e or 0.0, risk_category=inp.risk_category or "II", sdc=inp.sdc or "",
        d_post_in=inp.d_post_in or 0.0, roof_uplift_plf=inp.roof_uplift_plf,
        wind_drift_denominator=(1 / inp.wind_drift_limit_ratio) if inp.wind_drift_limit_ratio else 0.0,
        wood_bearing_factor=inp.wood_bearing_factor, carry_rotation=inp.carry_rotation,
        deflection_method=inp.deflection_method, framing_moisture=inp.framing_moisture,
        restraint_each_level=inp.restraint_each_level,
    )


def global_values_from_cases(cases: dict[str, DesignInputs]) -> dict[str, Any]:
    """Merge one or two load-case inputs: seismic-only fields come from the seismic case, wind-only from wind."""
    vals = dict(GLOBAL_DEFAULTS)
    first = cases.get("seismic") or cases.get("wind")
    if first is not None:
        vals.update(global_values_from_inputs(first))
    for lt, keys in (("seismic", SEISMIC_KEYS), ("wind", WIND_KEYS)):
        if lt in cases:
            gv = global_values_from_inputs(cases[lt])
            vals.update({k: gv[k] for k in keys})
    if "seismic" not in cases:
        vals.update(S_DS=0.0, C_d=0.0, I_e=0.0)
    return vals


def frames_from_cases(cases: dict[str, DesignInputs]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Story tables from one or two load cases (structure from the first, forces from each case)."""
    base = cases.get("seismic") or cases.get("wind")
    loads, chords, ties = [], [], []
    for k, s in enumerate(base.stories):
        row = {c: getattr(s, c) for c in LOAD_COLS if c not in ("F_seismic_lb", "F_wind_lb", *TRIB_COLS)}
        row["F_seismic_lb"] = cases["seismic"].stories[k].F_lb if "seismic" in cases else 0.0
        row["F_wind_lb"] = cases["wind"].stories[k].F_lb if "wind" in cases else 0.0
        tr = s.tributary
        row.update(trib_L_ft=tr.L_ft if tr else 0.0, trib_span_left_ft=tr.span_left_ft if tr else 0.0,
                   trib_span_right_ft=tr.span_right_ft if tr else 0.0,
                   trib_line_length_ft=(tr.line_length_ft or 0.0) if tr else 0.0)
        for lt, col in V_COL.items():
            ct = cases[lt].stories[k].tributary if lt in cases else None
            row[col] = ct.V_story_lb if ct else 0.0
        loads.append(row)
        chords.append({c: getattr(s.chord, c) for c in CHORD_COLS})
        t = s.tiedown
        if isinstance(t, RodSystem):
            ties.append(dict(kind=ROD, system_id=t.system_id, plate_width_in=t.plate_width_in,
                             plate_length_in=t.plate_length_in, plate_thickness_in=t.plate_thickness_in,
                             plate_Fy_psi=t.plate_Fy_psi, slack_in=t.slack_in,
                             takeup_elongation_in=t.takeup_elongation_in, rod_length_ft=t.rod_length_ft,
                             bearing_hole_in=t.bearing_hole_in, takeup_device=t.takeup_device,
                             shrinkage_in=t.shrinkage_in, model=None, T_allow_lb=None, delta_a_in=None))
        else:
            ties.append(dict(kind=HOLDDOWN, system_id=None, plate_width_in=None, plate_length_in=None,
                             plate_thickness_in=None, plate_Fy_psi=None, slack_in=None, takeup_elongation_in=None,
                             rod_length_ft=None, bearing_hole_in=None, takeup_device=True, shrinkage_in=0.0,
                             model=t.model, T_allow_lb=t.T_allow_lb, delta_a_in=t.delta_a_in))
    idx = pd.RangeIndex(1, len(base.stories) + 1, name="story")
    return (pd.DataFrame(loads, columns=LOAD_COLS, index=idx), pd.DataFrame(chords, columns=CHORD_COLS, index=idx),
            pd.DataFrame(ties, columns=TIE_COLS, index=idx))


def frames_from_inputs(inp: DesignInputs):
    return frames_from_cases({inp.load_type: inp})


def resize_frames(frames, n: int):
    """Grow (copying the top story) or shrink the three story tables to ``n`` rows."""
    out = []
    for df in frames:
        df = df.iloc[:n].copy()
        while len(df) < n:
            df.loc[len(df) + 1] = df.iloc[-1]
        df.index = pd.RangeIndex(1, n + 1, name="story")
        out.append(df)
    return tuple(out)


def _tributary(l, v_col: str | None) -> TributarySpec | None:
    """Tributary spec for one story row, or None when trib_L_ft is 0 or blank (F is then typed)."""
    if not _pos_or_none(l.get("trib_L_ft")):
        return None
    return TributarySpec(V_story_lb=_f(l.get(v_col)) if v_col else 0.0, L_ft=_f(l["trib_L_ft"]),
                         span_left_ft=_f(l.get("trib_span_left_ft")), span_right_ft=_f(l.get("trib_span_right_ft")),
                         line_length_ft=_pos_or_none(l.get("trib_line_length_ft")))


def stories_from_frames(loads: pd.DataFrame, chords: pd.DataFrame, ties: pd.DataFrame,
                        force_col: str = "F_lb", v_col: str | None = None) -> tuple[StoryInput, ...]:
    stories = []
    for k in range(len(loads)):
        l, c, t = loads.iloc[k], chords.iloc[k], ties.iloc[k]
        chord = ChordSpec(
            n_posts=int(_f(c["n_posts"])), post_nominal=str(_none(c["post_nominal"]) or "2x4"),
            species_group=str(_none(c["species_group"]) or ""), grade=str(_none(c["grade"]) or ""),
            size_class=str(_none(c["size_class"]) or ""), chord_length_ft=_f(c["chord_length_ft"]),
            d_arm_ft=_pos_or_none(c["d_arm_ft"]), d_out_of_plane_in=_pos_or_none(c["d_out_of_plane_in"]),
            top_plates_in=_f(c["top_plates_in"], 3.0), bottom_plate_in=_f(c["bottom_plate_in"], 1.5))
        if t["kind"] == ROD:
            tiedown = RodSystem(
                system_id=str(_none(t["system_id"]) or ""), plate_width_in=_f(t["plate_width_in"]),
                plate_length_in=_f(t["plate_length_in"]), plate_thickness_in=_f(t["plate_thickness_in"]),
                plate_Fy_psi=_f(t["plate_Fy_psi"], 36_000.0), slack_in=_f(t["slack_in"]),
                takeup_elongation_in=_f(t["takeup_elongation_in"]), rod_length_ft=_pos_or_none(t["rod_length_ft"]),
                bearing_hole_in=_pos_or_none(t["bearing_hole_in"]),
                takeup_device=True if _none(t["takeup_device"]) is None else bool(t["takeup_device"]),
                shrinkage_in=_f(t["shrinkage_in"]))
        else:
            tiedown = GenericHoldDown(model=_none(t["model"]), T_allow_lb=_pos_or_none(t["T_allow_lb"]),
                                      delta_a_in=_opt(t["delta_a_in"]))
        stories.append(StoryInput(
            h_ft=_f(l["h_ft"]), F_lb=_f(l[force_col]), assembly_id=str(_none(l["assembly_id"]) or ""), chord=chord,
            tiedown=tiedown, w_D_plf=_f(l["w_D_plf"]), w_wall_plf=_f(l["w_wall_plf"]), w_L_plf=_f(l["w_L_plf"]),
            w_Lr_plf=_f(l["w_Lr_plf"]), sides=int(_f(l["sides"], 1)),
            panel_type=str(_none(l["panel_type"]) or "OSB"), tributary=_tributary(l, v_col)))
    return tuple(stories)


def case_force(loads: pd.DataFrame, story: int, load_type: str) -> float:
    """The force that drives a load case at one story: tributary V_x when tributary is on, else the typed F."""
    l = loads.loc[story]
    if _pos_or_none(l.get("trib_L_ft")):
        return _f(l.get(V_COL[load_type]))
    return _f(l.get({"seismic": "F_seismic_lb", "wind": "F_wind_lb"}[load_type]))


def build_inputs(g: dict[str, Any], loads, chords, ties, load_type: str | None = None) -> DesignInputs:
    load_type = load_type or g.get("load_type", "seismic")
    force_col = {"seismic": "F_seismic_lb", "wind": "F_wind_lb"}.get(load_type, "F_lb")
    if force_col not in loads.columns:
        force_col = "F_lb"
    seismic = load_type == "seismic"
    denom = _pos_or_none(g.get("wind_drift_denominator"))
    return DesignInputs(
        load_type=load_type, b_ft=_f(g["b_ft"]),
        stories=stories_from_frames(loads, chords, ties, force_col, V_COL.get(load_type)),
        S_DS=_f(g["S_DS"]) if seismic else None, C_d=_pos_or_none(g["C_d"]) if seismic else None,
        I_e=_pos_or_none(g["I_e"]) if seismic else None, risk_category=g["risk_category"] if seismic else None,
        sdc=(g["sdc"] or None) if seismic else None, d_post_in=_pos_or_none(g["d_post_in"]),
        roof_uplift_plf=0.0 if seismic else _f(g["roof_uplift_plf"]),
        wind_drift_limit_ratio=None if seismic else ((1 / denom) if denom else None),
        wood_bearing_factor=_f(g["wood_bearing_factor"], 1.75), carry_rotation=bool(g["carry_rotation"]),
        deflection_method=g["deflection_method"], framing_moisture=g["framing_moisture"],
        restraint_each_level=bool(g["restraint_each_level"]),
        project_name=g.get("project_name", ""))


def build_cases(g: dict[str, Any], loads, chords, ties) -> dict[str, DesignInputs]:
    """One DesignInputs per load type that has at least one force entered (seismic and wind forces in lb)."""
    cases = {}
    for lt in ("seismic", "wind"):
        if any(case_force(loads, i, lt) > 0 for i in loads.index):
            cases[lt] = build_inputs(g, loads, chords, ties, load_type=lt)
    return cases
