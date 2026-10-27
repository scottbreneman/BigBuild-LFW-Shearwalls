"""Streamlit app: shear wall stack with seismic and wind forces, three-column wall view, and a stack summary.

Run from the repo root:   python -m streamlit run src/ui/app.py
(Windows venv: .venv\\Scripts\\python -m streamlit run src/ui/app.py)

Layout: project settings and capacity data on top; wall inputs on the left, the selected shear wall in the middle,
capacities and checks on the right; the whole-stack summary underneath. The UI holds no design logic: it builds
``design.inputs.DesignInputs`` (one per load case that has forces), runs ``design.engine.run_design`` for each and
reports, check by check, the larger demand/capacity ratio and the load case that produced it.
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

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from design.library import default_library  # noqa: E402
from design import factors as code_factors  # noqa: E402
from design.result import EDITIONS, OverallStatus  # noqa: E402
from ui import forms, reports  # noqa: E402
from ui.example import PLACEHOLDERS, example_cases  # noqa: E402
from ui.fbd import fbd_svg  # noqa: E402
from ui.graphic import dcr_colour, stack_svg  # noqa: E402
from ui.io import cases_from_json, cases_to_json  # noqa: E402
from ui.loadcases import LABEL, SHORT, CaseSet, run_cases  # noqa: E402
from ui.theme import (CSS, bars_html, case_chip, checks_panel_html, kpi_row, page_header, schedule_html,  # noqa: E402
                      section_header, tie_label, tiles_html)
from ui.trace_export import result_to_json  # noqa: E402

SRC_EXAMPLE = "WoodWorks example components"
SRC_PROJECT = "Project component library"
LIB_HELP = ("WoodWorks example = answer-key fixtures in tests/ (rows marked 'memory'). Project library = "
            "src/design/components/data; unverified or missing rows make checks report 'needs input'.")
DRIFT_OPTIONS = [0, 600, 500, 400, 360, 240]
GOV_AUTO = "Governing (auto)"

st.set_page_config(page_title="Shear Wall Stack Designer", layout="wide", initial_sidebar_state="collapsed")
st.markdown(CSS, unsafe_allow_html=True)


# ------------------------------------------------------------------ data sources and state
@st.cache_resource
def get_library(source: str):
    if source == SRC_EXAMPLE:
        from ui.example import example_library
        return example_library()
    return default_library()


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
    n = int(st.session_state["n_stories"])
    st.session_state["base_frames"] = forms.resize_frames(st.session_state["base_frames"], n)
    st.session_state["ver"] += 1
    st.session_state["sel_story"] = min(st.session_state.get("sel_story", 1), n)


def on_load_example() -> None:
    apply_cases(example_cases())
    st.session_state["lib_source"] = SRC_EXAMPLE


@contextmanager
def card(key: str, title: str, icon: str = "", pill: str = ""):
    with st.container(border=True, key=f"card_{key}"):
        st.markdown(section_header(title, icon, pill), unsafe_allow_html=True)
        yield


def img_html(svg: str) -> str:
    return f'<img style="width:100%" src="data:image/svg+xml;base64,{base64.b64encode(svg.encode()).decode()}"/>'


if "base_frames" not in st.session_state:
    apply_cases(example_cases())
    st.session_state["lib_source"] = SRC_EXAMPLE
if st.session_state.get("lib_source") not in (SRC_EXAMPLE, SRC_PROJECT):
    st.session_state["lib_source"] = SRC_EXAMPLE

# ------------------------------------------------------------------ sidebar (file in)
with st.sidebar:
    st.header("Files")
    up = st.file_uploader("Load inputs (.json)", type="json")
    if up is not None:
        marker = (up.name, up.size)
        if st.session_state.get("last_upload") != marker:
            try:
                apply_cases(cases_from_json(up.getvalue().decode("utf-8")))
                st.session_state["last_upload"] = marker
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                st.error(f"Could not read inputs file: {exc}")

head_l, head_r = st.columns([5, 1.3])
head_l.markdown(page_header(EDITIONS, "Prototype · needs PE review"), unsafe_allow_html=True)
report_slot = head_r.container()
tab_design, tab_trace, tab_basis, tab_verify, tab_report = st.tabs(
    ["Design", "Calc trace", "Engineering basis", "Items to verify", "Report"])

with tab_design:
    top_l, top_r = st.columns([3, 2])
    # ---------------------------------------------------------------- project settings
    with top_l:
        with card("project", "Project settings", "pin", "ASCE 7-22 · SDPWS 2021 · NDS 2024"):
            a, b, c, d = st.columns(4)
            a.text_input("Project name", key="g_project_name")
            b.selectbox("Stories (1 = bottom)", [1, 2, 3, 4, 5], key="n_stories", on_change=on_resize)
            c.number_input("Wall length b (ft)", min_value=0.0, step=0.5, key="g_b_ft")
            d.number_input("End post d_post (in); 0 = not given", min_value=0.0, step=0.5, key="g_d_post_in",
                           help="Default chord lever arm (decision D2). Not needed when every story has its own d arm.")
            e, f, g1, h1, i1 = st.columns(5)
            e.selectbox("Risk category", ["I", "II", "III", "IV"], key="g_risk_category")
            f.selectbox("Seismic design category", ["", "A", "B", "C", "D", "E", "F"], key="g_sdc")
            g1.number_input("S_DS", min_value=0.0, step=0.01, key="g_S_DS", format="%.3f")
            h1.number_input("C_d", min_value=0.0, step=0.5, key="g_C_d")
            i1.number_input("I_e", min_value=0.0, step=0.05, key="g_I_e")
            j, k, l1, m1 = st.columns(4)
            j.selectbox("Wind drift limit", DRIFT_OPTIONS, key="g_wind_drift_denominator",
                        format_func=lambda x: "none" if not x else f"H / {x}",
                        help="No code limit is applied for wind; the owner or project sets it (decision D6).")
            k.number_input("Net roof uplift (plf, strength)", min_value=0.0, step=10.0, key="g_roof_uplift_plf")
            l1.number_input("Wood bearing amplification", min_value=1.0, step=0.05, key="g_wood_bearing_factor",
                            help="Wood-to-wood crushing amplification (example §3.4.3, engineer judgement).")
            m1.write("")
            m1.checkbox("Carry rotation into drift (D6)", key="g_carry_rotation")
            n1, n2, n3, n4 = st.columns(4)
            n1.selectbox("Deflection method", ["3-term", "4-term"], key="g_deflection_method",
                         help="3-term: SDPWS Eq. 4.3-1 (the example's method). 4-term: SDPWS Commentary C4.3.4-1; needs the "
                              "panel and nail slip constants in the component library (decision D6).")
            n2.selectbox("Framing moisture", ["dry", "green"], key="g_framing_moisture",
                         help="Selects the nail-slip equation (4-term method only).")
            n3.write("")
            n3.checkbox("Tie-down restraint at every level", key="g_restraint_each_level",
                        help="Off: chord deformation accumulates up the building (example Table 3.17B). "
                             "Cannot be combined with 'carry rotation'.")
            with st.expander("Which example values are placeholders?"):
                for p in PLACEHOLDERS:
                    st.markdown(f"- {p}")

    # ---------------------------------------------------------------- capacities and data
    with top_r:
        with card("data", "Capacities and data", "grid"):
            st.selectbox("Component data", [SRC_EXAMPLE, SRC_PROJECT], key="lib_source", help=LIB_HELP)
            lib = get_library(st.session_state["lib_source"])
            counts = pd.DataFrame(lib.status_counts()).T.fillna(0).astype(int)
            tot = counts.sum()
            st.markdown(
                f'<span class="chip src verified">{int(tot.get("verified", 0))} verified</span>'
                f'<span class="chip src memory">{int(tot.get("memory", 0))} memory</span>'
                f'<span class="chip src">{int(tot.get("pending", 0))} pending</span>'
                f'<span class="note"> rows in the capacity tables</span>', unsafe_allow_html=True)
            tables = {"Shear wall assemblies (SDPWS Table 4.3A)": lib.shear_wall_assemblies,
                      "Continuous rod systems": lib.continuous_rod_systems, "Hold-downs": lib.holddowns,
                      "Lumber design values (NDS)": lib.lumber_design_values,
                      "Size factors (NDS Supplement 4A)": lib.size_factors, "Lumber sizes": lib.lumber_sizes,
                      "Sheathing panels": lib.sheathing_panels, "Nails": lib.nails}
            with st.expander("Browse capacity tables"):
                tname = st.selectbox("Table", list(tables), key="data_table")
                recs = [dataclasses.asdict(r) for r in tables[tname]]
                df_t = pd.DataFrame(recs)
                if "status" in df_t:
                    df_t["status"] = df_t["status"].map(lambda x: getattr(x, "value", x))
                st.dataframe(df_t.dropna(axis=1, how="all"), width="stretch", hide_index=True)
            st.button("Load WoodWorks 5-story example", on_click=on_load_example, width="stretch")

    ver = st.session_state["ver"]
    kpi_slot = st.container()
    col_l, col_m, col_r = st.columns([1.15, 1.7, 1.25])

    # ---------------------------------------------------------------- left: inputs for the selected wall
    loads, chords, ties = st.session_state["base_frames"]
    n = len(loads)
    if st.session_state.get("sel_story") not in range(1, n + 1):
        st.session_state["sel_story"] = 1

    def fv(x, default=0.0):
        try:
            return default if pd.isna(x) else x
        except (TypeError, ValueError):
            return x

    def wnum(df, col, label, story, **kw):
        val = st.number_input(label, value=float(fv(df.at[story, col])), key=f"w{ver}_{story}_{col}", **kw)
        df.at[story, col] = val
        return val

    def wchk(df, col, label, story):
        cur = fv(df.at[story, col], True)
        val = st.checkbox(label, value=bool(cur), key=f"w{ver}_{story}_{col}")
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

    def opts_of(values) -> list:
        out = []
        for v in values:
            if isinstance(v, str) and v and v not in out:
                out.append(v)
        return out

    with col_l:
        with card("left", "Wall inputs", "ruler"):
            sel = st.selectbox("Wall (story)", list(range(1, n + 1)), key="sel_story", format_func=lambda i: f"Story {i}")
            with st.expander("Loads", expanded=True):
                a1, a2 = st.columns(2)
                with a1:
                    wnum(loads, "F_seismic_lb", "Seismic F (lb)", sel, min_value=0.0, step=50.0, format="%.0f")
                with a2:
                    wnum(loads, "F_wind_lb", "Wind F (lb)", sel, min_value=0.0, step=50.0, format="%.0f")
                st.caption("Strength-level forces at the top of this story. Leave a load type at 0 on every story to skip it; "
                           "the program checks both and reports which governs.")
                b1, b2 = st.columns(2)
                with b1:
                    wnum(loads, "h_ft", "Height h (ft)", sel, min_value=0.0, step=0.5, format="%.2f")
                    wnum(loads, "w_D_plf", "Dead w_D (plf)", sel, min_value=0.0, format="%.1f")
                    wnum(loads, "w_L_plf", "Floor live w_L (plf)", sel, min_value=0.0, format="%.1f")
                with b2:
                    wnum(loads, "w_wall_plf", "Wall weight (plf)", sel, min_value=0.0, format="%.1f")
                    wnum(loads, "w_Lr_plf", "Roof live w_Lr (plf)", sel, min_value=0.0, format="%.1f")
            with st.expander("Nailing and sheathing", expanded=True):
                wsel(loads, "assembly_id", "Nailing / assembly", sel,
                     opts_of([x.assembly_id for x in lib.shear_wall_assemblies] + list(loads["assembly_id"])))
                c1, c2 = st.columns(2)
                with c1:
                    wsel(loads, "sides", "Sheathed sides", sel, [1, 2], cast=int)
                with c2:
                    wsel(loads, "panel_type", "Panel", sel, ["OSB", "Plywood"])
            with st.expander("Chord posts"):
                d1, d2 = st.columns(2)
                with d1:
                    wnum(chords, "n_posts", "Posts (n)", sel, min_value=1.0, step=1.0, format="%.0f")
                    wnum(chords, "chord_length_ft", "Chord length (ft)", sel, min_value=0.0, step=0.125, format="%.3f")
                with d2:
                    wsel(chords, "post_nominal", "Post", sel, opts_of([x.nominal for x in lib.lumber_sizes] + list(chords["post_nominal"])))
                    wnum(chords, "d_arm_ft", "d arm (ft); 0 = D2 default", sel, min_value=0.0, step=0.05, format="%.2f")
                g1c, g2c, g3c = st.columns(3)
                with g1c:
                    wnum(chords, "d_out_of_plane_in", "Post depth, out of plane (in); 0 = dressed", sel, min_value=0.0,
                         step=0.25, format="%.2f")
                with g2c:
                    wnum(chords, "top_plates_in", "Top plates (in)", sel, min_value=0.0, step=0.5, format="%.2f")
                with g3c:
                    wnum(chords, "bottom_plate_in", "Bottom plate (in)", sel, min_value=0.0, step=0.5, format="%.2f")
                wsel(chords, "species_group", "Species", sel,
                     opts_of(sorted({x.species_group for x in lib.lumber_design_values}) + list(chords["species_group"])))
                e1, e2 = st.columns(2)
                with e1:
                    wsel(chords, "grade", "Grade", sel, opts_of(sorted({x.grade for x in lib.lumber_design_values}) + list(chords["grade"])))
                with e2:
                    wsel(chords, "size_class", "Size class", sel,
                         opts_of(sorted({x.size_class for x in lib.lumber_design_values}) + list(chords["size_class"])))
            with st.expander("Tie-down"):
                kind = wsel(ties, "kind", "Type", sel, [forms.ROD, forms.HOLDDOWN])
                if kind == forms.ROD:
                    wsel(ties, "system_id", "Rod system", sel,
                         opts_of([x.system_id for x in lib.continuous_rod_systems] + list(ties["system_id"].dropna())))
                    f1, f2, f3 = st.columns(3)
                    with f1:
                        wnum(ties, "plate_width_in", "Plate w (in)", sel, min_value=0.0, step=0.25)
                        wnum(ties, "slack_in", "Slack (in)", sel, min_value=0.0, step=0.01, format="%.4f")
                    with f2:
                        wnum(ties, "plate_length_in", "Plate l (in)", sel, min_value=0.0, step=0.25)
                        wnum(ties, "takeup_elongation_in", "Take-up (in)", sel, min_value=0.0, step=0.005, format="%.4f")
                    with f3:
                        wnum(ties, "plate_thickness_in", "Plate t (in)", sel, min_value=0.0, step=0.125, format="%.3f")
                        wnum(ties, "plate_Fy_psi", "Plate Fy (psi)", sel, min_value=0.0, step=1000.0, format="%.0f")
                    wnum(ties, "rod_length_ft", "Rod length (ft); 0 = story h", sel, min_value=0.0, step=0.5)
                    h1, h2 = st.columns(2)
                    with h1:
                        wnum(ties, "bearing_hole_in", "Bearing hole (in); 0 = default", sel, min_value=0.0, step=0.0625, format="%.4f")
                    with h2:
                        wnum(ties, "shrinkage_in", "Shrinkage (in)", sel, min_value=0.0, step=0.01, format="%.3f")
                    wchk(ties, "takeup_device", "Take-up device (counts slack and take-up elongation)", sel)
                else:
                    wsel(ties, "model", "Hold-down model", sel, opts_of([x.model for x in lib.holddowns] + list(ties["model"].dropna())))
                    wnum(ties, "T_allow_lb", "T_allow (lb); 0 = use model", sel, min_value=0.0, step=100.0, format="%.0f")
                    wnum(ties, "delta_a_in", "Δ_a (in)", sel, min_value=0.0, step=0.01, format="%.3f")

    # ---------------------------------------------------------------- run the engine for each load case
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

    with kpi_slot:
        st.markdown(kpi_row(n, float(g["b_ft"] or 0), float(pd.to_numeric(loads["h_ft"], errors="coerce").fillna(0).sum()),
                            cs if valid else None), unsafe_allow_html=True)
        if run_error:
            st.error("The design engine raised an error. Send this to the calc builder.")
            st.code(run_error)
        elif not cases:
            st.info("Enter a seismic and/or wind force for at least one story. Each load type with a force is checked "
                    "and the governing one is reported.")
        elif not valid:
            for case, errs in cs.invalid().items():
                st.error(f"Fix these {LABEL[case].lower()} inputs before the engine will run checks:")
                st.table(pd.DataFrame([{"Field": e.field, "Problem": e.message} for e in errs]))
        else:
            {OverallStatus.PASS: st.success, OverallStatus.FAIL: st.error, OverallStatus.INCOMPLETE: st.warning}[cs.status]({
                OverallStatus.PASS: "All checks pass",
                OverallStatus.FAIL: "One or more checks FAIL",
                OverallStatus.INCOMPLETE: "Incomplete: some checks need engineer input or component data"}[cs.status])

    with report_slot:
        st.write("")
        if valid:
            gcase = reports.pick_case(cs, reports.GOV_AUTO)
            st.download_button(f"Calculation report ({LABEL[gcase]})", reports.html_report(cs, gcase),
                               file_name=f"{reports.file_stem(cs, gcase)}_report.html", mime="text/html",
                               key="dl_report_top", width="stretch", type="primary",
                               help="One self-contained HTML report from src/report for the governing load case. "
                                    "Open it and print to PDF from the browser. More options are on the Report tab.")
        else:
            st.button("Calculation report", disabled=True, width="stretch", help="Needs valid inputs.")

    with st.sidebar:
        if cases:
            st.download_button("Download inputs (.json)", cases_to_json(cases), file_name="shearwall_inputs.json",
                               mime="application/json", width="stretch")

    # ---------------------------------------------------------------- middle: the individual shear wall
    with col_m:
        with card("mid", f"Shear wall: story {sel}", "arrows"):
            if not valid:
                st.info("The wall view appears once the inputs are valid.")
            else:
                active = cs.cases
                view_opts = [GOV_AUTO] + [LABEL[c] for c in active]
                if st.session_state.get("view_case") not in view_opts:
                    st.session_state["view_case"] = GOV_AUTO
                view = st.selectbox("Load case shown", view_opts, key="view_case")
                _, gcase = cs.story_dcr(sel)
                vcase = (gcase or active[0]) if view == GOV_AUTO else next(c for c in active if LABEL[c] == view)
                gdcr, _gc = cs.story_dcr(sel)
                gtxt = "—" if gdcr is None else f"{gdcr:.2f}"
                st.markdown(f'<div class="govbanner"><span>Governing for story {sel}: <b>{LABEL.get(gcase, "none yet")}</b>'
                            f'{case_chip(gcase)}</span><span>max DCR <b>{gtxt}</b></span></div>', unsafe_allow_html=True)
                s_in = cs.inputs[vcase].stories[sel - 1]
                r = cs.results[vcase]
                comp_ck = next((c for c in r.stories[sel - 1].checks if c.category == "compression"), None)
                V, vv = cs.num(vcase, f"S{sel}.statics.V"), cs.num(vcase, f"S{sel}.shear.v")
                wdl, Mot = cs.num(vcase, f"S{sel}.statics.w_D"), cs.num(vcase, f"S{sel}.statics.M_OT")
                T = cs.num(vcase, f"S{sel}.chord.asd.T")
                C = comp_ck.demand if comp_ck is not None else None
                sdcr = r.stories[sel - 1].max_dcr
                fill = {"#DCFCE7": "#F0FDF4", "#FEF3C7": "#FFFBEB", "#FEE2E2": "#FEF2F2"}.get(dcr_colour(sdcr), "#F4F7F5")
                st.markdown(img_html(fbd_svg(story=sel, b_ft=cs.inputs[vcase].b_ft, h_ft=s_in.h_ft, V=V, v=vv, w_dl=wdl,
                                             T=T, C=C, tie_label=tie_label(s_in), tone_fill=fill)), unsafe_allow_html=True)
                fmt = lambda x, nd=0: "—" if x is None else f"{x:,.{nd}f}"  # noqa: E731
                st.markdown(tiles_html([
                    ("Story shear V", fmt(V), f"lb · {LABEL[vcase].lower()}, strength", ""),
                    ("Unit shear v", fmt(vv), "plf · ASD", "k"),
                    ("Overturning M_OT", fmt(Mot), "ft-lb", "o"),
                    ("Wall DL resisting", fmt(wdl), "plf · cumulative", ""),
                    ("Tie-down uplift T", fmt(T), "lb · ASD", "r")]), unsafe_allow_html=True)

    # ---------------------------------------------------------------- right: capacities and checks
    with col_r:
        with card("right", f"Capacities and checks: story {sel}", "list"):
            if not valid:
                st.info("Checks appear once the inputs are valid.")
            else:
                st.markdown('<div class="note">Demand against capacity for the governing load case of each check '
                            '(<span class="chip S">S</span> seismic, <span class="chip W">W</span> wind). Small text shows each '
                            'case, and the source status of the numbers.</div>', unsafe_allow_html=True)
                st.markdown(checks_panel_html(cs, sel), unsafe_allow_html=True)
                for c in cs.cases:
                    for ck in cs.results[c].stories[sel - 1].checks:
                        if ck.status.value == "needs_input":
                            st.warning(f"{LABEL[c]}: {ck.name}: {ck.message}")
                        elif ck.category == "detailing" and ck.message:
                            st.caption(f"{LABEL[c]}: {ck.message}")

    # ---------------------------------------------------------------- bottom: whole-stack summary
    if valid:
        with card("summary", "Wall stack summary", "layers", "colored by max DCR"):
            ca, cb = st.columns([3, 2])
            inp0 = cs.primary
            dcrs = {i: cs.story_dcr(i)[0] for i in range(1, n + 1)}
            force_lines = {}
            notes = {}
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
                                               notes=notes)), unsafe_allow_html=True)
            with cb:
                st.markdown('<div class="note">Max demand/capacity by story over both load cases. Green ≤ 0.90, amber '
                            '0.90 to 1.00, red above 1.00, grey = needs input.</div>', unsafe_allow_html=True)
                st.markdown(bars_html(cs, n), unsafe_allow_html=True)
            st.markdown(section_header("Schedule", "list"), unsafe_allow_html=True)
            st.markdown(schedule_html(cs, n, selected=sel), unsafe_allow_html=True)
            st.markdown('<div class="eqline">v = c · V / b  ·  DCR = demand / capacity  ·  T = max(0, (c · M_OT − λ_D · M_R) / d)  ·  '
                        'M_R = w_D · b² / 2  ·  c = ASD factor for the load case  ·  see the Calc trace tab for each step and its '
                        'code reference</div>', unsafe_allow_html=True)

# ------------------------------------------------------------------ calc trace
with tab_trace:
    if not valid:
        st.info("Run needs valid inputs first.")
    else:
        t1, t2 = st.columns(2)
        tcase = t1.selectbox("Load case", cs.cases, key="trace_case", format_func=lambda c: LABEL[c])
        res = cs.results[tcase]
        story = t2.selectbox("Story", [s.story for s in res.stories], key="trace_story")
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
                             width="stretch", hide_index=True)

        for c in res.stories[story - 1].checks:
            dcr = "" if c.dcr is None else f" · DCR {c.dcr:.3f}"
            with st.expander(f"{c.id} · {c.name} · {c.status.value}{dcr}"):
                if c.message:
                    st.info(c.message + (f" ({c.decision})" if c.decision else ""))
                if c.steps:
                    show_steps(c.steps)
        with st.expander("Stack: load combinations, story forces, chord forces"):
            show_steps(res.stack_steps)

# ------------------------------------------------------------------ engineering basis
def read_doc(name: str) -> str | None:
    f = repo_root() / "docs" / name
    try:
        return f.read_text(encoding="utf-8")
    except OSError:
        return None


with tab_basis:
    st.markdown(section_header("Editions", "layers"), unsafe_allow_html=True)
    st.markdown(" ".join(f'<span class="pill">{e}</span>' for e in EDITIONS), unsafe_allow_html=True)

    st.markdown(section_header("Code factors used by the checks", "list", "src/design/factors.py"), unsafe_allow_html=True)
    st.caption("Every factor with its value, citation and source status. 'memory' means taken from the WoodWorks example and "
               "not yet checked against the standard (see Items to verify).")
    frows = [{"Factor": k, "Value": v.value, "Citation": v.citation, "Status": v.status}
             for k, v in vars(code_factors).items() if isinstance(v, code_factors.Factor)]
    frows += [{"Factor": f"C_F (Fc) · {sp} {gr} {nom}", "Value": v.value, "Citation": v.citation, "Status": v.status}
              for (sp, gr, nom), v in getattr(code_factors, "_SIZE_FACTOR_FC", {}).items()]
    st.dataframe(pd.DataFrame(frows), width="stretch", hide_index=True)

    if valid:
        st.markdown(section_header("Load combinations and ASD factors", "arrows", "src/design/combos.py"), unsafe_allow_html=True)
        for c in cs.cases:
            steps = [x for x in cs.results[c].stack_steps if x.id.startswith("combo.")]
            with st.expander(f"{LABEL[c]}: {len(steps)} combination steps", expanded=(c == cs.cases[0])):
                st.dataframe(pd.DataFrame([{"Step": x.id, "Name": x.name, "Symbol": x.symbol, "Equation": x.equation_latex,
                                            "Value": str(x.value), "Citation": x.citation, "Status": x.status,
                                            "Note": x.note} for x in steps]), width="stretch", hide_index=True)
        st.markdown(section_header("Stack forces, overturning and chord forces", "ruler", "src/analysis · src/design/chords.py"),
                    unsafe_allow_html=True)
        for c in cs.cases:
            steps = [x for x in cs.results[c].stack_steps if not x.id.startswith("combo.")]
            with st.expander(f"{LABEL[c]}: {len(steps)} steps (all stories)"):
                st.dataframe(pd.DataFrame([{"Step": x.id, "Name": x.name, "Symbol": x.symbol, "Equation": x.equation_latex,
                                            "Substitution": x.substitution, "Value": str(x.value), "Unit": x.unit,
                                            "Citation": x.citation, "Status": x.status} for x in steps]),
                             width="stretch", hide_index=True)
    st.markdown(section_header("Component tables", "grid", "src/design/components"), unsafe_allow_html=True)
    st.dataframe(pd.DataFrame(lib.status_counts()).T.fillna(0).astype(int), width="stretch")
    doc = read_doc("design-engine.md")
    if doc:
        with st.expander("Design engine documentation (docs/design-engine.md)"):
            st.markdown(doc)

# ------------------------------------------------------------------ items to verify
with tab_verify:
    st.subheader("Component library status")
    st.dataframe(pd.DataFrame(lib.status_counts()).T.fillna(0).astype(int), width="stretch")
    items = lib.items_to_verify()
    st.write(f"{len(items)} component rows are not yet verified.")
    if valid:
        for c in cs.cases:
            res = cs.results[c]
            st.subheader(f"{LABEL[c]}: component rows used with status 'memory'")
            st.write(list(res.component_items_to_verify) or "none")
            st.write(f"{len(res.unverified_steps)} calculation steps are not verified or statics")
            if res.unverified_steps:
                with st.expander(f"{LABEL[c]}: list the steps"):
                    st.dataframe(pd.DataFrame([{"Step": s.id, "Name": s.name, "Citation": s.citation, "Status": s.status}
                                               for s in res.unverified_steps]), width="stretch", hide_index=True)
    doc = read_doc("engine-verification-checklist.md")
    if doc:
        with st.expander("Engine verification checklist (docs/engine-verification-checklist.md)"):
            st.markdown(doc)

# ------------------------------------------------------------------ report
with tab_report:
    st.markdown(section_header("Calculation report", "list", "src/report"), unsafe_allow_html=True)
    if not valid:
        st.write("Run needs valid inputs first.")
    else:
        st.markdown('<div class="note">The report generator renders the engine result: header, inputs, statics and free-body '
                    'diagrams, step-by-step calculations with equations and code references, summary, and the items to '
                    'verify. One report is produced per load case. Open the HTML file and print it to PDF from the browser. '
                    'Equations use KaTeX from a CDN; if your network blocks it, the LaTeX source shows instead.</div>',
                    unsafe_allow_html=True)
        r_choice = st.selectbox("Report for", reports.choices(cs), key="report_for")
        rcase = reports.pick_case(cs, r_choice)
        html = reports.html_report(cs, rcase)
        md = reports.markdown_report(cs, rcase)
        stem = reports.file_stem(cs, rcase)
        b1, b2, b3, b4 = st.columns(4)
        b1.download_button("Report (HTML)", html, file_name=f"{stem}_report.html", mime="text/html", key="dl_html",
                           width="stretch", type="primary")
        b2.download_button("Report (Markdown)", md, file_name=f"{stem}_report.md", mime="text/markdown", key="dl_md",
                           width="stretch")
        b3.download_button("Full result (.json)", result_to_json(cs.results[rcase]), file_name=f"{stem}_result.json",
                           mime="application/json", key="dl_json", width="stretch")
        b4.download_button("Inputs (.json)", cases_to_json(cases), file_name="shearwall_inputs.json",
                           mime="application/json", key="dl_inputs_report", width="stretch")
        st.caption(f"Governing case for the whole stack: {LABEL[reports.pick_case(cs, reports.GOV_AUTO)]}. "
                   f"Showing the {LABEL[rcase].lower()} report.")
        if st.toggle("Preview the report here", key="report_preview"):
            import streamlit.components.v1 as components
            components.html(html, height=900, scrolling=True)
