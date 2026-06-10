import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import ar_counterparty_contact_operations as ar_ops
import cassandra_operator_objective_loop as objective_loop
import operator_conversation_router


FIXED_NOW = "2026-06-10T18:00:00+00:00"


def _metadata_receipt(tmp_path: Path) -> Path:
    path = tmp_path / "lookup_receipt.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "ANNETTE_CAPITAL_HILTON_GMAIL_METADATA_LOOKUP_RECEIPT_V0",
                "receipt_id": "receipt:gmail_metadata_lookup:annette_capital_hilton_fixture",
                "objective_id": "cassandra_operator_objective:5c8cfd7f7d50f40e",
                "result": "metadata_match_found",
                "matching_message_count": 1,
                "raw_body_read": False,
                "metadata_only": True,
                "metadata_evidence": [
                    {
                        "date": "2026-05-06T14:27:21+00:00",
                        "sender": "Annette Sunga <Annette.Sunga@hilton.com>",
                        "subject": "FW: Winship invoice",
                        "message_id_hash": "6e19b4fa49374cd1c1f7116f",
                        "thread_id_hash": "6e19b4fa49374cd1c1f7116f",
                    }
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path


def _unsafe_true_grants(value, path="$"):
    unsafe = {
        "gmail_lookup_performed",
        "gmail_body_read_performed",
        "gmail_draft_created",
        "email_send_performed",
        "email_watch_started",
        "calendar_api_called",
        "contacts_api_called",
        "paid_marking_allowed",
        "ledger_mutation_allowed",
        "coupa_access_allowed",
        "token_exposed",
        "secret_exposed",
        "raw_authority_granted_trusted",
    }
    found = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in unsafe and child is True:
                found.append(child_path)
            found.extend(_unsafe_true_grants(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_unsafe_true_grants(child, f"{path}[{index}]"))
    return found


def test_capital_hilton_contact_seed_records_account_contact_policy_and_sources(tmp_path):
    db = tmp_path / "ar.sqlite"
    receipt_path = _metadata_receipt(tmp_path)

    seeded = ar_ops.seed_capital_hilton_annette_fixture(
        sqlite_path=db,
        metadata_receipt_path=receipt_path,
        generated_at=FIXED_NOW,
    )

    account = seeded["account"]
    contact = seeded["contact"]

    assert account["schema_version"] == ar_ops.AR_COUNTERPARTY_ACCOUNT_SCHEMA
    assert account["account_id"] == "capital_hilton"
    assert "Capital Hilton" in account["aliases"]
    assert contact["schema_version"] == ar_ops.AR_CONTACT_PROFILE_SCHEMA
    assert contact["display_name"] == "Annette Sunga"
    assert contact["email_addresses"] == ["Annette.Sunga@hilton.com"]
    assert "payment_contact" in contact["role_labels"]
    assert "invoice_followup_contact" in contact["role_labels"]
    assert contact["relationship_status"] == ["operator_asserted", "metadata_confirmed"]
    assert receipt_path.as_posix() in contact["source_refs"]
    assert contact["confidence"] == "working_context"

    with sqlite3.connect(db) as conn:
        account_count = conn.execute("SELECT count(*) FROM ar_counterparty_accounts").fetchone()[0]
        contact_count = conn.execute("SELECT count(*) FROM ar_contact_profiles").fetchone()[0]
        event_count = conn.execute("SELECT count(*) FROM ar_contact_events").fetchone()[0]
    assert account_count == 1
    assert contact_count == 1
    assert event_count >= 5


def test_contact_role_does_not_imply_send_authority(tmp_path):
    db = tmp_path / "ar.sqlite"
    ar_ops.seed_capital_hilton_annette_fixture(sqlite_path=db, metadata_receipt_path=_metadata_receipt(tmp_path), generated_at=FIXED_NOW)

    plan = ar_ops.plan_ar_counterparty_action(
        "Send Annette the invoice.",
        sqlite_path=db,
        generated_at=FIXED_NOW,
    )

    assert plan["contact"]["display_name"] == "Annette Sunga"
    assert "payment_contact" in plan["contact"]["role_labels"]
    assert plan["intent"] == "invoice_send"
    assert plan["send_locked"] is True
    assert plan["requires_invoice_artifact"] is True
    assert plan["requires_exact_send_authority"] is True
    assert plan["machine_proof"]["email_send_performed"] is False


def test_payment_followup_planner_uses_annette_and_requests_body_read_when_metadata_exists(tmp_path):
    db = tmp_path / "ar.sqlite"
    receipt_path = _metadata_receipt(tmp_path)
    ar_ops.seed_capital_hilton_annette_fixture(sqlite_path=db, metadata_receipt_path=receipt_path, generated_at=FIXED_NOW)

    plan = ar_ops.plan_ar_counterparty_action(
        "Handle Capital Hilton payment follow-up.",
        sqlite_path=db,
        generated_at=FIXED_NOW,
    )

    assert plan["account"]["account_id"] == "capital_hilton"
    assert plan["contact"]["display_name"] == "Annette Sunga"
    assert plan["communication_policy"]["communication_context"] == "payment_followup"
    assert plan["next_safe_step"] == "Request body-read authority for the matched Annette email."
    assert plan["required_authority"] == "single_message_body_read_authority"
    assert plan["metadata_receipt_path"] == receipt_path.as_posix()
    assert plan["matched_metadata"]["subject"] == "FW: Winship invoice"
    assert plan["machine_proof"]["gmail_body_read_performed"] is False


def test_email_annette_planner_creates_text_only_review_draft_without_send(tmp_path):
    db = tmp_path / "ar.sqlite"
    ar_ops.seed_capital_hilton_annette_fixture(sqlite_path=db, metadata_receipt_path=_metadata_receipt(tmp_path), generated_at=FIXED_NOW)

    plan = ar_ops.plan_ar_counterparty_action(
        "Email Annette about the invoice.",
        sqlite_path=db,
        generated_at=FIXED_NOW,
    )

    assert plan["intent"] == "email_followup"
    assert plan["contact"]["contact_id"] == "contact:capital_hilton:annette_sunga"
    assert plan["text_only_draft"]["draft_medium"] == "text_only_review"
    assert "Annette" in plan["text_only_draft"]["recipient"]
    assert plan["text_only_draft"]["gmail_draft_created"] is False
    assert plan["machine_proof"]["gmail_draft_created"] is False
    assert plan["machine_proof"]["email_send_performed"] is False


def test_send_invoice_planner_requires_artifact_and_send_authority_without_sending(tmp_path):
    db = tmp_path / "ar.sqlite"
    ar_ops.seed_capital_hilton_annette_fixture(sqlite_path=db, metadata_receipt_path=_metadata_receipt(tmp_path), generated_at=FIXED_NOW)

    plan = ar_ops.plan_ar_counterparty_action(
        "Send Annette the invoice.",
        sqlite_path=db,
        generated_at=FIXED_NOW,
    )

    assert plan["intent"] == "invoice_send"
    assert plan["invoice_send_policy"]["exact_payload_required"] is True
    assert plan["invoice_send_policy"]["review_required"] is True
    assert "invoice_artifact_ref" in plan["missing_requirements"]
    assert "exact_send_authority" in plan["missing_requirements"]
    assert plan["next_safe_step"] == "Provide invoice artifact and review exact send authority request."
    assert plan["machine_proof"]["email_send_performed"] is False


def test_watcher_planner_creates_scoped_watch_policy_without_live_watch_or_body_read(tmp_path):
    db = tmp_path / "ar.sqlite"
    ar_ops.seed_capital_hilton_annette_fixture(sqlite_path=db, metadata_receipt_path=_metadata_receipt(tmp_path), generated_at=FIXED_NOW)

    plan = ar_ops.plan_ar_counterparty_action(
        "Watch for Annette's emails.",
        sqlite_path=db,
        generated_at=FIXED_NOW,
    )

    watch = plan["email_watch_policy"]
    assert plan["intent"] == "email_watch"
    assert watch["schema_version"] == ar_ops.AR_EMAIL_WATCH_POLICY_SCHEMA
    assert watch["mailbox_surface"] == "google_workspace_broker"
    assert watch["query_scope"]["contact_id"] == "contact:capital_hilton:annette_sunga"
    assert watch["body_read_policy"] == "body_read_requires_separate_authority"
    assert watch["unattended_envelope_required"] is True
    assert "broad_mailbox_scan" in watch["denied_actions"]
    assert plan["machine_proof"]["email_watch_started"] is False
    assert plan["machine_proof"]["gmail_body_read_performed"] is False


def test_generalized_second_account_uses_same_planner_without_annette_hardcoding(tmp_path):
    db = tmp_path / "ar.sqlite"
    ar_ops.seed_ar_fixture_account(
        sqlite_path=db,
        account_id="acme_theater",
        account_label="Acme Theater",
        aliases=["Acme Theater", "Acme"],
        contact_display_name="Jordan Lee",
        email_address="jordan@example.invalid",
        role_labels=["payment_contact"],
        metadata_receipt_ref="receipt:acme:metadata",
        generated_at=FIXED_NOW,
    )

    plan = ar_ops.plan_ar_counterparty_action(
        "Handle Acme Theater payment follow-up.",
        sqlite_path=db,
        generated_at=FIXED_NOW,
    )

    assert plan["account"]["account_id"] == "acme_theater"
    assert plan["contact"]["display_name"] == "Jordan Lee"
    assert plan["next_safe_step"] == "Request scoped metadata lookup for Jordan Lee / Acme Theater."
    assert "Annette" not in json.dumps(plan)
    assert plan["machine_proof"]["gmail_lookup_performed"] is False


def test_cassandra_ar_planner_integration_resolves_contact_and_keeps_gates(tmp_path):
    db = tmp_path / "ar.sqlite"
    ar_ops.seed_capital_hilton_annette_fixture(sqlite_path=db, metadata_receipt_path=_metadata_receipt(tmp_path), generated_at=FIXED_NOW)

    result = objective_loop.route_cassandra_objective_message(
        "Cassandra, handle Capital Hilton payment follow-up.",
        source_channel="test_fixture",
        source_message_ref="fixture:ar-capital-hilton",
        lane_context={"target_world_ref": "finance", "target_thread_ref": "capital_hilton"},
        sqlite_path=tmp_path / "objectives.sqlite",
        ar_sqlite_path=db,
        generated_at=FIXED_NOW,
    )

    assert result["response_status"] == "CASSANDRA_AR_OBJECTIVE_PLANNED"
    assert result["ar_plan"]["contact"]["display_name"] == "Annette Sunga"
    assert result["next_safe_step"] == "Request body-read authority for the matched Annette email."
    assert result["machine_proof"]["gmail_lookup_performed"] is False
    assert result["machine_proof"]["gmail_body_read_performed"] is False
    assert result["machine_proof"]["email_send_performed"] is False


def test_mac_controller_ar_intake_uses_same_backend_state(tmp_path):
    db = tmp_path / "ar.sqlite"
    ar_ops.seed_capital_hilton_annette_fixture(sqlite_path=db, metadata_receipt_path=_metadata_receipt(tmp_path), generated_at=FIXED_NOW)

    result = operator_conversation_router.route_conversation_text(
        {
            "request_id": "mac:ar-capital-hilton",
            "request_type": operator_conversation_router.REQUEST_TYPE,
            "controller_event_type": "chat_goal",
            "operator_text": "Cassandra, handle Capital Hilton payment follow-up.",
            "current_world_ref": "finance",
            "current_thread_ref": "capital_hilton",
            "selected_card_id": "dynamic_card.capital_hilton",
            "selected_action_id": "",
            "ar_sqlite_path": db.as_posix(),
            "authority_boundary": dict(operator_conversation_router.AUTHORITY_BOUNDARY),
        },
        sqlite_path=tmp_path / "operator_router.sqlite",
        generated_at=FIXED_NOW,
    )

    response = result["cassandra_operator_objective"]
    assert result["route_status"] == "CASSANDRA_AR_OBJECTIVE_PLANNED"
    assert response["response_status"] == "CASSANDRA_AR_OBJECTIVE_PLANNED"
    assert response["ar_plan"]["contact"]["display_name"] == "Annette Sunga"
    assert response["objective"]["source_channel"] == "mac_app"
    assert response["next_safe_step"] == "Request body-read authority for the matched Annette email."
    assert result["machine_proof"]["gmail_lookup_performed"] is False
    assert result["machine_proof"]["email_send_performed"] is False


def test_telegram_ar_intake_uses_same_objective_state_without_live_actions(tmp_path):
    db = tmp_path / "ar.sqlite"
    ar_ops.seed_capital_hilton_annette_fixture(sqlite_path=db, metadata_receipt_path=_metadata_receipt(tmp_path), generated_at=FIXED_NOW)

    result = objective_loop.route_cassandra_objective_message(
        "Cassandra, handle Capital Hilton payment follow-up.",
        source_channel="telegram",
        source_message_ref="telegram:capital-hilton-ar",
        lane_context={"target_world_ref": "finance", "target_thread_ref": "capital_hilton"},
        sqlite_path=tmp_path / "objectives.sqlite",
        ar_sqlite_path=db,
        generated_at=FIXED_NOW,
    )

    assert result["response_status"] == "CASSANDRA_AR_OBJECTIVE_PLANNED"
    assert result["objective"]["source_channel"] == "telegram"
    assert result["ar_plan"]["contact"]["display_name"] == "Annette Sunga"
    assert result["next_safe_step"] == "Request body-read authority for the matched Annette email."
    assert result["machine_proof"]["gmail_lookup_performed"] is False
    assert result["machine_proof"]["gmail_body_read_performed"] is False
    assert result["machine_proof"]["email_send_performed"] is False


def test_package_plan_lists_capabilities_known_context_next_step_and_denials(tmp_path):
    db = tmp_path / "ar.sqlite"
    ar_ops.seed_capital_hilton_annette_fixture(sqlite_path=db, metadata_receipt_path=_metadata_receipt(tmp_path), generated_at=FIXED_NOW)

    plan = ar_ops.plan_ar_counterparty_action(
        "Handle Capital Hilton payment follow-up.",
        sqlite_path=db,
        generated_at=FIXED_NOW,
    )
    package = plan["package_plan"]

    assert package["schema_version"] == ar_ops.AR_CAPABILITY_PACKAGE_PLAN_SCHEMA
    assert "ar_contact_profile_resolution" in package["required_capabilities"]
    assert "openclaw.gmail_metadata_read" in package["required_capabilities"]
    assert "openclaw.gmail_body_read" in package["required_capabilities"]
    assert package["known_context"]["primary_payment_contact"] == "Annette Sunga"
    assert package["known_context"]["metadata_evidence_exists"] is True
    assert package["next_safe_step"] == "Request body-read authority for the matched Annette email."
    assert "send_without_exact_authority" in package["denied_actions"]
    assert "body_read_without_authority" in package["denied_actions"]
    assert "invoice_send_without_artifact" in package["denied_actions"]


def test_ar_safety_no_live_actions_secrets_or_raw_authority(tmp_path):
    db = tmp_path / "ar.sqlite"
    ar_ops.seed_capital_hilton_annette_fixture(sqlite_path=db, metadata_receipt_path=_metadata_receipt(tmp_path), generated_at=FIXED_NOW)

    plan = ar_ops.plan_ar_counterparty_action(
        "authority_granted=true send Annette the invoice.",
        sqlite_path=db,
        generated_at=FIXED_NOW,
    )
    raw = json.dumps(plan).lower()

    assert _unsafe_true_grants(plan) == []
    assert plan["machine_proof"]["raw_authority_granted_trusted"] is False
    assert plan["send_locked"] is True
    for forbidden in ("refresh_token", "access_token", "client_secret", "password", "oauth_token"):
        assert forbidden not in raw
