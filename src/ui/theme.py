"""Green card theme and small HTML builders for the Streamlit page (presentation only, no design logic)."""

from __future__ import annotations

from html import escape

from design.result import OverallStatus
from design.trace import CheckResult, CheckStatus
from ui.loadcases import LABEL, SHORT, CaseSet

GREEN_DARK, GREEN, GREEN_SOFT = "#166534", "#15803D", "#DCFCE7"

CSS = """
<style>
:root{--g9:#14532d;--g8:#166534;--g7:#15803d;--g6:#16a34a;--g1:#dcfce7;--g0:#f0fdf4;--ink:#1e293b;--mute:#64748b;
--line:#d4e3d9;--amber:#b45309;--amber-bg:#fef3c7;--red:#b91c1c;--red-bg:#fee2e2;--grey-bg:#eef2f0;
--mono:"JetBrains Mono",ui-monospace,Consolas,"Cascadia Mono",monospace;
--sans:Inter,"Segoe UI",system-ui,-apple-system,Roboto,sans-serif;}
html,body,[class*="stApp"]{font-family:var(--sans);color:var(--ink);}
.stApp{background:#f5faf6;}
.block-container{max-width:1180px;padding-top:1.6rem;}
header[data-testid="stHeader"]{background:transparent;}
/* page header */
.ws-head{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;margin-bottom:14px;}
.ws-title{font-size:1.55rem;font-weight:700;color:var(--g8);letter-spacing:-.01em;margin:0;}
.ws-sub{color:var(--mute);font-size:.86rem;margin-top:2px;}
.ws-pills{display:flex;gap:6px;flex-wrap:wrap;}
.pill{display:inline-block;font-family:var(--mono);font-size:.68rem;padding:3px 9px;border:1px solid var(--line);
 border-radius:7px;color:var(--g7);background:#fff;white-space:nowrap;}
.pill.warn{color:var(--amber);background:var(--amber-bg);border-color:#fcd9a0;}
/* KPI cards */
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:6px 0 14px;}
@media(max-width:900px){.kpis{grid-template-columns:repeat(2,1fr);}}
.kpi{background:#fff;border:1px solid var(--line);border-radius:16px;padding:16px 18px;min-height:132px;
 box-shadow:0 1px 2px rgba(20,83,45,.04);}
.kpi .lab{font-size:.84rem;font-weight:600;color:#334155;display:flex;justify-content:space-between;gap:8px;}
.kpi .ico{color:var(--g6);font-size:.95rem;}
.kpi .val{font-family:var(--mono);font-size:2.05rem;font-weight:700;margin-top:14px;color:var(--ink);line-height:1.1;}
.kpi .val small{font-size:.9rem;font-weight:500;color:#475569;margin-left:6px;}
.kpi .sub{font-size:.76rem;color:var(--mute);margin-top:6px;}
.kpi .val.g{color:#059669}.kpi .val.a{color:var(--amber)}.kpi .val.r{color:var(--red)}.kpi .val.p{color:var(--g7)}
/* section cards (st.container(border=True, key="card_*")) */
[class*="st-key-card_"]{background:#fff;border:1px solid var(--line)!important;border-radius:16px!important;
 padding:6px 10px 12px!important;box-shadow:0 1px 2px rgba(20,83,45,.04);margin-bottom:6px;}
.sec-h{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:6px 0 8px;}
.sec-h .t{font-size:.8rem;font-weight:700;letter-spacing:.06em;color:#334155;text-transform:uppercase;display:flex;align-items:center;gap:8px;}
.sec-h .t svg{stroke:var(--g6);}
.note{font-size:.84rem;color:#475569;margin:2px 0 8px;}
/* segmented radios */
.st-key-n_stories div[role="radiogroup"],.st-key-g_load_type div[role="radiogroup"],.st-key-lib_source div[role="radiogroup"]{gap:10px;flex-wrap:wrap;}
.st-key-n_stories div[role="radiogroup"]>label,.st-key-g_load_type div[role="radiogroup"]>label,.st-key-lib_source div[role="radiogroup"]>label{
 flex:1 1 0;min-width:110px;justify-content:center;border:1.5px solid var(--line);border-radius:12px;padding:10px 12px;background:#fff;
 font-weight:600;cursor:pointer;margin:0;}
.st-key-n_stories div[role="radiogroup"]>label>div:first-child,.st-key-g_load_type div[role="radiogroup"]>label>div:first-child,
.st-key-lib_source div[role="radiogroup"]>label>div:first-child{display:none;}
.st-key-n_stories div[role="radiogroup"]>label:has(input:checked),.st-key-g_load_type div[role="radiogroup"]>label:has(input:checked),
.st-key-lib_source div[role="radiogroup"]>label:has(input:checked){border-color:var(--g7);background:var(--g0);color:var(--g8);box-shadow:inset 0 0 0 1px var(--g7);}
/* tiles */
.tiles{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-top:10px;}
@media(max-width:900px){.tiles{grid-template-columns:repeat(2,1fr);}}
.tile{border:1px solid var(--line);border-radius:12px;padding:10px 12px;background:#fff;}
.tile .l{font-size:.72rem;color:var(--mute);}
.tile .v{font-family:var(--mono);font-size:1.05rem;font-weight:600;margin-top:4px;color:var(--g8);}
.tile .v.o{color:#c2410c}.tile .v.r{color:#be123c}.tile .v.k{color:var(--ink)}
.tile .u{font-size:.7rem;color:var(--mute);margin-top:2px;}
/* DCR pills and bars */
.dcr{display:inline-block;font-family:var(--mono);font-size:.78rem;padding:2px 9px;border-radius:7px;border:1px solid;}
.dcr.g{color:#047857;background:#ecfdf5;border-color:#6ee7b7;}.dcr.a{color:var(--amber);background:var(--amber-bg);border-color:#fcd9a0;}
.dcr.r{color:var(--red);background:var(--red-bg);border-color:#fca5a5;}.dcr.n{color:#64748b;background:var(--grey-bg);border-color:#d5dcd8;}
.bars .row{display:flex;align-items:center;gap:10px;margin:7px 0;font-size:.82rem;}
.bars .row .s{width:58px;font-weight:600;color:#334155;}
.bars .track{flex:1;height:12px;background:#edf3ef;border-radius:7px;position:relative;overflow:hidden;}
.bars .fill{height:100%;border-radius:7px;}
.bars .fill.g{background:#4ade80}.bars .fill.a{background:#fbbf24}.bars .fill.r{background:#f87171}.bars .fill.n{background:#cbd5d1}
.bars .num{width:86px;text-align:right;font-family:var(--mono);font-size:.78rem;color:#334155;}
/* schedule */
.sched-wrap{overflow-x:auto;}
table.sched{width:100%;border-collapse:collapse;font-size:.82rem;}
table.sched th{font-weight:600;color:#475569;text-align:right;padding:8px 8px;border-bottom:1.5px solid #c9dccf;white-space:nowrap;}
table.sched th:first-child,table.sched td:first-child{text-align:left;}
table.sched td{padding:9px 8px;border-bottom:1px solid #e6efe9;text-align:right;font-family:var(--mono);white-space:nowrap;}
table.sched td.txt{font-family:var(--sans);}
table.sched tr.sel td{background:var(--g0);}
.eqline{font-family:var(--mono);font-size:.72rem;color:#475569;margin-top:10px;}
.stButton>button:not([kind="primary"]),.stDownloadButton>button:not([kind="primary"]){border-radius:10px;border:1.5px solid var(--g7);color:var(--g8);font-weight:600;background:#fff;}
.stButton>button:not([kind="primary"]):hover,.stDownloadButton>button:not([kind="primary"]):hover{background:var(--g0);border-color:var(--g8);color:var(--g8);}
button[role="tab"][aria-selected="true"]{color:var(--g8)!important;}

/* chips and check rows */
.chip{display:inline-block;font-family:var(--mono);font-size:.66rem;font-weight:700;padding:1px 6px;border-radius:6px;margin-left:5px;vertical-align:middle;}
.chip.S{background:#fff7ed;color:#c2410c;border:1px solid #fed7aa;}.chip.W{background:#ecfeff;color:#0e7490;border:1px solid #a5f3fc;}
.chip.src{background:#f1f5f9;color:#475569;border:1px solid #e2e8f0;font-weight:500;}.chip.src.verified,.chip.src.statics{background:#ecfdf5;color:#047857;border-color:#a7f3d0;}
.chip.src.memory{background:var(--amber-bg);color:var(--amber);border-color:#fcd9a0;}
table.checks{width:100%;border-collapse:collapse;font-size:.8rem;}
table.checks td{padding:8px 4px;border-bottom:1px solid #e6efe9;vertical-align:top;}
table.checks td.n{font-weight:600;color:#334155;width:34%;}
table.checks td.v{font-family:var(--mono);text-align:right;white-space:nowrap;color:#334155;}
table.checks .sub{font-size:.68rem;color:var(--mute);font-weight:400;font-family:var(--mono);}
.govbanner{display:flex;align-items:center;justify-content:space-between;gap:8px;background:var(--g0);border:1px solid #bbf7d0;border-radius:10px;padding:8px 12px;margin:2px 0 8px;font-size:.84rem;}
.govbanner b{color:var(--g8);}
[class*="st-key-card_left"],[class*="st-key-card_right"]{background:#fff;}
</style>
"""

_ICONS = {
    "layers": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3 9 5-9 5-9-5z"/><path d="m3 13 9 5 9-5"/></svg>',
    "pin": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 21s7-6.2 7-11a7 7 0 0 0-14 0c0 4.8 7 11 7 11z"/><circle cx="12" cy="10" r="2.5"/></svg>',
    "ruler": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m3 17 14-14 4 4L7 21z"/><path d="m8 8 2 2M11 5l2 2M5 11l2 2"/></svg>',
    "arrows": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12h14M13 6l6 6-6 6"/></svg>',
    "list": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6h11M9 12h11M9 18h11M4 6l1 1 2-2M4 12l1 1 2-2M4 18l1 1 2-2"/></svg>',
    "grid": '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>',
}


def tone(dcr: float | None, incomplete: bool = False) -> str:
    if dcr is None or incomplete:
        return "n"
    return "r" if dcr > 1.0 else "a" if dcr > 0.90 else "g"


def section_header(title: str, icon: str = "", pill: str = "") -> str:
    p = f'<span class="pill">{escape(pill)}</span>' if pill else ""
    return f'<div class="sec-h"><div class="t">{_ICONS.get(icon, "")}{escape(title)}</div>{p}</div>'


def page_header(editions: tuple[str, ...], disclaimer: str) -> str:
    pills = "".join(f'<span class="pill">{escape(e)}</span>' for e in editions)
    return (f'<div class="ws-head"><div><div class="ws-title">Shear Wall Stack Designer</div>'
            f'<div class="ws-sub">Light-frame wood shear wall stack · calc trace on every number</div></div>'
            f'<div class="ws-pills">{pills}<span class="pill warn">{escape(disclaimer)}</span></div></div>')


def _kpi(label: str, icon: str, value: str, unit: str, sub: str, cls: str = "") -> str:
    u = f"<small>{escape(unit)}</small>" if unit else ""
    return (f'<div class="kpi"><div class="lab"><span>{escape(label)}</span><span class="ico">{icon}</span></div>'
            f'<div class="val {cls}">{escape(value)}{u}</div><div class="sub">{escape(sub)}</div></div>')


def kpi_row(n: int, b_ft: float, height_ft: float, cs: CaseSet | None) -> str:
    cards = [_kpi("Wall Stack", "▦", f"{n}", "stories", f"b = {b_ft:g} ft · H = {height_ft:g} ft")]
    ok = cs is not None and cs.valid
    if ok:
        vs = {c: cs.num(c, "S1.statics.V") for c in cs.cases}
        main = next((c for c in cs.cases if vs[c] is not None), None)
        if main:
            sub = " · ".join(f"{LABEL[c]} {vs[c] / 1000:,.2f} kips" for c in cs.cases if vs[c] is not None)
            cards.append(_kpi("Base Shear V (strength level)", "∿", f"{max(v for v in vs.values() if v is not None) / 1000:,.2f}",
                              "kips", sub, "p"))
        else:
            cards.append(_kpi("Base Shear V", "∿", "—", "", "", "p"))
        dcr, case, story, chk = cs.overall()
        if case:
            cards.append(_kpi("Governing Load Case", "◦", LABEL[case], "",
                              f"Story {story} · {(chk or '').split('.', 1)[-1]} ({chk})"))
            sub = {OverallStatus.PASS: "All checks within capacity", OverallStatus.FAIL: "One or more checks exceed capacity",
                   OverallStatus.INCOMPLETE: "Some checks need engineer input"}[cs.status]
            cards.append(_kpi("Max Demand/Capacity (DCR)", "⛨", f"{dcr:.2f}", "", sub, tone(dcr)))
            return f'<div class="kpis">{"".join(cards)}</div>'
    cards += [_kpi("Governing Load Case", "◦", "—", "", "enter seismic and/or wind forces"),
              _kpi("Max Demand/Capacity (DCR)", "⛨", "—", "", "no rated checks yet", "n")]
    if len(cards) == 3:
        cards.insert(1, _kpi("Base Shear V", "∿", "—", "", "", "p"))
    return f'<div class="kpis">{"".join(cards)}</div>'


def case_chip(case: str | None) -> str:
    return "" if case is None else f'<span class="chip {SHORT[case]}" title="{LABEL[case]}">{SHORT[case]}</span>'


def dcr_pill(status: CheckStatus | None, dcr: float | None, case: str | None = None) -> str:
    chip = case_chip(case)
    if status is None:
        return '<span class="dcr n">—</span>'
    if status is CheckStatus.NEEDS_INPUT:
        return f'<span class="dcr n">needs input</span>{chip}'
    if status in (CheckStatus.INFO, CheckStatus.NOT_APPLICABLE) or dcr is None:
        return '<span class="dcr n">—</span>'
    return f'<span class="dcr {tone(dcr)}">{dcr:.2f}</span>{chip}'


TIE_CATS = ("holddown", "rod", "plate_bearing", "plate_bending")


def _f(x, nd=0) -> str:
    return "—" if x is None else f"{x:,.{nd}f}"


def tie_label(story_input) -> str:
    t = story_input.tiedown
    return getattr(t, "system_id", None) or getattr(t, "model", None) or (
        f"T_allow {t.T_allow_lb:,.0f} lb" if getattr(t, "T_allow_lb", None) else "—")


def schedule_html(cs: CaseSet, n: int, selected: int | None = None) -> str:
    inp = cs.primary
    head = ["Story", "Governs", "Nailing", "Sides", "v demand (plf)", "v allow (plf)", "Shear", "Uplift T (lb)", "Tie-down",
            "Tie-down DCR", "Chord comp.", "Drift", "Status"]
    rows = []
    for i in range(n, 0, -1):  # top story first, like the elevation
        s = inp.stories[i - 1]
        _, gcase = cs.story_dcr(i)
        scase, shear = cs.check(i, ("shear",))
        tcase, tie = cs.check(i, TIE_CATS)
        dcase, drift = cs.check(i, ("drift",))
        ccase, comp = cs.check(i, ("compression",))
        st = cs.story_status(i)
        badge = {OverallStatus.PASS: '<span class="dcr g">pass</span>', OverallStatus.FAIL: '<span class="dcr r">FAIL</span>',
                 OverallStatus.INCOMPLETE: '<span class="dcr n">incomplete</span>'}.get(st, "")
        Tcase = tcase or gcase or "seismic"
        cls = ' class="sel"' if selected == i else ""
        v = cs.num(scase, f"S{i}.shear.v") if scase else None
        va = cs.num(scase, f"S{i}.shear.v_allow") if scase else None
        T = cs.num(Tcase, f"S{i}.chord.asd.T") if Tcase in cs.results else None
        rows.append(
            f"<tr{cls}><td class='txt'><b>Story {i}</b></td><td class='txt'>{LABEL.get(gcase, '—')}</td>"
            f"<td class='txt'>{escape(s.assembly_id or '—')}</td><td>{s.sides}</td><td>{_f(v)}</td><td>{_f(va)}</td>"
            f"<td>{dcr_pill(shear.status if shear else None, shear.dcr if shear else None, scase)}</td><td>{_f(T)}</td>"
            f"<td class='txt'>{escape(tie_label(s))}</td>"
            f"<td>{dcr_pill(tie.status if tie else None, tie.dcr if tie else None, tcase)}</td>"
            f"<td>{dcr_pill(comp.status if comp else None, comp.dcr if comp else None, ccase)}</td>"
            f"<td>{dcr_pill(drift.status if drift else None, drift.dcr if drift else None, dcase)}</td><td>{badge}</td></tr>")
    th = "".join(f"<th>{escape(h)}</th>" for h in head)
    return f'<div class="sched-wrap"><table class="sched"><thead><tr>{th}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def bars_html(cs: CaseSet, n: int) -> str:
    out = ['<div class="bars">']
    for i in range(n, 0, -1):
        dcr, case = cs.story_dcr(i)
        t = tone(dcr, dcr is None)
        w = 0 if dcr is None else min(dcr, 1.2) / 1.2 * 100
        label = "needs input" if dcr is None else f"{dcr:.2f}"
        gov = (cs.story_governing_check(i) or "").split(".", 1)[-1]
        out.append(f'<div class="row"><span class="s">Story {i}</span><div class="track"><div class="fill {t}" '
                   f'style="width:{w:.0f}%"></div></div><span class="num">{label} {escape(gov)}{case_chip(case)}</span></div>')
    out.append("</div>")
    return "".join(out)


def tiles_html(items: list[tuple[str, str, str, str]]) -> str:
    """items: (label, value, unit, colour-class)."""
    cells = "".join(f'<div class="tile"><div class="l">{escape(l)}</div><div class="v {c}">{escape(v)}</div>'
                    f'<div class="u">{escape(u)}</div></div>' for l, v, u, c in items)
    return f'<div class="tiles">{cells}</div>'


CHECK_ROWS = [("shear", ("shear",), "Sheathing shear"), ("aspect", ("aspect",), "Aspect ratio h/b"),
              ("comp", ("compression",), "Chord compression"), ("tie", ("holddown", "rod"), "Tie-down tension"),
              ("pbrg", ("plate_bearing",), "Bearing plate, bearing"), ("pbend", ("plate_bending",), "Bearing plate, bending"),
              ("drift", ("drift",), "Story drift")]


def _cv(x, unit: str) -> str:
    if x is None:
        return "—"
    return f"{x:,.2f} {unit}" if abs(x) < 10 else f"{x:,.0f} {unit}"


def checks_panel_html(cs: CaseSet, i: int) -> str:
    """Capacities and checks for story i: demand, capacity, DCR and the load case that produced it."""
    rows = []
    for _, cats, label in CHECK_ROWS:
        case, ck = cs.check(i, cats)
        if ck is None:
            continue
        both = cs.both(i, cats)
        sub = " · ".join(f"{SHORT[c]} {d:.2f}" for c, d in both.items() if d is not None)
        src = ck.worst_source
        src_chip = f'<span class="chip src {src}">{src}</span>' if src else ""
        if ck.status in (CheckStatus.PASS, CheckStatus.FAIL) and ck.dcr is not None:
            w = min(ck.dcr, 1.2) / 1.2 * 100
            bar = (f'<div class="bars"><div class="track" style="height:8px"><div class="fill {tone(ck.dcr)}" '
                   f'style="width:{w:.0f}%"></div></div></div>')
            right = (f"<div>{_cv(ck.demand, ck.demand_unit)}</div><div class='sub'>of {_cv(ck.capacity, ck.capacity_unit)}</div>")
            pill = dcr_pill(ck.status, ck.dcr, case)
        else:
            bar, right = "", f"<div class='sub'>{escape(ck.message[:70])}</div>" if ck.message else ""
            pill = dcr_pill(ck.status, ck.dcr, case)
        rows.append(f"<tr><td class='n'>{escape(label)}<div class='sub'>{escape(sub)} {src_chip}</div></td>"
                    f"<td>{bar}{pill}</td><td class='v'>{right}</td></tr>")
    return f'<table class="checks">{"".join(rows)}</table>'
