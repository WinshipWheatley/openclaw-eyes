import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import evidence_confidence_scoring as scoring


FIXED_NOW = "2026-06-03T14:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    _write_json(root / "canonical_state_map.json", {"status": "CANONICAL_STATE_MAP_READY"})
    _write_json(root / "package_event_index.json", {"status": "PACKAGE_EVENT_INDEX_READY"})
    _write_json(
        root / "artifact_lineage_registry.json",
        {
            "status": "ARTIFACT_LINEAGE_REGISTRY_READY",
            "artifacts": [
                {
                    "artifact_ref": "artifact:st_annes_operator_sent_invoice_pdf",
                    "artifact_kind": "pdf",
                    "lineage_status": "operator_sent",
                    "sha256": "sha256:stannes",
                    "proof_refs": ["generated/read_models/st_annes_invoice_status.json"],
                    "trusted_for_action": False,
                },
                {
                    "artifact_ref": "artifact:workroom_review_packet_fixture_screenshot",
                    "artifact_kind": "screenshot",
                    "lineage_status": "test_only",
                    "sha256": "",
                    "proof_refs": ["generated/read_models/workroom_review_packet_index.json"],
                    "trusted_for_action": False,
                },
            ],
        },
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
        "business_action_performed",
        "sent",
        "paid",
    }
    assert not [key for key, value in _walk_values(payload) if key in unsafe_keys and value is True]


def test_scores_receipts_hashes_generated_summaries_and_unknowns(tmp_path):
    read_model = scoring.build_read_model(
        read_model_root=_fixture_root(tmp_path),
        generated_at=FIXED_NOW,
    )

    assert read_model["status"] == "EVIDENCE_CONFIDENCE_SCORING_READY"
    classes = {fact["confidence_class"] for fact in read_model["facts"]}
    assert {
        "proven_receipt",
        "proven_artifact_hash",
        "operator_reported",
        "generated_summary",
        "inferred",
        "stale",
        "rejected",
        "test_only",
        "unknown",
    }.issubset(classes)
    facts = {fact["fact_ref"]: fact for fact in read_model["facts"]}
    assert facts["fact:st_annes_invoice_pdf_hash"]["confidence_class"] == "proven_artifact_hash"
    assert facts["fact:st_annes_manual_send_recorded"]["confidence_class"] == "proven_receipt"
    assert facts["fact:capital_hilton_paid_truth"]["confidence_class"] == "unknown"
    assert facts["fact:capital_hilton_paid_truth"]["should_show_primary"] is False
    assert facts["fact:capital_hilton_paid_truth"]["should_require_operator_review"] is True
    assert facts["fact:workroom_screenshot_fixture"]["confidence_class"] == "test_only"
    assert facts["fact:workroom_screenshot_fixture"]["should_show_primary"] is False
    _assert_no_unsafe_true_grants(read_model)


def test_generated_summaries_do_not_override_receipts(tmp_path):
    read_model = scoring.build_read_model(
        read_model_root=_fixture_root(tmp_path),
        generated_at=FIXED_NOW,
    )

    facts = {fact["fact_ref"]: fact for fact in read_model["facts"]}
    assert facts["fact:package_event_index_summary"]["confidence_class"] == "generated_summary"
    assert facts["fact:package_event_index_summary"]["should_show_primary"] is False
    assert "Cannot override receipts" in facts["fact:package_event_index_summary"]["recommended_ui_label"]


def test_missing_artifact_lineage_precondition_marks_not_ready(tmp_path):
    root = _fixture_root(tmp_path)
    _write_json(root / "artifact_lineage_registry.json", {"status": "NOT_READY", "artifacts": []})

    read_model = scoring.build_read_model(read_model_root=root, generated_at=FIXED_NOW)

    assert read_model["status"] == "EVIDENCE_CONFIDENCE_SCORING_NOT_READY"
    assert read_model["machine_proof"]["preconditions_ready"] is False
    _assert_no_unsafe_true_grants(read_model)


def test_export_writes_local_bridge_equal_and_wiki(tmp_path):
    result = scoring.export_evidence_confidence_scoring(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "Evidence Confidence Scoring.md",
        generated_at=FIXED_NOW,
    )

    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert local == bridge
    assert "paid truth requires payment evidence" in wiki
    assert result["status"] == "EVIDENCE_CONFIDENCE_SCORING_READY"
    _assert_no_unsafe_true_grants(local)
