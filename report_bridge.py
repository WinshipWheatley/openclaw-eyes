"""Report Bridge v0 for local node report package imports.

This module records sanitized report package metadata in the Business Ops ledger
under a separate ``report_bridge_*`` namespace. It is a local import layer only:
no runtime, deployment, remote management, agent activation, tool execution,
model execution, container execution, network authority, or truth promotion is
granted.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from business_ops_ledger import DEFAULT_DB_PATH, init_business_ops_ledger


REPORT_BRIDGE_VERSION = "report_bridge_v0"
REPORT_BRIDGE_SCHEMA_VERSION = "openclaw.report_bridge.v0"
DEFAULT_REPORT_BRIDGE_INBOX = Path("/mnt/e/openclaw/node_uplink/inbox")
MANIFEST_NAME = "report_bridge_manifest.json"

NO_AUTHORITY_FLAGS = {
    "runtime_authority": False,
    "deployment_authority": False,
    "remote_management_allowed": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "model_execution_allowed": False,
    "container_execution_allowed": False,
    "network_authority": False,
    "truth_promotion_allowed": False,
}

ALLOWED_PACKAGE_KINDS = {
    "node_report_package",
    "read_model_report_package",
    "generated_read_model_package",
    "operator_report_package",
}

SAFE_FILE_ROLES = {
    "read_model",
    "operator_report",
    "report",
    "receipt_summary",
    "artifact_metadata",
}

SAFE_SUFFIXES = {".json", ".md", ".txt"}

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
    "private",
)

FORBIDDEN_DATA_CLASS_HINTS = {
    "real_client_data",
    "client_private_data",
    "credentials",
    "secrets",
    "tokens",
    "raw_private_bodies",
    "legal_private",
    "tax_private",
    "finance_private",
}


@dataclass(frozen=True)
class ReportBridgeFile:
    relative_path: str
    size_bytes: int
    sha256: str
    role: str
    sensitivity_label: str
    raw_content_eligibility: str
    retrieval_eligibility: str
    ingestion_eligibility: str
    evidence_category: str
    notes: str


@dataclass(frozen=True)
class ReportBridgePackage:
    package_path: Path
    manifest_path: Path
    manifest_hash: str
    manifest: dict[str, Any]
    files: tuple[ReportBridgeFile, ...]


@dataclass(frozen=True)
class ReportBridgeImportResult:
    run_id: str
    db_path: str
    package_id: str
    package_path: str
    node_id: str
    node_kind: str
    project_id: str | None
    client_id: str | None
    file_count: int
    imported_file_count: int
    rejected_file_count: int
    status: str
    raw_body_included: bool
    client_data_included: bool
    truth_promotion_allowed: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256(
        "\0".join(str(part) for part in parts).encode("utf-8")
    ).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sql_statements() -> tuple[str, ...]:
    return (
        """
CREATE TABLE IF NOT EXISTS report_bridge_runs (
  run_id TEXT PRIMARY KEY,
  bridge_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  package_id TEXT,
  package_path TEXT,
  status TEXT NOT NULL,
  packages_imported INTEGER NOT NULL DEFAULT 0,
  files_imported INTEGER NOT NULL DEFAULT 0,
  files_rejected INTEGER NOT NULL DEFAULT 0,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  deployment_authority INTEGER NOT NULL DEFAULT 0,
  remote_management_allowed INTEGER NOT NULL DEFAULT 0,
  agent_activation_allowed INTEGER NOT NULL DEFAULT 0,
  tool_execution_allowed INTEGER NOT NULL DEFAULT 0,
  model_execution_allowed INTEGER NOT NULL DEFAULT 0,
  container_execution_allowed INTEGER NOT NULL DEFAULT 0,
  network_authority INTEGER NOT NULL DEFAULT 0,
  truth_promotion_allowed INTEGER NOT NULL DEFAULT 0,
  raw_body_included INTEGER NOT NULL DEFAULT 0,
  client_data_included INTEGER NOT NULL DEFAULT 0,
  source_basis_json TEXT NOT NULL,
  notes TEXT
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS report_bridge_nodes (
  node_id TEXT PRIMARY KEY,
  node_kind TEXT NOT NULL,
  owner_scope TEXT NOT NULL,
  source_root_id TEXT NOT NULL,
  project_id TEXT,
  client_id TEXT,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  package_count INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL,
  operator_review_required INTEGER NOT NULL DEFAULT 0,
  notes TEXT
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS report_bridge_projects (
  project_key TEXT PRIMARY KEY,
  project_id TEXT,
  client_id TEXT,
  owner_scope TEXT NOT NULL,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  package_count INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL,
  notes TEXT
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS report_bridge_packages (
  package_id TEXT PRIMARY KEY,
  schema_version TEXT NOT NULL,
  package_kind TEXT NOT NULL,
  node_id TEXT NOT NULL,
  node_kind TEXT NOT NULL,
  owner_scope TEXT NOT NULL,
  project_id TEXT,
  client_id TEXT,
  source_root_id TEXT NOT NULL,
  package_path TEXT NOT NULL,
  manifest_path TEXT NOT NULL,
  manifest_hash TEXT NOT NULL,
  generated_at TEXT NOT NULL,
  imported_at TEXT NOT NULL,
  run_id TEXT NOT NULL,
  file_count INTEGER NOT NULL DEFAULT 0,
  imported_file_count INTEGER NOT NULL DEFAULT 0,
  rejected_file_count INTEGER NOT NULL DEFAULT 0,
  total_bytes INTEGER NOT NULL DEFAULT 0,
  sensitivity_summary_json TEXT NOT NULL,
  allowed_data_classes_json TEXT NOT NULL,
  forbidden_data_classes_json TEXT NOT NULL,
  no_authority_flags_json TEXT NOT NULL,
  raw_body_included INTEGER NOT NULL DEFAULT 0,
  client_data_included INTEGER NOT NULL DEFAULT 0,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  deployment_authority INTEGER NOT NULL DEFAULT 0,
  remote_management_allowed INTEGER NOT NULL DEFAULT 0,
  agent_activation_allowed INTEGER NOT NULL DEFAULT 0,
  tool_execution_allowed INTEGER NOT NULL DEFAULT 0,
  model_execution_allowed INTEGER NOT NULL DEFAULT 0,
  container_execution_allowed INTEGER NOT NULL DEFAULT 0,
  network_authority INTEGER NOT NULL DEFAULT 0,
  truth_promotion_allowed INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL,
  notes TEXT,
  FOREIGN KEY (run_id) REFERENCES report_bridge_runs(run_id),
  FOREIGN KEY (node_id) REFERENCES report_bridge_nodes(node_id)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS report_bridge_files (
  file_id TEXT PRIMARY KEY,
  package_id TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  payload_path TEXT NOT NULL,
  role TEXT NOT NULL,
  size_bytes INTEGER NOT NULL,
  sha256 TEXT NOT NULL,
  hash_verified INTEGER NOT NULL DEFAULT 1,
  imported INTEGER NOT NULL DEFAULT 1,
  sensitivity_label TEXT NOT NULL,
  raw_content_eligibility TEXT NOT NULL,
  retrieval_eligibility TEXT NOT NULL,
  ingestion_eligibility TEXT NOT NULL,
  evidence_category TEXT NOT NULL,
  notes TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (package_id) REFERENCES report_bridge_packages(package_id) ON DELETE CASCADE,
  UNIQUE(package_id, relative_path)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS report_bridge_import_receipts (
  receipt_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  package_id TEXT,
  package_path TEXT NOT NULL,
  result TEXT NOT NULL,
  imported_file_count INTEGER NOT NULL DEFAULT 0,
  rejected_file_count INTEGER NOT NULL DEFAULT 0,
  checked_at TEXT NOT NULL,
  manifest_hash TEXT,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  deployment_authority INTEGER NOT NULL DEFAULT 0,
  remote_management_allowed INTEGER NOT NULL DEFAULT 0,
  agent_activation_allowed INTEGER NOT NULL DEFAULT 0,
  tool_execution_allowed INTEGER NOT NULL DEFAULT 0,
  model_execution_allowed INTEGER NOT NULL DEFAULT 0,
  container_execution_allowed INTEGER NOT NULL DEFAULT 0,
  network_authority INTEGER NOT NULL DEFAULT 0,
  truth_promotion_allowed INTEGER NOT NULL DEFAULT 0,
  raw_body_included INTEGER NOT NULL DEFAULT 0,
  client_data_included INTEGER NOT NULL DEFAULT 0,
  notes TEXT,
  FOREIGN KEY (run_id) REFERENCES report_bridge_runs(run_id)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS report_bridge_rejections (
  rejection_id TEXT PRIMARY KEY,
  run_id TEXT,
  package_id TEXT,
  package_path TEXT NOT NULL,
  rejection_type TEXT NOT NULL,
  rejection_reason TEXT NOT NULL,
  relative_path TEXT,
  created_at TEXT NOT NULL
)
""".strip(),
        "CREATE INDEX IF NOT EXISTS idx_report_bridge_packages_node ON report_bridge_packages(node_id)",
        "CREATE INDEX IF NOT EXISTS idx_report_bridge_packages_project ON report_bridge_packages(project_id, client_id)",
        "CREATE INDEX IF NOT EXISTS idx_report_bridge_files_role ON report_bridge_files(role)",
        "CREATE INDEX IF NOT EXISTS idx_report_bridge_rejections_type ON report_bridge_rejections(rejection_type)",
    )


def init_report_bridge_schema(db_path: str | Path | None = None) -> str:
    path = str(db_path or DEFAULT_DB_PATH)
    parent = Path(path).parent
    if parent and not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)
    init_business_ops_ledger(path)
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        for statement in _sql_statements():
            conn.execute(statement)
        conn.commit()
    finally:
        conn.close()
    return path


def report_bridge_table_names(db_path: str | Path | None = None) -> tuple[str, ...]:
    path = init_report_bridge_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            """
SELECT name
FROM sqlite_master
WHERE type = 'table' AND name LIKE 'report_bridge_%'
ORDER BY name
""".strip()
        ).fetchall()
        return tuple(row[0] for row in rows)
    finally:
        conn.close()


def resolve_report_bridge_package(
    *,
    package: str | Path | None = None,
    inbox: str | Path = DEFAULT_REPORT_BRIDGE_INBOX,
) -> Path:
    if package:
        candidate = Path(package)
        if candidate.is_file() and candidate.name == MANIFEST_NAME:
            return candidate.parent
        if candidate.is_dir() and (candidate / MANIFEST_NAME).is_file():
            return candidate
        raise ValueError(f"report bridge package is missing {MANIFEST_NAME}: {candidate}")

    inbox_path = Path(inbox)
    candidates: list[Path] = []
    if inbox_path.is_dir():
        if (inbox_path / MANIFEST_NAME).is_file():
            candidates.append(inbox_path)
        candidates.extend(
            path
            for path in inbox_path.iterdir()
            if path.is_dir() and (path / MANIFEST_NAME).is_file()
        )
    if not candidates:
        raise ValueError(f"no report bridge package found in inbox: {inbox_path}")
    return max(candidates, key=lambda item: (item / MANIFEST_NAME).stat().st_mtime)


def _required_text(manifest: Mapping[str, Any], key: str) -> str:
    value = manifest.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"manifest field is required: {key}")
    return value.strip()


def _optional_text(manifest: Mapping[str, Any], key: str) -> str | None:
    value = manifest.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"manifest field must be string or null: {key}")
    stripped = value.strip()
    return stripped or None


def _required_list(manifest: Mapping[str, Any], key: str) -> list[Any]:
    value = manifest.get(key)
    if not isinstance(value, list):
        raise ValueError(f"manifest field must be a list: {key}")
    return value


def _required_mapping(manifest: Mapping[str, Any], key: str) -> dict[str, Any]:
    value = manifest.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"manifest field must be an object: {key}")
    return dict(value)


def _is_true(manifest: Mapping[str, Any], *keys: str) -> bool:
    for key in keys:
        if manifest.get(key) is True:
            return True
    return False


def _authority_flag(manifest: Mapping[str, Any], key: str) -> bool:
    nested = manifest.get("no_authority_flags")
    if isinstance(nested, Mapping) and key in nested:
        value = nested[key]
    elif key in manifest:
        value = manifest[key]
    else:
        raise ValueError(f"manifest no-authority flag is required: {key}")
    if value is not False:
        raise ValueError(f"manifest no-authority flag must be false: {key}")
    return False


def _safe_relative_path(relative_path: str) -> Path:
    path = Path(relative_path)
    if path.is_absolute() or ".." in path.parts or not relative_path.strip():
        raise ValueError(f"unsafe package relative path: {relative_path}")
    return path


def _is_no_go_relative_path(relative_path: str) -> bool:
    parts = {part.lower() for part in Path(relative_path).parts}
    lowered = Path(relative_path).name.lower()
    if parts & NO_GO_PARTS:
        return True
    return any(hint in lowered for hint in NO_GO_FILE_HINTS)


def _normalized_data_classes(values: Iterable[Any]) -> tuple[str, ...]:
    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("data classes must be non-empty strings")
        normalized.append(value.strip())
    return tuple(normalized)


def _validate_manifest_shape(manifest: dict[str, Any]) -> None:
    schema_version = _required_text(manifest, "schema_version")
    if schema_version != REPORT_BRIDGE_SCHEMA_VERSION:
        raise ValueError(f"unsupported report bridge schema: {schema_version}")
    package_kind = _required_text(manifest, "package_kind")
    if package_kind not in ALLOWED_PACKAGE_KINDS:
        raise ValueError(f"unsupported report bridge package_kind: {package_kind}")
    for key in (
        "package_id",
        "generated_at",
        "node_id",
        "node_kind",
        "owner_scope",
        "source_root_id",
    ):
        _required_text(manifest, key)
    _optional_text(manifest, "project_id")
    _optional_text(manifest, "client_id")
    _required_mapping(manifest, "sensitivity_summary")
    _normalized_data_classes(_required_list(manifest, "allowed_data_classes"))
    _normalized_data_classes(_required_list(manifest, "forbidden_data_classes"))
    _required_list(manifest, "files")
    for key in NO_AUTHORITY_FLAGS:
        _authority_flag(manifest, key)
    if _is_true(manifest, "raw_body_included", "raw_bodies_included", "raw_file_bodies_included"):
        raise ValueError("report bridge package includes raw bodies")
    if _is_true(manifest, "client_data_included", "real_client_data_included"):
        raise ValueError("report bridge package includes client data")


def _validate_file_record(package_path: Path, record: Mapping[str, Any]) -> ReportBridgeFile:
    relative_text = str(record.get("relative_path") or "").strip()
    relative_path = _safe_relative_path(relative_text)
    payload_path = package_path / relative_path
    role = str(record.get("role") or "").strip()
    if role not in SAFE_FILE_ROLES:
        raise ValueError(f"unsupported report bridge file role: {role or '<missing>'}")
    if _is_no_go_relative_path(relative_text):
        raise ValueError(f"no-go report bridge file path: {relative_text}")
    if relative_path.suffix not in SAFE_SUFFIXES:
        raise ValueError(f"unsupported report bridge file suffix: {relative_text}")
    if not payload_path.is_file():
        raise ValueError(f"manifest file is missing from package: {relative_text}")

    size = record.get("size")
    if size is None:
        size = record.get("size_bytes")
    if not isinstance(size, int) or size < 0:
        raise ValueError(f"bad size for report bridge file: {relative_text}")
    if payload_path.stat().st_size != size:
        raise ValueError(f"size mismatch for report bridge file: {relative_text}")

    expected_hash = str(record.get("sha256") or "").strip().lower()
    if len(expected_hash) != 64:
        raise ValueError(f"bad sha256 for report bridge file: {relative_text}")
    observed_hash = _sha256_file(payload_path)
    if observed_hash != expected_hash:
        raise ValueError(f"hash mismatch for report bridge file: {relative_text}")

    sensitivity_label = str(record.get("sensitivity_label") or "internal_project").strip()
    raw_content_eligibility = str(record.get("raw_content_eligibility") or "metadata_only").strip()
    retrieval_eligibility = str(record.get("retrieval_eligibility") or "metadata_only").strip()
    ingestion_eligibility = str(record.get("ingestion_eligibility") or "metadata_only").strip()
    evidence_category = str(record.get("evidence_category") or role).strip()
    notes = str(record.get("notes") or "report_bridge_metadata_only_import").strip()
    return ReportBridgeFile(
        relative_path=relative_text,
        size_bytes=size,
        sha256=expected_hash,
        role=role,
        sensitivity_label=sensitivity_label,
        raw_content_eligibility=raw_content_eligibility,
        retrieval_eligibility=retrieval_eligibility,
        ingestion_eligibility=ingestion_eligibility,
        evidence_category=evidence_category,
        notes=notes,
    )


def validate_report_bridge_package(package_path: str | Path) -> ReportBridgePackage:
    package = Path(package_path)
    manifest_path = package / MANIFEST_NAME
    if not manifest_path.is_file():
        raise ValueError(f"report bridge package is missing {MANIFEST_NAME}: {package}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("report bridge manifest must be a JSON object")
    _validate_manifest_shape(manifest)
    files = tuple(
        _validate_file_record(package, record)
        for record in manifest["files"]
        if isinstance(record, Mapping)
    )
    if len(files) != len(manifest["files"]):
        raise ValueError("report bridge file records must be JSON objects")
    return ReportBridgePackage(
        package_path=package,
        manifest_path=manifest_path,
        manifest_hash=_sha256_file(manifest_path),
        manifest=manifest,
        files=files,
    )


def _json_list(values: Iterable[Any]) -> str:
    return stable_json(list(values))


def _record_rejection(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    package_id: str | None,
    package_path: str,
    rejection_type: str,
    reason: str,
    relative_path: str | None = None,
) -> None:
    now = utc_now()
    conn.execute(
        """
INSERT INTO report_bridge_rejections (
  rejection_id, run_id, package_id, package_path, rejection_type,
  rejection_reason, relative_path, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""".strip(),
        (
            _row_id("rbrej", run_id, package_id or "unknown", package_path, rejection_type, reason, relative_path or ""),
            run_id,
            package_id,
            package_path,
            rejection_type,
            reason,
            relative_path,
            now,
        ),
    )


def import_report_bridge_package(
    *,
    package: str | Path | None = None,
    inbox: str | Path = DEFAULT_REPORT_BRIDGE_INBOX,
    db_path: str | Path | None = None,
    run_id: str | None = None,
) -> ReportBridgeImportResult:
    path = init_report_bridge_schema(db_path)
    now = utc_now()
    package_path = resolve_report_bridge_package(package=package, inbox=inbox)
    resolved_run_id = run_id or _row_id("rbrun", package_path.as_posix(), now)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            """
INSERT INTO report_bridge_runs (
  run_id, bridge_version, created_at, package_path, status,
  source_basis_json, notes
) VALUES (?, ?, ?, ?, 'started', ?, ?)
ON CONFLICT(run_id) DO UPDATE SET
  bridge_version = excluded.bridge_version,
  package_path = excluded.package_path,
  status = excluded.status,
  source_basis_json = excluded.source_basis_json,
  notes = excluded.notes
""".strip(),
            (
                resolved_run_id,
                REPORT_BRIDGE_VERSION,
                now,
                package_path.as_posix(),
                stable_json(
                    {
                        "default_inbox": DEFAULT_REPORT_BRIDGE_INBOX.as_posix(),
                        "raw_body_included": False,
                        "client_data_included": False,
                        "truth_promotion": False,
                    }
                ),
                "Local report package metadata import only.",
            ),
        )
        try:
            package_record = validate_report_bridge_package(package_path)
        except Exception as exc:
            _record_rejection(
                conn,
                run_id=resolved_run_id,
                package_id=None,
                package_path=package_path.as_posix(),
                rejection_type="package_validation_failed",
                reason=str(exc),
            )
            conn.execute(
                """
UPDATE report_bridge_runs
SET completed_at = ?, status = 'rejected', files_rejected = 1
WHERE run_id = ?
""".strip(),
                (utc_now(), resolved_run_id),
            )
            conn.execute(
                """
INSERT INTO report_bridge_import_receipts (
  receipt_id, run_id, package_id, package_path, result, rejected_file_count,
  checked_at, notes
) VALUES (?, ?, NULL, ?, 'rejected', 1, ?, ?)
""".strip(),
                (
                    _row_id("rbrcpt", resolved_run_id, package_path.as_posix()),
                    resolved_run_id,
                    package_path.as_posix(),
                    utc_now(),
                    str(exc),
                ),
            )
            conn.commit()
            raise

        manifest = package_record.manifest
        package_id = _required_text(manifest, "package_id")
        node_id = _required_text(manifest, "node_id")
        node_kind = _required_text(manifest, "node_kind")
        owner_scope = _required_text(manifest, "owner_scope")
        source_root_id = _required_text(manifest, "source_root_id")
        project_id = _optional_text(manifest, "project_id")
        client_id = _optional_text(manifest, "client_id")
        generated_at = _required_text(manifest, "generated_at")
        package_kind = _required_text(manifest, "package_kind")
        allowed_data_classes = _normalized_data_classes(_required_list(manifest, "allowed_data_classes"))
        forbidden_data_classes = _normalized_data_classes(_required_list(manifest, "forbidden_data_classes"))
        no_authority = {key: False for key in NO_AUTHORITY_FLAGS}
        sensitivity_summary = _required_mapping(manifest, "sensitivity_summary")
        total_bytes = sum(file.size_bytes for file in package_record.files)

        node_existing = conn.execute(
            "SELECT first_seen_at FROM report_bridge_nodes WHERE node_id = ?",
            (node_id,),
        ).fetchone()
        first_seen = node_existing["first_seen_at"] if node_existing else now
        conn.execute(
            """
INSERT INTO report_bridge_nodes (
  node_id, node_kind, owner_scope, source_root_id, project_id, client_id,
  first_seen_at, last_seen_at, package_count, status,
  operator_review_required, notes
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 'observed_metadata_only', 0, ?)
ON CONFLICT(node_id) DO UPDATE SET
  node_kind = excluded.node_kind,
  owner_scope = excluded.owner_scope,
  source_root_id = excluded.source_root_id,
  project_id = excluded.project_id,
  client_id = excluded.client_id,
  last_seen_at = excluded.last_seen_at,
  package_count = report_bridge_nodes.package_count + 1,
  status = excluded.status,
  notes = excluded.notes
""".strip(),
            (
                node_id,
                node_kind,
                owner_scope,
                source_root_id,
                project_id,
                client_id,
                first_seen,
                now,
                "Observed through local Report Bridge package metadata.",
            ),
        )

        if project_id or client_id:
            project_key = _row_id("rbproj", project_id or "none", client_id or "none")
            existing_project = conn.execute(
                "SELECT first_seen_at FROM report_bridge_projects WHERE project_key = ?",
                (project_key,),
            ).fetchone()
            project_first_seen = existing_project["first_seen_at"] if existing_project else now
            conn.execute(
                """
INSERT INTO report_bridge_projects (
  project_key, project_id, client_id, owner_scope, first_seen_at,
  last_seen_at, package_count, status, notes
) VALUES (?, ?, ?, ?, ?, ?, 1, 'observed_metadata_only', ?)
ON CONFLICT(project_key) DO UPDATE SET
  project_id = excluded.project_id,
  client_id = excluded.client_id,
  owner_scope = excluded.owner_scope,
  last_seen_at = excluded.last_seen_at,
  package_count = report_bridge_projects.package_count + 1,
  status = excluded.status,
  notes = excluded.notes
""".strip(),
                (
                    project_key,
                    project_id,
                    client_id,
                    owner_scope,
                    project_first_seen,
                    now,
                    "Project/client metadata only; no client data access.",
                ),
            )

        existing_package = conn.execute(
            "SELECT package_id FROM report_bridge_packages WHERE package_id = ?",
            (package_id,),
        ).fetchone()
        if existing_package:
            conn.execute("DELETE FROM report_bridge_files WHERE package_id = ?", (package_id,))
        conn.execute(
            """
INSERT INTO report_bridge_packages (
  package_id, schema_version, package_kind, node_id, node_kind, owner_scope,
  project_id, client_id, source_root_id, package_path, manifest_path,
  manifest_hash, generated_at, imported_at, run_id, file_count,
  imported_file_count, rejected_file_count, total_bytes,
  sensitivity_summary_json, allowed_data_classes_json,
  forbidden_data_classes_json, no_authority_flags_json, status, notes
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, 'imported', ?)
ON CONFLICT(package_id) DO UPDATE SET
  schema_version = excluded.schema_version,
  package_kind = excluded.package_kind,
  node_id = excluded.node_id,
  node_kind = excluded.node_kind,
  owner_scope = excluded.owner_scope,
  project_id = excluded.project_id,
  client_id = excluded.client_id,
  source_root_id = excluded.source_root_id,
  package_path = excluded.package_path,
  manifest_path = excluded.manifest_path,
  manifest_hash = excluded.manifest_hash,
  generated_at = excluded.generated_at,
  imported_at = excluded.imported_at,
  run_id = excluded.run_id,
  file_count = excluded.file_count,
  imported_file_count = excluded.imported_file_count,
  rejected_file_count = excluded.rejected_file_count,
  total_bytes = excluded.total_bytes,
  sensitivity_summary_json = excluded.sensitivity_summary_json,
  allowed_data_classes_json = excluded.allowed_data_classes_json,
  forbidden_data_classes_json = excluded.forbidden_data_classes_json,
  no_authority_flags_json = excluded.no_authority_flags_json,
  status = excluded.status,
  notes = excluded.notes
""".strip(),
            (
                package_id,
                REPORT_BRIDGE_SCHEMA_VERSION,
                package_kind,
                node_id,
                node_kind,
                owner_scope,
                project_id,
                client_id,
                source_root_id,
                package_path.as_posix(),
                package_record.manifest_path.as_posix(),
                package_record.manifest_hash,
                generated_at,
                now,
                resolved_run_id,
                len(package_record.files),
                len(package_record.files),
                total_bytes,
                stable_json(sensitivity_summary),
                _json_list(allowed_data_classes),
                _json_list(forbidden_data_classes),
                stable_json(no_authority),
                "Metadata-only report package import; no raw file body stored.",
            ),
        )
        for file_record in package_record.files:
            conn.execute(
                """
INSERT INTO report_bridge_files (
  file_id, package_id, relative_path, payload_path, role, size_bytes,
  sha256, hash_verified, imported, sensitivity_label,
  raw_content_eligibility, retrieval_eligibility, ingestion_eligibility,
  evidence_category, notes, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(package_id, relative_path) DO UPDATE SET
  payload_path = excluded.payload_path,
  role = excluded.role,
  size_bytes = excluded.size_bytes,
  sha256 = excluded.sha256,
  hash_verified = excluded.hash_verified,
  imported = excluded.imported,
  sensitivity_label = excluded.sensitivity_label,
  raw_content_eligibility = excluded.raw_content_eligibility,
  retrieval_eligibility = excluded.retrieval_eligibility,
  ingestion_eligibility = excluded.ingestion_eligibility,
  evidence_category = excluded.evidence_category,
  notes = excluded.notes,
  created_at = excluded.created_at
""".strip(),
                (
                    _row_id("rbfile", package_id, file_record.relative_path),
                    package_id,
                    file_record.relative_path,
                    (package_path / file_record.relative_path).as_posix(),
                    file_record.role,
                    file_record.size_bytes,
                    file_record.sha256,
                    file_record.sensitivity_label,
                    file_record.raw_content_eligibility,
                    file_record.retrieval_eligibility,
                    file_record.ingestion_eligibility,
                    file_record.evidence_category,
                    file_record.notes,
                    now,
                ),
            )

        conn.execute(
            """
INSERT INTO report_bridge_import_receipts (
  receipt_id, run_id, package_id, package_path, result,
  imported_file_count, rejected_file_count, checked_at, manifest_hash, notes
) VALUES (?, ?, ?, ?, 'imported', ?, 0, ?, ?, ?)
ON CONFLICT(receipt_id) DO NOTHING
""".strip(),
            (
                _row_id("rbrcpt", resolved_run_id, package_id),
                resolved_run_id,
                package_id,
                package_path.as_posix(),
                len(package_record.files),
                utc_now(),
                package_record.manifest_hash,
                "Validated hashes and imported metadata only.",
            ),
        )
        conn.execute(
            """
UPDATE report_bridge_runs
SET completed_at = ?, package_id = ?, status = 'imported',
    packages_imported = 1, files_imported = ?, files_rejected = 0
WHERE run_id = ?
""".strip(),
            (utc_now(), package_id, len(package_record.files), resolved_run_id),
        )
        conn.commit()
        return ReportBridgeImportResult(
            run_id=resolved_run_id,
            db_path=path,
            package_id=package_id,
            package_path=package_path.as_posix(),
            node_id=node_id,
            node_kind=node_kind,
            project_id=project_id,
            client_id=client_id,
            file_count=len(package_record.files),
            imported_file_count=len(package_record.files),
            rejected_file_count=0,
            status="imported",
            raw_body_included=False,
            client_data_included=False,
            truth_promotion_allowed=False,
        )
    finally:
        conn.close()


def _latest_run_id(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        """
SELECT run_id
FROM report_bridge_runs
ORDER BY completed_at DESC, created_at DESC, run_id DESC
LIMIT 1
""".strip()
    ).fetchone()
    return row["run_id"] if row else None


def _all_package_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
SELECT package_id, package_kind, node_id, node_kind, owner_scope, project_id,
       client_id, source_root_id, generated_at, imported_at, file_count,
       imported_file_count, status
FROM report_bridge_packages
ORDER BY imported_at DESC, package_id
""".strip()
    ).fetchall()
    return [dict(row) for row in rows]


def _node_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
SELECT node_id, node_kind, owner_scope, source_root_id, project_id, client_id,
       package_count, status, last_seen_at
FROM report_bridge_nodes
ORDER BY node_id
""".strip()
    ).fetchall()
    return [dict(row) for row in rows]


def _project_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
SELECT project_key, project_id, client_id, owner_scope, package_count, status,
       last_seen_at
FROM report_bridge_projects
ORDER BY project_id, client_id
""".strip()
    ).fetchall()
    return [dict(row) for row in rows]


def _rejection_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
SELECT run_id, package_id, package_path, rejection_type, rejection_reason,
       relative_path, created_at
FROM report_bridge_rejections
ORDER BY created_at DESC, rejection_id
""".strip()
    ).fetchall()
    return [dict(row) for row in rows]


def build_report_bridge_report(
    db_path: str | Path | None = None,
    *,
    report: str = "summary",
    run_id: str | None = None,
) -> dict[str, Any]:
    path = init_report_bridge_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        resolved_run_id = run_id or _latest_run_id(conn)
        runs = conn.execute(
            """
SELECT *
FROM report_bridge_runs
ORDER BY completed_at DESC, created_at DESC, run_id DESC
""".strip()
        ).fetchall()
        packages = _all_package_rows(conn)
        nodes = _node_rows(conn)
        projects = _project_rows(conn)
        rejections = _rejection_rows(conn)
        files = conn.execute(
            "SELECT role, sensitivity_label, retrieval_eligibility, ingestion_eligibility FROM report_bridge_files"
        ).fetchall()
        counts = {
            "runs": len(runs),
            "packages": len(packages),
            "nodes": len(nodes),
            "projects": len(projects),
            "rejections": len(rejections),
            "files": len(files),
            "file_roles": dict(sorted(Counter(row["role"] for row in files).items())),
            "sensitivity_labels": dict(sorted(Counter(row["sensitivity_label"] for row in files).items())),
            "retrieval_eligibility": dict(sorted(Counter(row["retrieval_eligibility"] for row in files).items())),
            "ingestion_eligibility": dict(sorted(Counter(row["ingestion_eligibility"] for row in files).items())),
            "package_status": dict(sorted(Counter(row["status"] for row in packages).items())),
        }
        latest_run = dict(runs[0]) if runs else None
        if report == "summary":
            items = packages[:10]
        elif report == "packages":
            items = packages
        elif report == "rejected":
            items = rejections
        elif report == "nodes":
            items = nodes
        elif report == "projects":
            items = projects
        elif report == "latest":
            items = packages[:1]
        else:
            raise ValueError(f"unknown report bridge report: {report}")
        return {
            "status": "ok",
            "report": report,
            "db_path": str(path),
            "run_id": resolved_run_id,
            "latest_run": latest_run,
            "counts": counts,
            "items": items,
            "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
            "raw_body_imported": False,
            "client_data_imported": False,
            "truth_promoted": False,
        }
    finally:
        conn.close()


def format_import_result(result: ReportBridgeImportResult) -> str:
    return "\n".join(
        [
            "Report Bridge v0 Import",
            "",
            f"Run: `{result.run_id}`",
            f"Package: `{result.package_id}`",
            f"Package path: `{result.package_path}`",
            f"Node: `{result.node_id}` ({result.node_kind})",
            f"Project: `{result.project_id or 'none'}`",
            f"Client: `{result.client_id or 'none'}`",
            f"Files imported: {result.imported_file_count}/{result.file_count}",
            f"Rejected files: {result.rejected_file_count}",
            f"Status: {result.status}",
            "",
            "Boundary:",
            "- Imported metadata and safe report/read-model file records only.",
            "- No raw bodies, client data, truth promotion, runtime, agent, tool, network, model, container, deployment, or remote-management authority.",
        ]
    )


def format_report_bridge_report(payload: dict[str, Any]) -> str:
    lines = [
        f"Report Bridge v0 - {payload['report']}",
        "",
        f"Runs: {payload['counts']['runs']}",
        f"Packages: {payload['counts']['packages']}",
        f"Nodes: {payload['counts']['nodes']}",
        f"Projects: {payload['counts']['projects']}",
        f"Files: {payload['counts']['files']}",
        f"Rejections: {payload['counts']['rejections']}",
        "",
        "Counts:",
    ]
    for key in (
        "file_roles",
        "sensitivity_labels",
        "retrieval_eligibility",
        "ingestion_eligibility",
        "package_status",
    ):
        rendered = ", ".join(
            f"{name}={count}" for name, count in sorted(payload["counts"][key].items())
        )
        lines.append(f"- {key}: {rendered or 'none'}")
    lines.extend(["", "Items:"])
    for item in payload.get("items") or []:
        if "rejection_type" in item:
            lines.append(
                f"- {item['rejection_type']}: {item['package_path']} ({item['rejection_reason']})"
            )
        elif "node_id" in item and "package_id" not in item:
            lines.append(
                f"- {item['node_id']} ({item['node_kind']}, packages={item['package_count']}, {item['status']})"
            )
        elif "project_key" in item:
            lines.append(
                f"- project={item['project_id'] or 'none'} client={item['client_id'] or 'none'} packages={item['package_count']}"
            )
        else:
            lines.append(
                f"- {item['package_id']} from {item['node_id']} ({item['package_kind']}, files={item['imported_file_count']}, {item['status']})"
            )
    lines.extend(
        [
            "",
            "Boundary:",
            "- Report Bridge rows are metadata/read-model/report import records only.",
            "- Package arrival is not approval, freshness, truth promotion, runtime authority, or deployment authority.",
            "- Default inbox: `/mnt/e/openclaw/node_uplink/inbox`.",
        ]
    )
    return "\n".join(lines)


__all__ = [
    "DEFAULT_REPORT_BRIDGE_INBOX",
    "MANIFEST_NAME",
    "NO_AUTHORITY_FLAGS",
    "REPORT_BRIDGE_SCHEMA_VERSION",
    "REPORT_BRIDGE_VERSION",
    "ReportBridgeImportResult",
    "build_report_bridge_report",
    "format_import_result",
    "format_report_bridge_report",
    "import_report_bridge_package",
    "init_report_bridge_schema",
    "report_bridge_table_names",
    "resolve_report_bridge_package",
    "stable_json",
    "validate_report_bridge_package",
]
