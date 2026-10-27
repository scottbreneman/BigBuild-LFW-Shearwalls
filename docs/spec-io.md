# Spec: inputs, outputs, calc trace and report

Status: draft for engineer review on event day. Units are US customary (lb, ft, in, plf, psi). Load level is ASD. Editions: IBC 2024, SDPWS 2021, NDS 2024, ASCE 7-22. See [hackathon-plan.md](hackathon-plan.md) for stages, roles and the source-status rule.

Everything marked `memory` below was written from memory by Claude and is **not yet checked against the source**. Engineers read each cited section and change the status to `verified` (with their initials in the commit message or data row) or correct the item.

## 1. Inputs

### Global

| Name | Symbol | Unit | Notes |
| --- | --- | --- | --- |
| Load type | | seismic / wind | Selects the table column, the dead-load factor and the drift rule |
| Number of stories | n | unitless | 1 to 5; story 1 is the bottom |
| Design spectral acceleration | S_DS | unitless | Seismic only |
| Deflection amplification factor | C_d | unitless | Seismic drift only (Stage C) |
| Importance factor | I_e | unitless | Seismic drift only (Stage C) |

### Wall (same for every story in the stack)

| Name | Symbol | Unit | Notes |
| --- | --- | --- | --- |
| Wall length | b | ft | Solid wall, no openings |
| End post width | d_post | in | For the chord lever arm (decision D2) |

### Per story i (1 = bottom)

| Name | Symbol | Unit | Notes |
| --- | --- | --- | --- |
| Story height | h_i | ft | Floor-to-floor wall height |
| Applied lateral force at level i | F_i | lb | ASD level, already combined for the chosen load type (decision D8) |
| Dead load on the wall at level i | w_D,i | plf | Uniform along the wall, excluding wall self-weight |
| Wall self-weight | w_wall,i | plf | Optional |
| Nailing selection | | table row id | One row of the capacity table: panel grade, thickness, nail, edge spacing |
| Sheathing sides | | 1 or 2 | Combination rule for two sides is an engineer decision |
| Hold-down allowable tension | T_allow,i | lb | From the product evaluation report; user input |
| Chord modulus and area | E, A | psi, in² | Stage C only |
| Anchorage slip at the hold-down | Δ_a,i | in | Stage C only; from the product data |

### Capacity table row (data file)

| Field | Unit | Notes |
| --- | --- | --- |
| id, panel grade, thickness, nail type and size, edge spacing | text, in | One row per nailing selection |
| Nominal unit shear, seismic and wind | plf | SDPWS-2021 Table 4.3A. Entered by an engineer, never by an AI assistant |
| Apparent shear stiffness G_a | kip/in | Stage C |
| source_doc, table, page, footnotes | text | Required |
| status, entered_by, checked_by | text | `verified` or `memory`, with names |

## 2. Calc trace contract

Every check returns a list of steps instead of bare numbers. The screen and the report both read the same list, so what the engineer sees is what the report prints.

```python
@dataclass(frozen=True)
class Step:
    id: str              # "A.shear.v_demand"
    name: str            # "Unit shear demand"
    symbol: str          # "v"
    equation_latex: str  # "v = V / b"
    substitution: str    # "v = 4200 lb / 14 ft"  (values with units)
    value: float | str
    unit: str            # "plf"
    citation: str        # "SDPWS-2021 §4.3.3" or "statics"
    status: Literal["statics", "verified", "memory", "assumption"]
    note: str = ""

@dataclass(frozen=True)
class CheckResult:
    name: str            # "Shear in story 2"
    demand: float
    capacity: float
    dcr: float
    passed: bool
    steps: list[Step]
```

The calc builder owns these types in `src/design/`. If a provision is not settled, the check raises `NeedsEngineerInput("D3 aspect-ratio reduction")` and the screen shows that message beside the check.

## 3. Equations

Subscript i = story. Heights H_i are elevations of level i above the base of story 1. All forms below need an engineer's check against the cited source.

### Stage A (one wall, one story) and Stage B (stack)

| ID | Equation | Citation | Status |
| --- | --- | --- | --- |
| A1 | Story shear V_i = Σ F_j for j ≥ i; unit shear v_i = V_i / b | statics | statics |
| A2 | v_allow,i = v_n,i / Ω, with v_n from the capacity table (seismic or wind column) and Ω = 2.0 | SDPWS-2021 §4.3.3, Table 4.3A | memory |
| A3 | Shear DCR = v_i / v_allow,i | definition | statics |
| A4 | Aspect ratio h_i / b ≤ 3.5 | SDPWS-2021 Table 4.3.4 | memory |
| A5 | Capacity adjustment for h/b greater than 2 | SDPWS-2021 §4.3.4 | **not entered; decision D3** |
| A6 | Overturning at the bottom of story i: M_i = Σ F_j (H_j − H_{i−1}) for j ≥ i | statics | statics |
| A7 | Resisting moment M_res,i = λ · w_i · b² / 2, where w_i = Σ (w_D,j + w_wall,j) for j ≥ i is the cumulative uniform dead load (plf) at the bottom of story i | statics for the arm; λ below | statics |
| A8 | λ for wind = 0.6; for seismic λ = 0.6 − 0.14 S_DS | ASCE 7-22 §2.4.1 combinations 8 and 9, with E_v = 0.2 S_DS D from §12.4.2.2 | memory |
| A9 | Net chord and hold-down tension T_i = max(0, (M_i − M_res,i) / d_arm) | statics; lever arm d_arm per D2; stack method per D5 | assumption |
| A10 | Hold-down DCR = T_i / T_allow,i | definition | statics |

The default lever arm for D2 is d_arm = b − d_post / 12 (ft), post-center to post-center.

### Stage C (drift)

| ID | Equation | Citation | Status |
| --- | --- | --- | --- |
| C1 | δ_sw,i = 8 v h³ / (E A b) + v h / (1000 G_a) + h Δ_a / b, in inches, with v in plf, h and b in ft, E in psi, A in in², G_a in kip/in, Δ_a in in | SDPWS-2021 Eq. 4.3-1; WoodWorks example §3.4.2 | memory |
| C2 | Seismic amplified deflection δ_x = C_d δ_se / I_e | ASCE 7-22 §12.8.6 | memory |
| C3 | Story drift Δ_i = δ_x,i − δ_x,i−1 including the rotation carried up from lower stories | WoodWorks example §3.4.3 to §3.4.5; decision D6 | assumption |
| C4 | Wind: report δ and story drift only. No code limit is applied; the owner or project sets the criterion | ASCE 7-22 Appendix C (serviceability, non-mandatory) | memory |

## 4. Decisions the engineers settle

Record each answer here with initials, then update the status of the affected rows.

- [ ] D1 ASD only for the event (assumed).
- [ ] D2 Chord lever arm: post-center to post-center, or another definition.
- [ ] D3 Aspect-ratio limit and the capacity adjustment for h/b greater than 2. Read SDPWS-2021 §4.3.4 before coding.
- [ ] D4 Which dead load counts for resisting moment (self-weight, point loads from posts) and the λ factors in A8.
- [ ] D5 Stack chord force method: from the overturning moment, or cumulative story uplift. Match the reference example §3.3.6.
- [ ] D6 Drift: load level for v in C1 (ASD or strength) and the story-drift definition.
- [ ] D7 Tolerances for comparing results with the answer key.
- [ ] D8 Confirm applied story forces are supplied at ASD level (0.7E for seismic, 0.6W for wind).

## 5. Results

Per story: v, v_allow, shear DCR, aspect-ratio check, M, M_res, T, hold-down DCR, controlling check, pass or fail, and in Stage C δ_sw and story drift. Overall: governing story and check, plus a count of steps whose status is not `verified`.

## 6. Report generator

Input: the inputs above and the list of `CheckResult`. Output: one self-contained HTML file and a Markdown copy. Use string templates so no new dependency is needed; print to PDF from the browser for the event.

Sections:

1. Header: project name, date, load type, editions, git commit of the app, prototype disclaimer ("needs review by a licensed engineer").
2. Inputs table with units.
3. Assumptions and decisions (D1 to D8 and who made them).
4. Step-by-step calculations: for each step the equation, the substituted values, the result with units, the citation and the status.
5. Summary table of DCRs and the governing check.
6. Wall or stack graphic, colored by DCR.
7. Items to verify: every step whose status is not `verified`, with its citation, so an engineer can close them out.

## 7. Tests

Answer-key cases live in `tests/`. Engineers record expected values from the reference example with printed page numbers and tolerances (D7) before the code is compared. A test failure is investigated before any new feature is added.
