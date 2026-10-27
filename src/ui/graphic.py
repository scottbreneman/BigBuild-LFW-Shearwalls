"""Stack graphic as an SVG string, coloured by story DCR (no plotting dependency)."""

from __future__ import annotations

from html import escape

from design.inputs import DesignInputs
from design.result import DesignResult, OverallStatus

GREEN, AMBER, RED, GREY = "#DCFCE7", "#FEF3C7", "#FEE2E2", "#EEF2F0"
STROKE = {GREEN: "#16A34A", AMBER: "#D97706", RED: "#DC2626", GREY: "#94A3B8"}


def dcr_colour(dcr: float | None, incomplete: bool = False) -> str:
    if dcr is None or incomplete:
        return GREY
    if dcr > 1.0:
        return RED
    if dcr > 0.90:
        return AMBER
    return GREEN


def stack_svg(inp: DesignInputs, result: DesignResult | None = None, selected: int | None = None,
              story_dcrs: dict[int, float | None] | None = None, force_lines: dict[int, list[str]] | None = None,
              notes: dict[int, str] | None = None) -> str:
    px_per_ft, wall_w, left, top = 11.5, 190, 130, 26
    n = len(inp.stories)
    total_h = sum(s.h_ft for s in inp.stories) * px_per_ft
    width, height = 470, int(total_h + top + 40)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" '
           f'font-family="DejaVu Sans, Arial, sans-serif">']
    y = top
    for i in range(n, 0, -1):  # story n at the top of the drawing
        s = inp.stories[i - 1]
        h = s.h_ft * px_per_ft
        sr = result.stories[i - 1] if result and result.stories else None
        dcr_i = story_dcrs.get(i) if story_dcrs is not None else (sr.max_dcr if sr else None)
        has_result = story_dcrs is not None or sr is not None
        fill = dcr_colour(dcr_i, has_result and dcr_i is None)
        sw = 3.2 if selected == i else 1.5
        out.append(f'<rect x="{left}" y="{y:.1f}" width="{wall_w}" height="{h:.1f}" fill="{fill}" '
                   f'stroke="{STROKE[fill]}" stroke-width="{sw}"/>')
        out.append(f'<text x="{left - 8}" y="{y + h / 2 + 4:.1f}" font-size="12" text-anchor="end" fill="#166534" '
                   f'font-weight="bold">Story {i}</text>')
        out.append(f'<text x="{left + wall_w / 2}" y="{y + h / 2 - 2:.1f}" font-size="10.5" text-anchor="middle" '
                   f'fill="#222">{escape(s.assembly_id or "no assembly")}</text>')
        out.append(f'<text x="{left + wall_w / 2}" y="{y + h / 2 + 11:.1f}" font-size="10" text-anchor="middle" '
                   f'fill="#555">{s.sides} side{"s" if s.sides != 1 else ""} · h = {s.h_ft:g} ft</text>')
        # applied force arrow at the top of the story
        ay = y
        out.append(f'<line x1="{left - 40}" y1="{ay}" x2="{left}" y2="{ay}" stroke="#166534" stroke-width="1.6"/>'
                   f'<polygon points="{left},{ay} {left - 7},{ay - 3.5} {left - 7},{ay + 3.5}" fill="#166534"/>')
        for k, line in enumerate((force_lines or {}).get(i) or [f"F = {s.F_lb:,.0f} lb"]):
            out.append(f'<text x="{left - 44}" y="{ay - 4 - 11 * k:.0f}" font-size="9.5" text-anchor="end" fill="#166534">'
                       f'{escape(line)}</text>')
        # DCR label on the right
        if has_result and dcr_i is not None:
            out.append(f'<text x="{left + wall_w + 10}" y="{y + h / 2 + 4:.1f}" font-size="12" fill="#222" '
                       f'font-weight="bold">DCR {dcr_i:.2f}</text>')
            gov = (notes or {}).get(i) or (sr.governing_id or "").split(".", 1)[-1] if (notes or sr) else ""
            out.append(f'<text x="{left + wall_w + 10}" y="{y + h / 2 + 18:.1f}" font-size="9.5" fill="#555">{escape(gov)}</text>')
        elif has_result:
            out.append(f'<text x="{left + wall_w + 10}" y="{y + h / 2 + 4:.1f}" font-size="10.5" fill="#777">needs input</text>')
        y += h
    out.append(f'<line x1="{left - 8}" y1="{y}" x2="{left + wall_w + 8}" y2="{y}" stroke="#444" stroke-width="2.5"/>')
    out.append(f'<text x="{left + wall_w / 2}" y="{y + 16}" font-size="10.5" text-anchor="middle" fill="#555">'
               f'b = {inp.b_ft:g} ft</text>')
    out.append("</svg>")
    return "".join(out)
