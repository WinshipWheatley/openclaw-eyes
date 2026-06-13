import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import watch_desk_feed as feed
import openclaw_gemini_form_adapter as gemini


FIXED_NOW = "2026-06-10T21:10:00+00:00"


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_task(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _write_empty_intake(read_model_root: Path) -> None:
    path = read_model_root / "operator_intake_events.json"
    if path.exists():
        return
    _write_json(
        path,
        {
            "schema_version": "operator_intake_events_read_model_v0",
            "generated_at": FIXED_NOW,
            "events": [],
            "watch_desk_items": [],
        },
    )


def _build(read_model_root: Path, task_root: Path | None = None, previous=None, *, intake_stub: bool = True) -> dict:
    if intake_stub:
        _write_empty_intake(read_model_root)
    return feed.build_watch_desk_feed(
        read_model_root=read_model_root,
        task_root=task_root or read_model_root / "tasks",
        generated_at=FIXED_NOW,
        previous_item_states=previous,
    )


def _pending_approval_queue() -> dict:
    return {
        "approval_requests": [
            {
                "approval_request_id": "approval_request:one",
                "status": "pending",
                "requested_action": "approve_existing_packet",
                "plain_summary": "Do not copy this unsafe private raw body: winship@example.test",
            }
        ]
    }


def _intake_event(
    *,
    intake_id: str = "operator_intake:test",
    action_type: str = "income_payment_log",
    lane: str = "cassandra_finance",
    surface: str = "local_cli",
    receipt_path: str = "/tmp/openclaw-mission-control/receipts/operator_intake_test_receipt.json",
    received_at: str = "2026-06-10T21:00:00+00:00",
    summary: str = "Logged income: $900 from Live Arts MD.",
    watch_item: bool = False,
) -> dict:
    event = {
        "schema_version": "OPERATOR_INTAKE_EVENT_V0",
        "intake_id": intake_id,
        "surface": surface,
        "received_at_utc": received_at,
        "normalized_summary": summary,
        "parsed": {
            "action_type": action_type,
            "lane": lane,
            "fields": {},
        },
        "receipts": [
            {
                "path": receipt_path,
                "receipt_id": "operator_intake_receipt:test",
            }
        ],
        "watch_desk_items": [],
        "raw_text": "This raw source body must not be copied.",
        "raw_text_stored": True,
    }
    if watch_item:
        event["watch_desk_items"] = [
            {
                "item_id": f"operator_intake:{intake_id}",
                "intake_id": intake_id,
                "action_type": action_type,
                "lane": "cassandra_ar",
                "urgency": "watch",
                "plain_line": summary,
                "source_receipt_ref": f"{receipt_path}#receipt",
                "one_next_safe_action": "Review the local receipt; keep external mutation behind the existing approval spine.",
                "push_class": "on_demand",
            }
        ]
    return event


def _operator_intake_read_model(events: list[dict], *, generated_at: str = FIXED_NOW) -> dict:
    watch_items = []
    for event in events:
        watch_items.extend(event.get("watch_desk_items", []))
    return {
        "schema_version": "operator_intake_events_read_model_v0",
        "generated_at": generated_at,
        "events": events,
        "event_count": len(events),
        "watch_desk_items": watch_items,
    }


def test_approval_waiting_fixture_produces_exactly_one_item(tmp_path):
    _write_json(tmp_path / "approval_request_queue.json", _pending_approval_queue())

    payload = _build(tmp_path)

    assert payload["item_count"] == 1
    item = payload["feed_items"][0]
    assert item["lane"] == "guardian_approval"
    assert item["urgency"] == "needs_operator"
    assert item["source_receipt_ref"] == "generated/read_models/approval_request_queue.json#pending"
    assert item["push_candidate"] is True
    assert item["push_allowed"] is False


def test_cassandra_ar_send_authority_waiting_fixture_produces_exactly_one_item(tmp_path):
    _write_json(
        tmp_path / "cassandra_draft_worker_readback.json",
        {
            "request": {
                "request_id": "cassandra_request:one",
                "approval_required": True,
                "send_authority": False,
            },
            "readback": {
                "status": "DRAFT_READY_FOR_REVIEW",
                "approval_required": True,
                "operator_message": "Unsafe private raw body winship@example.test must not appear.",
            },
        },
    )

    payload = _build(tmp_path)

    assert payload["item_count"] == 1
    item = payload["feed_items"][0]
    assert item["lane"] == "cassandra_ar"
    assert item["urgency"] == "needs_operator"
    assert item["source_receipt_ref"] == "generated/read_models/cassandra_draft_worker_readback.json#readback"
    assert item["push_candidate"] is True
    assert item["push_allowed"] is False


def test_reply_timeout_failure_task_fixture_produces_exactly_one_item(tmp_path):
    task_root = tmp_path / "tasks"
    _write_task(
        task_root / "chief-cassandra-failure-20260610T205623.md",
        """title: chief-cassandra-failure-20260610T205623
profile: quick
goal: Investigate a reply timeout
scope:
- Request summary: unsafe private body with winship@example.test and quoted client text
success:
- Root cause identified
generated_by: chief_cassandra_failure
generated_at: 2026-06-10T20:56:23.068137
""",
    )

    payload = _build(tmp_path, task_root)

    assert payload["item_count"] == 1
    item = payload["feed_items"][0]
    assert item["lane"] == "cassandra_ar"
    assert item["urgency"] == "blocked"
    assert item["source_receipt_ref"].endswith("#generated_by")
    assert item["push_candidate"] is True
    assert item["push_allowed"] is False


def test_stale_sync_fixture_produces_exactly_one_item(tmp_path):
    _write_json(
        tmp_path / "sync_health.json",
        {
            "display_status": "needs_mac_sync",
            "mirror_status": "needs_mac_sync",
            "missing_expected": 2,
            "hash_mismatch": 1,
            "generated_at": FIXED_NOW,
        },
    )

    payload = _build(tmp_path)

    assert payload["item_count"] == 1
    item = payload["feed_items"][0]
    assert item["lane"] == "mac_sync"
    assert item["urgency"] == "watch"
    assert item["source_receipt_ref"] == "generated/read_models/sync_health.json#mirror_status"
    assert item["push_candidate"] is False
    assert item["push_allowed"] is False


def test_pending_model_consult_permission_fixture_produces_watch_item(tmp_path):
    _write_json(
        tmp_path / "model_work_package_router_status.json",
        {
            "schema_version": "model_work_package_router_status_v0",
            "watch_desk_items": [
                {
                    "item_id": "model_consult_permission:fixture",
                    "lane": "guardian_approval",
                    "urgency": "needs_operator",
                    "plain_line": "Model consult permission pending for Fable 5-class.",
                    "source_receipt_ref": "model_consult_permission:fixture#permission_request",
                    "one_next_safe_action": "Review the model consult permission request; no model call is allowed.",
                    "push_class": "approval_waiting",
                    "state": {
                        "package_id": "model_work_package:fixture",
                        "permission_request_id": "model_consult_permission:fixture",
                        "model_class": "external_deep_reasoner",
                        "operator_decision": "PENDING",
                        "execution_allowed": False,
                    },
                }
            ],
        },
    )

    payload = _build(tmp_path)

    assert payload["item_count"] == 1
    item = payload["feed_items"][0]
    assert item["item_id"] == "model_consult_permission:fixture"
    assert item["lane"] == "guardian_approval"
    assert item["urgency"] == "needs_operator"
    assert item["push_candidate"] is True
    assert item["push_allowed"] is False
    assert item["state"]["execution_allowed"] is False


def test_codex_work_package_lifecycle_fixture_produces_watch_item(tmp_path):
    _write_json(
        tmp_path / "codex_work_package_lifecycle.json",
        {
            "schema_version": "codex_work_package_lifecycle_v0",
            "watch_desk_items": [
                {
                    "item_id": "codex_work_package:fixture",
                    "lane": "chief_runtime",
                    "urgency": "watch",
                    "plain_line": "Worker package codex_work_package:fixture is claimed.",
                    "source_receipt_ref": "generated/read_models/codex_work_package_lifecycle.json#codex_work_package:fixture",
                    "one_next_safe_action": "Wait for the assigned worker output, then ingest the result.",
                    "push_class": "on_demand",
                    "push_allowed": False,
                    "package_id": "codex_work_package:fixture",
                    "status": "claimed",
                    "state": {
                        "package_id": "codex_work_package:fixture",
                        "objective_id": "operator_objective:fixture",
                        "capability_id": "read_only_email_lookup",
                        "status": "claimed",
                        "claimed_by": "pc_codex",
                        "execution_allowed": False,
                        "external_call_allowed": False,
                        "approval_created": False,
                    },
                }
            ],
        },
    )

    payload = _build(tmp_path)

    assert payload["item_count"] == 1
    item = payload["feed_items"][0]
    assert item["item_id"] == "codex_work_package:fixture"
    assert item["lane"] == "chief_runtime"
    assert item["urgency"] == "watch"
    assert item["push_allowed"] is False
    assert item["state"]["package_id"] == "codex_work_package:fixture"
    assert item["state"]["execution_allowed"] is False
    assert item["state"]["external_call_allowed"] is False
    assert item["state"]["approval_created"] is False


def test_data_room_live_chatgpt55_lane_fixture_produces_watch_item(tmp_path):
    _write_json(
        tmp_path / "data_room_live_chatgpt55_lane.json",
        {
            "schema_version": "DATA_ROOM_LIVE_CHATGPT55_LANE_STATE_V0",
            "lane_id": "data_room_live_chatgpt55",
            "lane_status": "active",
            "live_ready": True,
            "model_label": "gpt-5.5",
            "active_review_session_id": "data_room_review:test",
            "current_question_id": "review_question:payment",
            "last_advisory_request_id": "live_chatgpt55_data_room_advisory:test",
            "last_result_id": "resp_fake",
            "blocked_reason": "",
            "watch_desk_items": [
                {
                    "item_id": "data_room_live_chatgpt55:data_room_review:test",
                    "lane": "cassandra_ar",
                    "urgency": "watch",
                    "plain_line": "ChatGPT 5.5 Data Room lane active for data_room_review:test.",
                    "source_receipt_ref": "generated/read_models/data_room_live_chatgpt55_lane.json#lane",
                    "one_next_safe_action": "Continue the Data Room review in Cassandra; model advice remains advisory-only.",
                    "push_class": "info",
                    "state": {
                        "lane_status": "active",
                        "live_ready": True,
                        "model_label": "gpt-5.5",
                        "active_review_session_id": "data_room_review:test",
                        "current_question_id": "review_question:payment",
                        "external_action_allowed": False,
                        "runtime_mutation_allowed": False,
                    },
                }
            ],
        },
    )

    payload = _build(tmp_path)
    item = payload["feed_items"][0]

    assert item["item_id"] == "data_room_live_chatgpt55:data_room_review:test"
    assert item["lane"] == "cassandra_ar"
    assert item["push_allowed"] is False
    assert item["state"]["live_ready"] is True
    assert item["state"]["external_action_allowed"] is False
    assert item["state"]["runtime_mutation_allowed"] is False


def test_data_room_gemini_form_lane_fixture_produces_watch_items(tmp_path):
    state = gemini.build_data_room_gemini_form_session_state(
        package={
            "review_session_id": "data_room_review:test",
            "current_question_id": "review_question:payment",
            "current_question_index": 3,
            "total_questions": 23,
            "answered_questions": [],
            "skipped_questions": [],
            "deferred_questions": [],
            "unresolved_questions": [{"question_id": "review_question:payment"}],
            "done_criteria": {"done": False},
        },
        result={"request_id": "gemini_data_room_form_turn:test", "chat_log_summary_update": "Ready."},
        availability={"available": True, "provider_enabled": True, "credential_present": True, "model_label_present": True},
        lane_status="active",
        live_ready=True,
        blocked_reason="",
        generated_at_utc=FIXED_NOW,
        codex_finalizer_status="waiting_for_codex_dispatch",
        codex_finalizer_package_ref="codex_work_package:data_room_review:test",
    )
    _write_json(tmp_path / "data_room_gemini_form_session.json", state)

    payload = _build(tmp_path)
    item_ids = {item["item_id"] for item in payload["feed_items"]}

    assert "data_room_gemini_form:data_room_review:test" in item_ids
    assert "data_room_gemini_form_codex_finalizer:data_room_review:test" in item_ids
    for item in payload["feed_items"]:
        if item["item_id"].startswith("data_room_gemini_form"):
            assert item["lane"] == "cassandra_ar"
            assert item["push_allowed"] is False
            assert item["state"]["external_action_allowed"] is False
            assert item["state"]["runtime_mutation_allowed"] is False


def test_lm_consult_spine_status_fixture_produces_watch_item(tmp_path):
    _write_json(
        tmp_path / "openclaw_lm_consult_spine_status.json",
        {
            "schema_version": "LM_CONSULT_SPINE_STATUS_V0",
            "read_model_id": "openclaw_lm_consult_spine_status",
            "spine_built": True,
            "live_ready": False,
            "provider": "gemini",
            "blocked_reason": "blocked_provider_config_required",
            "watch_desk_items": [
                {
                    "item_id": "lm_consult_spine:gemini:blocked",
                    "lane": "chief_runtime",
                    "urgency": "blocked",
                    "plain_line": "LM consult spine built, but gemini is blocked: blocked_provider_config_required.",
                    "source_receipt_ref": "generated/read_models/openclaw_lm_consult_spine_status.json#status",
                    "one_next_safe_action": "Configure the provider through approved env/config.",
                    "push_class": "failure",
                    "state": {
                        "provider": "gemini",
                        "live_ready": False,
                        "blocked_reason": "blocked_provider_config_required",
                        "advisory_only": True,
                        "tools_exposed": False,
                        "execution_allowed": False,
                        "runtime_mutation_allowed": False,
                        "external_action_allowed": False,
                    },
                }
            ],
        },
    )

    payload = _build(tmp_path)

    items = {item["item_id"]: item for item in payload["feed_items"]}
    assert "lm_consult_spine:gemini:blocked" in items
    item = items["lm_consult_spine:gemini:blocked"]
    assert item["urgency"] == "blocked"
    assert item["push_allowed"] is False
    assert item["state"]["tools_exposed"] is False
    assert item["state"]["execution_allowed"] is False


def test_unchanged_state_produces_zero_new_push_candidates(tmp_path):
    _write_json(tmp_path / "approval_request_queue.json", _pending_approval_queue())
    first = _build(tmp_path)
    previous = feed.item_state_keys(first["feed_items"])

    second = _build(tmp_path, previous=previous)

    assert second["item_count"] == 1
    assert second["new_push_candidate_count"] == 0
    assert second["new_push_candidates"] == []


def test_proof_refs_are_present(tmp_path):
    _write_json(tmp_path / "approval_request_queue.json", _pending_approval_queue())
    _write_json(
        tmp_path / "sync_health.json",
        {"mirror_status": "needs_mac_sync", "missing_expected": 1, "hash_mismatch": 0},
    )

    payload = _build(tmp_path)

    assert payload["item_count"] == 2
    for item in payload["feed_items"]:
        assert item["source_receipt_ref"]
        assert item["source_receipt_ref"] in payload["source_receipt_refs"]


def test_no_private_raw_body_text_appears(tmp_path):
    _write_json(tmp_path / "approval_request_queue.json", _pending_approval_queue())
    _write_json(
        tmp_path / "cassandra_draft_worker_readback.json",
        {
            "request": {
                "request_id": "cassandra_request:unsafe",
                "approval_required": True,
                "send_authority": False,
            },
            "readback": {
                "status": "DRAFT_READY_FOR_REVIEW",
                "operator_message": "Unsafe quoted private content: pay winship@example.test now.",
            },
            "source_candidate": {
                "body_text": "This raw source body must not be copied.",
            },
        },
    )
    task_root = tmp_path / "tasks"
    _write_task(
        task_root / "chief-cassandra-failure-20260610T205623.md",
        """title: chief-cassandra-failure-20260610T205623
scope:
- Request summary: unsafe quoted private content with winship@example.test
generated_by: chief_cassandra_failure
generated_at: 2026-06-10T20:56:23.068137
""",
    )

    rendered = feed.stable_json(_build(tmp_path, task_root)).lower()

    assert "winship@example.test" not in rendered
    assert "unsafe quoted private content" not in rendered
    assert "this raw source body" not in rendered
    assert "plain_summary" not in rendered
    assert "operator_message" not in rendered
    assert '"body_text"' not in rendered


def test_recent_local_safe_intake_events_appear_in_watch_desk(tmp_path):
    events = [
        _intake_event(
            intake_id="operator_intake:income",
            action_type="income_payment_log",
            lane="cassandra_finance",
            summary="Logged income: $900 from Live Arts MD.",
        ),
        _intake_event(
            intake_id="operator_intake:expense",
            action_type="expense_log",
            lane="cassandra_finance",
            summary="Logged expense: $106 Claude Code Fable 5 as software.",
            receipt_path="/tmp/openclaw-mission-control/receipts/operator_intake_expense_receipt.json",
        ),
        _intake_event(
            intake_id="operator_intake:gig",
            action_type="gig_event_log",
            lane="cassandra_business/niles_context",
            summary="Logged gig: St. Anne's on 2026-06-11.",
            receipt_path="/tmp/openclaw-mission-control/receipts/operator_intake_gig_receipt.json",
        ),
        _intake_event(
            intake_id="operator_intake:preference",
            action_type="identity_signature_preference",
            lane="chief_identity",
            summary="Staged identity preference: use Winship locally.",
            receipt_path="/tmp/openclaw-mission-control/receipts/operator_intake_preference_receipt.json",
        ),
    ]
    _write_json(tmp_path / "operator_intake_events.json", _operator_intake_read_model(events))

    payload = _build(tmp_path, intake_stub=False)
    by_id = {item["item_id"]: item for item in payload["feed_items"]}

    assert payload["source_freshness"]["operator_intake_events"]["status"] == "fresh"
    assert by_id["operator_intake:operator_intake:income"]["lane"] == "cassandra_ar"
    assert by_id["operator_intake:operator_intake:expense"]["lane"] == "cassandra_ar"
    assert by_id["operator_intake:operator_intake:gig"]["lane"] == "niles_creative"
    assert by_id["operator_intake:operator_intake:preference"]["lane"] == "chief_runtime"
    assert all(item["push_allowed"] is False for item in by_id.values())


def test_feed_regenerates_after_new_local_intake_event(tmp_path):
    first = _intake_event(intake_id="operator_intake:first", summary="Logged income: $900 from Live Arts MD.")
    _write_json(tmp_path / "operator_intake_events.json", _operator_intake_read_model([first]))
    first_payload = _build(tmp_path, intake_stub=False)

    second = _intake_event(
        intake_id="operator_intake:second",
        action_type="expense_log",
        summary="Logged expense: $106 Claude Code Fable 5 as software.",
        receipt_path="/tmp/openclaw-mission-control/receipts/operator_intake_second_receipt.json",
        received_at="2026-06-10T21:05:00+00:00",
    )
    _write_json(tmp_path / "operator_intake_events.json", _operator_intake_read_model([second, first]))
    second_payload = _build(tmp_path, intake_stub=False)

    assert first_payload["item_count"] == 1
    assert second_payload["item_count"] == 2
    assert {item["item_id"] for item in second_payload["feed_items"]} == {
        "operator_intake:operator_intake:first",
        "operator_intake:operator_intake:second",
    }


def test_feed_points_to_telegram_receipt_when_surface_is_telegram(tmp_path):
    receipt_path = "/tmp/openclaw-mission-control/telegram/local_receipts/operator_intake_telegram_receipt.json"
    event = _intake_event(
        intake_id="operator_intake:telegram",
        surface="telegram",
        receipt_path=receipt_path,
        summary="Logged income: $900 from Live Arts MD.",
    )
    _write_json(tmp_path / "operator_intake_events.json", _operator_intake_read_model([event]))

    payload = _build(tmp_path, intake_stub=False)
    item = payload["feed_items"][0]

    assert item["item_id"] == "operator_intake:operator_intake:telegram"
    assert item["source_receipt_ref"] == f"{receipt_path}#receipt"
    assert item["state_hash"]
    assert item["push_allowed"] is False


def test_no_duplicate_when_intake_event_and_top_level_watch_item_overlap(tmp_path):
    event = _intake_event(
        intake_id="operator_intake:dedupe",
        summary="Logged income: $900 from Live Arts MD.",
        watch_item=True,
    )
    _write_json(tmp_path / "operator_intake_events.json", _operator_intake_read_model([event]))

    first = _build(tmp_path, intake_stub=False)
    second = _build(tmp_path, intake_stub=False)

    assert [item["item_id"] for item in first["feed_items"]] == ["operator_intake:operator_intake:dedupe"]
    assert [item["item_id"] for item in second["feed_items"]] == ["operator_intake:operator_intake:dedupe"]
    assert first["feed_items"][0]["state_hash"] == second["feed_items"][0]["state_hash"]


def test_intake_watch_item_preserves_skill_owner_missing_fields_and_info_push_class(tmp_path):
    event = _intake_event(
        intake_id="operator_intake:skill",
        summary="Logged income: $900 from Live Arts MD. Missing: invoice/project link, payment method.",
        watch_item=True,
    )
    event["watch_desk_items"][0].update(
        {
            "skill_id": "operator_skill:income_payment_log:v0",
            "owner_agent": "cassandra",
            "owner_lane": "cassandra_ar",
            "missing_fields": ["invoice/project link", "payment method"],
            "push_class": "info",
            "operator_local_timezone": "America/New_York",
            "operator_local_date": "2026-06-11",
            "normalized_event_date": "2026-06-11",
        }
    )
    _write_json(tmp_path / "operator_intake_events.json", _operator_intake_read_model([event]))

    payload = _build(tmp_path, intake_stub=False)
    item = payload["feed_items"][0]

    assert item["skill_id"] == "operator_skill:income_payment_log:v0"
    assert item["owner_agent"] == "cassandra"
    assert item["owner_lane"] == "cassandra_ar"
    assert item["missing_fields"] == ["invoice/project link", "payment method"]
    assert item["push_class"] == "info"
    assert item["push_candidate"] is False
    assert item["operator_local_timezone"] == "America/New_York"
    assert item["operator_local_date"] == "2026-06-11"
    assert item["normalized_event_date"] == "2026-06-11"


def test_clarification_proof_item_is_useful_and_non_pushy(tmp_path):
    receipt_path = "/tmp/openclaw-mission-control/receipts/operator_clarification_event_receipt.json"
    event = _intake_event(
        intake_id="operator_intake:clarify",
        action_type="operator_clarification_event",
        lane="chief_runtime",
        summary="Needs clarification before routing: what kind of action is it?",
        receipt_path=receipt_path,
        watch_item=True,
    )
    event["needs_clarification"] = ["action_type"]
    event["watch_desk_items"][0].update(
        {
            "lane": "chief_runtime",
            "owner_agent": "chief",
            "owner_lane": "chief_runtime",
            "skill_id": "operator_skill:operator_clarification_event:v0",
            "missing_fields": ["action_type"],
            "push_class": "needs_operator",
        }
    )
    _write_json(tmp_path / "operator_intake_events.json", _operator_intake_read_model([event]))

    first = _build(tmp_path, intake_stub=False)
    second = _build(tmp_path, intake_stub=False)
    item = first["feed_items"][0]

    assert item["item_id"] == "operator_intake:operator_intake:clarify"
    assert item["plain_line"] == "Needs clarification before routing: what kind of action is it?"
    assert item["source_receipt_ref"] == f"{receipt_path}#receipt"
    assert item["missing_fields"] == ["action_type"]
    assert item["push_allowed"] is False
    assert item["push_candidate"] is False
    assert [feed_item["item_id"] for feed_item in first["feed_items"]] == [
        feed_item["item_id"] for feed_item in second["feed_items"]
    ]


def test_stale_or_missing_operator_intake_read_model_warns_without_crashing(tmp_path):
    missing = _build(tmp_path, intake_stub=False)

    assert missing["item_count"] == 1
    assert missing["feed_items"][0]["item_id"] == "chief_runtime:operator_intake_events:missing"
    assert missing["feed_items"][0]["urgency"] == "watch"
    assert missing["source_freshness"]["operator_intake_events"]["status"] == "missing"

    stale_event = _intake_event(
        intake_id="operator_intake:stale",
        received_at="2026-06-10T21:05:00+00:00",
    )
    _write_json(
        tmp_path / "operator_intake_events.json",
        _operator_intake_read_model([stale_event], generated_at="2026-06-10T21:00:00+00:00"),
    )
    stale = _build(tmp_path, intake_stub=False)

    assert "operator_intake:operator_intake:stale" in {item["item_id"] for item in stale["feed_items"]}
    assert "chief_runtime:operator_intake_events:source_stale" in {
        item["item_id"] for item in stale["feed_items"]
    }
    assert stale["source_freshness"]["operator_intake_events"]["status"] == "source_stale"


def test_source_does_not_import_live_listener_runtime_db_network_or_model_tools():
    source = Path("watch_desk_feed.py").read_text(encoding="utf-8")
    forbidden_patterns = [
        r"^\s*import\s+cassandra_listener\b",
        r"^\s*from\s+cassandra_listener\b",
        r"^\s*import\s+sqlite3\b",
        r"^\s*import\s+subprocess\b",
        r"^\s*from\s+subprocess\b",
        r"^\s*import\s+requests\b",
        r"^\s*import\s+httpx\b",
        r"^\s*import\s+socket\b",
        r"os\.system\s*\(",
        r"subprocess\.",
        r"Popen\s*\(",
    ]
    for pattern in forbidden_patterns:
        assert re.search(pattern, source, flags=re.MULTILINE | re.IGNORECASE) is None
