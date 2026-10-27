"""Component library for the light-frame wood shear-wall tool.

This package holds the *data* side of the design checks: framing lumber,
sheathing panels, nails, sheathed-wall shear assemblies, hold-downs, and
continuous tie-down (rod) systems. It deliberately contains no design
formulas. Design values are read from CSV files in ``data/``; every record
carries a ``source`` citation and a ``status`` flag so nothing unverified
reaches a calculation silently.

Units are US customary throughout: inches, pounds, pounds per linear foot
(plf), pounds per square inch (psi). Column names in the CSV files include
the unit where one applies (``thickness_in``, ``Fb_psi``, ``v_n_plf``).

Reference editions: NDS 2024 (with Supplement), SDPWS 2021, IBC 2024,
ASCE 7-22. Manufacturer data cites the catalog or evaluation report edition.
"""

from .loader import (
    ComponentDataError,
    ComponentLibrary,
    UnverifiedComponentError,
    load_library,
    read_records,
)
from .schema import (
    ContinuousRodSystem,
    HoldDown,
    LumberDesignValues,
    LumberSize,
    Nail,
    SheathingPanel,
    ShearWallAssembly,
    SizeFactor,
    Status,
)

__all__ = [
    "ComponentDataError",
    "ComponentLibrary",
    "UnverifiedComponentError",
    "read_records",
    "ContinuousRodSystem",
    "HoldDown",
    "LumberDesignValues",
    "LumberSize",
    "Nail",
    "SheathingPanel",
    "ShearWallAssembly",
    "SizeFactor",
    "Status",
    "load_library",
]
