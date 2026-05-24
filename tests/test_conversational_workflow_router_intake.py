import json
import re
from pathlib import Path

import conversational_workflow_router_intake as intake
from scripts.import_conversational_workflow_router_intake import main as import_main


FIXED_NOW = "2026-05-25T00:30:00+00:00"


def _write_fixture(tmp_path: Path) -> Path:
    request = intake.make_capital_hilton_fixture_request(created_at=FIXED_NOW)
    path = tmp_path / "mission_control_chat_request_capital_hilton_invoice_fixture.json"
    path.write_text(intake.stable_json(request), encoding="utf-8")
    return path


def _import_fixture(tmp_path: Path, capsys) -> tuple[dict, dict]:
    request_path = _write_fixture(tmp_path)
    export_root = tmp_path / "read_models"
    assert import_main(
        [
            "--request-json",
            str(request_path),
            "--export-root",
            str(export_root),
            "--generated-at",
            FIXED_NOW,
            "--format",
            "summary",
        ]
    ) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))
    return summary, payload


def test_fixture_request_hash_helper_is_deterministic():
    first = intake.make_capital_hilton_fixture_request(created_at=FIXED_NOW)
    second = intake.make_capital_hilton_fixture_request(created_at=FIXED_NOW)

    assert intake.stable_json(first) == intake.stable_json(second)
    assert first["payload_hash"] == intake.compute_request_payload_hash(first)
    assert first["idempotency_key"]


def test_required_models_exist_in_imported_readback(tmp_path, capsys):
    _, payload = _import_fixture(tmp_path, capsys)
    proof = payload["machine_proof"]
    schemas = payload["model_schemas"]

    assert proof["intake_request_model_present"] is True
    assert proof["intake_result_model_present"] is True
    assert proof["router_human_card_model_present"] is True
    assert proof["router_readback_package_model_present"] is True
    assert proof["router_backend_package_target_model_present"] is True
    assert proof["router_intake_receipt_model_present"] is True
    assert proof["router_intake_blocker_model_present"] is True
    assert schemas["conversational_workflow_router_intake_request"]["required_fields"] == list(
        intake.REQUIRED_REQUEST_FIELDS
    )
    assert schemas["conversational_workflow_router_intake_result"]["parse_statuses"] == list(
        intake.PARSE_STATUSES
    )


def test_capital_hilton_request_routes_to_expected_result(tmp_path, capsys):
    summary, payload = _import_fixture(tmp_path, capsys)
    result = payload["intake_result"]
    target = payload["router_readback_package"]["backend_package_target"]

    assert summary["parse_status"] == "ROUTED_DRAFT_READY"
    assert result["parse_status"] == "ROUTED_DRAFT_READY"
    assert result["parser_mode"] == "deterministic_draft_router"
    assert result["model_parser_available"] is False
    assert result["operator_review_required"] is True
    assert result["external_authority"] is False
    assert target["workflow_type"] == "invoice_delivery_workflow"
    assert target["package_type"] == "WORKFLOW_MEMORY_PROPOSAL"
    assert target["can_create_now"] is False


def test_human_cards_match_expected_capital_hilton_readback(tmp_path, capsys):
    _, payload = _import_fixture(tmp_path, capsys)
    cards = payload["router_readback_package"]["cards"]
    by_type = {card["card_type"]: card for card in cards}

    assert set(by_type) == {"OPENCLAW_UNDERSTOOD", "PROPOSED_WORKFLOW", "MISSING_INFO", "BLOCKED"}
    understood = by_type["OPENCLAW_UNDERSTOOD"]
    assert understood["title"] == "OpenClaw understood"
    assert "Goal: prepare the Capital Hilton invoice workflow." in understood["bullets"]
    assert "Invoice basis: 4 dates at $400 each appear to be the working basis." in understood["bullets"]
    assert "Companion invoice: generate a Winship-branded Excel/PDF invoice." in understood["bullets"]
    assert "Destination/contact: Annette appears to be the email/payment follow-up contact." in understood["bullets"]
    assert "Official payment rail: Coupa supplier portal invoice from PO." in understood["bullets"]
    assert "Records: save the generated invoice with today's date for future invoice range tracking." in understood["bullets"]
    assert "External actions: locked." in understood["bullets"]

    proposed = by_type["PROPOSED_WORKFLOW"]
    assert proposed["title"] == "Proposed workflow"
    assert proposed["bullets"][0] == "1. Confirm captured dates/rate."
    assert proposed["bullets"][-1] == "10. Track payment state."

    missing = by_type["MISSING_INFO"]
    assert "Exact Coupa PO/reference." in missing["bullets"]
    assert "Whether Guardian approval exists." in missing["bullets"]

    blocked = by_type["BLOCKED"]
    assert "No email sent." in blocked["bullets"]
    assert "No Coupa access." in blocked["bullets"]
    assert "No browser opened." in blocked["bullets"]
    assert "No invoice submitted." in blocked["bullets"]
    assert "No approval requested." in blocked["bullets"]
    assert "No payment state changed." in blocked["bullets"]


def test_backend_package_target_roles_and_locks(tmp_path, capsys):
    _, payload = _import_fixture(tmp_path, capsys)
    target = payload["router_readback_package"]["backend_package_target"]

    for role in [
        "drafting_agent",
        "finance_delivery_agent",
        "protected_evidence_agent",
        "approval_agent",
        "artifact_generation_agent",
        "post_office_handoff",
        "final_readback_agent",
    ]:
        assert role in target["role_targets"]
    assert "email send" in target["blocked_actions"]
    assert "Coupa access" in target["blocked_actions"]
    assert "show cards to operator" in target["ready_actions"]
    assert payload["machine_proof"]["external_actions_locked"] is True


def test_receipt_is_metadata_only_and_external_authority_false(tmp_path, capsys):
    _, payload = _import_fixture(tmp_path, capsys)
    receipt = payload["router_intake_receipt"]

    assert receipt["intake_status"] == "ROUTED_DRAFT_READY"
    assert receipt["external_authority"] is False
    assert receipt["raw_body_ingestion"] is False
    assert receipt["credential_handling"] is False
    assert payload["machine_proof"]["all_live_authority_flags_false"] is True
    for key, value in payload["authority_boundary"].items():
        assert value is False, key


def test_missing_idempotency_and_hash_fail_closed(tmp_path, capsys):
    request = intake.make_capital_hilton_fixture_request(created_at=FIXED_NOW)
    request["idempotency_key"] = ""
    request["payload_hash"] = ""
    path = tmp_path / "mission_control_chat_request_missing_fields.json"
    path.write_text(intake.stable_json(request), encoding="utf-8")
    export_root = tmp_path / "read_models"

    assert import_main(["--request-json", str(path), "--export-root", str(export_root), "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))
    blockers = {item["blocker_type"] for item in payload["active_blockers_by_id"].values()}
    assert summary["parse_status"] == "REJECTED_INVALID_REQUEST"
    assert "MISSING_IDEMPOTENCY_KEY" in blockers
    assert "MISSING_PAYLOAD_HASH" in blockers
    assert payload["router_intake_receipt"]["external_authority"] is False


def test_payload_hash_mismatch_fails_closed(tmp_path, capsys):
    request = intake.make_capital_hilton_fixture_request(created_at=FIXED_NOW)
    request["sanitized_message_summary"] = request["sanitized_message_summary"] + " changed"
    path = tmp_path / "mission_control_chat_request_bad_hash.json"
    path.write_text(intake.stable_json(request), encoding="utf-8")
    export_root = tmp_path / "read_models"

    assert import_main(["--request-json", str(path), "--export-root", str(export_root), "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))
    blockers = {item["blocker_type"] for item in payload["active_blockers_by_id"].values()}
    assert summary["parse_status"] == "REJECTED_INVALID_REQUEST"
    assert "UNSUPPORTED_REQUEST_SHAPE" in blockers


def test_export_without_request_is_truthful_no_request_readiness(tmp_path, capsys):
    empty_inbox = tmp_path / "empty_inbox"
    empty_inbox.mkdir()
    export_root = tmp_path / "read_models"
    assert import_main(
        [
            "--inbox",
            str(empty_inbox),
            "--export-root",
            str(export_root),
            "--generated-at",
            FIXED_NOW,
            "--format",
            "summary",
        ]
    ) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))
    assert summary["route_mode"] == "NO_REQUEST_AVAILABLE"
    assert summary["parse_status"] == "NEEDS_MORE_DETAIL"
    assert payload["router_readback_package"]["cards"][0]["title"] == "Request blocked"
    assert "No Mission Control chat request is available" in payload["router_readback_package"]["cards"][0]["bullets"][0]


def test_generated_outputs_have_no_raw_pii_or_secret_like_values(tmp_path, capsys):
    _import_fixture(tmp_path, capsys)
    export_root = tmp_path / "read_models"
    json_path = export_root / intake.JSON_EXPORT_NAME
    operator_path = export_root / intake.OPERATOR_EXPORT_NAME
    data = json.loads(json_path.read_text(encoding="utf-8"))
    combined = json_path.read_text(encoding="utf-8") + "\n" + operator_path.read_text(encoding="utf-8")

    assert data["machine_proof"]["credentials_or_secrets_included"] is False
    assert data["machine_proof"]["raw_private_bodies_included"] is False
    assert data["machine_proof"]["raw_sensitive_fixture_values_included"] is False
    assert "@" not in combined
    assert not re.search(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", combined)
    assert "PO-" not in combined
    assert "ELIOPERATOR" in operator_path.read_text(encoding="utf-8")


def test_operator_markdown_is_human_facing(tmp_path, capsys):
    _import_fixture(tmp_path, capsys)
    operator = (tmp_path / "read_models" / intake.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")
    assert "OpenClaw understood" in operator
    assert "No email sent." in operator
    assert "schema_version" not in operator
    assert "handler" not in operator.lower()
    assert "manifest" not in operator.lower()


def test_source_does_not_import_network_runtime_or_external_modules():
    source = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "conversational_workflow_router_intake.py",
            "scripts/import_conversational_workflow_router_intake.py",
            "scripts/export_conversational_workflow_router_readback.py",
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
        "coupa.login",
        "send_message",
        "shell=true",
        "eval(",
    ]
    for token in forbidden:
        assert token not in source
