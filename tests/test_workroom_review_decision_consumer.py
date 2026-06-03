import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import openclaw_request_processor as processor
import openclaw_request_response_service as service
import workroom_review_decision_consumer as consumer
from scripts.run_openclaw_request_response_service import main as service_main


FIXED_NOW = "2026-06-03T20:00:00+00:00"
PACKET_ID = "review_packet:fixture"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    _write_json(
        root / "workroom_review_packet_index.json",
        {
            "status": "WORKROOM_REVIEW_PACKET_INDEX_READY",
            "packets": [
                {
                    "review_packet_id": PACKET_ID,
                    "package_id": "pkg:fixture",
                    "worker_ref": "pc_codex",
                    "channel_ref": "build_openclaw_backend",
                    "status": "REVIEW_PACKET_READY",
                    "human_summary": "PC_CODEX returned backend validation proof.",
                    "files_changed": ["backend.py", "tests/test_backend.py"],
                    "tests_run": ["pytest -q tests/test_backend.py"],
                    "receipts": ["generated/read_models/backend_receipt.json"],
                    "screenshots": [],
                    "proof_refs": ["generated/read_models/workroom_review_packet_index.json#fixture"],
                    "next_safe_action": "Review the packet and approve, request rework, or block by gate.",
                    "operator_decision_required": True,
                    "proof_collapsed_by_default": True,
                    "worker_inherits_speaker_authority": False,
                    "merge_allowed": False,
                    "push_allowed": False,
                    "business_action_performed": False,
                    "unsafe_scan_result": {"status": "PASS", "unsafe_true_grants": []},
                }
            ],
        },
    )
    _write_json(
        root / "workroom_review_decision_contract.json",
        {
            "status": "WORKROOM_REVIEW_DECISION_CONTRACT_READY",
            "decision_actions": [
                {"decision_action": action}
                for action in consumer.decision_contract.DECISION_ACTIONS
            ],
            "authority_boundary": consumer.AUTHORITY_BOUNDARY,
        },
    )
    _write_json(
        root / "package_event_index.json",
        {
            "status": "PACKAGE_EVENT_INDEX_READY",
            "events": [],
            "authority_boundary": {
                "git_push_allowed": False,
                "merge_allowed": False,
                "email_send_allowed": False,
                "ledger_posting_allowed": False,
                "business_action_allowed": False,
            },
        },
    )
    return root


def _request_payload(*, request_id: str, review_packet_id: str = PACKET_ID, decision_action: str) -> dict:
    return {
        "request_type": consumer.REQUEST_TYPE,
        "source_surface": "mission_control",
        "requested_mode": "operator",
        "request_id": request_id,
        "review_packet_id": review_packet_id,
        "decision_action": decision_action,
        "reason": "Operator reviewed the packet.",
        "authority_boundary": {
            "email_send_allowed": False,
            "ledger_posting_allowed": False,
            "browser_access_allowed": False,
            "gmail_allowed": False,
            "coupa_allowed": False,
            "portal_submit_allowed": False,
            "push_allowed": False,
            "merge_allowed": False,
            "sent": False,
            "paid": False,
        },
    }


def _consume(tmp_path: Path, request: dict) -> consumer.WorkroomReviewDecisionResult:
    return consumer.consume_workroom_review_decision_request(
        request,
        source_request_filename=f"mission_control_workroom_review_decision_request_{request['request_id']}.json",
        generated_at=FIXED_NOW,
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "Workroom Review Decision Consumer.md",
    )


def _walk_values(payload):
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield key, value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_values(value)


def _assert_no_unsafe_grants(payload: dict) -> None:
    rendered = json.dumps(payload, sort_keys=True)
    unsafe_true_fragments = [
        '"push_allowed": true',
        '"merge_allowed": true',
        '"git_push_allowed": true',
        '"email_send_allowed": true',
        '"gmail_allowed": true',
        '"browser_access_allowed": true',
        '"coupa_allowed": true',
        '"portal_submit_allowed": true',
        '"ledger_posting_allowed": true',
        '"ledger_mutation_allowed": true',
        '"workbook_mutation_allowed": true',
        '"pdf_export_allowed": true',
        '"paid": true',
        '"sent": true',
        '"merge_performed": true',
        '"git_push_performed": true',
        '"business_action_performed": true',
        '"email_send_performed": true',
        '"submit_performed": true',
        '"paid_marking_performed": true',
    ]
    assert not any(fragment in rendered for fragment in unsafe_true_fragments)


def _assert_review_only(receipt: dict) -> None:
    assert receipt["no_push"] is True
    assert receipt["no_merge"] is True
    assert receipt["no_business_action"] is True
    assert receipt["merge_performed"] is False
    assert receipt["git_push_performed"] is False
    assert receipt["worker_spawn_performed"] is False
    assert receipt["business_action_performed"] is False
    assert receipt["business_state_mutation_performed"] is False
    assert receipt["worker_ref_is_speaker"] is False
    assert receipt["speaker_ref"] == "chief"
    assert receipt["worker_ref"] == "pc_codex"
    _assert_no_unsafe_grants(receipt)


def test_approve_review_packet_records_decision_only(tmp_path):
    result = _consume(
        tmp_path,
        _request_payload(
            request_id="approve_fixture",
            decision_action="approve_review_packet_for_record",
        ),
    )

    assert result.status == "RECORDED"
    assert result.receipt["status"] == "OPERATOR_REVIEW_RECORDED"
    assert result.receipt["raw_internal_status"] == "RESPONSE_READY"
    assert result.receipt["next_safe_action"] == "Record complete. No merge or push performed."
    assert result.receipt["operator_display"]["speaker_ref"] == "chief"
    assert result.receipt["operator_display"]["plain_summary"].startswith("Chief recorded")
    _assert_review_only(result.receipt)


def test_request_rework_records_rework_only(tmp_path):
    result = _consume(
        tmp_path,
        _request_payload(
            request_id="rework_fixture",
            decision_action="request_review_packet_rework",
        ),
    )

    assert result.status == "RECORDED"
    assert result.receipt["status"] == "REWORK_REQUEST_RECORDED"
    assert result.receipt["next_safe_action"] == "Worker packet is marked for rework."
    assert result.receipt["contract_receipt"]["rework_requested"] is True
    _assert_review_only(result.receipt)


def test_informational_closes_review_only(tmp_path):
    result = _consume(
        tmp_path,
        _request_payload(
            request_id="informational_fixture",
            decision_action="mark_review_packet_informational",
        ),
    )

    assert result.status == "RECORDED"
    assert result.receipt["status"] == "INFORMATIONAL_REVIEW_CLOSED"
    assert result.receipt["next_safe_action"] == "No action needed."
    assert result.receipt["contract_receipt"]["informational_only"] is True
    _assert_review_only(result.receipt)


def test_unknown_review_packet_id_blocks(tmp_path):
    result = _consume(
        tmp_path,
        _request_payload(
            request_id="unknown_packet_fixture",
            review_packet_id="review_packet:missing",
            decision_action="approve_review_packet_for_record",
        ),
    )

    assert result.status == "BLOCKED"
    assert result.receipt["status"] == "BLOCKED_UNKNOWN_REVIEW_PACKET"
    assert result.receipt["raw_internal_status"] == "BLOCKED_WITH_REASON"
    assert result.receipt["speaker_ref"] == "chief"
    assert result.receipt["operator_display"]["headline"] == "Review packet not found"
    assert result.receipt["decision_recorded"] is False
    assert result.receipt["merge_performed"] is False
    assert result.receipt["git_push_performed"] is False
    assert result.receipt["business_action_performed"] is False
    _assert_no_unsafe_grants(result.receipt)


def test_unsafe_push_merge_send_authority_blocks_through_guardian(tmp_path):
    request = _request_payload(
        request_id="unsafe_fixture",
        decision_action="approve_review_packet_for_record",
    )
    request["authority_boundary"]["push_allowed"] = True
    request["authority_boundary"]["merge_allowed"] = True
    request["authority_boundary"]["email_send_allowed"] = True

    result = _consume(tmp_path, request)

    assert result.status == "BLOCKED"
    assert result.receipt["status"] == "BLOCKED_UNSAFE_AUTHORITY"
    assert result.receipt["speaker_ref"] == "guardian"
    assert result.receipt["voice_mode"] == "safety_gate"
    assert result.receipt["operator_display"]["speaker_ref"] == "guardian"
    assert set(result.receipt["unsafe_true_grants"]) == {
        "email_send_allowed",
        "merge_allowed",
        "push_allowed",
    }
    assert result.receipt["decision_recorded"] is False
    assert result.receipt["merge_performed"] is False
    assert result.receipt["git_push_performed"] is False
    assert result.receipt["email_send_performed"] is False
    _assert_no_unsafe_grants(result.receipt)


def test_json_parse_local_and_bridge_equal(tmp_path):
    result = _consume(
        tmp_path,
        _request_payload(
            request_id="json_parse_fixture",
            decision_action="approve_review_packet_for_record",
        ),
    )
    local_path = Path(result.receipt["read_model_paths"]["local_status_path"])
    bridge_path = Path(result.receipt["read_model_paths"]["bridge_status_path"])

    local = json.loads(local_path.read_text(encoding="utf-8"))
    bridge = json.loads(bridge_path.read_text(encoding="utf-8"))
    assert local == bridge
    assert local["status"] == consumer.CONSUMER_STATUS
    assert local["last_decision"]["receipt_id"] == result.receipt["receipt_id"]
    assert local["last_decision"]["read_model_paths"]["local_status_path"] == local_path.as_posix()
    assert local["machine_proof"]["merge_performed"] is False
    assert Path(result.receipt["read_model_paths"]["wiki_path"]).exists()


def test_unsafe_true_grant_scan_clean(tmp_path):
    result = _consume(
        tmp_path,
        _request_payload(
            request_id="scan_fixture",
            decision_action="approve_review_packet_for_record",
        ),
    )
    local = json.loads(Path(result.receipt["read_model_paths"]["local_status_path"]).read_text(encoding="utf-8"))
    unsafe_keys = {
        "push_allowed",
        "merge_allowed",
        "git_push_allowed",
        "email_send_allowed",
        "gmail_allowed",
        "browser_access_allowed",
        "coupa_allowed",
        "portal_submit_allowed",
        "ledger_posting_allowed",
        "ledger_mutation_allowed",
        "workbook_mutation_allowed",
        "pdf_export_allowed",
        "paid",
        "sent",
        "merge_performed",
        "git_push_performed",
        "business_action_performed",
        "email_send_performed",
        "submit_performed",
        "paid_marking_performed",
    }

    assert not [key for key, value in _walk_values(local) if key in unsafe_keys and value is True]
    assert local["machine_proof"]["unsafe_true_grants_absent"] is True


def test_request_response_service_consumes_review_decision_request(tmp_path, capsys):
    real_index = json.loads((ROOT / "generated/read_models/workroom_review_packet_index.json").read_text(encoding="utf-8"))
    review_packet_id = real_index["packets"][0]["review_packet_id"]
    inbox = tmp_path / "inbox"
    response_dir = tmp_path / "responses"
    export_root = tmp_path / "read_models"
    inbox.mkdir()
    request = _request_payload(
        request_id="service_review_decision_smoke",
        review_packet_id=review_packet_id,
        decision_action="approve_review_packet_for_record",
    )
    request_path = inbox / "mission_control_workroom_review_decision_request_service_smoke.json"
    _write_json(request_path, request)

    assert processor.classify_request_filename(request_path.name).request_family == "WORKROOM_REVIEW_DECISION_REQUEST"
    assert service.classify_request_path(request_path) == "WORKROOM_REVIEW_DECISION_REQUEST"

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
    response_path = response_dir / f"openclaw_response_for_mac_{service._safe_filename_part(request['request_id'])}.json"
    heartbeat_path = response_dir / f"openclaw_processing_for_mac_{service._safe_filename_part(request['request_id'])}.json"
    response = json.loads(response_path.read_text(encoding="utf-8"))
    heartbeat = json.loads(heartbeat_path.read_text(encoding="utf-8"))
    status = json.loads((export_root / "workroom_review_decision_status.json").read_text(encoding="utf-8"))

    assert service_payload["service_status"]["processed_count"] == 1
    assert heartbeat["request_type"] == "WORKROOM_REVIEW_DECISION_REQUEST"
    assert heartbeat["processing_status"] == "CHECKING_WORKROOM_REVIEW_DECISION"
    assert response["response_kind"] == "WORKROOM_REVIEW_DECISION_RESPONSE"
    assert response["internal_status"] == "RESPONSE_READY"
    assert response["review_packet_id"] == review_packet_id
    assert response["decision_status"] == "OPERATOR_REVIEW_RECORDED"
    assert response["operator_display"]["speaker_ref"] == "chief"
    assert response["worker_ref_is_speaker"] is False
    assert response["machine_proof"]["git_push_pull_fetch_run"] is False
    assert response["machine_proof"]["external_action_performed"] is False
    assert response["detail_disclosure"]["workroom_review_decision_consumer"]["git_push_performed"] is False
    assert response["detail_disclosure"]["workroom_review_decision_consumer"]["merge_performed"] is False
    assert status["last_decision"]["status"] == "OPERATOR_REVIEW_RECORDED"
    _assert_no_unsafe_grants(response)
