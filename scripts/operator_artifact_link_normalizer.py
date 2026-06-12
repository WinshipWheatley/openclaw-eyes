#!/usr/bin/env python3
"""Normalize operator-facing artifact links.

Workers sometimes create useful reports in WSL or tool-private cache paths that
the current operator UI cannot open. This helper copies intended operator
artifacts into a shared report folder and writes a small manifest with WSL,
Windows, URI, and open-instruction variants.

This is local artifact handling only. It does not call external APIs, move or
delete originals, inspect secrets, mutate business systems, or grant authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


PREFERRED_OPERATOR_REPORT_ROOT = Path("/mnt/e/OpenClaw_Operator_Reports")
FALLBACK_OPERATOR_REPORT_ROOT = Path("/tmp/openclaw-mission-control/operator_reports")
MANIFEST_NAME = "artifact_manifest.json"
OPEN_ME_NAME = "OPEN_ME.md"

UNSAFE_PATH_TERMS = (
    ".chief.env",
    ".google-secrets",
    "credential",
    "credentials",
    "password",
    "private_key",
    "secret",
    "secrets",
    "token",
    "tokens",
    "api_key",
)


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_task_id(task_id: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in str(task_id or "").strip())
    return cleaned.strip("._") or "operator_artifact"


def _source_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _looks_unsafe_to_export(path: str | Path) -> bool:
    normalized = str(path).lower().replace("\\", "/")
    return any(term in normalized for term in UNSAFE_PATH_TERMS)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def windows_path_for_wsl_path(path: str | Path) -> str:
    """Return a Windows-openable path for a WSL path when possible."""

    source = _source_path(path)
    parts = source.parts
    if len(parts) >= 4 and parts[0] == "/" and parts[1] == "mnt" and len(parts[2]) == 1:
        drive = parts[2].upper()
        rest = "\\".join(parts[3:])
        return f"{drive}:\\{rest}" if rest else f"{drive}:\\"

    try:
        result = subprocess.run(
            ["wslpath", "-w", source.as_posix()],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        result = None
    if result is not None and result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()

    distro = os.environ.get("WSL_DISTRO_NAME") or "Ubuntu"
    return "\\\\wsl.localhost\\" + distro + source.as_posix().replace("/", "\\")


def normalize_artifact_path(path: str | Path) -> dict[str, Any]:
    source = _source_path(path)
    exists = source.is_file()
    unsafe = _looks_unsafe_to_export(source)
    blocked_reason = ""
    if unsafe:
        blocked_reason = "path_looks_like_secret_or_credential_material"
    elif not source.exists():
        blocked_reason = "source_file_missing"
    elif not source.is_file():
        blocked_reason = "source_is_not_a_regular_file"
    return {
        "source_path": source.as_posix(),
        "exists": exists,
        "safe_to_export": bool(exists and not unsafe),
        "blocked_reason": blocked_reason,
        "wsl_path": source.as_posix(),
        "windows_path": windows_path_for_wsl_path(source),
        "file_uri": source.as_uri() if source.is_absolute() else "",
        "operator_copy_path": "",
        "operator_copy_windows_path": "",
        "open_instructions": [],
    }


def _operator_root(report_root: str | Path | None = None) -> Path:
    if report_root is not None:
        return Path(report_root)
    if Path("/mnt/e").is_dir():
        return PREFERRED_OPERATOR_REPORT_ROOT
    return FALLBACK_OPERATOR_REPORT_ROOT


def _destination_path(source: Path, destination_dir: Path) -> Path:
    candidate = destination_dir / source.name
    if not candidate.exists():
        return candidate
    source_hash = _sha256_file(source)
    try:
        if candidate.is_file() and _sha256_file(candidate) == source_hash:
            return candidate
    except OSError:
        pass
    suffix = source.suffix
    stem = source.stem
    short_hash = source_hash[:10]
    for index in range(0, 100):
        disambiguator = short_hash if index == 0 else f"{short_hash}_{index}"
        hashed_candidate = destination_dir / f"{stem}_{disambiguator}{suffix}"
        if not hashed_candidate.exists():
            return hashed_candidate
        try:
            if hashed_candidate.is_file() and _sha256_file(hashed_candidate) == source_hash:
                return hashed_candidate
        except OSError:
            continue
    raise FileExistsError(f"could not create non-conflicting operator artifact path for {source.name}")


def _open_instructions(entry: Mapping[str, Any]) -> list[str]:
    instructions = []
    if entry.get("operator_copy_windows_path"):
        instructions.append(f"Open from Windows: {entry['operator_copy_windows_path']}")
    if entry.get("operator_copy_path"):
        instructions.append(f"Open from WSL: {entry['operator_copy_path']}")
    if entry.get("windows_path"):
        instructions.append(f"Original Windows path, if accessible: {entry['windows_path']}")
    if entry.get("wsl_path"):
        instructions.append(f"Original WSL path: {entry['wsl_path']}")
    return instructions


def maybe_copy_to_operator_reports(
    path: str | Path,
    task_id: str,
    *,
    report_root: str | Path | None = None,
) -> dict[str, Any]:
    entry = normalize_artifact_path(path)
    if not entry["safe_to_export"]:
        entry["operator_copy_blocked"] = True
        entry["open_instructions"] = [
            f"Artifact was not copied: {entry['blocked_reason']}.",
            f"Source path checked: {entry['source_path']}",
        ]
        return entry

    source = Path(entry["source_path"])
    destination_dir = _operator_root(report_root) / _safe_task_id(task_id)
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = _destination_path(source, destination_dir)
    if not destination.exists():
        shutil.copy2(source, destination)

    entry.update(
        {
            "operator_copy_blocked": False,
            "operator_copy_path": destination.as_posix(),
            "operator_copy_windows_path": windows_path_for_wsl_path(destination),
            "operator_copy_file_uri": destination.as_uri(),
            "operator_report_dir": destination_dir.as_posix(),
            "operator_report_windows_dir": windows_path_for_wsl_path(destination_dir),
        }
    )
    entry["open_instructions"] = _open_instructions(entry)
    return entry


def write_operator_artifact_manifest(
    entries: Sequence[Mapping[str, Any]],
    *,
    task_id: str,
    report_dir: str | Path,
    description: str = "",
    manifest_name: str = MANIFEST_NAME,
) -> Path:
    report_dir = Path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "operator_artifact_manifest_v0",
        "task_id": _safe_task_id(task_id),
        "generated_at_utc": utc_now(),
        "description": description,
        "artifact_count": len(entries),
        "artifacts": [dict(entry) for entry in entries],
        "safety": {
            "external_api_called": False,
            "originals_moved": False,
            "originals_deleted": False,
            "secret_like_paths_exported": False,
        },
    }
    path = report_dir / manifest_name
    path.write_text(stable_json(payload), encoding="utf-8")
    return path


def render_operator_links(entries: Sequence[Mapping[str, Any]], *, task_id: str, description: str = "") -> str:
    lines = [
        f"# OpenClaw Operator Artifact Links: {_safe_task_id(task_id)}",
        "",
    ]
    if description:
        lines.extend([description, ""])
    lines.extend(
        [
            "Safety note: the original artifact was copied, not moved. Originals remain in place.",
            "",
        ]
    )
    for index, entry in enumerate(entries, start=1):
        lines.extend(
            [
                f"## Artifact {index}",
                "",
                f"- Source WSL path: `{entry.get('wsl_path', '')}`",
                f"- Source Windows path: `{entry.get('windows_path', '')}`",
                f"- Operator copy WSL path: `{entry.get('operator_copy_path', '')}`",
                f"- Operator copy Windows path: `{entry.get('operator_copy_windows_path', '')}`",
                f"- File URI: `{entry.get('file_uri', '')}`",
                "",
                "Open instructions:",
            ]
        )
        instructions = entry.get("open_instructions") or []
        if instructions:
            lines.extend(f"- {instruction}" for instruction in instructions)
        else:
            lines.append("- No openable copy was created.")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_open_me(
    entries: Sequence[Mapping[str, Any]],
    *,
    task_id: str,
    report_dir: str | Path,
    description: str = "",
) -> Path:
    report_dir = Path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / OPEN_ME_NAME
    path.write_text(render_operator_links(entries, task_id=task_id, description=description), encoding="utf-8")
    return path


def export_operator_artifact(
    source_path: str | Path,
    *,
    task_id: str,
    description: str = "",
    report_root: str | Path | None = None,
) -> dict[str, Any]:
    entry = maybe_copy_to_operator_reports(source_path, task_id, report_root=report_root)
    report_dir = Path(entry.get("operator_report_dir") or (_operator_root(report_root) / _safe_task_id(task_id)))
    manifest = write_operator_artifact_manifest([entry], task_id=task_id, report_dir=report_dir, description=description)
    open_me = write_open_me([entry], task_id=task_id, report_dir=report_dir, description=description)
    entry["manifest_path"] = manifest.as_posix()
    entry["manifest_windows_path"] = windows_path_for_wsl_path(manifest)
    entry["open_me_path"] = open_me.as_posix()
    entry["open_me_windows_path"] = windows_path_for_wsl_path(open_me)
    return entry


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export operator-openable artifact links.")
    parser.add_argument("source_path")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--description", default="")
    parser.add_argument("--report-root", default="")
    args = parser.parse_args(list(argv) if argv is not None else None)
    result = export_operator_artifact(
        args.source_path,
        task_id=args.task_id,
        description=args.description,
        report_root=args.report_root or None,
    )
    print(stable_json(result), end="")
    return 1 if result.get("operator_copy_blocked") else 0


if __name__ == "__main__":
    raise SystemExit(main())
