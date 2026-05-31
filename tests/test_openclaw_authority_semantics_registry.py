import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import openclaw_authority_semantics_registry as registry
from scripts.export_openclaw_authority_semantics_registry import main as export_main


FIXED_NOW = "2026-05-31T15:00:00+00:00"


def _payload() -> dict:
    return registry.build_registry_payload(generated_at=FIXED_NOW)


def test_registry_export_creates_json_operator_sqlite_schema_and_seed(tmp_path):
    read_root = tmp_path / "generated" / "read_models"
    system_root = tmp_path / "generated" / "system_knowledge"

    assert export_main(
        [
            "--read-model-root",
            str(read_root),
            "--system-knowledge-root",
            str(system_root),
            "--generated-at",
            FIXED_NOW,
        ]
    ) == 0

    json_path = read_root / registry.JSON_EXPORT_NAME
    operator_path = read_root / registry.OPERATOR_EXPORT_NAME
    sqlite_path = system_root / registry.SQLITE_EXPORT_NAME
    schema_path = system_root / registry.SCHEMA_EXPORT_NAME
    seed_path = system_root / registry.SEED_EXPORT_NAME

    assert json.loads(json_path.read_text(encoding="utf-8"))["schema_version"] == registry.SCHEMA_VERSION
    assert operator_path.exists()
    assert sqlite_path.exists()
    assert schema_path.exists()
    assert seed_path.exists()

    connection = sqlite3.connect(sqlite_path)
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert set(registry.REQUIRED_SQLITE_TABLES).issubset(tables)
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        connection.close()


def test_seeded_field_semantics_distinguish_prohibitions_from_grants():
    payload = _payload()
    fields = {row["field_name"]: row for row in payload["authority_field_semantics"]}

    assert fields["no_browser"]["field_family"] == "PROHIBITION_FLAG"
    assert "AUTHORITY_BOUNDARY" in fields["no_browser"]["forbidden_locations"]
    assert fields["no_browser"]["positive_replacement_field"] == "browser_access_allowed"
    assert fields["browser_access_allowed"]["field_family"] == "AUTHORITY_GRANT"
    assert fields["browser_access_allowed"]["default_value"] is False


def test_event_bridge_finance_profile_requires_safe_shape():
    payload = _payload()
    profile = {
        row["profile_ref"]: row for row in payload["authority_profiles"]
    }["event_bridge_finance_workflow_action_v0"]

    assert "safety_flags.no_browser" in profile["required_fields"]
    assert "authority_boundary.browser_access_allowed" in profile["required_fields"]
    assert "authority_boundary.no_browser" in profile["forbidden_fields"]
    assert "ledger_post_allowed" in profile["dangerous_authorities"]
    assert "execute PDF export" in profile["blocked_actions"]


def test_authority_boundary_no_browser_true_is_blocked_with_replacement_guidance():
    envelope = {
        **registry.build_registry_payload(generated_at=FIXED_NOW)["golden_path_fixtures"][0]["payload_json"],
        "authority_boundary": {"no_browser": True},
    }

    result = registry.validate_authority_semantics(envelope)

    assert result.valid is False
    assert result.errors[0] == "AUTHORITY_SEMANTICS_DRIFT:WRONG_BOOLEAN_POLARITY:authority_boundary.no_browser"
    assert result.positive_replacement_guidance["positive_replacement"] == "event_bridge_finance_workflow_action_template"
    assert result.positive_replacement_guidance["correct_safety_flags"]["no_browser"] is True
    assert result.positive_replacement_guidance["correct_authority_boundary"]["browser_access_allowed"] is False


def test_correct_safety_flags_and_denied_authority_boundary_pass_semantics():
    envelope = registry.build_registry_payload(generated_at=FIXED_NOW)["golden_path_fixtures"][0]["payload_json"]

    result = registry.validate_authority_semantics(envelope)

    assert result.valid is True
    assert result.errors == ()
    assert envelope["safety_flags"]["no_browser"] is True
    assert envelope["authority_boundary"]["browser_access_allowed"] is False


def test_dangerous_ledger_grant_and_missing_mutation_guard_emit_drift():
    envelope = registry.build_registry_payload(generated_at=FIXED_NOW)["golden_path_fixtures"][0]["payload_json"]
    envelope = {**envelope, "authority_boundary": dict(envelope["authority_boundary"])}
    envelope["authority_boundary"]["ledger_post_allowed"] = True
    envelope["safety_flags"] = dict(envelope["safety_flags"])
    envelope["safety_flags"].pop("operator_receipt_required_before_mutation")

    result = registry.validate_authority_semantics(envelope)
    drift_types = {signal["drift_type"] for signal in result.drift_signals}

    assert result.valid is False
    assert "UNSAFE_TRUE_GRANT" in drift_types
    assert "MISSING_REQUIRED_FIELD" in drift_types


def test_legacy_chat_and_business_mutation_without_receipt_emit_blocking_drift():
    envelope = registry.build_registry_payload(generated_at=FIXED_NOW)["golden_path_fixtures"][0]["payload_json"]
    envelope = {**envelope, "safety_flags": dict(envelope["safety_flags"])}
    envelope["safety_flags"]["legacy_chat_card_live_action_source_allowed"] = True
    envelope["safety_flags"]["business_mutation_without_receipt_allowed"] = True

    signals = registry.detect_authority_drift(envelope)
    by_type = {signal["drift_type"]: signal for signal in signals}

    assert by_type["LEGACY_CHAT_ACTION_ALLOWED"]["severity"] == "BLOCKER"
    assert by_type["MUTATION_WITHOUT_RECEIPT"]["severity"] == "CRITICAL"
    assert by_type["MUTATION_WITHOUT_RECEIPT"]["positive_replacement"] == "guardian_receipt_required_mutation_template"


def test_remediation_policies_do_not_silently_delete_or_mutate_without_receipts():
    payload = _payload()
    policies = payload["authority_remediation_policies"]

    assert all(policy["auto_remove_allowed"] is False for policy in policies)
    assert payload["machine_proof"]["no_policy_allows_silent_deletion"] is True
    assert payload["machine_proof"]["no_policy_allows_business_mutation_without_receipt"] is True
    assert {
        "AUTO_REGENERATE_DERIVED_VIEW",
        "PROPOSE_FIX",
        "CREATE_CHIEF_WORK_PACKAGE",
        "FREEZE_RAIL",
    }.issuperset(
        {
            policy["default_response"]
            for policy in policies
            if policy["drift_type"] in {"STALE_GENERATED_VIEW", "DUPLICATED_AUTHORITY_SEMANTICS", "ENTRENCHED_DRIFT"}
        }
    )


def test_positive_templates_golden_fixtures_and_device_shards_are_seeded():
    payload = _payload()

    assert {
        row["template_ref"] for row in payload["positive_occupation_templates"]
    } == {
        "event_bridge_finance_workflow_action_template",
        "event_bridge_finance_response_template",
        "live_arts_prepare_pdf_event_template",
        "telegram_finance_command_template",
        "mac_app_event_bridge_writer_template",
        "mac_excel_helper_authority_template",
        "guardian_receipt_required_mutation_template",
    }
    assert len(payload["golden_path_fixtures"]) == 7
    assert {
        row["device_ref"] for row in payload["device_authority_shards"]
    } == {
        "device:pc_backend",
        "device:mac_app",
        "device:mac_excel_helper_planned",
        "device:telegram_compact_surface",
        "device:runtime_actors",
    }
    assert all(row["payload_json"] for row in payload["golden_path_fixtures"])


def test_operator_summary_avoids_metaphor_and_backend_sludge():
    text = registry.format_operator_readback(_payload())

    assert "weed" not in text.lower()
    assert "crop" not in text.lower()
    assert "sunlight" not in text.lower()
    assert "hidden_request_payload" not in text
    assert "backend sludge" not in text.lower()
    assert "no_browser" in text
    assert "browser_access_allowed" in text
