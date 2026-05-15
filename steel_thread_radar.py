"""Steel Thread Frontier Radar v0 for OpenClaw.

The Steel Thread Radar records strategic frontier signals as bounded metadata:
patterns noticed, OpenClaw alignment, evidence basis, recommendations, and
next lane proposals. It is not a news bot, web crawler, model caller,
notification engine, action creator, or execution surface.
"""

from __future__ import annotations

import hashlib
import html
import json
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
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
DEFAULT_LOCAL_PACKET_ROOT = Path("generated/frontier_research_packets")
JSON_EXPORT_NAME = "steel_thread_radar.json"
OPERATOR_EXPORT_NAME = "steel_thread_radar_OPERATOR.md"
MAX_LOCAL_PACKET_BYTES = 120_000
MAX_FEED_FETCH_BYTES = 500_000
MAX_ITEM_EXCERPT_CHARS = 900

SOURCE_KINDS = {
    "operator_note",
    "markdown_doc",
    "report_bridge_package",
    "external_research_summary",
    "local_research_packet",
    "uploaded_source",
    "manual_seed",
    "unknown",
}

SOURCE_REGISTRY_KINDS = {
    "rss_feed",
    "atom_feed",
    "github_releases",
    "github_repo",
    "official_blog",
    "local_research_packet",
    "manual_seed",
}

TRUST_LEVELS = {"official", "reputable", "community", "operator_supplied", "unknown"}
FETCH_POLICIES = {"metadata_only", "title_summary_only", "release_notes_bounded", "local_packet_only"}

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
    "broad_web_crawl_allowed": False,
    "recursive_crawl_allowed": False,
    "browser_automation_allowed": False,
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

URL_SOURCE_KINDS = {"rss_feed", "atom_feed", "github_releases", "github_repo", "official_blog"}
NO_GO_PATH_PARTS = {
    ".chief.env",
    ".google-secrets",
    ".ssh",
    "auth",
    "client",
    "credential",
    "credentials",
    "cpa",
    "finance",
    "legal",
    "no-go",
    "no_go",
    "private",
    "secret",
    "secrets",
    "tax",
    "token",
    "vault",
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


@dataclass(frozen=True)
class SteelThreadSourceSeed:
    source_id: str
    source_name: str
    source_kind: str
    url: str | None
    local_path: str | None
    owner_scope: str
    trust_level: str
    enabled: bool
    fetch_policy: str
    max_items_per_run: int
    rate_limit_seconds: int


@dataclass(frozen=True)
class SteelThreadFetchResult:
    run_id: str
    db_path: str
    source_count: int
    enabled_source_count: int
    fetched_item_count: int
    local_packet_count: int
    rejected_count: int
    network_fetch_attempted: bool
    dry_run: bool


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


def steel_thread_source_seeds() -> tuple[SteelThreadSourceSeed, ...]:
    """Return the conservative v0 approved source registry seed set."""
    return (
        SteelThreadSourceSeed(
            source_id="operator_manual_frontier_notes",
            source_name="Operator manual frontier notes",
            source_kind="manual_seed",
            url=None,
            local_path=None,
            owner_scope="internal_platform",
            trust_level="operator_supplied",
            enabled=True,
            fetch_policy="metadata_only",
            max_items_per_run=20,
            rate_limit_seconds=0,
        ),
        SteelThreadSourceSeed(
            source_id="local_frontier_research_packets",
            source_name="Local frontier research packets",
            source_kind="local_research_packet",
            url=None,
            local_path=DEFAULT_LOCAL_PACKET_ROOT.as_posix(),
            owner_scope="internal_platform",
            trust_level="operator_supplied",
            enabled=True,
            fetch_policy="local_packet_only",
            max_items_per_run=20,
            rate_limit_seconds=0,
        ),
        SteelThreadSourceSeed(
            source_id="official_ai_tooling_feeds",
            source_name="Official AI tooling feeds",
            source_kind="official_blog",
            url=None,
            local_path=None,
            owner_scope="external_public",
            trust_level="official",
            enabled=False,
            fetch_policy="title_summary_only",
            max_items_per_run=10,
            rate_limit_seconds=3600,
        ),
        SteelThreadSourceSeed(
            source_id="github_agent_framework_releases",
            source_name="GitHub agent framework releases",
            source_kind="github_releases",
            url=None,
            local_path=None,
            owner_scope="external_public",
            trust_level="reputable",
            enabled=False,
            fetch_policy="release_notes_bounded",
            max_items_per_run=10,
            rate_limit_seconds=3600,
        ),
    )


def _validate_source_seed(seed: SteelThreadSourceSeed) -> None:
    if seed.source_kind not in SOURCE_REGISTRY_KINDS:
        raise ValueError(f"invalid source_kind: {seed.source_kind}")
    if seed.trust_level not in TRUST_LEVELS:
        raise ValueError(f"invalid trust_level: {seed.trust_level}")
    if seed.fetch_policy not in FETCH_POLICIES:
        raise ValueError(f"invalid fetch_policy: {seed.fetch_policy}")
    if seed.url and seed.source_kind not in URL_SOURCE_KINDS:
        raise ValueError("url configured for non-url source kind")


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
CREATE TABLE IF NOT EXISTS steel_thread_source_registry (
  source_id TEXT PRIMARY KEY,
  source_name TEXT NOT NULL,
  source_kind TEXT NOT NULL,
  url TEXT,
  local_path TEXT,
  owner_scope TEXT NOT NULL,
  trust_level TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 0,
  fetch_policy TEXT NOT NULL,
  max_items_per_run INTEGER NOT NULL DEFAULT 10,
  rate_limit_seconds INTEGER NOT NULL DEFAULT 3600,
  broad_web_crawl_allowed INTEGER NOT NULL DEFAULT 0,
  recursive_crawl_allowed INTEGER NOT NULL DEFAULT 0,
  browser_automation_allowed INTEGER NOT NULL DEFAULT 0,
  action_auto_create_allowed INTEGER NOT NULL DEFAULT 0,
  action_auto_approve_allowed INTEGER NOT NULL DEFAULT 0,
  action_auto_execute_allowed INTEGER NOT NULL DEFAULT 0,
  model_call_allowed INTEGER NOT NULL DEFAULT 0,
  agent_activation_allowed INTEGER NOT NULL DEFAULT 0,
  file_move_allowed INTEGER NOT NULL DEFAULT 0,
  file_delete_allowed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS steel_thread_feed_runs (
  feed_run_id TEXT PRIMARY KEY,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  source_count INTEGER NOT NULL DEFAULT 0,
  enabled_source_count INTEGER NOT NULL DEFAULT 0,
  fetched_item_count INTEGER NOT NULL DEFAULT 0,
  local_packet_count INTEGER NOT NULL DEFAULT 0,
  rejected_count INTEGER NOT NULL DEFAULT 0,
  dry_run INTEGER NOT NULL DEFAULT 0,
  network_fetch_attempted INTEGER NOT NULL DEFAULT 0,
  broad_web_crawl_allowed INTEGER NOT NULL DEFAULT 0,
  recursive_crawl_allowed INTEGER NOT NULL DEFAULT 0,
  browser_automation_allowed INTEGER NOT NULL DEFAULT 0,
  model_call_allowed INTEGER NOT NULL DEFAULT 0,
  action_created INTEGER NOT NULL DEFAULT 0,
  notification_sent INTEGER NOT NULL DEFAULT 0,
  notes TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS steel_thread_feed_items (
  item_id TEXT PRIMARY KEY,
  feed_run_id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  item_title TEXT NOT NULL,
  item_summary TEXT NOT NULL,
  item_url TEXT,
  item_hash TEXT NOT NULL,
  item_excerpt TEXT NOT NULL,
  source_kind TEXT NOT NULL,
  verification_status TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  raw_body_stored INTEGER NOT NULL DEFAULT 0,
  source_claim INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  FOREIGN KEY (source_id) REFERENCES steel_thread_source_registry(source_id)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS steel_thread_feed_item_classifications (
  classification_id TEXT PRIMARY KEY,
  item_id TEXT NOT NULL,
  signal_id TEXT NOT NULL,
  pattern_category TEXT NOT NULL,
  relevance_score TEXT NOT NULL,
  confidence TEXT NOT NULL,
  openclaw_alignment TEXT NOT NULL,
  recommendation TEXT NOT NULL,
  recommended_lane TEXT NOT NULL,
  routed_agent TEXT NOT NULL,
  reviewer TEXT,
  safety_reviewer TEXT,
  work_board_card_id TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (item_id) REFERENCES steel_thread_feed_items(item_id),
  FOREIGN KEY (signal_id) REFERENCES steel_thread_signals(signal_id)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS steel_thread_feed_fetch_receipts (
  fetch_receipt_id TEXT PRIMARY KEY,
  feed_run_id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  status TEXT NOT NULL,
  item_count INTEGER NOT NULL DEFAULT 0,
  message TEXT NOT NULL,
  network_used INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS steel_thread_feed_rejections (
  rejection_id TEXT PRIMARY KEY,
  feed_run_id TEXT NOT NULL,
  source_id TEXT,
  source_ref TEXT,
  rejection_reason TEXT NOT NULL,
  network_used INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
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
        "CREATE INDEX IF NOT EXISTS idx_steel_thread_sources_enabled ON steel_thread_source_registry(enabled)",
        "CREATE INDEX IF NOT EXISTS idx_steel_thread_feed_items_source ON steel_thread_feed_items(source_id)",
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


def seed_steel_thread_source_registry(
    db_path: str | Path | None = None,
    *,
    now: str | None = None,
) -> dict[str, int]:
    path = init_steel_thread_schema(db_path)
    observed_at = now or utc_now()
    conn = sqlite3.connect(path)
    try:
        for seed in steel_thread_source_seeds():
            _validate_source_seed(seed)
            conn.execute(
                """
INSERT INTO steel_thread_source_registry (
  source_id, source_name, source_kind, url, local_path, owner_scope,
  trust_level, enabled, fetch_policy, max_items_per_run, rate_limit_seconds,
  broad_web_crawl_allowed, recursive_crawl_allowed, browser_automation_allowed,
  action_auto_create_allowed, action_auto_approve_allowed,
  action_auto_execute_allowed, model_call_allowed, agent_activation_allowed,
  file_move_allowed, file_delete_allowed, created_at, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, ?, ?)
ON CONFLICT(source_id) DO UPDATE SET
  source_name = excluded.source_name,
  source_kind = excluded.source_kind,
  owner_scope = excluded.owner_scope,
  trust_level = excluded.trust_level,
  fetch_policy = excluded.fetch_policy,
  broad_web_crawl_allowed = 0,
  recursive_crawl_allowed = 0,
  browser_automation_allowed = 0,
  action_auto_create_allowed = 0,
  action_auto_approve_allowed = 0,
  action_auto_execute_allowed = 0,
  model_call_allowed = 0,
  agent_activation_allowed = 0,
  file_move_allowed = 0,
  file_delete_allowed = 0,
  updated_at = excluded.updated_at
""".strip(),
                (
                    seed.source_id,
                    seed.source_name,
                    seed.source_kind,
                    seed.url,
                    seed.local_path,
                    seed.owner_scope,
                    seed.trust_level,
                    1 if seed.enabled else 0,
                    seed.fetch_policy,
                    seed.max_items_per_run,
                    seed.rate_limit_seconds,
                    observed_at,
                    observed_at,
                ),
            )
        conn.commit()
        total = conn.execute("SELECT COUNT(*) FROM steel_thread_source_registry").fetchone()[0]
        enabled = conn.execute(
            "SELECT COUNT(*) FROM steel_thread_source_registry WHERE enabled = 1"
        ).fetchone()[0]
        return {"source_count": int(total), "enabled_source_count": int(enabled)}
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
    seed_steel_thread_source_registry(path)
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


def _path_has_no_go_hint(path: str | Path) -> bool:
    lowered = str(path).lower()
    parts = {part.lower() for part in Path(str(path)).parts}
    return bool(parts & NO_GO_PATH_PARTS) or any(part in lowered for part in NO_GO_PATH_PARTS)


def _safe_local_packet_dir(repo_root: str | Path, local_path: str | None) -> Path:
    if not local_path:
        raise ValueError("local packet source is missing local_path")
    root = Path(repo_root).resolve()
    candidate = (root / local_path).resolve()
    allowed = (root / DEFAULT_LOCAL_PACKET_ROOT).resolve()
    if candidate != allowed:
        raise ValueError("local packet source path is not the approved frontier packet directory")
    return candidate


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_frontier_packet(path: Path) -> dict[str, str]:
    if path.stat().st_size > MAX_LOCAL_PACKET_BYTES:
        raise ValueError("local packet exceeds max bounded size")
    if _path_has_no_go_hint(path):
        raise ValueError("local packet path crosses no-go boundary")
    text = path.read_text(encoding="utf-8")
    metadata: dict[str, str] = {}
    body = text
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        end_index = None
        for index, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                end_index = index
                break
        if end_index is not None:
            for line in lines[1:end_index]:
                if ":" in line:
                    key, value = line.split(":", 1)
                    metadata[key.strip()] = value.strip().strip('"')
            body = "\n".join(lines[end_index + 1 :])
    title = metadata.get("title")
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            title = title or stripped.lstrip("#").strip()
            break
    metadata["title"] = title or path.stem.replace("_", " ").title()
    metadata["body"] = body
    metadata["summary"] = metadata.get("summary") or _bounded_excerpt(body, 240)
    metadata["hash"] = _sha256_text(text)
    return metadata


def _bounded_excerpt(text: str, limit: int = MAX_ITEM_EXCERPT_CHARS) -> str:
    normalized = " ".join(str(text or "").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def _is_url_fetch_allowed(row: sqlite3.Row) -> bool:
    url = row["url"]
    if not url:
        return False
    parsed = urllib.parse.urlparse(url)
    return (
        row["enabled"] == 1
        and row["source_kind"] in URL_SOURCE_KINDS
        and parsed.scheme == "https"
        and bool(parsed.netloc)
    )


def _fetch_url_items(row: sqlite3.Row) -> list[dict[str, str]]:
    """Fetch bounded RSS/Atom-like items from an explicitly enabled source URL."""
    if not _is_url_fetch_allowed(row):
        raise ValueError("source URL is not explicitly enabled and allowlisted")
    request = urllib.request.Request(
        row["url"],
        headers={"User-Agent": "OpenClaw-SteelThreadRadar/0.1 metadata-only"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = response.read(MAX_FEED_FETCH_BYTES + 1)
    if len(payload) > MAX_FEED_FETCH_BYTES:
        raise ValueError("feed response exceeds bounded fetch size")
    root = ET.fromstring(payload)
    items: list[dict[str, str]] = []
    namespaces = {"atom": "http://www.w3.org/2005/Atom"}
    rss_items = root.findall(".//item")
    atom_items = root.findall(".//atom:entry", namespaces)
    for item in rss_items[: int(row["max_items_per_run"])]:
        title = item.findtext("title") or "Untitled feed item"
        link = item.findtext("link") or row["url"]
        summary = item.findtext("description") or item.findtext("summary") or ""
        items.append(
            {
                "title": html.unescape(_bounded_excerpt(title, 180)),
                "summary": html.unescape(_bounded_excerpt(summary, 400)),
                "url": link,
                "excerpt": html.unescape(_bounded_excerpt(summary, MAX_ITEM_EXCERPT_CHARS)),
                "hash": _sha256_text(f"{title}\n{link}\n{summary}"),
                "verification_status": "external_source_claim_unverified_until_review",
            }
        )
    for entry in atom_items[: int(row["max_items_per_run"]) - len(items)]:
        title = entry.findtext("atom:title", default="Untitled feed item", namespaces=namespaces)
        summary = entry.findtext("atom:summary", default="", namespaces=namespaces)
        link = row["url"]
        link_node = entry.find("atom:link", namespaces)
        if link_node is not None and link_node.get("href"):
            link = link_node.get("href", row["url"])
        items.append(
            {
                "title": html.unescape(_bounded_excerpt(title, 180)),
                "summary": html.unescape(_bounded_excerpt(summary, 400)),
                "url": link,
                "excerpt": html.unescape(_bounded_excerpt(summary, MAX_ITEM_EXCERPT_CHARS)),
                "hash": _sha256_text(f"{title}\n{link}\n{summary}"),
                "verification_status": "external_source_claim_unverified_until_review",
            }
        )
    return items


def _classify_feed_item(
    *,
    title: str,
    summary: str,
    excerpt: str,
    repo_root: str | Path,
) -> dict[str, str]:
    text = f"{title} {summary} {excerpt}".lower()
    work_board_exists = _surface_status(repo_root, "work_board.py") == "present"
    if any(term in text for term in ("kanban", "work board", "orchestration board", "agent task board", "symphony", "hermes")):
        return {
            "pattern_name": "local agent work board",
            "pattern_category": "agent_orchestration",
            "relevance_score": "high",
            "confidence": "medium",
            "openclaw_alignment": "aligned",
            "recommendation": "adapt",
            "recommended_lane": (
                "Mission Control Work Board Read-Only Surface v0"
                if work_board_exists
                else "OpenClaw Work Board v0"
            ),
            "next_safe_move": (
                "Use the local Work Board as the control plane and expose it read-only in Mission Control; "
                "do not add cloud dependency, arbitrary execution, or approval bypass."
            ),
            "routed_agent": "chief",
            "reviewer": "hermes",
            "safety_reviewer": "guardian",
            "risk_notes": "Operator/external pattern is unverified; adapt locally, approval-gated, and metadata-only.",
        }
    if any(term in text for term in ("context pack", "source pack", "upload-ready", "chatgpt project", "claude project")):
        return {
            "pattern_name": "focused source pack export",
            "pattern_category": "workflow_automation",
            "relevance_score": "high",
            "confidence": "high",
            "openclaw_alignment": "aligned",
            "recommendation": "adopt",
            "recommended_lane": "External AI Context Packager follow-up UX",
            "next_safe_move": "Keep context packs local/export-only; do not automate uploads.",
            "routed_agent": "chief",
            "reviewer": "hermes",
            "safety_reviewer": "guardian",
            "risk_notes": "Avoid private/no-go content and external upload automation.",
        }
    if any(term in text for term in ("runtime", "model backend", "agent activation", "container runtime", "local model runner")):
        return {
            "pattern_name": "model/runtime frontier signal",
            "pattern_category": "model_runtime",
            "relevance_score": "medium",
            "confidence": "low",
            "openclaw_alignment": "watch",
            "recommendation": "watch",
            "recommended_lane": "Agent Runtime Readiness follow-up review",
            "next_safe_move": "Ask Guardian/Hermes for a boundary review before any runtime lane.",
            "routed_agent": "guardian",
            "reviewer": "hermes",
            "safety_reviewer": "guardian",
            "risk_notes": "Runtime/model signals are future-gated; no model calls or activation from Steel Thread.",
        }
    return {
        "pattern_name": "frontier signal requiring review",
        "pattern_category": "unknown",
        "relevance_score": "medium",
        "confidence": "low",
        "openclaw_alignment": "unknown_review",
        "recommendation": "needs_review",
        "recommended_lane": "Steel Thread Review v0",
        "next_safe_move": "Review the source claim manually and decide whether it maps to an existing OpenClaw surface.",
        "routed_agent": "hermes",
        "reviewer": "hermes",
        "safety_reviewer": "guardian",
        "risk_notes": "Insufficient deterministic evidence for adoption.",
    }


def _insert_feed_signal(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    item_id: str,
    item: dict[str, str],
    source: sqlite3.Row,
    classification: dict[str, str],
    repo_root: str | Path,
    now: str,
) -> str:
    signal_id = _row_id("steel_signal_feed", item_id)
    seed = SteelThreadSeed(
        signal_id=signal_id,
        title=item["title"],
        short_summary=item["summary"] or item["excerpt"],
        source_kind="local_research_packet"
        if source["source_kind"] == "local_research_packet"
        else "external_research_summary",
        source_ref=item.get("url") or source["local_path"] or source["source_id"],
        evidence_basis=(
            f"{item['verification_status']}; source={source['source_id']}; "
            "bounded title/summary/excerpt only; raw body not stored."
        ),
        pattern_name=classification["pattern_name"],
        pattern_category=classification["pattern_category"],
        openclaw_mapping=("Steel Thread", "Work Board", "Chief", "Hermes", "Guardian", "Mission Control"),
        relevance_score=classification["relevance_score"],
        confidence=classification["confidence"],
        openclaw_alignment=classification["openclaw_alignment"],
        recommendation=classification["recommendation"],
        recommended_lane=classification["recommended_lane"],
        next_safe_move=classification["next_safe_move"],
        routed_agent=classification["routed_agent"],
        risk_notes=classification["risk_notes"],
        watchlist_note=classification["risk_notes"]
        if classification["recommendation"] in {"watch", "defer", "needs_review"}
        else None,
    )
    _insert_seed(conn, seed=seed, run_id=run_id, repo_root=repo_root, now=now)
    conn.execute(
        """
INSERT OR REPLACE INTO steel_thread_feed_item_classifications (
  classification_id, item_id, signal_id, pattern_category, relevance_score,
  confidence, openclaw_alignment, recommendation, recommended_lane,
  routed_agent, reviewer, safety_reviewer, work_board_card_id, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
""".strip(),
        (
            _row_id("steel_feed_class", item_id, signal_id),
            item_id,
            signal_id,
            classification["pattern_category"],
            classification["relevance_score"],
            classification["confidence"],
            classification["openclaw_alignment"],
            classification["recommendation"],
            classification["recommended_lane"],
            classification["routed_agent"],
            classification["reviewer"],
            classification["safety_reviewer"],
            now,
        ),
    )
    return signal_id


def _insert_feed_item(
    conn: sqlite3.Connection,
    *,
    feed_run_id: str,
    source: sqlite3.Row,
    item: dict[str, str],
    repo_root: str | Path,
    now: str,
) -> str:
    item_id = _row_id("steel_feed_item", source["source_id"], item.get("url") or item["title"], item["hash"])
    conn.execute(
        """
INSERT OR REPLACE INTO steel_thread_feed_items (
  item_id, feed_run_id, source_id, item_title, item_summary, item_url,
  item_hash, item_excerpt, source_kind, verification_status, observed_at,
  raw_body_stored, source_claim, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 1, ?)
""".strip(),
        (
            item_id,
            feed_run_id,
            source["source_id"],
            item["title"],
            item["summary"],
            item.get("url"),
            item["hash"],
            item["excerpt"],
            source["source_kind"],
            item["verification_status"],
            now,
            now,
        ),
    )
    classification = _classify_feed_item(
        title=item["title"],
        summary=item["summary"],
        excerpt=item["excerpt"],
        repo_root=repo_root,
    )
    _insert_feed_signal(
        conn,
        run_id=feed_run_id,
        item_id=item_id,
        item=item,
        source=source,
        classification=classification,
        repo_root=repo_root,
        now=now,
    )
    return item_id


def _local_packet_items(source: sqlite3.Row, repo_root: str | Path) -> list[dict[str, str]]:
    packet_dir = _safe_local_packet_dir(repo_root, source["local_path"])
    if not packet_dir.exists():
        return []
    items: list[dict[str, str]] = []
    for path in sorted(packet_dir.glob("*.md"))[: int(source["max_items_per_run"])]:
        metadata = _parse_frontier_packet(path)
        relative = path.resolve().relative_to(Path(repo_root).resolve()).as_posix()
        items.append(
            {
                "title": metadata["title"],
                "summary": metadata["summary"],
                "url": relative,
                "excerpt": _bounded_excerpt(metadata["body"]),
                "hash": metadata["hash"],
                "verification_status": metadata.get("verification_status")
                or "unverified_external_claim",
            }
        )
    return items


def fetch_steel_thread_sources(
    *,
    db_path: str | Path | None = None,
    repo_root: str | Path = ROOT,
    run_id: str | None = None,
    dry_run: bool = False,
) -> SteelThreadFetchResult:
    """Fetch/ingest explicitly approved Steel Thread sources.

    Default configured sources only ingest local packets and manual metadata.
    Disabled URL sources are never fetched.
    """
    path = init_steel_thread_schema(db_path)
    seed_steel_thread_source_registry(path)
    now = utc_now()
    feed_run_id = run_id or _row_id("steel_feed_run", now)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    fetched_item_count = 0
    local_packet_count = 0
    rejected_count = 0
    network_fetch_attempted = False
    try:
        sources = conn.execute(
            "SELECT * FROM steel_thread_source_registry ORDER BY source_id"
        ).fetchall()
        enabled_sources = [row for row in sources if row["enabled"] == 1]
        if not dry_run:
            conn.execute(
                """
INSERT OR REPLACE INTO steel_thread_runs (
  run_id, radar_version, created_at, completed_at, signal_count,
  high_relevance_count, autonomous_update_allowed, action_auto_create_allowed,
  action_auto_approve_allowed, action_auto_execute_allowed, external_api_allowed,
  web_crawl_allowed, model_call_allowed, agent_activation_allowed,
  network_authority, file_move_allowed, file_delete_allowed, notes
) VALUES (?, ?, ?, NULL, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, ?)
ON CONFLICT(run_id) DO UPDATE SET
  completed_at = NULL,
  autonomous_update_allowed = 0,
  action_auto_create_allowed = 0,
  action_auto_approve_allowed = 0,
  action_auto_execute_allowed = 0,
  external_api_allowed = 0,
  web_crawl_allowed = 0,
  model_call_allowed = 0,
  agent_activation_allowed = 0,
  network_authority = 0,
  file_move_allowed = 0,
  file_delete_allowed = 0,
  notes = excluded.notes
""".strip(),
                (
                    feed_run_id,
                    STEEL_THREAD_VERSION,
                    now,
                    "Approved-source intake run; recommendations remain metadata-only.",
                ),
            )
            conn.execute(
                """
INSERT OR REPLACE INTO steel_thread_feed_runs (
  feed_run_id, started_at, completed_at, source_count, enabled_source_count,
  fetched_item_count, local_packet_count, rejected_count, dry_run,
  network_fetch_attempted, broad_web_crawl_allowed, recursive_crawl_allowed,
  browser_automation_allowed, model_call_allowed, action_created,
  notification_sent, notes
) VALUES (?, ?, NULL, ?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, ?)
""".strip(),
                (
                    feed_run_id,
                    now,
                    len(sources),
                    len(enabled_sources),
                    "Approved-source intake run; no broad crawl, recursion, browser automation, model calls, actions, or notifications.",
                ),
            )
        for source in enabled_sources:
            items: list[dict[str, str]] = []
            status = "skipped"
            message = "manual metadata source; no fetch needed"
            network_used = False
            try:
                if source["source_kind"] == "manual_seed":
                    items = []
                elif source["source_kind"] == "local_research_packet":
                    items = _local_packet_items(source, repo_root)
                    local_packet_count += len(items)
                    status = "ok"
                    message = f"ingested {len(items)} local packet item(s)"
                elif source["source_kind"] in URL_SOURCE_KINDS:
                    if not _is_url_fetch_allowed(source):
                        raise ValueError("source URL is not explicitly enabled and allowlisted")
                    network_fetch_attempted = True
                    network_used = True
                    items = _fetch_url_items(source)
                    status = "ok"
                    message = f"fetched {len(items)} bounded feed item(s)"
                else:
                    raise ValueError(f"unsupported source kind: {source['source_kind']}")
                if not dry_run:
                    for item in items[: int(source["max_items_per_run"])]:
                        _insert_feed_item(conn, feed_run_id=feed_run_id, source=source, item=item, repo_root=repo_root, now=now)
                    conn.execute(
                        """
INSERT OR REPLACE INTO steel_thread_feed_fetch_receipts (
  fetch_receipt_id, feed_run_id, source_id, status, item_count,
  message, network_used, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""".strip(),
                        (
                            _row_id("steel_fetch_receipt", feed_run_id, source["source_id"]),
                            feed_run_id,
                            source["source_id"],
                            status,
                            len(items),
                            message,
                            1 if network_used else 0,
                            now,
                        ),
                    )
                fetched_item_count += len(items)
            except (ValueError, OSError, UnicodeDecodeError, ET.ParseError, urllib.error.URLError) as exc:
                rejected_count += 1
                if not dry_run:
                    conn.execute(
                        """
INSERT INTO steel_thread_feed_rejections (
  rejection_id, feed_run_id, source_id, source_ref, rejection_reason,
  network_used, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?)
""".strip(),
                        (
                            _row_id("steel_feed_reject", feed_run_id, source["source_id"], str(exc)),
                            feed_run_id,
                            source["source_id"],
                            source["url"] or source["local_path"],
                            str(exc),
                            1 if network_used else 0,
                            now,
                        ),
                    )
        if not dry_run:
            signal_count = conn.execute("SELECT COUNT(*) AS count FROM steel_thread_signals").fetchone()["count"]
            high_relevance_count = conn.execute(
                "SELECT COUNT(*) AS count FROM steel_thread_signals WHERE relevance_score = 'high'"
            ).fetchone()["count"]
            conn.execute(
                """
UPDATE steel_thread_runs
SET signal_count = ?, high_relevance_count = ?, completed_at = ?
WHERE run_id = ?
""".strip(),
                (signal_count, high_relevance_count, now, feed_run_id),
            )
            conn.execute(
                """
UPDATE steel_thread_feed_runs
SET completed_at = ?, fetched_item_count = ?, local_packet_count = ?,
    rejected_count = ?, network_fetch_attempted = ?
WHERE feed_run_id = ?
""".strip(),
                (
                    now,
                    fetched_item_count,
                    local_packet_count,
                    rejected_count,
                    1 if network_fetch_attempted else 0,
                    feed_run_id,
                ),
            )
            conn.commit()
        return SteelThreadFetchResult(
            run_id=feed_run_id,
            db_path=path,
            source_count=len(sources),
            enabled_source_count=len(enabled_sources),
            fetched_item_count=fetched_item_count,
            local_packet_count=local_packet_count,
            rejected_count=rejected_count,
            network_fetch_attempted=network_fetch_attempted,
            dry_run=dry_run,
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
            "source_registry_count": conn.execute(
                "SELECT COUNT(*) AS count FROM steel_thread_source_registry"
            ).fetchone()["count"],
            "enabled_source_count": conn.execute(
                "SELECT COUNT(*) AS count FROM steel_thread_source_registry WHERE enabled = 1"
            ).fetchone()["count"],
            "feed_item_count": conn.execute("SELECT COUNT(*) AS count FROM steel_thread_feed_items").fetchone()[
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


def _latest_feed_run(conn: sqlite3.Connection) -> dict[str, Any] | None:
    row = conn.execute(
        """
SELECT feed_run_id, completed_at, source_count, enabled_source_count,
       fetched_item_count, local_packet_count, rejected_count,
       network_fetch_attempted, dry_run
FROM steel_thread_feed_runs
ORDER BY completed_at DESC, feed_run_id DESC
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
        sources = _dict_rows(
            conn,
            """
SELECT source_id, source_name, source_kind, url, local_path, owner_scope,
       trust_level, enabled, fetch_policy, max_items_per_run,
       broad_web_crawl_allowed, recursive_crawl_allowed,
       browser_automation_allowed
FROM steel_thread_source_registry
ORDER BY source_id
""".strip(),
        )
        feed_items = _dict_rows(
            conn,
            """
SELECT i.item_id, i.source_id, i.item_title, i.item_summary, i.item_url,
       i.source_kind, i.verification_status, i.raw_body_stored,
       c.signal_id, c.pattern_category, c.relevance_score,
       c.openclaw_alignment, c.recommendation, c.recommended_lane,
       c.routed_agent, c.reviewer, c.safety_reviewer, c.work_board_card_id
FROM steel_thread_feed_items i
LEFT JOIN steel_thread_feed_item_classifications c ON c.item_id = i.item_id
ORDER BY i.created_at DESC, i.item_id DESC
LIMIT 20
""".strip(),
        )
        total_feed_item_count = conn.execute(
            "SELECT COUNT(*) AS count FROM steel_thread_feed_items"
        ).fetchone()["count"]
        recommendation_counts = Counter(signal["recommendation"] for signal in signals)
        category_counts = Counter(signal["pattern_category"] for signal in signals)
        enabled_sources = [source for source in sources if source["enabled"]]
        url_sources_enabled = [
            source for source in enabled_sources if source["source_kind"] in URL_SOURCE_KINDS and source["url"]
        ]
        return {
            "schema_version": READ_MODEL_VERSION,
            "generated_at": utc_now(),
            "source_ledger_path": str(path),
            "signal_count": len(signals),
            "high_relevance_count": sum(1 for signal in signals if signal["relevance_score"] == "high"),
            "source_registry_count": len(sources),
            "enabled_source_count": len(enabled_sources),
            "url_source_enabled_count": len(url_sources_enabled),
            "feed_item_count": total_feed_item_count,
            "latest_feed_run": _latest_feed_run(conn),
            "recommendations_by_status": dict(sorted(recommendation_counts.items())),
            "pattern_categories": dict(sorted(category_counts.items())),
            "top_recommendations": recommendations[:8],
            "watchlist_items": watchlist_items,
            "recommended_next_lanes": [row["recommended_lane"] for row in recommendations[:8]],
            "latest_signal": _latest_signal(conn),
            "signals": signals,
            "sources": sources,
            "latest_feed_items": feed_items,
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
        f"- Sources registered: {payload['source_registry_count']}",
        f"- Sources enabled: {payload['enabled_source_count']}",
        f"- Feed/local packet items: {payload['feed_item_count']}",
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
    lines.extend(["", "## Source Intake"])
    for source in payload["sources"]:
        enabled = "enabled" if source["enabled"] else "disabled"
        target = source["local_path"] or source["url"] or "metadata-only"
        lines.append(f"- {source['source_id']} ({source['source_kind']}, {enabled}): {target}")
    if payload["latest_feed_run"]:
        latest = payload["latest_feed_run"]
        lines.append("")
        lines.append(
            f"Latest feed run: {latest['feed_run_id']} "
            f"items={latest['fetched_item_count']} local_packets={latest['local_packet_count']} "
            f"rejected={latest['rejected_count']} network={bool(latest['network_fetch_attempted'])}"
        )
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
            f"Sources: {payload['counts']['source_registry_count']}",
            f"Enabled sources: {payload['counts']['enabled_source_count']}",
            f"Feed/local packet items: {payload['counts']['feed_item_count']}",
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


def format_fetch_result(result: SteelThreadFetchResult) -> str:
    lines = [
        "Steel Thread Frontier Source Intake v0",
        "",
        f"Run: {result.run_id}",
        f"Ledger: `{result.db_path}`",
        f"Sources: {result.source_count}",
        f"Enabled sources: {result.enabled_source_count}",
        f"{'Items found' if result.dry_run else 'Items ingested'}: {result.fetched_item_count}",
        f"Local packets: {result.local_packet_count}",
        f"Rejected: {result.rejected_count}",
        f"Network fetch attempted: {str(result.network_fetch_attempted).lower()}",
        f"Dry run: {str(result.dry_run).lower()}",
        "",
        "Boundary:",
        "- Only enabled approved sources are considered; disabled URL sources are not fetched.",
        "- No broad crawl, recursion, browser automation, model calls, actions, notifications, approvals, or execution.",
    ]
    return "\n".join(lines)
