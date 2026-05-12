import argparse
import json
import sys
import os
from business_ops_ledger import (
    get_file_inventory_by_root,
    get_file_inventory_by_extension,
    get_file_inventory_by_name
)

def main():
    parser = argparse.ArgumentParser(description="Query File Inventory Ledger")
    parser.add_argument("--db", required=True, help="Path to the SQLite ledger database")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--root-id", help="Filter by root ID")
    group.add_argument("--extension", help="Filter by file extension")
    group.add_argument("--file-name", help="Filter by file name")

    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"Error: Database not found at {args.db}", file=sys.stderr)
        sys.exit(1)

    results = []
    if args.root_id:
        results = get_file_inventory_by_root(args.root_id, args.db)
    elif args.extension:
        results = get_file_inventory_by_extension(args.extension, args.db)
    elif args.file_name:
        results = get_file_inventory_by_name(args.file_name, args.db)

    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
