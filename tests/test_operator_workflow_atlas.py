import ast
import json
from pathlib import Path

import operator_workflow_atlas as atlas
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_operator_workflow_atlas_read_model import main as export_main


FIXED_NOW = "2026-05-17T18:00:00+00:00"


def test_workflows_are_classified_with_status_and_confidence():
    payload = atlas.build_workflow_atlas(generated_at=FIXED_NOW)

    assert payload["schema_version"] == atlas.SCHEMA_VERSION
    assert payload["workflows_classified_with_confidence"] is True
    assert payload["workflow_count"] >= 10
    assert payload["built_implemented"]
    assert payload["built_not_integrated"]
    assert payload["desired_not_built"]
    assert payload["not_built_should_not_build_yet"]
    for workflow in payload["workflow_atlas"]:
        assert workflow["current_implementation_status"] in atlas.STATUS_CATEGORIES
        assert workflow["confidence"] in atlas.CONFIDENCE_LEVELS
        assert workflow["shared_bottleneck"]
        assert workflow["next_safe_lane"]


def test_old_docs_and_files_are_evidence_not_truth():
    payload = atlas.build_workflow_atlas(generated_at=FIXED_NOW)

    assert payload["old_files_treated_as_evidence_not_truth"] is True
    doc_sources = []
    for workflow in payload["workflow_atlas"]:
        assert workflow["old_files_treated_as_evidence_not_truth"] is True
        for source in workflow["current_evidence_sources"]:
            assert source["truth_status"] in atlas.EVIDENCE_NOT_TRUTH_STATUSES
            assert source["truth_status"] != "truth"
            if source["path"].startswith("docs/") or source["truth_status"].endswith("evidence_only"):
                doc_sources.append(source)
    assert doc_sources


def test_unknowns_are_not_treated_as_confirmed_built():
    payload = atlas.build_workflow_atlas(generated_at=FIXED_NOW)
    statuses = {item["workflow_name"]: item["current_implementation_status"] for item in payload["workflow_atlas"]}

    assert statuses["Niles album progress review"] != "CONFIRMED_BUILT_AND_WIRED"
    assert statuses["Remote builder bridge"] == "SHOULD_NOT_BUILD_YET"
    assert statuses["Hard-drive/cloud/file ingest"] == "SHOULD_NOT_BUILD_YET"
    assert (
        statuses["Markdown and source classification for broad workflow discovery"]
        == "BLOCKED_BY_MISSING_INGEST_OR_TAGGING"
    )


def test_workflows_group_by_shared_bottleneck():
    payload = atlas.build_workflow_atlas(generated_at=FIXED_NOW)
    bottlenecks = payload["shared_bottleneck_map"]

    assert "governed_receive_to_work_packet_projection" in bottlenecks
    assert bottlenecks["governed_receive_to_work_packet_projection"]["workflow_count"] >= 2
    assert "send_path_authority_gate" in bottlenecks
    assert "generic_review_packet_non_finance_reuse" in bottlenecks


def test_recommendations_use_post_preflight_batch_gate_and_pass():
    payload = atlas.build_workflow_atlas(generated_at=FIXED_NOW)

    assert payload["batch_gate_used"] is True
    assert payload["batch_gate_all_recommendations_pass"] is True
    assert payload["batch_gate_pass_count"] == 3
    assert len(payload["recommended_first_3_post_preflight_batch_lanes"]) == 3
    for lane in payload["recommended_first_3_post_preflight_batch_lanes"]:
        gate = lane["post_preflight_gate_evaluation"]
        assert gate["gate_status"] == "pass"
        assert gate["named_operator_workflow"]
        assert gate["shared_bottleneck"] != "modularity"
        assert gate["workflow_proof_output"]
        assert gate["runtime_authority_added"] is False
        assert gate["send_or_submit_authority_added"] is False
        assert gate["customer_deployment_authority_added"] is False


def test_missing_ingestion_is_reported_without_blocking_next_batch():
    payload = atlas.build_workflow_atlas(generated_at=FIXED_NOW)
    sufficiency = payload["markdown_source_classification_sufficiency"]

    assert payload["md_source_ingestion_required_before_next_batch"] is False
    assert sufficiency["sufficient_for_next_post_preflight_batch"] is True
    assert sufficiency["full_system_restructure_requires_ingestion_or_tagging"] is True
    assert sufficiency["smallest_needed_later_lane"]["lane_name"] == "Workflow Evidence Header Inventory v0"


def test_no_authority_runtime_send_or_deploy_path_is_added():
    payload = atlas.build_workflow_atlas(generated_at=FIXED_NOW)

    for key, expected in atlas.NO_AUTHORITY_FLAGS.items():
        assert payload[key] is expected
        assert payload["no_authority_flags"][key] is expected
    assert payload["runtime_authority_added"] is False
    assert payload["send_or_submit_authority_added"] is False
    assert payload["customer_deployment_authority_added"] is False


def test_export_writes_valid_json_and_operator_packet(tmp_path, capsys):
    export_root = tmp_path / "generated" / "read_models"

    exit_code = export_main(["--export-root", str(export_root), "--repo-root", str(tmp_path), "--format", "operator"])
    operator_text = capsys.readouterr().out
    payload = json.loads((export_root / atlas.JSON_EXPORT_NAME).read_text(encoding="utf-8"))

    assert exit_code == 0
    assert (export_root / atlas.OPERATOR_EXPORT_NAME).is_file()
    assert "Operator Workflow Atlas" in operator_text
    assert payload["batch_gate_all_recommendations_pass"] is True
    assert payload["operator_manual_rewrite_required"] is False
    assert payload["old_files_treated_as_evidence_not_truth"] is True


def test_generated_read_model_files_are_safe_mirror_candidates(tmp_path):
    export_root = tmp_path / "generated" / "read_models"
    atlas.export_operator_workflow_atlas(export_root=export_root, repo_root=tmp_path, generated_at=FIXED_NOW)

    expected = set(canonical_generated_read_model_expected_files(source_root=export_root, repo_root=tmp_path))
    assert atlas.JSON_EXPORT_NAME in expected
    assert atlas.OPERATOR_EXPORT_NAME in expected


def test_sources_do_not_execute_shell_network_or_repo_b():
    source_files = [
        Path("operator_workflow_atlas.py"),
        Path("scripts/export_operator_workflow_atlas_read_model.py"),
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
        "docker run",
        "send_message",
        "smtp",
    ]
    for path in source_files:
        text = path.read_text(encoding="utf-8").lower()
        for token in forbidden_text:
            assert token not in text

    tree = ast.parse(Path("operator_workflow_atlas.py").read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "subprocess" not in imported
