#!/usr/bin/env python3
"""Export operator planning ready packets into generated read-models.

The Mac read-model mirror only copies safe top-level files from
``generated/read_models``. These planning packets are authored in
``docs/operations`` but are useful to Mission Control as read-only posture.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from corpus_atlas import stable_json


PACKET_EXPORTS: tuple[tuple[str, str], ...] = (
    (
        "docs/operations/OPENCLAW_REMAINING_WORK_STRATIFIER_READY_PACKET.json",
        "OPENCLAW_REMAINING_WORK_STRATIFIER_READY_PACKET.json",
    ),
    (
        "docs/operations/OPENCLAW_CRITICAL_PATH_EXECUTION_PACKET_READY.json",
        "OPENCLAW_CRITICAL_PATH_EXECUTION_PACKET_READY.json",
    ),
)


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"ready packet must be a JSON object: {path}")
    return payload


def export_operator_planning_ready_packets(
    *,
    export_root: str | Path = "generated/read_models",
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(repo_root or ROOT)
    destination_root = root / export_root if not Path(export_root).is_absolute() else Path(export_root)
    destination_root.mkdir(parents=True, exist_ok=True)

    exports: list[dict[str, Any]] = []
    for source_relative, destination_name in PACKET_EXPORTS:
        source_path = root / source_relative
        if not source_path.is_file():
            raise FileNotFoundError(f"planning ready packet is missing: {source_path}")
        payload = _load_json_object(source_path)
        destination_path = destination_root / destination_name
        destination_path.write_text(stable_json(payload), encoding="utf-8")
        exports.append(
            {
                "source_path": source_relative,
                "path": destination_path.as_posix(),
                "relative_path": destination_name,
                "schema_version": payload.get("schema_version"),
                "runtime_authority_changed": payload.get("runtime_authority_changed", False),
                "data_imported": payload.get("data_imported", False),
            }
        )

    return {
        "schema_version": "operator_planning_ready_packet_exports_v0",
        "export_root": destination_root.as_posix(),
        "exports": exports,
        "exported_count": len(exports),
        "runtime_authority_changed": False,
        "data_imported": False,
        "app_changes_made": False,
    }


def format_export_summary(summary: dict[str, Any]) -> str:
    lines = [
        "Operator Planning Ready Packet Export v0",
        "",
        f"Export root: `{summary['export_root']}`",
        f"Exported count: {summary['exported_count']}",
        "",
        "Exports:",
    ]
    for item in summary["exports"]:
        lines.append(f"- `{item['relative_path']}` from `{item['source_path']}`")
    lines.extend(
        [
            "",
            "Boundary:",
            "- Generated read-model posture only; no Mission Control app edits, runtime authority, data import, or sync-path change.",
        ]
    )
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export docs/operations planning ready packets into generated/read_models."
    )
    parser.add_argument(
        "--export-root",
        default="generated/read_models",
        help="Generated read-model export root.",
    )
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    summary = export_operator_planning_ready_packets(export_root=args.export_root)
    if args.format == "json":
        print(stable_json(summary), end="")
    else:
        print(format_export_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
