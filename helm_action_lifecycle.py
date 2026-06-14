"""Helm action lifecycle V0.

This module resolves completed Helm action cards from local read models only.
It does not execute actions, touch providers, mutate ledgers, mutate workbooks,
export PDFs, submit portals, send email, or create business truth.
"""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_ACTIONABILITY_PATH = Path("generated/read_models/helm_actionability_surface.json")
DEFAULT_ST_ANNES_REVIEW_PATH = Path("generated/read_models/st_annes_work_log_review_surface.json")
DEFAULT_STATUS_PATH = Path("generated/read_models/helm_action_lifecycle_status.json")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Helm Action Lifecycle.md")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")

SCHEMA_VERSION = "helm_action_lifecycle_status_v0"
READ_MODEL_ID = "helm_action_lifecycle_status"
READY_STATUS = "HELM_ACTION_LIFECYCLE_READY"

ST_ANNES_CARD_IDS = {
    "st_annes_smoke_work_log_event",
    "safe_next_st_annes_review",
}

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


@dataclass(frozen=True)
class LifecycleResult:
    surface: dict[str, Any]
    status: dict[str, Any]


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path) -> Path:
    if path.is_absolute():
        return path
    return ROOT / path


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(_rooted(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object JSON at {path}")
    return payload


def _st_annes_event_status(review_surface: Mapping[str, Any]) -> tuple[str, str, Mapping[str, Any] | None]:
    events = review_surface.get("events")
    if not isinstance(events, list) or not events:
        return "", "", None
    event = next((item for item in events if isinstance(item, Mapping)), None)
    if event is None:
        return "", "", None
    staging_status = str(event.get("staging_status") or "")
    invoice_status = str(event.get("invoice_inclusion_status") or "")
    billing_status = str(event.get("billing_truth_status") or "")
    if billing_status == "SMOKE_OR_TEST_EVENT" and invoice_status == "NOT_INCLUDED_SMOKE_EVENT":
        return "RESOLVED_TEST_EVENT", "St. Anne's test event cleared.", event
    if invoice_status == "READY_FOR_MONTHLY_ROLLUP":
        return "READY_FOR_MONTHLY_ROLLUP", "St. Anne's event confirmed for month-end rollup.", event
    if staging_status == "DISCARDED_BY_OPERATOR":
        return "DISCARDED_BY_OPERATOR", "St. Anne's event discarded.", event
    return "", "", event


def _event_proof_refs(event: Mapping[str, Any] | None) -> list[str]:
    if event is None:
        return []
    refs: list[str] = []
    for item in event.get("hygiene_evidence_refs") or []:
        if isinstance(item, Mapping):
            path = str(item.get("path") or "")
            if path:
                refs.append(path)
        elif isinstance(item, str):
            refs.append(item)
    if refs:
        return refs
    return [
        "generated/read_models/st_annes_work_log_events.json",
        "generated/read_models/st_annes_work_log_review_surface.json",
    ]


def _is_st_annes_card(card: Mapping[str, Any]) -> bool:
    card_id = str(card.get("card_id") or "")
    target_thread = str(card.get("target_thread_ref") or "")
    payload_ref = str(card.get("payload_ref") or "")
    return (
        card_id in ST_ANNES_CARD_IDS
        or target_thread == "st_annes"
        or "st_annes_work_log_review_surface" in payload_ref
    )


def _active_cards(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        card
        for card in cards
        if card.get("visible_by_default", True) is not False
        and str(card.get("lifecycle_status") or "") not in {
            "RESOLVED_TEST_EVENT",
            "READY_FOR_MONTHLY_ROLLUP",
            "DISCARDED_BY_OPERATOR",
        }
    ]


def _next_action_from_cards(cards: list[dict[str, Any]]) -> dict[str, Any]:
    active = _active_cards(cards)
    preferred = next((card for card in active if card.get("card_id") == "capital_hilton_payment_watch"), None)
    if preferred is None:
        preferred = next((card for card in active if card.get("card_id") == "capital_hilton_proposal_watch"), None)
    if preferred is None and active:
        preferred = active[0]
    if preferred is None:
        return {
            "action_id": "no_urgent_action",
            "label": "No urgent action. Review proof only if needed.",
            "action_type": "inspect_proof",
            "target_world_ref": "system",
            "target_thread_ref": "helm",
            "payload_ref": "generated/read_models/helm_action_lifecycle_status.json",
            "reason": "No visible action card requires operator action.",
        }
    return {
        "action_id": str(preferred.get("card_id") or "next_action"),
        "label": str(preferred.get("action_label") or preferred.get("headline") or "Open next action"),
        "action_type": str(preferred.get("action_type") or "navigate"),
        "target_world_ref": str(preferred.get("target_world_ref") or ""),
        "target_thread_ref": str(preferred.get("target_thread_ref") or ""),
        "payload_ref": str(preferred.get("payload_ref") or ""),
        "reason": "The St. Anne's review card is resolved, so Helm advances to the next visible action card.",
    }


def _refresh_safe_next_question(surface: dict[str, Any]) -> None:
    primary = surface.get("primary_next_action") if isinstance(surface.get("primary_next_action"), Mapping) else {}
    questions = surface.get("suggested_questions")
    if not isinstance(questions, list):
        return
    for question in questions:
        if not isinstance(question, dict) or question.get("question_text") != "What is safe next?":
            continue
        label = str(primary.get("label") or "No urgent action. Review proof only if needed.")
        question["precomputed_answer"] = {
            "speaker_ref": "openclaw",
            "headline": f"Safe next: {label}.",
            "plain_summary": str(primary.get("reason") or "Helm advanced past completed cards to the next safe visible item."),
            "next_safe_action": label,
        }
        question["action"] = {
            "action_type": str(primary.get("action_type") or "inspect_proof"),
            "label": label,
            "target_world_ref": str(primary.get("target_world_ref") or ""),
            "target_thread_ref": str(primary.get("target_thread_ref") or ""),
            "payload_ref": str(primary.get("payload_ref") or ""),
        }
        break


def apply_lifecycle(
    *,
    actionability_surface: Mapping[str, Any],
    st_annes_review_surface: Mapping[str, Any],
    generated_at: str | None = None,
) -> LifecycleResult:
    generated_at = generated_at or utc_now()
    surface = json.loads(json.dumps(dict(actionability_surface)))
    cards = [dict(card) for card in surface.get("action_cards") or [] if isinstance(card, Mapping)]
    st_annes_status, completed_summary, event = _st_annes_event_status(st_annes_review_surface)
    proof_refs = _event_proof_refs(event)
    resolved_actions: list[dict[str, Any]] = []

    if st_annes_status:
        for card in cards:
            if not _is_st_annes_card(card):
                continue
            card["lifecycle_status"] = st_annes_status
            card["visible_by_default"] = False
            card["completed"] = True
            card["completed_summary"] = completed_summary
            card["proof_collapsed_by_default"] = True
            card["business_action"] = False
            if proof_refs:
                card["proof_refs"] = proof_refs
            resolved_actions.append(
                {
                    "card_id": str(card.get("card_id") or ""),
                    "status": st_annes_status,
                    "visible_by_default": False,
                    "completed_summary": completed_summary,
                    "event_id": str((event or {}).get("event_id") or ""),
                    "proof_refs": proof_refs,
                    "evidence_preserved": True,
                    "business_action_performed": False,
                }
            )

    surface["action_cards"] = cards
    surface["primary_next_action"] = _next_action_from_cards(cards)
    _refresh_safe_next_question(surface)
    history = dict(surface.get("history_policy") or {})
    history["show_full_history_by_default"] = False
    history["proof_collapsed_by_default"] = True
    history["raw_request_bodies_visible_by_default"] = False
    surface["history_policy"] = history
    surface["authority_boundary"] = {**dict(surface.get("authority_boundary") or {}), **AUTHORITY_BOUNDARY}
    surface["lifecycle"] = {
        "schema_version": SCHEMA_VERSION,
        "status": READY_STATUS,
        "generated_at": generated_at,
        "active_action_count": len(_active_cards(cards)),
        "resolved_action_count": len(resolved_actions),
        "resolved_action_refs": [item["card_id"] for item in resolved_actions],
        "proof_collapsed_by_default": True,
    }

    status = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS,
        "generated_at": generated_at,
        "active_action_count": len(_active_cards(cards)),
        "resolved_action_count": len(resolved_actions),
        "resolved_actions": resolved_actions,
        "primary_next_action": surface["primary_next_action"],
        "proof_refs": sorted(set(ref for item in resolved_actions for ref in item.get("proof_refs", []))),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "source_read_models": [
            "generated/read_models/helm_actionability_surface.json",
            "generated/read_models/st_annes_work_log_events.json",
            "generated/read_models/st_annes_work_log_review_surface.json",
            "generated/read_models/operator_conversation_journal.json",
            "generated/read_models/package_event_index.json",
        ],
        "rules": {
            "resolved_cards_visible_by_default": False,
            "proof_collapsed_by_default": True,
            "evidence_preserved": True,
            "business_truth_created": False,
            "invoice_send_ledger_excel_export_gated": True,
        },
        "machine_proof": {
            "read_model_and_sqlite_metadata_only": True,
            "business_action_truth_created": False,
            "no_invoice_created": True,
            "no_email_sent": True,
            "no_ledger_mutation": True,
            "no_workbook_mutation": True,
            "no_pdf_export": True,
            "proof_collapsed_by_default": True,
            "unsafe_true_grants_absent": True,
        },
    }
    return LifecycleResult(surface=surface, status=status)


def write_outputs(
    *,
    actionability_path: Path = DEFAULT_ACTIONABILITY_PATH,
    st_annes_review_path: Path = DEFAULT_ST_ANNES_REVIEW_PATH,
    status_path: Path = DEFAULT_STATUS_PATH,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    generated_at: str | None = None,
) -> LifecycleResult:
    result = apply_lifecycle(
        actionability_surface=_read_json(actionability_path),
        st_annes_review_surface=_read_json(st_annes_review_path),
        generated_at=generated_at,
    )
    actionability_output = _rooted(actionability_path)
    status_output = _rooted(status_path)
    wiki_output = _rooted(wiki_path)
    status_output.parent.mkdir(parents=True, exist_ok=True)
    wiki_output.parent.mkdir(parents=True, exist_ok=True)
    actionability_output.write_text(stable_json(result.surface), encoding="utf-8")
    status_output.write_text(stable_json(result.status), encoding="utf-8")
    wiki_output.write_text(_wiki_text(result.status), encoding="utf-8")
    if bridge_root is not None:
        bridge_root.mkdir(parents=True, exist_ok=True)
        shutil.copy2(status_output, bridge_root / status_output.name)
        shutil.copy2(actionability_output, bridge_root / actionability_output.name)
    return result


def _wiki_text(status: Mapping[str, Any]) -> str:
    primary = status.get("primary_next_action") if isinstance(status.get("primary_next_action"), Mapping) else {}
    return "\n".join(
        [
            "# Helm Action Lifecycle",
            "",
            f"Status: {status.get('status', READY_STATUS)}",
            "",
            "## Summary",
            f"- Active action cards: {status.get('active_action_count', 0)}",
            f"- Resolved action cards: {status.get('resolved_action_count', 0)}",
            f"- Primary next action: {primary.get('label', 'No urgent action. Review proof only if needed.')}",
            "",
            "## Resolved Actions",
            *(
                [
                    f"- `{item.get('card_id')}`: {item.get('completed_summary')} Proof remains collapsed."
                    for item in status.get("resolved_actions", [])
                    if isinstance(item, Mapping)
                ]
                or ["- None."]
            ),
            "",
            "## Boundary",
            "This lifecycle pass only updates read models. It does not send email, open Gmail, open browser or Coupa, submit portal actions, mutate ledgers, mutate workbooks, export PDFs, mark paid, or create invoice truth.",
            "",
        ]
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve completed Helm action cards.")
    parser.add_argument("--actionability-path", default=str(DEFAULT_ACTIONABILITY_PATH))
    parser.add_argument("--st-annes-review-path", default=str(DEFAULT_ST_ANNES_REVIEW_PATH))
    parser.add_argument("--status-path", default=str(DEFAULT_STATUS_PATH))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--bridge-root", default=str(DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--no-bridge", action="store_true")
    parser.add_argument("--generated-at")
    parser.add_argument("--format", choices=("json", "summary"), default="summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = write_outputs(
        actionability_path=Path(args.actionability_path),
        st_annes_review_path=Path(args.st_annes_review_path),
        status_path=Path(args.status_path),
        wiki_path=Path(args.wiki_path),
        bridge_root=None if args.no_bridge else Path(args.bridge_root),
        generated_at=args.generated_at,
    )
    if args.format == "json":
        print(stable_json(result.status), end="")
    else:
        print(
            f"{result.status['status']}: "
            f"{result.status['resolved_action_count']} resolved, "
            f"{result.status['active_action_count']} active"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
