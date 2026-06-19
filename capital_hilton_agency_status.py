"""Capital Hilton agency/provenance status read-model v0.

This module explains the current Capital Hilton payment state together with
who did what. It is evidence/status only: it does not send, submit, mutate a
ledger, move money, verify bank receipt, or mark paid.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "capital_hilton_agency_status_v0"
READ_MODEL_ID = "capital_hilton_agency_status"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"

CLIENT_REF = "capital_hilton"
CLIENT_DISPLAY_NAME = "Capital Hilton"
EXPECTED_CHECK_DATE = "2026-07-01"
INVOICE_RUN_STATUS_PATH = DEFAULT_EXPORT_ROOT / "capital_hilton_invoice_operator_run_status.json"

CURRENT_BUSINESS_STATUS = (
    "Everything is checked off except Capital Hilton sending the actual check; "
    "the check is expected to be sent on July 1, 2026."
)

AUTHORITY_FLAGS = {
    "status_read_model_only": True,
    "operator_supplied_current_status": True,
    "bank_or_payment_processor_verified": False,
    "check_received_or_deposited": False,
    "autonomous_openclaw_business_process_completed": False,
    "autonomous_openclaw_coupa_submit": False,
    "autonomous_openclaw_email_send": False,
    "ledger_mutation_performed": False,
    "money_movement_performed": False,
    "paid_marking_performed": False,
    "external_action_performed": False,
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _rooted(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return ROOT / candidate


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _load_invoice_run_status(path: Path = INVOICE_RUN_STATUS_PATH) -> dict[str, Any]:
    target = _rooted(path)
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _invoice_correlation(invoice_status: dict[str, Any]) -> dict[str, Any]:
    workbook_invoice = str(invoice_status.get("workbook_invoice_number") or "2026-1006").strip()
    coupa_invoice = str(invoice_status.get("coupa_invoice_number") or "2026 1006").strip()
    invoice_total = str(invoice_status.get("invoice_total") or "$2,000.00").strip()
    coupa_status = str(
        invoice_status.get("coupa_status_observed")
        or invoice_status.get("coupa_submission_status")
        or "Processing"
    ).strip()
    return {
        "workbook_invoice_number": workbook_invoice,
        "coupa_invoice_number": coupa_invoice,
        "invoice_total": invoice_total,
        "coupa_po_number": str(invoice_status.get("coupa_po_number") or "DCASH00983536").strip(),
        "coupa_internal_invoice_id": str(invoice_status.get("coupa_internal_invoice_id") or "1697749").strip(),
        "coupa_confirmation_ref": str(invoice_status.get("coupa_confirmation_ref") or "").strip(),
        "coupa_submission_status": coupa_status,
        "email_status": str(invoice_status.get("email_status") or "").strip(),
        "paid": bool(invoice_status.get("paid")),
        "payment_received_recorded": bool(invoice_status.get("payment_received_recorded")),
        "correlation_rule": (
            f"Treat Excel/PDF invoice {workbook_invoice} and Coupa invoice {coupa_invoice} as the same invoice; "
            "Coupa removed the hyphen for portal format."
        ),
        "paid_transition_requires": [
            "payment/check evidence explicitly tied to Capital Hilton or Hilton Smart Spend",
            f"amount matching or explainably reconciling to {invoice_total}",
            f"invoice reference matching {workbook_invoice} or {coupa_invoice}, or a protected receipt tying the payment to that invoice",
            "authorized finance/ledger receipt before paid marking",
        ],
    }


def build_capital_hilton_agency_status(*, generated_at: str | None = None) -> dict[str, Any]:
    invoice_status = _load_invoice_run_status()
    invoice_correlation = _invoice_correlation(invoice_status)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at or utc_now(),
        "client_ref": CLIENT_REF,
        "client_display_name": CLIENT_DISPLAY_NAME,
        "current_business_status": CURRENT_BUSINESS_STATUS,
        "openclaw_current_status": {
            "state": "payment_watch_waiting_for_expected_check",
            "plain_status": (
                "Capital Hilton is in payment watch. The invoice has been submitted/emailed with operator assistance, "
                "but the check has not been recorded as sent, received, deposited, or ledger-reconciled."
            ),
            "expected_external_event": "Capital Hilton sends the actual check on July 1, 2026.",
        },
        "outstanding_item": "actual_check_not_sent_or_received_yet",
        "expected_check_date": EXPECTED_CHECK_DATE,
        "invoice_correlation": invoice_correlation,
        "watch_status": {
            "desired_capital_hilton_email_watch": {
                "target_behavior": (
                    "Watch incoming Gmail metadata for Capital Hilton/Hilton/Smart Spend/Annette/Chyna/Will signals "
                    "that update check, Coupa, invoice, or payment timing."
                ),
                "current_repo_support": "Gmail metadata polling exists on request; AR email watch policy exists as policy-only.",
                "actual_live_capital_hilton_specific_watch_verified": False,
                "safe_status_label": "watch_needed_not_proven_live",
                "safe_next_step": (
                    "Wire a scoped metadata-only Capital Hilton email watch with receipts; body reads and sends remain separately gated."
                ),
            },
            "desired_ledger_payment_watch": {
                "target_behavior": (
                    "Watch authorized income/ledger surfaces for a check/payment entry matching the correlated Capital Hilton invoice."
                ),
                "current_repo_support": "Cassandra can check recent Gmail payment metadata and local income logs on request.",
                "actual_live_ledger_match_watch_verified": False,
                "safe_status_label": "ledger_checkpoint_needed_not_proven_live",
                "safe_next_step": (
                    "Create a read-only checkpoint that searches approved ledger/income records for the matching invoice/payment evidence."
                ),
            },
        },
        "status_transitions": [
            {
                "from": "payment_watch_waiting_for_expected_check",
                "to": "invoice_paid",
                "trigger": "matching check/payment evidence is received and reconciled to the invoice correlation",
                "allowed_without_operator_approval": False,
                "must_not_skip": ["payment evidence", "invoice correlation", "authorized ledger receipt"],
            },
            {
                "from": "invoice_paid",
                "to": "unbilled_played_gigs_ready_to_invoice",
                "trigger": "paid receipt closes the current invoice and the source gig log/workbook shows later completed, uninvoiced gigs",
                "allowed_without_operator_approval": True,
                "must_not_skip": ["source gig count", "date/rate basis", "already_invoiced exclusion"],
            },
            {
                "from": "unbilled_played_gigs_ready_to_invoice",
                "to": "invoice_preparation_requested",
                "trigger": "operator says to make/send/start the next Capital Hilton invoice",
                "allowed_without_operator_approval": False,
                "must_not_skip": ["invoice preview", "Coupa/Excel correlation", "Guardian/operator send/submit approval"],
            },
        ],
        "next_invoice_queue": {
            "state_after_current_invoice_paid": "show_completed_unbilled_gigs_ready_for_operator_command",
            "played_gig_count_source": "source workbook or gig log, not memory",
            "played_gig_count_currently_verified": None,
            "operator_facing_template": (
                "We have you down for X Capital Hilton gigs played and not yet invoiced. "
                "I am ready to prepare the next invoice when you tell me."
            ),
            "invoice_generation_rule": (
                "Do not create, send, or submit the next invoice merely because the previous invoice was paid; "
                "wait for the operator command and preserve approval gates."
            ),
        },
        "evidence_tier": "operator_supplied_current_status_not_bank_or_payment_proof",
        "source_of_current_status": {
            "source_type": "operator_supplied_correction",
            "source_channel": "telegram",
            "recorded_context": (
                "The operator corrected stale Coupa-blocker status and supplied the current truth: "
                "all prerequisites are checked off except the actual check, expected July 1, 2026."
            ),
        },
        "agency_attribution": [
            {
                "actor": "operator",
                "did": "supplied the current business truth and expected check date",
                "did_not_do": "provide bank/payment-processor proof that the check was sent or received",
            },
            {
                "actor": "codex_desktop",
                "did": (
                    "diagnosed stale Cassandra status behavior, patched/readied Cassandra and related Chief/polish-loop "
                    "status handling, restarted the Cassandra listener when authorized, and verified the Telegram readback"
                ),
                "did_not_do": "send external messages, submit Coupa, mutate finance ledgers, move money, cut the check, or verify receipt of funds",
            },
            {
                "actor": "cassandra",
                "did": "stored and read back the operator's current-status correction",
                "did_not_do": "complete or independently verify the external Capital Hilton payment process",
            },
            {
                "actor": "openclaw_autonomous_system",
                "did": "nothing that should be treated as an autonomous completion of the Capital Hilton payment workflow",
                "did_not_do": "autonomously complete Coupa, email, check issuance, bank verification, ledger posting, or paid marking",
            },
        ],
        "what_happened_because_codex_desktop_did_the_work": [
            "Cassandra can now reject stale Capital Hilton status when the operator says it is stale.",
            "Cassandra can ask what should change, store the supplied correction, and read back the updated status.",
            "Chief/polish-loop routing has a queued path for agent-response polish instead of pretending the old answer was fine.",
        ],
        "what_did_not_happen_because_codex_desktop_did_not_have_that_authority": [
            "No client or vendor message was sent.",
            "No Coupa/portal action was submitted.",
            "No ledger, invoice, payment, or paid-status primitive was mutated by this status path.",
            "No money moved, and no check was cut by the system.",
            "No live bank/payment-processor health is claimed.",
        ],
        "if_openclaw_had_done_this_autonomously_it_would_need_receipts_for": [
            "operator or Guardian authorization to begin the bounded Capital Hilton payment workflow",
            "read-only verification that PO/Coupa/account prerequisites were satisfied",
            "approved portal/email actions with receipts for any external submit/send step",
            "protected evidence references for sensitive portal or financial proof",
            "July 1, 2026 check issuance, then check receipt/deposit verification before any paid claim",
        ],
        "next_safe_action": (
            "Wait for the expected July 1, 2026 check; when it exists, verify the actual check/payment receipt "
            "through the authorized finance path before marking paid."
        ),
        "authority_flags": dict(AUTHORITY_FLAGS),
        "machine_proof": {
            "current_status_has_agency_attribution": True,
            "invoice_correlation_recorded": True,
            "email_watch_not_overclaimed": True,
            "ledger_watch_not_overclaimed": True,
            "paid_transition_guarded_by_payment_evidence": True,
            "next_invoice_queue_waits_for_operator_command": True,
            "operator_source_labeled": True,
            "codex_desktop_work_labeled": True,
            "autonomous_completion_false": True,
            "no_live_payment_health_claimed": True,
            "no_money_or_ledger_mutation_claimed": True,
        },
    }
    payload["content_hash"] = _content_hash(payload)
    return payload


_ENTITY_MARKERS = (
    "capital hilton",
    "capitol hilton",
    "hilton",
    "coupa",
    "smartspend",
)

_AGENCY_MARKERS = (
    "autonomous",
    "autonomously",
    "codex",
    "codex desktop",
    "who did",
    "what did",
    "because codex",
    "system did",
    "openclaw did",
    "provenance",
    "agency",
    "agency attribution",
    "how do you know",
    "core",
    "mimicking",
    "who supplied",
    "what happened because",
)

_OPENCLAW_STATUS_MARKERS = (
    "openclaw status",
    "open claw status",
    "current situation",
    "watching my emails",
    "watch my emails",
    "incoming emails",
    "capital hilton email",
    "ledger",
    "check came in",
    "check comes in",
    "invoice was paid",
    "invoice is paid",
    "paid invoice",
    "x gigs",
    "played gigs",
    "ready to send the invoice",
    "ready to send invoice",
    "next invoice",
)


def is_capital_hilton_agency_query(text: str) -> bool:
    q = (text or "").lower()
    return any(marker in q for marker in _ENTITY_MARKERS) and any(marker in q for marker in _AGENCY_MARKERS)


def is_capital_hilton_openclaw_status_query(text: str) -> bool:
    q = (text or "").lower()
    return any(marker in q for marker in _ENTITY_MARKERS) and any(
        marker in q for marker in _OPENCLAW_STATUS_MARKERS
    )


def format_capital_hilton_agency_answer(text: str) -> str | None:
    if not is_capital_hilton_agency_query(text):
        return None
    payload = build_capital_hilton_agency_status()
    return (
        "No — this should not be treated as OpenClaw autonomously completing the Capital Hilton payment workflow. "
        f"Core status: {payload['current_business_status']} "
        "Source: operator-supplied current status, not bank or payment-processor proof. "
        "Agency: you supplied the business truth; Codex Desktop did the Cassandra/Chief/polish-loop diagnosis, patching, restart/testing, and stale-correction wiring; Cassandra stored and read back that correction. "
        "OpenClaw did not autonomously send messages, submit Coupa, mutate a ledger, move money, cut the check, or verify that the check was received. "
        "If OpenClaw had done the payment workflow autonomously, it would need receipts for authorization, PO/Coupa/account readiness, any approved portal/email action, protected evidence, and the July 1 check issuance/receipt before claiming paid."
    )


def format_capital_hilton_openclaw_status_answer(text: str) -> str | None:
    if not is_capital_hilton_openclaw_status_query(text):
        return None
    payload = build_capital_hilton_agency_status()
    invoice = payload["invoice_correlation"]
    email_watch = payload["watch_status"]["desired_capital_hilton_email_watch"]
    ledger_watch = payload["watch_status"]["desired_ledger_payment_watch"]
    return (
        "Capital Hilton should be in payment-watch, not paid. "
        f"The correlated invoice is Excel/PDF {invoice['workbook_invoice_number']} / Coupa {invoice['coupa_invoice_number']}, "
        f"PO {invoice['coupa_po_number']}, total {invoice['invoice_total']}, Coupa status {invoice['coupa_submission_status']}. "
        f"Current business truth: {payload['current_business_status']} "
        f"Email watch target: watch incoming Capital Hilton/Hilton/Smart Spend metadata for new check or invoice info; current implementation status is {email_watch['safe_status_label']}, so do not claim a live Capital Hilton-specific Gmail watch until that receipt exists. "
        f"Ledger watch target: look for authorized income/ledger evidence matching this invoice; current implementation status is {ledger_watch['safe_status_label']}, so do not mark paid from memory or email alone. "
        "When matching payment evidence lands, the status becomes invoice_paid for that correlated invoice. "
        "After that, the next status is unbilled_played_gigs_ready_to_invoice: get X from the source workbook/gig log, then wait for your command before preparing or sending the next invoice."
    )


def _operator_markdown(payload: dict[str, Any]) -> str:
    evidence_tier = "operator supplied current status; not bank or payment-processor proof"
    lines = [
        "# Capital Hilton Agency Status",
        "",
        f"Status: {payload['current_business_status']}",
        f"OpenClaw State: {payload['openclaw_current_status']['state']}",
        "",
        "Invoice Correlation",
        f"- Excel/PDF invoice: {payload['invoice_correlation']['workbook_invoice_number']}",
        f"- Coupa invoice: {payload['invoice_correlation']['coupa_invoice_number']}",
        f"- PO: {payload['invoice_correlation']['coupa_po_number']}",
        f"- Total: {payload['invoice_correlation']['invoice_total']}",
        f"- Coupa status: {payload['invoice_correlation']['coupa_submission_status']}",
        "",
        "Evidence Tier",
        f"- {evidence_tier}",
        "",
        "Watch Status",
        f"- Email: {payload['watch_status']['desired_capital_hilton_email_watch']['safe_status_label']}",
        f"- Ledger: {payload['watch_status']['desired_ledger_payment_watch']['safe_status_label']}",
        "",
        "Agency Attribution",
    ]
    for item in payload["agency_attribution"]:
        actor_label = str(item["actor"]).replace("_", " ").title()
        lines.append(f"- {actor_label}: did {item['did']}; did not {item['did_not_do']}.")
    lines.extend(
        [
            "",
            "Not Done By This Status Path",
            *[f"- {item}" for item in payload["what_did_not_happen_because_codex_desktop_did_not_have_that_authority"]],
            "",
            f"Next Safe Action: {payload['next_safe_action']}",
            "",
        ]
    )
    return "\n".join(lines)


def export_read_model(
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> dict[str, str]:
    payload = build_capital_hilton_agency_status(generated_at=generated_at)
    out_root = _rooted(export_root)
    out_root.mkdir(parents=True, exist_ok=True)
    json_path = out_root / JSON_EXPORT_NAME
    operator_path = out_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(_operator_markdown(payload), encoding="utf-8")
    return {
        "schema_version": SCHEMA_VERSION,
        "json_path": str(json_path),
        "operator_path": str(operator_path),
        "content_hash": str(payload["content_hash"]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Capital Hilton agency/provenance status read-model.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args(argv)
    result = export_read_model(export_root=Path(args.export_root), generated_at=args.generated_at)
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
