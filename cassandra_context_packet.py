"""Deterministic context packet for Cassandra's email + calendar lane.

Cassandra's lane: email triage, draft previews, calendar state awareness.
The packet is grounded in real read-models — presence, runtime wiring posture,
email/calendar capability posture, sync health. Every fact carries source_ref
and freshness. NO confabulation.

DANK contract:
  (1) GROUNDED  — every fact carries source_ref + provenance; no invented data.
  (2) CURRENT   — freshness tracked from read-model generated_at or file mtime.
  (3) USEFUL    — surfacing exactly what operator asks Cassandra: email/calendar posture,
                  triage capability, draft readiness, blocked paths, sync health.
  (4) IN-VOICE  — truthful facts only; brain renders persona tone separately.
  (5) LANE-RICH — deeply reflects Cassandra's world: wiring audit, send posture,
                  governed capability classification, calendar context, fleet state.

ANTI-CONFABULATION: calendar EVENT data (titles/times/actual inbox threads) has
NO read-model source — it lives behind a live Google broker that is BLOCKED.
DATA GAP: live calendar events and live email metadata are explicitly flagged,
not fabricated. A flagged gap is SUCCESS; fake data is FAILURE.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from context_source import annotate_facts_with_ledger_provenance, ledger_machine_proof

SCHEMA_VERSION = "cassandra_context_packet_v0"
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")

# Read-models Cassandra cares about — only real files, no invented paths
CASSANDRA_READ_MODELS = (
    "cassandra_email_calendar_delta_detangle.json",   # capability classification + surface posture
    "cassandra_runtime_wiring_audit.json",            # service state, wiring gaps, roundtrip steps
    "agent_presence.json",                            # fleet presence including Cassandra's own state
    "sync_health.json",                               # PC/Mac sync pipeline status
    "cassandra_send_status_dry_run.json",             # Cassandra send/no-send posture
    "cassandra_governed_review_packet_request_proof.json",  # governed review packet proof
    "cassandra_draft_review_packet.json",             # draft preview packet posture
    "cassandra_listener_governed_intake_synthetic_proof.json",  # intake proof
)


# ---------------------------------------------------------------------------
# Shared helpers (mirror pattern from guardian_context_packet.py)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Per-read-model fact extractors
# ---------------------------------------------------------------------------

def _email_calendar_capability_facts(
    path: Path, payload: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Extract Cassandra email/calendar lane capability posture from delta-detangle."""
    facts: list[dict[str, Any]] = []
    fresh = _freshness(path, payload)
    src = _display_ref(path)
    provenance = "generated_read_model"

    detangle_status = str(payload.get("detangle_status") or "").strip()
    if detangle_status:
        _append_fact(
            facts,
            topic="email_calendar_posture",
            label="Email/calendar detangle status",
            value=detangle_status,
            source_ref=src,
            provenance=provenance,
            freshness=fresh,
        )

    current = payload.get("current_governed_capabilities")
    if isinstance(current, Mapping):
        review_ready = bool(current.get("governed_review_packet_path_ready"))
        draft_ready = bool(current.get("draft_preview_read_model_ready"))
        execution_enabled = bool(current.get("execution_enabled"))
        approval_receipt = bool(current.get("approval_receipt_present"))
        _append_fact(
            facts,
            topic="email_calendar_posture",
            label="Governed capability posture",
            value=(
                f"Review packet path ready: {review_ready}. "
                f"Draft preview read-model ready: {draft_ready}. "
                f"Execution enabled: {execution_enabled}. "
                f"Approval receipt present: {approval_receipt}."
            ),
            source_ref=src,
            provenance=provenance,
            freshness=fresh,
        )

    # Classification counts — what surfaces are governed vs blocked
    counts = payload.get("classification_counts")
    if isinstance(counts, Mapping) and counts:
        governed = counts.get("GOVERNED_REVIEW_PACKET_READY", 0)
        live_blocked = counts.get("LIVE_GMAIL_BLOCKED", 0)
        email_blocked = counts.get("EMAIL_SEND_BLOCKED", 0)
        cal_blocked = counts.get("CALENDAR_DISCOVERY_BLOCKED", 0)
        oauth_blocked = counts.get("OAUTH_CREDENTIAL_BLOCKED", 0)
        _append_fact(
            facts,
            topic="email_calendar_posture",
            label="Email/calendar surface classification counts",
            value=(
                f"Governed review-ready surfaces: {governed}. "
                f"Live Gmail blocked: {live_blocked}. "
                f"Email send blocked: {email_blocked}. "
                f"Calendar discovery blocked: {cal_blocked}. "
                f"OAuth/credential blocked: {oauth_blocked}."
            ),
            source_ref=src,
            provenance=provenance,
            freshness=fresh,
        )

    # Calendar operator context — surface the known state without faking events
    cal_ctx = payload.get("calendar_operator_context")
    if isinstance(cal_ctx, Mapping):
        merged_recorded = bool(cal_ctx.get("google_apple_calendar_merged_context_recorded"))
        live_cal_enabled = bool(cal_ctx.get("live_calendar_access_enabled"))
        cleanup_started = bool(cal_ctx.get("generic_calendar_cleanup_started"))
        normalization_allowed = bool(cal_ctx.get("calendar_normalization_allowed_now"))
        _append_fact(
            facts,
            topic="calendar_state",
            label="Calendar operator context (posture only — no live events)",
            value=(
                f"Google/Apple merged context recorded: {merged_recorded}. "
                f"Live calendar access enabled: {live_cal_enabled}. "
                f"Calendar cleanup started: {cleanup_started}. "
                f"Calendar normalization allowed now: {normalization_allowed}. "
                "NOTE: Live calendar event titles/times have NO read-model source — "
                "they are behind a blocked Google broker. This is a DATA GAP."
            ),
            source_ref=src,
            provenance=provenance,
            pii_tier="PUBLIC",
            freshness=fresh,
        )

    # Protected access requirements
    protected = payload.get("protected_access_requirements")
    if isinstance(protected, Mapping):
        gate_required = bool(protected.get("protected_access_gate_required_for_live_gmail_calendar"))
        unknown_fail_closed = bool(protected.get("unknown_surfaces_fail_closed"))
        _append_fact(
            facts,
            topic="email_calendar_posture",
            label="Protected access requirements",
            value=(
                f"Protected access gate required for live Gmail/calendar: {gate_required}. "
                f"Unknown email/calendar surfaces fail closed: {unknown_fail_closed}. "
                "OAuth/credential access allowed now: False."
            ),
            source_ref=src,
            provenance=provenance,
            freshness=fresh,
        )

    # Explicit data gap flag for live calendar events
    _append_fact(
        facts,
        topic="data_gap",
        label="DATA GAP: live calendar events",
        value=(
            "Live calendar event titles, times, and meeting details are NOT available in any "
            "read-model. They exist only behind a live Google Calendar broker that is BLOCKED "
            "(live_calendar_access_enabled=False). Cassandra cannot surface real calendar "
            "events without a protected-access workflow being built and approved. "
            "This gap must not be filled with fabricated events."
        ),
        source_ref=src,
        provenance="gap_detection",
        freshness=fresh,
    )

    # Explicit data gap flag for live email inbox
    _append_fact(
        facts,
        topic="data_gap",
        label="DATA GAP: live email inbox / thread content",
        value=(
            "Live email inbox metadata (subject lines, sender, counts) and thread bodies are "
            "NOT available in any read-model. Live Gmail access is BLOCKED "
            "(live_gmail_access_enabled=False). Cassandra cannot triage real email "
            "without a protected-access workflow being built and approved. "
            "This gap must not be filled with fabricated email data."
        ),
        source_ref=src,
        provenance="gap_detection",
        freshness=fresh,
    )

    return facts


def _runtime_wiring_facts(
    path: Path, payload: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Extract Cassandra runtime wiring posture — service state, gaps, roundtrip steps."""
    facts: list[dict[str, Any]] = []
    fresh = _freshness(path, payload)
    src = _display_ref(path)
    provenance = "generated_read_model:wiring_audit"

    counts = payload.get("counts")
    if isinstance(counts, Mapping):
        services = counts.get("service_count", "?")
        gaps = counts.get("gap_count", 0)
        live_proven = bool(counts.get("live_receive_proven"))
        governed_storage = bool(counts.get("governed_storage_proven"))
        reply_ready = bool(counts.get("reply_ready"))
        unsafe_surfaces = counts.get("unsafe_surface_count", 0)
        already_ported = counts.get("already_ported_count", 0)
        _append_fact(
            facts,
            topic="runtime_wiring",
            label="Cassandra runtime wiring posture",
            value=(
                f"Service count: {services}. "
                f"Wiring gaps: {gaps}. "
                f"Live Telegram receive proven: {live_proven}. "
                f"Governed storage proven: {governed_storage}. "
                f"Reply ready: {reply_ready}. "
                f"Unsafe surfaces: {unsafe_surfaces}. "
                f"Already ported to Repo A: {already_ported}."
            ),
            source_ref=src,
            provenance=provenance,
            freshness=fresh,
        )

    # Surface the open gaps so operator knows exactly what's unresolved
    gaps_list = [g for g in payload.get("gaps", ()) if isinstance(g, Mapping)]
    if gaps_list:
        gap_lines = []
        for gap in gaps_list[:5]:
            sev = str(gap.get("severity") or "?")
            kind = str(gap.get("gap_kind") or "?")
            title = str(gap.get("title") or "?")
            next_move = str(gap.get("next_safe_move") or "")
            gap_lines.append(f"[{sev}] {kind}: {title}. Next: {next_move}")
        _append_fact(
            facts,
            topic="runtime_wiring",
            label="Wiring gaps (open)",
            value="; ".join(gap_lines),
            source_ref=src,
            provenance=provenance,
            freshness=fresh,
        )

    # Roundtrip step status summary
    steps = [s for s in payload.get("roundtrip_steps", ()) if isinstance(s, Mapping)]
    if steps:
        step_summary = "; ".join(
            f"{s.get('step_name','?')}={s.get('status','?')}"
            for s in steps
        )
        _append_fact(
            facts,
            topic="runtime_wiring",
            label="Roundtrip step status",
            value=step_summary,
            source_ref=src,
            provenance=provenance,
            freshness=fresh,
        )

    # Service-level status
    services_list = payload.get("service_status")
    if isinstance(services_list, list):
        active = [s for s in services_list if isinstance(s, Mapping) and str(s.get("active_state") or "") == "active"]
        _append_fact(
            facts,
            topic="runtime_wiring",
            label="Cassandra systemd service states",
            value=(
                f"{len(active)} of {len(services_list)} Cassandra services active. "
                + ("; ".join(
                    f"{s.get('service_name', '?')}={s.get('active_state', '?')}"
                    for s in services_list
                    if isinstance(s, Mapping)
                )[:400] or "no services listed")
            ),
            source_ref=src,
            provenance=provenance,
            freshness=fresh,
        )

    return facts


def _cassandra_presence_facts(
    path: Path, payload: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Extract Cassandra-specific presence state from agent_presence.json."""
    facts: list[dict[str, Any]] = []
    fresh = _freshness(path, payload)
    src = _display_ref(path)
    provenance = "generated_read_model"

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
            label="Fleet online agents",
            value=(
                f"{len(online)} of {len(agents)} agents online: {names or 'none listed online'}."
            ),
            source_ref=src,
            provenance=provenance,
            freshness=fresh,
        )

    # Cassandra's specific presence entry
    cass_presence = payload.get("cassandra_presence")
    if isinstance(cass_presence, Mapping):
        actual = str(cass_presence.get("actual_state") or "unknown")
        blocker = str(cass_presence.get("blocker") or "none")
        recovery_status = str(cass_presence.get("recovery_status") or "unknown")
        _append_fact(
            facts,
            topic="cassandra_presence",
            label="Cassandra own presence state",
            value=(
                f"Actual state: {actual}. "
                f"Blocker: {blocker}. "
                f"Recovery status: {recovery_status}. "
                f"Desired state: {cass_presence.get('desired_state', 'online')}."
            ),
            source_ref=src,
            provenance=provenance,
            freshness=fresh,
        )

        # Surface the last recovery attempt if relevant
        last_attempt = cass_presence.get("last_recovery_attempt")
        if isinstance(last_attempt, Mapping) and last_attempt.get("attempted"):
            succeeded = bool(last_attempt.get("succeeded"))
            attempt_blocker = str(last_attempt.get("blocker") or "")
            _append_fact(
                facts,
                topic="cassandra_presence",
                label="Last Cassandra recovery attempt",
                value=(
                    f"Attempted at {last_attempt.get('attempted_at', '?')}. "
                    f"Succeeded: {succeeded}. "
                    f"Blocker: {attempt_blocker or 'none'}. "
                    f"Exit code: {last_attempt.get('exit_code', '?')}."
                ),
                source_ref=src,
                provenance=provenance,
                freshness=fresh,
            )

    # Blockers summary
    blockers = [b for b in payload.get("blockers", ()) if isinstance(b, Mapping)]
    if blockers:
        blocker_text = "; ".join(
            f"{b.get('agent_id','?')}: {b.get('blocker','?')}"
            for b in blockers[:5]
        )
        _append_fact(
            facts,
            topic="agent_presence",
            label="Fleet presence blockers",
            value=blocker_text,
            source_ref=src,
            provenance=provenance,
            freshness=fresh,
        )

    return facts


def _sync_health_facts(
    path: Path, payload: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Extract sync health relevant to Cassandra's context delivery."""
    facts: list[dict[str, Any]] = []
    fresh = _freshness(path, payload)
    src = _display_ref(path)
    provenance = "generated_read_model"

    sync_state = str(payload.get("sync_lifecycle_state") or "").strip()
    trust = str(payload.get("trust_status") or "").strip()
    display = str(payload.get("display_status") or "").strip()

    if sync_state or trust:
        last_mac = payload.get("last_mac_completion") if isinstance(payload.get("last_mac_completion"), Mapping) else {}
        last_time = str(last_mac.get("time") or "unknown")
        _append_fact(
            facts,
            topic="sync_health",
            label="PC/Mac read-model sync health",
            value=(
                f"Sync lifecycle: {sync_state or 'unknown'}. "
                f"Trust status: {trust or 'unknown'}. "
                f"Display status: {display or 'unknown'}. "
                f"Last Mac sync completion: {last_time}."
            ),
            source_ref=src,
            provenance=provenance,
            freshness=fresh,
        )

    # Surfance if there's an operator-required action
    check = payload.get("check_transmission_display")
    if isinstance(check, Mapping):
        headline = str(check.get("headline") or "").strip()
        next_move = str(check.get("next_safe_move") or "").strip()
        lamp = str(check.get("lamp_state") or "").strip()
        if headline:
            _append_fact(
                facts,
                topic="sync_health",
                label="Sync check transmission",
                value=(
                    f"Headline: {headline}. "
                    f"Lamp state: {lamp}. "
                    f"Next safe move: {next_move or 'none'}."
                ),
                source_ref=src,
                provenance=provenance,
                freshness=fresh,
            )

    return facts


def _send_posture_facts(
    path: Path, payload: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Extract Cassandra send/no-send dry-run posture."""
    facts: list[dict[str, Any]] = []
    fresh = _freshness(path, payload)
    src = _display_ref(path)
    provenance = "generated_read_model"

    schema_ver = str(payload.get("schema_version") or "").strip()
    if not schema_ver:
        return facts

    # Surface the key no-send posture signals
    send_allowed = bool(payload.get("send_allowed", False))
    dry_run = bool(payload.get("dry_run_mode", payload.get("dry_run", True)))
    hold_active = bool(payload.get("send_hold_active", payload.get("no_send_hold_active", True)))

    # Summarise whichever fields are present
    posture_parts = [
        f"send_allowed={send_allowed}",
        f"dry_run={dry_run}",
        f"send_hold_active={hold_active}",
    ]

    # Include any operator_note or status summary if present
    note = str(payload.get("operator_note") or payload.get("status_summary") or "").strip()
    if note:
        posture_parts.append(f"note: {note[:200]}")

    _append_fact(
        facts,
        topic="send_posture",
        label="Cassandra send/no-send dry-run posture",
        value="; ".join(posture_parts),
        source_ref=src,
        provenance=provenance,
        freshness=fresh,
    )

    return facts


def _intake_proof_facts(
    path: Path, payload: Mapping[str, Any], label_prefix: str = "Governed intake proof"
) -> list[dict[str, Any]]:
    """Extract intake/proof posture from governed review packet or intake proof read-model."""
    facts: list[dict[str, Any]] = []
    fresh = _freshness(path, payload)
    src = _display_ref(path)
    provenance = "generated_read_model"

    schema_ver = str(payload.get("schema_version") or "").strip()
    if not schema_ver:
        return facts

    # Try a few common summary/posture fields
    summary = str(
        payload.get("posture_summary")
        or payload.get("proof_summary")
        or payload.get("status_summary")
        or payload.get("operator_summary")
        or ""
    ).strip()

    if summary:
        _append_fact(
            facts,
            topic="governed_intake_posture",
            label=label_prefix,
            value=summary[:600],
            source_ref=src,
            provenance=provenance,
            freshness=fresh,
        )
    elif schema_ver:
        # No summary but schema is present — surface schema version as proof of existence
        _append_fact(
            facts,
            topic="governed_intake_posture",
            label=f"{label_prefix} (schema present)",
            value=f"Read-model present: schema_version={schema_ver}.",
            source_ref=src,
            provenance=provenance,
            freshness=fresh,
        )

    return facts


# ---------------------------------------------------------------------------
# Main read-model loader
# ---------------------------------------------------------------------------

def _cassandra_read_model_facts(
    root: Path,
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    """Load all Cassandra read-models and extract dank, grounded facts."""
    facts: list[dict[str, Any]] = []
    refs: list[str] = []
    proof: dict[str, Any] = {"read_model_presence": {}}

    payloads: dict[str, dict[str, Any]] = {}
    for name in CASSANDRA_READ_MODELS:
        path = root / name
        payload = _read_json(path)
        proof["read_model_presence"][name] = bool(payload)
        if not payload:
            continue
        payloads[name] = payload
        refs.append(_display_ref(path))

    # 1. Email/calendar capability posture (primary Cassandra lane)
    name = "cassandra_email_calendar_delta_detangle.json"
    if name in payloads:
        facts.extend(_email_calendar_capability_facts(root / name, payloads[name]))

    # 2. Runtime wiring posture — services, gaps, roundtrip proof
    name = "cassandra_runtime_wiring_audit.json"
    if name in payloads:
        facts.extend(_runtime_wiring_facts(root / name, payloads[name]))

    # 3. Agent presence — Cassandra's own state + fleet
    name = "agent_presence.json"
    if name in payloads:
        facts.extend(_cassandra_presence_facts(root / name, payloads[name]))

    # 4. Sync health — is the read-model pipeline healthy?
    name = "sync_health.json"
    if name in payloads:
        facts.extend(_sync_health_facts(root / name, payloads[name]))

    # 5. Send/no-send dry-run posture
    name = "cassandra_send_status_dry_run.json"
    if name in payloads:
        facts.extend(_send_posture_facts(root / name, payloads[name]))

    # 6. Governed review packet proof
    name = "cassandra_governed_review_packet_request_proof.json"
    if name in payloads:
        facts.extend(
            _intake_proof_facts(root / name, payloads[name], label_prefix="Governed review packet proof")
        )

    # 7. Draft review packet posture
    name = "cassandra_draft_review_packet.json"
    if name in payloads:
        facts.extend(
            _intake_proof_facts(root / name, payloads[name], label_prefix="Draft review packet posture")
        )

    # 8. Listener governed intake synthetic proof
    name = "cassandra_listener_governed_intake_synthetic_proof.json"
    if name in payloads:
        facts.extend(
            _intake_proof_facts(root / name, payloads[name], label_prefix="Listener intake synthetic proof")
        )

    return facts, refs, proof


# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------

def build_cassandra_context_packet(
    *,
    question: str = "",
    read_model_root: str | Path | None = None,
    require_email_calendar_read_model: bool = True,
) -> dict[str, Any]:
    """Build a grounded, dank context packet for Cassandra's lane.

    Args:
        question: The operator's question (for packet ID hashing).
        read_model_root: Path to generated/read_models directory.
        require_email_calendar_read_model: If True, inserts a DATA GAP fact when
            the primary email/calendar read-model is absent (never raises — gaps
            are explicit facts, not exceptions).

    Returns:
        A dict with schema_version, packet_id, facts, bounds, machine_proof,
        packet_text.
    """
    root = Path(read_model_root) if read_model_root is not None else DEFAULT_READ_MODEL_ROOT
    generated_at = _utc_now()

    facts, refs, proof = _cassandra_read_model_facts(root)

    email_cal_present = proof["read_model_presence"].get(
        "cassandra_email_calendar_delta_detangle.json", False
    )

    if require_email_calendar_read_model and not email_cal_present:
        facts.insert(
            0,
            {
                "fact_id": "email_calendar_posture:MISSING",
                "topic": "email_calendar_posture",
                "label": "DATA GAP: cassandra_email_calendar_delta_detangle.json absent",
                "value": (
                    "cassandra_email_calendar_delta_detangle.json not found. "
                    "Run scripts/export_cassandra_email_calendar_delta_detangle.py "
                    "to regenerate the email/calendar capability posture read-model."
                ),
                "provenance": "gap_detection",
                "freshness": {"as_of": generated_at},
                "source_ref": "generated/read_models/cassandra_email_calendar_delta_detangle.json",
                "pii_tier": "PUBLIC",
            },
        )

    facts = annotate_facts_with_ledger_provenance(
        facts,
        builder_name="cassandra_context_packet.build_cassandra_context_packet",
    )

    source_refs = tuple(
        dict.fromkeys(
            [
                *(f["source_ref"] for f in facts),
                *(str(f.get("ledger_source_ref") or "") for f in facts if f.get("ledger_source_ref")),
                *refs,
            ]
        )
    )
    basis = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "question_hash": hashlib.sha256(str(question or "").encode("utf-8")).hexdigest(),
        "source_refs": source_refs,
        "fact_count": len(facts),
    }
    packet_id = f"cassandra_context_packet:{_short_hash(basis)}"

    packet: dict[str, Any] = {
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
            "email_send_allowed": False,
            "gmail_draft_creation_allowed": False,
            "calendar_mutation_allowed": False,
            "live_email_access_allowed": False,
            "live_calendar_access_allowed": False,
            "oauth_credential_access_allowed": False,
            "claims_must_trace_to_packet": True,
        },
        "machine_proof": {
            "packet_compiler": "cassandra_context_packet.build_cassandra_context_packet",
            "read_model_root": str(root),
            "fact_count": len(facts),
            "email_calendar_read_model_present": email_cal_present,
            **ledger_machine_proof(
                builder_name="cassandra_context_packet.build_cassandra_context_packet",
                facts=facts,
            ),
            **proof,
        },
    }
    packet["packet_text"] = format_cassandra_context_packet(packet)
    return packet


def format_cassandra_context_packet(packet: Mapping[str, Any]) -> str:
    """Format a human-readable text rendering of the Cassandra context packet."""
    facts = [f for f in packet.get("facts", ()) if isinstance(f, Mapping)]
    bounds = packet.get("bounds", {}) if isinstance(packet.get("bounds"), Mapping) else {}
    lines = [
        f"CASSANDRA_CONTEXT_PACKET {packet.get('packet_id', '')}",
        f"Generated: {packet.get('generated_at', '')}",
        "",
        "Grounded facts (Cassandra lane: email + calendar):",
    ]
    for fact in facts[:25]:
        src = str(fact.get("source_ref") or "")
        prov = str(fact.get("provenance") or "")
        tier = str(fact.get("pii_tier") or "PUBLIC")
        lines.append(
            f"- [{fact.get('topic')}] {fact.get('label')}: {fact.get('value')} "
            f"[tier={tier}; provenance={prov}; source={src}]"
        )
    lines.extend([
        "",
        "Boundaries (Cassandra lane):",
        f"- SEND_HOLD absolute: {bool(bounds.get('send_hold_absolute', True))}",
        f"- Outbound send allowed: {bool(bounds.get('outbound_send_allowed', False))}",
        f"- Email send allowed: {bool(bounds.get('email_send_allowed', False))}",
        f"- Gmail draft creation allowed: {bool(bounds.get('gmail_draft_creation_allowed', False))}",
        f"- Calendar mutation allowed: {bool(bounds.get('calendar_mutation_allowed', False))}",
        f"- Live email access allowed: {bool(bounds.get('live_email_access_allowed', False))}",
        f"- Live calendar access allowed: {bool(bounds.get('live_calendar_access_allowed', False))}",
        f"- OAuth/credential access allowed: {bool(bounds.get('oauth_credential_access_allowed', False))}",
    ])
    return "\n".join(lines).strip()


__all__ = [
    "SCHEMA_VERSION",
    "CASSANDRA_READ_MODELS",
    "build_cassandra_context_packet",
    "format_cassandra_context_packet",
]
