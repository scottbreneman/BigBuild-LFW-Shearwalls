"""Preferred materials: a down-selection of the component library for design.

A ``MaterialPreferences`` names the assemblies, lumber, post sizes, rods and
hold-downs an office or project prefers. The UI filters its dropdowns with it
and auto-size (``design.autosize``) draws candidates from it. An empty list
means "no restriction". Presets are JSON files that can be shared; a copy is
saved with each project.
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass

from .components import ComponentLibrary
from .components.schema import ContinuousRodSystem, HoldDown, LumberDesignValues, ShearWallAssembly

SCHEMA_VERSION = 1
DF_SP = ("Douglas Fir-Larch", "Southern Pine")  # species using the DF/SP hold-down column


@dataclass(frozen=True)
class MaterialPreferences:
    name: str = ""
    assemblies: tuple[str, ...] = ()  # assembly_ids
    sides: tuple[int, ...] = (1, 2)  # sheathed sides auto-size may use
    panel_types: tuple[str, ...] = ("OSB",)  # first entry is used by auto-size
    lumber: tuple[tuple[str, str, str], ...] = ()  # (species_group, grade, size_class)
    post_sizes: tuple[str, ...] = ("2x4",)
    min_posts: int = 2
    max_posts: int = 16
    rods: tuple[str, ...] = ()  # system_ids
    holddowns: tuple[str, ...] = ()  # models
    notes: str = ""

    # ---- JSON -----------------------------------------------------------------

    def to_dict(self) -> dict:
        d = dataclasses.asdict(self)
        d["lumber"] = [list(x) for x in self.lumber]
        d["schema_version"] = SCHEMA_VERSION
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, d: dict) -> "MaterialPreferences":
        version = d.get("schema_version", SCHEMA_VERSION)
        if version != SCHEMA_VERSION:
            raise ValueError(f"Unsupported preferences schema_version {version!r}; expected {SCHEMA_VERSION}")
        known = {f.name for f in dataclasses.fields(cls)}
        kw = {k: v for k, v in d.items() if k in known}
        for k in ("assemblies", "panel_types", "post_sizes", "rods", "holddowns"):
            if k in kw:
                kw[k] = tuple(str(x) for x in kw[k])
        if "sides" in kw:
            kw["sides"] = tuple(int(x) for x in kw["sides"])
        if "lumber" in kw:
            kw["lumber"] = tuple(tuple(str(y) for y in x) for x in kw["lumber"])
        return cls(**kw)

    @classmethod
    def from_json(cls, text: str) -> "MaterialPreferences":
        return cls.from_dict(json.loads(text))

    # ---- library views (capacity ascending; rows without values last) ------------

    def assembly_options(self, lib: ComponentLibrary) -> list[tuple[ShearWallAssembly, int]]:
        """(assembly, sides) pairs in ascending capacity n·v_n (Ω is common to all, so it does not change the order)."""
        rows = [a for a in lib.shear_wall_assemblies if not self.assemblies or a.assembly_id in self.assemblies]
        pairs = [(a, n) for a in rows for n in sorted(self.sides)]
        return sorted(pairs, key=lambda p: (p[0].v_n_plf is None, (p[0].v_n_plf or 0) * p[1], p[0].assembly_id))

    def lumber_options(self, lib: ComponentLibrary) -> list[LumberDesignValues]:
        rows = [v for v in lib.lumber_design_values
                if not self.lumber or (v.species_group, v.grade, v.size_class) in self.lumber]
        return sorted(rows, key=lambda v: (v.Fc_psi is None, v.Fc_psi or 0, v.species_group, v.grade))

    def rod_options(self, lib: ComponentLibrary) -> list[ContinuousRodSystem]:
        rows = [r for r in lib.continuous_rod_systems if not self.rods or r.system_id in self.rods]
        return sorted(rows, key=lambda r: (r.rod_allowable_tension_lb is None, r.rod_allowable_tension_lb or 0,
                                           r.system_id))

    def holddown_options(self, lib: ComponentLibrary, species_group: str) -> list[HoldDown]:
        col = "allowable_tension_DF_SP_lb" if species_group in DF_SP else "allowable_tension_SPF_HF_lb"
        rows = [h for h in lib.holddowns if not self.holddowns or h.model in self.holddowns]
        return sorted(rows, key=lambda h: (getattr(h, col) is None, getattr(h, col) or 0, h.model))

    def post_size_options(self, lib: ComponentLibrary) -> list[str]:
        return [s.nominal for s in lib.lumber_sizes if not self.post_sizes or s.nominal in self.post_sizes]

    # ---- validation ------------------------------------------------------------

    def check_against(self, lib: ComponentLibrary) -> list[str]:
        """Warnings: preferred ids the library does not have, and how many preferred rows are not verified."""
        out = []

        def missing(label, wanted, have):
            gone = [w for w in wanted if w not in have]
            if gone:
                out.append(f"{label} not in the library: {', '.join(map(str, gone))}")

        missing("Assemblies", self.assemblies, {a.assembly_id for a in lib.shear_wall_assemblies})
        missing("Lumber", self.lumber, {(v.species_group, v.grade, v.size_class) for v in lib.lumber_design_values})
        missing("Post sizes", self.post_sizes, {s.nominal for s in lib.lumber_sizes})
        missing("Rods", self.rods, {r.system_id for r in lib.continuous_rod_systems})
        missing("Hold-downs", self.holddowns, {h.model for h in lib.holddowns})
        if not 1 <= self.min_posts <= self.max_posts:
            out.append(f"Post count range {self.min_posts}-{self.max_posts} is not valid")
        if not self.sides or any(n not in (1, 2) for n in self.sides):
            out.append("Sheathed sides must be 1 and/or 2")
        recs = ([a for a, _ in self.assembly_options(lib)] + self.lumber_options(lib) + self.rod_options(lib)
                + [h for h in lib.holddowns if not self.holddowns or h.model in self.holddowns])
        unverified = {}
        for r in {id(r): r for r in recs}.values():
            if r.status.value != "verified":
                unverified[r.status.value] = unverified.get(r.status.value, 0) + 1
        if unverified:
            out.append("Preferred rows not verified: " + ", ".join(f"{n} {s}" for s, n in sorted(unverified.items())))
        return out
