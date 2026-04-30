from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cassandra_email_triage import build_email_triage_operator_display


DEMO_CREATED_AT = "2026-04-30 12:00:00"

SYNTHETIC_MESSAGES = [
    {
        "message_id": "demo-prior-newsletter-001",
        "thread_id": "demo-prior-thread-001",
        "from_name": "Studio Deals",
        "from_email": "Studio Deals <deals@example.com>",
        "subject": "Newsletter sale already classified",
        "snippet": "Synthetic metadata preview for a previously reviewed promotion.",
        "labels": ["INBOX", "CATEGORY_PROMOTIONS"],
    },
    {
        "message_id": "demo-newsletter-002",
        "thread_id": "demo-thread-002",
        "from_name": "Gear Digest",
        "from_email": "Gear Digest <digest@example.com>",
        "subject": "Weekly newsletter sale on cases",
        "snippet": "Synthetic metadata preview with a discount code and unsubscribe footer.",
        "labels": ["INBOX", "UNREAD", "CATEGORY_PROMOTIONS"],
    },
    {
        "message_id": "demo-payment-003",
        "thread_id": "demo-thread-003",
        "from_name": "Vendor Desk",
        "from_email": "Vendor Desk <vendor@example.com>",
        "subject": "Vendor invoice update",
        "snippet": "Synthetic metadata preview for a higher-risk business item.",
        "labels": ["INBOX"],
    },
]

SYNTHETIC_PRIOR_RECORDS = [
    {
        "message_id": "demo-prior-newsletter-001",
        "thread_id": "demo-prior-thread-001",
        "operator_classification": "promotional",
        "future_suggested_handling": "suggest_folder_or_label",
        "source_capability": "google.gmail.read.metadata",
    }
]


def build_demo_display() -> dict:
    return build_email_triage_operator_display(
        SYNTHETIC_MESSAGES,
        SYNTHETIC_PRIOR_RECORDS,
        created_at=DEMO_CREATED_AT,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show a mocked Cassandra email triage dry-run display.")
    parser.add_argument("--json", action="store_true", help="Print the display payload as JSON.")
    args = parser.parse_args(argv)

    display = build_demo_display()
    if args.json:
        print(json.dumps(display, indent=2, sort_keys=True))
    else:
        print(display["display_text"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())