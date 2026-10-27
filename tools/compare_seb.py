"""Compare the design engine with the local SEB shear wall spreadsheet.

Prints engine vs spreadsheet for every mapped quantity; writes nothing to disk.
The spreadsheet stays local (git-ignored); set SEB_XLSX if it is not at the
default path under references/.

    .venv\\Scripts\\python tools\\compare_seb.py [--sheet NAME] [--all]
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]

from design.components import load_library  # noqa: E402
from design.engine import run_design  # noqa: E402
import seb_spreadsheet as seb  # noqa: E402

TOL = 0.005


def compare(wb, sheet: str, show_all: bool) -> int:
    print(f"\n=== {sheet}")
    reason = seb.unsupported(wb, sheet)
    if reason:
        print(f"  skipped: {reason}")
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        lib = load_library(seb.component_dir(wb, Path(tmp)))
        results = {run: run_design(seb.inputs_from_sheet(wb, sheet, run), lib) for run in ("design", "drift", "4-term")}
    ws = wb[sheet]
    for run, res in results.items():
        print(f"  engine ({run} run): {res.status.value}; needs input: {[n.check_id for n in res.needs_input]}")
    mismatches = 0
    for i in range(1, seb.N + 1):
        print(f"  -- story {i}")
        for p in [*seb.pairs(i), *seb.four_term_pairs(i)]:
            sheet_v = ws[p.cell].value
            eng = seb.engine_value(results[p.run], p)
            if sheet_v is None or isinstance(sheet_v, str):
                tag, diff = "sheet-only" if eng is None else "engine-only", ""
            elif eng is None:
                tag, diff = ("match" if sheet_v == 0 else "sheet-only"), ""
            else:
                ref = p.scale * float(sheet_v)
                rel = abs(eng - ref) / max(abs(ref), 1e-9) if abs(ref) > 1e-6 else abs(eng - ref)
                ok = rel <= TOL
                reason = seb.known_reason(wb, sheet, i, p)
                tag = "match" if ok else ("known" if reason else "MISMATCH")
                mismatches += tag == "MISMATCH"
                diff = f"{100 * rel:7.2f}%"
            if show_all or tag != "match":
                e = f"{eng:.5g}" if isinstance(eng, float) else str(eng)
                s = f"{p.scale * float(sheet_v):.5g}" if isinstance(sheet_v, (int, float)) else str(sheet_v)
                note = f"  ({seb.known_reason(wb, sheet, i, p)})" if tag == "known" else ""
                print(f"    {tag:11s} {p.label:26s} {p.cell:6s} engine={e:>11} sheet={s:>11} {diff}{note}")
    print(f"  {mismatches} unexplained mismatch(es) beyond {100 * TOL:.1f}%")
    return mismatches


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sheet", choices=seb.SHEETS, help="compare one sheet (default: both)")
    ap.add_argument("--all", action="store_true", help="also list matching quantities")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    path = seb.workbook_path()
    if path is None:
        print("Spreadsheet not found; set SEB_XLSX to its local path.")
        return 2
    wb = seb.load(path)
    total = sum(compare(wb, s, args.all) for s in ([args.sheet] if args.sheet else seb.SHEETS))
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
