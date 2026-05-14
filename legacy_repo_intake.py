"""Legacy GitHub Repo Intake v0 placeholder registry.

This module records future legacy repository intake contracts without cloning,
network access, file import, or truth promotion. It bridges placeholder legacy
roots into Corpus Atlas ``corpus_roots`` so the multi-root registry has one
place to represent non-canonical legacy sources.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from corpus_atlas import init_corpus_atlas_schema


LEGACY_REPO_INTAKE_VERSION = "legacy_repo_intake_v0"
PLACEHOLDER_ROOT_ID = "github_legacy_openclaw"


@dataclass(frozen=True)
class LegacyRepoIntakeResult:
    run_id: str
    db_path: str
    root_id: str
    root_count: int
    imported_count: int
    promoted_count: int


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
CREATE TABLE IF NOT EXISTS legacy_repo_intake_runs (
  run_id TEXT PRIMARY KEY,
  intake_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  root_count INTEGER NOT NULL DEFAULT 0,
  imported_count INTEGER NOT NULL DEFAULT 0,
  promoted_count INTEGER NOT NULL DEFAULT 0,
  network_access_attempted INTEGER NOT NULL DEFAULT 0,
  git_clone_attempted INTEGER NOT NULL DEFAULT 0,
  file_import_attempted INTEGER NOT NULL DEFAULT 0,
  truth_promotion_attempted INTEGER NOT NULL DEFAULT 0,
  runtime_authority INTEGER NOT NULL DEFAULT 0,
  source_basis_json TEXT NOT NULL,
  notes TEXT
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS legacy_repo_intake_roots (
  legacy_root_id TEXT PRIMARY KEY,
  root_id TEXT NOT NULL UNIQUE,
  repo_url TEXT,
  repo_name TEXT NOT NULL,
  root_kind TEXT NOT NULL,
  owner_scope TEXT NOT NULL,
  canonical_status TEXT NOT NULL,
  import_status TEXT NOT NULL,
  lineage_source TEXT NOT NULL,
  promotion_required INTEGER NOT NULL DEFAULT 1,
  operator_review_required INTEGER NOT NULL DEFAULT 1,
  registered_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  run_id TEXT NOT NULL,
  notes TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES legacy_repo_intake_runs(run_id)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS legacy_repo_intake_risks (
  risk_id TEXT PRIMARY KEY,
  root_id TEXT NOT NULL,
  risk_type TEXT NOT NULL,
  risk_level TEXT NOT NULL,
  risk_text TEXT NOT NULL,
  mitigation_status TEXT NOT NULL,
  operator_review_required INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  UNIQUE(root_id, risk_type)
)
""".strip(),
        "CREATE INDEX IF NOT EXISTS idx_legacy_repo_intake_roots_import ON legacy_repo_intake_roots(import_status)",
        "CREATE INDEX IF NOT EXISTS idx_legacy_repo_intake_roots_canonical ON legacy_repo_intake_roots(canonical_status)",
    )


def init_legacy_repo_intake_schema(db_path: str | Path | None = None) -> str:
    path = init_corpus_atlas_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        for statement in _sql_statements():
            conn.execute(statement)
        conn.commit()
    finally:
        conn.close()
    return path


def legacy_repo_intake_table_names(db_path: str | Path | None = None) -> tuple[str, ...]:
    path = init_legacy_repo_intake_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            """
SELECT name
FROM sqlite_master
WHERE type = 'table' AND name LIKE 'legacy_repo_intake_%'
ORDER BY name
""".strip()
        ).fetchall()
        return tuple(row[0] for row in rows)
    finally:
        conn.close()


def register_placeholder_legacy_repo(
    db_path: str | Path | None = None,
    *,
    run_id: str | None = None,
    root_id: str = PLACEHOLDER_ROOT_ID,
) -> LegacyRepoIntakeResult:
    path = init_legacy_repo_intake_schema(db_path)
    now = utc_now()
    resolved_run_id = run_id or _row_id("legacyrun", root_id, now)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            """
INSERT INTO legacy_repo_intake_runs (
  run_id, intake_version, created_at, source_basis_json, notes
) VALUES (?, ?, ?, ?, ?)
ON CONFLICT(run_id) DO UPDATE SET
  intake_version = excluded.intake_version,
  source_basis_json = excluded.source_basis_json,
  notes = excluded.notes
""".strip(),
            (
                resolved_run_id,
                LEGACY_REPO_INTAKE_VERSION,
                now,
                stable_json(
                    {
                        "placeholder_only": True,
                        "network_access": False,
                        "clone": False,
                        "file_import": False,
                        "truth_promotion": False,
                    }
                ),
                "Legacy root placeholder only; non-canonical until promoted in a later lane.",
            ),
        )

        repo_name = "github_legacy_openclaw"
        absolute_root = "not_imported://github/legacy_openclaw"
        conn.execute(
            """
INSERT INTO corpus_roots (
  root_id, root_kind, host_kind, owner_scope, project_id, client_id, instance_id,
  absolute_root, root_label, status, repo_url, repo_name, branch, commit_sha,
  remote_origin, canonical_status, import_status, mirror_of_root_id,
  lineage_source, created_at, updated_at, notes
) VALUES (?, 'legacy_git_repo', 'github', 'internal_platform', NULL, NULL, NULL,
          ?, 'Legacy GitHub OpenClaw repo', 'future_placeholder', NULL, ?,
          NULL, NULL, NULL, 'non_canonical_until_promoted', 'not_imported',
          NULL, 'legacy_external_repo', ?, ?, ?)
ON CONFLICT(root_id) DO UPDATE SET
  root_kind = excluded.root_kind,
  host_kind = excluded.host_kind,
  owner_scope = excluded.owner_scope,
  absolute_root = excluded.absolute_root,
  root_label = excluded.root_label,
  status = excluded.status,
  repo_url = excluded.repo_url,
  repo_name = excluded.repo_name,
  canonical_status = excluded.canonical_status,
  import_status = excluded.import_status,
  lineage_source = excluded.lineage_source,
  updated_at = excluded.updated_at,
  notes = excluded.notes
""".strip(),
            (
                root_id,
                absolute_root,
                repo_name,
                now,
                now,
                "Placeholder only. No clone, copy, import, or promotion has occurred.",
            ),
        )

        legacy_root_id = _row_id("legacyroot", root_id)
        existing = conn.execute(
            "SELECT registered_at FROM legacy_repo_intake_roots WHERE root_id = ?",
            (root_id,),
        ).fetchone()
        registered_at = existing["registered_at"] if existing else now
        conn.execute(
            """
INSERT INTO legacy_repo_intake_roots (
  legacy_root_id, root_id, repo_url, repo_name, root_kind, owner_scope,
  canonical_status, import_status, lineage_source, promotion_required,
  operator_review_required, registered_at, updated_at, run_id, notes
) VALUES (?, ?, NULL, ?, 'legacy_git_repo', 'internal_platform',
          'non_canonical_until_promoted', 'not_imported', 'legacy_external_repo',
          1, 1, ?, ?, ?, ?)
ON CONFLICT(root_id) DO UPDATE SET
  repo_url = excluded.repo_url,
  repo_name = excluded.repo_name,
  root_kind = excluded.root_kind,
  owner_scope = excluded.owner_scope,
  canonical_status = excluded.canonical_status,
  import_status = excluded.import_status,
  lineage_source = excluded.lineage_source,
  promotion_required = excluded.promotion_required,
  operator_review_required = excluded.operator_review_required,
  updated_at = excluded.updated_at,
  run_id = excluded.run_id,
  notes = excluded.notes
""".strip(),
            (
                legacy_root_id,
                root_id,
                repo_name,
                registered_at,
                now,
                resolved_run_id,
                "No external repository access has occurred; future import requires a bounded manifest/intake lane.",
            ),
        )

        risks = (
            (
                "stale_legacy_claims",
                "medium",
                "Legacy repository content may contain stale or superseded claims.",
            ),
            (
                "architecture_drift",
                "medium",
                "Legacy repository structure may not match current OpenClaw substrate boundaries.",
            ),
            (
                "sensitive_history",
                "high",
                "Legacy history may contain sensitive material and requires operator review before intake.",
            ),
        )
        for risk_type, risk_level, risk_text in risks:
            conn.execute(
                """
INSERT INTO legacy_repo_intake_risks (
  risk_id, root_id, risk_type, risk_level, risk_text, mitigation_status,
  operator_review_required, created_at
) VALUES (?, ?, ?, ?, ?, 'blocked_until_scoped_review', 1, ?)
ON CONFLICT(root_id, risk_type) DO UPDATE SET
  risk_level = excluded.risk_level,
  risk_text = excluded.risk_text,
  mitigation_status = excluded.mitigation_status,
  operator_review_required = excluded.operator_review_required,
  created_at = excluded.created_at
""".strip(),
                (_row_id("legacyrisk", root_id, risk_type), root_id, risk_type, risk_level, risk_text, now),
            )

        root_count = conn.execute("SELECT COUNT(*) FROM legacy_repo_intake_roots").fetchone()[0]
        imported_count = conn.execute(
            "SELECT COUNT(*) FROM legacy_repo_intake_roots WHERE import_status != 'not_imported'"
        ).fetchone()[0]
        promoted_count = conn.execute(
            "SELECT COUNT(*) FROM legacy_repo_intake_roots WHERE canonical_status != 'non_canonical_until_promoted'"
        ).fetchone()[0]
        conn.execute(
            """
UPDATE legacy_repo_intake_runs
SET completed_at = ?, root_count = ?, imported_count = ?, promoted_count = ?
WHERE run_id = ?
""".strip(),
            (utc_now(), root_count, imported_count, promoted_count, resolved_run_id),
        )
        conn.commit()
        return LegacyRepoIntakeResult(
            run_id=resolved_run_id,
            db_path=path,
            root_id=root_id,
            root_count=root_count,
            imported_count=imported_count,
            promoted_count=promoted_count,
        )
    finally:
        conn.close()


def _latest_run_id(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        """
SELECT run_id
FROM legacy_repo_intake_runs
ORDER BY completed_at DESC, created_at DESC, run_id DESC
LIMIT 1
""".strip()
    ).fetchone()
    return row["run_id"] if row else None


def build_legacy_repo_intake_report(
    db_path: str | Path | None = None,
    *,
    run_id: str | None = None,
    section: str = "summary",
) -> dict[str, Any]:
    path = init_legacy_repo_intake_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        resolved_run_id = run_id or _latest_run_id(conn)
        if not resolved_run_id:
            return {"status": "no_runs", "section": section, "items": []}
        run = conn.execute(
            "SELECT * FROM legacy_repo_intake_runs WHERE run_id = ?",
            (resolved_run_id,),
        ).fetchone()
        roots = [dict(row) for row in conn.execute(
            """
SELECT *
FROM legacy_repo_intake_roots
ORDER BY root_id
""".strip()
        ).fetchall()]
        risks = [dict(row) for row in conn.execute(
            """
SELECT *
FROM legacy_repo_intake_risks
ORDER BY risk_level DESC, risk_type
""".strip()
        ).fetchall()]
        if section == "roots":
            items = roots
        elif section == "promotion-candidates":
            items = [
                root for root in roots
                if root["promotion_required"] and root["operator_review_required"]
            ]
        elif section == "risks":
            items = risks
        elif section == "summary":
            items = roots
        else:
            raise ValueError(f"unknown legacy repo intake report: {section}")
        return {
            "status": "ok",
            "section": section,
            "run_id": resolved_run_id,
            "run": dict(run),
            "items": items,
            "risks": risks,
        }
    finally:
        conn.close()


def format_legacy_repo_intake_report(report: dict[str, Any]) -> str:
    if report.get("status") == "no_runs":
        return "Legacy Repo Intake v0\n\nNo legacy repo intake runs are recorded."
    run = report["run"]
    lines = [
        "Legacy Repo Intake v0",
        "",
        f"Run: `{report['run_id']}`",
        f"Roots: {run['root_count']}",
        f"Imported roots: {run['imported_count']}",
        f"Promoted roots: {run['promoted_count']}",
        f"Network access attempted: {bool(run['network_access_attempted'])}",
        f"Clone attempted: {bool(run['git_clone_attempted'])}",
        f"File import attempted: {bool(run['file_import_attempted'])}",
        f"Truth promotion attempted: {bool(run['truth_promotion_attempted'])}",
        "",
        "Items:",
    ]
    for item in report.get("items") or []:
        if "risk_type" in item:
            lines.append(f"- {item['risk_type']} ({item['risk_level']}): {item['risk_text']}")
        elif "root_id" in item:
            lines.append(
                f"- {item['root_id']} ({item.get('root_kind')}, {item.get('canonical_status')}, {item.get('import_status')})"
            )
    lines.extend(
        [
            "",
            "Boundary:",
            "- Legacy intake rows are non-canonical placeholders only.",
            "- No clone, network access, file import, or truth promotion is authorized.",
        ]
    )
    return "\n".join(lines)
