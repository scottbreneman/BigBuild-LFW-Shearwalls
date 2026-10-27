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
from ui.runtime import ensure_paths, git_commit, repo_root  # noqa: E402

ensure_paths()

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from design.autosize import autosize  # noqa: E402
from design.engine import run_design  # noqa: E402
from design.library import default_library  # noqa: E402
from design.preferences import MaterialPreferences  # noqa: E402
from design.result import EDITIONS, OverallStatus  # noqa: E402
from design.trace import CheckStatus  # noqa: E402
from ui import forms  # noqa: E402
from ui.graphic import stack_svg  # noqa: E402
from ui.io import inputs_from_json, inputs_to_json, preferences_from_project  # noqa: E402
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


def shipped_presets() -> dict[str, Path]:
    """Preset files in presets/ (shipped with the app), keyed by their display name."""
    out = {}
    for f in sorted((repo_root() / "presets").glob("*.json")):
        try:
            out[MaterialPreferences.from_json(f.read_text(encoding="utf-8")).name or f.stem] = f
        except Exception:  # noqa: BLE001  (a broken preset file must not stop the app)
            continue
    return out


def example_preset() -> MaterialPreferences:
    f = repo_root() / "presets" / "woodworks-example.json"
    return MaterialPreferences.from_json(f.read_text(encoding="utf-8")) if f.exists() else MaterialPreferences()


def apply_prefs(prefs: MaterialPreferences) -> None:
    st.session_state["prefs"] = prefs
    st.session_state["prefs_ver"] = st.session_state.get("prefs_ver", 0) + 1
    st.session_state.pop("autosize", None)


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
if "prefs" not in st.session_state:
    apply_prefs(example_preset())

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
                text = up.getvalue().decode("utf-8")
                apply_inputs(inputs_from_json(text))
                saved = preferences_from_project(text)
                if saved is not None:
                    apply_prefs(saved)
                st.session_state["last_upload"] = marker
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                st.error(f"Could not read inputs file: {exc}")
    st.caption("Editions: " + ", ".join(EDITIONS))

lib = get_library(st.session_state["lib_source"])
ver = st.session_state["ver"]

st.title("Light-frame wood shear wall stack")
st.warning(f"{DISCLAIMER} Source status of every value is shown; items not verified are listed under 'Items to verify'.")

tab_in, tab_mat, tab_res, tab_trace, tab_verify, tab_report = st.tabs(
    ["Inputs", "Materials", "Results", "Calc trace", "Items to verify", "Report"])

# ------------------------------------------------------------------ materials (preferred lists)
def pick_table(rows: list[dict], id_col: str, chosen, key: str) -> list:
    """Library rows with a 'Use' check column; returns the ticked ids in library order.

    Preferred ids not in this library (e.g. another data source) are kept, not dropped.
    """
    if not rows:
        st.caption("No rows in this library.")
        return [c for c in chosen]
    df = pd.DataFrame(rows)
    df.insert(0, "Use", df[id_col].isin(list(chosen)))
    out = st.data_editor(df, key=key, hide_index=True, use_container_width=True,
                         disabled=[c for c in df.columns if c != "Use"])
    here = set(df[id_col])
    return [c for c in chosen if c not in here] + list(out.loc[out["Use"], id_col])


def on_load_shipped_preset() -> None:
    path = shipped_presets().get(st.session_state.get("preset_pick"))
    if path is not None:
        apply_prefs(MaterialPreferences.from_json(path.read_text(encoding="utf-8")))


LUMBER_SEP = " | "

with tab_mat:
    prefs: MaterialPreferences = st.session_state["prefs"]
    pv = st.session_state["prefs_ver"]
    st.caption("Down-select the component library to the materials you prefer. The input dropdowns show only "
               "preferred options (unless 'Show all library options' is on), and **Auto-size** on the Inputs tab "
               "proposes the lightest preferred option that passes. An empty selection means no restriction. "
               "Row status is shown; unverified rows may be preferred and are flagged in the results.")
    pc1, pc2, pc3 = st.columns([2, 2, 2])
    presets = shipped_presets()
    with pc1:
        st.selectbox("Shipped presets", list(presets) or ["(none)"], key="preset_pick")
        st.button("Load shipped preset", on_click=on_load_shipped_preset, disabled=not presets)
    with pc2:
        pup = st.file_uploader("Load a preset (.json)", type="json", key="preset_upload")
        if pup is not None and st.session_state.get("last_preset_upload") != (pup.name, pup.size):
            try:
                apply_prefs(MaterialPreferences.from_json(pup.getvalue().decode("utf-8")))
                st.session_state["last_preset_upload"] = (pup.name, pup.size)
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                st.error(f"Could not read preset: {exc}")
    with pc3:
        p_name = st.text_input("Preset name", value=prefs.name, key=f"p_name_{pv}")

    m_asm, m_lum, m_rod, m_hd = st.tabs(["Sheathing and nailing", "Lumber and posts", "Rod systems", "Hold-downs"])
    with m_asm:
        sc1, sc2 = st.columns(2)
        p_sides = sc1.multiselect("Sheathed sides auto-size may use", [1, 2], default=list(prefs.sides),
                                  key=f"p_sides_{pv}")
        p_panels = sc2.multiselect("Panel type (the first is used by auto-size)", ["OSB", "Plywood"],
                                   default=[p for p in prefs.panel_types if p in ("OSB", "Plywood")],
                                   key=f"p_panels_{pv}")
        p_asm = pick_table([{"Assembly": a.assembly_id, "Grade": a.panel_grade,
                             "Panel t": a.min_nominal_panel_thickness_label, "Nail": a.nail_designation,
                             "Edge (in)": a.edge_nail_spacing_in, "v_n (plf)": a.v_n_plf,
                             "G_a OSB (k/in)": a.Ga_osb_kips_per_in, "G_a ply (k/in)": a.Ga_plywood_kips_per_in,
                             "Status": a.status.value} for a in lib.shear_wall_assemblies],
                           "Assembly", prefs.assemblies, f"p_asm_{pv}")
    with m_lum:
        lc1, lc2, lc3 = st.columns(3)
        p_posts = lc1.multiselect("Post sizes", [s.nominal for s in lib.lumber_sizes],
                                  default=[p for p in prefs.post_sizes if p in {s.nominal for s in lib.lumber_sizes}],
                                  key=f"p_posts_{pv}")
        p_min = lc2.number_input("Min posts per chord", min_value=1, max_value=40, value=prefs.min_posts,
                                 key=f"p_min_{pv}")
        p_max = lc3.number_input("Max posts per chord", min_value=1, max_value=40, value=prefs.max_posts,
                                 key=f"p_max_{pv}")
        p_lum = pick_table([{"Lumber": LUMBER_SEP.join((v.species_group, v.grade, v.size_class)),
                             "F_c (psi)": v.Fc_psi, "F_c⊥ (psi)": v.Fc_perp_psi, "E (psi)": v.E_psi,
                             "E_min (psi)": v.Emin_psi, "Status": v.status.value} for v in lib.lumber_design_values],
                           "Lumber", [LUMBER_SEP.join(x) for x in prefs.lumber], f"p_lum_{pv}")
    with m_rod:
        p_rods = pick_table([{"Rod system": r.system_id, "Diameter (in)": r.rod_diameter_in,
                              "Material": r.rod_material, "Allowable T (lb)": r.rod_allowable_tension_lb,
                              "A_e (in²)": r.rod_net_area_in2, "Status": r.status.value}
                             for r in lib.continuous_rod_systems], "Rod system", prefs.rods, f"p_rods_{pv}")
    with m_hd:
        p_hds = pick_table([{"Model": h.model, "Manufacturer": h.manufacturer,
                             "T_allow DF/SP (lb)": h.allowable_tension_DF_SP_lb,
                             "T_allow SPF/HF (lb)": h.allowable_tension_SPF_HF_lb,
                             "Deflection (in)": h.deflection_at_allowable_in, "Status": h.status.value}
                            for h in lib.holddowns], "Model", prefs.holddowns, f"p_hds_{pv}")

    new_prefs = MaterialPreferences(
        name=p_name, assemblies=tuple(p_asm), sides=tuple(sorted(int(x) for x in p_sides)),
        panel_types=tuple(p_panels), lumber=tuple(tuple(x.split(LUMBER_SEP)) for x in p_lum),
        post_sizes=tuple(p_posts), min_posts=int(p_min), max_posts=int(p_max), rods=tuple(p_rods),
        holddowns=tuple(p_hds), notes=prefs.notes)
    if new_prefs != prefs:
        st.session_state["prefs"] = new_prefs
        st.session_state.pop("autosize", None)
    prefs = new_prefs
    for w in prefs.check_against(lib):
        st.warning(w)
    st.download_button("Download preset (.json)", prefs.to_json(),
                       file_name=(prefs.name or "materials-preset").replace(" ", "_") + ".json",
                       mime="application/json")

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

    show_all = st.toggle("Show all library options (ignore the preferred materials)", key="show_all")
    view = MaterialPreferences() if show_all else prefs  # an empty preference list means everything
    lumber_rows = view.lumber_options(lib)
    asm_ids = opts(list(dict.fromkeys(a.assembly_id for a, _ in view.assembly_options(lib))),
                   base_loads["assembly_id"])
    rod_ids = opts([r.system_id for r in view.rod_options(lib)], base_ties["system_id"].dropna())
    hd_models = opts([h.model for h in lib.holddowns if not view.holddowns or h.model in view.holddowns],
                     base_ties["model"].dropna())
    species = opts(sorted({v.species_group for v in lumber_rows}), base_chords["species_group"])
    grades = opts(sorted({v.grade for v in lumber_rows}), base_chords["grade"])
    classes = opts(sorted({v.size_class for v in lumber_rows}), base_chords["size_class"])
    posts = opts(view.post_size_options(lib), base_chords["post_nominal"])

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
            "layout": SC("Geometry", options=forms.LAYOUTS, required=True,
                         help="given: enter chord length and d. example: from the post count by the example "
                              "layout (3 posts outboard of the rod, 6 in. rod gap)."),
            "post_thickness_in": NC("Post t along wall (in)", min_value=0.0, step=0.5),
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
    st.download_button("Download inputs (.json)", inputs_to_json(inp, prefs), file_name="shearwall_inputs.json",
                       mime="application/json", use_container_width=True,
                       help="Includes the project's preferred materials.")


# ------------------------------------------------------------------ auto-size: propose, then apply
def on_apply_autosize() -> None:
    prop = st.session_state.pop("autosize", None)
    if prop:
        apply_inputs(prop["result"].proposed)


def fmt_dcr(x) -> str:
    return "-" if x is None else f"{x:.2f}"


with tab_in:
    st.subheader("Auto-size with preferred materials (strength checks)")
    st.caption("For each story, proposes the lightest preferred nailing, chord posts and tie-down that pass shear, "
               "chord compression and tension (capacity ascending). Post geometry follows the example layout "
               "rule. Drift is checked and reported, not driven. Nothing changes until you apply.")
    snapshot = inputs_to_json(inp, prefs)
    runnable = res is not None and res.status is not OverallStatus.INVALID_INPUT
    if st.button("Auto-size", disabled=not runnable, key="autosize_run"):
        try:
            st.session_state["autosize"] = {"result": autosize(inp, lib, prefs), "snapshot": snapshot}
        except Exception:  # noqa: BLE001
            st.error("Auto-size raised an error. Send this to the calc builder.")
            st.code(traceback.format_exc())
    prop = st.session_state.get("autosize")
    if prop:
        a = prop["result"]
        stale = prop["snapshot"] != snapshot
        if stale:
            st.info("Inputs or preferred materials changed since this proposal; run Auto-size again.")
        summary = []
        for sp in a.stories:
            row = {"Story": sp.story, "Result": sp.status}
            for cat in ("shear", "compression", "rod", "holddown", "drift"):
                if cat in sp.dcr_before or cat in sp.dcr_after:
                    row[cat.capitalize()] = f"{fmt_dcr(sp.dcr_before.get(cat))} → {fmt_dcr(sp.dcr_after.get(cat))}"
            row["Notes"] = "; ".join(sp.notes)
            summary.append(row)
        st.dataframe(pd.DataFrame(summary).set_index("Story"), use_container_width=True)
        changes = [{"Story": sp.story, "Selection": c.field, "Current": c.current, "Proposed": c.proposed}
                   for sp in a.stories for c in sp.changes]
        if changes:
            st.dataframe(pd.DataFrame(changes), use_container_width=True, hide_index=True)
        else:
            st.caption("The current selections are already the lightest preferred options that pass.")
        st.button("Apply proposal", on_click=on_apply_autosize, type="primary", disabled=stale or not changes,
                  key="autosize_apply")

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
    st.download_button("Inputs (.json)", inputs_to_json(inp, prefs), file_name="shearwall_inputs.json",
                       mime="application/json", key="dl_inputs_report")
