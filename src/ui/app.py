"""Streamlit app: shear wall stack inputs, results, calc trace, items to verify.

Run from the repo root:   python -m streamlit run src/ui/app.py
(Windows venv: .venv\\Scripts\\python -m streamlit run src/ui/app.py)

The UI holds no design logic. It builds ``design.inputs.DesignInputs`` from the forms, calls
``design.engine.run_design`` and displays the returned ``DesignResult`` and its calc trace.
"""

from __future__ import annotations

import base64
import dataclasses
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/
from ui.runtime import ensure_paths, git_commit  # noqa: E402

ensure_paths()

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from design.engine import run_design  # noqa: E402
from design.library import default_library  # noqa: E402
from design.result import EDITIONS, OverallStatus  # noqa: E402
from design.trace import CheckStatus  # noqa: E402
from ui import forms  # noqa: E402
from ui.graphic import stack_svg  # noqa: E402
from ui.io import inputs_from_json, inputs_to_json  # noqa: E402
from ui.trace_export import DISCLAIMER, result_to_json, result_to_markdown  # noqa: E402

SRC_EXAMPLE = "WoodWorks example components (answer-key fixtures)"
SRC_PROJECT = "Project component library (src/design/components/data)"
CATS = [("shear", "Shear"), ("aspect", "Aspect"), ("compression", "Chord comp."), ("holddown", "Hold-down"),
        ("rod", "Rod"), ("plate_bearing", "Plate bearing"), ("plate_bending", "Plate bending"), ("drift", "Drift")]

st.set_page_config(page_title="Shear Wall Stack (prototype)", layout="wide")


# ------------------------------------------------------------------ data sources and state
@st.cache_resource
def get_library(source: str):
    if source == SRC_EXAMPLE:
        import woodworks_example as ex
        return ex.library()
    return default_library()


def example_inputs():
    import woodworks_example as ex
    return ex.inputs()


def apply_inputs(inp) -> None:
    for k, v in forms.global_values_from_inputs(inp).items():
        st.session_state[f"g_{k}"] = v
    st.session_state["n_stories"] = len(inp.stories)
    st.session_state["base_frames"] = forms.frames_from_inputs(inp)
    st.session_state["ver"] = st.session_state.get("ver", 0) + 1


def on_resize() -> None:
    n = int(st.session_state["n_stories"])
    st.session_state["base_frames"] = forms.resize_frames(st.session_state["base_frames"], n)
    st.session_state["ver"] += 1


def on_load_example() -> None:
    apply_inputs(example_inputs())
    st.session_state["lib_source"] = SRC_EXAMPLE


if "base_frames" not in st.session_state:
    apply_inputs(example_inputs())
    st.session_state["lib_source"] = SRC_EXAMPLE

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("Project")
    st.text_input("Project name", key="g_project_name")
    st.radio("Component data", [SRC_EXAMPLE, SRC_PROJECT], key="lib_source",
             help="The project library is mostly 'pending' until engineers fill and verify it; checks then report "
                  "'needs input' instead of using unchecked numbers.")
    st.button("Load WoodWorks 5-story example", on_click=on_load_example, use_container_width=True)
    up = st.file_uploader("Load inputs (.json)", type="json")
    if up is not None:
        marker = (up.name, up.size)
        if st.session_state.get("last_upload") != marker:
            try:
                apply_inputs(inputs_from_json(up.getvalue().decode("utf-8")))
                st.session_state["last_upload"] = marker
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                st.error(f"Could not read inputs file: {exc}")
    st.caption("Editions: " + ", ".join(EDITIONS))

lib = get_library(st.session_state["lib_source"])
ver = st.session_state["ver"]

st.title("Light-frame wood shear wall stack")
st.warning(f"{DISCLAIMER} Source status of every value is shown; items not verified are listed under 'Items to verify'.")

tab_in, tab_res, tab_trace, tab_verify, tab_report = st.tabs(
    ["Inputs", "Results", "Calc trace", "Items to verify", "Report"])

# ------------------------------------------------------------------ inputs
with tab_in:
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("Wall and load")
        st.radio("Load type", ["seismic", "wind"], key="g_load_type", horizontal=True)
        st.number_input("Wall length b (ft)", min_value=0.0, step=0.5, key="g_b_ft")
        st.number_input("Number of stories (1 = bottom)", min_value=1, max_value=5, step=1, key="n_stories",
                        on_change=on_resize)
        st.number_input("End post width d_post (in); 0 = not given", min_value=0.0, step=0.5, key="g_d_post_in",
                        help="Default chord lever arm (decision D2). Not needed when every story has its own d_arm.")
    seismic = st.session_state["g_load_type"] == "seismic"
    with c2:
        st.subheader("Seismic" if seismic else "Wind")
        if seismic:
            st.number_input("S_DS", min_value=0.0, step=0.01, key="g_S_DS", format="%.3f")
            st.number_input("C_d", min_value=0.0, step=0.5, key="g_C_d")
            st.number_input("I_e", min_value=0.0, step=0.05, key="g_I_e")
            st.selectbox("Risk category", ["I", "II", "III", "IV"], key="g_risk_category")
            st.selectbox("Seismic design category", ["", "A", "B", "C", "D", "E", "F"], key="g_sdc")
        else:
            st.number_input("Net roof uplift on wall (plf, strength level)", min_value=0.0, step=10.0,
                            key="g_roof_uplift_plf")
            st.number_input("Wind drift limit h / ___ ; 0 = no limit applied", min_value=0.0, step=50.0,
                            key="g_wind_drift_denominator",
                            help="No code limit is applied for wind; the owner or project sets it (decision D6).")
    with c3:
        st.subheader("Engineer settings")
        st.number_input("Wood bearing amplification", min_value=1.0, step=0.05, key="g_wood_bearing_factor",
                        help="Wood-to-wood crushing amplification (example §3.4.3, engineer judgement).")
        st.checkbox("Carry rotation from lower stories into drift (D6)", key="g_carry_rotation")
        if not seismic:
            st.caption("Seismic fields are hidden for wind.")
    st.caption("Story forces F are **strength level** (E_h or W). The engine applies the ASD and drift combination "
               "factors (decision D8, revised).")

    base_loads, base_chords, base_ties = st.session_state["base_frames"]

    def opts(base: list[str], current) -> list[str]:
        vals = [v for v in base if v]
        for c in current:
            if isinstance(c, str) and c and c not in vals:
                vals.append(c)
        return vals

    asm_ids = opts([a.assembly_id for a in lib.shear_wall_assemblies], base_loads["assembly_id"])
    rod_ids = opts([r.system_id for r in lib.continuous_rod_systems], base_ties["system_id"].dropna())
    hd_models = opts([h.model for h in lib.holddowns], base_ties["model"].dropna())
    species = opts(sorted({v.species_group for v in lib.lumber_design_values}), base_chords["species_group"])
    grades = opts(sorted({v.grade for v in lib.lumber_design_values}), base_chords["grade"])
    classes = opts(sorted({v.size_class for v in lib.lumber_design_values}), base_chords["size_class"])
    posts = opts([s.nominal for s in lib.lumber_sizes], base_chords["post_nominal"])

    NC = st.column_config.NumberColumn
    SC = st.column_config.SelectboxColumn
    t_loads, t_chords, t_ties = st.tabs(["Loads and nailing", "Chord posts", "Tie-downs"])
    with t_loads:
        loads = st.data_editor(base_loads, key=f"loads_{ver}", num_rows="fixed", use_container_width=True, column_config={
            "h_ft": NC("h (ft)", min_value=0.0, step=0.5, format="%.2f"),
            "F_lb": NC("F (lb)", min_value=0.0, step=50.0, format="%.0f"),
            "w_D_plf": NC("w_D (plf)", min_value=0.0, format="%.1f"),
            "w_wall_plf": NC("w_wall (plf)", min_value=0.0, format="%.1f"),
            "w_L_plf": NC("w_L (plf)", min_value=0.0, format="%.1f"),
            "w_Lr_plf": NC("w_Lr (plf)", min_value=0.0, format="%.1f"),
            "assembly_id": SC("Nailing / assembly", options=asm_ids, required=True),
            "sides": SC("Sides", options=[1, 2], required=True),
            "panel_type": SC("Panel", options=["OSB", "Plywood"], required=True)})
    with t_chords:
        chords = st.data_editor(base_chords, key=f"chords_{ver}", num_rows="fixed", use_container_width=True, column_config={
            "n_posts": NC("Posts (n)", min_value=1, step=1, format="%d"),
            "post_nominal": SC("Post", options=posts, required=True),
            "species_group": SC("Species", options=species, required=True),
            "grade": SC("Grade", options=grades, required=True),
            "size_class": SC("Size class", options=classes, required=True),
            "chord_length_ft": NC("Chord length (ft)", min_value=0.0, step=0.125, format="%.3f"),
            "d_arm_ft": NC("d arm (ft), blank = D2 default", min_value=0.0, step=0.05, format="%.2f"),
            "d_out_of_plane_in": NC("d out-of-plane (in), blank = dressed", min_value=0.0, step=0.25),
            "top_plates_in": NC("Top plates (in)", min_value=0.0, step=0.5),
            "bottom_plate_in": NC("Bottom plate (in)", min_value=0.0, step=0.5)})
    with t_ties:
        st.caption("Rod system: fill the plate and rod fields. Hold-down: fill model or T_allow. Unused cells stay blank.")
        ties = st.data_editor(base_ties, key=f"ties_{ver}", num_rows="fixed", use_container_width=True, column_config={
            "kind": SC("Type", options=[forms.ROD, forms.HOLDDOWN], required=True),
            "system_id": SC("Rod system", options=rod_ids),
            "plate_width_in": NC("Plate w (in)", min_value=0.0, step=0.25),
            "plate_length_in": NC("Plate l (in)", min_value=0.0, step=0.25),
            "plate_thickness_in": NC("Plate t (in)", min_value=0.0, step=0.125, format="%.3f"),
            "plate_Fy_psi": NC("Plate Fy (psi)", min_value=0.0, step=1000.0, format="%.0f"),
            "slack_in": NC("Slack (in)", min_value=0.0, step=0.01, format="%.4f"),
            "takeup_elongation_in": NC("Take-up (in)", min_value=0.0, step=0.005, format="%.4f"),
            "rod_length_ft": NC("Rod length (ft), blank = story h", min_value=0.0, step=0.5),
            "model": SC("Hold-down model", options=hd_models),
            "T_allow_lb": NC("T_allow (lb)", min_value=0.0, step=100.0, format="%.0f"),
            "delta_a_in": NC("Δ_a (in)", min_value=0.0, step=0.01, format="%.3f")})

    # nailing status panel: what the library says about each chosen assembly
    rows = []
    by_id = {a.assembly_id: a for a in lib.shear_wall_assemblies}
    for story, aid in loads["assembly_id"].items():
        a = by_id.get(aid)
        rows.append({"Story": story, "Assembly": aid, "Grade": a.panel_grade if a else "?",
                     "Panel t": a.min_nominal_panel_thickness_label if a else "?",
                     "Nail": a.nail_designation if a else "?", "Edge (in)": a.edge_nail_spacing_in if a else None,
                     "Library status": a.status.value if a else "not in library"})
    with st.expander("Nailing selection: library status per story"):
        st.dataframe(pd.DataFrame(rows).set_index("Story"), use_container_width=True)

# ------------------------------------------------------------------ run the engine
g = {k: st.session_state[f"g_{k}"] for k in forms.GLOBAL_DEFAULTS}
inp = forms.build_inputs(g, loads, chords, ties)
res, run_error = None, None
try:
    res = dataclasses.replace(run_design(inp, lib), git_commit=git_commit())
except Exception:  # noqa: BLE001  (surface engine bugs instead of a blank page)
    run_error = traceback.format_exc()

with st.sidebar:
    st.download_button("Download inputs (.json)", inputs_to_json(inp), file_name="shearwall_inputs.json",
                       mime="application/json", use_container_width=True)

# ------------------------------------------------------------------ results
with tab_res:
    if run_error:
        st.error("The design engine raised an error. Send this to the calc builder.")
        st.code(run_error)
    elif res.status is OverallStatus.INVALID_INPUT:
        st.error("Fix these inputs before the engine will run checks:")
        st.table(pd.DataFrame([{"Field": e.field, "Problem": e.message} for e in res.input_errors]))
    else:
        banner = {OverallStatus.PASS: st.success, OverallStatus.FAIL: st.error, OverallStatus.INCOMPLETE: st.warning}
        label = {OverallStatus.PASS: "All checks pass", OverallStatus.FAIL: "One or more checks FAIL",
                 OverallStatus.INCOMPLETE: "Incomplete: some checks need engineer input or component data"}
        banner[res.status](label[res.status])
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Governing story", res.governing_story or "-")
        m2.metric("Governing check", (res.governing_check or "-"))
        m3.metric("Max DCR", "-" if res.max_dcr is None else f"{res.max_dcr:.3f}")
        m4.metric("Unverified steps", len(res.unverified_steps))

        left, right = st.columns([3, 2])
        table = []
        for s in res.stories:
            row = {"Story": s.story}
            for cat, lab in CATS:
                chk = [c for c in s.checks if c.category == cat]
                if not chk:
                    row[lab] = "-"
                    continue
                c = chk[0]
                row[lab] = {CheckStatus.NEEDS_INPUT: "needs input", CheckStatus.INFO: "info",
                            CheckStatus.NOT_APPLICABLE: "n/a"}.get(c.status, f"{c.dcr:.2f}" if c.dcr is not None else "-")
            row["Governing"] = (s.governing_id or "-").split(".", 1)[-1]
            row["Max DCR"] = "-" if s.max_dcr is None else f"{s.max_dcr:.2f}"
            table.append(row)
        df = pd.DataFrame(table).set_index("Story")

        def colour(v):
            try:
                x = float(v)
            except (TypeError, ValueError):
                return "background-color:#E4E7EB" if v == "needs input" else ""
            return ("background-color:#F8CFCF" if x > 1 else "background-color:#FFF0C2" if x > 0.9
                    else "background-color:#DFF3E4")

        with left:
            st.subheader("Demand / capacity by story")
            st.dataframe(df.style.map(colour, subset=[lab for _, lab in CATS] + ["Max DCR"]), use_container_width=True)
            st.caption("Green ≤ 0.90, amber 0.90 to 1.00, red above 1.00, grey = needs input. Story 1 is the bottom.")
            if res.needs_input:
                st.subheader("Needs engineer input")
                st.dataframe(pd.DataFrame([{"Check": n.check_id, "Decision / data": n.decision, "Message": n.message}
                                           for n in res.needs_input]), use_container_width=True, hide_index=True)
        with right:
            st.subheader("Wall stack")
            b64 = base64.b64encode(stack_svg(inp, res).encode()).decode()
            st.markdown(f'<img style="width:100%" src="data:image/svg+xml;base64,{b64}"/>', unsafe_allow_html=True)

# ------------------------------------------------------------------ calc trace
with tab_trace:
    if res is None or res.status is OverallStatus.INVALID_INPUT:
        st.info("Run needs valid inputs first.")
    else:
        story = st.selectbox("Story", [s.story for s in res.stories])
        render_eq = st.checkbox("Render equations (slower)", value=False)

        def show_steps(steps):
            if render_eq:
                for s in steps:
                    st.latex(s.equation_latex)
                    st.caption(f"{s.substitution}  =  {s.value} {s.unit}  ·  {s.citation}  ·  {s.status}  ·  {s.id}")
            else:
                st.dataframe(pd.DataFrame([{"Step": s.id, "Name": s.name, "Symbol": s.symbol,
                                            "Equation": s.equation_latex, "Substitution": s.substitution,
                                            "Value": str(s.value), "Unit": s.unit, "Citation": s.citation,
                                            "Status": s.status, "Note": s.note} for s in steps]),
                             use_container_width=True, hide_index=True)

        for c in res.stories[story - 1].checks:
            dcr = "" if c.dcr is None else f" · DCR {c.dcr:.3f}"
            with st.expander(f"{c.id} · {c.name} · {c.status.value}{dcr}"):
                if c.message:
                    st.info(c.message + (f" ({c.decision})" if c.decision else ""))
                if c.steps:
                    show_steps(c.steps)
        with st.expander("Stack: load combinations, story forces, chord forces"):
            show_steps(res.stack_steps)

# ------------------------------------------------------------------ items to verify
with tab_verify:
    st.subheader("Component library status")
    counts = pd.DataFrame(lib.status_counts()).T.fillna(0).astype(int)
    st.dataframe(counts, use_container_width=True)
    if res is not None and res.status is not OverallStatus.INVALID_INPUT:
        st.subheader("Component rows used with status 'memory'")
        st.write(list(res.component_items_to_verify) or "none")
        st.subheader("Calculation steps not verified or statics")
        st.write(f"{len(res.unverified_steps)} steps")
        if res.unverified_steps:
            st.dataframe(pd.DataFrame([{"Step": s.id, "Name": s.name, "Citation": s.citation, "Status": s.status}
                                       for s in res.unverified_steps]), use_container_width=True, hide_index=True)

# ------------------------------------------------------------------ report
with tab_report:
    st.info("Interim downloads. The report generator (docs/spec-io.md §6) will replace the Markdown file.")
    if res is None or res.status is OverallStatus.INVALID_INPUT:
        st.write("Run needs valid inputs first.")
    else:
        st.download_button("Calc trace (.md)", result_to_markdown(res), file_name="shearwall_calc_trace.md",
                           mime="text/markdown")
        st.download_button("Full result (.json)", result_to_json(res), file_name="shearwall_result.json",
                           mime="application/json")
    st.download_button("Inputs (.json)", inputs_to_json(inp), file_name="shearwall_inputs.json",
                       mime="application/json", key="dl_inputs_report")
