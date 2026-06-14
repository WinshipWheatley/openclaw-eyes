#!/usr/bin/env python3
"""Export the reusable simple-invoice Event Bridge rail registry read-model."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import simple_invoice_event_bridge_rail_registry as registry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-root", type=Path, default=registry.DEFAULT_EXPORT_ROOT)
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args(argv)

    payload, json_path, operator_path = registry.export_simple_invoice_event_bridge_rail_registry(
        export_root=args.export_root,
        generated_at=args.generated_at,
    )
    print(
        registry.stable_json(
            {
                "read_model_id": payload["read_model_id"],
                "rail_ref": payload["rail_ref"],
                "json_path": json_path.as_posix(),
                "operator_path": operator_path.as_posix(),
                "client_count": payload["machine_proof"]["client_count"],
                "all_simple_clients_use_generic_rail": payload["machine_proof"][
                    "all_simple_clients_use_generic_rail"
                ],
                "no_live_actions_performed": payload["machine_proof"]["pdf_export_performed"] is False,
            }
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
