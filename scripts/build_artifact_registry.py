#!/usr/bin/env python3
"""Build a deterministic metadata-only registry of read-model artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
READ_MODEL_VERSION = "artifact_registry_v0"
MODE = "metadata_only_artifact_registry"

COMMON_CLAIMS_NOT_MADE = [
    "runtime_activation_authority",
    "backend_execution",
    "agent_activation",
    "active_agent_presence",
    "dynamic_world_state",
    "strategic_gravity_scoring",
    "live_health_claim",
    "process_liveness",
    "broker_connection",
    "networking",
    "external_tool_call",
    "customer_deployment",
    "sqlite_body_storage",
    "sqlite_write",
    "broad_file_scan",
    "hard_drive_scan",
    "private_data_access",
    "full_body_ingest",
]

EXPECTED_CORE_ARTIFACT_IDS = {
    "generated_current_state",
    "generated_next_actions",
    "source_inventory_output_contract",
    "helm_state_output_contract",
    "world_domain_registry_output_contract",
    "runtime_activation_gate_output_contract",
    "promotion_gate_output_contract",
    "safe_extraction_output_contract",
    "source_cards_output_contract",
    "working_context_packets_output_contract",
    "context_packet_retrieval_output_contract",
}

EXPECTED_GENERATED_STATUS_SECTION_IDS = {
    "generated_status_source_inventory_section",
    "generated_status_context_gates_section",
    "generated_status_helm_state_section",
    "generated_status_world_domain_registry_section",
}

READ_MODEL_OUTPUT_DIR = "generated/read_models"


def _tags(*items: str) -> list[str]:
    base = {
        "metadata_only",
        "read_model",
        "no_runtime_authority",
        "evidence",
        "boundary",
        "blocked",
        "next_safe_move",
    }
    return sorted(base | set(items))


ARTIFACT_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "artifact_id": "generated_current_state",
        "label": "Generated Current State",
        "artifact_type": "generated_status_markdown",
        "path_or_command": "Operator/GENERATED_CURRENT_STATE.md",
        "producer_script": "scripts/generate_operator_status.py",
        "producer_command": "python3 scripts/generate_operator_status.py --write",
        "expected_format": "markdown",
        "tags": _tags("generated_status", "operator_status", "app_fixture_safe", "codex_context_safe"),
        "authority_label": "read_model_status_only",
        "generated_on_demand": False,
        "current_status_source": "python3 scripts/generate_operator_status.py --check",
        "safe_for_mac_app": True,
        "safe_for_codex_context": True,
        "safe_for_nohup_workers": True,
        "safe_for_agent_context": True,
        "freshness_basis": "current when generate_operator_status.py --check passes",
        "verification_command": "python3 scripts/generate_operator_status.py --check",
    },
    {
        "artifact_id": "generated_next_actions",
        "label": "Generated Next Actions",
        "artifact_type": "generated_status_markdown",
        "path_or_command": "Operator/GENERATED_NEXT_ACTIONS.md",
        "producer_script": "scripts/generate_operator_status.py",
        "producer_command": "python3 scripts/generate_operator_status.py --write",
        "expected_format": "markdown",
        "tags": _tags("generated_status", "next_actions", "app_fixture_safe", "codex_context_safe"),
        "authority_label": "read_model_status_only",
        "generated_on_demand": False,
        "current_status_source": "python3 scripts/generate_operator_status.py --check",
        "safe_for_mac_app": True,
        "safe_for_codex_context": True,
        "safe_for_nohup_workers": True,
        "safe_for_agent_context": True,
        "freshness_basis": "current when generate_operator_status.py --check passes",
        "verification_command": "python3 scripts/generate_operator_status.py --check",
    },
    {
        "artifact_id": "source_inventory_output_contract",
        "label": "Source Inventory Output Contract",
        "artifact_type": "producer_output_contract",
        "path_or_command": "python3 scripts/build_source_inventory.py --format json",
        "producer_script": "scripts/build_source_inventory.py",
        "producer_command": "python3 scripts/build_source_inventory.py --format json",
        "expected_format": "json",
        "tags": _tags("source_inventory", "app_fixture_safe", "codex_context_safe"),
        "authority_label": "metadata_inventory_only",
        "generated_on_demand": True,
        "current_status_source": "producer_command",
        "safe_for_mac_app": True,
        "safe_for_codex_context": True,
        "safe_for_nohup_workers": True,
        "safe_for_agent_context": True,
        "freshness_basis": "generated on demand from explicit Source Inventory allowlist",
        "verification_command": "python3 scripts/build_source_inventory.py --format json | python3 -m json.tool",
    },
    {
        "artifact_id": "helm_state_output_contract",
        "label": "Helm State Output Contract",
        "artifact_type": "producer_output_contract",
        "path_or_command": "python3 scripts/build_helm_state.py --format json",
        "producer_script": "scripts/build_helm_state.py",
        "producer_command": "python3 scripts/build_helm_state.py --format json",
        "expected_format": "json",
        "tags": _tags("helm_state", "app_fixture_safe", "codex_context_safe"),
        "authority_label": "inspect_only_read_model",
        "generated_on_demand": True,
        "current_status_source": "generated_status_check_and_activation_gate",
        "safe_for_mac_app": True,
        "safe_for_codex_context": True,
        "safe_for_nohup_workers": True,
        "safe_for_agent_context": True,
        "freshness_basis": "generated status check, source inventory, context gates, and activation gate",
        "verification_command": "python3 scripts/build_helm_state.py --format json | python3 -m json.tool",
    },
    {
        "artifact_id": "world_domain_registry_output_contract",
        "label": "World / Domain Registry Output Contract",
        "artifact_type": "producer_output_contract",
        "path_or_command": "python3 scripts/build_world_domain_registry.py --format json",
        "producer_script": "scripts/build_world_domain_registry.py",
        "producer_command": "python3 scripts/build_world_domain_registry.py --format json",
        "expected_format": "json",
        "tags": _tags("world_registry", "app_fixture_safe", "codex_context_safe"),
        "authority_label": "registry_only_read_model",
        "generated_on_demand": True,
        "current_status_source": "static_registry_definitions",
        "safe_for_mac_app": True,
        "safe_for_codex_context": True,
        "safe_for_nohup_workers": True,
        "safe_for_agent_context": True,
        "freshness_basis": "generated on demand from explicit static world/domain registry",
        "verification_command": "python3 scripts/build_world_domain_registry.py --format json | python3 -m json.tool",
    },
    {
        "artifact_id": "runtime_activation_gate_output_contract",
        "label": "Runtime / Module Activation Gate Output Contract",
        "artifact_type": "producer_output_contract",
        "path_or_command": "python3 scripts/check_runtime_activation_gate.py --format json",
        "producer_script": "scripts/check_runtime_activation_gate.py",
        "producer_command": "python3 scripts/check_runtime_activation_gate.py --format json",
        "expected_format": "json",
        "tags": _tags("activation_gate", "context_gate", "codex_context_safe", "nohup_context_safe"),
        "authority_label": "blocked_readiness_contract",
        "generated_on_demand": True,
        "current_status_source": "producer_command",
        "safe_for_mac_app": True,
        "safe_for_codex_context": True,
        "safe_for_nohup_workers": True,
        "safe_for_agent_context": True,
        "freshness_basis": "v0 always blocks activation and names missing prerequisites",
        "verification_command": "python3 scripts/check_runtime_activation_gate.py --format json | python3 -m json.tool",
    },
    {
        "artifact_id": "promotion_gate_output_contract",
        "label": "Accepted Context Promotion Gate Output Contract",
        "artifact_type": "producer_output_contract",
        "path_or_command": "python3 scripts/promote_accepted_context.py --format json --all-allowlisted --reason-for-promotion <reason>",
        "producer_script": "scripts/promote_accepted_context.py",
        "producer_command": "python3 scripts/promote_accepted_context.py --format json --all-allowlisted --reason-for-promotion <reason>",
        "expected_format": "json",
        "tags": _tags("promotion_gate", "context_gate", "codex_context_safe", "nohup_context_safe"),
        "authority_label": "accepted_context_candidate_gate",
        "generated_on_demand": True,
        "current_status_source": "source_inventory_json_and_operator_reason",
        "safe_for_mac_app": False,
        "safe_for_codex_context": True,
        "safe_for_nohup_workers": True,
        "safe_for_agent_context": True,
        "freshness_basis": "fresh when built from current Source Inventory JSON and explicit promotion reason",
        "verification_command": "python3 -m pytest tests/test_accepted_context_promotion.py",
    },
    {
        "artifact_id": "safe_extraction_output_contract",
        "label": "Safe Body Extraction Output Contract",
        "artifact_type": "producer_output_contract",
        "path_or_command": "python3 scripts/extract_accepted_sources.py --promotion-manifest <promotion.json> --format json",
        "producer_script": "scripts/extract_accepted_sources.py",
        "producer_command": "python3 scripts/extract_accepted_sources.py --promotion-manifest <promotion.json> --format json",
        "expected_format": "json",
        "tags": _tags("safe_extraction", "context_gate", "codex_context_safe"),
        "authority_label": "parsed_evidence_not_truth",
        "generated_on_demand": True,
        "current_status_source": "promotion_manifest_and_source_hash",
        "safe_for_mac_app": False,
        "safe_for_codex_context": False,
        "safe_for_nohup_workers": False,
        "safe_for_agent_context": False,
        "freshness_basis": "fresh only for the specific promotion manifest and extracted source hashes",
        "verification_command": "python3 -m pytest tests/test_safe_body_extraction.py",
    },
    {
        "artifact_id": "source_cards_output_contract",
        "label": "Source Cards Output Contract",
        "artifact_type": "producer_output_contract",
        "path_or_command": "python3 scripts/build_source_cards.py --extraction-artifact <extraction.json> --format json",
        "producer_script": "scripts/build_source_cards.py",
        "producer_command": "python3 scripts/build_source_cards.py --extraction-artifact <extraction.json> --format json",
        "expected_format": "json",
        "tags": _tags("source_cards", "context_gate", "codex_context_safe", "app_fixture_safe", "nohup_context_safe"),
        "authority_label": "compact_source_card_read_model",
        "generated_on_demand": True,
        "current_status_source": "safe_extraction_artifact",
        "safe_for_mac_app": True,
        "safe_for_codex_context": True,
        "safe_for_nohup_workers": True,
        "safe_for_agent_context": True,
        "freshness_basis": "fresh when built from current safe extraction artifact",
        "verification_command": "python3 -m pytest tests/test_source_cards.py",
    },
    {
        "artifact_id": "working_context_packets_output_contract",
        "label": "Accepted Working Context Packets Output Contract",
        "artifact_type": "producer_output_contract",
        "path_or_command": "python3 scripts/build_working_context_packets.py --source-cards <source_cards.json> --format json",
        "producer_script": "scripts/build_working_context_packets.py",
        "producer_command": "python3 scripts/build_working_context_packets.py --source-cards <source_cards.json> --format json",
        "expected_format": "json",
        "tags": _tags("working_context_packets", "context_gate", "codex_context_safe", "nohup_context_safe"),
        "authority_label": "accepted_working_context_reasoning_only",
        "generated_on_demand": True,
        "current_status_source": "source_cards_artifact",
        "safe_for_mac_app": True,
        "safe_for_codex_context": True,
        "safe_for_nohup_workers": True,
        "safe_for_agent_context": True,
        "freshness_basis": "fresh when built from current source cards artifact",
        "verification_command": "python3 -m pytest tests/test_working_context_packets.py",
    },
    {
        "artifact_id": "context_packet_retrieval_output_contract",
        "label": "Agent Context Retrieval Gate Output Contract",
        "artifact_type": "producer_output_contract",
        "path_or_command": "python3 scripts/query_context_packets.py --packets <packets.json> --module <module> --format json",
        "producer_script": "scripts/query_context_packets.py",
        "producer_command": "python3 scripts/query_context_packets.py --packets <packets.json> --module <module> --format json",
        "expected_format": "json",
        "tags": _tags("retrieval_gate", "context_gate", "codex_context_safe", "nohup_context_safe"),
        "authority_label": "context_for_reasoning_only",
        "generated_on_demand": True,
        "current_status_source": "working_context_packets_artifact_and_exact_filter",
        "safe_for_mac_app": False,
        "safe_for_codex_context": True,
        "safe_for_nohup_workers": True,
        "safe_for_agent_context": True,
        "freshness_basis": "fresh for exact query filters against current packet artifact",
        "verification_command": "python3 -m pytest tests/test_context_packet_retrieval.py",
    },
    {
        "artifact_id": "generated_status_source_inventory_section",
        "label": "Generated Status Source Inventory Section",
        "artifact_type": "generated_status_section",
        "path_or_command": "Operator/GENERATED_CURRENT_STATE.md",
        "producer_script": "scripts/generate_operator_status.py",
        "producer_command": "python3 scripts/generate_operator_status.py --write",
        "expected_format": "markdown",
        "tags": _tags("generated_status", "source_inventory", "app_fixture_safe", "codex_context_safe"),
        "authority_label": "section_summary_read_model",
        "generated_on_demand": False,
        "current_status_source": "python3 scripts/generate_operator_status.py --check",
        "safe_for_mac_app": True,
        "safe_for_codex_context": True,
        "safe_for_nohup_workers": True,
        "safe_for_agent_context": True,
        "freshness_basis": "section current when generated status check passes",
        "verification_command": "python3 scripts/generate_operator_status.py --check",
        "section_heading": "## 3. Source Inventory",
    },
    {
        "artifact_id": "generated_status_context_gates_section",
        "label": "Generated Status Context Gates Section",
        "artifact_type": "generated_status_section",
        "path_or_command": "Operator/GENERATED_CURRENT_STATE.md",
        "producer_script": "scripts/generate_operator_status.py",
        "producer_command": "python3 scripts/generate_operator_status.py --write",
        "expected_format": "markdown",
        "tags": _tags("generated_status", "context_gate", "app_fixture_safe", "codex_context_safe"),
        "authority_label": "section_summary_read_model",
        "generated_on_demand": False,
        "current_status_source": "python3 scripts/generate_operator_status.py --check",
        "safe_for_mac_app": True,
        "safe_for_codex_context": True,
        "safe_for_nohup_workers": True,
        "safe_for_agent_context": True,
        "freshness_basis": "section current when generated status check passes",
        "verification_command": "python3 scripts/generate_operator_status.py --check",
        "section_heading": "## 4. Context Gates",
    },
    {
        "artifact_id": "generated_status_helm_state_section",
        "label": "Generated Status Helm State Section",
        "artifact_type": "generated_status_section",
        "path_or_command": "Operator/GENERATED_CURRENT_STATE.md",
        "producer_script": "scripts/generate_operator_status.py",
        "producer_command": "python3 scripts/generate_operator_status.py --write",
        "expected_format": "markdown",
        "tags": _tags("generated_status", "helm_state", "app_fixture_safe", "codex_context_safe"),
        "authority_label": "section_summary_read_model",
        "generated_on_demand": False,
        "current_status_source": "python3 scripts/generate_operator_status.py --check",
        "safe_for_mac_app": True,
        "safe_for_codex_context": True,
        "safe_for_nohup_workers": True,
        "safe_for_agent_context": True,
        "freshness_basis": "section current when generated status check passes",
        "verification_command": "python3 scripts/generate_operator_status.py --check",
        "section_heading": "## 5. Helm State",
    },
    {
        "artifact_id": "generated_status_world_domain_registry_section",
        "label": "Generated Status World / Domain Registry Section",
        "artifact_type": "generated_status_section",
        "path_or_command": "Operator/GENERATED_CURRENT_STATE.md",
        "producer_script": "scripts/generate_operator_status.py",
        "producer_command": "python3 scripts/generate_operator_status.py --write",
        "expected_format": "markdown",
        "tags": _tags("generated_status", "world_registry", "app_fixture_safe", "codex_context_safe"),
        "authority_label": "section_summary_read_model",
        "generated_on_demand": False,
        "current_status_source": "python3 scripts/generate_operator_status.py --check",
        "safe_for_mac_app": True,
        "safe_for_codex_context": True,
        "safe_for_nohup_workers": True,
        "safe_for_agent_context": True,
        "freshness_basis": "section current when generated status check passes",
        "verification_command": "python3 scripts/generate_operator_status.py --check",
        "section_heading": "## 6. World / Domain Registry",
    },
    {
        "artifact_id": "source_inventory_json_concept",
        "label": "Source Inventory JSON Concept",
        "artifact_type": "recommended_export_path",
        "path_or_command": f"{READ_MODEL_OUTPUT_DIR}/source_inventory.json",
        "producer_script": "scripts/build_source_inventory.py",
        "producer_command": f"python3 scripts/build_source_inventory.py --format json > {READ_MODEL_OUTPUT_DIR}/source_inventory.json",
        "expected_format": "json",
        "tags": _tags("source_inventory", "app_fixture_safe", "codex_context_safe"),
        "authority_label": "recommended_metadata_export",
        "generated_on_demand": True,
        "current_status_source": "recommended_export_not_required_in_v0",
        "safe_for_mac_app": True,
        "safe_for_codex_context": True,
        "safe_for_nohup_workers": True,
        "safe_for_agent_context": True,
        "freshness_basis": "future standardized export path; current source is producer command",
        "verification_command": "python3 scripts/build_source_inventory.py --format json | python3 -m json.tool",
    },
    {
        "artifact_id": "helm_state_json_concept",
        "label": "Helm State JSON Concept",
        "artifact_type": "recommended_export_path",
        "path_or_command": f"{READ_MODEL_OUTPUT_DIR}/helm_state.json",
        "producer_script": "scripts/build_helm_state.py",
        "producer_command": f"python3 scripts/build_helm_state.py --format json > {READ_MODEL_OUTPUT_DIR}/helm_state.json",
        "expected_format": "json",
        "tags": _tags("helm_state", "app_fixture_safe", "codex_context_safe"),
        "authority_label": "recommended_inspect_only_export",
        "generated_on_demand": True,
        "current_status_source": "recommended_export_not_required_in_v0",
        "safe_for_mac_app": True,
        "safe_for_codex_context": True,
        "safe_for_nohup_workers": True,
        "safe_for_agent_context": True,
        "freshness_basis": "future standardized export path; current source is producer command",
        "verification_command": "python3 scripts/build_helm_state.py --format json | python3 -m json.tool",
    },
    {
        "artifact_id": "world_domain_registry_json_concept",
        "label": "World / Domain Registry JSON Concept",
        "artifact_type": "recommended_export_path",
        "path_or_command": f"{READ_MODEL_OUTPUT_DIR}/world_domain_registry.json",
        "producer_script": "scripts/build_world_domain_registry.py",
        "producer_command": f"python3 scripts/build_world_domain_registry.py --format json > {READ_MODEL_OUTPUT_DIR}/world_domain_registry.json",
        "expected_format": "json",
        "tags": _tags("world_registry", "app_fixture_safe", "codex_context_safe"),
        "authority_label": "recommended_registry_export",
        "generated_on_demand": True,
        "current_status_source": "recommended_export_not_required_in_v0",
        "safe_for_mac_app": True,
        "safe_for_codex_context": True,
        "safe_for_nohup_workers": True,
        "safe_for_agent_context": True,
        "freshness_basis": "future standardized export path; current source is producer command",
        "verification_command": "python3 scripts/build_world_domain_registry.py --format json | python3 -m json.tool",
    },
    {
        "artifact_id": "runtime_activation_gate_json_concept",
        "label": "Runtime Activation Gate JSON Concept",
        "artifact_type": "recommended_export_path",
        "path_or_command": f"{READ_MODEL_OUTPUT_DIR}/runtime_activation_gate.json",
        "producer_script": "scripts/check_runtime_activation_gate.py",
        "producer_command": f"python3 scripts/check_runtime_activation_gate.py --format json > {READ_MODEL_OUTPUT_DIR}/runtime_activation_gate.json",
        "expected_format": "json",
        "tags": _tags("activation_gate", "app_fixture_safe", "codex_context_safe", "nohup_context_safe"),
        "authority_label": "recommended_blocked_gate_export",
        "generated_on_demand": True,
        "current_status_source": "recommended_export_not_required_in_v0",
        "safe_for_mac_app": True,
        "safe_for_codex_context": True,
        "safe_for_nohup_workers": True,
        "safe_for_agent_context": True,
        "freshness_basis": "future standardized export path; current source is producer command",
        "verification_command": "python3 scripts/check_runtime_activation_gate.py --format json | python3 -m json.tool",
    },
    {
        "artifact_id": "source_cards_json_concept",
        "label": "Source Cards JSON Concept",
        "artifact_type": "recommended_export_path",
        "path_or_command": f"{READ_MODEL_OUTPUT_DIR}/source_cards.json",
        "producer_script": "scripts/build_source_cards.py",
        "producer_command": f"python3 scripts/build_source_cards.py --extraction-artifact <extraction.json> --format json > {READ_MODEL_OUTPUT_DIR}/source_cards.json",
        "expected_format": "json",
        "tags": _tags("source_cards", "app_fixture_safe", "codex_context_safe", "nohup_context_safe"),
        "authority_label": "recommended_source_card_export",
        "generated_on_demand": True,
        "current_status_source": "recommended_export_not_required_in_v0",
        "safe_for_mac_app": True,
        "safe_for_codex_context": True,
        "safe_for_nohup_workers": True,
        "safe_for_agent_context": True,
        "freshness_basis": "future standardized export path; current source is safe extraction artifact",
        "verification_command": "python3 -m pytest tests/test_source_cards.py",
    },
    {
        "artifact_id": "working_context_packets_json_concept",
        "label": "Working Context Packets JSON Concept",
        "artifact_type": "recommended_export_path",
        "path_or_command": f"{READ_MODEL_OUTPUT_DIR}/working_context_packets.json",
        "producer_script": "scripts/build_working_context_packets.py",
        "producer_command": f"python3 scripts/build_working_context_packets.py --source-cards <source_cards.json> --format json > {READ_MODEL_OUTPUT_DIR}/working_context_packets.json",
        "expected_format": "json",
        "tags": _tags("working_context_packets", "codex_context_safe", "nohup_context_safe"),
        "authority_label": "recommended_packet_export",
        "generated_on_demand": True,
        "current_status_source": "recommended_export_not_required_in_v0",
        "safe_for_mac_app": True,
        "safe_for_codex_context": True,
        "safe_for_nohup_workers": True,
        "safe_for_agent_context": True,
        "freshness_basis": "future standardized export path; current source is source cards artifact",
        "verification_command": "python3 -m pytest tests/test_working_context_packets.py",
    },
    {
        "artifact_id": "context_packet_retrieval_json_concept",
        "label": "Context Packet Retrieval JSON Concept",
        "artifact_type": "recommended_export_path",
        "path_or_command": f"{READ_MODEL_OUTPUT_DIR}/context_packet_retrieval.json",
        "producer_script": "scripts/query_context_packets.py",
        "producer_command": f"python3 scripts/query_context_packets.py --packets <packets.json> --module <module> --format json > {READ_MODEL_OUTPUT_DIR}/context_packet_retrieval.json",
        "expected_format": "json",
        "tags": _tags("retrieval_gate", "codex_context_safe", "nohup_context_safe"),
        "authority_label": "recommended_retrieval_export",
        "generated_on_demand": True,
        "current_status_source": "recommended_export_not_required_in_v0",
        "safe_for_mac_app": False,
        "safe_for_codex_context": True,
        "safe_for_nohup_workers": True,
        "safe_for_agent_context": True,
        "freshness_basis": "future standardized export path; current source is exact retrieval query",
        "verification_command": "python3 -m pytest tests/test_context_packet_retrieval.py",
    },
)


def stable_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _file_metadata(path_or_command: str, root: Path) -> dict[str, Any]:
    path = Path(path_or_command)
    if path.is_absolute() or ".." in path.parts:
        return {
            "artifact_present": False,
            "content_sha256": None,
            "size_bytes": None,
            "hash_basis": "not_applicable_non_repo_path",
        }

    full_path = (root / path).resolve()
    try:
        full_path.relative_to(root.resolve())
    except ValueError:
        return {
            "artifact_present": False,
            "content_sha256": None,
            "size_bytes": None,
            "hash_basis": "not_applicable_outside_repo",
        }

    if not full_path.is_file():
        return {
            "artifact_present": False,
            "content_sha256": None,
            "size_bytes": None,
            "hash_basis": "not_present_or_generated_on_demand",
        }

    body = full_path.read_bytes()
    return {
        "artifact_present": True,
        "content_sha256": hashlib.sha256(body).hexdigest(),
        "size_bytes": len(body),
        "hash_basis": "explicit_allowlisted_file_sha256_body_not_emitted",
    }


def _artifact_record(definition: dict[str, Any], root: Path) -> dict[str, Any]:
    record = deepcopy(definition)
    if record["artifact_type"] in {"generated_status_markdown", "generated_status_section"}:
        file_metadata = _file_metadata(record["path_or_command"], root)
    else:
        file_metadata = {
            "artifact_present": False,
            "content_sha256": None,
            "size_bytes": None,
            "hash_basis": "generated_on_demand_contract",
        }

    record.update(
        {
            "body_ingested": False,
            "metadata_only": True,
            "runtime_authority": False,
            "activation_allowed": False,
            "backend_execution_authorized": False,
            "claims_not_made": list(COMMON_CLAIMS_NOT_MADE),
            **file_metadata,
        }
    )
    return record


def build_artifact_registry(*, root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    artifacts = [_artifact_record(definition, root) for definition in ARTIFACT_DEFINITIONS]

    safe_for_mac = sum(1 for artifact in artifacts if artifact["safe_for_mac_app"])
    safe_for_codex = sum(1 for artifact in artifacts if artifact["safe_for_codex_context"])
    safe_for_nohup = sum(1 for artifact in artifacts if artifact["safe_for_nohup_workers"])
    safe_for_agent = sum(1 for artifact in artifacts if artifact["safe_for_agent_context"])

    return {
        "read_model_version": READ_MODEL_VERSION,
        "mode": MODE,
        "metadata_only": True,
        "runtime_authority": False,
        "activation_allowed": False,
        "backend_execution_authorized": False,
        "body_ingested": False,
        "sqlite_touched": False,
        "broad_scan": False,
        "hard_drive_scan": False,
        "private_data_access": False,
        "artifact_count": len(artifacts),
        "consumer_summary": {
            "safe_for_mac_app": safe_for_mac,
            "safe_for_codex_context": safe_for_codex,
            "safe_for_nohup_workers": safe_for_nohup,
            "safe_for_agent_context": safe_for_agent,
        },
        "registry_scope": {
            "explicit_allowlist_only": True,
            "file_hashing": "explicit_registered_files_only",
            "file_bodies_emitted": False,
            "sqlite_writes": False,
            "recommended_output_dir": READ_MODEL_OUTPUT_DIR,
        },
        "artifacts": artifacts,
        "claims_not_made": list(COMMON_CLAIMS_NOT_MADE),
    }


def format_operator_artifact_registry(read_model: dict[str, Any]) -> str:
    consumers = read_model["consumer_summary"]
    section_count = sum(
        1
        for artifact in read_model["artifacts"]
        if artifact["artifact_type"] == "generated_status_section"
    )
    generated_markdown_count = sum(
        1
        for artifact in read_model["artifacts"]
        if artifact["artifact_type"] == "generated_status_markdown"
    )
    contract_count = sum(
        1
        for artifact in read_model["artifacts"]
        if artifact["artifact_type"] == "producer_output_contract"
    )
    export_count = sum(
        1
        for artifact in read_model["artifacts"]
        if artifact["artifact_type"] == "recommended_export_path"
    )
    lines = [
        "Read-Model Artifact Registry v0",
        "",
        "Evidence:",
        (
            f"- Registered {read_model['artifact_count']} metadata/read-model artifact records: "
            f"{generated_markdown_count} generated Markdown files, "
            f"{contract_count} producer contracts, {section_count} generated-status sections, "
            f"and {export_count} recommended export paths."
        ),
        (
            "- Consumer-safe records: "
            f"Mac app={consumers['safe_for_mac_app']}; "
            f"Codex context={consumers['safe_for_codex_context']}; "
            f"nohup/background workers={consumers['safe_for_nohup_workers']}; "
            f"agent context={consumers['safe_for_agent_context']}."
        ),
        "- Registered artifacts carry tags, authority labels, freshness basis, verification command, and explicit no-claims.",
        "",
        "Boundary:",
        "- Registry records metadata only; file bodies are not ingested, emitted, or stored in SQLite.",
        "- File hashes are computed only for explicit registered repo-local files; no broad scan is performed.",
        "- `runtime_authority=false`; `activation_allowed=false`; `backend_execution_authorized=false`.",
        "- Registry visibility does not authorize app writes, runtime actions, agents, brokers, external tools, networking, or customer deployment.",
        "",
        "Blocked:",
        "- Full body ingest, SQLite body storage, broad repo scan, hard-drive scan, private/legal/tax/CPA/AppData/runtime-log access remain blocked.",
        "- Runtime activation, backend execution, agent activation, broker wiring, external tool calls, networking, and customer deployment remain blocked.",
        "- Dynamic world state, strategic gravity scoring, active agent presence, live health, and process liveness are not claimed.",
        "",
        "Next safe move:",
        (
            f"- Standardize export/sync locations under `{READ_MODEL_OUTPUT_DIR}/` so the Mac app, "
            "Codex-on-Mac, and nohup/background workers consume registered read-model artifacts instead of guessing paths."
        ),
    ]
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the deterministic metadata-only read-model artifact registry."
    )
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format. Defaults to operator.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    read_model = build_artifact_registry()
    if args.format == "json":
        print(stable_json(read_model), end="")
    else:
        print(format_operator_artifact_registry(read_model))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
