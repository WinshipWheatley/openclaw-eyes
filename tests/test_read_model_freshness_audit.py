from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import read_model_freshness_audit as audit  # noqa: E402


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_audit_classifies_fresh_stale_missing_timestamp_bad_json_and_missing_file(tmp_path):
    root = tmp_path / "generated" / "read_models"
    _write_json(root / "fresh.json", {"generated_at": "2026-06-30T12:00:00Z"})
    _write_json(root / "stale.json", {"updated_at": "2026-06-01T12:00:00Z"})
    _write_json(root / "untimed.json", {"read_model_version": "v0"})
    (root / "bad.json").write_text("{bad", encoding="utf-8")

    result = audit.audit_read_models(
        ["fresh.json", "stale.json", "untimed.json", "bad.json", "missing.json"],
        read_model_root=root,
        today=date(2026, 7, 1),
        stale_after_days=14,
    )
    by_name = {item["name"]: item for item in result["items"]}

    assert by_name["fresh.json"]["freshness_status"] == "fresh"
    assert by_name["fresh.json"]["age_days"] == 1
    assert by_name["stale.json"]["freshness_status"] == "stale"
    assert by_name["stale.json"]["age_days"] == 30
    assert by_name["untimed.json"]["freshness_status"] == "missing_timestamp"
    assert by_name["bad.json"]["freshness_status"] == "bad_json"
    assert by_name["missing.json"]["freshness_status"] == "missing_file"
    assert result["summary"]["problem_count"] == 4


def test_discover_packet_read_models_includes_frontdoor_sources():
    names = audit.discover_packet_read_models()

    assert "agent_presence.json" in names
    assert "openclaw_capability_index.json" in names
