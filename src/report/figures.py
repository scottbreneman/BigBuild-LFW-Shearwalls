"""SVG free-body figure of the wall stack (statics: story shear and overturning).

Every number printed in the figure is read from the ``DesignResult`` (story forces from
the inputs, V, M_OT and C_E from the calc-trace steps). The only values computed here
are drawing coordinates.
"""

from __future__ import annotations

from html import escape

from design.result import DesignResult


_INK = "#1a1a1a"
_FORCE = "#b00020"
_REACT = "#0b6b3a"
_DIM = "#666666"


def _label(x: float, y: float, *parts, anchor: str = "start", size: float = 12, bold: bool = False,
           fill: str = _INK) -> str:
    """SVG text. A tuple part is a subscript, e.g. ``("F", ("5",), " = 9,397 lb")``."""
    drop = size * 0.28
    out, after_sub = [], False
    for p in parts:
        if isinstance(p, tuple):
            out.append(f'<tspan dy="{drop:.1f}" font-size="{size * 0.75:.1f}">{escape(p[0])}</tspan>')
            after_sub = True
        elif after_sub:
            out.append(f'<tspan dy="{-drop:.1f}">{escape(p)}</tspan>')
            after_sub = False
        else:
            out.append(escape(p))
    weight = ' font-weight="700"' if bold else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" font-size="{size}"{weight} '
            f'fill="{fill}">{"".join(out)}</text>')


def _arrow(x1: float, y1: float, x2: float, y2: float, color: str, marker: str, width: float = 2.2) -> str:
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" '
            f'stroke-width="{width}" marker-end="url(#{marker})"/>')


def _value(result: DesignResult, step_id: str) -> float | None:
    try:
        v = result.step(step_id).value
    except KeyError:
        return None
    return v if isinstance(v, (int, float)) else None


def stack_fbd_svg(result: DesignResult) -> str:
    inp = result.inputs
    n = len(inp.stories)
    heights = [s.h_ft for s in inp.stories]
    total_h, b = sum(heights), inp.b_ft
    scale = min(300 / b, 620 / total_h)  # px per ft, same in both directions
    wall_w = b * scale
    x0, top = 200.0, 56.0
    y_base = top + total_h * scale
    width, height = 900, y_base + 134

    elev = [0.0]  # elev[j] = elevation of the top of story j above the base of story 1
    for h in heights:
        elev.append(elev[-1] + h)

    def y(e: float) -> float:
        return y_base - e * scale

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height:.0f}" role="img" '
        f'aria-label="Free-body diagram of the shear wall stack" font-family="system-ui, Arial, sans-serif">',
        "<defs>"
        f'<marker id="arrF" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
        f'orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{_FORCE}"/></marker>'
        f'<marker id="arrR" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
        f'orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{_REACT}"/></marker>'
        f'<marker id="arrD" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" '
        f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{_DIM}"/></marker>'
        "</defs>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        _label(20, 22, "Strength-level forces. Story 1 is the bottom wall; each cut is at the base of the story "
                        "named at the right.", size=11, fill=_DIM),
    ]

    # Wall panels, one per story.
    for j in range(1, n + 1):
        y_top, y_bot = y(elev[j]), y(elev[j - 1])
        parts.append(f'<rect x="{x0:.1f}" y="{y_top:.1f}" width="{wall_w:.1f}" height="{y_bot - y_top:.1f}" '
                     f'fill="#f3f6f9" stroke="#333" stroke-width="1.5"/>')
        parts.append(_label(x0 + wall_w / 2, (y_top + y_bot) / 2 + 4, f"Story {j}", anchor="middle",
                            size=13, fill=_DIM))

    # Applied story forces at the top of each story, with the elevation dimension on the right.
    x_dim = x0 + wall_w + 24
    parts.append(f'<line x1="{x_dim:.1f}" y1="{y_base:.1f}" x2="{x_dim:.1f}" y2="{y(elev[n]):.1f}" '
                 f'stroke="{_DIM}" stroke-width="1" marker-start="url(#arrD)" marker-end="url(#arrD)"/>')
    for j in range(1, n + 1):
        yj = y(elev[j])
        F = inp.stories[j - 1].F_lb
        parts.append(_arrow(x0 - 130, yj, x0 - 2, yj, _FORCE, "arrF"))
        parts.append(_label(x0 - 130, yj - 7, "F", (str(j),), f" = {F:,.0f} lb", size=12, bold=True, fill=_FORCE))
        parts.append(f'<line x1="{x_dim - 4:.1f}" y1="{yj:.1f}" x2="{x_dim + 4:.1f}" y2="{yj:.1f}" '
                     f'stroke="{_DIM}" stroke-width="1"/>')
        parts.append(_label(x_dim + 8, yj + 4, "H", (str(j),), f" = {elev[j]:,.1f} ft", size=10, fill=_DIM))

    # Story cuts with the resulting shear, overturning moment and chord couple.
    x_note = x0 + wall_w + 118
    for i in range(1, n + 1):
        yc = y(elev[i - 1])
        parts.append(f'<line x1="{x0 - 30:.1f}" y1="{yc:.1f}" x2="{x0 + wall_w + 12:.1f}" y2="{yc:.1f}" '
                     f'stroke="#555" stroke-width="1.2" stroke-dasharray="6 4"/>')
        V = _value(result, f"S{i}.statics.V")
        M = _value(result, f"S{i}.statics.M_OT")
        C = _value(result, f"S{i}.chord.C_E")
        lines = []
        if V is not None:
            lines.append(("V", (str(i),), f" = {V:,.0f} lb"))
        if M is not None:
            lines.append(("M", (f"OT,{i}",), f" = {M:,.0f} ft-lb"))
        if C is not None:
            lines.append(("C", (f"E,{i}",), f" = M/d = {C:,.0f} lb"))
        for k, ln in enumerate(lines):
            parts.append(_label(x_note, yc - 8 - 15 * (len(lines) - 1 - k), *ln, size=12, fill=_INK))

    # Reactions at the base of story 1: shear V, and the tension / compression couple.
    xl, xr = x0 + 22, x0 + wall_w - 22
    parts.append(_arrow(x0 + wall_w - 50, y_base + 14, x0 + 50, y_base + 14, _REACT, "arrR"))
    V1 = _value(result, "S1.statics.V")
    if V1 is not None:
        parts.append(_label(x0 + wall_w / 2, y_base + 32, "V", ("1",), f" = ΣF = {V1:,.0f} lb", anchor="middle",
                            size=12, bold=True, fill=_REACT))
    parts.append(_arrow(xl, y_base + 2, xl, y_base + 34, _REACT, "arrR"))  # tension end: pulled down
    parts.append(_arrow(xr, y_base + 34, xr, y_base + 2, _REACT, "arrR"))  # compression end: pushed up
    parts.append(_label(xl - 8, y_base + 24, "T", anchor="end", size=12, bold=True, fill=_REACT))
    parts.append(_label(xr + 8, y_base + 24, "C", anchor="start", size=12, bold=True, fill=_REACT))

    # Lever arm of the couple (story 1) and the wall length.
    d1 = _value(result, "S1.statics.d")
    if d1 is not None:
        yl = y_base + 66
        parts.append(f'<line x1="{xl:.1f}" y1="{yl:.1f}" x2="{xr:.1f}" y2="{yl:.1f}" stroke="{_REACT}" '
                     f'stroke-width="1" marker-start="url(#arrD)" marker-end="url(#arrD)"/>')
        parts.append(_label((xl + xr) / 2, yl - 5, "d", ("1",), f" = {d1:,.2f} ft (couple lever arm, story 1)",
                            anchor="middle", size=11, fill=_REACT))
    yd = y_base + 100
    parts.append(f'<line x1="{x0:.1f}" y1="{yd:.1f}" x2="{x0 + wall_w:.1f}" y2="{yd:.1f}" stroke="{_DIM}" '
                 f'stroke-width="1" marker-start="url(#arrD)" marker-end="url(#arrD)"/>')
    parts.append(_label(x0 + wall_w / 2, yd + 16, f"b = {b:,.1f} ft", anchor="middle", size=12, fill=_DIM))

    parts.append("</svg>")
    return "\n".join(parts)

