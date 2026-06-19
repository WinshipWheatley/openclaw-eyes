"""OpenClaw Work Terrain Query Contract v0.

This read-model defines a metadata-first query grammar for finding OpenClaw
work terrain across source notes, contracts, generated read-models, receipts,
stable-map sections, tests, scripts, and validation artifacts. It does not run
queries over private bodies, scan broad roots, mutate files, launch tools, or
grant action authority.
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


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "openclaw_work_terrain_query_contract_v0"
READ_MODEL_ID = "openclaw_work_terrain_query_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"

ALLOWED_SOURCES = (
    "SQLITE_METADATA",
    "CORPUS_ATLAS_METADATA",
    "MARKDOWN_ATLAS_METADATA",
    "GENERATED_READ_MODELS",
    "OPERATOR_MARKDOWN_SUMMARIES",
    "STABLE_MAP_SECTIONS",
    "RECEIPT_METADATA",
    "SCRIPT_TEST_FILE_METADATA",
    "COMMIT_METADATA_IF_AVAILABLE",
    "VALIDATION_ARTIFACT_METADATA",
)

BLOCKED_SOURCES = (
    "BROAD_RAW_MARKDOWN_BODIES",
    "BROAD_PRIVATE_ROOTS",
    "MAC_PRIVATE_HOME",
    "PC_C_DRIVE",
    "EMAIL_ACCOUNT_BODIES",
    "COUPA_BROWSER_SESSIONS",
    "CREDENTIAL_STORES",
    "RAW_FINANCE_PRIVATE_BODIES",
)

WORK_TERRAIN_SOURCE_TYPES = (
    "MARKDOWN_FILE",
    "OPERATOR_MARKDOWN",
    "GENERATED_READ_MODEL_JSON",
    "GENERATED_OPERATOR_DIGEST",
    "PYTHON_CONTRACT",
    "EXPORT_SCRIPT",
    "TEST_FILE",
    "SQLITE_TABLE",
    "SQLITE_RECEIPT",
    "STABLE_MAP_SECTION",
    "MAC_SWIFT_SOURCE",
    "VALIDATION_SCREENSHOT",
    "WORKER_REPORT",
    "HANDOFF_FILE",
    "UNKNOWN_FAIL_CLOSED",
)

EXPECTED_RESULT_TYPES = (
    "terrain_metadata_result",
    "artifact_reference",
    "stable_map_visibility_record",
    "receipt_visibility_record",
    "classification_needed_marker",
)

QUERY_MODEL_FIELDS = (
    "query_id",
    "display_name",
    "query_text",
    "target_concepts",
    "target_actors",
    "target_worlds",
    "target_lanes",
    "target_repos",
    "target_artifact_types",
    "allowed_sources",
    "blocked_sources",
    "body_ingestion_allowed",
    "semantic_review_allowed",
    "authority_granted",
    "expected_result_types",
    "agent_map_binding_ids",
    "unresolved_target_actors",
    "next_safe_move",
)

AGENT_MAP_BINDING_FIELDS = (
    "binding_id",
    "query_id",
    "target_actor",
    "agent_id",
    "display_name",
    "lane_id",
    "lane_label",
    "status",
    "authority_level",
    "binding_basis",
    "matched_terms",
    "allowed_worlds",
    "allowed_output_kinds",
    "approval_required_for",
    "receipt_required_for",
    "routing_hints",
    "source_refs",
    "context_only",
    "action_authority_granted",
    "runtime_dispatch_allowed",
)

AGENT_MAP_SOURCE_REFS = (
    "agent_lane_registry.py::DEFAULT_AGENT_LANE_SEEDS",
    "generated/read_models/agent_lanes.json",
    "generated/read_models/agent_lanes_OPERATOR.md",
)

RESULT_SHAPE_FIELDS = (
    "result_id",
    "source_type",
    "source_ref",
    "path_or_key",
    "display_name",
    "matched_terms",
    "matched_actor",
    "matched_world",
    "matched_lane",
    "artifact_type",
    "current_known_status",
    "stable_map_visibility",
    "sqlite_visibility",
    "read_model_visibility",
    "receipt_visibility",
    "sensitivity_guess",
    "body_ingestion_status",
    "semantic_review_status",
    "next_classification_needed",
)

POLICY_FIELDS = (
    "metadata_first",
    "body_ingestion_default",
    "semantic_review_default",
    "private_root_policy",
    "c_drive_policy",
    "repo_b_policy",
    "mac_root_policy",
    "generated_artifact_policy",
    "stable_map_policy",
    "operator_attention_policy",
)

AUTHORITY_BOUNDARY = {
    "action_authority_granted": False,
    "body_ingestion_allowed": False,
    "semantic_review_allowed_now": False,
    "broad_private_root_scan_allowed": False,
    "c_drive_scan_allowed": False,
    "repo_b_mutation_allowed": False,
    "file_move_allowed": False,
    "file_delete_allowed": False,
    "file_rename_allowed": False,
    "file_rewrite_allowed": False,
    "file_archive_allowed": False,
    "stable_map_refresh_allowed": False,
    "mission_control_swift_change_allowed": False,
    "mac_sync_import_allowed": False,
    "network_operation_allowed": False,
    "git_push_pull_fetch_allowed": False,
    "model_api_execution_allowed": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "runtime_dispatch_allowed": False,
    "planner_builder_queue_autonomy_allowed": False,
    "credential_account_browser_email_coupa_access_allowed": False,
    "authority_escalation_allowed": False,
}


@dataclass(frozen=True)
class WorkTerrainQuery:
    query_id: str
    display_name: str
    query_text: str
    target_concepts: tuple[str, ...]
    target_actors: tuple[str, ...]
    target_worlds: tuple[str, ...]
    target_lanes: tuple[str, ...]
    target_repos: tuple[str, ...]
    target_artifact_types: tuple[str, ...]
    allowed_sources: tuple[str, ...]
    blocked_sources: tuple[str, ...]
    body_ingestion_allowed: bool
    semantic_review_allowed: bool
    authority_granted: bool
    expected_result_types: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class WorkTerrainQueryResultShape:
    result_id: str
    source_type: str
    source_ref: str
    path_or_key: str
    display_name: str
    matched_terms: tuple[str, ...]
    matched_actor: str
    matched_world: str
    matched_lane: str
    artifact_type: str
    current_known_status: str
    stable_map_visibility: str
    sqlite_visibility: str
    read_model_visibility: str
    receipt_visibility: str
    sensitivity_guess: str
    body_ingestion_status: str
    semantic_review_status: str
    next_classification_needed: str


@dataclass(frozen=True)
class WorkTerrainQueryPolicy:
    metadata_first: bool
    body_ingestion_default: bool
    semantic_review_default: bool
    private_root_policy: str
    c_drive_policy: str
    repo_b_policy: str
    mac_root_policy: str
    generated_artifact_policy: str
    stable_map_policy: str
    operator_attention_policy: str


@dataclass(frozen=True)
class WorkTerrainQueryAgentMapBinding:
    binding_id: str
    query_id: str
    target_actor: str
    agent_id: str
    display_name: str
    lane_id: str
    lane_label: str
    status: str
    authority_level: str
    binding_basis: str
    matched_terms: tuple[str, ...]
    allowed_worlds: tuple[str, ...]
    allowed_output_kinds: tuple[str, ...]
    approval_required_for: tuple[str, ...]
    receipt_required_for: tuple[str, ...]
    routing_hints: tuple[str, ...]
    source_refs: tuple[str, ...]
    context_only: bool
    action_authority_granted: bool
    runtime_dispatch_allowed: bool


@dataclass(frozen=True)
class WorkTerrainQueryExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    query_count: int
    source_type_count: int
    body_ingestion_allowed: bool
    semantic_review_allowed: bool
    action_authority_granted: bool


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _normalize_agent_key(value: str) -> str:
    return value.strip().lower().replace(" / ", "_").replace("/", "_").replace(" ", "_").replace("-", "_")


def _agent_lookup(seeds: tuple[AgentLaneSeed, ...] = DEFAULT_AGENT_LANE_SEEDS) -> dict[str, AgentLaneSeed]:
    lookup: dict[str, AgentLaneSeed] = {}
    for seed in seeds:
        keys = (seed.agent_id, seed.display_name, *seed.aliases)
        for key in keys:
            lookup.setdefault(_normalize_agent_key(key), seed)
    return lookup


def _query(
    query_id: str,
    *,
    display_name: str,
    query_text: str,
    target_concepts: tuple[str, ...],
    target_actors: tuple[str, ...] = (),
    target_worlds: tuple[str, ...] = (),
    target_lanes: tuple[str, ...] = (),
    target_repos: tuple[str, ...] = ("Repo A",),
    target_artifact_types: tuple[str, ...] = WORK_TERRAIN_SOURCE_TYPES,
    next_safe_move: str,
) -> WorkTerrainQuery:
    return WorkTerrainQuery(
        query_id=query_id,
        display_name=display_name,
        query_text=query_text,
        target_concepts=target_concepts,
        target_actors=target_actors,
        target_worlds=target_worlds,
        target_lanes=target_lanes,
        target_repos=target_repos,
        target_artifact_types=target_artifact_types,
        allowed_sources=ALLOWED_SOURCES,
        blocked_sources=BLOCKED_SOURCES,
        body_ingestion_allowed=False,
        semantic_review_allowed=False,
        authority_granted=False,
        expected_result_types=EXPECTED_RESULT_TYPES,
        next_safe_move=next_safe_move,
    )


def _agent_binding(query: WorkTerrainQuery, target_actor: str, seed: AgentLaneSeed) -> WorkTerrainQueryAgentMapBinding:
    return WorkTerrainQueryAgentMapBinding(
        binding_id=f"{query.query_id}::{seed.agent_id}",
        query_id=query.query_id,
        target_actor=target_actor,
        agent_id=seed.agent_id,
        display_name=seed.display_name,
        lane_id=seed.lane_id,
        lane_label=seed.lane_label,
        status=seed.status,
        authority_level=seed.authority_level,
        binding_basis="target_actor_to_agent_lane_registry",
        matched_terms=(target_actor,),
        allowed_worlds=seed.allowed_worlds,
        allowed_output_kinds=seed.allowed_output_kinds,
        approval_required_for=seed.approval_required_for,
        receipt_required_for=seed.receipt_required_for,
        routing_hints=seed.routing_hints,
        source_refs=AGENT_MAP_SOURCE_REFS,
        context_only=True,
        action_authority_granted=False,
        runtime_dispatch_allowed=False,
    )


def build_query_agent_map_wiring(
    queries: tuple[WorkTerrainQuery, ...],
    *,
    seeds: tuple[AgentLaneSeed, ...] = DEFAULT_AGENT_LANE_SEEDS,
) -> dict[str, Any]:
    lookup = _agent_lookup(seeds)
    bindings: list[WorkTerrainQueryAgentMapBinding] = []
    bindings_by_query_id: dict[str, list[str]] = {query.query_id: [] for query in queries}
    unresolved_by_query_id: dict[str, list[str]] = {query.query_id: [] for query in queries}

    for query in queries:
        seen_agent_ids: set[str] = set()
        for target_actor in query.target_actors:
            seed = lookup.get(_normalize_agent_key(target_actor))
            if seed is None:
                unresolved_by_query_id[query.query_id].append(target_actor)
                continue
            if seed.agent_id in seen_agent_ids:
                continue
            binding = _agent_binding(query, target_actor, seed)
            bindings.append(binding)
            bindings_by_query_id[query.query_id].append(binding.binding_id)
            seen_agent_ids.add(seed.agent_id)

    return {
        "mode": "query_target_actor_to_agent_lane_context_only",
        "source_refs": list(AGENT_MAP_SOURCE_REFS),
        "binding_model": {
            "model_name": "WorkTerrainQueryAgentMapBinding",
            "fields": list(AGENT_MAP_BINDING_FIELDS),
        },
        "bindings": [asdict(binding) for binding in bindings],
        "bindings_by_query_id": bindings_by_query_id,
        "unresolved_target_actors_by_query_id": unresolved_by_query_id,
        "unknown_actor_policy": (
            "Target actors absent from agent_lane_registry remain metadata labels only; "
            "they do not create routing, execution, or authority."
        ),
        "context_only": True,
        "unknowns_fail_closed": True,
        "action_authority_granted": False,
        "runtime_dispatch_allowed": False,
    }


def default_work_terrain_queries() -> tuple[WorkTerrainQuery, ...]:
    return (
        _query(
            "chief_related_work_terrain",
            display_name="Chief-Related Work Terrain",
            query_text="Show me all Chief-related OpenClaw terrain.",
            target_concepts=(
                "Chief",
                "work board",
                "cue candidates",
                "agentic loop",
                "reconciliation",
                "cross-off",
                "test harness",
                "build/repair",
                "queue/autonomy",
            ),
            target_actors=("Chief",),
            target_lanes=("chief_test_harness_cross_off", "operator_attention_promotion"),
            next_safe_move="Query metadata surfaces first, then route results to relationship indexing.",
        ),
        _query(
            "capital_hilton_related_work_terrain",
            display_name="Capital Hilton-Related Work Terrain",
            query_text="Show me everything related to Capital Hilton.",
            target_concepts=(
                "Capital Hilton",
                "Finance",
                "Cassandra",
                "Guardian",
                "invoice",
                "proof metadata",
                "protected proof intake",
            ),
            target_actors=("Cassandra", "Guardian"),
            target_worlds=("Finance",),
            target_lanes=("capital_hilton_proof_metadata", "capital_hilton_protected_proof_intake"),
            next_safe_move="Return metadata-only terrain and keep finance action locked.",
        ),
        _query(
            "security_pass_related_work_terrain",
            display_name="Security Pass-Related Work Terrain",
            query_text="Show me all Security Pass and authority-boundary terrain.",
            target_concepts=(
                "security pass",
                "authority",
                "Guardian",
                "trust clearance",
                "security delta",
                "blocked adapters",
            ),
            target_actors=("Guardian", "Hermes", "Chief"),
            target_lanes=("security_pass", "security_delta_review"),
            next_safe_move="Use results to find authority-boundary contracts and gap candidates.",
        ),
        _query(
            "niles_struna_related_work_terrain",
            display_name="Niles / Struna-Related Work Terrain",
            query_text="Show me all Niles, Struna, music, art, plugin, synth, and Mac-port terrain.",
            target_concepts=(
                "Niles",
                "Struna",
                "music/art world",
                "plugin",
                "synth",
                "Mac port",
            ),
            target_actors=("Niles", "Struna"),
            target_worlds=("Music", "Art"),
            target_repos=("Repo A", "Mac app metadata if imported"),
            next_safe_move="Keep Mac private roots blocked unless imported metadata exists.",
        ),
        _query(
            "repo_b_planner_builder_related_work_terrain",
            display_name="Repo B Planner / Builder-Related Work Terrain",
            query_text="Show me Repo B, planner, builder, orchestrator, and legacy runtime terrain.",
            target_concepts=("Repo B", "planner", "builder", "orchestrator", "legacy runtime"),
            target_actors=("Operator", "Chief"),
            target_repos=("Repo B reference metadata only",),
            target_artifact_types=("WORKER_REPORT", "HANDOFF_FILE", "MARKDOWN_FILE", "UNKNOWN_FAIL_CLOSED"),
            next_safe_move="Treat Repo B as reference-only unless a future explicit approval opens a narrower lane.",
        ),
    )


def default_result_shape() -> WorkTerrainQueryResultShape:
    return WorkTerrainQueryResultShape(
        result_id="example_result_shape_only",
        source_type="GENERATED_READ_MODEL_JSON",
        source_ref="generated/read_models/example.json",
        path_or_key="stable_map.example_section",
        display_name="Example Terrain Match",
        matched_terms=("Chief", "cross-off"),
        matched_actor="Chief",
        matched_world="none",
        matched_lane="chief_test_harness_cross_off",
        artifact_type="GENERATED_READ_MODEL_JSON",
        current_known_status="UNKNOWN_UNTIL_CLASSIFIED",
        stable_map_visibility="UNKNOWN_UNTIL_INDEXED",
        sqlite_visibility="UNKNOWN_UNTIL_INDEXED",
        read_model_visibility="VISIBLE_AS_METADATA",
        receipt_visibility="UNKNOWN_UNTIL_INDEXED",
        sensitivity_guess="UNKNOWN_FAIL_CLOSED",
        body_ingestion_status="NOT_INGESTED_METADATA_ONLY",
        semantic_review_status="NOT_ALLOWED_IN_THIS_CONTRACT",
        next_classification_needed="relationship_index_then_staleness_candidate_classification",
    )


def default_query_policy() -> WorkTerrainQueryPolicy:
    return WorkTerrainQueryPolicy(
        metadata_first=True,
        body_ingestion_default=False,
        semantic_review_default=False,
        private_root_policy="Broad private roots are blocked unless an exact operator-approved root is later provided.",
        c_drive_policy="PC C-drive surfaces are blocked in this contract.",
        repo_b_policy="Repo B is reference-only unless explicitly approved by a later bounded lane.",
        mac_root_policy="Mac private roots require operator approval and imported metadata; no PC-side Mac private scan.",
        generated_artifact_policy="Generated artifacts must be labeled separately from human-authored source notes.",
        stable_map_policy="Stable map is app-facing reflection, not source truth.",
        operator_attention_policy="A terrain match does not require operator attention until promoted by a later contract.",
    )


def build_openclaw_work_terrain_query_contract(*, generated_at: str | None = None) -> dict[str, Any]:
    queries = default_work_terrain_queries()
    policy = default_query_policy()
    result_shape = default_result_shape()
    agent_map_wiring = build_query_agent_map_wiring(queries)
    query_examples: list[dict[str, Any]] = []
    for query in queries:
        query_dict = asdict(query)
        query_dict["agent_map_binding_ids"] = agent_map_wiring["bindings_by_query_id"][query.query_id]
        query_dict["unresolved_target_actors"] = agent_map_wiring["unresolved_target_actors_by_query_id"][query.query_id]
        query_examples.append(query_dict)
    binding_agent_ids = sorted({binding["agent_id"] for binding in agent_map_wiring["bindings"]})
    all_queries_have_bindings = all(agent_map_wiring["bindings_by_query_id"][query.query_id] for query in queries)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at or utc_now(),
        "contract_status": "metadata_only_query_contract",
        "core_doctrine": {
            "terrain_records_broadly": True,
            "bodies_selectively": True,
            "truth_only_through_receipts": True,
            "file_existing_is_not_current": True,
            "markdown_note_is_not_doctrine": True,
            "worker_report_is_not_done_proof": True,
            "generated_read_model_does_not_require_operator_attention": True,
            "stable_map_is_app_facing_not_source_truth": True,
            "terrain_query_grants_mutation_or_promotion": False,
        },
        "query_domain_model": {
            "model_name": "WorkTerrainQuery",
            "fields": list(QUERY_MODEL_FIELDS),
            "allowed_sources": list(ALLOWED_SOURCES),
            "blocked_sources": list(BLOCKED_SOURCES),
            "expected_result_types": list(EXPECTED_RESULT_TYPES),
        },
        "agent_map_wiring": agent_map_wiring,
        "terrain_result_shape": {
            "model_name": "WorkTerrainQueryResultShape",
            "fields": list(RESULT_SHAPE_FIELDS),
            "example_shape": asdict(result_shape),
            "live_result": False,
        },
        "work_terrain_source_types": list(WORK_TERRAIN_SOURCE_TYPES),
        "default_query_examples": query_examples,
        "work_terrain_query_policy": asdict(policy),
        "questions_enabled_later": [
            "Which Chief docs exist?",
            "Which are current?",
            "Which are old prompts?",
            "Which are superseded?",
            "Which concepts overlap?",
            "Which files are missing stable-map representation?",
            "Which built artifacts lack a source note?",
            "Which source notes describe things already built?",
            "Which items need Hermes review?",
            "Which items need Chief reconciliation?",
            "Which items should become consolidation candidates?",
        ],
        "authority_boundary": {
            **AUTHORITY_BOUNDARY,
            "all_action_authority_flags_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        },
        "machine_proof": {
            "query_model_exists": True,
            "result_shape_exists": True,
            "policy_exists": True,
            "default_query_count": len(queries),
            "agent_map_wiring_exists": True,
            "agent_map_binding_model_exists": True,
            "agent_map_binding_count": len(agent_map_wiring["bindings"]),
            "agent_map_source_refs": list(AGENT_MAP_SOURCE_REFS),
            "all_default_queries_have_agent_map_bindings": all_queries_have_bindings,
            "bound_agent_ids": binding_agent_ids,
            "known_agent_bindings_from_agent_lane_registry": all(
                agent_id in {seed.agent_id for seed in DEFAULT_AGENT_LANE_SEEDS} for agent_id in binding_agent_ids
            ),
            "unknown_target_actors_fail_closed": agent_map_wiring["unknowns_fail_closed"],
            "struna_actor_unresolved_fail_closed": "Struna" in agent_map_wiring[
                "unresolved_target_actors_by_query_id"
            ]["niles_struna_related_work_terrain"],
            "operator_actor_unresolved_fail_closed": "Operator" in agent_map_wiring[
                "unresolved_target_actors_by_query_id"
            ]["repo_b_planner_builder_related_work_terrain"],
            "chief_example_exists": any(query.query_id == "chief_related_work_terrain" for query in queries),
            "capital_hilton_example_exists": any(
                query.query_id == "capital_hilton_related_work_terrain" for query in queries
            ),
            "body_ingestion_disabled": True,
            "semantic_review_disabled": True,
            "private_broad_roots_blocked": "BROAD_PRIVATE_ROOTS" in BLOCKED_SOURCES,
            "c_drive_blocked": "PC_C_DRIVE" in BLOCKED_SOURCES and policy.c_drive_policy.endswith("blocked in this contract."),
            "repo_b_reference_only": "reference-only" in policy.repo_b_policy,
            "stable_map_not_source_truth": policy.stable_map_policy == "Stable map is app-facing reflection, not source truth.",
            "no_action_authority": True,
            "credential_or_secret_included": False,
            "raw_private_body_included": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_openclaw_work_terrain_query_contract(payload: dict[str, Any]) -> str:
    policy = payload["work_terrain_query_policy"]
    lines = [
        "# OpenClaw Work Terrain Query Contract v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        "This contract gives OpenClaw a safe way to ask focused terrain questions before reading bodies or acting on anything. It looks for metadata first: SQLite rows, Atlas metadata, generated read-models, operator summaries, stable-map sections, receipts, scripts, tests, commits when already available, and validation artifacts.",
        "",
        "It does not decide what is current, stale, superseded, or ready to promote yet. It defines the query grammar that later relationship and classification lanes can use.",
        "",
        "## What It Can Ask Later",
        "",
    ]
    for query in payload["default_query_examples"]:
        binding_ids = ", ".join(query["agent_map_binding_ids"])
        unresolved = ", ".join(query["unresolved_target_actors"]) or "none"
        lines.append(
            f"- `{query['query_id']}`: {query['query_text']} "
            f"(agent-map bindings: {binding_ids}; unresolved actors: {unresolved})"
        )
    lines.extend(
        [
            "",
            "## Agent Map Wiring",
            "",
            "- Query target actors are bound to `agent_lane_registry.py::DEFAULT_AGENT_LANE_SEEDS` as context only.",
            "- Unknown target actors stay unresolved/fail-closed and grant no routing, runtime dispatch, or action authority.",
            f"- Binding count: `{payload['machine_proof']['agent_map_binding_count']}`.",
            "",
            "## Safety Policy",
            "",
            f"- Metadata first: `{str(policy['metadata_first']).lower()}`",
            f"- Body ingestion by default: `{str(policy['body_ingestion_default']).lower()}`",
            f"- Semantic review by default: `{str(policy['semantic_review_default']).lower()}`",
            f"- Repo B policy: {policy['repo_b_policy']}",
            f"- Stable map policy: {policy['stable_map_policy']}",
            "",
            "## Why This Matters",
            "",
            "A file existing does not make it current. A Markdown note does not make it doctrine. A worker report does not prove completion. A stable-map section is app-facing truth, not source truth. Terrain queries find references; later receipt and classification lanes decide what those references mean.",
            "",
            "## What Remains Blocked",
            "",
            "- Broad raw Markdown bodies, broad private roots, Mac private home folders, PC C-drive surfaces, email bodies, Coupa/browser sessions, credential stores, raw finance/private bodies, file moves/deletes/renames, model/tool/agent/runtime execution, network, git push/pull/fetch, Mac sync/import, and Mission Control Swift changes.",
            "",
            "## Next Batch Lane",
            "",
            "- Work Terrain Relationship Index: connect terrain results across source notes, built artifacts, receipts, and stable-map sections without deciding staleness yet.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_openclaw_work_terrain_query_contract(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> WorkTerrainQueryExportResult:
    payload = build_openclaw_work_terrain_query_contract(generated_at=generated_at)
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_openclaw_work_terrain_query_contract(payload), encoding="utf-8")
    return WorkTerrainQueryExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        query_count=len(payload["default_query_examples"]),
        source_type_count=len(payload["work_terrain_source_types"]),
        body_ingestion_allowed=payload["authority_boundary"]["body_ingestion_allowed"],
        semantic_review_allowed=payload["authority_boundary"]["semantic_review_allowed_now"],
        action_authority_granted=payload["authority_boundary"]["action_authority_granted"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export OpenClaw Work Terrain Query Contract.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_openclaw_work_terrain_query_contract(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    summary = {
        "schema_version": result.schema_version,
        "json_path": result.json_path,
        "operator_path": result.operator_path,
        "query_count": result.query_count,
        "source_type_count": result.source_type_count,
        "body_ingestion_allowed": result.body_ingestion_allowed,
        "semantic_review_allowed": result.semantic_review_allowed,
        "action_authority_granted": result.action_authority_granted,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        print(f"OpenClaw Work Terrain Query Contract: `{READ_MODEL_ID}`")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
    return 0


__all__ = [
    "ALLOWED_SOURCES",
    "AGENT_MAP_SOURCE_REFS",
    "BLOCKED_SOURCES",
    "JSON_EXPORT_NAME",
    "OPERATOR_EXPORT_NAME",
    "READ_MODEL_ID",
    "SCHEMA_VERSION",
    "WORK_TERRAIN_SOURCE_TYPES",
    "WorkTerrainQuery",
    "WorkTerrainQueryAgentMapBinding",
    "WorkTerrainQueryPolicy",
    "WorkTerrainQueryResultShape",
    "build_query_agent_map_wiring",
    "build_openclaw_work_terrain_query_contract",
    "default_query_policy",
    "default_result_shape",
    "default_work_terrain_queries",
    "export_openclaw_work_terrain_query_contract",
    "format_openclaw_work_terrain_query_contract",
    "stable_json",
]
