"""Which calc-trace steps belong to which report section."""

from __future__ import annotations

import re

from design.trace import Step

_STORY_PREFIX = re.compile(r"^S\d+\.")

# Statics steps that live inside checks (the chord forces); shown once, in the statics section.
_CHORD_STATICS = {"chord.C_E", "chord.M_R", "chord.asd.net", "chord.asd.T", "chord.dT"}


def local_id(step_id: str) -> str:
    """Step id without its story prefix: 'S3.shear.v_n' -> 'shear.v_n'."""
    return _STORY_PREFIX.sub("", step_id)


def is_combo(step: Step) -> bool:
    return step.id.startswith("combo.")


def is_statics(step: Step) -> bool:
    loc = local_id(step.id)
    return loc.startswith("statics.") or loc in _CHORD_STATICS


def story_of(step_id: str) -> int | None:
    m = _STORY_PREFIX.match(step_id)
    return int(m.group(0)[1:-1]) if m else None


def result_text(step: Step) -> str:
    """The step's value with its unit, e.g. '18,526 lb'."""
    from .numfmt import snum

    return f"{snum(step.value)} {step.unit}".strip()


_PROSE_WORD = re.compile(r"[A-Za-z]{3,}")


def tex_for(step: Step) -> str:
    """LaTeX for the step's equation. A few steps carry a plain-text note instead of a formula
    (e.g. a code provision); those are set as text so KaTeX does not run the words together."""
    eq = step.equation_latex
    if eq and not any(ch in eq for ch in "\\_^{") and len(_PROSE_WORD.findall(eq)) >= 2:
        return r"\text{" + eq + "}"
    return eq
