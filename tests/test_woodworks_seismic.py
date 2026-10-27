"""Answer key: WoodWorks five-story over-podium example, seismic shear wall (§3.3-3.4).

Expected values are read from the example's printed tables (page numbers are
printed pages; PDF page = printed + 6). Lists run bottom to top: story 1 is
the example's "3rd" wall, story 5 its "Roof" wall.

Tolerance (decision D7, provisional until the engineers set it): 1% relative,
or 0.6 of the last printed digit, whichever is larger, to absorb the
example's rounding. Matching the example is a regression benchmark, not
engineering validation.
"""

import pytest

from design.engine import run_design
from design.result import OverallStatus
from design.trace import CheckStatus
from woodworks_example import inputs, library

STORIES = range(1, 6)


@pytest.fixture(scope="module")
def result():
    return run_design(inputs(), library())


def approx(expected, digits):
    return pytest.approx(expected, rel=0.01, abs=0.6 * 10**-digits)


def assert_steps(result, key, expected, digits, scale=1.0):
    got = [result.step(f"S{i}.{key}").value / scale for i in STORIES]
    assert got == [approx(e, digits) for e in expected], f"{key}: got {[round(g, digits + 1) for g in got]}"


def assert_checks(result, check, attr, expected, digits, scale=1.0):
    got = [getattr(result.check(f"S{i}.{check}"), attr) / scale for i in STORIES]
    assert got == [approx(e, digits) for e in expected], f"{check}.{attr}: got {got}"


def test_runs_clean(result):
    assert result.input_errors == ()
    assert result.needs_input == ()
    assert result.status is OverallStatus.PASS


def test_table_3_5_shear_p30(result):
    assert_steps(result, "shear.v", [778, 723, 612, 447, 227], 0)
    assert_steps(result, "shear.v_allow", [920, 770, 770, 460, 310], 0)


def test_table_3_6_overturning_p31(result):
    assert_steps(result, "statics.M_OT", [1154.5, 832.3, 533.0, 279.2, 94.0], 1, scale=1000)
    assert_steps(result, "chord.C_E", [42.81, 30.63, 19.45, 10.10, 3.39], 2, scale=1000)


def test_table_3_8_compression_demand_p33(result):
    assert_steps(result, "chord.P_D", [5.29, 3.46, 1.99, 0.89, 0.20], 2, scale=1000)
    assert_checks(result, "comp", "demand", [36.15, 25.48, 15.94, 8.11, 2.60], 2, scale=1000)


def test_section_3_3_5_column_p34(result):
    s1 = result.check("S1.comp")
    steps = {s.id.split(".")[-1]: s.value for s in s1.steps}
    assert steps["l_e"] == approx(115.5, 1)
    assert steps["FcE"] == approx(468, 0)
    assert steps["Fc_star"] == approx(2760, 0)
    assert steps["C_P"] == approx(0.16, 2)
    assert steps["Fc_p"] == approx(450, 0)


def test_table_3_9_compression_capacity_p35(result):
    assert_checks(result, "comp", "capacity", [37.84, 30.74, 23.65, 16.55, 14.19], 2, scale=1000)
    assert_checks(result, "comp", "dcr", [0.96, 0.83, 0.67, 0.49, 0.18], 2)


def test_table_3_10_tension_p36(result):
    assert_steps(result, "chord.M_R", [889.8, 683.7, 477.7, 271.6, 65.6], 1, scale=1000)
    assert_steps(result, "chord.asd.net", [-424.5, -287.8, -167.1, -78.3, -37.5], 1, scale=1000)
    assert_steps(result, "chord.asd.T", [15.742, 10.591, 6.099, 2.833, 1.351], 3, scale=1000)
    assert_steps(result, "chord.dT", [5.151, 4.492, 3.266, 1.482, 1.351], 3, scale=1000)


def test_table_3_11_rods_p37(result):
    assert_checks(result, "rod", "capacity", [21.62, 17.08, 9.61, 6.67, 6.67], 2, scale=1000)
    assert_checks(result, "rod", "dcr", [0.73, 0.62, 0.63, 0.42, 0.20], 2)


def test_table_3_12_bearing_plates_p38(result):
    assert_steps(result, "plate_brg.A_brg", [10.65, 10.89, 9.81, 8.48, 8.48], 2)
    assert_steps(result, "plate_brg.C_b", [1.09, 1.09, 1.11, 1.13, 1.13], 2)
    assert_checks(result, "plate_brg", "capacity", [7.278, 7.446, 6.788, 5.964, 5.964], 3, scale=1000)
    assert_checks(result, "plate_brg", "dcr", [0.71, 0.60, 0.48, 0.25, 0.23], 2)


def test_plate_bending_level_3_p38(result):
    c = result.check("S1.plate_bend")
    assert c.demand == approx(2903, 0)
    assert c.capacity == approx(3816, 0)
    assert result.step("S1.plate_bend.Z").value == approx(0.177, 3)


def test_table_3_13_drift_forces_p40(result):
    assert_steps(result, "chord.drift.net", [-568.4, -381.9, -218.3, -100.3, -50.8], 1, scale=1000)
    assert_steps(result, "chord.drift.T", [21.075, 14.052, 7.966, 3.627, 1.829], 3, scale=1000)
    assert_steps(result, "chord.dT_drift", [7.023, 6.086, 4.339, 1.797, 1.829], 3, scale=1000)
    assert_steps(result, "drift.v", [1111, 1032, 875, 639, 324], 0)


def test_table_3_14_crushing_p45(result):
    def total(i):
        return sum(s.value for s in result.check(f"S{i}.drift").steps
                   if s.id.split(".")[-1] in ("crush_bot", "crush_sh", "crush_top"))
    got = [total(i) for i in STORIES]
    assert got == [approx(e, 3) for e in [0.046, 0.100, 0.078, 0.052, 0.021]]


def test_tables_3_15_to_3_17A_chord_deformation_p46_47(result):
    assert_steps(result, "drift.rod", [0.114, 0.096, 0.099, 0.066, 0.033], 3)
    assert_steps(result, "drift.crush_plate", [0.047, 0.032, 0.019, 0.009, 0.009], 3)
    assert_steps(result, "drift.delta_a", [0.289, 0.309, 0.272, 0.199, 0.131], 3)


def test_table_3_18_deflection_p48(result):
    assert_steps(result, "drift.d1", [0.002, 0.002, 0.003, 0.003, 0.002], 3)
    assert_steps(result, "drift.d2", [0.185, 0.199, 0.168, 0.213, 0.147], 3)
    assert_steps(result, "drift.d3", [0.100, 0.107, 0.094, 0.069, 0.045], 3)
    assert_steps(result, "drift.delta_sw", [0.287, 0.307, 0.265, 0.284, 0.194], 3)


def test_table_3_19_story_drift_p50(result):
    assert_checks(result, "drift", "demand", [1.15, 1.23, 1.06, 1.14, 0.78], 2)
    assert_checks(result, "drift", "capacity", [2.40] * 5, 2)
    assert all(result.check(f"S{i}.drift").status is CheckStatus.PASS for i in STORIES)


def test_governing_check(result):
    # Highest DCR in the stack: story 4 ("6th") sheathing shear, 447/460.
    assert result.governing_check == "S4.shear"
    assert result.governing_story == 4
    assert result.max_dcr == approx(0.97, 2)
