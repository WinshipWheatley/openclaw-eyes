#!/usr/bin/env python3
"""Run one external-LM shadow adapter proof from a compiled safe package."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import external_lm_safe_package_compiler
import external_lm_shadow_adapter


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the external LM shadow adapter in proof mode.")
    parser.add_argument("--lane", choices=("LM1", "LM2"), default="LM1")
    parser.add_argument("--db-path", type=Path, default=external_lm_shadow_adapter.DEFAULT_DB_PATH)
    parser.add_argument("--local-fallback-smoke", action="store_true")
    parser.add_argument(
        "--message",
        default="what's next for the Capital Hilton invoice?",
        help="Fixture operator message used to compile the safe package.",
    )
    args = parser.parse_args(argv)

    if args.lane == "LM1":
        compile_result = external_lm_safe_package_compiler.compile_lm1_safe_package(
            {
                "source_request_id": "external_lm_shadow_cli_lm1",
                "user_message": args.message,
                "world_ref": "finance",
                "client_ref": "capital_hilton",
                "workflow_ref": "capital_hilton_invoice_workflow",
                "file_display_name": "Invoice Capitol Hilton Running.xlsx",
                "artifact_kind": "running_invoice_workbook",
            }
        )
    else:
        compile_result = external_lm_safe_package_compiler.compile_lm2_safe_package(
            {
                "source_request_id": "external_lm_shadow_cli_lm2",
                "package_id": "role_package:external_lm_shadow_cli_lm2",
                "role_identity": "CASSANDRA_CLARA",
                "task": "Draft client-safe invoice package wording for Capital Hilton; do not send.",
                "world_ref": "finance",
                "client_ref": "capital_hilton",
                "workflow_ref": "capital_hilton_invoice_workflow",
                "privacy_level": "CLIENT_FINANCE_FILE_METADATA",
                "tokenization_applied": True,
                "raw_values_included": False,
                "tool_policy": {"allowed_tools": (), "forbidden_tools": ("gmail", "browser", "ledger_writer")},
                "authority_policy": {
                    "tool_authority_granted": False,
                    "external_action_authority_granted": False,
                    "send_submit_authority_granted": False,
                },
            }
        )

    result = external_lm_shadow_adapter.run_external_lm_shadow(
        compile_result,
        db_path=args.db_path,
        provider_config={"allow_local_fallback_smoke": args.local_fallback_smoke},
        local_fallback_smoke=args.local_fallback_smoke,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "lane": result["lane"],
                "model_class": result["model_class"],
                "provider_ref": result["provider_ref"],
                "gate_verdict": result["gate_verdict"],
                "shadow_only": result["shadow_only"],
                "production_authority": result["production_authority"],
                "sqlite_db_path": result["sqlite_db_path"],
                "run_id": result["run_id"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
