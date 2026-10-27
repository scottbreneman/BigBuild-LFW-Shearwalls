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

The **Design** tab reads top to bottom in the order an engineer works:

1. **Status first.** A banner (pass / FAIL / incomplete) naming the governing case, story and check, and four key numbers:
   max DCR, governing case, base shear and the stack size.
2. **Project settings**, collapsed to a one-line summary. Inside, grouped as Geometry, Seismic, Wind and Analysis options.
   Short option lists (stories 1–5, wind drift limit, 3-/4-term, dry/green) are always-visible segmented controls; the
   analysis switches are toggles.
3. **One control row**: the **story** selector, the **edit mode** (*One story*, or *All stories* to edit every story at
   once in spreadsheet-like tables), *Show all library options*, and **Auto-size**.
4. **Story view**: wall inputs on the left in tabs (Loads, Nailing, Posts, Tie-down); on the right the free-body diagram
   with a table of its key forces, and the **checks table** with DCR bars. **Select a check row to open its calc trace**
   in a side drawer.
5. **Wall stack summary**: the elevation coloured by DCR, a **story × check heatmap** (click a cell to select that
   story), and the **schedule** as a sortable table with DCR bars.

Seismic and wind forces (lb) are entered per story. Each load type that has a force is run through the engine and,
check by check, the larger demand/capacity ratio is shown with the case that produced it (S or W). There is no load-type
button: leave a load type at 0 on every story to skip it.

**Auto-size** (control row, or the Materials tab) opens a dialog with the proposal: proposed selections per story, the
worst-case DCRs after the change, and *Apply proposal*.

## Header, report and tabs

The header holds a **File** menu (open inputs, save inputs with the preferred materials, load the WoodWorks example) and the
**Calculation report** button, which downloads the self-contained HTML report (from `src/report`) for the governing
load case; print it to PDF from the browser. The **Report** tab lets you pick Governing, Seismic or Wind, download the HTML,
Markdown, full result JSON or inputs JSON, and preview the report in the page. The report loads KaTeX from a CDN; behind a
firewall the LaTeX source shows instead. **Materials** holds the component library (data source, status counts, table
browser) and the preferred materials. **Engineering basis** lists the editions, every code factor in
`src/design/factors.py` with its citation and status, the load combinations, stack forces and chord forces, the component
tables and `docs/design-engine.md`. **Items to verify** adds the open engine checklist. A test
(`test_app_exposes_every_design_input_field`) fails if the engine gains an input the form does not expose.

The theme lives in `.streamlit/config.toml` (green primary colour; red is kept for failing checks). The packaged app's
launcher passes the same values as flags; keep the two in step.

## What is where

| File | Purpose |
| --- | --- |
| `src/ui/app.py` | Streamlit page (Design, Materials, Calc trace, Engineering basis, Items to verify, Report tabs) |
| `src/ui/tables.py` | Result tables as pandas frames for native tables and the heatmap (checks, schedule, auto-size) |
| `src/ui/loadcases.py` | Runs the engine once per load case and reports the governing case per check and story. Could move into `src/design/` |
| `src/ui/reports.py` | Wraps `src/report` (`build_report`, `build_markdown`) for one load case; "Governing" picks the case with the larger max DCR |
| `src/ui/example.py` | The WoodWorks example as a seismic case (Chapter 3) plus a wind case (Tables 4.4 and 4.6); lists the placeholder values |
| `src/ui/forms.py` | Story tables <-> `DesignInputs` (no formulas) |
| `src/ui/io.py` | Inputs JSON import/export (two-case file, and the older single-case file) |
| `src/ui/theme.py` | Green card CSS and HTML builders (KPI row, schedule, checks panel, DCR bars). Presentation only |
| `src/ui/fbd.py` | Free-body loading diagram SVG; every value comes from the calc trace |
| `src/ui/graphic.py` | Stack elevation SVG coloured by DCR |
| `.streamlit/config.toml` | Green Streamlit theme and minimal toolbar; the packaged app passes the same values as flags |
| `packaging/` | PyInstaller spec, launcher, `build_exe.bat`, `run_app.bat` |
| `tests/test_ui.py` | Round-trip, envelope, export and headless app tests |

## Materials tab: preferred materials and auto-size

The **Materials** tab narrows the component library to the materials an office or project prefers:
- nailing assemblies (with the allowed sheathed sides and panel type)
- lumber species, grade and size class (with post sizes and a min/max post count)
- rod systems
- hold-downs

Each table shows the library row's values and its status. An empty selection means no restriction.

- **Presets.** Shipped presets live in `presets/` (`woodworks-example-production.json`, `woodworks-example.json` and `starter-office.json`). Load one, or upload an office preset, and download the current selection as JSON. The project's copy is saved as `material_preferences` inside the downloaded two-case inputs file; files without it still load.
- **Dropdowns.** The Design tab's wall-input dropdowns show only preferred options unless *Show all library options* (in the Capacities and data card) is on. A current selection is always kept.
- **Auto-size** (bottom of the Materials tab) calls `design.autosize.autosize_cases`. It proposes, for each story, the lightest preferred nailing, chord posts and tie-down that pass the strength checks in **every load case with a force** (seismic and wind). The proposal table shows the changes and the worst-case DCRs before and after; **Apply proposal** writes them into the inputs.
  - Posts use the example layout rule (*Chord geometry* = layout rule, in the Chord posts inputs).
  - Drift is reported, not driven.

## Component data source

The *Component data* selector (Capacities and data card) offers two sources.

- *Project component library* (the default) is `src/design/components/data`: the team's SDPWS Table 4.3A assemblies, NDS lumber values, rods and hold-downs.
  - The app opens on the WoodWorks example with its component ids mapped to these tables (`woodworks_example.production_inputs()`; the example passes on them, see `tests/test_production_library_example.py`).
  - It also opens with the *WoodWorks example materials (project library)* preset.
- *WoodWorks example components* are the small answer-key fixtures in `tests/fixtures/woodworks_components` (rows marked `memory`) that the tests use.

Switching the source loads that source's default preset. Inputs are left as entered; use *Load WoodWorks 5-story example* to reload the example with the right ids. Rows still pending report **needs input**, not a pass.

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
