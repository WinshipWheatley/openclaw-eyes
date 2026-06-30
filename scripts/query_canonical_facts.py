import argparse
import json
import sys
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from business_ops_ledger import (
    get_canonical_facts_by_heading,
    get_canonical_facts_by_source,
    resolve_business_ops_ledger_path,
)

def main():
    parser = argparse.ArgumentParser(description="Query canonical facts from SQLite ledger.")
    parser.add_argument("--db", required=True, help="Path to the SQLite database file.")
    parser.add_argument("--source", help="Source file filter.")
    parser.add_argument("--heading", help="Section heading filter.")
    
    args = parser.parse_args()

    if not args.source and not args.heading:
        print(json.dumps({"error": "Must provide --source or --heading filter."}))
        sys.exit(1)

    db_path = resolve_business_ops_ledger_path(args.db)
    if not os.path.exists(db_path):
        print(json.dumps({"error": f"Database file not found: {args.db}"}))
        sys.exit(1)

    try:
        if args.source:
            results = get_canonical_facts_by_source(args.source, db_path)
        else:
            results = get_canonical_facts_by_heading(args.heading, db_path)
        
        print(json.dumps(results, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
