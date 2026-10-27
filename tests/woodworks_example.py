"""Inputs for the WoodWorks five-story over-podium seismic shear wall (example §3.3-3.4).

Story numbering: story 1 is the bottom wall, which the example labels "3rd"
(it sits on the podium at level 2). The example labels each wall by the level
at its top, so story 5 is its "Roof" wall.

    story:            1      2      3      4      5
    example label:    3rd    4th    5th    6th    Roof

Values come from example Tables 3.4, 3.5, 3.6, 3.7, 3.9, 3.11, 3.12, 3.17A and §3.1.
"""

import dataclasses
from pathlib import Path

from design.components import load_library
from design.inputs import ChordSpec, DesignInputs, RodSystem, StoryInput

COMPONENTS_DIR = Path(__file__).parent / "fixtures" / "woodworks_components"

F_LB = [2282, 4564, 6847, 9129, 9397]  # Table 3.4, strength level, F3 .. Froof
FLOOR_D_PLF = [390, 390, 390, 390, 56]  # §3.3.5: floor 30 psf x 13 ft, roof 28 psf x 2 ft
WALL_PLF = 100  # 10 psf x 10 ft
FLOOR_L_PLF = [520, 520, 520, 520, 0]
ROOF_LR_PLF = [0, 0, 0, 0, 40]
NAILING = [("EX-OSB-15/32-10dc-4", 2), ("EX-OSB-15/32-10dc-2", 1), ("EX-OSB-15/32-10dc-2", 1),
           ("EX-OSB-15/32-10dc-4", 1), ("EX-OSB-15/32-10dc-6", 1)]  # Table 3.5
N_POSTS = [16, 13, 10, 7, 6]  # Table 3.9
CHORD_LENGTH_FT = [2.500, 2.125, 1.750, 1.375, 1.250]  # Table 3.8
D_ARM_FT = [26.97, 27.18, 27.40, 27.65, 27.75]  # Table 3.6
RODS = ["EX-F1554-36-1-1/8", "EX-F1554-36-1", "EX-F1554-36-3/4", "EX-F1554-36-5/8", "EX-F1554-36-5/8"]
PLATES = [(3.0, 4.0, 0.625), (3.0, 4.0, 0.625), (3.0, 3.5, 0.5), (3.0, 3.0, 0.375), (3.0, 3.0, 0.375)]  # Table 3.12


def library():
    return load_library(COMPONENTS_DIR)


def inputs(**overrides) -> DesignInputs:
    stories = []
    for k in range(5):
        asm, sides = NAILING[k]
        w, l, t = PLATES[k]
        stories.append(StoryInput(
            h_ft=10.0, F_lb=F_LB[k], assembly_id=asm, sides=sides,
            chord=ChordSpec(n_posts=N_POSTS[k], chord_length_ft=CHORD_LENGTH_FT[k], d_arm_ft=D_ARM_FT[k]),
            tiedown=RodSystem(RODS[k], w, l, t, slack_in=1 / 32, takeup_elongation_in=0.030),  # Table 3.17A
            w_D_plf=FLOOR_D_PLF[k], w_wall_plf=WALL_PLF, w_L_plf=FLOOR_L_PLF[k], w_Lr_plf=ROOF_LR_PLF[k],
        ))
    args = dict(load_type="seismic", b_ft=29.0, stories=tuple(stories), S_DS=1.206, C_d=4.0, I_e=1.0,
                risk_category="II", sdc="D", project_name="WoodWorks five-story example")  # §3.1
    args.update(overrides)
    return DesignInputs(**args)


# The same example on the production component library (src/design/components/data):
# fixture ids map to the production SDPWS Table 4.3A rows and F1554 rods (see PR #12,
# tests/test_production_library_example.py).
FIXTURE_TO_PRODUCTION = {
    "EX-OSB-15/32-10dc-": "WSP-SH-15/32-10dc-",
    "EX-F1554-36-": "F1554-36-",
}


def to_production_id(value: str) -> str:
    for old, new in FIXTURE_TO_PRODUCTION.items():
        if value.startswith(old):
            return new + value[len(old):]
    return value


def production_inputs(**overrides) -> DesignInputs:
    """The example inputs with component ids pointing at the production library."""
    inp = inputs(**overrides)
    stories = []
    for s in inp.stories:
        changes = {"assembly_id": to_production_id(s.assembly_id)}
        if isinstance(s.tiedown, RodSystem):
            changes["tiedown"] = dataclasses.replace(s.tiedown, system_id=to_production_id(s.tiedown.system_id))
        stories.append(dataclasses.replace(s, **changes))
    return dataclasses.replace(inp, stories=tuple(stories))
