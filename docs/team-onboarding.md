# Join the team with your own tools

## Common ground

GitHub holds the shared files and review history. Each member can use VS Code, another editor, a terminal coding agent, or a cloud coding workspace. Nobody needs the same AI subscription. Your coding-agent subscription authenticates your own tool; the app itself needs no model API key. A chat subscription may not include API usage or a particular coding integration. Keep credentials personal and out of the repository.

A browser chat without repository tools cannot directly edit or run this project: use it for discussion or review, then apply proposed changes through a checkout. Cloud agents with GitHub access can work in their own checkout and submit a branch or pull request. Access to one provider's cloud machine does not automatically grant access to another teammate.

## First handoff

1. Ask the repository owner for GitHub collaborator access or use a fork according to the team's preference. Read README.md, AGENTS.md, docs/proposal.md, and references/README.md.
2. Use your existing task checkout in a cloud agent. On your own computer, clone `https://github.com/scottbreneman/BigBuild-LFW-Shearwalls.git` and enter the folder. Create a branch for your task using your normal Git tool. Each cloud task is already isolated; do not create Git worktrees unless explicitly requested.
3. Install 64-bit Python 3.12 and create a virtual environment using the commands below. In VS Code, select that environment through “Python: Select Interpreter.” Other editors should select the same interpreter.
4. Tell your agent to read AGENTS.md explicitly if necessary. Agree on one small task and files with the team before asking it to implement changes. Application work begins at the event.
5. Run the generic checks. During event development, add and run checks against the chosen engineering example as well. Review the diff for assumptions, accidental files, and licensed content; open a focused pull request describing the change and verification.
6. Merge through the team's review process, then update other branches before overlapping work. Avoid simultaneous edits to the same files. Never share an active checkout among independent agents without coordinating file ownership.

## Linux cloud setup — verified target

From the repository root on Linux x86_64 with Python 3.12:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-linux-py312.lock
.venv/bin/python -m pip check
.venv/bin/python -m pytest tools/test_environment.py -q
```

The lock records all resolved package versions from the verified Linux environment. The NumPy, SciPy, pandas, Matplotlib, pytest, Streamlit, and OpenSeesPy versions selected by the team are also listed in requirements.txt.

## Windows or macOS local setup — not yet verified

Use a separate virtual environment for your platform; do not copy the cloud .venv. Use requirements.txt rather than the Linux lock because OpenSeesPy selects platform-specific dependencies. Python 3.12 is the shared target, subject to wheel availability.

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m pip check
.venv\Scripts\python -m pytest tools/test_environment.py -q
```

macOS:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
.venv/bin/python -m pytest tools/test_environment.py -q
```

These local commands are guidance, not evidence of Windows/macOS compatibility. If OpenSeesPy has no compatible wheel or cannot import on your OS/architecture, use the verified Linux x86_64 cloud environment (or WSL2 x86_64 after checking it separately). Do not spend event time trying arbitrary old versions or disabling package verification. Capture the exact error, OS, architecture, Python version, and package versions for diagnosis. Apple Silicon support must be checked; do not assume it from Python support alone.

## What to run

There is no application entry point yet. `tools/test_environment.py` checks generic tool behavior; it does not validate a wall or design standard. During the event, after the team creates an entry point, Streamlit can be started with `.venv/bin/python -m streamlit run <entrypoint.py>` (use the Windows interpreter path as appropriate). Hosted environments also need the provider's supported port exposure. Use the provider's access controls rather than publicly exposing a development server or restricted references.

## A useful first prompt for any coding agent

> Read AGENTS.md and the linked project documents. Inspect the current checkout and summarize the preparation boundary, selected standards, open engineering decisions, and available tooling. Do not implement application logic yet. Help me identify a small task and its verification, preserving teammates' changes.

When event development starts, replace the last sentence with the agreed task and acceptance criteria. Provide permitted reference links and page/section citations; do not ask the model to reconstruct unavailable standard tables from memory.

## Review and handoff

For each task, state what changed, engineering assumptions and their sources, checks actually run, and what remains undecided. The engineer confirms engineering assumptions; an assistant's confidence is not a substitute for comparison with an independent calculation. Keep a record of the event starting commit using the team's chosen Git tag or commit reference so event additions can be shown separately.
