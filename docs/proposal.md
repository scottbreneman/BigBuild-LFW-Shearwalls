# Proposal: Make the shear-wall spreadsheet explain itself

## The opportunity

Designers working on multi-story multifamily buildings often have limited wall length and many interacting design choices. Hand calculations and spreadsheets help check wood structural panel (WSP) shear walls, but tracing assumptions through a full stack can be cumbersome. A transparent, interactive calculation workflow could make these decisions easier to understand and review.

## Hackathon goal

Build a Python prototype for one five-story stack of vertically aligned, solid shear walls without openings. Starting with applied seismic loads, aim to show component-by-component verification and calculated story drift, with visible inputs, units, assumptions, intermediate results, and reference citations.

The intended components include sheathing, boundary studs/posts in compression and tension, hold-downs or continuous tie-downs, and associated stack connections. The exact checks and deformation model will be selected by the team from the references during the event. OpenSeesPy is available as a candidate analysis engine; it does not provide the wood design provisions automatically.

## Engineering basis and first demonstration

Use IBC 2024, SDPWS 2021, NDS 2024, and ASCE 7-22; exclude CBC. Select a worked reference example, reconcile its editions and assumptions with this basis, and reproduce a traceable set of component and deformation results. Differences in editions must be recorded rather than silently treated as equivalent.

For the initial demonstration, use applied story loads as inputs; complete building rigid diaphragm analysis is a possible extension. The team will decide the wall idealization, load conventions, boundary conditions, drift treatment, component checks, and acceptance tolerances at the event.

## If time permits

Explore changes in design assumptions and their consequences. Longer-term possibilities include comparing wall configurations and coupling stack stiffness to building-wide rigid diaphragm force distribution. These extensions are ideas, not promises for the first demonstration.

## Team and preparation

We welcome wood design knowledge, structural analysis, Python, interface design, testing, and AI-assisted coding skills. Beginners can contribute by checking references, documenting assumptions, and comparing outputs with worked calculations. Members may use different editors and coding assistants; GitHub branches and pull requests provide the common handoff.

Advance preparation consists of dependencies, empty folders, reference organization, generic tool checks, and onboarding instructions. Application development and engineering models begin at the hackathon. Success means an understandable, demonstrable, checked prototype with clearly stated limits; readiness for professional design use requires further validation and engineering review.
