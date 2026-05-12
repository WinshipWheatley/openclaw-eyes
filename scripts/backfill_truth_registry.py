import argparse
import hashlib
import sys
import os
from scripts.ingest_canonical_docs import SOURCE_REGISTRY
from business_ops_ledger import record_truth_registry_entry, init_business_ops_ledger

def map_truth_status(doc_category, temporal_or_doctrine):
    if temporal_or_doctrine == "temporal_checkpoint":
        return "historical_checkpoint"
    if temporal_or_doctrine == "doctrine_reference":
        return "doctrine_reference"
    return "declared"

def record_truth_registry_entry_idempotent(
    source_id: str,
    observed_path: str,
    origin_machine: str,
    sync_role: str,
    sensitivity_class: str,
    approval_status: str,
    truth_status: str,
    verification_required: bool,
    canonical_eligible: bool,
    canonical_path: str | None = None,
    content_hash: str | None = None,
    source_commit: str | None = None,
    doc_type: str | None = None,
    machine_scope: str | None = None,
    verification_source: str | None = None,
    verification_evidence_id: str | None = None,
    rejection_reason: str | None = None,
    verified_at: str | None = None,
    db_path: str | None = None,
) -> str:
    import sqlite3
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT source_id FROM truth_registry_entries WHERE source_id = ?", (source_id,))
    if cursor.fetchone():
        conn.close()
        return "skipped"

    query = """
        INSERT INTO truth_registry_entries (
            source_id, observed_path, canonical_path, origin_machine, sync_role,
            content_hash, source_commit, doc_type, machine_scope, sensitivity_class,
            approval_status, truth_status, verification_source, verification_evidence_id,
            verification_required, canonical_eligible, rejection_reason, verified_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = (
        source_id, observed_path, canonical_path, origin_machine, sync_role,
        content_hash, source_commit, doc_type, machine_scope, sensitivity_class,
        approval_status, truth_status, verification_source, verification_evidence_id,
        1 if verification_required else 0, 1 if canonical_eligible else 0, rejection_reason, verified_at
    )
    cursor.execute(query, params)
    conn.commit()
    conn.close()
    return "inserted"

def backfill(db_path, dry_run=False):
    if not dry_run:
        init_business_ops_ledger(db_path)

    stats = {"inserted": 0, "skipped": 0}
    for source_path, metadata in SOURCE_REGISTRY.items():
        source_id = hashlib.sha256(source_path.encode()).hexdigest()[:16]
        
        truth_status = map_truth_status(metadata.get("doc_category"), metadata.get("temporal_or_doctrine"))
        
        entry = {
            "source_id": source_id,
            "observed_path": source_path,
            "origin_machine": "pc",
            "sync_role": "source",
            "sensitivity_class": metadata["sensitivity_class"],
            "approval_status": "approved",
            "truth_status": truth_status,
            "verification_required": True,
            "canonical_eligible": True,
            "doc_type": metadata.get("doc_category"),
            "machine_scope": metadata.get("temporal_or_doctrine") or metadata.get("doc_category")
        }
        
        if dry_run:
            # Check existence in dry run
            conn = sqlite3.connect(db_path)
            exists = conn.execute("SELECT 1 FROM truth_registry_entries WHERE source_id = ?", (source_id,)).fetchone()
            conn.close()
            if exists:
                stats["skipped"] += 1
            else:
                stats["inserted"] += 1
        else:
            result = record_truth_registry_entry_idempotent(**entry, db_path=db_path)
            stats[result] += 1
            
    return stats

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    stats = backfill(args.db, args.dry_run)
    print(f"Stats: {stats}")

if __name__ == "__main__":
    main()
