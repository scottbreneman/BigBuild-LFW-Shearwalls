"""Result tables for the UI as pandas frames (presentation only; every number comes from the engine).

These feed native Streamlit tables and charts (``st.dataframe`` with progress-bar columns, an Altair
heatmap) in place of hand-built HTML, so they stay readable, sortable and accessible.
"""

from __future__ import annotations

import pandas as pd

from design.trace import CheckStatus
from ui.loadcases import LABEL, SHORT, CaseSet
from ui.theme import CHECK_ROWS, TIE_CATS, tie_label

DCR_MAX = 1.2  # progress bars run from 0 to 1.2 so overstress is still visible


def _rated(ck) -> bool:
    return ck is not None and ck.status in (CheckStatus.PASS, CheckStatus.FAIL) and ck.dcr is not None


def _value(x, unit: str) -> str:
    if x is None:
        return "—"
    return f"{x:,.2f} {unit}".strip() if abs(x) < 10 else f"{x:,.0f} {unit}".strip()


def status_text(ck) -> str:
    if ck is None:
        return "—"
    return {CheckStatus.PASS: "pass", CheckStatus.FAIL: "FAIL", CheckStatus.NEEDS_INPUT: "needs input",
            CheckStatus.INFO: "info", CheckStatus.NOT_APPLICABLE: "n/a"}[ck.status]


def checks_frame(cs: CaseSet, i: int) -> pd.DataFrame:
    """One row per check for story i: the governing load case's DCR, demand and capacity."""
    rows = []
    for key, cats, label in CHECK_ROWS:
        case, ck = cs.check(i, cats)
        if ck is None:
            continue
        others = " · ".join(f"{SHORT[c]} {d:.2f}" for c, d in cs.both(i, cats).items() if d is not None)
        rows.append({
            "key": key, "case_id": case, "check_id": ck.id,
            "Check": label,
            "DCR": ck.dcr if _rated(ck) else None,
            "Result": status_text(ck),
            "Case": SHORT.get(case, "—"),
            "Demand": _value(ck.demand, ck.demand_unit) if _rated(ck) else "—",
            "Capacity": _value(ck.capacity, ck.capacity_unit) if _rated(ck) else "—",
            "By case": others,
            "Source": ck.worst_source or "—",
            "Note": ck.message if not _rated(ck) else "",
        })
    return pd.DataFrame(rows)


SHORT_CHECK = {"Sheathing shear": "Shear", "Aspect ratio h/b": "Aspect", "Chord compression": "Compression",
               "Tie-down tension": "Tie-down", "Bearing plate, bearing": "Plate bearing",
               "Bearing plate, bending": "Plate bending", "Story drift": "Drift"}
HEAT_COLS = [SHORT_CHECK.get(label, label) for _, _, label in CHECK_ROWS]


def heatmap_frame(cs: CaseSet, n: int) -> pd.DataFrame:
    """Long table (story x check) with the governing DCR, for a heatmap."""
    rows = []
    for i in range(1, n + 1):
        for _, cats, label in CHECK_ROWS:
            case, ck = cs.check(i, cats)
            if ck is None:
                continue
            dcr = ck.dcr if _rated(ck) else None
            band = ("needs input" if ck.status is CheckStatus.NEEDS_INPUT else "n/a") if dcr is None else \
                ("over 1.00" if dcr > 1.0 else "0.90–1.00" if dcr > 0.9 else "≤ 0.90")
            rows.append({"Story": f"Story {i}", "story": i, "Check": SHORT_CHECK.get(label, label), "Name": label,
                         "DCR": dcr, "Band": band,
                         "Label": "—" if dcr is None else f"{dcr:.2f}", "Case": LABEL.get(case, "—")})
    return pd.DataFrame(rows)


def schedule_frame(cs: CaseSet, n: int) -> pd.DataFrame:
    """The wall schedule, top story first (like the elevation)."""
    inp = cs.primary
    rows = []
    for i in range(n, 0, -1):
        s = inp.stories[i - 1]
        _, gcase = cs.story_dcr(i)
        scase, shear = cs.check(i, ("shear",))
        tcase, tie = cs.check(i, TIE_CATS)
        ccase, comp = cs.check(i, ("compression",))
        dcase, drift = cs.check(i, ("drift",))
        tc = tcase or gcase or cs.cases[0]
        rows.append({
            "Story": i, "Governs": LABEL.get(gcase, "—"), "Status": cs.story_status(i).value,
            "Nailing": s.assembly_id or "—", "Sides": s.sides,
            "v (plf)": cs.num(scase, f"S{i}.shear.v") if scase else None,
            "v allow (plf)": cs.num(scase, f"S{i}.shear.v_allow") if scase else None,
            "Shear": shear.dcr if _rated(shear) else None,
            "Posts": f"({s.chord.n_posts}) {s.chord.post_nominal}",
            "Compression": comp.dcr if _rated(comp) else None,
            "Tie-down": tie_label(s), "Uplift T (lb)": cs.num(tc, f"S{i}.chord.asd.T") if tc in cs.results else None,
            "Tie-down DCR": tie.dcr if _rated(tie) else None,
            "Drift": drift.dcr if _rated(drift) else None,
        })
    return pd.DataFrame(rows)


SPECIES_SHORT = {"Douglas Fir-Larch": "DF-L", "Spruce-Pine-Fir": "SPF", "Southern Pine": "SP"}


def short_selection(text: str) -> str:
    """Compact a selection description for narrow table cells."""
    for long, short in SPECIES_SHORT.items():
        text = text.replace(long, short)
    return text.replace(", layout rule", "").replace(" side(s)", "")


def autosize_frame(result) -> pd.DataFrame:
    """One row per story: the proposed selections (only where they change) and the worst-case DCRs after."""
    rows = []
    for sp in result.stories:
        changes = {c.field: c for c in sp.changes}
        row = {"Story": sp.story, "Result": sp.status}
        for field in ("Nailing", "Posts", "Tie-down"):
            c = changes.get(field)
            row[field] = short_selection(c.proposed) if c else "unchanged"
        tension = "rod" if "rod" in sp.dcr_after else "holddown"
        for cat, label in (("shear", "Shear"), ("compression", "Compression"), (tension, "Tension"), ("drift", "Drift")):
            row[label] = sp.dcr_after.get(cat)
            row[f"{label} before"] = sp.dcr_before.get(cat)
        row["Notes"] = "; ".join(sp.notes)
        rows.append(row)
    return pd.DataFrame(rows)


def trace_frame(steps) -> pd.DataFrame:
    return pd.DataFrame([{"Step": s.name, "Equation": s.equation_latex, "Substitution": s.substitution,
                          "Value": s.value if isinstance(s.value, str) else f"{s.value:,.6g}", "Unit": s.unit,
                          "Citation": s.citation, "Status": s.status, "Note": s.note, "Id": s.id} for s in steps])
