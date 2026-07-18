#!/usr/bin/env python3
"""Run a no-send Clara invoice-copy taste pass through the deployed compose rail."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_voice_profiles import loop_closing_ask_for_workflow, voice_copy_rules_for_speaker
from clara_invoice_email_draft_package import build_clara_invoice_email_draft_package
from invoice_cockpit_client_registry import DEFAULT_CLARA_INVOICE_CLIENT_REGISTRY


DEFAULT_PDF = Path(
    "/mnt/e/openclaw/artifacts/invoice_workbooks/live_arts_md/2026-07/"
    "w1-finalized-2026-1004/invoice.pdf"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fact(topic: str, value: str, source_ref: str, *, at: str) -> dict[str, object]:
    return {
        "fact_id": "clara-copy:" + topic,
        "topic": topic,
        "label": topic,
        "value": value,
        "source_ref": source_ref,
        "provenance": "operator_receipt_or_verified_artifact",
        "freshness": {"as_of": at, "source_ref": source_ref},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()

    pdf = args.pdf.resolve()
    if not pdf.is_file():
        raise SystemExit(f"validated PDF missing: {pdf}")
    actual_sha256 = _sha256(pdf)
    if actual_sha256 != args.expected_sha256:
        raise SystemExit(f"validated PDF hash mismatch: {actual_sha256}")

    client = DEFAULT_CLARA_INVOICE_CLIENT_REGISTRY["live_arts_md"]
    recipient = str(client["canonical_recipient"])
    if recipient != "Accountant@liveartsmd.org":
        raise SystemExit(f"recipient lock mismatch: {recipient}")
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    closure = loop_closing_ask_for_workflow(
        "live_arts_md_invoice_workflow",
        client_ref="live_arts_md",
    )
    signoff = str(voice_copy_rules_for_speaker("clara")["signoff"])
    facts = (
        _fact(
            "invoice",
            "Invoice 2026-1004 is the July 2026 monthly speaker rental invoice for $100.",
            "Operator/from-codex/W2-B-VALIDATION-EVENT-1-CHAIN-RECEIPT-20260717-PC-Codex-Desktop.json",
            at=now,
        ),
        _fact(
            "recipient",
            "Megan Rivas's AP inbox is Accountant@liveartsmd.org.",
            "Operator/to-codex/OPERATOR-DECISIONS-ALL-3-YES-PLUS-LAMD-FACTS-20260717.md",
            at=now,
        ),
        _fact(
            "attachment",
            f"The validated invoice PDF is invoice.pdf with SHA-256 {actual_sha256}.",
            str(pdf),
            at=now,
        ),
        _fact(
            "workflow",
            f"Closing ask: {closure['ask_text']} {closure['why_text']}",
            "agent_voice_profiles.py#clara_loop_closure:live_arts_md",
            at=now,
        ),
    )
    recipient_package = {
        "to_recipients": (
            {
                "display_name": "Megan Rivas",
                "role": "invoice_accountant",
                "lane": "to",
                "email": recipient,
                "confirmation_status": "CONFIRMED_BY_RECEIPT",
                "proof_ref": "Operator/to-codex/OPERATOR-DECISIONS-ALL-3-YES-PLUS-LAMD-FACTS-20260717.md",
            },
        ),
        "cc_recipients": (),
        "recipient_confirmation_status": "CONFIRMED_BY_RECEIPT",
        "recipient_info_missing": (),
        "recipient_email_invented": False,
    }
    raw_ask = (
        "Regenerate the Live Arts MD July invoice email in Clara Reid's designed register: polished, "
        "personable, quietly confident, poised, and brief. The closing ask and its reason carry the "
        "warmth. Use no solicitous pleasantry, eager-agreeable padding, filler thanks, or well-wish. "
        "Greet Megan properly and preserve the closing ask and why."
    )
    draft = build_clara_invoice_email_draft_package(
        client_ref="live_arts_md",
        workflow_ref="live_arts_md_invoice_workflow",
        client_display_name="Live Arts MD",
        recipient_package=recipient_package,
        attachment_ready=True,
        attachment_refs=(str(pdf),),
        invoice_period_label="July 2026",
        supplier_portal_required=False,
        first_contact_intro_required=False,
        present_receipts=("clara_email_draft_receipt",),
        invoice_data={
            "client_name": "Live Arts MD",
            "attachment_filename": pdf.name,
            "coverage_label": "the July 2026 monthly speaker rental",
            "amount_total": 100.0,
            "line_items": (
                {"description": "Monthly speaker rental", "date": "July 2026", "amount": 100.0},
            ),
            "model_required_subject_atoms": ("2026-1004",),
            "model_canonical_subject": "2026-1004: July 2026 Monthly Speaker Rental Invoice",
            "model_required_body_atoms": ("July 2026", "$100", "monthly speaker rental"),
            "model_required_any_body_atom_groups": (("attached", "included", "enclosed"),),
            "model_forbidden_claims": ("already sent",),
            "model_copy_fact_citations": tuple(str(fact["source_ref"]) for fact in facts),
            "model_packet_facts": facts,
        },
        contact={"name": "Megan Rivas", "email": recipient, "role": "invoice_accountant"},
        client_record=client,
        raw_operator_ask=raw_ask,
        model_compose=True,
        compose_attempts=3,
        record_compose_telemetry=True,
    )
    proof = dict(draft["model_compose_proof"] or {})
    receipt = {
        "schema_version": "clara_invoice_copy_taste_pass_receipt_v2",
        "generated_at": now,
        "status": "LIVE_MODEL_COPY_SELECTED_NO_SEND",
        "taste_pass_id": proof.get("taste_pass_id"),
        "subject": draft["subject"],
        "body": draft["body"],
        "recipient": recipient,
        "attachment_path": str(pdf),
        "attachment_sha256": actual_sha256,
        "invoice_number": "2026-1004",
        "invoice_amount": "$100.00",
        "model_compose_proof": proof,
        "persona_fidelity": proof.get("persona_fidelity"),
        "send_hold_active": Path("/mnt/e/openclaw/orchestration/SEND_HOLD.md").is_file(),
        "provider_draft_created": False,
        "email_send_performed": False,
        "business_ledger_posted": False,
        "transaction_mutated": False,
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
