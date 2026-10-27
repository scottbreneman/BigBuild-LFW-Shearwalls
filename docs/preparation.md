# Preparation record

## Boundary

Prepared for the NCSEA Big Build Hackathon: documentation, empty application folders, Python packages, and generic environment tests. No shear-wall application code, design formulas, structural idealization, or engineering benchmark tests have been written. README and proposal are drafts for the owner to refine.

## Verified environment

Linux x86_64, Python 3.12.14. Exact resolved packages are in requirements-linux-py312.lock; direct selections are in requirements.txt. All seven requested packages are installed in .venv. No external service, model API key, or proprietary credential is needed for these generic checks.

- `python -m pip check`: no broken requirements.
- `python -m pytest tools/test_environment.py -q`: four tests passed.
- OpenSeesPy 3.8.0.0 / engine 3.8.0: generic linear elastic cantilever displacement was -0.005625, matching the independent P L^3 / (3 E I) result, with the support reaction also checked.
- NumPy/SciPy: solved and verified a small linear system; pandas: CSV round trip preserved results.
- Matplotlib: generated a PNG with a headless backend.
- Streamlit: its AppTest runner executed a generic input/output snippet and verified a changed input updates the displayed result. This checks framework execution, not browser connectivity or deployment.
- Reapplying the install script with the pinned Linux package list succeeded and reran the same four checks.

These checks establish tooling behavior only. They do not validate wood engineering methods, nonlinear model behavior, drift calculations, or compliance with any standard. Other operating systems and architectures have not been tested. No user-facing app or server is running.

## Still for the owner/team

Supply reference links/documents and confirm redistribution permissions. Select the benchmark and modeling/checking approach during the event. Confirm per-person GitHub and coding-agent access. Review the proposal and establish the event starting commit. The preparation files and owner-approved cantilever diaphragm PDF were committed and pushed to GitHub. The five-story podium PDF was subsequently approved by the owner and added to references/public/.

The cloud configuration draft records reinstall and future startup guidance. Saving it is separate from publishing an environment snapshot. Fresh-task restoration has not been independently tested. The preparation commit was pushed to GitHub main; subsequent reference additions are recorded in Git history.
