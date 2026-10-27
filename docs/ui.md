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
