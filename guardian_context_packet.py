"""Deterministic context packet for Guardian's HITL authority brain.

Guardian's lane: approvals + HITL — what's pending operator approval, what's
blocked/held, what authority decisions are open. The packet is grounded in real
ledger state and Guardian-specific read-models. NO confabulation.

DANK contract:
  (1) GROUNDED  — every fact carries source_ref + provenance; no invented data.
  (2) CURRENT   — freshness tracked from ledger generated_at or file mtime.
  (3) USEFUL    — surfacing exactly what operator asks Guardian: pending/held/open.
  (4) IN-VOICE  — truthful facts only; brain renders persona tone separately.
  (5) LANE-RICH — deeply reflects Guardian's world: HITL queue, approvals, authority posture.

ANTI-CONFABULATION: if the approval ledger is empty or absent, this is flagged
explicitly rather than fabricating approval state. Empty store = flagged gap, not fake data.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "guardian_context_packet_v0"
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")

# Read-models Guardian cares about
GUARDIAN_READ_MODELS = (
    "guardian_approval_posture.json",             # approval ledger counts (REAL, built by us)
    "guardian_hitl_authority_reconciliation.json", # which surfaces are active/mixed/legacy
    "guardian_hitl_sqlite_authority_contract.json", # contract definition + criteria
    "guardian_draft_approval_request_contract.json", # Capital Hilton send approval status
    "agent_presence.json",                         # fleet online state
    "guardian_hitl_surface_disposition.json",      # per-surface disposition
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _short_hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()[:16]


def _compact(value: Any, *, limit: int = 900) -> str:
    text = " ".join(str(value or "").replace("\x00", " ").split()).strip()
    return text[: limit - 3].rstrip() + "..." if len(text) > limit else text


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _freshness(path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    generated_at = str(
        payload.get("generated_at") or payload.get("updated_at") or ""
    ).strip()
    if not generated_at:
        try:
            generated_at = datetime.fromtimestamp(
                path.stat().st_mtime, timezone.utc
            ).replace(microsecond=0).isoformat()
        except OSError:
            generated_at = ""
    return {"as_of": generated_at, "source_ref": f"generated/read_models/{path.name}"}


def _display_ref(path: Path) -> str:
    return f"generated/read_models/{path.name}"


def _append_fact(
    facts: list[dict[str, Any]],
    *,
    topic: str,
    label: str,
    value: str,
    source_ref: str,
    provenance: str,
    pii_tier: str = "PUBLIC",
    freshness: Mapping[str, Any] | None = None,
) -> None:
    clean_value = _compact(value)
    if not clean_value:
        return
    fact = {
        "fact_id": f"{topic}:{_short_hash((label, clean_value, source_ref))}",
        "topic": topic,
        "label": _compact(label, limit=160),
        "value": clean_value,
        "provenance": provenance,
        "freshness": dict(freshness or {}),
        "source_ref": source_ref,
        "pii_tier": str(pii_tier or "PUBLIC").upper(),
    }
    facts.append(fact)


def _approval_posture_facts(
    path: Path, payload: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Pull dank facts from guardian_approval_posture.json (ledger-sourced)."""
    facts: list[dict[str, Any]] = []
    fresh = _freshness(path, payload)
    src = _display_ref(path)
    provenance = "generated_read_model:ledger_query"

    ledger_present = payload.get("ledger_present", False)

    if not ledger_present:
        gap = payload.get("data_gap") or "Approval ledger not found."
        _append_fact(
            facts,
            topic="approval_posture",
            label="Approval ledger gap",
            value=f"DATA GAP: {gap} Cannot surface real pending-approval state without the ledger.",
            source_ref=src,
            provenance=provenance,
            freshness=fresh,
        )
        return facts

    posture_summary = str(payload.get("posture_summary") or "").strip()
    if posture_summary:
        _append_fact(
            facts,
            topic="approval_posture",
            label="Approval posture (ledger-sourced)",
            value=posture_summary,
            source_ref=src,
            provenance=provenance,
            freshness=fresh,
        )

    # Pending count
    total = payload.get("pending_approval_count", 0)
    active = payload.get("active_not_expired_count", 0)
    req_info = payload.get("approval_requests", {})
    by_type = req_info.get("by_action_type", {})
    type_text = "; ".join(f"{cnt} {t}" for t, cnt in sorted(by_type.items())) if by_type else "none"
    _append_fact(
        facts,
        topic="approval_posture",
        label="Approval requests in ledger",
        value=(
            f"{total} approval records observed ({active} not-yet-expired by timestamp). "
            f"By type: {type_text}. "
            f"Note: all are shadow/dual-write entries; legacy JSON is authoritative for live gate state."
        ),
        source_ref=src,
        provenance=provenance,
        freshness=fresh,
    )

    # Receipt count
    receipt_info = payload.get("approval_receipts", {})
    receipt_total = receipt_info.get("total", 0)
    by_receipt = receipt_info.get("by_receipt_type", {})
    receipt_parts = [
        f"{rt}: {sum(v for v in statuses.values())} ({', '.join(f'{s}={c}' for s, c in statuses.items())})"
        for rt, statuses in sorted(by_receipt.items())
    ]
    _append_fact(
        facts,
        topic="approval_posture",
        label="Approval receipts in ledger",
        value=f"{receipt_total} receipts. " + ("; ".join(receipt_parts) or "none"),
        source_ref=src,
        provenance=provenance,
        freshness=fresh,
    )

    # Recovery clearances
    clearance_info = payload.get("recovery_clearances", {})
    if clearance_info.get("present"):
        clearance_total = clearance_info.get("total", 0)
        clearance_by_status = clearance_info.get("by_status", {})
        status_text = "; ".join(f"{cnt} {s}" for s, cnt in sorted(clearance_by_status.items()))
        recent = clearance_info.get("most_recent", {})
        recent_text = ""
        if recent:
            recent_text = (
                f" Most recent: agent={recent.get('agent_id','?')}, "
                f"action={recent.get('recovery_action_id','?')}, "
                f"status={recent.get('status','?')}, "
                f"requested={recent.get('requested_at','?')}."
            )
        _append_fact(
            facts,
            topic="recovery_clearances",
            label="Agent recovery clearances (fixed-scope)",
            value=(
                f"{clearance_total} Cassandra recovery clearances: {status_text}.{recent_text} "
                f"Fixed-scope Cassandra restart only; not general runtime approval authority."
            ),
            source_ref=src,
            provenance=provenance,
            freshness=fresh,
        )

    note = str(payload.get("note") or "").strip()
    if note:
        _append_fact(
            facts,
            topic="approval_posture",
            label="Approval ledger boundary note",
            value=note,
            source_ref=src,
            provenance=provenance,
            freshness=fresh,
        )

    return facts


def _authority_reconciliation_facts(
    path: Path, payload: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Pull Guardian authority reconciliation posture."""
    facts: list[dict[str, Any]] = []
    fresh = _freshness(path, payload)
    src = _display_ref(path)
    provenance = "generated_read_model"

    # Active authority surfaces count
    active_surfaces = [s for s in payload.get("active_authority_surfaces", ()) if isinstance(s, Mapping)]
    mixed_surfaces = [s for s in payload.get("mixed_authority_surfaces", ()) if isinstance(s, Mapping)]

    if active_surfaces or mixed_surfaces:
        active_names = ", ".join(
            str(s.get("surface_id") or s.get("surface") or "unknown")
            for s in active_surfaces[:6]
        )
        mixed_names = ", ".join(
            str(s.get("surface_id") or s.get("surface") or "unknown")
            for s in mixed_surfaces[:4]
        )
        _append_fact(
            facts,
            topic="authority_posture",
            label="Approval authority surfaces",
            value=(
                f"{len(active_surfaces)} active authority surfaces: {active_names or 'none'}. "
                f"{len(mixed_surfaces)} mixed/conflicting surfaces: {mixed_names or 'none'}. "
                f"Legacy JSON still active: {payload.get('legacy_json_still_active', True)}. "
                f"Old HITL deleted: {payload.get('old_hitl_deleted', False)}."
            ),
            source_ref=src,
            provenance=provenance,
            freshness=fresh,
        )

    next_safe = str(payload.get("next_safe_move") or "").strip()
    if next_safe:
        _append_fact(
            facts,
            topic="authority_posture",
            label="Guardian next safe move (authority)",
            value=next_safe,
            source_ref=src,
            provenance=provenance,
            freshness=fresh,
        )

    return facts


def _contract_facts(path: Path, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Pull Guardian SQLite contract criteria."""
    facts: list[dict[str, Any]] = []
    fresh = _freshness(path, payload)
    src = _display_ref(path)
    provenance = "generated_read_model"

    criteria = payload.get("contract_criteria")
    if isinstance(criteria, Mapping):
        met = [k for k, v in criteria.items() if v]
        not_met = [k for k, v in criteria.items() if not v]
        _append_fact(
            facts,
            topic="authority_posture",
            label="Guardian SQLite contract criteria",
            value=(
                f"Contract defined: {payload.get('contract_defined', False)}. "
                f"SQLite schema applied to runtime DB: {payload.get('sqlite_schema_applied_to_runtime_db', False)}. "
                f"Criteria met: {', '.join(met) or 'none'}. "
                f"Criteria not met: {', '.join(not_met) or 'none'}."
            ),
            source_ref=src,
            provenance=provenance,
            freshness=fresh,
        )

    return facts


def _draft_approval_facts(path: Path, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Pull Capital Hilton final-send approval request status."""
    facts: list[dict[str, Any]] = []
    fresh = _freshness(path, payload)
    src = _display_ref(path)
    provenance = "generated_read_model"

    status = str(payload.get("current_availability_status") or "").strip()
    available = payload.get("approval_request_available_now", False)
    blockers = [b for b in payload.get("blockers", ()) if isinstance(b, Mapping)]
    workflow_name = str(payload.get("workflow_name") or "Capital Hilton companion invoice email").strip()

    if status:
        blocker_text = ""
        if blockers:
            blocker_ids = ", ".join(str(b.get("blocker_id") or "") for b in blockers[:5])
            blocker_text = f" Blockers ({len(blockers)}): {blocker_ids}."

        _append_fact(
            facts,
            topic="draft_approval",
            label=f"Capital Hilton send approval status",
            value=(
                f"{workflow_name}: request available now = {available}. "
                f"Status: {status}.{blocker_text}"
            ),
            source_ref=src,
            provenance=provenance,
            freshness=fresh,
        )

    return facts


def _agent_presence_facts(path: Path, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Basic fleet online state relevant to Guardian context."""
    facts: list[dict[str, Any]] = []
    agents = [row for row in payload.get("agents", ()) if isinstance(row, Mapping)]
    online = [row for row in agents if str(row.get("actual_state") or "").lower() == "online"]
    if agents:
        names = ", ".join(
            str(row.get("display_name") or row.get("agent_id") or "agent")
            for row in online[:8]
        )
        _append_fact(
            facts,
            topic="agent_presence",
            label="Online agents",
            value=(
                f"{len(online)} of {len(agents)} agents online: {names or 'none listed online'}."
            ),
            source_ref=_display_ref(path),
            provenance="generated_read_model",
            freshness=_freshness(path, payload),
        )
    return facts


def _guardian_read_model_facts(
    root: Path,
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    """Load all Guardian read-models and extract dank facts."""
    facts: list[dict[str, Any]] = []
    refs: list[str] = []
    proof: dict[str, Any] = {"read_model_presence": {}}

    payloads: dict[str, dict[str, Any]] = {}
    for name in GUARDIAN_READ_MODELS:
        path = root / name
        payload = _read_json(path)
        proof["read_model_presence"][name] = bool(payload)
        if not payload:
            continue
        payloads[name] = payload
        refs.append(_display_ref(path))

    # 1. Approval posture (primary dank source — real ledger data)
    posture_path = root / "guardian_approval_posture.json"
    if "guardian_approval_posture.json" in payloads:
        facts.extend(_approval_posture_facts(posture_path, payloads["guardian_approval_posture.json"]))

    # 2. Authority reconciliation
    recon_path = root / "guardian_hitl_authority_reconciliation.json"
    if "guardian_hitl_authority_reconciliation.json" in payloads:
        facts.extend(_authority_reconciliation_facts(recon_path, payloads["guardian_hitl_authority_reconciliation.json"]))

    # 3. SQLite contract criteria
    contract_path = root / "guardian_hitl_sqlite_authority_contract.json"
    if "guardian_hitl_sqlite_authority_contract.json" in payloads:
        facts.extend(_contract_facts(contract_path, payloads["guardian_hitl_sqlite_authority_contract.json"]))

    # 4. Draft approval request status
    draft_path = root / "guardian_draft_approval_request_contract.json"
    if "guardian_draft_approval_request_contract.json" in payloads:
        facts.extend(_draft_approval_facts(draft_path, payloads["guardian_draft_approval_request_contract.json"]))

    # 5. Agent presence (fleet context)
    presence_path = root / "agent_presence.json"
    if "agent_presence.json" in payloads:
        facts.extend(_agent_presence_facts(presence_path, payloads["agent_presence.json"]))

    return facts, refs, proof


def build_guardian_context_packet(
    *,
    question: str = "",
    read_model_root: str | Path | None = None,
    require_posture_read_model: bool = True,
) -> dict[str, Any]:
    root = Path(read_model_root) if read_model_root is not None else DEFAULT_READ_MODEL_ROOT
    generated_at = _utc_now()

    facts, refs, proof = _guardian_read_model_facts(root)
    posture_present = proof["read_model_presence"].get("guardian_approval_posture.json", False)

    if require_posture_read_model and not posture_present:
        # Don't raise — flag it; this is a data gap, not a code error
        facts.insert(
            0,
            {
                "fact_id": "approval_posture:MISSING",
                "topic": "approval_posture",
                "label": "DATA GAP: guardian_approval_posture.json absent",
                "value": (
                    "guardian_approval_posture.json not found. Run "
                    "scripts/export_guardian_approval_posture_read_model.py to generate it from the ledger."
                ),
                "provenance": "gap_detection",
                "freshness": {"as_of": generated_at},
                "source_ref": "generated/read_models/guardian_approval_posture.json",
                "pii_tier": "PUBLIC",
            },
        )

    source_refs = tuple(dict.fromkeys([*(f["source_ref"] for f in facts), *refs]))
    basis = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "question_hash": hashlib.sha256(str(question or "").encode("utf-8")).hexdigest(),
        "source_refs": source_refs,
        "fact_count": len(facts),
    }
    packet_id = f"guardian_context_packet:{_short_hash(basis)}"

    return {
        "schema_version": SCHEMA_VERSION,
        "packet_id": packet_id,
        "status": "READY",
        "generated_at": generated_at,
        "question": _compact(question, limit=300),
        "facts": facts,
        "source_refs": list(source_refs),
        "bounds": {
            "send_hold_absolute": True,
            "outbound_send_allowed": False,
            "money_movement_allowed": False,
            "ledger_mutation_allowed": False,
            "approval_decision_allowed": False,
            "hitl_resolution_allowed": False,
            "claims_must_trace_to_packet": True,
        },
        "machine_proof": {
            "packet_compiler": "guardian_context_packet.build_guardian_context_packet",
            "read_model_root": str(root),
            "fact_count": len(facts),
            "approval_posture_read_model_present": posture_present,
            **proof,
        },
        "packet_text": format_guardian_context_packet(
            {"facts": facts, "bounds": {
                "send_hold_absolute": True,
                "outbound_send_allowed": False,
                "money_movement_allowed": False,
                "ledger_mutation_allowed": False,
                "approval_decision_allowed": False,
                "hitl_resolution_allowed": False,
            }, "packet_id": packet_id, "generated_at": generated_at}
        ),
    }


def format_guardian_context_packet(packet: Mapping[str, Any]) -> str:
    facts = [f for f in packet.get("facts", ()) if isinstance(f, Mapping)]
    bounds = packet.get("bounds", {}) if isinstance(packet.get("bounds"), Mapping) else {}
    lines = [
        f"GUARDIAN_CONTEXT_PACKET {packet.get('packet_id', '')}",
        f"Generated: {packet.get('generated_at', '')}",
        "",
        "Grounded facts:",
    ]
    for fact in facts[:20]:
        src = str(fact.get("source_ref") or "")
        prov = str(fact.get("provenance") or "")
        tier = str(fact.get("pii_tier") or "PUBLIC")
        lines.append(
            f"- {fact.get('label')}: {fact.get('value')} "
            f"[tier={tier}; provenance={prov}; source={src}]"
        )
    lines.extend([
        "",
        "Boundaries:",
        f"- SEND_HOLD absolute: {bool(bounds.get('send_hold_absolute', True))}",
        f"- Outbound send allowed: {bool(bounds.get('outbound_send_allowed', False))}",
        f"- Approval decision allowed: {bool(bounds.get('approval_decision_allowed', False))}",
        f"- HITL resolution allowed: {bool(bounds.get('hitl_resolution_allowed', False))}",
        f"- Ledger mutation allowed: {bool(bounds.get('ledger_mutation_allowed', False))}",
    ])
    return "\n".join(lines).strip()


__all__ = [
    "SCHEMA_VERSION",
    "GUARDIAN_READ_MODELS",
    "build_guardian_context_packet",
    "format_guardian_context_packet",
]
