# Reference library

Place only documents with confirmed redistribution permission in `public/`. Public availability alone does not grant permission to republish a PDF. Where permission is unclear, record the publisher's public link instead. Publisher links and approved repository copies are cataloged below. The cantilever diaphragm example is included in `public/` with the project owner's confirmation of distribution permission.

Store licensed/restricted standards outside the entire Git checkout, for example in a separately managed team folder. On this cloud machine, `/workspace/shearwall-private-references/` is available for this purpose; it is not part of the repository. Cloud snapshots may retain that folder: do not upload restricted files unless environment access and snapshot storage are permitted by the license. Keep restricted materials out of commits, issue attachments, AI prompts, and screenshots unless the applicable license and sharing permissions allow that use.

## Reference catalog

| Resource | Edition/status | Location and handling |
| --- | --- | --- |
| [WoodWorks five-story light-frame wood structure over podium](https://www.woodworks.org/wp-content/uploads/design_example_Five_Story_Light-Frame_Wood_Structure_Over-Podium_10.2025.pdf) | Second edition: November 2025 (title page). Target code/standard editions confirmed in §1.2. | Publisher link plus uploaded local copy outside Git. See source notes below. |
| [WoodWorks — A Design Example of a Cantilever Wood Diaphragm](public/design_example_Cantilever_Wood_Diaphragm_07.2026.pdf) | Cover: updated May 2026; target code/standard editions confirmed in §2 | Repository PDF; owner confirmed it may be included in Git on October 26, 2026. See source notes below. |
| IBC | 2024 | Publisher reference or licensed access outside Git |
| [AWC — Special Design Provisions for Wind and Seismic (SDPWS)](https://awc.org/resources/2021-sdpws/) | 2021; target project edition | Publisher resource page supplied by the owner; link only. See source notes below. |
| [AWC — National Design Specification for Wood Construction (NDS)](https://awc.org/resources/2024-nds/) and applicable Supplement | 2024; target project edition | Publisher resource page; owner identifies free access. Page contents, Supplement access, and usage terms not yet verified. |
| ASCE 7 | 7-22 | Publisher reference or licensed access outside Git |
| Additional shear-wall worked examples | To be selected | Record source, editions, units, and redistribution status |

For each added resource, record title, author/publisher, edition/date, official URL, access date, redistribution basis, relevant pages/sections, and which proposed benchmark it supports. Record errata and supplements when applicable. Do not infer reproduction permission from an AI assistant's answer.

## Source notes: WoodWorks five-story example

- Verified title: *Five-Story Light-Frame Wood Structure Over Podium*; publisher: WoodWorks – Wood Products Council.
- Edition: **Second edition: November 2025**, as stated on the title page (PDF page 3). The filename contains `10.2025`; use the title-page edition in citations. First edition: January 2010.
- Credited development team: Bill Tremayne, Jonas Houston, Jose Machuca, Gareth Morris, Austin Perrin, Ashley Cagle, Taylor Landry, and Scott Breneman.
- Source: owner-supplied publisher link and uploaded 75-page PDF, inspected October 24, 2026. Earlier publisher-link retrieval returned HTTP 403; inspection was completed using the upload.
- Local PDF outside Git: `/workspace/library-files/woodworks/design_example_Five_Story_Light-Frame_Wood_Structure_Over-Podium_10.2025.pdf`. This cloud-local file is not automatically available in teammates' clones. The publisher link remains the shared reference.
- Confirmed reference basis: §1.2, printed page 1 / PDF page 7, lists IBC 2024, ASCE 7-22, NDS 2024 and its 2024 Supplement, and SDPWS 2021, matching the project's selected editions. Additional steel/concrete references are also listed.
- Scope: a hotel with five light-frame wood stories over a one-story concrete podium. It illustrates selected design steps, not a complete building design. Selection of a standalone wall-stack benchmark and its assumptions remains event work.
- Handling: the upload is retained outside the Git checkout. No PDF or extracted publication text is committed; redistribution permission has not been established. No separate errata review has been completed.

### Useful sections for the hackathon

Page numbers below are **printed pages**; PDF viewer page numbers are six greater (e.g., printed 26 = PDF 32).

| Section | Printed page | Intended use |
| --- | --- | --- |
| 1.2 Codes and Reference Documents | 1 | Confirm reference editions |
| 3.1.2 Flexible vs. Rigid Diaphragm Analysis | 20 | Context for building-level assumptions |
| 3.3 Shear Wall Design Example | 26 | Candidate benchmark starting point |
| 3.3.1–3.3.3 Load combinations, load path, and lateral demands | 26–28 | Trace input force definitions |
| 3.3.4 Sheathing and Nailing | 29 | Component-check reference |
| 3.3.5 Chord Members in Compression | 30 | Component-check reference |
| 3.3.6 Chord Members in Tension | 35 | Component-check reference |
| 3.4.1 Drift Load Combination and Resulting Forces | 39 | Separate drift forces from other design demands |
| 3.4.2 Shear Wall Deflection Equation | 41 | Review deformation method at the event |
| 3.4.3 Vertical Chord Deformation | 42 | Review chord and connection deformation assumptions |
| 3.4.4 Shear Wall Deflections | 48 | Candidate intermediate verification results |
| 3.4.5 Story Drift | 49 | Candidate drift verification results |

This is an index for later engineering review, not an adopted modeling method or validation of the example's calculations.

## Source notes: WoodWorks cantilever diaphragm example

- Verified title: *A Design Example of a Cantilever Wood Diaphragm*; publisher: WoodWorks – Wood Products Council.
- Developed by R. Terry Malone, PE, SE, and Scott Breneman, PhD, PE, SE, as credited on the cover.
- Cover revision: **Updated May 2026**. The uploaded filename contains `07.2026`; distinguish the cover revision from the filename. PDF metadata records July 2026 creation/modification, which does not supersede the stated cover revision.
- Source: owner-uploaded 70-page PDF, inspected October 24, 2026. An official publisher URL has not been supplied or verified; do not infer one from the upload filename.
- Repository copy: [Cantilever Wood Diaphragm PDF](public/design_example_Cantilever_Wood_Diaphragm_07.2026.pdf). Copied unchanged from the owner's upload; file identity verified with SHA-256. It will be available in teammates' clones once committed and pushed.
- Confirmed basis: §2, page 4, identifies IBC 2024, ASCE 7-22, SDPWS 2021, and NDS 2024 with its Supplement, matching the selected project editions.
- Scope: a single-story open-front structure with a double cantilever diaphragm. Particularly useful for wall stiffness, revised rigid diaphragm force distribution, diaphragm flexibility, drift, and torsional checks. It complements the five-story wall-stack example; it is not itself a five-story benchmark.
- Distribution basis: on October 26, 2026, the project owner confirmed that this is a freely distributed document and may be included in Git. The supplied PDF is preserved unchanged, including its existing credits and notices. No separate errata review has been completed.

### Useful sections for the hackathon

For the sections below, printed page numbers match the PDF viewer page numbers.

| Section | Page | Intended use |
| --- | --- | --- |
| 2 Codes and Standards Basis of Design | 4 | Confirm editions |
| 5.1–5.3 Preliminary wall stiffness, initial RDA, initial ASD design | 12–14 | Understand initial assumptions and force distribution |
| 5.4 Calculated Nominal Wall Stiffness | 16 | Review wall deformation/stiffness calculation approach |
| 5.5 Revised RDA Load Distribution from Nominal Wall Stiffnesses | 24 | Candidate extension linking stiffness back to demands |
| 5.6 Capacity Verification of Wall Design | 25 | Review resulting component capacity checks |
| 7.3 Cantilever Diaphragm Deflection Equations | 40 | Later diaphragm-analysis reference |
| 7.4 Check Assumption of Rigid Diaphragm | 41 | Review diaphragm idealization |
| 7.5 Check Story Drift | 44 | Building response and drift context |
| 7.6–7.7 Torsional irregularity and redundancy | 52–55 | Later building-analysis scope |
| 9.5 Mid-Rise Multi-Family | 66 | Context for extending beyond one story |

This index identifies topics for later review; no analysis method or engineering implementation has been adopted from the example.

## Source notes: AWC SDPWS 2021

- Publisher: American Wood Council (AWC).
- Official resource page: https://awc.org/resources/2021-sdpws/
- Link supplied by the project owner on October 24, 2026; page contents and linked files have not yet been inspected.
- Intended role: primary standard reference for WSP shear-wall provisions within the agreed SDPWS 2021 scope. Specific sections, tables, commentary, and applicable errata are to be identified during reference review.
- Handling: public publisher link only; no standard text or PDF copied into Git. Confirm access and usage terms for any downloaded material before storing or sharing it.

## Source notes: AWC NDS 2024

- Publisher: American Wood Council (AWC).
- Official resource page supplied by the owner: https://awc.org/resources/2024-nds/
- Link supplied October 24, 2026. The owner identifies this as a free-access source; page contents, specific download/viewing options, and usage terms have not yet been inspected.
- Intended role: primary reference for the project's NDS 2024 wood-member and connection checks. Confirm access to the separate applicable 2024 Supplement and any relevant errata before using design values.
- Handling: retain the publisher link; no standard text or PDF copied into Git. Free access does not itself establish redistribution permission.

## Benchmark selection at the event

Choose an example with independently available inputs and results. Document geometry, units, story loads and their definitions, material properties, connections, base restraint, and load combinations. Record the calculation method, expected intermediate values, drift definitions, and tolerances before comparing program outputs. Explain differences between the source's editions and the target standards.
