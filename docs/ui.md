# Streamlit UI and Windows app

Status: prototype. The UI contains no design logic. It builds `design.inputs.DesignInputs` from forms, calls
`design.engine.run_design`, and shows the returned `DesignResult` and its calc trace.

## Run from source

From the repo root, with the project venv:

```sh
.venv/bin/python -m streamlit run src/ui/app.py          # Linux / macOS
.venv\Scripts\python -m streamlit run src/ui/app.py      # Windows
```

## Layout

Top row: **Project settings** (stories, wall length, risk category, SDC, S_DS, C_d, I_e, wind drift limit, roof uplift) and
**Capacities and data** (component data source, status counts, a browser for the capacity tables). Below, three columns:
**wall inputs** for the selected story (left), the **selected shear wall** as a free-body diagram (middle), and
**capacities and checks** (right). The **wall stack summary** (elevation, DCR bars, schedule) sits underneath.

Seismic and wind forces (lb) are entered per story. Each load type that has a force is run through the engine and,
check by check, the larger demand/capacity ratio is shown with the case that produced it (S or W). There is no load-type
button: leave a load type at 0 on every story to skip it.

## Report button and tabs

The top-right **Calculation report** button downloads the self-contained HTML report (from `src/report`) for the governing
load case; print it to PDF from the browser. The **Report** tab lets you pick Governing, Seismic or Wind, download the HTML,
Markdown, full result JSON or inputs JSON, and preview the report in the page. The report loads KaTeX from a CDN; behind a
firewall the LaTeX source shows instead. **Engineering basis** lists the editions, every code factor in
`src/design/factors.py` with its citation and status, the load combinations, stack forces and chord forces, the component
tables and `docs/design-engine.md`. **Items to verify** adds the open engine checklist. A test
(`test_app_exposes_every_design_input_field`) fails if the engine gains an input the form does not expose.

## What is where

| File | Purpose |
| --- | --- |
| `src/ui/app.py` | Streamlit page (Design, Calc trace, Items to verify, Report tabs) |
| `src/ui/loadcases.py` | Runs the engine once per load case and reports the governing case per check and story. Could move into `src/design/` |
| `src/ui/reports.py` | Wraps `src/report` (`build_report`, `build_markdown`) for one load case; "Governing" picks the case with the larger max DCR |
| `src/ui/example.py` | The WoodWorks example as a seismic case (Chapter 3) plus a wind case (Tables 4.4 and 4.6); lists the placeholder values |
| `src/ui/forms.py` | Story tables <-> `DesignInputs` (no formulas) |
| `src/ui/io.py` | Inputs JSON import/export (two-case file, and the older single-case file) |
| `src/ui/theme.py` | Green card CSS and HTML builders (KPI row, schedule, checks panel, DCR bars). Presentation only |
| `src/ui/fbd.py` | Free-body loading diagram SVG; every value comes from the calc trace |
| `src/ui/graphic.py` | Stack elevation SVG coloured by DCR |
| `.streamlit/config.toml` | Green Streamlit theme; the packaged app passes the same values as flags |
| `packaging/` | PyInstaller spec, launcher, `build_exe.bat`, `run_app.bat` |
| `tests/test_ui.py` | Round-trip, envelope, export and headless app tests |

## Component data source

The sidebar offers two sources. *WoodWorks example components* are the answer-key fixtures in
`tests/fixtures/woodworks_components` (rows marked `memory`). *Project component library* is
`src/design/components/data`; until engineers fill and verify rows, checks report **needs input**, not a pass.

## Windows app (not yet verified on Windows)

On a Windows machine, from the repo root with the venv active:

```bat
packaging\build_exe.bat
dist\ShearWallStack\ShearWallStack.exe --selftest
dist\ShearWallStack\ShearWallStack.exe
```

Keep the whole `dist\ShearWallStack` folder together. The build was trial-run on Linux only (spec, bundled data,
`--selftest`, and a headless session of the frozen app). The Linux folder is about 350 MB, mostly Streamlit's
dependencies.
