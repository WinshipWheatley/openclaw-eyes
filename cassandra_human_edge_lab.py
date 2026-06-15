"""Cassandra human-language edge lab.

This module runs local, test-marked conversation probes against Cassandra's
deterministic rails. It catalogs conversation source locations without ingesting
raw log bodies, then runs messy human-language scenarios through safe test
surfaces. It never calls Gmail, Calendar, brokers, live models, Telegram, or
external APIs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import cassandra_guided_review as guided_review
import global_run_mode_context
import operator_conversation_router


ROOT = Path(__file__).resolve().parent
DEFAULT_LAB_ROOT = Path("/tmp/openclaw-mission-control/human_edge_lab")
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "cassandra_human_edge_lab_v0"
READ_MODEL_ID = "cassandra_human_edge_lab"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
TEST_MARKER = global_run_mode_context.TEST_MARKER

AUTHORITY_BOUNDARY = {
    "raw_log_body_ingested": False,
    "live_model_called": False,
    "telegram_send_performed": False,
    "gmail_called": False,
    "email_sent": False,
    "calendar_called": False,
    "calendar_api_called": False,
    "calendar_event_created": False,
    "calendar_event_deleted": False,
    "external_api_called": False,
    "confirmed_reference_data_created": False,
    "hydration_performed": False,
    "production_write_performed": False,
}

CONVERSATION_SOURCE_CANDIDATES = (
    (Path("/mnt/c/OpenClaw/logs/cassandra_conversations.jsonl"), "raw_cassandra_conversation_log", "raw_debug_log_catalog_only"),
    (Path("/mnt/c/OpenClaw/logs/cassandra_listener.out"), "cassandra_listener_runtime_log", "runtime_status_catalog_only"),
    (Path("/mnt/c/OpenClaw/logs/cassandra_model_routes.jsonl"), "cassandra_model_route_log", "route_metadata_catalog_only"),
    (Path("/mnt/c/OpenClaw/logs/cassandra_correspondence.jsonl"), "cassandra_correspondence_log", "correspondence_metadata_catalog_only"),
    (Path("generated/read_models/operator_conversation_journal.json"), "operator_conversation_journal_read_model", "safe_summary_read_model"),
    (Path("generated/system_knowledge/operator_conversation_journal.sqlite"), "operator_conversation_journal_sqlite", "safe_summary_sqlite"),
    (Path("generated/read_models/guided_review_sessions.json"), "guided_review_sessions_read_model", "safe_summary_read_model"),
)


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def _short_hash(*parts: object, length: int = 16) -> str:
    joined = "\0".join(str(part) for part in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:length]


def _write_json(path: Path, payload: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")
    return path


def _write_data_room_promotion_fixture(lab_root: Path, *, generated_at: str) -> Path:
    """Write the smallest clean-checkout fixture needed for the edge lab."""
    return _write_json(
        lab_root / "openclaw_data_room_promotion_review_v0.json",
        {
            "schema_version": "openclaw_data_room_promotion_review_v0",
            "created_at_utc": generated_at,
            "authoritative": False,
            "safe_to_import_as_provisional": True,
            "source_artifacts": ["cassandra_human_edge_lab_fixture"],
            "review_status": "test_fixture_needs_winship_review",
            "safety_flags": dict(AUTHORITY_BOUNDARY),
            "review_records": [
                {
                    "record_id": "payment_privacy:trusted_clients",
                    "review_category": "policy_decision",
                    "provisional_fact": (
                        "Payment options can be easier for trusted clients, but private "
                        "bank details and private addresses must not be exposed to strangers."
                    ),
                    "proposed_promoted_value": (
                        "Should trusted clients get easier payment options while new clients "
                        "stay payment-privacy gated?"
                    ),
                    "recommended_action": "confirm",
                    "risk_if_wrong": "Private payment or address details could be exposed too broadly.",
                    "authoritative": False,
                    "promotion_requires_winship_confirmation": True,
                    "confidence": "test_fixture",
                    "review_status": "operator_review_required",
                }
            ],
        },
    )


def _reset_owned_lab_path(path: Path) -> None:
    allowed_names = {"data_room", "data_room_read_models", "router"}
    resolved = path.resolve()
    if path.name not in allowed_names or resolved == ROOT or resolved.parent == ROOT:
        raise ValueError(f"refusing_to_reset_non_lab_path:{path}")
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _load_latest_guided_review_session(review_root: Path) -> tuple[Path, dict[str, Any]]:
    active_index = review_root / "data_room_guided_review_active_session.json"
    if active_index.is_file():
        active = json.loads(active_index.read_text(encoding="utf-8"))
        session_path = Path(str(active.get("session_path") or ""))
        if session_path.is_file():
            return session_path, json.loads(session_path.read_text(encoding="utf-8"))
    session_paths = [
        path
        for path in review_root.glob("data_room_guided_review_session_*.json")
        if path.is_file() and not path.name.endswith("_OPERATOR.md")
    ]
    if not session_paths:
        return Path(""), {}
    session_path = max(session_paths, key=lambda path: path.stat().st_mtime_ns)
    return session_path, json.loads(session_path.read_text(encoding="utf-8"))


def _line_count(path: Path) -> int:
    if not path.exists() or not path.is_file():
        return 0
    try:
        with path.open("rb") as handle:
            return sum(1 for _ in handle)
    except OSError:
        return 0


def _source_record(path: Path, source_kind: str, privacy_posture: str) -> dict[str, Any]:
    rooted = _rooted(path)
    exists = rooted.exists()
    stat = rooted.stat() if exists and rooted.is_file() else None
    return {
        "schema_version": "CASSANDRA_CONVERSATION_SOURCE_CATALOG_ITEM_V0",
        "source_id": f"conversation_source:{_short_hash(rooted.as_posix(), source_kind)}",
        "source_kind": source_kind,
        "path": rooted.as_posix(),
        "exists": exists,
        "size_bytes": int(stat.st_size) if stat else 0,
        "line_count": _line_count(rooted),
        "privacy_posture": privacy_posture,
        "raw_content_sampled": False,
        "raw_body_ingested": False,
        "usable_for_edge_tests": privacy_posture in {"safe_summary_read_model", "safe_summary_sqlite", "route_metadata_catalog_only"},
        "test_marker": TEST_MARKER,
    }


def discover_cassandra_conversation_sources(
    candidates: Sequence[tuple[Path, str, str]] = CONVERSATION_SOURCE_CANDIDATES,
) -> list[dict[str, Any]]:
    """Catalog conversation sources without reading raw message bodies."""

    return [_source_record(path, source_kind, privacy_posture) for path, source_kind, privacy_posture in candidates]


def _test_run_mode_context(*, generated_at: str, scope_ref: str) -> dict[str, Any]:
    state = global_run_mode_context.build_run_mode_state(
        run_mode=global_run_mode_context.TEST_DRY_RUN,
        scope={
            "scope": "session",
            "target_world_ref": "human_edge_lab",
            "target_thread_ref": scope_ref,
            "target_project_ref": "cassandra_human_edge_lab",
        },
        generated_at=generated_at,
    )
    return global_run_mode_context.context_from_state(state, source="cassandra_human_edge_lab", generated_at=generated_at)


def _unsafe_true_paths(value: Any, path: str = "$") -> list[str]:
    unsafe = {
        "raw_log_body_ingested",
        "live_model_called",
        "telegram_send_performed",
        "gmail_called",
        "email_sent",
        "calendar_called",
        "calendar_api_called",
        "calendar_event_created",
        "calendar_event_deleted",
        "external_api_called",
        "confirmed_reference_data_created",
        "hydration_performed",
        "production_write_performed",
        "external_authority",
        "gmail_access_performed",
        "browser_access_performed",
        "coupa_access_performed",
        "portal_submit_performed",
        "ledger_mutation_performed",
        "paid_marking_performed",
        "workbook_mutation_performed",
        "pdf_export_performed",
    }
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in unsafe and child is True:
                found.append(child_path)
            found.extend(_unsafe_true_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_unsafe_true_paths(child, f"{path}[{index}]"))
    return found


def run_data_room_human_edge_scenario(
    *,
    lab_root: str | Path = DEFAULT_LAB_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    lab_base = _rooted(lab_root)
    root = lab_base / "data_room"
    read_root = lab_base / "data_room_read_models"
    promotion_review_path = _write_data_room_promotion_fixture(lab_base, generated_at=generated_at)
    _reset_owned_lab_path(root)
    _reset_owned_lab_path(read_root)
    turns = [
        ("Cassandra, go over the Data Room.", "2026-06-13T15:00:00+00:00"),
        ("I don't know what that means. Explain it like I'm five.", "2026-06-13T15:01:00+00:00"),
        ("What do you recommend and why?", "2026-06-13T15:02:00+00:00"),
        (
            "Let me ramble for a second: I want trusted clients to have easy payment options, "
            "but strangers should not see bank details or my private address.",
            "2026-06-13T15:03:00+00:00",
        ),
        ("yes", "2026-06-13T15:04:00+00:00"),
        ("I got paid $900 from Live Arts MD.", "2026-06-13T15:05:00+00:00"),
        ("What does invoice numbering mean here?", "2026-06-13T15:06:00+00:00"),
        ("skip", "2026-06-13T15:07:00+00:00"),
        ("Sometimes yes for trusted clients, no for new clients.", "2026-06-13T15:08:00+00:00"),
        ("no", "2026-06-13T15:09:00+00:00"),
    ]
    responses: list[dict[str, Any]] = []
    for text, timestamp in turns:
        response = guided_review.process_guided_review_message(
            text,
            surface="telegram_dryrun",
            review_root=root,
            read_model_root=read_root,
            promotion_review_path=promotion_review_path,
            generated_at_utc=timestamp,
        )
        responses.append(
            {
                "user_turn_hash": "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "redacted_user_excerpt": text[:160],
                "reply_text": (response or {}).get("reply_text"),
                "status": (response or {}).get("status"),
                "run_mode": (response or {}).get("run_mode"),
                "test_marker": (response or {}).get("test_marker"),
                "answer_recorded_count": ((response or {}).get("progress") or {}).get("answered"),
                "detoured_out_of_guided_review": response is None,
            }
        )
    session_path, session = _load_latest_guided_review_session(root)
    read_model_path = read_root / guided_review.READ_MODEL_NAME
    summary = {
        "schema_version": "CASSANDRA_HUMAN_EDGE_DATA_ROOM_SCENARIO_V0",
        "scenario_id": "data_room_messy_human_form_fill",
        "generated_at": generated_at,
        "run_mode": session.get("run_mode"),
        "test_marker": session.get("test_marker"),
        "test_artifact": bool(session.get("test_artifact")),
        "review_root": root.as_posix(),
        "read_model_path": read_model_path.as_posix(),
        "session_path": session_path.as_posix() if session_path else "",
        "answer_count": len(session.get("answer_records") or []),
        "pending_interaction_empty": not bool(session.get("pending_interaction")),
        "coach_interaction_commands": [item.get("command") for item in session.get("coach_interactions") or []],
        "responses": responses,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    summary["unsafe_true_paths"] = _unsafe_true_paths(summary)
    _write_json(root / "human_edge_transcript_summary.json", summary)
    return summary


def _router_request(text: str, *, world: str, thread: str, request_id: str, run_mode_context: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "request_type": operator_conversation_router.REQUEST_TYPE,
        "controller_event_type": "chat_goal",
        "operator_text": text,
        "current_world_ref": world,
        "current_thread_ref": thread,
        "selected_card_id": "dynamic_card.cassandra_human_edge_lab",
        "selected_action_id": "",
        "authority_boundary": dict(operator_conversation_router.AUTHORITY_BOUNDARY),
        "authority_requested": [],
        "run_mode_context": dict(run_mode_context),
    }


def run_router_human_edge_scenario(
    *,
    lab_root: str | Path = DEFAULT_LAB_ROOT,
    proof_read_model_root: str | Path = operator_conversation_router.DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    root = _rooted(lab_root) / "router"
    _reset_owned_lab_path(root)
    proof_read_root = _rooted(proof_read_model_root)
    sqlite_path = root / "router_edge.sqlite"
    context = _test_run_mode_context(generated_at=generated_at, scope_ref="conversation_router")
    cases = [
        (
            "coworker_help",
            "I don't know what to do here. Can you talk to me like a coworker and tell me the next safe move?",
            "finance",
            "capital_hilton",
        ),
        (
            "dry_run_email",
            "Send a dry-run email to winshiplive@gmail.com and label it as an OpenClaw test.",
            "finance",
            "capital_hilton",
        ),
        (
            "calendar_test_gap",
            "Can you make a test Google Calendar event for tomorrow and delete it after I review?",
            "ops",
            "calendar_tests",
        ),
        (
            "blocked_send_followup",
            "Can you send the Capital Hilton follow-up?",
            "business_development",
            "capital_hilton",
        ),
    ]
    results: list[dict[str, Any]] = []
    for case_id, text, world, thread in cases:
        request = _router_request(
            text,
            world=world,
            thread=thread,
            request_id=f"human_edge_lab_{case_id}",
            run_mode_context=context,
        )
        result = operator_conversation_router.route_conversation_text(
            request,
            read_model_root=proof_read_root,
            sqlite_path=sqlite_path,
            generated_at=generated_at,
        )
        display = result.get("operator_display") if isinstance(result.get("operator_display"), Mapping) else {}
        receipt = result.get("test_effect_receipt") if isinstance(result.get("test_effect_receipt"), Mapping) else {}
        results.append(
            {
                "case_id": case_id,
                "operator_text_hash": "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "redacted_operator_excerpt": text[:180],
                "route_status": result.get("route_status"),
                "backend_route": result.get("backend_route"),
                "headline": display.get("headline"),
                "plain_summary": display.get("plain_summary"),
                "next_safe_action": display.get("next_safe_action"),
                "test_effect_status": receipt.get("status", ""),
                "test_effect_actual_target": receipt.get("actual_target", ""),
                "test_marker": receipt.get("test_marker") or context.get("test_marker"),
                "external_effect": bool(receipt.get("external_effect")) if receipt else False,
                "email_send_performed": bool(receipt.get("email_send_performed")) if receipt else False,
                "calendar_api_called": bool(receipt.get("calendar_api_called")) if receipt else False,
                "calendar_event_created": bool(receipt.get("calendar_event_created")) if receipt else False,
                "calendar_event_deleted": bool(receipt.get("calendar_event_deleted")) if receipt else False,
                "unsafe_true_paths": _unsafe_true_paths(result),
            }
        )
    calendar_case = next((item for item in results if item["case_id"] == "calendar_test_gap"), {})
    calendar_adapter_status = (
        "dry_run_calendar_receipt_recorded_no_calendar_call_performed"
        if calendar_case.get("test_effect_status") == "DRY_RUN_RECORDED"
        else "not_configured_no_calendar_call_performed"
    )
    summary = {
        "schema_version": "CASSANDRA_HUMAN_EDGE_ROUTER_SCENARIO_V0",
        "scenario_id": "conversation_router_messy_human_effect_boundaries",
        "generated_at": generated_at,
        "run_mode": context["run_mode"],
        "test_marker": context["test_marker"],
        "router_root": root.as_posix(),
        "proof_read_model_root": proof_read_root.as_posix(),
        "sqlite_path": sqlite_path.as_posix(),
        "results": results,
        "calendar_test_adapter_status": calendar_adapter_status,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    summary["unsafe_true_paths"] = _unsafe_true_paths(summary)
    _write_json(root / "router_human_edge_summary.json", summary)
    return summary


def run_human_edge_lab(
    *,
    lab_root: str | Path = DEFAULT_LAB_ROOT,
    export_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    lab_root = _rooted(lab_root)
    source_catalog = discover_cassandra_conversation_sources()
    data_room = run_data_room_human_edge_scenario(lab_root=lab_root, generated_at=generated_at)
    router = run_router_human_edge_scenario(lab_root=lab_root, generated_at=generated_at)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "status": "CASSANDRA_HUMAN_EDGE_LAB_READY",
        "run_mode": global_run_mode_context.TEST_DRY_RUN,
        "test_marker": TEST_MARKER,
        "source_catalog": source_catalog,
        "data_room_scenario_ref": data_room["review_root"] + "/human_edge_transcript_summary.json",
        "router_scenario_ref": router["router_root"] + "/router_human_edge_summary.json",
        "data_room_summary": {
            "answer_count": data_room["answer_count"],
            "pending_interaction_empty": data_room["pending_interaction_empty"],
            "unsafe_true_paths": data_room["unsafe_true_paths"],
        },
        "router_summary": {
            "case_count": len(router["results"]),
            "calendar_test_adapter_status": router["calendar_test_adapter_status"],
            "unsafe_true_paths": router["unsafe_true_paths"],
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "safety_confirmation": {
            "raw_logs_cataloged_not_ingested": all(not source["raw_body_ingested"] for source in source_catalog),
            "no_external_actions": not _unsafe_true_paths({"data_room": data_room, "router": router}),
            "all_outputs_test_marked": data_room.get("test_marker") == TEST_MARKER and router.get("test_marker") == TEST_MARKER,
        },
    }
    payload["unsafe_true_paths"] = _unsafe_true_paths(payload)
    lab_summary_path = _write_json(lab_root / "cassandra_human_edge_lab_summary.json", payload)
    export_root = _rooted(export_root)
    export_path = _write_json(export_root / JSON_EXPORT_NAME, payload)
    payload["lab_summary_path"] = lab_summary_path.as_posix()
    payload["read_model_path"] = export_path.as_posix()
    _write_json(lab_summary_path, payload)
    _write_json(export_path, payload)
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run local Cassandra human-language edge lab.")
    parser.add_argument("--lab-root", default=str(DEFAULT_LAB_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--generated-at", default="")
    args = parser.parse_args(list(argv) if argv is not None else None)
    payload = run_human_edge_lab(
        lab_root=args.lab_root,
        export_root=args.export_root,
        generated_at=args.generated_at or None,
    )
    print(stable_json({"status": payload["status"], "lab_summary_path": payload["lab_summary_path"], "read_model_path": payload["read_model_path"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
