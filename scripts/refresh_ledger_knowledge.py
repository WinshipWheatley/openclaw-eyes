#!/usr/bin/env python3
"""Auto-refresh the ledger's knowledge VIEW so it can't go stale.

The business-ops ledger is the ONE robust knowledge view. Live operational stores (the system-
knowledge registry, event router, proof-to-response runtime, governance registry, agentic-chain
inspector) and derived atlases keep being written by their own generators; this re-folds each into
the ledger (idempotent — replaces that source's prior folded rows) and stamps a `knowledge_fold_runs`
freshness row. Run on a schedule (cron) so the view tracks the live system instead of drifting.

  python3 scripts/refresh_ledger_knowledge.py            # dry run (prints the plan + current staleness)
  python3 scripts/refresh_ledger_knowledge.py --confirm   # re-fold all registered sources + stamp freshness

A source listed here but missing on disk is reported (not silently skipped) so coverage gaps show.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fold_satellite_to_ledger as fold  # noqa: E402
import capability_ledger_reconciler  # noqa: E402
from packet_dankness_drain import drain_packet_enrich_queue  # noqa: E402
from polish_loop.control_plane import (  # noqa: E402
    ControlPlaneLedger,
    DEFAULT_LEDGER_PATH as DEFAULT_CONTROL_PLANE_LEDGER,
)

DEFAULT_LEDGER = Path("/home/openclaw/.openclaw/business_ops/ledger.sqlite")

# The complete set of knowledge sources whose data must stay fresh in the ledger.
# (system_catalog repos are folded by scripts/ingest_system_catalog_to_ledger.py; add a repo
#  refresh here once repo_catalog writes the ledger directly.)
KNOWLEDGE_SOURCES: tuple[dict, ...] = (
    {"prefix": "sysknow", "path": "/home/openclaw/generated/system_knowledge/openclaw_system_knowledge_registry.sqlite", "skip": {"build_task"}},
    {"prefix": "evrouter", "path": "/home/openclaw/generated/system_knowledge/operator_controller_event_router.sqlite", "skip": set()},
    {"prefix": "p2r", "path": "/home/openclaw/generated/system_knowledge/proof_to_response_runtime.sqlite", "skip": set()},
    {"prefix": "sqlgov", "path": "/home/openclaw/generated/system_knowledge/sqlite_governance_registry.sqlite", "skip": set()},
    {"prefix": "agchain", "path": "/home/openclaw/generated/system_knowledge/agentic_chain_inspector.sqlite", "skip": set()},
    {"prefix": "fsatlas", "path": "/mnt/e/openclaw/generated/read_models/openclaw_filesystem_atlas.sqlite", "skip": set()},
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _ensure_runs_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS knowledge_fold_runs "
        "(prefix TEXT, source_path TEXT, rows_written INTEGER, status TEXT, folded_at TEXT)"
    )


def staleness(ledger: Path) -> list[dict]:
    """Per-source last-fold time from knowledge_fold_runs (so drift is queryable)."""
    out = []
    conn = sqlite3.connect(f"file:{ledger}?mode=ro", uri=True)
    try:
        _has = conn.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='knowledge_fold_runs'"
        ).fetchone()[0]
        for s in KNOWLEDGE_SOURCES:
            last = None
            if _has:
                row = conn.execute(
                    "SELECT folded_at, rows_written, status FROM knowledge_fold_runs "
                    "WHERE prefix=? ORDER BY folded_at DESC LIMIT 1",
                    (s["prefix"],),
                ).fetchone()
                last = {"folded_at": row[0], "rows": row[1], "status": row[2]} if row else None
            out.append({"prefix": s["prefix"], "path": s["path"], "exists": Path(s["path"]).exists(), "last_fold": last})
    finally:
        conn.close()
    return out


def refresh(ledger: Path) -> dict:
    # Fold each source with its OWN lone connection (no second connection open at the same time —
    # SQLite same-process locks fail instantly regardless of busy_timeout). Stamp freshness AFTER.
    results, stamps = [], []
    for s in KNOWLEDGE_SOURCES:
        src = Path(s["path"])
        if not src.exists():
            results.append({"prefix": s["prefix"], "status": "MISSING_SOURCE", "path": s["path"]})
            stamps.append((s["prefix"], s["path"], 0, "MISSING_SOURCE", _utc_now()))
            continue
        res = fold.fold(src, ledger, s["prefix"], s["skip"])
        rows = sum(res["written"].values())
        results.append({"prefix": s["prefix"], "status": "refreshed", "rows": rows, "tables": len(res["written"])})
        stamps.append((s["prefix"], s["path"], rows, "refreshed", res["folded_at"]))
    stamp = sqlite3.connect(ledger, timeout=60)
    try:
        stamp.execute("PRAGMA busy_timeout=60000")
        _ensure_runs_table(stamp)
        stamp.executemany("INSERT INTO knowledge_fold_runs VALUES (?,?,?,?,?)", stamps)
        stamp.commit()
    finally:
        stamp.close()
    capability_projection_paths: dict[str, Path] = {}
    if ledger.resolve(strict=False) != DEFAULT_LEDGER.resolve(strict=False):
        capability_projection_paths = {
            "receipt_path": ledger.parent / "capability_ledger_reconciler_receipt.json",
            "attention_path": ledger.parent / "capability_ledger_drift_attention.json",
        }
    capability_result = capability_ledger_reconciler.reconcile_capabilities(
        ledger_path=ledger,
        confirm=True,
        **capability_projection_paths,
    )
    capability_summary = {
        key: capability_result.get(key)
        for key in (
            "status",
            "batch_id",
            "activation_count",
            "changed_count",
            "decision_count",
            "drift_count",
        )
    }
    packet_dankness_summary = {"processed": 0, "refreshed": 0, "escalated": 0}
    if DEFAULT_CONTROL_PLANE_LEDGER.exists():
        outcomes = drain_packet_enrich_queue(
            ControlPlaneLedger(DEFAULT_CONTROL_PLANE_LEDGER),
            max_tasks=10,
        )
        packet_dankness_summary = {
            "processed": len(outcomes),
            "refreshed": sum(1 for row in outcomes if row.get("outcome") == "refreshed"),
            "escalated": sum(1 for row in outcomes if row.get("outcome") == "escalated"),
        }
    return {
        "refreshed_at": _utc_now(),
        "sources": results,
        "capability_reconciliation": capability_summary,
        "packet_dankness_drain": packet_dankness_summary,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Refresh the ledger knowledge view (anti-staleness).")
    ap.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    ap.add_argument("--confirm", action="store_true")
    args = ap.parse_args()
    ledger = Path(args.ledger)
    if args.confirm:
        print(json.dumps(refresh(ledger), indent=2))
        return 0
    print(json.dumps({"dry_run": True, "current_staleness": staleness(ledger),
                      "operator_command": "python3 scripts/refresh_ledger_knowledge.py --confirm"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
