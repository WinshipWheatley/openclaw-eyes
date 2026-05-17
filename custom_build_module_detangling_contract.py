"""Custom build module-detangling contract v0.

This module defines deterministic planning records for future custom-build
lanes. It does not generate client repositories, extract code, deploy systems,
run agents, or grant runtime/send/customer authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "custom_build_module_detangling_contract_v0"
READ_MODEL_VERSION = "custom_build_module_detangling_contract_read_model_v0"
JSON_EXPORT_NAME = "custom_build_module_detangling_contract.json"
OPERATOR_EXPORT_NAME = "custom_build_module_detangling_contract_OPERATOR.md"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

NO_AUTHORITY_FLAGS = {
    "physical_module_extraction_added": False,
    "client_repo_generation_added": False,
    "repo_b_execution_allowed": False,
    "private_data_copy_allowed": False,
    "customer_deployment_authority": False,
    "runtime_authority": False,
    "tool_execution_authority": False,
    "model_execution_authority": False,
    "send_or_submit_authority": False,
    "openclaw_core_replacement_automatic": False,
}

REQUIRED_ASSESSMENT_FIELDS = (
    "assessment_id",
    "requested_custom_build",
    "use_case_summary",
    "capability_needed",
    "current_source_module_locations",
    "current_tangle_dependencies",
    "minimum_viable_extracted_module",
    "possible_module_variants",
    "private_data_risk",
    "authority_risk",
    "runtime_dependency_risk",
    "client_suitability",
    "openclaw_core_replacement_potential",
    "migration_recommendation",
    "validation_required_before_adoption",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _assessment(
    *,
    requested_custom_build: str,
    use_case_summary: str,
    capability_needed: tuple[str, ...],
    current_source_module_locations: tuple[dict[str, Any], ...],
    current_tangle_dependencies: tuple[dict[str, Any], ...],
    minimum_viable_extracted_module: dict[str, Any],
    possible_module_variants: tuple[dict[str, Any], ...],
    private_data_risk: str,
    authority_risk: str,
    runtime_dependency_risk: str,
    client_suitability: dict[str, Any],
    openclaw_core_replacement_potential: dict[str, Any],
    migration_recommendation: dict[str, Any],
    validation_required_before_adoption: tuple[str, ...],
) -> dict[str, Any]:
    normalized = requested_custom_build.strip().lower()
    payload = {
        "assessment_id": _row_id("moddetangle", normalized),
        "requested_custom_build": requested_custom_build,
        "use_case_summary": use_case_summary,
        "capability_needed": list(capability_needed),
        "current_source_module_locations": list(current_source_module_locations),
        "current_tangle_dependencies": list(current_tangle_dependencies),
        "minimum_viable_extracted_module": minimum_viable_extracted_module,
        "possible_module_variants": list(possible_module_variants),
        "private_data_risk": private_data_risk,
        "authority_risk": authority_risk,
        "runtime_dependency_risk": runtime_dependency_risk,
        "client_suitability": client_suitability,
        "openclaw_core_replacement_potential": openclaw_core_replacement_potential,
        "migration_recommendation": migration_recommendation,
        "validation_required_before_adoption": list(validation_required_before_adoption),
        "synthetic_example": True,
        "real_client_data_used": False,
        "private_data_copied": False,
        "client_suitability_granted_by_default": False,
        "core_replacement_automatic": False,
        **NO_AUTHORITY_FLAGS,
    }
    _validate_assessment(payload)
    return payload


def _validate_assessment(payload: dict[str, Any]) -> None:
    missing = [field for field in REQUIRED_ASSESSMENT_FIELDS if field not in payload]
    if missing:
        raise ValueError(f"detangling assessment missing fields: {', '.join(missing)}")
    if payload["client_suitability"].get("client_safe_by_default") is not False:
        raise ValueError("client suitability must not be granted by default")
    if payload["openclaw_core_replacement_potential"].get("automatic_replacement") is not False:
        raise ValueError("OpenClaw Core replacement must not be automatic")
    for key, expected in NO_AUTHORITY_FLAGS.items():
        if payload.get(key) is not expected:
            raise ValueError(f"authority flag changed: {key}")


def sample_assessments() -> tuple[dict[str, Any], ...]:
    return (
        _assessment(
            requested_custom_build="Synthetic Cassandra-only helper",
            use_case_summary=(
                "A friend/client build wants Cassandra-style receive-only fact intake and review "
                "packet drafting without Chief routing, Guardian approval, sends, or autonomous loops."
            ),
            capability_needed=(
                "receive_only_operator_fact_intake",
                "bounded_context_hashing",
                "review_only_packet_generation",
            ),
            current_source_module_locations=(
                {
                    "location": "cassandra_listener.py",
                    "role": "legacy/live Cassandra Telegram receive path",
                    "current_posture": "Repo A governed receive wiring exists; sends/replies blocked",
                },
                {
                    "location": "telegram_agent_intake.py",
                    "role": "governed Telegram intake metadata substrate",
                    "current_posture": "canonical receive metadata path",
                },
                {
                    "location": "cassandra_clara_fact_packet.py",
                    "role": "review-only fact packet builder",
                    "current_posture": "governed packet surface",
                },
            ),
            current_tangle_dependencies=(
                {
                    "dependency": "chief_control_plane",
                    "risk": "medium",
                    "reason": "Cassandra historically routes through Chief/session concepts.",
                    "required_for_minimum_module": False,
                },
                {
                    "dependency": "guardian_hitl_gate",
                    "risk": "high",
                    "reason": "Any action-capable proposal must remain approval-gated.",
                    "required_for_minimum_module": False,
                },
                {
                    "dependency": "watcher_scheduler_loop",
                    "risk": "high",
                    "reason": "Send-capable loop machinery is not needed for receive-only helper.",
                    "required_for_minimum_module": False,
                },
            ),
            minimum_viable_extracted_module={
                "module_id": "cassandra_clara_fact_intake",
                "module_shape": "standalone_smaller_module",
                "included_surfaces": (
                    "governed receive metadata",
                    "bounded hash/excerpt policy",
                    "review-only packet output",
                ),
                "excluded_surfaces": (
                    "Chief session/router state",
                    "Guardian action approval",
                    "Telegram/Gmail sends",
                    "watcher/scheduler loops",
                ),
            },
            possible_module_variants=(
                {
                    "variant_id": "cassandra_receive_only",
                    "variant_shape": "standalone_smaller_module",
                    "recommended_for_first_slice": True,
                },
                {
                    "variant_id": "cassandra_plus_guardian",
                    "variant_shape": "gated_module",
                    "recommended_for_first_slice": False,
                },
            ),
            private_data_risk="medium_requires_metadata_only_inputs",
            authority_risk="high_if_send_or_action_paths_are_copied",
            runtime_dependency_risk="medium_legacy_listener_identity_and_loop_risk",
            client_suitability={
                "client_safe_by_default": False,
                "suitability": "candidate_after_synthetic_tests",
                "reason": "Need tenant config, no-send proof, and no private Telegram/body storage proof.",
            },
            openclaw_core_replacement_potential={
                "automatic_replacement": False,
                "potential": "candidate_after_equivalence_proof",
                "reason": "A cleaner receive-only module could replace legacy Cassandra receive tangle later.",
            },
            migration_recommendation={
                "recommendation": "plan_standalone_receive_only_module_first",
                "core_action_now": "contract_only_no_extraction",
            },
            validation_required_before_adoption=(
                "synthetic receive fixture proof",
                "no raw body storage proof",
                "no send/reply authority proof",
                "tenant config boundary proof",
            ),
        ),
        _assessment(
            requested_custom_build="Synthetic Cassandra plus Chief planning helper",
            use_case_summary=(
                "A company/internal build wants Cassandra-style intake plus Chief-style deterministic "
                "planning, but not autonomous runtime loops or external sends."
            ),
            capability_needed=(
                "receive_only_fact_intake",
                "deterministic_intent_routing",
                "work_board_projection",
                "review_packet_planning",
            ),
            current_source_module_locations=(
                {
                    "location": "cassandra_listener.py",
                    "role": "Cassandra receive surface",
                    "current_posture": "legacy-adjacent but governed receive path exists",
                },
                {
                    "location": "intent_router.py",
                    "role": "deterministic intent routing",
                    "current_posture": "Repo A governed route planner",
                },
                {
                    "location": "work_board.py / agent_work_packet.py",
                    "role": "governed work packet projection",
                    "current_posture": "planning/work substrate",
                },
            ),
            current_tangle_dependencies=(
                {
                    "dependency": "chief_control_plane",
                    "risk": "medium",
                    "reason": "Chief routing is useful but must stay deterministic and no-send.",
                    "required_for_minimum_module": True,
                },
                {
                    "dependency": "agent_runtime_stack",
                    "risk": "high",
                    "reason": "Autonomous loop/runtime execution must not be copied into planning helper.",
                    "required_for_minimum_module": False,
                },
                {
                    "dependency": "memory_authority_substrate",
                    "risk": "medium",
                    "reason": "Facts may be read as parsed evidence, not truth.",
                    "required_for_minimum_module": True,
                },
            ),
            minimum_viable_extracted_module={
                "module_id": "cassandra_chief_planning_pair",
                "module_shape": "paired_module",
                "included_surfaces": (
                    "Cassandra receive metadata",
                    "Chief deterministic route selection",
                    "Work Board / Agent Work Packet planning output",
                ),
                "excluded_surfaces": (
                    "autonomous runtime execution",
                    "sender paths",
                    "legacy JSON approval authority",
                    "Repo B runtime code",
                ),
            },
            possible_module_variants=(
                {
                    "variant_id": "cassandra_chief_no_loop",
                    "variant_shape": "paired_module",
                    "recommended_for_first_slice": True,
                },
                {
                    "variant_id": "cassandra_chief_guardian_actionable",
                    "variant_shape": "gated_module",
                    "recommended_for_first_slice": False,
                },
            ),
            private_data_risk="medium_requires_sanitized_operator_prompts",
            authority_risk="high_if_work_packets_become_execution_authority",
            runtime_dependency_risk="high_if_old_loop_or_service_paths_are_copied",
            client_suitability={
                "client_safe_by_default": False,
                "suitability": "candidate_only_after_no_runtime_proof",
                "reason": "Planning output must remain advisory until HITL/action boundaries are proven.",
            },
            openclaw_core_replacement_potential={
                "automatic_replacement": False,
                "potential": "strong_candidate_after_work_packet_equivalence",
                "reason": "A clean Cassandra+Chief pair could reduce core tangle if it preserves route behavior.",
            },
            migration_recommendation={
                "recommendation": "define_paired_module_contract_then_synthetic_work_packet_proof",
                "core_action_now": "contract_only_no_caller_switch",
            },
            validation_required_before_adoption=(
                "no runtime execution proof",
                "work packet remains proposal/read-model only",
                "old HITL authority not copied",
                "module interface contract review",
            ),
        ),
        _assessment(
            requested_custom_build="Synthetic Report Bridge client status helper",
            use_case_summary=(
                "A client build wants sanitized status/proof summaries back to OpenClaw Core without "
                "exporting private client files or raw bodies."
            ),
            capability_needed=(
                "sanitized_status_import",
                "proof_summary_visibility",
                "client_private_data_exclusion",
            ),
            current_source_module_locations=(
                {
                    "location": "report_bridge.py",
                    "role": "sanitized report package validator/importer",
                    "current_posture": "rejects raw bodies and client data by default",
                },
                {
                    "location": "project_capsule.py",
                    "role": "project/client planning metadata",
                    "current_posture": "synthetic/client metadata only",
                },
                {
                    "location": "module_registry.py",
                    "role": "approved module posture registry",
                    "current_posture": "planning metadata only",
                },
            ),
            current_tangle_dependencies=(
                {
                    "dependency": "project_capsule_bundle_blueprint",
                    "risk": "low",
                    "reason": "Planning metadata dependency only.",
                    "required_for_minimum_module": False,
                },
                {
                    "dependency": "client_private_data_sources",
                    "risk": "high",
                    "reason": "Must never cross into Core except sanitized proof/status.",
                    "required_for_minimum_module": False,
                },
            ),
            minimum_viable_extracted_module={
                "module_id": "report_bridge_sanitized_summary",
                "module_shape": "client_only_extracted_module",
                "included_surfaces": (
                    "manifest validation",
                    "safe file metadata",
                    "status/proof/blocker summary fields",
                ),
                "excluded_surfaces": (
                    "raw client bodies",
                    "credentials/tokens",
                    "customer deployment",
                    "runtime service control",
                ),
            },
            possible_module_variants=(
                {
                    "variant_id": "report_bridge_client_status_only",
                    "variant_shape": "client_only_extracted_module",
                    "recommended_for_first_slice": True,
                },
                {
                    "variant_id": "report_bridge_plus_project_capsule",
                    "variant_shape": "paired_module",
                    "recommended_for_first_slice": False,
                },
            ),
            private_data_risk="high_but_blocked_by_contract",
            authority_risk="medium_if_status_is_misread_as_truth_or_execution",
            runtime_dependency_risk="low_metadata_only",
            client_suitability={
                "client_safe_by_default": False,
                "suitability": "candidate_after_package_fixture_tests",
                "reason": "The bridge is designed for clients but still needs per-client no-private-data proof.",
            },
            openclaw_core_replacement_potential={
                "automatic_replacement": False,
                "potential": "low_replacement_high_reuse",
                "reason": "Likely a reusable boundary module, not a replacement for core control plane.",
            },
            migration_recommendation={
                "recommendation": "keep_as_reusable_sanitized_bridge_contract",
                "core_action_now": "read_model_visibility_only",
            },
            validation_required_before_adoption=(
                "fixture package with no raw body data",
                "manifest no-go rejection proof",
                "Mission Control read-only visibility proof",
            ),
        ),
    )


def build_custom_build_module_detangling_read_model(*, generated_at: str | None = None) -> dict[str, Any]:
    assessments = sample_assessments()
    shape_counts = Counter(
        variant["variant_shape"]
        for assessment in assessments
        for variant in assessment["possible_module_variants"]
    )
    recommended_counts = Counter(
        assessment["migration_recommendation"]["recommendation"]
        for assessment in assessments
    )
    return {
        "schema_version": READ_MODEL_VERSION,
        "contract_schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "purpose": "Custom builds must pressure-test and reduce OpenClaw module tangles.",
        "doctrine": {
            "custom_builds_pay_down_modular_debt": True,
            "copying_tangles_by_default_allowed": False,
            "module_needs_are_detangling_pressure_tests": True,
            "openclaw_core_replacement_requires_explicit_proof": True,
        },
        "assessment_count": len(assessments),
        "variant_shape_counts": dict(sorted(shape_counts.items())),
        "migration_recommendation_counts": dict(sorted(recommended_counts.items())),
        "assessments": list(assessments),
        "future_lane_must_collect": list(REQUIRED_ASSESSMENT_FIELDS),
        "next_safe_lane": "Custom Build Module Detangling Intake Gate",
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }


def format_operator_read_model(read_model: dict[str, Any]) -> str:
    lines = [
        "# Custom Build Module Detangling Contract v0",
        "",
        "What this is:",
        "- A deterministic planning contract for future friend/client/company custom-build lanes.",
        "- It forces each custom build to ask whether a needed OpenClaw capability should be split, paired, gated, client-only, or later used to replace a tangled Core section.",
        "",
        "What this is not:",
        "- It is not client repo generation, deployment, runtime activation, physical module extraction, send authority, or automatic OpenClaw Core replacement.",
        "",
        "Summary:",
        f"- Synthetic assessments: {read_model['assessment_count']}.",
        f"- Variant shapes: {_count_line(read_model['variant_shape_counts'])}.",
        "",
        "Synthetic cases:",
    ]
    for assessment in read_model["assessments"]:
        module = assessment["minimum_viable_extracted_module"]
        recommendation = assessment["migration_recommendation"]
        lines.extend(
            [
                f"- `{assessment['assessment_id']}`: {assessment['requested_custom_build']}",
                f"  - minimum module: `{module['module_id']}` ({module['module_shape']})",
                f"  - recommendation: `{recommendation['recommendation']}`",
                f"  - client safe by default: `{str(assessment['client_suitability']['client_safe_by_default']).lower()}`",
                f"  - core replacement automatic: `{str(assessment['openclaw_core_replacement_potential']['automatic_replacement']).lower()}`",
            ]
        )
    lines.extend(
        [
            "",
            "Boundary:",
            "- `physical_module_extraction_added=false`.",
            "- `client_repo_generation_added=false`.",
            "- `runtime_authority=false`; `send_or_submit_authority=false`; `customer_deployment_authority=false`.",
            "- All examples are synthetic; no real client data is used or copied.",
            "",
            f"Next safe lane: {read_model['next_safe_lane']}",
            "",
        ]
    )
    return "\n".join(lines)


def _count_line(counts: dict[str, int]) -> str:
    return ", ".join(f"{key}={value}" for key, value in counts.items()) or "none"


def export_custom_build_module_detangling_read_model(
    *,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(__file__).resolve().parent / root
    root.mkdir(parents=True, exist_ok=True)
    read_model = build_custom_build_module_detangling_read_model(generated_at=generated_at)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(read_model), encoding="utf-8")
    operator_path.write_text(format_operator_read_model(read_model), encoding="utf-8")
    return {
        "export_version": READ_MODEL_VERSION,
        "json_path": json_path.as_posix(),
        "operator_path": operator_path.as_posix(),
        "assessment_count": read_model["assessment_count"],
        **NO_AUTHORITY_FLAGS,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export custom build module-detangling read-model.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--format", choices=("json", "operator", "summary"), default="summary")
    args = parser.parse_args(argv)
    summary = export_custom_build_module_detangling_read_model(export_root=args.export_root)
    if args.format == "json":
        payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))
        print(stable_json(payload), end="")
    elif args.format == "operator":
        print(Path(summary["operator_path"]).read_text(encoding="utf-8"), end="")
    else:
        print(stable_json(summary), end="")
    return 0


__all__ = [
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "READ_MODEL_VERSION",
    "REQUIRED_ASSESSMENT_FIELDS",
    "SCHEMA_VERSION",
    "build_custom_build_module_detangling_read_model",
    "export_custom_build_module_detangling_read_model",
    "format_operator_read_model",
    "sample_assessments",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
