"""Checks that this folder can run the Shear Wall Stack app, and says what is wrong if not.

Run from the repo folder:   .venv\\Scripts\\python check_app.py        (Windows)
                            .venv/bin/python check_app.py             (Linux / macOS)
Copy everything it prints if you need help.
"""

from __future__ import annotations

import importlib
import platform
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
problems: list[str] = []


def line(ok: bool | None, text: str) -> None:
    print(("  [ok]   " if ok else "  [FAIL] " if ok is False else "  [info] ") + text)


print("Shear Wall Stack: install check")
print("Folder:", ROOT)
print()
print("1. Python and packages")
line(None, f"Python {platform.python_version()} ({platform.system()}) at {sys.executable}")
if ".venv" not in sys.executable.replace("\\", "/"):
    line(None, "not running from this folder's .venv (that is fine if the packages below are installed)")
for pkg in ("streamlit", "pandas", "numpy"):
    try:
        m = importlib.import_module(pkg)
        line(True, f"{pkg} {getattr(m, '__version__', '?')}")
    except Exception as exc:  # noqa: BLE001
        line(False, f"{pkg} is not installed ({exc.__class__.__name__}). Run: {Path(sys.executable).name} -m pip install streamlit pandas")
        problems.append(f"missing package {pkg}")

print()
print("2. Files from the newest version (each must contain its marker text; if not, the old file is still there)")
MARKERS = {
    "src/ui/app.py": "Engineering basis",
    "src/ui/forms.py": "global_values_from_cases",
    "src/ui/io.py": "cases_from_json",
    "src/ui/theme.py": "checks_panel_html",
    "src/ui/graphic.py": "story_dcrs",
    "src/ui/fbd.py": "fbd_svg",
    "src/ui/loadcases.py": "run_cases",
    "src/ui/example.py": "example_cases",
    "src/ui/reports.py": "build_report",
    "src/ui/runtime.py": "ensure_paths",
    "src/report/__init__.py": "build_report",
    "src/design/engine.py": "run_design",
    "src/design/factors.py": "OMEGA_SEISMIC",
    "tests/woodworks_example.py": "def inputs",
    ".streamlit/config.toml": "theme",
    "run_app.bat": "streamlit",
}
for rel, marker in MARKERS.items():
    f = ROOT / rel
    if not f.exists():
        line(False, f"{rel} is MISSING")
        problems.append(f"missing {rel}")
        continue
    text = f.read_text(encoding="utf-8", errors="replace")
    if marker not in text:
        line(False, f"{rel} is the OLD version ({f.stat().st_size} bytes, '{marker}' not found)")
        problems.append(f"old file {rel}")
    else:
        line(True, f"{rel} ({f.stat().st_size} bytes)")

print()
print("3. Imports and a test calculation (the WoodWorks example, seismic and wind, plus a report)")
for p in (ROOT / "src", ROOT / "tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
try:
    for mod in ("design.engine", "report", "ui.forms", "ui.io", "ui.theme", "ui.graphic", "ui.fbd", "ui.loadcases",
                "ui.reports", "ui.example", "woodworks_example"):
        importlib.import_module(mod)
    line(True, "all modules import")
    from ui.example import example_cases, example_library
    from ui.loadcases import run_cases
    from ui import reports

    cs = run_cases(example_cases(), example_library())
    dcr, case, story, chk = cs.overall()
    line(cs.valid, f"engine ran both load cases: status {cs.status.value}, governing {case} story {story} {chk}, max DCR {dcr:.3f}")
    html = reports.html_report(cs, cs.cases[0])
    line("<html" in html, f"report built ({len(html) // 1024} KB)")
    if not cs.valid:
        problems.append("engine result not valid")
except Exception:  # noqa: BLE001
    line(False, "an import or calculation failed:")
    print(traceback.format_exc())
    problems.append("import or calculation error")

print()
if problems:
    print("RESULT: PROBLEMS FOUND ->", "; ".join(problems))
    print("Fix the [FAIL] lines above, or send this whole output for help.")
    sys.exit(1)
print("RESULT: ALL GOOD. Start the app with run_app.bat")
