"""Prepare due client invoice review packets without sending anything."""

from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import temporal_recurrence_registry
import workflow_package_queue
import workflow_package_request_consumer
from receivable_temporal_scoping import ClientPaidThroughStore, paid_up_state_for_client


SCHEMA_VERSION = "autonomous_invoice_prep_scheduler_v0"
ATTENTION_SCHEMA_VERSION = "autonomous_invoice_prep_attention_v0"

ROOT = Path(__file__).resolve().parent
DEFAULT_STATE_PATH = Path("generated/system_knowledge/autonomous_invoice_prep_state.json")
DEFAULT_ATTENTION_OUTBOX_PATH = Path("generated/read_models/autonomous_invoice_prep_attention.json")
DEFAULT_QUEUE_SQLITE_PATH = workflow_package_queue.DEFAULT_SQLITE_PATH
DEFAULT_PAID_THROUGH_STORE_PATH = Path(
    os.environ.get(
        "OPENCLAW_CLIENT_PAID_THROUGH_STORE",
        "generated/system_knowledge/client_paid_through.sqlite",
    )
)


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else ROOT / candidate


def _coerce_date(value: date | datetime | str | None) -> date:
    if value is None:
        return datetime.now(timezone.utc).date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)).date()


def _load_json(path: Path) -> dict[str, Any]:
    path = _rooted(path)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path = _rooted(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")


def _active_invoice_models() -> list[temporal_recurrence_registry.RecurrenceModel]:
    registry = temporal_recurrence_registry.ClientRecurrenceRegistry()
    models: list[temporal_recurrence_registry.RecurrenceModel] = []
    for client_ref in sorted(temporal_recurrence_registry.DEFAULT_RECURRENCE_MODELS):
        model = registry.get(client_ref)
        if model is not None and model.active and model.domain == "invoice":
            models.append(model)
    return models


def _authority_boundary_all_false() -> dict[str, bool]:
    keys = set(workflow_package_request_consumer.AUTHORITY_FALSE_FIELDS)
    keys.update(workflow_package_queue.AUTHORITY_BOUNDARY_DEFAULT)
    return {key: False for key in sorted(keys)}


CLIENT_DISPLAY_NAMES = {
    "st_annes": "St. Anne's",
    "live_arts_md": "Live Arts MD",
}


def _invoice_review_request(*, client_ref: str, next_due: date, generated_at: str) -> dict[str, Any]:
    display_name = CLIENT_DISPLAY_NAMES[client_ref]
    source_text = (
        f"Autonomous invoice prep: {display_name} invoice is due "
        f"for {next_due.isoformat()}. Route this to Cassandra for a dry-run review and preview before send; "
        "show the proof packet first. No email send."
    )
    protected_hash = workflow_package_queue.protected_text_hash(source_text)
    return {
        "request_type": workflow_package_request_consumer.REQUEST_TYPE,
        "kind": workflow_package_request_consumer.REQUEST_KIND,
        "request_id": f"autonomous_invoice_prep_{client_ref}_{next_due:%Y%m%d}",
        "source_surface": "mission_control",
        "source_channel": "autonomous_invoice_prep_scheduler",
        "requested_mode": "operator",
        "world_ref": "finance",
        "thread_ref": client_ref,
        "source_text": source_text,
        "source_text_ref": "protected_text_hash:" + protected_hash,
        "protected_text_hash": protected_hash,
        "result_receipt_required": True,
        "authority_boundary": _authority_boundary_all_false(),
        "idempotency_key": f"autonomous_invoice_prep:{client_ref}:{next_due.isoformat()}",
        "created_at": generated_at,
        "no_external_action": True,
    }


def _attention_event(
    *,
    client_ref: str,
    receipt: Mapping[str, Any],
    next_due: date,
    generated_at: str,
) -> dict[str, Any]:
    proof_refs = list(receipt.get("proof_refs") or [])
    return {
        "event_id": f"autonomous_invoice_prep:{client_ref}:{next_due.isoformat()}",
        "schema_version": "autonomous_invoice_prep_attention_event_v0",
        "generated_at": generated_at,
        "target_surface": "operator_attention_lane",
        "headline": f"{CLIENT_DISPLAY_NAMES[client_ref]} invoice is due",
        "operator_message": (
            f"{CLIENT_DISPLAY_NAMES[client_ref]} invoice is due; I prepared the dry-run review packet. "
            "Review it and approve to send only after Guardian approval."
        ),
        "workflow_ref": str(receipt.get("workflow_ref") or ""),
        "client_ref": client_ref,
        "next_expected_invoice": next_due.isoformat(),
        "package_id": str(receipt.get("package_id") or ""),
        "package_status": str(receipt.get("package_status") or ""),
        "capability_gate_status": str(receipt.get("capability_gate_status") or ""),
        "proof_refs": proof_refs,
        "dry_run_proof_bundle": dict(receipt.get("dry_run_proof_bundle") or {}),
        "telegram_nudge": {
            "would_notify_operator": True,
            "telegram_send_performed": False,
            "send_hold_locked": True,
        },
        "authority_boundary": dict(workflow_package_queue.AUTHORITY_BOUNDARY_DEFAULT),
        "machine_proof": {
            "prepared_only": True,
            "operator_surface_emitted": True,
            "email_send_performed": False,
            "telegram_send_performed": False,
            "ledger_mutation_performed": False,
            "ledger_posting_performed": False,
            "business_action_performed": False,
            "proof_ref_count": len(proof_refs),
        },
    }


def _upsert_attention_event(path: Path, event: Mapping[str, Any], *, generated_at: str) -> None:
    payload = _load_json(path)
    events = payload.get("events") if isinstance(payload.get("events"), list) else []
    by_id = {
        str(row.get("event_id")): dict(row)
        for row in events
        if isinstance(row, Mapping) and row.get("event_id")
    }
    by_id[str(event["event_id"])] = dict(event)
    ordered = sorted(by_id.values(), key=lambda row: str(row.get("event_id") or ""))
    _write_json(
        path,
        {
            "schema_version": ATTENTION_SCHEMA_VERSION,
            "read_model_id": "autonomous_invoice_prep_attention",
            "generated_at": generated_at,
            "status": "AUTONOMOUS_INVOICE_PREP_ATTENTION_READY" if ordered else "IDLE",
            "events": ordered,
            "machine_proof": {
                "operator_attention_lane_surface": True,
                "email_send_performed": False,
                "telegram_send_performed": False,
                "ledger_mutation_performed": False,
                "unsafe_true_grants_absent": True,
            },
        },
    )


def _load_state(path: Path, *, generated_at: str) -> dict[str, Any]:
    state = _load_json(path)
    prepared = state.get("prepared_cycles")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "prepared_cycles": dict(prepared) if isinstance(prepared, Mapping) else {},
    }


def _write_state(path: Path, state: Mapping[str, Any], *, generated_at: str) -> None:
    payload = dict(state)
    payload["schema_version"] = SCHEMA_VERSION
    payload["generated_at"] = generated_at
    _write_json(path, payload)


def _prepare_client(
    *,
    client_ref: str,
    next_due: date,
    generated_at: str,
    queue_sqlite_path: Path,
) -> dict[str, Any]:
    request = _invoice_review_request(client_ref=client_ref, next_due=next_due, generated_at=generated_at)
    result = workflow_package_request_consumer.consume_workflow_package_request(
        request,
        source_request_filename=f"autonomous_invoice_prep_{client_ref}_{next_due:%Y%m%d}.json",
        generated_at=generated_at,
        sqlite_path=_rooted(queue_sqlite_path),
    )
    receipt = dict(result.receipt)
    return {
        "client_ref": client_ref,
        "next_expected_invoice": next_due.isoformat(),
        "workflow_ref": str(receipt.get("workflow_ref") or "st_annes_monthly_invoice_rollup"),
        "package_id": str(receipt.get("package_id") or ""),
        "receipt": receipt,
        "machine_proof": {
            "generic_prepare_path": True,
            "dry_run_consumer_reused": True,
            "email_send_performed": False,
            "telegram_send_performed": False,
            "ledger_mutation_performed": False,
            "business_action_performed": False,
        },
    }


def run_once(
    *,
    today: date | datetime | str | None = None,
    paid_through_store_path: str | Path = DEFAULT_PAID_THROUGH_STORE_PATH,
    queue_sqlite_path: str | Path = DEFAULT_QUEUE_SQLITE_PATH,
    state_path: str | Path = DEFAULT_STATE_PATH,
    attention_outbox_path: str | Path = DEFAULT_ATTENTION_OUTBOX_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    today_date = _coerce_date(today)
    paid_store = ClientPaidThroughStore(_rooted(paid_through_store_path))
    state = _load_state(_rooted(state_path), generated_at=generated_at)
    prepared_cycles = state["prepared_cycles"]
    prepared: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    models = _active_invoice_models()

    for model in models:
        paid_state = paid_up_state_for_client(
            model.client_ref,
            now=today_date,
            paid_through_store=paid_store,
        )
        next_due = paid_state.next_expected_invoice
        row = {
            "client_ref": model.client_ref,
            "cadence": model.cadence,
            "status": paid_state.status,
            "paid_through": paid_state.paid_through.isoformat() if paid_state.paid_through else None,
            "next_expected_invoice": next_due.isoformat() if next_due else None,
        }
        if paid_state.status != "invoice_due" or next_due is None or today_date < next_due:
            skipped.append({**row, "reason": "not_due"})
            continue

        cycle_key = f"{model.client_ref}:{next_due.isoformat()}"
        if cycle_key in prepared_cycles:
            skipped.append({**row, "reason": "already_prepared_for_cycle"})
            continue

        if model.client_ref not in CLIENT_DISPLAY_NAMES:
            skipped.append({**row, "reason": "no_autonomous_prepare_path"})
            continue

        prep = _prepare_client(
            client_ref=model.client_ref,
            next_due=next_due,
            generated_at=generated_at,
            queue_sqlite_path=_rooted(queue_sqlite_path),
        )
        event = _attention_event(
            client_ref=model.client_ref,
            receipt=prep["receipt"],
            next_due=next_due,
            generated_at=generated_at,
        )
        _upsert_attention_event(_rooted(attention_outbox_path), event, generated_at=generated_at)
        prepared_cycles[cycle_key] = {
            "client_ref": model.client_ref,
            "workflow_ref": prep["workflow_ref"],
            "next_expected_invoice": next_due.isoformat(),
            "package_id": prep["package_id"],
            "attention_event_id": event["event_id"],
            "prepared_at": generated_at,
        }
        prepared.append(prep)

    _write_state(_rooted(state_path), state, generated_at=generated_at)
    skip_priority = {
        "already_prepared_for_cycle": 0,
        "no_autonomous_prepare_path": 1,
        "not_due": 2,
    }
    skipped.sort(
        key=lambda row: (
            skip_priority.get(str(row.get("reason") or ""), 99),
            str(row.get("client_ref") or ""),
        )
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "today": today_date.isoformat(),
        "status": "PREPARED" if prepared else "IDLE",
        "prepared": prepared,
        "skipped": skipped,
        "state_path": str(_rooted(state_path)),
        "attention_outbox_path": str(_rooted(attention_outbox_path)),
        "queue_sqlite_path": str(_rooted(queue_sqlite_path)),
        "machine_proof": {
            "recurrence_registry_used": True,
            "paid_through_store_used": True,
            "dry_run_workflow_consumer_used": bool(prepared),
            "active_clients_evaluated": len(models),
            "prepare_only": True,
            "email_send_performed": False,
            "telegram_send_performed": False,
            "ledger_mutation_performed": False,
            "ledger_posting_performed": False,
            "business_action_performed": False,
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Run one prepare-only scheduler pass.")
    parser.add_argument("--today", help="Override today's date as YYYY-MM-DD for tests or replays.")
    parser.add_argument("--paid-through-store", default=str(DEFAULT_PAID_THROUGH_STORE_PATH))
    parser.add_argument("--queue-sqlite", default=str(DEFAULT_QUEUE_SQLITE_PATH))
    parser.add_argument("--state-path", default=str(DEFAULT_STATE_PATH))
    parser.add_argument("--attention-outbox", default=str(DEFAULT_ATTENTION_OUTBOX_PATH))
    parser.add_argument("--generated-at")
    args = parser.parse_args(argv)
    if not args.once:
        parser.error("autonomous invoice prep only supports --once; use the systemd timer for scheduling")
    result = run_once(
        today=args.today,
        paid_through_store_path=args.paid_through_store,
        queue_sqlite_path=args.queue_sqlite,
        state_path=args.state_path,
        attention_outbox_path=args.attention_outbox,
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
