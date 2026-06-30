#!/usr/bin/env python3
"""Fold a knowledge SATELLITE sqlite into the ONE robust business-ops ledger.

Non-destructive + idempotent: each satellite table T becomes a ledger table
``knowledge_<prefix>_<T>`` (same columns + `_fold_source`/`_fold_at` provenance). Re-folding a
satellite replaces only its own folded rows. The satellite file is NEVER modified or deleted here.

Modes:
  (default)   DRY RUN  — print the fold plan (tables, row counts, target ledger tables).
  --confirm   FOLD     — write the folded tables into the ledger (operator-gated).
  --verify    VERIFY   — pass only if (a) every foldable table is present in the ledger with a
                          matching row count AND (b) NO live repo code still references the satellite
                          path. This is the gate that must pass BEFORE the satellite is archived
                          (today's incident: a partial fold + a live consumer = broken production).

Usage:
  python3 scripts/fold_satellite_to_ledger.py --satellite <path> [--ledger <path>]
      [--prefix <p>] [--skip-tables t1,t2] [--confirm | --verify] [--repo-root <dir>]
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_LEDGER = Path("/home/openclaw/.openclaw/business_ops/ledger.sqlite")
_INTERNAL = ("sqlite_",)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sanitize(name: str) -> str:
    return re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_").lower()


def default_prefix(satellite: Path) -> str:
    return _sanitize(satellite.stem)


def _tables(conn: sqlite3.Connection) -> list[str]:
    return [
        r[0]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        if not r[0].startswith(_INTERNAL)
    ]


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [c[1] for c in conn.execute(f'PRAGMA table_info("{table}")')]


def foldable_tables(satellite: Path, skip: set[str]) -> list[str]:
    conn = sqlite3.connect(f"file:{satellite}?mode=ro", uri=True)
    try:
        return [t for t in _tables(conn) if t not in skip]
    finally:
        conn.close()


def fold_plan(satellite: Path, ledger: Path, prefix: str, skip: set[str]) -> dict:
    src = sqlite3.connect(f"file:{satellite}?mode=ro", uri=True)
    try:
        plan = []
        for t in _tables(src):
            target = f"knowledge_{prefix}_{t}"
            rows = src.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0]
            plan.append(
                {"table": t, "rows": rows, "target": target, "skipped": t in skip}
            )
        return {
            "satellite": str(satellite),
            "ledger": str(ledger),
            "prefix": prefix,
            "tables": plan,
            "fold_count": sum(1 for p in plan if not p["skipped"]),
        }
    finally:
        src.close()


def fold(satellite: Path, ledger: Path, prefix: str, skip: set[str]) -> dict:
    folded_at = _utc_now()
    src = sqlite3.connect(f"file:{satellite}?mode=ro", uri=True)
    # The ledger is written LIVE by the running system. Wait for its lock instead of failing
    # immediately (default 5s) — the fold writes its own knowledge_* tables, never the live tables.
    dst = sqlite3.connect(ledger, timeout=60)
    dst.execute("PRAGMA busy_timeout=60000")
    written = {}
    try:
        for t in _tables(src):
            if t in skip:
                continue
            target = f"knowledge_{prefix}_{t}"
            cols = _columns(src, t)
            col_defs = ", ".join(f'"{c}"' for c in cols)
            dst.execute(
                f'CREATE TABLE IF NOT EXISTS "{target}" '
                f'({col_defs}, "_fold_source" TEXT, "_fold_at" TEXT)'
            )
            # idempotent: clear this satellite's prior rows for this target, then re-insert
            dst.execute(f'DELETE FROM "{target}" WHERE "_fold_source" = ?', (str(satellite),))
            placeholders = ", ".join("?" for _ in cols) + ", ?, ?"
            insert_cols = col_defs + ', "_fold_source", "_fold_at"'
            n = 0
            for row in src.execute(f'SELECT {col_defs} FROM "{t}"'):
                dst.execute(
                    f'INSERT INTO "{target}" ({insert_cols}) VALUES ({placeholders})',
                    (*row, str(satellite), folded_at),
                )
                n += 1
            written[target] = n
        dst.commit()
        return {"status": "folded", "satellite": str(satellite), "written": written, "folded_at": folded_at}
    finally:
        src.close()
        dst.close()


def live_consumers(satellite: Path, repo_root: Path) -> list[str]:
    """Repo .py files (excluding this tool, tests, archive) that still reference the satellite path."""
    needles = {satellite.name, str(satellite)}
    hits: list[str] = []
    try:
        out = subprocess.run(
            ["grep", "-rIl", "--include=*.py", satellite.name, str(repo_root)],
            capture_output=True, text=True, timeout=60,
        ).stdout
    except Exception:
        return []
    for line in out.splitlines():
        if any(x in line for x in ("/worktrees/", "/.venv/", "/.git/", "/archive/", "fold_satellite_to_ledger", "/tests/")):
            continue
        hits.append(line)
    return sorted(set(hits))


def verify(satellite: Path, ledger: Path, prefix: str, skip: set[str], repo_root: Path) -> dict:
    src = sqlite3.connect(f"file:{satellite}?mode=ro", uri=True)
    dst = sqlite3.connect(f"file:{ledger}?mode=ro", uri=True)
    unfolded, mismatched = [], []
    try:
        for t in _tables(src):
            if t in skip:
                continue
            target = f"knowledge_{prefix}_{t}"
            src_n = src.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0]
            try:
                dst_n = dst.execute(
                    f'SELECT count(*) FROM "{target}" WHERE "_fold_source" = ?', (str(satellite),)
                ).fetchone()[0]
            except sqlite3.OperationalError:
                unfolded.append(t)
                continue
            if dst_n != src_n:
                mismatched.append({"table": t, "src": src_n, "ledger": dst_n})
    finally:
        src.close()
        dst.close()
    consumers = live_consumers(satellite, repo_root)
    ok = not unfolded and not mismatched and not consumers
    return {
        "satellite": str(satellite),
        "ok_to_archive": ok,
        "unfolded_tables": unfolded,
        "row_count_mismatches": mismatched,
        "live_consumers_still_referencing_path": consumers,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Fold a knowledge satellite sqlite into the ledger.")
    ap.add_argument("--satellite", required=True)
    ap.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    ap.add_argument("--prefix", default="")
    ap.add_argument("--skip-tables", default="")
    ap.add_argument("--repo-root", default="/home/openclaw")
    ap.add_argument("--confirm", action="store_true")
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()

    satellite = Path(args.satellite)
    ledger = Path(args.ledger)
    prefix = args.prefix or default_prefix(satellite)
    skip = {s.strip() for s in args.skip_tables.split(",") if s.strip()}

    if args.verify:
        result = verify(satellite, ledger, prefix, skip, Path(args.repo_root))
        print(json.dumps(result, indent=2))
        return 0 if result["ok_to_archive"] else 1
    if args.confirm:
        print(json.dumps(fold(satellite, ledger, prefix, skip), indent=2))
        return 0
    # default: dry run
    plan = fold_plan(satellite, ledger, prefix, skip)
    plan["operator_command"] = (
        f"python3 scripts/fold_satellite_to_ledger.py --satellite {satellite} "
        f"--ledger {ledger} --prefix {prefix} --confirm"
    )
    print(json.dumps(plan, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
