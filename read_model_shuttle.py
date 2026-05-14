"""Cross-machine read-model shuttle helpers.

This module packages generated read-model exports for manual transfer to the
Mac mirror folder, then imports the returned Mac metadata manifest through the
existing Mac Mirror Atlas path. It does not add networking, runtime authority,
tool execution, or truth promotion.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from business_ops_ledger import DEFAULT_DB_PATH
from corpus_atlas import stable_json
from mac_mirror_atlas import (
    MANIFEST_SCHEMA_VERSION,
    format_mac_mirror_report,
    import_root_manifest,
    query_mac_mirror_report_section,
)


SHUTTLE_VERSION = "openclaw.read_model_shuttle.v0"
DEFAULT_SOURCE_ROOT = Path("generated/read_models")
DEFAULT_TRANSFER_ROOT = Path("/mnt/e/openclaw")
DEFAULT_TO_MAC_ROOT = DEFAULT_TRANSFER_ROOT / "shuttle" / "to_mac"
DEFAULT_RETURNED_MANIFEST_PATH = DEFAULT_TRANSFER_ROOT / "mac_generated_read_models_manifest.json"
DEFAULT_IMPORT_MANIFEST_PATH = Path("/home/openclaw/import_manifests/mac_generated_read_models_manifest.json")
DEFAULT_MAC_DESTINATION_ROOT = "/Users/hwinshipwheatley/openclaw_generated_read_models"
MAC_GENERATED_ROOT_ID = "mac_generated_read_models"
MAC_GENERATED_ROOT_KIND = "generated_read_model_mirror"
SAFE_READ_MODEL_SUFFIXES = {".json", ".md", ".txt"}
DEFAULT_FROM_MAC_SEARCH_ROOTS = (
    DEFAULT_TRANSFER_ROOT / "shuttle" / "from_mac",
    DEFAULT_TRANSFER_ROOT,
    Path("/home/openclaw/import_manifests"),
)

NO_AUTHORITY_FLAGS = {
    "runtime_authority": False,
    "backend_execution_allowed": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "model_execution_allowed": False,
    "container_execution_allowed": False,
    "network_authority": False,
    "truth_promotion_allowed": False,
}

CLAIMS_NOT_MADE = (
    "runtime_activation",
    "backend_execution",
    "agent_activation",
    "tool_execution",
    "model_execution",
    "container_execution",
    "network_authority",
    "truth_promotion",
    "raw_private_body_import",
)

NO_GO_PARTS = {
    ".ssh",
    ".gnupg",
    ".google-secrets",
    ".private",
    "private",
    "secrets",
    "vaults",
    "finance",
    "legal",
    "tax",
    "cpa",
    "runtime_logs",
}

NO_GO_FILE_HINTS = (
    "credential",
    "credentials",
    "secret",
    "token",
    ".env",
    "sqlite",
    "ledger",
    "manifest",
    "private",
)

EVIDENCE_CATEGORY_BY_NAME = {
    "source_inventory.json": "source_inventory",
    "helm_state.json": "helm_state",
    "world_domain_registry.json": "world_registry",
    "world_status.json": "world_status",
    "artifact_registry.json": "artifact_registry",
    "runtime_activation_gate.json": "runtime_gate",
    "evidence_freshness.json": "evidence_freshness",
    "generated_current_state.md": "operator_status",
    "generated_next_actions.md": "operator_status",
    "tool_inventory.json": "context_gate",
    "tool_inventory_OPERATOR.md": "context_gate",
    "tool_intake.json": "context_gate",
    "tool_intake_OPERATOR.md": "context_gate",
    "context_selection.json": "context_gate",
    "context_selection_OPERATOR.md": "context_gate",
}


@dataclass(frozen=True)
class ShuttlePrepareResult:
    package_path: str
    manifest_path: str
    file_count: int
    total_bytes: int
    copied_files: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class ShuttleImportResult:
    manifest_path: str
    copied_manifest_path: str
    import_run_id: str
    root_id: str
    path_count: int
    hashed_count: int
    no_go_count: int
    matched_mirror_candidates: int
    mismatched_mirror_candidates: int
    reports: dict[str, dict[str, Any]]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _root() -> Path:
    return Path(__file__).resolve().parent


def _resolve_repo_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return _root() / candidate


def _display_path(path: str | Path) -> str:
    path_obj = Path(path)
    try:
        return path_obj.resolve().relative_to(_root().resolve()).as_posix()
    except (OSError, ValueError):
        return path_obj.as_posix()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _package_name(generated_at: str) -> str:
    stamp = generated_at.replace("-", "").replace(":", "").replace("+00:00", "Z")
    return f"read_models_{stamp[:8]}_{stamp[9:15]}"


def _is_no_go_relative_path(relative_path: str) -> bool:
    parts = {part.lower() for part in Path(relative_path).parts}
    lowered = Path(relative_path).name.lower()
    if parts & NO_GO_PARTS:
        return True
    return any(hint in lowered for hint in NO_GO_FILE_HINTS)


def is_safe_generated_read_model_file(path: Path, source_root: Path) -> bool:
    try:
        relative_path = path.relative_to(source_root).as_posix()
    except ValueError:
        return False
    if "/" in relative_path:
        return False
    if not path.is_file():
        return False
    if path.name.startswith("."):
        return False
    if path.suffix not in SAFE_READ_MODEL_SUFFIXES:
        return False
    if _is_no_go_relative_path(relative_path):
        return False
    return True


def iter_safe_generated_read_models(source_root: str | Path = DEFAULT_SOURCE_ROOT) -> list[Path]:
    root = _resolve_repo_path(source_root)
    if not root.is_dir():
        raise ValueError(f"generated read-model source root does not exist: {root}")
    return [
        path
        for path in sorted(root.iterdir(), key=lambda item: item.name)
        if is_safe_generated_read_model_file(path, root)
    ]


def _file_record(*, source_root: Path, source_path: Path, payload_path: Path) -> dict[str, Any]:
    relative_path = source_path.relative_to(source_root).as_posix()
    size_bytes = source_path.stat().st_size
    digest = _sha256_file(source_path)
    return {
        "relative_path": relative_path,
        "source_path": _display_path(source_path),
        "payload_path": payload_path.as_posix(),
        "destination_path": f"{DEFAULT_MAC_DESTINATION_ROOT}/{relative_path}",
        "size_bytes": size_bytes,
        "sha256": digest,
        "hash_algorithm": "sha256",
    }


def prepare_mac_read_model_shuttle(
    *,
    source_root: str | Path = DEFAULT_SOURCE_ROOT,
    output_root: str | Path = DEFAULT_TO_MAC_ROOT,
    generated_at: str | None = None,
    package_name: str | None = None,
) -> ShuttlePrepareResult:
    generated_at = generated_at or utc_now()
    source = _resolve_repo_path(source_root)
    output = Path(output_root)
    package = output / (package_name or _package_name(generated_at))
    payload_root = package / "payload" / "generated_read_models"
    payload_root.mkdir(parents=True, exist_ok=True)

    file_records: list[dict[str, Any]] = []
    for source_path in iter_safe_generated_read_models(source):
        payload_path = payload_root / source_path.name
        shutil.copy2(source_path, payload_path)
        record = _file_record(
            source_root=source,
            source_path=source_path,
            payload_path=Path("payload") / "generated_read_models" / source_path.name,
        )
        copied_hash = _sha256_file(payload_path)
        if copied_hash != record["sha256"]:
            raise ValueError(f"hash mismatch after copying {source_path}")
        if payload_path.stat().st_size != record["size_bytes"]:
            raise ValueError(f"size mismatch after copying {source_path}")
        file_records.append(record)

    manifest = {
        "shuttle_manifest_version": SHUTTLE_VERSION,
        "generated_at": generated_at,
        "package_id": package.name,
        "source_host_kind": "pc_wsl",
        "source_root": _display_path(source),
        "destination_host_kind": "mac",
        "destination_root": DEFAULT_MAC_DESTINATION_ROOT,
        "payload_root": "payload/generated_read_models",
        "file_count": len(file_records),
        "total_bytes": sum(record["size_bytes"] for record in file_records),
        "files": file_records,
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
        "raw_private_bodies_included": False,
        "sqlite_databases_included": False,
        "import_manifests_included": False,
        "claims_not_made": list(CLAIMS_NOT_MADE),
    }
    manifest_path = package / "shuttle_manifest.json"
    manifest_path.write_text(stable_json(manifest), encoding="utf-8")

    apply_path = package / "APPLY_ON_MAC.sh"
    apply_path.write_text(mac_apply_script(), encoding="utf-8")
    apply_path.chmod(0o755)

    readme_path = package / "README.md"
    readme_path.write_text(
        "\n".join(
            [
                "# OpenClaw Read-Model Shuttle Package",
                "",
                "Run this from the package folder on the Mac:",
                "",
                "```bash",
                "bash APPLY_ON_MAC.sh",
                "```",
                "",
                "The script copies generated read-model files into:",
                f"`{DEFAULT_MAC_DESTINATION_ROOT}`",
                "",
                "It then verifies sizes and hashes, writes `mac_generated_read_models_manifest.json`,",
                "and writes `RETURN_TO_PC_README.txt`.",
                "",
                "This package does not grant runtime, agent, tool, model, container, network, or truth-promotion authority.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    return ShuttlePrepareResult(
        package_path=package.as_posix(),
        manifest_path=manifest_path.as_posix(),
        file_count=len(file_records),
        total_bytes=sum(record["size_bytes"] for record in file_records),
        copied_files=tuple(file_records),
    )


def _stat_record(path: Path) -> tuple[int | None, str | None, str | None]:
    try:
        stat_result = path.lstat()
    except OSError:
        return None, None, None
    return (
        stat_result.st_size,
        datetime.fromtimestamp(stat_result.st_mtime, timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        datetime.fromtimestamp(stat_result.st_ctime, timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
    )


def _path_type(path: Path) -> str:
    if path.is_symlink():
        return "symlink"
    if path.is_file():
        return "file"
    if path.is_dir():
        return "directory"
    return "unknown"


def _generated_evidence_category(relative_path: str) -> str:
    return EVIDENCE_CATEGORY_BY_NAME.get(Path(relative_path).name, "unknown")


def _mac_manifest_path_record(root: Path, path: Path) -> dict[str, Any]:
    relative_path = path.relative_to(root).as_posix()
    path_type = _path_type(path)
    size_bytes, mtime, ctime = _stat_record(path)
    no_go = _is_no_go_relative_path(relative_path)
    safe_file = (
        path_type == "file"
        and path.suffix in SAFE_READ_MODEL_SUFFIXES
        and not no_go
        and not path.name.startswith(".")
    )
    content_hash = _sha256_file(path) if safe_file else None
    return {
        "relative_path": relative_path,
        "path_type": path_type,
        "size_bytes": size_bytes,
        "mtime": mtime,
        "ctime": ctime,
        "content_hash": content_hash,
        "hash_algorithm": "sha256" if content_hash else None,
        "raw_content_eligibility": "eligible" if safe_file else ("no_go" if no_go else "metadata_only"),
        "sensitivity_label": "internal_project" if safe_file else ("no_go" if no_go else "metadata_only"),
        "source_role": "generated_read_model" if safe_file else ("secret_boundary" if no_go else "unknown"),
        "freshness_label": "generated_current" if safe_file else ("no_go_boundary" if no_go else "unknown"),
        "canonicality": "generated_current" if safe_file else ("no_go_boundary" if no_go else "unknown_review"),
        "retrieval_eligibility": "generated_read_model_only"
        if safe_file
        else ("blocked_no_go" if no_go else "metadata_only"),
        "ingestion_eligibility": "generated_snapshot_only"
        if safe_file
        else ("no_go" if no_go else "metadata_only"),
        "world_binding": "cross_world" if safe_file else ("security" if no_go else "unknown"),
        "evidence_category": _generated_evidence_category(relative_path) if safe_file else "unknown",
        "notes": "read_model_shuttle_mac_manifest",
    }


def build_mac_generated_read_model_manifest(
    *,
    destination_root: str | Path,
    output: str | Path,
    generated_at: str | None = None,
) -> dict[str, Any]:
    root = Path(destination_root).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Mac generated read-model root does not exist: {root}")
    generated_at = generated_at or utc_now()
    path_records: list[dict[str, Any]] = []
    for path in sorted(root.iterdir(), key=lambda item: item.name):
        if path.name == "mac_generated_read_models_manifest.json":
            continue
        path_records.append(_mac_manifest_path_record(root, path))
    manifest = {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "generated_at": generated_at,
        "host_kind": "mac",
        "root_id": MAC_GENERATED_ROOT_ID,
        "root_kind": MAC_GENERATED_ROOT_KIND,
        "owner_scope": "internal_platform",
        "absolute_root": root.as_posix(),
        "machine_label": None,
        "branch": None,
        "commit_sha": None,
        "remote_origin": None,
        "repo_name": None,
        "path_records": path_records,
        "claims_not_made": [
            "raw_file_bodies",
            "remote_scan",
            "filesystem_move",
            "runtime_activation",
            "agent_activation",
            "truth_authority",
        ],
    }
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(stable_json(manifest), encoding="utf-8")
    return manifest


def mac_apply_script() -> str:
    return r'''#!/usr/bin/env bash
set -euo pipefail

PACKAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PAYLOAD_DIR="$PACKAGE_DIR/payload/generated_read_models"
DEST_DIR="${OPENCLAW_MAC_READ_MODEL_ROOT:-/Users/hwinshipwheatley/openclaw_generated_read_models}"

mkdir -p "$DEST_DIR"
cp "$PAYLOAD_DIR"/* "$DEST_DIR"/

python3 - "$PACKAGE_DIR" "$DEST_DIR" <<'PY'
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

package_dir = Path(sys.argv[1]).resolve()
dest_dir = Path(sys.argv[2]).expanduser().resolve()
manifest_path = package_dir / "shuttle_manifest.json"
shuttle = json.loads(manifest_path.read_text(encoding="utf-8"))

def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

for record in shuttle["files"]:
    destination = dest_dir / record["relative_path"]
    if not destination.is_file():
        raise SystemExit(f"missing copied read model: {destination}")
    if destination.stat().st_size != record["size_bytes"]:
        raise SystemExit(f"size mismatch: {destination}")
    if sha256_file(destination) != record["sha256"]:
        raise SystemExit(f"hash mismatch: {destination}")

safe_suffixes = {".json", ".md", ".txt"}
no_go_parts = {
    ".ssh", ".gnupg", ".google-secrets", ".private", "private", "secrets",
    "vaults", "finance", "legal", "tax", "cpa", "runtime_logs",
}
no_go_hints = ("credential", "credentials", "secret", "token", ".env", "sqlite", "ledger", "manifest", "private")
category_by_name = {
    "source_inventory.json": "source_inventory",
    "helm_state.json": "helm_state",
    "world_domain_registry.json": "world_registry",
    "world_status.json": "world_status",
    "artifact_registry.json": "artifact_registry",
    "runtime_activation_gate.json": "runtime_gate",
    "evidence_freshness.json": "evidence_freshness",
    "generated_current_state.md": "operator_status",
    "generated_next_actions.md": "operator_status",
    "tool_inventory.json": "context_gate",
    "tool_inventory_OPERATOR.md": "context_gate",
    "tool_intake.json": "context_gate",
    "tool_intake_OPERATOR.md": "context_gate",
    "context_selection.json": "context_gate",
    "context_selection_OPERATOR.md": "context_gate",
}

def stable_json(payload):
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"

def iso_from_timestamp(value):
    return datetime.fromtimestamp(value, timezone.utc).replace(microsecond=0).isoformat()

def path_type(path):
    if path.is_symlink():
        return "symlink"
    if path.is_file():
        return "file"
    if path.is_dir():
        return "directory"
    return "unknown"

def no_go(relative_path):
    parts = {part.lower() for part in Path(relative_path).parts}
    lowered = Path(relative_path).name.lower()
    return bool(parts & no_go_parts) or any(hint in lowered for hint in no_go_hints)

def path_record(path):
    relative_path = path.relative_to(dest_dir).as_posix()
    stat_result = path.lstat()
    kind = path_type(path)
    blocked = no_go(relative_path)
    safe_file = (
        kind == "file"
        and path.suffix in safe_suffixes
        and not blocked
        and not path.name.startswith(".")
    )
    content_hash = sha256_file(path) if safe_file else None
    return {
        "relative_path": relative_path,
        "path_type": kind,
        "size_bytes": stat_result.st_size,
        "mtime": iso_from_timestamp(stat_result.st_mtime),
        "ctime": iso_from_timestamp(stat_result.st_ctime),
        "content_hash": content_hash,
        "hash_algorithm": "sha256" if content_hash else None,
        "raw_content_eligibility": "eligible" if safe_file else ("no_go" if blocked else "metadata_only"),
        "sensitivity_label": "internal_project" if safe_file else ("no_go" if blocked else "metadata_only"),
        "source_role": "generated_read_model" if safe_file else ("secret_boundary" if blocked else "unknown"),
        "freshness_label": "generated_current" if safe_file else ("no_go_boundary" if blocked else "unknown"),
        "canonicality": "generated_current" if safe_file else ("no_go_boundary" if blocked else "unknown_review"),
        "retrieval_eligibility": "generated_read_model_only" if safe_file else ("blocked_no_go" if blocked else "metadata_only"),
        "ingestion_eligibility": "generated_snapshot_only" if safe_file else ("no_go" if blocked else "metadata_only"),
        "world_binding": "cross_world" if safe_file else ("security" if blocked else "unknown"),
        "evidence_category": category_by_name.get(Path(relative_path).name, "unknown") if safe_file else "unknown",
        "notes": "read_model_shuttle_mac_manifest",
    }

path_records = []
for path in sorted(dest_dir.iterdir(), key=lambda item: item.name):
    if path.name == "mac_generated_read_models_manifest.json":
        continue
    path_records.append(path_record(path))

generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
mac_manifest = {
    "manifest_schema_version": "openclaw.root_manifest.v0",
    "generated_at": generated_at,
    "host_kind": "mac",
    "root_id": "mac_generated_read_models",
    "root_kind": "generated_read_model_mirror",
    "owner_scope": "internal_platform",
    "absolute_root": dest_dir.as_posix(),
    "machine_label": None,
    "branch": None,
    "commit_sha": None,
    "remote_origin": None,
    "repo_name": None,
    "path_records": path_records,
    "claims_not_made": [
        "raw_file_bodies",
        "remote_scan",
        "filesystem_move",
        "runtime_activation",
        "agent_activation",
        "truth_authority",
    ],
}
(package_dir / "mac_generated_read_models_manifest.json").write_text(stable_json(mac_manifest), encoding="utf-8")
(package_dir / "RETURN_TO_PC_README.txt").write_text(
    "Return this package folder, or at least mac_generated_read_models_manifest.json, to the PC/WSL import side.\n",
    encoding="utf-8",
)
print(f"Copied and verified {len(shuttle['files'])} read-model files.")
print(f"Wrote {package_dir / 'mac_generated_read_models_manifest.json'}")
PY
'''


def resolve_returned_manifest(
    *,
    manifest: str | Path | None = None,
    package: str | Path | None = None,
    search_roots: Iterable[str | Path] = DEFAULT_FROM_MAC_SEARCH_ROOTS,
) -> Path:
    if manifest:
        path = Path(manifest)
        if not path.is_file():
            raise ValueError(f"manifest does not exist: {path}")
        return path
    if package:
        package_path = Path(package)
        candidate = package_path / "mac_generated_read_models_manifest.json"
        if not candidate.is_file():
            raise ValueError(f"package does not contain returned manifest: {candidate}")
        return candidate
    candidates: list[Path] = []
    for root in search_roots:
        root_path = Path(root)
        if root_path.is_file() and root_path.name == "mac_generated_read_models_manifest.json":
            candidates.append(root_path)
        elif root_path.is_dir():
            candidates.extend(root_path.glob("mac_generated_read_models_manifest.json"))
            candidates.extend(root_path.glob("*/mac_generated_read_models_manifest.json"))
    if not candidates:
        raise ValueError("no returned mac_generated_read_models_manifest.json found")
    return max(candidates, key=lambda item: item.stat().st_mtime)


def _validate_returned_mac_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("manifest_schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ValueError("unsupported returned manifest schema")
    if manifest.get("root_id") != MAC_GENERATED_ROOT_ID:
        raise ValueError("returned manifest must have root_id=mac_generated_read_models")
    if not isinstance(manifest.get("path_records"), list):
        raise ValueError("returned manifest path_records must be a list")
    forbidden_body_keys = {"body", "content", "raw_body", "file_body", "text"}
    for record in manifest["path_records"]:
        if forbidden_body_keys & set(record):
            raise ValueError("returned manifest must not contain raw file bodies")
    return manifest


def import_mac_read_model_shuttle(
    *,
    manifest: str | Path | None = None,
    package: str | Path | None = None,
    db_path: str | Path = DEFAULT_DB_PATH,
    import_manifest_path: str | Path = DEFAULT_IMPORT_MANIFEST_PATH,
    run_id: str | None = None,
) -> ShuttleImportResult:
    source_manifest = resolve_returned_manifest(manifest=manifest, package=package)
    _validate_returned_mac_manifest(source_manifest)

    import_path = Path(import_manifest_path)
    import_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_manifest, import_path)

    result = import_root_manifest(
        manifest_path=import_path,
        db_path=db_path,
        run_id=run_id,
    )
    reports = {
        "generated_read_model_mirror": query_mac_mirror_report_section(
            db_path=db_path,
            section="generated-read-model-mirror",
        ),
        "mirror_mismatches": query_mac_mirror_report_section(
            db_path=db_path,
            section="mirror-mismatches",
        ),
        "mac_roots": query_mac_mirror_report_section(db_path=db_path, section="mac-roots"),
    }
    return ShuttleImportResult(
        manifest_path=source_manifest.as_posix(),
        copied_manifest_path=import_path.as_posix(),
        import_run_id=result.run_id,
        root_id=result.root_id,
        path_count=result.path_count,
        hashed_count=result.hashed_count,
        no_go_count=result.no_go_count,
        matched_mirror_candidates=result.matched_mirror_candidates,
        mismatched_mirror_candidates=result.mismatched_mirror_candidates,
        reports=reports,
    )


def format_prepare_result(result: ShuttlePrepareResult) -> str:
    lines = [
        "Read-Model Shuttle Prepare v0",
        "",
        f"Package: `{result.package_path}`",
        f"Manifest: `{result.manifest_path}`",
        f"Files: {result.file_count}",
        f"Total bytes: {result.total_bytes}",
        "",
        "Copied files:",
    ]
    lines.extend(
        f"- {record['relative_path']} ({record['size_bytes']} bytes, sha256={record['sha256']})"
        for record in result.copied_files
    )
    lines.extend(
        [
            "",
            "Boundary:",
            "- Package contains generated read-model/operator files only.",
            "- No runtime, backend, agent, tool, model, container, network, or truth-promotion authority is granted.",
            "",
            "Next Mac step:",
            "- Move the package folder to the Mac and run `bash APPLY_ON_MAC.sh` from inside it.",
        ]
    )
    return "\n".join(lines)


def format_import_result(result: ShuttleImportResult) -> str:
    mirror_report = result.reports["generated_read_model_mirror"]
    mismatch_report = result.reports["mirror_mismatches"]
    root_report = result.reports["mac_roots"]
    lines = [
        "Read-Model Shuttle Import v0",
        "",
        f"Returned manifest: `{result.manifest_path}`",
        f"Copied manifest: `{result.copied_manifest_path}`",
        f"Import run: `{result.import_run_id}`",
        f"Root: `{result.root_id}`",
        f"Paths imported: {result.path_count}",
        f"Hashed safe files: {result.hashed_count}",
        f"No-go metadata rows: {result.no_go_count}",
        f"Matched mirrors: {result.matched_mirror_candidates}",
        f"Mismatched mirrors: {result.mismatched_mirror_candidates}",
        "",
        "Generated read-model mirror report:",
        format_mac_mirror_report(mirror_report),
        "",
        "Mirror mismatch report:",
        format_mac_mirror_report(mismatch_report),
        "",
        "Mac roots report:",
        format_mac_mirror_report(root_report),
        "",
        "Boundary:",
        "- Imported manifest metadata only; no raw file bodies, runtime activation, agent activation, or truth promotion.",
    ]
    return "\n".join(lines)


__all__ = [
    "DEFAULT_FROM_MAC_SEARCH_ROOTS",
    "DEFAULT_MAC_DESTINATION_ROOT",
    "DEFAULT_RETURNED_MANIFEST_PATH",
    "DEFAULT_SOURCE_ROOT",
    "DEFAULT_TO_MAC_ROOT",
    "DEFAULT_TRANSFER_ROOT",
    "NO_AUTHORITY_FLAGS",
    "ShuttleImportResult",
    "ShuttlePrepareResult",
    "build_mac_generated_read_model_manifest",
    "format_import_result",
    "format_prepare_result",
    "import_mac_read_model_shuttle",
    "is_safe_generated_read_model_file",
    "iter_safe_generated_read_models",
    "mac_apply_script",
    "prepare_mac_read_model_shuttle",
    "resolve_returned_manifest",
]
