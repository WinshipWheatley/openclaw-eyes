import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import assignment_loop_contract as contract
import model_work_package_router as model_router


FIXED_NOW = "2026-06-12T18:00:00+00:00"


def _assignment(**overrides):
    fields = {
        "requested_by": "operator",
        "owner_agent": "chief",
        "worker_type": "codex",
        "goal": "Patch a bounded backend issue.",
        "sources": ["model_work_package_router.py"],
        "standard": "Focused tests pass and unsafe scan is clean.",
        "proof_required": ["pytest output", "unsafe scan result"],
        "stop_condition": "Stop after summary; do not push.",
        "current_status": "active",
        "receipts": ["generated/read_models/example.json#receipt"],
        "watch_desk_refs": ["assignment_loop:example"],
        "operator_next_action": "Review proof.",
        "created_at_utc": FIXED_NOW,
    }
    fields.update(overrides)
    return contract.build_assignment_loop(**fields)


def test_assignment_loop_has_required_fields_and_phases():
    assignment = _assignment()

    assert assignment["schema_version"] == contract.SCHEMA_VERSION
    for field in (
        "assignment_id",
        "requested_by",
        "owner_agent",
        "worker_type",
        "goal",
        "sources",
        "standard",
        "permission_boundary",
        "proof_required",
        "stop_condition",
        "current_status",
        "receipts",
        "watch_desk_refs",
        "operator_next_action",
        "safety_flags",
    ):
        assert field in assignment
    assert assignment["phases"] == list(contract.ASSIGNMENT_PHASES)


def test_every_model_work_package_can_reference_assignment_loop():
    package = model_router.build_model_work_package(
        task_type="code implementation with tests",
        requested_by_agent="chief",
        owner_agent="codex",
        context_refs=["tests/test_assignment_loop_contract.py"],
        created_at_utc=FIXED_NOW,
    )
    assignment = contract.build_assignment_for_model_work_package(package, created_at_utc=FIXED_NOW)
    linked = contract.add_assignment_ref_to_model_work_package(package, assignment)

    assert linked["schema_version"] == "MODEL_WORK_PACKAGE_V0"
    assert linked["assignment_loop_ref"] == assignment["assignment_id"]
    assert linked["assignment_loop_schema"] == contract.SCHEMA_VERSION
    assert linked["execution_allowed"] is False
    assert linked["runtime_mutation_allowed"] is False
    assert linked["external_call_allowed"] is False


def test_model_work_package_builder_accepts_assignment_loop_ref():
    package = model_router.build_model_work_package(
        task_type="quick summary",
        assignment_loop_ref="assignment_loop:abc",
        context_refs=["generated/read_models/safe.json#summary"],
        created_at_utc=FIXED_NOW,
    )

    assert package["assignment_loop_ref"] == "assignment_loop:abc"
    assert package["execution_allowed"] is False


def test_watch_desk_can_show_assignment_statuses():
    active = contract.build_watch_desk_item_for_assignment(_assignment(current_status="active"))
    blocked = contract.build_watch_desk_item_for_assignment(_assignment(current_status="blocked", receipts=[]))
    completed = contract.build_watch_desk_item_for_assignment(_assignment(current_status="completed"))

    assert active["lane"] == "chief_runtime"
    assert active["urgency"] == "watch"
    assert blocked["urgency"] == "blocked"
    assert blocked["push_candidate"] is True
    assert completed["urgency"] == "info"
    assert active["state"]["model_output_runtime_mutation_allowed"] is False
    assert active["state"]["guardian_hitl_separate"] is True


def test_no_model_output_directly_mutates_runtime_and_guardian_separate():
    assignment = _assignment()

    assert assignment["permission_boundary"]["model_output_runtime_mutation_allowed"] is False
    assert assignment["permission_boundary"]["model_output_business_mutation_allowed"] is False
    assert assignment["permission_boundary"]["guardian_hitl_remains_separate"] is True
    assert assignment["permission_boundary"]["guardian_approval_created_by_assignment_loop"] is False
    assert assignment["safety_flags"]["runtime_policy_mutated"] is False
    assert assignment["safety_flags"]["approval_created"] is False


def test_parking_lot_items_attach_to_active_assignments_without_readying_them():
    assignment = _assignment(receipts=[], current_status="blocked")
    parked = contract.attach_parking_lot_item(
        assignment,
        parking_ref="consult_parked_note:abc",
        reason="Missing matching source context.",
    )
    readiness = contract.assignment_ready_status(parked)

    assert "consult_parked_note:abc" in parked["parking_lot_refs"]
    assert parked["parking_lot_policy"]["attached_to_assignment"] is True
    assert parked["parking_lot_policy"]["does_not_mark_ready"] is True
    assert readiness["ready"] is False
    assert "receipt_or_proof_ref" in readiness["missing_before_ready"]


def test_proof_is_required_before_ready():
    missing_proof = _assignment(receipts=[])
    ready = _assignment(receipts=["generated/read_models/example.json#receipt"])

    assert contract.assignment_ready_status(missing_proof)["ready"] is False
    assert contract.assignment_ready_status(ready)["ready"] is True


def test_export_json_bridge_equality_and_wiki(tmp_path):
    result = contract.export_assignment_loop_contract(
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "Assignment Loop Contract.md",
        generated_at=FIXED_NOW,
    )
    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert result["status"] == contract.READY_STATUS
    assert local == bridge
    assert wiki.startswith("# Assignment Loop Contract")
    assert local["machine_proof"]["new_approval_system_created"] is False
    assert local["machine_proof"]["new_dashboard_created"] is False
    assert local["machine_proof"]["proof_required_before_ready"] is True


def test_unsafe_true_grant_scan_clean():
    read_model = contract.build_read_model(generated_at=FIXED_NOW)

    assert contract.unsafe_true_grants(read_model["examples"]) == []
    assert read_model["unsafe_true_grants"] == []
    assert read_model["status"] == contract.READY_STATUS
