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
| Risk category | | I to IV | Seismic drift limit; only I and II (0.020 h_sx) are entered |
| Seismic design category | SDC | A to F | 3x framing detailing flag (SDPWS §4.3.7.1 item 5) |
| Wind drift limit | r_w | unitless ratio | Wind only. Allowable story drift / story height, e.g. 1/400. User supplied (decision D6) |
| Net roof uplift on the wall | w_up | plf | Wind only, strength level; adds w_up b²/2 to overturning (example §4.5.2) |
| Deflection method | | 3-term / 4-term | Stage C. 3-term SDPWS Eq. 4.3-1 (default) or 4-term Commentary Eq. C4.3.4-1 |
| Framing moisture | | dry / green | 4-term only; selects the nail slip equation |
| Rotation carried up | | yes / no | Stage C, default no. Adds the rotation of the stories below (decision D6) |
| Tie-down restraint at every level | | yes / no | Stage C, default yes. No: chord deformation accumulates up the building (example Table 3.17B) |

### Wall (same for every story in the stack)

| Name | Symbol | Unit | Notes |
| --- | --- | --- | --- |
| Wall length | b | ft | Solid wall, no openings |
| End post width | d_post | in | For the chord lever arm (decision D2) |

### Per story i (1 = bottom)

| Name | Symbol | Unit | Notes |
| --- | --- | --- | --- |
| Story height | h_i | ft | Floor-to-floor wall height |
| Applied lateral force at level i | F_i | lb | **Strength level** (E_h or W). The engine applies 0.7E_h / 0.6W and the drift combinations (decision D8) |
| Dead load on the wall at level i | w_D,i | plf | Uniform along the wall, excluding wall self-weight |
| Live and roof live load at level i | w_L,i, w_Lr,i | plf | For chord compression combinations |
| Chord posts | n, size, species, grade | | Compression posts at each wall end; chord length L_c (ft) and lever arm d (ft) |
| Chord geometry | layout | given / example | given: L_c and d entered. example: from the post count by the layout rule A16 (post thickness along the wall, 3 posts outboard, 6 in. rod gap) |
| Preferred materials | | preset JSON | Down-selection used by the UI dropdowns and auto-size (preferred assemblies + sides + panel type, lumber + post sizes + post-count range, rods, hold-downs). Saved with the project |
| Tie-down | | | Generic hold-down (model or T_allow, Δ_a) or continuous rod (rod id, bearing plate W × L × t, F_y, slack, take-up elongation) |
| Wall self-weight | w_wall,i | plf | Optional |
| Nailing selection | | table row id | One row of the capacity table: panel grade, thickness, nail, edge spacing |
| Sheathing sides | | 1 or 2 | Combination rule for two sides is an engineer decision |
| Hold-down allowable tension | T_allow,i | lb | From the product evaluation report; user input |
| Chord modulus and area | E, A | psi, in² | Stage C only |
| Anchorage slip at the hold-down | Δ_a,i | in | Stage C only; from the product data |
| Take-up device present | | yes / no | Rod systems, default yes. No: slack and device elongation drop out and shrinkage is counted |
| Story shrinkage | Δ_sh,i | in | Rod systems without a take-up device (example §2.3, Table 2.1) |

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
    id: str              # "S2.shear"
    name: str            # "Sheathing shear, story 2"
    story: int
    category: str        # shear | detailing | aspect | compression | holddown | rod | plate_bearing | plate_bending | drift
    status: CheckStatus  # pass | fail | needs_input | info | not_applicable
    demand: float | None
    capacity: float | None
    dcr: float | None
    demand_unit: str
    capacity_unit: str
    message: str         # e.g. the needs-input text
    decision: str        # decision id when status is needs_input ("D3", "component data")
    steps: tuple[Step, ...]
    # properties: passed, worst_source
```

The calc builder owns these types in `src/design/trace.py`; the engine entry point is `design.engine.run_design(inputs) -> DesignResult` (see [design-engine.md](design-engine.md)). If a provision is not settled, the check raises `NeedsEngineerInput("D3 aspect-ratio reduction")` and the screen shows that message beside the check.

## 3. Equations

Subscript i = story. Heights H_i are elevations of level i above the base of story 1. All forms below need an engineer's check against the cited source.

### Stage A (one wall, one story) and Stage B (stack)

| ID | Equation | Citation | Status |
| --- | --- | --- | --- |
| A1 | Story shear V_i = Σ F_j for j ≥ i; unit shear v_i = V_i / b | statics | statics |
| A2 | v_allow,i = n_sides · v_n,i / Ω, with v_n from the capacity table; Ω = 2.8 seismic, 2.0 wind; two sides double the capacity when both sides match | SDPWS-2021 §4.1.4.1, §4.1.4.2, §4.3.5.4.1, Table 4.3A; example §3.3.4, §4.2 | memory |
| A3 | Shear DCR = v_i / v_allow,i | definition | statics |
| A4 | Aspect ratio h_i / b ≤ 2.0 with no adjustment; above 2.0 the check returns needs-input (D3) | SDPWS-2021 §4.3.3; example §3.3 | memory |
| A5 | Capacity adjustment for h/b greater than 2 | SDPWS-2021 §4.3.4 | **not entered; decision D3** |
| A6 | Overturning at the bottom of story i: M_i = Σ F_j (H_j − H_{i−1}) for j ≥ i | statics | statics |
| A7 | Resisting moment M_res,i = λ · w_i · b² / 2, where w_i = Σ (w_D,j + w_wall,j) for j ≥ i is the cumulative uniform dead load (plf) at the bottom of story i | statics for the arm; λ below | statics |
| A8 | Tension: seismic 0.6 − 0.14 S_DS (combo 10, with 0.7E_h); wind 0.6 (combo 7a, with 0.6W) | ASCE 7-22 §2.4.5 combo 10, §2.4.1 combo 7a, E_v = 0.2 S_DS D per §12.4.2.2; example §3.3.6, §4.5 | memory |
| A9 | Net chord and hold-down tension T_i = max(0, (M_i − M_res,i) / d_arm) | statics; lever arm d_arm per D2; stack method per D5 | assumption |
| A10 | Hold-down DCR = T_i / T_allow,i (rod system: T_i vs rod allowable from the component library) | definition | statics |
| A11 | Chord compression C = max of seismic combos 8: (1 + 0.14 S_DS) P_D + 0.7 C_E and 9: (1 + 0.105 S_DS) P_D + 0.525 C_E + 0.75 P_L; wind 5a: P_D + 0.6 C_W and 6a: P_D + 0.75 P_L + 0.45 C_W + 0.75 P_Lr; P_D = w_D L_c; C_E = M_OT / d | ASCE 7-22 §2.4.5, §2.4.1; example §3.3.5, Table 3.8 | memory |
| A12 | Post capacity P_allow = min(F'_c, F'_c⊥) n A_post; F'_c = F_c C_D C_M C_t C_F C_i C_P, C_D = 1.6, l_e = h − plates, out-of-plane axis | NDS-2024 §3.6, §3.7.1 Eq. 3.7-1, §3.10; example §3.3.5, Table 3.9 | memory |
| A13 | Bearing plate: ΔT_i ≤ F_c⊥ C_b (W L − π (d_rod + 3/16)² / 4), C_b = (l_b + 0.375) / l_b | NDS-2024 §3.10.4; example §3.3.6, Table 3.12 | memory |
| A14 | Plate bending: f W (L/2)² / 2 ≤ F_y (W − d_rod − 1/16) t² / 4 / 1.67 | AISC 360-22 Eq. F11-1; example §3.3.6 | memory |
| A16 | Layout rule: X_t = n_out t + g/2; X_c = centroid of n posts (n_out outboard, the rest inboard after the gap g); L_c = (n t + g)/12; d = b − (X_t + X_c)/12, defaults n_out = 3, g = 6 in. | statics; example Figs. 3.7–3.8, Tables 3.6 and 3.8 (reproduced); SEB post types N1–N5 | assumption |
| A17 | Auto-size: for each story, the lightest preferred option (capacity ascending) that passes, in order: sheathing shear (assembly × sides), chord compression (lumber × post size × count with A16), tension (rod or hold-down). Drift is reported, not driven. Proposed, then applied by the engineer | owner decision 2026-10-27 | assumption |
| A15 | Differential tension per floor ΔT_i = max(0, T_i − T_i+1) | statics; example Table 3.10 | statics |

The default lever arm for D2 is d_arm = b − d_post / 12 (ft), post-center to post-center.

### Stage C (drift)

| ID | Equation | Citation | Status |
| --- | --- | --- | --- |
| C1 | δ_sw,i = 8 v h³ / (E A b) + v h / (1000 G_a) + h Δ_a / b, in inches, with v in plf, h and b in ft, E in psi, A in in², G_a in kip/in, Δ_a in in. Rod systems: Δ_a = (rod elongation + crushing + bearing-plate crushing + slack + take-up) b / d | SDPWS-2021 Eq. 4.3-1; WoodWorks example §3.4.2-3.4.3, Fig. 3.10 | memory |
| C2 | Seismic amplified deflection δ_x = C_d δ_se / I_e | ASCE 7-22 §12.8.6 | memory |
| C3 | Story drift: each story analysed floor to floor, δ_sw,i used as the elastic story drift; seismic Δ_i = C_d δ_sw,i / I_e ≤ 0.020 h_sx (Risk Category I, II). Rotation carried up from lower stories is not applied (option returns needs-input) | WoodWorks example §3.4.4-3.4.5; ASCE 7-22 Table 12.12-1; decision D6 | assumption |
| C1a | 4-term option: δ_sw,i = 8 v h³ / (E A b) + v h / (n G_v t_v) + 0.75 h e_n + h Δ_a / b, with e_n = k (V_n / den)^exp, V_n = (v / n) s / 12 per nail per side, k = 1.2 when panels are not Structural I. G_v t_v and the slip constants come from the component library | SDPWS-2021 Commentary Eq. C4.3.4-1, Tables C4.2.2A/B/D; example §3.4.2 | memory |
| C5 | No take-up device: Δ_a includes the story shrinkage Δ_sh and drops slack and take-up elongation | example §3.4.3, Table 3.17B | assumption |
| C6 | No tie-down restraint at every level: Δ_a,i = Σ Δ_a,k for k ≤ i is used in the anchorage term | example Table 3.17B (cumulative column) | assumption |
| C7 | Rotation carried up: θ_k = Δ_a,k / (12 b) + 1.5 δ_b,k / (12 h_k); Δ_below,i = 12 h_i Σ θ_k for k < i; the story drift uses δ_sw,i + Δ_below,i. Not combined with C6 | statics, rigid-body geometry; decision D6 | assumption |
| C4 | Wind: δ_sw,i at v = 1.0W/b, chord tension 0.6D + 1.0W, no C_d or I_e; check δ_sw,i ≤ r_w h_i with the user-supplied wind drift limit r_w. Without r_w the check returns needs-input | ASCE 7-22 Appendix C commentary (non-mandatory); example §4.6; decision D6 | assumption |

## 4. Decisions the engineers settle

Record each answer here with initials, then update the status of the affected rows.

- [ ] D1 ASD only for the event (assumed).
- [ ] D2 Chord lever arm: post-center to post-center, or another definition.
- [ ] D3 Aspect-ratio limit and the capacity adjustment for h/b greater than 2. Read SDPWS-2021 §4.3.4 before coding.
- [ ] D4 Which dead load counts for resisting moment (self-weight, point loads from posts) and the λ factors in A8.
- [ ] D5 Stack chord force method: from the overturning moment, or cumulative story uplift. Match the reference example §3.3.6.
- [ ] D6 Drift: load level for v in C1 (ASD or strength) and the story-drift definition. Seismic follows the example (strength level, floor to floor). **Wind (owner, 2026-10-27): check against a user-provided drift limit; forces 1.0W and 0.6D + 1.0W.** **Rotation carried up (owner, 2026-10-27): optional, by rigid-body geometry (C7), not the SEB spreadsheet's d / H form.** 4-term deflection, no-take-up shrinkage and cumulative chord deformation are options (C1a, C5, C6); the default stays the example's 3-term floor-to-floor method.
- [ ] D7 Tolerances for comparing results with the answer key.
- [x] D8 Applied story forces are supplied at **strength level**; the engine applies 0.7E_h / 0.6W and the drift combinations (owner, 2026-10-27; matches example Tables 3.4 and 4.4).

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
