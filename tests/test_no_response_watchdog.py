from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import hermes_observer
import no_response_watchdog as watchdog


NOW = datetime(2026, 6, 29, 12, 0, tzinfo=timezone.utc)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _request(inbox: Path, name: str, *, minutes_old: int = 10, lane: str = "telegram_pc_maestro_listener") -> Path:
    path = inbox / name
    _write_json(
        path,
        {
            "created_at": (NOW - timedelta(minutes=minutes_old)).isoformat(),
            "lane": lane,
            "request_id": "maestro_telegram_900_deadbeef",
            "source_request_id": "maestro_telegram_900_deadbeef",
            "operator_message": "hello?",
        },
    )
    return path


def test_old_unanswered_request_emits_agent_suggestion(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    response_dir = tmp_path / "to_mac"
    _request(inbox, "mission_control_operator_instruction_request_maestro_telegram_900_deadbeef.json")

    suggestions = watchdog.no_response_observer(
        inbox=inbox,
        response_dir=response_dir,
        now=NOW,
        timeout_s=180,
        systemctl_fn=lambda service: "inactive",
    )

    assert len(suggestions) == 1
    suggestion = suggestions[0]
    assert suggestion["id"] == "no_response_maestro"
    assert "1 requests to maestro" in suggestion["evidence"]
    assert "is-active(openclaw-request-response.service)=inactive" in suggestion["evidence"]
    assert suggestion["severity"] == "high"
    assert suggestion["source"] == "no_response_watchdog"


def test_matching_response_suppresses_suggestion(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    response_dir = tmp_path / "to_mac"
    request_path = _request(inbox, "mission_control_operator_instruction_request_maestro_telegram_901_aaa.json")
    _write_json(
        response_dir / "openclaw_response_for_mac_maestro_telegram_901_aaa.json",
        {
            "source_request_filename": request_path.name,
            "source_request_id": "maestro_telegram_901_aaa",
            "internal_status": "FAILED_WITH_REASON",
            "why_it_happened": "fixture failure response still counts as a reply",
        },
    )

    assert watchdog.no_response_observer(inbox=inbox, response_dir=response_dir, now=NOW) == []


def test_processing_marker_suppresses_suggestion(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    response_dir = tmp_path / "to_mac"
    request_path = _request(inbox, "mission_control_operator_instruction_request_maestro_telegram_902_bbb.json")
    _write_json(
        response_dir / "openclaw_processing_for_mac_maestro_telegram_902_bbb.json",
        {
            "source_request_filename": request_path.name,
            "source_request_id": "maestro_telegram_902_bbb",
            "terminal": False,
        },
    )

    assert watchdog.no_response_observer(inbox=inbox, response_dir=response_dir, now=NOW) == []


def test_watchdog_suggestion_routes_through_existing_hermes_loop(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    response_dir = tmp_path / "to_mac"
    _request(inbox, "mission_control_operator_instruction_request_maestro_telegram_903_ccc.json")
    filed: list[str] = []

    result = hermes_observer.run_hermes_fleet_loop(
        observers=[
            lambda: watchdog.no_response_observer(
                inbox=inbox,
                response_dir=response_dir,
                now=NOW,
                timeout_s=180,
                systemctl_fn=lambda service: "inactive",
            )
        ],
        file_fn=lambda suggestion: filed.append(suggestion["id"]) or {"task_id": "task_no_response"},
        notify_fn=lambda routed: None,
        handoff_fn=lambda suggestion, receipt: None,
        allowed_targets=frozenset({"chief", "guardian"}),
        state_store=tmp_path / "gap_state.json",
    )

    assert result["routed_to_chief"] == ["no_response_maestro"]
    assert filed == ["no_response_maestro"]


def test_unknown_package_profile_is_registered() -> None:
    from self_improvement_request import compile_self_improvement_package

    package = compile_self_improvement_package(
        {
            "id": "no_response_maestro",
            "build_goal": "Investigate and repair no-response handling for Maestro lane requests.",
            "evidence": "fixture",
        },
        agent="hermes",
    )

    assert "no_response_watchdog.py" in package["allowed_files"]
    assert any("tests/test_no_response_watchdog.py" in item for item in package["tests_to_run"])
