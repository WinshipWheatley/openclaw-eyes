import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import openclaw_request_processor as processor
import openclaw_request_response_service as service
import workflow_package_queue as queue
import workflow_package_request_consumer as consumer
from scripts.run_openclaw_request_response_service import main as service_main


FIXED_NOW = "2026-06-02T02:30:00+00:00"


def _request_payload(*, request_id: str, source_text: str, world_ref: str, thread_ref: str) -> dict:
    protected_hash = queue.protected_text_hash(source_text)
    payload = {
        "schema_version": "operator_instruction_writer_v0",
        "request_id": request_id,
        "source_request_id": request_id,
        "request_type": consumer.REQUEST_TYPE,
        "kind": consumer.REQUEST_KIND,
        "source_surface": "mission_control",
        "source_channel": "mission_control_chat",
        "requested_mode": "operator",
        "result_receipt_required": True,
        "world": world_ref,
        "world_ref": world_ref,
        "thread_ref": thread_ref,
        "source_text": source_text,
        "operator_message": source_text,
        "source_text_ref": "protected_text_hash:" + protected_hash,
        "protected_text_hash": protected_hash,
        "privacy_impact": "pending",
        "idempotency_key": f"workflow_package_request:{request_id}",
        "created_at": FIXED_NOW,
        "authority_boundary": {key: False for key in consumer.AUTHORITY_FALSE_FIELDS},
        "mac_wrote_request_only": True,
        "no_external_action": True,
    }
    payload["payload_hash"] = "sha256:" + processor._short_hash(payload)
    return payload


def _write_request(path: Path, *, request_id: str, source_text: str, world_ref: str, thread_ref: str) -> dict:
    payload = _request_payload(
        request_id=request_id,
        source_text=source_text,
        world_ref=world_ref,
        thread_ref=thread_ref,
    )
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def _safe_response_path(response_dir: Path, request_id: str) -> Path:
    return response_dir / f"openclaw_response_for_mac_{service._safe_filename_part(request_id)}.json"


def _safe_heartbeat_path(response_dir: Path, request_id: str) -> Path:
    return response_dir / f"openclaw_processing_for_mac_{service._safe_filename_part(request_id)}.json"


def _sentence_count(text: str) -> int:
    return sum(1 for char in text if char in ".?!")


def _assert_compact_display(display):
    assert len(display["headline"].split()) <= 8
    assert _sentence_count(display["plain_summary"]) <= 1
    assert _sentence_count(display["next_safe_action"]) <= 1
    assert display["proof_caption"] == "Proof available."
    assert display["show_machine_details_by_default"] is False
    assert display["why_it_matters"]
    assert isinstance(display["secondary_facts"], list)


def _assert_system_question_display(display, *, speaker_ref: str, voice_mode: str):
    assert display["speaker_ref"] == speaker_ref
    assert display["voice_profile_ref"] == f"agent_voice_profile:{speaker_ref}"
    assert display["voice_mode"] == voice_mode
    assert display["audience"] == "internal_operator"
    assert display["headline"]
    assert display["plain_summary"]
    assert display["next_safe_action"]
    assert display["proof_caption"] == "Proof available."
    assert display["show_machine_details_by_default"] is False
    assert display["proof_refs_collapsed"] is True
    _assert_compact_display(display)


def _assert_no_unsafe_grants(payload):
    rendered = json.dumps(payload, sort_keys=True)
    unsafe_true_fragments = [
        '"email_send_allowed": true',
        '"gmail_allowed": true',
        '"coupa_allowed": true',
        '"coupa_submit_allowed": true',
        '"ledger_posting_allowed": true',
        '"paid": true',
        '"sent": true',
        '"portal_submit_allowed": true',
        '"business_action_performed": true',
    ]
    assert not any(fragment in rendered for fragment in unsafe_true_fragments)


def test_chief_vs_spawned_worker_question_routes_to_system_question_answer(tmp_path):
    request = _request_payload(
        request_id="system_question_chief_vs_worker",
        source_text="What is the difference between Chief and a spawned worker?",
        world_ref="operations",
        thread_ref="openclaw",
    )

    result = consumer.consume_workflow_package_request(
        request,
        source_request_filename="mission_control_operator_instruction_request_system_question_chief_vs_worker.json",
        generated_at=FIXED_NOW,
        sqlite_path=tmp_path / "workflow_package_queue.sqlite",
    )

    assert result.status == "RECORDED"
    assert result.package is None
    assert result.receipt["workflow_ref"] == "system_question_answer"
    assert result.receipt["package_status"] == "ANSWER_READY"
    assert result.receipt["raw_internal_status"] == "RESPONSE_READY"
    assert result.receipt["machine_proof"]["system_question_answer_local_only"] is True
    assert result.receipt["machine_proof"]["package_recorded"] is False
    assert not (tmp_path / "workflow_package_queue.sqlite").exists()
    _assert_system_question_display(result.receipt["operator_display"], speaker_ref="hermes", voice_mode="recommendation")
    assert "Chief is a named OpenClaw role" in json.dumps(result.receipt["system_question_answer"])
    _assert_no_unsafe_grants(result.receipt)


def test_capital_hilton_block_question_routes_to_chief_diagnostic_answer(tmp_path):
    request = _request_payload(
        request_id="system_question_capital_hilton_block",
        source_text="Why did Submit Capital Hilton invoice block?",
        world_ref="finance",
        thread_ref="capital_hilton",
    )

    result = consumer.consume_workflow_package_request(
        request,
        source_request_filename="mission_control_operator_instruction_request_system_question_capital_hilton_block.json",
        generated_at=FIXED_NOW,
        sqlite_path=tmp_path / "workflow_package_queue.sqlite",
    )

    assert result.receipt["workflow_ref"] == "system_question_answer"
    _assert_system_question_display(result.receipt["operator_display"], speaker_ref="chief", voice_mode="diagnostic")
    assert "provider gate" in result.receipt["operator_display"]["routing_reason"]
    assert "Capital Hilton" in result.receipt["operator_display"]["headline"]
    assert "Submit gate" in json.dumps(result.receipt["system_question_answer"]) or "final Submit gate" in json.dumps(result.receipt["system_question_answer"])
    _assert_no_unsafe_grants(result.receipt)


def test_send_email_question_routes_to_guardian_safety_answer(tmp_path):
    request = _request_payload(
        request_id="system_question_send_email",
        source_text="Can this send email?",
        world_ref="operations",
        thread_ref="openclaw",
    )

    result = consumer.consume_workflow_package_request(
        request,
        source_request_filename="mission_control_operator_instruction_request_system_question_send_email.json",
        generated_at=FIXED_NOW,
        sqlite_path=tmp_path / "workflow_package_queue.sqlite",
    )

    assert result.receipt["workflow_ref"] == "system_question_answer"
    _assert_system_question_display(result.receipt["operator_display"], speaker_ref="guardian", voice_mode="safety_gate")
    assert "Email send authority is closed" == result.receipt["operator_display"]["headline"]
    assert result.receipt["machine_proof"]["email_send_performed"] is False
    _assert_no_unsafe_grants(result.receipt)


def test_sqlite_st_annes_question_summarizes_refs_not_raw_rows(tmp_path):
    raw_marker = "RAW_ROW_BODY_SHOULD_NOT_APPEAR"
    request = _request_payload(
        request_id="system_question_st_annes_sqlite",
        source_text=f"What does SQLite know about St. Anne's work logs? {raw_marker * 20}",
        world_ref="finance",
        thread_ref="st_annes",
    )

    result = consumer.consume_workflow_package_request(
        request,
        source_request_filename="mission_control_operator_instruction_request_system_question_st_annes_sqlite.json",
        generated_at=FIXED_NOW,
        sqlite_path=tmp_path / "workflow_package_queue.sqlite",
    )
    rendered = json.dumps(result.receipt)

    assert result.receipt["workflow_ref"] == "system_question_answer"
    _assert_system_question_display(result.receipt["operator_display"], speaker_ref="chief", voice_mode="diagnostic")
    assert "SQLite has work-log metadata" == result.receipt["operator_display"]["headline"]
    assert raw_marker not in rendered
    assert len(result.receipt["system_question_answer"]["question"]) <= 240
    _assert_no_unsafe_grants(result.receipt)


def test_unknown_system_question_returns_safe_openclaw_fallback(tmp_path):
    request = _request_payload(
        request_id="system_question_unknown",
        source_text="What does OpenClaw know about the purple submarine?",
        world_ref="operations",
        thread_ref="openclaw",
    )

    result = consumer.consume_workflow_package_request(
        request,
        source_request_filename="mission_control_operator_instruction_request_system_question_unknown.json",
        generated_at=FIXED_NOW,
        sqlite_path=tmp_path / "workflow_package_queue.sqlite",
    )

    assert result.receipt["workflow_ref"] == "system_question_answer"
    _assert_system_question_display(result.receipt["operator_display"], speaker_ref="openclaw", voice_mode="operator_calm")
    assert result.receipt["operator_display"]["headline"] == "No local answer found"
    assert result.receipt["system_question_answer"]["answer"]["unknown"]
    assert result.receipt["system_question_answer"]["answer"]["proof_refs"]
    assert result.receipt["machine_proof"]["live_execution_performed"] is False
    _assert_no_unsafe_grants(result.receipt)


def test_safe_next_question_routes_to_openclaw_status_answer(tmp_path):
    request = _request_payload(
        request_id="system_question_safe_next",
        source_text="What is safe next?",
        world_ref="operations",
        thread_ref="openclaw",
    )

    result = consumer.consume_workflow_package_request(
        request,
        source_request_filename="mission_control_operator_instruction_request_system_question_safe_next.json",
        generated_at=FIXED_NOW,
        sqlite_path=tmp_path / "workflow_package_queue.sqlite",
    )

    assert result.receipt["workflow_ref"] == "system_question_answer"
    _assert_system_question_display(result.receipt["operator_display"], speaker_ref="openclaw", voice_mode="operator_calm")
    assert "safe next" in result.receipt["operator_display"]["headline"].lower()
    assert result.receipt["system_question_answer"]["answer"]["proof_refs"]
    _assert_no_unsafe_grants(result.receipt)


def test_consumer_records_valid_workflow_package_request_in_queue_sqlite(tmp_path):
    sqlite_path = tmp_path / "workflow_package_queue.sqlite"
    request = _request_payload(
        request_id="church_sound_operator_instruction_smoke",
        source_text="Mark that I'm at church running sound.",
        world_ref="operations",
        thread_ref="church_sound",
    )

    result = consumer.consume_workflow_package_request(
        request,
        source_request_filename="mission_control_operator_instruction_request_church_sound.json",
        generated_at=FIXED_NOW,
        sqlite_path=sqlite_path,
    )

    assert result.status == "RECORDED"
    assert result.receipt["raw_internal_status"] == "RESPONSE_READY"
    assert result.receipt["workflow_ref"] == "st_annes_work_log_event"
    assert result.receipt["client_ref"] == "st_annes"
    assert result.receipt["package_status"] == "OPERATOR_REVIEW_REQUIRED"
    assert result.receipt["target_world_ref"] == "finance"
    assert result.receipt["target_thread_ref"] == "st_annes"
    assert result.receipt["operator_display"]["headline"] == "St. Anne's work log captured"
    assert result.receipt["speaker_ref"] == "cassandra"
    assert result.receipt["voice_profile_ref"] == "agent_voice_profile:cassandra"
    assert result.receipt["voice_mode"] == "operator_intake"
    assert result.receipt["audience"] == "internal_operator"
    assert result.receipt["operator_display"]["speaker_ref"] == "cassandra"
    assert result.receipt["operator_display"]["voice_profile_ref"] == "agent_voice_profile:cassandra"
    assert result.receipt["operator_display"]["voice_mode"] == "operator_intake"
    assert result.receipt["operator_display"]["routing_reason"] == "work-log intake"
    assert result.receipt["operator_display"]["status_label"] == "Needs confirmation"
    assert result.receipt["operator_display"]["tone"] == "warning"
    assert result.receipt["operator_display"]["plain_summary"] == "Saved as a draft event until you confirm it."
    assert result.receipt["operator_display"]["next_safe_action"] == "Confirm or discard."
    _assert_compact_display(result.receipt["operator_display"])
    assert "st_annes_work_log_event" not in result.receipt["operator_display"]["headline"]
    assert result.receipt["operator_display"]["show_machine_details_by_default"] is False
    assert result.receipt["machine_proof"]["queue_noop_worker_only"] is True
    assert result.receipt["machine_proof"]["business_state_mutation_performed"] is False

    with sqlite3.connect(sqlite_path) as conn:
        row = conn.execute(
            "select workflow_ref, client_ref, status from packages where package_id = ?",
            (result.receipt["package_id"],),
        ).fetchone()
        assert row == ("st_annes_work_log_event", "st_annes", "OPERATOR_REVIEW_REQUIRED")
        raw_text_stored = conn.execute("select raw_text_stored from package_inputs").fetchone()[0]
        assert raw_text_stored == 0
        gates = conn.execute(
            "select email_send_allowed, ledger_posting_allowed, browser_access_allowed, gmail_allowed, "
            "coupa_allowed, portal_submit_allowed, paid, sent from business_action_gate_results"
        ).fetchall()
        assert gates == [(0, 0, 0, 0, 0, 0, 0, 0)]


def test_st_annes_work_log_from_capital_hilton_context_cross_lane_routes_to_finance_st_annes(tmp_path):
    request = _request_payload(
        request_id="church_sound_from_capital_hilton_context",
        source_text="Mark that I'm at church running sound.",
        world_ref="finance",
        thread_ref="capital_hilton_invoice_workflow",
    )

    result = consumer.consume_workflow_package_request(
        request,
        source_request_filename="mission_control_operator_instruction_request_church_sound_cross_lane.json",
        generated_at=FIXED_NOW,
        sqlite_path=tmp_path / "workflow_package_queue.sqlite",
    )

    assert result.status == "RECORDED"
    assert result.receipt["workflow_ref"] == "st_annes_work_log_event"
    assert result.receipt["current_world_ref"] == "finance"
    assert result.receipt["current_thread_ref"] == "capital_hilton"
    assert result.receipt["target_world_ref"] == "finance"
    assert result.receipt["target_thread_ref"] == "st_annes"
    assert result.receipt["cross_lane_routed"] is True
    assert result.receipt["routing_note"] == "Routed to Finance / St. Anne's."


def test_capital_hilton_invoice_from_capital_hilton_context_stays_in_finance_capital_hilton(tmp_path):
    request = _request_payload(
        request_id="capital_hilton_invoice_same_lane_context",
        source_text="Submit Capital Hilton invoice.",
        world_ref="finance",
        thread_ref="capital_hilton_invoice_workflow",
    )

    result = consumer.consume_workflow_package_request(
        request,
        source_request_filename="mission_control_operator_instruction_request_capital_hilton_invoice_same_lane.json",
        generated_at=FIXED_NOW,
        sqlite_path=tmp_path / "workflow_package_queue.sqlite",
    )

    assert result.receipt["workflow_ref"] == "capital_hilton_invoice_operator_assist"
    assert result.receipt["current_world_ref"] == "finance"
    assert result.receipt["current_thread_ref"] == "capital_hilton"
    assert result.receipt["target_world_ref"] == "finance"
    assert result.receipt["target_thread_ref"] == "capital_hilton"
    assert result.receipt["cross_lane_routed"] is False
    assert result.receipt["routing_note"] == ""


def test_capital_hilton_proposal_from_finance_context_routes_to_business_development(tmp_path):
    request = _request_payload(
        request_id="capital_hilton_proposal_from_finance_context",
        source_text="Follow up on the Capital Hilton proposal.",
        world_ref="finance",
        thread_ref="capital_hilton_invoice_workflow",
    )

    result = consumer.consume_workflow_package_request(
        request,
        source_request_filename="mission_control_operator_instruction_request_capital_hilton_proposal_cross_lane.json",
        generated_at=FIXED_NOW,
        sqlite_path=tmp_path / "workflow_package_queue.sqlite",
    )

    assert result.receipt["workflow_ref"] == "capital_hilton_proposal_followup"
    assert result.receipt["current_world_ref"] == "finance"
    assert result.receipt["current_thread_ref"] == "capital_hilton"
    assert result.receipt["target_world_ref"] == "business_development"
    assert result.receipt["target_thread_ref"] == "capital_hilton"
    assert result.receipt["cross_lane_routed"] is True
    assert result.receipt["routing_note"] == "Routed to Business Development / Capital Hilton."


def test_finance_thread_index_includes_st_annes_and_exports_bridge(tmp_path):
    result = consumer.export_finance_thread_index(
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        generated_at=FIXED_NOW,
    )

    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    assert local == bridge
    threads = {thread["thread_ref"]: thread for thread in local["threads"]}
    assert set(threads) >= {"capital_hilton", "live_arts_md", "st_annes"}
    assert threads["st_annes"]["display_name"] == "St. Anne's"
    assert "st_annes_work_log_event" in threads["st_annes"]["primary_workflow_refs"]
    assert all(value is False for value in local["authority_boundary"].values())


def test_consumer_blocks_unsafe_true_grant_without_queue_write(tmp_path):
    sqlite_path = tmp_path / "workflow_package_queue.sqlite"
    request = _request_payload(
        request_id="unsafe_operator_instruction_smoke",
        source_text="Submit Capital Hilton invoice.",
        world_ref="finance",
        thread_ref="capital_hilton_invoice_workflow",
    )
    unsafe_key = "email_send_" + "allowed"
    request["authority_boundary"][unsafe_key] = bool(1)

    result = consumer.consume_workflow_package_request(
        request,
        source_request_filename="mission_control_operator_instruction_request_unsafe.json",
        generated_at=FIXED_NOW,
        sqlite_path=sqlite_path,
    )

    assert result.status == "BLOCKED"
    assert result.receipt["raw_internal_status"] == "BLOCKED_WITH_REASON"
    assert f"authority_true:{unsafe_key}" in result.blockers
    assert result.receipt["speaker_ref"] == "guardian"
    assert result.receipt["voice_profile_ref"] == "agent_voice_profile:guardian"
    assert result.receipt["voice_mode"] == "safety_gate"
    assert result.receipt["operator_display"]["speaker_ref"] == "guardian"
    assert result.receipt["operator_display"]["voice_profile_ref"] == "agent_voice_profile:guardian"
    assert result.receipt["operator_display"]["routing_reason"] == "protected authority or access boundary"
    assert not sqlite_path.exists()


def test_service_processes_three_workflow_package_requests_and_writes_scoped_responses(tmp_path, capsys, monkeypatch):
    inbox = tmp_path / "inbox"
    response_dir = tmp_path / "responses"
    export_root = tmp_path / "read_models"
    sqlite_path = tmp_path / "workflow_package_queue.sqlite"
    inbox.mkdir()
    monkeypatch.setenv(consumer.SQLITE_PATH_ENV, sqlite_path.as_posix())

    requests = [
        _write_request(
            inbox / "mission_control_operator_instruction_request_church_sound_operator_instruction_smoke.json",
            request_id="church_sound_operator_instruction_smoke",
            source_text="Mark that I'm at church running sound.",
            world_ref="finance",
            thread_ref="capital_hilton_invoice_workflow",
        ),
        _write_request(
            inbox / "mission_control_operator_instruction_request_capital_hilton_business_development_operator_instruction_smoke.json",
            request_id="capital_hilton_business_development_operator_instruction_smoke",
            source_text="Follow up on the Capital Hilton proposal.",
            world_ref="business_development",
            thread_ref="capital_hilton_business_development",
        ),
        _write_request(
            inbox / "mission_control_operator_instruction_request_capital_hilton_invoice_workflow_operator_instruction_smoke.json",
            request_id="capital_hilton_invoice_workflow_operator_instruction_smoke",
            source_text="Submit Capital Hilton invoice.",
            world_ref="finance",
            thread_ref="capital_hilton_invoice_workflow",
        ),
    ]

    assert all(processor.classify_request_filename(path.name).request_family == "WORKFLOW_PACKAGE_REQUEST" for path in inbox.iterdir())
    assert all(service.classify_request_path(path) == "WORKFLOW_PACKAGE_REQUEST" for path in inbox.iterdir())

    assert service_main(
        [
            "--watch-seconds",
            "1",
            "--max-requests",
            "3",
            "--inbox",
            str(inbox),
            "--response-dir",
            str(response_dir),
            "--export-root",
            str(export_root),
            "--generated-at",
            FIXED_NOW,
            "--format",
            "json",
        ]
    ) == 0
    service_payload = json.loads(capsys.readouterr().out)
    assert service_payload["service_status"]["processed_count"] == 3
    assert service_payload["service_status"]["service_status"] == "REQUEST_PROCESSED"

    expected = {
        "church_sound_operator_instruction_smoke": (
            "st_annes_work_log_event",
            "st_annes",
            "OPERATOR_REVIEW_REQUIRED",
            "St. Anne's work log captured",
            "Needs confirmation",
            "warning",
            "Confirm or discard.",
            "Saved as a draft event until you confirm it.",
            "cassandra",
            "agent_voice_profile:cassandra",
            "operator_intake",
            "finance",
            "capital_hilton",
            "finance",
            "st_annes",
            True,
            "Routed to Finance / St. Anne's.",
        ),
        "capital_hilton_business_development_operator_instruction_smoke": (
            "capital_hilton_proposal_followup",
            "capital_hilton",
            "OPERATOR_REVIEW_REQUIRED",
            "Proposal follow-up staged",
            "Needs review",
            "calm",
            "Review the follow-up.",
            "No email will be sent until approved.",
            "cassandra",
            "agent_voice_profile:cassandra",
            "operator_calm",
            "business_development",
            "capital_hilton",
            "business_development",
            "capital_hilton",
            False,
            "",
        ),
        "capital_hilton_invoice_workflow_operator_instruction_smoke": (
            "capital_hilton_invoice_operator_assist",
            "capital_hilton",
            "PROVIDER_GATE_REQUIRED",
            "Capital Hilton needs operator assist",
            "Provider gate required",
            "blocked",
            "Stage an operator-assist packet.",
            "Coupa cannot run unattended.",
            "chief",
            "agent_voice_profile:chief",
            "diagnostic",
            "finance",
            "capital_hilton",
            "finance",
            "capital_hilton",
            False,
            "",
        ),
    }
    for request in requests:
        response = json.loads(_safe_response_path(response_dir, request["request_id"]).read_text(encoding="utf-8"))
        heartbeat = json.loads(_safe_heartbeat_path(response_dir, request["request_id"]).read_text(encoding="utf-8"))
        (
            workflow_ref,
            client_ref,
            package_status,
            headline,
            status_label,
            tone,
            next_safe_action,
            plain_summary,
            speaker_ref,
            voice_profile_ref,
            voice_mode,
            current_world_ref,
            current_thread_ref,
            target_world_ref,
            target_thread_ref,
            cross_lane_routed,
            routing_note,
        ) = expected[request["request_id"]]

        assert heartbeat["request_type"] == "WORKFLOW_PACKAGE_REQUEST"
        assert heartbeat["processing_status"] == "CHECKING_WORKFLOW_PACKAGE_QUEUE"
        assert response["source_request_id"] == request["request_id"]
        assert response["raw_internal_status"] == "RESPONSE_READY"
        assert response["internal_status"] == "RESPONSE_READY"
        assert response["response_kind"] == "WORKFLOW_PACKAGE_REQUEST_RESPONSE"
        assert response["workflow_ref"] == workflow_ref
        assert response["client_ref"] == client_ref
        assert response["package_status"] == package_status
        assert response["current_world_ref"] == current_world_ref
        assert response["current_thread_ref"] == current_thread_ref
        assert response["target_world_ref"] == target_world_ref
        assert response["target_thread_ref"] == target_thread_ref
        assert response["cross_lane_routed"] is cross_lane_routed
        assert response["routing_note"] == routing_note
        assert response["package_id"].startswith("workflow_package:")
        display = response["operator_display"]
        assert display["headline"] == headline
        assert display["status_label"] == status_label
        assert display["tone"] == tone
        assert display["plain_summary"] == plain_summary
        assert display["next_safe_action"] == next_safe_action
        _assert_compact_display(display)
        assert display["speaker_ref"] == speaker_ref
        assert display["voice_profile_ref"] == voice_profile_ref
        assert display["voice_mode"] == voice_mode
        assert display["audience"] == "internal_operator"
        assert display["routing_reason"]
        assert display["proof_caption"] == "Proof available."
        assert display["show_machine_details_by_default"] is False
        assert workflow_ref not in display["headline"]
        assert response["headline"] == headline
        assert response["speaker_ref"] == speaker_ref
        assert response["voice_mode"] == voice_mode
        assert response["audience"] == "internal_operator"
        assert response["routing_reason"] == display["routing_reason"]
        assert response["primary_status"] == status_label
        assert response["next_action"] == f"Next: {next_safe_action}"
        assert response["visible_cards"][0]["bullets"] == [plain_summary, f"Next: {next_safe_action}"]
        assert response["detail_disclosure"]["workflow_package_request_consumer"]["operator_display"] == display
        assert response["no_external_authority_granted"] is True
        assert response["detail_disclosure"]["workflow_package_request_consumer"]["package_status"] == package_status
        assert response["detail_disclosure"]["workflow_package_request_consumer"]["workflow_ref"] == workflow_ref
        assert response["detail_disclosure"]["workflow_package_request_consumer"]["target_thread_ref"] == target_thread_ref
        assert response["detail_disclosure"]["workflow_package_request_consumer"]["cross_lane_routed"] is cross_lane_routed
        assert response["detail_disclosure"]["package"]["workflow_ref"] == workflow_ref
        assert response["detail_disclosure"]["package"]["operator_display"]["why_it_matters"]
        assert response["detail_disclosure"]["package"]["operator_display"]["secondary_facts"]
        if package_status == "PROVIDER_GATE_REQUIRED":
            assert "cannot run unattended" in display["plain_summary"]
            assert "final Submit gate" in response["detail_disclosure"]["package"]["capability_gate_result"]["reason"]
        assert response["machine_proof"]["email_send_performed"] is False
        assert response["machine_proof"]["browser_access_performed"] is False
        assert response["machine_proof"]["coupa_access_or_submit_performed"] is False
        assert response["machine_proof"]["workbook_body_read_performed"] is False
        assert response["machine_proof"]["pdf_generation_performed"] is False
        assert response["machine_proof"]["payment_tracking_write_performed"] is False
        assert response["machine_proof"]["external_action_performed"] is False

    with sqlite3.connect(sqlite_path) as conn:
        rows = conn.execute("select workflow_ref, client_ref, status from packages order by workflow_ref").fetchall()
    assert rows == [
        ("capital_hilton_invoice_operator_assist", "capital_hilton", "PROVIDER_GATE_REQUIRED"),
        ("capital_hilton_proposal_followup", "capital_hilton", "OPERATOR_REVIEW_REQUIRED"),
        ("st_annes_work_log_event", "st_annes", "OPERATOR_REVIEW_REQUIRED"),
    ]


def test_service_processes_system_question_request_file_without_queue_write(tmp_path, capsys, monkeypatch):
    inbox = tmp_path / "inbox"
    response_dir = tmp_path / "responses"
    export_root = tmp_path / "read_models"
    sqlite_path = tmp_path / "workflow_package_queue.sqlite"
    inbox.mkdir()
    monkeypatch.setenv(consumer.SQLITE_PATH_ENV, sqlite_path.as_posix())
    request = _write_request(
        inbox / "mission_control_operator_instruction_request_system_question_send_email.json",
        request_id="system_question_send_email",
        source_text="Can this send email?",
        world_ref="operations",
        thread_ref="openclaw",
    )

    assert service_main(
        [
            "--watch-seconds",
            "1",
            "--max-requests",
            "1",
            "--inbox",
            str(inbox),
            "--response-dir",
            str(response_dir),
            "--export-root",
            str(export_root),
            "--generated-at",
            FIXED_NOW,
            "--format",
            "json",
        ]
    ) == 0
    service_payload = json.loads(capsys.readouterr().out)
    response = json.loads(_safe_response_path(response_dir, request["request_id"]).read_text(encoding="utf-8"))

    assert service_payload["service_status"]["processed_count"] == 1
    assert response["raw_internal_status"] == "RESPONSE_READY"
    assert response["response_kind"] == "WORKFLOW_PACKAGE_REQUEST_RESPONSE"
    assert response["workflow_ref"] == "system_question_answer"
    assert response["package_status"] == "ANSWER_READY"
    assert response["operator_display"]["speaker_ref"] == "guardian"
    assert response["operator_display"]["voice_mode"] == "safety_gate"
    assert response["operator_display"]["proof_refs_collapsed"] is True
    assert response["detail_disclosure"]["workflow_package_request_consumer"]["machine_proof"]["package_recorded"] is False
    assert response["detail_disclosure"]["system_question_answer"]["workflow_ref"] == "system_question_answer"
    assert response["machine_proof"]["email_send_performed"] is False
    assert response["machine_proof"]["external_action_performed"] is False
    assert not sqlite_path.exists()
