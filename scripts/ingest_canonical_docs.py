
import argparse
import sys
import subprocess
import os
from scripts.extract_canonical_facts import extract_markdown_sections
from business_ops_ledger import record_canonical_fact, init_business_ops_ledger

SOURCE_REGISTRY = {
    "docs/operations/OPENCLAW_RECEIPT_SPINE_CHECKPOINT_V9.md": {
        "doc_category": "receipt_spine_checkpoint",
        "sensitivity_class": "operational_canonical",
        "allowed_actors": ["cassandra", "chief", "guardian", "hermes"],
        "temporal_or_doctrine": "temporal_checkpoint",
        "description": "Checkpoint for receipt spine status"
    },
    "docs/operations/OPENCLAW_KNOWLEDGE_INGESTION_CHECKPOINT_V2.md": {
        "doc_category": "knowledge_ingestion_checkpoint",
        "sensitivity_class": "operational_canonical",
        "allowed_actors": ["cassandra", "chief", "guardian", "hermes"],
        "temporal_or_doctrine": "temporal_checkpoint",
        "description": "Checkpoint for knowledge ingestion state"
    },
    "docs/operations/OPENCLAW_PACKET_TO_RECEIPT_MAPPING_V0.md": {
        "doc_category": "receipt_mapping",
        "sensitivity_class": "operational_canonical",
        "allowed_actors": ["cassandra", "chief", "guardian", "hermes"],
        "temporal_or_doctrine": "doctrine_reference",
        "description": "Mapping of agent packets to receipt requirements"
    },
    "docs/operations/CASSANDRA_MACHINE_CONTRACT.md": {
        "doc_category": "machine_contract",
        "sensitivity_class": "operational_canonical",
        "allowed_actors": ["cassandra", "chief", "guardian", "hermes"],
        "temporal_or_doctrine": "doctrine_reference",
        "description": "Cassandra agent machine contract"
    },
    "docs/operations/CHIEF_MACHINE_CONTRACT.md": {
        "doc_category": "machine_contract",
        "sensitivity_class": "operational_canonical",
        "allowed_actors": ["chief", "guardian", "hermes"],
        "temporal_or_doctrine": "doctrine_reference",
        "description": "Chief agent machine contract"
    },
    "docs/operations/GUARDIAN_MACHINE_CONTRACT.md": {
        "doc_category": "machine_contract",
        "sensitivity_class": "operational_canonical",
        "allowed_actors": ["guardian", "chief", "hermes"],
        "temporal_or_doctrine": "doctrine_reference",
        "description": "Guardian agent machine contract"
    },
    "docs/operations/HERMES_MACHINE_CONTRACT.md": {
        "doc_category": "machine_contract",
        "sensitivity_class": "operational_canonical",
        "allowed_actors": ["hermes", "chief", "guardian"],
        "temporal_or_doctrine": "doctrine_reference",
        "description": "Hermes agent machine contract"
    },
    "docs/producer/PRODUCER_ARCHETYPE.md": {
        "doc_category": "producer_archetype",
        "sensitivity_class": "operational_canonical",
        "allowed_actors": ["niles", "cassandra", "chief", "hermes"],
        "temporal_or_doctrine": "doctrine_reference",
        "description": "canonical creative/taste archetype for Niles/Producer"
    },
    "docs/producer/PRODUCER_MACHINE_CONTRACT.md": {
        "doc_category": "producer_machine_contract",
        "sensitivity_class": "operational_canonical",
        "allowed_actors": ["niles", "chief", "hermes"],
        "temporal_or_doctrine": "doctrine_reference",
        "description": "machine-readable boundaries and artifact contract for Niles/Producer"
    }
}

def main():
    parser = argparse.ArgumentParser(description="Ingest a single canonical doc.")
    parser.add_argument("--db", required=True, help="Path to SQLite ledger")
    parser.add_argument("--source", required=True, help="Path to source file")
    args = parser.parse_args()

    if args.source not in SOURCE_REGISTRY:
        print(f"Error: Source '{args.source}' is not allowed. Permitted sources: {list(SOURCE_REGISTRY.keys())}")
        sys.exit(1)

    metadata = SOURCE_REGISTRY[args.source]

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
            sensitivity_class=metadata["sensitivity_class"],
            allowed_actors=metadata["allowed_actors"],
            db_path=args.db
        )
    print(f"Successfully ingested {len(facts)} facts from {args.source}")

if __name__ == "__main__":
    main()
