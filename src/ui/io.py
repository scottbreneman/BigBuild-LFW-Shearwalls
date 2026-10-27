"""JSON import/export of ``DesignInputs`` (UI side only; no design logic).

Schema version 2 adds an optional ``material_preferences`` block (the project's
copy of its preferred-materials preset); version 1 files still load.
"""

from __future__ import annotations

import dataclasses
import json

from design.inputs import ChordSpec, DesignInputs, GenericHoldDown, RodSystem, StoryInput
from design.preferences import MaterialPreferences

SCHEMA_VERSION = 2
READABLE_VERSIONS = (1, 2)


def inputs_to_dict(inp: DesignInputs, prefs: MaterialPreferences | None = None) -> dict:
    d = dataclasses.asdict(inp)
    for s_new, s in zip(d["stories"], inp.stories):
        s_new["tiedown"]["type"] = "rod" if isinstance(s.tiedown, RodSystem) else "holddown"
    if prefs is not None:
        d["material_preferences"] = prefs.to_dict()
    d["schema_version"] = SCHEMA_VERSION
    return d


def inputs_to_json(inp: DesignInputs, prefs: MaterialPreferences | None = None) -> str:
    return json.dumps(inputs_to_dict(inp, prefs), indent=2)


def inputs_from_dict(d: dict) -> DesignInputs:
    version = d.get("schema_version", SCHEMA_VERSION)
    if version not in READABLE_VERSIONS:
        raise ValueError(f"Unsupported inputs schema_version {version!r}; expected one of {READABLE_VERSIONS}")
    stories = []
    for s in d["stories"]:
        s = dict(s)
        chord = ChordSpec(**s.pop("chord"))
        td = dict(s.pop("tiedown"))
        kind = td.pop("type", "rod" if "system_id" in td else "holddown")
        tiedown = RodSystem(**td) if kind == "rod" else GenericHoldDown(**td)
        stories.append(StoryInput(chord=chord, tiedown=tiedown, **s))
    top = {k: v for k, v in d.items() if k not in ("stories", "schema_version", "material_preferences")}
    return DesignInputs(stories=tuple(stories), **top)


def inputs_from_json(text: str) -> DesignInputs:
    return inputs_from_dict(json.loads(text))


def preferences_from_project(text: str) -> MaterialPreferences | None:
    """The project's saved preferred-materials block, or None (version 1 files have none)."""
    d = json.loads(text).get("material_preferences")
    return MaterialPreferences.from_dict(d) if d else None
