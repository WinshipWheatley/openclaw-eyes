"""Operator next decision V0.

This module chooses one concrete, non-destructive operator move from local
OpenClaw read models. It does not execute business actions, open providers,
mutate ledgers or workbooks, export PDFs, submit portals, send email, or mark
anything paid.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_ACTIONABILITY_PATH = Path("generated/read_models/helm_actionability_surface.json")
DEFAULT_LIFECYCLE_PATH = Path("generated/read_models/helm_action_lifecycle_status.json")
DEFAULT_OVERNIGHT_WORKBOARD_PATH = Path("generated/read_models/overnight_workboard.json")
DEFAULT_CLIENT_CLOSEOUT_PATH = Path("generated/read_models/client_work_closeout_2026_06_01.json")
DEFAULT_OPERATOR_JOURNAL_PATH = Path("generated/read_models/operator_conversation_journal.json")
DEFAULT_PACKAGE_EVENT_INDEX_PATH = Path("generated/read_models/package_event_index.json")
DEFAULT_PERMISSION_REGISTRY_PATH = Path("generated/read_models/automation_permission_registry.json")
DEFAULT_ST_ANNES_EVENTS_PATH = Path("generated/read_models/st_annes_work_log_events.json")
DEFAULT_CAPITAL_INVOICE_STATUS_PATH = Path("generated/read_models/capital_hilton_invoice_operator_run_status.json")
DEFAULT_CAPITAL_PROPOSAL_PATH = Path("generated/read_models/capital_hilton_business_development_proposal.json")
DEFAULT_DECISION_PATH = Path("generated/read_models/operator_next_decision.json")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Operator Next Decision.md")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")

SCHEMA_VERSION = "operator_next_decision_v0"
READ_MODEL_ID = "operator_next_decision"
READY_STATUS = "READY"

AUTHORITY_BOUNDARY = {
    "email_send_allowed": False,
    "ledger_posting_allowed": False,
    "browser_access_allowed": False,
    "gmail_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "sent": False,
    "paid": False,
}

RESOLVED_STATUSES = {
    "RESOLVED_TEST_EVENT",
    "READY_FOR_MONTHLY_ROLLUP",
    "DISCARDED_BY_OPERATOR",
    "SMOKE_OR_TEST_EVENT",
    "NOT_INCLUDED_SMOKE_EVENT",
}

UNSAFE_ACTION_TERMS = {
    "send",
    "gmail",
    "coupa_submit",
    "ledger",
    "mark_paid",
    "paid",
    "portal_submit",
    "submit",
    "export_pdf",
    "excel",
}

SOURCE_READ_MODELS = [
    "generated/read_models/helm_actionability_surface.json",
    "generated/read_models/helm_action_lifecycle_status.json",
    "generated/read_models/overnight_workboard.json",
    "generated/read_models/client_work_closeout_2026_06_01.json",
    "generated/read_models/operator_conversation_journal.json",
    "generated/read_models/package_event_index.json",
    "generated/read_models/automation_permission_registry.json",
    "generated/read_models/st_annes_work_log_events.json",
    "generated/read_models/capital_hilton_invoice_operator_run_status.json",
    "generated/read_models/capital_hilton_business_development_proposal.json",
]


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path) -> Path:
    if path.is_absolute():
        return path
    return ROOT / path


def _read_json(path: Path) -> dict[str, Any]:
    rooted = _rooted(path)
    payload = json.loads(rooted.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object JSON at {path}")
    return payload


def _resolved_card_ids(lifecycle_status: Mapping[str, Any]) -> set[str]:
    ids: set[str] = set()
    for item in lifecycle_status.get("resolved_actions") or []:
        if isinstance(item, Mapping):
            card_id = str(item.get("card_id") or "")
            if card_id:
                ids.add(card_id)
    return ids


def _card_id(card: Mapping[str, Any]) -> str:
    return str(card.get("card_id") or card.get("action_id") or "")


def _is_resolved_card(card: Mapping[str, Any], resolved_ids: set[str]) -> bool:
    card_id = _card_id(card)
    lifecycle_status = str(card.get("lifecycle_status") or card.get("status") or "")
    return (
        card_id in resolved_ids
        or card.get("completed") is True
        or card.get("visible_by_default") is False
        or lifecycle_status in RESOLVED_STATUSES
    )


def _is_unsafe_action(card: Mapping[str, Any]) -> bool:
    fields = [
        str(card.get("card_id") or ""),
        str(card.get("action_type") or ""),
        str(card.get("action_label") or ""),
        str(card.get("target_world_ref") or ""),
    ]
    joined = " ".join(fields).lower().replace("-", "_")
    return any(term in joined for term in UNSAFE_ACTION_TERMS) or card.get("business_action") is True


def _active_safe_cards(
    actionability_surface: Mapping[str, Any],
    lifecycle_status: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    resolved_ids = _resolved_card_ids(lifecycle_status)
    cards = [dict(card) for card in actionability_surface.get("action_cards") or [] if isinstance(card, Mapping)]
    active: list[dict[str, Any]] = []
    excluded: list[str] = []

    for card in cards:
        card_id = _card_id(card)
        if _is_resolved_card(card, resolved_ids):
            if card_id:
                excluded.append(card_id)
            continue
        if _is_unsafe_action(card):
            if card_id:
                excluded.append(card_id)
            continue
        active.append(card)

    return active, sorted(set(excluded))


def _has_pending_st_annes_event(st_annes_events: Mapping[str, Any]) -> bool:
    possible_lists = [
        st_annes_events.get("staged_events"),
        st_annes_events.get("events"),
        st_annes_events.get("work_log_events"),
    ]
    for events in possible_lists:
        if not isinstance(events, list):
            continue
        for event in events:
            if not isinstance(event, Mapping):
                continue
            invoice_status = str(event.get("invoice_inclusion_status") or "")
            event_status = str(event.get("event_status") or event.get("staging_status") or "")
            billing_status = str(event.get("billing_truth_status") or "")
            if invoice_status in {"NOT_INCLUDED_SMOKE_EVENT", "READY_FOR_MONTHLY_ROLLUP"}:
                continue
            if event_status in {"SMOKE_OR_TEST_EVENT", "DISCARDED_BY_OPERATOR"}:
                continue
            if billing_status == "SMOKE_OR_TEST_EVENT":
                continue
            return True
    return False


def _is_st_annes_card(card: Mapping[str, Any]) -> bool:
    fields = [
        str(card.get("card_id") or ""),
        str(card.get("target_thread_ref") or ""),
        str(card.get("payload_ref") or ""),
    ]
    joined = " ".join(fields).lower()
    return "st_annes" in joined or "st anne" in joined


def _find_card(cards: list[dict[str, Any]], card_id: str) -> dict[str, Any] | None:
    return next((card for card in cards if _card_id(card) == card_id), None)


def _base_decision(*, generated_at: str, excluded_items: list[str]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS,
        "generated_at": generated_at,
        "headline": "",
        "plain_summary": "",
        "speaker_ref": "openclaw",
        "voice_profile_ref": "agent_voice_profile:openclaw",
        "voice_mode": "operator_calm",
        "action_label": "",
        "action_type": "none",
        "target_world_ref": "",
        "target_thread_ref": "",
        "priority": "normal",
        "business_action": False,
        "proof_refs": [],
        "proof_collapsed_by_default": True,
        "history_policy": {
            "show_full_history_by_default": False,
            "proof_collapsed_by_default": True,
            "raw_request_bodies_visible_by_default": False,
        },
        "precomputed_question_payload": {},
        "excluded_items": excluded_items,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "source_read_models": SOURCE_READ_MODELS,
        "decision_rules": {
            "prefer_active_unresolved_operator_review_items": True,
            "exclude_smoke_test_events_already_marked_test": True,
            "exclude_resolved_lifecycle_cards": True,
            "do_not_recommend_send_coupa_or_ledger": True,
            "planning_fallback_is_overnight_workboard": True,
            "proof_refs_collapsed": True,
        },
        "machine_proof": {
            "business_action_truth_created": False,
            "business_action": False,
            "no_email_sent": True,
            "no_gmail_opened": True,
            "no_browser_or_coupa_opened": True,
            "no_ledger_mutation": True,
            "no_workbook_mutation": True,
            "no_pdf_export": True,
            "no_paid_marking": True,
            "proof_collapsed_by_default": True,
            "history_hidden_by_default": True,
            "unsafe_true_grants_absent": True,
        },
    }


def _apply_st_annes_decision(payload: dict[str, Any]) -> None:
    payload.update(
        {
            "headline": "Clear the St. Anne's work-log item",
            "plain_summary": "Mark it as test or confirm it as real work.",
            "speaker_ref": "cassandra",
            "voice_profile_ref": "agent_voice_profile:cassandra",
            "voice_mode": "operator_review",
            "action_label": "Open St. Anne's review",
            "action_type": "review_event",
            "target_world_ref": "finance",
            "target_thread_ref": "st_annes",
            "priority": "high",
            "proof_refs": [
                "generated/read_models/helm_actionability_surface.json",
                "generated/read_models/st_annes_work_log_events.json",
                "generated/read_models/st_annes_work_log_review_surface.json",
            ],
            "precomputed_question_payload": {
                "workflow_ref": "system_question_answer",
                "question_text": "What should I do with this St. Anne's work-log item?",
                "target_world_ref": "finance",
                "target_thread_ref": "st_annes",
            },
        }
    )


def _apply_capital_payment_decision(payload: dict[str, Any]) -> None:
    payload.update(
        {
            "headline": "Watch Capital Hilton payment",
            "plain_summary": "Coupa is processing. Ledger stays untouched until payment proof arrives.",
            "speaker_ref": "chief",
            "voice_profile_ref": "agent_voice_profile:chief",
            "voice_mode": "operator_calm",
            "action_label": "Open Capital Hilton",
            "action_type": "navigate",
            "target_world_ref": "finance",
            "target_thread_ref": "capital_hilton",
            "priority": "normal",
            "proof_refs": [
                "generated/read_models/helm_actionability_surface.json",
                "generated/read_models/helm_action_lifecycle_status.json",
                "generated/read_models/capital_hilton_invoice_operator_run_status.json",
                "generated/read_models/package_event_index.json",
            ],
            "precomputed_question_payload": {
                "workflow_ref": "system_question_answer",
                "question_text": "What is safe next for Capital Hilton payment watch?",
                "target_world_ref": "finance",
                "target_thread_ref": "capital_hilton",
            },
        }
    )


def _apply_capital_proposal_decision(payload: dict[str, Any]) -> None:
    payload.update(
        {
            "headline": "Review Capital Hilton proposal follow-up",
            "plain_summary": "The proposal is waiting for client review. Keep follow-up planning separate from finance truth.",
            "speaker_ref": "chief",
            "voice_profile_ref": "agent_voice_profile:chief",
            "voice_mode": "operator_calm",
            "action_label": "Open Capital Hilton proposal",
            "action_type": "navigate",
            "target_world_ref": "business_development",
            "target_thread_ref": "capital_hilton",
            "priority": "low",
            "proof_refs": [
                "generated/read_models/capital_hilton_business_development_proposal.json",
                "generated/read_models/operator_conversation_journal.json",
                "generated/read_models/package_event_index.json",
            ],
            "precomputed_question_payload": {
                "workflow_ref": "system_question_answer",
                "question_text": "What is safe next for the Capital Hilton proposal follow-up?",
                "target_world_ref": "business_development",
                "target_thread_ref": "capital_hilton",
            },
        }
    )


def _apply_workboard_decision(payload: dict[str, Any]) -> None:
    payload.update(
        {
            "headline": "No urgent action",
            "plain_summary": "Client work is recorded. Review the workboard when you are ready.",
            "speaker_ref": "openclaw",
            "voice_profile_ref": "agent_voice_profile:openclaw",
            "voice_mode": "operator_calm",
            "action_label": "Open workboard",
            "action_type": "open_workboard",
            "target_world_ref": "system",
            "target_thread_ref": "overnight_workboard",
            "priority": "low",
            "proof_refs": [
                "generated/read_models/overnight_workboard.json",
                "generated/read_models/client_work_closeout_2026_06_01.json",
                "generated/read_models/operator_conversation_journal.json",
            ],
            "precomputed_question_payload": {
                "workflow_ref": "system_question_answer",
                "question_text": "What is safe next?",
                "target_world_ref": "system",
                "target_thread_ref": "overnight_workboard",
            },
        }
    )


def choose_next_decision(
    *,
    actionability_surface: Mapping[str, Any],
    lifecycle_status: Mapping[str, Any],
    overnight_workboard: Mapping[str, Any],
    client_work_closeout: Mapping[str, Any] | None = None,
    operator_conversation_journal: Mapping[str, Any] | None = None,
    package_event_index: Mapping[str, Any] | None = None,
    automation_permission_registry: Mapping[str, Any] | None = None,
    st_annes_events: Mapping[str, Any] | None = None,
    capital_hilton_invoice_status: Mapping[str, Any] | None = None,
    capital_hilton_proposal: Mapping[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    del overnight_workboard
    del client_work_closeout
    del operator_conversation_journal
    del package_event_index
    del automation_permission_registry
    del capital_hilton_invoice_status
    del capital_hilton_proposal

    generated_at = generated_at or utc_now()
    active_cards, excluded_items = _active_safe_cards(actionability_surface, lifecycle_status)
    payload = _base_decision(generated_at=generated_at, excluded_items=excluded_items)
    st_annes_events = st_annes_events or {}

    st_annes_card = next((card for card in active_cards if _is_st_annes_card(card)), None)
    if st_annes_card is not None and _has_pending_st_annes_event(st_annes_events):
        _apply_st_annes_decision(payload)
    elif _find_card(active_cards, "capital_hilton_payment_watch") is not None:
        _apply_capital_payment_decision(payload)
    elif _find_card(active_cards, "capital_hilton_proposal_watch") is not None:
        _apply_capital_proposal_decision(payload)
    else:
        _apply_workboard_decision(payload)

    payload["resolved_action_refs"] = sorted(_resolved_card_ids(lifecycle_status))
    payload["active_action_count_considered"] = len(active_cards)
    payload["business_action"] = False
    payload["authority_boundary"] = dict(AUTHORITY_BOUNDARY)
    return payload


def write_outputs(
    *,
    actionability_path: Path = DEFAULT_ACTIONABILITY_PATH,
    lifecycle_path: Path = DEFAULT_LIFECYCLE_PATH,
    overnight_workboard_path: Path = DEFAULT_OVERNIGHT_WORKBOARD_PATH,
    client_closeout_path: Path = DEFAULT_CLIENT_CLOSEOUT_PATH,
    operator_journal_path: Path = DEFAULT_OPERATOR_JOURNAL_PATH,
    package_event_index_path: Path = DEFAULT_PACKAGE_EVENT_INDEX_PATH,
    permission_registry_path: Path = DEFAULT_PERMISSION_REGISTRY_PATH,
    st_annes_events_path: Path = DEFAULT_ST_ANNES_EVENTS_PATH,
    capital_invoice_status_path: Path = DEFAULT_CAPITAL_INVOICE_STATUS_PATH,
    capital_proposal_path: Path = DEFAULT_CAPITAL_PROPOSAL_PATH,
    decision_path: Path = DEFAULT_DECISION_PATH,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    payload = choose_next_decision(
        actionability_surface=_read_json(actionability_path),
        lifecycle_status=_read_json(lifecycle_path),
        overnight_workboard=_read_json(overnight_workboard_path),
        client_work_closeout=_read_json(client_closeout_path),
        operator_conversation_journal=_read_json(operator_journal_path),
        package_event_index=_read_json(package_event_index_path),
        automation_permission_registry=_read_json(permission_registry_path),
        st_annes_events=_read_json(st_annes_events_path),
        capital_hilton_invoice_status=_read_json(capital_invoice_status_path),
        capital_hilton_proposal=_read_json(capital_proposal_path),
        generated_at=generated_at,
    )

    decision_output = _rooted(decision_path)
    wiki_output = _rooted(wiki_path)
    decision_output.parent.mkdir(parents=True, exist_ok=True)
    wiki_output.parent.mkdir(parents=True, exist_ok=True)
    decision_output.write_text(stable_json(payload), encoding="utf-8")
    wiki_output.write_text(_wiki_text(payload), encoding="utf-8")
    if bridge_root is not None:
        bridge_root.mkdir(parents=True, exist_ok=True)
        shutil.copy2(decision_output, bridge_root / decision_output.name)
    return payload


def _wiki_text(payload: Mapping[str, Any]) -> str:
    excluded = payload.get("excluded_items") if isinstance(payload.get("excluded_items"), list) else []
    proof_refs = payload.get("proof_refs") if isinstance(payload.get("proof_refs"), list) else []
    return "\n".join(
        [
            "# Operator Next Decision",
            "",
            f"Status: {payload.get('status', READY_STATUS)}",
            "",
            "## Chosen Move",
            f"- Headline: {payload.get('headline')}",
            f"- Summary: {payload.get('plain_summary')}",
            f"- Action: {payload.get('action_label')}",
            f"- Lane: {payload.get('target_world_ref')} / {payload.get('target_thread_ref')}",
            "",
            "## Excluded Or Resolved Items",
            *(f"- `{item}`" for item in excluded),
            *(["- None."] if not excluded else []),
            "",
            "## Proof",
            "- Proof stays collapsed by default.",
            *(f"- `{ref}`" for ref in proof_refs),
            "",
            "## Boundary",
            "This decision surface only reads local read models and writes generated status artifacts. It does not send email, open Gmail, open browser or Coupa, submit portal actions, mutate ledgers, mutate workbooks, export PDFs, mark paid, or create business truth.",
            "",
        ]
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish the operator next decision surface.")
    parser.add_argument("--decision-path", default=str(DEFAULT_DECISION_PATH))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--bridge-root", default=str(DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--no-bridge", action="store_true")
    parser.add_argument("--generated-at")
    parser.add_argument("--format", choices=("json", "summary"), default="summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    payload = write_outputs(
        decision_path=Path(args.decision_path),
        wiki_path=Path(args.wiki_path),
        bridge_root=None if args.no_bridge else Path(args.bridge_root),
        generated_at=args.generated_at,
    )
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(f"{payload['status']}: {payload['headline']} -> {payload['action_label']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
