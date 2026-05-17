import json
from pathlib import Path

from cassandra_chief_memory_authority import build_cassandra_chief_structured_import_plan
from cassandra_chief_memory_import_approval import (
    JSON_EXPORT_NAME,
    OPERATOR_EXPORT_NAME,
    build_cassandra_chief_memory_import_approval,
    export_cassandra_chief_memory_import_approval,
    format_cassandra_chief_memory_import_approval,
)
from scripts.export_cassandra_chief_memory_import_approval_read_model import main as export_main


FIXED_NOW = "2026-05-16T12:00:00+00:00"


def _structured_plan():
    return build_cassandra_chief_structured_import_plan(generated_at=FIXED_NOW)


def _hitl_proof(**overrides):
    proof = {
        "schema_version": "guardian_hitl_cassandra_proposal_shadow_v0",
        "safe_to_import_cassandra_chief_memory": True,
        "runtime_authority_changed": False,
        "caller_switched": False,
        "old_hitl_deleted": False,
        "raw_payload_stored": False,
        "callback_decision_shadow_support": True,
    }
    proof.update(overrides)
    return proof


def _by_name(items):
    return {item["display_name"]: item for item in items}


def test_approval_receipt_records_operator_category_decisions_without_import():
    receipt = build_cassandra_chief_memory_import_approval(
        structured_import_plan=_structured_plan(),
        hitl_proof=_hitl_proof(),
        generated_at=FIXED_NOW,
    )

    assert receipt["schema_version"] == "cassandra_chief_memory_import_approval_v0"
    assert receipt["data_imported"] is False
    assert receipt["raw_data_imported"] is False
    assert receipt["raw_content_read"] is False
    assert receipt["runtime_authority_changed"] is False
    assert receipt["hitl_proof_required"] is True
    assert receipt["hitl_proof_satisfied"] is True
    assert receipt["safe_to_import_structured_facts"] is True
    assert receipt["next_safe_lane"] == "Cassandra/Chief Structured Fact Import v0"

    approved = _by_name(receipt["approved_categories"])
    assert set(approved) == {
        "contacts and nicknames",
        "company/contact relationships",
        "allowed email recipients / email permission posture",
        "invoice facts",
        "receivable/payment tracking",
    }
    assert all(item["import_allowed_now"] is False for item in approved.values())
    assert all(item["import_allowed_later"] is True for item in approved.values())
    assert all(item["raw_content_allowed"] is False for item in approved.values())
    assert all(item["no_send_authority"] is True for item in approved.values())
    assert all(item["no_runtime_authority"] is True for item in approved.values())
    assert all(
        item["evidence_status_for_later_import"] == "parsed_evidence_not_truth"
        for item in approved.values()
    )
    assert all(
        item["trust_status_for_later_import"] == "needs_operator_confirmation"
        for item in approved.values()
    )


def test_non_import_fates_remain_blocked_deferred_or_metadata_only():
    receipt = build_cassandra_chief_memory_import_approval(
        structured_import_plan=_structured_plan(),
        hitl_proof=_hitl_proof(),
        generated_at=FIXED_NOW,
    )

    evidence_only = _by_name(receipt["evidence_source_only_categories"])
    assert set(evidence_only) == {"Chief session/task memory", "Windows-side logs"}
    assert all(item["approved_fate"] == "register_as_evidence_source_only" for item in evidence_only.values())
    assert all(item["import_allowed_later"] is False for item in evidence_only.values())

    summarize_only = _by_name(receipt["summarize_extract_only_categories"])
    assert set(summarize_only) == {
        "Cassandra notes",
        "correspondence metadata",
        "calendar/event notes metadata",
        "billing tracker CSV/PDF paths",
    }
    assert all(item["approved_fate"] == "summarize_or_extract_only" for item in summarize_only.values())
    assert all(item["raw_content_allowed"] is False for item in summarize_only.values())

    reconcile_first = _by_name(receipt["reconcile_first_categories"])
    assert set(reconcile_first) == {"old HITL JSON/JSONL state"}
    assert reconcile_first["old HITL JSON/JSONL state"]["approved_fate"] == "authority_conflict_reconcile_first"
    assert receipt["old_hitl_imported"] is False

    cleanup_later = _by_name(receipt["cleanup_later_categories"])
    assert set(cleanup_later) == {"untracked polish_loop Cassandra failure tasks"}
    assert cleanup_later["untracked polish_loop Cassandra failure tasks"]["approved_fate"] == "delete_local_residue_later"
    assert receipt["cleanup_files_deleted"] is False

    deferred = _by_name(receipt["deferred_categories"])
    assert set(deferred) == {"album/song progress state", "dirty generated agent_presence snapshots"}
    assert receipt["agent_presence_imported"] is False


def test_hitl_proof_is_required_before_structured_fact_import_is_safe():
    receipt = build_cassandra_chief_memory_import_approval(
        structured_import_plan=_structured_plan(),
        hitl_proof=_hitl_proof(safe_to_import_cassandra_chief_memory=False),
        generated_at=FIXED_NOW,
    )

    assert receipt["hitl_proof_required"] is True
    assert receipt["hitl_proof_satisfied"] is False
    assert receipt["safe_to_import_structured_facts"] is False
    assert receipt["next_safe_lane"] == "Resolve Cassandra HITL proof before structured fact import"


def test_operator_packet_summarizes_approval_without_claiming_import():
    receipt = build_cassandra_chief_memory_import_approval(
        structured_import_plan=_structured_plan(),
        hitl_proof=_hitl_proof(),
        generated_at=FIXED_NOW,
    )
    rendered = format_cassandra_chief_memory_import_approval(receipt)

    assert "Approved for later structured import" in rendered
    assert "Evidence-source-only" in rendered
    assert "Summarize/extract-only" in rendered
    assert "Reconcile-first / not imported" in rendered
    assert "Cleanup later only" in rendered
    assert "Deferred" in rendered
    assert "No data was imported." in rendered
    assert "No raw content was read." in rendered
    assert "Old HITL JSON/JSONL was not imported." in rendered
    assert "Cleanup candidates were not deleted." in rendered


def test_export_writes_valid_json_and_operator_outputs(tmp_path):
    export_root = tmp_path / "read_models"
    plan_path = tmp_path / "plan.json"
    proof_path = tmp_path / "proof.json"
    plan_path.write_text(json.dumps(_structured_plan()), encoding="utf-8")
    proof_path.write_text(json.dumps(_hitl_proof()), encoding="utf-8")

    summary = export_cassandra_chief_memory_import_approval(
        export_root=export_root,
        structured_import_plan_path=plan_path,
        hitl_proof_path=proof_path,
        generated_at=FIXED_NOW,
    )

    assert summary["safe_to_import_structured_facts"] is True
    payload = json.loads((export_root / JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (export_root / OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")
    assert payload["approval_receipt_id"] == summary["approval_receipt_id"]
    assert payload["data_imported"] is False
    assert "Structured fact import safe now: `true`" in operator

    assert export_main(
        [
            "--export-root",
            str(export_root),
            "--structured-import-plan",
            str(plan_path),
            "--hitl-proof",
            str(proof_path),
            "--format",
            "json",
        ]
    ) == 0


def test_receipt_surface_does_not_import_repo_b_or_use_network_send_subprocess():
    source_files = [
        Path("cassandra_chief_memory_import_approval.py"),
        Path("scripts/export_cassandra_chief_memory_import_approval_read_model.py"),
    ]
    forbidden = [
        "/home/openclaw_external/openclaw-runtime",
        "import subprocess",
        "subprocess.",
        "os.system",
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "send_message",
        "reply_text",
        "smtplib",
        "shell=True",
        "eval(",
    ]
    for path in source_files:
        text = path.read_text(encoding="utf-8").lower()
        for token in forbidden:
            assert token.lower() not in text
