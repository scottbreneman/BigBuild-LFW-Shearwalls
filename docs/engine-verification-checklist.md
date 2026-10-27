# Engine verification checklist

Status: open. Companion to the decisions list in [spec-io.md](spec-io.md) §4.

The component tables (`src/design/components/data/`) are verified. What remains `memory` in the app are the **factors and equations in the engine**, all taken from the WoodWorks five-story example, which cites the sections below. None has been checked against the standard itself. Every one prints as `memory` in the report's "Items to verify" appendix until an engineer checks it.

How to close an item: open the cited section, confirm the value or the form of the equation, then tick the box and add initials and date. The calc builder flips the status in `src/design/factors.py` (or the `Tracer.step(...)` call in the check) from `"memory"` to `"verified"`. If the standard disagrees with the example, record the difference here rather than silently changing the number.

Grouped by book so each one is opened once.

## SDPWS 2021

| Done | Item | Value in engine | Cited section | Used in |
| --- | --- | --- | --- | --- |
| [ ] | ASD reduction factor, seismic, Ω | 2.8 | §4.1.4.1 | `factors.OMEGA_SEISMIC` → shear check |
| [ ] | ASD reduction factor, wind, Ω | 2.0 | §4.1.4.2 | `factors.OMEGA_WIND` → shear check |
| [ ] | Two-sided wall multiplier (same sheathing and nailing both faces) | 2.0 | §4.3.5.4.1 | `factors.TWO_SIDED_MULTIPLIER` |
| [ ] | Aspect ratio with no capacity reduction, h/b ≤ | 2.0 | §4.3.3 (see also decision D3, §4.3.4) | `factors.ASPECT_RATIO_NO_REDUCTION`, `check_aspect` |
| [ ] | 3x framing trigger: nominal unit shear > | 980 plf (SDC D–F) | §4.3.7.1 item 5 | `factors.FRAMING_3X_NOMINAL_PLF`, `check_framing_3x` |
| [ ] | 3x framing trigger: 10d common at edge spacing ≤ | 3 in. | §4.3.7.1 item 5 | `factors.FRAMING_3X_10D_SPACING_IN` |
| [ ] | Deflection equation form: δ = 8vh³/(EAb) + vh/(1000 G_a) + hΔ_a/b | — | Eq. 4.3-1 | `checks/drift.py` |

## NDS 2024 (and Supplement)

| Done | Item | Value in engine | Cited section | Used in |
| --- | --- | --- | --- | --- |
| [ ] | Load duration factor C_D, wind/seismic | 1.6 | Table 2.3.2 | `factors.C_D_LATERAL` → compression, bearing |
| [ ] | Wet service C_M, dry | 1.0 | §4.3.3 | `factors.C_M` |
| [ ] | Temperature C_t | 1.0 | §2.3.3 | `factors.C_t` |
| [ ] | Incising C_i, not incised | 1.0 | §4.3.8 | `factors.C_i` |
| [ ] | Buckling length coefficient K_e, pinned-pinned | 1.0 | Appendix G | `factors.K_e` |
| [ ] | Column parameter c, sawn lumber | 0.8 | §3.7.1 | `factors.C_SAWN` |
| [ ] | Critical buckling F_cE = 0.822 E'_min / (l_e/d)² | 0.822 | §3.7.1 | `checks/compression.py` |
| [ ] | Column stability factor C_P equation | — | Eq. 3.7-1 | `checks/compression.py` |
| [ ] | Applicability table for adjustment factors (which factors apply to F_c, F_c⊥, E_min) | — | Table 4.3.1 | `checks/compression.py`, `checks/tiedown.py` |
| [ ] | Size factor C_F(F_c), DF-L No.1 2x4 | 1.15 | Supplement Table 4A adjustment factors | `factors._SIZE_FACTOR_FC` (now also in `size_factors.csv`, verified) |
| [ ] | Bearing area factor C_b = (l_b + 0.375)/l_b for l_b < 6 in.; 1.0 otherwise | — | §3.10.4 | `checks/tiedown.py` |
| [ ] | Compression ⊥ at 0.02 in. deformation: F_c⊥0.02 = 0.73 F_c⊥ | 0.73 | §4.2.6 | `factors.FC_PERP_002_RATIO` → drift |
| [ ] | Column and bearing checks (post compression; plate bearing) | — | §3.6, §3.10 | `checks/compression.py` |

## ASCE 7-22

| Done | Item | Value in engine | Cited section | Used in |
| --- | --- | --- | --- | --- |
| [ ] | ASD seismic combination factor on E_h | 0.7 | §2.4.5 | `combos.py` |
| [ ] | Combination 8 dead-load factor 1.0 + 0.7(0.2 S_DS) | 1.0 + 0.14 S_DS | §2.4.5 comb. 8; E_v per §12.4.2.2 | `combos.py` → compression |
| [ ] | Combination 9 dead-load factor 1.0 + 0.525(0.2 S_DS) | 1.0 + 0.105 S_DS | §2.4.5 comb. 9 | `combos.py` |
| [ ] | Combination 10 dead-load factor 0.6 − 0.7(0.2 S_DS) | 0.6 − 0.14 S_DS | §2.4.5 comb. 10 | `combos.py` → tension/hold-down |
| [ ] | ASD wind factor on W; combinations 5a/6a/7a (0.6D + 0.6W) | 0.6 | §2.4.1 | `combos.py` |
| [ ] | Drift forces: strength-level E_h, no 0.7 | — | §12.8.6.1 | `combos.py` → drift |
| [ ] | Amplified deflection δ_x = C_d δ_xe / I_e | — | Eq. 12.8-16 | `checks/drift.py` |
| [ ] | Allowable story drift, Risk Category I/II, light-frame walls | 0.020 h_sx | Table 12.12-1 | `factors.DRIFT_LIMIT_RC_I_II` |

## AISC

| Done | Item | Value in engine | Cited section | Used in |
| --- | --- | --- | --- | --- |
| [ ] | Steel plate hole oversize for bending check | 1/16 in. | Steel Manual Table J3.3 (engine cites 16th ed.; team copy is 14th — confirm the table is the same) | `factors.STEEL_PLATE_HOLE_OVERSIZE_IN` |
| [ ] | Flexure safety factor Ω_b for the bearing plate | 1.67 | AISC 360-22 Ch. F, Eq. F11-1 | `factors.OMEGA_STEEL_FLEXURE` |
| [ ] | Steel modulus E | 29,000,000 psi | AISC 360-22 | `factors.E_STEEL_PSI` |
| [ ] | Rod tension: F_nt = 0.75 F_u, Ω = 2.00 | — | AISC 360 Eq. J3-1, Table J3.2 | applied in `continuous_rod_systems.csv` (verified) |

## APA / example-only

| Done | Item | Value in engine | Cited source | Used in |
| --- | --- | --- | --- | --- |
| [ ] | Sheathing bearing at 0.02 in. and 0.04 in. deformation | 210 psi, 360 psi | APA Panel Design Specification (2020), via example §3.4.3 | `factors.SHEATHING_FC_002_PSI`, `_004_PSI` → drift |
| [ ] | Bearing-plate hole in wood plate | rod dia + 3/16 in. | example §3.3.6 (assumption) | `factors.BEARING_AREA_HOLE_OVERSIZE_IN` |
| [ ] | 45° bearing spread through plates | 6 in. | example §3.4.3, Table 3.14 (assumption) | `factors.SHEATHING_SPREAD_IN` |
| [ ] | Take-up device slack and elongation | 1/32 in., 0.03 in. | example Table 3.17A (manufacturer value) | drift inputs |

## Record of changes

| Date | Item | Finding | Initials |
| --- | --- | --- | --- |
| | | | |
