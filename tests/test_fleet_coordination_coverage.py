from __future__ import annotations

import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config" / "fleet_coordination.v2.json"


def test_registry_has_exact_six_seats_and_honest_capabilities() -> None:
    from fleet_coordination_coverage import load_registry

    registry = load_registry(REGISTRY)
    recipients = {row["seat"]: row for row in registry["recipients"]}

    assert set(recipients) == {
        "PC-Sol",
        "Mac-Sol-Desktop",
        "Mac-Sol-VSCode",
        "Mac-Fable",
        "Gemini",
        "Opus",
    }
    assert recipients["PC-Sol"]["delivery"]["thread_id"] == "019f7780-d5f8-76b0-9dde-ead4bf0735f4"
    assert recipients["PC-Sol"]["delivery"]["doorbell"] == "yes"
    assert recipients["PC-Sol"]["delivery"]["midturn"] == "no"
    assert recipients["PC-Sol"]["delivery"]["codex_home"] == "/mnt/c/Users/Open Claw/.codex"
    assert recipients["PC-Sol"]["needs_operator_kick"] is True
    assert recipients["Mac-Sol-Desktop"]["delivery"]["doorbell"] == "no"
    assert recipients["Mac-Sol-Desktop"]["needs_operator_kick"] is True
    assert recipients["Gemini"]["delivery"]["midturn"] == "unsupported"


def test_portable_path_refs_resolve_without_traversal(tmp_path: Path) -> None:
    from fleet_coordination_coverage import RegistryError, resolve_path_ref

    repo = tmp_path / "repo"
    board = tmp_path / "board"
    assert resolve_path_ref("repo:Operator/to-codex", repo_root=repo, board_root=board) == repo / "Operator/to-codex"
    assert resolve_path_ref("board:codex_mac_bridge/to-codex-mac", repo_root=repo, board_root=board) == board / "codex_mac_bridge/to-codex-mac"
    with pytest.raises(RegistryError, match="path_ref_traversal"):
        resolve_path_ref("board:../escape", repo_root=repo, board_root=board)
    with pytest.raises(RegistryError, match="path_ref_prefix"):
        resolve_path_ref("home:/tmp", repo_root=repo, board_root=board)


def test_coverage_uses_watcher_state_not_checkin_age(tmp_path: Path) -> None:
    from fleet_coordination_coverage import build_coverage, load_registry

    watcher_dir = tmp_path / "WATCHER"
    checkin_dir = tmp_path / "CHECKIN"
    watcher_dir.mkdir()
    checkin_dir.mkdir()
    (watcher_dir / "WATCHER-PC-Sol.json").write_text(
        json.dumps(
            {
                "schema_version": "openclaw_fleet_watcher_state_v2b",
                "seat": "PC-Sol",
                "monitor_status": "ready",
                "watched_lanes": ["/inbound", "/WAKE"],
                "doorbell": "yes",
                "midturn": "yes",
                "needs_operator_kick": False,
                "last_event_id": "event-1",
                "last_delivery": "delivered",
                "last_detail": "woke",
                "delivery_counts": {
                    "doorbell": 2,
                    "midturn": 1,
                    "normal": 3,
                    "urgent": 1,
                    "coalesced": 9,
                    "failures": 0,
                },
            }
        ),
        encoding="utf-8",
    )
    (checkin_dir / "CHECKIN-PC-Sol.json").write_text(
        json.dumps(
            {
                "seat": "PC-Sol",
                "status": "working",
                "last_seen": "2000-01-01T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    coverage = build_coverage(
        load_registry(REGISTRY),
        watcher_dir=watcher_dir,
        checkin_dir=checkin_dir,
    )
    rows = {row["seat"]: row for row in coverage["recipients"]}

    assert rows["PC-Sol"]["infrastructure"] == "ready"
    assert rows["PC-Sol"]["needs_operator_kick"] is True
    assert rows["PC-Sol"]["midturn"] == "no"
    assert rows["PC-Sol"]["checkin_status"] == "working"
    assert "checkin_age" not in rows["PC-Sol"]
    assert rows["PC-Sol"]["delivery_counts"]["urgent"] == 1
    assert rows["Mac-Fable"]["doorbell"] == "yes"
    assert rows["Mac-Fable"]["infrastructure"] == "missing"
    assert rows["Mac-Fable"]["needs_operator_kick"] is True
    assert rows["Gemini"]["doorbell"] == "no"
    assert rows["Gemini"]["midturn"] == "unsupported"


def test_dual_coverage_outputs_are_byte_identical(tmp_path: Path) -> None:
    from fleet_coordination_coverage import build_coverage, load_registry, write_coverage

    watcher_dir = tmp_path / "WATCHER"
    checkin_dir = tmp_path / "CHECKIN"
    watcher_dir.mkdir()
    checkin_dir.mkdir()
    payload = build_coverage(
        load_registry(REGISTRY),
        watcher_dir=watcher_dir,
        checkin_dir=checkin_dir,
    )
    repo_output = tmp_path / "repo" / "coverage.json"
    board_output = tmp_path / "board" / "coverage.json"

    write_coverage(payload, outputs=(repo_output, board_output))

    assert repo_output.read_bytes() == board_output.read_bytes()
    assert repo_output.stat().st_mode & 0o777 == 0o644


def test_coverage_preserves_blocked_pending_host_binding(tmp_path: Path) -> None:
    from fleet_coordination_coverage import build_coverage, load_registry

    watcher_dir = tmp_path / "WATCHER"
    checkin_dir = tmp_path / "CHECKIN"
    watcher_dir.mkdir()
    checkin_dir.mkdir()
    (watcher_dir / "WATCHER-PC-Sol.json").write_text(
        json.dumps(
            {
                "schema_version": "openclaw_fleet_watcher_state_v2b",
                "seat": "PC-Sol",
                "monitor_status": "ready",
                "watched_lanes": ["/inbound", "/WAKE"],
                "doorbell": "yes",
                "midturn": "blocked_pending_host_binding",
                "needs_operator_kick": True,
                "delivery_counts": {},
            }
        ),
        encoding="utf-8",
    )

    coverage = build_coverage(
        load_registry(REGISTRY),
        watcher_dir=watcher_dir,
        checkin_dir=checkin_dir,
    )
    rows = {row["seat"]: row for row in coverage["recipients"]}

    assert rows["PC-Sol"]["doorbell"] == "yes"
    assert rows["PC-Sol"]["midturn"] == "blocked_pending_host_binding"
    assert rows["PC-Sol"]["needs_operator_kick"] is True


def test_registry_rejects_duplicates_and_symlink(tmp_path: Path) -> None:
    from fleet_coordination_coverage import RegistryError, load_registry

    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    payload["recipients"].append(dict(payload["recipients"][0]))
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RegistryError, match="duplicate_seat"):
        load_registry(duplicate)
    linked = tmp_path / "linked.json"
    linked.symlink_to(REGISTRY)
    with pytest.raises(RegistryError, match="registry_not_regular"):
        load_registry(linked)
