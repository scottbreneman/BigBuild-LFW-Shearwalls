"""Render a report ``Document`` as one HTML file.

Styles are inline. Equations are typeset with KaTeX loaded from a CDN; if the script cannot
load (offline), each equation stays on the page as readable LaTeX source. Everything else
works offline and prints to PDF from the browser.
"""

from __future__ import annotations

import re
from html import escape

from design.trace import Step

from .model import Document, Figure, Paragraph, StepTable, Subheading, Table
from .refs import citation_for, example_label
from .steps import result_text, tex_for

KATEX_VERSION = "0.16.11"
KATEX_CSS = f"https://cdn.jsdelivr.net/npm/katex@{KATEX_VERSION}/dist/katex.min.css"
KATEX_JS = f"https://cdn.jsdelivr.net/npm/katex@{KATEX_VERSION}/dist/katex.min.js"

_CSS = """
:root { color-scheme: light; }
body { font-family: system-ui, -apple-system, "Segoe UI", Arial, sans-serif; color: #1a1a1a;
       max-width: 1100px; margin: 2rem auto; padding: 0 1rem; line-height: 1.45; }
h1 { font-size: 1.6rem; margin-bottom: .25rem; }
h2 { font-size: 1.2rem; border-bottom: 2px solid #333; padding-bottom: .2rem; margin-top: 2rem; }
h3 { font-size: 1.02rem; margin: 1.4rem 0 .3rem; }
.banner { border: 2px solid #b00020; background: #fdecea; color: #7a0014; padding: .6rem .9rem;
          font-weight: 600; margin: .75rem 0 1rem; }
table { border-collapse: collapse; width: 100%; margin: .5rem 0 1rem; font-size: .9rem; }
caption { text-align: left; font-size: .85rem; color: #444; padding-bottom: .25rem; }
th, td { border: 1px solid #bbb; padding: .3rem .5rem; text-align: left; vertical-align: top; }
th { background: #eef1f4; }
td.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
tr.band-a td { background: #fbfcfd; }
tr.band-b td { background: #edf1f6; }
tr.pass td { background: #f1f9f1; }
tr.info td { background: #f4f4f4; }
/* After the bands: a failing or incomplete check must stay visible through the story banding. */
tr.fail td { background: #fdecea; }
tr.needs-input td { background: #fff7e0; }
tr.governing td { font-weight: 700; }
td[rowspan] { vertical-align: middle; text-align: center; font-weight: 600; }
table.steps { font-size: .82rem; }
table.steps td.eq { min-width: 12rem; }
table.steps td.res { white-space: nowrap; font-variant-numeric: tabular-nums; }
.tex { font-family: "Cambria Math", "STIX Two Math", serif; }
.step-name small { color: #555; }
.step-note { color: #555; font-size: .78rem; }
.ref-code { font-weight: 600; }
.ref-ex, .ref-basis { color: #444; }
.ref-gap { color: #8a5a00; font-size: .78rem; }
.badge { display: inline-block; padding: 0 .4rem; border-radius: .6rem; font-size: .74rem; border: 1px solid #999;
         white-space: nowrap; }
.badge.verified, .badge.statics { background: #e6f4e6; border-color: #5a9a5a; }
.badge.memory { background: #fff2cc; border-color: #c99a00; }
.badge.assumption { background: #e8eefb; border-color: #5b78b8; }
figure { margin: 1rem 0; }
figure svg { width: 100%; max-width: 900px; height: auto; border: 1px solid #ccc; }
figcaption { font-size: .85rem; color: #444; margin-top: .3rem; }
@media print {
  body { max-width: none; margin: 0; font-size: 10pt; }
  h2, h3 { break-after: avoid; }
  table, tr, figure { break-inside: avoid; }
}
"""

_KATEX_RENDER = """
window.addEventListener('load', function () {
  if (!window.katex) { return; }  // offline: the LaTeX source stays visible
  document.querySelectorAll('.tex').forEach(function (el) {
    try { katex.render(el.getAttribute('data-tex'), el, {throwOnError: false}); } catch (e) {}
  });
});
"""

_SUB = re.compile(r"_([A-Za-z0-9,\u03b4\u22a5*']+)")


def _symbol(sym: str) -> str:
    """Plain-text symbol with subscripts: 'M_OT' -> M<sub>OT</sub>."""
    return _SUB.sub(lambda m: f"<sub>{m.group(1)}</sub>", escape(sym))


def render_html(doc: Document) -> str:
    uses_math = any(isinstance(b, StepTable) for s in doc.sections for b in s.blocks)
    head = [
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{escape(doc.title)}</title>",
        f"<style>{_CSS}</style>",
    ]
    if uses_math:
        head += [f'<link rel="stylesheet" href="{KATEX_CSS}">', f'<script defer src="{KATEX_JS}"></script>']
    parts = ["<!DOCTYPE html>", '<html lang="en">', "<head>", *head, "</head>", "<body>",
             f"<h1>{escape(doc.title)}</h1>", f'<div class="banner">{escape(doc.banner)}</div>']
    for section in doc.sections:
        parts.append(f'<section id="{escape(section.id, quote=True)}">')
        parts.append(f"<h2>{escape(section.title)}</h2>")
        for block in section.blocks:
            parts.append(_block(block))
        parts.append("</section>")
    if uses_math:
        parts.append(f"<script>{_KATEX_RENDER}</script>")
    parts += ["</body>", "</html>", ""]
    return "\n".join(parts)


def _block(block) -> str:
    if isinstance(block, Paragraph):
        return f"<p>{escape(block.text)}</p>"
    if isinstance(block, Subheading):
        return f"<h3>{escape(block.text)}</h3>"
    if isinstance(block, Figure):
        cap = f"<figcaption>{escape(block.caption)}</figcaption>" if block.caption else ""
        return f"<figure>{block.svg}{cap}</figure>"
    if isinstance(block, StepTable):
        return _step_table(block)
    return _table(block)


def _table(t: Table) -> str:
    out = ["<table>"]
    if t.caption:
        out.append(f"<caption>{escape(t.caption)}</caption>")
    out.append("<thead><tr>" + "".join(f"<th>{escape(h)}</th>" for h in t.headers) + "</tr></thead>")
    out.append("<tbody>")
    spans = _spans(t)
    for i, row in enumerate(t.rows):
        cls = t.row_classes[i] if t.row_classes else ""
        tr = f' class="{escape(cls, quote=True)}"' if cls else ""
        cells = "".join(_cell(c, j, t, spans.get((i, j))) for j, c in enumerate(row)
                        if spans.get((i, j)) != 0)  # 0 = covered by the rowspan above
        out.append(f"<tr{tr}>{cells}</tr>")
    out += ["</tbody>", "</table>"]
    return "\n".join(out)


def _spans(t: Table) -> dict[tuple[int, int], int]:
    """{(row, col): rowspan} for the first row of each run in ``span_col``; 0 for the rows it covers."""
    if t.span_col is None:
        return {}
    j, out, start = t.span_col, {}, 0
    for i in range(1, len(t.rows) + 1):
        if i == len(t.rows) or t.rows[i][j] != t.rows[start][j]:
            out[(start, j)] = i - start
            for k in range(start + 1, i):
                out[(k, j)] = 0
            start = i
    return out


def _cell(text: str, j: int, t: Table, span: int | None = None) -> str:
    body = _symbol(text) if j in t.symbol_cols else escape(text)
    attrs = f' rowspan="{span}"' if span and span > 1 else ""
    cls = ' class="num"' if j in t.align_right else ""
    return f"<td{cls}{attrs}>{body}</td>"


def _equation(step: Step) -> str:
    if not step.equation_latex:
        return ""
    # data-tex feeds KaTeX; the element's own text is the fallback shown if KaTeX cannot load.
    return (f'<span class="tex" data-tex="{escape(tex_for(step), quote=True)}">'
            f'{escape(step.equation_latex)}</span>')


def _reference(step: Step, *, include_basis: bool = True) -> str:
    c = citation_for(step)
    out = [f'<div class="ref-code">{escape(r)}</div>' for r in c.code]
    out += [f'<div class="ref-ex">{escape(example_label(r))}</div>' for r in c.example]
    if include_basis:
        out += [f'<div class="ref-basis">{escape(b.capitalize() if b == "statics" else b)}</div>' for b in c.basis]
    if c.gap:
        out.append(f'<div class="ref-gap">\u26a0 {escape(c.gap)}</div>')
    return "".join(out)


def _badge(step: Step) -> str:
    return f'<span class="badge {escape(step.status)}">{escape(step.status)}</span>'


def _step_name(step: Step) -> str:
    sym = f" <small>{_symbol(step.symbol)}</small>" if step.symbol else ""
    note = f'<div class="step-note">{escape(step.note)}</div>' if step.note else ""
    return f'<span class="step-name">{escape(step.name)}{sym}</span>{note}'


def _step_table(t: StepTable) -> str:
    out = ['<table class="steps">']
    if t.caption:
        out.append(f"<caption>{escape(t.caption)}</caption>")
    if t.mode == "catalog":
        heads = ("Step", "Equation", "Reference", "Source status")
    else:
        heads = ("Step", "Equation", "Substitution", "Result", "Reference", "Source status")
    out.append("<thead><tr>" + "".join(f"<th>{h}</th>" for h in heads) + "</tr></thead><tbody>")
    for s in t.steps:
        sid = escape(s.id, quote=True)
        if t.mode == "catalog":
            cells = [_step_name(s), f'<td class="eq">{_equation(s)}</td>', _reference(s), _badge(s)]
            row = f"<td>{cells[0]}</td>{cells[1]}<td>{cells[2]}</td><td>{cells[3]}</td>"
        else:
            row = (f"<td>{_step_name(s)}</td><td class=\"eq\">{_equation(s)}</td><td>{escape(s.substitution)}</td>"
                   f'<td class="res">{escape(result_text(s))}</td><td>{_reference(s)}</td><td>{_badge(s)}</td>')
        out.append(f'<tr data-step-id="{sid}">{row}</tr>')
    out += ["</tbody>", "</table>"]
    return "\n".join(out)
