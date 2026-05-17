"""Post-preflight batch gate v0.

This module evaluates future post-preflight lane proposals as structured,
deterministic gate objects. It is planning/read-model substrate only: no module
extraction, repo generation, runtime activation, external sends, deployment, or
Mission Control changes are authorized here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "post_preflight_batch_gate_v0"
READ_MODEL_VERSION = "post_preflight_batch_gate_read_model_v0"
JSON_EXPORT_NAME = "post_preflight_batch_gate.json"
OPERATOR_EXPORT_NAME = "post_preflight_batch_gate_OPERATOR.md"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

PASS = "pass"
FAIL = "fail"

ACCEPTED_ARTIFACT_KINDS = {
    "read_model",
    "operator_packet",
    "mission_control_surface",
    "test_proof",
    "workflow_packet",
    "review_packet",
    "receipt",
}

VAGUE_BOTTLENECKS = {
    "modularity",
    "abstract prep",
    "architecture cleanup",
    "general cleanup",
    "briar patch",
    "modules",
    "planning",
    "prep",
}

RISKY_AUTHORITY_TYPES = {
    "approval",
    "customer_deployment",
    "deployment",
    "model_execution",
    "portal_submit",
    "runtime",
    "send",
    "tool_execution",
}

NO_AUTHORITY_FLAGS = {
    "module_extraction_added": False,
    "client_repo_generation_added": False,
    "runtime_authority_added": False,
    "tool_execution_authority_added": False,
    "model_execution_authority_added": False,
    "send_or_submit_authority_added": False,
    "customer_deployment_authority_added": False,
    "mission_control_app_changed": False,
    "repo_b_execution_allowed": False,
}

REQUIRED_GATE_FIELDS = (
    "lane_name",
    "lane_summary",
    "named_operator_workflow",
    "shared_bottleneck",
    "steel_thread_contract_link",
    "reusable_substrate_improvement",
    "workflow_proof_output",
    "detangling_scope",
    "module_split_disposition",
    "authority_change_requested",
    "authority_gate_required",
    "expected_artifacts",
    "validation_required",
    "gate_status",
    "failure_reasons",
    "recommendation",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _norm(value: object) -> str:
    return str(value or "").strip()


def _slug(value: object) -> str:
    return _norm(value).lower().replace("_", " ").strip()


def _is_truthy_text(value: object) -> bool:
    return bool(_norm(value))


def _artifact_kinds(expected_artifacts: list[dict[str, Any]]) -> set[str]:
    return {
        _slug(item.get("artifact_kind")).replace(" ", "_")
        for item in expected_artifacts
        if isinstance(item, dict)
    }


def _module_split_disposition_ok(disposition: dict[str, Any]) -> bool:
    mode = _slug(disposition.get("disposition")).replace(" ", "_")
    if mode in {"none", "not_needed", "record_future_work", "opportunistic_detangling"}:
        return True
    return False


def evaluate_post_preflight_lane(
    *,
    lane_name: str,
    lane_summary: str,
    named_operator_workflow: str,
    shared_bottleneck: str,
    steel_thread_contract_link: str,
    reusable_substrate_improvement: str,
    workflow_proof_output: str,
    detangling_scope: dict[str, Any],
    module_split_disposition: dict[str, Any],
    authority_change_requested: dict[str, Any] | None = None,
    authority_gate_required: bool = False,
    expected_artifacts: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
    validation_required: list[str] | tuple[str, ...] = (),
    synthetic_example: bool = True,
) -> dict[str, Any]:
    authority_change = authority_change_requested or {
        "requested": False,
        "authority_types": [],
        "reason": "no authority change requested",
    }
    artifacts = list(expected_artifacts)
    validation = list(validation_required)
    failure_reasons: list[str] = []

    if not _is_truthy_text(lane_name):
        failure_reasons.append("missing_lane_name")
    if not _is_truthy_text(lane_summary):
        failure_reasons.append("missing_lane_summary")
    if not _is_truthy_text(named_operator_workflow):
        failure_reasons.append("missing_named_operator_workflow")
    if not _is_truthy_text(shared_bottleneck):
        failure_reasons.append("missing_shared_bottleneck")
    elif _slug(shared_bottleneck) in VAGUE_BOTTLENECKS:
        failure_reasons.append("shared_bottleneck_is_vague_theme")
    if not _is_truthy_text(steel_thread_contract_link):
        failure_reasons.append("missing_steel_thread_contract_link")
    if not _is_truthy_text(reusable_substrate_improvement):
        failure_reasons.append("missing_reusable_substrate_improvement")
    if not _is_truthy_text(workflow_proof_output):
        failure_reasons.append("missing_workflow_proof_output")
    if not artifacts:
        failure_reasons.append("missing_expected_artifacts")
    elif not (_artifact_kinds(artifacts) & ACCEPTED_ARTIFACT_KINDS):
        failure_reasons.append("expected_artifacts_do_not_include_accepted_output")
    if not validation:
        failure_reasons.append("missing_validation_required")

    if detangling_scope.get("physical_module_extraction_requested") is True:
        failure_reasons.append("physical_module_extraction_requested")
    if detangling_scope.get("client_repo_generation_requested") is True:
        failure_reasons.append("client_repo_generation_requested")
    if detangling_scope.get("detangling_required_before_workflow_proof") is True:
        failure_reasons.append("detangling_became_mandatory_prep_detour")
    if not _module_split_disposition_ok(module_split_disposition):
        failure_reasons.append("module_split_disposition_not_supported")

    requested_authority_types = {
        _slug(item).replace(" ", "_")
        for item in authority_change.get("authority_types", [])
    }
    risky_authority_requested = bool(authority_change.get("requested")) or bool(
        requested_authority_types & RISKY_AUTHORITY_TYPES
    )
    if risky_authority_requested and not authority_gate_required:
        failure_reasons.append("ungated_authority_expansion_requested")

    gate_status = PASS if not failure_reasons else FAIL
    return {
        "gate_object_id": _row_id("postpreflightgate", lane_name, named_operator_workflow, shared_bottleneck),
        "lane_name": lane_name,
        "lane_summary": lane_summary,
        "named_operator_workflow": named_operator_workflow,
        "shared_bottleneck": shared_bottleneck,
        "steel_thread_contract_link": steel_thread_contract_link,
        "reusable_substrate_improvement": reusable_substrate_improvement,
        "workflow_proof_output": workflow_proof_output,
        "detangling_scope": {
            "serves_lane_directly": bool(detangling_scope.get("serves_lane_directly")),
            "opportunistic_only": bool(detangling_scope.get("opportunistic_only", True)),
            "physical_module_extraction_requested": bool(
                detangling_scope.get("physical_module_extraction_requested")
            ),
            "client_repo_generation_requested": bool(
                detangling_scope.get("client_repo_generation_requested")
            ),
            "detangling_required_before_workflow_proof": bool(
                detangling_scope.get("detangling_required_before_workflow_proof")
            ),
            "notes": _norm(detangling_scope.get("notes")),
        },
        "module_split_disposition": module_split_disposition,
        "authority_change_requested": authority_change,
        "authority_gate_required": bool(authority_gate_required),
        "expected_artifacts": artifacts,
        "validation_required": validation,
        "gate_status": gate_status,
        "failure_reasons": tuple(failure_reasons),
        "recommendation": _recommendation(gate_status, failure_reasons, module_split_disposition),
        "synthetic_example": synthetic_example,
        "briar_patch_operator_language_only": True,
        "abstract_prep_allowed_without_workflow": False,
        "batch_by_shared_bottleneck": True,
        "one_batch_reusable_substrate_plus_workflow_proof": True,
        **NO_AUTHORITY_FLAGS,
    }


def _recommendation(gate_status: str, failure_reasons: list[str], module_split_disposition: dict[str, Any]) -> str:
    if gate_status == PASS:
        if _slug(module_split_disposition.get("disposition")).replace(" ", "_") == "record_future_work":
            return "proceed_with_lane_and_record_module_split_for_future_work"
        return "proceed_with_bounded_post_preflight_lane"
    if "ungated_authority_expansion_requested" in failure_reasons:
        return "stop_and_create_explicit_authority_gate_lane"
    if "missing_named_operator_workflow" in failure_reasons:
        return "stop_until_lane_names_real_operator_workflow"
    if "detangling_became_mandatory_prep_detour" in failure_reasons:
        return "shrink_to_workflow_proof_and_record_split_future_work"
    return "revise_lane_until_gate_passes"


def synthetic_gate_examples() -> tuple[dict[str, Any], ...]:
    return (
        evaluate_post_preflight_lane(
            lane_name="Generic Review Packet Reuse for Capital Hilton Followup",
            lane_summary="Reuse the generic review packet proof schema for a real Capital Hilton followup packet.",
            named_operator_workflow="Capital Hilton manual invoice review",
            shared_bottleneck="review_packet_schema_reuse",
            steel_thread_contract_link="cassandra_governed_review_packet_request_proof_v1",
            reusable_substrate_improvement="Generic review packet parser/read-model contract stays workflow-neutral.",
            workflow_proof_output="Capital Hilton followup review packet generated from governed facts.",
            detangling_scope={
                "serves_lane_directly": True,
                "opportunistic_only": True,
                "physical_module_extraction_requested": False,
                "client_repo_generation_requested": False,
                "detangling_required_before_workflow_proof": False,
                "notes": "Keep workflow-specific values inside generic packet fields.",
            },
            module_split_disposition={
                "disposition": "none",
                "recorded_future_work": False,
                "reason": "No physical split needed for this prompt.",
            },
            authority_change_requested={
                "requested": False,
                "authority_types": [],
                "reason": "Review-only packet refresh.",
            },
            expected_artifacts=[
                {
                    "artifact_kind": "review_packet",
                    "path_or_contract": "generated/read_models/capital_hilton_actionable_review_packet.json",
                },
                {
                    "artifact_kind": "test_proof",
                    "path_or_contract": "tests/test_cassandra_governed_review_packet_request.py",
                },
            ],
            validation_required=(
                "focused review packet tests",
                "JSON validation",
                "no-send/no-submit flags",
            ),
        ),
        evaluate_post_preflight_lane(
            lane_name="Abstract Module Prep Sprint",
            lane_summary="Prepare modules before deciding which workflow matters.",
            named_operator_workflow="",
            shared_bottleneck="modularity",
            steel_thread_contract_link="",
            reusable_substrate_improvement="General modularity cleanup.",
            workflow_proof_output="",
            detangling_scope={
                "serves_lane_directly": False,
                "opportunistic_only": False,
                "physical_module_extraction_requested": False,
                "client_repo_generation_requested": False,
                "detangling_required_before_workflow_proof": True,
                "notes": "Invalid abstract prep.",
            },
            module_split_disposition={
                "disposition": "record_future_work",
                "recorded_future_work": True,
                "reason": "Still invalid because no workflow proof is named.",
            },
            authority_change_requested={
                "requested": False,
                "authority_types": [],
                "reason": "No authority change requested.",
            },
            expected_artifacts=[],
            validation_required=(),
        ),
        evaluate_post_preflight_lane(
            lane_name="Cassandra Intake to Niles Album Review Packet",
            lane_summary=(
                "Use the receive/intake proof bottleneck to produce a review-only Niles album status packet, "
                "while recording any Cassandra/Niles split as future work."
            ),
            named_operator_workflow="Niles album progress review",
            shared_bottleneck="governed_receive_to_review_packet_projection",
            steel_thread_contract_link="telegram_agent_intake_to_work_packet_contract",
            reusable_substrate_improvement="Reuse governed intake to review packet projection without adding send authority.",
            workflow_proof_output="Niles album review packet or missing-facts packet.",
            detangling_scope={
                "serves_lane_directly": True,
                "opportunistic_only": True,
                "physical_module_extraction_requested": False,
                "client_repo_generation_requested": False,
                "detangling_required_before_workflow_proof": False,
                "notes": "Record Cassandra/Niles boundary pressure but do not extract modules in this lane.",
            },
            module_split_disposition={
                "disposition": "record_future_work",
                "recorded_future_work": True,
                "future_work_id": "niles_album_matrix_boundary_review",
                "reason": "Module split pressure is visible but not needed for this workflow proof.",
            },
            authority_change_requested={
                "requested": False,
                "authority_types": [],
                "reason": "Review-only album packet.",
            },
            expected_artifacts=[
                {
                    "artifact_kind": "operator_packet",
                    "path_or_contract": "generated/read_models/niles_album_review_packet_OPERATOR.md",
                },
                {
                    "artifact_kind": "read_model",
                    "path_or_contract": "generated/read_models/niles_album_review_packet.json",
                },
            ],
            validation_required=("packet tests", "JSON validation", "no runtime/send authority proof"),
        ),
        evaluate_post_preflight_lane(
            lane_name="Ungated Send and Deployment Shortcut",
            lane_summary="Turn on send/deploy authority while refreshing a packet.",
            named_operator_workflow="Capital Hilton invoice review",
            shared_bottleneck="review_packet_to_external_action",
            steel_thread_contract_link="cassandra_governed_review_packet_request_proof_v1",
            reusable_substrate_improvement="Attempt to jump from review packet to external action.",
            workflow_proof_output="Email send and deployment result.",
            detangling_scope={
                "serves_lane_directly": False,
                "opportunistic_only": False,
                "physical_module_extraction_requested": False,
                "client_repo_generation_requested": False,
                "detangling_required_before_workflow_proof": False,
                "notes": "Invalid authority expansion.",
            },
            module_split_disposition={
                "disposition": "not_needed",
                "recorded_future_work": False,
                "reason": "No module split.",
            },
            authority_change_requested={
                "requested": True,
                "authority_types": ["send", "runtime", "customer_deployment"],
                "reason": "Invalid: requests external authority without gate.",
            },
            authority_gate_required=False,
            expected_artifacts=[
                {
                    "artifact_kind": "receipt",
                    "path_or_contract": "external send receipt",
                }
            ],
            validation_required=("none_safe_enough_for_ungated_authority",),
        ),
    )


def build_post_preflight_batch_gate_read_model(*, generated_at: str | None = None) -> dict[str, Any]:
    examples = synthetic_gate_examples()
    status_counts = Counter(item["gate_status"] for item in examples)
    failure_counts = Counter(reason for item in examples for reason in item["failure_reasons"])
    return {
        "schema_version": READ_MODEL_VERSION,
        "contract_schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "purpose": "Evaluate post-preflight lanes before abstract prep, vague modularity work, or unsafe authority expansion.",
        "operator_label": "Briar Patch Batch Gate",
        "briar_patch_operator_language_only": True,
        "required_gate_fields": list(REQUIRED_GATE_FIELDS),
        "gate_questions": [
            "Does this lane unlock or improve a named real operator workflow within one prompt?",
            "Does it reuse or strengthen the steel-thread contract?",
            "Is the batch grouped by a shared bottleneck, not a vague theme?",
            "Does any modular detangling serve the lane directly?",
            "If a module split is discovered but not needed now, is it recorded as future work?",
            "Does the lane avoid new send/submit/runtime/approval authority unless explicitly gated?",
            "Is the expected output a read-model, packet, Mission Control surface, test/proof, or real workflow improvement?",
        ],
        "example_count": len(examples),
        "gate_status_counts": dict(sorted(status_counts.items())),
        "failure_reason_counts": dict(sorted(failure_counts.items())),
        "examples": list(examples),
        "abstract_prep_allowed_without_workflow": False,
        "batch_by_shared_bottleneck": True,
        "one_batch_reusable_substrate_plus_workflow_proof": True,
        "detangling_posture": "opportunistic_now_record_future_splits_without_detour",
        "next_safe_lane": "Run Post-Preflight Gate On Next Lane",
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }


def format_operator_read_model(read_model: dict[str, Any]) -> str:
    lines = [
        "# Briar Patch Batch Gate",
        "",
        "Machine contract: `post_preflight_batch_gate_v0`.",
        "",
        "What this does:",
        "- Checks proposed post-preflight lanes before they drift into abstract prep or vague modularity work.",
        "- Requires one reusable substrate improvement plus one named real operator workflow proof.",
        "- Records module split pressure as future work when extraction is not needed now.",
        "",
        "What this does not do:",
        "- No module extraction, client repo generation, runtime activation, sends, submits, deployment, or approval authority.",
        "",
        "Summary:",
        f"- Examples: {read_model['example_count']}.",
        f"- Status counts: {_count_line(read_model['gate_status_counts'])}.",
        f"- Failure counts: {_count_line(read_model['failure_reason_counts'])}.",
        "",
        "Examples:",
    ]
    for item in read_model["examples"]:
        lines.extend(
            [
                f"- `{item['lane_name']}` -> `{item['gate_status']}`",
                f"  - workflow: `{item['named_operator_workflow'] or 'missing'}`",
                f"  - bottleneck: `{item['shared_bottleneck'] or 'missing'}`",
                f"  - recommendation: `{item['recommendation']}`",
            ]
        )
        if item["failure_reasons"]:
            lines.append(f"  - failures: {', '.join(item['failure_reasons'])}")
    lines.extend(
        [
            "",
            "Boundary:",
            "- `abstract_prep_allowed_without_workflow=false`.",
            "- `module_extraction_added=false`; `client_repo_generation_added=false`.",
            "- `runtime_authority_added=false`; `send_or_submit_authority_added=false`; `customer_deployment_authority_added=false`.",
            "",
            f"Next safe lane: {read_model['next_safe_lane']}",
            "",
        ]
    )
    return "\n".join(lines)


def _count_line(counts: dict[str, int]) -> str:
    return ", ".join(f"{key}={value}" for key, value in counts.items()) or "none"


def export_post_preflight_batch_gate_read_model(
    *,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(__file__).resolve().parent / root
    root.mkdir(parents=True, exist_ok=True)
    read_model = build_post_preflight_batch_gate_read_model(generated_at=generated_at)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(read_model), encoding="utf-8")
    operator_path.write_text(format_operator_read_model(read_model), encoding="utf-8")
    return {
        "export_version": READ_MODEL_VERSION,
        "json_path": json_path.as_posix(),
        "operator_path": operator_path.as_posix(),
        "example_count": read_model["example_count"],
        **NO_AUTHORITY_FLAGS,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export post-preflight batch gate read-model.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--format", choices=("json", "operator", "summary"), default="summary")
    args = parser.parse_args(argv)
    summary = export_post_preflight_batch_gate_read_model(export_root=args.export_root)
    if args.format == "json":
        print(Path(summary["json_path"]).read_text(encoding="utf-8"), end="")
    elif args.format == "operator":
        print(Path(summary["operator_path"]).read_text(encoding="utf-8"), end="")
    else:
        print(stable_json(summary), end="")
    return 0


__all__ = [
    "ACCEPTED_ARTIFACT_KINDS",
    "FAIL",
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "PASS",
    "READ_MODEL_VERSION",
    "REQUIRED_GATE_FIELDS",
    "SCHEMA_VERSION",
    "build_post_preflight_batch_gate_read_model",
    "evaluate_post_preflight_lane",
    "export_post_preflight_batch_gate_read_model",
    "format_operator_read_model",
    "stable_json",
    "synthetic_gate_examples",
]


if __name__ == "__main__":
    raise SystemExit(main())
