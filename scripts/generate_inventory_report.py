import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from business_ops_ledger import resolve_business_ops_ledger_path

def generate_report(db_path, root_id=None):
    resolved_db_path = resolve_business_ops_ledger_path(db_path)

    uri = f"file:{Path(resolved_db_path).as_posix()}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.OperationalError as e:
        print(f"Error: Database not found at {db_path}: {e}", file=sys.stderr)
        return
    cursor = conn.cursor()

    query = "SELECT * FROM file_inventory"
    params = ()
    if root_id:
        query += " WHERE root_id = ?"
        params = (root_id,)
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    columns = [d[0] for d in cursor.description]
    data = [dict(zip(columns, row)) for row in rows]
    conn.close()

    if not data:
        print(f"Inventory Report for {root_id or 'All Roots'}")
        print("No records found.")
        return

    total_files = len(data)
    total_size = sum(r['size_bytes'] for r in data)
    extensions = Counter(r['extension'] for r in data)
    eligibility = Counter(r['ingest_eligibility'] for r in data)
    
    sorted_data = sorted(data, key=lambda x: x['size_bytes'], reverse=True)
    top_10 = sorted_data[:10]
    
    sorted_files = sorted(data, key=lambda x: x['relative_path'])

    print(f"--- Inventory Report for {root_id or 'All Roots'} ---")
    print(f"Total Files: {total_files}")
    print(f"Total Size: {total_size} bytes")
    print("\nFile Counts by Extension:")
    for ext, count in extensions.items():
        print(f"  {ext}: {count}")
    
    print("\nFile Counts by Eligibility:")
    for status, count in eligibility.items():
        print(f"  {status}: {count}")
    
    print("\nTop 10 Largest Files:")
    for f in top_10:
        print(f"  {f['size_bytes']} bytes - {f['relative_path']}")
        
    print("\nFile List:")
    for f in sorted_files:
        print(f"  {f['relative_path']}")

    print("\n[BOUNDARY NOTE: Metadata only. No file contents read. No hashes computed.]")

def main():
    parser = argparse.ArgumentParser(description="Generate Operator Inventory Report")
    parser.add_argument("--db", required=True, help="Path to the SQLite ledger database")
    parser.add_argument("--root-id", help="Filter by root ID")
    args = parser.parse_args()
    generate_report(args.db, args.root_id)

if __name__ == "__main__":
    main()
