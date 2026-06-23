#!/usr/bin/env python3
"""Ingest the Codex backlog (Batch 044-093) into the Phase-C control-plane ledger.

SAFE BY DESIGN: admits every task as **PROPOSED** (NOT dispatchable), so the live `--once` cron
never picks them up. Loading the backlog ("ingest") is separated from running it ("dispatch") —
promotion PROPOSED->READY is a deliberate, audited step done after the done-vs-open status audit
(this batch is heavily duplicated and partly already-shipped; blind dispatch = false progress).

Idempotent: a task whose id (`backlog-<nnn>`) already exists is skipped, so re-runs are safe.
`--dry-run` parses + reports and writes nothing. Source of truth is the authoritative work queue.
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_QUEUE = Path("/mnt/e/openclaw/orchestration/MASTER-WORK-QUEUE.md")
DEFAULT_LEDGER = ROOT / "polish_loop" / "control_plane.sqlite3"
PROPOSED_TTL_SECONDS = 30 * 24 * 3600  # 30 days — long enough to survive the audit + promotion

# `- **044** [P1/brain-quality] 003a-deterministic-operator-truth-query-intent`
_ROW = re.compile(r"^\s*-\s+\*\*(\d+)\*\*\s+\[([^/\]]+)/([^\]]+)\]\s+(.+?)\s*$")


def parse_batch(queue_path: Path) -> list[dict]:
    """Parse the '044-093' batch rows into structured task dicts. Order preserved."""
    text = queue_path.read_text(encoding="utf-8")
    # restrict to the NEW BATCH section so we never pick up the detailed lane lists above
    marker = text.find("NEW BATCH 044-093")
    section = text[marker:] if marker != -1 else text
    items: list[dict] = []
    for line in section.splitlines():
        m = _ROW.match(line)
        if not m:
            continue
        num, priority, category, slug = m.group(1), m.group(2).strip(), m.group(3).strip(), m.group(4).strip()
        items.append({
            "num": num,
            "priority": priority,
            "category": category,
            "slug": slug,
            "task_id": f"backlog-{num}",
            "branch_hint": f"codex/{num}-{slug}",
        })
    return items


def existing_backlog_ids(ledger_path: Path) -> set[str]:
    if not ledger_path.exists():
        return set()
    con = sqlite3.connect(f"file:{ledger_path}?mode=ro", uri=True, timeout=10)
    try:
        return {r[0] for r in con.execute("SELECT id FROM tasks WHERE id LIKE 'backlog-%'")}
    finally:
        con.close()


def ingest(queue_path: Path, ledger_path: Path, *, dry_run: bool) -> dict:
    items = parse_batch(queue_path)
    have = existing_backlog_ids(ledger_path)
    to_admit = [it for it in items if it["task_id"] not in have]
    skipped = [it for it in items if it["task_id"] in have]

    if dry_run:
        return {"parsed": len(items), "would_admit": len(to_admit), "already_present": len(skipped),
                "items": items, "to_admit": to_admit}

    from polish_loop.control_plane import ControlPlaneLedger

    ledger = ControlPlaneLedger(ledger_path)
    admitted: list[str] = []
    for it in to_admit:
        goal = (f"Codex backlog {it['num']} [{it['priority']}/{it['category']}]: {it['slug']}. "
                f"Detailed spec: MASTER-WORK-QUEUE.md batch 044-093 + branch {it['branch_hint']}. "
                f"PROPOSED only — promote to READY after the done-vs-open audit.")
        tid = ledger.admit_task(
            task_id=it["task_id"],
            source="human_intent",
            task_type="codex_backlog",
            requested_status="PROPOSED",       # NEVER dispatchable on ingest
            payload={
                "num": it["num"], "priority": it["priority"], "category": it["category"],
                "slug": it["slug"], "goal": goal, "branch_hint": it["branch_hint"],
                "queue_ref": str(queue_path), "batch": "044-093",
            },
            acceptance_ref={"queue": "MASTER-WORK-QUEUE.md", "batch": "044-093", "branch": it["branch_hint"]},
            ttl_seconds=PROPOSED_TTL_SECONDS,
            max_attempts=3,
        )
        admitted.append(tid)
    return {"parsed": len(items), "admitted": len(admitted), "already_present": len(skipped),
            "admitted_ids": admitted}


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest Codex backlog 044-093 into the Phase-C ledger (PROPOSED only)")
    ap.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    ap.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    res = ingest(args.queue, args.ledger, dry_run=args.dry_run)
    if args.dry_run:
        print(f"[dry-run] parsed={res['parsed']} would_admit={res['would_admit']} already_present={res['already_present']}")
        for it in res["items"]:
            mark = "NEW" if it in res["to_admit"] else "skip"
            print(f"  [{mark}] {it['task_id']:<13} [{it['priority']}/{it['category']}] {it['slug']}")
    else:
        print(f"INGESTED (PROPOSED): admitted={res['admitted']} already_present={res['already_present']} parsed={res['parsed']}")
        print("All admitted as PROPOSED (NOT dispatchable). Promote to READY only after the done-vs-open audit.")


if __name__ == "__main__":
    main()
