#!/usr/bin/env python3
"""Export the OpenClaw hot-path event bridge contract read-model."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import openclaw_event_bridge_contract as contract


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-root", type=Path, default=contract.DEFAULT_EXPORT_ROOT)
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args()

    payload, json_path, operator_path = contract.export_openclaw_event_bridge_contract(
        export_root=args.export_root,
        generated_at=args.generated_at,
    )
    print(
        contract.stable_json(
            {
                "read_model_id": payload["read_model_id"],
                "json_path": json_path.as_posix(),
                "operator_path": operator_path.as_posix(),
                "registered_workflow_action_count": len(payload["registered_workflow_actions"]),
                "mac_telegram_payload_parity": payload["machine_proof"][
                    "mac_and_telegram_same_workflow_payload_shape"
                ],
                "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
            }
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
