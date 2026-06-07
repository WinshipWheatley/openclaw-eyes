import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import local_lm_proof_response_pilot_postmortem as postmortem
import proof_to_response_runtime


FIXED_NOW = "2026-06-07T14:30:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_sqlite(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        ("fallback_receipt", "present", "Verifier blocked the draft; safe fallback was published."),
        ("model_invocation_attempt_receipt", "present", "Exactly one local Ollama invocation attempt was recorded."),
        ("verifier_pass_fail_receipt", "present", "Deterministic verifier result: fail."),
    ]
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
CREATE TABLE local_lm_pilot_receipts (
  receipt_id TEXT PRIMARY KEY,
  receipt_ref TEXT NOT NULL,
  receipt_status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  source_ref TEXT NOT NULL,
  proof_summary TEXT NOT NULL,
  payload_hash TEXT NOT NULL,
  receipt_json TEXT NOT NULL
)
"""
        )
        for ref, status, summary in rows:
            conn.execute(
                "INSERT INTO local_lm_pilot_receipts VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (f"local_lm_pilot:{ref}", ref, status, FIXED_NOW, "", summary, "", "{}"),
            )
        conn.commit()


def _fixture_root(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "generated" / "read_models"
    _write_json(
        root / "local_lm_proof_response_one_time_pilot.json",
        {
            "status": "LOCAL_LM_PROOF_RESPONSE_ONE_TIME_PILOT_READY",
            "publication_decision": "safe_fallback_published",
            "model_output_parse": {
                "json_parse_succeeded": False,
                "raw_stdout_sha256": "sha256:stdout",
                "raw_stderr_sha256": "sha256:stderr",
            },
            "candidate_response": {
                "response_id": "local_ollama_candidate:parse_failed:finance_capital_hilton_payment_watch",
                "proof_bundle_id": "redacted_proof_bundle:finance_capital_hilton_payment_watch",
                "speaker_ref": "chief",
                "draft_headline": "",
                "draft_body": "",
                "draft_next_step": "",
                "claimed_facts": [],
                "implied_actions": [],
                "requested_controls": [],
                "uncertainty_notes": ["model_output_json_parse_failed"],
            },
            "verifier_result": {
                "verifier_id": "proof_to_response_verifier_v0",
                "status": "BLOCKED_BY_DETERMINISTIC_VERIFIER",
                "publishable": False,
                "verification_errors": [
                    "response_not_concise",
                    "required_phrase_missing:payment evidence",
                    "required_phrase_missing:ledger",
                    "next_step_not_allowed:",
                ],
                "unsafe_true_grants": [],
            },
            "published_response": {
                "verification_status": "fallback",
                "headline": "Needs verification",
                "body": "I need stronger proof before I can publish a response.",
                "next_step": "Show details",
            },
        },
    )
    _write_json(
        root / proof_to_response_runtime.LATEST_JSON_EXPORT_NAME,
        {
            "status": proof_to_response_runtime.READY_STATUS,
            "candidate_source": "local_ollama_one_time_pilot",
            "proof_to_response_status": "fallback",
            "latest_response": {"headline": "Needs verification"},
        },
    )
    _write_json(
        root / proof_to_response_runtime.STATUS_JSON_EXPORT_NAME,
        {
            "status": proof_to_response_runtime.READY_STATUS,
            "active_candidate_source": proof_to_response_runtime.CANDIDATE_SOURCE_SHADOW_PILOT,
        },
    )
    _write_json(root / "proof_bundle_freshness_trace_status.json", {"status": "PROOF_BUNDLE_FRESHNESS_TRACE_INTEGRATION_READY"})
    _write_json(root / "proof_bundle_builder_redaction_status.json", {"status": "PROOF_BUNDLE_BUILDER_REDACTION_INTEGRATION_READY"})
    sqlite_path = tmp_path / "pilot.sqlite"
    _write_sqlite(sqlite_path)
    return root, sqlite_path


def _read_model(tmp_path: Path) -> dict:
    root, sqlite_path = _fixture_root(tmp_path)
    return postmortem.build_read_model(read_model_root=root, sqlite_path=sqlite_path, generated_at=FIXED_NOW)


def test_postmortem_records_verifier_failure_reason(tmp_path):
    read_model = _read_model(tmp_path)

    assert read_model["status"] == postmortem.READY_STATUS
    assert read_model["machine_proof"]["verifier_failure_reason_recorded"] is True
    assert "response_not_concise" in read_model["analysis"]["verification_errors"]
    assert "required_phrase_missing:payment evidence" in read_model["analysis"]["verification_errors"]


def test_postmortem_confirms_fallback_published(tmp_path):
    read_model = _read_model(tmp_path)

    assert read_model["analysis"]["fallback_correctly_published"] is True
    assert read_model["fallback_publication"]["fallback_receipt_present"] is True
    assert read_model["fallback_publication"]["latest_response_status"] == "fallback"


def test_postmortem_does_not_mark_pilot_successful_if_draft_failed(tmp_path):
    read_model = _read_model(tmp_path)

    assert read_model["pilot_draft_successful"] is False
    assert read_model["pilot_attempt_successful"] is False
    assert read_model["machine_proof"]["does_not_mark_pilot_successful_if_draft_failed"] is True
    assert read_model["answer_to_required_questions"]["failure_type"] == "non_json_structurally_invalid_empty_candidate"


def test_recommendations_do_not_loosen_protected_gates(tmp_path):
    read_model = _read_model(tmp_path)
    verifier_policy = read_model["recommendations"]["verifier_policy"]

    assert "Do not loosen truth or authority checks to make the model pass." in verifier_policy
    assert "Do not loosen protected gates." in verifier_policy
    assert read_model["authority_boundary"]["truth_checks_loosened"] is False
    assert read_model["authority_boundary"]["protected_gate_loosened"] is False


def test_classifies_failure_as_non_json_not_factually_unsafe(tmp_path):
    analysis = _read_model(tmp_path)["analysis"]
    classification = analysis["failure_classification"]

    assert classification["non_json"] is True
    assert classification["structurally_invalid"] is True
    assert classification["empty_candidate_after_parse_failure"] is True
    assert classification["factually_unsafe"] is False
    assert analysis["draft_included_unsupported_completion_claims"] is False
    assert analysis["draft_included_protected_action_promises"] is False
    assert analysis["draft_included_machine_contract_jargon"] is False


def test_next_test_is_schema_adapter_not_rerun(tmp_path):
    recs = _read_model(tmp_path)["recommendations"]

    assert recs["next_test_recommendation"] == "schema_adapter_test"
    assert recs["next_invocation_requires_operator_approval"] is True
    assert recs["local_retry_recommended_now"] is False
    assert recs["external_synthetic_test_recommended_now"] is False


def test_unsafe_true_grant_scan_clean(tmp_path):
    read_model = _read_model(tmp_path)

    assert postmortem.unsafe_true_grants(read_model) == []
    assert read_model["unsafe_true_grants"] == []
    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True


def test_export_json_bridge_equality_and_wiki(tmp_path):
    root, sqlite_path = _fixture_root(tmp_path)
    result = postmortem.export_postmortem(
        read_model_root=root,
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "Local LM Proof Response Pilot Postmortem.md",
        sqlite_path=sqlite_path,
        generated_at=FIXED_NOW,
    )
    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert result["status"] == postmortem.READY_STATUS
    assert local == bridge
    assert postmortem.unsafe_true_grants(local) == []
    assert wiki.startswith("# Local LM Proof Response Pilot Postmortem")
