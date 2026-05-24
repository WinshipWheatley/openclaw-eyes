#!/usr/bin/env python3
"""Mac-side generated read-model mirror sync helper.

Run this from the backend clone on macOS. It copies safe generated read-model
files into the Mac mirror folder, builds the Mac generated-read-model manifest,
and drops the manifest/report onto the E-drive share when mounted.
"""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from corpus_atlas import stable_json
from generated_read_model_files import (
    MISSION_CONTROL_CAPTURE_INTAKE_READ_MODEL_FILES,
    MISSION_CONTROL_REVIEW_PACKET_READ_MODEL_FILES,
)
from read_model_shuttle import (
    DEFAULT_MAC_DESTINATION_ROOT,
    build_mac_generated_read_model_manifest,
    iter_safe_generated_read_models,
)


MAC_SHARE_ROOT = Path("/Volumes/openclaw_e")
DEFAULT_LOCAL_MANIFEST_PATH = Path("~/Desktop/openclaw_mac_manifests/mac_generated_read_models_manifest.json")
DEFAULT_SHARE_MANIFEST_PATH = MAC_SHARE_ROOT / "mac_generated_read_models_manifest.json"
DEFAULT_SHARE_REPORT_PATH = MAC_SHARE_ROOT / "shuttle" / "from_mac" / "read_model_sync_latest.json"
KEY_READ_MODEL_FILES = (
    "operator_actions.json",
    "agent_lanes.json",
    "project_capsules.json",
    "report_bridge.json",
    "context_selection.json",
    *MISSION_CONTROL_REVIEW_PACKET_READ_MODEL_FILES,
    *MISSION_CONTROL_CAPTURE_INTAKE_READ_MODEL_FILES,
)


def sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_mac_platform(platform_name: str | None = None) -> None:
    observed = platform_name or platform.system()
    if observed != "Darwin":
        raise RuntimeError(
            "mac_sync_generated_read_models.py must run on macOS from the backend clone"
        )


def run_git_pull(repo_root: Path) -> dict[str, Any]:
    result = subprocess.run(
        ["git", "pull", "origin", "main"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=120,
        shell=False,
    )
    return {
        "command": "git pull origin main",
        "exit_code": result.returncode,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-4000:],
    }


def _display_path(path: Path) -> str:
    return path.expanduser().as_posix()


def _copy_read_models(source_root: Path, destination_root: Path) -> tuple[dict[str, Any], ...]:
    destination_root.mkdir(parents=True, exist_ok=True)
    copied: list[dict[str, Any]] = []
    for source_path in iter_safe_generated_read_models(source_root):
        destination_path = destination_root / source_path.name
        shutil.copy2(source_path, destination_path)
        source_hash = sha256_file(source_path)
        copied_hash = sha256_file(destination_path)
        if copied_hash != source_hash:
            raise RuntimeError(f"hash mismatch after copy: {source_path.name}")
        copied.append(
            {
                "relative_path": source_path.name,
                "source_path": source_path.as_posix(),
                "destination_path": destination_path.as_posix(),
                "size_bytes": destination_path.stat().st_size,
                "sha256": copied_hash,
            }
        )
    return tuple(copied)


def sync_generated_read_models(
    *,
    repo_root: str | Path = ROOT,
    destination_root: str | Path = DEFAULT_MAC_DESTINATION_ROOT,
    local_manifest_path: str | Path = DEFAULT_LOCAL_MANIFEST_PATH,
    share_root: str | Path = MAC_SHARE_ROOT,
    pull: bool = False,
    require_share: bool = False,
    platform_name: str | None = None,
) -> dict[str, Any]:
    validate_mac_platform(platform_name)
    repo = Path(repo_root).expanduser().resolve()
    source_root = repo / "generated" / "read_models"
    if not source_root.is_dir():
        raise RuntimeError(f"generated read-model source root is missing: {source_root}")

    git_pull_result = run_git_pull(repo) if pull else None
    if git_pull_result and git_pull_result["exit_code"] != 0:
        raise RuntimeError(f"git pull failed: {git_pull_result['stderr']}")

    destination = Path(destination_root).expanduser().resolve()
    copied = _copy_read_models(source_root, destination)

    local_manifest = Path(local_manifest_path).expanduser()
    manifest = build_mac_generated_read_model_manifest(
        destination_root=destination,
        output=local_manifest,
    )
    manifest_hash = sha256_file(local_manifest)
    share = Path(share_root)
    share_mounted = share.is_dir()
    share_manifest_path: str | None = None
    share_report_path: str | None = None

    if require_share and not share_mounted:
        raise RuntimeError(f"required Mac share is not mounted: {share}")

    key_files_present = {
        name: (destination / name).is_file()
        for name in KEY_READ_MODEL_FILES
    }
    report = {
        "sync_version": "read_model_mirror_automation_v0",
        "repo_root": repo.as_posix(),
        "source_root": source_root.as_posix(),
        "destination_root": destination.as_posix(),
        "copied_count": len(copied),
        "copied_files": list(copied),
        "local_manifest_path": _display_path(local_manifest),
        "manifest_size_bytes": local_manifest.stat().st_size,
        "manifest_sha256": manifest_hash,
        "pc_drop_written": False,
        "pc_drop_manifest_path": None,
        "pc_drop_report_path": None,
        "share_mounted": share_mounted,
        "key_files_present": key_files_present,
        "manifest_path_count": len(manifest.get("path_records", [])),
        "git_pull": git_pull_result,
        "runtime_authority": False,
        "agent_activation_allowed": False,
        "tool_execution_allowed": False,
        "model_execution_allowed": False,
        "network_authority": False,
        "launchd_installed": False,
        "files_deleted": False,
        "files_moved": False,
    }

    if share_mounted:
        share_manifest = share / "mac_generated_read_models_manifest.json"
        share_manifest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local_manifest, share_manifest)
        share_report = share / "shuttle" / "from_mac" / "read_model_sync_latest.json"
        share_report.parent.mkdir(parents=True, exist_ok=True)
        share_manifest_path = share_manifest.as_posix()
        share_report_path = share_report.as_posix()
        report["pc_drop_written"] = True
        report["pc_drop_manifest_path"] = share_manifest_path
        report["pc_drop_report_path"] = share_report_path
        report["share_manifest_path"] = share_manifest_path
        report["share_report_path"] = share_report_path
        share_report.write_text(stable_json(report), encoding="utf-8")
    else:
        report["share_manifest_path"] = share_manifest_path
        report["share_report_path"] = share_report_path
    return report


def format_sync_report(report: dict[str, Any]) -> str:
    key_lines = [
        f"- {name}: {'present' if present else 'missing'}"
        for name, present in sorted(report["key_files_present"].items())
    ]
    lines = [
        "Mac Generated Read-Model Sync v0",
        "",
        f"Copied files: {report['copied_count']}",
        f"Destination: `{report['destination_root']}`",
        f"Manifest: `{report['local_manifest_path']}`",
        f"Manifest sha256: `{report['manifest_sha256']}`",
        f"PC drop written: `{str(report['pc_drop_written']).lower()}`",
    ]
    if report["pc_drop_manifest_path"]:
        lines.append(f"PC drop manifest: `{report['pc_drop_manifest_path']}`")
    if not report["share_mounted"]:
        lines.append("PC drop skipped: `/Volumes/openclaw_e` is not mounted.")
    lines.extend(["", "Key files:", *key_lines, "", "Boundary:"])
    lines.append("- Local sync and metadata manifest only; no launchd, SSH, SCP, rsync, runtime, agents, Docker, Ollama, or Mission Control edits.")
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync generated read-models into the Mac mirror folder.")
    parser.add_argument("--pull", action="store_true", help="Run git pull origin main before copying.")
    parser.add_argument("--require-share", action="store_true", help="Fail if /Volumes/openclaw_e is not mounted.")
    parser.add_argument("--repo-root", default=ROOT.as_posix(), help="Backend repo root.")
    parser.add_argument("--destination-root", default=DEFAULT_MAC_DESTINATION_ROOT, help="Mac generated read-model destination.")
    parser.add_argument("--local-manifest-path", default=DEFAULT_LOCAL_MANIFEST_PATH.as_posix(), help="Local Mac manifest output path.")
    parser.add_argument("--share-root", default=MAC_SHARE_ROOT.as_posix(), help="Mounted E-drive share root.")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    report = sync_generated_read_models(
        repo_root=args.repo_root,
        destination_root=args.destination_root,
        local_manifest_path=args.local_manifest_path,
        share_root=args.share_root,
        pull=args.pull,
        require_share=args.require_share,
    )
    if args.format == "json":
        print(stable_json(report), end="")
    else:
        print(format_sync_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
