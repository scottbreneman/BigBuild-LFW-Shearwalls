# Project instructions for coding assistants

Read README.md, docs/proposal.md, docs/team-onboarding.md, and references/README.md before work. These instructions apply regardless of editor or agent provider. If your tool does not automatically load AGENTS.md, ask it to read this file explicitly.

Before the hackathon, prepare only documentation, dependencies, generic tool verification, and empty application folders. Do not implement the shear-wall app, engineering models, formulas, or design tests until the owner explicitly starts event development.

Use IBC 2024, SDPWS 2021, NDS 2024, and ASCE 7-22. Exclude CBC. Do not invent standard provisions, table entries, stiffness assumptions, or citations. Ask the engineering owner to resolve missing engineering decisions. Keep units, force definitions, assumptions, and reference editions explicit when implementation begins.

Keep licensed/restricted documents outside the checkout. Never add credentials, restricted source excerpts, or private project data to Git or shared prompts without appropriate authorization. Read resource permissions before using documents.

Each cloud task is already isolated: use its existing checkout and do not create a Git worktree unless requested. Check git status before changes. Preserve others' work. Keep changes focused, explain the handoff, and run relevant checks. Never claim engineering validation from a generic environment smoke test.

Run tooling verification with `.venv/bin/python -m pytest tools/test_environment.py -q` on Linux/macOS or `.venv\Scripts\python -m pytest tools/test_environment.py -q` on Windows. Engineering tests belong in tests/ once event development begins. No app entry point exists yet.
