
import argparse
import sys
import subprocess
import os
from scripts.extract_canonical_facts import extract_markdown_sections
from business_ops_ledger import record_canonical_fact, init_business_ops_ledger

ALLOWED_SOURCES = [
    "docs/operations/OPENCLAW_RECEIPT_SPINE_CHECKPOINT_V9.md",
    "docs/operations/OPENCLAW_KNOWLEDGE_INGESTION_CHECKPOINT_V2.md",
    "docs/operations/OPENCLAW_PACKET_TO_RECEIPT_MAPPING_V0.md"
]

def main():
    parser = argparse.ArgumentParser(description="Ingest a single canonical doc.")
    parser.add_argument("--db", required=True, help="Path to SQLite ledger")
    parser.add_argument("--source", required=True, help="Path to source file")
    args = parser.parse_args()

    if args.source not in ALLOWED_SOURCES:
        print(f"Error: Source '{args.source}' is not allowed. Permitted sources: {ALLOWED_SOURCES}")
        sys.exit(1)

    if not os.path.exists(args.source):
        print(f"Error: Source file '{args.source}' not found.")
        sys.exit(1)

    # Get Git HEAD
    try:
        git_head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception as e:
        print(f"Error: Could not get git HEAD: {e}")
        sys.exit(1)

    # Read file
    with open(args.source, "r") as f:
        content = f.read()

    # Extract
    facts = extract_markdown_sections(content, args.source, git_head)

    # Ingest
    init_business_ops_ledger(args.db)
    for fact in facts:
        fact_id = f"fact_{fact['content_hash'][:8]}"
        record_canonical_fact(
            fact_id=fact_id,
            source_file=fact['source_file'],
            section_heading=fact['section_heading'],
            source_commit=fact['source_commit'],
            fact_text=fact['fact_text'],
            sensitivity_class=fact['sensitivity_class'],
            allowed_actors=fact['allowed_actors'],
            db_path=args.db
        )
    print(f"Successfully ingested {len(facts)} facts from {args.source}")

if __name__ == "__main__":
    main()
