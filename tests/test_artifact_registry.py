import json

from scripts.build_artifact_registry import (
    EXPECTED_CORE_ARTIFACT_IDS,
    EXPECTED_GENERATED_STATUS_SECTION_IDS,
    EXPECTED_STANDARDIZED_EXPORT_IDS,
    EXPECTED_STANDARDIZED_EXPORT_PATHS,
    READ_MODEL_VERSION,
    build_artifact_registry,
    format_operator_artifact_registry,
    main,
)


REQUIRED_ARTIFACT_FIELDS = {
    "artifact_id",
    "label",
    "artifact_type",
    "path_or_command",
    "producer_script",
    "producer_command",
    "expected_format",
    "tags",
    "authority_label",
    "body_ingested",
    "metadata_only",
    "generated_on_demand",
    "current_status_source",
    "safe_for_mac_app",
    "safe_for_codex_context",
    "safe_for_nohup_workers",
    "safe_for_agent_context",
    "runtime_authority",
    "activation_allowed",
    "backend_execution_authorized",
    "freshness_basis",
    "verification_command",
    "claims_not_made",
}


def _registry():
    return build_artifact_registry()


def _artifact_by_id(payload):
    return {artifact["artifact_id"]: artifact for artifact in payload["artifacts"]}


def _payload_text(payload):
    return json.dumps(payload, sort_keys=True).lower()


def test_json_output_has_required_top_level_fields():
    payload = _registry()

    assert payload["read_model_version"] == READ_MODEL_VERSION
    assert payload["mode"] == "metadata_only_artifact_registry"
    for key in [
        "runtime_authority",
        "activation_allowed",
        "backend_execution_authorized",
        "body_ingested",
        "broad_scan",
        "artifact_count",
        "artifacts",
        "claims_not_made",
    ]:
        assert key in payload
    assert payload["artifact_count"] == len(payload["artifacts"])


def test_registry_is_metadata_only_with_no_body_ingest():
    payload = _registry()

    assert payload["metadata_only"] is True
    assert payload["body_ingested"] is False
    assert payload["sqlite_touched"] is False
    assert payload["broad_scan"] is False
    assert payload["hard_drive_scan"] is False
    assert payload["private_data_access"] is False
    for artifact in payload["artifacts"]:
        assert artifact["metadata_only"] is True
        assert artifact["body_ingested"] is False


def test_expected_core_artifacts_and_producers_are_registered():
    artifacts = _artifact_by_id(_registry())

    assert EXPECTED_CORE_ARTIFACT_IDS <= set(artifacts)
    assert artifacts["generated_current_state"]["path_or_command"] == "Operator/GENERATED_CURRENT_STATE.md"
    assert artifacts["generated_next_actions"]["path_or_command"] == "Operator/GENERATED_NEXT_ACTIONS.md"
    assert artifacts["source_inventory_output_contract"]["producer_script"] == "scripts/build_source_inventory.py"
    assert artifacts["helm_state_output_contract"]["producer_script"] == "scripts/build_helm_state.py"
    assert artifacts["world_domain_registry_output_contract"]["producer_script"] == "scripts/build_world_domain_registry.py"
    assert artifacts["world_status_output_contract"]["producer_script"] == "scripts/build_world_status.py"
    assert artifacts["artifact_registry_output_contract"]["producer_script"] == "scripts/build_artifact_registry.py"
    assert artifacts["evidence_freshness_output_contract"]["producer_script"] == "scripts/build_evidence_freshness.py"
    assert artifacts["runtime_activation_gate_output_contract"]["producer_script"] == "scripts/check_runtime_activation_gate.py"


def test_generated_status_sections_are_represented():
    artifacts = _artifact_by_id(_registry())

    assert EXPECTED_GENERATED_STATUS_SECTION_IDS <= set(artifacts)
    for artifact_id in EXPECTED_GENERATED_STATUS_SECTION_IDS:
        artifact = artifacts[artifact_id]
        assert artifact["artifact_type"] == "generated_status_section"
        assert artifact["path_or_command"] == "Operator/GENERATED_CURRENT_STATE.md"
        assert "generated_status" in artifact["tags"]
        assert artifact["expected_format"] == "markdown"


def test_each_artifact_has_required_fields_tags_and_consumer_flags():
    payload = _registry()

    for artifact in payload["artifacts"]:
        assert REQUIRED_ARTIFACT_FIELDS <= set(artifact)
        assert artifact["tags"]
        assert isinstance(artifact["safe_for_mac_app"], bool)
        assert isinstance(artifact["safe_for_codex_context"], bool)
        assert isinstance(artifact["safe_for_nohup_workers"], bool)
        assert isinstance(artifact["safe_for_agent_context"], bool)
        assert artifact["freshness_basis"]
        assert artifact["verification_command"]


def test_registry_does_not_grant_runtime_or_backend_execution_authority():
    payload = _registry()

    assert payload["runtime_authority"] is False
    assert payload["activation_allowed"] is False
    assert payload["backend_execution_authorized"] is False
    for artifact in payload["artifacts"]:
        assert artifact["runtime_authority"] is False
        assert artifact["activation_allowed"] is False
        assert artifact["backend_execution_authorized"] is False


def test_registry_marks_intended_consumers():
    artifacts = _artifact_by_id(_registry())

    assert artifacts["generated_current_state"]["safe_for_mac_app"] is True
    assert artifacts["helm_state_json_export"]["safe_for_mac_app"] is True
    assert artifacts["world_domain_registry_json_export"]["safe_for_mac_app"] is True
    assert artifacts["world_status_json_export"]["safe_for_mac_app"] is True
    assert artifacts["evidence_freshness_json_export"]["safe_for_mac_app"] is True
    assert artifacts["source_inventory_operator_export"]["safe_for_codex_context"] is True
    assert artifacts["runtime_activation_gate_operator_export"]["safe_for_nohup_workers"] is True
    assert artifacts["generated_next_actions_markdown_export"]["safe_for_agent_context"] is True


def test_standardized_export_paths_are_registered_and_present():
    artifacts = _artifact_by_id(_registry())

    assert EXPECTED_STANDARDIZED_EXPORT_IDS <= set(artifacts)
    export_records = [
        artifact
        for artifact in artifacts.values()
        if artifact["artifact_type"] == "standardized_export_path"
    ]
    assert {artifact["path_or_command"] for artifact in export_records} == set(
        EXPECTED_STANDARDIZED_EXPORT_PATHS
    )
    for artifact in export_records:
        assert artifact["producer_script"] == "scripts/export_read_models.py"
        assert artifact["producer_command"] == "python3 scripts/export_read_models.py --format json"
        assert artifact["current_status_source"] == "python3 scripts/export_read_models.py --check"
        assert artifact["verification_command"] == "python3 scripts/export_read_models.py --check"
        assert artifact["artifact_present"] is True
        assert artifact["content_sha256"] is None
        assert artifact["hash_basis"] == "explicit_standardized_export_path_presence_only_body_not_read"


def test_operator_output_uses_cockpit_grammar():
    output = format_operator_artifact_registry(_registry())

    assert "Read-Model Artifact Registry v0" in output
    assert (
        "Registered 34 metadata/read-model artifact records: "
        "2 generated Markdown files, 12 producer contracts, "
        "4 generated-status sections, and 16 standardized export paths."
    ) in output
    assert "Evidence:" in output
    assert "Boundary:" in output
    assert "Blocked:" in output
    assert "Next safe move:" in output
    assert output.index("Evidence:") < output.index("Boundary:")
    assert output.index("Boundary:") < output.index("Blocked:")
    assert output.index("Blocked:") < output.index("Next safe move:")
    assert '"artifacts"' not in output


def test_output_does_not_claim_live_or_runtime_behavior():
    payload = _registry()
    text = _payload_text(payload) + "\n" + format_operator_artifact_registry(payload).lower()

    for forbidden in [
        "all systems nominal",
        "runtime healthy",
        "runtime ready",
        "runtime activation is allowed",
        "agents are active",
        "dynamic worlds are active",
        "strategic gravity scoring is implemented",
        "broker connected",
        "external tools active",
        "networking enabled",
        "customer deployment active",
        "live heartbeat",
        "process heartbeat",
    ]:
        assert forbidden not in text

    assert "live_health_claim" in payload["claims_not_made"]
    assert "runtime_activation_authority" in payload["claims_not_made"]
    assert "strategic_gravity_scoring" in payload["claims_not_made"]


def test_no_broad_scan_or_private_path_records_are_present():
    payload = _registry()
    text = _payload_text(payload)

    for forbidden_path in [
        ".chief.env",
        ".google-secrets",
        "private/",
        "legal/",
        "tax/",
        "cpa/",
        "appdata",
        "runtime_logs",
        "/mnt/c",
        "c:/users",
    ]:
        assert forbidden_path not in text
    assert payload["broad_scan"] is False
    assert payload["hard_drive_scan"] is False


def test_cli_json_output_is_machine_readable(capsys):
    exit_code = main(["--format", "json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["read_model_version"] == READ_MODEL_VERSION
    assert payload["body_ingested"] is False
    assert payload["runtime_authority"] is False
    assert payload["artifact_count"] == len(payload["artifacts"])


def test_cli_operator_output(capsys):
    exit_code = main(["--format", "operator"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Read-Model Artifact Registry v0" in output
    assert "Evidence:" in output
    assert "Boundary:" in output
    assert "Blocked:" in output
    assert "Next safe move:" in output
