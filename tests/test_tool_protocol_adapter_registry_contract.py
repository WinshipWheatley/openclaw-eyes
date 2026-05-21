import json
from pathlib import Path

import tool_protocol_adapter_registry_contract as contract
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_tool_protocol_adapter_registry_contract import main as export_main


FIXED_NOW = "2026-05-22T02:30:00+00:00"


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
        "agent_package_preview_contract.json": {
            "schema_version": "agent_package_preview_contract_v0",
            "read_model_id": "agent_package_preview_contract",
        },
        "agent_memory_scope_contract.json": {
            "schema_version": "agent_memory_scope_contract_v0",
            "read_model_id": "agent_memory_scope_contract",
        },
        "package_compiler_contract.json": {
            "schema_version": "package_compiler_contract_v0",
            "read_model_id": "package_compiler_contract",
        },
        "capability_skill_registry_metadata_delta.json": {
            "schema_version": "capability_skill_registry_metadata_delta_v0",
            "read_model_id": "capability_skill_registry_metadata_delta",
        },
        "guardian_protected_access_gate_spec.json": {
            "schema_version": "guardian_protected_access_gate_spec_v0",
            "read_model_id": "guardian_protected_access_gate_spec",
        },
        "protected_evidence_reference_receipt.json": {
            "schema_version": "protected_evidence_reference_receipt_v0",
            "read_model_id": "protected_evidence_reference_receipt",
        },
        "operator_map_bundle_contract.json": {
            "schema_version": "operator_map_bundle_contract_v0",
            "read_model_id": "operator_map_bundle_contract",
        },
    }
    for name, payload in fixtures.items():
        _write_json(read_models / name, payload)


def _build(tmp_path: Path) -> dict:
    _fixture_repo(tmp_path)
    return contract.build_tool_protocol_adapter_registry_contract(repo_root=tmp_path, generated_at=FIXED_NOW)


def _adapters(payload: dict) -> dict:
    return {item["adapter_id"]: item for item in payload["adapters"]}


def _actors(payload: dict) -> dict:
    return {item["actor_id"]: item for item in payload["actor_to_adapter_rules"]}


def _capabilities(payload: dict) -> dict:
    return {item["capability_class"]: item for item in payload["capability_classes"]}


def test_contract_is_deterministic_and_metadata_only(tmp_path):
    first = _build(tmp_path)
    second = _build(tmp_path)

    assert contract.stable_json(first) == contract.stable_json(second)
    assert first["schema_version"] == contract.SCHEMA_VERSION
    assert first["read_model_id"] == "tool_protocol_adapter_registry_contract"
    assert first["contract_status"] == "deterministic_tool_protocol_adapter_registry_metadata_only"
    assert first["runtime_authority"] is False
    assert first["tool_execution_authority"] is False
    assert first["external_tool_authority"] is False
    assert first["model_call_authority"] is False
    assert first["agent_call_authority"] is False
    assert first["browser_oauth_account_access_enabled"] is False
    assert first["gmail_calendar_coupa_telegram_enabled"] is False
    assert first["credential_authority"] is False
    assert first["operator_final_authority"] is True


def test_adapter_categories_states_and_capability_classes_are_explicit(tmp_path):
    payload = _build(tmp_path)
    states = payload["adapter_state_model"]
    caps = _capabilities(payload)

    assert [item["category_id"] for item in payload["adapter_categories"]] == list(contract.ADAPTER_CATEGORIES)
    assert states["allowed_states"] == list(contract.ADAPTER_STATES)
    assert states["unknown_adapter_result"] == "UNKNOWN_FAIL_CLOSED"
    assert states["adapter_may_self_authorize"] is False
    assert states["actor_may_self_grant_tool"] is False
    assert set(caps) == set(contract.CAPABILITY_CLASSES)
    assert caps["READ_METADATA"]["current_authority_status"] == "allowed_for_deterministic_refs_only"
    assert caps["READ_RAW_CONTENT"]["current_authority_status"] == "blocked_now"
    assert caps["BROWSER_SESSION"]["current_authority_status"] == "blocked_now"
    assert caps["MODEL_CALL"]["current_authority_status"] == "blocked_now"
    assert caps["QUEUE_EXECUTION"]["current_authority_status"] == "post_security_future_gated"
    assert caps["CANONICAL_MEMORY_PROMOTION"]["current_authority_status"] == "blocked_now"


def test_current_authority_matrix_allows_only_bounded_metadata_and_validation(tmp_path):
    payload = _build(tmp_path)
    matrix = payload["current_authority_matrix"]

    for allowed in [
        "read-model inspection",
        "stable map inspection",
        "deterministic package preview",
        "contract export",
        "focused test/build verification in bounded worker tasks",
        "receipt-only metadata generation",
        "static validation",
        "forbidden-authority scans",
        "proof/reference display",
    ]:
        assert allowed in matrix["allowed_now"]
    for blocked in [
        "live browser/OAuth/account flows",
        "Gmail/calendar/Coupa/Telegram access",
        "credentials/tokens/cookies",
        "autonomous sends/submits/approvals",
        "live model calls from OpenClaw runtime",
        "agent launch/runtime daemon",
        "planner/builder execution",
        "queue/autonomy execution",
        "arbitrary shell execution",
        "broad filesystem indexing",
        "raw private body ingestion",
        "external retained memory",
        "hidden monitoring",
        "PC C-drive artifact writes",
        "file delete/move authority",
        "broad repair/remount authority",
    ]:
        assert blocked in matrix["blocked_now"]


def test_required_adapter_examples_are_present_and_non_live(tmp_path):
    payload = _build(tmp_path)
    adapters = _adapters(payload)

    required = {
        "stable_map_bundle_reader",
        "package_preview_exporter",
        "focused_test_runner",
        "bounded_build_verifier",
        "cassandra_capital_hilton_invoice_proof_adapter",
        "guardian_protected_access_gate",
        "chief_test_harness_adapter",
        "browser_oauth_adapter",
        "gmail_calendar_adapter",
        "coupa_adapter",
        "telegram_adapter",
        "repo_b_planner_builder_adapter",
    }
    assert required.issubset(set(adapters))
    assert adapters["stable_map_bundle_reader"]["adapter_state"] == "ACTIVE_READ_ONLY"
    assert adapters["package_preview_exporter"]["adapter_state"] == "ACTIVE_PREVIEW_ONLY"
    assert adapters["cassandra_capital_hilton_invoice_proof_adapter"]["adapter_state"] == "FUTURE_GATED"
    assert adapters["guardian_protected_access_gate"]["adapter_state"] == "RECEIPT_ONLY"
    assert adapters["chief_test_harness_adapter"]["adapter_state"] == "FUTURE_GATED"
    assert adapters["browser_oauth_adapter"]["adapter_state"] == "BLOCKED_NO_AUTHORITY"
    assert adapters["gmail_calendar_adapter"]["adapter_state"] == "BLOCKED_NO_AUTHORITY"
    assert adapters["coupa_adapter"]["adapter_state"] == "BLOCKED_SENSITIVE"
    assert adapters["telegram_adapter"]["adapter_state"] == "BLOCKED_NO_AUTHORITY"
    assert adapters["repo_b_planner_builder_adapter"]["adapter_state"] == "CANDIDATE_UNMAPPED"
    for adapter in adapters.values():
        assert adapter["adapter_may_self_authorize"] is False
        assert adapter["live_execution_enabled_now"] is False
        assert adapter["required_receipts"]
        assert adapter["stop_conditions"]
        assert adapter["quarantine_conditions"]
        assert adapter["revocation_conditions"]


def test_adapter_actor_model_package_references_are_known(tmp_path):
    payload = _build(tmp_path)

    for adapter in payload["adapters"]:
        assert adapter["category"] in contract.ADAPTER_CATEGORIES
        assert adapter["adapter_state"] in contract.ADAPTER_STATES
        assert set(adapter["capability_classes"]).issubset(set(contract.CAPABILITY_CLASSES))
        assert set(adapter["actor_eligibility"]).issubset(set(contract.KNOWN_ACTOR_IDS))
        assert set(adapter["model_class_eligibility"]).issubset(set(contract.MODEL_CLASSES))
        assert set(adapter["package_types_allowed"]).issubset(set(contract.PACKAGE_TYPES))
        assert set(adapter["package_types_blocked"]).issubset(set(contract.PACKAGE_TYPES))


def test_sensitive_external_account_adapters_block_current_use(tmp_path):
    adapters = _adapters(_build(tmp_path))

    for adapter_id in ["browser_oauth_adapter", "gmail_calendar_adapter", "coupa_adapter", "telegram_adapter"]:
        adapter = adapters[adapter_id]
        assert not adapter["current_allowed_actions"]
        assert adapter["required_operator_approval"] is True
        assert adapter["required_guardian_review"] is True
        assert "security_audit" in adapter["required_gates"]
        assert "network_used" in adapter["output_receipt_shape"]
        assert "account_accessed" in adapter["output_receipt_shape"]
        assert "send_submit_approve_performed" in adapter["output_receipt_shape"]
    assert "submit invoice" in adapters["coupa_adapter"]["current_blocked_actions"]
    assert "send/mutate" in adapters["gmail_calendar_adapter"]["current_blocked_actions"]


def test_actor_to_adapter_rules_match_openclaw_actor_boundaries(tmp_path):
    actors = _actors(_build(tmp_path))

    assert set(actors) == set(contract.KNOWN_ACTOR_IDS)
    assert "operator_is_not_a_tool_adapter" in actors["operator_winship"]["blocked_adapter_classes"]
    assert "repair" in actors["chief"]["blocked_adapter_classes"]
    assert "self-authorization" in actors["guardian"]["blocked_adapter_classes"]
    assert "Coupa access" in actors["cassandra"]["blocked_adapter_classes"]
    assert "runtime execution" in actors["hermes"]["blocked_adapter_classes"]
    assert "broad private library ingestion" in actors["niles"]["blocked_adapter_classes"]
    assert "credentials" in actors["codex"]["blocked_adapter_classes"]
    assert "retained memory" in actors["gemini_antigravity"]["blocked_adapter_classes"]
    for rule in actors.values():
        assert rule["can_self_grant_tool"] is False
        assert rule["required_boundary"]


def test_package_binding_fails_closed_when_tool_requirements_are_missing(tmp_path):
    payload = _build(tmp_path)
    binding = payload["package_binding_rule"]

    for requirement in [
        "adapter exists in registry",
        "adapter state allows package use",
        "package type is allowed",
        "actor is eligible",
        "model class is eligible",
        "memory scope permits the context",
        "sensitivity ceiling is not exceeded",
        "Guardian gate passes if required",
        "Operator approval exists if required",
        "receipt requirements are defined",
        "stop conditions are explicit",
    ]:
        assert requirement in binding["package_may_reference_adapter_only_if"]
    assert binding["blocked_statuses"] == list(contract.PACKAGE_TOOL_BLOCK_STATUSES)
    assert binding["natural_language_permission_counts_as_authority"] is False
    assert binding["unknown_adapter_result"] == "TOOL_UNKNOWN_FAIL_CLOSED"


def test_protocol_adapter_doctrine_receipts_and_quarantine_are_bounded(tmp_path):
    payload = _build(tmp_path)
    doctrine = payload["protocol_adapter_doctrine"]
    receipts = payload["tool_receipt_requirements"]
    quarantine = payload["failure_quarantine_policy"]

    assert doctrine["definition"] == "A deterministic wrapper/interface contract, not a live integration."
    assert "input shape" in doctrine["may_define"]
    assert "receipt shape" in doctrine["may_define"]
    assert "live credentials" in doctrine["must_not_define"]
    assert "hidden network calls" in doctrine["must_not_define"]
    assert receipts["future_execution_receipts_required"] is True
    assert receipts["current_execution_receipts_future_gated"] is True
    assert receipts["metadata_receipts_allowed_now_when_schema_exists"] is True
    assert receipts["receipt_cannot_claim_unobserved_execution"] is True
    for field in [
        "receipt_id",
        "adapter_id",
        "package_id",
        "actor",
        "model_class",
        "capability_class_used",
        "network_used",
        "account_accessed",
        "send_submit_approve_performed",
        "receipt_hash",
    ]:
        assert field in receipts["required_fields"]
    assert "tries to use credentials/account/browser" in quarantine["quarantine_when"]
    assert "unexpected network attempt" in quarantine["quarantine_when"]
    assert quarantine["quarantine_is_non_destructive"] is True


def test_mission_control_guidance_and_stable_map_integration_are_non_executing(tmp_path):
    payload = _build(tmp_path)
    guidance = payload["mission_control_surface_guidance"]
    stable = payload["stable_map_integration"]

    assert "active read-only adapters" in guidance["adapter_registry_overview"]
    assert "tools included" in guidance["package_preview_tool_section"]
    assert "what adapters this actor can use now" in guidance["actor_detail"]
    assert "live execute buttons" in guidance["do_not_show"]
    assert "credential prompts" in guidance["do_not_show"]
    assert "Gmail/calendar/Coupa/Telegram live controls" in guidance["do_not_show"]
    assert stable["registry_generated_as_read_model"] is True
    assert stable["summary_included_in_stable_map_bundle_now"] is False
    assert stable["safe_summary_to_include_next"]["contract_id"] == "tool_protocol_adapter_registry_contract"
    assert "memory_candidate_receipt_v0" in stable["safe_summary_to_include_next"]["next_recommended_lane"]


def test_operator_powershell_note_is_captured_without_repair_authority(tmp_path):
    payload = _build(tmp_path)
    notes = {item["note_id"]: item for item in payload["operator_field_notes"]}

    assert "powershell_window_did_not_close" in notes
    note = notes["powershell_window_did_not_close"]
    assert note["source_type"] == "operator_reported_context"
    assert note["action_taken_now"] == "none"
    assert note["authority_added"] is False
    assert "bridge/process lifecycle evidence" in note["summary"]


def test_evidence_sources_are_bounded_and_do_not_grant_authority(tmp_path):
    payload = _build(tmp_path)
    sources = {item["source_id"]: item for item in payload["evidence_sources"]}

    assert sources["agent_platform_alignment"]["present"] is True
    assert sources["agent_identity_actor_router_contract"]["present"] is True
    assert sources["model_selection_policy_contract"]["present"] is True
    assert sources["agent_package_preview_contract"]["present"] is True
    assert sources["agent_memory_scope_contract"]["present"] is True
    assert sources["capability_skill_registry_metadata_delta"]["present"] is True
    assert all(item["raw_private_body_imported"] is False for item in sources.values())
    assert all(item["credentials_or_secrets_imported"] is False for item in sources.values())
    assert all(item["authority_granted_by_source_presence"] is False for item in sources.values())


def test_recommended_next_lanes_match_tool_adapter_maturity_path(tmp_path):
    payload = _build(tmp_path)
    lanes = [item["lane_id"] for item in payload["recommended_next_lanes"]]

    assert lanes == [
        "memory_candidate_receipt_v0",
        "model_selection_receipt_v0",
        "package_preview_receipt_v0",
        "mission_control_package_preview_actor_routing_surface_v0",
    ]


def test_export_script_writes_json_and_operator_outputs(tmp_path, capsys):
    _fixture_repo(tmp_path)
    export_root = tmp_path / "generated" / "read_models"

    exit_code = export_main(
        [
            "--repo-root",
            tmp_path.as_posix(),
            "--export-root",
            export_root.as_posix(),
            "--format",
            "summary",
        ]
    )

    assert exit_code == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["schema_version"] == contract.SCHEMA_VERSION
    assert summary["adapter_count"] >= 20
    assert summary["active_read_only_count"] >= 4
    assert summary["blocked_or_future_gated_count"] >= 8
    assert summary["runtime_authority_added"] is False
    assert summary["tool_execution_authority_added"] is False
    payload = json.loads((export_root / contract.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (export_root / contract.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")
    assert payload["read_model_id"] == "tool_protocol_adapter_registry_contract"
    assert "Tool Protocol Adapter Registry Contract v0" in operator
    assert "browser_oauth_adapter" in operator


def test_generated_outputs_are_canonical_read_model_files(tmp_path):
    _fixture_repo(tmp_path)
    export_root = tmp_path / "generated" / "read_models"
    contract.export_tool_protocol_adapter_registry_contract(
        repo_root=tmp_path,
        export_root=export_root,
        generated_at=FIXED_NOW,
    )

    expected = set(canonical_generated_read_model_expected_files(source_root=export_root, repo_root=tmp_path))

    assert contract.JSON_EXPORT_NAME in expected
    assert contract.OPERATOR_EXPORT_NAME in expected


def test_source_has_no_runtime_network_delete_or_c_drive_authority_strings():
    text = Path("tool_protocol_adapter_registry_contract.py").read_text(encoding="utf-8").lower()
    for token in [
        "subprocess",
        "shell=true",
        "os.system",
        "import requests",
        "httpx.",
        "urllib.request",
        "/mnt/" + "c/openclaw",
        "c:\\openclaw",
        ".unlink(",
        "shutil.rmtree",
        "shutil.move",
    ]:
        assert token not in text
