"""
SQLite Ledger v0 - Append-only receipt layer for Business Ops Spine events.
"""

import sqlite3
import json
import logging
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = ".openclaw/business_ops/ledger.sqlite"


def init_business_ops_ledger(db_path: str | None = None) -> str:
    path = db_path or DEFAULT_DB_PATH
    try:
        conn = sqlite3.connect(path)
        cursor = conn.cursor()

        # 1. events
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                event_type TEXT NOT NULL,
                actor TEXT NOT NULL,
                prompt_hash TEXT,
                operator_visible_summary TEXT,
                raw_sensitive_data_stored INTEGER DEFAULT 0,
                replay_safe INTEGER DEFAULT 0
            )
        """)

        # 2. packets
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS packets (
                packet_id TEXT PRIMARY KEY,
                event_id TEXT,
                intent_name TEXT,
                request_category TEXT,
                actor_name TEXT,
                execution_authority INTEGER DEFAULT 0,
                approval_required INTEGER DEFAULT 0,
                approval_tier TEXT,
                action_status TEXT,
                packet_json_safe TEXT,
                FOREIGN KEY (event_id) REFERENCES events (event_id)
            )
        """)

        # 3. capability_decisions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS capability_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                packet_id TEXT NOT NULL,
                capability_name TEXT NOT NULL,
                decision TEXT NOT NULL,
                reason TEXT,
                FOREIGN KEY (packet_id) REFERENCES packets (packet_id)
            )
        """)

        # 4. retrieval_receipts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS retrieval_receipts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                packet_id TEXT NOT NULL,
                source TEXT NOT NULL,
                attempted INTEGER DEFAULT 0,
                blocked INTEGER DEFAULT 0,
                reason TEXT,
                evidence_ref TEXT,
                raw_sensitive_data_stored INTEGER DEFAULT 0,
                FOREIGN KEY (packet_id) REFERENCES packets (packet_id)
            )
        """)

        # 5. side_effects
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS side_effects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                packet_id TEXT NOT NULL,
                effect_type TEXT NOT NULL,
                status TEXT NOT NULL,
                approval_required INTEGER DEFAULT 0,
                approval_tier TEXT,
                replay_safe INTEGER DEFAULT 0,
                external_ref TEXT,
                FOREIGN KEY (packet_id) REFERENCES packets (packet_id)
            )
        """)

        # 6. operator_explanations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS operator_explanations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT,
                packet_id TEXT,
                summary TEXT NOT NULL,
                safe_for_telegram INTEGER DEFAULT 1,
                FOREIGN KEY (event_id) REFERENCES events (event_id),
                FOREIGN KEY (packet_id) REFERENCES packets (packet_id)
            )
        """)

        # 7. canonical_facts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS canonical_facts (
                fact_id TEXT PRIMARY KEY,
                source_file TEXT NOT NULL,
                section_heading TEXT NOT NULL,
                source_commit TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                fact_text TEXT NOT NULL,
                sensitivity_class TEXT NOT NULL,
                allowed_actors TEXT NOT NULL,
                doc_category TEXT,
                temporal_or_doctrine TEXT,
                source_description TEXT,
                ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                truth_source_id TEXT,
                truth_status TEXT,
                verification_required INTEGER DEFAULT 1,
                verification_evidence_id TEXT
            )
        """)

        # 8. file_inventory
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_inventory (
                file_id TEXT PRIMARY KEY,
                root_id TEXT NOT NULL,
                drive_label TEXT,
                absolute_path TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                file_name TEXT NOT NULL,
                extension TEXT,
                file_type_guess TEXT,
                size_bytes INTEGER NOT NULL,
                modified_at TEXT NOT NULL,
                discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                content_hash TEXT,
                sensitivity_guess TEXT,
                ingest_eligibility TEXT CHECK(ingest_eligibility IN ('eligible_metadata_only', 'excluded', 'unknown')),
                exclusion_reason TEXT
            )
        """)

        # 9. truth_registry_entries
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS truth_registry_entries (
                source_id TEXT PRIMARY KEY,
                observed_path TEXT NOT NULL,
                canonical_path TEXT,
                origin_machine TEXT NOT NULL CHECK (origin_machine IN ('pc','mac','external_drive','unknown')),
                sync_role TEXT NOT NULL CHECK (sync_role IN ('source','mirror','copied_export','review_surface')),
                content_hash TEXT,
                mirror_hash_match INTEGER CHECK (mirror_hash_match IN (0,1)),
                source_commit TEXT,
                doc_type TEXT,
                machine_scope TEXT,
                sensitivity_class TEXT NOT NULL,
                approval_status TEXT NOT NULL CHECK (approval_status IN ('candidate','approved','rejected')),
                truth_status TEXT NOT NULL CHECK (truth_status IN ('declared','doctrine_reference','test_verified','runtime_verified','historical_checkpoint','stale_possible','rejected')),
                verification_source TEXT,
                verification_evidence_id TEXT,
                verification_required INTEGER NOT NULL CHECK (verification_required IN (0,1)),
                canonical_eligible INTEGER NOT NULL CHECK (canonical_eligible IN (0,1)),
                rejection_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                verified_at TEXT
            )
        """)

        # 10. verification_evidence
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS verification_evidence (
                evidence_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                evidence_type TEXT NOT NULL CHECK (evidence_type IN ('test_proof','runtime_receipt','checkpoint','manual_review','commit_proof')),
                evidence_ref TEXT NOT NULL,
                evidence_summary TEXT,
                source_commit TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
    except Exception as e:
        logger.error(f"Failed to initialize ledger at {path}: {e}")
        return path


def record_file_inventory_entry(
    file_id: str,
    root_id: str,
    drive_label: str | None,
    absolute_path: str,
    relative_path: str,
    file_name: str,
    extension: str | None,
    file_type_guess: str | None,
    size_bytes: int,
    modified_at: str,
    content_hash: str | None,
    sensitivity_guess: str | None,
    ingest_eligibility: str,
    exclusion_reason: str | None,
    db_path: str | None = None,
) -> bool:
    """
    Persists a file inventory metadata entry.
    """
    if size_bytes < 0:
        raise ValueError("size_bytes cannot be negative")
    if ingest_eligibility not in ['eligible_metadata_only', 'excluded', 'unknown']:
        raise ValueError("Invalid ingest_eligibility")

    query = """
        INSERT INTO file_inventory (
            file_id, root_id, drive_label, absolute_path, relative_path,
            file_name, extension, file_type_guess, size_bytes, modified_at,
            content_hash, sensitivity_guess, ingest_eligibility, exclusion_reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = (
        file_id, root_id, drive_label, absolute_path, relative_path,
        file_name, extension, file_type_guess, size_bytes, modified_at,
        content_hash, sensitivity_guess, ingest_eligibility, exclusion_reason
    )
    return _execute_write(query, params, db_path)


def record_canonical_fact(
    fact_id: str,
    source_file: str,
    section_heading: str,
    source_commit: str,
    fact_text: str,
    sensitivity_class: str,
    allowed_actors: list[str],
    doc_category: str | None = None,
    temporal_or_doctrine: str | None = None,
    source_description: str | None = None,
    truth_source_id: str | None = None,
    truth_status: str | None = None,
    verification_required: int = 1,
    verification_evidence_id: str | None = None,
    db_path: str | None = None,
) -> bool:
    """
    Records a canonical fact to the ledger.
    Validates inputs for safety, content constraints, and PII presence.
    """
    import hashlib
    import re

    # 1. Validation
    if not fact_text or len(fact_text.strip()) == 0:
        raise ValueError("fact_text cannot be empty.")
    if not all([source_file, section_heading, source_commit]):
        raise ValueError("Missing mandatory provenance fields.")

    allowed_sensitivity = {"public_canonical", "operational_canonical", "non_sensitive"}
    if sensitivity_class not in allowed_sensitivity:
        raise ValueError(f"Invalid sensitivity_class: {sensitivity_class}")

    # 2. PII Check
    pii_patterns = [
        r"\d{3}-\d{2}-\d{4}",  # SSN
        r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",  # Email
        r"\d{3}-\d{3}-\d{4}"  # Phone
    ]
    for pattern in pii_patterns:
        if re.search(pattern, fact_text):
            raise ValueError("PII detected in fact_text.")

    # 3. Hash
    content_hash = hashlib.sha256(fact_text.encode("utf-8")).hexdigest()

    # 4. Write
    query = """
        INSERT INTO canonical_facts (
            fact_id, source_file, section_heading, source_commit,
            content_hash, fact_text, sensitivity_class, allowed_actors,
            doc_category, temporal_or_doctrine, source_description,
            truth_source_id, truth_status, verification_required, verification_evidence_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = (
        fact_id,
        source_file,
        section_heading,
        source_commit,
        content_hash,
        fact_text,
        sensitivity_class,
        json.dumps(allowed_actors),
        doc_category,
        temporal_or_doctrine,
        source_description,
        truth_source_id,
        truth_status,
        verification_required,
        verification_evidence_id,
    )
    return _execute_write(query, params, db_path)


def get_canonical_facts_by_source(source_file: str, db_path: str | None = None) -> list[dict[str, Any]]:
    return _query_canonical_facts("SELECT * FROM canonical_facts WHERE source_file = ?", (source_file,), db_path)

def get_canonical_facts_by_heading(section_heading: str, db_path: str | None = None) -> list[dict[str, Any]]:
    return _query_canonical_facts("SELECT * FROM canonical_facts WHERE section_heading = ?", (section_heading,), db_path)

def _query_canonical_facts(query: str, params: tuple, db_path: str | None = None) -> list[dict[str, Any]]:
    path = db_path or DEFAULT_DB_PATH
    uri = f"file:{path}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
        cursor = conn.cursor()
        cursor.execute(query, params)
        columns = [d[0] for d in cursor.description]
        results = []
        for row in cursor.fetchall():
            fact = dict(zip(columns, row))
            # Parse JSON back
            fact["allowed_actors"] = json.loads(fact["allowed_actors"])
            results.append(fact)
        conn.close()
        return results
    except Exception as e:
        logger.error(f"Failed to query canonical facts: {e}")
        return []


def _execute_write(query: str, params: tuple, db_path: str | None = None) -> bool:
    path = db_path or DEFAULT_DB_PATH
    try:
        conn = sqlite3.connect(path)
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Ledger write failure: {e}")
        return False


def append_event(
    event_id: str,
    event_type: str,
    actor: str,
    prompt_hash: Optional[str] = None,
    operator_visible_summary: Optional[str] = None,
    raw_sensitive_data_stored: bool = False,
    replay_safe: bool = False,
    db_path: str | None = None,
) -> bool:
    query = """
        INSERT INTO events (
            event_id, ts, event_type, actor, prompt_hash,
            operator_visible_summary, raw_sensitive_data_stored, replay_safe
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = (
        event_id,
        datetime.now().isoformat(),
        event_type,
        actor,
        prompt_hash,
        operator_visible_summary,
        1 if raw_sensitive_data_stored else 0,
        1 if replay_safe else 0,
    )
    return _execute_write(query, params, db_path)


def append_packet_receipt(
    packet: Any,
    event_id: Optional[str] = None,
    db_path: str | None = None,
) -> bool:
    """
    Records a BusinessOpsPacket. Expects 'packet' to have to_dict() or be a dict.
    """
    try:
        if hasattr(packet, "to_dict"):
            p_dict = packet.to_dict()
        else:
            p_dict = packet

        query = """
            INSERT INTO packets (
                packet_id, event_id, intent_name, request_category,
                actor_name, execution_authority, approval_required,
                approval_tier, action_status, packet_json_safe
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            p_dict.get("packet_id"),
            event_id,
            p_dict.get("intent_name"),
            p_dict.get("request_category"),
            p_dict.get("actor_name"),
            1 if p_dict.get("execution_authority") else 0,
            1 if p_dict.get("approval_required") else 0,
            p_dict.get("approval_tier"),
            p_dict.get("action_status"),
            json.dumps(p_dict),
        )
        return _execute_write(query, params, db_path)
    except Exception as e:
        logger.error(f"Failed to append packet receipt: {e}")
        return False


def append_capability_decision(
    packet_id: str,
    capability_name: str,
    decision: str,
    reason: Optional[str] = None,
    db_path: str | None = None,
) -> bool:
    query = """
        INSERT INTO capability_decisions (
            packet_id, capability_name, decision, reason
        ) VALUES (?, ?, ?, ?)
    """
    params = (packet_id, capability_name, decision, reason)
    return _execute_write(query, params, db_path)


def append_retrieval_receipt(
    packet_id: str,
    source: str,
    attempted: bool = True,
    blocked: bool = False,
    reason: Optional[str] = None,
    evidence_ref: Optional[str] = None,
    raw_sensitive_data_stored: bool = False,
    db_path: str | None = None,
) -> bool:
    query = """
        INSERT INTO retrieval_receipts (
            packet_id, source, attempted, blocked, reason,
            evidence_ref, raw_sensitive_data_stored
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    params = (
        packet_id,
        source,
        1 if attempted else 0,
        1 if blocked else 0,
        reason,
        evidence_ref,
        1 if raw_sensitive_data_stored else 0,
    )
    return _execute_write(query, params, db_path)


def append_side_effect(
    packet_id: str,
    effect_type: str,
    status: str,
    approval_required: bool = False,
    approval_tier: Optional[str] = None,
    replay_safe: bool = False,
    external_ref: Optional[str] = None,
    db_path: str | None = None,
) -> bool:
    query = """
        INSERT INTO side_effects (
            packet_id, effect_type, status, approval_required,
            approval_tier, replay_safe, external_ref
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    params = (
        packet_id,
        effect_type,
        status,
        1 if approval_required else 0,
        approval_tier,
        1 if replay_safe else 0,
        external_ref,
    )
    return _execute_write(query, params, db_path)


def append_operator_explanation(
    summary: str,
    event_id: Optional[str] = None,
    packet_id: Optional[str] = None,
    safe_for_telegram: bool = True,
    db_path: str | None = None,
) -> bool:
    query = """
        INSERT INTO operator_explanations (
            event_id, packet_id, summary, safe_for_telegram
        ) VALUES (?, ?, ?, ?)
    """
    params = (event_id, packet_id, summary, 1 if safe_for_telegram else 0)
    return _execute_write(query, params, db_path)


def record_truth_registry_entry(
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
) -> bool:
    """Records a new truth registry entry with strict validation."""
    if truth_status in ['runtime_verified', 'test_verified'] and not (verification_evidence_id or verification_source):
        raise ValueError(f"truth_status '{truth_status}' requires verification_evidence_id or verification_source.")

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
    return _execute_write(query, params, db_path)

def record_verification_evidence(
    evidence_id: str,
    source_id: str,
    evidence_type: str,
    evidence_ref: str,
    evidence_summary: str | None = None,
    source_commit: str | None = None,
    db_path: str | None = None,
) -> bool:
    query = """
        INSERT INTO verification_evidence (
            evidence_id, source_id, evidence_type, evidence_ref, evidence_summary, source_commit
        ) VALUES (?, ?, ?, ?, ?, ?)
    """
    params = (evidence_id, source_id, evidence_type, evidence_ref, evidence_summary, source_commit)
    return _execute_write(query, params, db_path)

def get_truth_registry_entries_by_status(truth_status: str, db_path: str | None = None) -> list[dict[str, Any]]:
    return _query_truth_registry("SELECT * FROM truth_registry_entries WHERE truth_status = ?", (truth_status,), db_path)

def get_truth_registry_entries_by_approval_status(approval_status: str, db_path: str | None = None) -> list[dict[str, Any]]:
    return _query_truth_registry("SELECT * FROM truth_registry_entries WHERE approval_status = ?", (approval_status,), db_path)

def get_truth_registry_entries_by_doc_type(doc_type: str, db_path: str | None = None) -> list[dict[str, Any]]:
    return _query_truth_registry("SELECT * FROM truth_registry_entries WHERE doc_type = ?", (doc_type,), db_path)

def get_truth_registry_entries_requiring_verification(db_path: str | None = None) -> list[dict[str, Any]]:
    return _query_truth_registry("SELECT * FROM truth_registry_entries WHERE verification_required = 1", (), db_path)

def get_truth_registry_entry(source_id: str, db_path: str | None = None) -> dict[str, Any] | None:
    results = _query_truth_registry("SELECT * FROM truth_registry_entries WHERE source_id = ?", (source_id,), db_path)
    return results[0] if results else None

def get_verification_evidence_for_source(source_id: str, db_path: str | None = None) -> list[dict[str, Any]]:
    path = db_path or DEFAULT_DB_PATH
    uri = f"file:{path}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM verification_evidence WHERE source_id = ?", (source_id,))
        columns = [d[0] for d in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        return results
    except Exception as e:
        logger.error(f"Failed to query verification evidence: {e}")
        return []

def _query_truth_registry(query: str, params: tuple, db_path: str | None = None) -> list[dict[str, Any]]:
    path = db_path or DEFAULT_DB_PATH
    uri = f"file:{path}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
        cursor = conn.cursor()
        cursor.execute(query, params)
        columns = [d[0] for d in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        return results
    except Exception as e:
        logger.error(f"Failed to query truth registry: {e}")
        return []

def get_file_inventory_by_root(root_id: str, db_path: str | None = None) -> list[dict[str, Any]]:
    return _query_file_inventory("SELECT * FROM file_inventory WHERE root_id = ?", (root_id,), db_path)

def get_file_inventory_by_extension(extension: str, db_path: str | None = None) -> list[dict[str, Any]]:
    return _query_file_inventory("SELECT * FROM file_inventory WHERE extension = ?", (extension,), db_path)

def get_file_inventory_by_name(file_name: str, db_path: str | None = None) -> list[dict[str, Any]]:
    return _query_file_inventory("SELECT * FROM file_inventory WHERE file_name = ?", (file_name,), db_path)

def _query_file_inventory(query: str, params: tuple, db_path: str | None = None) -> list[dict[str, Any]]:
    path = db_path or DEFAULT_DB_PATH
    uri = f"file:{path}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
        cursor = conn.cursor()
        cursor.execute(query, params)
        columns = [d[0] for d in cursor.description]
        results = []
        for row in cursor.fetchall():
            results.append(dict(zip(columns, row)))
        conn.close()
        return results
    except Exception as e:
        logger.error(f"Failed to query file_inventory: {e}")
        return []


def get_last_event_summary(db_path: str | None = None) -> Optional[str]:
    path = db_path or DEFAULT_DB_PATH
    try:
        conn = sqlite3.connect(path)
        cursor = conn.cursor()
        cursor.execute("SELECT operator_visible_summary FROM events ORDER BY ts DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception as e:
        logger.error(f"Failed to get last event summary: {e}")
        return None


def get_packet_summary(packet_id: str, db_path: str | None = None) -> Optional[dict[str, Any]]:
    path = db_path or DEFAULT_DB_PATH
    try:
        conn = sqlite3.connect(path)
        cursor = conn.cursor()
        cursor.execute("SELECT intent_name, action_status, approval_required FROM packets WHERE packet_id = ?", (packet_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "intent_name": row[0],
                "action_status": row[1],
                "approval_required": bool(row[2]),
            }
        return None
    except Exception as e:
        logger.error(f"Failed to get packet summary: {e}")
        return None

def record_action_intent_gate_receipt(
    packet_id: str,
    packet_type: str,
    gate_result: str,
    evaluation_summary: str,
    actor: str = "OpenClaw",
    db_path: str | None = None,
    **kwargs: Any,
) -> bool:
    """
    Records an action_intent_gate_receipt to the ledger.
    This records the gate/evaluation handling only and does NOT imply execution.
    """
    import uuid
    event_id = f"aig_{uuid.uuid4().hex[:8]}"

    # 1. Append the base event
    success = append_event(
        event_id=event_id,
        event_type="action_intent_gate_receipt",
        actor=actor,
        operator_visible_summary=evaluation_summary,
        db_path=db_path
    )
    if not success:
        return False

    # 2. Append the packet record for more structured lookup
    packet_data = {
        "packet_id": packet_id,
        "packet_type": packet_type,
        "intent_name": packet_type,
        "request_category": "action_intent",
        "actor_name": actor,
        "execution_authority": 0,  # Explicit: no execution
        "approval_required": kwargs.get("approval_required", 0),
        "action_status": f"gate_{gate_result}",
        "gate_result": gate_result,
        "evaluation_summary": evaluation_summary,
        "recorded_at": datetime.now().isoformat(),
        "no_execution_without_approval": True,
        **kwargs
    }

    return append_packet_receipt(packet_data, event_id=event_id, db_path=db_path)




def record_approval_log_entry(
    packet_id: str,
    packet_type: str,
    approval_verdict: str,
    approval_summary: str,
    approver_name: str,
    request_id: str | None = None,
    db_path: str | None = None,
    **kwargs: Any,
) -> bool:
    """
    Records an approval_log_entry to the ledger.
    This records the decision only and does NOT imply execution or completion.
    """
    import uuid
    from datetime import datetime
    event_id = f"ale_{uuid.uuid4().hex[:8]}"

    # 1. Append the base event
    display_summary = f"{approval_verdict}: {approval_summary}"
    success = append_event(
        event_id=event_id,
        event_type="approval_log_entry",
        actor=approver_name,
        operator_visible_summary=display_summary,
        db_path=db_path
    )
    if not success:
        return False

    # 2. Append the packet record
    packet_data = {
        "packet_id": packet_id,
        "packet_type": packet_type,
        "receipt_type": "approval_log_entry",
        "approval_verdict": approval_verdict,
        "approval_summary": approval_summary,
        "approver_name": approver_name,
        "request_id": request_id,
        "action_status": "approval_decision_recorded",
        "decision_record_only": True,
        "execution_recorded": False,
        "mutation_recorded": False,
        "no_execution_recorded": True,
        "execution_authority": 0,  # Explicit: no execution
        "recorded_at": datetime.now().isoformat(),
        **kwargs
    }

    return append_packet_receipt(packet_data, event_id=event_id, db_path=db_path)




def record_approval_request_record(
    packet_id: str,
    packet_type: str,
    approval_id: str,
    approval_request_summary: str,
    requester_agent: str,
    action_intent_ref: str | None = None,
    risk_tier: str | None = None,
    db_path: str | None = None,
    **kwargs: Any,
) -> bool:
    """
    Records an approval_request_record to the ledger.
    This records the formal request only and does NOT imply a decision or execution.
    """
    import uuid
    from datetime import datetime
    event_id = f"arr_{uuid.uuid4().hex[:8]}"

    # 1. Append the base event
    success = append_event(
        event_id=event_id,
        event_type="approval_request_record",
        actor=requester_agent,
        operator_visible_summary=approval_request_summary,
        db_path=db_path
    )
    if not success:
        return False

    # 2. Append the packet record
    packet_data = {
        "packet_id": packet_id,
        "packet_type": packet_type,
        "intent_name": packet_type,
        "receipt_type": "approval_request_record",
        "approval_id": approval_id,
        "action_intent_ref": action_intent_ref,
        "risk_tier": risk_tier,
        "requester_agent": requester_agent,
        "approval_request_summary": approval_request_summary,
        "action_status": "approval_request_recorded",
        "request_status": "approval_request_recorded",
        "decision_status": "no_decision_recorded",
        "decision_recorded": False,
        "decision_record_only": False,
        "execution_recorded": False,
        "mutation_recorded": False,
        "no_execution_recorded": True,
        "execution_authority": 0,  # Explicit: no execution
        "recorded_at": datetime.now().isoformat(),
        **kwargs
    }

    return append_packet_receipt(packet_data, event_id=event_id, db_path=db_path)



def record_outreach_email_draft_receipt(
    packet_id: str,
    draft_id: str,
    thread_id: str,
    target_intent: str,
    actor: str = "OpenClaw",
    db_path: str | None = None,
) -> bool:
    """
    Records an outreach_email_draft_receipt to the ledger.
    This records draft metadata only and does NOT imply send, approval, or delivery.
    """
    import uuid
    from datetime import datetime
    event_id = f"oed_{uuid.uuid4().hex[:8]}"

    # 1. Append the base event
    summary = f"Draft created for: {target_intent} (Draft Only/Not Sent)"
    success = append_event(
        event_id=event_id,
        event_type="outreach_email_draft_receipt",
        actor=actor,
        operator_visible_summary=summary,
        db_path=db_path
    )
    if not success:
        return False

    # 2. Append the packet record
    packet_data = {
        "packet_id": packet_id,
        "draft_id": draft_id,
        "thread_id": thread_id,
        "target_intent": target_intent,
        "packet_type": "outreach_email_draft_receipt",
        "action_status": "draft_metadata_recorded",
        "draft_only": True,
        "sent_recorded": False,
        "approval_required": True,
        "execution_authority": 0,
        "send_authority": 0,
        "no_send_recorded": True,
        "recorded_at": datetime.now().isoformat()
    }

    return append_packet_receipt(packet_data, event_id=event_id, db_path=db_path)

def record_pii_vault_receipt(
    packet_id: str,
    token_mapping_id: str,
    target_intent: str,
    actor: str = "OpenClaw",
    db_path: str | None = None,
    **kwargs
) -> bool:
    """
    Records a pii_vault_record to the ledger.
    This records vault metadata only and does NOT imply exposure, extraction,
    or execution authority. It strictly rejects any raw PII or textual content fields.
    """
    import uuid
    from datetime import datetime

    # 1. Strictly reject unsafe keys
    unsafe_keys = {
        "raw_text", "pii_text", "email_body", "message_body",
        "prompt_body", "sensitive_content", "unredacted_text",
        "original_text", "recipient_email", "phone_number",
        "ssn", "address"
    }
    for key in unsafe_keys:
        if key in kwargs:
            raise ValueError(f"Unsafe key '{key}' is strictly forbidden in pii_vault_record.")

    event_id = f"pii_{uuid.uuid4().hex[:8]}"

    # 2. Append the base event
    summary = f"Vault reference recorded for: {target_intent} (Redacted Metadata Only)"
    success = append_event(
        event_id=event_id,
        event_type="pii_vault_record",
        actor=actor,
        operator_visible_summary=summary,
        db_path=db_path
    )
    if not success:
        return False

    # 3. Append the packet record
    packet_data = {
        "packet_id": packet_id,
        "token_mapping_id": token_mapping_id,
        "target_intent": target_intent,
        "packet_type": "pii_vault_record",
        "action_status": "redacted_metadata_recorded",
        "redacted_metadata_only": True,
        "raw_pii_stored": False,
        "vault_write_verified": False,
        "external_model_access_granted": False,
        "execution_authority": 0,
        "sensitive_content_access": 0,
        "recorded_at": datetime.now().isoformat(),
        **kwargs
    }

    return append_packet_receipt(packet_data, event_id=event_id, db_path=db_path)
