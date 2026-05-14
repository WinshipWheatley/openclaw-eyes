"""Project Capsule v0 for bounded synthetic client/project planning.

This module records non-authorizing project capsule metadata in the existing
Business Ops ledger under a separate ``project_capsule_*`` namespace. It is a
planning and inspection layer only: no runtime, deployment, client-data,
network, tool, or agent authority is granted.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from business_ops_ledger import DEFAULT_DB_PATH, init_business_ops_ledger


PROJECT_CAPSULE_VERSION = "project_capsule_v0"
DEMO_PROJECT_ID = "demo_project_capsule_v0"
DEMO_CLIENT_ID = "demo_client"

WORLD_IDS = {
    "music_art",
    "finance",
    "operations",
    "security",
    "build",
    "research",
    "communications",
    "business_development",
    "cross_world",
    "no_world",
    "unknown",
}

NO_AUTHORITY_FLAGS = {
    "runtime_authority": False,
    "deployment_authority": False,
    "client_data_access": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "network_authority": False,
}

DEMO_WORLDS = (
    ("operations", "demo_project_scope"),
    ("build", "demo_project_scope"),
    ("communications", "demo_project_scope"),
)

DEMO_TOOLS = (
    ("copier", "template_candidate", "candidate"),
    ("pocketbase", "future_client_app_backend_candidate", "candidate"),
    ("datasette", "future_sqlite_inspection_candidate", "candidate"),
    ("sqlite_utils", "future_sqlite_metadata_candidate", "candidate"),
)

DEMO_BOUNDARIES = (
    (
        "synthetic_demo_metadata",
        "allowed",
        "metadata_only",
        "Synthetic project planning data is allowed inside this demo capsule.",
    ),
    (
        "public_project_metadata",
        "allowed",
        "metadata_only",
        "Public/internal project metadata may be referenced for planning.",
    ),
    (
        "generated_read_model_metadata",
        "allowed",
        "metadata_only",
        "Generated read-model metadata may be referenced without treating it as truth.",
    ),
    (
        "real_client_data",
        "forbidden",
        "blocked",
        "No real client data is allowed in Project Capsule v0.",
    ),
    (
        "credentials_secrets_tokens",
        "forbidden",
        "blocked",
        "Credentials, secrets, tokens, and auth material remain no-go.",
    ),
    (
        "private_legal_tax_finance",
        "forbidden",
        "blocked",
        "Private, legal, tax, CPA, and finance material is not in scope.",
    ),
    (
        "runtime_logs_production_data",
        "forbidden",
        "blocked",
        "Runtime logs and production customer data are not in scope.",
    ),
)

DEMO_RECEIPT_REQUIREMENTS = (
    ("capsule_creation_receipt", "Record capsule creation and authority posture."),
    ("boundary_review_receipt", "Record any future operator boundary review."),
    ("approval_gate_receipt", "Required before any future deployment or client-data lane."),
)

DEMO_READ_MODEL_REQUIREMENTS = (
    ("project_capsules.json", "Expose capsule posture as a generated read-model."),
    ("context_selection.json", "Use context packet posture as bounded evidence context."),
    ("tool_intake.json", "Use tool candidate policy without approving tools."),
    ("tool_inventory.json", "Inspect installed-tool posture without executing tools."),
)

DEMO_NEXT_MOVES = (
    (
        1,
        "review_demo_capsule_boundaries",
        "Review synthetic capsule boundaries before using it as a prompt substrate.",
    ),
    (
        2,
        "export_project_capsule_read_model",
        "Generate standalone project capsule read-model files.",
    ),
    (
        3,
        "export_synthetic_template",
        "Create a synthetic demo starter folder without deployment authority.",
    ),
)

DEFAULT_SELECTED_MODULES = (
    "project_capsule",
    "corpus_atlas",
    "evidence_kettle",
    "context_selection",
    "tool_inventory",
    "tool_intake",
    "read_model_shuttle",
)


@dataclass(frozen=True)
class ProjectCapsuleResult:
    run_id: str
    db_path: str
    project_id: str
    capsule_count: int
    world_count: int
    tool_count: int
    boundary_count: int
    next_move_count: int


@dataclass(frozen=True)
class ModuleSelectionResult:
    project_id: str
    selected_module_count: int
    runtime_authority: bool
    activation_count: int


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256(
        "\0".join(str(part) for part in parts).encode("utf-8")
    ).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _sql_statements() -> tuple[str, ...]:
    return (
        """
CREATE TABLE IF NOT EXISTS project_capsule_runs (
  run_id TEXT PRIMARY KEY,
  capsule_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  demo_mode INTEGER NOT NULL DEFAULT 1,
  capsule_count INTEGER NOT NULL DEFAULT 0,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  deployment_authority INTEGER NOT NULL DEFAULT 0,
  client_data_access INTEGER NOT NULL DEFAULT 0,
  agent_activation_allowed INTEGER NOT NULL DEFAULT 0,
  tool_execution_allowed INTEGER NOT NULL DEFAULT 0,
  network_authority INTEGER NOT NULL DEFAULT 0,
  source_basis_json TEXT NOT NULL,
  notes TEXT
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS project_capsules (
  capsule_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL UNIQUE,
  client_id TEXT,
  owner_id TEXT,
  project_name TEXT NOT NULL,
  project_goal TEXT NOT NULL,
  target_user_company TEXT NOT NULL,
  owner_scope TEXT NOT NULL,
  status TEXT NOT NULL,
  approval_status TEXT NOT NULL,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  deployment_authority INTEGER NOT NULL DEFAULT 0,
  client_data_access INTEGER NOT NULL DEFAULT 0,
  agent_activation_allowed INTEGER NOT NULL DEFAULT 0,
  tool_execution_allowed INTEGER NOT NULL DEFAULT 0,
  network_authority INTEGER NOT NULL DEFAULT 0,
  synthetic_demo INTEGER NOT NULL DEFAULT 1,
  deployment_posture TEXT NOT NULL,
  support_management_posture TEXT NOT NULL,
  next_safe_move TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  run_id TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES project_capsule_runs(run_id)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS project_capsule_worlds (
  world_link_id TEXT PRIMARY KEY,
  capsule_id TEXT NOT NULL,
  world_id TEXT NOT NULL,
  binding_basis TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (capsule_id) REFERENCES project_capsules(capsule_id) ON DELETE CASCADE,
  UNIQUE(capsule_id, world_id, binding_basis)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS project_capsule_tools (
  tool_link_id TEXT PRIMARY KEY,
  capsule_id TEXT NOT NULL,
  tool_id TEXT NOT NULL,
  tool_role TEXT NOT NULL,
  candidate_status TEXT NOT NULL,
  approval_status TEXT NOT NULL,
  integration_status TEXT NOT NULL,
  execution_authority INTEGER NOT NULL DEFAULT 0,
  source_basis TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (capsule_id) REFERENCES project_capsules(capsule_id) ON DELETE CASCADE,
  UNIQUE(capsule_id, tool_id, tool_role)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS project_capsule_boundaries (
  boundary_id TEXT PRIMARY KEY,
  capsule_id TEXT NOT NULL,
  data_class TEXT NOT NULL,
  boundary_kind TEXT NOT NULL,
  authority_status TEXT NOT NULL,
  notes TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (capsule_id) REFERENCES project_capsules(capsule_id) ON DELETE CASCADE,
  UNIQUE(capsule_id, data_class, boundary_kind)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS project_capsule_receipt_requirements (
  requirement_id TEXT PRIMARY KEY,
  capsule_id TEXT NOT NULL,
  receipt_type TEXT NOT NULL,
  required INTEGER NOT NULL DEFAULT 1,
  notes TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (capsule_id) REFERENCES project_capsules(capsule_id) ON DELETE CASCADE,
  UNIQUE(capsule_id, receipt_type)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS project_capsule_read_model_requirements (
  requirement_id TEXT PRIMARY KEY,
  capsule_id TEXT NOT NULL,
  read_model_name TEXT NOT NULL,
  required INTEGER NOT NULL DEFAULT 1,
  purpose TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (capsule_id) REFERENCES project_capsules(capsule_id) ON DELETE CASCADE,
  UNIQUE(capsule_id, read_model_name)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS project_capsule_next_moves (
  next_move_id TEXT PRIMARY KEY,
  capsule_id TEXT NOT NULL,
  sequence INTEGER NOT NULL,
  move_label TEXT NOT NULL,
  move_text TEXT NOT NULL,
  authority_required TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (capsule_id) REFERENCES project_capsules(capsule_id) ON DELETE CASCADE,
  UNIQUE(capsule_id, sequence, move_label)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS project_capsule_modules (
  module_link_id TEXT PRIMARY KEY,
  capsule_id TEXT NOT NULL,
  module_id TEXT NOT NULL,
  selection_status TEXT NOT NULL,
  activation_status TEXT NOT NULL,
  authority_posture TEXT NOT NULL,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  operator_review_required INTEGER NOT NULL DEFAULT 0,
  source_basis TEXT NOT NULL,
  notes TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (capsule_id) REFERENCES project_capsules(capsule_id) ON DELETE CASCADE,
  UNIQUE(capsule_id, module_id)
)
""".strip(),
        "CREATE INDEX IF NOT EXISTS idx_project_capsules_project ON project_capsules(project_id)",
        "CREATE INDEX IF NOT EXISTS idx_project_capsule_modules_module ON project_capsule_modules(module_id)",
    )


def init_project_capsule_schema(db_path: str | Path | None = None) -> str:
    path = str(db_path or DEFAULT_DB_PATH)
    db_parent = Path(path).parent
    if db_parent and not db_parent.exists():
        db_parent.mkdir(parents=True, exist_ok=True)
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


def project_capsule_table_names(db_path: str | Path | None = None) -> tuple[str, ...]:
    path = init_project_capsule_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            """
SELECT name
FROM sqlite_master
WHERE type = 'table' AND name LIKE 'project_capsule_%'
ORDER BY name
""".strip()
        ).fetchall()
        return tuple(row[0] for row in rows)
    finally:
        conn.close()


def _delete_child_rows(conn: sqlite3.Connection, capsule_id: str) -> None:
    for table in (
        "project_capsule_worlds",
        "project_capsule_tools",
        "project_capsule_boundaries",
        "project_capsule_receipt_requirements",
        "project_capsule_read_model_requirements",
        "project_capsule_next_moves",
    ):
        conn.execute(f"DELETE FROM {table} WHERE capsule_id = ?", (capsule_id,))


def create_demo_project_capsule(
    db_path: str | Path | None = None,
    *,
    run_id: str | None = None,
) -> ProjectCapsuleResult:
    path = init_project_capsule_schema(db_path)
    now = utc_now()
    resolved_run_id = run_id or _row_id("pcaprun", DEMO_PROJECT_ID, now)
    capsule_id = _row_id("pcap", DEMO_PROJECT_ID)

    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            """
INSERT INTO project_capsule_runs (
  run_id, capsule_version, created_at, demo_mode, source_basis_json, notes
) VALUES (?, ?, ?, 1, ?, ?)
ON CONFLICT(run_id) DO UPDATE SET
  capsule_version = excluded.capsule_version,
  demo_mode = excluded.demo_mode,
  source_basis_json = excluded.source_basis_json,
  notes = excluded.notes
""".strip(),
            (
                resolved_run_id,
                PROJECT_CAPSULE_VERSION,
                now,
                stable_json(
                    {
                        "synthetic_demo_only": True,
                        "real_client_data": False,
                        "deployment": False,
                        "runtime_activation": False,
                        "tool_execution": False,
                    }
                ),
                "Project Capsule v0 creates a synthetic demo planning contract only.",
            ),
        )

        existing = conn.execute(
            "SELECT created_at FROM project_capsules WHERE project_id = ?",
            (DEMO_PROJECT_ID,),
        ).fetchone()
        created_at = existing[0] if existing else now
        next_safe_move = "Export the project capsule read-model, then generate the synthetic demo template."
        conn.execute(
            """
INSERT INTO project_capsules (
  capsule_id, project_id, client_id, owner_id, project_name, project_goal,
  target_user_company, owner_scope, status, approval_status, runtime_authority,
  deployment_authority, client_data_access, agent_activation_allowed,
  tool_execution_allowed, network_authority, synthetic_demo,
  deployment_posture, support_management_posture, next_safe_move,
  created_at, updated_at, run_id
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 1, ?, ?, ?, ?, ?, ?)
ON CONFLICT(project_id) DO UPDATE SET
  client_id = excluded.client_id,
  owner_id = excluded.owner_id,
  project_name = excluded.project_name,
  project_goal = excluded.project_goal,
  target_user_company = excluded.target_user_company,
  owner_scope = excluded.owner_scope,
  status = excluded.status,
  approval_status = excluded.approval_status,
  runtime_authority = excluded.runtime_authority,
  deployment_authority = excluded.deployment_authority,
  client_data_access = excluded.client_data_access,
  agent_activation_allowed = excluded.agent_activation_allowed,
  tool_execution_allowed = excluded.tool_execution_allowed,
  network_authority = excluded.network_authority,
  synthetic_demo = excluded.synthetic_demo,
  deployment_posture = excluded.deployment_posture,
  support_management_posture = excluded.support_management_posture,
  next_safe_move = excluded.next_safe_move,
  updated_at = excluded.updated_at,
  run_id = excluded.run_id
""".strip(),
            (
                capsule_id,
                DEMO_PROJECT_ID,
                DEMO_CLIENT_ID,
                "internal_demo_owner",
                "Demo Client Operations Helper",
                "Synthetic local planning capsule for a small operations helper; no real client data, deployment, or runtime authority.",
                "Synthetic demo operations team",
                "internal_demo",
                "draft",
                "not_approved",
                "deployment_not_authorized",
                "support_planning_only",
                next_safe_move,
                created_at,
                now,
                resolved_run_id,
            ),
        )

        _delete_child_rows(conn, capsule_id)
        for world_id, basis in DEMO_WORLDS:
            if world_id not in WORLD_IDS:
                raise ValueError(f"unknown world id: {world_id}")
            conn.execute(
                """
INSERT INTO project_capsule_worlds (
  world_link_id, capsule_id, world_id, binding_basis, created_at
) VALUES (?, ?, ?, ?, ?)
""".strip(),
                (_row_id("pcapworld", capsule_id, world_id, basis), capsule_id, world_id, basis, now),
            )

        for tool_id, role, candidate_status in DEMO_TOOLS:
            conn.execute(
                """
INSERT INTO project_capsule_tools (
  tool_link_id, capsule_id, tool_id, tool_role, candidate_status,
  approval_status, integration_status, execution_authority, source_basis, created_at
) VALUES (?, ?, ?, ?, ?, 'not_approved', 'not_integrated', 0, ?, ?)
""".strip(),
                (
                    _row_id("pcaptool", capsule_id, tool_id, role),
                    capsule_id,
                    tool_id,
                    role,
                    candidate_status,
                    "tool_intake_policy_metadata",
                    now,
                ),
            )

        for data_class, kind, authority_status, notes in DEMO_BOUNDARIES:
            conn.execute(
                """
INSERT INTO project_capsule_boundaries (
  boundary_id, capsule_id, data_class, boundary_kind, authority_status, notes, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?)
""".strip(),
                (
                    _row_id("pcapboundary", capsule_id, data_class, kind),
                    capsule_id,
                    data_class,
                    kind,
                    authority_status,
                    notes,
                    now,
                ),
            )

        for receipt_type, notes in DEMO_RECEIPT_REQUIREMENTS:
            conn.execute(
                """
INSERT INTO project_capsule_receipt_requirements (
  requirement_id, capsule_id, receipt_type, required, notes, created_at
) VALUES (?, ?, ?, 1, ?, ?)
""".strip(),
                (_row_id("pcapreceipt", capsule_id, receipt_type), capsule_id, receipt_type, notes, now),
            )

        for read_model_name, purpose in DEMO_READ_MODEL_REQUIREMENTS:
            conn.execute(
                """
INSERT INTO project_capsule_read_model_requirements (
  requirement_id, capsule_id, read_model_name, required, purpose, created_at
) VALUES (?, ?, ?, 1, ?, ?)
""".strip(),
                (
                    _row_id("pcapreadmodel", capsule_id, read_model_name),
                    capsule_id,
                    read_model_name,
                    purpose,
                    now,
                ),
            )

        for sequence, label, text in DEMO_NEXT_MOVES:
            conn.execute(
                """
INSERT INTO project_capsule_next_moves (
  next_move_id, capsule_id, sequence, move_label, move_text,
  authority_required, status, created_at
) VALUES (?, ?, ?, ?, ?, 'operator_review_before_authority', 'open', ?)
""".strip(),
                (_row_id("pcapmove", capsule_id, sequence, label), capsule_id, sequence, label, text, now),
            )

        capsule_count = conn.execute("SELECT COUNT(*) FROM project_capsules").fetchone()[0]
        counts = _capsule_child_counts(conn, capsule_id)
        conn.execute(
            """
UPDATE project_capsule_runs
SET completed_at = ?, capsule_count = ?
WHERE run_id = ?
""".strip(),
            (utc_now(), capsule_count, resolved_run_id),
        )
        conn.commit()
        return ProjectCapsuleResult(
            run_id=resolved_run_id,
            db_path=path,
            project_id=DEMO_PROJECT_ID,
            capsule_count=capsule_count,
            world_count=counts["worlds"],
            tool_count=counts["tools"],
            boundary_count=counts["boundaries"],
            next_move_count=counts["next_moves"],
        )
    finally:
        conn.close()


def _latest_run_id(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        """
SELECT run_id
FROM project_capsule_runs
ORDER BY completed_at DESC, created_at DESC, run_id DESC
LIMIT 1
""".strip()
    ).fetchone()
    return row["run_id"] if row else None


def _capsule_child_counts(conn: sqlite3.Connection, capsule_id: str) -> dict[str, int]:
    tables = {
        "worlds": "project_capsule_worlds",
        "tools": "project_capsule_tools",
        "boundaries": "project_capsule_boundaries",
        "receipt_requirements": "project_capsule_receipt_requirements",
        "read_model_requirements": "project_capsule_read_model_requirements",
        "next_moves": "project_capsule_next_moves",
        "modules": "project_capsule_modules",
    }
    return {
        key: int(
            conn.execute(f"SELECT COUNT(*) FROM {table} WHERE capsule_id = ?", (capsule_id,)).fetchone()[0]
        )
        for key, table in tables.items()
    }


def _rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def get_project_capsule(
    db_path: str | Path | None = None,
    *,
    project_id: str = DEMO_PROJECT_ID,
) -> dict[str, Any] | None:
    path = init_project_capsule_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM project_capsules WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        if not row:
            return None
        capsule = dict(row)
        capsule_id = capsule["capsule_id"]
        capsule["worlds"] = _rows(
            conn,
            "SELECT world_id, binding_basis FROM project_capsule_worlds WHERE capsule_id = ? ORDER BY world_id",
            (capsule_id,),
        )
        capsule["tools"] = _rows(
            conn,
            """
SELECT tool_id, tool_role, candidate_status, approval_status, integration_status,
       execution_authority, source_basis
FROM project_capsule_tools
WHERE capsule_id = ?
ORDER BY tool_id
""".strip(),
            (capsule_id,),
        )
        capsule["boundaries"] = _rows(
            conn,
            """
SELECT data_class, boundary_kind, authority_status, notes
FROM project_capsule_boundaries
WHERE capsule_id = ?
ORDER BY boundary_kind, data_class
""".strip(),
            (capsule_id,),
        )
        capsule["receipt_requirements"] = _rows(
            conn,
            """
SELECT receipt_type, required, notes
FROM project_capsule_receipt_requirements
WHERE capsule_id = ?
ORDER BY receipt_type
""".strip(),
            (capsule_id,),
        )
        capsule["read_model_requirements"] = _rows(
            conn,
            """
SELECT read_model_name, required, purpose
FROM project_capsule_read_model_requirements
WHERE capsule_id = ?
ORDER BY read_model_name
""".strip(),
            (capsule_id,),
        )
        capsule["next_moves"] = _rows(
            conn,
            """
SELECT sequence, move_label, move_text, authority_required, status
FROM project_capsule_next_moves
WHERE capsule_id = ?
ORDER BY sequence
""".strip(),
            (capsule_id,),
        )
        capsule["modules"] = _rows(
            conn,
            """
SELECT module_id, selection_status, activation_status, authority_posture,
       runtime_authority, operator_review_required, source_basis, notes
FROM project_capsule_modules
WHERE capsule_id = ?
ORDER BY module_id
""".strip(),
            (capsule_id,),
        )
        capsule["child_counts"] = _capsule_child_counts(conn, capsule_id)
        return capsule
    finally:
        conn.close()


def build_project_capsule_report(
    db_path: str | Path | None = None,
    *,
    run_id: str | None = None,
) -> dict[str, Any]:
    path = init_project_capsule_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        resolved_run_id = run_id or _latest_run_id(conn)
        if not resolved_run_id:
            return {"status": "no_runs", "section": "summary"}
        run = conn.execute(
            "SELECT * FROM project_capsule_runs WHERE run_id = ?",
            (resolved_run_id,),
        ).fetchone()
        capsule_rows = conn.execute(
            """
SELECT project_id, client_id, project_name, owner_scope, status, approval_status,
       runtime_authority, deployment_authority, client_data_access, synthetic_demo,
       next_safe_move
FROM project_capsules
ORDER BY project_id
""".strip()
        ).fetchall()
        status_counts = Counter(row["status"] for row in capsule_rows)
        approval_counts = Counter(row["approval_status"] for row in capsule_rows)
        return {
            "status": "ok",
            "section": "summary",
            "run_id": resolved_run_id,
            "run": dict(run),
            "counts": {
                "status": dict(sorted(status_counts.items())),
                "approval_status": dict(sorted(approval_counts.items())),
            },
            "capsules": [dict(row) for row in capsule_rows],
        }
    finally:
        conn.close()


def link_project_capsule_modules(
    db_path: str | Path | None = None,
    *,
    project_id: str = DEMO_PROJECT_ID,
    module_ids: Iterable[str] = DEFAULT_SELECTED_MODULES,
) -> ModuleSelectionResult:
    path = init_project_capsule_schema(db_path)
    now = utc_now()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        capsule = conn.execute(
            "SELECT capsule_id FROM project_capsules WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        if capsule is None:
            raise ValueError(f"project capsule not found: {project_id}")
        capsule_id = capsule["capsule_id"]
        unique_module_ids = tuple(dict.fromkeys(module_ids))
        for module_id in unique_module_ids:
            conn.execute(
                """
INSERT INTO project_capsule_modules (
  module_link_id, capsule_id, module_id, selection_status, activation_status,
  authority_posture, runtime_authority, operator_review_required, source_basis,
  notes, created_at
) VALUES (?, ?, ?, 'selected_planning_safe', 'not_activated', 'planning_only',
          0, 0, 'project_capsule_module_selection_v0', ?, ?)
ON CONFLICT(capsule_id, module_id) DO UPDATE SET
  selection_status = excluded.selection_status,
  activation_status = excluded.activation_status,
  authority_posture = excluded.authority_posture,
  runtime_authority = excluded.runtime_authority,
  operator_review_required = excluded.operator_review_required,
  source_basis = excluded.source_basis,
  notes = excluded.notes,
  created_at = excluded.created_at
""".strip(),
                (
                    _row_id("pcapmodule", capsule_id, module_id),
                    capsule_id,
                    module_id,
                    "Selected for planning context only; no module activation or runtime authority.",
                    now,
                ),
            )
        conn.commit()
        row = conn.execute(
            """
SELECT COUNT(*) AS count,
       SUM(CASE WHEN runtime_authority != 0 THEN 1 ELSE 0 END) AS runtime_count,
       SUM(CASE WHEN activation_status != 'not_activated' THEN 1 ELSE 0 END) AS activation_count
FROM project_capsule_modules
WHERE capsule_id = ?
""".strip(),
            (capsule_id,),
        ).fetchone()
        return ModuleSelectionResult(
            project_id=project_id,
            selected_module_count=int(row["count"]),
            runtime_authority=bool(row["runtime_count"]),
            activation_count=int(row["activation_count"]),
        )
    finally:
        conn.close()


def _count_line(title: str, counts: dict[str, int]) -> str:
    rendered = ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
    return f"- {title}: {rendered or 'none'}"


def format_project_capsule_report(report: dict[str, Any]) -> str:
    if report.get("status") == "no_runs":
        return "Project Capsule v0\n\nNo project capsule runs are recorded."
    run = report["run"]
    lines = [
        "Project Capsule v0",
        "",
        f"Run: `{report['run_id']}`",
        f"Capsules: {run['capsule_count']}",
        f"Demo mode: {bool(run['demo_mode'])}",
        f"Runtime authority: {bool(run['runtime_authority'])}",
        f"Deployment authority: {bool(run['deployment_authority'])}",
        f"Client data access: {bool(run['client_data_access'])}",
        "",
        "Counts:",
        _count_line("Status", report["counts"]["status"]),
        _count_line("Approval status", report["counts"]["approval_status"]),
        "",
        "Capsules:",
    ]
    for capsule in report.get("capsules") or []:
        lines.append(
            f"- {capsule['project_id']} ({capsule['project_name']}, {capsule['status']}, "
            f"{capsule['approval_status']}, synthetic_demo={bool(capsule['synthetic_demo'])})"
        )
    lines.extend(
        [
            "",
            "Boundary:",
            "- Project capsules are planning contracts only.",
            "- No runtime, deployment, client-data, network, tool, or agent authority is granted.",
        ]
    )
    return "\n".join(lines)


def format_project_capsule_detail(capsule: dict[str, Any] | None) -> str:
    if capsule is None:
        return "Project Capsule v0\n\nProject capsule not found."
    lines = [
        "Project Capsule v0 - Detail",
        "",
        f"Project: `{capsule['project_id']}`",
        f"Name: {capsule['project_name']}",
        f"Client: `{capsule['client_id']}`",
        f"Status: {capsule['status']}",
        f"Approval: {capsule['approval_status']}",
        f"Runtime authority: {bool(capsule['runtime_authority'])}",
        f"Deployment authority: {bool(capsule['deployment_authority'])}",
        f"Client data access: {bool(capsule['client_data_access'])}",
        "",
        "Worlds:",
    ]
    lines.extend(f"- {item['world_id']} ({item['binding_basis']})" for item in capsule["worlds"])
    lines.append("")
    lines.append("Tools:")
    lines.extend(
        f"- {item['tool_id']} ({item['tool_role']}, {item['approval_status']}, {item['integration_status']})"
        for item in capsule["tools"]
    )
    lines.append("")
    lines.append("Boundaries:")
    lines.extend(
        f"- {item['boundary_kind']}: {item['data_class']} ({item['authority_status']})"
        for item in capsule["boundaries"]
    )
    lines.append("")
    lines.append("Read-model requirements:")
    lines.extend(f"- {item['read_model_name']}" for item in capsule["read_model_requirements"])
    lines.append("")
    lines.append("Receipt requirements:")
    lines.extend(f"- {item['receipt_type']}" for item in capsule["receipt_requirements"])
    lines.append("")
    lines.append("Next moves:")
    lines.extend(
        f"- {item['sequence']}. {item['move_label']}: {item['move_text']}"
        for item in capsule["next_moves"]
    )
    if capsule["modules"]:
        lines.append("")
        lines.append("Selected modules:")
        lines.extend(
            f"- {item['module_id']} ({item['selection_status']}, {item['activation_status']})"
            for item in capsule["modules"]
        )
    lines.extend(
        [
            "",
            "Boundary:",
            "- Detail rows do not authorize deployment, runtime, tool execution, client data, or agent activation.",
        ]
    )
    return "\n".join(lines)
