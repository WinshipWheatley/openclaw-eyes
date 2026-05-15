"""External AI Context Packager v0 for OpenClaw.

This module builds focused, upload-ready context packs for external AI
workspaces and local agents. It is a packaging/export layer only: no uploads,
no browser automation, no network calls, no runtime activation, and no private
or no-go raw content access.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import zipfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from business_ops_ledger import DEFAULT_DB_PATH, init_business_ops_ledger
from generated_read_model_files import (
    canonical_generated_read_model_records,
    is_no_go_generated_read_model_relative_path,
)


ROOT = Path(__file__).resolve().parent
CONTEXT_PACK_VERSION = "external_ai_context_packager_v0"
READ_MODEL_VERSION = "external_ai_context_packs_read_model_v0"
DEFAULT_EXPORT_ROOT = Path("generated/context_packs")
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_READ_MODEL_EXPORT_ROOT = Path("generated/read_models")
JSON_EXPORT_NAME = "external_ai_context_packs.json"
OPERATOR_EXPORT_NAME = "external_ai_context_packs_OPERATOR.md"
DEFAULT_PACK_ID = "mission_control_current"

SUPPORTED_PROFILES = {
    "chatgpt_project": {
        "target_file_count": 40,
        "upload_batch_size": 10,
        "avoid_giant_zip": True,
        "description": "Focused ChatGPT Project source bundle with START_HERE and small batches.",
    },
    "claude_project": {
        "target_file_count": 45,
        "upload_batch_size": 12,
        "avoid_giant_zip": True,
        "description": "Focused Claude Project source bundle with human summaries first.",
    },
    "codex_session": {
        "target_file_count": 55,
        "upload_batch_size": 15,
        "avoid_giant_zip": False,
        "description": "Source bundle for a bounded Codex session.",
    },
    "gemini_session": {
        "target_file_count": 45,
        "upload_batch_size": 12,
        "avoid_giant_zip": True,
        "description": "Focused Gemini session source bundle.",
    },
    "local_agent": {
        "target_file_count": 80,
        "upload_batch_size": 20,
        "avoid_giant_zip": False,
        "description": "Local agent source bundle; generated files remain local.",
    },
    "generic_zip": {
        "target_file_count": 100,
        "upload_batch_size": 25,
        "avoid_giant_zip": False,
        "description": "Generic local ZIP/export bundle.",
    },
}

MACHINE_JSON_BASENAMES = {
    "agent_lanes.json",
    "agent_runtime_readiness.json",
    "agent_work_packets.json",
    "context_selection.json",
    "dropped_intents.json",
    "intent_router.json",
    "markdown_evidence.json",
    "operator_actions.json",
    "project_capsules.json",
    "recent_file_context.json",
    "report_bridge.json",
}

EXCLUDED_READ_MODEL_BASENAMES = {
    "external_ai_context_packs.json",
    "external_ai_context_packs_OPERATOR.md",
}

NO_AUTHORITY_FLAGS = {
    "external_upload_allowed": False,
    "browser_automation_allowed": False,
    "network_authority": False,
    "raw_private_included": False,
    "no_go_included": False,
    "secrets_included": False,
    "agent_activation_allowed": False,
    "action_auto_execute_allowed": False,
}

SENSITIVE_PATH_HINTS = {
    ".chief.env",
    ".env",
    ".google-secrets",
    ".ssh",
    "auth",
    "client_raw",
    "credential",
    "credentials",
    "cpa",
    "finance",
    "legal",
    "no_go",
    "no-go",
    "private",
    "secret",
    "secrets",
    "tax",
    "token",
    "vault",
}


@dataclass(frozen=True)
class ContextPackBuildResult:
    pack_id: str
    run_id: str
    profile: str
    output_path: str
    zip_path: str | None
    file_count: int
    source_file_count: int
    total_byte_size: int
    safety_status: str
    warning_count: int


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _safe_id(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in value.strip().lower())
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    if not cleaned:
        raise ValueError("pack id/focus cannot be empty")
    return cleaned[:96]


def _display_path(path: str | Path, *, repo_root: str | Path = ROOT) -> str:
    path_obj = Path(path)
    try:
        return path_obj.resolve().relative_to(Path(repo_root).resolve()).as_posix()
    except (OSError, ValueError):
        return path_obj.as_posix()


def _resolve_repo_path(path: str | Path, *, repo_root: str | Path = ROOT) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return Path(repo_root) / candidate


def _path_has_sensitive_hint(relative_path: str) -> bool:
    lowered = relative_path.lower()
    parts = {part.lower() for part in Path(relative_path).parts}
    if parts & SENSITIVE_PATH_HINTS:
        return True
    return any(hint in lowered for hint in SENSITIVE_PATH_HINTS)


def _is_safe_source_record(record: dict[str, Any]) -> bool:
    relative_path = str(record["relative_path"])
    if "/" in relative_path:
        return False
    if relative_path in EXCLUDED_READ_MODEL_BASENAMES:
        return False
    if is_no_go_generated_read_model_relative_path(relative_path):
        return False
    if _path_has_sensitive_hint(relative_path):
        return False
    return True


def select_context_pack_read_model_records(
    *,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    repo_root: str | Path = ROOT,
) -> tuple[dict[str, Any], ...]:
    """Select safe read-model files for context packs.

    Human/operator Markdown and text summaries are selected dynamically. JSON is
    limited to a named machine-state set so packs do not become undifferentiated
    raw dumps every time the backend grows a new export.
    """

    records = [
        dict(record)
        for record in canonical_generated_read_model_records(
            source_root=read_model_root,
            repo_root=repo_root,
            include_hash=True,
        )
        if _is_safe_source_record(record)
    ]
    selected: list[dict[str, Any]] = []
    for record in records:
        name = str(record["relative_path"])
        suffix = Path(name).suffix.lower()
        if suffix in {".md", ".txt"}:
            selected.append({**record, "selection_reason": "human_operator_summary"})
            continue
        if name in MACHINE_JSON_BASENAMES:
            selected.append({**record, "selection_reason": "selected_machine_state_json"})

    priority = {
        "generated_current_state.md": 0,
        "generated_next_actions.md": 1,
        "agent_runtime_readiness_OPERATOR.md": 2,
        "agent_runtime_readiness.json": 3,
        "intent_router_OPERATOR.md": 4,
        "intent_router.json": 5,
        "agent_lanes_OPERATOR.md": 6,
        "agent_lanes.json": 7,
        "operator_actions_OPERATOR.md": 8,
        "operator_actions.json": 9,
    }
    return tuple(sorted(selected, key=lambda item: (priority.get(item["relative_path"], 100), item["relative_path"])))


def _sql_statements() -> tuple[str, ...]:
    return (
        """
CREATE TABLE IF NOT EXISTS context_pack_runs (
  run_id TEXT PRIMARY KEY,
  packager_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  pack_count INTEGER NOT NULL DEFAULT 0,
  raw_private_included INTEGER NOT NULL DEFAULT 0,
  no_go_included INTEGER NOT NULL DEFAULT 0,
  secrets_included INTEGER NOT NULL DEFAULT 0,
  external_upload_allowed INTEGER NOT NULL DEFAULT 0,
  browser_automation_allowed INTEGER NOT NULL DEFAULT 0,
  network_authority INTEGER NOT NULL DEFAULT 0,
  agent_activation_allowed INTEGER NOT NULL DEFAULT 0,
  action_auto_execute_allowed INTEGER NOT NULL DEFAULT 0,
  notes TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS context_packs (
  pack_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  profile TEXT NOT NULL,
  world TEXT NOT NULL,
  task_focus TEXT NOT NULL,
  output_path TEXT NOT NULL,
  zip_path TEXT,
  file_count INTEGER NOT NULL DEFAULT 0,
  source_file_count INTEGER NOT NULL DEFAULT 0,
  total_byte_size INTEGER NOT NULL DEFAULT 0,
  safety_status TEXT NOT NULL,
  warning_count INTEGER NOT NULL DEFAULT 0,
  raw_private_included INTEGER NOT NULL DEFAULT 0,
  no_go_included INTEGER NOT NULL DEFAULT 0,
  secrets_included INTEGER NOT NULL DEFAULT 0,
  external_upload_allowed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES context_pack_runs(run_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS context_pack_files (
  context_pack_file_id TEXT PRIMARY KEY,
  pack_id TEXT NOT NULL,
  run_id TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  role TEXT NOT NULL,
  size_bytes INTEGER NOT NULL,
  sha256 TEXT NOT NULL,
  source_path TEXT,
  source_role TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (pack_id) REFERENCES context_packs(pack_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS context_pack_sources (
  context_pack_source_id TEXT PRIMARY KEY,
  pack_id TEXT NOT NULL,
  run_id TEXT NOT NULL,
  source_ref TEXT NOT NULL,
  source_kind TEXT NOT NULL,
  included INTEGER NOT NULL DEFAULT 0,
  exclusion_reason TEXT,
  selection_reason TEXT,
  raw_private_included INTEGER NOT NULL DEFAULT 0,
  no_go_included INTEGER NOT NULL DEFAULT 0,
  secrets_included INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY (pack_id) REFERENCES context_packs(pack_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS context_pack_profiles (
  profile TEXT PRIMARY KEY,
  target_file_count INTEGER NOT NULL,
  upload_batch_size INTEGER NOT NULL,
  avoid_giant_zip INTEGER NOT NULL DEFAULT 1,
  description TEXT NOT NULL,
  created_at TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS context_pack_safety_checks (
  context_pack_safety_check_id TEXT PRIMARY KEY,
  pack_id TEXT NOT NULL,
  run_id TEXT NOT NULL,
  check_name TEXT NOT NULL,
  status TEXT NOT NULL,
  summary TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (pack_id) REFERENCES context_packs(pack_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS context_pack_receipts (
  context_pack_receipt_id TEXT PRIMARY KEY,
  pack_id TEXT NOT NULL,
  run_id TEXT NOT NULL,
  receipt_kind TEXT NOT NULL,
  summary TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (pack_id) REFERENCES context_packs(pack_id) ON DELETE CASCADE
)
""".strip(),
        "CREATE INDEX IF NOT EXISTS idx_context_packs_profile ON context_packs(profile)",
        "CREATE INDEX IF NOT EXISTS idx_context_pack_files_pack ON context_pack_files(pack_id)",
    )


def init_external_ai_context_pack_schema(db_path: str | Path | None = None) -> str:
    path = str(db_path or DEFAULT_DB_PATH)
    parent = Path(path).parent
    if parent and not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)
    init_business_ops_ledger(path)
    conn = sqlite3.connect(path)
    try:
        for statement in _sql_statements():
            conn.execute(statement)
        conn.commit()
    finally:
        conn.close()
    return path


def context_pack_table_names(db_path: str | Path | None = None) -> tuple[str, ...]:
    path = init_external_ai_context_pack_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            """
SELECT name
FROM sqlite_master
WHERE type = 'table' AND name LIKE 'context_pack%'
ORDER BY name
""".strip()
        ).fetchall()
        return tuple(row[0] for row in rows)
    finally:
        conn.close()


def _seed_profiles(conn: sqlite3.Connection, now: str) -> None:
    for profile, policy in SUPPORTED_PROFILES.items():
        conn.execute(
            """
INSERT INTO context_pack_profiles (
  profile, target_file_count, upload_batch_size, avoid_giant_zip,
  description, created_at
) VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT(profile) DO UPDATE SET
  target_file_count = excluded.target_file_count,
  upload_batch_size = excluded.upload_batch_size,
  avoid_giant_zip = excluded.avoid_giant_zip,
  description = excluded.description
""".strip(),
            (
                profile,
                int(policy["target_file_count"]),
                int(policy["upload_batch_size"]),
                1 if policy["avoid_giant_zip"] else 0,
                str(policy["description"]),
                now,
            ),
        )


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_text_excerpt(path: Path, *, max_chars: int = 3600) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return "Unavailable."
    if len(text) <= max_chars:
        return text.rstrip()
    return text[: max_chars - 3].rstrip() + "..."


def _read_model_path(
    name: str,
    *,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    repo_root: str | Path = ROOT,
) -> Path:
    return _resolve_repo_path(read_model_root, repo_root=repo_root) / name


def _json_summary_line(name: str, payload: dict[str, Any]) -> str:
    if not payload:
        return f"- `{name}`: present; JSON summary unavailable."
    if name == "agent_runtime_readiness.json":
        smoke = payload.get("smoke_test_results") or {}
        return (
            f"- Agent runtime readiness: agents={payload.get('agent_count', 0)}, "
            f"ready={payload.get('ready_for_dry_run_count', 0)}, "
            f"status={payload.get('latest_start_sequence_status', 'unknown')}, "
            f"smoke_passed={smoke.get('passed', 0)}, smoke_failed={smoke.get('failed', 0)}."
        )
    if name == "intent_router.json":
        return (
            f"- Intent Router: intents={payload.get('total_intents', payload.get('intent_count', 0))}, "
            f"needs_review={payload.get('needs_review_count', 0)}."
        )
    if name == "agent_lanes.json":
        return f"- Agent Lanes: agents={payload.get('agent_count', 0)}, lanes={payload.get('lane_count', 0)}."
    if name == "operator_actions.json":
        return (
            f"- Operator Actions: requests={payload.get('request_count', 0)}, "
            f"pending={payload.get('pending_approval_count', 0)}, completed={payload.get('completed_count', 0)}."
        )
    if name == "recent_file_context.json":
        return (
            f"- Recent File Context: candidates={payload.get('candidate_count', 0)}, "
            f"latest_resolution={payload.get('latest_resolution', {}) or 'none'}."
        )
    if name == "markdown_evidence.json":
        return (
            f"- Markdown Evidence: sources={payload.get('source_count', 0)}, "
            f"items={payload.get('item_count', 0)}, truth_promotion=false."
        )
    if name == "dropped_intents.json":
        return (
            f"- Dropped Intents: total={payload.get('total_count', 0)}, "
            f"unresolved={payload.get('unresolved_count', 0)}, deferred={payload.get('deferred_count', 0)}."
        )
    if name == "agent_work_packets.json":
        return f"- Agent Work Packets: packets={payload.get('packet_count', 0)}, execution_allowed=false."
    if name == "project_capsules.json":
        return f"- Project Capsules: capsules={payload.get('capsule_count', 0)}, client_data_access=false."
    if name == "report_bridge.json":
        return (
            f"- Report Bridge: packages={payload.get('package_count', 0)}, "
            f"rejected={payload.get('rejected_package_count', payload.get('rejected_count', 0))}."
        )
    return f"- `{name}`: schema={payload.get('schema_version', payload.get('read_model_version', 'unknown'))}."


def _current_state_markdown(
    *,
    read_model_root: str | Path,
    repo_root: str | Path,
    selected_records: tuple[dict[str, Any], ...],
) -> str:
    lines = [
        "# Current State",
        "",
        "This file summarizes selected generated read-models for an external AI/context consumer.",
        "It is a source bundle summary, not truth promotion.",
        "",
        "Selected posture:",
    ]
    for record in selected_records:
        name = record["relative_path"]
        if Path(name).suffix.lower() != ".json":
            continue
        payload = _load_json(_read_model_path(name, read_model_root=read_model_root, repo_root=repo_root))
        lines.append(_json_summary_line(name, payload))
    state_path = _read_model_path("generated_current_state.md", read_model_root=read_model_root, repo_root=repo_root)
    if state_path.exists():
        lines.extend(["", "Generated Current State excerpt:", "", _read_text_excerpt(state_path, max_chars=2400)])
    return "\n".join(lines).rstrip() + "\n"


def _next_actions_markdown(*, read_model_root: str | Path, repo_root: str | Path) -> str:
    next_path = _read_model_path("generated_next_actions.md", read_model_root=read_model_root, repo_root=repo_root)
    lines = [
        "# Next Actions",
        "",
        "Use this as orientation only. Any execution or approval must happen through OpenClaw gates.",
        "",
    ]
    if next_path.exists():
        lines.append(_read_text_excerpt(next_path, max_chars=3200))
    else:
        lines.append("- No generated next-actions read-model was available.")
    return "\n".join(lines).rstrip() + "\n"


def _safety_boundaries_markdown() -> str:
    lines = [
        "# Safety Boundaries",
        "",
        "This pack is an offline source bundle. It does not grant authority.",
        "",
        "No-authority flags:",
    ]
    for key, value in NO_AUTHORITY_FLAGS.items():
        lines.append(f"- `{key}`: `{str(value).lower()}`")
    lines.extend(
        [
            "",
            "Blocked in this lane:",
            "- No automatic upload to ChatGPT, Claude, Gemini, Codex, or any external service.",
            "- No browser/UI automation.",
            "- No network API calls.",
            "- No private/no-go raw content.",
            "- No file moves, deletes, renames, deployment, runtime activation, or agent activation.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _upload_instructions_markdown(profile: str, file_count: int, warnings: list[str]) -> str:
    policy = SUPPORTED_PROFILES[profile]
    lines = [
        "# Upload Instructions",
        "",
        f"Target profile: `{profile}`.",
        "",
        "This pack is ready for manual upload or local attachment. OpenClaw did not upload anything.",
        "",
        "Recommended order:",
        "1. Upload `00_START_HERE.md`, `MANIFEST.json`, `CURRENT_STATE.md`, and `SAFETY_BOUNDARIES.md` first.",
        "2. Upload the files in `selected_read_models/` in small batches.",
        "3. Keep `UPLOAD_INSTRUCTIONS.md` available as the operator checklist.",
        "",
        f"Suggested batch size: around {policy['upload_batch_size']} files.",
        f"Target source count for this profile: around {policy['target_file_count']} files.",
    ]
    if policy["avoid_giant_zip"]:
        lines.append("- Prefer individual focused files over one giant ZIP for project knowledge uploads.")
    else:
        lines.append("- ZIP is available for local transport, but individual files remain easier to inspect.")
    lines.extend(["", f"Current source file count: {file_count}."])
    if warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.extend(["", "Warnings:", "- none"])
    return "\n".join(lines).rstrip() + "\n"


def _start_here_markdown(
    *,
    pack_id: str,
    profile: str,
    world: str,
    task_focus: str,
    selected_count: int,
) -> str:
    return "\n".join(
        [
            "# OpenClaw External AI Context Pack",
            "",
            f"Pack: `{pack_id}`",
            f"Profile: `{profile}`",
            f"World/domain: `{world}`",
            f"Task focus: `{task_focus}`",
            "",
            "Purpose:",
            "- Provide a focused current OpenClaw source bundle for an external AI project/session or local agent.",
            "- Preserve safety boundaries while reducing manual file gathering.",
            "",
            "Start with:",
            "- `CURRENT_STATE.md` for current posture.",
            "- `READ_MODEL_INDEX.md` for exact selected generated surfaces.",
            "- `SAFETY_BOUNDARIES.md` before proposing action.",
            "- `UPLOAD_INSTRUCTIONS.md` for manual upload batching.",
            "",
            f"Selected read-model files: {selected_count}.",
            "",
            "Boundary:",
            "- This pack is evidence/context, not authority or truth promotion.",
            "- No upload, browser automation, network call, runtime activation, or execution occurred.",
        ]
    ) + "\n"


def _read_model_index_markdown(
    *,
    selected_records: tuple[dict[str, Any], ...],
    all_safe_records: tuple[dict[str, Any], ...],
) -> str:
    selected_names = {record["relative_path"] for record in selected_records}
    lines = [
        "# Read-Model Index",
        "",
        "Selected read-model files copied into `selected_read_models/`:",
    ]
    for record in selected_records:
        lines.append(
            f"- `{record['relative_path']}` ({record['size_bytes']} bytes, {record['selection_reason']})"
        )
    excluded = [record for record in all_safe_records if record["relative_path"] not in selected_names]
    lines.extend(["", "Available safe generated read-model files not copied into this focused pack:"])
    if excluded:
        for record in excluded:
            lines.append(f"- `{record['relative_path']}`")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "Selection policy:",
            "- Human/operator Markdown and text companions are included dynamically.",
            "- JSON inclusion is limited to selected machine-state surfaces.",
            "- Manifests, SQLite files, temp files, hidden files, and no-go/private path hints are excluded.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _evidence_index_markdown(selected_records: tuple[dict[str, Any], ...]) -> str:
    lines = [
        "# Evidence Index",
        "",
        "Included evidence/context surfaces:",
    ]
    for record in selected_records:
        lines.append(
            f"- `selected_read_models/{record['relative_path']}` "
            f"role=generated_read_model selection={record['selection_reason']} hash={record['sha256']}"
        )
    lines.extend(
        [
            "",
            "Evidence posture:",
            "- Generated read-models and summaries are evidence/context surfaces.",
            "- They are not truth by default and do not authorize execution.",
            "- Private/no-go raw content and secrets are not included.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _file_record(pack_dir: Path, path: Path, *, role: str, source_path: str | None = None, source_role: str | None = None) -> dict[str, Any]:
    stat_result = path.stat()
    return {
        "relative_path": path.relative_to(pack_dir).as_posix(),
        "role": role,
        "size_bytes": stat_result.st_size,
        "sha256": sha256_file(path),
        "source_path": source_path,
        "source_role": source_role,
    }


def _write_pack_file(pack_dir: Path, relative_path: str, text: str, role: str) -> dict[str, Any]:
    path = pack_dir / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return _file_record(pack_dir, path, role=role)


def _copy_source_file(pack_dir: Path, source_path: Path, relative_path: str, source_role: str) -> dict[str, Any]:
    target = pack_dir / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target)
    return _file_record(pack_dir, target, role="selected_read_model", source_path=source_path.as_posix(), source_role=source_role)


def _zip_pack(pack_dir: Path, zip_path: Path) -> dict[str, Any]:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(pack_dir.rglob("*")):
            if not path.is_file() or path == zip_path:
                continue
            archive.write(path, path.relative_to(pack_dir).as_posix())
    return _file_record(pack_dir, zip_path, role="local_archive_zip")


def _warnings_for_profile(profile: str, source_file_count: int) -> list[str]:
    policy = SUPPORTED_PROFILES[profile]
    warnings: list[str] = []
    target = int(policy["target_file_count"])
    if source_file_count > target:
        warnings.append(
            f"Source file count {source_file_count} exceeds the {profile} target of about {target}; split or trim before upload."
        )
    if policy["avoid_giant_zip"]:
        warnings.append("ZIP is generated for local convenience, but project uploads should prefer focused individual files.")
    return warnings


def build_external_ai_context_pack(
    *,
    db_path: str | Path | None = None,
    profile: str = "chatgpt_project",
    world: str = "build",
    focus: str = DEFAULT_PACK_ID,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    repo_root: str | Path = ROOT,
    create_zip: bool = True,
    run_id: str | None = None,
) -> ContextPackBuildResult:
    if profile not in SUPPORTED_PROFILES:
        raise ValueError(f"unsupported context pack profile: {profile}")
    path = init_external_ai_context_pack_schema(db_path)
    now = utc_now()
    pack_id = _safe_id(focus)
    resolved_run_id = run_id or _row_id("ctxpackrun", pack_id, profile, world, now)
    output_root = _resolve_repo_path(export_root, repo_root=repo_root)
    pack_dir = output_root / pack_id
    pack_dir.mkdir(parents=True, exist_ok=True)

    all_safe_records = tuple(
        dict(record)
        for record in canonical_generated_read_model_records(
            source_root=read_model_root,
            repo_root=repo_root,
            include_hash=True,
        )
        if _is_safe_source_record(record)
    )
    selected_records = select_context_pack_read_model_records(
        read_model_root=read_model_root,
        repo_root=repo_root,
    )
    warnings = _warnings_for_profile(profile, 7 + len(selected_records))
    files: list[dict[str, Any]] = []
    files.append(
        _write_pack_file(
            pack_dir,
            "00_START_HERE.md",
            _start_here_markdown(
                pack_id=pack_id,
                profile=profile,
                world=world,
                task_focus=focus,
                selected_count=len(selected_records),
            ),
            "start_here",
        )
    )
    files.append(
        _write_pack_file(
            pack_dir,
            "CURRENT_STATE.md",
            _current_state_markdown(
                read_model_root=read_model_root,
                repo_root=repo_root,
                selected_records=selected_records,
            ),
            "current_state_summary",
        )
    )
    files.append(_write_pack_file(pack_dir, "NEXT_ACTIONS.md", _next_actions_markdown(read_model_root=read_model_root, repo_root=repo_root), "next_actions_summary"))
    files.append(_write_pack_file(pack_dir, "EVIDENCE_INDEX.md", _evidence_index_markdown(selected_records), "evidence_index"))
    files.append(_write_pack_file(pack_dir, "READ_MODEL_INDEX.md", _read_model_index_markdown(selected_records=selected_records, all_safe_records=all_safe_records), "read_model_index"))
    files.append(_write_pack_file(pack_dir, "SAFETY_BOUNDARIES.md", _safety_boundaries_markdown(), "safety_boundaries"))
    files.append(_write_pack_file(pack_dir, "UPLOAD_INSTRUCTIONS.md", _upload_instructions_markdown(profile, 7 + len(selected_records), warnings), "upload_instructions"))

    read_model_source_root = _resolve_repo_path(read_model_root, repo_root=repo_root)
    for record in selected_records:
        source_path = read_model_source_root / record["relative_path"]
        files.append(
            _copy_source_file(
                pack_dir,
                source_path,
                f"selected_read_models/{record['relative_path']}",
                record["selection_reason"],
            )
        )

    manifest_payload = {
        "schema_version": CONTEXT_PACK_VERSION,
        "pack_id": pack_id,
        "profile": profile,
        "world": world,
        "task_focus": focus,
        "generated_at": now,
        "source_basis": "generated/read_models selected by safe generated read-model helper",
        "output_path": _display_path(pack_dir, repo_root=repo_root),
        "target_profile_policy": SUPPORTED_PROFILES[profile],
        "files": files,
        "selected_source_count": len(selected_records),
        "available_safe_read_model_count": len(all_safe_records),
        "excluded_policy": [
            "manifests",
            "SQLite databases",
            "temp files",
            "hidden files",
            "no-go/private/sensitive path hints",
            "non-selected raw JSON read-models",
        ],
        "warnings": warnings,
        "safety_status": "safe_for_manual_upload_review",
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }
    manifest_path = pack_dir / "MANIFEST.json"
    manifest_path.write_text(stable_json(manifest_payload), encoding="utf-8")
    files.insert(1, _file_record(pack_dir, manifest_path, role="manifest"))

    zip_path: Path | None = None
    if create_zip:
        zip_path = pack_dir / f"OpenClaw_ContextPack_{pack_id}.zip"
        files.append(_zip_pack(pack_dir, zip_path))

    total_byte_size = sum(int(record["size_bytes"]) for record in files)
    source_file_count = len([record for record in files if record["role"] != "local_archive_zip"])
    safety_status = "safe_for_manual_upload_review"

    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        _seed_profiles(conn, now)
        for table in (
            "context_pack_receipts",
            "context_pack_safety_checks",
            "context_pack_sources",
            "context_pack_files",
            "context_packs",
        ):
            conn.execute(f"DELETE FROM {table} WHERE pack_id = ?", (pack_id,))
        conn.execute(
            """
INSERT INTO context_pack_runs (
  run_id, packager_version, created_at, completed_at, pack_count,
  raw_private_included, no_go_included, secrets_included, external_upload_allowed,
  browser_automation_allowed, network_authority, agent_activation_allowed,
  action_auto_execute_allowed, notes
) VALUES (?, ?, ?, ?, 1, 0, 0, 0, 0, 0, 0, 0, 0, ?)
ON CONFLICT(run_id) DO UPDATE SET
  completed_at = excluded.completed_at,
  pack_count = 1,
  raw_private_included = 0,
  no_go_included = 0,
  secrets_included = 0,
  external_upload_allowed = 0,
  browser_automation_allowed = 0,
  network_authority = 0,
  agent_activation_allowed = 0,
  action_auto_execute_allowed = 0,
  notes = excluded.notes
""".strip(),
            (
                resolved_run_id,
                CONTEXT_PACK_VERSION,
                now,
                now,
                "Built focused context pack; no upload, no browser automation, no network.",
            ),
        )
        conn.execute(
            """
INSERT INTO context_packs (
  pack_id, run_id, profile, world, task_focus, output_path, zip_path,
  file_count, source_file_count, total_byte_size, safety_status,
  warning_count, raw_private_included, no_go_included, secrets_included,
  external_upload_allowed, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, ?)
""".strip(),
            (
                pack_id,
                resolved_run_id,
                profile,
                world,
                focus,
                _display_path(pack_dir, repo_root=repo_root),
                _display_path(zip_path, repo_root=repo_root) if zip_path else None,
                len(files),
                source_file_count,
                total_byte_size,
                safety_status,
                len(warnings),
                now,
            ),
        )
        for file_record in files:
            conn.execute(
                """
INSERT INTO context_pack_files (
  context_pack_file_id, pack_id, run_id, relative_path, role,
  size_bytes, sha256, source_path, source_role, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""".strip(),
                (
                    _row_id("ctxpackfile", pack_id, file_record["relative_path"]),
                    pack_id,
                    resolved_run_id,
                    file_record["relative_path"],
                    file_record["role"],
                    file_record["size_bytes"],
                    file_record["sha256"],
                    file_record.get("source_path"),
                    file_record.get("source_role"),
                    now,
                ),
            )
        selected_names = {record["relative_path"] for record in selected_records}
        for record in all_safe_records:
            included = record["relative_path"] in selected_names
            conn.execute(
                """
INSERT INTO context_pack_sources (
  context_pack_source_id, pack_id, run_id, source_ref, source_kind,
  included, exclusion_reason, selection_reason, raw_private_included,
  no_go_included, secrets_included, created_at
) VALUES (?, ?, ?, ?, 'generated_read_model', ?, ?, ?, 0, 0, 0, ?)
""".strip(),
                (
                    _row_id("ctxpacksource", pack_id, record["relative_path"]),
                    pack_id,
                    resolved_run_id,
                    record["relative_path"],
                    1 if included else 0,
                    None if included else "not_selected_for_focused_pack",
                    next(
                        (item["selection_reason"] for item in selected_records if item["relative_path"] == record["relative_path"]),
                        None,
                    ),
                    now,
                ),
            )
        safety_checks = (
            ("no_go_paths", "pass", "No selected context-pack source path contains no-go/private path hints."),
            ("secrets_paths", "pass", "No selected source path contains credential/secret path hints."),
            ("upload_authority", "pass", "Packager does not upload files or automate browsers."),
            ("network_authority", "pass", "Packager does not call network APIs."),
        )
        for check_name, status, summary in safety_checks:
            conn.execute(
                """
INSERT INTO context_pack_safety_checks (
  context_pack_safety_check_id, pack_id, run_id, check_name,
  status, summary, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?)
""".strip(),
                (_row_id("ctxpacksafe", pack_id, check_name), pack_id, resolved_run_id, check_name, status, summary, now),
            )
        receipt_payload = {
            "pack_id": pack_id,
            "profile": profile,
            "output_path": _display_path(pack_dir, repo_root=repo_root),
            "zip_path": _display_path(zip_path, repo_root=repo_root) if zip_path else None,
            "file_count": len(files),
            "source_file_count": source_file_count,
            "total_byte_size": total_byte_size,
            "warnings": warnings,
            **NO_AUTHORITY_FLAGS,
        }
        conn.execute(
            """
INSERT INTO context_pack_receipts (
  context_pack_receipt_id, pack_id, run_id, receipt_kind,
  summary, payload_json, created_at
) VALUES (?, ?, ?, 'context_pack_build_receipt', ?, ?, ?)
""".strip(),
            (
                _row_id("ctxpackreceipt", pack_id, resolved_run_id),
                pack_id,
                resolved_run_id,
                f"Built context pack {pack_id} for {profile}; no external upload occurred.",
                stable_json(receipt_payload),
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return ContextPackBuildResult(
        pack_id=pack_id,
        run_id=resolved_run_id,
        profile=profile,
        output_path=_display_path(pack_dir, repo_root=repo_root),
        zip_path=_display_path(zip_path, repo_root=repo_root) if zip_path else None,
        file_count=len(files),
        source_file_count=source_file_count,
        total_byte_size=total_byte_size,
        safety_status=safety_status,
        warning_count=len(warnings),
    )


REPORT_SECTIONS = {"summary", "packs", "latest"}


def _pack_summary(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "pack_id": row["pack_id"],
        "run_id": row["run_id"],
        "profile": row["profile"],
        "world": row["world"],
        "task_focus": row["task_focus"],
        "output_path": row["output_path"],
        "zip_path": row["zip_path"],
        "file_count": row["file_count"],
        "source_file_count": row["source_file_count"],
        "total_byte_size": row["total_byte_size"],
        "safety_status": row["safety_status"],
        "warning_count": row["warning_count"],
        "raw_private_included": bool(row["raw_private_included"]),
        "no_go_included": bool(row["no_go_included"]),
        "secrets_included": bool(row["secrets_included"]),
        "external_upload_allowed": bool(row["external_upload_allowed"]),
        "created_at": row["created_at"],
    }


def build_external_ai_context_pack_report(
    *,
    db_path: str | Path | None = None,
    report: str = "summary",
    pack_id: str | None = None,
) -> dict[str, Any]:
    if report not in REPORT_SECTIONS:
        raise ValueError(f"unknown context pack report: {report}")
    path = init_external_ai_context_pack_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        params: tuple[Any, ...] = ()
        where = ""
        if pack_id:
            where = "WHERE pack_id = ?"
            params = (pack_id,)
        rows = conn.execute(
            f"""
SELECT *
FROM context_packs
{where}
ORDER BY created_at DESC, pack_id
""".strip(),
            params,
        ).fetchall()
        items = rows[:1] if report == "latest" else rows[:20]
        profile_counts = Counter(row["profile"] for row in rows)
        safety_counts = Counter(row["safety_status"] for row in rows)
        file_rows: list[dict[str, Any]] = []
        if pack_id:
            file_rows = [
                dict(row)
                for row in conn.execute(
                    """
SELECT relative_path, role, size_bytes, sha256, source_path, source_role
FROM context_pack_files
WHERE pack_id = ?
ORDER BY relative_path
""".strip(),
                    (pack_id,),
                ).fetchall()
            ]
        return {
            "status": "ok",
            "report": report,
            "db_path": str(path),
            "pack_count": len(rows),
            "counts": {
                "by_profile": dict(sorted(profile_counts.items())),
                "by_safety_status": dict(sorted(safety_counts.items())),
                "raw_private_included": sum(1 for row in rows if row["raw_private_included"]),
                "no_go_included": sum(1 for row in rows if row["no_go_included"]),
                "secrets_included": sum(1 for row in rows if row["secrets_included"]),
                "external_upload_allowed": sum(1 for row in rows if row["external_upload_allowed"]),
            },
            "latest_pack": _pack_summary(rows[0]) if rows else None,
            "items": [_pack_summary(row) for row in items],
            "files": file_rows,
            "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        }
    finally:
        conn.close()


def _counts_line(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def format_external_ai_context_pack_report(payload: dict[str, Any]) -> str:
    lines = [
        f"External AI Context Packager v0 - {payload['report']}",
        "",
        f"Packs: {payload['pack_count']}",
        f"By profile: {_counts_line(payload['counts']['by_profile'])}",
        f"By safety status: {_counts_line(payload['counts']['by_safety_status'])}",
        f"Raw private included rows: {payload['counts']['raw_private_included']}",
        f"No-go included rows: {payload['counts']['no_go_included']}",
        f"Secrets included rows: {payload['counts']['secrets_included']}",
        "",
        "Items:",
    ]
    for item in payload.get("items") or []:
        lines.append(
            f"- `{item['pack_id']}` profile={item['profile']} files={item['file_count']} "
            f"output=`{item['output_path']}` safety={item['safety_status']}"
        )
    if not payload.get("items"):
        lines.append("- none")
    if payload.get("files"):
        lines.extend(["", "Pack files:"])
        for file_record in payload["files"]:
            lines.append(
                f"- `{file_record['relative_path']}` role={file_record['role']} bytes={file_record['size_bytes']}"
            )
    lines.extend(
        [
            "",
            "Boundary:",
            "- Packaging/export only; no upload, browser automation, network call, runtime activation, or execution.",
        ]
    )
    return "\n".join(lines)


def build_external_ai_context_packs_read_model(
    *,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    report = build_external_ai_context_pack_report(db_path=db_path, report="summary")
    latest = report["latest_pack"]
    return {
        "schema_version": READ_MODEL_VERSION,
        "read_model_version": READ_MODEL_VERSION,
        "mode": "external_ai_context_packaging_posture_only",
        "generated_at": utc_now(),
        "source_ledger_path": _display_path(report["db_path"]),
        "source_ledger_namespace": "context_pack_*",
        "pack_count": report["pack_count"],
        "latest_pack": latest,
        "profile": latest["profile"] if latest else None,
        "output_path": latest["output_path"] if latest else None,
        "file_count": latest["file_count"] if latest else 0,
        "zip_path": latest["zip_path"] if latest else None,
        "safety_status": latest["safety_status"] if latest else "no_packs",
        "upload_instructions_summary": (
            "Manual upload only. Start with 00_START_HERE.md, MANIFEST.json, CURRENT_STATE.md, "
            "and SAFETY_BOUNDARIES.md; upload selected_read_models in small batches."
            if latest
            else "No pack has been built yet."
        ),
        "counts": report["counts"],
        "packs": report["items"],
        "supported_profiles": sorted(SUPPORTED_PROFILES),
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }


def format_external_ai_context_packs_read_model(read_model: dict[str, Any]) -> str:
    latest = read_model.get("latest_pack")
    lines = [
        "# External AI Context Packs Read-Model v0",
        "",
        "What this is:",
        "- A generated read-model over safe context-pack exports for external AI projects/sessions and local agents.",
        "",
        "What this is not:",
        "- It is not upload automation, browser automation, network access, agent activation, or execution.",
        "",
        "Summary:",
        f"- Packs: {read_model['pack_count']}.",
        f"- Latest safety status: `{read_model['safety_status']}`.",
        f"- Supported profiles: {', '.join(read_model['supported_profiles'])}.",
        "",
        "Latest pack:",
    ]
    if latest:
        lines.extend(
            [
                f"- Pack: `{latest['pack_id']}`.",
                f"- Profile: `{latest['profile']}`.",
                f"- Output: `{latest['output_path']}`.",
                f"- Files: {latest['file_count']} source_files={latest['source_file_count']}.",
                f"- ZIP: `{latest['zip_path'] or 'none'}`.",
                f"- Raw private included: `{str(latest['raw_private_included']).lower()}`.",
                f"- No-go included: `{str(latest['no_go_included']).lower()}`.",
                f"- Secrets included: `{str(latest['secrets_included']).lower()}`.",
            ]
        )
    else:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "Upload posture:",
            f"- {read_model['upload_instructions_summary']}",
            "",
            "Authority boundary:",
        ]
    )
    for key, value in NO_AUTHORITY_FLAGS.items():
        lines.append(f"- `{key}`: `{str(value).lower()}`.")
    return "\n".join(lines) + "\n"


def export_external_ai_context_pack_read_model(
    *,
    db_path: str | Path | None = None,
    export_root: str | Path = DEFAULT_READ_MODEL_EXPORT_ROOT,
) -> dict[str, Any]:
    root = _resolve_repo_path(export_root)
    root.mkdir(parents=True, exist_ok=True)
    read_model = build_external_ai_context_packs_read_model(db_path=db_path)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(read_model), encoding="utf-8")
    operator_path.write_text(format_external_ai_context_packs_read_model(read_model), encoding="utf-8")
    return {
        "export_version": READ_MODEL_VERSION,
        "json_path": _display_path(json_path),
        "operator_path": _display_path(operator_path),
        "pack_count": read_model["pack_count"],
        "latest_pack_id": read_model["latest_pack"]["pack_id"] if read_model.get("latest_pack") else None,
        **NO_AUTHORITY_FLAGS,
    }


def format_build_result(result: ContextPackBuildResult) -> str:
    return "\n".join(
        [
            "External AI Context Packager v0",
            "",
            f"Pack: `{result.pack_id}`",
            f"Run: `{result.run_id}`",
            f"Profile: `{result.profile}`",
            f"Output: `{result.output_path}`",
            f"ZIP: `{result.zip_path or 'none'}`",
            f"Files: {result.file_count}",
            f"Source files: {result.source_file_count}",
            f"Total bytes: {result.total_byte_size}",
            f"Safety status: `{result.safety_status}`",
            f"Warnings: {result.warning_count}",
            "",
            "Boundary:",
            "- Generated a local context pack only; no upload, browser automation, network call, or execution occurred.",
        ]
    )


__all__ = [
    "CONTEXT_PACK_VERSION",
    "DEFAULT_PACK_ID",
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "READ_MODEL_VERSION",
    "REPORT_SECTIONS",
    "SUPPORTED_PROFILES",
    "ContextPackBuildResult",
    "build_external_ai_context_pack",
    "build_external_ai_context_pack_report",
    "build_external_ai_context_packs_read_model",
    "context_pack_table_names",
    "export_external_ai_context_pack_read_model",
    "format_build_result",
    "format_external_ai_context_pack_report",
    "format_external_ai_context_packs_read_model",
    "init_external_ai_context_pack_schema",
    "select_context_pack_read_model_records",
    "stable_json",
]
