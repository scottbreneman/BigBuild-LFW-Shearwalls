"""Renderer-neutral document model for the calculation report (docs/spec-io.md §6).

``sections.build_document`` turns a ``DesignResult`` into a ``Document``; the HTML
and Markdown renderers walk the same ``Document``, so the two outputs cannot
disagree about content.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Union

# Row classes the HTML renderer styles; Markdown ignores them.
ROW_CLASSES = ("pass", "fail", "needs-input", "info", "governing")


@dataclass(frozen=True)
class Paragraph:
    text: str


@dataclass(frozen=True)
class Table:
    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    caption: str = ""
    row_classes: tuple[str, ...] = ()  # one entry per row ("" for none); may be empty
    align_right: tuple[int, ...] = ()  # column indexes holding numbers

    def __post_init__(self) -> None:
        for r in self.rows:
            if len(r) != len(self.headers):
                raise ValueError(f"row has {len(r)} cells, table has {len(self.headers)} columns: {r!r}")
        if self.row_classes and len(self.row_classes) != len(self.rows):
            raise ValueError("row_classes must be empty or match the number of rows")


Block = Union[Paragraph, Table]


@dataclass(frozen=True)
class Section:
    id: str
    title: str
    blocks: tuple[Block, ...] = ()


@dataclass(frozen=True)
class Document:
    title: str
    banner: str  # prototype disclaimer, shown prominently at the top
    sections: tuple[Section, ...] = field(default_factory=tuple)
