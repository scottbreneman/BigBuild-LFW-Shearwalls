"""What still needs an engineer's check, and where to change it.

Two things carry a source status (docs/hackathon-plan.md): the calculation steps in the
engine source, and the rows of the component library. This reads both and prints the work
that is left, hardest-hitting first, with the file and line to edit.

    python tools/verification_worklist.py                  # Markdown to stdout
    python tools/verification_worklist.py -o docs/verification-worklist.md
    python tools/verification_worklist.py --library production

Nothing here is hard-coded: re-run it after verifying something and the list shrinks.

To close an item out:

* a calculation step: change its ``status`` from ``"memory"`` / ``"assumption"`` to
  ``"verified"`` at the file and line shown, and name the checker and date in the commit.
* a component row: set ``status=verified`` and fill ``checked_by`` in the CSV, as the
  SDPWS Table 4.3A rows already do.
"""

from __future__ import annotations

import argparse
import ast
import csv
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "src", ROOT / "tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

UNVERIFIED = ("memory", "assumption")
# Step status is the 9th positional argument of Tracer.step (see src/design/trace.py).
_STATUS_ARG, _CITATION_ARG, _KEY_ARG, _NAME_ARG = 8, 7, 0, 1
CODES = ("SDPWS", "NDS", "ASCE", "AISC", "IBC")


@dataclass
class Site:
    """One ``Tracer.step`` call in the engine source whose status is hard-coded."""

    status: str
    file: str
    line: int
    key: str | None
    name: str | None
    citation: str | None  # None when the call builds it from an expression
    governs: bool = False
    stories: int = 0
    runtime_citation: str = ""

    @property
    def shown_citation(self) -> str:
        return self.runtime_citation or self.citation or "(built at run time)"

    @property
    def document(self) -> str:
        c = self.shown_citation
        return next((x for x in CODES if c.startswith(x)), "no code reference")


def _const(call: ast.Call, index: int, name: str):
    for kw in call.keywords:
        if kw.arg == name and isinstance(kw.value, ast.Constant):
            return kw.value.value
    if len(call.args) > index and isinstance(call.args[index], ast.Constant):
        return call.args[index].value
    return None


def _display_path(path: Path, root: Path) -> str:
    """Repo-relative where possible, so the line can be pasted into an editor."""
    for base in (ROOT, root):
        try:
            return str(path.relative_to(base))
        except ValueError:
            continue
    return str(path)


def scan_source(root: Path) -> tuple[list[Site], Counter]:
    """Every ``.step(...)`` call in src/, by the status written into it."""
    sites, totals = [], Counter()
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "step"):
                continue
            status = _const(node, _STATUS_ARG, "status")
            if status is None:
                continue  # status comes from a component row, so the row's own status governs
            totals[status] += 1
            if status in UNVERIFIED:
                sites.append(Site(status, _display_path(path, root), node.lineno,
                                  _const(node, _KEY_ARG, "key"), _const(node, _NAME_ARG, "name"),
                                  _const(node, _CITATION_ARG, "citation")))
    return sites, totals


def add_runtime_facts(sites: list[Site], library: str) -> str:
    """Fill in the citation and the governing flag by running the engine once.

    Steps whose citation is built from an expression only show it at run time, and only a run
    says which checks govern. Returns a note for the header, or "" when the run was skipped.
    """
    try:
        from design.engine import run_design
        from design.library import default_library
        from report.steps import local_id
        import woodworks_example as example
    except Exception as exc:  # noqa: BLE001  (the list is still useful without a run)
        return f"Engine not importable, so citations and priorities are missing: {exc}"

    lib = default_library() if library == "production" else example.library()

    # The seismic and wind paths reuse step keys, so a seismic-only run would hand a wind step the
    # seismic citation. Run both where possible, and key on the step's name as well as its key.
    runs, statuses = [], []
    for kwargs in ({}, {"load_type": "wind", "wind_drift_limit_ratio": 1 / 400}):
        try:
            result = run_design(example.inputs(**kwargs), lib)
        except Exception:  # noqa: BLE001  (a wind run is a bonus, not a requirement)
            continue
        runs.append(result)
        statuses.append(f"{result.load_type} {result.status.value}")

    seen: dict[tuple[str, str], dict] = {}
    for result in runs:
        governing = {s.governing_id for s in result.stories if s.governing_id}
        gov_steps = {st.id for s in result.stories for c in s.checks if c.id in governing for st in c.steps}
        every = [st for s in result.stories for c in s.checks for st in c.steps] + list(result.stack_steps)
        for st in every:
            r = seen.setdefault((st.name, local_id(st.id).rsplit(".", 1)[-1]),
                                {"cit": st.citation, "gov": False, "n": 0})
            r["gov"] |= st.id in gov_steps
            r["n"] += 1

    for site in sites:
        # Join only on an exact (name, key) pair: a near miss would cite the wrong code section.
        match = seen.get((site.name, site.key)) if site.name and site.key else None
        if match:
            site.runtime_citation = match["cit"]
            site.governs = match["gov"]
            site.stories = match["n"]
    ran = sum(1 for s in sites if s.runtime_citation)
    return (f"Priorities come from running the WoodWorks example against the {library} library "
            f"({', '.join(statuses)}); {ran} of {len(sites)} steps were matched to a run. "
            "The rest keep the citation written at the call site.")


@dataclass
class Rows:
    pending: list[tuple[str, str, str]] = field(default_factory=list)  # (row id, status, source)
    verified: int = 0


_META = ("source_doc", "table", "page", "status", "entered_by", "checked_by", "notes", "footnotes")


def _identify(row: dict) -> str:
    """Name a row from its leading descriptive columns, so each line points at a real entry."""
    parts: list[str] = []
    for key, value in row.items():
        if key in _META:
            break
        value = (value or "").strip()
        if not value or any(value in kept for kept in parts):
            continue  # skip blanks and values already implied by an earlier column
        parts.append(value)
        if len(parts) == 3:
            break
    return " · ".join(parts) or "(row)"


def scan_library(data_dir: Path) -> dict[str, Rows]:
    """Component rows that are not yet verified, by CSV."""
    out: dict[str, Rows] = {}
    for path in sorted(data_dir.glob("*.csv")):
        rows = Rows()
        with path.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                status = (row.get("status") or "").strip()
                if status == "verified":
                    rows.verified += 1
                    continue
                ident = _identify(row)
                source = " ".join(x for x in (row.get("source_doc"), row.get("table"), row.get("page")) if x)
                rows.pending.append((ident, status or "(blank)", source))
        out[path.name] = rows
    return out


def _bar(done: int, total: int, width: int = 24) -> str:
    filled = 0 if not total else round(width * done / total)
    return f"[{'#' * filled}{'.' * (width - filled)}] {done}/{total}"


def build(library: str) -> str:
    sites, totals = scan_source(ROOT / "src")
    note = add_runtime_facts(sites, library)
    lib_rows = scan_library(ROOT / "src" / "design" / "components" / "data")

    verified_steps = totals.get("verified", 0)
    tracked = verified_steps + len(sites)  # statics steps need no check, so they are not counted
    lib_done = sum(r.verified for r in lib_rows.values())
    lib_total = lib_done + sum(len(r.pending) for r in lib_rows.values())

    out = [
        "# Verification worklist",
        "",
        "Generated by `python tools/verification_worklist.py`. Re-run it after verifying something.",
        "",
        "Every calculation step and component row carries a source status "
        "(`statics`, `verified`, `memory`, `assumption`). This lists what is not yet `verified`, "
        "with the file and line to change. `memory` was recalled and never checked against the "
        "source; `assumption` is a team decision that needs recording, not a lookup.",
        "",
        "## Progress",
        "",
        f"- Calculation steps: `{_bar(verified_steps, tracked)}` verified "
        f"({totals.get('statics', 0)} more are plain statics and need no source check)",
        f"- Component rows: `{_bar(lib_done, lib_total)}` verified",
        "",
        note,
        "",
        "## Calculation steps",
        "",
        "Start at the top: steps marked **governs** set a reported demand/capacity ratio, so checking "
        "them changes what the design says. Within a document the work is one reading task, so a file "
        "is usually cheapest to close out in one sitting.",
        "",
    ]

    by_doc: dict[str, list[Site]] = defaultdict(list)
    for s in sites:
        by_doc[s.document].append(s)
    order = sorted(by_doc, key=lambda d: (d == "no code reference", -sum(x.governs for x in by_doc[d])))
    for doc in order:
        items = sorted(by_doc[doc], key=lambda s: (not s.governs, s.file, s.line))
        gov = sum(1 for s in items if s.governs)
        out += [f"### {doc} — {len(items)} steps, {gov} governing", "",
                "| | Status | Where | Step | Citation |", "| --- | --- | --- | --- | --- |"]
        for s in items:
            mark = "**governs**" if s.governs else ""
            where = f"`{s.file}:{s.line}`"
            name = (s.name or s.key or "").replace("|", "\\|")
            out.append(f"| {mark} | {s.status} | {where} | {name} | {s.shown_citation.replace('|', '')} |")
        out.append("")

    out += ["## Component library rows", "",
            "Set `status=verified` and fill `checked_by` in the CSV once the row is checked against its "
            "printed source, as the SDPWS Table 4.3A rows already do.", ""]
    for name, rows in sorted(lib_rows.items(), key=lambda kv: -len(kv[1].pending)):
        if not rows.pending:
            out.append(f"- **{name}** — all {rows.verified} rows verified")
            continue
        out += ["", f"### {name} — {len(rows.pending)} to check, {rows.verified} verified", "",
                "| Row | Status | Source |", "| --- | --- | --- |"]
        for ident, status, source in rows.pending:
            out.append(f"| `{ident}` | {status} | {source or '(not recorded)'} |")
    out.append("")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--out", type=Path, help="write Markdown here instead of stdout")
    ap.add_argument("--library", choices=("example", "production"), default="example",
                    help="which component library to run for priorities (default: example, so every check runs)")
    args = ap.parse_args()
    text = build(args.library)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
