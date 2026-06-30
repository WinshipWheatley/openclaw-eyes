
import argparse
import hashlib
import sys
import subprocess
import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.extract_canonical_facts import extract_markdown_sections
from business_ops_ledger import (
    init_business_ops_ledger,
    resolve_business_ops_ledger_path,
    _query_truth_registry,
)
from canonical_fact_ingest import _PRODUCTION_DB_PATH, _init_fts_tables, ingest_graded_fact

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
    # NOTE (populate-1b): CORE_ARCHITECTURE_PRINCIPLES.md, AGENTS.md, and
    # OPEN_CLAW_MANIFEST.md were dropped from the registry — the root copies are
    # gitignored/untracked (absent in a clean checkout) and AGENTS.md is a thin
    # redirect with no parseable sections. Their doctrine is captured, grounded,
    # and verified in canonical_doctrine_facts.py (loaded via load_doctrine_facts).
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


def _is_production_db(db_path: str) -> bool:
    return str(Path(db_path).expanduser().resolve()) == str(Path(_PRODUCTION_DB_PATH).expanduser().resolve())


def replace_stale_doc_section_facts(
    db_path: str,
    *,
    source_file: str,
    section_heading: str,
    new_content_hash: str,
) -> dict:
    """Remove stale doc-ingested rows for one source/section before re-ingest."""
    db_path = resolve_business_ops_ledger_path(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        _init_fts_tables(conn)
        rows = conn.execute(
            """SELECT fact_id, content_hash
               FROM canonical_facts
               WHERE source_file = ?
                 AND section_heading = ?
                 AND content_hash != ?""",
            (source_file, section_heading, new_content_hash),
        ).fetchall()
        stale_hashes = [row["content_hash"] for row in rows]
        stale_fact_ids = [row["fact_id"] for row in rows]
        removed_fts_rows = 0
        removed_queue_rows = 0

        for chash in stale_hashes:
            fts_before = conn.execute(
                "SELECT COUNT(*) FROM fts_canonical_facts WHERE content_hash = ?",
                (chash,),
            ).fetchone()[0]
            queue_before = conn.execute(
                "SELECT COUNT(*) FROM embedding_work_queue WHERE content_hash = ?",
                (chash,),
            ).fetchone()[0]
            conn.execute("DELETE FROM fts_canonical_facts WHERE content_hash = ?", (chash,))
            conn.execute("DELETE FROM embedding_work_queue WHERE content_hash = ?", (chash,))
            removed_fts_rows += int(fts_before)
            removed_queue_rows += int(queue_before)

        if stale_hashes:
            marks = ",".join("?" for _ in stale_hashes)
            conn.execute(f"DELETE FROM canonical_facts WHERE content_hash IN ({marks})", stale_hashes)

        conn.commit()
        return {
            "source_file": source_file,
            "section_heading": section_heading,
            "removed_facts": stale_fact_ids,
            "removed_hashes": stale_hashes,
            "removed_fts_rows": removed_fts_rows,
            "removed_queue_rows": removed_queue_rows,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Ingest a single canonical doc.")
    parser.add_argument("--db", required=True, help="Path to SQLite ledger")
    parser.add_argument("--source", required=True, help="Path to source file")
    parser.add_argument("--confirm", action="store_true", help="Allow a sanctioned production ledger write.")
    args = parser.parse_args()

    if _is_production_db(args.db) and not args.confirm:
        print(
            "SAFETY: production ledger write requires --confirm. "
            f"Operator-pending command: python3 scripts/ingest_canonical_docs.py --db {args.db} "
            f"--source {args.source} --confirm"
        )
        sys.exit(2)
    db_path = resolve_business_ops_ledger_path(args.db)

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
    init_business_ops_ledger(db_path)

    truth_entry = None
    registry_data = _query_truth_registry(
        "SELECT * FROM truth_registry_entries WHERE observed_path = ?",
        (args.source,),
        db_path,
    )
    if registry_data:
        truth_entry = registry_data[0]

    inserted = 0
    skipped = 0
    replaced = 0
    removed_stale_facts = []
    for fact in facts:
        new_content_hash = hashlib.sha256(fact["fact_text"].encode("utf-8")).hexdigest()
        replacement = replace_stale_doc_section_facts(
            db_path,
            source_file=fact["source_file"],
            section_heading=fact["section_heading"],
            new_content_hash=new_content_hash,
        )
        removed_stale_facts.extend(replacement["removed_facts"])
        record = _build_fact_record(fact, metadata, truth_entry)
        result = ingest_graded_fact(record, db_path=db_path, allow_production=args.confirm)
        if result["status"] == "inserted":
            inserted += 1
        elif result["status"] == "replaced":
            replaced += 1
        else:
            skipped += 1

    print(
        f"Successfully ingested {len(facts)} facts from {args.source}: "
        f"{inserted} inserted, {replaced} replaced, {skipped} skipped (deduped), "
        f"{len(removed_stale_facts)} stale source-section facts removed."
    )


if __name__ == "__main__":
    main()
