"""JSON import/export of ``DesignInputs`` (UI side only; no design logic)."""

from __future__ import annotations

import dataclasses
import json

from design.inputs import ChordSpec, DesignInputs, GenericHoldDown, RodSystem, StoryInput

SCHEMA_VERSION = 1


def inputs_to_dict(inp: DesignInputs) -> dict:
    d = dataclasses.asdict(inp)
    for s_new, s in zip(d["stories"], inp.stories):
        s_new["tiedown"]["type"] = "rod" if isinstance(s.tiedown, RodSystem) else "holddown"
    d["schema_version"] = SCHEMA_VERSION
    return d


def inputs_to_json(inp: DesignInputs) -> str:
    return json.dumps(inputs_to_dict(inp), indent=2)


def inputs_from_dict(d: dict) -> DesignInputs:
    version = d.get("schema_version", SCHEMA_VERSION)
    if version != SCHEMA_VERSION:
        raise ValueError(f"Unsupported inputs schema_version {version!r}; expected {SCHEMA_VERSION}")
    stories = []
    for s in d["stories"]:
        s = dict(s)
        chord = ChordSpec(**s.pop("chord"))
        td = dict(s.pop("tiedown"))
        kind = td.pop("type", "rod" if "system_id" in td else "holddown")
        tiedown = RodSystem(**td) if kind == "rod" else GenericHoldDown(**td)
        stories.append(StoryInput(chord=chord, tiedown=tiedown, **s))
    top = {k: v for k, v in d.items() if k not in ("stories", "schema_version")}
    return DesignInputs(stories=tuple(stories), **top)


def inputs_from_json(text: str) -> DesignInputs:
    return inputs_from_dict(json.loads(text))
