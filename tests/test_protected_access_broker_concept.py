import ast
import json
from pathlib import Path

import protected_access_broker_concept as concept
from generated_read_model_files import canonical_generated_read_model_expected_files
from scripts.export_protected_access_broker_concept import main as export_main


FIXED_NOW = "2026-05-19T02:00:00+00:00"


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_repo(root: Path) -> None:
    fixtures = {
        "generated/read_models/chief_status_rail.json": {
            "schema_version": "chief_status_rail_v0",
            "rail_status": "completed_visibility_planning_only",
        },
        "generated/read_models/build_now_vs_hold_queue_posture.json": {
            "schema_version": "build_now_vs_hold_queue_posture_v0",
            "posture_scope": "visibility_routing_work_packet_posture_only",
            "chief_status_precondition": {"satisfied": True},
        },
        "generated/read_models/repo_b_remaining_capability_delta_map.json": {
            "schema_version": "repo_b_remaining_capability_delta_map_v0",
            "repo_b_reference_only": True,
            "repo_b_code_executed": False,
            "credential_or_oauth_accessed": False,
        },
        "generated/read_models/operator_sovereignty_power_stage_gate.json": {
            "schema_version": "operator_sovereignty_power_stage_gate_read_model_v0",
            "current_power_stage": {
                "current_power_stage_id": "stage_1_visibility_read_model_review_packet",
                "classification": "Stage 1 current; Stage 2 pieces modeled; Stages 3-5 blocked.",
            },
            "stage_3_blocked_without_protected_pii_broker_controls": True,
            "stage_4_blocked_without_hard_stop_and_tamper_controls": True,
        },
        "generated/read_models/guardian_responsibility_dna_audit.json": {
            "schema_version": "guardian_responsibility_dna_audit_v0",
            "guardian_modeled_as_executor": False,
        },
        "generated/read_models/guardian_draft_approval_request_contract.json": {
            "schema_version": "guardian_draft_approval_request_contract_v0",
            "approval_request_created": False,
        },
        "generated/read_models/capital_hilton_external_artifact_proof_capture.json": {
            "schema_version": "capital_hilton_external_artifact_proof_capture_v0",
            "capture_mode": "operator_supplied_safe_metadata_only",
        },
        "generated/read_models/capital_hilton_operator_proof_input_packet.json": {
            "schema_version": "capital_hilton_operator_proof_input_packet_v0",
            "template_only": True,
        },
        "generated/read_models/capital_hilton_coupa_execution_path.json": {
            "schema_version": "capital_hilton_coupa_execution_path_v0",
            "coupa_submit_enabled": False,
        },
        "generated/read_models/capital_hilton_send_approval_gate.json": {
            "schema_version": "capital_hilton_send_approval_gate_v0",
            "send_approval_executable": False,
        },
        "generated/read_models/cassandra_email_calendar_capability_reconciliation.json": {
            "schema_version": "cassandra_email_calendar_capability_reconciliation_v0",
            "oauth_or_credentials_accessed": False,
            "email_send_enabled": False,
            "calendar_mutation_enabled": False,
        },
        "generated/read_models/tool_inventory.json": {
            "schema_version": "tool_inventory_read_model_v0",
        },
        "generated/read_models/tool_intake.json": {
            "schema_version": "tool_intake_read_model_v0",
        },
    }
    for rel, payload in fixtures.items():
        _write(root / rel, payload)


def _build(tmp_path: Path) -> dict:
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)
    return concept.build_protected_access_broker_concept(repo_root=repo, generated_at=FIXED_NOW)


def _surface(payload: dict, surface_id: str) -> dict:
    return next(item for item in payload["protected_access_surfaces"] if item["surface_id"] == surface_id)


def test_preconditions_are_checked_and_satisfied(tmp_path):
    payload = _build(tmp_path)

    assert payload["preconditions"]["chief_status_rail_completion_v0_satisfied"] is True
    assert payload["preconditions"]["build_now_vs_hold_queue_posture_v0_satisfied"] is True
    assert payload["preconditions"]["all_preconditions_satisfied"] is True


def test_credentials_tokens_oauth_and_tool_bridges_are_blocked(tmp_path):
    payload = _build(tmp_path)
    oauth = _surface(payload, "oauth_tool_bridges")
    client_credentials = _surface(payload, "client_company_credentials")

    assert oauth["primary_classification"] == "UNSAFE_OR_BLOCKED"
    assert "REQUIRES_SECURITY_THRESHOLD" in oauth["policy_classifications"]
    assert oauth["live_access_status"] == "oauth_tool_bridge_blocked"
    assert "OAuth client secret" in oauth["forbidden_raw_values"]
    assert client_credentials["primary_classification"] == "NORMAL_READ_MODEL_FORBIDDEN"
    assert client_credentials["agent_direct_access_allowed"] is False
    assert payload["oauth_access_enabled"] is False
    assert payload["tokens_or_secrets_accessed"] is False


def test_raw_pii_private_documents_are_forbidden_in_normal_read_models(tmp_path):
    payload = _build(tmp_path)
    forbidden = payload["normal_read_model_forbidden_values"]
    finance_private = _surface(payload, "bank_remit_home_address_check_images")

    for value in (
        "raw passwords",
        "raw OAuth client secrets or refresh tokens",
        "bank account or routing details",
        "home address",
        "check images or deposit images",
        "raw PDF bodies",
        "raw Excel workbook bodies",
        "private legal/client documents",
    ):
        assert value in forbidden
    assert finance_private["primary_classification"] == "NORMAL_READ_MODEL_FORBIDDEN"
    assert payload["normal_read_model_forbids_raw_pii_private_docs"] is True
    assert payload["raw_secret_or_pii_stored"] is False
    assert payload["raw_private_document_stored"] is False


def test_protected_references_and_metadata_are_allowed_only_in_safe_form(tmp_path):
    payload = _build(tmp_path)
    coupa = _surface(payload, "capital_hilton_coupa_payment_invoice_proof")
    excel = _surface(payload, "capital_hilton_excel_pdf_invoice_artifacts")

    assert coupa["primary_classification"] == "PROTECTED_REFERENCE_ALLOWED"
    assert excel["primary_classification"] == "PROTECTED_REFERENCE_ALLOWED"
    assert "protected_artifact_reference" in coupa["safe_metadata_or_reference_allowed"]
    assert "artifact_identity_or_hash" in excel["safe_metadata_or_reference_allowed"]
    assert "raw PDF body" in coupa["forbidden_raw_values"]
    assert "raw Excel workbook body" in excel["forbidden_raw_values"]
    assert payload["protected_references_allowed_only_in_safe_metadata_form"] is True


def test_guardian_and_security_threshold_remain_required_for_live_access(tmp_path):
    payload = _build(tmp_path)

    for surface in payload["protected_access_surfaces"]:
        if surface["surface_id"] != "unknown_sensitive_surface":
            assert surface["guardian_gate_required_for_live_access"] is True
            assert surface["security_threshold_required_for_live_access"] is True
    assert payload["guardian_gate_required_for_live_sensitive_access"] is True
    assert payload["security_threshold_required_for_live_access"] is True
    assert payload["current_stage_evidence"]["stage_3_blocked_without_protected_pii_broker_controls"] is True
    assert payload["current_stage_evidence"]["stage_4_blocked_without_hard_stop_and_tamper_controls"] is True


def test_agents_do_not_receive_direct_credentials_or_account_authority(tmp_path):
    payload = _build(tmp_path)

    assert payload["agent_boundary"]["agents_receive_direct_credentials"] is False
    assert payload["agent_boundary"]["agents_may_use_oauth_or_tokens_directly"] is False
    assert payload["agents_receive_direct_credentials"] is False
    assert all(surface["agent_direct_access_allowed"] is False for surface in payload["protected_access_surfaces"])


def test_browser_tool_and_unknown_surfaces_fail_closed(tmp_path):
    payload = _build(tmp_path)
    browser = _surface(payload, "browser_automation")
    unknown = _surface(payload, "unknown_sensitive_surface")

    assert browser["primary_classification"] == "REQUIRES_SECURITY_THRESHOLD"
    assert browser["live_access_status"] == "browser_automation_blocked"
    assert "LIVE_ACCESS_BLOCKED" in browser["policy_classifications"]
    assert unknown["primary_classification"] == "UNKNOWN_FAIL_CLOSED"
    assert unknown["unknown_or_ambiguous_access_fails_closed"] is True
    assert payload["unknown_access_surfaces_fail_closed"] is True


def test_eli5_summary_exists_and_next_lanes_are_bounded(tmp_path):
    payload = _build(tmp_path)
    eli5 = payload["operator_eli5_summary"]

    assert "may remember that a sensitive thing exists" in eli5["here_is_what_protected_access_means"]
    assert "Metadata" in eli5["what_openclaw_can_safely_track_now"]
    assert "Passwords" in eli5["what_must_stay_out_of_normal_read_models"]
    assert len(eli5["next_1_to_3_sensible_lanes"]) == 3
    assert payload["next_recommended_lane"] == "Protected Evidence Reference Receipt v0"


def test_no_live_execution_access_or_authority_is_enabled(tmp_path):
    payload = _build(tmp_path)

    for key, expected in concept.NO_AUTHORITY_FLAGS.items():
        assert payload[key] is expected
        assert payload["no_authority_flags"][key] is expected
    assert payload["live_access_blocked"] is True
    assert payload["credentials_enabled"] is False
    assert payload["gmail_calendar_coupa_accessed"] is False
    assert payload["browser_automation_added"] is False
    assert payload["runtime_authority_added"] is False


def test_repo_b_is_used_only_through_existing_repo_a_delta_read_model(tmp_path):
    payload = _build(tmp_path)

    assert payload["repo_b_delta_reference"]["used_existing_repo_a_delta_read_model_only"] is True
    assert payload["repo_b_delta_reference"]["repo_b_filesystem_inspected"] is False
    assert payload["repo_b_delta_reference"]["repo_b_code_executed"] is False
    assert payload["repo_b_filesystem_inspected"] is False
    assert payload["repo_b_code_executed"] is False


def test_generated_read_model_is_deterministic_exportable_and_safe_mirror_candidate(tmp_path, capsys):
    repo = tmp_path / "repo_a"
    _fixture_repo(repo)

    first = concept.build_protected_access_broker_concept(repo_root=repo, generated_at=FIXED_NOW)
    second = concept.build_protected_access_broker_concept(repo_root=repo, generated_at=FIXED_NOW)
    assert concept.stable_json(first) == concept.stable_json(second)

    exit_code = export_main(["--repo-root", str(repo), "--export-root", "generated/read_models", "--format", "operator"])
    operator_text = capsys.readouterr().out
    payload = json.loads((repo / "generated/read_models" / concept.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    expected = set(canonical_generated_read_model_expected_files(source_root=repo / "generated/read_models", repo_root=repo))

    assert exit_code == 0
    assert "Protected Access Broker Concept" in operator_text
    assert payload["schema_version"] == concept.SCHEMA_VERSION
    assert concept.JSON_EXPORT_NAME in expected
    assert concept.OPERATOR_EXPORT_NAME in expected


def test_source_does_not_import_live_brokers_or_execute_network_browser_or_repo_b():
    source_files = [
        Path("protected_access_broker_concept.py"),
        Path("scripts/export_protected_access_broker_concept.py"),
    ]
    forbidden_text = [
        "/home/openclaw_external/openclaw-runtime",
        "subprocess.",
        "os.system",
        "asyncio.",
        "requests.",
        "httpx.",
        "urllib.request",
        "selenium",
        "playwright",
        "pyautogui",
        "smtplib",
        "InstalledAppFlow",
        "build(\"gmail\"",
        "build(\"calendar\"",
        "send_message(",
        "reply_text(",
        "send_email(",
        "import google_access_broker",
        "from google_access_broker",
    ]
    for path in source_files:
        text = path.read_text(encoding="utf-8")
        for needle in forbidden_text:
            assert needle not in text
        tree = ast.parse(text)
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported.update(
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        assert "subprocess" not in imported
        assert "requests" not in imported
        assert "httpx" not in imported
        assert "google_access_broker" not in imported
