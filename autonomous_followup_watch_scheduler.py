"""Run prepare-only client follow-up watches on a schedule."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from client_followup_watch import ClientFollowupWatchStore, DEFAULT_FOLLOWUP_DB_PATH
import st_annes_forward_tracking_workflow as st_annes_tracking


SCHEMA_VERSION = "autonomous_followup_watch_scheduler_v0"
ATTENTION_SCHEMA_VERSION = "autonomous_followup_watch_attention_v0"

ROOT = Path(__file__).resolve().parent
DEFAULT_STATE_PATH = Path("generated/system_knowledge/autonomous_followup_watch_state.json")
DEFAULT_ATTENTION_OUTBOX_PATH = Path("generated/read_models/autonomous_followup_watch_attention.json")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_ST_ANNES_SENT_RECEIPT_PATH = Path("generated/read_models/st_annes_invoice_status.json")
DEFAULT_ST_ANNES_MESSAGES_PATH = Path("generated/system_knowledge/st_annes_followup_observed_messages.json")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else ROOT / candidate


def _optional_rooted(path: str | Path | None) -> str | None:
    if path in (None, ""):
        return None
    return str(_rooted(path))


def _load_json(path: str | Path) -> dict[str, Any]:
    path = _rooted(path)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    path = _rooted(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")


def _load_messages(path: str | Path) -> list[dict[str, Any]]:
    path = _rooted(path)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if isinstance(payload, list):
        return [dict(item) for item in payload if isinstance(item, Mapping)]
    if isinstance(payload, Mapping):
        messages = payload.get("messages")
        if isinstance(messages, list):
            return [dict(item) for item in messages if isinstance(item, Mapping)]
    return []


def _load_sent_receipt(path: str | Path) -> dict[str, Any]:
    path = _rooted(path)
    payload = _load_json(path)
    if not payload:
        return {
            "ok": False,
            "proof_ref": "",
            "invoice_ref": "st_annes_invoice",
        }
    if "ok" in payload:
        return dict(payload)
    sent_at = (
        payload.get("sent_at_utc_iso")
        or payload.get("source_receipt_generated_at")
        or payload.get("generated_at")
    )
    ok = bool(
        payload.get("manual_send_out_of_band_known") is True
        or payload.get("invoice_status") == "MANUAL_SEND_OUT_OF_BAND_RECORDED"
        or payload.get("invoice_status") == "SENT"
        or payload.get("openclaw_send_performed") is True
    )
    if ok and not sent_at:
        ok = False
    return {
        "ok": ok,
        "sent_at_utc_iso": str(sent_at or ""),
        "invoice_ref": str(payload.get("invoice_ref") or payload.get("invoice_period") or "st_annes_invoice"),
        "proof_ref": str(payload.get("content_hash") or payload.get("source_receipt_path") or path),
        "invoice_status": str(payload.get("invoice_status") or ""),
        "recipient": str(payload.get("recipient") or "draper.carter@gmail.com"),
        "cc": [str(item) for item in payload.get("cc") or []],
        "subject": str(payload.get("subject") or ""),
        "provenance": str(payload.get("send_provenance") or ""),
        "operator_authorized": payload.get("operator_authorized") is True,
        "gmail_message_id": str(payload.get("gmail_message_id") or ""),
    }


def _load_state(path: str | Path, *, generated_at: str) -> dict[str, Any]:
    payload = _load_json(path)
    surfaced = payload.get("surfaced_event_ids")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "surfaced_event_ids": dict(surfaced) if isinstance(surfaced, Mapping) else {},
    }


def _write_state(path: str | Path, state: Mapping[str, Any], *, generated_at: str) -> None:
    payload = dict(state)
    payload["schema_version"] = SCHEMA_VERSION
    payload["generated_at"] = generated_at
    _write_json(path, payload)


def _safe_authority_boundary(boundary: Mapping[str, Any] | None) -> dict[str, Any]:
    safe = dict(boundary or {})
    safe.update(
        {
            "send_performed": False,
            "email_send_performed": False,
            "gmail_send_performed": False,
            "telegram_send_performed": False,
            "ledger_mutation_performed": False,
            "ledger_post_performed": False,
            "draft_only": True,
            "send_hold_required": True,
            "guardian_required": True,
        }
    )
    return safe


def _st_annes_followup_event(
    tracking_state: Mapping[str, Any],
    *,
    generated_at: str,
) -> dict[str, Any] | None:
    follow_up = tracking_state.get("follow_up")
    if not isinstance(follow_up, Mapping) or follow_up.get("status") != "FOLLOW_UP_DUE":
        return None
    proposal = follow_up.get("proposal")
    if not isinstance(proposal, Mapping):
        return None
    due_at = str(follow_up.get("due_at_utc_iso") or "")
    step = str(follow_up.get("step") or "")
    invoice_ref = str(tracking_state.get("invoice_ref") or "st_annes_invoice")
    event_id = f"autonomous_followup_watch:st_annes:{invoice_ref}:{step}:{due_at}"
    return {
        "event_id": event_id,
        "event_kind": "st_annes_forward_tracking_followup",
        "generated_at": generated_at,
        "target_surface": "operator_attention_lane",
        "headline": "St. Anne's follow-up is due",
        "operator_message": (
            "St. Anne's follow-up is due from the Draper to Glenn tracking workflow. "
            "A draft is prepared for review; send still requires Guardian/operator approval."
        ),
        "workflow_ref": str(tracking_state.get("workflow_ref") or st_annes_tracking.WORKFLOW_REF),
        "client_ref": "st_annes",
        "invoice_ref": invoice_ref,
        "followup_step": step,
        "due_at_utc_iso": due_at,
        "proposal": dict(proposal),
        "authority_boundary": _safe_authority_boundary(proposal.get("authority_boundary") if isinstance(proposal, Mapping) else {}),
        "machine_proof": {
            "st_annes_forward_tracking_workflow_used": True,
            "prepare_only": True,
            "email_send_performed": False,
            "gmail_send_performed": False,
            "telegram_send_performed": False,
            "ledger_mutation_performed": False,
            "business_action_performed": False,
        },
    }


def _st_annes_monitoring_event(
    tracking_state: Mapping[str, Any],
    *,
    generated_at: str,
) -> dict[str, Any] | None:
    monitoring = tracking_state.get("monitoring")
    if (
        tracking_state.get("workflow_stage") != "awaiting_forward_to_glenn"
        or not isinstance(monitoring, Mapping)
        or monitoring.get("status") != "ARMED"
    ):
        return None
    invoice_ref = str(tracking_state.get("invoice_ref") or "st_annes_invoice")
    sent_at = str(tracking_state.get("sent_at_utc_iso") or "")
    return {
        "event_id": f"autonomous_followup_watch:st_annes:armed:{invoice_ref}:{sent_at}",
        "event_kind": "st_annes_receivable_monitor_armed",
        "generated_at": generated_at,
        "target_surface": "operator_attention_lane",
        "headline": "St. Anne's forward monitor armed",
        "operator_message": (
            "The June invoice is recorded SENT to Draper. Monitoring is armed for "
            "Draper's forward to Glenn; nothing downstream is recorded yet."
        ),
        "workflow_ref": str(
            tracking_state.get("workflow_ref") or st_annes_tracking.WORKFLOW_REF
        ),
        "client_ref": "st_annes",
        "invoice_ref": invoice_ref,
        "operator_surface_flag": str(
            tracking_state.get("operator_surface_flag")
            or "AWAITING_DRAPER_FORWARD_TO_GLENN"
        ),
        "due_at_utc_iso": str(monitoring.get("due_at_utc_iso") or ""),
        "payment_check_cadence": dict(
            tracking_state.get("payment_check_cadence") or {}
        ),
        "authority_boundary": _safe_authority_boundary({}),
        "machine_proof": {
            "monitoring_only": True,
            "local_observed_messages_only": True,
            "email_send_performed": False,
            "gmail_send_performed": False,
            "telegram_send_performed": False,
            "ledger_mutation_performed": False,
            "paid_marking_performed": False,
            "business_action_performed": False,
        },
    }


def _client_followup_event(proposal: Mapping[str, Any], *, generated_at: str) -> dict[str, Any]:
    proposal_id = str(proposal.get("proposal_id") or proposal.get("watch_id") or "")
    client_name = str(proposal.get("client_name") or proposal.get("client_ref") or "client")
    return {
        "event_id": f"autonomous_followup_watch:client_followup:{proposal_id}",
        "event_kind": "client_followup_watch_proposal",
        "generated_at": generated_at,
        "target_surface": "operator_attention_lane",
        "headline": f"{client_name} follow-up is due",
        "operator_message": (
            "A client follow-up is due from the follow-up watch store. "
            "A draft is prepared for review; send still requires Guardian/operator approval."
        ),
        "client_ref": str(proposal.get("client_ref") or ""),
        "watch_id": str(proposal.get("watch_id") or ""),
        "proposal_id": proposal_id,
        "due_at_utc_iso": str(proposal.get("due_at_utc_iso") or ""),
        "draft": dict(proposal.get("draft") or {}),
        "approval_request": dict(proposal.get("approval_request") or {}),
        "authority_boundary": _safe_authority_boundary(proposal.get("authority_boundary") if isinstance(proposal, Mapping) else {}),
        "machine_proof": {
            "client_followup_watch_used": True,
            "prepare_only": True,
            "email_send_performed": False,
            "gmail_send_performed": False,
            "telegram_send_performed": False,
            "ledger_mutation_performed": False,
            "business_action_performed": False,
        },
    }


def _upsert_attention_events(
    path: str | Path,
    events: Sequence[Mapping[str, Any]],
    *,
    generated_at: str,
) -> None:
    payload = _load_json(path)
    current = payload.get("events") if isinstance(payload.get("events"), list) else []
    by_id = {
        str(row.get("event_id")): dict(row)
        for row in current
        if isinstance(row, Mapping) and row.get("event_id")
    }
    for event in events:
        by_id[str(event["event_id"])] = dict(event)
    ordered = sorted(
        by_id.values(),
        key=lambda event: (str(event.get("event_kind") or ""), str(event.get("event_id") or "")),
    )
    _write_json(
        path,
        {
            "schema_version": ATTENTION_SCHEMA_VERSION,
            "read_model_id": "autonomous_followup_watch_attention",
            "generated_at": generated_at,
            "status": "AUTONOMOUS_FOLLOWUP_WATCH_ATTENTION_READY" if ordered else "IDLE",
            "events": ordered,
            "machine_proof": {
                "operator_attention_lane_surface": True,
                "prepare_only": True,
                "email_send_performed": False,
                "gmail_send_performed": False,
                "telegram_send_performed": False,
                "ledger_mutation_performed": False,
                "unsafe_true_grants_absent": True,
            },
        },
    )


def _append_if_new(
    *,
    event: Mapping[str, Any],
    state: dict[str, Any],
    prepared: list[dict[str, Any]],
    skipped: list[dict[str, Any]],
    generated_at: str,
) -> None:
    surfaced = state["surfaced_event_ids"]
    event_id = str(event["event_id"])
    if event_id in surfaced:
        skipped.append(
            {
                "event_id": event_id,
                "event_kind": str(event.get("event_kind") or ""),
                "reason": "already_surfaced",
            }
        )
        return
    surfaced[event_id] = {
        "event_kind": str(event.get("event_kind") or ""),
        "surfaced_at": generated_at,
    }
    prepared.append(dict(event))


def run_once(
    *,
    now_utc_iso: str | None = None,
    st_annes_sent_receipt_path: str | Path = DEFAULT_ST_ANNES_SENT_RECEIPT_PATH,
    st_annes_messages_path: str | Path = DEFAULT_ST_ANNES_MESSAGES_PATH,
    contacts_db_path: str | Path | None = None,
    followup_db_path: str | Path = DEFAULT_FOLLOWUP_DB_PATH,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    attention_outbox_path: str | Path = DEFAULT_ATTENTION_OUTBOX_PATH,
    state_path: str | Path = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    generated_at = now_utc_iso or utc_now()
    state = _load_state(state_path, generated_at=generated_at)
    prepared: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    export_root_path = _rooted(export_root)
    previous_state = _load_json(export_root_path / st_annes_tracking.JSON_EXPORT_NAME)
    sent_receipt = _load_sent_receipt(st_annes_sent_receipt_path)
    messages = _load_messages(st_annes_messages_path)
    tracking_state = st_annes_tracking.advance_st_annes_receivable_state(
        sent_receipt=sent_receipt,
        messages=messages,
        contacts_db_path=_optional_rooted(contacts_db_path),
        generated_at_utc_iso=generated_at,
        previous_state=previous_state,
    )
    export_result = st_annes_tracking.export_st_annes_receivable_state(
        tracking_state,
        export_root=export_root_path,
    )
    st_annes_event = _st_annes_followup_event(tracking_state, generated_at=generated_at)
    if st_annes_event is not None:
        _append_if_new(
            event=st_annes_event,
            state=state,
            prepared=prepared,
            skipped=skipped,
            generated_at=generated_at,
        )

    followup_store = ClientFollowupWatchStore(str(_rooted(followup_db_path)))
    armed_watch: dict[str, Any] = {}
    if tracking_state.get("sent") is True:
        armed_watch = followup_store.add_watch(
            client_ref="st_annes",
            client_name="St. Anne's",
            recipient=str(
                tracking_state.get("recipient") or "draper.carter@gmail.com"
            ),
            subject=str(
                tracking_state.get("subject")
                or f"Invoice {tracking_state.get('invoice_ref') or 'st_annes_invoice'}"
            ),
            sent_at_utc_iso=str(tracking_state.get("sent_at_utc_iso") or ""),
            invoice_ref=str(
                tracking_state.get("invoice_ref") or "st_annes_invoice"
            ),
            days_without_reply=st_annes_tracking.FOLLOWUP_CADENCE_DAYS,
            created_at_utc_iso=generated_at,
        )
        forward_proof = tracking_state.get("forward_proof")
        if isinstance(forward_proof, Mapping):
            armed_watch = followup_store.record_reply_seen(
                str(armed_watch["watch_id"]),
                reply_seen_at_utc_iso=str(
                    forward_proof.get("received_at_utc_iso") or generated_at
                ),
                reply_ref=str(forward_proof.get("message_id") or ""),
            )
        monitoring_event = _st_annes_monitoring_event(
            tracking_state,
            generated_at=generated_at,
        )
        if monitoring_event is not None:
            _append_if_new(
                event=monitoring_event,
                state=state,
                prepared=prepared,
                skipped=skipped,
                generated_at=generated_at,
            )
    due_proposals = followup_store.due_followup_proposals(generated_at)
    for proposal in due_proposals:
        _append_if_new(
            event=_client_followup_event(proposal, generated_at=generated_at),
            state=state,
            prepared=prepared,
            skipped=skipped,
            generated_at=generated_at,
        )

    if prepared:
        _upsert_attention_events(attention_outbox_path, prepared, generated_at=generated_at)
    _write_state(state_path, state, generated_at=generated_at)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "PREPARED" if prepared else "IDLE",
        "prepared": prepared,
        "skipped": skipped,
        "st_annes_tracking": {
            "module_used": True,
            "state": tracking_state,
            "read_model_path": export_result.read_model_path,
            "observed_message_count": len(messages),
        },
        "client_followup_watch": {
            "module_used": True,
            "db_path": str(_rooted(followup_db_path)),
            "armed_watch": armed_watch,
            "due_proposals": due_proposals,
            "due_proposal_count": len(due_proposals),
        },
        "attention_outbox_path": str(_rooted(attention_outbox_path)),
        "state_path": str(_rooted(state_path)),
        "machine_proof": {
            "st_annes_forward_tracking_workflow_used": True,
            "client_followup_watch_used": True,
            "followup_watch_armed": bool(armed_watch),
            "prepare_only": True,
            "local_observed_messages_only": True,
            "gmail_api_called": False,
            "gmail_body_read_performed": False,
            "email_send_performed": False,
            "gmail_send_performed": False,
            "telegram_send_performed": False,
            "ledger_mutation_performed": False,
            "ledger_posting_performed": False,
            "paid_marking_performed": False,
            "business_action_performed": False,
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Run one prepare-only follow-up watch pass.")
    parser.add_argument("--now-utc-iso")
    parser.add_argument("--st-annes-sent-receipt-path", default=str(DEFAULT_ST_ANNES_SENT_RECEIPT_PATH))
    parser.add_argument("--st-annes-messages-path", default=str(DEFAULT_ST_ANNES_MESSAGES_PATH))
    parser.add_argument("--contacts-db-path")
    parser.add_argument("--followup-db-path", default=str(DEFAULT_FOLLOWUP_DB_PATH))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--attention-outbox", default=str(DEFAULT_ATTENTION_OUTBOX_PATH))
    parser.add_argument("--state-path", default=str(DEFAULT_STATE_PATH))
    args = parser.parse_args(argv)
    if not args.once:
        parser.error("autonomous follow-up watch only supports --once; use the systemd timer for scheduling")
    result = run_once(
        now_utc_iso=args.now_utc_iso,
        st_annes_sent_receipt_path=args.st_annes_sent_receipt_path,
        st_annes_messages_path=args.st_annes_messages_path,
        contacts_db_path=args.contacts_db_path,
        followup_db_path=args.followup_db_path,
        export_root=args.export_root,
        attention_outbox_path=args.attention_outbox,
        state_path=args.state_path,
    )
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
