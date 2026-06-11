import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import watch_desk_feed as feed


FIXED_NOW = "2026-06-10T21:10:00+00:00"


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_task(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _build(read_model_root: Path, task_root: Path | None = None, previous=None) -> dict:
    return feed.build_watch_desk_feed(
        read_model_root=read_model_root,
        task_root=task_root or read_model_root / "tasks",
        generated_at=FIXED_NOW,
        previous_item_states=previous,
    )


def _pending_approval_queue() -> dict:
    return {
        "approval_requests": [
            {
                "approval_request_id": "approval_request:one",
                "status": "pending",
                "requested_action": "approve_existing_packet",
                "plain_summary": "Do not copy this unsafe private raw body: winship@example.test",
            }
        ]
    }


def test_approval_waiting_fixture_produces_exactly_one_item(tmp_path):
    _write_json(tmp_path / "approval_request_queue.json", _pending_approval_queue())

    payload = _build(tmp_path)

    assert payload["item_count"] == 1
    item = payload["feed_items"][0]
    assert item["lane"] == "guardian_approval"
    assert item["urgency"] == "needs_operator"
    assert item["source_receipt_ref"] == "generated/read_models/approval_request_queue.json#pending"
    assert item["push_candidate"] is True
    assert item["push_allowed"] is False


def test_cassandra_ar_send_authority_waiting_fixture_produces_exactly_one_item(tmp_path):
    _write_json(
        tmp_path / "cassandra_draft_worker_readback.json",
        {
            "request": {
                "request_id": "cassandra_request:one",
                "approval_required": True,
                "send_authority": False,
            },
            "readback": {
                "status": "DRAFT_READY_FOR_REVIEW",
                "approval_required": True,
                "operator_message": "Unsafe private raw body winship@example.test must not appear.",
            },
        },
    )

    payload = _build(tmp_path)

    assert payload["item_count"] == 1
    item = payload["feed_items"][0]
    assert item["lane"] == "cassandra_ar"
    assert item["urgency"] == "needs_operator"
    assert item["source_receipt_ref"] == "generated/read_models/cassandra_draft_worker_readback.json#readback"
    assert item["push_candidate"] is True
    assert item["push_allowed"] is False


def test_reply_timeout_failure_task_fixture_produces_exactly_one_item(tmp_path):
    task_root = tmp_path / "tasks"
    _write_task(
        task_root / "chief-cassandra-failure-20260610T205623.md",
        """title: chief-cassandra-failure-20260610T205623
profile: quick
goal: Investigate a reply timeout
scope:
- Request summary: unsafe private body with winship@example.test and quoted client text
success:
- Root cause identified
generated_by: chief_cassandra_failure
generated_at: 2026-06-10T20:56:23.068137
""",
    )

    payload = _build(tmp_path, task_root)

    assert payload["item_count"] == 1
    item = payload["feed_items"][0]
    assert item["lane"] == "cassandra_ar"
    assert item["urgency"] == "blocked"
    assert item["source_receipt_ref"].endswith("#generated_by")
    assert item["push_candidate"] is True
    assert item["push_allowed"] is False


def test_stale_sync_fixture_produces_exactly_one_item(tmp_path):
    _write_json(
        tmp_path / "sync_health.json",
        {
            "display_status": "needs_mac_sync",
            "mirror_status": "needs_mac_sync",
            "missing_expected": 2,
            "hash_mismatch": 1,
            "generated_at": FIXED_NOW,
        },
    )

    payload = _build(tmp_path)

    assert payload["item_count"] == 1
    item = payload["feed_items"][0]
    assert item["lane"] == "mac_sync"
    assert item["urgency"] == "watch"
    assert item["source_receipt_ref"] == "generated/read_models/sync_health.json#mirror_status"
    assert item["push_candidate"] is False
    assert item["push_allowed"] is False


def test_unchanged_state_produces_zero_new_push_candidates(tmp_path):
    _write_json(tmp_path / "approval_request_queue.json", _pending_approval_queue())
    first = _build(tmp_path)
    previous = feed.item_state_keys(first["feed_items"])

    second = _build(tmp_path, previous=previous)

    assert second["item_count"] == 1
    assert second["new_push_candidate_count"] == 0
    assert second["new_push_candidates"] == []


def test_proof_refs_are_present(tmp_path):
    _write_json(tmp_path / "approval_request_queue.json", _pending_approval_queue())
    _write_json(
        tmp_path / "sync_health.json",
        {"mirror_status": "needs_mac_sync", "missing_expected": 1, "hash_mismatch": 0},
    )

    payload = _build(tmp_path)

    assert payload["item_count"] == 2
    for item in payload["feed_items"]:
        assert item["source_receipt_ref"]
        assert item["source_receipt_ref"] in payload["source_receipt_refs"]


def test_no_private_raw_body_text_appears(tmp_path):
    _write_json(tmp_path / "approval_request_queue.json", _pending_approval_queue())
    _write_json(
        tmp_path / "cassandra_draft_worker_readback.json",
        {
            "request": {
                "request_id": "cassandra_request:unsafe",
                "approval_required": True,
                "send_authority": False,
            },
            "readback": {
                "status": "DRAFT_READY_FOR_REVIEW",
                "operator_message": "Unsafe quoted private content: pay winship@example.test now.",
            },
            "source_candidate": {
                "body_text": "This raw source body must not be copied.",
            },
        },
    )
    task_root = tmp_path / "tasks"
    _write_task(
        task_root / "chief-cassandra-failure-20260610T205623.md",
        """title: chief-cassandra-failure-20260610T205623
scope:
- Request summary: unsafe quoted private content with winship@example.test
generated_by: chief_cassandra_failure
generated_at: 2026-06-10T20:56:23.068137
""",
    )

    rendered = feed.stable_json(_build(tmp_path, task_root)).lower()

    assert "winship@example.test" not in rendered
    assert "unsafe quoted private content" not in rendered
    assert "this raw source body" not in rendered
    assert "plain_summary" not in rendered
    assert "operator_message" not in rendered
    assert '"body_text"' not in rendered


def test_source_does_not_import_live_listener_runtime_db_network_or_model_tools():
    source = Path("watch_desk_feed.py").read_text(encoding="utf-8")
    forbidden_patterns = [
        r"^\s*import\s+cassandra_listener\b",
        r"^\s*from\s+cassandra_listener\b",
        r"^\s*import\s+sqlite3\b",
        r"^\s*import\s+subprocess\b",
        r"^\s*from\s+subprocess\b",
        r"^\s*import\s+requests\b",
        r"^\s*import\s+httpx\b",
        r"^\s*import\s+socket\b",
        r"os\.system\s*\(",
        r"subprocess\.",
        r"Popen\s*\(",
    ]
    for pattern in forbidden_patterns:
        assert re.search(pattern, source, flags=re.MULTILINE | re.IGNORECASE) is None
