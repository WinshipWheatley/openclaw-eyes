import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import operator_memory_distillation as memory


FIXED_NOW = "2026-06-03T14:15:00+00:00"
RAW_PROMPT = "RAW_OPERATOR_PROMPT_BODY_SHOULD_NOT_APPEAR"
SECRET = "SECRET_TOKEN_SHOULD_NOT_APPEAR"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    _write_json(
        root / "operator_conversation_journal.json",
        {
            "status": "OPERATOR_CONVERSATION_JOURNAL_READY",
            "entries": [
                {
                    "journal_entry_id": "journal:fixture",
                    "raw_request_body": RAW_PROMPT,
                    "secret": SECRET,
                }
            ],
        },
    )
    _write_json(root / "package_event_index.json", {"status": "PACKAGE_EVENT_INDEX_READY"})
    _write_json(root / "artifact_lineage_registry.json", {"status": "ARTIFACT_LINEAGE_REGISTRY_READY"})
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
        "raw_prompt_stored",
        "business_truth_created",
        "business_action_performed",
        "sent",
        "paid",
    }
    assert not [key for key, value in _walk_values(payload) if key in unsafe_keys and value is True]


def test_distills_privacy_safe_memory_candidates(tmp_path):
    read_model = memory.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)

    assert read_model["status"] == "OPERATOR_MEMORY_DISTILLATION_READY"
    categories = {candidate["category"] for candidate in read_model["memory_candidates"]}
    assert {
        "client_preferences",
        "workflow_lessons",
        "provider_failure_modes",
        "voice_taste_preferences",
        "lane_order_preferences",
        "payment_followup_facts",
        "do_not_repeat",
        "unresolved_questions",
    } == categories
    rendered = json.dumps(read_model)
    assert RAW_PROMPT not in rendered
    assert SECRET not in rendered
    assert all(candidate["raw_prompt_stored"] is False for candidate in read_model["memory_candidates"])
    assert all(candidate["business_truth_created"] is False for candidate in read_model["memory_candidates"])
    assert all(candidate["promotion_status"] == "candidate" for candidate in read_model["memory_candidates"])
    assert all(candidate["proof_refs"] for candidate in read_model["memory_candidates"])
    _assert_no_unsafe_true_grants(read_model)


def test_seed_examples_are_present(tmp_path):
    read_model = memory.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)
    summaries = " ".join(candidate["distilled_summary"] for candidate in read_model["memory_candidates"])

    assert "St. Anne" in summaries
    assert "Helm should be action desk" in summaries
    assert "Coupa invoice numbers cannot use hyphen" in summaries
    assert "Excel helper permissions are unstable" in summaries
    assert "Proof should be collapsed" in summaries


def test_missing_journal_precondition_marks_not_ready(tmp_path):
    root = _fixture_root(tmp_path)
    _write_json(root / "operator_conversation_journal.json", {"status": "NOT_READY"})

    read_model = memory.build_read_model(read_model_root=root, generated_at=FIXED_NOW)

    assert read_model["status"] == "OPERATOR_MEMORY_DISTILLATION_NOT_READY"
    assert read_model["machine_proof"]["preconditions_ready"] is False
    _assert_no_unsafe_true_grants(read_model)


def test_export_writes_local_bridge_equal_and_wiki(tmp_path):
    result = memory.export_operator_memory_distillation(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "Operator Memory Distillation.md",
        generated_at=FIXED_NOW,
    )

    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert local == bridge
    assert "No raw long prompt dumps" in wiki
    assert result["status"] == "OPERATOR_MEMORY_DISTILLATION_READY"
    _assert_no_unsafe_true_grants(local)
