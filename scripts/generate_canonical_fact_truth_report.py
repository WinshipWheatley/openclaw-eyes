import argparse
import sqlite3
import sys

def run_report(db_path, truth_status=None, source=None, verification_required=None):
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

    facts = cursor.execute(query, params).fetchall()

    if not facts:
        print("No canonical facts found matching the criteria.")
        return

    print("Canonical Fact Truth Report")
    print("===========================")
    print(f"Total facts: {len(facts)}")
    
    # Counts
    status_counts = {}
    ver_counts = {0: 0, 1: 0}
    source_counts = {}
    
    for fact in facts:
        status_counts[fact['truth_status']] = status_counts.get(fact['truth_status'], 0) + 1
        ver_counts[fact['verification_required']] = ver_counts.get(fact['verification_required'], 0) + 1
        source_counts[fact['source_file']] = source_counts.get(fact['source_file'], 0) + 1
    
    print("\nCount by truth_status:")
    for s, c in status_counts.items():
        print(f"  {s}: {c}")
        
    print("\nCount by verification_required:")
    for v, c in ver_counts.items():
        print(f"  {bool(v)}: {c}")
        
    print("\nCount by source_file:")
    for s, c in source_counts.items():
        print(f"  {s}: {c}")

    print("\nFact Listing:")
    # Group by source_file and section_heading
    grouped = {}
    for fact in facts:
        key = (fact['source_file'], fact['section_heading'])
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(fact)
    
    for (sf, sh), fs in grouped.items():
        print(f"\nSource: {sf} | Section: {sh}")
        for f in fs:
            print(f"  - ID: {f['fact_id']} | Status: {f['truth_status']} | SourceID: {f['truth_source_id']} | VerRequired: {bool(f['verification_required'])} | EvidenceID: {f['verification_evidence_id']}")

    print("\nBoundary note: Truth status describes verification posture, not runtime authority.")
    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Canonical Fact Truth Report")
    parser.add_argument("--db", required=True, help="Path to SQLite DB")
    parser.add_argument("--truth-status", help="Filter by truth status")
    parser.add_argument("--source", help="Filter by source file")
    parser.add_argument("--verification-required", action="store_true", help="Filter by verification required")
    args = parser.parse_args()
    
    run_report(args.db, args.truth_status, args.source, args.verification_required)
