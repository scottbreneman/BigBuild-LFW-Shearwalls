"""Renderer-neutral document model for the calculation report (docs/spec-io.md §6).

``sections.build_document`` turns a ``DesignResult`` into a ``Document``; the HTML
and Markdown renderers walk the same ``Document``, so the two outputs cannot
disagree about content.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Union

from design.trace import Step

# Story tables list the top story first (5, 4, 3, 2, 1), like the building. Set False for bottom-up.
STORIES_TOP_DOWN = True


def story_order(n: int) -> list[int]:
    """Story numbers (1 = bottom) in the order report tables list them."""
    stories = list(range(1, n + 1))
    return stories[::-1] if STORIES_TOP_DOWN else stories


@dataclass(frozen=True)
class Paragraph:
    text: str


@dataclass(frozen=True)
class Subheading:
    text: str


@dataclass(frozen=True)
class Table:
    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    caption: str = ""
    # One entry per row, space-separated class names the HTML renderer styles
    # (pass, fail, needs-input, info, governing); Markdown ignores them.
    row_classes: tuple[str, ...] = ()
    align_right: tuple[int, ...] = ()  # column indexes holding numbers
    symbol_cols: tuple[int, ...] = ()  # column indexes holding symbols such as M_OT (HTML shows subscripts)
    # Column whose runs of equal values merge into one cell (HTML rowspan), e.g. one "5" beside
    # all of story 5's checks. Markdown has no merged cells, so it repeats the value.
    span_col: int | None = None

    def __post_init__(self) -> None:
        for r in self.rows:
            if len(r) != len(self.headers):
                raise ValueError(f"row has {len(r)} cells, table has {len(self.headers)} columns: {r!r}")
        if self.row_classes and len(self.row_classes) != len(self.rows):
            raise ValueError("row_classes must be empty or match the number of rows")


@dataclass(frozen=True)
class StepTable:
    """Calc-trace steps shown with their equation (typeset as LaTeX), reference and source status.

    ``calc`` shows the substituted values and result; ``catalog`` shows the equation and its
    reference only, once per check, without numbers.
    """

    steps: tuple[Step, ...]
    caption: str = ""
    mode: Literal["calc", "catalog"] = "calc"


@dataclass(frozen=True)
class Figure:
    svg: str  # a complete <svg> element
    caption: str = ""
    markdown_note: str = "Figure not included in the Markdown copy; see the HTML report."


Block = Union[Paragraph, Subheading, Table, StepTable, Figure]


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
