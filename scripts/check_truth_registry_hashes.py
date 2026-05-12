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
    parser = argparse.ArgumentParser(description="Check truth registry hashes and optionally invalidate stale entries.")
    parser.add_argument("--db", required=True, help="Path to SQLite ledger")
    parser.add_argument("--allow-hashing", action="store_true", help="Explicitly allow reading bytes and hashing")
    parser.add_argument("--apply", action="store_true", help="Apply invalidations to the database")
    parser.add_argument("--dry-run", action="store_true", help="Synonym for not using --apply (informative only)")
    parser.add_argument("--source", help="Optional specific SOURCE_REGISTRY file to check")

    args = parser.parse_args()

    if not args.allow_hashing:
        sys.stderr.write("Error: --allow-hashing is required to compute hashes.\n")
        sys.exit(1)

    sources_to_check = []
    if args.source:
        if args.source not in SOURCE_REGISTRY:
            sys.stderr.write(f"Error: Source '{args.source}' is not in SOURCE_REGISTRY.\n")
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
        truth_status = row.get('truth_status')

        if not os.path.exists(source_path):
            print(f"[{source_path}] missing_file: File does not exist on disk.")
            continue

        if existing_hash is None or hash_status in ('not_recorded', 'unknown'):
            print(f"[{source_path}] no_baseline: No baseline hash recorded in registry.")
            continue

        current_hash = compute_sha256(source_path)

        if current_hash == existing_hash:
            print(f"[{source_path}] current: Hash matches baseline.")
            if args.apply and hash_status != 'current':
                _execute_write("UPDATE truth_registry_entries SET hash_status = 'current' WHERE source_id = ?", (row['source_id'],), args.db)
        else:
            if not args.apply:
                print(f"[{source_path}] would_invalidate: Content hash differs from baseline ({current_hash[:8]} vs {existing_hash[:8]}).")
            else:
                now = datetime.now(timezone.utc).isoformat()
                new_truth_status = truth_status
                if truth_status in ('test_verified', 'runtime_verified'):
                    new_truth_status = 'stale_possible'
                
                reason = f"content hash mismatch: current={current_hash}"
                
                success = _execute_write(
                    """
                    UPDATE truth_registry_entries 
                    SET hash_status = 'changed',
                        verification_invalidated_at = ?,
                        invalidation_reason = ?,
                        verification_required = 1,
                        truth_status = ?
                    WHERE source_id = ?
                    """,
                    (now, reason, new_truth_status, row['source_id']),
                    args.db
                )
                if success:
                    status_msg = f" (downgraded to {new_truth_status})" if new_truth_status != truth_status else ""
                    print(f"[{source_path}] invalidated: Hash mismatch detected. Status updated to 'changed'{status_msg}.")
                else:
                    print(f"[{source_path}] error: Failed to update database.")

if __name__ == "__main__":
    main()
