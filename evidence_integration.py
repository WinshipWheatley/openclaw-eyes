import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Union

from ar_counterparty_contact_operations import (
    registry_register,
    object_path,
    governed_artifact_path,
    _short_hash,
)
from evidence_importer import import_evidence

def import_and_register_evidence(
    conn: sqlite3.Connection,
    source_path: Union[str, Path],
    governed_root: Union[str, Path],
    account_id: str,
    source_system: str,
    source_event: str,
    source_locator: str,
    world: str,
    schema_version: str = "V0",
    extractor_version: str = "V0",
    mime_type: Optional[str] = None,
    privacy_classification: Optional[str] = None,
    source_modified_timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Atomically imports source bytes and registers the evidence with provenance.
    Leaves orphaned content objects intact if registry insertion fails.
    Defaults to quarantined/pending status.
    Explicitly supersedes previous active evidence for the same locator if content changed.
    """
    source_path = Path(source_path)
    governed_root = Path(governed_root).resolve()
    
    # 1. Import bytes durably.
    # This happens BEFORE database transaction so failure leaves DB untouched.
    # If DB fails later, the content object is left orphaned intact.
    file_hash = import_evidence(source_path, governed_root)
    byte_size = source_path.stat().st_size
    
    # 2. Compute governed path
    rel_path = object_path(file_hash)
    # Validate it
    governed_path = governed_artifact_path(rel_path, governed_root)
    
    now_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    
    # We must operate inside a transaction for registry lookup/insert
    with conn:
        # Check for supersession
        # We look for the most recent active record for the same source_locator.
        old_row = conn.execute(
            """SELECT evidence_id, evidence_hash FROM ar_evidence_registry 
               WHERE account_id=? AND source_system=? AND source_locator=? AND governance_status='active'
               ORDER BY ingestion_timestamp DESC LIMIT 1""",
            (account_id, source_system, source_locator)
        ).fetchone()
        
        supersedes_id = None
        if old_row:
            old_row_dict = dict(old_row)
            if old_row_dict["evidence_hash"] != file_hash:
                supersedes_id = old_row_dict["evidence_id"]
                
        # Generate a deterministic evidence_id based on source occurrence and content
        evidence_id = "ev:" + _short_hash(source_system, source_event, source_locator, file_hash)
        
        # 3. Register the exact hash and governed path
        row = registry_register(
            conn=conn,
            evidence_id=evidence_id,
            account_id=account_id,
            source_system=source_system,
            source_event=source_event,
            source_locator=source_locator,
            evidence_hash=file_hash,
            governed_artifact_path_str=str(governed_path),
            world=world,
            first_seen_timestamp=now_ts,
            ingestion_timestamp=now_ts,
            extractor_version=extractor_version,
            schema_version=schema_version,
            source_reference=str(source_path),
            mime_type=mime_type,
            byte_size=byte_size,
            privacy_classification=privacy_classification,
            source_modified_timestamp=source_modified_timestamp,
            supersedes_evidence_id=supersedes_id,
            governance_status="quarantined",
            processing_status="pending",
            availability="available"
        )
        
    return row
