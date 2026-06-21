from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import openclaw_system_knowledge_registry as registry


def _read_json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_protected_currencies_map_has_all_10_source_currencies() -> None:
    payload = _read_json("generated/read_models/protected_currencies_map.json")
    currencies = {row["display_name"]: row for row in payload["currencies"]}

    assert payload["status"] == "READ_ONLY_DESIGN"
    assert set(currencies) == {
        "Money",
        "Time",
        "Attention",
        "Mental energy",
        "Technical complexity",
        "Operational risk",
        "Creative momentum",
        "Reputation",
        "Relationship capital",
        "Future maintenance burden",
    }
    assert currencies["Money"]["primary_agent"] == "clara"
    assert currencies["Time"]["primary_agent"] == "clara"
    assert currencies["Reputation"]["primary_agent"] == "clara"
    assert currencies["Technical complexity"]["primary_agent"] == "hermes"
    assert currencies["Future maintenance burden"]["primary_agent"] == "hermes"
    assert currencies["Creative momentum"]["primary_agent"] == "niles"
    assert payload["authority_boundary"]["live_decision_authority_granted"] is False
    assert payload["authority_boundary"]["send_or_money_action_allowed"] is False


def test_recommendation_postures_are_exact_controlled_states() -> None:
    payload = _read_json("generated/read_models/recommendation_postures.json")
    postures = [row["posture"] for row in payload["controlled_states"]]

    assert postures == [
        "SUFFICIENT",
        "SMALLER FIT",
        "NOT YET",
        "OPTIONAL ENHANCEMENT",
        "PREMIUM JUSTIFIED",
        "NO ACTION",
        "WRONG FIT",
        "NEEDS ONE FACT",
    ]
    for row in payload["controlled_states"]:
        assert row["meaning"]
        assert row["allowed_when"]
        assert row["not_allowed_when"]
    assert payload["authority_boundary"]["active_prompt_mutation"] is False


def test_advice_integrity_receipt_schema_has_13_doctrine_fields_and_sqlite_table(tmp_path: Path) -> None:
    required = registry.ADVICE_INTEGRITY_RECEIPT_REQUIRED_FIELDS
    payload = registry.build_registry(Path.cwd())
    schema = payload["advice_integrity_receipt_schema"]

    assert len(required) == 13
    assert tuple(schema["required_fields"]) == required
    assert "trust_gear_state" in required
    assert "minimum_sufficient_option" in required
    assert "verified_constraints" in required
    assert registry.TABLE_COLUMNS["advice_integrity_receipt"] == (
        "receipt_id",
        *required,
        "generated_at",
        "status",
    )

    result = registry.export_registry(tmp_path)
    sqlite_path = result["paths"]["sqlite"]
    with sqlite3.connect(sqlite_path) as conn:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(advice_integrity_receipt)")]
        count = conn.execute("SELECT COUNT(*) FROM advice_integrity_receipt").fetchone()[0]

    assert columns == list(registry.TABLE_COLUMNS["advice_integrity_receipt"])
    assert count == 0
    assert schema["authority_boundary"]["autonomous_decline_or_task_drop"] is False
    assert schema["authority_boundary"]["client_send_allowed"] is False


def test_authority_trust_gear_progresses_without_day_one_autonomy() -> None:
    payload = _read_json("generated/read_models/authority_trust_gear.json")
    actions = {row["action_id"]: row for row in payload["high_risk_actions"]}

    assert set(actions) == {"DECLINE_CLIENT_WORK", "PARK_OPERATOR_TASK"}
    assert payload["default_level"] == "LEVEL_1_RECOMMEND_ONLY"
    assert payload["receipt_integration"]["receipt_schema_id"] == "Advice_Integrity_Receipt"
    assert payload["receipt_integration"]["required_receipt_field"] == "trust_gear_state"
    for action in actions.values():
        levels = {row["level"]: row for row in action["levels"]}
        assert set(levels) == {
            "LEVEL_1_RECOMMEND_ONLY",
            "LEVEL_2_CONDITIONAL_AUTONOMY",
            "LEVEL_3_FULL_AUTONOMY",
        }
        assert "5 approved Level 1" in levels["LEVEL_2_CONDITIONAL_AUTONOMY"]["unlock_condition"]
        assert "10 successful Level 2" in levels["LEVEL_3_FULL_AUTONOMY"]["unlock_condition"]
        assert all(row["allowed_without_operator"] is False for row in action["levels"])
    assert payload["authority_boundary"]["day_one_autonomy_granted"] is False
    assert payload["authority_boundary"]["live_task_deletion_allowed"] is False
