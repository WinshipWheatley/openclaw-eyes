#!/usr/bin/env python3
"""Generate the orchestration-progress read-model from real shipped milestones.

Answers "where are we at" for agent packets. Source of truth = git history on the
current branch (feat/fix/chore/perf/refactor commits = shipped milestones). Pure,
deterministic, refreshable, NO confabulation: the packet carries only what actually
shipped; the agent's brain renders it in-voice. This is "Change 4 done right" --
orchestration milestones, not raw control-plane worker tasks.

Run: python3 scripts/export_orchestration_progress_read_model.py
Output: generated/read_models/orchestration_progress.json
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "generated" / "read_models" / "orchestration_progress.json"
SCHEMA_VERSION = "orchestration_progress_read_model_v0"
MILESTONE_KINDS = frozenset({"feat", "fix", "chore", "perf", "refactor"})
DEFAULT_LIMIT = 15


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
    ).stdout.strip()


def _commit_kind(subject: str) -> str:
    head = subject.split("(", 1)[0].split(":", 1)[0].strip().lower()
    return head


def build(limit: int = DEFAULT_LIMIT) -> dict:
    branch = _git("rev-parse", "--abbrev-ref", "HEAD") or "unknown"
    raw = _git("log", f"-{limit * 4}", "--no-merges", "--pretty=%h%x1f%cI%x1f%s")
    milestones: list[dict] = []
    for line in raw.splitlines():
        parts = line.split("\x1f")
        if len(parts) != 3:
            continue
        commit, at, subject = parts
        if _commit_kind(subject) in MILESTONE_KINDS:
            milestones.append({"commit": commit, "at": at, "summary": subject})
        if len(milestones) >= limit:
            break
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": "scripts/export_orchestration_progress_read_model.py",
        "branch": branch,
        "shipped_milestones": milestones,
        "shipped_count": len(milestones),
        "note": "Recently shipped engineering milestones on the active branch (git-sourced, truthful).",
    }


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    artifact = build()
    OUT.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"wrote {OUT.relative_to(ROOT)} :: {artifact['shipped_count']} milestones on "
        f"{artifact['branch']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
