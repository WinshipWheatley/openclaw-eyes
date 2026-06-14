import json
import sqlite3
from pathlib import Path

import package_event_index as index


FIXED_NOW = "2026-06-02T16:30:00+00:00"
RAW_LONG_BODY = "RAW_LONG_PROMPT_BODY_SHOULD_NOT_BE_INDEXED"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _proof_refs(request_ref: Path, response_ref: Path, package_id: str) -> list[dict]:
    return [
        {"proof_type": "request_ref", "path": str(request_ref)},
        {"proof_type": "response_ref", "path": str(response_ref)},
        {"proof_type": "workflow_package", "ref": package_id},
        {"proof_type": "sqlite_path", "path": "generated/system_knowledge/workflow_package_queue.sqlite"},
    ]


def _write_workflow_package_sqlite(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE packages (
              package_id TEXT PRIMARY KEY,
              workflow_ref TEXT,
              world TEXT,
              client_ref TEXT,
              source_surface TEXT,
              source_text_ref TEXT,
              protected_text_hash TEXT,
              pii_status TEXT,
              privacy_impact_json TEXT,
              provider_policy TEXT,
              authority_boundary_json TEXT,
              status TEXT,
              created_at TEXT,
              updated_at TEXT
            )
            """
        )
        for package_id, workflow_ref, world, client_ref, status in [
            ("workflow_package:st_annes_1", "st_annes_work_log_event", "invoice_operations", "st_annes", "OPERATOR_REVIEW_REQUIRED"),
            ("workflow_package:capital_invoice_1", "capital_hilton_invoice_operator_assist", "invoice_operations", "capital_hilton", "PROVIDER_GATE_REQUIRED"),
            ("workflow_package:capital_proposal_1", "capital_hilton_proposal_followup", "business_development", "capital_hilton", "OPERATOR_REVIEW_REQUIRED"),
        ]:
            conn.execute(
                """
                INSERT INTO packages (
                  package_id, workflow_ref, world, client_ref, source_surface, source_text_ref,
                  protected_text_hash, pii_status, privacy_impact_json, provider_policy,
                  authority_boundary_json, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'mission_control', ?, ?, 'MINIMAL_BUSINESS_CONTEXT', '{}',
                  'local_noop_worker_only', ?, ?, ?, ?)
                """,
                (
                    package_id,
                    workflow_ref,
                    world,
                    client_ref,
                    f"protected_text_hash:sha256:{package_id.rsplit(':', 1)[-1]}",
                    f"sha256:{package_id.rsplit(':', 1)[-1]}",
                    json.dumps({"email_send_allowed": False, "ledger_posting_allowed": False, "paid": False}),
                    status,
                    FIXED_NOW,
                    FIXED_NOW,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def _fixture_sources(tmp_path: Path) -> dict[str, Path]:
    read_model_root = tmp_path / "generated/read_models"
    sqlite_root = tmp_path / "generated/system_knowledge"
    inbox = tmp_path / "bridge/mission_control_capture_requests/inbox"
    responses = tmp_path / "bridge/mission_control_responses/to_mac"

    package_db = sqlite_root / "workflow_package_queue.sqlite"
    journal_db = sqlite_root / "operator_conversation_journal.sqlite"
    ledger_db = sqlite_root / "business_ledger.sqlite"
    _write_workflow_package_sqlite(package_db)
    journal_db.write_bytes(b"")
    ledger_db.write_bytes(b"ledger must not be opened or indexed")

    flows = [
        {
            "journal_entry_id": "operator_conversation_journal:st_annes",
            "package_id": "workflow_package:st_annes_1",
            "workflow_ref": "st_annes_work_log_event",
            "request_name": "mission_control_operator_instruction_request_church_sound.json",
            "response_name": "openclaw_response_for_mac_church_sound.json",
            "target_world_ref": "finance",
            "target_thread_ref": "st_annes",
            "speaker_ref": "cassandra",
            "package_status": "OPERATOR_REVIEW_REQUIRED",
            "action_status": "OPERATOR_REVIEW_REQUIRED",
            "source_surface": "mission_control",
        },
        {
            "journal_entry_id": "operator_conversation_journal:capital_invoice",
            "package_id": "workflow_package:capital_invoice_1",
            "workflow_ref": "capital_hilton_invoice_operator_assist",
            "request_name": "mission_control_operator_instruction_request_capital_invoice.json",
            "response_name": "openclaw_response_for_mac_capital_invoice.json",
            "target_world_ref": "finance",
            "target_thread_ref": "capital_hilton",
            "speaker_ref": "chief",
            "package_status": "PROVIDER_GATE_REQUIRED",
            "action_status": "PROVIDER_GATE_REQUIRED",
            "source_surface": "mission_control",
        },
        {
            "journal_entry_id": "operator_conversation_journal:capital_proposal",
            "package_id": "workflow_package:capital_proposal_1",
            "workflow_ref": "capital_hilton_proposal_followup",
            "request_name": "mission_control_operator_instruction_request_capital_proposal.json",
            "response_name": "openclaw_response_for_mac_capital_proposal.json",
            "target_world_ref": "business_development",
            "target_thread_ref": "capital_hilton",
            "speaker_ref": "cassandra",
            "package_status": "OPERATOR_REVIEW_REQUIRED",
            "action_status": "OPERATOR_REVIEW_REQUIRED",
            "source_surface": "mission_control",
        },
    ]
    entries = []
    for flow in flows:
        request_ref = inbox / flow["request_name"]
        response_ref = responses / flow["response_name"]
        _write_json(
            request_ref,
            {
                "request_id": flow["package_id"].replace("workflow_package:", "request_"),
                "request_type": "WORKFLOW_PACKAGE_REQUEST_V0",
                "source_surface": "mission_control",
                "source_text": RAW_LONG_BODY * 8,
                "protected_text_hash": "sha256:" + flow["package_id"].rsplit(":", 1)[-1],
                "created_at": FIXED_NOW,
            },
        )
        _write_json(
            response_ref,
            {
                "source_request_id": flow["package_id"].replace("workflow_package:", "request_"),
                "workflow_ref": flow["workflow_ref"],
                "package_id": flow["package_id"],
                "package_status": flow["package_status"],
                "raw_internal_status": "RESPONSE_READY",
                "target_world_ref": flow["target_world_ref"],
                "target_thread_ref": flow["target_thread_ref"],
                "speaker_ref": flow["speaker_ref"],
                "operator_message": RAW_LONG_BODY * 8,
                "created_at": FIXED_NOW,
                "machine_proof": {
                    "email_send_performed": False,
                    "ledger_mutation_performed": False,
                    "business_state_mutation_performed": False,
                },
            },
        )
        entries.append(
            {
                **flow,
                "request_ref": str(request_ref),
                "response_ref": str(response_ref),
                "created_at": FIXED_NOW,
                "proof_refs": _proof_refs(request_ref, response_ref, flow["package_id"]),
                "raw_request_body_stored": False,
            }
        )

    _write_json(
        read_model_root / "operator_conversation_journal.json",
        {
            "read_model_id": "operator_conversation_journal",
            "status": "OPERATOR_CONVERSATION_JOURNAL_READY",
            "entry_count": len(entries),
            "entries": entries,
        },
    )
    _write_json(
        read_model_root / "workflow_package_queue_contract.json",
        {
            "read_model_id": "workflow_package_queue_contract",
            "status": "WORKFLOW_PACKAGE_QUEUE_V0_READY",
            "sqlite_path": str(package_db),
            "packages": [],
        },
    )
    _write_json(
        read_model_root / "capital_hilton_invoice_operator_run_status.json",
        {
            "read_model_id": "capital_hilton_invoice_operator_run_status",
            "status": "CAPITAL_HILTON_OPERATOR_RUN_RECORDED",
            "workflow_ref": "capital_hilton_invoice_operator_run",
            "client_ref": "capital_hilton",
            "coupa_submitted": True,
            "coupa_status_observed": "Processing",
            "email_to_annette_sent": True,
            "ledger_mutation_performed": False,
            "paid": False,
            "proof_refs": {"receipt_ref": "capital_hilton_receipt.json"},
        },
    )
    _write_json(
        read_model_root / "st_annes_invoice_status.json",
        {
            "read_model_id": "st_annes_invoice_status",
            "workflow_ref": "st_annes_invoice_workflow",
            "client_ref": "st_annes",
            "invoice_status": "MANUAL_SEND_OUT_OF_BAND_RECORDED",
            "paid": False,
        },
    )
    _write_json(
        read_model_root / "client_work_closeout_2026_06_01.json",
        {
            "read_model_id": "client_work_closeout_2026_06_01",
            "status": "CLIENT_WORK_CLOSEOUT_READY",
            "completed_work": [
                {"work_id": "capital_hilton_fight_weekend_proposal", "client_ref": "capital_hilton"}
            ],
        },
    )
    _write_json(
        read_model_root / "capital_hilton_business_development_proposal.json",
        {
            "read_model_id": "capital_hilton_business_development_proposal",
            "status": "CAPITAL_HILTON_PROPOSAL_SENT_RECORDED",
            "proposal_status": "SENT_FOR_CLIENT_REVIEW",
        },
    )
    return {
        "read_model_root": read_model_root,
        "sqlite_root": sqlite_root,
        "inbox": inbox,
        "responses": responses,
        "package_db": package_db,
        "journal_db": journal_db,
        "ledger_db": ledger_db,
    }


def _build(tmp_path: Path) -> dict:
    paths = _fixture_sources(tmp_path)
    payload = index.build_package_event_index(
        read_model_root=paths["read_model_root"],
        sqlite_root=paths["sqlite_root"],
        request_inbox=paths["inbox"],
        response_dir=paths["responses"],
        generated_at=FIXED_NOW,
    )
    return {"payload": payload, **paths}


def _row_by_workflow(payload: dict, workflow_ref: str) -> dict:
    return next(row for row in payload["events"] if row["workflow_ref"] == workflow_ref)


def test_st_annes_work_log_request_links_response_and_journal(tmp_path):
    data = _build(tmp_path)
    row = _row_by_workflow(data["payload"], "st_annes_work_log_event")

    assert row["package_id"] == "workflow_package:st_annes_1"
    assert row["request_ref"].endswith("mission_control_operator_instruction_request_church_sound.json")
    assert row["response_ref"].endswith("openclaw_response_for_mac_church_sound.json")
    assert row["journal_entry_id"] == "operator_conversation_journal:st_annes"
    assert row["target_world_ref"] == "finance"
    assert row["target_thread_ref"] == "st_annes"
    assert row["business_action_performed"] is False


def test_capital_hilton_invoice_operator_assist_links_submitted_status_read_model(tmp_path):
    data = _build(tmp_path)
    row = _row_by_workflow(data["payload"], "capital_hilton_invoice_operator_assist")

    assert row["package_status"] == "PROVIDER_GATE_REQUIRED"
    assert row["speaker_ref"] == "chief"
    assert row["business_action_performed"] is True
    assert row["business_action_kind"] == "operator_assisted_coupa_submission_and_email_recorded"
    assert "generated/read_models/capital_hilton_invoice_operator_run_status.json" in row["linked_read_models"]
    assert row["authority_summary"]["paid_truth"] is False
    assert row["authority_summary"]["ledger_excluded"] is True


def test_capital_hilton_proposal_links_business_development_read_model(tmp_path):
    data = _build(tmp_path)
    row = _row_by_workflow(data["payload"], "capital_hilton_proposal_followup")

    assert row["target_world_ref"] == "business_development"
    assert row["target_thread_ref"] == "capital_hilton"
    assert row["business_action_performed"] is True
    assert row["business_action_kind"] == "operator_assisted_proposal_send_recorded"
    assert "generated/read_models/client_work_closeout_2026_06_01.json" in row["linked_read_models"]


def test_raw_request_bodies_are_not_dumped(tmp_path):
    payload = _build(tmp_path)["payload"]
    rendered = json.dumps(payload)

    assert RAW_LONG_BODY not in rendered
    assert all(event["raw_request_body_stored"] is False for event in payload["events"])


def test_ledger_db_is_excluded(tmp_path):
    data = _build(tmp_path)
    payload = data["payload"]
    rendered = json.dumps(payload)

    assert "business_ledger.sqlite" not in rendered
    assert payload["source_systems"]["business_ledger"]["included"] is False
    assert payload["source_systems"]["business_ledger"]["policy"] == "excluded"


def test_no_unsafe_true_grants(tmp_path):
    payload = _build(tmp_path)["payload"]
    unsafe_keys = {
        "email_send_allowed",
        "gmail_allowed",
        "coupa_allowed",
        "coupa_submit_allowed",
        "ledger_posting_allowed",
        "paid",
        "sent",
        "portal_submit_allowed",
    }

    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                yield key, item
                yield from walk(item)
        elif isinstance(value, list):
            for item in value:
                yield from walk(item)

    assert not [(key, value) for key, value in walk(payload) if key in unsafe_keys and value is True]
    assert payload["machine_proof"]["unsafe_true_grants_absent"] is True


def test_sqlite_row_count_matches_json_count(tmp_path):
    paths = _fixture_sources(tmp_path)
    result = index.export_package_event_index(
        read_model_root=paths["read_model_root"],
        sqlite_root=paths["sqlite_root"],
        request_inbox=paths["inbox"],
        response_dir=paths["responses"],
        export_root=tmp_path / "generated/read_models",
        bridge_export_root=tmp_path / "bridge/read_models",
        wiki_path=tmp_path / "generated/wiki/openclaw/Package Event Index.md",
        sqlite_path=tmp_path / "generated/system_knowledge/package_event_index.sqlite",
        generated_at=FIXED_NOW,
    )
    payload = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))

    conn = sqlite3.connect(result["sqlite_path"])
    try:
        row_count = conn.execute("SELECT COUNT(*) FROM package_event_index").fetchone()[0]
        source_count = conn.execute("SELECT COUNT(*) FROM package_event_index_sources").fetchone()[0]
    finally:
        conn.close()

    assert row_count == payload["event_count"]
    assert source_count >= 4
    assert json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8")) == payload
    assert Path(result["wiki_path"]).exists()
