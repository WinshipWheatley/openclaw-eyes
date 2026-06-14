#!/usr/bin/env python3
"""Export the operator action event journal read-model."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import operator_action_event_journal


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=operator_action_event_journal.DEFAULT_DB_PATH)
    parser.add_argument("--export-root", type=Path, default=operator_action_event_journal.DEFAULT_EXPORT_ROOT)
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args()
    payload, json_path, operator_path = operator_action_event_journal.export_read_model(
        db_path=args.db,
        export_root=args.export_root,
        generated_at=args.generated_at,
    )
    print(
        operator_action_event_journal.stable_json(
            {
                "read_model_id": payload["read_model_id"],
                "json_path": json_path.as_posix(),
                "operator_path": operator_path.as_posix(),
                "event_count_returned": payload["event_count_returned"],
                "pending_operator_intent_count": len(payload["pending_operator_intents"]),
            }
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
