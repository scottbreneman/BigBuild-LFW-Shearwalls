"""Path setup and data sources for the Streamlit app (works from source and when frozen by PyInstaller)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    if getattr(sys, "frozen", False):  # PyInstaller bundle
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[2]


def ensure_paths() -> Path:
    """Make ``design``, ``analysis`` (src/) and ``woodworks_example`` (tests/) importable."""
    root = repo_root()
    for p in (root / "src", root / "tests"):
        if p.is_dir() and str(p) not in sys.path:
            sys.path.insert(0, str(p))
    return root


def git_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=repo_root(), capture_output=True,
                             text=True, timeout=3)
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""
