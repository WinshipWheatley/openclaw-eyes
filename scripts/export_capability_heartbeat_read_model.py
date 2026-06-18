#!/usr/bin/env python3
"""Export the capability heartbeat read-model artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.probe_capability_heartbeat import (
    DEFAULT_LIVE_ROOT,
    DEFAULT_REGISTRY_PATH,
    build_report,
    format_operator,
    stable_json,
)


JSON_EXPORT_NAME = "capability_heartbeat.json"
OPERATOR_EXPORT_NAME = "capability_heartbeat_OPERATOR.md"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
EXPORT_VERSION = "capability_heartbeat_export_v0"


def _export_root_path(export_root: str | Path) -> Path:
    path = Path(export_root)
    if path.is_absolute():
        return path
    return ROOT / path


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def export_capability_heartbeat_read_model(
    *,
    registry_path: Path = DEFAULT_REGISTRY_PATH,
    live_root: Path = DEFAULT_LIVE_ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
    check: bool = False,
) -> dict[str, Any]:
    root = _export_root_path(export_root)
    report = build_report(
        registry_path,
        live_root=live_root,
        generated_at=generated_at,
    )
    operator = format_operator(report)
    json_text = stable_json(report)

    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    expected = {
        json_path: json_text,
        operator_path: operator,
    }

    stale_exports: list[str] = []
    if check:
        for path, text in expected.items():
            if not path.is_file() or path.read_text(encoding="utf-8") != text:
                stale_exports.append(path.as_posix())
    else:
        root.mkdir(parents=True, exist_ok=True)
        for path, text in expected.items():
            path.write_text(text, encoding="utf-8")

    return {
        "export_version": EXPORT_VERSION,
        "schema_version": report["schema_version"],
        "generated_at": report["generated_at"],
        "registry_path": report["registry_path"],
        "live_root": report["live_root"],
        "export_root": root.as_posix(),
        "json_path": json_path.as_posix(),
        "operator_path": operator_path.as_posix(),
        "capability_count": report["capability_count"],
        "live_status_counts": report["live_status_counts"],
        "drift_count": report["drift_count"],
        "drift_capabilities": report["drift_capabilities"],
        "check_mode": check,
        "check_status": "stale" if stale_exports else "current",
        "stale_exports": stale_exports,
        "read_only_probe": True,
        "runtime_authority": False,
        "service_mutations": False,
        "send_or_dispatch_calls": False,
        "external_writes": False,
        "install_or_enable_performed": False,
        "exports": [
            {
                "artifact_id": "capability_heartbeat",
                "format": "json",
                "path": json_path.as_posix(),
                "relative_path": _display_path(json_path),
            },
            {
                "artifact_id": "capability_heartbeat_operator",
                "format": "operator_markdown",
                "path": operator_path.as_posix(),
                "relative_path": _display_path(operator_path),
            },
        ],
    }


def format_summary(summary: dict[str, Any]) -> str:
    lines = [
        "# Capability Heartbeat Export",
        "",
        f"Evidence: exported `{summary['json_path']}` and `{summary['operator_path']}`.",
        (
            "Boundary: read-only live probes only; no service mutation, install, enable, "
            "restart, send, or dispatch."
        ),
        f"Status: {summary['capability_count']} capabilities; drift_count={summary['drift_count']}.",
        f"Live status counts: {summary['live_status_counts']}",
        (
            "Drift capabilities: "
            + (", ".join(summary["drift_capabilities"]) if summary["drift_capabilities"] else "none")
        ),
        "Next safe move: Opus reviews the branch and decides whether to install the proposed timer.",
    ]
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY_PATH)
    parser.add_argument("--live-root", type=Path, default=DEFAULT_LIVE_ROOT)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--generated-at", help="Optional fixed timestamp for deterministic tests.")
    parser.add_argument("--check", action="store_true", help="Check whether exports are current without writing.")
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    summary = export_capability_heartbeat_read_model(
        registry_path=args.registry,
        live_root=args.live_root,
        export_root=args.export_root,
        generated_at=args.generated_at,
        check=args.check,
    )
    if args.format == "json":
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(format_summary(summary), end="")
    return 1 if args.check and summary["check_status"] != "current" else 0


if __name__ == "__main__":
    raise SystemExit(main())
