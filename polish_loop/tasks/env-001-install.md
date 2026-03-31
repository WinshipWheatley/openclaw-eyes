
title: env-001-install
goal: Complete required environment installs and verification on both PC and Mac so env-001 can move past audit-only.
scope:
- Run on each machine:
  - `python3 -m pip install --user uv reportlab openai-whisper`
- Verify on each machine:
  - `python3 -m pip show uv reportlab openai-whisper`
  - `gh --version`
  - `sqlite3 --version`
  - `mkdir -p ~/Eyes/skills && ls -ld ~/Eyes/skills`
success condition:
- `uv`, `reportlab`, and `openai-whisper` are installed on PC and Mac.
- `gh` and `sqlite3` version checks pass on PC and Mac.
- `~/Eyes/skills` exists on PC and Mac.
blockers/dependencies:
- Approval-gated package installation in autonomous context.
- Mac-side execution/access for Mac machine changes.
- `python3` + `pip` availability on both machines.