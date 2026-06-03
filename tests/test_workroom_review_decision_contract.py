import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import workroom_review_decision_contract as contract


FIXED_NOW = "2026-06-03T19:00:00+00:00"
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
                    "worker_ref": "pc_codex",
                    "channel_ref": "build_openclaw_backend",
                    "status": "REVIEW_PACKET_READY",
                    "operator_decision_required": True,
                    "merge_allowed": False,
                    "push_allowed": False,
                    "business_action_performed": False,
                }
            ],
        },
    )
    _write_json(
        root / "spawned_worker_package_lifecycle.json",
        {
            "status": "SPAWNED_WORKER_PACKAGE_LIFECYCLE_READY",
            "authority_rules": [
                "Worker does not inherit speaker authority.",
                "Operator approval is required before merge or recorded completion.",
            ],
        },
    )
    return root


def _walk_values(payload):
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield key, value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_values(value)


def _assert_required_decision_fields(receipt: dict) -> None:
    for field in contract.REQUIRED_DECISION_FIELDS:
        assert field in receipt
    assert receipt["review_packet_id"] == PACKET_ID
    assert receipt["operator_reviewed"] is True
    assert receipt["no_push"] is True
    assert receipt["no_merge"] is True
    assert receipt["no_business_action"] is True
    assert all(value is False for value in receipt["authority_boundary"].values())


def test_approve_decision_records_review_only():
    receipt = contract.build_decision_receipt(
        review_packet_id=PACKET_ID,
        decision_action="approve_review_packet_for_record",
        reason="Looks ready to record.",
        generated_at=FIXED_NOW,
    )

    _assert_required_decision_fields(receipt)
    assert receipt["status"] == "APPROVED_FOR_RECORD_ONLY"
    assert receipt["decision_accepted"] is True
    assert receipt["decision_effect"] == "operator_review_recorded_only"
    assert receipt["review_closed"] is True
    assert receipt["merge_performed"] is False
    assert receipt["git_push_performed"] is False
    assert receipt["business_action_performed"] is False


def test_rework_decision_records_rework_request_only():
    receipt = contract.build_decision_receipt(
        review_packet_id=PACKET_ID,
        decision_action="request_review_packet_rework",
        reason="Needs clearer test proof.",
        generated_at=FIXED_NOW,
    )

    _assert_required_decision_fields(receipt)
    assert receipt["status"] == "REWORK_REQUESTED"
    assert receipt["decision_effect"] == "rework_request_receipt_only"
    assert receipt["rework_requested"] is True
    assert receipt["review_closed"] is False
    assert "do not spawn a worker" in receipt["next_safe_action"].lower()
    assert receipt["worker_spawn_performed"] is False


def test_informational_decision_closes_review_without_action():
    receipt = contract.build_decision_receipt(
        review_packet_id=PACKET_ID,
        decision_action="mark_review_packet_informational",
        reason="Useful status only.",
        generated_at=FIXED_NOW,
    )

    _assert_required_decision_fields(receipt)
    assert receipt["status"] == "MARKED_INFORMATIONAL"
    assert receipt["decision_effect"] == "review_closed_without_action"
    assert receipt["informational_only"] is True
    assert receipt["review_closed"] is True
    assert receipt["business_action_performed"] is False


def test_unsafe_push_merge_send_authority_rejected():
    receipt = contract.build_decision_receipt(
        review_packet_id=PACKET_ID,
        decision_action="approve_review_packet_for_record",
        requested_authority={
            "git_push_allowed": True,
            "merge_allowed": True,
            "email_send_allowed": True,
        },
        generated_at=FIXED_NOW,
    )

    assert receipt["status"] == "REJECTED_UNSAFE_OR_INVALID_DECISION"
    assert receipt["decision_accepted"] is False
    assert receipt["operator_reviewed"] is False
    assert receipt["no_push"] is True
    assert receipt["no_merge"] is True
    assert receipt["no_business_action"] is True
    assert receipt["unsafe_true_grants"] == [
        "email_send_allowed",
        "git_push_allowed",
        "merge_allowed",
    ]
    assert "unsafe_true_grant:git_push_allowed" in receipt["blockers"]
    assert all(value is False for value in receipt["authority_boundary"].values())


def test_read_model_exports_json_parseable_local_and_bridge_equal(tmp_path):
    result = contract.export_workroom_review_decision_contract(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "Workroom Review Decision Contract.md",
        generated_at=FIXED_NOW,
    )

    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    assert local == bridge
    assert local["status"] == contract.CONTRACT_STATUS
    assert {item["decision_action"] for item in local["decision_actions"]} == set(contract.DECISION_ACTIONS)
    assert len(local["example_decision_receipts"]) == 3
    assert result["decision_action_count"] == "3"
    assert Path(result["wiki_path"]).exists()


def test_unsafe_true_grant_scan_clean(tmp_path):
    read_model = contract.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)
    approve = contract.build_decision_receipt(
        review_packet_id=PACKET_ID,
        decision_action="approve_review_packet_for_record",
        generated_at=FIXED_NOW,
    )
    unsafe_keys = set(contract.AUTHORITY_BOUNDARY) | {
        "push_allowed",
        "merge_performed",
        "git_push_performed",
        "business_action_performed",
        "email_send_performed",
        "submit_performed",
        "worker_inherits_speaker_authority",
    }

    assert not [key for key, value in _walk_values(read_model) if key in unsafe_keys and value is True]
    assert not [key for key, value in _walk_values(approve) if key in unsafe_keys and value is True]
    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True
