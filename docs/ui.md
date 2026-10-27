# Streamlit UI and Windows app

Status: prototype. The UI contains no design logic. It builds `design.inputs.DesignInputs` from forms, calls
`design.engine.run_design`, and shows the returned `DesignResult` and its calc trace.

## Run from source

From the repo root, with the project venv:

```sh
.venv/bin/python -m streamlit run src/ui/app.py          # Linux / macOS
.venv\Scripts\python -m streamlit run src/ui/app.py      # Windows
```

## What is where

| File | Purpose |
| --- | --- |
| `src/ui/app.py` | Streamlit page: Inputs, Results, Calc trace, Items to verify, Report tabs |
| `src/ui/forms.py` | Story tables <-> `DesignInputs` (no formulas) |
| `src/ui/io.py` | Inputs JSON import/export |
| `src/ui/graphic.py` | Stack SVG coloured by story DCR |
| `src/ui/trace_export.py` | Interim Markdown/JSON download of the calc trace (the report builder will replace it) |
| `src/ui/runtime.py` | Path setup; works from source and from the packaged app |
| `packaging/` | PyInstaller spec, launcher, `build_exe.bat`, `run_app.bat` |
| `tests/test_ui.py` | Round-trip, export and headless app tests |

## Materials tab: preferred materials and auto-size

The **Materials** tab narrows the component library to the materials an office or project prefers:
- nailing assemblies (with the allowed sheathed sides and panel type)
- lumber species, grade and size class (with post sizes and a min/max post count)
- rod systems
- hold-downs

Each table shows the library row's values and its status. An empty selection means no restriction.

- **Presets.** Shipped presets live in `presets/` (`woodworks-example.json` and `starter-office.json`). Load one, or upload an office preset, and download the current selection as JSON. The project's copy is saved inside the downloaded inputs file (schema version 2); version 1 files still load.
- **Dropdowns.** The Inputs-tab dropdowns show only preferred options unless *Show all library options* is on. A current selection is always kept.
- **Auto-size** (Inputs tab) calls `design.autosize.autosize`. It proposes, for each story, the lightest preferred nailing, chord posts and tie-down that pass the strength checks. The proposal table shows the changes and the DCRs before and after; **Apply proposal** writes them into the inputs.
  - Posts use the example layout rule (chord *Geometry* = `example`).
  - Drift is reported, not driven.

## Component data source

The sidebar offers two sources.

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
