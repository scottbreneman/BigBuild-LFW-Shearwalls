"""UI smoke tests: inputs round-trip, trace export, and the Streamlit app driven headlessly."""

from pathlib import Path

import pytest
from woodworks_example import inputs as example_inputs
from woodworks_example import library as example_library

from design.engine import run_design
from design.result import OverallStatus
from ui import forms
from ui.graphic import stack_svg
from ui.io import inputs_from_json, inputs_to_json
from ui.trace_export import result_to_json, result_to_markdown

APP = str(Path(__file__).resolve().parents[1] / "src" / "ui" / "app.py")


def test_inputs_json_round_trip():
    inp = example_inputs()
    assert inputs_from_json(inputs_to_json(inp)) == inp


def test_frames_round_trip_matches_example():
    inp = example_inputs()
    g = forms.global_values_from_inputs(inp)
    loads, chords, ties = forms.frames_from_inputs(inp)
    assert forms.build_inputs(g, loads, chords, ties) == inp


def test_resize_frames_grows_and_shrinks():
    frames = forms.frames_from_inputs(example_inputs())
    for n in (3, 5):
        assert all(len(f) == n for f in forms.resize_frames(frames, n))
    assert all(len(f) == 5 for f in forms.resize_frames(forms.resize_frames(frames, 2), 5))


def test_exports_and_graphic_from_example_result():
    inp = example_inputs()
    res = run_design(inp, example_library())
    assert res.status is OverallStatus.PASS
    md = result_to_markdown(res)
    assert "S4.shear" in md and "Prototype output" in md
    assert '"status": "pass"' in result_to_json(res)
    svg = stack_svg(inp, res)
    assert svg.startswith("<svg") and svg.count("Story ") == 5


def test_graphic_works_without_result():
    assert stack_svg(example_inputs(), None).endswith("</svg>")


def _app():
    from streamlit.testing.v1 import AppTest
    return AppTest.from_file(APP, default_timeout=60)


def test_app_runs_example_and_passes():
    at = _app().run()
    assert not at.exception, at.exception
    assert any("All checks pass" in s.value for s in at.success)


def test_app_blank_length_is_reported_not_crashed():
    at = _app().run()
    at.number_input(key="g_b_ft").set_value(0.0).run()
    assert not at.exception, at.exception
    assert any("Fix these inputs" in e.value for e in at.error)


def test_app_project_library_is_incomplete_not_pass():
    at = _app().run()
    at.radio(key="lib_source").set_value("Project component library (src/design/components/data)").run()
    assert not at.exception, at.exception
    assert not any("All checks pass" in s.value for s in at.success)
    assert any("Incomplete" in w.value for w in at.warning)


# --- preferred materials and auto-size -----------------------------------------------------------


def test_project_json_v2_carries_preferences_and_v1_still_loads():
    import json

    from design.preferences import MaterialPreferences
    from ui.io import preferences_from_project

    inp = example_inputs()
    prefs = MaterialPreferences(name="Office", rods=("R1",))
    text = inputs_to_json(inp, prefs)
    assert inputs_from_json(text) == inp and preferences_from_project(text) == prefs
    v1 = json.loads(inputs_to_json(inp))
    v1["schema_version"] = 1
    assert inputs_from_json(json.dumps(v1)) == inp and preferences_from_project(json.dumps(v1)) is None


def test_shipped_presets_load():
    from design.preferences import MaterialPreferences

    files = sorted((Path(APP).parents[2] / "presets").glob("*.json"))
    assert files
    for f in files:
        assert MaterialPreferences.from_json(f.read_text(encoding="utf-8")).name


def test_app_materials_tab_and_autosize_apply():
    at = _app().run()
    assert not at.exception, at.exception
    assert any("Down-select the component library" in c.value for c in at.caption)
    assert at.toggle(key="show_all").value is False
    at.button(key="autosize_run").click().run()
    assert not at.exception, at.exception
    apply = at.button(key="autosize_apply")
    assert not apply.disabled
    apply.click().run()
    assert not at.exception, at.exception
    assert "autosize" not in at.session_state
    loads, chords, ties = at.session_state["base_frames"]
    assert set(chords["layout"]) == {"example"}  # posts now follow the layout rule
