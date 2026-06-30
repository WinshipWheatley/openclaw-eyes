import argparse
import sys
import sqlite3
from pathlib import Path
from scripts.ingest_canonical_docs import SOURCE_REGISTRY

def get_db_connection(db_path):
    """Return a read-only database connection."""
    return sqlite3.connect(f"file:{Path(db_path).as_posix()}?mode=ro", uri=True)

def generate_report(db_path):
    try:
        conn = get_db_connection(db_path)
    except sqlite3.OperationalError as e:
        print(f"Error: Database not found at {db_path}: {e}")
        return False

    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    total_registry_sources = len(SOURCE_REGISTRY)
    present_in_db = 0
    missing_from_db = []
    
    hash_status_counts = {}
    truth_status_counts = {}
    
    unsafe_entries = []
    unbaselined_doctrine_references = []

    for source_path in SOURCE_REGISTRY:
        cursor.execute(
            "SELECT truth_status, hash_status FROM truth_registry_entries WHERE observed_path = ?",
            (source_path,)
        )
        row = cursor.fetchone()
        
        if row:
            present_in_db += 1
            truth_status = row['truth_status']
            hash_status = row['hash_status']
            
            hash_status_counts[hash_status] = hash_status_counts.get(hash_status, 0) + 1
            truth_status_counts[truth_status] = truth_status_counts.get(truth_status, 0) + 1
            
            is_unsafe = False
            reason = ""
            
            # Rule: hash_status=changed is always unsafe
            if hash_status == 'changed':
                is_unsafe = True
                reason = "Hash changed"
            
            # Rule: test_verified/runtime_verified require hash_status=current
            elif truth_status in ('test_verified', 'runtime_verified') and hash_status != 'current':
                is_unsafe = True
                reason = f"Verified status '{truth_status}' with hash status '{hash_status}'"
            
            if is_unsafe:
                unsafe_entries.append((source_path, truth_status, hash_status, reason))
            
            # Rule: doctrine_reference with hash_status=not_recorded is allowed but noted
            if SOURCE_REGISTRY[source_path].get('temporal_or_doctrine') == 'doctrine_reference' and hash_status == 'not_recorded':
                unbaselined_doctrine_references.append(source_path)
                
        else:
            missing_from_db.append(source_path)
            unsafe_entries.append((source_path, "MISSING", "MISSING", "Not in truth registry"))

    # Printing the report
    print("--- TRUTH INGEST READINESS REPORT ---")
    print(f"Total SOURCE_REGISTRY entries: {total_registry_sources}")
    print(f"Entries present in DB:         {present_in_db}")
    print(f"Entries missing from DB:       {len(missing_from_db)}")
    
    print("\nHash Status Counts:")
    if not hash_status_counts:
        print("  (None)")
    for status, count in sorted(hash_status_counts.items()):
        print(f"  {status}: {count}")
        
    print("\nTruth Status Counts:")
    if not truth_status_counts:
        print("  (None)")
    for status, count in sorted(truth_status_counts.items()):
        print(f"  {status}: {count}")

    if unbaselined_doctrine_references:
        print("\nUnbaselined Doctrine References (Allowed but noted):")
        for path in unbaselined_doctrine_references:
            print(f"  {path}")

    if unsafe_entries:
        print("\nUnsafe Entries for Verified Inheritance:")
        for path, ts, hs, reason in unsafe_entries:
            print(f"  {path} (truth={ts}, hash={hs}): {reason}")
    else:
        print("\nNo unsafe entries found.")

    print("\n" + "="*40)
    if unsafe_entries:
        print("RESULT: NOT_READY_FOR_CONTROLLED_INGEST")
        conn.close()
        return False
    else:
        print("RESULT: READY_FOR_CONTROLLED_INGEST")
        conn.close()
        return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Report readiness for controlled ingestion.")
    parser.add_argument("--db", required=True, help="Path to the business ops ledger SQLite database.")
    args = parser.parse_args()
    
    success = generate_report(args.db)
    if not success:
        sys.exit(1)
