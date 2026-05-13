import json
import sqlite3

import pytest

from business_ops_ledger import init_business_ops_ledger, record_receipt


MODULE_ATLAS_ARTIFACTS = [
    ("docs/module_atlas/OPENCLAW_MODULE_ATLAS_V0.md", "docs_only"),
    ("docs/module_atlas/OPENCLAW_MODULE_MANIFEST_DRAFT_SCHEMA_V0.md", "inert"),
    ("docs/module_atlas/OPENCLAW_SYNTHETIC_MODULE_MANIFEST_EXAMPLES_V0.md", "inert"),
    ("docs/module_atlas/OPENCLAW_MODULE_MANIFEST_VALIDATION_CONTRACT_V0.md", "validation_proven"),
    ("scripts/validate_module_manifests.py", "validation_proven"),
    ("tests/test_module_manifest_validation.py", "validation_proven"),
]


@pytest.fixture
def temp_ledger(tmp_path):
    db_path = tmp_path / "generic_receipts.sqlite"
    init_business_ops_ledger(str(db_path))
    return str(db_path)


def _packet_payloads(db_path):
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT packet_json_safe FROM packets ORDER BY packet_id").fetchall()
    finally:
        conn.close()
    return [json.loads(row[0]) for row in rows]


def test_generic_receipt_records_artifact_checkpoint(temp_ledger):
    receipt_id = record_receipt(
        receipt_type="artifact_checkpoint",
        artifact_path="docs/module_atlas/OPENCLAW_MODULE_ATLAS_V0.md",
        commit_hash="6a1d5d9d1304ad2ff5228fa16e8db2e016b4eb1c",
        artifact_type="module_atlas_doc",
        artifact_status="docs_only",
        authority_status="no_runtime_authority",
        runtime_activation=False,
        sqlite_meaning="receipt_record_only",
        payload={"checkpoint_reason": "module_atlas_receipt_spine_proof"},
        db_path=temp_ledger,
    )

    assert receipt_id
    conn = sqlite3.connect(temp_ledger)
    try:
        event = conn.execute(
            "SELECT event_type, actor, operator_visible_summary FROM events WHERE event_id = ?",
            (receipt_id,),
        ).fetchone()
        packet = conn.execute(
            "SELECT packet_json_safe FROM packets WHERE packet_id = ?",
            (receipt_id,),
        ).fetchone()
    finally:
        conn.close()

    assert event[0] == "artifact_checkpoint"
    assert event[1] == "generic_receipt_spine_v0"
    assert "receipt_record_only" in event[2]
    assert packet is not None


def test_generic_receipt_stores_metadata_payload_only_not_full_markdown_body(temp_ledger):
    record_receipt(
        receipt_type="artifact_checkpoint",
        artifact_path="docs/module_atlas/OPENCLAW_MODULE_ATLAS_V0.md",
        artifact_status="docs_only",
        payload={"validation_command": "python3 scripts/validate_module_manifests.py"},
        db_path=temp_ledger,
    )

    packet_json = json.dumps(_packet_payloads(temp_ledger)[0], sort_keys=True)
    assert "payload_json" in packet_json
    assert "validation_command" in packet_json
    assert "# OpenClaw Module Atlas v0" not in packet_json
    assert "## 4. Candidate Module Families" not in packet_json


def test_module_atlas_artifact_receipts_remain_non_runtime_authority(temp_ledger):
    for artifact_path, artifact_status in MODULE_ATLAS_ARTIFACTS:
        receipt_id = record_receipt(
            receipt_type="artifact_checkpoint",
            artifact_path=artifact_path,
            commit_hash="6a1d5d9d1304ad2ff5228fa16e8db2e016b4eb1c",
            artifact_type="module_atlas_validation_artifact",
            artifact_status=artifact_status,
            authority_status="no_runtime_authority",
            runtime_activation=False,
            payload={"proof_scope": "module_atlas_validation_artifact_checkpoint"},
            db_path=temp_ledger,
        )
        assert receipt_id

    payloads = _packet_payloads(temp_ledger)
    assert len(payloads) == len(MODULE_ATLAS_ARTIFACTS)
    assert {payload["runtime_activation"] for payload in payloads} == {False}
    assert {payload["authority_status"] for payload in payloads} == {"no_runtime_authority"}
    assert {payload["sqlite_meaning"] for payload in payloads} == {"receipt_record_only"}


def test_missing_artifact_path_fails_safely_without_rows(temp_ledger):
    receipt_id = record_receipt(
        receipt_type="artifact_checkpoint",
        artifact_path="docs/module_atlas/DOES_NOT_EXIST.md",
        payload={"checkpoint_reason": "missing_path_should_not_record"},
        db_path=temp_ledger,
    )

    assert receipt_id == ""
    conn = sqlite3.connect(temp_ledger)
    try:
        event_count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        packet_count = conn.execute("SELECT COUNT(*) FROM packets").fetchone()[0]
    finally:
        conn.close()
    assert event_count == 0
    assert packet_count == 0


def test_generic_spine_represents_multiple_receipt_types_without_new_writers(temp_ledger):
    checkpoint_id = record_receipt(
        receipt_type="artifact_checkpoint",
        artifact_path="docs/module_atlas/OPENCLAW_MODULE_MANIFEST_VALIDATION_CONTRACT_V0.md",
        artifact_status="validation_proven",
        payload={"proof": "contract checkpoint"},
        db_path=temp_ledger,
    )
    validation_id = record_receipt(
        receipt_type="validation_result",
        artifact_path="scripts/validate_module_manifests.py",
        artifact_status="validation_proven",
        authority_status="validation_evidence_only",
        payload={
            "command": "python3 scripts/validate_module_manifests.py docs/module_atlas/OPENCLAW_SYNTHETIC_MODULE_MANIFEST_EXAMPLES_V0.md",
            "result": "pass",
        },
        db_path=temp_ledger,
    )

    assert checkpoint_id
    assert validation_id
    conn = sqlite3.connect(temp_ledger)
    try:
        event_types = {
            row[0] for row in conn.execute("SELECT event_type FROM events").fetchall()
        }
    finally:
        conn.close()
    assert event_types == {"artifact_checkpoint", "validation_result"}


def test_generic_receipt_rejects_runtime_activation_and_body_payloads(temp_ledger):
    with pytest.raises(ValueError, match="runtime_activation=True"):
        record_receipt(
            receipt_type="artifact_checkpoint",
            artifact_path="docs/module_atlas/OPENCLAW_MODULE_ATLAS_V0.md",
            runtime_activation=True,
            payload={},
            db_path=temp_ledger,
        )

    with pytest.raises(ValueError, match="full document or artifact body"):
        record_receipt(
            receipt_type="artifact_checkpoint",
            artifact_path="docs/module_atlas/OPENCLAW_MODULE_ATLAS_V0.md",
            payload={"markdown_body": "# OpenClaw Module Atlas v0\n..."},
            db_path=temp_ledger,
        )
