# Design engine

`src/design/engine.py` turns a `DesignInputs` into a `DesignResult`. The UI and the report both render that result; neither recomputes anything. Inputs, equations and decisions are in [spec-io.md](spec-io.md). Component data comes from the [component library](component-library.md).

```python
from design.engine import run_design
from design.inputs import DesignInputs, StoryInput, ChordSpec, RodSystem, GenericHoldDown

result = run_design(inputs)            # optional 2nd arg: a ComponentLibrary (tests pass a fixture library)
result.status                          # pass | fail | incomplete | invalid_input
result.input_errors                    # show these and nothing else when status is invalid_input
for story in result.stories:           # bottom to top
    story.max_dcr, story.governing_id, story.status
    for check in story.checks:         # CheckResult: id, name, category, status, demand, capacity, dcr, units, message
        check.steps                    # Step: equation_latex, substitution, value, unit, citation, status
result.governing_story, result.governing_check, result.max_dcr
result.needs_input                     # (check_id, decision, message): show beside the check
result.unverified_steps                # report appendix "Items to verify" (status memory or assumption)
result.component_items_to_verify       # library rows still at status memory
result.to_dict()                       # JSON-safe, for st.session_state or the report
```

## Checks per story

| id | Category | Demand vs capacity | Example reference |
| --- | --- | --- | --- |
| `S{i}.shear` | shear | v (plf) vs n·v_n/Ω | §3.3.4, Table 3.5 |
| `S{i}.framing` | detailing | INFO: 3x framing flag | §3.3.4 |
| `S{i}.aspect` | aspect | h/b vs 2.0 (needs-input D3 above 2.0) | §3.3 |
| `S{i}.comp` | compression | chord compression (lb) vs post capacity | §3.3.5, Tables 3.8-3.9 |
| `S{i}.holddown` | holddown | T vs T_allow (generic hold-down only) | spec-io A10 |
| `S{i}.rod` | rod | T vs rod allowable (rod system only) | Table 3.11 |
| `S{i}.plate_brg` | plate_bearing | ΔT vs bearing capacity | Table 3.12 |
| `S{i}.plate_bend` | plate_bending | plate moment vs F_y Z / 1.67 | §3.3.6 |
| `S{i}.drift` | drift | seismic C_d δ_sw / I_e vs 0.020 h_sx; wind δ_sw vs user limit | §3.4, Tables 3.13-3.19 |

The DCR is demand / capacity. PASS means DCR ≤ 1.0. Colour bands belong to the UI. A check that cannot run returns `needs_input` with a `decision` (`D3`, `D6`, `C_F`, `component data`). The rest of the stack still runs. Stack-level steps (load combinations, statics, chord forces) are in `result.stack_steps`. Every check also copies the steps it depends on, so each check's expander is self-contained.

## Status of the numbers

- Code-provision steps are `memory`: transcribed from the WoodWorks example and not yet checked by an engineer against the standard.
- Team decisions are `assumption`.
- Component values carry their library row's status.
- Production library rows are all `pending` today, so a real run returns `incomplete` until the engineers fill the tables.

The answer-key test ([tests/test_woodworks_seismic.py](../tests/test_woodworks_seismic.py)) uses a test-only component set transcribed from the example ([tests/fixtures/woodworks_components/](../tests/fixtures/woodworks_components/)). It reproduces example Tables 3.5 to 3.19 within a provisional tolerance (D7). That is a regression benchmark, not engineering validation.

## Not yet covered

- Wind answer key (example Tables 4.4-4.9).
- Chord tension in wood posts for the generic hold-down path.
- NDS slenderness limit and C_T.
- Live load reduction.
- Rotation carried up between stories (D6).
- Size factors other than DF-L No.1 2x4 (`design/factors.py`).
- Drift limits for Risk Categories III and IV.
