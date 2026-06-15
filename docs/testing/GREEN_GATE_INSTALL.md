# Green Gate Install

The green gate is the local full-suite safety check for pushes and merge candidates. It must run on a fresh clean checkout of the exact ref being validated, not in a stateful development worktree.

## Install

From the repository root on local WSL disk:

```bash
ln -sf ../../scripts/pre-push.hook .git/hooks/pre-push
chmod +x scripts/green_gate.sh .git/hooks/pre-push
```

The hook only gates pushes to `refs/heads/main`. Branch pushes are allowed, but integration must still run the gate on the branch result before promotion.

## Required Environment

- Run from local ext4 only: `/tmp/...` or `/home/openclaw/...`; the script rejects other roots.
- Never run Git worktrees or the clean-room checkout under `/mnt/e` or `/mnt/c`; those mounts have wedged Git and pytest.
- Use the validated Python: `OPENCLAW_VENV=/home/openclaw/.venv/bin/python`.
- The venv must import both `pytest` and `pytest_timeout`.
- Keep the tracked generated fixtures that made the clean checkout green, including the Mac/read-model and proof-to-response status fixtures checked by `scripts/green_gate.sh`.

## Manual Run

```bash
OPENCLAW_REPO=/home/openclaw \
OPENCLAW_VENV=/home/openclaw/.venv/bin/python \
scripts/green_gate.sh HEAD
```

Optional knobs:

```bash
OPENCLAW_GREEN_GATE_WORKTREE_ROOT=/tmp/openclaw-green-gate
OPENCLAW_PYTEST_TIMEOUT_SECONDS=90
OPENCLAW_PYTEST_TIMEOUT_METHOD=thread
```

The script rejects `/mnt/e` and `/mnt/c`, requires local ext4, verifies `pytest-timeout`, checks required clean-checkout fixtures, then runs:

```bash
OPENCLAW_TEST_MODE=1 OPENCLAW_SEND_HOLD=1 python -m pytest -q -rA --timeout=90 --timeout-method=thread
```

A hanging test should now fail loudly with a named pytest timeout instead of wedging the full gate.
