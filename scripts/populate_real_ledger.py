#!/usr/bin/env python3
"""populate_real_ledger.py — the ONLY sanctioned writer of the production canonical-fact ledger.

SAFETY MODEL:
  * Writing the real ledger requires the explicit --confirm flag AND is the single action a
    one-use operator approval authorizes. Without --confirm this does a DRY RUN against a
    temporary COPY of the ledger and reports exactly what WOULD change — the real ledger is
    never opened for writing.
  * The underlying ingest door hard-refuses the production path unless allow_production=True;
    only this script (with --confirm) passes it.
  * Every confirmed run writes an auditable receipt recording the inserted content_hashes, so
    the population is fully REVERSIBLE via --rollback <receipt>.

Run from the repo root (e.g. /home/openclaw).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import canonical_doctrine_facts as cdf
import model_selection_doctrine_facts as ms
import niles_lane_doctrine_facts as nl
from canonical_fact_ingest import reconcile_fact_index, _PRODUCTION_DB_PATH

REAL_LEDGER = str(Path(_PRODUCTION_DB_PATH).expanduser().resolve())
RECEIPT_DIR = Path("generated/ledger_population_receipts")


def _count(db: str) -> int:
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        return con.execute("SELECT COUNT(*) FROM canonical_facts").fetchone()[0]
    except Exception:
        return 0


def _populate(db: str, allow_production: bool) -> dict:
    """Load the curated, grounded doctrine facts via the single door, then reconcile the index.

    Loads BOTH curated doctrine sets (shared-doctrine SD-1..13 and model-selection
    MS-1..N). Results are merged so the receipt's inserted_content_hashes covers
    every insert from either set — keeping the whole population rollback-safe.
    """
    res = cdf.load_doctrine_facts(db, allow_production=allow_production)
    ms_res = ms.load_model_selection_doctrine(db, allow_production=allow_production)
    nl_res = nl.load_niles_lane_doctrine(db, allow_production=allow_production)
    reconcile_fact_index(db, allow_production=allow_production)
    return {
        "inserted": res["inserted"] + ms_res["inserted"] + nl_res["inserted"],
        "skipped": res["skipped"] + ms_res["skipped"] + nl_res["skipped"],
        "ungrounded_skipped": res["ungrounded_skipped"] + ms_res["ungrounded_skipped"] + nl_res["ungrounded_skipped"],
        "total": res["total"] + ms_res["total"] + nl_res["total"],
        "results": [*res.get("results", []), *ms_res.get("results", []), *nl_res.get("results", [])],
    }


def _do_rollback(receipt_path: str) -> int:
    receipt = json.loads(Path(receipt_path).read_text())
    target = receipt["db"]
    hashes = receipt.get("inserted_content_hashes", [])
    if not hashes:
        print("Nothing to roll back (receipt has no inserted_content_hashes).")
        return 0
    con = sqlite3.connect(target)
    marks = ",".join("?" * len(hashes))
    con.execute(f"DELETE FROM canonical_facts WHERE content_hash IN ({marks})", hashes)
    for tbl in ("fts_canonical_facts", "embedding_work_queue"):
        try:
            con.execute(f"DELETE FROM {tbl} WHERE content_hash IN ({marks})", hashes)
        except Exception:
            pass
    con.commit()
    print(f"Rolled back {len(hashes)} facts from {target}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Sanctioned populator of the real canonical-fact ledger.")
    ap.add_argument("--confirm", action="store_true",
                    help="ACTUALLY write the real ledger (one-use operator approval required). "
                         "Without this flag, runs a dry run on a temp copy.")
    ap.add_argument("--db", default=REAL_LEDGER, help="Target ledger (default: the real production ledger).")
    ap.add_argument("--rollback", metavar="RECEIPT", help="Reverse a prior population using its receipt JSON.")
    args = ap.parse_args(argv)

    if args.rollback:
        return _do_rollback(args.rollback)

    before = _count(args.db)

    if not args.confirm:
        # DRY RUN: populate a temp COPY; the real ledger is never written.
        with tempfile.TemporaryDirectory() as td:
            preview = str(Path(td) / "preview.sqlite")
            if Path(args.db).exists():
                shutil.copy2(args.db, preview)
            res = _populate(preview, allow_production=False)  # temp path → guard not engaged
            after = _count(preview)
        print("=== DRY RUN — real ledger NOT touched ===")
        print(f"target          : {args.db}")
        print(f"canonical_facts : {before} -> {after}  (+{after - before})")
        print(f"doctrine loader : inserted={res['inserted']} skipped={res['skipped']} "
              f"ungrounded_skipped={res['ungrounded_skipped']}")
        print("To write for real, re-run with --confirm under a one-use operator approval.")
        return 0

    # CONFIRMED real-ledger write.
    print("=== POPULATING REAL LEDGER (--confirm) ===")
    print(f"target: {args.db}")
    res = _populate(args.db, allow_production=True)
    after = _count(args.db)
    inserted_hashes = [r.get("content_hash") for r in res.get("results", []) if r.get("status") == "inserted"]
    receipt = {
        "action": "populate_real_ledger",
        "db": args.db,
        "canonical_facts_before": before,
        "canonical_facts_after": after,
        "inserted": res["inserted"],
        "skipped": res["skipped"],
        "ungrounded_skipped": res["ungrounded_skipped"],
        "inserted_content_hashes": inserted_hashes,
        "source": "canonical_doctrine_facts.SHARED_DOCTRINE_FACTS + model_selection_doctrine_facts.MODEL_SELECTION_DOCTRINE_FACTS + niles_lane_doctrine_facts.NILES_LANE_DOCTRINE_FACTS",
        "written_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    receipt_file = RECEIPT_DIR / f"populate_real_ledger_{stamp}.json"
    receipt_file.write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    print(f"receipt : {receipt_file}")
    print(f"rollback: python3 scripts/populate_real_ledger.py --rollback {receipt_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
