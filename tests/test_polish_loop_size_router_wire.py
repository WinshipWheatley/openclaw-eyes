from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from polish_loop.control_plane import ControlPlaneLedger, InvalidTransition, SIZE_ROUTER_FLAG
from polish_loop.task_routing import ROUTING_SCHEMA_VERSION


def _ledger(tmp_path: Path) -> ControlPlaneLedger:
    return ControlPlaneLedger(tmp_path / "control.sqlite3")


def _small_payload(**overrides) -> dict:
    payload = {
        "goal": "Add one synthetic unit test for the parser.",
        "scope": ["Update one parser edge case."],
        "success_criteria": ["The parser returns the expected synthetic row."],
        "allowed_files": ["tests/test_queue_parser.py"],
        "forbidden_files": ["workspaces/openclaw_program/generated_read_models"],
        "allowed_actions": ["edit allowed test file", "run focused pytest"],
        "forbidden_actions": ["no live systems", "no external actions", "no credentials"],
        "tests_to_run": [
            "/home/openclaw/.venv/bin/python -m pytest tests/test_queue_parser.py -q"
        ],
        "stop_conditions": ["stop if production access would be needed"],
    }
    payload.update(overrides)
    return payload


def _rows(ledger: ControlPlaneLedger, sql: str, *params: object) -> list[dict]:
    with sqlite3.connect(ledger.path) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _event_details(ledger: ControlPlaneLedger, event_type: str) -> list[dict]:
    rows = _rows(
        ledger,
        "SELECT detail FROM events WHERE event_type = ? ORDER BY id",
        event_type,
    )
    return [json.loads(row["detail"]) if row["detail"] else {} for row in rows]


def test_flag_off_admit_and_claim_legacy_ready_without_routing(monkeypatch, tmp_path):
    monkeypatch.delenv(SIZE_ROUTER_FLAG, raising=False)
    ledger = _ledger(tmp_path)

    task_id = ledger.admit_task(
        task_id="legacy-ready",
        source="human_intent",
        task_type="synthetic_legacy",
        requested_status="READY",
        payload={"goal": "legacy sparse task", "synthetic": True},
        acceptance_ref={"synthetic": True},
    )

    task = ledger.get_task(task_id)
    assert task["status"] == "READY"
    assert task["dispatchable"] == 1
    assert "routing" not in task["payload"]
    assert _event_details(ledger, "TASK_ADMITTED") == [
        {"requested_status": "READY", "dispatchable": True}
    ]

    lease = ledger.claim_task(task_id, owner="size-router-test", lease_seconds=600)
    assert lease is not None
    assert ledger.get_task(task_id)["status"] == "LEASED"


def test_flag_on_small_task_ready_with_routing_metadata(monkeypatch, tmp_path):
    monkeypatch.setenv(SIZE_ROUTER_FLAG, "1")
    ledger = _ledger(tmp_path)

    task_id = ledger.admit_task(
        task_id="small-ready",
        source="human_intent",
        task_type="synthetic_router",
        requested_status="READY",
        payload=_small_payload(),
        acceptance_ref={"acceptance_path": "tests/test_queue_parser.py"},
    )

    task = ledger.get_task(task_id)
    routing = task["payload"]["routing"]
    assert task["status"] == "READY"
    assert task["dispatchable"] == 1
    assert routing["schema_version"] == ROUTING_SCHEMA_VERSION
    assert routing["size_class"] == "small"
    assert routing["readiness"] == "ready"
    assert routing["minimum_model_tier"] == "small"
    assert routing["local_model_allowed"] is True
    assert _event_details(ledger, "TASK_ADMITTED")[0]["routing"]["size_class"] == "small"


def test_flag_on_large_task_is_held_proposed_not_claimable(monkeypatch, tmp_path):
    monkeypatch.setenv(SIZE_ROUTER_FLAG, "1")
    ledger = _ledger(tmp_path)

    task_id = ledger.admit_task(
        task_id="large-held",
        source="human_intent",
        task_type="synthetic_router",
        requested_status="READY",
        payload=_small_payload(
            goal="Reconcile the full synthetic dispatch stack.",
            scope=[f"Implement bounded step {index}" for index in range(7)],
            success_criteria=[f"Acceptance check {index}" for index in range(2)],
            allowed_files=[f"polish_loop/module_{index}.py" for index in range(8)],
            tests_to_run=[f"pytest test_{index}.py" for index in range(8)],
        ),
        acceptance_ref={"acceptance_path": "tests/test_queue_parser.py"},
    )

    task = ledger.get_task(task_id)
    routing = task["payload"]["routing"]
    assert task["status"] == "PROPOSED"
    assert task["dispatchable"] == 0
    assert task["payload"]["holding_reason"] == "large_requires_decomposition"
    assert routing["size_class"] == "large"
    assert routing["decomposition_required"] is True
    assert routing["minimum_model_tier"] == "large"
    assert routing["local_model_allowed"] is False
    assert ledger.claim_task(task_id, owner="size-router-test", lease_seconds=600) is None


def test_flag_on_ambiguous_payload_is_held_with_unknown_risk(monkeypatch, tmp_path):
    monkeypatch.setenv(SIZE_ROUTER_FLAG, "1")
    ledger = _ledger(tmp_path)

    task_id = ledger.admit_task(
        task_id="ambiguous-held",
        source="human_intent",
        task_type="synthetic_router",
        requested_status="READY",
        payload={"goal": "Fix the thing"},
    )

    task = ledger.get_task(task_id)
    routing = task["payload"]["routing"]
    assert task["status"] == "PROPOSED"
    assert task["dispatchable"] == 0
    assert routing["size_class"] == "unknown"
    assert "unknown" in routing["risk_flags"]
    assert routing["local_model_allowed"] is False


def test_flag_on_risky_payload_is_held_not_dispatchable(monkeypatch, tmp_path):
    monkeypatch.setenv(SIZE_ROUTER_FLAG, "1")
    ledger = _ledger(tmp_path)

    task_id = ledger.admit_task(
        task_id="risky-held",
        source="human_intent",
        task_type="synthetic_router",
        requested_status="READY",
        payload=_small_payload(
            goal="Send email update for a live action.",
            forbidden_actions=["no live sends", "no external actions", "no credentials"],
        ),
        acceptance_ref={"acceptance_path": "tests/test_queue_parser.py"},
    )

    task = ledger.get_task(task_id)
    routing = task["payload"]["routing"]
    assert task["status"] == "PROPOSED"
    assert task["dispatchable"] == 0
    assert "external_action" in routing["risk_flags"]
    assert routing["readiness"] == "blocked"
    assert ledger.claim_next_ready(owner="size-router-test", lease_seconds=600) is None


def test_promote_to_ready_revalidates_routing_and_records_hold(monkeypatch, tmp_path):
    monkeypatch.setenv(SIZE_ROUTER_FLAG, "1")
    ledger = _ledger(tmp_path)

    task_id = ledger.admit_task(
        task_id="proposed-large",
        source="human_intent",
        task_type="synthetic_router",
        requested_status="PROPOSED",
        payload=_small_payload(
            allowed_files=[f"polish_loop/module_{index}.py" for index in range(8)],
            tests_to_run=[f"pytest test_{index}.py" for index in range(8)],
        ),
        acceptance_ref={"acceptance_path": "tests/test_queue_parser.py"},
    )

    with pytest.raises(InvalidTransition, match="large_requires_decomposition"):
        ledger.promote_to_ready(task_id, actor="size-router-test", source="human_intent")

    task = ledger.get_task(task_id)
    assert task["status"] == "PROPOSED"
    assert task["dispatchable"] == 0
    assert task["payload"]["routing"]["size_class"] == "large"
    assert _event_details(ledger, "TASK_PROMOTION_HELD")[0]["routing"]["size_class"] == "large"


def test_promote_to_ready_stores_routing_for_small_proposal(monkeypatch, tmp_path):
    monkeypatch.setenv(SIZE_ROUTER_FLAG, "1")
    ledger = _ledger(tmp_path)

    task_id = ledger.admit_task(
        task_id="proposed-small",
        source="human_intent",
        task_type="synthetic_router",
        requested_status="PROPOSED",
        payload=_small_payload(),
        acceptance_ref={"acceptance_path": "tests/test_queue_parser.py"},
    )

    ledger.promote_to_ready(task_id, actor="size-router-test", source="human_intent")

    task = ledger.get_task(task_id)
    assert task["status"] == "READY"
    assert task["dispatchable"] == 1
    assert task["payload"]["routing"]["schema_version"] == ROUTING_SCHEMA_VERSION
    assert task["payload"]["routing"]["size_class"] == "small"
