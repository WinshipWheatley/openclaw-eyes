import json
import sqlite3
from pathlib import Path

import operator_conversation_journal as journal


FIXED_NOW = "2026-06-02T06:15:00+00:00"


def _write_request(request_dir: Path, *, request_id: str, source_text: str, world_ref: str, thread_ref: str) -> Path:
    request_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "request_id": request_id,
        "source_request_id": request_id,
        "request_type": "WORKFLOW_PACKAGE_REQUEST_V0",
        "source_surface": "mission_control",
        "world_ref": world_ref,
        "thread_ref": thread_ref,
        "source_text_ref": f"protected_text_hash:sha256:{request_id}",
        "protected_text_hash": f"sha256:{request_id}",
        "source_text": source_text,
        "operator_message": source_text,
        "authority_boundary": {key: False for key in journal.AUTHORITY_BOUNDARY},
    }
    path = request_dir / f"mission_control_operator_instruction_request_{request_id}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_response(
    response_dir: Path,
    *,
    request_id: str,
    workflow_ref: str,
    client_ref: str,
    current_world_ref: str,
    current_thread_ref: str,
    target_world_ref: str,
    target_thread_ref: str,
    speaker_ref: str,
    voice_mode: str,
    headline: str,
    summary: str,
    package_status: str,
) -> Path:
    response_dir.mkdir(parents=True, exist_ok=True)
    response = {
        "response_kind": "WORKFLOW_PACKAGE_REQUEST_RESPONSE",
        "source_request_id": request_id,
        "generated_at": FIXED_NOW,
        "workflow_ref": workflow_ref,
        "client_ref": client_ref,
        "current_world_ref": current_world_ref,
        "current_thread_ref": current_thread_ref,
        "target_world_ref": target_world_ref,
        "target_thread_ref": target_thread_ref,
        "cross_lane_routed": current_world_ref != target_world_ref or current_thread_ref != target_thread_ref,
        "routing_note": "Routed to Finance / St. Anne's."
        if target_thread_ref == "st_annes" and current_thread_ref != target_thread_ref
        else "",
        "speaker_ref": speaker_ref,
        "voice_mode": voice_mode,
        "package_status": package_status,
        "primary_status": package_status,
        "operator_display": {
            "speaker_ref": speaker_ref,
            "voice_mode": voice_mode,
            "audience": "internal_operator",
            "headline": headline,
            "plain_summary": summary,
            "next_safe_action": "Review.",
            "proof_caption": "Proof available.",
            "show_machine_details_by_default": False,
        },
        "detail_disclosure": {
            "workflow_package_request_consumer": {
                "package_id": f"workflow_package:{request_id}",
                "sqlite_path": "generated/system_knowledge/workflow_package_queue.sqlite",
            }
        },
    }
    path = response_dir / f"openclaw_response_for_mac_{request_id}.json"
    path.write_text(json.dumps(response, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _fixture_dirs(tmp_path: Path):
    request_dir = tmp_path / "requests"
    response_dir = tmp_path / "responses"
    _write_request(
        request_dir,
        request_id="st_annes_from_capital_hilton",
        source_text="Mark that I'm at church running sound.",
        world_ref="finance",
        thread_ref="capital_hilton_invoice_workflow",
    )
    _write_response(
        response_dir,
        request_id="st_annes_from_capital_hilton",
        workflow_ref="st_annes_work_log_event",
        client_ref="st_annes",
        current_world_ref="finance",
        current_thread_ref="capital_hilton",
        target_world_ref="finance",
        target_thread_ref="st_annes",
        speaker_ref="cassandra",
        voice_mode="operator_intake",
        headline="St. Anne's work log captured",
        summary="Saved as a draft event until you confirm it.",
        package_status="OPERATOR_REVIEW_REQUIRED",
    )
    _write_request(
        request_dir,
        request_id="capital_hilton_proposal",
        source_text="Follow up on the Capital Hilton proposal.",
        world_ref="finance",
        thread_ref="capital_hilton_invoice_workflow",
    )
    _write_response(
        response_dir,
        request_id="capital_hilton_proposal",
        workflow_ref="capital_hilton_proposal_followup",
        client_ref="capital_hilton",
        current_world_ref="finance",
        current_thread_ref="capital_hilton",
        target_world_ref="business_development",
        target_thread_ref="capital_hilton",
        speaker_ref="cassandra",
        voice_mode="operator_calm",
        headline="Proposal follow-up staged",
        summary="No email will be sent until approved.",
        package_status="OPERATOR_REVIEW_REQUIRED",
    )
    _write_request(
        request_dir,
        request_id="capital_hilton_invoice",
        source_text="Submit Capital Hilton invoice.",
        world_ref="finance",
        thread_ref="capital_hilton_invoice_workflow",
    )
    _write_response(
        response_dir,
        request_id="capital_hilton_invoice",
        workflow_ref="capital_hilton_invoice_operator_assist",
        client_ref="capital_hilton",
        current_world_ref="finance",
        current_thread_ref="capital_hilton",
        target_world_ref="finance",
        target_thread_ref="capital_hilton",
        speaker_ref="chief",
        voice_mode="diagnostic",
        headline="Capital Hilton needs operator assist",
        summary="Coupa cannot run unattended.",
        package_status="PROVIDER_GATE_REQUIRED",
    )
    return request_dir, response_dir


def test_journal_groups_required_threads_and_preserves_short_display_copy(tmp_path):
    request_dir, response_dir = _fixture_dirs(tmp_path)

    payload = journal.build_journal(
        request_dir=request_dir,
        response_dir=response_dir,
        finance_thread_index_path=tmp_path / "missing_finance.json",
        business_development_proposal_path=tmp_path / "missing_proposal.json",
        generated_at=FIXED_NOW,
    )

    assert payload["status"] == journal.READY_STATUS
    assert payload["grouped_thread_counts"] == {
        "business_development/capital_hilton": 1,
        "finance/capital_hilton": 1,
        "finance/st_annes": 1,
    }
    by_thread = {(entry["target_world_ref"], entry["target_thread_ref"]): entry for entry in payload["entries"]}
    assert by_thread[("finance", "st_annes")]["headline"] == "St. Anne's work log captured"
    assert by_thread[("finance", "st_annes")]["short_summary"] == "Saved as a draft event until you confirm it."
    assert by_thread[("business_development", "capital_hilton")]["headline"] == "Proposal follow-up staged"
    assert by_thread[("finance", "capital_hilton")]["package_status"] == "PROVIDER_GATE_REQUIRED"
    assert all(entry["show_machine_details_by_default"] is False for entry in payload["entries"])


def test_journal_uses_refs_not_raw_prompt_dumps(tmp_path):
    request_dir, response_dir = _fixture_dirs(tmp_path)

    payload = journal.build_journal(
        request_dir=request_dir,
        response_dir=response_dir,
        generated_at=FIXED_NOW,
    )
    serialized_entries = json.dumps(payload["entries"], ensure_ascii=False)

    assert "Mark that I'm at church running sound." not in serialized_entries
    for entry in payload["entries"]:
        assert "source_text" not in entry
        assert "operator_message" not in entry
        assert entry["raw_request_body_stored"] is False
        assert entry["source_text_ref"].startswith("protected_text_hash:")
        assert entry["request_ref"].endswith(".json")
        assert entry["response_ref"].endswith(".json")
        assert entry["proof_refs"]


def test_publish_journal_writes_sqlite_and_has_no_unsafe_authority(tmp_path):
    request_dir, response_dir = _fixture_dirs(tmp_path)

    result = journal.publish_journal(
        request_dir=request_dir,
        response_dir=response_dir,
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        sqlite_path=tmp_path / "operator_conversation_journal.sqlite",
        generated_at=FIXED_NOW,
    )

    local = json.loads(Path(result.read_model_path).read_text())
    bridge = json.loads(Path(result.bridge_path).read_text())
    assert local == bridge
    assert all(value is False for value in local["authority_boundary"].values())
    assert local["machine_proof"]["no_raw_request_body_fields"] is True
    assert local["machine_proof"]["st_annes_group_present"] is True

    conn = sqlite3.connect(result.sqlite_path)
    try:
        count = conn.execute("SELECT COUNT(*) FROM operator_conversation_journal_entries").fetchone()[0]
        st_annes = conn.execute(
            """
            SELECT target_world_ref, target_thread_ref, show_machine_details_by_default
            FROM operator_conversation_journal_entries
            WHERE target_thread_ref = 'st_annes'
            """
        ).fetchone()
    finally:
        conn.close()
    assert count == 3
    assert st_annes == ("finance", "st_annes", 0)
