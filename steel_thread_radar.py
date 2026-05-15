"""Steel Thread Frontier Radar v0 for OpenClaw.

The Steel Thread Radar records strategic frontier signals as bounded metadata:
patterns noticed, OpenClaw alignment, evidence basis, recommendations, and
next lane proposals. It is not a news bot, web crawler, model caller,
notification engine, action creator, or execution surface.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from business_ops_ledger import DEFAULT_DB_PATH, init_business_ops_ledger


ROOT = Path(__file__).resolve().parent
STEEL_THREAD_VERSION = "steel_thread_frontier_radar_v0"
READ_MODEL_VERSION = "steel_thread_radar_read_model_v0"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
JSON_EXPORT_NAME = "steel_thread_radar.json"
OPERATOR_EXPORT_NAME = "steel_thread_radar_OPERATOR.md"

SOURCE_KINDS = {
    "operator_note",
    "markdown_doc",
    "report_bridge_package",
    "external_research_summary",
    "uploaded_source",
    "manual_seed",
    "unknown",
}

PATTERN_CATEGORIES = {
    "agent_orchestration",
    "local_first_ai",
    "coding_agents",
    "model_runtime",
    "UI_helm_pattern",
    "workflow_automation",
    "file_context",
    "business_model",
    "security_boundary",
    "unknown",
}

RELEVANCE_SCORES = {"low", "medium", "high"}
CONFIDENCE_LEVELS = {"low", "medium", "high"}
ALIGNMENT_STATUSES = {"aligned", "watch", "conflicting", "distracting", "unknown_review"}
RECOMMENDATIONS = {"adopt", "adapt", "watch", "defer", "ignore", "needs_review"}

NO_AUTHORITY_FLAGS = {
    "autonomous_update_allowed": False,
    "action_auto_create_allowed": False,
    "action_auto_approve_allowed": False,
    "action_auto_execute_allowed": False,
    "external_api_allowed": False,
    "web_crawl_allowed": False,
    "model_call_allowed": False,
    "agent_activation_allowed": False,
    "network_authority": False,
    "file_move_allowed": False,
    "file_delete_allowed": False,
}


@dataclass(frozen=True)
class SteelThreadSeed:
    signal_id: str
    title: str
    short_summary: str
    source_kind: str
    source_ref: str
    evidence_basis: str
    pattern_name: str
    pattern_category: str
    openclaw_mapping: tuple[str, ...]
    relevance_score: str
    confidence: str
    openclaw_alignment: str
    recommendation: str
    recommended_lane: str
    next_safe_move: str
    routed_agent: str
    risk_notes: str
    watchlist_note: str | None = None


@dataclass(frozen=True)
class SteelThreadBuildResult:
    run_id: str
    db_path: str
    signal_count: int
    high_relevance_count: int
    recommendations_by_status: dict[str, int]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _display_path(path: str | Path) -> str:
    path_obj = Path(path)
    try:
        return path_obj.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return path_obj.as_posix()


def _export_root_path(export_root: str | Path) -> Path:
    path = Path(export_root)
    if path.is_absolute():
        return path
    return ROOT / path


def _surface_status(repo_root: str | Path, relative_path: str) -> str:
    return "present" if (Path(repo_root) / relative_path).exists() else "not_present"


def _validate_seed(seed: SteelThreadSeed) -> None:
    if seed.source_kind not in SOURCE_KINDS:
        raise ValueError(f"invalid source_kind: {seed.source_kind}")
    if seed.pattern_category not in PATTERN_CATEGORIES:
        raise ValueError(f"invalid pattern_category: {seed.pattern_category}")
    if seed.relevance_score not in RELEVANCE_SCORES:
        raise ValueError(f"invalid relevance_score: {seed.relevance_score}")
    if seed.confidence not in CONFIDENCE_LEVELS:
        raise ValueError(f"invalid confidence: {seed.confidence}")
    if seed.openclaw_alignment not in ALIGNMENT_STATUSES:
        raise ValueError(f"invalid openclaw_alignment: {seed.openclaw_alignment}")
    if seed.recommendation not in RECOMMENDATIONS:
        raise ValueError(f"invalid recommendation: {seed.recommendation}")


def steel_thread_seed_signals(repo_root: str | Path = ROOT) -> tuple[SteelThreadSeed, ...]:
    """Return deterministic manual seed signals for v0.

    These are safe operator/repo-supplied signals only. No web lookup or live
    verification is attempted here.
    """
    work_board_status = _surface_status(repo_root, "work_board.py")
    context_pack_status = _surface_status(repo_root, "external_ai_context_packager.py")
    action_path_status = _surface_status(repo_root, "operator_action.py")
    return (
        SteelThreadSeed(
            signal_id="steel_signal_agent_work_board_orchestration",
            title="Agent work board / orchestration board pattern",
            short_summary=(
                "Operator-supplied OpenAI Symphony / Hermes Kanban pattern suggests "
                "agent task boards can be useful as orchestration control planes."
            ),
            source_kind="operator_note",
            source_ref="operator_supplied_tiktok_summary_openai_symphony_hermes_kanban",
            evidence_basis=(
                "source_claim/operator_note only; no direct web verification in this lane. "
                f"OpenClaw Work Board surface status: {work_board_status}."
            ),
            pattern_name="local agent work board",
            pattern_category="agent_orchestration",
            openclaw_mapping=(
                "Intent Router",
                "Agent Lane Registry",
                "Agent Work Packets",
                "Operator Actions",
                "Work Board",
                "Mission Control",
            ),
            relevance_score="high",
            confidence="medium",
            openclaw_alignment="aligned",
            recommendation="adapt",
            recommended_lane=(
                "OpenClaw Work Board v0 is built; next safe lane is Mission Control "
                "Work Board Read-Only Surface v0."
            ),
            next_safe_move=(
                "Surface the local SQLite Work Board in Mission Control as read-only "
                "cards; keep approval and execution backend-gated."
            ),
            routed_agent="chief",
            risk_notes=(
                "Do not add cloud board dependency, arbitrary execution, or auto-approval. "
                "Treat external product claims as unverified source claims."
            ),
        ),
        SteelThreadSeed(
            signal_id="steel_signal_external_ai_context_packs",
            title="Context pack generation for external AI tools",
            short_summary=(
                "Focused upload-ready context packs reduce manual context gathering for "
                "ChatGPT, Claude, Codex, Gemini, and local agents."
            ),
            source_kind="markdown_doc",
            source_ref="docs/operations/OPENCLAW_EXTERNAL_AI_CONTEXT_PACKAGER_V0.md",
            evidence_basis=(
                "Current OpenClaw context packager lane and read-model; "
                f"context packager surface status: {context_pack_status}."
            ),
            pattern_name="focused source pack export",
            pattern_category="workflow_automation",
            openclaw_mapping=(
                "External AI Context Packager",
                "Markdown Knowledge Atlas",
                "Generated Read-Models",
                "Agent Work Packets",
            ),
            relevance_score="high",
            confidence="high",
            openclaw_alignment="aligned",
            recommendation="adopt",
            recommended_lane=(
                "External AI Context Packager v0 is built; consider a Mission Control "
                "context-pack selection surface later."
            ),
            next_safe_move=(
                "Keep packs local/export-only and add operator selection UX later; "
                "do not automate browser uploads or external API calls."
            ),
            routed_agent="chief",
            risk_notes="Avoid giant undifferentiated dumps, no-go/private content, and external upload automation.",
        ),
        SteelThreadSeed(
            signal_id="steel_signal_helm_control_path_maturity",
            title="Helm control path maturity",
            short_summary=(
                "OpenClaw's orient/request/review/approve/execute/receipt loop is "
                "becoming the core local-first control path."
            ),
            source_kind="manual_seed",
            source_ref="operator_action_path_and_mission_control_helm_doctrine",
            evidence_basis=(
                "Existing Operator Action Path, Operator Intent Inbox, Work Board, "
                f"and Mission Control read-only helm doctrine. Operator action surface status: {action_path_status}."
            ),
            pattern_name="approval-gated helm operations",
            pattern_category="UI_helm_pattern",
            openclaw_mapping=(
                "Operator Intent Inbox",
                "Operator Action Path",
                "Work Board",
                "Agent Runtime Readiness",
                "Mission Control Helm",
            ),
            relevance_score="high",
            confidence="high",
            openclaw_alignment="watch",
            recommendation="watch",
            recommended_lane="Mission Control Request Path v0",
            next_safe_move=(
                "Let Mission Control draft request JSON into the shared inbox, but keep "
                "approval and execution separate and backend-gated."
            ),
            routed_agent="chief",
            risk_notes="No action buttons that bypass approval; no fake live health; no hidden persistence or execution.",
            watchlist_note="Watch for UI pressure to collapse request, approval, and execution into one unsafe control.",
        ),
    )


def _sql_statements() -> tuple[str, ...]:
    return (
        """
CREATE TABLE IF NOT EXISTS steel_thread_runs (
  run_id TEXT PRIMARY KEY,
  radar_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  signal_count INTEGER NOT NULL DEFAULT 0,
  high_relevance_count INTEGER NOT NULL DEFAULT 0,
  autonomous_update_allowed INTEGER NOT NULL DEFAULT 0,
  action_auto_create_allowed INTEGER NOT NULL DEFAULT 0,
  action_auto_approve_allowed INTEGER NOT NULL DEFAULT 0,
  action_auto_execute_allowed INTEGER NOT NULL DEFAULT 0,
  external_api_allowed INTEGER NOT NULL DEFAULT 0,
  web_crawl_allowed INTEGER NOT NULL DEFAULT 0,
  model_call_allowed INTEGER NOT NULL DEFAULT 0,
  agent_activation_allowed INTEGER NOT NULL DEFAULT 0,
  network_authority INTEGER NOT NULL DEFAULT 0,
  file_move_allowed INTEGER NOT NULL DEFAULT 0,
  file_delete_allowed INTEGER NOT NULL DEFAULT 0,
  notes TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS steel_thread_signals (
  signal_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  title TEXT NOT NULL,
  short_summary TEXT NOT NULL,
  source_kind TEXT NOT NULL,
  source_ref TEXT NOT NULL,
  evidence_basis TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  pattern_category TEXT NOT NULL,
  relevance_score TEXT NOT NULL,
  confidence TEXT NOT NULL,
  openclaw_alignment TEXT NOT NULL,
  recommendation TEXT NOT NULL,
  recommended_lane TEXT NOT NULL,
  routed_agent TEXT NOT NULL,
  risk_notes TEXT NOT NULL,
  action_created INTEGER NOT NULL DEFAULT 0,
  notification_sent INTEGER NOT NULL DEFAULT 0,
  raw_body_stored INTEGER NOT NULL DEFAULT 0,
  autonomous_update_allowed INTEGER NOT NULL DEFAULT 0,
  external_api_allowed INTEGER NOT NULL DEFAULT 0,
  web_crawl_allowed INTEGER NOT NULL DEFAULT 0,
  model_call_allowed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES steel_thread_runs(run_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS steel_thread_evidence_links (
  evidence_link_id TEXT PRIMARY KEY,
  signal_id TEXT NOT NULL,
  source_kind TEXT NOT NULL,
  source_ref TEXT NOT NULL,
  evidence_basis TEXT NOT NULL,
  verified_truth_claim INTEGER NOT NULL DEFAULT 0,
  raw_body_stored INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY (signal_id) REFERENCES steel_thread_signals(signal_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS steel_thread_patterns (
  pattern_id TEXT PRIMARY KEY,
  signal_id TEXT NOT NULL,
  pattern_name TEXT NOT NULL,
  pattern_category TEXT NOT NULL,
  openclaw_mapping_json TEXT NOT NULL,
  relevance_score TEXT NOT NULL,
  confidence TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (signal_id) REFERENCES steel_thread_signals(signal_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS steel_thread_recommendations (
  recommendation_id TEXT PRIMARY KEY,
  signal_id TEXT NOT NULL,
  recommendation TEXT NOT NULL,
  recommended_lane TEXT NOT NULL,
  next_safe_move TEXT NOT NULL,
  routed_agent TEXT NOT NULL,
  approval_required INTEGER NOT NULL DEFAULT 1,
  action_created INTEGER NOT NULL DEFAULT 0,
  notification_sent INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY (signal_id) REFERENCES steel_thread_signals(signal_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS steel_thread_alignment_links (
  alignment_link_id TEXT PRIMARY KEY,
  signal_id TEXT NOT NULL,
  related_surface TEXT NOT NULL,
  relation TEXT NOT NULL,
  surface_status TEXT NOT NULL,
  authority_note TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (signal_id) REFERENCES steel_thread_signals(signal_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS steel_thread_watchlist_items (
  watchlist_item_id TEXT PRIMARY KEY,
  signal_id TEXT NOT NULL,
  title TEXT NOT NULL,
  watch_reason TEXT NOT NULL,
  next_review_trigger TEXT NOT NULL,
  notification_sent INTEGER NOT NULL DEFAULT 0,
  action_created INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY (signal_id) REFERENCES steel_thread_signals(signal_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS steel_thread_query_receipts (
  query_receipt_id TEXT PRIMARY KEY,
  query_kind TEXT NOT NULL,
  filter_value TEXT,
  result_count INTEGER NOT NULL,
  generated_at TEXT NOT NULL,
  raw_body_stored INTEGER NOT NULL DEFAULT 0
)
""".strip(),
        "CREATE INDEX IF NOT EXISTS idx_steel_thread_signals_relevance ON steel_thread_signals(relevance_score)",
        "CREATE INDEX IF NOT EXISTS idx_steel_thread_signals_recommendation ON steel_thread_signals(recommendation)",
        "CREATE INDEX IF NOT EXISTS idx_steel_thread_patterns_category ON steel_thread_patterns(pattern_category)",
    )


def init_steel_thread_schema(db_path: str | Path | None = None) -> str:
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


def steel_thread_table_names(db_path: str | Path | None = None) -> tuple[str, ...]:
    path = init_steel_thread_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            """
SELECT name
FROM sqlite_master
WHERE type = 'table' AND name LIKE 'steel_thread%'
ORDER BY name
""".strip()
        ).fetchall()
        return tuple(row[0] for row in rows)
    finally:
        conn.close()


def _clear_seed_children(conn: sqlite3.Connection, signal_id: str) -> None:
    for table in (
        "steel_thread_evidence_links",
        "steel_thread_patterns",
        "steel_thread_recommendations",
        "steel_thread_alignment_links",
        "steel_thread_watchlist_items",
    ):
        conn.execute(f"DELETE FROM {table} WHERE signal_id = ?", (signal_id,))


def _insert_seed(
    conn: sqlite3.Connection,
    *,
    seed: SteelThreadSeed,
    run_id: str,
    repo_root: str | Path,
    now: str,
) -> None:
    _validate_seed(seed)
    _clear_seed_children(conn, seed.signal_id)
    conn.execute(
        """
INSERT OR REPLACE INTO steel_thread_signals (
  signal_id, run_id, title, short_summary, source_kind, source_ref,
  evidence_basis, observed_at, pattern_category, relevance_score, confidence,
  openclaw_alignment, recommendation, recommended_lane, routed_agent,
  risk_notes, action_created, notification_sent, raw_body_stored,
  autonomous_update_allowed, external_api_allowed, web_crawl_allowed,
  model_call_allowed, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 0, ?)
""".strip(),
        (
            seed.signal_id,
            run_id,
            seed.title,
            seed.short_summary,
            seed.source_kind,
            seed.source_ref,
            seed.evidence_basis,
            now,
            seed.pattern_category,
            seed.relevance_score,
            seed.confidence,
            seed.openclaw_alignment,
            seed.recommendation,
            seed.recommended_lane,
            seed.routed_agent,
            seed.risk_notes,
            now,
        ),
    )
    evidence_id = _row_id("steel_evidence", seed.signal_id, seed.source_ref)
    conn.execute(
        """
INSERT OR REPLACE INTO steel_thread_evidence_links (
  evidence_link_id, signal_id, source_kind, source_ref, evidence_basis,
  verified_truth_claim, raw_body_stored, created_at
) VALUES (?, ?, ?, ?, ?, 0, 0, ?)
""".strip(),
        (evidence_id, seed.signal_id, seed.source_kind, seed.source_ref, seed.evidence_basis, now),
    )
    pattern_id = _row_id("steel_pattern", seed.signal_id, seed.pattern_name)
    conn.execute(
        """
INSERT OR REPLACE INTO steel_thread_patterns (
  pattern_id, signal_id, pattern_name, pattern_category, openclaw_mapping_json,
  relevance_score, confidence, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""".strip(),
        (
            pattern_id,
            seed.signal_id,
            seed.pattern_name,
            seed.pattern_category,
            stable_json(list(seed.openclaw_mapping)),
            seed.relevance_score,
            seed.confidence,
            now,
        ),
    )
    recommendation_id = _row_id("steel_recommendation", seed.signal_id, seed.recommended_lane)
    conn.execute(
        """
INSERT OR REPLACE INTO steel_thread_recommendations (
  recommendation_id, signal_id, recommendation, recommended_lane,
  next_safe_move, routed_agent, approval_required, action_created,
  notification_sent, created_at
) VALUES (?, ?, ?, ?, ?, ?, 1, 0, 0, ?)
""".strip(),
        (
            recommendation_id,
            seed.signal_id,
            seed.recommendation,
            seed.recommended_lane,
            seed.next_safe_move,
            seed.routed_agent,
            now,
        ),
    )
    for surface in seed.openclaw_mapping:
        surface_ref = surface.lower().replace(" ", "_")
        relative_guess = {
            "work_board": "work_board.py",
            "intent_router": "intent_router.py",
            "agent_lane_registry": "agent_lane_registry.py",
            "agent_work_packets": "agent_work_packet.py",
            "operator_actions": "operator_action.py",
            "external_ai_context_packager": "external_ai_context_packager.py",
            "mission_control": "docs/operations/OPENCLAW_SUBSTRATE_MISSION_CONTROL_CHECKPOINT_V1.md",
        }.get(surface_ref, "")
        status = _surface_status(repo_root, relative_guess) if relative_guess else "metadata_link_only"
        conn.execute(
            """
INSERT OR REPLACE INTO steel_thread_alignment_links (
  alignment_link_id, signal_id, related_surface, relation, surface_status,
  authority_note, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?)
""".strip(),
            (
                _row_id("steel_align", seed.signal_id, surface),
                seed.signal_id,
                surface,
                "openclaw_mapping",
                status,
                "Metadata alignment only; this link grants no authority.",
                now,
            ),
        )
    if seed.watchlist_note or seed.recommendation in {"watch", "defer", "needs_review"}:
        conn.execute(
            """
INSERT OR REPLACE INTO steel_thread_watchlist_items (
  watchlist_item_id, signal_id, title, watch_reason, next_review_trigger,
  notification_sent, action_created, created_at
) VALUES (?, ?, ?, ?, ?, 0, 0, ?)
""".strip(),
            (
                _row_id("steel_watch", seed.signal_id),
                seed.signal_id,
                seed.title,
                seed.watchlist_note or seed.risk_notes,
                "Review when Chief proposes the related lane or new operator evidence arrives.",
                now,
            ),
        )


def build_steel_thread_radar(
    *,
    db_path: str | Path | None = None,
    repo_root: str | Path = ROOT,
    run_id: str | None = None,
) -> SteelThreadBuildResult:
    path = init_steel_thread_schema(db_path)
    now = utc_now()
    actual_run_id = run_id or _row_id("steel_run", STEEL_THREAD_VERSION, now)
    seeds = steel_thread_seed_signals(repo_root)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(
            """
INSERT OR REPLACE INTO steel_thread_runs (
  run_id, radar_version, created_at, completed_at, signal_count,
  high_relevance_count, autonomous_update_allowed, action_auto_create_allowed,
  action_auto_approve_allowed, action_auto_execute_allowed, external_api_allowed,
  web_crawl_allowed, model_call_allowed, agent_activation_allowed,
  network_authority, file_move_allowed, file_delete_allowed, notes
) VALUES (?, ?, ?, NULL, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, ?)
""".strip(),
            (
                actual_run_id,
                STEEL_THREAD_VERSION,
                now,
                "Manual-seed frontier radar run; no external API, web crawl, model call, action, or notification.",
            ),
        )
        for seed in seeds:
            _insert_seed(conn, seed=seed, run_id=actual_run_id, repo_root=repo_root, now=now)
        counts = Counter(
            row["recommendation"]
            for row in conn.execute("SELECT recommendation FROM steel_thread_signals").fetchall()
        )
        signal_count = conn.execute("SELECT COUNT(*) AS count FROM steel_thread_signals").fetchone()["count"]
        high_relevance_count = conn.execute(
            "SELECT COUNT(*) AS count FROM steel_thread_signals WHERE relevance_score = 'high'"
        ).fetchone()["count"]
        conn.execute(
            """
UPDATE steel_thread_runs
SET completed_at = ?, signal_count = ?, high_relevance_count = ?
WHERE run_id = ?
""".strip(),
            (now, signal_count, high_relevance_count, actual_run_id),
        )
        conn.commit()
        return SteelThreadBuildResult(
            run_id=actual_run_id,
            db_path=path,
            signal_count=int(signal_count),
            high_relevance_count=int(high_relevance_count),
            recommendations_by_status=dict(sorted(counts.items())),
        )
    finally:
        conn.close()


REPORT_SECTIONS = {
    "summary",
    "recommendations",
    "watchlist",
    "high-relevance",
    "category",
}


def _dict_rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def build_steel_thread_report(
    *,
    db_path: str | Path | None = None,
    report: str = "summary",
    category: str | None = None,
) -> dict[str, Any]:
    if report not in REPORT_SECTIONS:
        raise ValueError(f"unsupported report: {report}")
    if category and category not in PATTERN_CATEGORIES:
        raise ValueError(f"unsupported category: {category}")
    path = init_steel_thread_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        counts = {
            "signal_count": conn.execute("SELECT COUNT(*) AS count FROM steel_thread_signals").fetchone()["count"],
            "high_relevance_count": conn.execute(
                "SELECT COUNT(*) AS count FROM steel_thread_signals WHERE relevance_score = 'high'"
            ).fetchone()["count"],
            "watchlist_count": conn.execute("SELECT COUNT(*) AS count FROM steel_thread_watchlist_items").fetchone()[
                "count"
            ],
        }
        recommendations_by_status = dict(
            Counter(row["recommendation"] for row in conn.execute("SELECT recommendation FROM steel_thread_signals"))
        )
        rows: list[dict[str, Any]]
        filter_value = category
        if report == "recommendations":
            rows = _dict_rows(
                conn,
                """
SELECT s.signal_id, s.title, s.relevance_score, s.confidence, s.openclaw_alignment,
       r.recommendation, r.recommended_lane, r.next_safe_move, r.routed_agent
FROM steel_thread_signals s
JOIN steel_thread_recommendations r ON r.signal_id = s.signal_id
ORDER BY CASE s.relevance_score WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
         s.title
""".strip(),
            )
        elif report == "watchlist":
            rows = _dict_rows(
                conn,
                """
SELECT w.title, w.watch_reason, w.next_review_trigger, s.recommendation, s.routed_agent
FROM steel_thread_watchlist_items w
JOIN steel_thread_signals s ON s.signal_id = w.signal_id
ORDER BY w.title
""".strip(),
            )
        elif report == "high-relevance":
            rows = _dict_rows(
                conn,
                """
SELECT signal_id, title, pattern_category, confidence, openclaw_alignment,
       recommendation, recommended_lane, risk_notes
FROM steel_thread_signals
WHERE relevance_score = 'high'
ORDER BY title
""".strip(),
            )
        elif report == "category":
            rows = _dict_rows(
                conn,
                """
SELECT s.signal_id, s.title, s.relevance_score, s.confidence,
       s.openclaw_alignment, s.recommendation, s.recommended_lane
FROM steel_thread_signals s
WHERE s.pattern_category = ?
ORDER BY s.title
""".strip(),
                (category or "unknown",),
            )
        else:
            rows = _dict_rows(
                conn,
                """
SELECT signal_id, title, source_kind, pattern_category, relevance_score,
       confidence, openclaw_alignment, recommendation, recommended_lane
FROM steel_thread_signals
ORDER BY title
""".strip(),
            )
        receipt_id = _row_id("steel_query", report, category or "", utc_now())
        conn.execute(
            """
INSERT INTO steel_thread_query_receipts (
  query_receipt_id, query_kind, filter_value, result_count, generated_at, raw_body_stored
) VALUES (?, ?, ?, ?, ?, 0)
""".strip(),
            (receipt_id, report, filter_value, len(rows), utc_now()),
        )
        conn.commit()
        return {
            "schema_version": STEEL_THREAD_VERSION,
            "db_path": path,
            "report": report,
            "category": category,
            "counts": counts,
            "recommendations_by_status": dict(sorted(recommendations_by_status.items())),
            "rows": rows,
            "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        }
    finally:
        conn.close()


def _latest_signal(conn: sqlite3.Connection) -> dict[str, Any] | None:
    row = conn.execute(
        """
SELECT signal_id, title, source_kind, pattern_category, relevance_score,
       recommendation, recommended_lane, created_at
FROM steel_thread_signals
ORDER BY created_at DESC, signal_id DESC
LIMIT 1
""".strip()
    ).fetchone()
    return dict(row) if row else None


def build_steel_thread_read_model(db_path: str | Path | None = None) -> dict[str, Any]:
    path = init_steel_thread_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        signals = _dict_rows(
            conn,
            """
SELECT signal_id, title, short_summary, source_kind, source_ref,
       evidence_basis, pattern_category, relevance_score, confidence,
       openclaw_alignment, recommendation, recommended_lane, routed_agent,
       risk_notes
FROM steel_thread_signals
ORDER BY CASE relevance_score WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
         title
""".strip(),
        )
        recommendations = _dict_rows(
            conn,
            """
SELECT r.recommendation, r.recommended_lane, r.next_safe_move, r.routed_agent,
       s.title, s.relevance_score, s.confidence
FROM steel_thread_recommendations r
JOIN steel_thread_signals s ON s.signal_id = r.signal_id
ORDER BY CASE s.relevance_score WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
         s.title
""".strip(),
        )
        watchlist_items = _dict_rows(
            conn,
            """
SELECT w.title, w.watch_reason, w.next_review_trigger
FROM steel_thread_watchlist_items w
ORDER BY w.title
""".strip(),
        )
        recommendation_counts = Counter(signal["recommendation"] for signal in signals)
        category_counts = Counter(signal["pattern_category"] for signal in signals)
        return {
            "schema_version": READ_MODEL_VERSION,
            "generated_at": utc_now(),
            "source_ledger_path": str(path),
            "signal_count": len(signals),
            "high_relevance_count": sum(1 for signal in signals if signal["relevance_score"] == "high"),
            "recommendations_by_status": dict(sorted(recommendation_counts.items())),
            "pattern_categories": dict(sorted(category_counts.items())),
            "top_recommendations": recommendations[:8],
            "watchlist_items": watchlist_items,
            "recommended_next_lanes": [row["recommended_lane"] for row in recommendations[:8]],
            "latest_signal": _latest_signal(conn),
            "signals": signals,
            "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        }
    finally:
        conn.close()


def _operator_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Steel Thread Frontier Radar",
        "",
        "Steel Thread is strategic signal intake for OpenClaw. It records frontier patterns, "
        "OpenClaw alignment, and next-lane recommendations without browsing, calling models, "
        "creating actions, or notifying the operator.",
        "",
        "## Summary",
        f"- Signals: {payload['signal_count']}",
        f"- High relevance: {payload['high_relevance_count']}",
        f"- Recommendations: {payload['recommendations_by_status']}",
        "",
        "## Top Recommendations",
    ]
    for row in payload["top_recommendations"]:
        lines.append(
            f"- **{row['title']}**: {row['recommendation']} -> {row['recommended_lane']}"
        )
        lines.append(f"  - Next safe move: {row['next_safe_move']}")
    lines.extend(["", "## Watchlist"])
    if payload["watchlist_items"]:
        for row in payload["watchlist_items"]:
            lines.append(f"- **{row['title']}**: {row['watch_reason']}")
    else:
        lines.append("- No watchlist items recorded.")
    lines.extend(
        [
            "",
            "## Boundary",
            "- Steel Thread is not an autonomous updater, news bot, web crawler, model-calling agent, or action engine.",
            "- Operator-supplied external claims are source claims unless separately verified.",
            "- Recommendations require explicit lane approval before implementation.",
            "",
            "## No-Authority Flags",
        ]
    )
    for key, value in payload["no_authority_flags"].items():
        lines.append(f"- {key}={str(value).lower()}")
    return "\n".join(lines) + "\n"


def export_steel_thread_radar_read_model(
    *,
    db_path: str | Path | None = None,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
) -> dict[str, Any]:
    payload = build_steel_thread_read_model(db_path)
    out_root = _export_root_path(export_root)
    out_root.mkdir(parents=True, exist_ok=True)
    json_path = out_root / JSON_EXPORT_NAME
    operator_path = out_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(_operator_markdown(payload), encoding="utf-8")
    return {
        "json_path": _display_path(json_path),
        "operator_path": _display_path(operator_path),
        "signal_count": payload["signal_count"],
        "high_relevance_count": payload["high_relevance_count"],
        "recommendations_by_status": payload["recommendations_by_status"],
        "no_authority_flags": payload["no_authority_flags"],
    }


def format_build_result(result: SteelThreadBuildResult) -> str:
    lines = [
        "Steel Thread Frontier Radar v0",
        "",
        f"Run: {result.run_id}",
        f"Ledger: `{result.db_path}`",
        f"Signals: {result.signal_count}",
        f"High relevance: {result.high_relevance_count}",
        f"Recommendations: {result.recommendations_by_status}",
        "",
        "Boundary:",
        "- Manual seed signals only; no web/API/model calls, actions, notifications, or autonomous updates.",
    ]
    return "\n".join(lines)


def format_steel_thread_report(payload: dict[str, Any]) -> str:
    lines = [
        "Steel Thread Frontier Radar v0",
        "",
        f"Report: {payload['report']}",
    ]
    if payload.get("category"):
        lines.append(f"Category: {payload['category']}")
    lines.extend(
        [
            f"Signals: {payload['counts']['signal_count']}",
            f"High relevance: {payload['counts']['high_relevance_count']}",
            f"Watchlist: {payload['counts']['watchlist_count']}",
            f"Recommendations: {payload['recommendations_by_status']}",
            "",
            "Rows:",
        ]
    )
    if not payload["rows"]:
        lines.append("- none")
    for row in payload["rows"]:
        title = row.get("title") or row.get("signal_id") or "row"
        recommendation = row.get("recommendation")
        lane = row.get("recommended_lane")
        if recommendation and lane:
            lines.append(f"- {title}: {recommendation} -> {lane}")
        else:
            lines.append(f"- {title}")
    lines.extend(
        [
            "",
            "Boundary:",
            "- No authority to browse, call APIs/models, notify, create actions, approve, execute, move, or delete files.",
        ]
    )
    return "\n".join(lines)

