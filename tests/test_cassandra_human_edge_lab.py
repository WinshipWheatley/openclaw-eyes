import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cassandra_human_edge_lab as lab
import cassandra_guided_review as guided_review
import global_run_mode_context


FIXED_NOW = "2026-06-13T21:30:00+00:00"


@pytest.fixture(autouse=True)
def promotion_review_fixture(tmp_path, monkeypatch):
    review_root = tmp_path / "promotion_review_fixture"
    review_root.mkdir()
    promotion_review_path = review_root / guided_review.DEFAULT_PROMOTION_REVIEW_FILENAME
    promotion_review_path.write_text(
        json.dumps(
            {
                "schema_version": "openclaw_data_room_promotion_review_v0",
                "authoritative": False,
                "source_artifacts": ["test_fixture"],
                "review_records": [
                    {
                        "record_id": "fixture:payment_privacy",
                        "review_category": "policy_decision",
                        "provisional_fact": "Trusted clients may receive easy payment options; strangers must not see bank details or private address.",
                        "proposed_promoted_value": "Should trusted clients receive easy payment options while strangers are blocked from private payment details?",
                        "recommended_action": "confirm",
                        "risk_if_wrong": "Private payment details could be exposed to the wrong audience.",
                    },
                    {
                        "record_id": "fixture:invoice_numbering",
                        "review_category": "needs_source",
                        "provisional_fact": "Invoice numbering policy still needs an exact operator source.",
                        "proposed_promoted_value": "",
                        "recommended_action": "source_needed",
                        "risk_if_wrong": "OpenClaw could draft invoices with the wrong numbering convention.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(guided_review, "DEFAULT_DURABLE_PROMOTION_REVIEW_PATH", promotion_review_path)
    monkeypatch.setattr(guided_review, "DEFAULT_LEGACY_DURABLE_PROMOTION_REVIEW_PATH", promotion_review_path)


def _unsafe_true_paths(value, path="$"):
    unsafe = {
        "raw_log_body_ingested",
        "live_model_called",
        "telegram_send_performed",
        "gmail_called",
        "email_sent",
        "calendar_called",
        "calendar_api_called",
        "calendar_event_created",
        "calendar_event_deleted",
        "external_api_called",
        "confirmed_reference_data_created",
        "hydration_performed",
        "production_write_performed",
        "external_effect",
        "email_send_performed",
    }
    found = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in unsafe and child is True:
                found.append(child_path)
            found.extend(_unsafe_true_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_unsafe_true_paths(child, f"{path}[{index}]"))
    return found


def test_conversation_source_catalog_does_not_ingest_raw_logs(tmp_path):
    raw = tmp_path / "cassandra_conversations.jsonl"
    raw.write_text('{"user": "private raw body"}\n', encoding="utf-8")

    sources = lab.discover_cassandra_conversation_sources(
        [(raw, "raw_cassandra_conversation_log", "raw_debug_log_catalog_only")]
    )

    assert sources[0]["exists"] is True
    assert sources[0]["line_count"] == 1
    assert sources[0]["raw_content_sampled"] is False
    assert sources[0]["raw_body_ingested"] is False
    assert "private raw body" not in json.dumps(sources)
    assert sources[0]["test_marker"] == global_run_mode_context.TEST_MARKER


def test_data_room_human_edge_lab_records_only_confirmed_candidate_in_test_mode(tmp_path):
    result = lab.run_data_room_human_edge_scenario(lab_root=tmp_path / "lab", generated_at=FIXED_NOW)

    assert result["run_mode"] == global_run_mode_context.TEST_DRY_RUN
    assert result["test_marker"] == global_run_mode_context.TEST_MARKER
    assert result["answer_count"] == 1
    assert result["pending_interaction_empty"] is True
    assert "ask_eli5" in result["coach_interaction_commands"]
    assert "recommend" in result["coach_interaction_commands"]
    assert "pending_answer_candidate_confirmed" in result["coach_interaction_commands"]
    assert result["unsafe_true_paths"] == []
    assert Path(result["review_root"], "human_edge_transcript_summary.json").is_file()


def test_data_room_human_edge_lab_is_repeatable_without_accumulating_answers(tmp_path):
    first = lab.run_data_room_human_edge_scenario(lab_root=tmp_path / "lab", generated_at=FIXED_NOW)
    second = lab.run_data_room_human_edge_scenario(lab_root=tmp_path / "lab", generated_at=FIXED_NOW)

    assert first["answer_count"] == 1
    assert second["answer_count"] == 1
    assert second["pending_interaction_empty"] is True
    assert second["unsafe_true_paths"] == []


def test_blank_active_session_path_does_not_read_cwd_directory(tmp_path, monkeypatch):
    root = tmp_path / "lab" / "data_room"
    root.mkdir(parents=True)
    (root / "data_room_guided_review_active_session.json").write_text(
        json.dumps(
            {
                "schema_version": "guided_review_active_session_index_v0",
                "review_session_id": "fixture",
                "session_path": "",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    session_path, session = lab._load_active_guided_review_session(root)

    assert session_path is None
    assert session == {}


def test_router_human_edge_lab_uses_test_effects_and_blocks_calendar_mutation(tmp_path):
    result = lab.run_router_human_edge_scenario(lab_root=tmp_path / "lab", generated_at=FIXED_NOW)
    by_case = {item["case_id"]: item for item in result["results"]}

    assert result["run_mode"] == global_run_mode_context.TEST_DRY_RUN
    assert result["test_marker"] == global_run_mode_context.TEST_MARKER
    assert by_case["coworker_help"]["headline"] == "Payment evidence needed"
    assert "payment evidence" in by_case["coworker_help"]["plain_summary"].lower()
    assert "stronger proof" not in by_case["coworker_help"]["plain_summary"].lower()
    assert by_case["dry_run_email"]["test_effect_status"] in {"DRY_RUN_RECORDED", "DRY_RUN_ONLY"}
    assert by_case["dry_run_email"]["test_effect_actual_target"] == "winshiplive@gmail.com"
    assert by_case["dry_run_email"]["external_effect"] is False
    assert by_case["dry_run_email"]["email_send_performed"] is False
    assert by_case["calendar_test_gap"]["test_effect_status"] == "DRY_RUN_RECORDED"
    assert by_case["calendar_test_gap"]["route_status"] == "TEXT_RESPONSE_READY"
    assert by_case["calendar_test_gap"]["calendar_api_called"] is False
    assert by_case["calendar_test_gap"]["calendar_event_created"] is False
    assert by_case["calendar_test_gap"]["calendar_event_deleted"] is False
    assert result["calendar_test_adapter_status"] == "dry_run_calendar_receipt_recorded_no_calendar_call_performed"
    assert _unsafe_true_paths(result) == []
    assert result["unsafe_true_paths"] == []


def test_full_human_edge_lab_writes_test_marked_read_model(tmp_path):
    payload = lab.run_human_edge_lab(
        lab_root=tmp_path / "lab",
        export_root=tmp_path / "read_models",
        generated_at=FIXED_NOW,
    )

    read_model = json.loads(Path(payload["read_model_path"]).read_text(encoding="utf-8"))

    assert payload["status"] == "CASSANDRA_HUMAN_EDGE_LAB_READY"
    assert payload["test_marker"] == global_run_mode_context.TEST_MARKER
    assert payload["safety_confirmation"]["raw_logs_cataloged_not_ingested"] is True
    assert payload["safety_confirmation"]["no_external_actions"] is True
    assert payload["safety_confirmation"]["all_outputs_test_marked"] is True
    assert read_model["read_model_id"] == lab.READ_MODEL_ID
    assert read_model["unsafe_true_paths"] == []
    assert Path(payload["lab_summary_path"]).is_file()
