import json
import re
import sys
from dataclasses import fields
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import operator_attention_delivery_contract as attention
from scripts.export_operator_attention_delivery_contract import main as export_main


FIXED_NOW = "2026-05-26T01:00:00+00:00"


def _payload() -> dict:
    return attention.build_payload(generated_at=FIXED_NOW)


def _item(payload: dict, key: str) -> dict:
    return payload["attention_items"][key]


def _assert_no_live_authority(item: dict) -> None:
    assert item["external_delivery_allowed"] is False
    assert item["telegram_send_allowed"] is False
    assert item["push_allowed"] is False
    assert item["email_send_allowed"] is False
    assert item["external_action_allowed"] is False
    assert all(value is False for value in item["authority_boundary"].values())
    linked = item["linked_local_surface_request"]
    assert linked["raw_body_allowed"] is False
    assert linked["external_model_share_allowed"] is False
    assert linked["external_action_allowed"] is False
    assert linked["local_only"] is True


def test_required_models_exist_with_required_fields():
    assert tuple(field.name for field in fields(attention.OperatorAttentionItem)) == (
        "attention_id",
        "world_ref",
        "client_ref",
        "workflow_ref",
        "actor_label",
        "human_message",
        "concise_spoken_guidance",
        "reason_for_attention",
        "operator_only_reason",
        "urgency_level",
        "delivery_targets_allowed",
        "operator_presence_context",
        "display_policy",
        "primary_human_action_label",
        "linked_local_surface_request",
        "required_confirmation",
        "authority_boundary",
        "external_delivery_allowed",
        "telegram_send_allowed",
        "push_allowed",
        "email_send_allowed",
        "external_action_allowed",
        "expires_or_stale_after",
        "receipt_required_after_operator_action",
        "fixture_ref",
        "attention_to_local_surface_binding",
    )
    assert tuple(field.name for field in fields(attention.AttentionToLocalSurfaceBinding)) == (
        "binding_id",
        "attention_id",
        "primary_human_action_label",
        "local_surface_request_id",
        "local_surface_type",
        "binding_status",
        "direct_execution_allowed",
        "validation_required_after_result",
        "next_safe_move",
    )
    assert tuple(field.name for field in fields(attention.OperatorPresenceContext)) == (
        "context_id",
        "presence_context",
        "preferred_display_policy",
        "auto_open_surface_when_active_preferred",
        "show_single_action_when_away",
        "next_safe_move",
    )


def test_active_in_chat_maps_to_auto_open_surface_when_active():
    payload = _payload()
    capital_hilton = _item(payload, "cassandra_capital_hilton_invoice_reminder")
    guardian = _item(payload, "guardian_protected_file_boundary")

    assert capital_hilton["operator_presence_context"] == "active_in_chat"
    assert capital_hilton["display_policy"] == "auto_open_surface_when_active"
    assert guardian["operator_presence_context"] == "active_in_chat"
    assert guardian["display_policy"] == "auto_open_surface_when_active"
    assert payload["machine_proof"]["active_in_chat_prefers_auto_open_surface_when_active"] is True


def test_away_maps_to_show_single_action_when_away():
    payload = _payload()
    bank = _item(payload, "chief_bank_ledger_stale")
    niles = _item(payload, "niles_music_scene_file")

    assert bank["operator_presence_context"] == "away"
    assert bank["display_policy"] == "show_single_action_when_away"
    assert bank["primary_human_action_label"] == "Update ledger"
    assert niles["operator_presence_context"] == "away"
    assert niles["display_policy"] == "show_single_action_when_away"
    assert niles["primary_human_action_label"] == "Add scene file"
    assert payload["machine_proof"]["away_uses_single_action_when_away"] is True


def test_no_action_items_map_to_quiet_below_deck_and_do_not_surface():
    payload = _payload()
    quiet = _item(payload, "quiet_below_deck_backend_handled")

    assert quiet["reason_for_attention"] == "quiet_backend_handled"
    assert quiet["display_policy"] == "quiet_below_deck"
    assert tuple(quiet["delivery_targets_allowed"]) == ()
    assert quiet["linked_local_surface_request"]["surface_type"] == "NO_SURFACE_REQUEST"
    assert "quiet_below_deck_backend_handled" in payload["quiet_attention_items"]
    assert "quiet_below_deck_backend_handled" not in payload["surfaced_attention_items"]
    assert payload["machine_proof"]["no_action_items_are_quiet_below_deck"] is True


def test_attention_actions_bind_to_structured_local_surface_types():
    payload = _payload()

    for key, item in payload["attention_items"].items():
        binding = item["attention_to_local_surface_binding"]
        linked = item["linked_local_surface_request"]
        assert binding["attention_id"] == item["attention_id"]
        assert binding["primary_human_action_label"] == item["primary_human_action_label"]
        assert binding["local_surface_request_id"] == linked["request_id"]
        assert binding["local_surface_type"] == linked["surface_type"]
        assert binding["direct_execution_allowed"] is False
        assert attention.validate_attention_item(item) == (), key

    assert payload["machine_proof"]["all_attention_actions_bind_to_local_surface_request"] is True
    assert payload["machine_proof"]["all_linked_surface_requests_validate"] is True


def test_no_attention_action_triggers_live_external_execution():
    payload = _payload()

    for item in payload["attention_items"].values():
        _assert_no_live_authority(item)
    assert payload["machine_proof"]["telegram_send_performed"] is False
    assert payload["machine_proof"]["push_notification_performed"] is False
    assert payload["machine_proof"]["email_send_performed"] is False
    assert payload["machine_proof"]["external_action_performed"] is False
    assert payload["machine_proof"]["workflow_execution_performed"] is False
    assert payload["machine_proof"]["all_live_authority_false"] is True


def test_telegram_push_and_email_targets_are_candidate_only():
    payload = _payload()
    bank = _item(payload, "chief_bank_ledger_stale")
    niles = _item(payload, "niles_music_scene_file")
    policy = payload["delivery_policy"]

    assert "telegram_candidate" in bank["delivery_targets_allowed"]
    assert "mobile_notification_candidate" in bank["delivery_targets_allowed"]
    assert "telegram_candidate" in niles["delivery_targets_allowed"]
    assert "presentation candidates only" in policy["candidate_delivery_policy"]
    assert "not sends" in policy["candidate_delivery_policy"]
    assert bank["telegram_send_allowed"] is False
    assert bank["push_allowed"] is False
    assert bank["email_send_allowed"] is False
    assert payload["machine_proof"]["candidate_delivery_only"] is True


def test_capital_hilton_fixture_uses_fixture_refs_not_fake_live_paths():
    payload = _payload()
    item = _item(payload, "cassandra_capital_hilton_invoice_reminder")
    rendered = json.dumps(item).lower()

    assert item["world_ref"] == "finance"
    assert item["client_ref"] == "capital_hilton"
    assert item["workflow_ref"] == "capital_hilton_invoice_workflow"
    assert item["actor_label"] == "Cassandra"
    assert item["fixture_ref"] == "capital_hilton_invoice_workbook_candidate"
    assert item["linked_local_surface_request"]["surface_type"] in {"OPEN_FILE_PICKER", "SHOW_FIELD_MAPPING_PANEL"}
    assert "/mnt/" not in rendered
    assert "/volumes/" not in rendered
    assert "/users/" not in rendered
    assert "fake po" not in rendered
    assert "sent" not in item["human_message"].lower()
    assert payload["machine_proof"]["capital_hilton_fixture_uses_fixture_ref_only"] is True


def test_bank_ledger_stale_maps_to_statement_intake_local_surface():
    item = _item(_payload(), "chief_bank_ledger_stale")
    linked = item["linked_local_surface_request"]

    assert item["actor_label"] == "Chief"
    assert item["workflow_ref"] == "bank_ledger_update"
    assert item["primary_human_action_label"] == "Update ledger"
    assert linked["surface_type"] == "OPEN_FILE_PICKER"
    assert linked["human_label"] == "Choose bank statement"
    assert ".pdf" in linked["allowed_file_extensions"]
    _assert_no_live_authority(item)


def test_guardian_protected_file_maps_to_confirmation_boundary_surface():
    item = _item(_payload(), "guardian_protected_file_boundary")
    linked = item["linked_local_surface_request"]

    assert item["actor_label"] == "Guardian"
    assert item["reason_for_attention"] == "protected_boundary_decision"
    assert item["required_confirmation"] is True
    assert linked["surface_type"] == "SHOW_CONFIRMATION_CARD"
    assert linked["human_label"] == "Review boundary"
    assert linked["requires_operator_confirmation"] is True
    assert linked["safe_to_auto_open"] is False
    _assert_no_live_authority(item)


def test_niles_music_item_is_cross_domain_and_not_invoice_specific():
    item = _item(_payload(), "niles_music_scene_file")
    rendered = json.dumps(item).lower()

    assert item["world_ref"] == "music"
    assert item["workflow_ref"] == "x32_scene_or_monitor_mix"
    assert item["actor_label"] == "Niles"
    assert item["linked_local_surface_request"]["surface_type"] == "OPEN_FILE_PICKER"
    assert ".x32" in item["linked_local_surface_request"]["allowed_file_extensions"]
    assert "capital_hilton" not in rendered
    assert "invoice" not in rendered
    _assert_no_live_authority(item)


def test_generated_json_parses_and_operator_markdown_exports(tmp_path, capsys):
    assert export_main(["--export-root", str(tmp_path), "--generated-at", FIXED_NOW, "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads((tmp_path / attention.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (tmp_path / attention.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert summary["read_model_id"] == attention.READ_MODEL_ID
    assert summary["attention_item_count"] == 5
    assert summary["local_surface_contract_bound"] is True
    assert summary["all_items_validate"] is True
    assert payload["readback"]["status"] == "OPERATOR_ATTENTION_DELIVERY_CONTRACT_READY"
    assert "Attention contract only" in operator
    assert "Cassandra" in operator
    assert "Niles" in operator


def test_generated_outputs_have_no_active_authority_or_private_body_values(tmp_path):
    payload = _payload()
    attention.write_exports(payload, tmp_path)
    combined = (tmp_path / attention.JSON_EXPORT_NAME).read_text(encoding="utf-8") + "\n" + (
        tmp_path / attention.OPERATOR_EXPORT_NAME
    ).read_text(encoding="utf-8")
    lowered = combined.lower()

    assert payload["machine_proof"]["all_live_authority_false"] is True
    assert not re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", combined)
    for forbidden in (
        "actual secret",
        "credential value",
        "password value",
        "raw private body value",
        "workbook body value",
        "cell value",
        "telegram sent",
        "email sent",
        "invoice submitted",
        "fake receipt",
    ):
        assert forbidden not in lowered
