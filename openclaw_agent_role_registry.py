"""Canonical OpenClaw agent role cards for LM2 worker packages.

This module normalizes compact role context for worker packages. It does not
invoke models, start services, inspect credentials, create approvals, mutate
runtime policy, or grant authority. Full role documents remain references; LM2
packages receive a compact role card by default.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parent

SCHEMA_VERSION = "AGENT_ROLE_CARD_V0"
REGISTRY_SCHEMA_VERSION = "OPENCLAW_AGENT_ROLE_REGISTRY_V0"
READ_MODEL_ID = "openclaw_agent_role_registry"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
STATUS_READY = "OPENCLAW_AGENT_ROLE_REGISTRY_READY"

DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_SYSTEM_KNOWLEDGE_ROOT = Path("generated/system_knowledge/agent_roles")
SYSTEM_KNOWLEDGE_JSON_NAME = "openclaw_agent_role_registry_v0.json"

ROLE_CONTEXT_STRATEGIES = (
    "compact_role_card",
    "full_context_ref",
    "adapter_native_agent_command",
    "none",
)

REQUIRED_AGENT_IDS = (
    "cassandra",
    "chief",
    "guardian",
    "niles",
    "hermes",
    "watch_desk",
)

AUTHORITY_BOUNDARY = {
    "model_output_grants_runtime_authority": False,
    "model_output_grants_business_authority": False,
    "tool_authority_granted": False,
    "external_action_allowed": False,
    "runtime_mutation_allowed": False,
    "guardian_approval_created": False,
    "direct_send_allowed": False,
    "ledger_mutation_allowed": False,
    "paid_marking_allowed": False,
    "daw_media_mutation_allowed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _rooted(path: Path | str) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _short_hash(*parts: object, length: int = 16) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:length]


def _card(
    *,
    agent_id: str,
    display_name: str,
    role_summary: str,
    owns: Sequence[str],
    may_request: Sequence[str],
    must_route_through: Sequence[str],
    must_not: Sequence[str],
    runtime_mode: str,
    service_names: Sequence[str],
    canonical_files: Sequence[str],
    safety_boundaries: Sequence[str],
    package_context_summary: str,
    full_context_refs: Sequence[str],
    updated_at_utc: str,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "agent_role_ref": f"agent_role_card:{agent_id}",
        "agent_id": agent_id,
        "display_name": display_name,
        "role_summary": role_summary,
        "owns": list(owns),
        "may_request": list(may_request),
        "must_route_through": list(must_route_through),
        "must_not": list(must_not),
        "runtime_mode": runtime_mode,
        "service_names": list(service_names),
        "canonical_files": list(canonical_files),
        "safety_boundaries": list(safety_boundaries),
        "package_context_summary": package_context_summary,
        "full_context_refs": list(full_context_refs),
        "updated_at_utc": updated_at_utc,
        "native_agent_command_policy": {
            "slash_agent_command_required": False,
            "slash_agent_command_allowed_only_if_proven": True,
            "canonical_package_remains_provider_agnostic": True,
        },
        "subagent_policy": {
            "native_subagent_use": "metadata_only_if_reported_inside_worker_sandbox",
            "parent_package_boundary_remains_binding": True,
            "extra_authority_granted": False,
            "worker_run_manager_tracks_parent_only_v0": True,
            "final_output_must_be_canonical_result_envelope": True,
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def default_role_cards(*, updated_at_utc: str | None = None) -> dict[str, dict[str, Any]]:
    updated_at_utc = updated_at_utc or utc_now()
    cards = [
        _card(
            agent_id="cassandra",
            display_name="Cassandra",
            role_summary="Business ops, AR, client follow-up, operator communications, Universal Intake, and Data Room guided review.",
            owns=[
                "business ops and AR summaries",
                "client follow-up drafts and exact-send requests",
                "Universal Operator Intake",
                "Data Room guided review and review coach sessions",
                "local business receipts/read models",
            ],
            may_request=[
                "Chief implementation or runtime triage packages",
                "Guardian exact-send or high-risk approval review",
                "Niles creative-lane handoff",
                "Hermes adapter/boundary review",
            ],
            must_route_through=[
                "Guardian/HITL for sends, approvals, paid marking, and protected actions",
                "Chief for code/runtime implementation work",
                "confirmed reference/hydration rails for Data Room promotion",
            ],
            must_not=[
                "send email or create Gmail drafts without explicit current authority",
                "mutate invoices, ledgers, Coupa, bank records, workbooks, PDFs, or paid status",
                "promote provisional review answers into runtime policy",
                "read secrets or credential material",
            ],
            runtime_mode="systemd_service",
            service_names=["cassandra-listener.service"],
            canonical_files=[
                "cassandra_listener.py",
                "cassandra_brain.py",
                "operator_universal_intake.py",
                "cassandra_guided_review.py",
                "cassandra_review_coach.py",
                "hitl_action_service.py",
                "watch_desk_feed.py",
            ],
            safety_boundaries=[
                "authoritative=false for guided review until promotion",
                "runtime_policy_changed=false unless a separate explicit gate does it",
                "exact-send and protected action authority stay behind Guardian",
            ],
            package_context_summary=(
                "Act for Cassandra as an advisory business-ops worker. Produce bounded text, drafts, "
                "or review output only; do not execute sends, paid marking, ledger work, or external actions."
            ),
            full_context_refs=[".claude/commands/cassandra.md", "agent_lane_registry.py#cassandra"],
            updated_at_utc=updated_at_utc,
        ),
        _card(
            agent_id="chief",
            display_name="Chief",
            role_summary="System orchestration, runtime triage, model/package routing, validation posture, and bounded work packet preparation.",
            owns=[
                "runtime coordination",
                "model work package routing",
                "assignment loop packaging",
                "worker run lifecycle verification",
                "service and sync health summaries",
            ],
            may_request=[
                "Cassandra business-context review",
                "Guardian safety or approval review",
                "Hermes adapter/boundary review",
                "Niles creative metadata review",
            ],
            must_route_through=[
                "Guardian/HITL for approvals and risky actions",
                "existing Worker Run Manager for worker dispatch/ingest",
                "Watch Desk for operator-facing projection",
            ],
            must_not=[
                "bypass Guardian",
                "execute another agent lane directly",
                "inspect secrets or credential material",
                "mutate runtime policy or external systems without explicit current scope",
            ],
            runtime_mode="systemd_service",
            service_names=[
                "chief-listener.service",
                "chief-worker.service",
                "chief-memory-worker.service",
                "chief-state-worker.service",
                "chief-watcher-brain.service",
            ],
            canonical_files=[
                "chief_listener.py",
                "chief_worker.py",
                "model_work_package_router.py",
                "assignment_loop_contract.py",
                "codex_work_package_lifecycle.py",
                "watch_desk_feed.py",
            ],
            safety_boundaries=[
                "coordinate and validate, do not self-grant execution",
                "worker packages are bounded and receipt-backed",
                "model output never mutates runtime directly",
            ],
            package_context_summary=(
                "Act for Chief as a bounded implementation or runtime-review worker. Follow the package "
                "sources, proof, stop condition, and validation plan; do not push, approve, or mutate runtime."
            ),
            full_context_refs=[".claude/commands/chief.md", "agent_lane_registry.py#chief"],
            updated_at_utc=updated_at_utc,
        ),
        _card(
            agent_id="guardian",
            display_name="Guardian",
            role_summary="Human-in-the-loop authorization boundary, risk review, exact-action approval capture, and denial/approval state.",
            owns=[
                "HITL approval boundary",
                "risk and protected-action review",
                "exact-send approval capture",
                "approval/denial receipts",
            ],
            may_request=[
                "Chief implementation follow-up for safety defects",
                "Cassandra readback when a business send needs exact text",
            ],
            must_route_through=[
                "hitl_action_service.py and hitl_pending_store.py for approval state",
                "operator confirmation for high-risk actions",
            ],
            must_not=[
                "execute business logic after approval",
                "send email",
                "create a second approval system",
                "disclose secrets or credential material",
            ],
            runtime_mode="human_approval",
            service_names=["chief-guardian-listener.service"],
            canonical_files=[
                "chief_guardian_listener.py",
                "chief_guardian_sender.py",
                "hitl_action_service.py",
                "hitl_pending_store.py",
            ],
            safety_boundaries=[
                "approval capture is separate from action execution",
                "exact action text and scope are required where runtime demands it",
                "duplicates and expired approvals must not execute twice",
            ],
            package_context_summary=(
                "Act for Guardian as a safety review worker. Return risk findings, approval cautions, "
                "or rejection reasons only; do not execute the approved action."
            ),
            full_context_refs=[".claude/commands/guardian.md", "agent_lane_registry.py#guardian"],
            updated_at_utc=updated_at_utc,
        ),
        _card(
            agent_id="niles",
            display_name="Niles",
            role_summary="Music, audio, creative, session, and production planning lane.",
            owns=[
                "music and creative planning",
                "album/session/setlist notes",
                "creative metadata review packets",
                "live-set prep as metadata",
            ],
            may_request=[
                "Chief runtime/package support",
                "Cassandra business-context handoff when creative work touches clients or payments",
                "Guardian review for publishing, file mutation, or public release risk",
            ],
            must_route_through=[
                "operator approval for DAW/media/session writes",
                "Cassandra or Guardian for business/public-facing action",
            ],
            must_not=[
                "start DAW, Logic, Ableton, OBS, or audio engines",
                "mutate session, media, stems, bounces, artwork, or release files",
                "scan private media/session folders broadly",
                "read secrets or credential material",
            ],
            runtime_mode="logical_only_spawned_worker",
            service_names=[],
            canonical_files=[
                "agent_lane_registry.py",
                "operator_universal_intake.py",
                "chief_fundo_identity.py",
                "chief_fundo_session.py",
                "chief_fundo_release.py",
            ],
            safety_boundaries=[
                "metadata and planning first",
                "no DAW/media mutation by default",
                "creative notes are not business authorization",
            ],
            package_context_summary=(
                "Act for Niles as a creative planning worker. Produce notes, options, or metadata review "
                "only; do not touch DAW, media, release, or private session files."
            ),
            full_context_refs=[".claude/commands/niles.md", "agent_lane_registry.py#niles"],
            updated_at_utc=updated_at_utc,
        ),
        _card(
            agent_id="hermes",
            display_name="Hermes",
            role_summary="Adapter/protocol boundary review, connector posture, sidecar contracts, and advisory synthesis.",
            owns=[
                "adapter and protocol boundary review",
                "connector/tool wrapper readiness posture",
                "sidecar contract inventory",
                "non-canonical advisory synthesis",
            ],
            may_request=[
                "Chief implementation/package work",
                "Guardian review for sensitive connector boundaries",
            ],
            must_route_through=[
                "Chief for runtime changes",
                "Guardian for sensitive capability enablement",
                "existing adapter contracts for tool execution proposals",
            ],
            must_not=[
                "launch generic sidecars or gateways without explicit bounded authorization",
                "read connector secrets or credential material",
                "own or execute business logic",
                "approve actions",
            ],
            runtime_mode="sidecar_adapter_unsafe_to_start_by_default",
            service_names=["hermes-gateway.service"],
            canonical_files=[
                "openclaw_hermes_sidecar.py",
                "tool_protocol_adapter_registry_contract.py",
                "tool_adapter_receipt_contract.py",
                "openclaw_event_bridge_adapter.py",
            ],
            safety_boundaries=[
                "adapter readiness does not grant execution authority",
                "sidecar launch is explicitly gated",
                "business logic remains in owning lanes",
            ],
            package_context_summary=(
                "Act for Hermes as an adapter/boundary reviewer. Return advisory analysis or contract "
                "findings only; do not launch sidecars, tools, connectors, or business actions."
            ),
            full_context_refs=[".claude/commands/hermes.md", "agent_lane_registry.py#hermes"],
            updated_at_utc=updated_at_utc,
        ),
        _card(
            agent_id="watch_desk",
            display_name="Watch Desk",
            role_summary="Read-only operator attention projection sourced from receipts and read models.",
            owns=[
                "operator attention feed projection",
                "watch items from existing receipts/read models",
                "next-safe-action summaries",
            ],
            may_request=[
                "Chief review when projection source state is inconsistent",
                "Cassandra summary when a business item needs human-facing wording",
            ],
            must_route_through=[
                "source read model or receipt for every item",
                "existing approval rails for any action suggested by a watch item",
            ],
            must_not=[
                "mutate source state",
                "create approvals",
                "execute actions",
                "invent source truth without receipts",
            ],
            runtime_mode="read_only_projection",
            service_names=[],
            canonical_files=["watch_desk_feed.py"],
            safety_boundaries=[
                "push_allowed remains false by default",
                "projection is not approval",
                "source receipts/read models remain canonical",
            ],
            package_context_summary=(
                "Act for Watch Desk as a projection/summarization worker. Return attention items or "
                "next-safe-action text only; do not mutate source state or create approvals."
            ),
            full_context_refs=["agent_lane_registry.py#watch_desk", "watch_desk_feed.py"],
            updated_at_utc=updated_at_utc,
        ),
    ]
    return {card["agent_id"]: card for card in cards}


def resolve_agent_role_card(agent_id: str, *, updated_at_utc: str | None = None) -> dict[str, Any]:
    cards = default_role_cards(updated_at_utc=updated_at_utc)
    normalized = str(agent_id or "").strip().lower().replace("-", "_")
    return dict(cards.get(normalized) or cards["chief"])


def compact_role_card(agent_id: str, *, updated_at_utc: str | None = None) -> dict[str, Any]:
    card = resolve_agent_role_card(agent_id, updated_at_utc=updated_at_utc)
    return {
        "schema_version": card["schema_version"],
        "agent_role_ref": card["agent_role_ref"],
        "agent_id": card["agent_id"],
        "display_name": card["display_name"],
        "role_summary": card["role_summary"],
        "owns": card["owns"],
        "may_request": card["may_request"],
        "must_route_through": card["must_route_through"],
        "must_not": card["must_not"],
        "runtime_mode": card["runtime_mode"],
        "safety_boundaries": card["safety_boundaries"],
        "package_context_summary": card["package_context_summary"],
        "full_context_refs": card["full_context_refs"],
        "native_agent_command_policy": card["native_agent_command_policy"],
        "subagent_policy": card["subagent_policy"],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def package_role_context(
    *,
    requested_by_agent: str,
    owner_agent: str,
    role_context_strategy: str = "compact_role_card",
    updated_at_utc: str | None = None,
) -> dict[str, Any]:
    strategy = role_context_strategy if role_context_strategy in ROLE_CONTEXT_STRATEGIES else "compact_role_card"
    requested = str(requested_by_agent or "operator").strip().lower().replace("-", "_")
    owner = str(owner_agent or "chief").strip().lower().replace("-", "_")
    card = compact_role_card(owner, updated_at_utc=updated_at_utc)
    return {
        "requested_by_agent": requested,
        "owner_agent": owner,
        "agent_role_ref": card["agent_role_ref"],
        "agent_role_summary": card["package_context_summary"],
        "agent_role_card": card if strategy == "compact_role_card" else {},
        "full_agent_context_refs": list(card["full_context_refs"]),
        "role_context_strategy": strategy,
        "adapter_native_agent_command": "",
        "role_context_inlined_full_docs": False,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def build_registry(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    cards = default_role_cards(updated_at_utc=generated_at)
    missing = sorted(set(REQUIRED_AGENT_IDS) - set(cards))
    payload: dict[str, Any] = {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": STATUS_READY if not missing else "OPENCLAW_AGENT_ROLE_REGISTRY_BLOCKED",
        "generated_at": generated_at,
        "role_card_schema": SCHEMA_VERSION,
        "required_agent_ids": list(REQUIRED_AGENT_IDS),
        "missing_agent_ids": missing,
        "role_context_strategies": list(ROLE_CONTEXT_STRATEGIES),
        "default_role_context_strategy": "compact_role_card",
        "role_cards": cards,
        "package_contract": {
            "required_package_fields": [
                "requested_by_agent",
                "owner_agent",
                "agent_role_ref",
                "agent_role_summary",
                "full_agent_context_refs",
                "role_context_strategy",
            ],
            "full_role_docs_inlined_by_default": False,
            "native_slash_agents_required": False,
            "subagents_grant_extra_authority": False,
        },
        "audited_sources": [
            "agent_lane_registry.py",
            ".claude/commands/cassandra.md",
            ".claude/commands/chief.md",
            ".claude/commands/niles.md",
            ".claude/commands/hermes.md",
            ".claude/commands/guardian.md",
            "watch_desk_feed.py",
        ],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "role_card_count": len(cards),
            "all_required_agents_present": not missing,
            "full_context_refs_not_inlined_by_default": True,
            "native_slash_agent_mode_optional": True,
            "subagents_metadata_only": True,
            "model_calls_performed": False,
            "external_api_calls_performed": False,
            "runtime_mutation_performed": False,
            "approval_created": False,
        },
    }
    payload["machine_proof"]["content_hash"] = "sha256:" + hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()
    return payload


def render_operator_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# OpenClaw Agent Role Registry",
        "",
        f"Status: {payload.get('status')}",
        "",
        "LM2 packages receive a compact role card plus context references by default. Full role docs are not inlined.",
        "",
        "## Agents",
    ]
    cards = payload.get("role_cards") if isinstance(payload.get("role_cards"), Mapping) else {}
    for agent_id in REQUIRED_AGENT_IDS:
        card = cards.get(agent_id, {}) if isinstance(cards, Mapping) else {}
        lines.extend(
            [
                f"- {card.get('display_name', agent_id)} (`{agent_id}`)",
                f"  - role: {card.get('role_summary', '')}",
                f"  - runtime: {card.get('runtime_mode', '')}",
                f"  - package context: {card.get('package_context_summary', '')}",
            ]
        )
    lines.extend(
        [
            "",
            "## Package Rule",
            "- Default strategy: compact_role_card.",
            "- Full context remains referenced, not copied into every package.",
            "- Native slash-agent commands are optional and must be proven before an adapter uses them.",
            "- Native subagents, if a worker uses them, stay inside the parent package boundary and grant no extra authority.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_agent_role_registry(
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    system_knowledge_root: Path = DEFAULT_SYSTEM_KNOWLEDGE_ROOT,
    generated_at: str | None = None,
) -> dict[str, str]:
    payload = build_registry(generated_at=generated_at)
    export_root = _rooted(export_root)
    system_knowledge_root = _rooted(system_knowledge_root)
    read_model_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    system_knowledge_path = system_knowledge_root / SYSTEM_KNOWLEDGE_JSON_NAME
    _write_json(read_model_path, payload)
    _write_text(operator_path, render_operator_markdown(payload))
    _write_json(system_knowledge_path, payload)
    bridge_path = ""
    if bridge_root is not None:
        bridge = Path(bridge_root)
        bridge.mkdir(parents=True, exist_ok=True)
        bridge_target = bridge / JSON_EXPORT_NAME
        shutil.copy2(read_model_path, bridge_target)
        bridge_path = bridge_target.as_posix()
    return {
        "status": str(payload["status"]),
        "read_model_path": read_model_path.as_posix(),
        "operator_path": operator_path.as_posix(),
        "system_knowledge_path": system_knowledge_path.as_posix(),
        "bridge_path": bridge_path,
    }


def main() -> int:
    result = export_agent_role_registry()
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
