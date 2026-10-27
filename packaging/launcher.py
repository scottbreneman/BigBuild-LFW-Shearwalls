"""Entry point for the packaged app (also works from source: python packaging/launcher.py).

Starts the Streamlit server on localhost and opens the browser. Nothing leaves the machine.
"""

from __future__ import annotations

import os
import sys
import threading
import webbrowser
from pathlib import Path


def selftest(root: Path) -> int:
    """Run the WoodWorks example through the engine using the bundled data. Exit code 0 = OK."""
    for p in (root / "src", root / "tests"):
        if p.is_dir() and str(p) not in sys.path:
            sys.path.insert(0, str(p))
    import woodworks_example as ex
    from design.engine import run_design
    from design.library import default_library
    from ui.io import inputs_from_json, inputs_to_json

    inp = ex.inputs()
    assert inputs_from_json(inputs_to_json(inp)) == inp
    res = run_design(inp, ex.library())
    print(f"example: {res.status.value}, governing {res.governing_check}, max DCR {res.max_dcr:.3f}")
    real = run_design(inp, default_library())
    print(f"project library: {real.status.value} ({len(real.needs_input)} checks need input)")
    ok = res.status.value == "pass" and real.status.value == "incomplete"
    print("SELFTEST OK" if ok else "SELFTEST FAILED")
    return 0 if ok else 1


def main() -> None:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    if "--selftest" in sys.argv:
        sys.exit(selftest(root))
    app = root / "src" / "ui" / "app.py"
    port = int(os.environ.get("SHEARWALL_PORT", "8501"))
    os.environ["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"

    from streamlit.web import cli as stcli

    if os.environ.get("SHEARWALL_NO_BROWSER") != "1":
        threading.Timer(3.0, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    sys.argv = [
        "streamlit", "run", str(app),
        f"--server.port={port}", "--server.address=localhost", "--server.headless=true",
        "--server.fileWatcherType=none", "--browser.gatherUsageStats=false", "--global.developmentMode=false",
    ]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
