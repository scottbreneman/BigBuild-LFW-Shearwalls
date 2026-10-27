"""Free-body loading diagram for one story's wall (SVG, presentation only).

Every number shown is passed in from the engine's calc trace; nothing is computed here.
"""

from __future__ import annotations

from html import escape

MONO = "JetBrains Mono, Consolas, ui-monospace, monospace"


def _f(x, nd=0, suffix="") -> str:
    return "—" if x is None else f"{x:,.{nd}f}{suffix}"


def _arrow(x1, y1, x2, y2, colour, w=1.8) -> str:
    import math
    a = math.atan2(y2 - y1, x2 - x1)
    L = 7
    p1 = (x2 - L * math.cos(a - 0.45), y2 - L * math.sin(a - 0.45))
    p2 = (x2 - L * math.cos(a + 0.45), y2 - L * math.sin(a + 0.45))
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{colour}" stroke-width="{w}"/>'
            f'<polygon points="{x2:.1f},{y2:.1f} {p1[0]:.1f},{p1[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}" fill="{colour}"/>')


def fbd_svg(*, story: int, b_ft: float, h_ft: float, V, v, w_dl, T, C, tie_label: str, tone_fill: str = "#F0FDF4") -> str:
    W, wall_w = 860, 600
    wall_h = max(110, min(190, wall_w * h_ft / b_ft)) if b_ft > 0 else 150
    x0, x1 = 130, 130 + wall_w
    y_top = 96
    y_bot = y_top + wall_h
    H = int(y_bot + 120)
    g8, g7, ink, mute = "#166534", "#15803D", "#1E293B", "#64748B"
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%" font-family="{MONO}">']
    # wall body and end posts (chords)
    s.append(f'<rect x="{x0}" y="{y_top}" width="{wall_w}" height="{wall_h:.1f}" fill="{tone_fill}" stroke="{g7}" stroke-width="2"/>')
    for px in (x0, x1 - 16):
        s.append(f'<rect x="{px}" y="{y_top}" width="16" height="{wall_h:.1f}" fill="#BBF7D0" stroke="{g7}" stroke-width="1.2"/>')
    s.append(f'<text x="{(x0 + x1) / 2}" y="{y_top + wall_h / 2 + 4:.1f}" font-size="12" text-anchor="middle" fill="{g8}" '
             f'font-weight="600">STORY {story} WALL</text>')
    # lateral load: entering arrow and distributed shear flow
    s.append(_arrow(24, y_top - 12, x0, y_top - 12, "#4F46E5" if False else g7, 2.4))
    s.append(f'<text x="24" y="{y_top - 22}" font-size="12" font-weight="700" fill="{g8}">V = {_f(V)} lb</text>')
    for k in range(6):
        ax = x0 + 40 + k * (wall_w - 80) / 5
        s.append(_arrow(ax - 14, y_top - 12, ax + 14, y_top - 12, g7, 1.6))
    s.append(f'<text x="{(x0 + x1) / 2}" y="{y_top - 24}" font-size="11" text-anchor="middle" fill="{mute}">'
             f'unit shear v = {_f(v)} plf (ASD)</text>')
    # resisting dead load
    for k in range(7):
        ax = x0 + 52 + k * (wall_w - 104) / 6
        s.append(_arrow(ax, y_top + 14, ax, y_top + 40, "#475569", 1.5))
    s.append(f'<text x="{(x0 + x1) / 2}" y="{y_top + 58}" font-size="11" text-anchor="middle" fill="#475569">'
             f'w_DL = {_f(w_dl)} plf (cumulative dead load)</text>')
    # ground
    s.append(f'<line x1="{x0 - 30}" y1="{y_bot}" x2="{x1 + 30}" y2="{y_bot}" stroke="#334155" stroke-width="2.5"/>')
    for k in range(int((wall_w + 60) / 12)):
        gx = x0 - 30 + k * 12
        s.append(f'<line x1="{gx}" y1="{y_bot + 8}" x2="{gx + 8}" y2="{y_bot}" stroke="#94A3B8" stroke-width="1"/>')
    # tension (tie-down) at left, compression at right
    s.append(f'<rect x="{x0}" y="{y_bot - 34}" width="16" height="34" fill="#DC2626" stroke="#991B1B"/>')
    s.append(_arrow(x0 + 8, y_bot + 40, x0 + 8, y_bot + 2, "#DC2626", 2.4))
    s.append(f'<text x="{x0 - 8}" y="{y_bot + 58}" font-size="12" font-weight="700" fill="#B91C1C">T = {_f(T)} lb</text>')
    s.append(f'<text x="{x0 - 8}" y="{y_bot + 73}" font-size="10.5" fill="{mute}">{escape(tie_label)}</text>')
    s.append(_arrow(x1 - 8, y_bot + 40, x1 - 8, y_bot + 2, g7, 2.4))
    s.append(f'<text x="{x1 + 8}" y="{y_bot + 58}" font-size="12" font-weight="700" fill="{g8}" text-anchor="end">C = {_f(C)} lb</text>')
    s.append(f'<text x="{x1 + 8}" y="{y_bot + 73}" font-size="10.5" fill="{mute}" text-anchor="end">chord compression</text>')
    # dimensions
    s.append(f'<line x1="{x0}" y1="{y_bot + 92}" x2="{x1}" y2="{y_bot + 92}" stroke="{mute}" stroke-width="1"/>'
             f'<line x1="{x0}" y1="{y_bot + 87}" x2="{x0}" y2="{y_bot + 97}" stroke="{mute}"/>'
             f'<line x1="{x1}" y1="{y_bot + 87}" x2="{x1}" y2="{y_bot + 97}" stroke="{mute}"/>')
    s.append(f'<text x="{(x0 + x1) / 2}" y="{y_bot + 108}" font-size="11.5" text-anchor="middle" fill="{ink}">'
             f'wall length b = {b_ft:g} ft</text>')
    s.append(f'<line x1="{x1 + 36}" y1="{y_top}" x2="{x1 + 36}" y2="{y_bot}" stroke="{mute}"/>'
             f'<line x1="{x1 + 31}" y1="{y_top}" x2="{x1 + 41}" y2="{y_top}" stroke="{mute}"/>'
             f'<line x1="{x1 + 31}" y1="{y_bot}" x2="{x1 + 41}" y2="{y_bot}" stroke="{mute}"/>')
    s.append(f'<text transform="translate({x1 + 56},{(y_top + y_bot) / 2}) rotate(90)" font-size="11.5" text-anchor="middle" '
             f'fill="{ink}">h = {h_ft:g} ft</text>')
    s.append("</svg>")
    return "".join(s)
