"""Code factors used by the checks, each with its citation and source status.

Values are taken from the WoodWorks five-story example, which cites the
listed standard sections. None has been checked against the standard by an
engineer yet, so all carry ``memory``. Values not given in the example are
deliberately absent; ``size_factor_Fc`` raises ``NeedsEngineerInput`` for them.
"""

from __future__ import annotations

from dataclasses import dataclass

from .trace import NeedsEngineerInput, SourceStatus

EX = "WoodWorks 5-story example"


@dataclass(frozen=True)
class Factor:
    value: float
    citation: str
    status: SourceStatus = "memory"


OMEGA_SEISMIC = Factor(2.8, f"SDPWS-2021 §4.1.4.1; {EX} §3.3.4, §4.2")
OMEGA_WIND = Factor(2.0, f"SDPWS-2021 §4.1.4.2; {EX} §4.2")
TWO_SIDED_MULTIPLIER = Factor(2.0, f"SDPWS-2021 §4.3.5.4.1 (same sheathing and nailing both sides); {EX} §3.3.4")
ASPECT_RATIO_NO_REDUCTION = Factor(2.0, f"SDPWS-2021 §4.3.3; {EX} §3.3")
FRAMING_3X_NOMINAL_PLF = Factor(980.0, f"SDPWS-2021 §4.3.7.1 item 5; {EX} §3.3.4")
FRAMING_3X_10D_SPACING_IN = Factor(3.0, f"SDPWS-2021 §4.3.7.1 item 5; {EX} §3.3.4")

# NDS 2024 adjustment factors as applied in example §3.3.5
C_D_LATERAL = Factor(1.6, f"NDS-2024 Table 2.3.2 (seismic/wind); {EX} §3.3.5")
C_M = Factor(1.0, f"NDS-2024 §4.3.3, dry service; {EX} §3.3.5")
C_t = Factor(1.0, f"NDS-2024 §2.3.3; {EX} §3.3.5")
C_i = Factor(1.0, f"NDS-2024 §4.3.8, not incised; {EX} §3.3.5")
K_e = Factor(1.0, f"NDS-2024 Appendix G, pinned-pinned; {EX} §3.3.5")
C_SAWN = Factor(0.8, f"NDS-2024 §3.7.1, sawn lumber; {EX} §3.3.5")

_SIZE_FACTOR_FC = {
    ("Douglas Fir-Larch", "No.1", "2x4"): Factor(1.15, f"NDS-2024 Supplement Table 4A adjustment factors; {EX} §3.3.5"),
}


def size_factor_Fc(species_group: str, grade: str, nominal: str) -> Factor:
    try:
        return _SIZE_FACTOR_FC[(species_group, grade, nominal)]
    except KeyError:
        raise NeedsEngineerInput(
            "C_F", f"size factor C_F for Fc of {species_group} {grade} {nominal} not entered "
                   "(add it to design/factors.py from NDS-2024 Supplement Table 4A)"
        ) from None


# Bearing / bending of the tie-down plate (example §3.3.6)
BEARING_AREA_HOLE_OVERSIZE_IN = Factor(3 / 16, f"{EX} §3.3.6 (rod hole in wood plate)", "assumption")
STEEL_PLATE_HOLE_OVERSIZE_IN = Factor(1 / 16, f"AISC Steel Manual 16th ed. Table J3.3; {EX} §3.3.6")
OMEGA_STEEL_FLEXURE = Factor(1.67, f"AISC 360-22 Chapter F, Eq. F11-1; {EX} §3.3.6")
E_STEEL_PSI = Factor(29_000_000.0, f"AISC 360-22; {EX} §3.4.3", "memory")

# Deformation (example §3.4.3, Fig. 3.10)
FC_PERP_002_RATIO = Factor(0.73, f"NDS-2024 §4.2.6; {EX} §3.4.3, Fig. 3.10")
SHEATHING_FC_002_PSI = Factor(210.0, f"APA Panel Design Specification (2020); {EX} §3.4.3")
SHEATHING_FC_004_PSI = Factor(360.0, f"APA Panel Design Specification (2020); {EX} §3.4.3")
SHEATHING_SPREAD_IN = Factor(6.0, f"{EX} §3.4.3, Table 3.14 (45° spread through the plates)", "assumption")
DRIFT_LIMIT_RC_I_II = Factor(0.020, f"ASCE 7-22 Table 12.12-1; {EX} §3.4.5")
