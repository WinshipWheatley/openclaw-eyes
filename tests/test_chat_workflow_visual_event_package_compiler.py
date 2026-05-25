import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import chat_workflow_visual_event_package_compiler as compiler
from scripts.export_chat_workflow_visual_event_package_compiler import main as export_main


FIXED_NOW = "2026-05-25T23:15:00+00:00"


def _payload() -> dict:
    return compiler.build_payload(generated_at=FIXED_NOW)


def test_required_models_exist():
    for name in [
        "ChatWorkflowVisualEventPackageCompiler",
        "VisualEventType",
        "VisualPromptPackage",
        "VisualProviderPolicy",
        "VisualMetaphorMapping",
        "VisualPrivacyPolicy",
        "VisualEventReadback",
        "VisualEventBlocker",
    ]:
        assert hasattr(compiler, name)
        assert name in _payload()["model_schemas"]


def test_event_taxonomy_provider_policy_metaphors_and_privacy_exist():
    payload = _payload()
    event_types = {row["event_type"]: row for row in payload["visual_event_types"]}
    mappings = {row["event_type"]: row for row in payload["visual_metaphor_mappings"]}
    privacy = {row["privacy_class"]: row for row in payload["visual_privacy_policies"]}

    for event_type in compiler.EVENT_TYPES:
        assert event_type in event_types
        assert event_type in mappings
    assert event_types["COMPLETION_CONFIRMED"]["default_metaphor"] == "perfect_game_sweep"
    assert mappings["BLOCKED_MISSING_INPUT"]["metaphor_style"] == "bowling_single_pin_left"
    assert mappings["BLOCKED_APPROVAL_REQUIRED"]["metaphor_style"] == "guardian_checkpoint_lock"
    assert mappings["BLOCKED_SECRET_REQUIRED"]["metaphor_style"] == "protected_safe_box"
    assert privacy["CLIENT_PRIVATE"]["safe_to_send_to_cloud"] is False
    assert privacy["PROTECTED_SECRET"]["safe_to_send_to_cloud"] is False
    assert "raw PO numbers" in privacy["CLIENT_PRIVATE"]["blocked_from_prompt"]


def test_capital_hilton_missing_po_visual_blocks_cloud_and_success_claims():
    example = _payload()["examples"]["capital_hilton_missing_po"]
    package = example["visual_package"]
    provider = example["provider_policy"]

    assert package["visual_event_type"] == "BLOCKED_MISSING_INPUT"
    assert package["metaphor_style"] == "bowling_single_pin_left"
    assert "invoice basis exists" in package["allowed_visual_facts"]
    assert "missing Coupa PO/reference" in package["allowed_visual_facts"]
    assert "invoice sent" in package["forbidden_visual_claims"]
    assert "Coupa invoice submitted" in package["forbidden_visual_claims"]
    assert "payment updated" in package["forbidden_visual_claims"]
    assert "approval complete" in package["forbidden_visual_claims"]
    assert provider["preferred_provider_family"] == "MAC_ANIMATION_NATIVE"
    assert provider["cloud_generation_allowed"] is False
    assert "VIDEO_MODEL_CLOUD_GATED" in provider["blocked_provider_families"]
    assert example["readback"]["status"] == "VISUAL_PACKAGE_LOCAL_ANIMATION_READY"


def test_file_reference_captured_visual_does_not_claim_analysis():
    example = _payload()["examples"]["file_reference_captured"]
    package = example["visual_package"]

    assert package["visual_event_type"] == "FILE_REFERENCE_CAPTURED"
    assert package["metaphor_style"] == "source_object_into_folder"
    assert "file reference captured" in package["allowed_visual_facts"]
    assert "file body not read" in package["allowed_visual_facts"]
    assert "file analyzed" in package["forbidden_visual_claims"]
    assert "contents extracted" in package["forbidden_visual_claims"]
    assert package["provider_policy"]["preferred_provider_family"] == "STATIC_VISUAL_CARD"
    assert package["provider_policy"]["cloud_generation_allowed"] is False


def test_completion_confirmed_fixture_is_receipt_bound():
    example = _payload()["examples"]["completion_confirmed_fixture"]
    package = example["visual_package"]

    assert example["completion_receipts_modeled_present"] is True
    assert package["visual_event_type"] == "COMPLETION_CONFIRMED"
    assert package["truth_state"] == "COMPLETION_CONFIRMED"
    assert package["metaphor_style"] == "perfect_game_sweep"
    assert package["proof_refs"] == ("generated/read_models/invoice_delivery_completion_proof_aggregator.json",)
    assert package["provider_policy"]["async_generation_only"] is True
    assert package["provider_policy"]["cloud_generation_allowed"] is False
    assert example["readback"]["status"] == "VISUAL_PACKAGE_LOCAL_ANIMATION_READY"


def test_false_strike_blocked_fail_closed():
    example = _payload()["examples"]["false_strike_blocked"]
    attempted = example["attempted_visual_package"]

    assert attempted["visual_event_type"] == "SUCCESS_CONFIRMED"
    assert attempted["truth_state"] == "BLOCKED_MISSING_INPUT"
    assert attempted["metaphor_style"] == "bowling_strike_clean_sweep"
    assert example["blocker_type"] == "FALSE_SUCCESS_VISUAL_CLAIM"
    assert example["fail_closed"] is True
    assert example["readback"]["status"] == "BLOCKED_FALSE_VISUAL_CLAIM"
    assert "FALSE_SUCCESS_VISUAL_CLAIM" in example["readback"]["blocked_items"]


def test_guardian_approval_required_visual_is_strict():
    example = _payload()["examples"]["guardian_approval_required"]
    package = example["visual_package"]

    assert package["visual_event_type"] == "BLOCKED_APPROVAL_REQUIRED"
    assert package["response_author"] == "GUARDIAN"
    assert package["agent_vibe"] == "vibe:guardian:strict_proof"
    assert package["metaphor_style"] == "guardian_checkpoint_lock"
    assert "approval/proof gate missing" in package["allowed_visual_facts"]
    assert "approval complete" in package["forbidden_visual_claims"]
    assert package["provider_policy"]["cloud_generation_allowed"] is False


def test_blockers_exist_and_fail_closed():
    blockers = {row["blocker_type"]: row for row in _payload()["visual_event_blockers"]}

    for blocker_type in compiler.BLOCKER_TYPES:
        assert blocker_type in blockers
        assert blockers[blocker_type]["fail_closed"] is True
    assert blockers["FALSE_SUCCESS_VISUAL_CLAIM"]["severity"] == "critical"
    assert blockers["PROVIDER_CALL_ATTEMPTED"]["severity"] == "critical"


def test_all_live_authority_false_and_provider_calls_not_made():
    payload = _payload()

    assert payload["machine_proof"]["all_live_authority_false"] is True
    assert payload["machine_proof"]["provider_calls_made"] is False
    for key, value in payload["authority_boundary"].items():
        assert value is False, key
    for key in [
        "video_generation_performed",
        "image_generation_performed",
        "cloud_model_call_performed",
        "local_model_call_performed",
        "visual_asset_generation_performed",
        "visual_playback_performed",
        "external_action_performed",
        "workflow_run_performed",
        "agent_dispatch_performed",
        "credential_handling_performed",
        "raw_body_ingestion_performed",
        "mac_sync_import_performed",
        "swift_change_performed",
        "git_push_performed",
        "network_used",
    ]:
        assert payload["machine_proof"][key] is False


def test_export_writes_json_and_operator_markdown(tmp_path, capsys):
    assert export_main(["--export-root", str(tmp_path), "--generated-at", FIXED_NOW, "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads((tmp_path / compiler.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (tmp_path / compiler.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert summary["read_model_id"] == compiler.READ_MODEL_ID
    assert summary["capital_hilton_event"] == "BLOCKED_MISSING_INPUT"
    assert summary["file_capture_event"] == "FILE_REFERENCE_CAPTURED"
    assert summary["completion_fixture_event"] == "COMPLETION_CONFIRMED"
    assert summary["false_strike_blocker"] == "FALSE_SUCCESS_VISUAL_CLAIM"
    assert summary["guardian_event"] == "BLOCKED_APPROVAL_REQUIRED"
    assert summary["all_live_authority_false"] is True
    assert summary["provider_calls_made"] is False
    assert payload["schema_version"] == compiler.SCHEMA_VERSION
    assert "Chat Workflow Visual Event Package Compiler" in operator
    assert "No video generation" in operator


def test_generated_outputs_have_no_credentials_private_bodies_or_raw_prompt_data(tmp_path):
    payload = _payload()
    compiler.write_exports(payload, tmp_path)
    text = "\n".join(path.read_text(encoding="utf-8") for path in tmp_path.iterdir())

    assert "actual secret" not in text.lower()
    assert "raw private body value" not in text.lower()
    assert "credential value" not in text.lower()
    assert "token value" not in text.lower()
    assert "database schema value" not in text.lower()
    assert "raw email address value" not in text.lower()
    assert "raw provider id value" not in text.lower()
    assert "AKIA" not in text
    assert not re.search(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", text)
    prompt_text = json.dumps(payload["examples"], sort_keys=True)
    assert not re.search(r"sha256:[0-9a-f]{32,}", prompt_text.lower())
    assert not re.search(r"/Users/|/home/|/mnt/|C:\\\\", text)
