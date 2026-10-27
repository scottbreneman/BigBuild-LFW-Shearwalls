# BigBuild: Light Frame Wood Shear Walls

**Help build an explainable wood shear-wall design tool at the NCSEA Big Build Hackathon.**

Engineering designers of multi-story multifamily buildings often work through shear-wall stacks using hand calculations and spreadsheets. We want to explore a Python app that makes those calculations visible, checks individual components, and shows how design assumptions affect the results.

Our first target is one five-story stack of solid wood structural panel (WSP) shear walls without openings, with applied seismic story loads, component checks, and story drift results. References: IBC 2024, SDPWS 2021, NDS 2024, and ASCE 7-22. CBC is outside this project's scope.

Bring wood design experience, Python or structural analysis skills, UI ideas, or curiosity about directing AI coding tools. Different editors and coding-agent subscriptions are welcome: GitHub, readable documentation, and repeatable checks are our shared workspace.

**Status: the hackathon is underway.** Event development has started; engineering methods, application code, and the demonstration are being built now. Pre-event preparation (tooling, references, onboarding) is recorded in [docs/preparation.md](docs/preparation.md). OpenSeesPy is an installed candidate engine, not a settled wall-modeling method.

- [One-page proposal](docs/proposal.md)
- [Join the team and set up your tools](docs/team-onboarding.md)
- [Resource catalog and document handling](references/README.md)
- [Preparation and verification record](docs/preparation.md)

## Layout

| Location | Intended use during the hackathon |
| --- | --- |
| `src/analysis/` | Structural model and response calculations |
| `src/design/` | Component checks and reported calculation steps |
| `src/ui/` | User interface; Streamlit is available |
| `tests/` | Engineering benchmarks and regression tests |
| `references/public/` | Documents with confirmed redistribution permission |
| `tools/` | Generic environment verification, independent of the app |

Application and engineering work is in progress. Prototype results will need validation against selected references and engineering review before project use.
