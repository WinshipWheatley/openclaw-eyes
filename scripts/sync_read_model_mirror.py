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
RUNNER_VERSION = "read_model_mirror_auto_runner_v0_2"
PC_ROOT = Path("/mnt/e/openclaw")
REQUEST_MARKER_PATH = PC_ROOT / "shuttle" / "to_mac" / "read_model_sync_required.json"
NEXT_MAC_COMMAND = (
    "cd ~/Developer/OpenClawBackend/openclaw\n"
    "PYTHONDONTWRITEBYTECODE=1 python3 scripts/sync_read_model_mirror.py --pull --format operator"
)
NEXT_PC_COMMAND = (
    "cd /home/openclaw\n"
    "PYTHONDONTWRITEBYTECODE=1 python3 scripts/sync_read_model_mirror.py --format operator"
)
NO_AUTHORITY_FLAGS = {
    "runtime_authority": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "model_execution_allowed": False,
    "network_authority": False,
    "docker_allowed": False,
    "ollama_allowed": False,
    "remote_control_allowed": False,
    "file_delete_allowed": False,
    "file_move_allowed": False,
}


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
            "sync_runner_version": RUNNER_VERSION,
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
            **NO_AUTHORITY_FLAGS,
        }
    return {
        "sync_runner_version": RUNNER_VERSION,
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
        **NO_AUTHORITY_FLAGS,
    }


def _mirror_health(report: dict[str, Any]) -> dict[str, Any]:
    mirror = report.get("generated_read_model_mirror") or {}
    counts = mirror.get("counts") or {}
    missing_files = list(mirror.get("missing_expected_files") or [])
    extra_files = list(mirror.get("extra_files") or [])
    mismatch_files = list(mirror.get("hash_mismatch_files") or [])
    missing_expected = int(counts.get("missing_expected") or 0)
    extra = int(counts.get("extra") or 0)
    hash_mismatch = int(counts.get("hash_mismatch") or 0)
    if missing_expected > 0 and hash_mismatch > 0:
        status = "needs_mac_sync"
        reason = (
            "Mac generated-read-model mirror is stale: it is missing canonical "
            "backend files and has hash-mismatched files."
        )
    elif hash_mismatch > 0:
        status = "needs_mac_sync"
        reason = "Mac generated-read-model mirror is stale: files differ from backend canonical generated/read_models."
    elif missing_expected > 0:
        status = "needs_mac_sync"
        reason = "Mac generated-read-model folder is behind backend canonical generated/read_models."
    elif extra > 0:
        status = "review_needed"
        reason = "Mac generated-read-model mirror has extra files not present in backend canonical generated/read_models."
    else:
        status = "ok"
        reason = "Mac generated-read-model mirror is current."
    return {
        "status": status,
        "reason": reason,
        "counts": {
            "canonical_expected": int(counts.get("canonical_expected") or 0),
            "observed": int(counts.get("observed") or 0),
            "missing_expected": missing_expected,
            "extra": extra,
            "hash_mismatch": hash_mismatch,
            "matched_hash": int(counts.get("matched_hash") or 0),
        },
        "missing_expected_files": missing_files,
        "extra_files": extra_files,
        "hash_mismatch_files": mismatch_files,
    }


def _write_sync_required_marker(
    *,
    marker_path: str | Path = REQUEST_MARKER_PATH,
    health: dict[str, Any],
) -> str | None:
    path = Path(marker_path)
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    import datetime as _datetime

    marker = {
        "schema_version": "read_model_sync_required_v0",
        "generated_at": _datetime.datetime.now(_datetime.timezone.utc).replace(microsecond=0).isoformat(),
        "reason": health["reason"],
        "missing_expected_files": health.get("missing_expected_files", []),
        "hash_mismatch_files": health.get("hash_mismatch_files", []),
        "requested_by": "pc_wsl_auto_runner",
        "next_expected_responder": "mac_read_model_sync_agent",
        "manual_fallback_mac_command": NEXT_MAC_COMMAND,
        "next_mac_command": NEXT_MAC_COMMAND,
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }
    path.write_text(stable_json(marker), encoding="utf-8")
    return path.as_posix()


def sync_read_model_mirror(
    *,
    pull: bool = False,
    require_share: bool = False,
    dry_run: bool = False,
    db_path: str | Path | None = None,
    manifest: str | Path = DEFAULT_RETURNED_MANIFEST_PATH,
    platform_name: str | None = None,
    e_drive_root: str | Path = Path("/mnt/e/openclaw"),
    request_marker_path: str | Path = REQUEST_MARKER_PATH,
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
        try:
            report = sync_generated_read_models(
                pull=pull,
                require_share=require_share,
                platform_name="Darwin",
            )
        except RuntimeError as exc:
            if "required Mac share is not mounted" not in str(exc):
                raise
            return {
                "sync_runner_version": RUNNER_VERSION,
                "status": "share_missing",
                "environment": environment,
                "behavior": "mac_sync_generated_read_models",
                "pc_import_not_attempted": True,
                "message": str(exc),
                "next_pc_command": NEXT_PC_COMMAND,
                **NO_AUTHORITY_FLAGS,
            }
        share_mounted = bool(report.get("share_mounted"))
        status = "needs_pc_import" if share_mounted else "share_missing"
        return {
            "sync_runner_version": RUNNER_VERSION,
            "status": status,
            "environment": environment,
            "behavior": "mac_sync_generated_read_models",
            "pc_import_not_attempted": True,
            "next_pc_command": NEXT_PC_COMMAND,
            "message": (
                "Mac sync complete; run the unified command on PC/WSL to import the dropped manifest."
                if share_mounted
                else "Mac local sync completed, but /Volumes/openclaw_e is not mounted so PC/WSL cannot import the manifest yet."
            ),
            "mac_sync": report,
            **NO_AUTHORITY_FLAGS,
        }

    if not manifest_path.is_file():
        return {
            "sync_runner_version": RUNNER_VERSION,
            "status": "manifest_missing",
            "environment": environment,
            "behavior": "import_latest_mac_read_model_mirror",
            "manifest_path": manifest_path.as_posix(),
            "message": f"Mac generated-read-model manifest is missing: {manifest_path}",
            "next_mac_command": NEXT_MAC_COMMAND,
            "mac_sync_not_attempted": True,
            "pc_import_not_attempted": True,
            **NO_AUTHORITY_FLAGS,
        }

    report = import_latest_mac_read_model_mirror(
        manifest=manifest_path,
        db_path=db_path if db_path is not None else None,
    )
    health = _mirror_health(report)
    marker_path = None
    if (
        health["status"] == "needs_mac_sync"
        or health["counts"].get("missing_expected", 0) > 0
        or health["counts"].get("hash_mismatch", 0) > 0
    ):
        marker_path = _write_sync_required_marker(
            marker_path=request_marker_path,
            health=health,
        )
    return {
        "sync_runner_version": RUNNER_VERSION,
        "status": health["status"],
        "environment": environment,
        "behavior": "import_latest_mac_read_model_mirror",
        "mirror_health": health,
        "request_marker_path": marker_path,
        "next_mac_command": NEXT_MAC_COMMAND if marker_path else None,
        "next_expected_responder": "mac_read_model_sync_agent" if marker_path else None,
        "mac_sync_not_attempted": True,
        "pc_import": report,
        **NO_AUTHORITY_FLAGS,
    }


def format_runner_report(payload: dict[str, Any]) -> str:
    lines = [
        "Read-Model Mirror Auto-Runner v0.2",
        "",
        f"Environment: `{payload['environment']}`",
        f"Status: `{payload['status']}`",
    ]
    if payload.get("status") == "manifest_missing":
        lines.extend(
            [
                f"Manifest: `{payload['manifest_path']}`",
                f"Message: {payload['message']}",
                "",
                "Next safe move:",
                "- Run this command on the Mac while `/Volumes/openclaw_e` is mounted:",
                "```bash",
                payload["next_mac_command"],
                "```",
            ]
        )
    elif payload.get("behavior") == "mac_sync_generated_read_models":
        lines.extend(["", payload.get("message", ""), "", format_sync_report(payload["mac_sync"])])
        if payload.get("status") == "needs_pc_import":
            lines.extend(
                [
                    "",
                    "Next safe move on PC/WSL:",
                    "```bash",
                    payload["next_pc_command"],
                    "```",
                ]
            )
        elif payload.get("status") == "share_missing":
            lines.extend(
                [
                    "",
                    "Next safe move:",
                    "- Mount `/Volumes/openclaw_e`, rerun the unified command on Mac, then run it on PC/WSL.",
                ]
            )
    elif payload.get("behavior") == "import_latest_mac_read_model_mirror":
        health = payload["mirror_health"]
        counts = health["counts"]
        lines.extend(
            [
                "",
                "Mirror health:",
                f"- canonical_expected={counts['canonical_expected']}",
                f"- observed={counts['observed']}",
                f"- missing_expected={counts['missing_expected']}",
                f"- extra={counts['extra']}",
                f"- hash_mismatch={counts['hash_mismatch']}",
                f"- matched_hash={counts['matched_hash']}",
                f"- reason: {health['reason']}",
            ]
        )
        if payload.get("status") == "needs_mac_sync" and payload.get("request_marker_path"):
            lines.extend(
                [
                    "",
                    "Next safe move:",
                    "- Mac mirror is stale; sync request marker written. Mac LaunchAgent should respond automatically.",
                    f"- Request marker: `{payload['request_marker_path']}`",
                    f"- Expected responder: `{payload.get('next_expected_responder', 'mac_read_model_sync_agent')}`",
                ]
            )
        if health.get("missing_expected_files"):
            lines.extend(["", "Missing expected files:"])
            lines.extend(f"- {item}" for item in health["missing_expected_files"])
        if health.get("extra_files"):
            lines.extend(["", "Extra files needing review:"])
            lines.extend(f"- {item}" for item in health["extra_files"])
        if health.get("hash_mismatch_files"):
            lines.extend(["", "Hash mismatch files:"])
            lines.extend(f"- {item}" for item in health["hash_mismatch_files"])
        if payload.get("status") == "needs_mac_sync":
            lines.extend(
                [
                    "",
                    "Manual fallback only:",
                    "```bash",
                    payload.get("next_mac_command") or NEXT_MAC_COMMAND,
                    "```",
                ]
            )
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
            "sync_runner_version": RUNNER_VERSION,
            "status": "error",
            "environment": "unsupported",
            "message": str(exc),
        }
        if args.format == "json":
            print(stable_json(payload), end="")
        else:
            print("Read-Model Mirror Auto-Runner v0.2")
            print("")
            print(f"Status: `error`")
            print(f"Message: {exc}")
        return 2

    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(format_runner_report(payload))
    return 0 if payload.get("status") in {"ok", "needs_pc_import", "mac_sync_complete", "dry_run"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
