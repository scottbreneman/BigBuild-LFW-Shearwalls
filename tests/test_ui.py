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
from report import build_markdown, build_report
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


def test_report_tab_builds_a_report_from_the_example_result():
    """What the Report tab's buttons hand to st.download_button."""
    res = run_design(example_inputs(), example_library())
    html, md = build_report(res), build_markdown(res)
    assert html.startswith("<!DOCTYPE html>") and html.rstrip().endswith("</html>")
    assert isinstance(html, str) and isinstance(md, str)  # download_button takes str directly
    for text in (html, md):
        assert "Prototype output" in text
        assert "S4.shear" in text


def test_report_tab_carries_the_git_commit_the_app_stamps():
    import dataclasses

    from ui.runtime import git_commit

    res = dataclasses.replace(run_design(example_inputs(), example_library()), git_commit=git_commit() or "abc1234")
    assert res.git_commit in build_report(res)


def test_report_builds_even_when_inputs_are_invalid():
    """The tab guards on INVALID_INPUT, but the report must not raise if that guard ever moves."""
    import dataclasses

    res = run_design(dataclasses.replace(example_inputs(), b_ft=-1.0), example_library())
    assert res.status is OverallStatus.INVALID_INPUT
    assert "Fix these inputs before the engine will run checks" in build_report(res)


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
