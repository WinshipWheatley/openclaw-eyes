"""LM2 canonical worker spine consolidation artifacts.

This module builds documentation/read-model artifacts only. It does not create
a worker registry, queue database, model router, service, approval system, or
dashboard. Runtime worker package state remains canonical in
codex_work_package_lifecycle.py.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import codex_work_package_lifecycle as lifecycle


SCHEMA_VERSION = "LM2_CANONICAL_WORKER_SPINE_CONSOLIDATION_V0"
STATUS_READY = "OPENCLAW_LM2_CANONICAL_WORKER_SPINE_CONSOLIDATION_READY"

DEFAULT_SYSTEM_KNOWLEDGE_ROOT = Path("generated/system_knowledge/worker_spine_consolidation")
DEFAULT_READ_MODEL_PATH = Path("generated/read_models/lm2_worker_spine_status.json")
SPINE_JSON_NAME = "lm2_canonical_worker_spine_v0.json"
SPINE_MD_NAME = "lm2_canonical_worker_spine_v0.md"
REPO_B_JSON_NAME = "repo_b_legacy_disposition_v0.json"
REPO_B_MD_NAME = "repo_b_legacy_disposition_v0.md"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _content_hash(payload: Mapping[str, Any]) -> str:
    clone = dict(payload)
    machine = clone.get("machine_proof")
    if isinstance(machine, Mapping):
        machine = dict(machine)
        machine.pop("content_hash", None)
        clone["machine_proof"] = machine
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def repo_a_module_roles() -> list[dict[str, str]]:
    return [
        {
            "path": "codex_work_package_lifecycle.py",
            "role": "runtime_spine",
            "disposition": "canonical",
            "reason": "Owns package queue, dispatch claims, result ingest, validation receipts, activation decisions, SQLite registry, and Watch Desk projection.",
        },
        {
            "path": "scripts/openclaw_run.py",
            "role": "cli_control_surface",
            "disposition": "canonical_cli",
            "reason": "Existing operator CLI for status/show/dispatch/ingest against codex_work_package_lifecycle.py.",
        },
        {
            "path": "assignment_loop_contract.py",
            "role": "task_container",
            "disposition": "canonical_contract",
            "reason": "Defines bounded assignment fields: goal, sources, standard, permission boundary, proof, and stop condition.",
        },
        {
            "path": "openclaw_lm_consult_spine.py",
            "role": "consult_transport",
            "disposition": "canonical_transport",
            "reason": "Provider-neutral advisory request/result contract; can stage work that becomes a canonical worker package.",
        },
        {
            "path": "openclaw_agent_role_registry.py",
            "role": "agent_role_context",
            "disposition": "canonical_contract",
            "reason": "Provides compact role cards and full context refs for LM2 packages without inlining large agent docs.",
        },
        {
            "path": "provider_access_catalog.py",
            "role": "provider_access_metadata",
            "disposition": "support_metadata",
            "reason": "Describes installed/provider access modes; metadata does not grant execution authority.",
        },
        {
            "path": "provider_access_auth_status.py",
            "role": "provider_auth_metadata",
            "disposition": "support_metadata",
            "reason": "Records safe auth/subscription status probes without model invocation or credential values.",
        },
        {
            "path": "proof_to_response_verifier.py",
            "role": "proof_verification",
            "disposition": "canonical_verifier",
            "reason": "Deterministic proof-to-response publication gate; invoked by worker result ingest only when explicit proof specs are supplied.",
        },
        {
            "path": "watch_desk_feed.py",
            "role": "projection",
            "disposition": "canonical_projection",
            "reason": "Displays canonical worker lifecycle items without adding a dashboard or new lane.",
        },
        {
            "path": "spawned_worker_package_lifecycle.py",
            "role": "contract_only",
            "disposition": "deprecated_runtime_retained",
            "reason": "Retained for historical spawned-worker lifecycle contract/read model; runtime queue is canonical elsewhere.",
        },
        {
            "path": "cross_machine_worker_dispatch_package.py",
            "role": "support_metadata",
            "disposition": "compatibility",
            "reason": "Retained for cross-machine packaging metadata; not a live dispatch runtime.",
        },
        {
            "path": "openclaw_lm_child_package_gate.py",
            "role": "contract_only",
            "disposition": "future_contract_not_runtime",
            "reason": "Retained as future child-package gate contract; no LM2 spawning path is enabled here.",
        },
        {
            "path": "model_work_package_router.py",
            "role": "support_metadata",
            "disposition": "metadata_router_not_runtime_registry",
            "reason": "Deterministic model class/package metadata; canonical runtime registry remains codex_work_package_lifecycle.py.",
        },
    ]


def repo_b_legacy_disposition() -> dict[str, Any]:
    return {
        "schema_version": "REPO_B_LEGACY_DISPOSITION_V0",
        "repo_b_root": "/home/openclaw_external/openclaw-runtime",
        "runtime_authority": "reference_only",
        "repo_b_code_imported": False,
        "represented_in_repo_a": [
            {
                "repo_b_concept": "chief_router.py routing/orchestration",
                "repo_a_rail": "Operator Context Switchboard, agent_lane_registry.py, openclaw_lm_consult_spine.py",
                "disposition": "represented_in_repo_a",
            },
            {
                "repo_b_concept": "chief_watcher_brain.py watch/status ideas",
                "repo_a_rail": "watch_desk_feed.py and generated/read_models status projections",
                "disposition": "represented_in_repo_a",
            },
            {
                "repo_b_concept": "chief_worker.py / ceo_briefing_worker.py worker concepts",
                "repo_a_rail": "codex_work_package_lifecycle.py plus Assignment Loop",
                "disposition": "represented_in_repo_a",
            },
        ],
        "superseded": [
            {
                "repo_b_concept": "older bridge/broker package flow",
                "repo_a_replacement": "scripts/openclaw_run.py dispatch/ingest and canonical package SQLite registry",
            },
            {
                "repo_b_concept": "legacy approval bridge concepts",
                "repo_a_replacement": "Guardian/HITL exact-send approval spine, kept separate from LM2.",
            },
        ],
        "unsafe_blocked": [
            "google_access_broker.py OAuth/token/credential bridge patterns",
            "legacy OAuth refresh or credential storage paths",
            "automatic broker-based Gmail/Calendar/Contacts access",
            "autonomous repair loops that mutate runtime or restart services without current rails",
            "old bridge code that bypasses Guardian/HITL or package receipts",
        ],
        "candidate_pattern_only": [
            {
                "pattern": "watcher summaries",
                "repo_a_expression": "Watch Desk item sourced from canonical read models and receipts only.",
            },
            {
                "pattern": "queue balancing",
                "repo_a_expression": "Worker Run Manager queue metadata, not a separate live queue.",
            },
            {
                "pattern": "capability registry language",
                "repo_a_expression": "Capability status read models and Assignment Loop proof requirements.",
            },
        ],
        "unknown_needs_review": [
            "Any Repo B file not explicitly classified here.",
            "Any broker/repair capability whose safety cannot be proven from current Repo A receipts.",
        ],
        "blocked_legacy_patterns": [
            "old OAuth",
            "google_access_broker",
            "credential bridge",
            "automatic external broker",
            "autonomous repair loop",
        ],
        "hard_rule": "Repo B is reference-only and not runtime authority; useful patterns must be re-expressed through Repo A rails.",
    }


def agent_usability_matrix() -> list[dict[str, Any]]:
    return [
        {
            "agent": "Cassandra",
            "can_request_worker_package": True,
            "can_dispatch": False,
            "can_ingest_result": False,
            "can_verify_proof": False,
            "can_summarize_next_action": True,
            "missing_integration": "Use orchestrator rails to create Assignment Loop or LM Consult request; dispatch remains operator/Chief controlled.",
        },
        {
            "agent": "Chief",
            "can_request_worker_package": True,
            "can_dispatch": True,
            "can_ingest_result": True,
            "can_verify_proof": True,
            "can_summarize_next_action": True,
            "missing_integration": "No automatic model execution; dispatch/ingest remains explicit.",
        },
        {
            "agent": "Niles",
            "can_request_worker_package": True,
            "can_dispatch": False,
            "can_ingest_result": False,
            "can_verify_proof": False,
            "can_summarize_next_action": True,
            "missing_integration": "Creative lane requests need packaged context; no DAW/media daemon authority.",
        },
        {
            "agent": "Hermes",
            "can_request_worker_package": True,
            "can_dispatch": False,
            "can_ingest_result": False,
            "can_verify_proof": False,
            "can_summarize_next_action": True,
            "missing_integration": "Adapter/boundary role only; do not start a sidecar in this consolidation.",
        },
        {
            "agent": "Guardian",
            "can_request_worker_package": False,
            "can_dispatch": False,
            "can_ingest_result": False,
            "can_verify_proof": True,
            "can_summarize_next_action": True,
            "missing_integration": "Guardian remains separate approval/safety gate and does not become a worker dispatcher.",
        },
        {
            "agent": "Watch Desk",
            "can_request_worker_package": False,
            "can_dispatch": False,
            "can_ingest_result": False,
            "can_verify_proof": False,
            "can_summarize_next_action": True,
            "missing_integration": "Projection only; push_allowed remains false.",
        },
    ]


def build_lm2_spine_read_model(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    repo_b = repo_b_legacy_disposition()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": STATUS_READY,
        "generated_at": generated_at,
        "canonical_spine": lifecycle.canonical_spine_metadata(),
        "runtime_spine_files": [
            "codex_work_package_lifecycle.py",
            "scripts/openclaw_run.py",
            "assignment_loop_contract.py",
            "openclaw_lm_consult_spine.py",
            "provider_access_catalog.py",
            "provider_access_auth_status.py",
            "proof_to_response_verifier.py",
            "watch_desk_feed.py",
        ],
        "adapter_functions": [
            "create_worker_package_from_assignment_loop",
            "create_worker_package_from_lm_consult_request",
        ],
        "module_roles": repo_a_module_roles(),
        "repo_b_legacy_disposition_summary": {
            "represented_in_repo_a_count": len(repo_b["represented_in_repo_a"]),
            "superseded_count": len(repo_b["superseded"]),
            "unsafe_blocked_count": len(repo_b["unsafe_blocked"]),
            "candidate_pattern_only_count": len(repo_b["candidate_pattern_only"]),
            "unknown_needs_review_count": len(repo_b["unknown_needs_review"]),
        },
        "agent_usability_matrix": agent_usability_matrix(),
        "watch_desk_behavior": {
            "projection_source": "codex_work_package_lifecycle.py build_read_model watch_desk_items",
            "new_dashboard_created": False,
            "new_lane_created": False,
            "push_allowed": False,
        },
        "current_known_blockers": [
            "No automatic model execution is enabled.",
            "Repo B remains reference-only.",
            "Provider auth/subscription metadata does not grant execution authority.",
        ],
        "what_not_to_build_next": [
            "Do not create another worker registry or queue database.",
            "Do not resurrect Repo B google_access_broker/OAuth/credential bridge code.",
            "Do not create a new model router or approval system.",
            "Do not let LM2 output mutate runtime directly.",
        ],
        "safety_flags": {
            "model_api_called": False,
            "worker_spawned": False,
            "new_sqlite_registry_created": False,
            "runtime_policy_mutated": False,
            "confirmed_reference_data_created": False,
            "hydration_run": False,
            "repo_b_code_imported": False,
            "guardian_approval_created": False,
        },
        "authority_boundary": lifecycle.AUTHORITY_BOUNDARY,
    }
    payload["machine_proof"] = {
        "content_hash": _content_hash(payload),
        "no_model_calls": True,
        "no_new_queue_database": True,
        "repo_b_reference_only": True,
        "watch_desk_push_allowed_false": True,
    }
    return payload


def render_lm2_spine_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# LM2 Canonical Worker Spine",
        "",
        f"Status: {payload.get('status')}",
        "",
        "LM2 is the spawned advisory/worker layer: a bounded model/worker instance receives a deterministic package with goal, sources, standard, permission boundary, proof requirement, expected output schema, and stop condition. It has no direct runtime authority.",
        "",
        "## Canonical Runtime Spine",
        f"- File: `{payload['canonical_spine']['canonical_spine_file']}`",
        f"- SQLite registry: `{payload['canonical_spine']['sqlite_registry_path']}`",
        "- CLI: `scripts/openclaw_run.py`",
        "- Watch Desk projection: `watch_desk_feed.py` consumes canonical lifecycle read-model items.",
        "",
        "## Adapter Functions",
    ]
    lines.extend(f"- `{name}`" for name in payload.get("adapter_functions", []))
    lines.extend(["", "## Module Roles"])
    for row in payload.get("module_roles", []):
        lines.append(f"- `{row['path']}`: {row['role']} / {row['disposition']}")
    lines.extend(["", "## Agent Usability"])
    for row in payload.get("agent_usability_matrix", []):
        lines.append(
            f"- {row['agent']}: request={row['can_request_worker_package']}, dispatch={row['can_dispatch']}, ingest={row['can_ingest_result']}, verify={row['can_verify_proof']}, summarize={row['can_summarize_next_action']}"
        )
    lines.extend(
        [
            "",
            "## Repo B Legacy Disposition",
            "Repo B is reference-only and not runtime authority. Unsafe OAuth, broker, credential, and autonomous repair-loop patterns stay blocked.",
            "",
            "## What Not To Build Next",
        ]
    )
    lines.extend(f"- {item}" for item in payload.get("what_not_to_build_next", []))
    return "\n".join(lines) + "\n"


def render_repo_b_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Repo B Legacy Disposition",
        "",
        "Repo B is reference-only and not runtime authority. No Repo B code becomes live runtime code in this task.",
        "",
        "## Unsafe Blocked",
    ]
    lines.extend(f"- {item}" for item in payload.get("unsafe_blocked", []))
    lines.extend(["", "## Represented In Repo A"])
    for row in payload.get("represented_in_repo_a", []):
        lines.append(f"- {row['repo_b_concept']} -> {row['repo_a_rail']}")
    lines.extend(["", "## Candidate Pattern Only"])
    for row in payload.get("candidate_pattern_only", []):
        lines.append(f"- {row['pattern']} -> {row['repo_a_expression']}")
    return "\n".join(lines) + "\n"


def export_lm2_canonical_worker_spine(
    *,
    system_knowledge_root: Path = DEFAULT_SYSTEM_KNOWLEDGE_ROOT,
    read_model_path: Path = DEFAULT_READ_MODEL_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    payload = build_lm2_spine_read_model(generated_at=generated_at)
    repo_b = repo_b_legacy_disposition()
    system_knowledge_root.mkdir(parents=True, exist_ok=True)
    read_model_path.parent.mkdir(parents=True, exist_ok=True)
    spine_json = system_knowledge_root / SPINE_JSON_NAME
    spine_md = system_knowledge_root / SPINE_MD_NAME
    repo_b_json = system_knowledge_root / REPO_B_JSON_NAME
    repo_b_md = system_knowledge_root / REPO_B_MD_NAME
    spine_json.write_text(stable_json(payload), encoding="utf-8")
    spine_md.write_text(render_lm2_spine_markdown(payload), encoding="utf-8")
    repo_b_json.write_text(stable_json(repo_b), encoding="utf-8")
    repo_b_md.write_text(render_repo_b_markdown(repo_b), encoding="utf-8")
    read_model_path.write_text(stable_json(payload), encoding="utf-8")
    return {
        "status": STATUS_READY,
        "spine_json_path": spine_json.as_posix(),
        "spine_markdown_path": spine_md.as_posix(),
        "repo_b_json_path": repo_b_json.as_posix(),
        "repo_b_markdown_path": repo_b_md.as_posix(),
        "read_model_path": read_model_path.as_posix(),
    }


if __name__ == "__main__":
    print(stable_json(export_lm2_canonical_worker_spine()), end="")
