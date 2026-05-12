import argparse
import json
import sys
import os
from business_ops_ledger import get_canonical_facts_by_source, get_canonical_facts_by_heading

def main():
    parser = argparse.ArgumentParser(description="Query canonical facts from SQLite ledger.")
    parser.add_argument("--db", required=True, help="Path to the SQLite database file.")
    parser.add_argument("--source", help="Source file filter.")
    parser.add_argument("--heading", help="Section heading filter.")
    
    args = parser.parse_args()

    if not args.source and not args.heading:
        print(json.dumps({"error": "Must provide --source or --heading filter."}))
        sys.exit(1)

    if not os.path.exists(args.db):
        print(json.dumps({"error": f"Database file not found: {args.db}"}))
        sys.exit(1)

    try:
        if args.source:
            results = get_canonical_facts_by_source(args.source, args.db)
        else:
            results = get_canonical_facts_by_heading(args.heading, args.db)
        
        print(json.dumps(results, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
