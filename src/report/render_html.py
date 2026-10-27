"""Render a report ``Document`` as one self-contained HTML file (no external assets).

Styles are inline so the file opens offline and prints to PDF from the browser.
"""

from __future__ import annotations

from html import escape

from .model import Document, Paragraph, Table

_CSS = """
:root { color-scheme: light; }
body { font-family: system-ui, -apple-system, "Segoe UI", Arial, sans-serif; color: #1a1a1a;
       max-width: 1000px; margin: 2rem auto; padding: 0 1rem; line-height: 1.45; }
h1 { font-size: 1.6rem; margin-bottom: .25rem; }
h2 { font-size: 1.2rem; border-bottom: 2px solid #333; padding-bottom: .2rem; margin-top: 2rem; }
.banner { border: 2px solid #b00020; background: #fdecea; color: #7a0014; padding: .6rem .9rem;
          font-weight: 600; margin: .75rem 0 1rem; }
table { border-collapse: collapse; width: 100%; margin: .5rem 0 1rem; font-size: .9rem; }
caption { text-align: left; font-size: .85rem; color: #444; padding-bottom: .25rem; }
th, td { border: 1px solid #bbb; padding: .3rem .5rem; text-align: left; vertical-align: top; }
th { background: #eef1f4; }
td.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
tr.pass td { background: #f1f9f1; }
tr.fail td { background: #fdecea; }
tr.needs-input td { background: #fff7e0; }
tr.info td { background: #f4f4f4; }
tr.governing td { font-weight: 700; }
@media print {
  body { max-width: none; margin: 0; font-size: 10pt; }
  h2 { break-after: avoid; }
  table, tr { break-inside: avoid; }
}
"""


def render_html(doc: Document) -> str:
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{escape(doc.title)}</title>",
        f"<style>{_CSS}</style>",
        "</head>",
        "<body>",
        f"<h1>{escape(doc.title)}</h1>",
        f'<div class="banner">{escape(doc.banner)}</div>',
    ]
    for section in doc.sections:
        parts.append(f'<section id="{escape(section.id, quote=True)}">')
        parts.append(f"<h2>{escape(section.title)}</h2>")
        for block in section.blocks:
            parts.append(_paragraph(block) if isinstance(block, Paragraph) else _table(block))
        parts.append("</section>")
    parts += ["</body>", "</html>", ""]
    return "\n".join(parts)


def _paragraph(p: Paragraph) -> str:
    return f"<p>{escape(p.text)}</p>"


def _table(t: Table) -> str:
    out = ["<table>"]
    if t.caption:
        out.append(f"<caption>{escape(t.caption)}</caption>")
    out.append("<thead><tr>" + "".join(f"<th>{escape(h)}</th>" for h in t.headers) + "</tr></thead>")
    out.append("<tbody>")
    for i, row in enumerate(t.rows):
        cls = t.row_classes[i] if t.row_classes else ""
        tr = f' class="{escape(cls, quote=True)}"' if cls else ""
        cells = "".join(
            f'<td class="num">{escape(c)}</td>' if j in t.align_right else f"<td>{escape(c)}</td>"
            for j, c in enumerate(row)
        )
        out.append(f"<tr{tr}>{cells}</tr>")
    out += ["</tbody>", "</table>"]
    return "\n".join(out)
