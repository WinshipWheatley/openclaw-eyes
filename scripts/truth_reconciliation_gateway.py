import argparse
import sqlite3
import os
import sys
import hashlib
import json
from typing import Any, Dict

# Attempt to import SOURCE_REGISTRY
sys.path.append(os.getcwd())
try:
    from scripts.ingest_canonical_docs import SOURCE_REGISTRY
except ImportError:
    SOURCE_REGISTRY = {}

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
        "block_reason": None
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

        # 3. Alignment Checks
        if fact_row["source_file"] != reg_row["observed_path"]:
            result["block_reason"] = f"Alignment mismatch: fact source_file '{fact_row['source_file']}' vs registry observed_path '{reg_row['observed_path']}'"
            conn.close()
            return result

        if fact_row["source_file"] not in SOURCE_REGISTRY:
            result["block_reason"] = f"Source file not in SOURCE_REGISTRY: {fact_row['source_file']}"
            conn.close()
            return result

        if reg_row["hash_status"] != "current":
            result["state"] = "DIFF_FOUND"
            result["block_reason"] = f"Registry hash_status is '{reg_row['hash_status']}', expected 'current'"
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

        # All checks passed
        result["status"] = "PASS"
        result["state"] = "NO_DIFF_FOUND"
        conn.close()
        return result

    except Exception as e:
        result["block_reason"] = f"Internal error: {str(e)}"
        return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Truth Reconciliation Gateway - Chunk 1 JIT Integrity")
    parser.add_argument("--db", default=".openclaw/business_ops/ledger.sqlite", help="Path to SQLite DB")
    parser.add_argument("--fact-id", required=True, help="Fact ID to check")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    check_result = check_fact_source_integrity(args.db, args.fact_id)

    if args.json:
        print(json.dumps(check_result, indent=2))
    else:
        print(f"Status: {check_result['status']}")
        print(f"State: {check_result['state']}")
        print(f"Fact ID: {check_result['fact_id']}")
        print(f"Source File: {check_result['source_file']}")
        if check_result['status'] == "BLOCK":
            print(f"Block Reason: {check_result['block_reason']}")
        else:
            print("Integrity check PASSED.")
