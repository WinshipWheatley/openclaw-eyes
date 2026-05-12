import argparse
import sqlite3
import os
import sys

def run_report(db_path, truth_status=None, source=None, verification_required=None):
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = "SELECT * FROM canonical_facts WHERE 1=1"
    params = []
    if truth_status:
        query += " AND truth_status = ?"
        params.append(truth_status)
    if source:
        query += " AND source_file = ?"
        params.append(source)
    if verification_required is not None:
        query += " AND verification_required = ?"
        params.append(1 if verification_required else 0)

    try:
        facts = cursor.execute(query, params).fetchall()
    except sqlite3.OperationalError as e:
        print(f"Error querying database: {e}")
        conn.close()
        return

    if not facts:
        print("No canonical facts found matching the criteria.")
        conn.close()
        return

    print("Canonical Fact Truth Report")
    print("===========================")
    print(f"Total facts: {len(facts)}")
    
    # Counts
    status_counts = {}
    ver_counts = {0: 0, 1: 0}
    source_counts = {}
    
    for fact in facts:
        st = fact['truth_status'] or "None"
        status_counts[st] = status_counts.get(st, 0) + 1

        vr = 1 if fact['verification_required'] else 0
        ver_counts[vr] = ver_counts.get(vr, 0) + 1

        sf = fact['source_file']
        source_counts[sf] = source_counts.get(sf, 0) + 1

    print("\nCount by truth_status:")
    for s, c in sorted(status_counts.items()):
        print(f"  {s}: {c}")

    print("\nCount by verification_required:")
    for v, c in sorted(ver_counts.items()):
        print(f"  {bool(v)}: {c}")

    print("\nCount by source_file:")
    for s, c in sorted(source_counts.items()):
        print(f"  {s}: {c}")

    print("\nFact Listing:")
    for f in facts:
        print(f"  - ID: {f['fact_id']} | Source: {f['source_file']} | Section: {f['section_heading']} | Status: {f['truth_status']} | SourceID: {f['truth_source_id']} | VerRequired: {bool(f['verification_required'])} | EvidenceID: {f['verification_evidence_id']}")

    print("\nBoundary note: Truth status describes verification posture, not runtime authority.")
    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Canonical Fact Truth Report")
    parser.add_argument("--db", required=True, help="Path to SQLite DB")
    parser.add_argument("--truth-status", help="Filter by truth status")
    parser.add_argument("--source", help="Filter by source file")
    parser.add_argument("--verification-required", action="store_true", help="Filter for facts that require verification")
    args = parser.parse_args()

    # If the flag is not provided, we don't want to filter by it.
    # If it is provided, we want verification_required=1.
    ver_req = 1 if args.verification_required else None

    run_report(args.db, args.truth_status, args.source, ver_req)
