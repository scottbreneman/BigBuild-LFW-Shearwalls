"""The production component library reproduces the WoodWorks example.

tests/test_woodworks_seismic.py runs the example on a fixture library transcribed
from the example itself. This test re-points the example's component ids at the
production tables (SDPWS Table 4.3A rows, NDS Table 4A values, F1554 Gr. 36 rods)
and checks that every check still passes with DCRs within 0.5% of the fixture run.
The small shear differences come from the fixture's back-calculated v_n (868 plf)
versus the tabulated 870 plf.
"""

import dataclasses

import pytest

from design.engine import run_design
from design.result import OverallStatus
from woodworks_example import inputs, library

FIXTURE_TO_PRODUCTION = {
    "EX-OSB-15/32-10dc-": "WSP-SH-15/32-10dc-",
    "EX-F1554-36-": "F1554-36-",
}


def _remap(value: str) -> str:
    for old, new in FIXTURE_TO_PRODUCTION.items():
        if value.startswith(old):
            return new + value[len(old):]
    return value


def _production_inputs():
    inp = inputs()
    stories = []
    for s in inp.stories:
        changes = {"assembly_id": _remap(s.assembly_id)}
        td = getattr(s, "tiedown", None)
        if td is not None and hasattr(td, "system_id"):
            changes["tiedown"] = dataclasses.replace(td, system_id=_remap(td.system_id))
        stories.append(dataclasses.replace(s, **changes))
    return dataclasses.replace(inp, stories=tuple(stories))


def test_production_library_reproduces_woodworks_example():
    fixture = run_design(inputs(), library())
    production = run_design(_production_inputs())  # default = production library
    assert fixture.status is OverallStatus.PASS
    assert production.status is OverallStatus.PASS, [n.message for n in production.needs_input]
    assert not production.needs_input
    for sf, sp in zip(fixture.stories, production.stories):
        for cf, cp in zip(sf.checks, sp.checks):
            assert cf.id == cp.id and cf.status is cp.status, cf.id
            if cf.dcr is not None:
                assert cp.dcr == pytest.approx(cf.dcr, rel=5e-3), cf.id
