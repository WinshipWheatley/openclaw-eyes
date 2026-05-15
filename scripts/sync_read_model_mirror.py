#!/usr/bin/env python3
"""Machine-aware read-model mirror runner.

Run this from either the Mac backend clone or the PC/WSL backend repo. It
detects the host and delegates to the existing side-specific helper:

- macOS: copy generated read-models to the Mac mirror and drop a manifest.
- PC/WSL: import the returned Mac manifest and report mirror health.
"""

from __future__ import annotations

import argparse
import platform
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from corpus_atlas import stable_json
from read_model_shuttle import DEFAULT_RETURNED_MANIFEST_PATH
from scripts.import_latest_mac_read_model_mirror import (
    format_latest_import_report,
    import_latest_mac_read_model_mirror,
)
from scripts.mac_sync_generated_read_models import (
    MAC_SHARE_ROOT,
    format_sync_report,
    sync_generated_read_models,
)


ENV_MAC = "mac"
ENV_PC_WSL = "pc_wsl"


def detect_environment(
    *,
    platform_name: str | None = None,
    e_drive_root: str | Path = Path("/mnt/e/openclaw"),
) -> str:
    observed = platform_name or platform.system()
    if observed == "Darwin":
        return ENV_MAC
    if observed == "Linux" and Path(e_drive_root).is_dir():
        return ENV_PC_WSL
    raise RuntimeError(
        "Unsupported read-model mirror environment. Expected macOS or Linux/WSL with /mnt/e/openclaw mounted."
    )


def _dry_run_report(
    *,
    environment: str,
    pull: bool,
    require_share: bool,
    manifest_path: Path,
) -> dict[str, Any]:
    if environment == ENV_MAC:
        return {
            "sync_runner_version": "read_model_mirror_auto_runner_v0",
            "status": "dry_run",
            "environment": environment,
            "planned_behavior": "mac_sync_generated_read_models",
            "pull_requested": pull,
            "require_share": require_share,
            "mac_share_root": MAC_SHARE_ROOT.as_posix(),
            "pc_import_not_attempted": True,
            "runtime_authority": False,
            "agent_activation_allowed": False,
            "tool_execution_allowed": False,
            "model_execution_allowed": False,
            "network_authority": False,
        }
    return {
        "sync_runner_version": "read_model_mirror_auto_runner_v0",
        "status": "dry_run",
        "environment": environment,
        "planned_behavior": "import_latest_mac_read_model_mirror",
        "manifest_path": manifest_path.as_posix(),
        "manifest_exists": manifest_path.is_file(),
        "mac_sync_not_attempted": True,
        "runtime_authority": False,
        "agent_activation_allowed": False,
        "tool_execution_allowed": False,
        "model_execution_allowed": False,
        "network_authority": False,
    }


def sync_read_model_mirror(
    *,
    pull: bool = False,
    require_share: bool = False,
    dry_run: bool = False,
    db_path: str | Path | None = None,
    manifest: str | Path = DEFAULT_RETURNED_MANIFEST_PATH,
    platform_name: str | None = None,
    e_drive_root: str | Path = Path("/mnt/e/openclaw"),
) -> dict[str, Any]:
    environment = detect_environment(platform_name=platform_name, e_drive_root=e_drive_root)
    manifest_path = Path(manifest)
    if dry_run:
        return _dry_run_report(
            environment=environment,
            pull=pull,
            require_share=require_share,
            manifest_path=manifest_path,
        )

    if environment == ENV_MAC:
        report = sync_generated_read_models(
            pull=pull,
            require_share=require_share,
            platform_name="Darwin",
        )
        return {
            "sync_runner_version": "read_model_mirror_auto_runner_v0",
            "status": "ok",
            "environment": environment,
            "behavior": "mac_sync_generated_read_models",
            "pc_import_not_attempted": True,
            "mac_sync": report,
        }

    if not manifest_path.is_file():
        return {
            "sync_runner_version": "read_model_mirror_auto_runner_v0",
            "status": "missing_manifest",
            "environment": environment,
            "behavior": "import_latest_mac_read_model_mirror",
            "manifest_path": manifest_path.as_posix(),
            "message": f"Mac generated-read-model manifest is missing: {manifest_path}",
            "mac_sync_not_attempted": True,
            "pc_import_not_attempted": True,
            "runtime_authority": False,
            "agent_activation_allowed": False,
            "tool_execution_allowed": False,
            "model_execution_allowed": False,
            "network_authority": False,
        }

    report = import_latest_mac_read_model_mirror(
        manifest=manifest_path,
        db_path=db_path if db_path is not None else None,
    )
    return {
        "sync_runner_version": "read_model_mirror_auto_runner_v0",
        "status": "ok",
        "environment": environment,
        "behavior": "import_latest_mac_read_model_mirror",
        "mac_sync_not_attempted": True,
        "pc_import": report,
    }


def format_runner_report(payload: dict[str, Any]) -> str:
    lines = [
        "Read-Model Mirror Auto-Runner v0",
        "",
        f"Environment: `{payload['environment']}`",
        f"Status: `{payload['status']}`",
    ]
    if payload.get("status") == "missing_manifest":
        lines.extend(
            [
                f"Manifest: `{payload['manifest_path']}`",
                f"Message: {payload['message']}",
                "",
                "Next safe move:",
                "- Run the unified command on the Mac while `/Volumes/openclaw_e` is mounted, then run it again on PC/WSL.",
            ]
        )
    elif payload.get("behavior") == "mac_sync_generated_read_models":
        lines.extend(["", format_sync_report(payload["mac_sync"])])
    elif payload.get("behavior") == "import_latest_mac_read_model_mirror":
        lines.extend(["", format_latest_import_report(payload["pc_import"])])
    else:
        lines.extend(
            [
                f"Planned behavior: `{payload['planned_behavior']}`",
                f"Pull requested: `{str(payload.get('pull_requested', False)).lower()}`",
                f"Manifest exists: `{str(payload.get('manifest_exists', 'not_applicable')).lower()}`",
            ]
        )
    lines.extend(
        [
            "",
            "Boundary:",
            "- Machine-aware wrapper only; it delegates to existing Mac sync or PC import helpers.",
            "- It does not change Mission Control, generated read-model contracts, runtime, agents, Docker, Ollama, or C-drive paths.",
        ]
    )
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the correct read-model mirror step for this machine.")
    parser.add_argument("--pull", action="store_true", help="On Mac only, run git pull before syncing.")
    parser.add_argument("--require-share", action="store_true", help="On Mac only, fail if /Volumes/openclaw_e is missing.")
    parser.add_argument("--dry-run", action="store_true", help="Detect and report planned behavior without syncing/importing.")
    parser.add_argument(
        "--manifest",
        default=DEFAULT_RETURNED_MANIFEST_PATH.as_posix(),
        help="PC/WSL returned manifest path. Defaults to /mnt/e/openclaw/mac_generated_read_models_manifest.json.",
    )
    parser.add_argument("--db", help="PC/WSL SQLite ledger path. Defaults to Business Ops ledger.")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        payload = sync_read_model_mirror(
            pull=args.pull,
            require_share=args.require_share,
            dry_run=args.dry_run,
            db_path=args.db,
            manifest=args.manifest,
        )
    except RuntimeError as exc:
        payload = {
            "sync_runner_version": "read_model_mirror_auto_runner_v0",
            "status": "error",
            "environment": "unsupported",
            "message": str(exc),
        }
        if args.format == "json":
            print(stable_json(payload), end="")
        else:
            print("Read-Model Mirror Auto-Runner v0")
            print("")
            print(f"Status: `error`")
            print(f"Message: {exc}")
        return 2

    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(format_runner_report(payload))
    return 0 if payload.get("status") != "missing_manifest" else 1


if __name__ == "__main__":
    raise SystemExit(main())
