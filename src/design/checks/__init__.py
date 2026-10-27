"""Per-story design checks. Each function takes (ctx, story) and returns a CheckResult."""

from __future__ import annotations

from dataclasses import dataclass

from analysis.stack import StoryForces

from ..chords import ChordForces
from ..combos import ComboSet
from ..components import ComponentLibrary
from ..inputs import DesignInputs, StoryInput


@dataclass(frozen=True)
class Context:
    inp: DesignInputs
    lib: ComponentLibrary
    combos: ComboSet
    forces: tuple[StoryForces, ...]
    chords: tuple[ChordForces, ...]

    def story(self, i: int) -> StoryInput:
        return self.inp.stories[i - 1]

    def sf(self, i: int) -> StoryForces:
        return self.forces[i - 1]

    def ch(self, i: int) -> ChordForces:
        return self.chords[i - 1]
