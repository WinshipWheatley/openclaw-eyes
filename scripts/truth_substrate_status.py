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

        # 2. Decision Receipts Metrics
        cursor.execute("""
            SELECT p.packet_json_safe, e.ts
            FROM packets p
            JOIN events e ON p.event_id = e.event_id
            WHERE e.event_type = 'truth_packet_decision_receipt'
            ORDER BY e.ts DESC
        """)
        receipt_status_counts = {}
        latest_receipt = None

        rows = cursor.fetchall()
        for i, row in enumerate(rows):
            payload = json.loads(row[0])
            status = payload.get("packet_status", "unknown")
            receipt_status_counts[status] = receipt_status_counts.get(status, 0) + 1
            if i == 0:
                latest_receipt = payload
                # ensure recorded_at is present
                if "recorded_at" not in latest_receipt:
                    latest_receipt["recorded_at"] = row["ts"]

        # 3. Gateway Packet Posture (Inferred from DB state)
        # VERIFIED: verification_required=0 or (verification_required=1 and verification_evidence_id resolves to evidence for the same source)
        # UNCERTAIN: verification_required=1 and (verification_evidence_id is NULL/empty or does not resolve)
        # BLOCKED: hash_status != 'current' (This is a simplified view for status)

        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE
                    WHEN verification_required = 0
                    THEN 1
                    WHEN verification_required = 1
                         AND verification_evidence_id IS NOT NULL
                         AND verification_evidence_id != ''
                         AND EXISTS (
                             SELECT 1 FROM verification_evidence ve
                             WHERE ve.evidence_id = canonical_facts.verification_evidence_id
                             AND ve.source_id = canonical_facts.truth_source_id
                         )
                    THEN 1
                    ELSE 0
                END) as verified_candidate,
                SUM(CASE
                    WHEN verification_required = 1
                         AND (
                             verification_evidence_id IS NULL
                             OR verification_evidence_id = ''
                             OR NOT EXISTS (
                                 SELECT 1 FROM verification_evidence ve
                                 WHERE ve.evidence_id = canonical_facts.verification_evidence_id
                                 AND ve.source_id = canonical_facts.truth_source_id
                             )
                         )
                    THEN 1
                    ELSE 0
                END) as uncertain_candidate
            FROM canonical_facts
        """)
        posture_row = cursor.fetchone()

        # We also need to check registry for blocked status (hash mismatch)
        cursor.execute("SELECT COUNT(*) FROM truth_registry_entries WHERE hash_status != 'current'")
        blocked_sources_count = cursor.fetchone()[0]

        # 4. SOURCE_REGISTRY Coverage & Hash Metrics
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
                "decision_receipts": {
                    "by_status": receipt_status_counts,
                    "latest": latest_receipt,
                    "total": sum(receipt_status_counts.values())
                },
                "gateway_posture": {
                    "verified_candidate_facts": posture_row["verified_candidate"] or 0,
                    "uncertain_candidate_facts": posture_row["uncertain_candidate"] or 0,
                    "blocked_sources_count": blocked_sources_count,
                    "runtime_authority": False,
                    "note": "MODEL_BLOCKED takes precedence over candidate status if hash mismatch exists."
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

    print("Candidate Truth Substrate Status Summary")
    print("========================================")
    print(f"Canonical Facts: {facts['total']}")
    print(f"  - Verification Required: {facts['by_verification_required'].get(True, 0)}")
    print(f"  - Verification Not Required: {facts['by_verification_required'].get(False, 0)}")

    print(f"\nFact Posture Breakdown:")
    for s, c in sorted(facts["by_truth_status"].items()):
        print(f"  - {s}: {c}")

    dr = metrics.get("decision_receipts", {})
    if dr and dr.get("total", 0) > 0:
        print(f"\nTruth Packet Decision Receipts (Audit Ledger):")
        print(f"  - Total Decisions Recorded: {dr['total']}")
        for s, c in sorted(dr["by_status"].items()):
            print(f"    - {s}: {c}")

        latest = dr.get("latest")
        if latest:
            print(f"  - Latest Decision ({latest['recorded_at']}):")
            print(f"    - Status: {latest['packet_status']}")
            print(f"    - Crossed Model Boundary: {bool(latest['fact_text_crossed_model_boundary'])}")
            print(f"    - Content Redacted: {bool(latest['fact_text_redacted_in_receipt'])}")
            print(f"    - Runtime Authority: {bool(latest['runtime_authority'])}")
            print(f"    - External Model Access: {bool(latest['external_model_access_granted'])}")

        # Warning if recent blocks/uncertainties
        if dr["by_status"].get("MODEL_BLOCKED", 0) > 0 or dr["by_status"].get("MODEL_ALLOWED_UNCERTAIN", 0) > 0:
            print(f"  - NOTICE: Recent BLOCKED or UNCERTAIN decisions exist. Review gateway audit logs.")

    gp = metrics["gateway_posture"]
    print(f"\nCandidate Truth Gateway Packet Posture (Boundary View):")
    print(f"  - MODEL_ALLOWED_VERIFIED: {gp['verified_candidate_facts']} candidate facts")
    print(f"  - MODEL_ALLOWED_UNCERTAIN: {gp['uncertain_candidate_facts']} candidate facts")
    print(f"  - MODEL_BLOCKED: {gp['blocked_sources_count']} sources with hash mismatch")
    print(f"  - Runtime Authority: {gp['runtime_authority']}")
    print(f"  - {gp['note']}")

    print(f"\nSource Registry Coverage: {registry['present_sources']}/{registry['total_sources']}")


    print("\nRegistry Hash Status:")
    if not registry["hash_status_counts"]:
        print("  - (No entries)")
    for s, c in sorted(registry["hash_status_counts"].items()):
        print(f"  - {s}: {c}")

    print(f"\nReadiness: {readiness['result']}")
    if not readiness["is_ready"]:
        print(f"  - Unsafe/Missing sources: {readiness['unsafe_count']}")

    print("\nBoundary note: Truth status describes candidate verification posture, not live runtime health, agent authority, or terminal gateway decisions.")

if __name__ == "__main__":
    main()
