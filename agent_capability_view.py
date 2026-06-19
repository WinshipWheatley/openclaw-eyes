"""Agent Capability View v0 for OpenClaw.

This read model projects existing agent/lane registries into a richer
per-agent capability surface. Lane registry data is the authority boundary;
legacy capability registry rows are included as context-only claims and never
grant runtime dispatch, tool execution, model execution, external send, or
approval bypass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_lane_registry import DEFAULT_AGENT_LANE_SEEDS, AgentLaneSeed
from capability_registry import REGISTRY as LEGACY_CAPABILITY_REGISTRY


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "agent_capability_view_v0"
READ_MODEL_ID = "agent_capability_view"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"

SOURCE_REFS = (
    "agent_lane_registry.py::DEFAULT_AGENT_LANE_SEEDS",
    "capability_registry.py::REGISTRY",
    "generated/read_models/agent_lanes.json",
    "generated/read_models/agent_capability_migration_map.json",
)

AUTHORITY_BOUNDARY = {
    "agent_activation_allowed": False,
    "direct_execution_allowed": False,
    "runtime_dispatch_allowed": False,
    "approval_bypass_allowed": False,
    "external_send_allowed": False,
    "tool_execution_allowed": False,
    "model_execution_allowed": False,
    "network_operation_allowed": False,
    "credential_or_secret_access_allowed": False,
    "no_go_raw_access_allowed": False,
    "client_deployment_allowed": False,
    "truth_promotion_allowed": False,
    "stable_map_update_allowed": False,
}


@dataclass(frozen=True)
class AgentCapabilityViewExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    agent_count: int
    lane_capability_count: int
    legacy_claim_count: int
    action_authority_granted: bool


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _display_path(path: str | Path) -> str:
    path_obj = Path(path)
    try:
        return path_obj.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return path_obj.as_posix()


def _export_root_path(export_root: str | Path) -> Path:
    path = Path(export_root)
    if path.is_absolute():
        return path
    return ROOT / path


def _legacy_capability_claims(agent_id: str) -> list[dict[str, Any]]:
    actor = LEGACY_CAPABILITY_REGISTRY.get(agent_id)
    if actor is None:
        return []
    claims: list[dict[str, Any]] = []
    for capability in actor.capabilities:
        claim_status = (
            "LEGACY_CONNECTED_CLAIM_NEEDS_RECEIPT"
            if capability.connected
            else "LEGACY_NOT_CONNECTED"
        )
        claims.append(
            {
                "capability_name": capability.name,
                "domain": capability.domain,
                "description": capability.description,
                "legacy_connected": bool(capability.connected),
                "legacy_scope": list(capability.scope),
                "caveats": capability.caveats,
                "claim_status": claim_status,
                "claim_basis": "legacy_capability_registry_context_only",
                "action_authority_granted": False,
                "runtime_authority_granted": False,
                "runtime_dispatch_allowed": False,
            }
        )
    return sorted(claims, key=lambda item: (item["domain"], item["capability_name"]))


def _lane_capability(
    *,
    agent_id: str,
    capability_kind: str,
    capability_name: str,
    status: str,
    source_ref: str,
    posture: str,
) -> dict[str, Any]:
    return {
        "capability_id": f"{agent_id}:{capability_kind}:{capability_name}",
        "capability_kind": capability_kind,
        "capability_name": capability_name,
        "status": status,
        "source_ref": source_ref,
        "posture": posture,
        "action_authority_granted": False,
        "runtime_dispatch_allowed": False,
        "activation_allowed": False,
    }


def _lane_capabilities(seed: AgentLaneSeed) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for input_kind in seed.allowed_input_kinds:
        records.append(
            _lane_capability(
                agent_id=seed.agent_id,
                capability_kind="allowed_input",
                capability_name=input_kind,
                status="LANE_ALLOWED_CONTEXT_INPUT",
                source_ref="agent_lane_registry.allowed_input_kinds",
                posture="metadata_or_evidence_only",
            )
        )
    for input_kind in seed.blocked_input_kinds:
        records.append(
            _lane_capability(
                agent_id=seed.agent_id,
                capability_kind="blocked_input",
                capability_name=input_kind,
                status="BLOCKED_BY_LANE_BOUNDARY",
                source_ref="agent_lane_registry.blocked_input_kinds",
                posture="blocked",
            )
        )
    for output_kind in seed.allowed_output_kinds:
        records.append(
            _lane_capability(
                agent_id=seed.agent_id,
                capability_kind="allowed_output",
                capability_name=output_kind,
                status="LANE_ALLOWED_NON_EXECUTING_OUTPUT",
                source_ref="agent_lane_registry.allowed_output_kinds",
                posture="proposal_or_read_model_surface",
            )
        )
    for output_kind in seed.blocked_output_kinds:
        records.append(
            _lane_capability(
                agent_id=seed.agent_id,
                capability_kind="blocked_output",
                capability_name=output_kind,
                status="BLOCKED_BY_LANE_BOUNDARY",
                source_ref="agent_lane_registry.blocked_output_kinds",
                posture="blocked",
            )
        )
    for source_kind, source_posture in seed.source_kind_postures:
        records.append(
            _lane_capability(
                agent_id=seed.agent_id,
                capability_kind="source_posture",
                capability_name=source_kind,
                status="SOURCE_METADATA_ONLY_OR_REQUEST_ONLY",
                source_ref="agent_lane_registry.source_kind_postures",
                posture=source_posture,
            )
        )
    for approval in seed.approval_required_for:
        records.append(
            _lane_capability(
                agent_id=seed.agent_id,
                capability_kind="approval_required",
                capability_name=approval,
                status="APPROVAL_REQUIRED_BEFORE_ACTION",
                source_ref="agent_lane_registry.approval_required_for",
                posture="approval_gate_required",
            )
        )
    for receipt in seed.receipt_required_for:
        records.append(
            _lane_capability(
                agent_id=seed.agent_id,
                capability_kind="receipt_required",
                capability_name=receipt,
                status="RECEIPT_REQUIRED_FOR_OUTPUT",
                source_ref="agent_lane_registry.receipt_required_for",
                posture="receipt_required",
            )
        )
    return sorted(records, key=lambda item: (item["capability_kind"], item["capability_name"]))


def _agent_record(seed: AgentLaneSeed) -> dict[str, Any]:
    lane_caps = _lane_capabilities(seed)
    legacy_claims = _legacy_capability_claims(seed.agent_id)
    return {
        "agent_id": seed.agent_id,
        "display_name": seed.display_name,
        "lane_id": seed.lane_id,
        "lane_label": seed.lane_label,
        "status": seed.status,
        "authority_level": seed.authority_level,
        "role_summary": seed.role_summary,
        "allowed_worlds": list(seed.allowed_worlds),
        "aliases": list(seed.aliases),
        "routing_hints": list(seed.routing_hints),
        "lane_capabilities": lane_caps,
        "legacy_capability_claims": legacy_claims,
        "capability_summary": {
            "lane_capability_count": len(lane_caps),
            "allowed_input_count": len(seed.allowed_input_kinds),
            "blocked_input_count": len(seed.blocked_input_kinds),
            "allowed_output_count": len(seed.allowed_output_kinds),
            "blocked_output_count": len(seed.blocked_output_kinds),
            "approval_required_count": len(seed.approval_required_for),
            "receipt_required_count": len(seed.receipt_required_for),
            "legacy_claim_count": len(legacy_claims),
            "legacy_connected_claim_count": sum(1 for claim in legacy_claims if claim["legacy_connected"]),
        },
        "source_kind_postures": [
            {
                "source_kind": source_kind,
                "source_posture": source_posture,
                "can_auto_execute": False,
                "api_wired_by_view": False,
            }
            for source_kind, source_posture in seed.source_kind_postures
        ],
        "integration_posture": {
            "view_role": "routing_context_and_capability_readback",
            "legacy_claims_do_not_override_lane_authority": True,
            "runtime_dispatch_allowed": False,
            "action_authority_granted": False,
            "approval_bypass_allowed": False,
        },
        "activation_status": "NOT_ACTIVATED_BY_VIEW",
        "action_authority_granted": False,
        "runtime_dispatch_allowed": False,
    }


def _append_index(index: dict[str, list[str]], key: str, agent_id: str) -> None:
    index.setdefault(key, [])
    if agent_id not in index[key]:
        index[key].append(agent_id)


def _sorted_index(index: dict[str, list[str]]) -> dict[str, list[str]]:
    return {key: sorted(value) for key, value in sorted(index.items())}


def build_agent_capability_view(
    *,
    generated_at: str | None = None,
    seeds: tuple[AgentLaneSeed, ...] = DEFAULT_AGENT_LANE_SEEDS,
) -> dict[str, Any]:
    agents = [_agent_record(seed) for seed in sorted(seeds, key=lambda item: item.agent_id)]
    seed_agent_ids = {seed.agent_id for seed in seeds}
    legacy_actor_ids = set(LEGACY_CAPABILITY_REGISTRY)
    agents_by_world: dict[str, list[str]] = {}
    agents_by_source_kind: dict[str, list[str]] = {}
    agents_by_allowed_output_kind: dict[str, list[str]] = {}
    agents_by_capability_domain: dict[str, list[str]] = {}
    for agent in agents:
        agent_id = agent["agent_id"]
        for world in agent["allowed_worlds"]:
            _append_index(agents_by_world, world, agent_id)
        for source in agent["source_kind_postures"]:
            _append_index(agents_by_source_kind, source["source_kind"], agent_id)
        for capability in agent["lane_capabilities"]:
            if capability["capability_kind"] == "allowed_output":
                _append_index(agents_by_allowed_output_kind, capability["capability_name"], agent_id)
        for claim in agent["legacy_capability_claims"]:
            _append_index(agents_by_capability_domain, claim["domain"], agent_id)

    lane_capability_count = sum(len(agent["lane_capabilities"]) for agent in agents)
    legacy_claim_count = sum(len(agent["legacy_capability_claims"]) for agent in agents)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at or utc_now(),
        "mode": "rich_agent_capability_readback_context_only",
        "source_refs": list(SOURCE_REFS),
        "agent_count": len(agents),
        "lane_capability_count": lane_capability_count,
        "legacy_capability_claim_count": legacy_claim_count,
        "agents": agents,
        "agents_by_world": _sorted_index(agents_by_world),
        "agents_by_source_kind": _sorted_index(agents_by_source_kind),
        "agents_by_allowed_output_kind": _sorted_index(agents_by_allowed_output_kind),
        "agents_by_capability_domain": _sorted_index(agents_by_capability_domain),
        "registry_agent_ids_without_legacy_capability_claims": sorted(seed_agent_ids - legacy_actor_ids),
        "legacy_actor_ids_not_in_lane_registry": sorted(legacy_actor_ids - seed_agent_ids),
        "legacy_claim_policy": {
            "legacy_capability_registry_is_authority": False,
            "connected_legacy_claim_means": "contextual historical claim requiring receipt/lane verification",
            "lane_registry_controls_authority_boundary": True,
        },
        "operator_query_examples": [
            "what can Cassandra do with email?",
            "which agents can produce codex work packets?",
            "which agents belong to music_art?",
            "which source channels are metadata-only?",
        ],
        "authority_boundary": {
            **AUTHORITY_BOUNDARY,
            "all_action_authority_flags_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        },
        "machine_proof": {
            "capability_view_exists": True,
            "agent_lane_registry_source_present": True,
            "legacy_capability_registry_source_present": True,
            "seed_agent_count": len(seeds),
            "legacy_actor_count": len(legacy_actor_ids),
            "rich_agent_count": len(agents),
            "watch_desk_present": any(agent["agent_id"] == "watch_desk" for agent in agents),
            "legacy_connected_claims_are_context_only": True,
            "all_agents_no_action_authority": all(agent["action_authority_granted"] is False for agent in agents),
            "all_agents_no_runtime_dispatch": all(agent["runtime_dispatch_allowed"] is False for agent in agents),
            "runtime_dispatch_allowed": False,
            "external_send_allowed": False,
            "tool_model_network_authority_granted": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_agent_capability_view(payload: dict[str, Any]) -> str:
    lines = [
        "# Agent Capability View v0",
        "",
        "Evidence:",
        f"- Agents: `{payload['agent_count']}`.",
        f"- Lane capability records: `{payload['lane_capability_count']}`.",
        f"- Legacy capability claims included as context only: `{payload['legacy_capability_claim_count']}`.",
        "- Lane registry controls authority; legacy connected claims do not activate integrations.",
        "",
        "Agents:",
    ]
    for agent in payload["agents"]:
        summary = agent["capability_summary"]
        lines.append(
            f"- `{agent['agent_id']}` / `{agent['lane_id']}`: outputs `{summary['allowed_output_count']}`, "
            f"approvals `{summary['approval_required_count']}`, legacy claims `{summary['legacy_claim_count']}`."
        )
    lines.extend(
        [
            "",
            "Boundary:",
            "- Context/readback only. No agent activation, direct execution, runtime dispatch, approval bypass, external send, network, tool, model, credential, no-go raw access, client deployment, stable-map update, or truth promotion authority.",
            "- Legacy `capability_registry.py` connected flags are historical/contextual claims that require receipt and lane verification.",
            "",
            "Blocked:",
            "- Treating this view as an execution router or integration proof remains blocked.",
            "- Any write/send/tool/model/runtime action still requires the normal approval and receipt path.",
            "",
            "Next safe move:",
            "- Let Mission Control and operator-intent surfaces use this as a capability readback context, then route work packets through existing approval gates.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_agent_capability_view(
    *,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> AgentCapabilityViewExportResult:
    root = _export_root_path(export_root)
    root.mkdir(parents=True, exist_ok=True)
    payload = build_agent_capability_view(generated_at=generated_at)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_agent_capability_view(payload), encoding="utf-8")
    return AgentCapabilityViewExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        agent_count=payload["agent_count"],
        lane_capability_count=payload["lane_capability_count"],
        legacy_claim_count=payload["legacy_capability_claim_count"],
        action_authority_granted=payload["authority_boundary"]["agent_activation_allowed"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Agent Capability View read-model.")
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--generated-at", default=None)
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_agent_capability_view(
        export_root=args.export_root,
        generated_at=args.generated_at,
    )
    summary = asdict(result)
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        print(f"Agent Capability View: `{READ_MODEL_ID}`")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
        print(f"- Agents: `{result.agent_count}`")
    return 0


__all__ = [
    "JSON_EXPORT_NAME",
    "OPERATOR_EXPORT_NAME",
    "READ_MODEL_ID",
    "SCHEMA_VERSION",
    "build_agent_capability_view",
    "export_agent_capability_view",
    "format_agent_capability_view",
    "stable_json",
]
