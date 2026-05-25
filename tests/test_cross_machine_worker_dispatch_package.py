import json
import re
from pathlib import Path

import cross_machine_worker_dispatch_package as dispatch
from scripts.export_cross_machine_worker_dispatch_package import main as export_main


FIXED_NOW = "2026-05-25T05:00:00+00:00"


def _build() -> dict:
    return dispatch.build_cross_machine_worker_dispatch_package(generated_at=FIXED_NOW)


def test_required_models_exist_and_payload_is_deterministic():
    first = _build()
    second = _build()

    assert dispatch.stable_json(first) == dispatch.stable_json(second)
    assert first["schema_version"] == dispatch.SCHEMA_VERSION
    assert first["read_model_id"] == dispatch.READ_MODEL_ID
    proof = first["machine_proof"]
    assert proof["cross_machine_worker_dispatch_package_model_present"] is True
    assert proof["worker_routing_decision_model_present"] is True
    assert proof["worker_context_package_model_present"] is True
    assert proof["worker_authority_boundary_model_present"] is True
    assert proof["worker_return_readback_model_present"] is True
    assert proof["worker_dispatch_card_model_present"] is True
    assert proof["cross_machine_dispatch_blocker_model_present"] is True


def test_required_field_lists_exist():
    payload = _build()
    schemas = payload["model_schemas"]

    assert schemas["cross_machine_worker_dispatch_package"]["required_fields"] == list(dispatch.REQUIRED_DISPATCH_FIELDS)
    assert schemas["worker_routing_decision"]["required_fields"] == list(dispatch.REQUIRED_DECISION_FIELDS)
    assert schemas["worker_context_package"]["required_fields"] == list(dispatch.REQUIRED_CONTEXT_FIELDS)
    assert schemas["worker_authority_boundary"]["required_fields"] == list(dispatch.REQUIRED_AUTHORITY_FIELDS)
    assert schemas["worker_return_readback"]["required_fields"] == list(dispatch.REQUIRED_RETURN_FIELDS)
    assert schemas["worker_dispatch_card"]["required_fields"] == list(dispatch.REQUIRED_CARD_FIELDS)
    assert schemas["cross_machine_dispatch_blocker"]["required_fields"] == list(dispatch.REQUIRED_BLOCKER_FIELDS)


def test_enums_exist():
    payload = _build()

    assert payload["machine_proof"]["target_worker_types_present"] is True
    assert payload["machine_proof"]["target_machines_present"] is True
    assert payload["machine_proof"]["dispatch_statuses_present"] is True
    for worker in ["MAC_CODEX", "PC_CODEX", "GEMINI_AGY", "LOCAL_OLLAMA", "GUARDIAN", "CASSANDRA", "UNKNOWN_NEEDS_ROUTING"]:
        assert worker in payload["target_worker_types"]
    for machine in ["MAC", "PC_WSL", "CLOUD_OR_EXTERNAL_MODEL", "LOCAL_ONLY", "UNKNOWN"]:
        assert machine in payload["target_machines"]


def test_mac_codex_mission_control_route_example_exists():
    payload = _build()
    example = payload["examples"]["mac_codex_mission_control_chat_ui"]
    dispatch_record = example["dispatch"]
    authority = example["authority_boundary"]

    assert payload["machine_proof"]["mac_codex_route_exists"] is True
    assert dispatch_record["target_worker_type"] == "MAC_CODEX"
    assert dispatch_record["target_machine"] == "MAC"
    assert dispatch_record["task_type"] == "SWIFTUI_APP_UI"
    assert "SwiftUI view edits" in dispatch_record["allowed_actions"]
    assert "Xcode build/test" in dispatch_record["allowed_actions"]
    assert "Repo A backend mutation" in dispatch_record["forbidden_actions"]
    assert authority["file_write_allowed"] is True
    assert authority["external_authority"] is False


def test_apple_app_integration_examples_exist_and_block_mutation():
    payload = _build()
    logic = payload["examples"]["mac_codex_logic_pro_project_recognition"]
    final_cut = payload["examples"]["mac_codex_final_cut_metadata_display"]

    assert payload["machine_proof"]["apple_app_integration_examples_exist"] is True
    assert logic["dispatch"]["target_worker_type"] == "MAC_CODEX"
    assert logic["dispatch"]["task_type"] == "APPLE_APP_INTEGRATION_SCOUT_OR_UI"
    assert "DAW mutation" in logic["dispatch"]["forbidden_actions"]
    assert "audio file mutation" in logic["dispatch"]["forbidden_actions"]
    assert final_cut["dispatch"]["target_worker_type"] == "MAC_CODEX"
    assert "project mutation" in final_cut["dispatch"]["forbidden_actions"]
    assert "export" in final_cut["dispatch"]["forbidden_actions"]


def test_mail_route_blocks_external_send_authority():
    payload = _build()
    mail = payload["examples"]["mac_mail_invoice_send_boundary_blocked"]

    assert payload["machine_proof"]["mac_mail_boundary_blocks_send"] is True
    assert mail["dispatch"]["dispatch_status"] == "BLOCKED_AUTHORITY"
    assert "send email" in mail["dispatch"]["forbidden_actions"]
    assert "create live Mail draft" in mail["dispatch"]["forbidden_actions"]
    assert mail["authority_boundary"]["external_authority"] is False
    assert mail["authority_boundary"]["approval_required"] is True


def test_pc_codex_backend_route_example_exists():
    payload = _build()
    example = payload["examples"]["pc_codex_chat_readback_card_mirror"]

    assert payload["machine_proof"]["pc_codex_route_exists"] is True
    assert example["dispatch"]["target_worker_type"] == "PC_CODEX"
    assert example["dispatch"]["target_machine"] == "PC_WSL"
    assert example["dispatch"]["task_type"] == "BACKEND_READMODEL"
    assert "Python module edits" in example["dispatch"]["allowed_actions"]
    assert "focused pytest" in example["dispatch"]["validation_commands"]
    assert "Mac Swift edits" in example["dispatch"]["forbidden_actions"]
    assert example["authority_boundary"]["file_write_allowed"] is True


def test_gemini_agy_read_only_route_example_exists():
    payload = _build()
    example = payload["examples"]["gemini_agy_card_contract_audit"]

    assert payload["machine_proof"]["gemini_route_exists"] is True
    assert example["dispatch"]["target_worker_type"] == "GEMINI_AGY"
    assert example["dispatch"]["task_type"] == "READ_ONLY_AUDIT"
    assert "read-only audit" in example["dispatch"]["allowed_actions"]
    assert "file edits" in example["dispatch"]["forbidden_actions"]
    assert example["authority_boundary"]["file_write_allowed"] is False
    assert example["authority_boundary"]["shell_allowed"] is False


def test_ambiguous_route_example_asks_for_clarification():
    payload = _build()
    example = payload["examples"]["ambiguous_make_it_better"]

    assert payload["machine_proof"]["ambiguous_route_exists"] is True
    assert example["dispatch"]["target_worker_type"] == "UNKNOWN_NEEDS_ROUTING"
    assert example["dispatch"]["dispatch_status"] == "BLOCKED_MISSING_CONTEXT"
    assert "ask a clarifying question" in example["dispatch"]["allowed_actions"]
    assert "worker dispatch" in example["dispatch"]["forbidden_actions"]
    assert "Ask whether this is Mac app work" in example["routing_decision"]["next_safe_move"]


def test_wrong_worker_and_authority_too_broad_blocker_examples_exist():
    payload = _build()
    wrong = payload["examples"]["wrong_worker_swiftui_to_pc_codex"]
    broad = payload["examples"]["authority_too_broad_mail_coupa_send"]

    assert payload["machine_proof"]["wrong_worker_blocker_example_exists"] is True
    assert "WRONG_WORKER_SELECTED" in wrong["active_blockers"]
    assert wrong["dispatch"]["dispatch_status"] == "BLOCKED_AUTHORITY"
    assert payload["machine_proof"]["authority_too_broad_blocker_example_exists"] is True
    assert "AUTHORITY_TOO_BROAD" in broad["active_blockers"]
    assert "EXTERNAL_ACTION_INCLUDED" in broad["active_blockers"]


def test_blockers_exist_and_fail_closed():
    payload = _build()
    blockers = payload["cross_machine_dispatch_blockers_by_id"]
    blocker_types = {blocker["blocker_type"] for blocker in blockers.values()}

    assert payload["machine_proof"]["blockers_present"] is True
    for expected in dispatch.BLOCKER_TYPES:
        assert expected in blocker_types
    assert blockers["cross_machine_dispatch_blocker_unknown_fail_closed"]["fail_closed"] is True
    assert blockers["cross_machine_dispatch_blocker_authority_too_broad"]["fail_closed"] is True


def test_all_live_authority_false_and_no_external_authority_in_examples():
    payload = _build()

    assert payload["machine_proof"]["all_live_authority_flags_false"] is True
    assert payload["machine_proof"]["no_example_grants_external_authority"] is True
    for key, value in payload["authority_boundary"].items():
        assert value is False, key
    for example in payload["examples"].values():
        authority = example["authority_boundary"]
        assert authority["external_authority"] is False
        assert authority["network_allowed"] is False
        assert authority["credential_handling_allowed"] is False
        assert authority["raw_body_ingestion_allowed"] is False


def test_operator_cards_hide_machine_contract_language():
    payload = _build()

    assert payload["machine_proof"]["operator_cards_hide_machine_contract"] is True
    for example in payload["examples"].values():
        card_text = " ".join(
            [
                example["operator_card"]["title"],
                example["operator_card"]["summary"],
                example["operator_card"]["target_worker_label"],
                example["operator_card"]["target_machine_label"],
            ]
        ).lower()
        assert "schema" not in card_text
        assert "handler" not in card_text


def test_export_writes_parseable_outputs(tmp_path, capsys):
    export_root = tmp_path / "read_models"
    assert export_main(["--export-root", str(export_root), "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    json_path = Path(summary["json_path"])
    operator_path = Path(summary["operator_path"])
    data = json.loads(json_path.read_text(encoding="utf-8"))

    assert summary["mac_codex_route_exists"] is True
    assert summary["pc_codex_route_exists"] is True
    assert data["machine_proof"]["all_live_authority_flags_false"] is True
    assert "ELIOPERATOR" in operator_path.read_text(encoding="utf-8")


def test_no_raw_pii_or_private_bodies_in_generated_outputs(tmp_path, capsys):
    export_root = tmp_path / "read_models"
    assert export_main(["--export-root", str(export_root), "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    json_path = Path(summary["json_path"])
    operator_path = Path(summary["operator_path"])
    data = json.loads(json_path.read_text(encoding="utf-8"))
    combined = json_path.read_text(encoding="utf-8") + "\n" + operator_path.read_text(encoding="utf-8")

    assert data["machine_proof"]["credentials_or_secrets_included"] is False
    assert data["machine_proof"]["raw_private_bodies_included"] is False
    assert data["machine_proof"]["raw_pii_in_packages"] is False
    assert "@" not in combined
    assert not re.search(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", combined)
    assert "raw email body:" not in combined.lower()
    assert "raw pdf body:" not in combined.lower()
    assert "access_token" not in combined.lower()


def test_source_does_not_import_network_or_runtime_modules():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "cross_machine_worker_dispatch_package.py",
            "scripts/export_cross_machine_worker_dispatch_package.py",
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
        "codex exec",
        "gemini --prompt",
        "ollama_call(",
        "nemotron_call(",
        "openrouter_call(",
    ]
    for token in forbidden:
        assert token not in source
