import ast
import json
from pathlib import Path

import post_preflight_batch_gate as gate
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_post_preflight_batch_gate_read_model import main as export_main


FIXED_NOW = "2026-05-17T16:30:00+00:00"


def test_structured_gate_fields_are_present_and_deterministic():
    first = gate.build_post_preflight_batch_gate_read_model(generated_at=FIXED_NOW)
    second = gate.build_post_preflight_batch_gate_read_model(generated_at=FIXED_NOW)

    assert gate.stable_json(first) == gate.stable_json(second)
    assert first["schema_version"] == gate.READ_MODEL_VERSION
    assert first["contract_schema_version"] == gate.SCHEMA_VERSION
    for item in first["examples"]:
        for field in gate.REQUIRED_GATE_FIELDS:
            assert field in item
        assert item["synthetic_example"] is True
        assert item["briar_patch_operator_language_only"] is True


def test_valid_lane_passes_only_when_tied_to_named_workflow():
    payload = gate.evaluate_post_preflight_lane(
        lane_name="Review Packet Reuse",
        lane_summary="Use generic proof schema for Capital Hilton followup.",
        named_operator_workflow="Capital Hilton invoice review",
        shared_bottleneck="review_packet_schema_reuse",
        steel_thread_contract_link="cassandra_governed_review_packet_request_proof_v1",
        reusable_substrate_improvement="Generic packet schema remains reusable.",
        workflow_proof_output="Capital Hilton review packet",
        detangling_scope={"serves_lane_directly": True, "opportunistic_only": True},
        module_split_disposition={"disposition": "none"},
        authority_change_requested={"requested": False, "authority_types": []},
        expected_artifacts=[{"artifact_kind": "review_packet", "path_or_contract": "packet.json"}],
        validation_required=["pytest focused"],
    )
    assert payload["gate_status"] == gate.PASS

    missing_workflow = {**payload, "named_operator_workflow": ""}
    rerun = gate.evaluate_post_preflight_lane(
        lane_name=missing_workflow["lane_name"],
        lane_summary=missing_workflow["lane_summary"],
        named_operator_workflow=missing_workflow["named_operator_workflow"],
        shared_bottleneck=missing_workflow["shared_bottleneck"],
        steel_thread_contract_link=missing_workflow["steel_thread_contract_link"],
        reusable_substrate_improvement=missing_workflow["reusable_substrate_improvement"],
        workflow_proof_output=missing_workflow["workflow_proof_output"],
        detangling_scope=missing_workflow["detangling_scope"],
        module_split_disposition=missing_workflow["module_split_disposition"],
        authority_change_requested=missing_workflow["authority_change_requested"],
        expected_artifacts=missing_workflow["expected_artifacts"],
        validation_required=missing_workflow["validation_required"],
    )
    assert rerun["gate_status"] == gate.FAIL
    assert "missing_named_operator_workflow" in rerun["failure_reasons"]


def test_abstract_prep_lane_fails_without_workflow_and_shared_bottleneck():
    examples = gate.synthetic_gate_examples()
    abstract = next(item for item in examples if item["lane_name"] == "Abstract Module Prep Sprint")

    assert abstract["gate_status"] == gate.FAIL
    assert "missing_named_operator_workflow" in abstract["failure_reasons"]
    assert "shared_bottleneck_is_vague_theme" in abstract["failure_reasons"]
    assert "detangling_became_mandatory_prep_detour" in abstract["failure_reasons"]
    assert abstract["abstract_prep_allowed_without_workflow"] is False


def test_batching_by_shared_bottleneck_and_substrate_plus_workflow_are_required():
    payload = gate.evaluate_post_preflight_lane(
        lane_name="Vague Theme Lane",
        lane_summary="Do some module work.",
        named_operator_workflow="Capital Hilton invoice review",
        shared_bottleneck="modularity",
        steel_thread_contract_link="contract",
        reusable_substrate_improvement="Some shared substrate work.",
        workflow_proof_output="Packet",
        detangling_scope={"serves_lane_directly": True, "opportunistic_only": True},
        module_split_disposition={"disposition": "none"},
        authority_change_requested={"requested": False, "authority_types": []},
        expected_artifacts=[{"artifact_kind": "read_model", "path_or_contract": "x.json"}],
        validation_required=["json validation"],
    )

    assert payload["batch_by_shared_bottleneck"] is True
    assert payload["one_batch_reusable_substrate_plus_workflow_proof"] is True
    assert payload["gate_status"] == gate.FAIL
    assert "shared_bottleneck_is_vague_theme" in payload["failure_reasons"]


def test_module_split_can_be_recorded_without_triggering_extraction():
    split = next(
        item
        for item in gate.synthetic_gate_examples()
        if item["lane_name"] == "Cassandra Intake to Niles Album Review Packet"
    )

    assert split["gate_status"] == gate.PASS
    assert split["module_split_disposition"]["disposition"] == "record_future_work"
    assert split["detangling_scope"]["physical_module_extraction_requested"] is False
    assert split["module_extraction_added"] is False
    assert split["recommendation"] == "proceed_with_lane_and_record_module_split_for_future_work"


def test_authority_expansion_fails_unless_explicitly_gated():
    ungated = next(
        item
        for item in gate.synthetic_gate_examples()
        if item["lane_name"] == "Ungated Send and Deployment Shortcut"
    )

    assert ungated["gate_status"] == gate.FAIL
    assert "ungated_authority_expansion_requested" in ungated["failure_reasons"]
    assert ungated["send_or_submit_authority_added"] is False
    assert ungated["runtime_authority_added"] is False
    assert ungated["customer_deployment_authority_added"] is False

    gated = gate.evaluate_post_preflight_lane(
        lane_name="Authority Gate Inspection",
        lane_summary="Inspect an authority request without granting it.",
        named_operator_workflow="Capital Hilton invoice review",
        shared_bottleneck="approval_boundary_review",
        steel_thread_contract_link="guardian_hitl_sqlite_authority_contract",
        reusable_substrate_improvement="Authority request is forced into explicit gate.",
        workflow_proof_output="Authority gate readiness packet",
        detangling_scope={"serves_lane_directly": True, "opportunistic_only": True},
        module_split_disposition={"disposition": "none"},
        authority_change_requested={"requested": True, "authority_types": ["send"]},
        authority_gate_required=True,
        expected_artifacts=[{"artifact_kind": "operator_packet", "path_or_contract": "gate.md"}],
        validation_required=["no authority added proof"],
    )
    assert gated["gate_status"] == gate.PASS
    assert gated["send_or_submit_authority_added"] is False


def test_export_writes_valid_read_model_and_operator_packet(tmp_path, capsys):
    export_root = tmp_path / "read_models"

    exit_code = export_main(["--export-root", str(export_root), "--format", "operator"])
    operator_text = capsys.readouterr().out
    payload = json.loads((export_root / gate.JSON_EXPORT_NAME).read_text(encoding="utf-8"))

    assert exit_code == 0
    assert (export_root / gate.OPERATOR_EXPORT_NAME).is_file()
    assert "Briar Patch Batch Gate" in operator_text
    assert payload["briar_patch_operator_language_only"] is True
    assert payload["abstract_prep_allowed_without_workflow"] is False
    assert payload["module_extraction_added"] is False
    assert payload["client_repo_generation_added"] is False
    assert payload["runtime_authority_added"] is False
    assert payload["send_or_submit_authority_added"] is False
    assert payload["customer_deployment_authority_added"] is False


def test_generated_read_model_files_are_safe_mirror_candidates(tmp_path):
    export_root = tmp_path / "generated" / "read_models"
    gate.export_post_preflight_batch_gate_read_model(export_root=export_root, generated_at=FIXED_NOW)

    expected = set(canonical_generated_read_model_expected_files(source_root=export_root, repo_root=tmp_path))
    assert gate.JSON_EXPORT_NAME in expected
    assert gate.OPERATOR_EXPORT_NAME in expected


def test_sources_have_no_external_runtime_shell_or_repo_b_execution():
    source_files = [
        Path("post_preflight_batch_gate.py"),
        Path("scripts/export_post_preflight_batch_gate_read_model.py"),
    ]
    forbidden_text = [
        "/home/openclaw_external/openclaw-runtime",
        "subprocess.",
        "os.system",
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "git clone",
        "git push",
        "docker run",
        "ollama run",
        "send_message",
        "smtp",
    ]
    for path in source_files:
        text = path.read_text(encoding="utf-8").lower()
        for token in forbidden_text:
            assert token not in text

    tree = ast.parse(Path("post_preflight_batch_gate.py").read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "subprocess" not in imported
