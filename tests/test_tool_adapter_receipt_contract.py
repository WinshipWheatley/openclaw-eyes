import json
from pathlib import Path

import tool_adapter_receipt_contract as contract
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_tool_adapter_receipt_contract import main as export_main


FIXED_NOW = "2026-05-22T08:15:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_repo(root: Path) -> None:
    read_models = root / "generated" / "read_models"
    fixtures = {
        "agent_platform_alignment.json": {
            "schema_version": "agent_platform_alignment_v0",
            "read_model_id": "agent_platform_alignment",
        },
        "agent_identity_actor_router_contract.json": {
            "schema_version": "agent_identity_actor_router_contract_v0",
            "read_model_id": "agent_identity_actor_router_contract",
        },
        "model_selection_policy_contract.json": {
            "schema_version": "model_selection_policy_contract_v0",
            "read_model_id": "model_selection_policy_contract",
        },
        "model_selection_receipt_contract.json": {
            "schema_version": "model_selection_receipt_contract_v0",
            "read_model_id": "model_selection_receipt_contract",
        },
        "agent_package_preview_contract.json": {
            "schema_version": "agent_package_preview_contract_v0",
            "read_model_id": "agent_package_preview_contract",
        },
        "package_preview_receipt_contract.json": {
            "schema_version": "package_preview_receipt_contract_v0",
            "read_model_id": "package_preview_receipt_contract",
        },
        "agent_memory_scope_contract.json": {
            "schema_version": "agent_memory_scope_contract_v0",
            "read_model_id": "agent_memory_scope_contract",
        },
        "memory_candidate_receipt_contract.json": {
            "schema_version": "memory_candidate_receipt_contract_v0",
            "read_model_id": "memory_candidate_receipt_contract",
        },
        "tool_protocol_adapter_registry_contract.json": {
            "schema_version": "tool_protocol_adapter_registry_contract_v0",
            "read_model_id": "tool_protocol_adapter_registry_contract",
        },
        "agent_terrain_awareness_readback_contract.json": {
            "schema_version": "agent_terrain_awareness_readback_contract_v0",
            "read_model_id": "agent_terrain_awareness_readback_contract",
        },
        "openclaw_map_manifest.json": {
            "schema_version": "openclaw_map_manifest_v0",
            "read_model_id": "openclaw_map_manifest",
            "map_generation_id": "map_fixture",
            "bundle_hash": "sha256:fixture",
        },
        "operator_threshold_map_contract.json": {
            "schema_version": "operator_threshold_map_contract_v0",
            "read_model_id": "operator_threshold_map_contract",
        },
    }
    for name, payload in fixtures.items():
        _write_json(read_models / name, payload)


def _build(tmp_path: Path) -> dict:
    _fixture_repo(tmp_path)
    return contract.build_tool_adapter_receipt_contract(repo_root=tmp_path, generated_at=FIXED_NOW)


def _examples(payload: dict) -> dict:
    return {item["example_id"]: item for item in payload["example_tool_adapter_receipts"]}


def _capabilities(payload: dict) -> dict:
    return {item["capability_class"]: item for item in payload["capability_classes"]}


def test_contract_is_deterministic_and_metadata_only(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.SCHEMA_VERSION
    assert first["read_model_id"] == "tool_adapter_receipt_contract"
    assert first["contract_status"] == "deterministic_tool_adapter_receipt_metadata_only"
    assert first["runtime_authority"] is False
    assert first["tool_execution_authority"] is False
    assert first["live_tool_execution"] is False
    assert first["model_call_authority"] is False
    assert first["model_api_execution_authority"] is False
    assert first["model_router_runtime_authority"] is False
    assert first["actor_agent_activation_authority"] is False
    assert first["browser_oauth_account_access_enabled"] is False
    assert first["gmail_calendar_coupa_telegram_enabled"] is False
    assert first["credential_authority"] is False
    assert first["send_submit_approval_enabled"] is False
    assert first["queue_autonomy_execution_enabled"] is False
    assert first["planner_builder_execution_enabled"] is False
    assert first["runtime_daemon_enabled"] is False
    assert first["arbitrary_command_execution_enabled"] is False
    assert first["network_operation_enabled"] is False
    assert first["file_mutation_authority"] is False
    assert first["repo_b_mutation_enabled"] is False
    assert first["mission_control_app_authority_added"] is False
    assert first["mac_sync_or_import_triggered"] is False
    assert first["pc_c_drive_artifact_write_allowed"] is False
    assert first["operator_final_authority"] is True


def test_core_doctrine_prevents_adapter_authority(tmp_path):
    doctrine = _build(tmp_path)["core_doctrine"]

    assert doctrine["tools_protocol_adapters_are_not_authority_by_themselves"] is True
    assert doctrine["adapter_may_not_self_authorize"] is True
    assert doctrine["actor_may_not_grant_itself_tool"] is True
    assert doctrine["package_preview_is_required_before_future_adapter_use"] is True
    assert doctrine["tool_adapter_receipt_does_not_perform_tool_execution"] is True


def test_receipt_types_states_capability_classes_and_schema_are_explicit(tmp_path):
    payload = _build(tmp_path)
    schema = payload["tool_adapter_receipt_schema"]

    assert [item["receipt_type"] for item in payload["receipt_types"]] == list(contract.RECEIPT_TYPES)
    assert [item["receipt_state"] for item in payload["receipt_states"]] == list(contract.RECEIPT_STATES)
    assert [item["capability_class"] for item in payload["capability_classes"]] == list(contract.CAPABILITY_CLASSES)
    assert all(item["tool_execution_allowed"] is False for item in payload["receipt_types"])
    assert all(item["runtime_execution_allowed"] is False for item in payload["receipt_states"])
    assert payload["receipt_states"][contract.RECEIPT_STATES.index("ADAPTER_ALLOWED_READ_ONLY")]["read_only_state"] is True
    assert schema["required_fields"] == list(contract.RECEIPT_FIELDS)
    assert schema["hard_defaults"]["raw_body_included"] is False
    assert schema["hard_defaults"]["credential_material_present"] is False
    assert schema["hard_defaults"]["account_access_allowed"] is False
    assert schema["hard_defaults"]["network_allowed"] is False
    assert schema["hard_defaults"]["browser_session_allowed"] is False
    assert schema["hard_defaults"]["send_submit_approval_allowed"] is False
    assert schema["hard_defaults"]["file_write_allowed"] is False
    assert schema["hard_defaults"]["command_execution_allowed"] is False
    assert schema["hard_defaults"]["runtime_dispatch_allowed"] is False
    assert schema["hard_defaults"]["tool_execution_performed"] is False
    assert schema["hard_defaults"]["model_call_performed"] is False
    assert schema["hard_defaults"]["agent_activation_performed"] is False
    assert schema["hard_defaults"]["queue_execution_performed"] is False
    assert schema["missing_or_unknown_result"] == "ADAPTER_UNKNOWN_FAIL_CLOSED_RECEIPT"
    for field in [
        "tool_adapter_receipt_id",
        "adapter_id",
        "adapter_registry_reference",
        "package_preview_receipt_reference",
        "actor_id",
        "model_selection_receipt_reference",
        "memory_scope_reference",
        "capability_class_requested",
        "capability_class_granted",
        "capability_class_blocked",
        "account_access_allowed",
        "network_allowed",
        "tool_execution_performed",
        "receipt_hash",
    ]:
        assert field in schema["required_fields"]


def test_capability_class_policy_blocks_high_risk_authority(tmp_path):
    capabilities = _capabilities(_build(tmp_path))

    assert capabilities["READ_METADATA"]["blocked_now"] is False
    assert capabilities["READ_METADATA"]["future_gated"] is False
    assert capabilities["RECEIPT_WRITE"]["blocked_now"] is False
    assert capabilities["RECEIPT_WRITE"]["future_gated"] is False
    assert capabilities["MEMORY_CANDIDATE_WRITE"]["current_authority_posture"] == "candidate_only_not_canonical"
    assert capabilities["MEMORY_CANDIDATE_WRITE"]["future_gated"] is True
    assert capabilities["MEMORY_CANDIDATE_WRITE"]["operator_approval_required"] is True
    for high_risk in [
        "READ_RAW_CONTENT",
        "WRITE_LOCAL_FILE",
        "RUN_TEST",
        "RUN_BUILD",
        "RUN_SCRIPT",
        "SEND_MESSAGE",
        "SUBMIT_FORM",
        "APPROVE_ACTION",
        "MUTATE_ACCOUNT",
        "BROWSER_SESSION",
        "NETWORK_API",
        "MODEL_CALL",
        "AGENT_LAUNCH",
        "QUEUE_EXECUTION",
        "CANONICAL_MEMORY_PROMOTION",
    ]:
        policy = capabilities[high_risk]
        assert policy["blocked_now"] is True
        assert policy["future_gated"] is True
        assert policy["operator_approval_required"] is True
        assert policy["security_audit_required"] is True
        assert policy["receipt_required"] is True


def test_binding_requirements_and_current_authority_matrix_are_fail_closed(tmp_path):
    payload = _build(tmp_path)
    binding = payload["adapter_binding_requirements"]
    matrix = payload["current_authority_matrix"]

    assert "adapter exists in Tool Protocol Adapter Registry" in binding["valid_only_if"]
    assert "package preview receipt exists or package preview is explicitly marked missing" in binding["valid_only_if"]
    assert "model selection is checked" in binding["valid_only_if"]
    assert "memory scope is checked" in binding["valid_only_if"]
    assert "output receipt shape exists" in binding["valid_only_if"]
    assert binding["fail_closed_reasons"] == list(contract.BINDING_FAIL_CLOSED_REASONS)
    assert binding["unknown_adapter_result"] == "ADAPTER_UNKNOWN_FAIL_CLOSED_RECEIPT"
    assert binding["adapter_self_authorization_allowed"] is False
    for allowed in [
        "stable map bundle readback",
        "generated read-model inspection",
        "deterministic contract export metadata",
        "package preview display",
        "receipt metadata generation",
        "static validation",
        "forbidden-authority scans",
        "proof/reference display",
    ]:
        assert allowed in matrix["allowed_now"]
    for blocked in [
        "live browser/OAuth/account flows",
        "Gmail/calendar/Coupa/Telegram access",
        "credentials/tokens/cookies/API keys",
        "autonomous sends/submits/approvals",
        "live model calls from OpenClaw runtime",
        "agent launch/runtime daemon",
        "planner/builder execution",
        "queue/autonomy execution",
        "arbitrary shell execution",
        "broad filesystem indexing",
        "raw private body ingestion",
        "external retained memory",
        "C-drive artifact writes",
        "file delete/move authority",
        "broad repair/remount authority",
    ]:
        assert blocked in matrix["blocked_now"]


def test_examples_cover_required_adapter_receipts(tmp_path):
    examples = _examples(_build(tmp_path))

    assert set(examples) == {
        "stable_map_bundle_reader",
        "package_preview_exporter",
        "codex_scoped_build_verifier",
        "cassandra_capital_hilton_invoice_proof_adapter",
        "guardian_protected_access_gate",
        "chief_test_harness_adapter",
        "browser_oauth_adapter",
        "gmail_calendar_adapter",
        "coupa_adapter",
        "telegram_adapter",
        "repo_b_planner_builder_adapter",
        "memory_candidate_receipt_writer",
    }
    stable_map = examples["stable_map_bundle_reader"]
    assert stable_map["adapter_state"] == "ACTIVE_READ_ONLY"
    assert stable_map["capability_class_requested"] == "READ_METADATA"
    assert stable_map["capability_class_granted"] == "READ_METADATA"
    assert "map proof receipt" in stable_map["output_refs_expected"]
    package_exporter = examples["package_preview_exporter"]
    assert package_exporter["receipt_type"] == "ADAPTER_ALLOWED_PREVIEW_ONLY_RECEIPT"
    assert package_exporter["capability_class_granted"] == "RECEIPT_WRITE"
    codex = examples["codex_scoped_build_verifier"]
    assert codex["capability_class_blocked"] == "RUN_TEST"
    assert codex["command_execution_requested"] is True
    cassandra = examples["cassandra_capital_hilton_invoice_proof_adapter"]
    assert cassandra["sensitivity"] == "FINANCE_PROTECTED"
    assert cassandra["guardian_gate_status"] == "required"
    assert cassandra["account_access_requested"] is True
    guardian = examples["guardian_protected_access_gate"]
    assert guardian["guardian_gate_status"] == "Guardian_is_gate_not_self_authorizer"
    chief = examples["chief_test_harness_adapter"]
    assert chief["capability_class_blocked"] == "RUN_TEST"
    browser = examples["browser_oauth_adapter"]
    assert browser["network_requested"] is True
    assert browser["browser_session_requested"] is True
    assert browser["account_access_requested"] is True
    gmail = examples["gmail_calendar_adapter"]
    assert gmail["send_submit_approval_requested"] is True
    coupa = examples["coupa_adapter"]
    assert "CREDENTIAL_MATERIAL_BLOCKED" in coupa["blocked_reasons"]
    telegram = examples["telegram_adapter"]
    assert telegram["capability_class_blocked"] == "SEND_MESSAGE"
    repo_b = examples["repo_b_planner_builder_adapter"]
    assert repo_b["capability_class_blocked"] == "QUEUE_EXECUTION"
    memory = examples["memory_candidate_receipt_writer"]
    assert memory["capability_class_granted"] == "MEMORY_CANDIDATE_WRITE"
    assert "canonical memory promotion" in memory["current_blocked_actions"]
    for example in examples.values():
        assert example["raw_body_included"] is False
        assert example["credential_material_present"] is False
        assert example["account_access_allowed"] is False
        assert example["network_allowed"] is False
        assert example["browser_session_allowed"] is False
        assert example["send_submit_approval_allowed"] is False
        assert example["file_write_allowed"] is False
        assert example["command_execution_allowed"] is False
        assert example["runtime_dispatch_allowed"] is False
        assert example["tool_execution_performed"] is False
        assert example["model_call_performed"] is False
        assert example["agent_activation_performed"] is False
        assert example["queue_execution_performed"] is False
        assert example["tool_or_protocol_execution_authorized"] is False


def test_receipt_quarantine_and_revocation_policy_is_explicit(tmp_path):
    policy = _build(tmp_path)["receipt_quarantine_revocation_policy"]

    for trigger in [
        "adapter claims authority it does not have",
        "adapter references unknown registry entry",
        "adapter skips package preview receipt",
        "adapter skips model selection receipt",
        "adapter skips memory scope",
        "adapter includes raw private body",
        "adapter includes credentials/secrets/tokens/cookies",
        "adapter attempts browser/account/network access without gate",
        "adapter attempts send/submit/approval",
        "adapter attempts command execution or runtime activation",
        "adapter output contradicts proof",
        "adapter receipt malformed",
        "receipt hash missing",
        "sensitive data leak",
        "failed Guardian gate",
        "failed Operator gate",
        "external retained memory detected",
        "broad filesystem indexing attempted",
    ]:
        assert trigger in policy["quarantine_triggers"]
    for trigger in [
        "adapter registry state changed",
        "tool adapter quarantined",
        "package preview revoked",
        "model selection revoked",
        "memory candidate revoked",
        "Guardian gate revoked",
        "Operator approval revoked",
        "security audit blocks adapter",
        "receipt conflict discovered",
        "provider/tool route becomes unavailable",
    ]:
        assert trigger in policy["revocation_triggers"]
    assert policy["missing_or_malformed_receipt_result"] == "ADAPTER_QUARANTINED_RECEIPT"
    assert policy["quarantine_is_non_destructive"] is True
    assert policy["revocation_blocks_future_adapter_use"] is True


def test_evidence_sources_are_bounded_and_source_presence_grants_no_authority(tmp_path):
    payload = _build(tmp_path)

    assert {item["source_id"] for item in payload["evidence_sources"]} == {
        "agent_platform_alignment",
        "agent_identity_actor_router_contract",
        "model_selection_policy_contract",
        "model_selection_receipt_contract",
        "agent_package_preview_contract",
        "package_preview_receipt_contract",
        "agent_memory_scope_contract",
        "memory_candidate_receipt_contract",
        "tool_protocol_adapter_registry_contract",
        "agent_terrain_awareness_readback_contract",
        "stable_map_bundle",
        "operator_threshold_map_contract",
    }
    assert all(item["present"] is True for item in payload["evidence_sources"])
    assert all(item["raw_private_body_imported"] is False for item in payload["evidence_sources"])
    assert all(item["credentials_or_secrets_imported"] is False for item in payload["evidence_sources"])
    assert all(item["authority_granted_by_source_presence"] is False for item in payload["evidence_sources"])


def test_mission_control_and_stable_map_guidance_remain_read_only(tmp_path):
    payload = _build(tmp_path)
    guidance = payload["mission_control_surface_guidance"]
    stable_map = payload["stable_map_integration"]

    for hidden in [
        "live tool execution controls",
        "browser/OAuth launch controls",
        "Gmail/calendar/Coupa/Telegram controls",
        "credential prompts",
        "account controls",
        "send/submit/approval controls",
        "arbitrary command execution controls",
        "raw private context",
        "hidden routing",
        "adapter authorized itself claims",
    ]:
        assert hidden in guidance["hide_or_block"]
    assert "adapter name" in guidance["tool_adapter_receipt_card"]
    assert "requested adapters" in guidance["package_preview_tool_section"]
    assert "tool adapter summary" in guidance["agent_dossier_integration"]
    assert stable_map["contract_generated_as_read_model"] is True
    assert stable_map["summary_included_in_stable_map_bundle_now"] is False
    assert stable_map["safe_summary_to_include_next"]["contract_id"] == "tool_adapter_receipt_contract"
    assert stable_map["safe_summary_to_include_next"]["receipt_types_count"] == len(contract.RECEIPT_TYPES)
    assert stable_map["safe_summary_to_include_next"]["adapter_examples_count"] == 12
    assert stable_map["safe_summary_to_include_next"]["live_execution_authority"] is False


def test_recommended_next_lanes_are_ordered(tmp_path):
    lanes = _build(tmp_path)["recommended_next_lanes"]

    assert [lane["lane_id"] for lane in lanes] == [
        "package_preview_surface_mission_control_integration_v0",
        "memory_review_promotion_surface_v0",
        "capital_hilton_proof_metadata_packet_v0",
        "tool_adapter_receipt_surface_v0",
        "model_router_implementation_plan_v0",
    ]
    assert lanes[0]["title"] == "Package Preview Surface / Mission Control Integration v0"
    assert lanes[0]["hard_boundary"] == "Mac read-only UI; no dispatch controls"


def test_export_script_writes_json_and_operator_outputs(tmp_path, capsys):
    _fixture_repo(tmp_path)
    export_root = tmp_path / "generated" / "read_models"

    assert export_main(["--repo-root", tmp_path.as_posix(), "--export-root", export_root.as_posix(), "--format", "summary"]) == 0

    summary = json.loads(capsys.readouterr().out)
    assert summary["schema_version"] == contract.SCHEMA_VERSION
    assert summary["receipt_type_count"] == len(contract.RECEIPT_TYPES)
    assert summary["receipt_state_count"] == len(contract.RECEIPT_STATES)
    assert summary["capability_class_count"] == len(contract.CAPABILITY_CLASSES)
    assert summary["example_count"] == 12
    assert summary["live_tool_execution_added"] is False
    json_path = export_root / contract.JSON_EXPORT_NAME
    operator_path = export_root / contract.OPERATOR_EXPORT_NAME
    assert json_path.is_file()
    assert operator_path.is_file()
    exported = json.loads(json_path.read_text(encoding="utf-8"))
    assert exported["read_model_id"] == "tool_adapter_receipt_contract"
    assert exported["machine_proof"]["content_hash"].startswith("sha256:")
    operator_text = operator_path.read_text(encoding="utf-8")
    assert "Tool Adapter Receipt Contract v0" in operator_text
    assert "ADAPTER_ALLOWED_READ_ONLY" in operator_text


def test_generated_outputs_are_safe_canonical_read_model_files(tmp_path, capsys):
    _fixture_repo(tmp_path)
    export_root = tmp_path / "generated" / "read_models"

    assert export_main(["--repo-root", tmp_path.as_posix(), "--export-root", export_root.as_posix(), "--format", "summary"]) == 0
    capsys.readouterr()

    expected = canonical_generated_read_model_expected_files(export_root, repo_root=tmp_path)
    assert contract.JSON_EXPORT_NAME in expected
    assert contract.OPERATOR_EXPORT_NAME in expected


def test_contract_source_avoids_runtime_and_destructive_implementation_patterns():
    source = Path(contract.__file__).read_text(encoding="utf-8").lower()

    for forbidden in [
        "subprocess",
        "os.system",
        "shell=true",
        "requests.",
        "httpx.",
        "urllib.request",
        ".unlink(",
        "shutil.rmtree",
        "shutil.move",
        "/mnt/" + "c/",
        "file:///" + "c:",
    ]:
        assert forbidden not in source
