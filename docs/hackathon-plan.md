# Hackathon team plan (event day, 5 hours)

Status: draft for the team and the repository owner. Companion to [proposal.md](proposal.md) and [spec-io.md](spec-io.md). Times below are hours elapsed since kickoff.

## Goal for the day

A Streamlit app that designs and checks a stack of solid wood structural panel (WSP) shear walls for **seismic and wind** applied story loads, and a **report generator** that writes out every equation, substituted value, result and code reference behind the screen. The screen is the explorer. The report is the deliverable an engineer can check.

Editions: IBC 2024, SDPWS 2021, NDS 2024, ASCE 7-22. CBC is out of scope. ASD is assumed until the owner says otherwise.

## Scope in stages

Stop at the last stage that works end to end. Do not start a stage until the one before it passes its checks.

| Stage | What works | Target |
| --- | --- | --- |
| A | One wall at one story. Seismic or wind. Unit shear, aspect ratio, overturning, hold-down tension. Calc trace and report | by 2:30 |
| B | Five-story stack with cumulative story shear, overturning and chord/hold-down forces. Wall graphic colored by demand/capacity ratio (DCR) | by 3:15 |
| C | Story drift (SDPWS deflection equation, then story drift). Only if A and B pass their answer-key checks | stretch |

Out of scope: openings and perforated walls, building-wide rigid diaphragm distribution, LRFD, OpenSeesPy modeling. OpenSeesPy stays a candidate for a later cross-check.

## Transparency rule: source status

The team decided on event day that equations and factors may come from memory (an engineer's or Claude's) so the build is not blocked. Every one must be visible. Each equation, factor and table value carries one status, and the report prints it beside the value:

| Status | Meaning |
| --- | --- |
| `statics` | Plain mechanics, no code provision involved |
| `verified` | Checked by an engineer against the named source page; checker named in the data or spec |
| `memory` | Recalled, not yet checked against the source. Allowed in the build, always shown, always listed in the report's "Items to verify" appendix |
| `assumption` | A team decision, written down with who made it |

Claude does not supply SDPWS table values from memory because it cannot recall them reliably. An engineer enters them from the SDPWS table or the reference example and marks them `verified` or `memory`. Where a provision's form is uncertain, the code raises a clear "needs engineer input" error instead of guessing.

`AGENTS.md` says not to invent provisions or table entries. This rule is the team's way of staying transparent while moving fast, and it needs the repository owner's confirmation.

## Roles and file ownership

One owner per area keeps eight people from editing the same files.

| Role | People | Owns |
| --- | --- | --- |
| Lead | 1 | Merges pull requests, resolves disagreements, keeps `main` working, tags the event starting commit |
| Engineering | 2 | `docs/spec-io.md` equations and decisions; expected values for tests. One writes, the other checks independently |
| Data | 1 | Table data files under `src/design/` with source, page and status on every row |
| Calc builder | 1 | `src/analysis/` and `src/design/` (checks return calc-trace steps) |
| UI builder | 1 | `src/ui/` (Streamlit inputs, results, wall/stack graphic) |
| Report builder | 1 | `src/report/` (new folder; owner to confirm) |
| Pitch | 1 | Demo script, slides, README additions, submission |

## Timeline

| Time | Goal |
| --- | --- |
| 0:00-0:30 | Agree the input/output list and the calc-trace contract in `spec-io.md`. Everyone runs the environment check. UI and report builders start on sample data |
| 0:30-2:30 | Parallel build: data entry, Stage A checks, Streamlit form, report skeleton. First pull requests merged by 1:30 |
| 2:30-3:15 | Integrate. Run the answer-key cases. Any mismatch with the engineers' expected values is fixed before new features. Stage B |
| 3:15-4:00 | Polish: input validation, graphic, report layout, prototype disclaimer. Stage C only if ahead |
| 4:00 | Feature freeze. Bug fixes only |
| 4:00-5:00 | Rehearse the demo twice, finish slides, submit with 15 minutes to spare |

## Answer key

The five-story WoodWorks example in `references/public/` is the candidate benchmark (printed pages: §3.3 shear wall design, p. 26; §3.4 drift, p. 39). Engineers record the expected intermediate values with page numbers and tolerances before the code is compared to them. Differences in editions are recorded, not hidden. The team still confirms this choice.

## Working rules

1. Read `AGENTS.md`, `README.md` and `docs/spec-io.md` first. Claude Code does not load `AGENTS.md` by itself, so tell it to read the file.
2. Work on a branch, open small pull requests, and merge often. Check `git status` before starting.
3. Ask for one small change at a time and check results against hand values after each change.
4. Run `.venv/bin/python -m pytest tools/test_environment.py -q` (Windows: `.venv\Scripts\python`). That test checks tooling only, not engineering.
5. A good-looking result is not a correct result. Engineers confirm numbers.
6. Nobody is stuck for more than 15 minutes without asking.

## Demo (3 minutes)

1. The problem: shear-wall stacks are checked by hand and spreadsheets, and the assumptions are hard to trace.
2. Enter story loads, pick seismic or wind, and see DCRs, the controlling check and hold-down forces on the wall graphic.
3. Change the nailing and watch a failing wall turn passing.
4. Open the generated report: every equation, value, citation and source status, plus the "Items to verify" list.
5. Close with the limits (prototype, needs engineering review) and what is next.
