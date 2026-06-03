import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import artifact_lineage_registry as lineage


FIXED_NOW = "2026-06-03T13:45:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_file(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _fixture_root(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "generated" / "read_models"
    artifacts = tmp_path / "artifacts"
    st_pdf = _write_file(artifacts / "st_annes" / "Invoice_St_Annes_May_2026_OPERATOR_SENT.pdf", b"st annes pdf")
    st_receipt = _write_file(artifacts / "st_annes" / "st_annes_manual_invoice_sent_receipt.json", b"{}")
    cap_pdf = _write_file(artifacts / "capital_hilton" / "Invoice_Capital_Hilton_2026-06-01.pdf", b"capital pdf")
    cap_report = _write_file(artifacts / "capital_hilton" / "capital_hilton_invoice_operator_run_report.md", b"report")
    proposal_pdf = _write_file(artifacts / "proposals" / "Capital_Hilton_Fight_Weekend_Entertainment_Proposal_DRAFT.pdf", b"proposal")
    proposal_receipt = _write_file(artifacts / "proposals" / "capital_hilton_proposal_email_sent_receipt.json", b"{}")
    live_pdf = _write_file(artifacts / "live_arts_md" / "Invoice_2026-1001_Live_Arts_MD_June_2026_Speaker_Rental_scope_corrected_live_arts_md.pdf", b"live arts")
    screenshot = _write_file(tmp_path / "generated" / "screenshots" / "example_mission_control_review.png", b"png")

    _write_json(root / "package_event_index.json", {"status": "PACKAGE_EVENT_INDEX_READY"})
    _write_json(root / "canonical_state_map.json", {"status": "CANONICAL_STATE_MAP_READY"})
    _write_json(
        root / "st_annes_invoice_status.json",
        {
            "client_ref": "st_annes",
            "workflow_ref": "st_annes_invoice_workflow",
            "invoice_status": "MANUAL_SEND_OUT_OF_BAND_RECORDED",
            "source_pdf_path": str(st_pdf),
            "source_receipt_path": str(st_receipt),
        },
    )
    _write_json(
        root / "capital_hilton_invoice_operator_run_status.json",
        {
            "client_ref": "capital_hilton",
            "workflow_ref": "capital_hilton_invoice_operator_run",
            "status": "CAPITAL_HILTON_OPERATOR_RUN_RECORDED",
            "artifact_refs": {
                "pdf": {"kind": "operator_run_invoice_pdf", "path": str(cap_pdf)},
                "run_report": {"kind": "operator_run_report", "path": str(cap_report)},
            },
        },
    )
    _write_json(
        root / "capital_hilton_business_development_proposal.json",
        {
            "client_ref": "capital_hilton",
            "proposal_status": "SENT_FOR_CLIENT_REVIEW",
            "artifact_refs": {
                "pdf": {"kind": "proposal_pdf_draft", "path": str(proposal_pdf)},
                "proposal_send_receipt": {"kind": "proposal_email_sent_receipt", "path": str(proposal_receipt)},
            },
        },
    )
    _write_json(
        root / "workroom_review_packet_index.json",
        {
            "status": "WORKROOM_REVIEW_PACKET_INDEX_READY",
            "packets": [
                {
                    "review_packet_id": "review_packet:fixture",
                    "package_id": "pkg:fixture",
                    "proof_refs": [str(screenshot)],
                }
            ],
        },
    )
    return root, artifacts


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
        "trusted_for_action",
        "business_action_performed",
        "sent",
        "paid",
    }
    assert not [key for key, value in _walk_values(payload) if key in unsafe_keys and value is True]


def test_builds_lineage_for_known_artifacts(tmp_path):
    root, artifacts = _fixture_root(tmp_path)

    read_model = lineage.build_read_model(
        read_model_root=root,
        artifact_search_roots=[artifacts],
        sqlite_path=tmp_path / "artifact_lineage_registry.sqlite",
        generated_at=FIXED_NOW,
    )

    assert read_model["status"] == "ARTIFACT_LINEAGE_REGISTRY_READY"
    refs = {artifact["artifact_ref"]: artifact for artifact in read_model["artifacts"]}
    assert "artifact:st_annes_operator_sent_invoice_pdf" in refs
    assert "artifact:capital_hilton_invoice_pdf" in refs
    assert "artifact:capital_hilton_proposal_pdf" in refs
    assert "artifact:live_arts_corrected_invoice_pdf" in refs
    assert "artifact:workroom_review_packet_fixture_screenshot" in refs
    assert refs["artifact:st_annes_operator_sent_invoice_pdf"]["lineage_status"] == "operator_sent"
    assert refs["artifact:live_arts_corrected_invoice_pdf"]["lineage_status"] == "active"
    assert all(artifact["trusted_for_action"] is False for artifact in read_model["artifacts"])
    assert all(artifact["sha256"].startswith("sha256:") for artifact in read_model["artifacts"] if artifact["path_exists"])
    _assert_no_unsafe_true_grants(read_model)


def test_missing_precondition_marks_not_ready(tmp_path):
    root, artifacts = _fixture_root(tmp_path)
    _write_json(root / "canonical_state_map.json", {"status": "NOT_READY"})

    read_model = lineage.build_read_model(
        read_model_root=root,
        artifact_search_roots=[artifacts],
        sqlite_path=tmp_path / "artifact_lineage_registry.sqlite",
        generated_at=FIXED_NOW,
    )

    assert read_model["status"] == "ARTIFACT_LINEAGE_REGISTRY_NOT_READY"
    assert read_model["machine_proof"]["preconditions_ready"] is False
    _assert_no_unsafe_true_grants(read_model)


def test_export_writes_sqlite_local_bridge_equal_and_wiki(tmp_path):
    root, artifacts = _fixture_root(tmp_path)

    result = lineage.export_artifact_lineage_registry(
        read_model_root=root,
        artifact_search_roots=[artifacts],
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        sqlite_path=tmp_path / "system_knowledge" / "artifact_lineage_registry.sqlite",
        wiki_path=tmp_path / "wiki" / "Artifact Lineage Registry.md",
        generated_at=FIXED_NOW,
    )

    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert local == bridge
    assert "does not delete or overwrite artifacts" in wiki
    conn = sqlite3.connect(result["sqlite_path"])
    try:
        row_count = conn.execute("SELECT COUNT(*) FROM artifact_lineage").fetchone()[0]
    finally:
        conn.close()
    assert row_count == local["artifact_count"]
    assert result["status"] == "ARTIFACT_LINEAGE_REGISTRY_READY"
    _assert_no_unsafe_true_grants(local)
