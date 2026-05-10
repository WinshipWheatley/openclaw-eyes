#!/usr/bin/env python3
"""
Proof Coverage Audit v0
Compares Expected Proof Manifest against actual ledger receipts.
"""

import sqlite3
import json
import argparse
import sys
import os
import re
import subprocess
from datetime import datetime
from typing import List, Dict, Any, Optional

DEFAULT_DB_PATH = ".openclaw/business_ops/ledger.sqlite"
MANIFEST_PATH = "docs/operations/OPENCLAW_EXPECTED_PROOF_MANIFEST_V0.md"

def get_connection(db_path: str):
    if not os.path.exists(db_path):
        # Return a dummy connection or handle it
        raise FileNotFoundError(f"Ledger database not found at: {db_path}")
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)

def get_current_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()[:8]
    except Exception:
        return "unknown"

def parse_manifest(path: str) -> List[Dict[str, str]]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Manifest not found at: {path}")
    
    with open(path, 'r') as f:
        content = f.read()
    
    # Simple table parser for v0
    # Looking for: | Label | Command | Evidence Class | Supported Surface |
    # And then rows like: | `label` | `command` | ...
    
    lines = content.splitlines()
    table_started = False
    proofs = []
    
    for line in lines:
        if "| Label | Command |" in line:
            table_started = True
            continue
        if table_started:
            if "|" not in line or "---" in line:
                if proofs: # Already found some, table ended
                    break
                continue
            
            # Row: | `label` | `command` | ...
            cols = [c.strip() for c in line.split("|") if c.strip()]
            if len(cols) >= 2:
                label = cols[0].strip("`")
                command = cols[1].strip("`")
                proofs.append({"label": label, "command": command})
    
    if not proofs:
        raise ValueError(f"Could not parse any proof labels from manifest at {path}")
    
    return proofs

def parse_receipt_summary(summary: str) -> Dict[str, Any]:
    # Standard format: [PASS|FAIL] [label] exit=[N] head=[HASH] dirty=[bool]
    # Example: PASS generated_status_check exit=0 head=0f781b4 dirty=false
    
    parts = summary.split()
    if len(parts) < 2:
        return {"status": "UNKNOWN", "label": "unknown"}
    
    res = {
        "status": parts[0],
        "label": parts[1],
        "exit": "unknown",
        "head": "unknown",
        "dirty": "unknown"
    }
    
    for part in parts[2:]:
        if "=" in part:
            k, v = part.split("=", 1)
            res[k] = v
            
    return res

def get_latest_receipts(conn: sqlite3.Connection, labels: List[str]) -> Dict[str, Dict[str, Any]]:
    cursor = conn.cursor()
    receipts = {}
    
    for label in labels:
        # We need to find the latest event of type test_proof_receipt that mentions this label in summary
        # Since the summary starts with status and label, we can search for "% label %"
        query = """
            SELECT ts, operator_visible_summary 
            FROM events 
            WHERE event_type = 'test_proof_receipt' 
              AND operator_visible_summary LIKE ?
            ORDER BY ts DESC LIMIT 1
        """
        cursor.execute(query, (f"% {label} %",))
        row = cursor.fetchone()
        if row:
            ts, summary = row
            parsed = parse_receipt_summary(summary)
            # Verify the label matches exactly (in case of partial matches)
            if parsed["label"] == label:
                receipts[label] = {
                    "ts": ts,
                    "summary": summary,
                    "parsed": parsed
                }
    
    return receipts

SAFE_GENERATED_FILES = [
    "Operator/GENERATED_CURRENT_STATE.md",
    "Operator/GENERATED_NEXT_ACTIONS.md"
]

def is_safe_drift(proof_head: str, current_head: str) -> bool:
    if proof_head == "unknown" or current_head == "unknown":
        return False
    try:
        # Get names of files changed between proof_head and current_head
        diff_output = subprocess.check_output(
            ["git", "diff", "--name-only", f"{proof_head}..{current_head}"],
            text=True
        ).strip()
        if not diff_output:
            return True # No changes is definitely safe (should have been MATCH though)
        
        changed_files = diff_output.splitlines()
        for f in changed_files:
            if f not in SAFE_GENERATED_FILES:
                return False
        return True
    except Exception:
        return False

def audit_coverage(manifest_proofs: List[Dict[str, str]], receipts: Dict[str, Dict[str, Any]], current_head: str) -> List[Dict[str, Any]]:
    results = []
    for p in manifest_proofs:
        label = p["label"]
        command = p["command"]
        receipt = receipts.get(label)
        
        res = {
            "label": label,
            "command": command,
            "ts": None,
            "status": "MISSING",
            "relation": "UNKNOWN",
            "repo": "UNKNOWN",
            "signal": "MISSING"
        }
        
        if receipt:
            parsed = receipt["parsed"]
            res["ts"] = receipt["ts"]
            res["status"] = parsed["status"]
            res["head"] = parsed["head"]
            
            # Relation (MATCH/DRIFT)
            if parsed["head"] == current_head:
                res["relation"] = "MATCH"
            else:
                res["relation"] = "DRIFT"
            
            # Repo (CLEAN/DIRTY)
            if parsed["dirty"] == "false":
                res["repo"] = "CLEAN"
            elif parsed["dirty"] == "true":
                res["repo"] = "DIRTY"
            
            # Signal
            if res["status"] == "FAIL":
                res["signal"] = "FAILING"
            elif res["status"] == "PASS":
                if res["relation"] == "MATCH" and res["repo"] == "CLEAN":
                    res["signal"] = "CONFIRMED"
                elif res["relation"] == "DRIFT" and res["repo"] == "CLEAN" and is_safe_drift(parsed["head"], current_head):
                    res["signal"] = "CONFIRMED*" # Safe drift
                else:
                    res["signal"] = "WEAK"
        
        results.append(res)
    
    return results

def print_table(results: List[Dict[str, Any]], current_head: str):
    print("=== Proof Coverage Audit v0 ===")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Current Head: {current_head}")
    print("")
    
    header = f"{'Label':<30} {'Status':<8} {'Relation':<10} {'Repo':<8} {'Signal':<12}"
    print(header)
    print("-" * len(header))
    
    for r in results:
        print(f"{r['label']:<30} {r['status']:<8} {r['relation']:<10} {r['repo']:<8} {r['signal']:<12}")
    
    print("\nSignal Legend:")
    print("  CONFIRMED   : PASS + MATCH + CLEAN")
    print("  CONFIRMED*  : PASS + DRIFT (Safe read-model refresh only) + CLEAN")
    print("  WEAK        : PASS but DRIFT (unsafe) or DIRTY")
    print("  FAILING     : FAIL")
    print("  MISSING     : No receipt found")
    print("\nNote: Proof coverage audits expected receipts only. It does not claim whole-system health.")

def main():
    parser = argparse.ArgumentParser(description="Audit Proof Coverage")
    parser.add_argument("--db", help="Path to the ledger database")
    parser.add_argument("--check", action="store_true", help="Exit nonzero if any proof is MISSING, FAILING, or WEAK")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    
    args = parser.parse_args()
    
    db_path = args.db or os.environ.get("OPENCLAW_LEDGER_PATH", DEFAULT_DB_PATH)
    current_head = get_current_head()
    
    try:
        manifest_proofs = parse_manifest(MANIFEST_PATH)
        labels = [p["label"] for p in manifest_proofs]
        
        try:
            conn = get_connection(db_path)
            receipts = get_latest_receipts(conn, labels)
            conn.close()
        except FileNotFoundError:
            receipts = {}
            
        results = audit_coverage(manifest_proofs, receipts, current_head)
        
        if args.json:
            print(json.dumps({"current_head": current_head, "results": results}, indent=2))
        else:
            print_table(results, current_head)
            
        if args.check:
            # Check for MISSING, FAILING, or WEAK
            # CONFIRMED and CONFIRMED* are allowed
            failed = [r for r in results if r["signal"] in ("MISSING", "FAILING", "WEAK")]
            if failed:
                if not args.json:
                    print(f"\nCHECK FAILED: {len(failed)} proof(s) missing, failing, or weak.", file=sys.stderr)
                sys.exit(1)


    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
