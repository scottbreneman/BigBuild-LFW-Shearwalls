"""Dataclass schemas for shear-wall components.

Each record type mirrors one CSV file in ``data/``. Fields whose names end
in a unit suffix (``_in``, ``_psi``, ``_plf``, ``_lb``, ``_kips_per_in``)
carry that unit. Design-value fields are ``Optional`` so a row can exist
with its geometry filled in while the engineer is still transcribing the
standard's values; such rows must carry ``status = pending``.

No design provisions live here. Section properties on ``LumberSize`` are
plain geometry (rectangle area, section modulus, moment of inertia).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Status(str, Enum):
    """Source status of a data record, matching docs/spec-io.md and the
    team's transparency rule in docs/hackathon-plan.md.

    verified   - values entered and checked by an engineer against the named
                 source page; ``checked_by`` names the checker.
    memory     - values entered from recall (an engineer's), not yet checked
                 against the source. Usable in the build; always flagged and
                 listed in the report's "Items to verify".
    pending    - row exists (usually geometry only) but design values have
                 not been entered. Lookups refuse these by default.
    superseded - kept for history; never returned by lookups.
    """

    VERIFIED = "verified"
    MEMORY = "memory"
    PENDING = "pending"
    SUPERSEDED = "superseded"


@dataclass(frozen=True)
class SourcedRecord:
    """Fields common to every component record (spec-io.md §1, capacity table row)."""

    source_doc: str
    """Document: standard + edition ("SDPWS 2021"), catalog + edition, or
    evaluation report number. Never blank."""

    table: str
    """Table or section within the document ("Table 4.3A"). May be blank
    only when the document has no table structure (e.g. an ESR)."""

    page: str
    """Printed page number(s) in the cited document. Blank until entered."""

    status: Status
    entered_by: str = ""  # initials of whoever typed the values in
    checked_by: str = ""  # initials of the engineer who checked them; required for verified
    notes: str = ""


# --------------------------------------------------------------------------
# Framing lumber
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class LumberSize(SourcedRecord):
    """Dressed (actual) dimensions of a nominal sawn-lumber size.

    ``thickness_in`` is the smaller dimension (nominal 2 -> 1.5);
    ``width_in`` is the larger (nominal 4 -> 3.5). Bending about the strong
    axis takes ``width_in`` as the depth.
    """

    nominal: str = ""  # e.g. "2x4", "4x6"
    thickness_in: float = 0.0
    width_in: float = 0.0

    # Section properties as printed in NDS Supplement Table 1B, kept so a test
    # can confirm the computed rectangle properties agree with the table.
    table_area_in2: Optional[float] = None
    table_Sxx_in3: Optional[float] = None
    table_Ixx_in4: Optional[float] = None
    table_Syy_in3: Optional[float] = None
    table_Iyy_in4: Optional[float] = None

    @property
    def area_in2(self) -> float:
        return self.thickness_in * self.width_in

    @property
    def Sx_in3(self) -> float:
        """Section modulus, strong axis (depth = width_in)."""
        return self.thickness_in * self.width_in**2 / 6.0

    @property
    def Ix_in4(self) -> float:
        """Moment of inertia, strong axis (depth = width_in)."""
        return self.thickness_in * self.width_in**3 / 12.0

    @property
    def Sy_in3(self) -> float:
        """Section modulus, weak axis (depth = thickness_in)."""
        return self.width_in * self.thickness_in**2 / 6.0

    @property
    def Iy_in4(self) -> float:
        """Moment of inertia, weak axis (depth = thickness_in)."""
        return self.width_in * self.thickness_in**3 / 12.0


@dataclass(frozen=True)
class LumberDesignValues(SourcedRecord):
    """Reference design values for a species group / grade / size class.

    Values are the *reference* (unadjusted) values from the NDS Supplement.
    Adjustment factors (C_D, C_M, C_t, C_F, C_r, C_P, ...) are applied by the
    design module, not stored here.

    ``size_class`` is the row label used by the source table. For DF-L and
    SPF this is typically a thickness/width range such as
    ``2"-4" thick, 2" & wider``; Southern Pine tables are width-specific
    (``2x4``, ``2x6``, ...). Use the source's own label.
    """

    species_group: str = ""  # "Douglas Fir-Larch", "Spruce-Pine-Fir", "Southern Pine"
    grade: str = ""  # "Select Structural", "No.1", "No.2", "Stud", ...
    size_class: str = ""
    Fb_psi: Optional[float] = None
    Ft_psi: Optional[float] = None
    Fv_psi: Optional[float] = None
    Fc_perp_psi: Optional[float] = None
    Fc_psi: Optional[float] = None
    E_psi: Optional[float] = None
    Emin_psi: Optional[float] = None
    specific_gravity: Optional[float] = None  # G, for fastener design


# --------------------------------------------------------------------------
# Sheathing panels
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SheathingPanel(SourcedRecord):
    """A wood structural panel (WSP) product class."""

    panel_type: str = ""  # "OSB" or "Plywood"
    panel_grade: str = ""  # "Sheathing" or "Structural I"
    nominal_thickness_label: str = ""  # "7/16", "15/32", ...
    nominal_thickness_in: float = 0.0
    span_rating: str = ""  # "24/16", "32/16", ... blank if not tracked
    exposure: str = ""  # "Exposure 1", "Exterior", blank if not tracked


# --------------------------------------------------------------------------
# Nails
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Nail(SourcedRecord):
    """A nail by trade designation."""

    designation: str = ""  # "8d common", "10d box", ...
    pennyweight: str = ""  # "8d"
    nail_type: str = ""  # "common", "box", "sinker", "cooler", ...
    diameter_in: float = 0.0
    length_in: float = 0.0
    head_diameter_in: Optional[float] = None
    bending_yield_Fyb_psi: Optional[float] = None


# --------------------------------------------------------------------------
# Sheathed shear-wall assemblies (SDPWS 2021 Table 4.3A structure)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ShearWallAssembly(SourcedRecord):
    """One row of a nominal unit shear capacity table for WSP shear walls.

    Mirrors the columns of SDPWS 2021 Table 4.3A for wood structural panel
    shear walls. ``v_n_plf`` is the single *nominal* unit shear capacity the
    table prints per cell; the table's footnote 1 points to SDPWS 4.1.4 for
    the ASD allowable and LRFD factored values, and that conversion (and any
    seismic/wind distinction) lives in the design module with its own
    citation. ``Ga_*`` is the apparent shear-wall shear stiffness (kips/in)
    used in the SDPWS deflection equation, tabulated for OSB and for
    plywood.
    """

    assembly_id: str = ""  # stable key, e.g. "WSP-S-7/16-8dc-6"
    sheathing_material: str = ""  # "WSP"
    panel_grade: str = ""  # "Sheathing" or "Structural I"
    min_nominal_panel_thickness_label: str = ""
    min_nominal_panel_thickness_in: float = 0.0
    min_fastener_penetration_in: Optional[float] = None
    nail_designation: str = ""  # key into nails.csv
    edge_nail_spacing_in: float = 0.0  # 6, 4, 3, 2
    v_n_plf: Optional[float] = None
    Ga_osb_kips_per_in: Optional[float] = None
    Ga_plywood_kips_per_in: Optional[float] = None
    footnotes: str = ""  # source table footnote numbers that apply to the row


# --------------------------------------------------------------------------
# Hold-downs and continuous tie-down systems
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class HoldDown(SourcedRecord):
    """A discrete hold-down (e.g. Simpson HDU, HDQ series).

    Allowable loads are manufacturer-published ASD values for the stated
    post species; apply the manufacturer's load-duration and other
    conditions in the design module.
    """

    model: str = ""
    manufacturer: str = ""
    anchor_diameter_in: Optional[float] = None
    fastener_description: str = ""  # e.g. "SDS 1/4 x 2-1/2"
    fastener_count: Optional[int] = None
    min_post: str = ""  # e.g. "4x4", "(2) 2x4", "6x6"
    allowable_tension_DF_SP_lb: Optional[float] = None
    allowable_tension_SPF_HF_lb: Optional[float] = None
    deflection_at_allowable_in: Optional[float] = None
    evaluation_report: str = ""  # e.g. "ICC-ES ESR-2330"


@dataclass(frozen=True)
class ContinuousRodSystem(SourcedRecord):
    """A continuous rod tie-down (ATS-type) run element.

    One record per rod size/material. Take-up devices and bearing plates are
    described textually for now; they get their own tables if the drift
    model needs their stiffness.
    """

    system_id: str = ""
    manufacturer: str = ""
    rod_diameter_in: float = 0.0
    rod_material: str = ""  # ASTM designation, e.g. "A36", "A307", "A193 B7"
    rod_allowable_tension_lb: Optional[float] = None
    rod_net_area_in2: Optional[float] = None
    take_up_device: str = ""
    bearing_plate: str = ""
    evaluation_report: str = ""


# Convenience: which dataclass goes with which data file.
RECORD_TYPES = {
    "lumber_sizes": LumberSize,
    "lumber_design_values": LumberDesignValues,
    "sheathing_panels": SheathingPanel,
    "nails": Nail,
    "shear_wall_assemblies": ShearWallAssembly,
    "holddowns": HoldDown,
    "continuous_rod_systems": ContinuousRodSystem,
}
