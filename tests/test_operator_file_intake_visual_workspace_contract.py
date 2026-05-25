import json
import re
from pathlib import Path

import operator_file_intake_visual_workspace_contract as visual
from scripts.export_operator_file_intake_visual_workspace_contract import main as export_main


FIXED_NOW = "2026-05-25T14:00:00+00:00"


def _build() -> dict:
    return visual.build_operator_file_intake_visual_workspace_contract(generated_at=FIXED_NOW)


def test_required_models_exist_and_payload_is_deterministic():
    first = _build()
    second = _build()

    assert visual.stable_json(first) == visual.stable_json(second)
    assert first["schema_version"] == visual.SCHEMA_VERSION
    assert first["read_model_id"] == visual.READ_MODEL_ID
    proof = first["machine_proof"]
    assert proof["operator_file_intake_contract_model_present"] is True
    assert proof["operator_file_source_ref_model_present"] is True
    assert proof["visual_workspace_request_model_present"] is True
    assert proof["visual_workspace_artifact_binding_model_present"] is True
    assert proof["visual_workspace_bundle_model_present"] is True
    assert proof["app_automation_request_model_present"] is True
    assert proof["visual_mode_transition_model_present"] is True
    assert proof["file_visual_workspace_blocker_model_present"] is True
    assert proof["operator_file_intake_visual_workspace_elioperator_report_model_present"] is True


def test_required_field_lists_exist():
    payload = _build()
    schemas = payload["model_schemas"]

    assert schemas["operator_file_intake_contract"]["required_fields"] == list(visual.REQUIRED_CONTRACT_FIELDS)
    assert schemas["operator_file_source_ref"]["required_fields"] == list(visual.REQUIRED_SOURCE_REF_FIELDS)
    assert schemas["visual_workspace_request"]["required_fields"] == list(visual.REQUIRED_WORKSPACE_REQUEST_FIELDS)
    assert schemas["visual_workspace_artifact_binding"]["required_fields"] == list(visual.REQUIRED_ARTIFACT_BINDING_FIELDS)
    assert schemas["visual_workspace_bundle"]["required_fields"] == list(visual.REQUIRED_WORKSPACE_BUNDLE_FIELDS)
    assert schemas["app_automation_request"]["required_fields"] == list(visual.REQUIRED_AUTOMATION_REQUEST_FIELDS)
    assert schemas["visual_mode_transition"]["required_fields"] == list(visual.REQUIRED_TRANSITION_FIELDS)
    assert schemas["file_visual_workspace_blocker"]["required_fields"] == list(visual.REQUIRED_BLOCKER_FIELDS)
    assert schemas["operator_file_intake_visual_workspace_elioperator_report"]["required_fields"] == list(visual.REQUIRED_REPORT_FIELDS)


def test_file_types_intake_modes_visual_modes_and_targets_exist():
    payload = _build()

    assert payload["machine_proof"]["file_types_exist"] is True
    assert payload["machine_proof"]["intake_modes_exist"] is True
    assert payload["machine_proof"]["visual_modes_exist"] is True
    assert payload["machine_proof"]["target_surfaces_exist"] is True
    assert payload["machine_proof"]["artifact_roles_exist"] is True
    assert payload["machine_proof"]["open_modes_exist"] is True
    assert payload["machine_proof"]["target_apps_exist"] is True
    assert payload["machine_proof"]["automation_modes_exist"] is True
    assert payload["machine_proof"]["visual_transition_modes_exist"] is True
    for expected in ["spreadsheet", "screenshot", "invoice_artifact", "folder_or_project_capsule", "unknown_file_fail_closed"]:
        assert expected in payload["supported_file_types"]
    for expected in ["REFERENCE_ONLY", "METADATA_ONLY", "PROTECTED_EVIDENCE_REFERENCE", "FUTURE_FULL_INGEST_GATED"]:
        assert expected in payload["intake_modes"]
    for expected in ["SHOW_SPREADSHEET_AND_DOC", "SHOW_INVOICE_PACKET", "SHOW_MEDIA_SESSION_OVERVIEW", "UNKNOWN_NEEDS_FRAMING"]:
        assert expected in payload["visual_modes"]


def test_contract_policies_forbid_raw_body_and_private_path_exposure():
    payload = _build()
    contract = payload["operator_file_intake_contract"]
    policy_text = "\n".join(contract["doctrine"] + contract["raw_body_policy"] + contract["source_reference_policy"])

    assert "Raw private bodies do not go to LLMs by default." in policy_text
    assert "Raw bodies are not ingested by default." in policy_text
    assert "Use safe display labels instead of full private paths." in policy_text
    assert payload["machine_proof"]["source_refs_hide_private_paths"] is True


def test_album_spreadsheet_song_doc_example_exists():
    payload = _build()
    example = payload["examples"]["album_spreadsheet_song_doc"]
    request = example["visual_workspace_request"]
    refs = example["source_refs"]
    bindings = example["artifact_bindings"]

    assert payload["machine_proof"]["album_spreadsheet_song_doc_example_exists"] is True
    assert request["visual_mode"] == "SHOW_SPREADSHEET_AND_DOC"
    assert request["target_worker_type"] == "MAC_CODEX"
    assert request["target_machine"] == "MAC"
    assert refs["source_ref_album_spreadsheet"]["file_type"] == "spreadsheet"
    assert refs["source_ref_song_rich_text_doc"]["file_type"] == "rich_text_doc"
    assert bindings["binding_album_primary_spreadsheet"]["open_mode"] == "READ_ONLY_PREVIEW"
    assert example["raw_body_to_llm"] is False


def test_invoice_workspace_example_exists_and_blocks_send_submit():
    payload = _build()
    example = payload["examples"]["capital_hilton_invoice_workspace"]
    request = example["visual_workspace_request"]
    bundle = example["visual_workspace_bundle"]

    assert payload["machine_proof"]["invoice_workspace_example_exists"] is True
    assert request["visual_mode"] == "SHOW_INVOICE_PACKET"
    assert request["target_worker_type"] == "MAC_CODEX"
    assert "No email send." in bundle["warnings_or_locks"]
    assert "No Coupa access." in bundle["warnings_or_locks"]
    assert example["send_or_submit_performed"] is False


def test_required_examples_exist():
    payload = _build()
    proof = payload["machine_proof"]

    assert proof["legal_contract_example_exists"] is True
    assert proof["video_edit_review_example_exists"] is True
    assert proof["live_show_planning_example_exists"] is True
    assert proof["client_delivery_example_exists"] is True
    assert proof["bug_debug_example_exists"] is True
    assert proof["protected_proof_example_exists"] is True
    assert proof["invoice_artifact_example_exists"] is True
    assert proof["screenshot_proof_example_exists"] is True
    assert proof["app_automation_example_exists"] is True
    assert proof["unsafe_send_blocker_exists"] is True


def test_legal_and_protected_proof_examples_hide_raw_bodies():
    payload = _build()
    legal = payload["examples"]["legal_contract_review_workspace"]
    protected = payload["examples"]["protected_proof_workspace"]
    screenshot = payload["examples"]["screenshot_proof"]

    assert legal["legal_advice_authority"] is False
    assert legal["raw_contract_body_to_llm"] is False
    assert legal["source_ref"]["protected_ref_required"] is True
    assert protected["guardian_may_be_required"] is True
    assert protected["raw_body_hidden"] is True
    assert screenshot["raw_body_in_normal_read_model"] is False


def test_app_automation_and_unsafe_send_examples_are_gated():
    payload = _build()
    logic = payload["examples"]["app_automation_request"]["app_automation_request"]
    unsafe = payload["examples"]["unsafe_automation_blocker"]

    assert logic["target_app"] == "Logic Pro"
    assert logic["target_machine"] == "MAC"
    assert logic["automation_mode"] == "SHOW_OR_PREVIEW"
    assert logic["mutation_allowed"] is False
    assert "mutate project" in logic["forbidden_commands"]
    assert unsafe["blocker_type"] == "SEND_EXPORT_PUBLISH_WITHOUT_APPROVAL"
    assert unsafe["email_send_blocked"] is True
    assert unsafe["app_automation_request"]["mutation_allowed"] is False


def test_visual_mode_transition_exists():
    payload = _build()
    transition = payload["examples"]["visual_mode_transition"]["visual_mode_transition"]

    assert payload["machine_proof"]["visual_mode_transition_exists"] is True
    assert transition["from_mode"] == "CHAT_ONLY"
    assert transition["to_mode"] == "VISUAL_WORKSPACE"
    assert transition["trigger_phrase"] == "Show me what's going on."


def test_blockers_exist_and_fail_closed():
    payload = _build()
    blockers = payload["file_visual_workspace_blockers_by_id"]
    blocker_types = {blocker["blocker_type"] for blocker in blockers.values()}

    assert payload["machine_proof"]["blockers_exist"] is True
    for expected in visual.BLOCKER_TYPES:
        assert expected in blocker_types
    assert blockers["file_visual_workspace_blocker_raw_file_body_to_llm"]["fail_closed"] is True
    assert blockers["file_visual_workspace_blocker_unknown_fail_closed"]["severity"] == "CRITICAL"
    assert "VISUAL_WORKSPACE_PRETENDS_TO_BE_PROOF" in blocker_types
    assert "HIDDEN_APP_AUTOMATION" in blocker_types


def test_all_live_authority_false_and_no_execution():
    payload = _build()

    assert payload["machine_proof"]["all_live_authority_flags_false"] is True
    assert payload["machine_proof"]["file_ingestion_performed"] is False
    assert payload["machine_proof"]["raw_body_extraction_performed"] is False
    assert payload["machine_proof"]["app_automation_performed"] is False
    assert payload["machine_proof"]["file_mutation_performed"] is False
    assert payload["machine_proof"]["external_app_control_performed"] is False
    assert payload["machine_proof"]["email_send_performed"] is False
    assert payload["machine_proof"]["project_edit_performed"] is False
    assert payload["machine_proof"]["screenshot_capture_performed"] is False
    assert payload["machine_proof"]["screen_recording_performed"] is False
    assert payload["machine_proof"]["export_or_publish_performed"] is False
    assert payload["machine_proof"]["agent_dispatch_performed"] is False
    assert payload["machine_proof"]["model_call_performed"] is False
    assert payload["machine_proof"]["external_action_performed"] is False
    for key, value in payload["authority_boundary"].items():
        assert value is False, key


def test_export_writes_parseable_outputs(tmp_path, capsys):
    export_root = tmp_path / "read_models"
    assert export_main(["--export-root", str(export_root), "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    json_path = Path(summary["json_path"])
    operator_path = Path(summary["operator_path"])
    data = json.loads(json_path.read_text(encoding="utf-8"))

    assert summary["file_types_exist"] is True
    assert summary["intake_modes_exist"] is True
    assert summary["album_spreadsheet_song_doc_example_exists"] is True
    assert summary["invoice_workspace_example_exists"] is True
    assert data["machine_proof"]["all_live_authority_flags_false"] is True
    assert "ELIOPERATOR" in operator_path.read_text(encoding="utf-8")


def test_generated_outputs_have_no_raw_pii_secrets_or_private_bodies(tmp_path, capsys):
    export_root = tmp_path / "read_models"
    assert export_main(["--export-root", str(export_root), "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    json_path = Path(summary["json_path"])
    operator_path = Path(summary["operator_path"])
    data = json.loads(json_path.read_text(encoding="utf-8"))
    combined = json_path.read_text(encoding="utf-8") + "\n" + operator_path.read_text(encoding="utf-8")

    assert data["machine_proof"]["credentials_or_secrets_included"] is False
    assert data["machine_proof"]["raw_private_bodies_included"] is False
    assert data["machine_proof"]["raw_pii_in_generated_outputs"] is False
    assert not re.search(r"\b[A-Za-z]:\\\\", combined)
    assert not re.search(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", combined)
    assert "raw email body:" not in combined.lower()
    assert "private key" not in combined.lower()
    assert "api_key" not in combined.lower()


def test_source_does_not_import_network_runtime_or_external_modules():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "operator_file_intake_visual_workspace_contract.py",
            "scripts/export_operator_file_intake_visual_workspace_contract.py",
        ]
    )
    forbidden = [
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "subprocess.",
        "os.system",
        "smtplib",
        "selenium",
        "playwright",
        "send_message",
        "shell=true",
        "eval(",
    ]
    for token in forbidden:
        assert token not in source
