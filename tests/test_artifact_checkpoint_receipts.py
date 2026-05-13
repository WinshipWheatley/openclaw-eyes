import json
import sqlite3

import pytest

from business_ops_ledger import init_business_ops_ledger
from scripts.generate_operator_status import (
    get_artifact_checkpoint_receipts,
    generate_current_state,
)
from scripts.record_artifact_checkpoint_receipts import (
    ArtifactCheckpoint,
    record_artifact_checkpoints,
)


COMMIT_HASH = "d097d9833e655629f6dfcb231ef9a3d3607bec2c"
ATLAS_DOC = "docs/module_atlas/OPENCLAW_MODULE_ATLAS_V0.md"
SCHEMA_DOC = "docs/module_atlas/OPENCLAW_MODULE_MANIFEST_DRAFT_SCHEMA_V0.md"


@pytest.fixture
def temp_ledger(tmp_path):
    db_path = tmp_path / "artifact_checkpoints.sqlite"
    init_business_ops_ledger(str(db_path))
    return str(db_path)


def _packet_payloads(db_path):
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT packet_json_safe FROM packets ORDER BY packet_id").fetchall()
    finally:
        conn.close()
    return [json.loads(row[0]) for row in rows]


def _snapshot_with_artifacts(artifact_receipts):
    return {
        "timestamp": "2026-05-13T10:00:00",
        "where_are_we": {
            "git_head": "d097d98",
            "git_branch": "main",
            "git_status": "Clean",
        },
        "ledger_info": {
            "status": "active",
            "event_count": 2,
            "has_snapshot_receipt": True,
        },
        "confirmed_current": [
            "Git HEAD: d097d98 feat(receipts)",
            "Ledger Status: active",
        ],
        "recent_proofs": [],
        "strongest_clean_proof": None,
        "artifact_checkpoint_receipts": artifact_receipts,
        "active_lane": "Receipt spine validation.",
        "allowed_tools": "Repo and ledger metadata reads.",
        "forbidden_surfaces": "Private/no-go paths.",
        "north_star": "Receipts are evidence only.",
        "truth_substrate": {"status": "unavailable", "reason": "test fixture"},
        "next_safe_move": "Continue docs/tests only.",
        "visible_road_horizon": {
            "visible_moves": ["Move 1"],
            "branch_after": "Proof",
            "unsafe_beyond": "Runtime activation",
        },
    }


def test_recording_explicit_artifact_checkpoints_writes_generic_receipts(temp_ledger):
    results = record_artifact_checkpoints(
        [
            ArtifactCheckpoint(ATLAS_DOC, "module-atlas-v0", "module_atlas_doc", "docs_only"),
            ArtifactCheckpoint(SCHEMA_DOC, "manifest-schema-v0", "module_atlas_doc", "inert"),
        ],
        commit_hash=COMMIT_HASH,
        source_basis=["docs/operations/OPENCLAW_GENERIC_RECEIPT_SPINE_V0.md"],
        db_path=temp_ledger,
    )

    assert [result["recorded"] for result in results] == [True, True]
    payloads = _packet_payloads(temp_ledger)
    assert {payload["receipt_type"] for payload in payloads} == {"artifact_checkpoint"}
    assert {payload["artifact_path"] for payload in payloads} == {ATLAS_DOC, SCHEMA_DOC}


def test_missing_artifact_path_fails_safely(temp_ledger):
    results = record_artifact_checkpoints(
        [
            ArtifactCheckpoint(
                "docs/module_atlas/DOES_NOT_EXIST.md",
                "missing",
                "module_atlas_doc",
                "docs_only",
            )
        ],
        commit_hash=COMMIT_HASH,
        db_path=temp_ledger,
    )

    assert results[0]["recorded"] is False
    conn = sqlite3.connect(temp_ledger)
    try:
        assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM packets").fetchone()[0] == 0
    finally:
        conn.close()


def test_artifact_checkpoint_receipts_store_metadata_only(temp_ledger):
    record_artifact_checkpoints(
        [ArtifactCheckpoint(ATLAS_DOC, "module-atlas-v0", "module_atlas_doc", "docs_only")],
        commit_hash=COMMIT_HASH,
        db_path=temp_ledger,
    )

    packet_json = json.dumps(_packet_payloads(temp_ledger)[0], sort_keys=True)
    assert "module-atlas-v0" in packet_json
    assert "# OpenClaw Module Atlas v0" not in packet_json
    assert "## 4. Candidate Module Families" not in packet_json
    assert '"full_body_ingested": false' in packet_json


def test_artifact_checkpoint_receipts_are_non_runtime_no_authority(temp_ledger):
    record_artifact_checkpoints(
        [ArtifactCheckpoint(ATLAS_DOC, "module-atlas-v0", "module_atlas_doc", "docs_only")],
        commit_hash=COMMIT_HASH,
        db_path=temp_ledger,
    )

    payload = _packet_payloads(temp_ledger)[0]
    assert payload["runtime_activation"] is False
    assert payload["authority_status"] == "no_runtime_authority"
    assert payload["sqlite_meaning"] == "receipt_record_only"


def test_generated_status_surfaces_module_atlas_artifact_receipts(temp_ledger):
    record_artifact_checkpoints(
        [
            ArtifactCheckpoint(ATLAS_DOC, "module-atlas-v0", "module_atlas_doc", "docs_only"),
            ArtifactCheckpoint(SCHEMA_DOC, "manifest-schema-v0", "module_atlas_doc", "inert"),
        ],
        commit_hash=COMMIT_HASH,
        db_path=temp_ledger,
    )

    receipts = get_artifact_checkpoint_receipts(
        db_path=temp_ledger,
        artifact_paths=[ATLAS_DOC, SCHEMA_DOC],
    )
    output = generate_current_state(_snapshot_with_artifacts(receipts))

    assert "### Module Atlas Artifact Checkpoints" in output
    assert "Metadata-only SQLite artifact receipts" in output
    assert ATLAS_DOC in output
    assert SCHEMA_DOC in output
    assert "status=docs-only" in output
    assert "status=inert" in output
    assert "authority=no-runtime-authority" in output
    assert "runtime_activation=false" in output
    assert "No Runtime Authority" in output
