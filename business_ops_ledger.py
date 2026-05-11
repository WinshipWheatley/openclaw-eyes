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

        conn.commit()
        conn.close()
        return path
    except Exception as e:
        logger.error(f"Failed to initialize ledger at {path}: {e}")
        return path


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
