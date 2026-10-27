"""UI tests: inputs round-trip, two-load-case envelope, export, graphics, and the Streamlit app driven headlessly."""

from pathlib import Path

from woodworks_example import inputs as seismic_example
from woodworks_example import library as example_library

from design.engine import run_design
from design.result import OverallStatus
from ui import forms
from ui.example import example_cases
from ui.fbd import fbd_svg
from ui.graphic import stack_svg
from ui.io import cases_from_json, cases_to_json, inputs_from_json, inputs_to_json
from ui.loadcases import run_cases
from ui.theme import checks_panel_html, schedule_html
from ui.trace_export import result_to_json, result_to_markdown

APP = str(Path(__file__).resolve().parents[1] / "src" / "ui" / "app.py")


# ---------------------------------------------------------------- data layer
def test_single_inputs_json_round_trip():
    inp = seismic_example()
    assert inputs_from_json(inputs_to_json(inp)) == inp


def test_two_case_json_round_trip_and_v1_fallback():
    cases = example_cases()
    assert cases_from_json(cases_to_json(cases)) == cases
    only = cases_from_json(inputs_to_json(seismic_example()))   # an old single-case file still loads
    assert list(only) == ["seismic"]


def test_example_has_seismic_and_wind_forces():
    cases = example_cases()
    assert [s.F_lb for s in cases["wind"].stories] == [2259, 2360, 2439, 2504, 3033]  # example Table 4.6
    assert cases["wind"].roof_uplift_plf == 82.7 and cases["wind"].wind_drift_limit_ratio == 1 / 400


def test_frames_round_trip_both_cases():
    cases = example_cases()
    g = forms.global_values_from_cases(cases)
    loads, chords, ties = forms.frames_from_cases(cases)
    assert list(loads.columns[:3]) == ["h_ft", "F_seismic_lb", "F_wind_lb"]
    assert forms.build_cases(g, loads, chords, ties) == cases


def test_zero_forces_skip_a_load_case():
    cases = example_cases()
    g = forms.global_values_from_cases(cases)
    loads, chords, ties = forms.frames_from_cases(cases)
    loads["F_wind_lb"] = 0.0
    assert list(forms.build_cases(g, loads, chords, ties)) == ["seismic"]
    loads["F_seismic_lb"] = 0.0
    assert forms.build_cases(g, loads, chords, ties) == {}


def test_resize_frames_grows_and_shrinks():
    frames = forms.frames_from_cases(example_cases())
    for n in (3, 5):
        assert all(len(f) == n for f in forms.resize_frames(frames, n))
    assert all(len(f) == 5 for f in forms.resize_frames(forms.resize_frames(frames, 2), 5))


# ---------------------------------------------------------------- envelope of the two load cases
def test_envelope_reports_governing_case_per_story_and_matches_engine():
    cs = run_cases(example_cases(), example_library())
    assert cs.valid and cs.status is OverallStatus.PASS and cs.cases == ["seismic", "wind"]
    dcr, case, story, chk = cs.overall()
    assert (case, story, chk) == ("seismic", 4, "S4.shear") and abs(dcr - 0.9721) < 1e-3
    seismic_only = run_design(seismic_example(), example_library())
    assert seismic_only.max_dcr == dcr                      # seismic governs the whole example
    assert all(cs.story_dcr(i)[1] == "seismic" for i in range(1, 6))
    assert cs.both(1, ("shear",))["wind"] < cs.both(1, ("shear",))["seismic"]


def test_a_large_wind_force_governs_and_fails():
    cases = example_cases()
    import dataclasses as dc
    stories = tuple(dc.replace(s, F_lb=s.F_lb * 20) for s in cases["wind"].stories)
    cases["wind"] = dc.replace(cases["wind"], stories=stories)
    cs = run_cases(cases, example_library())
    assert cs.status is OverallStatus.FAIL and cs.overall()[1] == "wind"
    assert cs.story_dcr(1)[1] == "wind"


# ---------------------------------------------------------------- exports and drawings
def test_exports_and_graphics():
    cs = run_cases(example_cases(), example_library())
    res = cs.results["seismic"]
    assert "S4.shear" in result_to_markdown(res) and '"status": "pass"' in result_to_json(res)
    svg = stack_svg(cs.primary, None, selected=4, story_dcrs={i: cs.story_dcr(i)[0] for i in range(1, 6)},
                    force_lines={i: ["E = 1 lb", "W = 2 lb"] for i in range(1, 6)})
    assert svg.startswith("<svg") and svg.count("Story ") == 5 and "DCR 0.97" in svg
    assert stack_svg(cs.primary, None).endswith("</svg>")
    out = fbd_svg(story=4, b_ft=29.0, h_ft=10.0, V=cs.num("seismic", "S4.statics.V"), v=cs.num("seismic", "S4.shear.v"),
                  w_dl=cs.num("seismic", "S4.statics.w_D"), T=cs.num("seismic", "S4.chord.asd.T"),
                  C=res.check("S4.comp").demand, tie_label="rod")
    assert "18,526" in out and "T = 2,833 lb" in out


def test_schedule_and_check_panel_html():
    cs = run_cases(example_cases(), example_library())
    sched = schedule_html(cs, 5, selected=4)
    assert sched.count("<tr") == 6 and "Seismic" in sched and 'class="chip S"' in sched
    panel = checks_panel_html(cs, 4)
    assert "Sheathing shear" in panel and "Tie-down tension" in panel and "0.97" in panel


# ---------------------------------------------------------------- the app, driven headlessly
def _app():
    from streamlit.testing.v1 import AppTest
    return AppTest.from_file(APP, default_timeout=60)


def test_app_runs_example_and_passes():
    at = _app().run()
    assert not at.exception, at.exception
    assert any("All checks pass" in s.value for s in at.success)


def test_app_has_cards_kpis_fbd_checks_and_schedule():
    at = _app().run()
    assert not at.exception, at.exception
    html = " ".join(m.value for m in at.markdown)
    assert "Shear Wall Stack Designer" in html and 'class="kpis"' in html and "Governing Load Case" in html
    assert "Shear wall: story 1" in html and "Capacities and checks: story 1" in html
    assert 'class="checks"' in html and 'class="sched"' in html and "Wall stack summary" in html
    assert "data:image/svg+xml;base64," in html


def test_app_blank_length_is_reported_not_crashed():
    at = _app().run()
    at.number_input(key="g_b_ft").set_value(0.0).run()
    assert not at.exception, at.exception
    assert any("Fix these" in e.value for e in at.error)


PROJECT, FIXTURES = "Project component library", "WoodWorks example components"


def test_app_defaults_to_the_project_library():
    at = _app().run()
    assert at.selectbox(key="lib_source").value == PROJECT
    assert at.session_state["prefs"].name == "WoodWorks example materials (project library)"
    assert any("All checks pass" in s.value for s in at.success)  # the example on the production tables


def test_app_fixture_source_loads_its_own_example_and_preset():
    at = _app().run()
    at.selectbox(key="lib_source").set_value(FIXTURES).run()
    assert at.session_state["prefs"].name == "WoodWorks example (answer-key fixtures)"
    next(b for b in at.button if b.label == "Load WoodWorks 5-story example").click().run()
    assert not at.exception, at.exception
    assert any("All checks pass" in s.value for s in at.success)
    loads, _, _ = at.session_state["base_frames"]
    assert all(a.startswith("EX-") for a in loads["assembly_id"])


def test_app_story_count_and_story_selection_do_not_crash():
    at = _app().run()
    at.selectbox(key="n_stories").set_value(3).run()
    assert not at.exception, at.exception
    at.selectbox(key="sel_story").set_value(3).run()
    assert not at.exception, at.exception
    assert "Shear wall: story 3" in " ".join(m.value for m in at.markdown)


def test_app_large_wind_force_makes_wind_govern():
    at = _app().run()
    ver = at.session_state["ver"]
    at.number_input(key=f"w{ver}_1_F_wind_lb").set_value(80000.0).run()
    assert not at.exception, at.exception
    assert any("FAIL" in e.value for e in at.error)
    assert "Wind" in " ".join(m.value for m in at.markdown if "kpi" in m.value)


def test_app_single_load_case_still_works():
    at = _app().run()
    ver = at.session_state["ver"]
    at.number_input(key=f"w{ver}_1_F_wind_lb").set_value(0.0).run()
    frames = at.session_state["base_frames"]
    for story in range(2, 6):
        frames[0].at[story, "F_wind_lb"] = 0.0
    at.run()
    assert not at.exception, at.exception
    assert any("All checks pass" in s.value for s in at.success)


# ---------------------------------------------------------------- report button, engineering basis, restored fields
def test_reports_wrapper_builds_html_and_markdown_per_case():
    from ui import reports
    cs = run_cases(example_cases(), example_library())
    assert reports.choices(cs) == ["Governing (auto)", "Seismic", "Wind"]
    assert reports.pick_case(cs, "Governing (auto)") == "seismic" and reports.pick_case(cs, "Wind") == "wind"
    html, md = reports.html_report(cs, "wind"), reports.markdown_report(cs, "seismic")
    assert html.startswith("<!DOCTYPE html>") and "Wood shear wall design report" in html
    assert "Items to verify" in md and reports.file_stem(cs, "wind").endswith("_wind")


def test_app_has_report_button_and_all_tabs():
    at = _app().run()
    assert not at.exception, at.exception
    top = ["Design", "Materials", "Calc trace", "Engineering basis", "Items to verify", "Report"]
    assert [t.label for t in at.tabs if t.label in top] == top  # the Materials tab also has its own sub-tabs
    labels = [getattr(b, "label", "") or str(b.proto.label) for b in at.get("download_button")]
    assert any(l.startswith("Calculation report") for l in labels), labels
    assert any(l == "Report (HTML)" for l in labels) and any(l == "Report (Markdown)" for l in labels)


def test_app_basis_tab_shows_factors_combinations_and_all_tables():
    at = _app().run()
    html = " ".join(m.value for m in at.markdown)
    assert "Code factors used by the checks" in html and "Load combinations and ASD factors" in html
    assert "Stack forces, overturning and chord forces" in html and "Component tables" in html
    # every engine Factor constant is listed in one of the dataframes
    from design import factors
    names = {k for k, v in vars(factors).items() if isinstance(v, factors.Factor)}
    seen = set()
    for df in at.dataframe:
        v = df.value
        if "Factor" in getattr(v, "columns", []):
            seen |= set(v["Factor"])
    assert names <= seen


def test_app_exposes_every_chord_field_the_engine_accepts():
    at = _app().run()
    ver = at.session_state["ver"]
    for col in ("n_posts", "chord_length_ft", "d_arm_ft", "d_out_of_plane_in", "top_plates_in", "bottom_plate_in"):
        at.number_input(key=f"w{ver}_1_{col}")           # raises if the widget is missing
    for col in ("post_nominal", "species_group", "grade", "size_class"):
        at.selectbox(key=f"w{ver}_1_{col}")


def test_app_exposes_every_design_input_field():
    """Every field of the engine's input dataclasses is reachable from the form (directly or via a settings widget)."""
    import dataclasses as dc
    from design.inputs import ChordSpec, DesignInputs, GenericHoldDown, RodSystem, StoryInput
    covered_top = {"load_type", "stories", "b_ft", "S_DS", "C_d", "I_e", "risk_category", "sdc", "d_post_in", "roof_uplift_plf",
                   "wind_drift_limit_ratio", "wood_bearing_factor", "carry_rotation", "project_name",
                   "deflection_method", "framing_moisture", "restraint_each_level"}
    assert {f.name for f in dc.fields(DesignInputs)} <= covered_top
    form = set(forms.LOAD_COLS) | set(forms.CHORD_COLS) | set(forms.TIE_COLS)
    story_fields = {f.name for f in dc.fields(StoryInput)} - {"F_lb", "chord", "tiedown"}
    assert story_fields <= form
    assert {f.name for f in dc.fields(ChordSpec)} <= form
    assert {f.name for f in dc.fields(RodSystem)} <= form | {"system_id"}
    assert {f.name for f in dc.fields(GenericHoldDown)} <= form | {"model"}


def test_new_engine_options_round_trip_and_reach_the_engine():
    import dataclasses as dc
    cases = example_cases()
    g = forms.global_values_from_cases(cases)
    g.update(deflection_method="4-term", framing_moisture="green", restraint_each_level=False)
    loads, chords, ties = forms.frames_from_cases(cases)
    ties.loc[2, "takeup_device"] = False
    ties.loc[2, "shrinkage_in"] = 0.1
    ties.loc[2, "bearing_hole_in"] = 0.25
    built = forms.build_cases(g, loads, chords, ties)["seismic"]
    assert (built.deflection_method, built.framing_moisture, built.restraint_each_level) == ("4-term", "green", False)
    rod = built.stories[1].tiedown
    assert (rod.takeup_device, rod.shrinkage_in, rod.bearing_hole_in) == (False, 0.1, 0.25)
    assert dc.replace(built, project_name="x") != built
    assert cases_from_json(cases_to_json({"seismic": built}))["seismic"] == built      # survives save and load


def test_app_new_engine_options_do_not_crash():
    at = _app().run()
    at.selectbox(key="g_deflection_method").set_value("4-term").run()
    assert not at.exception, at.exception
    at.checkbox(key="g_restraint_each_level").set_value(False).run()
    assert not at.exception, at.exception


# ---------------------------------------------------------------- preferred materials and auto-size
def test_project_file_carries_preferences_and_files_without_them_still_load():
    import json

    from design.preferences import MaterialPreferences
    from ui.io import preferences_from_project

    cases = example_cases()
    prefs = MaterialPreferences(name="Office", rods=("R1",))
    text = cases_to_json(cases, prefs)
    assert cases_from_json(text) == cases and preferences_from_project(text) == prefs
    plain = cases_to_json(cases)
    assert "material_preferences" not in json.loads(plain) and preferences_from_project(plain) is None
    single = inputs_to_json(seismic_example())  # v1 single-case file
    assert preferences_from_project(single) is None


def test_example_cases_on_the_production_library_pass_both_load_cases():
    cs = run_cases(example_cases(production=True), None)  # None = default (production) library
    assert all(r.status is OverallStatus.PASS for r in cs.results.values())


def test_shipped_presets_load():
    from design.preferences import MaterialPreferences

    files = sorted((Path(APP).parents[2] / "presets").glob("*.json"))
    assert len(files) >= 3
    for f in files:
        assert MaterialPreferences.from_json(f.read_text(encoding="utf-8")).name


def test_app_materials_tab_and_autosize_apply_for_both_load_cases():
    at = _app().run()
    assert not at.exception, at.exception
    assert any("Down-select the component library" in c.value for c in at.caption)
    assert at.toggle(key="show_all").value is False
    at.button(key="autosize_run").click().run()
    assert not at.exception, at.exception
    prop = at.session_state["autosize"]["result"]
    assert set(prop.proposed_cases) == {"seismic", "wind"}
    for res in prop.result_cases.values():  # strength checks pass in every load case
        for i in range(1, 6):
            for c in ("shear", "comp", "rod"):
                assert res.check(f"S{i}.{c}").status.value == "pass"
    apply = at.button(key="autosize_apply")
    assert not apply.disabled
    apply.click().run()
    assert not at.exception, at.exception
    assert "autosize" not in at.session_state
    _, chords, _ = at.session_state["base_frames"]
    assert set(chords["layout"]) == {"example"}  # posts now follow the layout rule
