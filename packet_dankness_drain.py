#!/usr/bin/env python3
"""Autonomous drain for the dankifier self-improving loop.

The observe hook QUEUES packet_enrich gaps on real usage; this DRAINS them: runs the grounded
enricher (refresh a real source / escalate) and marks each task terminal. It only ever touches
type='packet_enrich' tasks (never heal/worker tasks). BOUNDED per run (max_tasks) so it can't
run away — designed to be invoked periodically (timer/cron), process a small batch, and exit.

Grounded-only: enrich_one refreshes a real generator or escalates to the operator; it NEVER
fabricates. That contract — not a kill-switch — is what makes running this autonomously safe.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Mapping

ROOT = Path(__file__).resolve().parent
for _p in (str(ROOT), str(ROOT / "polish_loop")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from polish_loop.control_plane import ControlPlaneLedger, DEFAULT_LEDGER_PATH, iso_now
from packet_dankness_enricher import ESCALATIONS_PATH, enrich_one


def _payload(task: Mapping[str, Any]) -> dict[str, Any]:
    p = task.get("payload")
    if isinstance(p, str):
        try:
            return json.loads(p)
        except ValueError:
            return {}
    return dict(p) if isinstance(p, Mapping) else {}


def drain_packet_enrich_queue(
    ledger: ControlPlaneLedger,
    *,
    max_tasks: int = 10,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    escalations_path: Path = ESCALATIONS_PATH,
) -> list[dict[str, Any]]:
    """Process up to max_tasks queued packet_enrich tasks. Returns per-task outcomes."""
    ready = [
        t for t in ledger.list_tasks()
        if t.get("type") == "packet_enrich" and t.get("status") == "READY"
    ][:max_tasks]
    outcomes: list[dict[str, Any]] = []
    for task in ready:
        result = enrich_one(_payload(task), runner=runner, escalations_path=escalations_path)
        reason = f"dankness_{result.get('outcome', 'unknown')}"
        # Lightweight terminalization: packet_enrich tasks need no worker verification.
        # Scoped to type='packet_enrich' + status='READY' so we can never disturb other work.
        with ledger.connect() as conn:
            conn.execute(
                "UPDATE tasks SET status='DONE', terminal_reason=?, updated_at=? "
                "WHERE id=? AND type='packet_enrich' AND status='READY'",
                (reason, iso_now(), task["id"]),
            )
        outcomes.append({"task_id": task["id"], "outcome": result.get("outcome"), "detail": result})
    return outcomes


def main() -> int:
    if not DEFAULT_LEDGER_PATH.exists():
        print("dankness drain: no control-plane ledger yet (nothing queued)")
        return 0
    ledger = ControlPlaneLedger(DEFAULT_LEDGER_PATH)
    outcomes = drain_packet_enrich_queue(ledger)
    refreshed = sum(1 for o in outcomes if o["outcome"] == "refreshed")
    escalated = sum(1 for o in outcomes if o["outcome"] == "escalated")
    print(f"dankness drain: processed {len(outcomes)} (refreshed {refreshed}, escalated {escalated})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
