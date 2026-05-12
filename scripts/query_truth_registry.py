import argparse
import json
import sys
from business_ops_ledger import (
    get_truth_registry_entry,
    get_truth_registry_entries_by_status,
    get_truth_registry_entries_by_approval_status,
    get_truth_registry_entries_by_doc_type,
    get_truth_registry_entries_requiring_verification
)

def main():
    parser = argparse.ArgumentParser(description="Query Canonical Truth Registry")
    parser.add_argument("--db", required=True, help="Path to ledger DB")
    parser.add_argument("--truth-status")
    parser.add_argument("--approval-status")
    parser.add_argument("--doc-type")
    parser.add_argument("--requires-verification", action="store_true")
    parser.add_argument("--source-id")
    args = parser.parse_args()

    if not any([args.truth_status, args.approval_status, args.doc_type, args.requires_verification, args.source_id]):
        parser.error("At least one filter is required")

    data = []
    if args.source_id:
        entry = get_truth_registry_entry(args.source_id, db_path=args.db)
        if entry:
            data = [entry]
    elif args.truth_status:
        data = get_truth_registry_entries_by_status(args.truth_status, db_path=args.db)
    elif args.approval_status:
        data = get_truth_registry_entries_by_approval_status(args.approval_status, db_path=args.db)
    elif args.doc_type:
        data = get_truth_registry_entries_by_doc_type(args.doc_type, db_path=args.db)
    elif args.requires_verification:
        data = get_truth_registry_entries_requiring_verification(db_path=args.db)

    print(json.dumps(data, indent=2))

if __name__ == "__main__":
    main()
