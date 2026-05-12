import os
import sys
import sqlite3
import json
import argparse
from typing import Any, Dict, List, Optional

# Add CWD to sys.path to allow importing from scripts
sys.path.append(os.getcwd())

try:
    from scripts.ingest_canonical_docs import SOURCE_REGISTRY
except ImportError:
    SOURCE_REGISTRY = {}

DEFAULT_DB_PATH = ".openclaw/business_ops/ledger.sqlite"

def get_truth_substrate_status(db_path: str = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """
    Returns deterministic truth substrate metrics for operator status integration.
    """
    if not os.path.exists(db_path):
        return {"status": "unavailable", "reason": "Database missing"}

    try:
        # Use URI for read-only to avoid side-effects
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check for required tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        required_tables = ["canonical_facts", "truth_registry_entries"]
        missing_tables = [t for t in required_tables if t not in tables]
        if missing_tables:
            conn.close()
            return {"status": "unavailable", "reason": f"Missing tables: {', '.join(missing_tables)}"}

        # 1. Canonical Facts Metrics
        cursor.execute("SELECT COUNT(*) FROM canonical_facts")
        total_facts = cursor.fetchone()[0]

        cursor.execute("SELECT truth_status, COUNT(*) as count FROM canonical_facts GROUP BY truth_status")
        truth_status_counts = {row["truth_status"] or "None": row["count"] for row in cursor.fetchall()}

        cursor.execute("SELECT verification_required, COUNT(*) as count FROM canonical_facts GROUP BY verification_required")
        ver_req_counts = {bool(row["verification_required"]): row["count"] for row in cursor.fetchall()}

        # 2. SOURCE_REGISTRY Coverage & Hash Metrics
        registry_total = len(SOURCE_REGISTRY)
        registry_present = 0
        hash_status_counts = {}
        registry_truth_status_counts = {}
        unsafe_entries = []

        for source_path in SOURCE_REGISTRY:
            cursor.execute(
                "SELECT truth_status, hash_status FROM truth_registry_entries WHERE observed_path = ?",
                (source_path,)
            )
            row = cursor.fetchone()

            if row:
                registry_present += 1
                truth_status = row["truth_status"]
                hash_status = row["hash_status"]

                hash_status_counts[hash_status] = hash_status_counts.get(hash_status, 0) + 1
                registry_truth_status_counts[truth_status] = registry_truth_status_counts.get(truth_status, 0) + 1

                # Readiness Logic (consistent with truth_ingest_readiness_report.py)
                is_unsafe = False
                if hash_status == "changed":
                    is_unsafe = True
                elif truth_status in ("test_verified", "runtime_verified") and hash_status != "current":
                    is_unsafe = True
                
                if is_unsafe:
                    unsafe_entries.append(source_path)
            else:
                unsafe_entries.append(source_path)

        conn.close()

        is_ready = len(unsafe_entries) == 0

        return {
            "status": "available",
            "metrics": {
                "facts": {
                    "total": total_facts,
                    "by_truth_status": truth_status_counts,
                    "by_verification_required": ver_req_counts
                },
                "registry": {
                    "total_sources": registry_total,
                    "present_sources": registry_present,
                    "hash_status_counts": hash_status_counts,
                    "truth_status_counts": registry_truth_status_counts
                },
                "readiness": {
                    "is_ready": is_ready,
                    "unsafe_count": len(unsafe_entries),
                    "result": "READY" if is_ready else "NOT_READY"
                }
            }
        }

    except Exception as e:
        return {"status": "unavailable", "reason": f"Error: {str(e)}"}

def main():
    parser = argparse.ArgumentParser(description="Truth Substrate Status Metrics")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="Path to SQLite DB")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    status = get_truth_substrate_status(args.db)

    if args.json:
        print(json.dumps(status, indent=2))
        return

    if status["status"] == "unavailable":
        print(f"Truth Substrate Status: UNAVAILABLE ({status['reason']})")
        return

    metrics = status["metrics"]
    facts = metrics["facts"]
    registry = metrics["registry"]
    readiness = metrics["readiness"]

    print("Truth Substrate Status Summary")
    print("==============================")
    print(f"Canonical Facts: {facts['total']}")
    print(f"  - Verification Required: {facts['by_verification_required'].get(True, 0)}")
    print(f"  - Verification Not Required: {facts['by_verification_required'].get(False, 0)}")
    
    print("\nFact Posture Breakdown:")
    for s, c in sorted(facts["by_truth_status"].items()):
        print(f"  - {s}: {c}")

    print(f"\nSource Registry Coverage: {registry['present_sources']}/{registry['total_sources']}")
    
    print("\nRegistry Hash Status:")
    if not registry["hash_status_counts"]:
        print("  - (No entries)")
    for s, c in sorted(registry["hash_status_counts"].items()):
        print(f"  - {s}: {c}")

    print(f"\nReadiness: {readiness['result']}")
    if not readiness["is_ready"]:
        print(f"  - Unsafe/Missing sources: {readiness['unsafe_count']}")
    
    print("\nBoundary note: Truth status describes verification posture, not runtime authority.")

if __name__ == "__main__":
    main()
