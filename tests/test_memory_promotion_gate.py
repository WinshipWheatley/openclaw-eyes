import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import memory_promotion_gate as gate


FIXED_NOW = "2026-06-03T14:30:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    _write_json(root / "gate_decision_ledger.json", {"status": "GATE_DECISION_LEDGER_READY"})
    _write_json(
        root / "operator_memory_distillation.json",
        {
            "status": "OPERATOR_MEMORY_DISTILLATION_READY",
            "memory_candidates": [
                {
                    "memory_ref": "memory_candidate:client",
                    "category": "payment_followup_facts",
                    "distilled_summary": "Capital Hilton is on payment watch.",
                    "privacy_class": "client_ref_only",
                    "allowed_usage": "Use as reminder only.",
                    "proof_refs": ["generated/read_models/capital_hilton_invoice_operator_run_status.json"],
                },
                {
                    "memory_ref": "memory_candidate:taste",
                    "category": "voice_taste_preferences",
                    "distilled_summary": "Cassandra leads homecoming briefings.",
                    "privacy_class": "operator_taste_preference",
                    "allowed_usage": "Use for tone only.",
                    "proof_refs": ["generated/read_models/homecoming_brief.json"],
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
        "automatic_promotion_performed",
        "raw_prompt_stored",
        "business_truth_created",
        "business_action_performed",
        "sent",
        "paid",
    }
    assert not [key for key, value in _walk_values(payload) if key in unsafe_keys and value is True]


def test_memory_promotion_gate_keeps_candidates_unpromoted(tmp_path):
    read_model = gate.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)

    assert read_model["status"] == "MEMORY_PROMOTION_GATE_READY"
    assert read_model["promotion_entry_count"] == 2
    entries = {entry["memory_ref"]: entry for entry in read_model["promotion_entries"]}
    assert entries["memory_candidate:client"]["promotion_status"] == "candidate"
    assert entries["memory_candidate:client"]["operator_approval_required"] is True
    assert entries["memory_candidate:taste"]["promotion_status"] == "candidate"
    assert entries["memory_candidate:taste"]["operator_approval_required"] is False
    assert all(entry["forbidden_usage"] for entry in read_model["promotion_entries"])
    assert read_model["machine_proof"]["automatic_promotion_performed"] is False
    _assert_no_unsafe_true_grants(read_model)


def test_missing_distillation_precondition_marks_not_ready(tmp_path):
    root = _fixture_root(tmp_path)
    _write_json(root / "operator_memory_distillation.json", {"status": "NOT_READY", "memory_candidates": []})

    read_model = gate.build_read_model(read_model_root=root, generated_at=FIXED_NOW)

    assert read_model["status"] == "MEMORY_PROMOTION_GATE_NOT_READY"
    assert read_model["machine_proof"]["preconditions_ready"] is False
    _assert_no_unsafe_true_grants(read_model)


def test_export_writes_local_bridge_equal_and_wiki(tmp_path):
    result = gate.export_memory_promotion_gate(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "Memory Promotion Gate.md",
        generated_at=FIXED_NOW,
    )

    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert local == bridge
    assert "No automatic promotion" in wiki
    assert result["status"] == "MEMORY_PROMOTION_GATE_READY"
    _assert_no_unsafe_true_grants(local)
