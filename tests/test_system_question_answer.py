import json
import sqlite3
from pathlib import Path

import system_question_answer as sqa


FIXED_NOW = "2026-06-02T08:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_sources(root: Path, sqlite_root: Path) -> None:
    _write_json(
        root / "workflow_package_queue_contract.json",
        {
            "packages": [
                {
                    "workflow_ref": "capital_hilton_invoice_operator_assist",
                    "status": "PROVIDER_GATE_REQUIRED",
                    "capability_gate_result": {
                        "status": "PROVIDER_GATE_REQUIRED",
                        "reason": "Operator-assist provider and final Submit gate are not explicitly staged.",
                    },
                }
            ],
            "authority_boundary_default": {
                "email_send_allowed": False,
                "ledger_posting_allowed": False,
                "browser_access_allowed": False,
                "gmail_allowed": False,
                "coupa_allowed": False,
                "portal_submit_allowed": False,
                "sent": False,
                "paid": False,
            },
        },
    )
    _write_json(
        root / "automation_permission_registry.json",
        {
            "permission_statuses": {
                "gmail_send": "blocked_until_explicit_send_gate",
                "coupa_submit": "blocked_until_explicit_submit_gate",
                "ledger_post": "blocked",
                "paid_marking": "blocked",
            },
            "authority_boundary": {
                "email_send_allowed": False,
                "ledger_posting_allowed": False,
                "browser_access_allowed": False,
                "gmail_allowed": False,
                "coupa_allowed": False,
                "portal_submit_allowed": False,
                "sent": False,
                "paid": False,
            },
        },
    )
    _write_json(root / "operator_assist_provider_registry.json", {"status": "OPERATOR_ASSIST_PROVIDER_REGISTRY_READY"})
    _write_json(root / "agent_voice_routing_contract.json", {"status": "AGENT_VOICE_ROUTING_V0_READY"})
    _write_json(root / "agent_voice_profiles.json", {"status": "AGENT_VOICE_PROFILES_V0_READY"})
    _write_json(root / "operator_conversation_journal.json", {"status": "OPERATOR_CONVERSATION_JOURNAL_READY"})
    _write_json(root / "overnight_workboard.json", {"mode": "planning_only"})
    _write_json(
        root / "st_annes_work_log_events.json",
        {
            "event_count": 1,
            "staged_events": [
                {
                    "event_id": "st_annes_work_log:fixture",
                    "description": "RAW_SECRET_ROW_SHOULD_NOT_APPEAR",
                }
            ],
        },
    )
    _write_json(root / "st_annes_monthly_work_log_contract.json", {"status": "ST_ANNES_MONTHLY_WORK_LOG_CONTRACT_READY"})
    _write_json(root / "operator_human_readability_surface.json", {"status": "OPERATOR_HUMAN_READABILITY_SURFACE_READY"})
    _write_json(root / "openclaw_lm_child_package_gate.json", {"status": "CHILD_PACKAGE_GATE_CONTRACT_READY"})
    _write_json(root / "role_package_gate.json", {"status": "ROLE_PACKAGE_GATE_READY"})

    sqlite_root.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sqlite_root / "st_annes_monthly_work_log.sqlite")
    try:
        conn.execute("CREATE TABLE work_log_events (event_id TEXT, description TEXT)")
        conn.execute(
            "INSERT INTO work_log_events VALUES (?, ?)",
            ("event_1", "RAW_SECRET_ROW_SHOULD_NOT_APPEAR"),
        )
        conn.execute("CREATE TABLE review_actions (review_id TEXT)")
        conn.commit()
    finally:
        conn.close()


def _answer(question: str, tmp_path: Path) -> dict:
    read_model_root = tmp_path / "read_models"
    sqlite_root = tmp_path / "sqlite"
    _fixture_sources(read_model_root, sqlite_root)
    return sqa.answer_system_question(
        question,
        read_model_root=read_model_root,
        sqlite_root=sqlite_root,
    )


def _walk_values(payload):
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield key, value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_values(value)


def test_chief_vs_spawned_worker_answer_explains_role_vs_package_worker(tmp_path):
    payload = _answer("What is the difference between Chief and a spawned worker?", tmp_path)
    text = json.dumps(payload)

    assert payload["workflow_ref"] == "system_question_answer"
    assert payload["speaker_ref"] in {"hermes", "chief"}
    assert "Chief is a named OpenClaw role" in text
    assert "package-bound execution thread" in text
    assert payload["machine_proof"]["child_agent_spawned"] is False
    assert payload["machine_proof"]["external_llm_called"] is False


def test_capital_hilton_submit_block_explains_provider_and_submit_gate(tmp_path):
    payload = _answer("Why did Submit Capital Hilton invoice block?", tmp_path)
    text = json.dumps(payload)

    assert payload["speaker_ref"] == "chief"
    assert payload["voice_mode"] == "diagnostic"
    assert "PROVIDER_GATE_REQUIRED" in text
    assert "final Submit gate" in text
    assert "No Coupa action" in text
    assert payload["authority_boundary"]["coupa_allowed"] is False


def test_email_authority_question_routes_to_guardian_and_blocks_send(tmp_path):
    payload = _answer("Can this send email?", tmp_path)
    text = json.dumps(payload)

    assert payload["speaker_ref"] == "guardian"
    assert payload["voice_mode"] == "safety_gate"
    assert "No email can be sent" in text
    assert "blocked_until_explicit_send_gate" in text
    assert payload["authority_boundary"]["email_send_allowed"] is False
    assert payload["machine_proof"]["email_send_performed"] is False


def test_sqlite_work_log_answer_summarizes_metadata_without_dumping_rows(tmp_path):
    payload = _answer("What does SQLite know about St. Anne's work logs?", tmp_path)
    text = json.dumps(payload)

    assert payload["speaker_ref"] == "chief"
    assert payload["voice_mode"] == "diagnostic"
    assert "work_log_events" in text
    assert "review_actions" in text
    assert "table counts" in text.lower()
    assert "RAW_SECRET_ROW_SHOULD_NOT_APPEAR" not in text
    assert payload["answer"]["unknown"]


def test_unknown_question_returns_safe_fallback_with_unknowns_and_proof_refs(tmp_path):
    payload = _answer("What does OpenClaw know about the purple submarine?", tmp_path)

    assert payload["speaker_ref"] == "openclaw"
    assert payload["answer"]["headline"] == "No local answer found"
    assert payload["answer"]["unknown"]
    assert payload["answer"]["proof_refs"]
    assert payload["machine_proof"]["live_execution_performed"] is False


def test_contract_exports_local_and_bridge_json_equal(tmp_path):
    read_model_root = tmp_path / "read_models"
    sqlite_root = tmp_path / "sqlite"
    _fixture_sources(read_model_root, sqlite_root)

    result = sqa.export_system_question_answer(
        read_model_root=read_model_root,
        sqlite_root=sqlite_root,
        export_root=tmp_path / "exported",
        bridge_export_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "System Question Answering.md",
        generated_at=FIXED_NOW,
    )

    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    assert local == bridge
    assert local["status"] == sqa.CONTRACT_STATUS
    assert local["workflow_ref"] == "system_question_answer"
    assert local["privacy"]["privacy_impact"] == "local_only"
    assert len(local["examples"]) == 5
    assert Path(result["wiki_path"]).exists()


def test_no_unsafe_true_grants(tmp_path):
    payload = _answer("Can this send email?", tmp_path)
    unsafe_keys = {
        "email_send_allowed",
        "ledger_posting_allowed",
        "browser_access_allowed",
        "gmail_allowed",
        "coupa_allowed",
        "portal_submit_allowed",
        "sent",
        "paid",
    }
    assert not [
        key
        for key, value in _walk_values(payload)
        if key in unsafe_keys and value is True
    ]
    assert payload["machine_proof"]["unsafe_true_grants_absent"] is True
