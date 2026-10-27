# Component library

`src/design/components/` holds the material and product data the design checks will draw on: framing lumber, sheathing panels, nails, sheathed shear-wall assemblies, hold-downs, and continuous rod tie-down systems. It contains **no design formulas**. Adjustment factors, ASD/LRFD conversion, and the deflection equation belong in the design module and cite the standard there.

## Why the data is in CSV

Each component type is one CSV file in `src/design/components/data/`. An engineer can open it in Excel, fill in a row from the standard or catalog in front of them, and set the row's status. Python (`loader.py`) reads the file into a typed record (`schema.py`), rejects anything it cannot parse, and refuses to hand a `pending` row to a calculation unless the caller explicitly asks for it. The tool therefore cannot quietly use a number nobody has checked.

Units are US customary and are written into the column names: `_in`, `_psi`, `_plf`, `_lb`, `_kips_per_in`.

## The three bookkeeping columns

Every table ends with the same three columns.

| Column | Meaning |
| --- | --- |
| `source` | Where the row's values came from: standard + edition + table, or manufacturer catalog edition + page, or evaluation report number. Must never be blank; the loader fails on a blank source. |
| `status` | `pending` — row exists but values are not yet entered or not yet checked. `verified` — values transcribed and checked by an engineer against the cited source. `superseded` — kept for history, never returned. |
| `notes` | Free text: what still needs filling, footnotes that apply, edition differences. |

**Every seeded row is `pending`.** That includes the lumber dressed sizes and nail dimensions, which were typed in from common knowledge and need a two-minute check against the cited table before they are flipped to `verified`. Design values (`Fb_psi`, `v_seismic_nominal_plf`, allowable hold-down tension, …) were deliberately left blank: the onboarding guidance is not to have a coding assistant reconstruct standard tables from memory, and the AGENTS.md rule is not to invent table entries.

## Tables

### `lumber_sizes.csv` — dressed dimensions

Nominal size, actual thickness (smaller dimension) and width (larger dimension). Area and section moduli are computed by the `LumberSize` record from the rectangle; nothing else is stored. Source: NDS 2024 Supplement Table 1B.

### `lumber_design_values.csv` — reference design values

One row per species group × grade × size class. Reference (unadjusted) values `Fb`, `Ft`, `Fv`, `Fc⊥`, `Fc`, `E`, `Emin` in psi, plus specific gravity `G` for fastener design.

| Species group | Rows seeded | Source |
| --- | --- | --- |
| Douglas Fir-Larch | SS, No.1, No.2, Stud for `2"-4" thick, 2" & wider`; No.1, No.2 Posts & Timbers | NDS 2024 Supplement Tables 4A and 4D |
| Spruce-Pine-Fir | SS, No.1, No.2, Stud for `2"-4" thick, 2" & wider` | NDS 2024 Supplement Table 4A |
| Southern Pine | SS, No.1, No.2, Stud for each of 2x4 … 2x12; No.1, No.2 Posts & Timbers | NDS 2024 Supplement Tables 4B and 4D |

Southern Pine values are width-specific, so the `size_class` column holds the actual size (`2x6`) rather than a range. Use the source table's own row label in `size_class` so a reviewer can find it. `G` comes from NDS 2024 Table 12.3.3A; note that in `notes` if you cite a different table.

If the team settles on a species not listed (Hem-Fir, for example), add rows; do not repurpose existing ones.

### `sheathing_panels.csv` — wood structural panels

OSB and plywood, `Sheathing` and `Structural I` grades, nominal thicknesses 3/8 through 5/8. `nominal_thickness_in` is the decimal of the label and is what the assembly table joins on. `span_rating` and `exposure` are blank until something needs them.

### `nails.csv` — nail dimensions

Trade designation (`8d common`), type, diameter and length in inches. `Fyb` (bending yield strength) is blank; fill from NDS 2024 Table I1 only if nail yield-mode design is added. Source: NDS 2024 Appendix L, Table L4. Shear-wall assembly rows reference nails by `designation`, and a test checks the reference resolves.

### `shear_wall_assemblies.csv` — SDPWS Table 4.3A structure

One row per (panel grade, minimum panel thickness, nail, edge nail spacing) combination — the same cell structure as SDPWS 2021 Table 4.3A for blocked wood structural panel shear walls. Fill, per row:

- `min_fastener_penetration_in`
- `v_seismic_nominal_plf` — nominal unit shear capacity, seismic
- `Ga_osb_kips_per_in` and `Ga_plywood_kips_per_in` — apparent shear stiffness
- `v_wind_nominal_plf` — nominal unit shear capacity, wind
- `footnotes` — the footnote letters that apply to that row (framing species, 3x framing at close spacing, panel orientation, etc.)

The values are **nominal** exactly as tabulated. The ASD reduction factor and LRFD resistance factor from SDPWS 4.3.3 are applied in the design module, which must cite that section.

`assembly_id` is a stable key of the form `WSP-<grade>-<thickness>-<nail>-<spacing>`, e.g. `WSP-S1-15/32-10dc-3` (Structural I, 15/32 in., 10d common, 3 in. edge spacing). Once an ID is used anywhere, do not rename it; mark the row `superseded` and add a new one.

### `holddowns.csv` — discrete hold-downs

Simpson HDU and HDQ/HHDQ series seeded by model and screw type only. Fill anchor diameter, fastener count, minimum post, allowable tension for DF/SP and for SPF/HF posts, deflection at allowable load, and the evaluation report number, citing the catalog edition and page. If another manufacturer is used, add rows with that manufacturer's name.

### `continuous_rod_systems.csv` — rod tie-downs (ATS-type)

One row per rod diameter × material (standard strength and high strength). Fill allowable rod tension, net tensile area, the take-up device and bearing plate used, and the evaluation report. If the drift model needs take-up device slip or bearing-plate crushing stiffness, those get their own tables rather than being squeezed in here.

## Workflow for filling a table

1. Open the CSV in Excel or a text editor. Keep the header row exactly as it is.
2. With the cited standard or catalog open, fill one row at a time. Put the page or table in `source` if it is not already specific enough.
3. Set `status` to `verified` only after a second look against the source. If you transcribed but did not re-check, leave `pending` and say so in `notes`.
4. Save as CSV (UTF-8). Do not let Excel reformat fractions or add thousands separators.
5. Run `python -m pytest tests/test_component_library.py -q` from the repo root. The tests check parsing, citations, and cross-references between tables; they do not check the values.
6. Commit with a message saying which table and which source you worked from.

## Using the library in code

```python
from design.components import load_library

lib = load_library()
post = lib.lumber_size("4x4")                     # raises UnverifiedComponentError until verified
post = lib.lumber_size("4x4", allow_pending=True) # exploratory use only
asm = lib.assembly("WSP-SH-7/16-8dc-4")
nail = lib.nail(asm.nail_designation)
print(lib.pending())                              # how many rows per table still need values
```

Anything that reaches a reported calculation must come from a `verified` row; `allow_pending=True` is for development and must not appear in the design checks.
