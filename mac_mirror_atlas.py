"""Safe manifest bridge for Mac-side OpenClaw roots.

This module does not crawl a remote Mac. It builds local metadata manifests for
explicit roots and imports transferred manifests into the existing Corpus Atlas
``corpus_*`` tables.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from business_ops_ledger import DEFAULT_DB_PATH
from corpus_atlas import (
    CANONICALITY_LABELS,
    EVIDENCE_CATEGORIES,
    FRESHNESS_LABELS,
    INGESTION_ELIGIBILITY,
    RAW_CONTENT_ELIGIBILITY,
    REORG_BUCKETS,
    RETRIEVAL_ELIGIBILITY,
    SENSITIVITY_LABELS,
    SOURCE_ROLES,
    WORLD_BINDINGS,
    CorpusPathRecord,
    _insert_path,
    _insert_reorg_candidate,
    _insert_sensitivity_label,
    _insert_standard_labels,
    _insert_world_binding,
    _path_id,
    _row_id,
    init_corpus_atlas_schema,
    sensitivity_boundary,
    stable_json,
)


MANIFEST_SCHEMA_VERSION = "openclaw.root_manifest.v0"
MAC_MIRROR_ATLAS_VERSION = "mac_mirror_atlas_v0"
DEFAULT_PC_ROOT_ID = "pc_wsl_home_openclaw"
MAX_HASH_BYTES = 5_000_000

EXPECTED_MAC_ROOTS = {
    "mac_mission_control_app": {
        "host_kind": "mac",
        "owner_scope": "internal_platform",
        "root_kind": "app_repo",
        "absolute_root": "/Users/hwinshipwheatley/Developer/OpenClawMissionControl/OpenClaw Mission Controle",
        "canonical_status": "non_canonical_app_root",
        "mirror_of_root_id": DEFAULT_PC_ROOT_ID,
        "lineage_source": "mission_control_app",
    },
    "mac_generated_read_models": {
        "host_kind": "mac",
        "owner_scope": "internal_platform",
        "root_kind": "generated_read_model_mirror",
        "absolute_root": "/Users/hwinshipwheatley/openclaw_generated_read_models",
        "canonical_status": "non_canonical_mirror",
        "mirror_of_root_id": DEFAULT_PC_ROOT_ID,
        "lineage_source": "generated/read_models",
    },
    "mac_openclaw_mirror": {
        "host_kind": "mac",
        "owner_scope": "internal_platform",
        "root_kind": "operating_mirror",
        "absolute_root": None,
        "canonical_status": "non_canonical_mirror",
        "mirror_of_root_id": DEFAULT_PC_ROOT_ID,
        "lineage_source": "operator_supplied_manifest",
    },
}

EXPECTED_GENERATED_READ_MODEL_FILES = (
    "source_inventory.json",
    "helm_state.json",
    "world_domain_registry.json",
    "world_status.json",
    "artifact_registry.json",
    "runtime_activation_gate.json",
    "evidence_freshness.json",
    "generated_current_state.md",
    "generated_next_actions.md",
    "tool_inventory.json",
    "tool_intake.json",
)

NO_DESCEND_DIR_NAMES = {
    ".git",
    ".build",
    ".swiftpm",
    ".xcodeproj/xcuserdata",
    "DerivedData",
    "build",
    "node_modules",
    ".cache",
    ".pytest_cache",
    "__pycache__",
}

APP_SOURCE_SUFFIXES = (
    ".swift",
    ".xcodeproj",
    ".xcworkspace",
    ".pbxproj",
    ".plist",
    ".entitlements",
    ".json",
    ".md",
    ".yml",
    ".yaml",
    ".toml",
)


@dataclass(frozen=True)
class ManifestBuildResult:
    manifest: dict[str, Any]
    path_count: int
    hashed_count: int
    no_go_count: int
    output_path: str | None


@dataclass(frozen=True)
class ManifestImportResult:
    run_id: str
    root_id: str
    path_count: int
    matched_mirror_candidates: int
    mismatched_mirror_candidates: int
    no_go_count: int
    hashed_count: int


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256_text(*parts: str) -> str:
    return hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()


def _manifest_run_id(root_id: str, generated_at: str) -> str:
    digest = _sha256_text(root_id, generated_at)
    return f"macmanifest_{digest[:20]}"


def _sanitize_remote(remote: str | None) -> str | None:
    if not remote:
        return None
    if "://" in remote and "@" in remote:
        scheme, rest = remote.split("://", 1)
        credentials, host_part = rest.split("@", 1)
        if credentials:
            return f"{scheme}://***@{host_part}"
    return remote


def _run_git_metadata(root: Path) -> dict[str, str | None]:
    metadata = {
        "branch": None,
        "commit_sha": None,
        "remote_origin": None,
        "repo_name": None,
    }
    commands = {
        "branch": ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        "commit_sha": ["git", "rev-parse", "HEAD"],
        "remote_origin": ["git", "remote", "get-url", "origin"],
    }
    for key, command in commands.items():
        try:
            result = subprocess.run(
                command,
                cwd=root,
                capture_output=True,
                check=False,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode == 0:
            value = result.stdout.decode("utf-8", errors="replace").strip()
            metadata[key] = _sanitize_remote(value) if key == "remote_origin" else value
    if metadata["remote_origin"]:
        metadata["repo_name"] = Path(str(metadata["remote_origin"]).rstrip("/")).name.removesuffix(".git")
    return metadata


def reject_broad_root(root_arg: str) -> None:
    raw = root_arg.strip()
    if not raw:
        raise ValueError("root must not be empty")
    lowered = raw.lower().replace("\\", "/")
    if lowered in {"/", "/home", "/users", "c:/", "c:", "c://"}:
        raise ValueError(f"refusing broad root: {root_arg}")
    resolved = Path(raw).expanduser().resolve()
    if resolved in {Path("/"), Path("/home"), Path("/Users")}:
        raise ValueError(f"refusing broad root: {root_arg}")
    if len(resolved.parts) <= 2 and resolved.is_absolute():
        raise ValueError(f"refusing broad root: {root_arg}")
    if not resolved.exists() or not resolved.is_dir():
        raise ValueError(f"root must be an existing directory: {root_arg}")


def _path_type(path: Path) -> str:
    try:
        if path.is_symlink():
            return "symlink"
        if path.is_file():
            return "file"
        if path.is_dir():
            return "directory"
    except OSError:
        return "unknown"
    return "unknown"


def _stat_metadata(path: Path) -> tuple[int | None, str | None, str | None]:
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


def _is_generated_root(root_id: str, root_kind: str) -> bool:
    return root_id == "mac_generated_read_models" or root_kind == "generated_read_model_mirror"


def _is_app_root(root_id: str, root_kind: str) -> bool:
    return root_id == "mac_mission_control_app" or root_kind == "app_repo"


def _is_no_descend_dir(relative_path: str) -> bool:
    name = Path(relative_path).name
    return name in NO_DESCEND_DIR_NAMES or relative_path.endswith(".xcodeproj/xcuserdata")


def _is_safe_app_source(relative_path: str, path_type: str) -> bool:
    if path_type != "file":
        return False
    return relative_path.endswith(APP_SOURCE_SUFFIXES)


def _classify_manifest_path(
    *,
    relative_path: str,
    path_type: str,
    root_id: str,
    root_kind: str,
) -> dict[str, Any]:
    boundary = sensitivity_boundary(relative_path)
    if boundary:
        sensitivity_label, source_role, raw_content_eligibility, reason = boundary
        retrieval = "blocked_no_go" if raw_content_eligibility == "no_go" else "metadata_only"
        ingestion = "no_go" if raw_content_eligibility == "no_go" else "metadata_only"
        return {
            "raw_content_eligibility": raw_content_eligibility,
            "sensitivity_label": sensitivity_label,
            "source_role": source_role,
            "freshness_label": "no_go_boundary"
            if raw_content_eligibility == "no_go"
            else "sensitive_metadata_only",
            "canonicality": "no_go_boundary",
            "retrieval_eligibility": retrieval,
            "ingestion_eligibility": ingestion,
            "world_binding": "security" if sensitivity_label == "credential_boundary" else "no_world",
            "evidence_category": "no_go_boundary",
            "reorg_bucket": "sensitive_no_go",
            "reorg_reason": reason,
            "reorg_confidence": 0.95,
            "requires_operator_review": True,
            "metadata_basis": reason,
        }

    if _is_no_descend_dir(relative_path):
        return {
            "raw_content_eligibility": "metadata_only",
            "sensitivity_label": "metadata_only",
            "source_role": "cache" if Path(relative_path).name != ".git" else "config",
            "freshness_label": "sensitive_metadata_only",
            "canonicality": "unknown_review",
            "retrieval_eligibility": "metadata_only",
            "ingestion_eligibility": "metadata_only",
            "world_binding": "no_world",
            "evidence_category": "unknown",
            "reorg_bucket": "unknown_review",
            "reorg_reason": "build/cache/git-internal boundary; metadata only",
            "reorg_confidence": 0.8,
            "requires_operator_review": True,
            "metadata_basis": "mac_manifest_metadata_only_boundary",
        }

    if _is_generated_root(root_id, root_kind):
        is_file = path_type == "file"
        return {
            "raw_content_eligibility": "eligible" if is_file else "metadata_only",
            "sensitivity_label": "internal_project",
            "source_role": "generated_read_model",
            "freshness_label": "generated_current" if is_file else "generated_read_model_fact",
            "canonicality": "generated_current",
            "retrieval_eligibility": "generated_read_model_only",
            "ingestion_eligibility": "generated_snapshot_only" if is_file else "metadata_only",
            "world_binding": "cross_world",
            "evidence_category": _generated_evidence_category(relative_path),
            "reorg_bucket": "generated_output",
            "reorg_reason": "Mac generated read-model mirror metadata",
            "reorg_confidence": 0.9,
            "requires_operator_review": False,
            "metadata_basis": "mac_generated_read_model_manifest",
        }

    if _is_app_root(root_id, root_kind) and _is_safe_app_source(relative_path, path_type):
        return {
            "raw_content_eligibility": "eligible",
            "sensitivity_label": "internal_project",
            "source_role": "source_code",
            "freshness_label": "source_claim",
            "canonicality": "tracked_source",
            "retrieval_eligibility": "metadata_only",
            "ingestion_eligibility": "metadata_only",
            "world_binding": "build",
            "evidence_category": "unknown",
            "reorg_bucket": "app_source",
            "reorg_reason": "Mac Mission Control app source metadata; non-canonical",
            "reorg_confidence": 0.85,
            "requires_operator_review": False,
            "metadata_basis": "mac_app_source_manifest",
        }

    if path_type == "directory":
        return {
            "raw_content_eligibility": "metadata_only",
            "sensitivity_label": "internal_project",
            "source_role": "source_code" if _is_app_root(root_id, root_kind) else "unknown",
            "freshness_label": "source_claim" if _is_app_root(root_id, root_kind) else "unknown",
            "canonicality": "tracked_source" if _is_app_root(root_id, root_kind) else "unknown_review",
            "retrieval_eligibility": "metadata_only",
            "ingestion_eligibility": "metadata_only",
            "world_binding": "build" if _is_app_root(root_id, root_kind) else "unknown",
            "evidence_category": "unknown",
            "reorg_bucket": "app_source" if _is_app_root(root_id, root_kind) else "unknown_review",
            "reorg_reason": "directory metadata only",
            "reorg_confidence": 0.5,
            "requires_operator_review": not _is_app_root(root_id, root_kind),
            "metadata_basis": "mac_manifest_directory_metadata",
        }

    return {
        "raw_content_eligibility": "unknown",
        "sensitivity_label": "internal_project",
        "source_role": "unknown",
        "freshness_label": "unknown",
        "canonicality": "unknown_review",
        "retrieval_eligibility": "blocked_unknown",
        "ingestion_eligibility": "needs_review",
        "world_binding": "unknown",
        "evidence_category": "unknown",
        "reorg_bucket": "unknown_review",
        "reorg_reason": "Mac manifest path requires operator review",
        "reorg_confidence": 0.35,
        "requires_operator_review": True,
        "metadata_basis": "mac_manifest_unknown_path",
    }


def _generated_evidence_category(relative_path: str) -> str:
    name = Path(relative_path).name
    if name == "source_inventory.json":
        return "source_inventory"
    if name == "helm_state.json":
        return "helm_state"
    if name == "world_domain_registry.json":
        return "world_registry"
    if name == "world_status.json":
        return "world_status"
    if name == "artifact_registry.json":
        return "artifact_registry"
    if name == "evidence_freshness.json":
        return "evidence_freshness"
    if name == "runtime_activation_gate.json":
        return "runtime_gate"
    if name in {"generated_current_state.md", "generated_next_actions.md"}:
        return "operator_status"
    return "unknown"


def _should_hash(classification: dict[str, Any], path_type: str, size_bytes: int | None) -> bool:
    if path_type != "file":
        return False
    if classification["raw_content_eligibility"] != "eligible":
        return False
    if classification["sensitivity_label"] not in {"public_project", "internal_project"}:
        return False
    if size_bytes is None or size_bytes > MAX_HASH_BYTES:
        return False
    return True


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iter_manifest_paths(root: Path, root_id: str, root_kind: str) -> list[Path]:
    queue: deque[Path] = deque(sorted(root.iterdir(), key=lambda item: item.name))
    result: list[Path] = []
    seen: set[str] = set()
    while queue:
        path = queue.popleft()
        try:
            relative_path = path.relative_to(root).as_posix()
        except ValueError:
            continue
        if relative_path in seen:
            continue
        seen.add(relative_path)
        result.append(path)

        path_type = _path_type(path)
        classification = _classify_manifest_path(
            relative_path=relative_path,
            path_type=path_type,
            root_id=root_id,
            root_kind=root_kind,
        )
        if path_type != "directory":
            continue
        if classification["raw_content_eligibility"] in {"no_go"}:
            continue
        if classification["sensitivity_label"] in {
            "credential_boundary",
            "finance_boundary",
            "legal_tax_boundary",
            "private",
            "runtime_log_boundary",
            "no_go",
            "metadata_only",
        }:
            continue
        try:
            queue.extend(sorted(path.iterdir(), key=lambda item: item.name))
        except OSError:
            continue
    return result


def build_root_manifest(
    *,
    root: str | Path,
    root_id: str,
    root_kind: str,
    host_kind: str,
    owner_scope: str,
    output: str | Path | None = None,
    machine_label: str | None = None,
) -> ManifestBuildResult:
    reject_broad_root(str(root))
    root_path = Path(root).expanduser().resolve()
    generated_at = utc_now()
    git = _run_git_metadata(root_path)
    path_records: list[dict[str, Any]] = []
    hashed_count = 0
    no_go_count = 0

    for path in _iter_manifest_paths(root_path, root_id, root_kind):
        relative_path = path.relative_to(root_path).as_posix()
        path_type = _path_type(path)
        size_bytes, mtime, ctime = _stat_metadata(path)
        classification = _classify_manifest_path(
            relative_path=relative_path,
            path_type=path_type,
            root_id=root_id,
            root_kind=root_kind,
        )
        content_hash = None
        hash_algorithm = None
        if _should_hash(classification, path_type, size_bytes):
            content_hash = _hash_file(path)
            hash_algorithm = "sha256"
            hashed_count += 1
        if classification["raw_content_eligibility"] == "no_go":
            no_go_count += 1
        path_records.append(
            {
                "relative_path": relative_path,
                "path_type": path_type,
                "size_bytes": size_bytes,
                "mtime": mtime,
                "ctime": ctime,
                "content_hash": content_hash,
                "hash_algorithm": hash_algorithm,
                "raw_content_eligibility": classification["raw_content_eligibility"],
                "sensitivity_label": classification["sensitivity_label"],
                "source_role": classification["source_role"],
                "freshness_label": classification["freshness_label"],
                "canonicality": classification["canonicality"],
                "retrieval_eligibility": classification["retrieval_eligibility"],
                "ingestion_eligibility": classification["ingestion_eligibility"],
                "world_binding": classification["world_binding"],
                "evidence_category": classification["evidence_category"],
                "notes": classification["metadata_basis"],
            }
        )

    manifest = {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "generated_at": generated_at,
        "host_kind": host_kind,
        "root_id": root_id,
        "root_kind": root_kind,
        "owner_scope": owner_scope,
        "absolute_root": root_path.as_posix(),
        "machine_label": machine_label,
        "branch": git["branch"],
        "commit_sha": git["commit_sha"],
        "remote_origin": git["remote_origin"],
        "repo_name": git["repo_name"],
        "path_records": path_records,
        "claims_not_made": [
            "raw_file_bodies",
            "remote_mac_scan",
            "ssh",
            "scp",
            "rsync",
            "filesystem_copy",
            "filesystem_move",
            "runtime_activation",
            "agent_activation",
            "truth_authority",
        ],
    }

    output_path = None
    if output:
        out = Path(output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(stable_json(manifest), encoding="utf-8")
        output_path = out.as_posix()

    return ManifestBuildResult(
        manifest=manifest,
        path_count=len(path_records),
        hashed_count=hashed_count,
        no_go_count=no_go_count,
        output_path=output_path,
    )


def _validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("manifest_schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ValueError("unsupported manifest_schema_version")
    if not isinstance(manifest.get("path_records"), list):
        raise ValueError("manifest path_records must be a list")
    for record in manifest["path_records"]:
        if not isinstance(record, dict):
            raise ValueError("path record must be an object")
        forbidden_body_keys = {"body", "content", "raw_body", "file_body", "text"}
        if forbidden_body_keys & set(record):
            raise ValueError("manifest path records must not include raw file bodies")
        if not record.get("relative_path") or str(record["relative_path"]).startswith("/"):
            raise ValueError("path record relative_path must be relative")


def _root_defaults(root_id: str) -> dict[str, Any]:
    return EXPECTED_MAC_ROOTS.get(
        root_id,
        {
            "host_kind": "unknown",
            "owner_scope": "internal_platform",
            "root_kind": "unknown",
            "absolute_root": None,
            "canonical_status": "non_canonical_manifest_import",
            "mirror_of_root_id": DEFAULT_PC_ROOT_ID,
            "lineage_source": "operator_supplied_manifest",
        },
    )


def _safe_label(value: Any, allowed: set[str], default: str) -> str:
    return value if isinstance(value, str) and value in allowed else default


def _record_from_manifest(
    *,
    manifest: dict[str, Any],
    path_record: dict[str, Any],
    run_id: str,
) -> CorpusPathRecord:
    root_id = str(manifest["root_id"])
    relative_path = str(path_record["relative_path"]).strip("/")
    path_type = _safe_label(path_record.get("path_type"), {"file", "directory", "symlink", "unknown"}, "unknown")
    sensitivity_label = _safe_label(path_record.get("sensitivity_label"), SENSITIVITY_LABELS, "unknown")
    raw_content_eligibility = _safe_label(
        path_record.get("raw_content_eligibility"),
        RAW_CONTENT_ELIGIBILITY,
        "unknown",
    )
    retrieval_eligibility = _safe_label(
        path_record.get("retrieval_eligibility"),
        RETRIEVAL_ELIGIBILITY,
        "blocked_unknown",
    )
    ingestion_eligibility = _safe_label(
        path_record.get("ingestion_eligibility"),
        INGESTION_ELIGIBILITY,
        "needs_review",
    )
    if raw_content_eligibility == "no_go" or sensitivity_label in {
        "credential_boundary",
        "finance_boundary",
        "legal_tax_boundary",
        "private",
        "runtime_log_boundary",
        "no_go",
    }:
        content_hash = None
        hash_algorithm = None
        retrieval_eligibility = "blocked_no_go" if raw_content_eligibility == "no_go" else "blocked_sensitive"
        ingestion_eligibility = "no_go"
    else:
        content_hash = path_record.get("content_hash")
        hash_algorithm = path_record.get("hash_algorithm")
    parent = Path(relative_path).parent.as_posix()
    if parent == ".":
        parent = ""
    absolute_path = str(manifest["absolute_root"]).rstrip("/") + "/" + relative_path
    return CorpusPathRecord(
        path_id=_path_id(root_id, run_id, relative_path),
        root_id=root_id,
        run_id=run_id,
        absolute_path=absolute_path,
        relative_path=relative_path,
        parent_relative_path=parent,
        path_name=Path(relative_path).name,
        path_type=path_type,
        tracked_status=_safe_label(path_record.get("tracked_status"), {"tracked", "untracked", "ignored", "unknown"}, "unknown"),
        git_head=str(manifest.get("commit_sha") or "unknown"),
        size_bytes=path_record.get("size_bytes"),
        mtime=path_record.get("mtime"),
        ctime=path_record.get("ctime"),
        content_hash=content_hash if isinstance(content_hash, str) else None,
        hash_algorithm=hash_algorithm if isinstance(hash_algorithm, str) else None,
        source_role=_safe_label(path_record.get("source_role"), SOURCE_ROLES, "unknown"),
        freshness_label=_safe_label(path_record.get("freshness_label"), FRESHNESS_LABELS, "unknown"),
        sensitivity_label=sensitivity_label,
        raw_content_eligibility=raw_content_eligibility,
        retrieval_eligibility=retrieval_eligibility,
        ingestion_eligibility=ingestion_eligibility,
        canonicality=_safe_label(path_record.get("canonicality"), CANONICALITY_LABELS, "unknown_review"),
        world_binding=_safe_label(path_record.get("world_binding"), WORLD_BINDINGS, "unknown"),
        evidence_category=_safe_label(path_record.get("evidence_category"), EVIDENCE_CATEGORIES, "unknown"),
        reorg_status="advisory",
        reorg_bucket=_reorg_bucket_for_manifest(path_record),
        reorg_reason=str(path_record.get("notes") or "imported root manifest metadata"),
        reorg_confidence=0.8,
        requires_operator_review=bool(
            path_record.get("requires_operator_review")
            or path_record.get("retrieval_eligibility") in {"blocked_unknown", "needs_operator_review"}
            or path_record.get("ingestion_eligibility") == "needs_review"
        ),
        metadata_basis="imported_root_manifest_no_raw_bodies",
        body_read=False,
        runtime_authority=False,
    )


def _reorg_bucket_for_manifest(path_record: dict[str, Any]) -> str:
    if path_record.get("raw_content_eligibility") == "no_go":
        return "sensitive_no_go"
    if path_record.get("source_role") == "generated_read_model":
        return "generated_output"
    if path_record.get("source_role") == "source_code":
        return "app_source"
    return "unknown_review"


def _upsert_root(conn: sqlite3.Connection, manifest: dict[str, Any], now: str) -> None:
    root_id = str(manifest["root_id"])
    defaults = _root_defaults(root_id)
    root_kind = str(manifest.get("root_kind") or defaults["root_kind"])
    host_kind = str(manifest.get("host_kind") or defaults["host_kind"])
    owner_scope = str(manifest.get("owner_scope") or defaults["owner_scope"])
    absolute_root = str(manifest.get("absolute_root") or defaults.get("absolute_root") or "manifest://unknown")
    canonical_status = str(defaults.get("canonical_status") or "non_canonical_manifest_import")
    conn.execute(
        """
INSERT INTO corpus_roots (
  root_id, root_kind, host_kind, owner_scope, project_id, client_id, instance_id,
  absolute_root, root_label, status, repo_url, repo_name, branch, commit_sha,
  remote_origin, canonical_status, import_status, mirror_of_root_id,
  lineage_source, created_at, updated_at, notes
) VALUES (?, ?, ?, ?, NULL, NULL, NULL, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(root_id) DO UPDATE SET
  root_kind = excluded.root_kind,
  host_kind = excluded.host_kind,
  owner_scope = excluded.owner_scope,
  absolute_root = excluded.absolute_root,
  root_label = excluded.root_label,
  status = excluded.status,
  repo_name = excluded.repo_name,
  branch = excluded.branch,
  commit_sha = excluded.commit_sha,
  remote_origin = excluded.remote_origin,
  canonical_status = excluded.canonical_status,
  import_status = excluded.import_status,
  mirror_of_root_id = excluded.mirror_of_root_id,
  lineage_source = excluded.lineage_source,
  updated_at = excluded.updated_at,
  notes = excluded.notes
""".strip(),
        (
            root_id,
            root_kind,
            host_kind,
            owner_scope,
            absolute_root,
            f"Imported manifest root {root_id}",
            "imported_manifest_metadata",
            manifest.get("repo_name"),
            manifest.get("branch"),
            manifest.get("commit_sha"),
            manifest.get("remote_origin"),
            canonical_status,
            "manifest_imported_metadata",
            defaults.get("mirror_of_root_id"),
            defaults.get("lineage_source"),
            now,
            now,
            "Imported from explicit root manifest; non-canonical metadata only.",
        ),
    )


def _insert_manifest_run(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    manifest: dict[str, Any],
    now: str,
    path_count: int,
) -> None:
    source_basis = {
        "manifest_schema_version": manifest["manifest_schema_version"],
        "manifest_generated_at": manifest["generated_at"],
        "raw_file_bodies_imported": False,
        "remote_scan": False,
        "runtime_authority": False,
    }
    conn.execute(
        """
INSERT INTO corpus_atlas_runs (
  run_id, root_id, atlas_version, started_at, completed_at, git_head, git_branch,
  repo_root, scan_mode, max_depth_policy, path_count, top_level_count,
  body_ingested, raw_sensitive_data_stored, runtime_authority,
  activation_allowed, backend_execution_authorized, source_basis_json, notes
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, ?, ?)
ON CONFLICT(run_id) DO UPDATE SET
  root_id = excluded.root_id,
  atlas_version = excluded.atlas_version,
  started_at = excluded.started_at,
  completed_at = excluded.completed_at,
  git_head = excluded.git_head,
  git_branch = excluded.git_branch,
  repo_root = excluded.repo_root,
  scan_mode = excluded.scan_mode,
  max_depth_policy = excluded.max_depth_policy,
  path_count = excluded.path_count,
  top_level_count = excluded.top_level_count,
  body_ingested = 0,
  raw_sensitive_data_stored = 0,
  runtime_authority = 0,
  activation_allowed = 0,
  backend_execution_authorized = 0,
  source_basis_json = excluded.source_basis_json,
  notes = excluded.notes
""".strip(),
        (
            run_id,
            manifest["root_id"],
            MAC_MIRROR_ATLAS_VERSION,
            manifest["generated_at"],
            now,
            manifest.get("commit_sha") or "unknown",
            manifest.get("branch") or "unknown",
            manifest.get("absolute_root") or "unknown",
            "imported_metadata_manifest_no_raw_bodies",
            "manifest_explicit_root_only",
            path_count,
            sum(1 for record in manifest["path_records"] if "/" not in record["relative_path"].strip("/")),
            stable_json(source_basis).strip(),
            "Mac/root mirror manifest import; non-canonical metadata only.",
        ),
    )


def import_root_manifest(
    *,
    manifest_path: str | Path,
    db_path: str | Path | None = None,
    run_id: str | None = None,
) -> ManifestImportResult:
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    _validate_manifest(manifest)
    db = init_corpus_atlas_schema(db_path or DEFAULT_DB_PATH)
    now = utc_now()
    run_id = run_id or _manifest_run_id(str(manifest["root_id"]), str(manifest["generated_at"]))
    records = [
        _record_from_manifest(manifest=manifest, path_record=record, run_id=run_id)
        for record in manifest["path_records"]
    ]

    conn = sqlite3.connect(db)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        _upsert_root(conn, manifest, now)
        _insert_manifest_run(conn, run_id=run_id, manifest=manifest, now=now, path_count=len(records))
        for record in records:
            _insert_path(conn, record, now)
            _insert_standard_labels(conn, record, now)
            _insert_world_binding(
                conn,
                path_id=record.path_id,
                world_id=record.world_binding,
                confidence=0.8 if record.world_binding not in {"unknown", "no_world"} else 0.4,
                basis="imported_root_manifest",
                now=now,
            )
            _insert_sensitivity_label(conn, record, now)
            _insert_reorg_candidate(conn, record, now)
        matched, mismatched = _insert_mirror_comparisons(
            conn,
            root_id=str(manifest["root_id"]),
            imported_records=records,
            now=now,
        )
        conn.commit()
    finally:
        conn.close()

    return ManifestImportResult(
        run_id=run_id,
        root_id=str(manifest["root_id"]),
        path_count=len(records),
        matched_mirror_candidates=matched,
        mismatched_mirror_candidates=mismatched,
        no_go_count=sum(1 for record in records if record.raw_content_eligibility == "no_go"),
        hashed_count=sum(1 for record in records if record.content_hash),
    )


def _insert_mirror_comparisons(
    conn: sqlite3.Connection,
    *,
    root_id: str,
    imported_records: list[CorpusPathRecord],
    now: str,
) -> tuple[int, int]:
    matched = 0
    mismatched = 0
    pc_hash_rows = conn.execute(
        """
SELECT path_id, relative_path, content_hash
FROM corpus_paths
WHERE root_id = ? AND content_hash IS NOT NULL
  AND sensitivity_label IN ('public_project','internal_project')
  AND raw_content_eligibility = 'eligible'
ORDER BY run_id DESC
""".strip(),
        (DEFAULT_PC_ROOT_ID,),
    ).fetchall()
    by_hash: dict[str, list[tuple[str, str]]] = {}
    by_relative: dict[str, tuple[str, str | None]] = {}
    for path_id, relative_path, content_hash in pc_hash_rows:
        by_hash.setdefault(content_hash, []).append((path_id, relative_path))
        by_relative.setdefault(relative_path, (path_id, content_hash))

    for record in imported_records:
        if not record.content_hash:
            continue
        for pc_path_id, pc_relative_path in by_hash.get(record.content_hash, []):
            _insert_mirror_candidate_row(
                conn,
                path_id=pc_path_id,
                mirror_root_id=root_id,
                suggested_relative_path=record.relative_path,
                mirror_kind="safe_content_hash_match",
                status="matched_hash",
                basis=f"sha256 match with PC path {pc_relative_path}",
                now=now,
            )
            matched += 1
        pc_same_relative = by_relative.get(_pc_relative_for_mac_record(root_id, record.relative_path))
        if pc_same_relative and pc_same_relative[1] and pc_same_relative[1] != record.content_hash:
            _insert_mirror_candidate_row(
                conn,
                path_id=pc_same_relative[0],
                mirror_root_id=root_id,
                suggested_relative_path=record.relative_path,
                mirror_kind="same_relative_path_hash_mismatch",
                status="hash_mismatch",
                basis="same relative path but safe content hash differs",
                now=now,
            )
            mismatched += 1
    return matched, mismatched


def _pc_relative_for_mac_record(root_id: str, relative_path: str) -> str:
    if root_id == "mac_generated_read_models":
        return f"generated/read_models/{relative_path.strip('/')}"
    return relative_path.strip("/")


def _insert_mirror_candidate_row(
    conn: sqlite3.Connection,
    *,
    path_id: str,
    mirror_root_id: str,
    suggested_relative_path: str,
    mirror_kind: str,
    status: str,
    basis: str,
    now: str,
) -> None:
    mirror_id = _row_id("cmirror", path_id, mirror_root_id, suggested_relative_path, status)
    conn.execute(
        """
INSERT INTO corpus_mirror_candidates (
  mirror_id, path_id, mirror_root_id, suggested_relative_path, mirror_kind,
  status, basis, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(path_id, mirror_root_id, suggested_relative_path) DO UPDATE SET
  mirror_kind = excluded.mirror_kind,
  status = excluded.status,
  basis = excluded.basis,
  created_at = excluded.created_at
""".strip(),
        (
            mirror_id,
            path_id,
            mirror_root_id,
            suggested_relative_path,
            mirror_kind,
            status,
            basis,
            now,
        ),
    )


def query_mac_mirror_report_section(
    *,
    db_path: str | Path | None = None,
    section: str,
) -> dict[str, Any]:
    db = init_corpus_atlas_schema(db_path or DEFAULT_DB_PATH)
    conn = sqlite3.connect(db)
    try:
        if section in {"roots", "mac-roots"}:
            items = _mac_roots(conn)
            return {"section": section, "items": items, "counts": {"mac_roots": len(items)}}
        if section == "mirror-mismatches":
            items = _mirror_rows(conn, status="hash_mismatch")
            return {"section": section, "items": items, "counts": {"hash_mismatch": len(items)}}
        if section == "mirrors":
            items = _mirror_rows(conn)
            return {"section": section, "items": items, "counts": dict(Counter(item["status"] for item in items))}
        if section == "generated-read-model-mirror":
            return _generated_read_model_mirror_report(conn)
    finally:
        conn.close()
    raise ValueError(f"unknown Mac mirror report section: {section}")


def _mac_roots(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
SELECT root_id, root_kind, host_kind, owner_scope, absolute_root, status,
       canonical_status, import_status, mirror_of_root_id, lineage_source,
       branch, commit_sha, remote_origin
FROM corpus_roots
WHERE host_kind = 'mac' OR root_id LIKE 'mac_%'
ORDER BY root_id
""".strip()
    ).fetchall()
    keys = (
        "root_id",
        "root_kind",
        "host_kind",
        "owner_scope",
        "absolute_root",
        "status",
        "canonical_status",
        "import_status",
        "mirror_of_root_id",
        "lineage_source",
        "branch",
        "commit_sha",
        "remote_origin",
    )
    return [dict(zip(keys, row)) for row in rows]


def _mirror_rows(conn: sqlite3.Connection, status: str | None = None) -> list[dict[str, Any]]:
    params: tuple[Any, ...] = ()
    where = ""
    if status:
        where = "WHERE m.status = ?"
        params = (status,)
    rows = conn.execute(
        f"""
SELECT p.root_id AS source_root_id, p.relative_path AS source_relative_path,
       m.mirror_root_id, m.suggested_relative_path, m.mirror_kind, m.status, m.basis
FROM corpus_mirror_candidates m
JOIN corpus_paths p ON p.path_id = m.path_id
{where}
ORDER BY m.mirror_root_id, p.relative_path, m.status
""".strip(),
        params,
    ).fetchall()
    keys = (
        "source_root_id",
        "source_relative_path",
        "mirror_root_id",
        "suggested_relative_path",
        "mirror_kind",
        "status",
        "basis",
    )
    return [dict(zip(keys, row)) for row in rows]


def _generated_read_model_mirror_report(conn: sqlite3.Connection) -> dict[str, Any]:
    latest_run = conn.execute(
        """
SELECT run_id
FROM corpus_atlas_runs
WHERE root_id = 'mac_generated_read_models'
ORDER BY completed_at DESC, started_at DESC
LIMIT 1
""".strip()
    ).fetchone()
    if not latest_run:
        return {
            "section": "generated-read-model-mirror",
            "items": [],
            "counts": {
                "mac_generated_read_models_imported": 0,
                "missing_expected": len(EXPECTED_GENERATED_READ_MODEL_FILES),
            },
            "missing_expected_files": list(EXPECTED_GENERATED_READ_MODEL_FILES),
            "extra_files": [],
        }
    run_id = latest_run[0]
    rows = conn.execute(
        """
SELECT relative_path, content_hash, freshness_label, retrieval_eligibility,
       ingestion_eligibility, sensitivity_label
FROM corpus_paths
WHERE root_id = 'mac_generated_read_models' AND run_id = ?
ORDER BY relative_path
""".strip(),
        (run_id,),
    ).fetchall()
    items = [
        {
            "relative_path": row[0],
            "content_hash_present": bool(row[1]),
            "freshness_label": row[2],
            "retrieval_eligibility": row[3],
            "ingestion_eligibility": row[4],
            "sensitivity_label": row[5],
        }
        for row in rows
    ]
    observed = {item["relative_path"] for item in items}
    expected = set(EXPECTED_GENERATED_READ_MODEL_FILES)
    mirror_rows = _mirror_rows(conn)
    relevant_mirror_rows = [
        item for item in mirror_rows if item["mirror_root_id"] == "mac_generated_read_models"
    ]
    return {
        "section": "generated-read-model-mirror",
        "run_id": run_id,
        "items": items,
        "missing_expected_files": sorted(expected - observed),
        "extra_files": sorted(observed - expected),
        "mirror_candidates": relevant_mirror_rows,
        "counts": {
            "observed": len(items),
            "missing_expected": len(expected - observed),
            "extra": len(observed - expected),
            **dict(Counter(item["status"] for item in relevant_mirror_rows)),
        },
    }


def format_mac_mirror_report(payload: dict[str, Any]) -> str:
    lines = [f"Mac Mirror Atlas v0 - {payload['section']}", ""]
    if payload.get("counts"):
        rendered = ", ".join(f"{key}={value}" for key, value in sorted(payload["counts"].items()))
        lines.append(f"Counts: {rendered}")
        lines.append("")
    if payload["section"] == "generated-read-model-mirror":
        if payload.get("missing_expected_files"):
            lines.append("Missing Expected Files:")
            lines.extend(f"- {item}" for item in payload["missing_expected_files"])
            lines.append("")
        if payload.get("extra_files"):
            lines.append("Extra Files:")
            lines.extend(f"- {item}" for item in payload["extra_files"])
            lines.append("")
    lines.append("Items:")
    if not payload.get("items"):
        lines.append("- none")
    else:
        for item in payload["items"]:
            if "root_id" in item:
                lines.append(
                    f"- {item['root_id']} ({item['root_kind']}, {item['canonical_status']}, {item['import_status']})"
                )
            elif "source_relative_path" in item:
                lines.append(
                    f"- {item['source_relative_path']} -> {item['mirror_root_id']}:{item['suggested_relative_path']} ({item['status']})"
                )
            else:
                lines.append(
                    f"- {item['relative_path']} ({item['freshness_label']}, {item['retrieval_eligibility']}, hash={item['content_hash_present']})"
                )
    lines.extend(
        [
            "",
            "Boundary:",
            "- Manifest imports are metadata-only and non-canonical.",
            "- No Mac filesystem crawl, SSH, SCP, rsync, copy, move, runtime, or agent activation is authorized.",
        ]
    )
    return "\n".join(lines)
