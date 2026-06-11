import os
import sys

import pytest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture()
def isolated_hitl(monkeypatch, tmp_path):
    import hitl_action_service as svc
    import hitl_pending_store as store

    monkeypatch.setattr(store, "HITL_STATE_PATH", tmp_path / "hitl_state.json")
    monkeypatch.setattr(store, "HITL_AUDIT_LOG", tmp_path / "hitl_audit.jsonl")
    monkeypatch.setattr(store, "_shadow_cassandra_hitl_proposal", lambda *args, **kwargs: None)
    monkeypatch.setattr(store, "_shadow_cassandra_hitl_decision", lambda *args, **kwargs: None)
    svc.clear_action_dispatchers_for_tests()
    yield svc, store
    svc.clear_action_dispatchers_for_tests()


def _create_operator_action(svc, action_type="test_generic_dispatch", request_id="request:test:1", **kwargs):
    return svc.create_operator_action_approval_request(
        action_type=action_type,
        owner_agent="test_agent",
        owner_objective_id="objective:test",
        request_id=request_id,
        summary="Test operator action",
        payload={"value": "ok"},
        risk_warning="Fixture only.",
        expires_at="2099-01-01T00:00:00+00:00",
        route_back={"type": "test_dispatcher"},
        **kwargs,
    )


def test_exact_gmail_send_dispatcher_auto_registers(isolated_hitl):
    svc, _store = isolated_hitl

    registered = svc.register_builtin_action_dispatchers()

    assert svc.ACTION_TYPE_EXACT_GMAIL_SEND in registered
    assert svc.get_action_dispatcher(svc.ACTION_TYPE_EXACT_GMAIL_SEND) is not None


def test_first_class_refs_and_execution_result_are_on_operator_action(isolated_hitl):
    svc, store = isolated_hitl

    created = _create_operator_action(
        svc,
        authority_refs=["authority:test"],
        credential_lease_refs=["credential_lease:test"],
        risk_tier="high",
    )

    record = store.get_action(created["action_id"])
    payload = record["payload"]
    assert payload["authority_refs"] == ["authority:test"]
    assert payload["credential_lease_refs"] == ["credential_lease:test"]
    assert payload["risk_tier"] == "high"
    assert payload["execution_result"]["status"] == "pending_approval"
    assert created["authority_refs"] == ["authority:test"]
    assert created["credential_lease_refs"] == ["credential_lease:test"]


def test_approval_persists_dispatch_state_before_executor_runs(isolated_hitl):
    svc, store = isolated_hitl
    seen_dispatch_states = []

    def dispatcher(action):
        current = store.get_action(action["action_id"])
        seen_dispatch_states.append(current["approved_dispatch"]["status"])
        return {"status": "success", "receipt_ref": "receipt:fake-success", "terminal": True}

    svc.register_action_dispatcher("test_generic_dispatch", dispatcher)
    created = _create_operator_action(svc)

    assert svc.approve_action(created["action_id"], approved_by="winship") is True

    record = store.get_action(created["action_id"])
    assert seen_dispatch_states == ["in_progress"]
    assert record["status"] == store.APPROVED
    assert record["approved_dispatch"]["status"] == "succeeded"
    assert record["execution_result"]["status"] == "success"
    assert record["execution_result"]["receipt_ref"] == "receipt:fake-success"
    assert record["execution_result"]["terminal"] is True


def test_pending_approved_dispatch_can_be_redriven_after_restart(isolated_hitl):
    svc, store = isolated_hitl
    calls = []

    created = _create_operator_action(svc)
    assert svc.approve_action(created["action_id"], approved_by="winship", dispatch_now=False) is True
    pending = store.get_action(created["action_id"])
    assert pending["approved_dispatch"]["status"] == "pending"

    svc.clear_action_dispatchers_for_tests()

    def dispatcher(action):
        calls.append(action["action_id"])
        return {"status": "success", "receipt_ref": "receipt:redrive", "terminal": True}

    svc.register_action_dispatcher("test_generic_dispatch", dispatcher)
    result = svc.redrive_pending_dispatches()

    record = store.get_action(created["action_id"])
    assert result["processed"] == 1
    assert calls == [created["action_id"]]
    assert record["execution_result"]["status"] == "success"
    assert record["execution_result"]["receipt_ref"] == "receipt:redrive"


def test_failed_dispatch_writes_generic_execution_result(isolated_hitl):
    svc, store = isolated_hitl

    def dispatcher(_action):
        raise RuntimeError("fixture dispatch failure")

    svc.register_action_dispatcher("test_generic_dispatch", dispatcher)
    created = _create_operator_action(svc)

    assert svc.approve_action(created["action_id"], approved_by="winship") is True

    record = store.get_action(created["action_id"])
    assert record["approved_dispatch"]["status"] == "failed"
    assert record["execution_result"]["status"] == "failed"
    assert record["execution_result"]["terminal"] is True
    assert record["decision_receipt"]["dispatch_status"] == "dispatch_exception"


def test_duplicate_approval_and_dispatch_do_not_double_execute(isolated_hitl):
    svc, store = isolated_hitl
    calls = []

    def dispatcher(action):
        calls.append(action["action_id"])
        return {"status": "success", "receipt_ref": "receipt:once", "terminal": True}

    svc.register_action_dispatcher("test_generic_dispatch", dispatcher)
    created = _create_operator_action(svc)

    assert svc.approve_action(created["action_id"], approved_by="winship") is True
    assert svc.approve_action(created["action_id"], approved_by="winship") is False
    redrive = svc.dispatch_approved_action(created["action_id"])

    assert calls == [created["action_id"]]
    assert redrive["dispatch_status"] == "already_terminal"
    assert store.get_action(created["action_id"])["execution_result"]["receipt_ref"] == "receipt:once"


def test_expired_approval_does_not_execute(isolated_hitl):
    svc, store = isolated_hitl
    calls = []
    svc.register_action_dispatcher(
        "test_generic_dispatch",
        lambda action: calls.append(action["action_id"]) or {"status": "success"},
    )
    created = _create_operator_action(svc, ttl_seconds=-1)

    assert svc.approve_action(created["action_id"], approved_by="winship") is False

    record = store.get_action(created["action_id"])
    assert record["status"] == store.EXPIRED
    assert calls == []


def test_unknown_action_type_defaults_high_and_blocks_dispatch(isolated_hitl):
    svc, store = isolated_hitl
    import hitl_notification_service as notify

    created = _create_operator_action(svc, action_type="unknown_future_action")
    action_id = created["action_id"]
    action = store.get_action(action_id)

    assert notify._risk_level("unknown_future_action") == "HIGH"
    assert "Risk: HIGH" in notify.format_notification(action)
    assert svc.approve_action(action_id, approved_by="winship") is True

    record = store.get_action(action_id)
    assert record["approved_dispatch"]["status"] == "blocked"
    assert record["execution_result"]["status"] == "blocked"
    assert record["decision_receipt"]["dispatch_status"] == "no_dispatcher_registered"
