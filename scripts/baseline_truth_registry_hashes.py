import argparse
import sys
import os
import hashlib
import sqlite3
from datetime import datetime, timezone
from scripts.ingest_canonical_docs import SOURCE_REGISTRY
from business_ops_ledger import _query_truth_registry, _execute_write

def compute_sha256(filepath):
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

def main():
    parser = argparse.ArgumentParser(description="Baseline truth registry hashes for SOURCE_REGISTRY entries.")
    parser.add_argument("--db", required=True, help="Path to SQLite ledger")
    parser.add_argument("--allow-hashing", action="store_true", help="Explicitly allow reading bytes and hashing")
    parser.add_argument("--dry-run", action="store_true", help="Do not write to database")
    parser.add_argument("--source", help="Optional specific SOURCE_REGISTRY file to baseline")

    args = parser.parse_args()

    if not args.allow_hashing and not args.dry_run:
        print("Error: --allow-hashing is required to compute hashes, unless --dry-run is used to list planned candidates.")
        sys.exit(1)

    sources_to_check = []
    if args.source:
        if args.source not in SOURCE_REGISTRY:
            print(f"Error: Source '{args.source}' is not in SOURCE_REGISTRY.")
            sys.exit(1)
        sources_to_check = [args.source]
    else:
        sources_to_check = list(SOURCE_REGISTRY.keys())

    for source_path in sources_to_check:
        # Find matching row
        rows = _query_truth_registry("SELECT * FROM truth_registry_entries WHERE observed_path = ?", (source_path,), args.db)
        if not rows:
            print(f"[{source_path}] missing: No truth_registry_entries row found.")
            continue
        
        row = rows[0]
        hash_status = row.get('hash_status', 'not_recorded')
        existing_hash = row.get('source_content_hash')

        if not args.allow_hashing:
            print(f"[{source_path}] planned_candidate: Would check hash (requires --allow-hashing). Current status: {hash_status}")
            continue

        if not os.path.exists(source_path):
            print(f"[{source_path}] missing_file: File does not exist on disk.")
            continue

        current_hash = compute_sha256(source_path)

        if hash_status in ('not_recorded', 'unknown') or existing_hash is None:
            if args.dry_run:
                print(f"[{source_path}] dry_run: Would update baseline hash (status: {hash_status} -> current)")
            else:
                now = datetime.now(timezone.utc).isoformat()
                success = _execute_write(
                    """
                    UPDATE truth_registry_entries 
                    SET source_content_hash = ?, 
                        hash_algorithm = 'sha256', 
                        hash_recorded_at = ?, 
                        hash_status = 'current' 
                    WHERE source_id = ?
                    """,
                    (current_hash, now, row['source_id']),
                    args.db
                )
                if success:
                    print(f"[{source_path}] baseline_applied: Hash recorded (status: current)")
                else:
                    print(f"[{source_path}] error: Failed to update database.")
        else:
            if current_hash == existing_hash:
                print(f"[{source_path}] current: Hash matches baseline.")
                # Ensure status is current if it was unknown but hash matched
                if hash_status != 'current' and not args.dry_run:
                    _execute_write("UPDATE truth_registry_entries SET hash_status = 'current' WHERE source_id = ?", (row['source_id'],), args.db)
            else:
                print(f"[{source_path}] changed_detected_not_applied: Content hash differs from baseline.")

if __name__ == "__main__":
    main()
