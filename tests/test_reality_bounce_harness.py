import json
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import guardian_output_gate
import intent_ingest_gate
import local_shadow_lm_runner
import reality_bounce_harness as harness


FIXED_NOW = "2026-05-26T00:00:00+00:00"


def _receipt_rows(db_path: Path) -> list[sqlite3.Row]:
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("SELECT * FROM repoa_worker_run_receipts ORDER BY source_request_id").fetchall()


def _receipt_count(db_path: Path) -> int:
    with sqlite3.connect(db_path) as conn:
        exists = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='repoa_worker_run_receipts'"
        ).fetchone()[0]
        if not exists:
            return 0
        return conn.execute("SELECT COUNT(*) FROM repoa_worker_run_receipts").fetchone()[0]


def test_arbitrary_status_text_routes_to_chief_and_writes_receipt(tmp_path):
    db_path = tmp_path / "reality_bounce.sqlite"
    payload = harness.run_text(
        "what's next for Capital Hilton?",
        db_path=db_path,
        generated_at=FIXED_NOW,
    )
    result = payload["result"]

    assert result["status"] == harness.STATUS_ACCEPTED_WITH_RECEIPT
    assert result["selected_role_family"] == "CHIEF"
    assert result["selected_voice"] == "CHIEF"
    assert result["worker_fixture_used"].endswith("local_status_v0")
    assert result["guardian_result"]["validation_result"]["verdict"] == guardian_output_gate.VALIDATED
    assert result["receipt_written"] is True
    assert payload["machine_proof"]["live_lm1_call_performed"] is False
    assert payload["machine_proof"]["repo_b_runtime_started"] is False

    rows = _receipt_rows(db_path)
    assert len(rows) == 1
    row = rows[0]
    receipt_payload = json.loads(row["payload_json"])
    assert row["source_request_id"] == result["source_request_id"]
    assert row["role_family"] == "CHIEF"
    assert row["selected_voice"] == "CHIEF"
    assert row["validation_verdict"] == guardian_output_gate.VALIDATED
    assert row["external_action"] == 0
    assert row["authority_used"] == 0
    assert receipt_payload["receipt_classification"] == "reality_bounce_fixture"
    assert receipt_payload["production_receipt"] is False


def test_curly_apostrophe_status_text_routes_to_chief(tmp_path):
    db_path = tmp_path / "reality_bounce.sqlite"
    payload = harness.run_text(
        "what\u2019s next for Capital Hilton?",
        db_path=db_path,
        generated_at=FIXED_NOW,
    )
    result = payload["result"]

    assert result["status"] == harness.STATUS_ACCEPTED_WITH_RECEIPT
    assert result["selected_role_family"] == "CHIEF"
    assert result["selected_voice"] == "CHIEF"
    assert result["receipt_written"] is True
    assert "next safe move for the Capital Hilton invoice" in payload["operator_stdout"]


def test_arbitrary_draft_text_routes_to_clara_and_writes_draft_receipt(tmp_path):
    db_path = tmp_path / "reality_bounce.sqlite"
    payload = harness.run_text(
        "draft a note to Hilton about the invoice package",
        db_path=db_path,
        generated_at=FIXED_NOW,
    )
    result = payload["result"]
    worker_result = result["worker_result"]

    assert result["status"] == harness.STATUS_ACCEPTED_WITH_RECEIPT
    assert result["selected_role_family"] == "CASSANDRA_CLARA"
    assert result["selected_voice"] == "CLARA"
    assert worker_result["response_kind"] == "draft"
    assert worker_result["send_performed"] is False
    assert worker_result["requested_tool_calls"] == ()
    assert worker_result["requested_external_actions"] == ()
    assert "sent" not in worker_result["draft_text"].lower()
    assert "Hi Capital Hilton team" in payload["operator_stdout"]
    assert "Draft only - nothing was sent" in payload["operator_stdout"]

    rows = _receipt_rows(db_path)
    assert len(rows) == 1
    assert rows[0]["role_family"] == "CASSANDRA_CLARA"
    assert rows[0]["selected_voice"] == "CLARA"
    assert rows[0]["external_action"] == 0
    assert rows[0]["authority_used"] == 0


def test_package_prep_text_routes_to_delegated_graph_and_writes_child_parent_receipts(tmp_path):
    db_path = tmp_path / "reality_bounce.sqlite"
    payload = harness.run_text(
        "prepare the Capital Hilton invoice package",
        db_path=db_path,
        generated_at=FIXED_NOW,
    )
    result = payload["result"]

    assert result["status"] == harness.STATUS_ACCEPTED_WITH_RECEIPT
    assert result["selected_role_family"] == "DELEGATED_PACKAGE_GRAPH"
    assert result["worker_fixture_used"] == harness.WORKER_DELEGATED_PACKAGE_GRAPH
    assert result["receipt_written"] is True
    assert result["guardian_result"]["validation_result"]["verdict"] == guardian_output_gate.VALIDATED
    assert "Draft path prepared." in payload["operator_stdout"]
    assert "Coupa portal submission proof is still required before this invoice can be treated as sent." in payload[
        "operator_stdout"
    ]
    assert "Guardian validated outputs" not in payload["operator_stdout"]
    assert payload["machine_proof"]["delegated_package_graph_used"] is True
    assert payload["machine_proof"]["send_submit_performed"] is False
    assert result["scoped_mac_response_candidate"]["proof_flags"]["guardian_output_validation_status"] == (
        "PASSED_FOR_DRAFT_DISPLAY_ONLY"
    )
    assert result["scoped_mac_response_candidate"]["proof_flags"]["guardian_approval_request_status"] == "NOT_CREATED"

    rows = _receipt_rows(db_path)
    assert len(rows) == 3
    assert {row["role_family"] for row in rows} == {"CHIEF", "CASSANDRA_CLARA"}
    assert all(row["external_action"] == 0 for row in rows)
    assert all(row["authority_used"] == 0 for row in rows)

    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        graph_row = conn.execute("SELECT * FROM delegated_package_graph_runs").fetchone()

    assert graph_row is not None
    graph_payload = json.loads(graph_row["payload_json"])
    assert len(graph_payload["child_receipt_ids"]) == 2
    assert graph_payload["parent_receipt_id"] == result["receipt_id"]
    assert graph_payload["parent_source_request_id"] == result["source_request_id"]


def test_prepare_and_send_runs_delegated_graph_but_blocks_send_portion(tmp_path):
    db_path = tmp_path / "reality_bounce.sqlite"
    payload = harness.run_text(
        "prepare and send the Capital Hilton invoice package",
        db_path=db_path,
        generated_at=FIXED_NOW,
    )
    result = payload["result"]

    assert result["status"] == harness.STATUS_ACCEPTED_WITH_RECEIPT
    assert result["selected_role_family"] == "DELEGATED_PACKAGE_GRAPH"
    assert result["worker_fixture_used"] == harness.WORKER_DELEGATED_PACKAGE_GRAPH
    assert result["receipt_written"] is True
    assert "Approval is required before any send step." in payload["operator_stdout"]
    assert "Nothing was sent or submitted." in payload["operator_stdout"]
    assert result["boundary_flags"]["send_submit_performed"] is False

    rows = _receipt_rows(db_path)
    assert len(rows) == 3
    assert all("send" not in json.loads(row["payload_json"])["receipt_classification"] for row in rows)
    assert all(row["external_action"] == 0 for row in rows)
    assert all(row["authority_used"] == 0 for row in rows)


def test_send_invoice_now_blocks_without_worker_completion_receipt(tmp_path):
    db_path = tmp_path / "reality_bounce.sqlite"
    payload = harness.run_text("send the invoice now", db_path=db_path, generated_at=FIXED_NOW)
    result = payload["result"]

    assert result["status"] == harness.STATUS_BLOCKED
    assert result["gate2_result"]["outcome"] == intent_ingest_gate.BLOCKED_AUTHORITY
    assert result["worker_result"] is None
    assert result["receipt_written"] is False
    assert "approval" in payload["operator_stdout"].lower()
    assert _receipt_count(db_path) == 0


def test_ambiguous_text_returns_clarification_without_worker_receipt(tmp_path):
    db_path = tmp_path / "reality_bounce.sqlite"
    payload = harness.run_text("do the thing", db_path=db_path, generated_at=FIXED_NOW)
    result = payload["result"]

    assert result["status"] == harness.STATUS_CLARIFICATION
    assert result["gate2_result"]["outcome"] == intent_ingest_gate.NEEDS_CLARIFICATION
    assert result["receipt_written"] is False
    assert "what should openclaw work on" in payload["operator_stdout"].lower()
    assert _receipt_count(db_path) == 0


def test_whats_next_still_routes_to_chief_only_not_delegated_graph(tmp_path):
    db_path = tmp_path / "reality_bounce.sqlite"
    payload = harness.run_text(
        "what's next for Capital Hilton?",
        db_path=db_path,
        generated_at=FIXED_NOW,
    )
    result = payload["result"]

    assert result["status"] == harness.STATUS_ACCEPTED_WITH_RECEIPT
    assert result["selected_role_family"] == "CHIEF"
    assert result["worker_fixture_used"].endswith("local_status_v0")
    assert payload["machine_proof"]["delegated_package_graph_used"] is False
    assert _receipt_count(db_path) == 1
    with sqlite3.connect(db_path) as conn:
        exists = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='delegated_package_graph_runs'"
        ).fetchone()[0]
    assert exists == 0


def test_delete_other_from_openclaw_is_supersession_or_clarification_not_physical_delete(tmp_path):
    payload = harness.run_text(
        "delete the other one from OpenClaw",
        db_path=tmp_path / "reality_bounce.sqlite",
        generated_at=FIXED_NOW,
    )
    result = payload["result"]
    accepted = result["gate2_result"].get("accepted_intent") or {}

    assert result["status"] in {harness.STATUS_ACCEPTED_RESPONSE_ONLY, harness.STATUS_CLARIFICATION}
    assert result["worker_result"] is None
    assert result["receipt_written"] is False
    assert result["boundary_flags"]["file_mutation_performed"] is False
    assert "deleted from disk" in payload["operator_stdout"].lower() or result["status"] == harness.STATUS_CLARIFICATION
    if accepted:
        assert accepted["safe_action_type"] == "SUPERSEDE_ACTIVE_REFERENCE_NOT_PHYSICAL_DELETE"
        assert "do not delete any file from disk" in accepted["requested_action"].lower()


def test_unsafe_worker_output_claiming_sent_submitted_paid_is_guardian_blocked(tmp_path):
    payload = harness.unsafe_claim_guardian_fixture(
        db_path=tmp_path / "reality_bounce.sqlite",
        generated_at=FIXED_NOW,
    )

    validation = payload["guardian_result"]["validation_result"]
    assert validation["verdict"] == guardian_output_gate.BLOCKED_FORBIDDEN_CLAIM
    assert validation["output_publish_allowed"] is False
    assert {"sent", "submitted", "paid"}.issubset(set(validation["forbidden_claims"]))
    assert payload["receipt_written"] is False


def test_money_request_denied_then_rogue_worker_sends_claim(tmp_path):
    db_path = tmp_path / "reality_bounce.sqlite"
    denied_payload = harness.run_text(
        "send the invoice now",
        db_path=db_path,
        generated_at=FIXED_NOW,
    )
    denied_result = denied_payload["result"]

    assert denied_result["status"] == harness.STATUS_BLOCKED
    assert denied_result["gate2_result"]["outcome"] == intent_ingest_gate.BLOCKED_AUTHORITY
    assert denied_result["worker_result"] is None
    assert denied_result["receipt_written"] is False
    assert denied_result["boundary_flags"]["external_action_performed"] is False
    assert denied_result["boundary_flags"]["send_submit_performed"] is False
    assert _receipt_count(db_path) == 0

    rogue_payload = harness.unsafe_claim_guardian_fixture(
        db_path=db_path,
        generated_at=FIXED_NOW,
    )
    validation = rogue_payload["guardian_result"]["validation_result"]

    assert validation["verdict"] == guardian_output_gate.BLOCKED_FORBIDDEN_CLAIM
    assert validation["output_publish_allowed"] is False
    assert {"sent", "submitted"}.issubset(set(validation["forbidden_claims"]))
    assert rogue_payload["receipt_written"] is False
    assert rogue_payload["machine_proof"]["external_action_performed"] is False
    assert rogue_payload["machine_proof"]["send_submit_performed"] is False
    assert _receipt_count(db_path) == 0


def test_cli_stdout_is_operator_language_and_not_backend_sludge(tmp_path):
    db_path = tmp_path / "cli_reality_bounce.sqlite"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_reality_bounce.py",
            "draft a note to Hilton about the invoice package",
            "--db-path",
            str(db_path),
            "--generated-at",
            FIXED_NOW,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    stdout = completed.stdout

    assert "Draft prepared" in stdout
    assert "Hi Capital Hilton team" in stdout
    assert "Draft only - nothing was sent" in stdout
    forbidden = ("worker route unavailable", "deterministic worker rule", "Gate 2", "Gate 3", "request contract")
    assert not any(term.lower() in stdout.lower() for term in forbidden)


def _fake_shadow_result(*, lane, request_id, route_decision, parsed_json, status=local_shadow_lm_runner.RESULT_OK, error=""):
    return {
        "schema_version": local_shadow_lm_runner.SCHEMA_VERSION,
        "runner_id": local_shadow_lm_runner.RUNNER_ID,
        "status": status,
        "lane": lane,
        "request_id": request_id,
        "provider_policy_id": route_decision.get("selected_provider_policy_id", ""),
        "provider_ref": route_decision.get("selected_provider_ref", ""),
        "selected_model_class": route_decision.get("selected_model_class", ""),
        "local_model": "test-local-shadow-model",
        "prompt_hash": "sha256:test",
        "parsed_json": parsed_json,
        "raw_response_text": json.dumps(parsed_json),
        "error": error,
        "duration_ms": 1,
        "authority_boundary": dict(local_shadow_lm_runner.AUTHORITY_BOUNDARY),
        "shadow_policy": dict(local_shadow_lm_runner.LOCAL_SHADOW_POLICY),
    }


def _install_fake_shadow_runner(monkeypatch, *, rogue_lm2_sent_claim=False):
    def fake_generate_json(*, prompt, lane, request_id, route_decision, **_kwargs):
        lowered = prompt.lower()
        if lane == "LM1_INTENT_PROPOSAL":
            operator_text = ""
            marker = '"operator_text": "'
            if marker in prompt:
                operator_text = prompt.split(marker, 1)[1].split('"', 1)[0].lower()
            if "send the invoice now" in operator_text:
                parsed = {
                    "inferred_intent_type": "REQUEST_APPROVAL",
                    "target_agent_role": "CASSANDRA",
                    "requested_action": "Send the invoice now.",
                    "confidence": "HIGH",
                    "ambiguity_status": "UNAMBIGUOUS",
                    "authority_requested": {"send_submit": True, "external_action": True},
                    "authority_granted": {"send_submit": False, "external_action": False},
                }
            elif "do the thing" in operator_text:
                parsed = {
                    "inferred_intent_type": "ASK_CLARIFICATION",
                    "target_agent_role": "OPENCLAW_SYSTEM",
                    "requested_action": "Ask what object and safe outcome the operator means.",
                    "confidence": "MEDIUM",
                    "ambiguity_status": "MISSING_CONTEXT",
                    "required_clarification": "What should OpenClaw work on - the invoice workbook, the invoice package, or something else?",
                    "missing_requirements": ["MISSING_CONTEXT"],
                }
            elif "draft a note" in operator_text:
                parsed = {
                    "inferred_intent_type": "CAPTURE_MISSING_INPUT",
                    "target_agent_role": "CASSANDRA",
                    "requested_action": "comms_draft_or_status",
                    "confidence": "HIGH",
                    "ambiguity_status": "UNAMBIGUOUS",
                    "authority_requested": {"send_submit": False, "external_action": False},
                }
            elif "real workbook" in operator_text and "remove the test" in operator_text:
                parsed = {
                    "inferred_intent_type": "ATTACH_SOURCE_REF",
                    "target_agent_role": "OPENCLAW_SYSTEM",
                    "requested_action": "Retire the previous OpenClaw active reference and use newest workbook as current; preserve files on disk.",
                    "confidence": "HIGH",
                    "ambiguity_status": "UNAMBIGUOUS",
                    "source_refs_used": ["local_artifact_reference:newest_capital_hilton_workbook"],
                    "authority_requested": {"file_mutation": False, "external_action": False},
                }
            else:
                parsed = {
                    "inferred_intent_type": "ANSWER_STATUS",
                    "target_agent_role": "CHIEF",
                    "requested_action": "status_or_next_safe_move",
                    "confidence": "HIGH",
                    "ambiguity_status": "UNAMBIGUOUS",
                    "authority_requested": {"send_submit": False, "external_action": False},
                }
            return _fake_shadow_result(lane=lane, request_id=request_id, route_decision=route_decision, parsed_json=parsed)

        if rogue_lm2_sent_claim:
            parsed = {
                "response_author": "CHIEF",
                "headline": "Invoice sent",
                "one_line_answer": "I sent the invoice.",
                "eliwinship": "I sent the invoice and submitted it.",
                "next_action": "Done.",
                "completion_claims": ["sent", "submitted"],
            }
        elif "selected_voice" in prompt and "CLARA" in prompt:
            parsed = {
                "response_author": "CASSANDRA_CLARA",
                "selected_voice": "CLARA",
                "headline": "Draft prepared",
                "one_line_answer": "Clara prepared draft wording only.",
                "draft_text": "Hi Capital Hilton team - I am preparing the invoice package for review.",
                "next_action": "Next: review the draft before any delivery step.",
                "requested_tool_calls": [],
                "requested_external_actions": [],
                "authority_requested": {"send_submit": False, "external_action": False},
            }
        else:
            parsed = {
                "response_author": "CHIEF",
                "headline": "Next safe move",
                "one_line_answer": "Review the current workbook and mapping, then prepare the approval packet.",
                "eliwinship": "Here is the next safe move: review the current workbook and field mapping, then prepare the invoice package for approval. Nothing will be sent until approved.",
                "next_action": "Next: confirm workbook and mapping.",
                "requested_tool_calls": [],
                "requested_external_actions": [],
                "authority_requested": {"send_submit": False, "external_action": False},
            }
        return _fake_shadow_result(lane=lane, request_id=request_id, route_decision=route_decision, parsed_json=parsed)

    monkeypatch.setattr(harness.local_shadow_lm_runner, "generate_json", fake_generate_json)


def test_shadow_lm_mode_is_explicit_and_off_by_default(tmp_path):
    payload = harness.run_text(
        "what's next for Capital Hilton?",
        db_path=tmp_path / "reality_bounce.sqlite",
        generated_at=FIXED_NOW,
    )

    assert payload["mode"] == "local"
    assert payload["shadow_lm_status"] == "NOT_REQUESTED"
    assert payload["machine_proof"]["shadow_lm_requested"] is False
    assert payload["machine_proof"]["model_call_performed"] is False


def test_shadow_lm_policy_or_availability_block_records_no_model_completion(tmp_path, monkeypatch):
    def fake_generate_json(*, lane, request_id, route_decision, **_kwargs):
        return _fake_shadow_result(
            lane=lane,
            request_id=request_id,
            route_decision=route_decision,
            parsed_json={},
            status=local_shadow_lm_runner.RESULT_MODEL_UNAVAILABLE,
            error="No local model available.",
        )

    monkeypatch.setattr(harness.local_shadow_lm_runner, "generate_json", fake_generate_json)
    payload = harness.run_text(
        "what's next for Capital Hilton?",
        mode="shadow-lm",
        db_path=tmp_path / "reality_bounce.sqlite",
        generated_at=FIXED_NOW,
    )

    assert payload["mode"] == "shadow-lm"
    assert payload["shadow_lm_status"] == "SHADOW_LM_BLOCKED_OR_INCOMPLETE"
    assert payload["machine_proof"]["model_call_performed"] is False
    assert payload["machine_proof"]["shadow_record_written"] is True
    assert payload["result"]["status"] == harness.STATUS_CONTEXT_NEEDED
    assert "normal local route is still available" in payload["operator_stdout"]


def test_shadow_lm_status_message_passes_gate2_gate4_and_records_sqlite(tmp_path, monkeypatch):
    db_path = tmp_path / "reality_bounce.sqlite"
    _install_fake_shadow_runner(monkeypatch)

    payload = harness.run_text(
        "what\u2019s next for Capital Hilton?",
        mode="shadow-lm",
        db_path=db_path,
        generated_at=FIXED_NOW,
    )
    shadow = payload["shadow_lm_result"]

    assert payload["shadow_lm_status"] == "SHADOW_LM_RAN"
    assert payload["machine_proof"]["shadow_lm1_call_performed"] is True
    assert payload["machine_proof"]["shadow_lm2_call_performed"] is True
    assert payload["machine_proof"]["production_authority_false"] is True
    assert shadow["gate2_result"]["outcome"] == intent_ingest_gate.ACCEPTED_INTENT
    assert shadow["gate4_result"]["validation_result"]["verdict"] == guardian_output_gate.VALIDATED
    assert shadow["shadow_record_written"] is True
    assert shadow["lm1_call_result"]["local_model"] == "test-local-shadow-model"

    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM reality_bounce_shadow_lm_runs").fetchone()[0]
    assert count == 1


def test_shadow_lm_clara_draft_passes_without_send_claim(tmp_path, monkeypatch):
    _install_fake_shadow_runner(monkeypatch)
    payload = harness.run_text(
        "draft a note to Hilton about the invoice package",
        mode="shadow-lm",
        db_path=tmp_path / "reality_bounce.sqlite",
        generated_at=FIXED_NOW,
    )
    shadow = payload["shadow_lm_result"]

    assert shadow["gate2_result"]["outcome"] == intent_ingest_gate.ACCEPTED_INTENT
    assert shadow["selected_voice"] == "CLARA"
    assert shadow["gate4_result"]["validation_result"]["verdict"] == guardian_output_gate.VALIDATED
    assert "Hi Capital Hilton team" in payload["operator_stdout"]
    assert "Draft only - nothing was sent" in payload["operator_stdout"]


def test_shadow_lm_send_request_remains_gate2_blocked_and_no_lm2(tmp_path, monkeypatch):
    _install_fake_shadow_runner(monkeypatch)
    payload = harness.run_text(
        "send the invoice now",
        mode="shadow-lm",
        db_path=tmp_path / "reality_bounce.sqlite",
        generated_at=FIXED_NOW,
    )
    shadow = payload["shadow_lm_result"]

    assert shadow["gate2_result"]["outcome"] == intent_ingest_gate.BLOCKED_AUTHORITY
    assert shadow["lm2_call_result"] is None
    assert payload["machine_proof"]["shadow_lm1_call_performed"] is True
    assert payload["machine_proof"]["shadow_lm2_call_performed"] is False
    assert "cannot send this without approval" in payload["operator_stdout"].lower()


def test_shadow_lm_ambiguous_request_clarifies_and_no_lm2(tmp_path, monkeypatch):
    _install_fake_shadow_runner(monkeypatch)
    payload = harness.run_text(
        "do the thing",
        mode="shadow-lm",
        db_path=tmp_path / "reality_bounce.sqlite",
        generated_at=FIXED_NOW,
    )
    shadow = payload["shadow_lm_result"]

    assert shadow["gate2_result"]["outcome"] == intent_ingest_gate.NEEDS_CLARIFICATION
    assert shadow["lm2_call_result"] is None
    assert "what should openclaw work on" in payload["operator_stdout"].lower()


def test_shadow_lm_clara_draft_claiming_sent_is_guardian_blocked(tmp_path, monkeypatch):
    _install_fake_shadow_runner(monkeypatch, rogue_lm2_sent_claim=True)
    payload = harness.run_text(
        "draft a note to Hilton about the invoice package",
        mode="shadow-lm",
        db_path=tmp_path / "reality_bounce.sqlite",
        generated_at=FIXED_NOW,
    )
    validation = payload["shadow_lm_result"]["gate4_result"]["validation_result"]

    assert validation["verdict"] == guardian_output_gate.BLOCKED_FORBIDDEN_CLAIM
    assert payload["result"]["status"] == harness.STATUS_GUARDIAN_BLOCKED
    assert payload["machine_proof"]["external_action_performed"] is False
