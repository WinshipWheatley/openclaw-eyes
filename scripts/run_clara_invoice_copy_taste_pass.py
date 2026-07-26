#!/usr/bin/env python3
"""Run a no-send Clara invoice-copy taste pass through the deployed compose rail."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from clara_invoice_email_draft_package import build_clara_invoice_email_draft_package
from clara_lamd_compose_spec import (
    DEFAULT_PDF,
    build_lamd_clara_compose_kwargs,
    verify_pdf,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()

    pdf = args.pdf.resolve()
    try:
        actual_sha256 = verify_pdf(pdf, args.expected_sha256)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    draft = build_clara_invoice_email_draft_package(
        **build_lamd_clara_compose_kwargs(
            pdf=pdf,
            actual_sha256=actual_sha256,
            generated_at=now,
            compose_attempts=3,
            record_compose_telemetry=True,
        )
    )
    proof = dict(draft["model_compose_proof"] or {})
    receipt = {
        "schema_version": "clara_invoice_copy_taste_pass_receipt_v2",
        "generated_at": now,
        "status": "LIVE_MODEL_COPY_SELECTED_NO_SEND",
        "taste_pass_id": proof.get("taste_pass_id"),
        "subject": draft["subject"],
        "body": draft["body"],
        "recipient": "Accountant@liveartsmd.org",
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
