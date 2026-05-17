#!/usr/bin/env python3
"""Export Cassandra date-awareness proof and redacted wrong-date scan."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "generated" / "read_models" / "cassandra_date_awareness.json"
OUT_OPERATOR = ROOT / "generated" / "read_models" / "cassandra_date_awareness_OPERATOR.md"

import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cassandra_date_awareness import (  # noqa: E402
    build_authoritative_date_context,
    resolve_relative_date_phrase,
    scan_wrong_date_correspondence,
)


def build_read_model() -> dict[str, Any]:
    now = datetime.now().astimezone()
    phrases = (
        "today",
        "yesterday",
        "tomorrow",
        "this friday",
        "last thursday",
        "next week",
        "last week",
        "next month",
        "last month",
        "next year",
        "last year",
    )
    scan = scan_wrong_date_correspondence()
    return {
        "schema_version": "cassandra_date_awareness_v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "runtime_authority_changed": False,
        "send_authority_added": False,
        "reply_authority_added": False,
        "correction_sent": False,
        "tokens_exposed": False,
        "raw_chat_ids_exposed": False,
        "raw_private_content_included": False,
        "system_date": now.date().isoformat(),
        "system_weekday": now.strftime("%A"),
        "authoritative_date_context": build_authoritative_date_context(now=now),
        "relative_date_resolutions": [resolve_relative_date_phrase(phrase, now=now).as_dict() for phrase in phrases],
        "root_cause": (
            "Cassandra had only limited temporal anchors and no deterministic direct-answer path for "
            "explicit relative-date questions, allowing stale model memory to answer dates."
        ),
        "fix_summary": [
            "Added deterministic relative-date resolution for common operator phrases.",
            "Added direct date-awareness answers before LLM fallback.",
            "Inserted authoritative system/operator date context before persona/prompt text.",
            "Scanned targeted Cassandra correspondence/log files for known stale wrong-date signatures without emitting raw content.",
        ],
        "wrong_date_scan": scan,
        "wrong_date_correspondence_found": bool(scan.get("wrong_date_correspondence_found")),
        "recommended_correction": (
            "Review the redacted match metadata and prepare a manual correction note if needed."
            if scan.get("wrong_date_correspondence_found")
            else "No visible wrong-date correspondence matching June 24, 2024 signatures was found in the targeted scan."
        ),
        "next_safe_move": "Cassandra Intake-to-Work Packet Live Proof v0",
    }


def render_operator(model: dict[str, Any]) -> str:
    scan = model["wrong_date_scan"]
    lines = [
        "# Cassandra Date Awareness v0",
        "",
        f"Status: fixed. System date used: `{model['system_date']}` ({model['system_weekday']}).",
        "",
        "## What Changed",
        "- Cassandra now has deterministic answers for common relative-date questions.",
        "- The authoritative date context is placed before persona/prompt text.",
        "- Model memory is explicitly not allowed to decide current dates.",
        "",
        "## Relative Date Proof",
    ]
    for item in model["relative_date_resolutions"]:
        lines.append(f"- `{item['phrase']}` -> {item['label']}")
    lines.extend(
        [
            "",
            "## Wrong-Date Correspondence Scan",
            f"- Targeted files scanned: `{len(scan['scanned_files'])}`.",
            f"- Wrong-date matches found: `{scan['wrong_date_match_count']}`.",
            "- Raw content included: `false`.",
            "- Correction sent: `false`.",
            "",
        ]
    )
    if scan["matches"]:
        lines.append("Redacted match metadata:")
        for item in scan["matches"]:
            lines.append(
                f"- `{Path(item['path']).name}` line `{item['line_number']}` "
                f"timestamp=`{item['timestamp'] or 'unknown'}` route=`{item['route'] or 'unknown'}`"
            )
    else:
        lines.append("No visible recent correspondence matching `June 24, 2024` / `2024-06-24` signatures was found.")
    lines.extend(
        [
            "",
            "## Boundaries",
            "- No Telegram messages were sent.",
            "- No replies were enabled.",
            "- No tokens, raw chat IDs, secrets, env values, or raw private content were included.",
            "- Runtime authority did not change.",
            "",
            "## Next Safe Move",
            f"- {model['next_safe_move']}",
        ]
    )
    return "\n".join(lines) + "\n"


def write_outputs(model: dict[str, Any]) -> None:
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(model, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUT_OPERATOR.write_text(render_operator(model), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=("json", "operator"), required=True)
    args = parser.parse_args()

    model = build_read_model()
    write_outputs(model)
    if args.format == "json":
        print(json.dumps(model, indent=2, sort_keys=True))
    else:
        print(render_operator(model), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
