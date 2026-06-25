import sqlite3
import json
from datetime import datetime, timezone
from typing import Any, Dict

def build_capital_hilton_read_model(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    T011: Pure Capital Hilton payload builder.
    Reads the seeded Capital Hilton AR records from the SQLite database
    and structures them into a coherent read-model dictionary.
    No file I/O or DB writes are performed.
    """
    conn.row_factory = sqlite3.Row
    
    # Get account
    account_row = conn.execute(
        "SELECT * FROM ar_counterparty_accounts WHERE account_id = 'capital_hilton'"
    ).fetchone()
    
    if not account_row:
        return {
            "read_model_domain": "capital_hilton_ar_context",
            "schema_version": "AR_CAPITAL_HILTON_READ_MODEL_V0",
            "status": "missing_account",
            "account": None,
            "contacts": [],
            "communication_policies": [],
            "evidence_registry": [],
        }
    
    account_data = json.loads(account_row["account_json"])
    
    # Get contacts
    contact_rows = conn.execute(
        "SELECT * FROM ar_contact_profiles WHERE account_id = 'capital_hilton'"
    ).fetchall()
    contacts = [json.loads(row["contact_json"]) for row in contact_rows]
    
    # Get policies
    policy_rows = conn.execute(
        "SELECT * FROM ar_communication_policies WHERE account_id = 'capital_hilton'"
    ).fetchall()
    policies = [json.loads(row["policy_json"]) for row in policy_rows]
    
    # Get evidence links
    evidence_rows = conn.execute(
        "SELECT evidence_id, source_system, source_event, source_locator, evidence_hash, governed_artifact_path, world, governance_status, processing_status, availability, ingestion_timestamp FROM ar_evidence_registry WHERE account_id = 'capital_hilton'"
    ).fetchall()
    evidence = [dict(row) for row in evidence_rows]
    
    # T015: Response/receipt traceability fields
    import uuid
    
    # Structure the read-model
    read_model = {
        "read_model_domain": "capital_hilton_ar_context",
        "schema_version": "AR_CAPITAL_HILTON_READ_MODEL_V0",
        "status": "available",
        "account": account_data,
        "contacts": contacts,
        "communication_policies": policies,
        "evidence_registry": evidence,
        "traceability": {
            "receipt_id": f"receipt:ar_read_model:{uuid.uuid4().hex[:16]}",
            "command_id": "command:capital_hilton_ar_generation",
            "telegram_bot_username": "@openclaw_cassandra_bot",
            "telegram_display_name": "Clara Reid"
        },
        "generation_timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds")
    }
    
    return read_model
