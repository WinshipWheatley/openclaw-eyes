import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import gate_decision_ledger as ledger


FIXED_NOW = "2026-06-03T13:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    _write_json(
        root / "workflow_package_queue_contract.json",
        {"status": "WORKFLOW_PACKAGE_QUEUE_V0_READY"},
    )
    _write_json(
        root / "agent_voice_routing_contract.json",
        {"status": "AGENT_VOICE_ROUTING_V0_READY"},
    )
    _write_json(
        root / "automation_permission_registry.json",
        {"status": "AUTOMATION_PERMISSION_REGISTRY_READY"},
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


def _assert_no_unsafe_true_grants(payload: dict) -> None:
    unsafe_keys = {
        "email_send_allowed",
        "ledger_posting_allowed",
        "browser_access_allowed",
        "gmail_allowed",
        "coupa_allowed",
        "portal_submit_allowed",
        "workbook_mutation_allowed",
        "pdf_export_allowed",
        "git_push_allowed",
        "worker_spawn_allowed",
        "external_provider_allowed",
        "authority_granted",
        "sent",
        "paid",
        "business_action_performed",
    }
    assert not [key for key, value in _walk_values(payload) if key in unsafe_keys and value is True]


def test_builds_gate_decision_ledger_with_required_gates(tmp_path):
    read_model = ledger.build_read_model(
        read_model_root=_fixture_root(tmp_path),
        sqlite_path=tmp_path / "gate_decision_ledger.sqlite",
        generated_at=FIXED_NOW,
    )

    assert read_model["status"] == "GATE_DECISION_LEDGER_READY"
    gates = {entry["gate_ref"]: entry for entry in read_model["decisions"]}
    assert {
        "send_email",
        "coupa_submit",
        "ledger_post",
        "mark_paid",
        "workbook_mutation",
        "pdf_export",
        "git_push",
        "worker_spawn",
        "external_provider",
        "local_only_read",
    } == set(gates)
    assert gates["send_email"]["decision"] == "approval_required"
    assert gates["send_email"]["speaker_ref"] == "guardian"
    assert gates["ledger_post"]["decision"] == "blocked"
    assert gates["local_only_read"]["decision"] == "allowed"
    assert all(entry["authority_granted"] is False for entry in read_model["decisions"])
    assert read_model["machine_proof"]["business_action_performed"] is False
    _assert_no_unsafe_true_grants(read_model)


def test_missing_precondition_marks_gate_ledger_not_ready(tmp_path):
    root = _fixture_root(tmp_path)
    _write_json(root / "automation_permission_registry.json", {"status": "NOT_READY"})

    read_model = ledger.build_read_model(
        read_model_root=root,
        sqlite_path=tmp_path / "gate_decision_ledger.sqlite",
        generated_at=FIXED_NOW,
    )

    assert read_model["status"] == "GATE_DECISION_LEDGER_NOT_READY"
    assert read_model["machine_proof"]["preconditions_ready"] is False
    _assert_no_unsafe_true_grants(read_model)


def test_export_writes_sqlite_local_bridge_equal_and_wiki(tmp_path):
    result = ledger.export_gate_decision_ledger(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        sqlite_path=tmp_path / "system_knowledge" / "gate_decision_ledger.sqlite",
        wiki_path=tmp_path / "wiki" / "Gate Decision Ledger.md",
        generated_at=FIXED_NOW,
    )

    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert local == bridge
    assert "non-financial" in wiki
    conn = sqlite3.connect(result["sqlite_path"])
    try:
        row_count = conn.execute("SELECT COUNT(*) FROM gate_decisions").fetchone()[0]
    finally:
        conn.close()
    assert row_count == local["decision_count"]
    assert result["status"] == "GATE_DECISION_LEDGER_READY"
    _assert_no_unsafe_true_grants(local)
