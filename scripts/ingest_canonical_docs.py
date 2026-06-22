
import argparse
import sys
import subprocess
import os
from scripts.extract_canonical_facts import extract_markdown_sections
from business_ops_ledger import init_business_ops_ledger, _query_truth_registry
from canonical_fact_ingest import ingest_graded_fact

# ---------------------------------------------------------------------------
# Original 9 allow-listed sources (unchanged)
# ---------------------------------------------------------------------------
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
    },

    # ---------------------------------------------------------------------------
    # Extended sources (operator requirement: shared doctrine, allowed_actors=all)
    # ---------------------------------------------------------------------------
    "OPENCLAW_RUNTIME.md": {
        "doc_category": "runtime_doctrine",
        "sensitivity_class": "public_canonical",
        "allowed_actors": ["cassandra", "chief", "guardian", "hermes", "niles", "gemini", "all"],
        "temporal_or_doctrine": "doctrine_reference",
        "description": "OpenClaw canonical runtime law — shared doctrine for all agents"
    },
    "CORE_ARCHITECTURE_PRINCIPLES.md": {
        "doc_category": "architecture_doctrine",
        "sensitivity_class": "public_canonical",
        "allowed_actors": ["cassandra", "chief", "guardian", "hermes", "niles", "gemini", "all"],
        "temporal_or_doctrine": "doctrine_reference",
        "description": "Core architecture principles — shared doctrine for all agents"
    },
    "AGENTS.md": {
        "doc_category": "agent_rules_doctrine",
        "sensitivity_class": "public_canonical",
        "allowed_actors": ["cassandra", "chief", "guardian", "hermes", "niles", "gemini", "all"],
        "temporal_or_doctrine": "doctrine_reference",
        "description": "AGENTS adapter — canonical runtime law pointer for all agents"
    },
    "OPEN_CLAW_MANIFEST.md": {
        "doc_category": "manifest_doctrine",
        "sensitivity_class": "public_canonical",
        "allowed_actors": ["cassandra", "chief", "guardian", "hermes", "niles", "gemini", "all"],
        "temporal_or_doctrine": "doctrine_reference",
        "description": "OpenClaw manifest — shared doctrine and purpose declaration"
    },
}


def _build_fact_record(fact: dict, metadata: dict, truth_entry: dict | None) -> dict:
    """Assemble the full record dict for ingest_graded_fact."""
    record = {
        "source_file": fact["source_file"],
        "section_heading": fact["section_heading"],
        "source_commit": fact["source_commit"],
        "fact_text": fact["fact_text"],
        "sensitivity_class": metadata["sensitivity_class"],
        "allowed_actors": metadata["allowed_actors"],
        "doc_category": metadata.get("doc_category"),
        "temporal_or_doctrine": metadata.get("temporal_or_doctrine"),
        "source_description": metadata.get("description"),
        "truth_source_id": None,
        "truth_status": "declared",
        "verification_required": 1,
        "verification_evidence_id": None,
    }

    if truth_entry:
        hash_status = truth_entry.get("hash_status") or "not_recorded"
        truth_status = truth_entry["truth_status"]
        verification_required = truth_entry["verification_required"]
        verification_evidence_id = truth_entry.get("verification_evidence_id")

        if hash_status == "changed":
            truth_status = "stale_possible"
            verification_required = 1
        elif hash_status != "current":
            if truth_status in ("test_verified", "runtime_verified"):
                truth_status = "stale_possible"
                verification_required = 1

        record.update({
            "truth_source_id": truth_entry["source_id"],
            "truth_status": truth_status,
            "verification_required": verification_required,
            "verification_evidence_id": verification_evidence_id,
        })

    return record


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

    # Extract sections
    facts = extract_markdown_sections(content, args.source, git_head)

    # Init ledger + try to find truth registry entry
    init_business_ops_ledger(args.db)

    truth_entry = None
    registry_data = _query_truth_registry(
        "SELECT * FROM truth_registry_entries WHERE observed_path = ?",
        (args.source,),
        args.db,
    )
    if registry_data:
        truth_entry = registry_data[0]

    inserted = 0
    skipped = 0
    for fact in facts:
        record = _build_fact_record(fact, metadata, truth_entry)
        result = ingest_graded_fact(record, db_path=args.db)
        if result["status"] == "inserted":
            inserted += 1
        else:
            skipped += 1

    print(
        f"Successfully processed {len(facts)} facts from {args.source}: "
        f"{inserted} inserted, {skipped} skipped (deduped)."
    )


if __name__ == "__main__":
    main()
