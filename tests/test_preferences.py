"""Preferred-materials model: JSON round trip, filtering, ordering and warnings."""

import pytest

from design.components import load_library
from design.preferences import MaterialPreferences
from woodworks_example import library

DFL1 = ("Douglas Fir-Larch", "No.1", '2"-4" thick, 2" & wider')


@pytest.fixture(scope="module")
def prod():
    return load_library()


def test_json_round_trip():
    p = MaterialPreferences(name="Office", assemblies=("A", "B"), sides=(1,), lumber=(DFL1,), rods=("R",),
                            holddowns=("H",), min_posts=3, max_posts=12, notes="n")
    assert MaterialPreferences.from_json(p.to_json()) == p


def test_unknown_schema_version_rejected():
    with pytest.raises(ValueError):
        MaterialPreferences.from_dict({"schema_version": 99})


def test_empty_lists_mean_everything(prod):
    p = MaterialPreferences(sides=(1,))
    assert len(p.assembly_options(prod)) == len(prod.shear_wall_assemblies)
    assert len(p.rod_options(prod)) == len(prod.continuous_rod_systems)
    assert len(p.lumber_options(prod)) == len(prod.lumber_design_values)


def test_assembly_options_ascend_by_capacity_and_respect_sides(prod):
    ids = tuple(a.assembly_id for a in prod.shear_wall_assemblies[:6])
    opts = MaterialPreferences(assemblies=ids, sides=(1, 2)).assembly_options(prod)
    assert {a.assembly_id for a, _ in opts} == set(ids) and {n for _, n in opts} == {1, 2}
    caps = [a.v_n_plf * n for a, n in opts if a.v_n_plf is not None]
    assert caps == sorted(caps)


def test_rods_ascend_and_rows_without_values_come_last(prod):
    opts = MaterialPreferences().rod_options(prod)
    vals = [r.rod_allowable_tension_lb for r in opts]
    filled = [v for v in vals if v is not None]
    assert filled == sorted(filled)
    assert vals[len(filled):] == [None] * (len(vals) - len(filled))


def test_check_against_reports_missing_ids_and_unverified_rows(prod):
    p = MaterialPreferences(assemblies=("NOPE",), rods=("F1554-36-5/8",), min_posts=5, max_posts=2)
    warn = " | ".join(p.check_against(prod))
    assert "NOPE" in warn and "Post count range" in warn and "not verified" in warn


def test_fixture_preset_is_clean():
    p = MaterialPreferences(lumber=(DFL1,))
    warn = p.check_against(library())
    assert not any("not in the library" in w for w in warn)
