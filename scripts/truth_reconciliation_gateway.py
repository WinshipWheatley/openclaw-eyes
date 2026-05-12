import argparse
import sqlite3
import os
import sys
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List

# Attempt to import SOURCE_REGISTRY
sys.path.append(os.getcwd())
try:
    from scripts.ingest_canonical_docs import SOURCE_REGISTRY
except ImportError:
    SOURCE_REGISTRY = {}

# State constants
CANDIDATE_SURFACED = "CANDIDATE_SURFACED"
CHECK_RUNNING = "CHECK_RUNNING"
NO_DIFF_FOUND = "NO_DIFF_FOUND"
DIFF_FOUND = "DIFF_FOUND"
RECONCILIATION_ALLOWED = "RECONCILIATION_ALLOWED"
RECONCILIATION_BLOCKED = "RECONCILIATION_BLOCKED"
RECONCILIATION_APPLIED = "RECONCILIATION_APPLIED"
RECALLED_AFTER_RECONCILIATION = "RECALLED_AFTER_RECONCILIATION"
RECHECK_RUNNING = "RECHECK_RUNNING"
RECHECK_PASSED = "RECHECK_PASSED"
RECHECK_FAILED = "RECHECK_FAILED"
PACKET_READY = "PACKET_READY"
MODEL_ALLOWED_VERIFIED = "MODEL_ALLOWED_VERIFIED"
MODEL_ALLOWED_UNCERTAIN = "MODEL_ALLOWED_UNCERTAIN"
MODEL_ALLOWED = MODEL_ALLOWED_VERIFIED # Alias for v0/v1 compatibility
CHECK_FAILED = "CHECK_FAILED"
MODEL_BLOCKED = "MODEL_BLOCKED"

def calculate_sha256(file_path: str) -> str:
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def check_fact_source_integrity(db_path: str, fact_id: str) -> Dict[str, Any]:
    """
    Read-only JIT source integrity checker for a specific canonical fact.
    """
    result = {
        "status": "BLOCK",
        "state": "CHECK_FAILED",
        "fact_id": fact_id,
        "source_file": None,
        "truth_source_id": None,
        "truth_status": None,
        "verification_required": None,
        "source_content_hash": None,
        "disk_content_hash": None,
        "hash_status": None,
        "block_reason": None,
        "repairable": False
    }

    if not os.path.exists(db_path):
        result["block_reason"] = f"Database not found: {db_path}"
        return result

    try:
        # Open SQLite read-only
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 1. Load canonical_facts row
        cursor.execute("SELECT * FROM canonical_facts WHERE fact_id = ?", (fact_id,))
        fact_row = cursor.fetchone()
        if not fact_row:
            result["block_reason"] = f"Fact not found: {fact_id}"
            conn.close()
            return result

        result["source_file"] = fact_row["source_file"]
        result["truth_source_id"] = fact_row["truth_source_id"]
        result["truth_status"] = fact_row["truth_status"]
        result["verification_required"] = bool(fact_row["verification_required"])

        # 2. Load matching truth_registry_entries row
        cursor.execute(
            "SELECT * FROM truth_registry_entries WHERE source_id = ?",
            (fact_row["truth_source_id"],)
        )
        reg_row = cursor.fetchone()
        if not reg_row:
            result["block_reason"] = f"Registry entry missing for source_id: {fact_row['truth_source_id']}"
            conn.close()
            return result

        result["source_content_hash"] = reg_row["source_content_hash"]
        result["hash_status"] = reg_row["hash_status"]

        # 3. Alignment Checks
        if fact_row["source_file"] != reg_row["observed_path"]:
            result["block_reason"] = f"Alignment mismatch: fact source_file '{fact_row['source_file']}' vs registry observed_path '{reg_row['observed_path']}'"
            conn.close()
            return result

        if fact_row["source_file"] not in SOURCE_REGISTRY:
            result["block_reason"] = f"Source file not in SOURCE_REGISTRY: {fact_row['source_file']}"
            conn.close()
            return result

        if not reg_row["source_content_hash"]:
            result["block_reason"] = "Registry source_content_hash is missing"
            conn.close()
            return result

        # 4. JIT Disk Hash Check
        if not os.path.exists(fact_row["source_file"]):
            result["state"] = "DIFF_FOUND"
            result["block_reason"] = f"Source file missing from disk: {fact_row['source_file']}"
            conn.close()
            return result

        disk_hash = calculate_sha256(fact_row["source_file"])
        result["disk_content_hash"] = disk_hash

        if disk_hash != reg_row["source_content_hash"]:
            result["state"] = "DIFF_FOUND"
            result["block_reason"] = "Disk hash mismatch vs recorded source_content_hash"
            conn.close()
            return result

        # 5. Hash Status Check
        if reg_row["hash_status"] != "current":
            result["state"] = "DIFF_FOUND"
            result["block_reason"] = f"Registry hash_status is '{reg_row['hash_status']}', expected 'current'"
            # Disk hash matches source_content_hash, so it is repairable
            result["repairable"] = True
            conn.close()
            return result

        # All checks passed
        result["status"] = "PASS"
        result["state"] = "NO_DIFF_FOUND"
        conn.close()
        return result

    except Exception as e:
        result["block_reason"] = f"Internal error: {str(e)}"
        return result

def build_llm_truth_packet(db_path: str, fact_id: str, question: str = None, allow_reconciliation: bool = False) -> Dict[str, Any]:
    """
    Builds a final LLM truth packet with v1 reconciliation support.
    """
    transitions = [CANDIDATE_SURFACED, CHECK_RUNNING]

    # 1. Integrity Check
    integrity = check_fact_source_integrity(db_path, fact_id)

    if integrity["status"] == "BLOCK":
        if integrity["state"] == "DIFF_FOUND":
            transitions.append(DIFF_FOUND)

            # Reconciliation Attempt
            if allow_reconciliation:
                transitions.append(RECONCILIATION_ALLOWED)

                try:
                    # OPEN SQLite for writing (reconciliation)
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()

                    if integrity["repairable"]:
                        # Repair hash_status to 'current'
                        cursor.execute(
                            "UPDATE truth_registry_entries SET hash_status = 'current' WHERE source_id = ?",
                            (integrity["truth_source_id"],)
                        )
                        # Also update any facts linked to this source
                        cursor.execute(
                            "UPDATE canonical_facts SET verification_required = 0 WHERE truth_source_id = ?",
                            (integrity["truth_source_id"],)
                        )
                        conn.commit()
                        conn.close()
                        transitions.append(RECONCILIATION_APPLIED)

                        # MANDATORY RE-QUERY / RE-CHECK LOOP
                        transitions.append(RECALLED_AFTER_RECONCILIATION)
                        transitions.append(RECHECK_RUNNING)

                        recheck = check_fact_source_integrity(db_path, fact_id)
                        if recheck["status"] == "PASS":
                            transitions.append(RECHECK_PASSED)
                            # Continue to packet generation using fresh state
                        else:
                            transitions.append(RECHECK_FAILED)
                            transitions.append(MODEL_BLOCKED)
                            return {
                                "status": MODEL_BLOCKED,
                                "state": MODEL_BLOCKED,
                                "transitions": transitions,
                                "question": question,
                                "block_reason": f"Recheck failed after reconciliation: {recheck['block_reason']}",
                                "fact_id": fact_id,
                                "verified_facts": []
                            }
                    else:
                        # Mismatch Invalidation
                        now = datetime.now(timezone.utc).isoformat()
                        new_truth_status = integrity["truth_status"]
                        # Downgrade only if test_verified or runtime_verified
                        if integrity["truth_status"] in ("test_verified", "runtime_verified"):
                            new_truth_status = "stale_possible"

                        # Update Registry
                        cursor.execute(
                            """
                            UPDATE truth_registry_entries
                            SET hash_status = 'changed',
                                verification_invalidated_at = ?,
                                invalidation_reason = ?,
                                verification_required = 1,
                                truth_status = ?
                            WHERE source_id = ?
                            """,
                            (now, "JIT hash mismatch detected", new_truth_status, integrity["truth_source_id"])
                        )
                        # Update Canonical Facts
                        cursor.execute(
                            """
                            UPDATE canonical_facts
                            SET truth_status = ?,
                                verification_required = 1
                            WHERE truth_source_id = ?
                            """,
                            (new_truth_status, integrity["truth_source_id"])
                        )
                        conn.commit()
                        conn.close()
                        transitions.append(RECONCILIATION_APPLIED)
                        transitions.append(MODEL_BLOCKED)

                        return {
                            "status": MODEL_BLOCKED,
                            "state": MODEL_BLOCKED,
                            "transitions": transitions,
                            "question": question,
                            "block_reason": f"Hash mismatch detected. Invalidation applied: {integrity['block_reason']}",
                            "fact_id": fact_id,
                            "verified_facts": []
                        }

                except Exception as e:
                    transitions.append(CHECK_FAILED)
                    transitions.append(MODEL_BLOCKED)
                    return {
                        "status": MODEL_BLOCKED,
                        "state": MODEL_BLOCKED,
                        "transitions": transitions,
                        "question": question,
                        "block_reason": f"Reconciliation error: {str(e)}",
                        "fact_id": fact_id,
                        "verified_facts": []
                    }
            else:
                if integrity["repairable"]:
                    transitions.append(RECONCILIATION_BLOCKED)
                transitions.append(MODEL_BLOCKED)
                return {
                    "status": MODEL_BLOCKED,
                    "state": MODEL_BLOCKED,
                    "transitions": transitions,
                    "question": question,
                    "block_reason": integrity["block_reason"],
                    "fact_id": fact_id,
                    "verified_facts": []
                }
        else:
            transitions.append(CHECK_FAILED)
            transitions.append(MODEL_BLOCKED)
            return {
                "status": MODEL_BLOCKED,
                "state": MODEL_BLOCKED,
                "transitions": transitions,
                "question": question,
                "block_reason": integrity["block_reason"],
                "fact_id": fact_id,
                "verified_facts": []
            }
    else:
        transitions.append(NO_DIFF_FOUND)

    # 2. Build Packet (Recalled from SQLite to ensure fresh state)
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM canonical_facts WHERE fact_id = ?", (fact_id,))
        fact = cursor.fetchone()
        conn.close()

        if not fact:
            transitions.append(CHECK_FAILED)
            transitions.append(MODEL_BLOCKED)
            return {
                "status": MODEL_BLOCKED,
                "state": MODEL_BLOCKED,
                "transitions": transitions,
                "question": question,
                "block_reason": "Fact disappeared during recall",
                "fact_id": fact_id,
                "verified_facts": []
            }

        # Labels
        truth_status = fact["truth_status"] or "UNKNOWN"
        labels = [
            "[REPO-SOURCE]",
            "[HASH-CURRENT]",
            f"[{truth_status.upper()}]"
        ]
        if fact["verification_required"]:
            labels.append("[VERIFY_REQUIRED]")

        # Provenance
        provenance = {
            "fact_id": fact["fact_id"],
            "source_file": fact["source_file"],
            "source_commit": fact["source_commit"],
            "content_hash": fact["content_hash"],
            "truth_source_id": fact["truth_source_id"],
            "truth_status": fact["truth_status"],
            "verification_required": bool(fact["verification_required"]),
            "verification_evidence_id": fact["verification_evidence_id"]
        }

        verified_fact = {
            "id": fact["fact_id"],
            "text": fact["fact_text"],
            "labels": " ".join(labels),
            "provenance": provenance
        }

        transitions.append(PACKET_READY)
        transitions.append(MODEL_ALLOWED)

        return {
            "status": MODEL_ALLOWED,
            "state": MODEL_ALLOWED,
            "transitions": transitions,
            "question": question,
            "substrate_status": "READY",
            "verified_facts": [verified_fact],
            "runtime_authority": False,
            "answer_boundary": "Answer only from verified_facts. Truth status describes verification posture, not runtime health or agent authority."
        }

    except Exception as e:
        transitions.append(CHECK_FAILED)
        transitions.append(MODEL_BLOCKED)
        return {
            "status": MODEL_BLOCKED,
            "state": MODEL_BLOCKED,
            "transitions": transitions,
            "question": question,
            "block_reason": f"Internal packet generation error: {str(e)}",
            "fact_id": fact_id,
            "verified_facts": []
        }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Truth Reconciliation Gateway v1 - JIT Integrity & Mechanical Repair")
    parser.add_argument("--db", default=".openclaw/business_ops/ledger.sqlite", help="Path to SQLite DB")
    parser.add_argument("--fact-id", required=True, help="Fact ID to check")
    parser.add_argument("--packet", action="store_true", help="Generate final LLM truth packet")
    parser.add_argument("--allow-reconciliation", action="store_true", help="Allow mechanical metadata repairs")
    parser.add_argument("--question", help="Question associated with the packet")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if args.packet:
        result = build_llm_truth_packet(args.db, args.fact_id, args.question, allow_reconciliation=args.allow_reconciliation)
    else:
        result = check_fact_source_integrity(args.db, args.fact_id)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if args.packet:
            print(f"Status: {result['status']}")
            print(f"State: {result['state']}")
            print(f"Transitions: {' -> '.join(result['transitions'])}")
            if result['status'] == MODEL_BLOCKED:
                print(f"Block Reason: {result['block_reason']}")
            else:
                for f in result['verified_facts']:
                    print(f"\nFact ID: {f['id']}")
                    print(f"Labels: {f['labels']}")
                    print(f"Text: {f['text']}")
        else:
            print(f"Status: {result['status']}")
            print(f"State: {result['state']}")
            print(f"Fact ID: {result['fact_id']}")
            print(f"Source File: {result['source_file']}")
            if result['status'] == "BLOCK":
                print(f"Block Reason: {result['block_reason']}")
                if result.get("repairable"):
                    print("Status is REPAIRABLE with --allow-reconciliation")
                else:
                    print("Status is INVALIDATABLE with --allow-reconciliation")
            else:
                print("Integrity check PASSED.")
