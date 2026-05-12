import argparse
import sqlite3
import sys

def resync_canonical_facts(db_path, source=None, truth_source_id=None, dry_run=False):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get registry entries
    registry_query = "SELECT source_id, truth_status, verification_required, verification_evidence_id FROM truth_registry_entries"
    registry_entries = {row['source_id']: row for row in cursor.execute(registry_query).fetchall()}

    # Get facts to update
    query = "SELECT fact_id, source_file, truth_source_id FROM canonical_facts WHERE truth_source_id IS NOT NULL"
    params = []
    if source:
        query += " AND source_file = ?"
        params.append(source)
    if truth_source_id:
        query += " AND truth_source_id = ?"
        params.append(truth_source_id)

    facts = cursor.execute(query, params).fetchall()

    if not facts:
        print("No canonical facts found requiring resync.")
        return

    updated_count = 0
    for fact in facts:
        ts_id = fact['truth_source_id']
        if ts_id in registry_entries:
            entry = registry_entries[ts_id]
            if dry_run:
                print(f"[DRY-RUN] Would update fact {fact['fact_id']} (source: {fact['source_file']}) to status: {entry['truth_status']}")
                updated_count += 1
            else:
                cursor.execute("""
                    UPDATE canonical_facts 
                    SET truth_status = ?, 
                        verification_required = ?, 
                        verification_evidence_id = ?
                    WHERE fact_id = ?
                """, (entry['truth_status'], entry['verification_required'], entry['verification_evidence_id'], fact['fact_id']))
                updated_count += 1
    
    if not dry_run:
        conn.commit()
        print(f"Successfully resynced {updated_count} facts.")
    else:
        print(f"Dry-run: {updated_count} facts identified for update.")
    
    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Resync canonical_facts truth metadata from registry.")
    parser.add_argument("--db", required=True, help="Path to SQLite DB")
    parser.add_argument("--source", help="Filter by source file")
    parser.add_argument("--truth-source-id", help="Filter by truth source ID")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without writing")
    args = parser.parse_args()
    
    resync_canonical_facts(args.db, args.source, args.truth_source_id, args.dry_run)
