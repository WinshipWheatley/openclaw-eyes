import argparse
import sys
import os
import json

# Add current directory to sys.path to allow imports
sys.path.append(os.getcwd())

try:
    from scripts.answer_harness import answer_operator_question
except ImportError:
    # Fallback if running from within scripts directory
    sys.path.append(os.path.join(os.getcwd(), ".."))
    from answer_harness import answer_operator_question

def main():
    parser = argparse.ArgumentParser(description="Human-facing operator truth query wrapper.")
    parser.add_argument("question", help="The question to ask.")
    parser.add_argument("--db", default=".openclaw/business_ops/ledger.sqlite", help="Path to the SQLite database.")
    parser.add_argument("--record-receipt", action="store_true", help="Opt-in: Record truth decision receipt to ledger.")
    parser.add_argument("--receipt-db-path", help="Path to the database for recording receipts.")
    parser.add_argument("--allow-reconciliation", action="store_true", help="Allow mechanical metadata repairs during query.")

    args = parser.parse_args()

    # Call answer_harness
    result = answer_operator_question(
        args.db,
        args.question,
        allow_reconciliation=args.allow_reconciliation,
        record_receipt=args.record_receipt,
        receipt_db_path=args.receipt_db_path
    )

    # Print concise operator-readable response
    print("\n" + "="*40)
    print(f"OPERATOR TRUTH QUERY: {args.question}")
    print("="*40)

    status = result.get("status", "UNKNOWN")
    print(f"Status: {status}")

    if status == "SUCCESS":
        print("\nAnswer:")
        print("-" * 20)
        print(result.get("answer"))
    elif status == "REFUSED":
        print(f"\nQuery Refused: {result.get('answer')}")
    elif status == "MODEL_BLOCKED":
        print(f"\nQuery Blocked: {result.get('answer')}")
    else:
        print(f"\nStatus: {status}")
        print(f"Detail: {result.get('answer')}")

    summary = result.get("truth_summary")
    if summary:
        print("\nTruth Summary Metadata:")
        print(f"  - Allowed Candidates:   {summary.get('allowed_candidate_count', 0)}")
        print(f"  - Uncertain Candidates: {summary.get('uncertain_candidate_count', 0)}")
        print(f"  - Blocked Candidates:   {summary.get('blocked_candidate_count', 0)}")
        
        reasons = summary.get("blocked_reasons", [])
        if reasons:
            print(f"  - Blocked Reasons: {len(reasons)} fact(s) blocked.")
            # Summarize reasons if there are many, or just list them if few
            unique_reasons = set(r["reason"] for r in reasons)
            for r in unique_reasons:
                print(f"    - {r}")

        boundary_crossed = summary.get("omitted_blocked_candidates_did_not_cross_boundary", False)
        print(f"  - Omitted blocked candidates did NOT cross boundary: {boundary_crossed}")

    boundary = result.get("answer_boundary")
    if boundary:
        print(f"\nBoundary: {boundary}")

    authority = result.get("runtime_authority", False)
    print(f"Runtime Authority: {authority}")
    print("\nNon-authorizing Statement: Truth status describes candidate verification posture, not live runtime health, agent authority, or terminal gateway decisions.")
    print("="*40 + "\n")

if __name__ == "__main__":
    main()
