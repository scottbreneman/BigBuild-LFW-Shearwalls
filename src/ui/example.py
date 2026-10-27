"""WoodWorks five-story example as a seismic case plus a wind case (inputs only).

Seismic: the engine's own fixture (example Chapter 3). Wind: per-wall story forces from example Tables 4.4 and 4.6
(Ftotal / 2 for the two 29-ft walls per line, strength-level W, story 1 = "3rd" ... story 5 = "Roof").
"""

from __future__ import annotations

import dataclasses as dc

from ui.runtime import ensure_paths

ensure_paths()

WIND_F_LB = [2259, 2360, 2439, 2504, 3033]  # Table 4.6, "Shear Wall Story Force", 3rd .. Roof
ROOF_UPLIFT_PLF = 82.7                       # back-calculated from Table 4.6 roof M_OT (65 ft-k); engineer to confirm
WIND_DRIFT_RATIO = 1 / 400                   # placeholder: example §4.6 cites H/600 to H/400 as common practice (D6)

PLACEHOLDERS = (
    "Roof uplift 82.7 plf: back-calculated from example Table 4.6 (roof M_OT 65 ft-k), not stated in the example text.",
    "Wind drift limit H/400: placeholder; the example gives H/600 to H/400 as common practice. The owner sets it (D6).",
    "Wind forces are the example's Chapter 4 values on the Chapter 3 wall and components, so the wall is checked "
    "for both load types in one demo. The example itself designs Chapter 4 with different chords.",
)


def example_cases(production: bool = False):
    """Seismic and wind cases; ``production=True`` points the component ids at the project library."""
    import woodworks_example as ex
    seis = ex.production_inputs() if production else ex.inputs()
    wind_stories = tuple(dc.replace(s, F_lb=float(WIND_F_LB[k])) for k, s in enumerate(seis.stories))
    wind = dc.replace(seis, load_type="wind", stories=wind_stories, S_DS=None, C_d=None, I_e=None, risk_category=None,
                      sdc=None, roof_uplift_plf=ROOF_UPLIFT_PLF, wind_drift_limit_ratio=WIND_DRIFT_RATIO)
    return {"seismic": seis, "wind": wind}


def example_library():
    import woodworks_example as ex
    return ex.library()
