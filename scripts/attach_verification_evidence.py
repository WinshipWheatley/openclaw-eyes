import argparse
import sqlite3
import uuid
from datetime import datetime
from business_ops_ledger import record_verification_evidence, get_truth_registry_entry

EVIDENCE_TYPES = ['test_proof', 'runtime_receipt', 'checkpoint', 'manual_review', 'commit_proof']

TRUTH_STATUS_UPGRADE_RULES = {
    'test_verified': ['test_proof'],
    'runtime_verified': ['runtime_receipt'],
    'historical_checkpoint': ['checkpoint', 'commit_proof'],
    'doctrine_reference': ['manual_review', 'commit_proof'],
    'rejected': ['manual_review'],
    'declared': ['manual_review'],
    'stale_possible': ['manual_review']
}

def attach_evidence(db_path, source_id, evidence_type, evidence_ref, evidence_summary, target_truth_status=None):
    if evidence_type not in EVIDENCE_TYPES:
        print(f"Error: Unsupported evidence_type '{evidence_type}'.")
        return False

    entry = get_truth_registry_entry(source_id, db_path)
    if not entry:
        print(f"Error: source_id '{source_id}' not found.")
        return False

    if target_truth_status:
        if target_truth_status not in TRUTH_STATUS_UPGRADE_RULES:
            print(f"Error: Unsupported target status '{target_truth_status}'.")
            return False
        
        allowed_types = TRUTH_STATUS_UPGRADE_RULES[target_truth_status]
        if evidence_type not in allowed_types:
            print(f"Error: evidence_type '{evidence_type}' does not permit target status '{target_truth_status}'.")
            return False

    # Record Evidence
    evidence_id = f"ev_{uuid.uuid4().hex[:8]}"
    success = record_verification_evidence(
        evidence_id, source_id, evidence_type, evidence_ref, evidence_summary, 
        source_commit=entry.get('source_commit'), db_path=db_path
    )
    
    if not success:
        print("Error: Failed to record verification evidence.")
        return False

    # Update Status if requested
    if target_truth_status:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE truth_registry_entries 
            SET truth_status = ?, 
                verification_evidence_id = ?, 
                verified_at = ?
            WHERE source_id = ?
        """, (target_truth_status, evidence_id, datetime.now().isoformat(), source_id))
        conn.commit()
        conn.close()
        print(f"Status upgraded to '{target_truth_status}' and evidence '{evidence_id}' attached.")
    else:
        print(f"Evidence '{evidence_id}' attached.")

    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Attach verification evidence and optionally upgrade truth status.")
    parser.add_argument("--db", required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--evidence-type", required=True)
    parser.add_argument("--evidence-ref", required=True)
    parser.add_argument("--evidence-summary", required=True)
    parser.add_argument("--target-truth-status")
    args = parser.parse_args()

    attach_evidence(args.db, args.source_id, args.evidence_type, args.evidence_ref, args.evidence_summary, args.target_truth_status)
