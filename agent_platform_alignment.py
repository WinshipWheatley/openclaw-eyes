"""Agent Platform Alignment v0 for OpenClaw.

This read-model translates current agent-platform primitives into OpenClaw's
local-first deterministic contracts. It is metadata only: no models, agents,
tools, network calls, browser/OAuth surfaces, credentials, queues, runtime
daemons, send/submit flows, or PC C-drive writes are activated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "agent_platform_alignment_v0"
JSON_EXPORT_NAME = "agent_platform_alignment.json"
OPERATOR_EXPORT_NAME = "agent_platform_alignment_OPERATOR.md"

NO_AUTHORITY_FLAGS = {
    "runtime_authority": False,
    "activation_allowed": False,
    "backend_execution_authorized": False,
    "external_tool_authority": False,
    "credential_authority": False,
    "agent_self_authority": False,
    "persistent_agent_claimed_live": False,
    "always_on_assistant_claimed_live": False,
    "model_api_called": False,
    "agent_activated": False,
    "tool_protocol_activated": False,
    "browser_oauth_account_access_enabled": False,
    "gmail_calendar_coupa_telegram_enabled": False,
    "send_submit_approval_enabled": False,
    "network_execution_enabled": False,
    "hidden_memory_capture_enabled": False,
    "background_surveillance_enabled": False,
    "broad_file_indexing_enabled": False,
    "pc_c_drive_artifact_write_allowed": False,
    "mission_control_app_authority_added": False,
}

BLOCKED_CAPABILITIES = (
    (
        "autonomous_email_send",
        "Autonomous email send remains blocked until a later security gate grants narrow authority.",
    ),
    (
        "calendar_mutation",
        "Calendar mutation remains blocked; Cassandra calendar work is visibility/detangle only.",
    ),
    (
        "browser_coupa_credential_use",
        "Browser, Coupa, OAuth, account, and credential use are not active platform capabilities.",
    ),
    (
        "oauth_tool_bridge_activation",
        "Tool protocol or OAuth bridge activation requires a future governed adapter lane.",
    ),
    (
        "network_execution",
        "Network execution is not part of this deterministic alignment read-model.",
    ),
    (
        "runtime_daemon_claims",
        "Always-on or daemonized agents are future-gated readiness concepts only.",
    ),
    (
        "agent_self_assigned_authority",
        "Actors and agents may not choose their own clearance, memory, tools, or action rights.",
    ),
    (
        "hidden_memory_capture",
        "Memory capture must be explicit, scoped, visible, and receipt-backed.",
    ),
    (
        "background_surveillance",
        "Background monitoring is blocked unless later represented by explicit gates and receipts.",
    ),
    (
        "broad_file_indexing",
        "Broad filesystem indexing is blocked; approved source inventories remain bounded.",
    ),
)


@dataclass(frozen=True)
class EvidenceSource:
    source_id: str
    path: str
    role: str


@dataclass(frozen=True)
class ExistingPrimitive:
    primitive_id: str
    platform_primitive: str
    openclaw_surface: str
    status: str
    evidence_refs: tuple[str, ...]
    maps_to: tuple[str, ...]
    current_boundary: str


@dataclass(frozen=True)
class MissingPrimitive:
    primitive_id: str
    missing_surface: str
    readiness_state: str
    why_needed: str
    blocked_until: str


@dataclass(frozen=True)
class RecommendedLane:
    lane_id: str
    title: str
    priority: str
    why_next: str
    output_should_define: tuple[str, ...]
    hard_boundary: str


@dataclass(frozen=True)
class AgentPlatformAlignmentExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    primitive_count: int
    missing_count: int
    runtime_authority_added: bool
    credential_authority_added: bool


EVIDENCE_SOURCES = (
    EvidenceSource(
        "package_compiler_contract",
        "generated/read_models/package_compiler_contract.json",
        "deterministic package schema, boundary validation, and preview-only package posture",
    ),
    EvidenceSource(
        "operator_workbench_actor_host_registry",
        "generated/read_models/operator_workbench_actor_host_registry.json",
        "known workbenches, actor hosts, conservative autonomy levels, and receipt expectations",
    ),
    EvidenceSource(
        "capability_skill_registry_metadata_delta",
        "generated/read_models/capability_skill_registry_metadata_delta.json",
        "metadata-only capability and skill posture",
    ),
    EvidenceSource(
        "protected_access_broker_concept",
        "generated/read_models/protected_access_broker_concept.json",
        "future protected-access broker concept without live access authority",
    ),
    EvidenceSource(
        "guardian_protected_access_gate_spec",
        "generated/read_models/guardian_protected_access_gate_spec.json",
        "Guardian gate posture for protected access and authority boundaries",
    ),
    EvidenceSource(
        "protected_evidence_reference_receipt",
        "generated/read_models/protected_evidence_reference_receipt.json",
        "protected proof can be referenced by receipt without exposing keys or private bodies",
    ),
    EvidenceSource(
        "cassandra_email_calendar_delta_detangle",
        "generated/read_models/cassandra_email_calendar_delta_detangle.json",
        "Cassandra email/calendar visibility and detangle boundary",
    ),
    EvidenceSource(
        "work_board",
        "generated/read_models/work_board.json",
        "Chief work-board and build posture visibility",
    ),
    EvidenceSource(
        "operator_awareness_agent_package_spine",
        "generated/read_models/operator_awareness_agent_package_spine.json",
        "awareness gaps, package preview, confidence posture, and detour shape",
    ),
    EvidenceSource(
        "operator_nested_lane_mission_package_spine",
        "generated/read_models/operator_nested_lane_mission_package_spine.json",
        "nested lane and actor/agent/package doctrine",
    ),
    EvidenceSource(
        "sync_health",
        "generated/read_models/sync_health.json",
        "stable map/raw mirror split and bridge proof posture",
    ),
    EvidenceSource(
        "operator_map_bundle_contract",
        "generated/read_models/operator_map_bundle_contract.json",
        "stable app-facing map bundle and receipt contract",
    ),
)

EXISTING_PRIMITIVES = (
    ExistingPrimitive(
        "package_compiler_contract",
        "deterministic mission/package compiler",
        "package_compiler_contract",
        "tracked_preview_only",
        ("package_compiler_contract",),
        (
            "actor/model candidate metadata",
            "agent character/persona metadata",
            "context included/excluded",
            "authority boundary",
            "proof and receipt requirements",
        ),
        "Packages can be previewed and exported as metadata; live dispatch is future-gated.",
    ),
    ExistingPrimitive(
        "capability_skill_registry",
        "skill/capability registry",
        "capability_skill_registry_metadata_delta",
        "tracked_metadata_only",
        ("capability_skill_registry_metadata_delta",),
        (
            "candidate skills",
            "safe/blocked capability posture",
            "read-model evidence references",
        ),
        "Capabilities are descriptive and do not grant execution or plugin authority.",
    ),
    ExistingPrimitive(
        "protected_access_gates",
        "governed action and protected-context gates",
        "Guardian protected access / protected evidence receipts",
        "tracked_fail_closed",
        (
            "protected_access_broker_concept",
            "guardian_protected_access_gate_spec",
            "protected_evidence_reference_receipt",
        ),
        (
            "protected proof reference",
            "authority boundary",
            "no credential exposure",
            "fail-closed access posture",
        ),
        "Protected proof can be referenced by metadata; keys, credentials, and private bodies are not available.",
    ),
    ExistingPrimitive(
        "cassandra_comms_detangle",
        "communications agent surface",
        "cassandra_email_calendar_delta_detangle",
        "tracked_visibility_only",
        ("cassandra_email_calendar_delta_detangle",),
        (
            "review/draft packet visibility",
            "email/calendar capability separation",
            "blocked live send/mutation boundary",
        ),
        "Cassandra can be described as a future comms character; Gmail/calendar/live send stay blocked.",
    ),
    ExistingPrimitive(
        "chief_work_and_health_posture",
        "coordination, work-board, and check-light posture",
        "Chief work board / system health / sync health",
        "tracked_read_model_only",
        ("work_board", "sync_health"),
        (
            "current mission",
            "work packet posture",
            "health light proof",
            "stable map receipt state",
        ),
        "Chief receives diagnostic/package previews only unless a later gate grants bounded action.",
    ),
    ExistingPrimitive(
        "mission_control_awareness_spine",
        "operator awareness and gap map",
        "operator awareness and nested lane spines",
        "tracked_operator_surface",
        ("operator_awareness_agent_package_spine", "operator_nested_lane_mission_package_spine"),
        (
            "known/partly-known/unknown/undiscovered posture",
            "confidence/detour path",
            "future package preview",
        ),
        "Mission Control displays deterministic read-model truth; it is not backend authority.",
    ),
    ExistingPrimitive(
        "stable_map_and_sync_receipts",
        "app-surface integration contract",
        "stable map bundle / sync health",
        "tracked_app_visible_contract",
        ("sync_health", "operator_map_bundle_contract"),
        (
            "stable app-visible map",
            "raw read-model proof/detail split",
            "Mac receipt readback",
        ),
        "Mac consumes local map snapshots and receipts; raw generated files remain proof/detail.",
    ),
    ExistingPrimitive(
        "domain_agent_future_mapping",
        "domain agent role mapping",
        "Niles/Cassandra/Guardian/Chief/Hermes lane contracts",
        "partly_tracked_future_gated",
        (
            "operator_nested_lane_mission_package_spine",
            "operator_workbench_actor_host_registry",
        ),
        (
            "music/art agent candidate",
            "communications agent candidate",
            "security/boundary agent candidate",
            "coordination/diagnostic agent candidate",
        ),
        "Agent characters are durable roles, but no persistent agent runtime is active.",
    ),
)

MISSING_PRIMITIVES = (
    MissingPrimitive(
        "durable_agent_identity_registry",
        "agent identity registry",
        "NEEDS_CONTRACT",
        "Chief, Cassandra, Guardian, Hermes, Niles, Codex, Gemini/Antigravity, and future actors need explicit identities before routing.",
        "No package-routing or tool authority should depend on informal names.",
    ),
    MissingPrimitive(
        "actor_model_router_contract",
        "actor/model router and model-selection policy",
        "NEEDS_CONTRACT",
        "The platform must know which actor/model candidate is appropriate for a lane, risk class, and workbench.",
        "No live model call or automatic selection before deterministic routing policy exists.",
    ),
    MissingPrimitive(
        "memory_scope_contract",
        "per-agent memory and read-model scope contract",
        "NEEDS_CONTRACT",
        "Persistent assistants require explicit memory boundaries and source-truth precedence.",
        "No hidden memory capture or broad indexing.",
    ),
    MissingPrimitive(
        "tool_protocol_adapter_registry",
        "tool protocol adapter registry",
        "NEEDS_SECURITY_AUDIT",
        "Future MCP/tool/app integrations need per-adapter capabilities, proof, and revocation posture.",
        "No browser/OAuth/tool bridge activation before a governed adapter contract and security audit.",
    ),
    MissingPrimitive(
        "per_agent_clearance_levels",
        "per-agent clearance and authority matrix",
        "NEEDS_CONTRACT",
        "Each character/actor pair needs explicit read/write/action permissions and forbidden zones.",
        "No agent may self-assign authority.",
    ),
    MissingPrimitive(
        "task_queue_lifecycle_receipts",
        "task queue lifecycle and result receipts",
        "POST_SECURITY_FUTURE_GATED",
        "Always-on agents require visible request, accept, run, stop, receipt, and failure states.",
        "No queue/autonomy/planner-builder execution before security gates.",
    ),
    MissingPrimitive(
        "action_result_receipts",
        "action result receipt contract",
        "NEEDS_CONTRACT",
        "Every future action must produce deterministic proof of what happened, what changed, and what did not happen.",
        "No natural-language success claim should establish action success.",
    ),
    MissingPrimitive(
        "revocation_kill_switch_contract",
        "revocation, disable, quarantine, and kill-switch contract",
        "NEEDS_CONTRACT",
        "Persistent agents need a visible way to stop, revoke, quarantine, and audit them.",
        "No always-on worker should exist without disable/quarantine proof.",
    ),
    MissingPrimitive(
        "compromise_suspicion_posture",
        "compromise/suspicion posture",
        "NEEDS_CONTRACT",
        "Agent platforms need a deterministic way to classify suspicious behavior, stale receipts, and unexpected capability requests.",
        "Suspicion must fail closed and surface to Guardian/Chief.",
    ),
)

RECOMMENDED_NEXT_LANES = (
    RecommendedLane(
        "agent_identity_actor_router_contract_v0",
        "Agent Identity + Actor Router Contract v0",
        "P0",
        "OpenClaw should know who/what each agent character and actor/model candidate is before routing packages or granting tools.",
        (
            "durable agent identity records",
            "actor/model candidate records",
            "role fit and risk fit",
            "default memory scope",
            "default clearance",
            "forbidden capabilities",
            "proof/receipt expectations",
        ),
        "Metadata/read-model only; no model calls, live agents, tool activation, credentials, or runtime daemon.",
    ),
    RecommendedLane(
        "memory_scope_and_source_truth_contract_v0",
        "Agent Memory Scope + Source Truth Contract v0",
        "P1",
        "Persistent assistants are unsafe unless memory scope, read-model precedence, and operator memory status are explicit.",
        (
            "read-model scope classes",
            "operator memory vs proof rule",
            "private body exclusion policy",
            "revocation and stale-memory handling",
        ),
        "No broad file scan or hidden memory capture.",
    ),
    RecommendedLane(
        "tool_protocol_adapter_registry_v0",
        "Tool Protocol Adapter Registry v0",
        "P2",
        "Future tools/protocols need deterministic adapter records and blocked-by-default authority before security audit.",
        (
            "adapter id",
            "capability class",
            "credential posture",
            "activation gate",
            "receipt requirement",
            "revocation path",
        ),
        "No OAuth, browser, network, app, or plugin activation.",
    ),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _content_hash(payload: Any) -> str:
    text = stable_json(payload)
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_json_if_present(path: str | Path, *, repo_root: str | Path = ROOT) -> dict[str, Any]:
    target = Path(path)
    if not target.is_absolute():
        target = Path(repo_root) / target
    if not target.is_file():
        return {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _source_status(source: EvidenceSource, *, repo_root: str | Path) -> dict[str, Any]:
    payload = _read_json_if_present(source.path, repo_root=repo_root)
    return {
        "source_id": source.source_id,
        "path": source.path,
        "role": source.role,
        "present": bool(payload),
        "schema_version": payload.get("schema_version") or payload.get("read_model_version"),
        "read_model_id": payload.get("read_model_id"),
        "raw_private_body_imported": False,
        "authority_granted_by_source_presence": False,
    }


def _primitive_record(primitive: ExistingPrimitive) -> dict[str, Any]:
    return {
        "primitive_id": primitive.primitive_id,
        "platform_primitive": primitive.platform_primitive,
        "openclaw_surface": primitive.openclaw_surface,
        "status": primitive.status,
        "evidence_refs": list(primitive.evidence_refs),
        "maps_to": list(primitive.maps_to),
        "current_boundary": primitive.current_boundary,
        "live_runtime_authority": False,
        "credential_or_external_tool_authority": False,
    }


def _missing_record(item: MissingPrimitive) -> dict[str, Any]:
    return {
        "primitive_id": item.primitive_id,
        "missing_surface": item.missing_surface,
        "readiness_state": item.readiness_state,
        "why_needed": item.why_needed,
        "blocked_until": item.blocked_until,
        "safe_current_representation": "read-model gap / future-gated contract need",
    }


def _blocked_capability_records() -> list[dict[str, Any]]:
    return [
        {
            "capability_id": capability_id,
            "status": "blocked_or_future_gated",
            "reason": reason,
            "may_be_reopened_by": "later security-audited contract with explicit gates, receipts, and operator visibility",
        }
        for capability_id, reason in BLOCKED_CAPABILITIES
    ]


def _recommended_lane_record(lane: RecommendedLane) -> dict[str, Any]:
    return {
        "lane_id": lane.lane_id,
        "title": lane.title,
        "priority": lane.priority,
        "why_next": lane.why_next,
        "output_should_define": list(lane.output_should_define),
        "hard_boundary": lane.hard_boundary,
    }


def build_agent_platform_alignment(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    source_records = [_source_status(source, repo_root=repo_root) for source in EVIDENCE_SOURCES]
    source_presence = {source["source_id"]: source["present"] for source in source_records}
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": "agent_platform_alignment",
        "generated_at": generated_at,
        **NO_AUTHORITY_FLAGS,
        "alignment_status": "deterministic_read_model_only",
        "operator_summary": (
            "OpenClaw already has many agent-platform primitives as deterministic contracts: "
            "packages, capabilities, gates, receipts, awareness maps, stable app map transport, "
            "and health proof. It does not yet have live persistent agents. The next safe step is "
            "to define agent identities and actor/model routing before any package dispatch or tool authority."
        ),
        "platform_translation": {
            "modern_agent_platform_direction": [
                "persistent assistants",
                "tool protocols",
                "memory models",
                "agent routing",
                "skill/capability registries",
                "governed action gates",
                "app-surface integrations",
            ],
            "openclaw_translation": [
                "SQLite/read-model receipts as durable truth",
                "package compiler previews instead of prompt improvisation",
                "Guardian/Chief/Cassandra/Niles/Hermes roles as future-gated agent characters",
                "capability registries as descriptive metadata, not tool grants",
                "stable map bundle as app-facing local snapshot",
                "protected proof references instead of raw private content",
            ],
            "always_on_agent_position": "future_gated_readiness_only",
        },
        "evidence_sources": source_records,
        "source_presence_summary": source_presence,
        "existing_openclaw_primitives": [_primitive_record(item) for item in EXISTING_PRIMITIVES],
        "missing_platform_primitives": [_missing_record(item) for item in MISSING_PRIMITIVES],
        "blocked_capabilities": _blocked_capability_records(),
        "recommended_next_lanes": [_recommended_lane_record(item) for item in RECOMMENDED_NEXT_LANES],
        "mission_control_surface_guidance": {
            "top_layer_what_this_means": (
                "OpenClaw is becoming an agent platform, but today this is only readiness mapping: "
                "what exists, what is missing, and what remains blocked."
            ),
            "middle_layer_primitives_and_gaps": [
                "show existing package/capability/gate/memory/sync primitives",
                "show missing identity/router/memory/tool/receipt/kill-switch contracts",
                "show blocked capabilities without offering live controls",
            ],
            "lower_layer_proof_contract_refs": [
                "link to generated read-models and receipts",
                "keep raw proof/detail below the operator orientation",
                "do not render this as a backend table wall",
            ],
            "confidence_display_rule": (
                "Do not show noisy confidence when posture is deterministic; show uncertainty only when it changes the next safe move."
            ),
            "helm_guidance": "This belongs as an alignment/readiness lane, not an execution or chat surface.",
        },
        "next_safe_lane": {
            "lane_id": "agent_identity_actor_router_contract_v0",
            "title": "Agent Identity + Actor Router Contract v0",
            "reason": (
                "Define durable agent characters and actor/model candidates before package routing, tool authority, "
                "persistent assistants, or workbench launch paths."
            ),
        },
        "machine_proof": {
            "source_read_models_present": source_presence,
            "content_hash": None,
            "raw_private_bodies_included": False,
            "credentials_or_secrets_included": False,
            "runtime_activation_added": False,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_agent_platform_alignment(payload: dict[str, Any]) -> str:
    existing = payload["existing_openclaw_primitives"]
    missing = payload["missing_platform_primitives"]
    blocked = payload["blocked_capabilities"]
    next_lane = payload["next_safe_lane"]
    lines = [
        "# Agent Platform Alignment v0",
        "",
        "## Operator Summary",
        payload["operator_summary"],
        "",
        "## What OpenClaw Already Has",
    ]
    for item in existing:
        lines.append(
            f"- `{item['primitive_id']}`: {item['platform_primitive']} via {item['openclaw_surface']} "
            f"({item['status']})."
        )
    lines.extend(["", "## Missing Before Persistent Agents"])
    for item in missing:
        lines.append(f"- `{item['primitive_id']}`: {item['missing_surface']} ({item['readiness_state']}).")
    lines.extend(["", "## Blocked Capabilities"])
    for item in blocked:
        lines.append(f"- `{item['capability_id']}`: {item['status']}. {item['reason']}")
    lines.extend(
        [
            "",
            "## Mission Control Guidance",
            f"- Top layer: {payload['mission_control_surface_guidance']['top_layer_what_this_means']}",
            "- Middle layer: primitives, gaps, and blocked capabilities.",
            "- Lower layer: proof and contract references.",
            "- Do not make this a backend table wall or live control surface.",
            "",
            "## Next Safe Lane",
            f"- `{next_lane['lane_id']}`: {next_lane['title']}",
            f"- Reason: {next_lane['reason']}",
            "",
            "## Authority Boundary",
        ]
    )
    for key, value in NO_AUTHORITY_FLAGS.items():
        lines.append(f"- `{key}`: `{str(value).lower()}`")
    return "\n".join(lines).rstrip() + "\n"


def export_agent_platform_alignment(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> AgentPlatformAlignmentExportResult:
    payload = build_agent_platform_alignment(repo_root=repo_root, generated_at=generated_at)
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_agent_platform_alignment(payload), encoding="utf-8")
    return AgentPlatformAlignmentExportResult(
        schema_version=payload["schema_version"],
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        primitive_count=len(payload["existing_openclaw_primitives"]),
        missing_count=len(payload["missing_platform_primitives"]),
        runtime_authority_added=bool(payload["runtime_authority"]),
        credential_authority_added=bool(payload["credential_authority"]),
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Agent Platform Alignment read-model.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_agent_platform_alignment(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    if args.format == "json":
        payload = build_agent_platform_alignment(repo_root=args.repo_root)
        print(stable_json(payload), end="")
    elif args.format == "operator":
        payload = build_agent_platform_alignment(repo_root=args.repo_root)
        print(format_agent_platform_alignment(payload), end="")
    else:
        print(
            stable_json(
                {
                    "schema_version": result.schema_version,
                    "json_path": result.json_path,
                    "operator_path": result.operator_path,
                    "primitive_count": result.primitive_count,
                    "missing_count": result.missing_count,
                    "runtime_authority_added": result.runtime_authority_added,
                    "credential_authority_added": result.credential_authority_added,
                }
            ),
            end="",
        )
    return 0


__all__ = [
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "SCHEMA_VERSION",
    "build_agent_platform_alignment",
    "export_agent_platform_alignment",
    "format_agent_platform_alignment",
    "main",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
