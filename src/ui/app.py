"""Streamlit app: shear wall stack with seismic and wind forces.

Run from the repo root:   python -m streamlit run src/ui/app.py
(Windows venv: .venv\\Scripts\\python -m streamlit run src/ui/app.py)

Layout (Design tab): result status and key numbers first; project settings collapsed to a one-line summary;
one control row (story, edit mode, show-all, auto-size); then the selected story's inputs, free-body diagram
and checks side by side; the whole-stack summary underneath. Clicking a check opens its calc trace. The UI holds
no design logic: it builds ``design.inputs.DesignInputs`` (one per load case that has forces), runs
``design.engine.run_design`` for each and reports, check by check, the larger demand/capacity ratio and the
load case that produced it.
"""

from __future__ import annotations

import base64
import dataclasses
import sys
import traceback
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # src/
from ui.runtime import ensure_paths, git_commit, repo_root  # noqa: E402

ensure_paths()

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from design import factors as code_factors  # noqa: E402
from design.autosize import autosize_cases  # noqa: E402
from design.library import default_library  # noqa: E402
from design.preferences import MaterialPreferences  # noqa: E402
from design.result import EDITIONS, OverallStatus  # noqa: E402
from ui import forms, reports, tables  # noqa: E402
from ui.example import PLACEHOLDERS, example_cases  # noqa: E402
from ui.fbd import fbd_svg  # noqa: E402
from ui.graphic import dcr_colour, stack_svg  # noqa: E402
from ui.io import cases_from_json, cases_to_json, preferences_from_project  # noqa: E402
from ui.loadcases import LABEL, SHORT, CaseSet, run_cases  # noqa: E402
from ui.theme import CSS, page_header, section_header, tie_label  # noqa: E402
from ui.trace_export import result_to_json  # noqa: E402

SRC_EXAMPLE = "WoodWorks example components"
SRC_PROJECT = "Project component library"
LIB_HELP = ("Project library (default): the team's component tables in src/design/components/data (SDPWS Table 4.3A, "
            "NDS lumber, rods, hold-downs). WoodWorks example: the small answer-key fixtures in tests/ used by the tests. "
            "Switching loads that source's materials preset. Unverified or missing rows make checks report 'needs input'.")
DRIFT_OPTIONS = [0, 600, 500, 400, 360, 240]
GOV_AUTO = "Governing (auto)"
ONE, ALL = "One story", "All stories"
DCR_COLORS = {"≤ 0.90": "#16A34A", "0.90–1.00": "#F59E0B", "over 1.00": "#DC2626", "needs input": "#94A3B8", "n/a": "#E2E8F0"}

st.set_page_config(page_title="Shear wall stack designer", page_icon=":material/foundation:", layout="wide",
                   initial_sidebar_state="collapsed")
st.markdown(CSS, unsafe_allow_html=True)


# ------------------------------------------------------------------ data sources and state
@st.cache_resource
def get_library(source: str):
    if source == SRC_EXAMPLE:
        from ui.example import example_library
        return example_library()
    return default_library()


def shipped_presets() -> dict[str, Path]:
    """Preset files in presets/ (shipped with the app), keyed by their display name."""
    out = {}
    for f in sorted((repo_root() / "presets").glob("*.json")):
        try:
            out[MaterialPreferences.from_json(f.read_text(encoding="utf-8")).name or f.stem] = f
        except Exception:  # noqa: BLE001  (a broken preset file must not stop the app)
            continue
    return out


DEFAULT_PRESET = {SRC_PROJECT: "woodworks-example-production.json", SRC_EXAMPLE: "woodworks-example.json"}


def default_preset(source: str) -> MaterialPreferences:
    """The shipped preset matching a data source (the example's materials in that library)."""
    f = repo_root() / "presets" / DEFAULT_PRESET[source]
    return MaterialPreferences.from_json(f.read_text(encoding="utf-8")) if f.exists() else MaterialPreferences()


def apply_prefs(prefs: MaterialPreferences) -> None:
    st.session_state["prefs"] = prefs
    st.session_state["prefs_ver"] = st.session_state.get("prefs_ver", 0) + 1
    st.session_state.pop("autosize", None)


def on_source_change() -> None:
    """A different library has different ids: load its matching preset (inputs are left as entered)."""
    apply_prefs(default_preset(st.session_state["lib_source"]))


def apply_cases(cases) -> None:
    vals = forms.global_values_from_cases(cases)
    vals["wind_drift_denominator"] = int(round(vals["wind_drift_denominator"])) if vals["wind_drift_denominator"] else 0
    for k, v in vals.items():
        st.session_state[f"g_{k}"] = v
    frames = forms.frames_from_cases(cases)
    st.session_state["n_stories"] = len(frames[0])
    st.session_state["base_frames"] = frames
    st.session_state["ver"] = st.session_state.get("ver", 0) + 1
    st.session_state["sel_story"] = 1


def on_resize() -> None:
    n = int(st.session_state["n_stories"] or 1)
    st.session_state["base_frames"] = forms.resize_frames(st.session_state["base_frames"], n)
    st.session_state["ver"] += 1
    st.session_state["sel_story"] = min(st.session_state.get("sel_story") or 1, n)


def on_edit_mode() -> None:
    st.session_state["ver"] += 1  # fresh widgets in the other mode, read from the shared story tables


def on_load_example() -> None:
    """The WoodWorks example with component ids for the selected data source, and that source's preset."""
    source = st.session_state["lib_source"]
    apply_cases(example_cases(production=source == SRC_PROJECT))
    apply_prefs(default_preset(source))


def current_cases():
    g = {k: st.session_state[f"g_{k}"] for k in forms.GLOBAL_DEFAULTS}
    return forms.build_cases(g, *st.session_state["base_frames"])


def on_autosize() -> None:
    """Run auto-size on the current inputs (both load cases) and open the proposal dialog."""
    cases = current_cases()
    prefs = st.session_state["prefs"]
    st.session_state["autosize"] = {"result": autosize_cases(cases, get_library(st.session_state["lib_source"]), prefs),
                                    "snapshot": cases_to_json(cases, prefs)}
    st.session_state["autosize_open"] = True


def on_apply_autosize() -> None:
    prop = st.session_state.pop("autosize", None)
    st.session_state["autosize_open"] = False
    if prop:
        apply_cases(prop["result"].proposed_cases)
        st.toast("Auto-size proposal applied", icon=":material/check_circle:")


def on_close_autosize() -> None:
    st.session_state["autosize_open"] = False


def on_heatmap_select() -> None:
    """Clicking a heatmap cell selects that story."""
    try:
        pts = st.session_state["heatmap"]["selection"]["pick"]
    except (KeyError, TypeError):
        return
    if pts:
        st.session_state["sel_story"] = int(pts[0]["story"])


@contextmanager
def card(key: str, title: str, icon: str = "", pill: str = ""):
    with st.container(border=True, key=f"card_{key}"):
        st.markdown(section_header(title, icon, pill), unsafe_allow_html=True)
        yield


def img_html(svg: str, alt: str) -> str:
    return (f'<img style="width:100%" alt="{alt}" '
            f'src="data:image/svg+xml;base64,{base64.b64encode(svg.encode()).decode()}"/>')


def fmt_num(x, nd=0) -> str:
    return "—" if x is None else f"{x:,.{nd}f}"


if "base_frames" not in st.session_state:
    st.session_state["lib_source"] = SRC_PROJECT
    apply_cases(example_cases(production=True))
if st.session_state.get("lib_source") not in (SRC_EXAMPLE, SRC_PROJECT):
    st.session_state["lib_source"] = SRC_PROJECT
if "prefs" not in st.session_state:
    apply_prefs(default_preset(st.session_state["lib_source"]))
st.session_state.setdefault("edit_mode", ONE)

# ------------------------------------------------------------------ header: title, file menu, report
head_l, head_r = st.columns([3, 2], vertical_alignment="center")
head_l.markdown(page_header(EDITIONS, "Prototype · needs PE review"), unsafe_allow_html=True)
header_actions = head_r.container(horizontal=True, horizontal_alignment="right", vertical_alignment="center")

tab_design, tab_mat, tab_trace, tab_basis, tab_verify, tab_report = st.tabs(
    ["Design", "Materials", "Calc trace", "Engineering basis", "Items to verify", "Report"])
lib = get_library(st.session_state["lib_source"])


# ------------------------------------------------------------------ materials: library and preferred lists
def pick_table(rows: list[dict], id_col: str, chosen, key: str, height: int | str = "auto") -> list:
    """Library rows with a 'Use' check column; returns the ticked ids in library order.

    Preferred ids not shown (filtered out, or from another data source) are kept, not dropped.
    """
    if not rows:
        st.caption("No rows match.")
        return list(chosen)
    df = pd.DataFrame(rows)
    df.insert(0, "Use", df[id_col].isin(list(chosen)))
    out = st.data_editor(df, key=key, hide_index=True, height=height,
                         disabled=[c for c in df.columns if c != "Use"],
                         column_config={"Use": st.column_config.CheckboxColumn("Use", width="small"),
                                        "Status": st.column_config.TextColumn("Status", width="small")})
    here = set(df[id_col])
    return [c for c in chosen if c not in here] + list(out.loc[out["Use"], id_col])


def on_load_shipped_preset() -> None:
    path = shipped_presets().get(st.session_state.get("preset_pick"))
    if path is not None:
        apply_prefs(MaterialPreferences.from_json(path.read_text(encoding="utf-8")))


def on_set_assemblies(ids: list[str], add: bool) -> None:
    prefs = st.session_state["prefs"]
    cur = list(prefs.assemblies)
    new = cur + [i for i in ids if i not in cur] if add else [i for i in cur if i not in ids]
    apply_prefs(dataclasses.replace(prefs, assemblies=tuple(new)))


LUMBER_SEP = " | "

with tab_mat:
    prefs: MaterialPreferences = st.session_state["prefs"]
    pv = st.session_state["prefs_ver"]
    with card("library", "Component library", "grid"):
        lc1, lc2 = st.columns([2, 3], vertical_alignment="bottom")
        lc1.selectbox("Component data", [SRC_PROJECT, SRC_EXAMPLE], key="lib_source", help=LIB_HELP,
                      on_change=on_source_change)
        tot = pd.DataFrame(lib.status_counts()).T.fillna(0).astype(int).sum()
        with lc2.container(horizontal=True, vertical_alignment="center"):
            st.badge(f"{int(tot.get('verified', 0))} verified", icon=":material/verified:", color="green")
            st.badge(f"{int(tot.get('memory', 0))} memory", icon=":material/history_edu:", color="orange")
            st.badge(f"{int(tot.get('pending', 0))} pending", icon=":material/pending:", color="gray")
            st.caption("rows in the component tables")
        with st.expander("Browse the component tables", icon=":material/table_view:"):
            tables_by_name = {"Shear wall assemblies (SDPWS Table 4.3A)": lib.shear_wall_assemblies,
                              "Continuous rod systems": lib.continuous_rod_systems, "Hold-downs": lib.holddowns,
                              "Lumber design values (NDS)": lib.lumber_design_values,
                              "Size factors (NDS Supplement 4A)": lib.size_factors, "Lumber sizes": lib.lumber_sizes,
                              "Sheathing panels": lib.sheathing_panels, "Nails": lib.nails}
            tname = st.selectbox("Table", list(tables_by_name), key="data_table")
            df_t = pd.DataFrame([dataclasses.asdict(r) for r in tables_by_name[tname]])
            if "status" in df_t:
                df_t["status"] = df_t["status"].map(lambda x: getattr(x, "value", x))
            st.dataframe(df_t.dropna(axis=1, how="all"), hide_index=True)

    with card("materials", "Preferred materials", "grid", prefs.name or "unnamed preset"):
        st.caption("Down-select the component library to the materials you prefer. The Design tab's dropdowns show only "
                   "preferred options (unless 'Show all library options' is on), and **Auto-size** proposes the "
                   "lightest preferred option that passes. An empty selection means no restriction. Row status is shown; "
                   "unverified rows may be preferred and are flagged in the results.")
        presets = shipped_presets()
        with st.container(horizontal=True, vertical_alignment="bottom"):
            p_name = st.text_input("Preset name", value=prefs.name, key=f"p_name_{pv}")
            st.selectbox("Load a shipped preset", list(presets) or ["(none)"], key="preset_pick",
                         help="Pick a preset and press Load. The current preset's name is shown on the left.")
            st.button("Load", on_click=on_load_shipped_preset, disabled=not presets, icon=":material/download_done:",
                      help="Replace the current preferences with the selected shipped preset.")
            with st.popover("Import", icon=":material/upload_file:"):
                pup = st.file_uploader("Preset file (.json)", type="json", key="preset_upload")
                if pup is not None and st.session_state.get("last_preset_upload") != (pup.name, pup.size):
                    try:
                        apply_prefs(MaterialPreferences.from_json(pup.getvalue().decode("utf-8")))
                        st.session_state["last_preset_upload"] = (pup.name, pup.size)
                        st.rerun()
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Could not read preset: {exc}")

        m_asm, m_lum, m_rod, m_hd = st.tabs([":material/layers: Sheathing and nailing", ":material/carpenter: Lumber and posts",
                                             ":material/hardware: Rod systems", ":material/link: Hold-downs"])
        with m_asm:
            sc1, sc2 = st.columns(2)
            p_sides = sc1.pills("Sheathed sides auto-size may use", [1, 2], selection_mode="multi",
                                default=list(prefs.sides), key=f"p_sides_{pv}",
                                format_func=lambda x: "1 side" if x == 1 else "2 sides")
            p_panels = sc2.pills("Panel type (the first is used by auto-size)", ["OSB", "Plywood"], selection_mode="multi",
                                 default=[p for p in prefs.panel_types if p in ("OSB", "Plywood")], key=f"p_panels_{pv}")
            asms = lib.shear_wall_assemblies
            st.caption("Filter the list (filters only change what is shown, not what is preferred):")
            fc1, fc2 = st.columns(2)
            f_grade = fc1.pills("Grade", sorted({a.panel_grade for a in asms}), selection_mode="multi", key="f_grade",
                                wrap=True)
            f_thick = fc2.pills("Panel thickness", sorted({a.min_nominal_panel_thickness_label for a in asms},
                                                          key=lambda t: next(a.min_nominal_panel_thickness_in for a in asms
                                                                             if a.min_nominal_panel_thickness_label == t)),
                                selection_mode="multi", key="f_thick", wrap=True)
            fc3, fc4 = st.columns(2)
            f_nail = fc3.pills("Nail", sorted({a.nail_designation for a in asms}, key=lambda x: int(x.split("d")[0])
                                              if x.split("d")[0].isdigit() else 99), selection_mode="multi",
                               key="f_nail", wrap=True)
            f_space = fc4.pills("Edge spacing (in)", sorted({a.edge_nail_spacing_in for a in asms}), selection_mode="multi",
                                key="f_space", format_func=lambda x: f"{x:g}", wrap=True)
            shown = [a for a in asms if (not f_grade or a.panel_grade in f_grade)
                     and (not f_thick or a.min_nominal_panel_thickness_label in f_thick)
                     and (not f_nail or a.nail_designation in f_nail)
                     and (not f_space or a.edge_nail_spacing_in in f_space)]
            p_asm = pick_table([{"Assembly": a.assembly_id, "Grade": a.panel_grade,
                                 "Panel": a.min_nominal_panel_thickness_label, "Nail": a.nail_designation,
                                 "Edge (in)": a.edge_nail_spacing_in, "v_n (plf)": a.v_n_plf,
                                 "G_a OSB (k/in)": a.Ga_osb_kips_per_in, "G_a ply (k/in)": a.Ga_plywood_kips_per_in,
                                 "Status": a.status.value} for a in shown],
                               "Assembly", prefs.assemblies, f"p_asm_{pv}", height=320)
            with st.container(horizontal=True, vertical_alignment="center"):
                ids = [a.assembly_id for a in shown]
                st.button("Prefer all shown", on_click=on_set_assemblies, args=(ids, True), icon=":material/done_all:")
                st.button("Clear shown", on_click=on_set_assemblies, args=(ids, False), icon=":material/remove_done:")
                st.caption(f"{len(p_asm)} of {len(asms)} assemblies preferred · {len(shown)} shown"
                           if p_asm else f"None ticked: all {len(asms)} assemblies are allowed · {len(shown)} shown")
        with m_lum:
            lc1, lc2, lc3 = st.columns([2, 1, 1])
            sizes_here = [x.nominal for x in lib.lumber_sizes]
            p_posts = lc1.pills("Post sizes", sizes_here, selection_mode="multi",
                                default=[p for p in prefs.post_sizes if p in sizes_here], key=f"p_posts_{pv}")
            p_min = lc2.number_input("Min posts per chord", min_value=1, max_value=40, value=prefs.min_posts,
                                     key=f"p_min_{pv}")
            p_max = lc3.number_input("Max posts per chord", min_value=1, max_value=40, value=prefs.max_posts,
                                     key=f"p_max_{pv}")
            f_species = st.pills("Species", sorted({v.species_group for v in lib.lumber_design_values}),
                                 selection_mode="multi", key="f_species")
            lum_shown = [v for v in lib.lumber_design_values if not f_species or v.species_group in f_species]
            p_lum = pick_table([{"Lumber": LUMBER_SEP.join((v.species_group, v.grade, v.size_class)),
                                 "F_c (psi)": v.Fc_psi, "F_c⊥ (psi)": v.Fc_perp_psi, "E (psi)": v.E_psi,
                                 "E_min (psi)": v.Emin_psi, "Status": v.status.value} for v in lum_shown],
                               "Lumber", [LUMBER_SEP.join(x) for x in prefs.lumber], f"p_lum_{pv}", height=320)
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
            name=p_name, assemblies=tuple(p_asm), sides=tuple(sorted(int(x) for x in (p_sides or []))),
            panel_types=tuple(p_panels or []), lumber=tuple(tuple(x.split(LUMBER_SEP)) for x in p_lum),
            post_sizes=tuple(p_posts or []), min_posts=int(p_min), max_posts=int(p_max), rods=tuple(p_rods),
            holddowns=tuple(p_hds), notes=prefs.notes)
        if new_prefs != prefs:
            st.session_state["prefs"] = new_prefs
            st.session_state.pop("autosize", None)
        prefs = new_prefs
        for w in prefs.check_against(lib):
            st.warning(w, icon=":material/warning:")
        st.download_button("Download preset (.json)", prefs.to_json(), icon=":material/download:",
                           file_name=(prefs.name or "materials-preset").replace(" ", "_") + ".json",
                           mime="application/json")

    with card("autosize", "Auto-size with preferred materials", "layers", "strength checks"):
        st.caption("For each story, proposes the lightest preferred nailing, chord posts and tie-down that pass shear, "
                   "chord compression and tension in every load case with a force (capacity ascending). Post geometry "
                   "follows the example layout rule. Drift is checked and reported, not driven. Nothing changes until "
                   "you apply.")
        st.button("Auto-size", key="autosize_run", on_click=on_autosize, type="primary", icon=":material/auto_fix_high:")

# ------------------------------------------------------------------ design tab
with tab_design:
    status_slot = st.container()  # result banner and key numbers, filled once the engine has run

    # ---- project settings, collapsed to a one-line summary
    ss = st.session_state
    drift_txt = "no wind drift limit" if not ss.get("g_wind_drift_denominator") else f"wind H/{ss['g_wind_drift_denominator']}"
    summary = (f"Project settings · {ss.get('n_stories')} stories · b = {ss.get('g_b_ft', 0):g} ft · "
               f"RC {ss.get('g_risk_category')} · SDC {ss.get('g_sdc') or '—'} · S_DS {ss.get('g_S_DS', 0):g} · {drift_txt} · "
               f"{ss.get('g_deflection_method')} deflection")
    with st.expander(summary, icon=":material/tune:"):
        pg, ps, pw, pa = st.columns([1.2, 1.2, 1, 1.3], gap="medium")
        with pg:
            st.markdown("**Geometry**")
            st.text_input("Project name", key="g_project_name")
            st.segmented_control("Stories (1 = bottom)", [1, 2, 3, 4, 5], key="n_stories", on_change=on_resize,
                                 required=True)
            st.number_input("Wall length b (ft)", min_value=0.0, step=0.5, key="g_b_ft")
            st.number_input("End post width (in)", min_value=0.0, step=0.5, key="g_d_post_in",
                            help="Default chord lever arm (decision D2); 0 = not given. Not needed when every story has "
                                 "its own d arm or uses the layout rule.")
        with ps:
            st.markdown("**Seismic**")
            c1, c2 = st.columns(2)
            c1.selectbox("Risk category", ["I", "II", "III", "IV"], key="g_risk_category")
            c2.selectbox("SDC", ["", "A", "B", "C", "D", "E", "F"], key="g_sdc", help="Seismic design category")
            st.number_input("S_DS", min_value=0.0, step=0.01, key="g_S_DS", format="%.3f")
            c3, c4 = st.columns(2)
            c3.number_input("C_d", min_value=0.0, step=0.5, key="g_C_d")
            c4.number_input("I_e", min_value=0.0, step=0.05, key="g_I_e")
        with pw:
            st.markdown("**Wind**")
            drift_opts = DRIFT_OPTIONS + [d for d in [ss.get("g_wind_drift_denominator")] if d not in DRIFT_OPTIONS]
            st.segmented_control("Wind drift limit", drift_opts, key="g_wind_drift_denominator", required=True,
                                 format_func=lambda x: "none" if not x else f"H/{x}",
                                 help="No code limit is applied for wind; the owner or project sets it (decision D6).")
            st.number_input("Net roof uplift (plf, strength)", min_value=0.0, step=10.0, key="g_roof_uplift_plf")
        with pa:
            st.markdown("**Analysis options**")
            st.segmented_control("Deflection method", ["3-term", "4-term"], key="g_deflection_method", required=True,
                                 help="3-term: SDPWS Eq. 4.3-1 (the example's method). 4-term: SDPWS Commentary C4.3.4-1; "
                                      "needs the panel and nail slip constants in the component library (decision D6).")
            st.segmented_control("Framing moisture", ["dry", "green"], key="g_framing_moisture", required=True,
                                 help="Selects the nail-slip equation (4-term method only).")
            st.number_input("Wood bearing amplification", min_value=1.0, step=0.05, key="g_wood_bearing_factor",
                            help="Wood-to-wood crushing amplification (example §3.4.3, engineer judgement).")
            st.toggle("Carry rotation from lower stories into drift", key="g_carry_rotation",
                      help="Decision D6, rigid-body geometry.")
            st.toggle("Tie-down restraint at every level", key="g_restraint_each_level",
                      help="Off: chord deformation accumulates up the building (example Table 3.17B). "
                           "Cannot be combined with carried rotation.")
        with st.popover("Which example values are placeholders?", icon=":material/info:"):
            for p in PLACEHOLDERS:
                st.markdown(f"- {p}")

    ver = st.session_state["ver"]
    loads, chords, ties = st.session_state["base_frames"]
    n = len(loads)
    if st.session_state.get("sel_story") not in range(1, n + 1):
        st.session_state["sel_story"] = 1

    # ---- one control row: story, edit mode, show-all, auto-size
    with st.container(horizontal=True, vertical_alignment="bottom", gap="medium"):
        st.segmented_control("Story", list(range(1, n + 1)), key="sel_story", required=True,
                             format_func=lambda i: f"Story {i}", help="Story 1 is the bottom wall. You can also click "
                                                                       "a story in the heatmap below.")
        st.segmented_control("Edit", [ONE, ALL], key="edit_mode", required=True, on_change=on_edit_mode,
                             help="All stories: edit every story at once in tables, like a spreadsheet.")
        st.toggle("Show all library options", key="show_all",
                  help="Off: the dropdowns list only the materials ticked on the Materials tab.")
        st.space("stretch")
        st.button("Auto-size", key="autosize_run_design", on_click=on_autosize, icon=":material/auto_fix_high:",
                  help="Propose the lightest preferred materials that pass the strength checks.")
    sel = st.session_state["sel_story"]
    view = MaterialPreferences() if st.session_state.get("show_all") else prefs  # empty preferences = everything
    lumber_view = view.lumber_options(lib)

    def fv(x, default=0.0):
        try:
            return default if pd.isna(x) else x
        except (TypeError, ValueError):
            return x

    def wnum(df, col, label, story, **kw):
        val = st.number_input(label, value=float(fv(df.at[story, col])), key=f"w{ver}_{story}_{col}", **kw)
        df.at[story, col] = val
        return val

    def wtog(df, col, label, story, **kw):
        cur = fv(df.at[story, col], True)
        val = st.toggle(label, value=bool(cur), key=f"w{ver}_{story}_{col}", **kw)
        df.at[story, col] = val
        return val

    def wsel(df, col, label, story, options, fmt=None, cast=None):
        cur = fv(df.at[story, col], "")
        cur = cast(cur) if cast and cur != "" else cur
        opts = list(options)
        if cur not in opts:
            opts.insert(0, cur)
        val = st.selectbox(label, opts, index=opts.index(cur), key=f"w{ver}_{story}_{col}", format_func=fmt or str)
        df.at[story, col] = val
        return val

    def wseg(df, col, label, story, options, fmt=None, cast=None, **kw):
        """Two to five options: keep them visible."""
        cur = fv(df.at[story, col], "")
        cur = cast(cur) if cast and cur != "" else cur
        opts = list(options)
        if cur not in opts:
            opts.insert(0, cur)
        val = st.segmented_control(label, opts, default=cur, key=f"w{ver}_{story}_{col}", format_func=fmt or str,
                                   required=True, **kw)
        df.at[story, col] = val
        return val

    def opts_of(values) -> list:
        out = []
        for v in values:
            if isinstance(v, str) and v and v not in out:
                out.append(v)
        return out

    asm_opts = opts_of([a.assembly_id for a, _ in view.assembly_options(lib)] + list(loads["assembly_id"]))
    post_opts = opts_of(view.post_size_options(lib) + list(chords["post_nominal"]))
    species_opts = opts_of(sorted({x.species_group for x in lumber_view}) + list(chords["species_group"]))
    grade_opts = opts_of(sorted({x.grade for x in lumber_view}) + list(chords["grade"]))
    class_opts = opts_of(sorted({x.size_class for x in lumber_view}) + list(chords["size_class"]))
    rod_opts = opts_of([x.system_id for x in view.rod_options(lib)] + list(ties["system_id"].dropna()))
    hd_opts = opts_of([x.model for x in lib.holddowns if not view.holddowns or x.model in view.holddowns]
                      + list(ties["model"].dropna()))

    edit_all = st.session_state["edit_mode"] == ALL
    if edit_all:
        col_l = col_m = col_r = None
        with card("all", "All stories", "list", "edit like a spreadsheet · story 1 is the bottom"):
            NC, SC = st.column_config.NumberColumn, st.column_config.SelectboxColumn
            e_loads, e_posts, e_ties = st.tabs([":material/south: Loads and nailing", ":material/view_column: Chord posts",
                                                ":material/link: Tie-downs"])
            with e_loads:
                ed_l = st.data_editor(loads, key=f"tbl_loads_{ver}", num_rows="fixed", column_config={
                    "h_ft": NC("h (ft)", min_value=0.0, step=0.5, format="%.2f"),
                    "F_seismic_lb": NC("Seismic F (lb)", min_value=0.0, step=50.0, format="%.0f"),
                    "F_wind_lb": NC("Wind F (lb)", min_value=0.0, step=50.0, format="%.0f"),
                    "w_D_plf": NC("Dead w_D (plf)", min_value=0.0, format="%.1f"),
                    "w_wall_plf": NC("Wall weight (plf)", min_value=0.0, format="%.1f"),
                    "w_L_plf": NC("Floor live (plf)", min_value=0.0, format="%.1f"),
                    "w_Lr_plf": NC("Roof live (plf)", min_value=0.0, format="%.1f"),
                    "assembly_id": SC("Nailing / assembly", options=asm_opts, required=True, width="large"),
                    "sides": SC("Sides", options=[1, 2], required=True),
                    "panel_type": SC("Panel", options=["OSB", "Plywood"], required=True)})
            with e_posts:
                ed_c = st.data_editor(chords, key=f"tbl_chords_{ver}", num_rows="fixed", column_config={
                    "n_posts": NC("Posts", min_value=1, step=1, format="%d"),
                    "post_nominal": SC("Post", options=post_opts, required=True),
                    "species_group": SC("Species", options=species_opts, required=True),
                    "grade": SC("Grade", options=grade_opts, required=True),
                    "size_class": SC("Size class", options=class_opts, required=True),
                    "layout": SC("Geometry", options=forms.LAYOUTS, required=True),
                    "post_thickness_in": NC("Post t (in)", min_value=0.0, step=0.5),
                    "outboard_posts": NC("Outboard posts", min_value=0, step=1, format="%d"),
                    "rod_gap_in": NC("Rod gap (in)", min_value=0.0, step=0.5),
                    "chord_length_ft": NC("Chord length (ft)", min_value=0.0, step=0.125, format="%.3f"),
                    "d_arm_ft": NC("d arm (ft)", min_value=0.0, step=0.05, format="%.2f"),
                    "d_out_of_plane_in": NC("Depth out of plane (in)", min_value=0.0, step=0.25),
                    "top_plates_in": NC("Top plates (in)", min_value=0.0, step=0.5),
                    "bottom_plate_in": NC("Bottom plate (in)", min_value=0.0, step=0.5)})
            with e_ties:
                ed_t = st.data_editor(ties, key=f"tbl_ties_{ver}", num_rows="fixed", column_config={
                    "kind": SC("Type", options=[forms.ROD, forms.HOLDDOWN], required=True),
                    "system_id": SC("Rod system", options=rod_opts),
                    "plate_width_in": NC("Plate w (in)", min_value=0.0, step=0.25),
                    "plate_length_in": NC("Plate l (in)", min_value=0.0, step=0.25),
                    "plate_thickness_in": NC("Plate t (in)", min_value=0.0, step=0.125, format="%.3f"),
                    "plate_Fy_psi": NC("Plate Fy (psi)", min_value=0.0, step=1000.0, format="%.0f"),
                    "slack_in": NC("Slack (in)", min_value=0.0, step=0.01, format="%.4f"),
                    "takeup_elongation_in": NC("Take-up (in)", min_value=0.0, step=0.005, format="%.4f"),
                    "rod_length_ft": NC("Rod length (ft)", min_value=0.0, step=0.5),
                    "bearing_hole_in": NC("Bearing hole (in)", min_value=0.0, step=0.0625, format="%.4f"),
                    "takeup_device": st.column_config.CheckboxColumn("Take-up device"),
                    "shrinkage_in": NC("Shrinkage (in)", min_value=0.0, step=0.01, format="%.3f"),
                    "model": SC("Hold-down model", options=hd_opts),
                    "T_allow_lb": NC("T_allow (lb)", min_value=0.0, step=100.0, format="%.0f"),
                    "delta_a_in": NC("Δ_a (in)", min_value=0.0, step=0.01, format="%.3f")})
            for frame, edited in ((loads, ed_l), (chords, ed_c), (ties, ed_t)):
                for c in frame.columns:
                    frame[c] = edited[c]
            st.caption("Rod system rows use the plate and rod columns; hold-down rows use model or T_allow. Chord length "
                       "and d are ignored where Geometry = example (layout rule).")
    else:
        col_l, col_r = st.columns([1, 2.15])
        col_m = col_r  # the wall view and its checks stack in one wide results column
        # ---- left: inputs for the selected wall
        with col_l:
            with card("left", f"Wall inputs: story {sel}", "ruler"):
                t_loads, t_nail, t_posts, t_tie = st.tabs(["Loads", "Nailing", "Posts", "Tie-down"])
                with t_loads:
                    a1, a2 = st.columns(2)
                    with a1:
                        wnum(loads, "F_seismic_lb", "Seismic F (lb)", sel, min_value=0.0, step=50.0, format="%.0f")
                    with a2:
                        wnum(loads, "F_wind_lb", "Wind F (lb)", sel, min_value=0.0, step=50.0, format="%.0f")
                    st.caption("Strength-level forces at the top of this story. A load type at 0 on every story is "
                               "skipped; the program checks both and reports which governs.")
                    b1, b2 = st.columns(2)
                    with b1:
                        wnum(loads, "h_ft", "Height h (ft)", sel, min_value=0.0, step=0.5, format="%.2f")
                        wnum(loads, "w_D_plf", "Dead w_D (plf)", sel, min_value=0.0, format="%.1f")
                        wnum(loads, "w_L_plf", "Floor live w_L (plf)", sel, min_value=0.0, format="%.1f")
                    with b2:
                        wnum(loads, "w_wall_plf", "Wall weight (plf)", sel, min_value=0.0, format="%.1f")
                        wnum(loads, "w_Lr_plf", "Roof live w_Lr (plf)", sel, min_value=0.0, format="%.1f")
                with t_nail:
                    wsel(loads, "assembly_id", "Nailing / assembly", sel, asm_opts)
                    c1, c2 = st.columns(2)
                    with c1:
                        wseg(loads, "sides", "Sheathed sides", sel, [1, 2], cast=int)
                    with c2:
                        wseg(loads, "panel_type", "Panel", sel, ["OSB", "Plywood"])
                with t_posts:
                    lay = wseg(chords, "layout", "Chord geometry", sel, forms.LAYOUTS,
                               fmt=lambda x: {"given": "Enter L_c and d", "example": "Layout rule"}.get(x, x),
                               help="Layout rule: chord length and lever arm follow from the post count "
                                    "(example Figs. 3.7–3.8).")
                    d1, d2 = st.columns(2)
                    with d1:
                        wnum(chords, "n_posts", "Posts (n)", sel, min_value=1.0, step=1.0, format="%.0f")
                    with d2:
                        wsel(chords, "post_nominal", "Post", sel, post_opts)
                    if lay == "example":
                        k1, k2, k3 = st.columns(3)
                        with k1:
                            wnum(chords, "post_thickness_in", "Post t (in)", sel, min_value=0.0, step=0.5,
                                 help="Post dimension along the wall")
                        with k2:
                            wnum(chords, "outboard_posts", "Outboard", sel, min_value=0.0, step=1.0, format="%.0f",
                                 help="Posts outboard of the rod")
                        with k3:
                            wnum(chords, "rod_gap_in", "Rod gap (in)", sel, min_value=0.0, step=0.5)
                    g1c, g2c = st.columns(2)
                    with g1c:
                        wnum(chords, "chord_length_ft", "Chord length (ft)", sel, min_value=0.0, step=0.125,
                             format="%.3f", disabled=lay == "example")
                    with g2c:
                        wnum(chords, "d_arm_ft", "d arm (ft)", sel, min_value=0.0, step=0.05, format="%.2f",
                             disabled=lay == "example", help="0 = default from the end post width (D2)")
                    wsel(chords, "species_group", "Species", sel, species_opts)
                    e1, e2 = st.columns(2)
                    with e1:
                        wsel(chords, "grade", "Grade", sel, grade_opts)
                    with e2:
                        wsel(chords, "size_class", "Size class", sel, class_opts)
                    with st.expander("Depth and plates"):
                        wnum(chords, "d_out_of_plane_in", "Post depth out of plane (in)", sel, min_value=0.0, step=0.25,
                             format="%.2f", help="0 = dressed width")
                        p1, p2 = st.columns(2)
                        with p1:
                            wnum(chords, "top_plates_in", "Top plates (in)", sel, min_value=0.0, step=0.5, format="%.2f")
                        with p2:
                            wnum(chords, "bottom_plate_in", "Bottom plate (in)", sel, min_value=0.0, step=0.5,
                                 format="%.2f")
                with t_tie:
                    kind = wseg(ties, "kind", "Type", sel, [forms.ROD, forms.HOLDDOWN])
                    if kind == forms.ROD:
                        wsel(ties, "system_id", "Rod system", sel, rod_opts)
                        f1, f2, f3 = st.columns(3)
                        with f1:
                            wnum(ties, "plate_width_in", "Plate w (in)", sel, min_value=0.0, step=0.25)
                        with f2:
                            wnum(ties, "plate_length_in", "Plate l (in)", sel, min_value=0.0, step=0.25)
                        with f3:
                            wnum(ties, "plate_thickness_in", "Plate t (in)", sel, min_value=0.0, step=0.125, format="%.3f")
                        wtog(ties, "takeup_device", "Take-up device", sel,
                             help="Counts slack and take-up elongation; without it, shrinkage is counted instead.")
                        with st.expander("Rod, plate and take-up details"):
                            h1, h2 = st.columns(2)
                            with h1:
                                wnum(ties, "slack_in", "Slack (in)", sel, min_value=0.0, step=0.01, format="%.4f")
                                wnum(ties, "plate_Fy_psi", "Plate Fy (psi)", sel, min_value=0.0, step=1000.0, format="%.0f")
                                wnum(ties, "bearing_hole_in", "Bearing hole (in)", sel, min_value=0.0, step=0.0625,
                                     format="%.4f", help="0 = rod diameter + 3/16 in.")
                            with h2:
                                wnum(ties, "takeup_elongation_in", "Take-up (in)", sel, min_value=0.0, step=0.005,
                                     format="%.4f")
                                wnum(ties, "rod_length_ft", "Rod length (ft)", sel, min_value=0.0, step=0.5,
                                     help="0 = story height")
                                wnum(ties, "shrinkage_in", "Shrinkage (in)", sel, min_value=0.0, step=0.01, format="%.3f")
                    else:
                        wsel(ties, "model", "Hold-down model", sel, hd_opts)
                        wnum(ties, "T_allow_lb", "T_allow (lb)", sel, min_value=0.0, step=100.0, format="%.0f",
                             help="0 = use the model's catalog value")
                        wnum(ties, "delta_a_in", "Δ_a (in)", sel, min_value=0.0, step=0.01, format="%.3f")

    # ---- run the engine for each load case
    g = {k: st.session_state[f"g_{k}"] for k in forms.GLOBAL_DEFAULTS}
    cases = forms.build_cases(g, loads, chords, ties)
    cs, run_error = None, None
    if cases:
        try:
            raw = run_cases(cases, lib)
            commit = git_commit()
            cs = CaseSet(raw.inputs, {c: dataclasses.replace(r, git_commit=commit) for c, r in raw.results.items()})
        except Exception:  # noqa: BLE001  (surface engine bugs instead of a blank page)
            run_error = traceback.format_exc()
    valid = cs is not None and cs.valid

    # ---- status first: banner and key numbers
    with status_slot:
        if run_error:
            st.error("The design engine raised an error. Send this to the calc builder.", icon=":material/bug_report:")
            st.code(run_error)
        elif not cases:
            st.info("Enter a seismic and/or wind force for at least one story. Each load type with a force is checked "
                    "and the governing one is reported.", icon=":material/info:")
        elif not valid:
            for case, errs in cs.invalid().items():
                st.error(f"Fix these {LABEL[case].lower()} inputs before the engine will run checks:",
                         icon=":material/error:")
                st.table(pd.DataFrame([{"Field": e.field, "Problem": e.message} for e in errs]))
        else:
            dcr, gcase_all, gstory, gchk = cs.overall()
            banner = {OverallStatus.PASS: (st.success, "All checks pass", ":material/check_circle:"),
                      OverallStatus.FAIL: (st.error, "One or more checks FAIL", ":material/cancel:"),
                      OverallStatus.INCOMPLETE: (st.warning, "Incomplete: some checks need engineer input or component "
                                                             "data", ":material/pending:")}[cs.status]
            gov_txt = (f" · governing: {LABEL[gcase_all]}, story {gstory}, {(gchk or '').split('.', 1)[-1]} "
                       f"(DCR {dcr:.2f})") if gcase_all else ""
            banner[0](banner[1] + gov_txt, icon=banner[2])
            vs = {c: cs.num(c, "S1.statics.V") for c in cs.cases}
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Max demand / capacity", "—" if dcr is None else f"{dcr:.2f}", border=True, height="stretch",
                      help="Largest DCR over every check, story and load case. Green ≤ 0.90, amber to 1.00, red above.")
            k2.metric(f"Governing case · story {gstory}" if gcase_all else "Governing case",
                      LABEL[gcase_all] if gcase_all else "—", border=True, height="stretch",
                      help=f"Governing check: {gchk}" if gchk else None)
            vmax = max((v for v in vs.values() if v is not None), default=None)
            k3.metric("Base shear V (strength)", "—" if vmax is None else f"{vmax / 1000:,.2f} kips", border=True,
                      height="stretch",
                      help=" · ".join(f"{LABEL[c]} {v / 1000:,.2f} kips" for c, v in vs.items() if v is not None))
            height_ft = float(pd.to_numeric(loads["h_ft"], errors="coerce").fillna(0).sum())
            k4.metric("Wall stack", f"{n} stories", border=True, height="stretch",
                      help=f"b = {float(g['b_ft'] or 0):g} ft, H = {height_ft:g} ft")

    # ---- header actions: file menu and the report
    with header_actions:
        with st.popover("File", icon=":material/folder_open:"):
            up = st.file_uploader("Open inputs (.json)", type="json", key="inputs_upload")
            if up is not None:
                marker = (up.name, up.size)
                if st.session_state.get("last_upload") != marker:
                    try:
                        text = up.getvalue().decode("utf-8")
                        apply_cases(cases_from_json(text))
                        saved = preferences_from_project(text)
                        if saved is not None:
                            apply_prefs(saved)
                        st.session_state["last_upload"] = marker
                        st.rerun()
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Could not read inputs file: {exc}")
            if cases:
                st.download_button("Save inputs (.json)", cases_to_json(cases, prefs), file_name="shearwall_inputs.json",
                                   mime="application/json", width="stretch", icon=":material/save:",
                                   help="Both load cases and the project's preferred materials.")
            st.button("Load WoodWorks 5-story example", on_click=on_load_example, width="stretch",
                      icon=":material/menu_book:", help="Loads the example with component ids for the selected data source.")
        if valid:
            gcase = reports.pick_case(cs, reports.GOV_AUTO)
            st.download_button(f"Calculation report ({LABEL[gcase]})", reports.html_report(cs, gcase),
                               file_name=f"{reports.file_stem(cs, gcase)}_report.html", mime="text/html",
                               key="dl_report_top", type="primary", icon=":material/description:",
                               help="One self-contained HTML report from src/report for the governing load case. "
                                    "Open it and print to PDF from the browser. More options are on the Report tab.")
        else:
            st.button("Calculation report", disabled=True, icon=":material/description:", help="Needs valid inputs.")

    # ---- middle: the individual shear wall
    if not edit_all:
        with col_m:
            with card("mid", f"Shear wall: story {sel}", "arrows"):
                if not valid:
                    st.caption("The wall view appears once the inputs are valid.")
                else:
                    active = cs.cases
                    view_opts = [GOV_AUTO] + [LABEL[c] for c in active]
                    if st.session_state.get("view_case") not in view_opts:
                        st.session_state["view_case"] = GOV_AUTO
                    v_choice = st.segmented_control("Load case shown", view_opts, key="view_case", required=True)
                    gdcr, gcase_s = cs.story_dcr(sel)
                    vcase = (gcase_s or active[0]) if v_choice == GOV_AUTO else next(c for c in active if LABEL[c] == v_choice)
                    st.caption(f"Governing for story {sel}: **{LABEL.get(gcase_s, 'none yet')}** · max DCR "
                               f"**{'—' if gdcr is None else f'{gdcr:.2f}'}** · showing {LABEL[vcase].lower()}")
                    s_in = cs.inputs[vcase].stories[sel - 1]
                    r = cs.results[vcase]
                    comp_ck = next((c for c in r.stories[sel - 1].checks if c.category == "compression"), None)
                    V, vv = cs.num(vcase, f"S{sel}.statics.V"), cs.num(vcase, f"S{sel}.shear.v")
                    wdl, Mot = cs.num(vcase, f"S{sel}.statics.w_D"), cs.num(vcase, f"S{sel}.statics.M_OT")
                    T = cs.num(vcase, f"S{sel}.chord.asd.T")
                    C = comp_ck.demand if comp_ck is not None else None
                    sdcr = r.stories[sel - 1].max_dcr
                    fill = {"#DCFCE7": "#F0FDF4", "#FEF3C7": "#FFFBEB", "#FEE2E2": "#FEF2F2"}.get(dcr_colour(sdcr), "#F4F7F5")
                    fbd_col, val_col = st.columns([3, 1.6], vertical_alignment="center")
                    fbd_col.markdown(img_html(fbd_svg(story=sel, b_ft=cs.inputs[vcase].b_ft, h_ft=s_in.h_ft, V=V, v=vv,
                                                      w_dl=wdl, T=T, C=C, tie_label=tie_label(s_in), tone_fill=fill),
                                              f"Free-body diagram of story {sel}"), unsafe_allow_html=True)
                    val_col.table(pd.DataFrame(
                        [("Story shear V", f"{fmt_num(V)} lb"), ("Unit shear v (ASD)", f"{fmt_num(vv)} plf"),
                         ("Overturning M_OT", f"{fmt_num(Mot)} ft-lb"), ("Dead load w_D (cum.)", f"{fmt_num(wdl)} plf"),
                         ("Uplift T (ASD)", f"{fmt_num(T)} lb"), ("Compression C (ASD)", f"{fmt_num(C)} lb")],
                        columns=["Quantity", "Value"]).set_index("Quantity"),
                        alt=f"Key forces for story {sel}")
                    val_col.caption("V and M_OT at strength level.")

        # ---- right: capacities and checks (click a row for its calc trace)
        @st.dialog("Calc trace", width="large", position="right", icon=":material/functions:")
        def trace_dialog(case: str, check_id: str) -> None:
            ck = cs.results[case].check(check_id)
            st.markdown(f"**{ck.name}** · {LABEL[case]} · `{ck.id}`")
            if ck.dcr is not None:
                d1, d2, d3 = st.columns(3)
                d1.metric("Demand", f"{ck.demand:,.4g} {ck.demand_unit}", border=True)
                d2.metric("Capacity", f"{ck.capacity:,.4g} {ck.capacity_unit}", border=True)
                d3.metric("DCR", f"{ck.dcr:.3f}", border=True)
            if ck.message:
                st.info(ck.message + (f" ({ck.decision})" if ck.decision else ""), icon=":material/info:")
            if st.toggle("Render equations", key="trace_dialog_latex"):
                for s_ in ck.steps:
                    st.latex(s_.equation_latex)
                    st.caption(f"{s_.name}: {s_.substitution} = {s_.value} {s_.unit} · {s_.citation} · {s_.status}")
            else:
                st.dataframe(tables.trace_frame(ck.steps), hide_index=True,
                             column_config={"Citation": st.column_config.TextColumn(width="large"),
                                            "Substitution": st.column_config.TextColumn(width="large")})

        with col_r:
            with card("right", f"Capacities and checks: story {sel}", "list"):
                if not valid:
                    st.caption("Checks appear once the inputs are valid.")
                else:
                    ck_df = tables.checks_frame(cs, sel)
                    ev = st.dataframe(
                        ck_df, key=f"checks_{ver}_{sel}", on_select="rerun", selection_mode="single-row",
                        hide_index=True, column_order=["Check", "DCR", "Case", "Demand", "Capacity", "Source"],
                        column_config={
                            "Check": st.column_config.TextColumn("Check", width="medium"),
                            "DCR": st.column_config.ProgressColumn("DCR", min_value=0.0, max_value=tables.DCR_MAX,
                                                                   format="%.2f", width="small",
                                                                   help="Governing load case; bar runs to 1.2"),
                            "Case": st.column_config.TextColumn("Case", width="small", help="S seismic, W wind"),
                            "Source": st.column_config.TextColumn("Source", width="small",
                                                                  help="Weakest source status of the numbers")})
                    st.caption("Select a row to open its calc trace. Bars show the governing load case (S or W).")
                    rows = ev.selection.rows if ev is not None else []
                    marker = (ver, sel, rows[0]) if rows else None
                    if marker and st.session_state.get("trace_open") != marker:
                        st.session_state["trace_open"] = marker
                        row = ck_df.iloc[rows[0]]
                        trace_dialog(row["case_id"], row["check_id"])
                    elif not marker:
                        st.session_state.pop("trace_open", None)
                    for c in cs.cases:
                        for ck in cs.results[c].stories[sel - 1].checks:
                            if ck.status.value == "needs_input":
                                st.warning(f"{LABEL[c]}: {ck.name}: {ck.message}", icon=":material/pending:")
                            elif ck.category == "detailing" and ck.message:
                                st.caption(f"{LABEL[c]}: {ck.message}")

    # ---- bottom: whole-stack summary
    if valid:
        with card("summary", "Wall stack summary", "layers", "coloured by DCR"):
            ca, cb = st.columns([1.35, 2.15], vertical_alignment="center")
            inp0 = cs.primary
            dcrs = {i: cs.story_dcr(i)[0] for i in range(1, n + 1)}
            force_lines, notes = {}, {}
            for i in range(1, n + 1):
                lines = []
                fe, fw = float(fv(loads.at[i, "F_seismic_lb"])), float(fv(loads.at[i, "F_wind_lb"]))
                if fe > 0:
                    lines.append(f"E = {fe:,.0f} lb")
                if fw > 0:
                    lines.append(f"W = {fw:,.0f} lb")
                force_lines[i] = lines or ["no force"]
                gc = cs.story_governing_check(i)
                case = cs.story_dcr(i)[1]
                notes[i] = f"{(gc or '').split('.', 1)[-1]} ({SHORT.get(case, '')})" if gc else ""
            with ca:
                st.markdown(img_html(stack_svg(inp0, None, selected=sel, story_dcrs=dcrs, force_lines=force_lines,
                                               notes=notes), "Wall stack elevation coloured by DCR"),
                            unsafe_allow_html=True)
            with cb:
                hm = tables.heatmap_frame(cs, n)
                pick = alt.selection_point(name="pick", fields=["story"], on="click")
                order = [f"Story {i}" for i in range(n, 0, -1)]
                base = alt.Chart(hm).encode(
                    x=alt.X("Check:N", sort=tables.HEAT_COLS, title=None,
                            axis=alt.Axis(labelAngle=0, orient="top", labelLimit=120, labelFontSize=12)),
                    y=alt.Y("Story:N", sort=order, title=None))
                rect = base.mark_rect(stroke="white", strokeWidth=2, cornerRadius=3).encode(
                    color=alt.Color("Band:N", title="DCR", scale=alt.Scale(domain=list(DCR_COLORS),
                                                                         range=list(DCR_COLORS.values())),
                                    legend=alt.Legend(orient="bottom")),
                    opacity=alt.condition(pick, alt.value(1.0), alt.value(0.55)),
                    tooltip=["Story", alt.Tooltip("Name:N", title="Check"), alt.Tooltip("DCR:Q", format=".3f"),
                             "Case"]).add_params(pick)
                text = base.mark_text(fontSize=13, fontWeight=600, color="white").encode(text="Label:N")
                st.altair_chart((rect + text).properties(height=46 * n + 70), key="heatmap", on_select=on_heatmap_select,
                                selection_mode="pick", alt="Heatmap of demand/capacity by story and check")
                st.caption("Governing DCR by story and check over both load cases. Click a cell to select that story.")

            sched = tables.schedule_frame(cs, n)
            prog = lambda label: st.column_config.ProgressColumn(label, min_value=0.0, max_value=tables.DCR_MAX,  # noqa: E731
                                                                 format="%.2f")
            st.markdown(section_header("Schedule", "list"), unsafe_allow_html=True)
            st.dataframe(sched, hide_index=True, column_order=[
                "Story", "Status", "Governs", "Shear", "Compression", "Tie-down DCR", "Drift", "Nailing", "Sides",
                "v (plf)", "v allow (plf)", "Posts", "Tie-down", "Uplift T (lb)"], column_config={
                "Story": st.column_config.NumberColumn("Story", pinned=True, width="small"),
                "Status": st.column_config.TextColumn("Status", width="small"),
                "Sides": st.column_config.NumberColumn("Sides", width="small"),
                "v (plf)": st.column_config.NumberColumn("v (plf)", format="%.0f"),
                "v allow (plf)": st.column_config.NumberColumn("v allow (plf)", format="%.0f"),
                "Uplift T (lb)": st.column_config.NumberColumn("Uplift T (lb)", format="%.0f"),
                "Shear": prog("Shear"), "Compression": prog("Compression"), "Tie-down DCR": prog("Tie-down"),
                "Drift": prog("Drift")})

    # ---- auto-size proposal (opened from the control row or the Materials tab)
    @st.dialog("Auto-size proposal", width="large", on_dismiss=on_close_autosize, icon=":material/auto_fix_high:")
    def autosize_dialog() -> None:
        prop = st.session_state.get("autosize")
        if not prop:
            st.caption("Run Auto-size first.")
            return
        a_res = prop["result"]
        if prop["snapshot"] != (cases_to_json(cases, prefs) if cases else ""):
            st.info("Inputs or preferred materials changed since this proposal; run Auto-size again.",
                    icon=":material/update:")
        df = tables.autosize_frame(a_res)
        bar = lambda c: st.column_config.ProgressColumn(c, min_value=0.0, max_value=tables.DCR_MAX, format="%.2f",  # noqa: E731
                                                        width="small", help="Worst load case, after the change")
        st.dataframe(df, hide_index=True,
                     column_order=["Story", "Result", "Nailing", "Posts", "Tie-down", "Shear", "Compression", "Tension",
                                   "Drift", "Notes"],
                     column_config={"Story": st.column_config.NumberColumn(width="small"),
                                    "Result": st.column_config.TextColumn(width="small"),
                                    "Nailing": st.column_config.TextColumn("Nailing (proposed)", width="medium"),
                                    "Posts": st.column_config.TextColumn("Posts (proposed)", width="medium"),
                                    "Tie-down": st.column_config.TextColumn("Tie-down (proposed)", width="small"),
                                    "Shear": bar("Shear"), "Compression": bar("Compression"), "Tension": bar("Tension"),
                                    "Drift": bar("Drift"), "Notes": st.column_config.TextColumn(width="large")})
        changed = any(sp.changes for sp in a_res.stories)
        if changed:
            with st.expander("Current → proposed, story by story", icon=":material/compare_arrows:"):
                for sp in a_res.stories:
                    for c in sp.changes:
                        st.markdown(f"**Story {sp.story} · {c.field}:** {tables.short_selection(c.current)} → "
                                    f"**{tables.short_selection(c.proposed)}**")
        else:
            st.caption("The current selections are already the lightest preferred options that pass.")
        with st.container(horizontal=True, horizontal_alignment="right"):
            st.button("Close", key="autosize_close", on_click=on_close_autosize)
            st.button("Apply proposal", key="autosize_apply", type="primary", on_click=on_apply_autosize,
                      disabled=not changed, icon=":material/check:")

    if st.session_state.get("autosize_open"):
        autosize_dialog()

# ------------------------------------------------------------------ calc trace
with tab_trace:
    if not valid:
        st.info("Run needs valid inputs first.", icon=":material/info:")
    else:
        with st.container(horizontal=True, vertical_alignment="bottom", gap="medium"):
            tcase = st.segmented_control("Load case", cs.cases, key="trace_case", format_func=lambda c: LABEL[c],
                                         required=True, default=cs.cases[0])
            res = cs.results[tcase]
            story = st.segmented_control("Story", [s.story for s in res.stories], key="trace_story", required=True,
                                         default=1, format_func=lambda i: f"Story {i}")
            render_eq = st.toggle("Render equations (slower)", value=False)
        for c in res.stories[story - 1].checks:
            dcr = "" if c.dcr is None else f" · DCR {c.dcr:.3f}"
            icon = {"pass": ":material/check_circle:", "fail": ":material/cancel:",
                    "needs_input": ":material/pending:"}.get(c.status.value, ":material/info:")
            with st.expander(f"{c.name} · {c.status.value}{dcr}", icon=icon):
                st.caption(c.id)
                if c.message:
                    st.info(c.message + (f" ({c.decision})" if c.decision else ""), icon=":material/info:")
                if c.steps:
                    if render_eq:
                        for s_ in c.steps:
                            st.latex(s_.equation_latex)
                            st.caption(f"{s_.substitution}  =  {s_.value} {s_.unit}  ·  {s_.citation}  ·  {s_.status}  ·  {s_.id}")
                    else:
                        st.dataframe(tables.trace_frame(c.steps), hide_index=True,
                                     column_config={"Citation": st.column_config.TextColumn(width="large")})
        with st.expander("Stack: load combinations, story forces, chord forces", icon=":material/stacks:"):
            st.dataframe(tables.trace_frame(res.stack_steps), hide_index=True,
                         column_config={"Citation": st.column_config.TextColumn(width="large")})


# ------------------------------------------------------------------ engineering basis
def read_doc(name: str) -> str | None:
    f = repo_root() / "docs" / name
    try:
        return f.read_text(encoding="utf-8")
    except OSError:
        return None


WIDE = {"Citation": st.column_config.TextColumn(width="large"), "Note": st.column_config.TextColumn(width="medium"),
        "Equation": st.column_config.TextColumn(width="medium")}

with tab_basis:
    st.markdown(section_header("Editions", "layers"), unsafe_allow_html=True)
    with st.container(horizontal=True):
        for e in EDITIONS:
            st.badge(e, color="green")
    st.markdown(section_header("Code factors used by the checks", "list", "src/design/factors.py"), unsafe_allow_html=True)
    st.caption("Every factor with its value, citation and source status. 'memory' means taken from the WoodWorks example and "
               "not yet checked against the standard (see Items to verify).")
    frows = [{"Factor": k, "Value": v.value, "Citation": v.citation, "Status": v.status}
             for k, v in vars(code_factors).items() if isinstance(v, code_factors.Factor)]
    frows += [{"Factor": f"C_F (Fc) · {sp} {gr} {nom}", "Value": v.value, "Citation": v.citation, "Status": v.status}
              for (sp, gr, nom), v in getattr(code_factors, "_SIZE_FACTOR_FC", {}).items()]
    st.dataframe(pd.DataFrame(frows), hide_index=True, column_config=WIDE)

    if valid:
        st.markdown(section_header("Load combinations and ASD factors", "arrows", "src/design/combos.py"), unsafe_allow_html=True)
        for c in cs.cases:
            steps = [x for x in cs.results[c].stack_steps if x.id.startswith("combo.")]
            with st.expander(f"{LABEL[c]}: {len(steps)} combination steps", expanded=(c == cs.cases[0])):
                st.dataframe(pd.DataFrame([{"Step": x.id, "Name": x.name, "Symbol": x.symbol, "Equation": x.equation_latex,
                                            "Value": str(x.value), "Citation": x.citation, "Status": x.status,
                                            "Note": x.note} for x in steps]), hide_index=True, column_config=WIDE)
        st.markdown(section_header("Stack forces, overturning and chord forces", "ruler", "src/analysis · src/design/chords.py"),
                    unsafe_allow_html=True)
        for c in cs.cases:
            steps = [x for x in cs.results[c].stack_steps if not x.id.startswith("combo.")]
            with st.expander(f"{LABEL[c]}: {len(steps)} steps (all stories)"):
                st.dataframe(pd.DataFrame([{"Step": x.id, "Name": x.name, "Symbol": x.symbol, "Equation": x.equation_latex,
                                            "Substitution": x.substitution, "Value": str(x.value), "Unit": x.unit,
                                            "Citation": x.citation, "Status": x.status} for x in steps]),
                             hide_index=True, column_config=WIDE)
    st.markdown(section_header("Component tables", "grid", "src/design/components"), unsafe_allow_html=True)
    st.dataframe(pd.DataFrame(lib.status_counts()).T.fillna(0).astype(int))
    doc = read_doc("design-engine.md")
    if doc:
        with st.expander("Design engine documentation (docs/design-engine.md)", icon=":material/menu_book:"):
            st.markdown(doc)

# ------------------------------------------------------------------ items to verify
with tab_verify:
    st.subheader("Component library status")
    st.dataframe(pd.DataFrame(lib.status_counts()).T.fillna(0).astype(int))
    items = lib.items_to_verify()
    st.caption(f"{len(items)} component rows are not yet verified.")
    if valid:
        for c in cs.cases:
            res = cs.results[c]
            st.subheader(f"{LABEL[c]}: component rows used with status 'memory'")
            st.write(list(res.component_items_to_verify) or "none")
            st.caption(f"{len(res.unverified_steps)} calculation steps are not verified or statics")
            if res.unverified_steps:
                with st.expander(f"{LABEL[c]}: list the steps"):
                    st.dataframe(pd.DataFrame([{"Step": s.id, "Name": s.name, "Citation": s.citation, "Status": s.status}
                                               for s in res.unverified_steps]), hide_index=True, column_config=WIDE)
    doc = read_doc("engine-verification-checklist.md")
    if doc:
        with st.expander("Engine verification checklist (docs/engine-verification-checklist.md)", icon=":material/checklist:"):
            st.markdown(doc)

# ------------------------------------------------------------------ report
with tab_report:
    st.markdown(section_header("Calculation report", "list", "src/report"), unsafe_allow_html=True)
    if not valid:
        st.caption("Run needs valid inputs first.")
    else:
        st.caption("The report generator renders the engine result: header, inputs, statics and free-body diagrams, "
                   "step-by-step calculations with equations and code references, summary, and the items to verify. One "
                   "report is produced per load case. Open the HTML file and print it to PDF from the browser. Equations "
                   "use KaTeX from a CDN; if your network blocks it, the LaTeX source shows instead.")
        r_choice = st.segmented_control("Report for", reports.choices(cs), key="report_for", required=True,
                                        default=reports.choices(cs)[0])
        rcase = reports.pick_case(cs, r_choice)
        html = reports.html_report(cs, rcase)
        md = reports.markdown_report(cs, rcase)
        stem = reports.file_stem(cs, rcase)
        with st.container(horizontal=True):
            st.download_button("Report (HTML)", html, file_name=f"{stem}_report.html", mime="text/html", key="dl_html",
                               type="primary", icon=":material/description:")
            st.download_button("Report (Markdown)", md, file_name=f"{stem}_report.md", mime="text/markdown", key="dl_md",
                               icon=":material/article:")
            st.download_button("Full result (.json)", result_to_json(cs.results[rcase]), file_name=f"{stem}_result.json",
                               mime="application/json", key="dl_json", icon=":material/data_object:")
            st.download_button("Inputs (.json)", cases_to_json(cases, prefs), file_name="shearwall_inputs.json",
                               mime="application/json", key="dl_inputs_report", icon=":material/save:")
        st.caption(f"Governing case for the whole stack: {LABEL[reports.pick_case(cs, reports.GOV_AUTO)]}. "
                   f"Showing the {LABEL[rcase].lower()} report.")
        if st.toggle("Preview the report here", key="report_preview"):
            st.iframe(html, height=900, alt="Calculation report preview")
