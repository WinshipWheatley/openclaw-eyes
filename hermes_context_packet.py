"""Deterministic context packet for Hermes's routing/handoff + SEND_HOLD safety lane.

Hermes is a READ-ONLY safety sidecar: it explains routing/adapter boundaries,
clarifies the canonical agent roster, and REFUSES sends/money (SEND_HOLD hard).

DANK contract:
  (1) GROUNDED  — every fact carries source_ref + provenance; no invented data.
  (2) CURRENT   — freshness tracked from read-model generated_at or file mtime.
  (3) USEFUL    — surfaces exactly what operator asks Hermes: routing targets,
                  blocked output kinds, SEND_HOLD posture, authority flags.
  (4) IN-VOICE  — truthful facts only; brain renders persona tone separately.
  (5) LANE-RICH — deeply reflects Hermes's world: route targets, blocked outputs,
                  gateway policy, advisory memo contract, change sentinel.

ANTI-CONFABULATION (CRITICAL):
  - Route targets are loaded from DEFAULT_AGENT_LANE_SEEDS — the SAME source the
    gateway uses (_agent_route_targets in openclaw_hermes_gateway_policy.py).
    If the registry import fails, a DATA GAP is flagged.
  - Read-model absence → flagged gap, never fabricated facts.
  - All authority flags remain hard-False in every packet.
  - This module never sends, executes, writes, or calls models.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from context_source import annotate_facts_with_ledger_provenance, ledger_machine_proof

SCHEMA_VERSION = "hermes_context_packet_v0"
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")

# Read-models Hermes cares about, in priority order.
HERMES_READ_MODELS = (
    "hermes_mission_sentinel.json",      # live-arts / invoice send-readiness sentinel
    "hermes_gravity_controller.json",    # purpose-bound gravity controller decisions
    "hermes_chief_build_handoff.json",   # Hermes→Chief build handoff state
    "openclaw_change_sentinel.json",     # system-wide change sentinel (hermes_summary key)
    "agent_presence.json",               # fleet online state
    "openclaw_hermes_sidecar.json",      # sidecar inventory
)

# Hard-coded authority flags — NEVER flipped in any packet.
# send_hold_absolute=True means HOLD is ACTIVE.
_HERMES_AUTHORITY_FLAGS: dict[str, bool] = {
    "send_hold_absolute": True,
    "outbound_send_allowed": False,
    "money_movement_allowed": False,
    "ledger_mutation_allowed": False,
    "agent_dispatch_allowed": False,
    "approval_decision_allowed": False,
    "canonical_write_allowed": False,
    "tool_execution_allowed": False,
    "model_execution_allowed": False,
    "coupa_browser_allowed": False,
    "runtime_authority": False,
}


# ---------------------------------------------------------------------------
# Utility helpers (mirrors maestro_context_packet / guardian_context_packet)
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
            generated_at = (
                datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
                .replace(microsecond=0)
                .isoformat()
            )
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
# Lane-specific fact extractors
# ---------------------------------------------------------------------------

def _route_target_facts() -> list[dict[str, Any]]:
    """Load canonical route targets from agent_lane_registry.DEFAULT_AGENT_LANE_SEEDS.

    This is the SAME source the gateway policy uses (_agent_route_targets in
    openclaw_hermes_gateway_policy.py), so Hermes's context packet stays
    consistent with what the gateway will actually route.

    DATA GAP: if the import fails, we flag it explicitly — never fabricate.
    """
    facts: list[dict[str, Any]] = []
    source_ref = "agent_lane_registry.DEFAULT_AGENT_LANE_SEEDS"
    provenance = "agent_lane_registry_seeds"

    try:
        from agent_lane_registry import DEFAULT_AGENT_LANE_SEEDS  # noqa: PLC0415

        agents = []
        for seed in DEFAULT_AGENT_LANE_SEEDS:
            agents.append({
                "agent_id": seed.agent_id,
                "display_name": seed.display_name,
                "lane_id": seed.lane_id,
                "authority_level": seed.authority_level,
                "blocked_output_kinds": list(seed.blocked_output_kinds),
                "role_summary": seed.role_summary,
            })

        # Roster fact
        roster_summary = "; ".join(
            f"{a['agent_id']} ({a['authority_level']}, lane={a['lane_id']})"
            for a in agents
        )
        _append_fact(
            facts,
            topic="route_targets",
            label="Canonical agent roster (route targets)",
            value=(
                f"{len(agents)} registered agents: {roster_summary}. "
                "Source: DEFAULT_AGENT_LANE_SEEDS (same source as gateway policy)."
            ),
            source_ref=source_ref,
            provenance=provenance,
        )

        # Hermes's own lane bounds — most critical for self-awareness
        hermes_seed = next(
            (s for s in DEFAULT_AGENT_LANE_SEEDS if s.agent_id == "hermes"), None
        )
        if hermes_seed is not None:
            blocked_str = ", ".join(sorted(hermes_seed.blocked_output_kinds))
            _append_fact(
                facts,
                topic="hermes_lane_bounds",
                label="Hermes blocked output kinds (canonical)",
                value=(
                    f"Hermes lane={hermes_seed.lane_id}; "
                    f"authority={hermes_seed.authority_level}; "
                    f"blocked outputs: {blocked_str}."
                ),
                source_ref=source_ref,
                provenance=provenance,
            )
            hints_str = ", ".join(hermes_seed.routing_hints)
            if hints_str:
                _append_fact(
                    facts,
                    topic="hermes_lane_bounds",
                    label="Hermes routing hints (what Hermes handles)",
                    value=hints_str,
                    source_ref=source_ref,
                    provenance=provenance,
                )
            if hermes_seed.notes:
                _append_fact(
                    facts,
                    topic="hermes_lane_bounds",
                    label="Hermes lane notes",
                    value=str(hermes_seed.notes),
                    source_ref=source_ref,
                    provenance=provenance,
                )

    except Exception as exc:  # noqa: BLE001
        _append_fact(
            facts,
            topic="route_targets",
            label="DATA GAP: agent_lane_registry import failed",
            value=(
                f"Cannot load canonical route targets: {type(exc).__name__}: {exc}. "
                "Run agent_lane_registry.seed_agent_lane_registry() to populate the registry."
            ),
            source_ref=source_ref,
            provenance="gap_detection",
        )

    return facts


def _gateway_policy_facts() -> list[dict[str, Any]]:
    """Extract Hermes gateway policy posture from the deterministic gateway module.

    Reads the SEND_HOLD env vars and probes the gateway policy to surface
    the live safety posture for this session.  READ-ONLY: probing fires the
    deterministic truthful_reply_for_text, which has no side effects.
    """
    facts: list[dict[str, Any]] = []
    source_ref = "openclaw_hermes_gateway_policy"
    provenance = "gateway_policy_module"

    test_mode = bool(int(os.environ.get("OPENCLAW_TEST_MODE", "0")))
    send_hold = bool(int(os.environ.get("OPENCLAW_SEND_HOLD", "0")))

    _append_fact(
        facts,
        topic="send_hold_posture",
        label="SEND_HOLD posture (env)",
        value=(
            f"OPENCLAW_SEND_HOLD={int(send_hold)}. "
            f"OPENCLAW_TEST_MODE={int(test_mode)}. "
            "SEND_HOLD is always in force for Hermes: no external send, no money, "
            "no route receipt written, no agent dispatch."
        ),
        source_ref=source_ref,
        provenance=provenance,
    )

    try:
        import openclaw_hermes_gateway_policy as gwp  # noqa: PLC0415

        has_truthful_fn = callable(getattr(gwp, "truthful_reply_for_text", None))
        has_sanitize_fn = callable(getattr(gwp, "sanitize_gateway_response", None))
        # Probe a known SEND_HOLD phrase — deterministic, no side effects.
        probe_result = gwp.truthful_reply_for_text("send an email to cassandra")
        send_blocked = probe_result is not None and "SEND_HOLD" in probe_result

        _append_fact(
            facts,
            topic="send_hold_posture",
            label="Gateway policy integrity check",
            value=(
                f"truthful_reply_for_text present: {has_truthful_fn}. "
                f"sanitize_gateway_response present: {has_sanitize_fn}. "
                f"Send-denial fires on probe: {send_blocked}. "
                "Checks from openclaw_hermes_gateway_policy — same module gateway patches at runtime."
            ),
            source_ref=source_ref,
            provenance=provenance,
        )
    except Exception as exc:  # noqa: BLE001
        _append_fact(
            facts,
            topic="send_hold_posture",
            label="DATA GAP: openclaw_hermes_gateway_policy import failed",
            value=f"Gateway policy module unavailable: {type(exc).__name__}: {exc}.",
            source_ref=source_ref,
            provenance="gap_detection",
        )

    return facts


def _advisory_contract_facts() -> list[dict[str, Any]]:
    """Surface Hermes advisory contract constants (hermes_advisory_packet.py)."""
    facts: list[dict[str, Any]] = []
    source_ref = "hermes_advisory_packet"
    provenance = "advisory_contract_module"

    try:
        import hermes_advisory_packet as hap  # noqa: PLC0415

        _append_fact(
            facts,
            topic="advisory_contract",
            label="Hermes advisory authority level",
            value=(
                f"authority_level={hap.HERMES_AUTHORITY_LEVEL}. "
                f"output_kind={hap.HERMES_OUTPUT_KIND}. "
                f"promotion_required={hap.HERMES_PROMOTION_REQUIRED}. "
                f"Permission fields hard-False: {', '.join(hap.FALSE_PERMISSION_FIELDS)}."
            ),
            source_ref=source_ref,
            provenance=provenance,
        )
        _append_fact(
            facts,
            topic="advisory_contract",
            label="Hermes withheld surfaces (advisory contract)",
            value=", ".join(hap.REQUIRED_WITHHELD_SURFACES),
            source_ref=source_ref,
            provenance=provenance,
        )
    except Exception as exc:  # noqa: BLE001
        _append_fact(
            facts,
            topic="advisory_contract",
            label="DATA GAP: hermes_advisory_packet import failed",
            value=f"Advisory contract module unavailable: {type(exc).__name__}: {exc}.",
            source_ref=source_ref,
            provenance="gap_detection",
        )

    return facts


def _mission_sentinel_facts(path: Path, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Extract key routing/safety facts from hermes_mission_sentinel.json."""
    facts: list[dict[str, Any]] = []
    fresh = _freshness(path, payload)
    src = _display_ref(path)
    provenance = "generated_read_model"

    automation_status = str(payload.get("automation_ready_status") or "").strip()
    contract_status = str(payload.get("contract_status") or "").strip()
    if automation_status or contract_status:
        _append_fact(
            facts,
            topic="mission_sentinel",
            label="Mission sentinel automation/contract status",
            value=(
                f"automation_ready_status={automation_status or 'absent'}. "
                f"contract_status={contract_status or 'absent'}."
            ),
            source_ref=src,
            provenance=provenance,
            freshness=fresh,
        )

    authority_boundary = payload.get("authority_boundary")
    if isinstance(authority_boundary, Mapping):
        true_flags = [k for k, v in authority_boundary.items() if v is True]
        false_flags = [k for k, v in authority_boundary.items() if v is False]
        _append_fact(
            facts,
            topic="mission_sentinel",
            label="Mission sentinel authority boundary",
            value=(
                f"{len(false_flags)} flags explicitly False; "
                f"{len(true_flags)} flags True (SHOULD be zero): "
                f"{', '.join(true_flags) or 'none (correct)'}. "
                "All sends/mutations/approvals remain off."
            ),
            source_ref=src,
            provenance=provenance,
            freshness=fresh,
        )

    blockers = payload.get("current_blockers")
    if isinstance(blockers, (list, tuple)) and blockers:
        _append_fact(
            facts,
            topic="mission_sentinel",
            label="Current blockers (send readiness)",
            value="; ".join(str(b) for b in blockers[:8]),
            source_ref=src,
            provenance=provenance,
            freshness=fresh,
            pii_tier="LIGHT",
        )

    operator_summary = str(payload.get("operator_summary") or "").strip()
    if operator_summary:
        _append_fact(
            facts,
            topic="mission_sentinel",
            label="Mission sentinel operator summary",
            value=operator_summary,
            source_ref=src,
            provenance=provenance,
            freshness=fresh,
            pii_tier="LIGHT",
        )

    return facts


def _gravity_controller_facts(path: Path, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Extract Hermes gravity controller posture."""
    facts: list[dict[str, Any]] = []
    fresh = _freshness(path, payload)
    src = _display_ref(path)
    provenance = "generated_read_model"

    contract_status = str(payload.get("contract_status") or "").strip()
    machine_proof = payload.get("machine_proof")
    if isinstance(machine_proof, Mapping):
        all_false = bool(machine_proof.get("all_authority_flags_false"))
        read_model_only = bool(machine_proof.get("read_model_only"))
        example_count = machine_proof.get("example_count", 0)
        _append_fact(
            facts,
            topic="gravity_controller",
            label="Gravity controller machine proof",
            value=(
                f"contract_status={contract_status or 'absent'}. "
                f"all_authority_flags_false={all_false}. "
                f"read_model_only={read_model_only}. "
                f"example_decision_count={example_count}."
            ),
            source_ref=src,
            provenance=provenance,
            freshness=fresh,
        )

    gravity_statuses = payload.get("gravity_statuses")
    if isinstance(gravity_statuses, (list, tuple)) and gravity_statuses:
        _append_fact(
            facts,
            topic="gravity_controller",
            label="Defined gravity statuses",
            value=", ".join(str(g) for g in gravity_statuses),
            source_ref=src,
            provenance=provenance,
            freshness=fresh,
        )

    operator_summary = payload.get("operator_summary")
    if isinstance(operator_summary, Mapping):
        dev_view = str(operator_summary.get("developer_view") or "").strip()
        if dev_view:
            _append_fact(
                facts,
                topic="gravity_controller",
                label="Gravity controller operator summary (developer view)",
                value=dev_view,
                source_ref=src,
                provenance=provenance,
                freshness=fresh,
            )

    return facts


def _build_handoff_facts(path: Path, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Extract Hermes→Chief build handoff state."""
    facts: list[dict[str, Any]] = []
    fresh = _freshness(path, payload)
    src = _display_ref(path)
    provenance = "generated_read_model"

    authority_boundary = payload.get("authority_boundary")
    if isinstance(authority_boundary, Mapping):
        true_flags = [k for k, v in authority_boundary.items() if v is True]
        _append_fact(
            facts,
            topic="build_handoff",
            label="Hermes→Chief build handoff authority boundary",
            value=(
                f"{len(authority_boundary)} flags in boundary. "
                f"Flags set True (MUST be empty): {', '.join(true_flags) or 'none (correct)'}. "
                "Git-push and all mutations remain off."
            ),
            source_ref=src,
            provenance=provenance,
            freshness=fresh,
        )

    button_enabled = payload.get("button_enabled")
    if button_enabled is not None:
        _append_fact(
            facts,
            topic="build_handoff",
            label="Build handoff button state",
            value=f"button_enabled={bool(button_enabled)}.",
            source_ref=src,
            provenance=provenance,
            freshness=fresh,
        )

    return facts


def _change_sentinel_facts(path: Path, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Extract Hermes summary from openclaw_change_sentinel.json."""
    facts: list[dict[str, Any]] = []
    fresh = _freshness(path, payload)
    src = _display_ref(path)
    provenance = "generated_read_model"

    # Prefer hermes_summary (singular dict) — same key maestro_context_packet uses.
    summary = payload.get("hermes_summary")
    if not isinstance(summary, Mapping):
        summaries = payload.get("hermes_summaries")
        if isinstance(summaries, (list, tuple)) and summaries:
            summary = summaries[0] if isinstance(summaries[0], Mapping) else {}

    if isinstance(summary, Mapping):
        what_changed = str(summary.get("what_changed") or "").strip()
        what_to_do_next = str(summary.get("what_to_do_next") or "").strip()
        action_required = summary.get("action_required", False)
        parts = [p for p in (what_changed, what_to_do_next) if p]
        if parts:
            _append_fact(
                facts,
                topic="change_sentinel",
                label="System change sentinel (Hermes view)",
                value=(
                    f"action_required={action_required}. "
                    + "; ".join(parts)
                ),
                source_ref=src,
                provenance=provenance,
                freshness=fresh,
            )

    return facts


def _agent_presence_facts(path: Path, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Basic fleet online state relevant to Hermes routing context."""
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
            label="Online agents (routing context)",
            value=(
                f"{len(online)} of {len(agents)} agents online: {names or 'none listed online'}. "
                "Route requests must target a canonical agent with a proven bridge."
            ),
            source_ref=_display_ref(path),
            provenance="generated_read_model",
            freshness=_freshness(path, payload),
        )
    return facts


# ---------------------------------------------------------------------------
# Aggregate read-model loader
# ---------------------------------------------------------------------------

def _hermes_read_model_facts(
    root: Path,
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    """Load all Hermes read-models and extract dank facts."""
    facts: list[dict[str, Any]] = []
    refs: list[str] = []
    proof: dict[str, Any] = {"read_model_presence": {}}

    payloads: dict[str, dict[str, Any]] = {}
    for name in HERMES_READ_MODELS:
        path = root / name
        payload = _read_json(path)
        proof["read_model_presence"][name] = bool(payload)
        if not payload:
            continue
        payloads[name] = payload
        refs.append(_display_ref(path))

    if "hermes_mission_sentinel.json" in payloads:
        facts.extend(
            _mission_sentinel_facts(
                root / "hermes_mission_sentinel.json",
                payloads["hermes_mission_sentinel.json"],
            )
        )

    if "hermes_gravity_controller.json" in payloads:
        facts.extend(
            _gravity_controller_facts(
                root / "hermes_gravity_controller.json",
                payloads["hermes_gravity_controller.json"],
            )
        )

    if "hermes_chief_build_handoff.json" in payloads:
        facts.extend(
            _build_handoff_facts(
                root / "hermes_chief_build_handoff.json",
                payloads["hermes_chief_build_handoff.json"],
            )
        )

    if "openclaw_change_sentinel.json" in payloads:
        facts.extend(
            _change_sentinel_facts(
                root / "openclaw_change_sentinel.json",
                payloads["openclaw_change_sentinel.json"],
            )
        )

    if "agent_presence.json" in payloads:
        facts.extend(
            _agent_presence_facts(
                root / "agent_presence.json",
                payloads["agent_presence.json"],
            )
        )

    return facts, refs, proof


# ---------------------------------------------------------------------------
# Public build function
# ---------------------------------------------------------------------------

def build_hermes_context_packet(
    *,
    question: str = "",
    read_model_root: str | Path | None = None,
) -> dict[str, Any]:
    """Build a grounded, source-tagged context packet for Hermes's lane.

    READ-ONLY: no sends, no money, no writes, no agent dispatch.
    Authority flags are hard-coded and never overridden at runtime.
    """
    root = Path(read_model_root) if read_model_root is not None else DEFAULT_READ_MODEL_ROOT
    generated_at = _utc_now()

    # 1. Lane-invariant facts (from code/modules — no file I/O needed)
    route_facts = _route_target_facts()
    gateway_facts = _gateway_policy_facts()
    advisory_facts = _advisory_contract_facts()

    # 2. Read-model facts (from generated/read_models/)
    rm_facts, rm_refs, proof = _hermes_read_model_facts(root)

    # Assemble in priority order:
    # lane bounds first, then gateway posture, then advisory contract, then read-models.
    facts = [*route_facts, *gateway_facts, *advisory_facts, *rm_facts]

    facts = annotate_facts_with_ledger_provenance(
        facts,
        builder_name="hermes_context_packet.build_hermes_context_packet",
    )

    source_refs = tuple(
        dict.fromkeys(
            [
                *(f["source_ref"] for f in facts),
                *(str(f.get("ledger_source_ref") or "") for f in facts if f.get("ledger_source_ref")),
                *rm_refs,
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
    packet_id = f"hermes_context_packet:{_short_hash(basis)}"

    # Authority flags — hard-coded; send_hold_absolute is always True.
    bounds = dict(_HERMES_AUTHORITY_FLAGS)

    return {
        "schema_version": SCHEMA_VERSION,
        "packet_id": packet_id,
        "status": "READY",
        "generated_at": generated_at,
        "question": _compact(question, limit=300),
        "facts": facts,
        "source_refs": list(source_refs),
        "bounds": bounds,
        "machine_proof": {
            "packet_compiler": "hermes_context_packet.build_hermes_context_packet",
            "read_model_root": str(root),
            "fact_count": len(facts),
            "read_model_count": len(rm_refs),
            "authority_flags_verified": dict(bounds),
            **ledger_machine_proof(
                builder_name="hermes_context_packet.build_hermes_context_packet",
                facts=facts,
            ),
            **proof,
        },
        "packet_text": format_hermes_context_packet(
            {
                "facts": facts,
                "bounds": bounds,
                "packet_id": packet_id,
                "generated_at": generated_at,
            }
        ),
    }


def format_hermes_context_packet(packet: Mapping[str, Any]) -> str:
    facts = [f for f in packet.get("facts", ()) if isinstance(f, Mapping)]
    bounds = packet.get("bounds", {}) if isinstance(packet.get("bounds"), Mapping) else {}
    lines = [
        f"HERMES_CONTEXT_PACKET {packet.get('packet_id', '')}",
        f"Generated: {packet.get('generated_at', '')}",
        "",
        "Grounded facts:",
    ]
    for fact in facts[:25]:
        src = str(fact.get("source_ref") or "")
        prov = str(fact.get("provenance") or "")
        tier = str(fact.get("pii_tier") or "PUBLIC")
        lines.append(
            f"- {fact.get('label')}: {fact.get('value')} "
            f"[tier={tier}; provenance={prov}; source={src}]"
        )
    lines.extend(
        [
            "",
            "Boundaries (Hermes hard limits):",
            f"- SEND_HOLD absolute: {bool(bounds.get('send_hold_absolute', True))}",
            f"- Outbound send allowed: {bool(bounds.get('outbound_send_allowed', False))}",
            f"- Money movement allowed: {bool(bounds.get('money_movement_allowed', False))}",
            f"- Agent dispatch allowed: {bool(bounds.get('agent_dispatch_allowed', False))}",
            f"- Ledger mutation allowed: {bool(bounds.get('ledger_mutation_allowed', False))}",
            f"- Canonical write allowed: {bool(bounds.get('canonical_write_allowed', False))}",
        ]
    )
    return "\n".join(lines).strip()


__all__ = [
    "SCHEMA_VERSION",
    "HERMES_READ_MODELS",
    "build_hermes_context_packet",
    "format_hermes_context_packet",
]
