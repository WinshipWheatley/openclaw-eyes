import ast
import json
from pathlib import Path

import custom_build_module_detangling_contract as contract
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_custom_build_module_detangling_contract_read_model import main as export_main


FIXED_NOW = "2026-05-17T16:00:00+00:00"


def test_assessments_serialize_deterministically_and_are_synthetic():
    first = contract.build_custom_build_module_detangling_read_model(generated_at=FIXED_NOW)
    second = contract.build_custom_build_module_detangling_read_model(generated_at=FIXED_NOW)

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.READ_MODEL_VERSION
    assert first["contract_schema_version"] == contract.SCHEMA_VERSION
    assert first["assessment_count"] >= 3
    assert all(item["synthetic_example"] is True for item in first["assessments"])
    assert all(item["real_client_data_used"] is False for item in first["assessments"])
    assert all(item["private_data_copied"] is False for item in first["assessments"])


def test_tangled_dependencies_and_variants_are_explicit():
    read_model = contract.build_custom_build_module_detangling_read_model(generated_at=FIXED_NOW)
    by_request = {item["requested_custom_build"]: item for item in read_model["assessments"]}

    cassandra_only = by_request["Synthetic Cassandra-only helper"]
    assert {"chief_control_plane", "guardian_hitl_gate", "watcher_scheduler_loop"} <= {
        item["dependency"] for item in cassandra_only["current_tangle_dependencies"]
    }
    assert cassandra_only["minimum_viable_extracted_module"]["module_shape"] == "standalone_smaller_module"
    assert {item["variant_shape"] for item in cassandra_only["possible_module_variants"]} == {
        "standalone_smaller_module",
        "gated_module",
    }

    cassandra_chief = by_request["Synthetic Cassandra plus Chief planning helper"]
    assert cassandra_chief["minimum_viable_extracted_module"]["module_shape"] == "paired_module"
    assert any(
        item["dependency"] == "agent_runtime_stack" and item["required_for_minimum_module"] is False
        for item in cassandra_chief["current_tangle_dependencies"]
    )


def test_client_suitability_and_core_replacement_are_not_automatic():
    read_model = contract.build_custom_build_module_detangling_read_model(generated_at=FIXED_NOW)

    assert read_model["openclaw_core_replacement_automatic"] is False
    for assessment in read_model["assessments"]:
        assert assessment["client_suitability"]["client_safe_by_default"] is False
        assert assessment["client_suitability_granted_by_default"] is False
        assert assessment["openclaw_core_replacement_potential"]["automatic_replacement"] is False
        assert assessment["core_replacement_automatic"] is False
        assert assessment["migration_recommendation"]["core_action_now"]
        assert assessment["validation_required_before_adoption"]


def test_no_runtime_send_deploy_or_customer_authority_is_implied():
    read_model = contract.build_custom_build_module_detangling_read_model(generated_at=FIXED_NOW)

    for key, expected in contract.NO_AUTHORITY_FLAGS.items():
        assert read_model[key] is expected
        assert read_model["no_authority_flags"][key] is expected
    for assessment in read_model["assessments"]:
        for key, expected in contract.NO_AUTHORITY_FLAGS.items():
            assert assessment[key] is expected


def test_export_writes_read_model_and_operator_packet(tmp_path, capsys):
    export_root = tmp_path / "read_models"

    exit_code = export_main(["--export-root", str(export_root), "--format", "operator"])
    operator_text = capsys.readouterr().out
    payload = json.loads((export_root / contract.JSON_EXPORT_NAME).read_text(encoding="utf-8"))

    assert exit_code == 0
    assert (export_root / contract.OPERATOR_EXPORT_NAME).is_file()
    assert "Custom Build Module Detangling Contract v0" in operator_text
    assert payload["assessment_count"] >= 3
    assert payload["client_repo_generation_added"] is False
    assert payload["runtime_authority"] is False
    assert payload["send_or_submit_authority"] is False


def test_generated_read_model_files_are_safe_mirror_candidates(tmp_path):
    export_root = tmp_path / "generated" / "read_models"
    contract.export_custom_build_module_detangling_read_model(export_root=export_root, generated_at=FIXED_NOW)

    expected = set(canonical_generated_read_model_expected_files(source_root=export_root, repo_root=tmp_path))
    assert contract.JSON_EXPORT_NAME in expected
    assert contract.OPERATOR_EXPORT_NAME in expected


def test_sources_have_no_external_runtime_shell_or_repo_b_execution():
    source_files = [
        Path("custom_build_module_detangling_contract.py"),
        Path("scripts/export_custom_build_module_detangling_contract_read_model.py"),
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

    tree = ast.parse(Path("custom_build_module_detangling_contract.py").read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "subprocess" not in imported
