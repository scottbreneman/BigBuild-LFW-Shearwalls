"""Engine inputs (docs/spec-io.md §1, extended for the WoodWorks example checks).

Units are US customary and carried in the field names. Story forces ``F_lb``
are at **strength level** (E_h or W); the engine applies the ASD and drift
load-combination factors (decision D8, revised). Story 1 is the bottom.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Union

LoadType = Literal["seismic", "wind"]


@dataclass(frozen=True)
class ChordSpec:
    """Compression posts at each end of the wall (example §3.3.5, Fig. 3.7)."""

    n_posts: int
    post_nominal: str = "2x4"  # key into lumber_sizes.csv
    species_group: str = "Douglas Fir-Larch"  # keys into lumber_design_values.csv
    grade: str = "No.1"
    size_class: str = '2"-4" thick, 2" & wider'
    chord_length_ft: float = 0.0  # total chord length incl. the rod gap; gravity tributary to the chord
    d_arm_ft: float | None = None  # rod centre to post centroid; default per D2 from wall d_post_in
    d_out_of_plane_in: float | None = None  # post dimension across the wall; default = dressed width
    top_plates_in: float = 3.0  # subtracted from story height for the post's unbraced length
    bottom_plate_in: float = 1.5


@dataclass(frozen=True)
class GenericHoldDown:
    """Discrete hold-down: a library model or a direct allowable (spec-io T_allow,i and Δ_a,i)."""

    model: str | None = None  # key into holddowns.csv
    T_allow_lb: float | None = None  # used when no model is given
    delta_a_in: float | None = None  # total vertical deformation at drift-level load, Stage C


@dataclass(frozen=True)
class RodSystem:
    """Continuous rod tie-down with a bearing plate at the top of the story (example §3.3.6)."""

    system_id: str  # key into continuous_rod_systems.csv
    plate_width_in: float
    plate_length_in: float
    plate_thickness_in: float
    plate_Fy_psi: float = 36_000.0  # ASTM A36 (example §3.3.6)
    slack_in: float = 0.0  # take-up device travel before engagement (example Table 3.17A)
    takeup_elongation_in: float = 0.0  # manufacturer value (example Table 3.17A)
    rod_length_ft: float | None = None  # bearing restraint to restraint; default story height
    bearing_hole_in: float | None = None  # rod hole in the wood under the plate; default rod + 3/16 in.
    takeup_device: bool = True  # shrinkage-compensating take-up device present (example §3.4.3)
    shrinkage_in: float = 0.0  # story shrinkage; counted only without a take-up device (example Table 3.17B)


Tiedown = Union[GenericHoldDown, RodSystem]


@dataclass(frozen=True)
class StoryInput:
    h_ft: float  # floor-to-floor height
    F_lb: float  # strength-level lateral force applied at the top of this story
    assembly_id: str  # key into shear_wall_assemblies.csv
    chord: ChordSpec
    tiedown: Tiedown
    w_D_plf: float = 0.0  # floor/roof dead load delivered at the top of this story, excl. wall weight
    w_wall_plf: float = 0.0  # self-weight of this story's wall
    w_L_plf: float = 0.0  # floor live load delivered at the top of this story
    w_Lr_plf: float = 0.0  # roof live load delivered at the top of this story
    sides: int = 1  # sheathed sides, same assembly on each side
    panel_type: Literal["OSB", "Plywood"] = "OSB"  # selects G_a column


@dataclass(frozen=True)
class DesignInputs:
    load_type: LoadType
    b_ft: float  # wall length, same for every story
    stories: tuple[StoryInput, ...]
    S_DS: float | None = None
    C_d: float | None = None
    I_e: float | None = None
    risk_category: str | None = None  # "I", "II", "III", "IV"
    sdc: str | None = None  # seismic design category, for the 3x framing flag
    d_post_in: float | None = None  # end post width for the default lever arm (D2)
    roof_uplift_plf: float = 0.0  # wind: strength-level net roof uplift on the wall (example §4.5.2)
    wind_drift_limit_ratio: float | None = None  # wind: allowable story drift / story height, e.g. 1/400 (D6)
    wood_bearing_factor: float = 1.75  # wood-to-wood crushing amplification (example §3.4.3, EOR judgement)
    carry_rotation: bool = False  # D6: add rigid-body and bending rotation of the stories below
    deflection_method: Literal["3-term", "4-term"] = "3-term"  # SDPWS Eq. 4.3-1 or Commentary Eq. C4.3.4-1
    framing_moisture: Literal["dry", "green"] = "dry"  # selects the nail-slip equation (4-term only)
    restraint_each_level: bool = True  # tie-down bearing restraint at every floor; False accumulates Δ_a (Table 3.17B)
    project_name: str = ""


@dataclass(frozen=True)
class InputError:
    field: str
    message: str


def validate(inp: DesignInputs) -> list[InputError]:
    """Range and completeness checks; the engine runs no checks while this list is non-empty."""
    errs: list[InputError] = []

    def need(cond: bool, fld: str, msg: str) -> None:
        if not cond:
            errs.append(InputError(fld, msg))

    need(inp.load_type in ("seismic", "wind"), "load_type", "must be 'seismic' or 'wind'")
    need(inp.b_ft > 0, "b_ft", "wall length must be positive")
    need(1 <= len(inp.stories) <= 5, "stories", "1 to 5 stories are supported")
    if inp.load_type == "seismic":
        need(inp.S_DS is not None and inp.S_DS >= 0, "S_DS", "required for seismic and must be >= 0")
        need(inp.C_d is not None and inp.C_d > 0, "C_d", "required for seismic drift and must be > 0")
        need(inp.I_e is not None and inp.I_e > 0, "I_e", "required for seismic drift and must be > 0")
        need(inp.risk_category in ("I", "II", "III", "IV"), "risk_category", "one of I, II, III, IV")
    need(inp.wood_bearing_factor >= 1.0, "wood_bearing_factor", "must be >= 1.0")
    need(inp.roof_uplift_plf >= 0, "roof_uplift_plf", "must be >= 0")
    need(inp.deflection_method in ("3-term", "4-term"), "deflection_method", "'3-term' or '4-term'")
    need(inp.framing_moisture in ("dry", "green"), "framing_moisture", "'dry' or 'green'")
    need(not (inp.carry_rotation and not inp.restraint_each_level), "carry_rotation",
         "cannot be combined with restraint_each_level=False (both carry lower-story deformation up)")
    if inp.wind_drift_limit_ratio is not None:
        need(0 < inp.wind_drift_limit_ratio < 0.1, "wind_drift_limit_ratio", "a ratio such as 1/400 = 0.0025")

    for i, s in enumerate(inp.stories, start=1):
        p = f"stories[{i}]"
        need(s.h_ft > 0, f"{p}.h_ft", "story height must be positive")
        need(s.F_lb >= 0, f"{p}.F_lb", "story force must be >= 0")
        need(s.sides in (1, 2), f"{p}.sides", "1 or 2")
        need(s.panel_type in ("OSB", "Plywood"), f"{p}.panel_type", "'OSB' or 'Plywood'")
        for name in ("w_D_plf", "w_wall_plf", "w_L_plf", "w_Lr_plf"):
            need(getattr(s, name) >= 0, f"{p}.{name}", "must be >= 0")
        c = s.chord
        need(c.n_posts >= 1, f"{p}.chord.n_posts", "at least one post")
        need(c.chord_length_ft > 0, f"{p}.chord.chord_length_ft", "must be positive")
        if c.d_arm_ft is not None:
            need(0 < c.d_arm_ft < inp.b_ft, f"{p}.chord.d_arm_ft", "must be between 0 and the wall length")
        else:
            need(inp.d_post_in is not None and inp.d_post_in > 0, "d_post_in",
                 f"needed for the default lever arm of story {i} (or give chord.d_arm_ft)")
        need(s.h_ft * 12 > c.top_plates_in + c.bottom_plate_in, f"{p}.chord", "plates exceed story height")
        t = s.tiedown
        if isinstance(t, RodSystem):
            for name in ("plate_width_in", "plate_length_in", "plate_thickness_in", "plate_Fy_psi"):
                need(getattr(t, name) > 0, f"{p}.tiedown.{name}", "must be positive")
            need(t.slack_in >= 0 and t.takeup_elongation_in >= 0, f"{p}.tiedown", "slack and take-up must be >= 0")
            need(t.shrinkage_in >= 0, f"{p}.tiedown.shrinkage_in", "must be >= 0")
            if t.bearing_hole_in is not None:
                need(0 < t.bearing_hole_in < min(t.plate_width_in, t.plate_length_in), f"{p}.tiedown.bearing_hole_in",
                     "must be positive and smaller than the plate")
        elif isinstance(t, GenericHoldDown):
            need(t.model is not None or t.T_allow_lb is not None, f"{p}.tiedown",
                 "give a hold-down model or T_allow_lb")
        else:
            errs.append(InputError(f"{p}.tiedown", "must be GenericHoldDown or RodSystem"))
    return errs
