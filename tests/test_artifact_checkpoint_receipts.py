import json
import sqlite3

import pytest

from business_ops_ledger import init_business_ops_ledger
from scripts.generate_operator_status import (
    MODULE_ATLAS_BOOTSTRAP_COMMAND,
    get_artifact_checkpoint_receipts,
    generate_current_state,
)
from scripts.record_artifact_checkpoint_receipts import (
    ArtifactCheckpoint,
    MODULE_ATLAS_ARTIFACT_CHECKPOINTS,
    MODULE_ATLAS_ARTIFACT_PATHS,
    ensure_module_atlas_artifact_checkpoints,
    main as record_artifact_checkpoint_main,
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
        "artifact_checkpoint_expected_total": len(artifact_receipts),
        "artifact_checkpoint_bootstrap_command": MODULE_ATLAS_BOOTSTRAP_COMMAND,
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


def test_module_atlas_bootstrap_records_expected_artifact_checkpoint_receipts(temp_ledger):
    results = ensure_module_atlas_artifact_checkpoints(
        commit_hash=COMMIT_HASH,
        db_path=temp_ledger,
    )

    assert len(results) == len(MODULE_ATLAS_ARTIFACT_CHECKPOINTS)
    assert {result["action"] for result in results} == {"recorded"}
    payloads = _packet_payloads(temp_ledger)
    assert {payload["artifact_path"] for payload in payloads} == set(MODULE_ATLAS_ARTIFACT_PATHS)
    assert {payload["receipt_type"] for payload in payloads} == {"artifact_checkpoint"}
    assert {payload["authority_status"] for payload in payloads} == {"no_runtime_authority"}


def test_module_atlas_bootstrap_is_idempotent_on_rerun(temp_ledger):
    first = ensure_module_atlas_artifact_checkpoints(
        commit_hash=COMMIT_HASH,
        db_path=temp_ledger,
    )
    second = ensure_module_atlas_artifact_checkpoints(
        commit_hash=COMMIT_HASH,
        db_path=temp_ledger,
    )

    assert {result["action"] for result in first} == {"recorded"}
    assert {result["action"] for result in second} == {"present"}
    conn = sqlite3.connect(temp_ledger)
    try:
        event_count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        packet_count = conn.execute("SELECT COUNT(*) FROM packets").fetchone()[0]
    finally:
        conn.close()
    assert event_count == len(MODULE_ATLAS_ARTIFACT_CHECKPOINTS)
    assert packet_count == len(MODULE_ATLAS_ARTIFACT_CHECKPOINTS)


def test_module_atlas_bootstrap_cli_is_operator_readable_and_idempotent(temp_ledger, capsys):
    first_exit = record_artifact_checkpoint_main(
        ["--module-atlas", "--ensure", "--commit-hash", COMMIT_HASH, "--db", temp_ledger]
    )
    first_output = capsys.readouterr().out
    second_exit = record_artifact_checkpoint_main(
        ["--module-atlas", "--ensure", "--commit-hash", COMMIT_HASH, "--db", temp_ledger]
    )
    second_output = capsys.readouterr().out

    assert first_exit == 0
    assert second_exit == 0
    assert "Module Atlas receipt bootstrap" in first_output
    assert "Evidence: committed docs/code artifacts are checked against metadata-only receipts." in first_output
    assert "Boundary: receipt-record-only; no runtime authority or full body ingest." in first_output
    assert "RECORDED docs/module_atlas/OPENCLAW_MODULE_ATLAS_V0.md" in first_output
    assert "Summary: ensured=6 recorded=6 present=0 failed=0" in first_output
    assert "PRESENT docs/module_atlas/OPENCLAW_MODULE_ATLAS_V0.md" in second_output
    assert "Summary: ensured=6 recorded=0 present=6 failed=0" in second_output


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
    assert '"body_ingest_status": "not_ingested"' in packet_json


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
    assert "**Evidence:** committed docs/code artifacts have metadata-only SQLite checkpoint receipts." in output
    assert "**Boundary:** recorded checkpoint only; not runtime authority." in output
    assert "**Blocked:** no module, agent, broker, customer deployment, or runtime behavior is activated or authorized by these receipts." in output
    assert "**Next safe move:** review docs/tests/receipts; runtime activation still requires a separate approved lane." in output
    assert "No full Markdown/code body is ingested" in output
    assert "| Artifact | Receipt Time | Checkpoint | Authority Boundary |" in output
    assert "recorded `docs-only`" in output
    assert "recorded `inert`" in output
    assert ATLAS_DOC in output
    assert SCHEMA_DOC in output
    assert "`authority=no-runtime-authority`" in output
    assert "`runtime_activation=false`" in output
    assert "`sqlite=receipt-record-only`" in output
    assert "`body=not-ingested`" in output
    assert "no module, agent, broker, customer deployment, or runtime behavior is activated or authorized" in output.lower()
    forbidden_claims = [
        "runtime ready",
        "runtime-ready",
        "module active",
        "modules active",
        "broker connected",
        "agent wired",
        "customer deployment active",
    ]
    output_lower = output.lower()
    for claim in forbidden_claims:
        assert claim not in output_lower

    artifact_section = output.split("### Module Atlas Artifact Checkpoints", 1)[1].split("## 3.", 1)[0]
    assert "[ARTIFACT_CHECKPOINT]" not in artifact_section
    assert "[MODULE_ATLAS_ARTIFACT]" not in artifact_section
    assert len(artifact_section.splitlines()) <= 11


def test_generated_status_missing_receipts_shows_bootstrap_next_safe_move():
    snapshot = _snapshot_with_artifacts([])
    snapshot["artifact_checkpoint_expected_total"] = len(MODULE_ATLAS_ARTIFACT_PATHS)

    output = generate_current_state(snapshot)

    assert "### Module Atlas Artifact Checkpoints" in output
    assert "no local Module Atlas checkpoint receipts found for 6 committed docs/code artifacts" in output
    assert f"run `{MODULE_ATLAS_BOOTSTRAP_COMMAND}`" in output
    assert "recorded checkpoint only; not runtime authority" in output
    assert "No full Markdown/code body is ingested" in output
    output_lower = output.lower()
    for claim in [
        "runtime ready",
        "module active",
        "modules active",
        "broker connected",
        "customer deployment active",
    ]:
        assert claim not in output_lower
