"""The production component library reproduces the WoodWorks example.

tests/test_woodworks_seismic.py runs the example on a fixture library transcribed
from the example itself. This test re-points the example's component ids at the
production tables (SDPWS Table 4.3A rows, NDS Table 4A values, F1554 Gr. 36 rods)
and checks that every check still passes with DCRs within 0.5% of the fixture run.
The small shear differences come from the fixture's back-calculated v_n (868 plf)
versus the tabulated 870 plf.
"""

import pytest

from design.engine import run_design
from design.result import OverallStatus
from woodworks_example import inputs, library
from woodworks_example import production_inputs as _production_inputs  # fixture ids -> production ids


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
