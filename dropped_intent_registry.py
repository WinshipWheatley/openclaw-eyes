"""Dropped Intent Registry v0 for OpenClaw.

This module records old unresolved or deferred operator directions as durable
metadata in the Business Ops ledger. It reads only safe OpenClaw surfaces,
stores short excerpts, and exports a bounded read-model. It does not notify the
operator, create actions, execute work, call models, or read no-go raw content.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from business_ops_ledger import DEFAULT_DB_PATH, init_business_ops_ledger
from intent_router import init_intent_router_schema


ROOT = Path(__file__).resolve().parent
DROPPED_INTENT_VERSION = "dropped_intent_registry_v0"
READ_MODEL_VERSION = "dropped_intents_read_model_v0"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
JSON_EXPORT_NAME = "dropped_intents.json"
OPERATOR_EXPORT_NAME = "dropped_intents_OPERATOR.md"
MAX_EXCERPT_CHARS = 220
MAX_SOURCE_BYTES = 250_000
MAX_GENERIC_CANDIDATES = 40

SOURCE_KINDS = {
    "markdown_doc",
    "generated_read_model",
    "context_packet",
    "intent_record",
    "project_capsule",
    "operator_note",
}

CURRENT_STATUSES = {
    "unresolved",
    "built",
    "deferred",
    "rejected",
    "superseded",
    "unknown_review",
}

STATUS_CONFIDENCE = {"high", "medium", "low"}

NO_AUTHORITY_FLAGS = {
    "notification_allowed": False,
    "autonomous_prompting_allowed": False,
    "action_auto_create_allowed": False,
    "action_auto_approve_allowed": False,
    "action_auto_execute_allowed": False,
    "agent_activation_allowed": False,
    "network_authority": False,
    "model_call_allowed": False,
    "raw_private_scan_allowed": False,
    "file_move_allowed": False,
    "file_delete_allowed": False,
}

INTENT_PHRASES = (
    "i want",
    "i would like",
    "eventually",
    "we should",
    "next lane",
    "future lane",
    "later",
    "do not forget",
    "bring this back",
    "should build",
    "needs to",
    "i need",
    "i want to be able to",
)

NO_GO_PATH_PARTS = (
    ".ssh",
    ".gnupg",
    ".google-secrets",
    ".private",
    "private",
    "secrets",
    "secret",
    "vault",
    "auth",
    "legal",
    "tax",
    "cpa",
    "polish_loop/tasks",
)


@dataclass(frozen=True)
class DroppedIntentSeed:
    key: str
    title: str
    short_summary: str
    terms: tuple[str, ...]
    original_text_excerpt: str
    world_hint: str
    agent_hint: str
    lane_hint: str
    intent_category: str
    suggested_next_question: str
    suggested_next_lane: str
    default_status: str
    default_confidence: str


@dataclass(frozen=True)
class SafeSource:
    source_kind: str
    source_path: str | None
    source_ref: str
    text: str
    source_hash: str
    first_observed_at: str | None = None


@dataclass(frozen=True)
class DroppedIntentBuildResult:
    run_id: str
    db_path: str
    total_count: int
    counts_by_status: dict[str, int]
    source_count: int


KNOWN_INTENT_SEEDS = (
    DroppedIntentSeed(
        key="legacy_github_repo_intake_live",
        title="Legacy GitHub Repo Intake v0.1",
        short_summary="Inspect older OpenClaw build material as a non-canonical legacy root before any merge or promotion.",
        terms=("legacy github", "legacy repo", "github_legacy_openclaw", "older build repo"),
        original_text_excerpt="Legacy GitHub Repo Intake v0.1 should inspect older build repo material as non-canonical.",
        world_hint="build",
        agent_hint="chief",
        lane_hint="system_orchestration",
        intent_category="legacy_repo_intake",
        suggested_next_question="Do you still want to inspect the older GitHub build as a non-canonical legacy root?",
        suggested_next_lane="Legacy GitHub Repo Intake v0.1",
        default_status="deferred",
        default_confidence="high",
    ),
    DroppedIntentSeed(
        key="project_capsule_real_template_workflow",
        title="Project Capsule v0.1 / Real Template Workflow",
        short_summary="Turn the synthetic demo capsule into a repeatable real-but-empty client/project starter workflow.",
        terms=("project capsule v0.1", "real template workflow", "real-but-empty", "client/project repos"),
        original_text_excerpt="Project Capsule v0.1 / Real Template Workflow should turn the synthetic capsule into a repeatable generator.",
        world_hint="business_development",
        agent_hint="chief",
        lane_hint="system_orchestration",
        intent_category="project_capsule_request",
        suggested_next_question="Do you want to promote the synthetic capsule generator into a real-but-empty project workflow next?",
        suggested_next_lane="Project Capsule v0.1 / Real Template Workflow",
        default_status="deferred",
        default_confidence="high",
    ),
    DroppedIntentSeed(
        key="mission_control_action_request_writing",
        title="Mission Control action request writing",
        short_summary="Let Mission Control draft strict Operator Action request JSON into the shared E-drive inbox.",
        terms=("mission control", "action request", "app-side request", "frontend request writer"),
        original_text_excerpt="Mission Control should eventually write action requests, while approval and execution stay backend-gated.",
        world_hint="operations",
        agent_hint="chief",
        lane_hint="system_orchestration",
        intent_category="operator_action_request",
        suggested_next_question="Do you want Mission Control to draft action request files into the E-drive inbox next?",
        suggested_next_lane="Mission Control Action Request Writer v0",
        default_status="unresolved",
        default_confidence="high",
    ),
    DroppedIntentSeed(
        key="recent_file_context_resolver",
        title="Recent File Context Resolver",
        short_summary="Resolve requests like 'that new file' against File Event Queue metadata without opening raw private content.",
        terms=("recent file", "that new file", "new logic file", "file event queue", "file context"),
        original_text_excerpt="Recent-file context resolution should connect operator wording to safe file-event metadata.",
        world_hint="operations",
        agent_hint="chief",
        lane_hint="system_orchestration",
        intent_category="file_context_request",
        suggested_next_question="Do you want to build recent-file context resolution over File Event Queue metadata?",
        suggested_next_lane="Recent File Context Resolver v0",
        default_status="unresolved",
        default_confidence="high",
    ),
    DroppedIntentSeed(
        key="telegram_chief_bridge",
        title="Telegram Chief Bridge",
        short_summary="Represent Telegram as a future intent source without wiring APIs, polling, sending, or approval bypass.",
        terms=("telegram", "chief", "metadata only", "no telegram api", "telegram-ready"),
        original_text_excerpt="Telegram-ready metadata exists, but no Telegram API or Chief bridge is wired.",
        world_hint="communications",
        agent_hint="chief",
        lane_hint="system_orchestration",
        intent_category="source_channel_bridge",
        suggested_next_question="Do you still want a Telegram-to-Chief intent source, and should it stay metadata-only first?",
        suggested_next_lane="Telegram Intent Source v0",
        default_status="deferred",
        default_confidence="high",
    ),
    DroppedIntentSeed(
        key="niles_producer_telegram_lane",
        title="Niles / Producer Telegram lane",
        short_summary="Clarify whether Producer remains an alias for Niles or needs a separate Telegram-facing lane later.",
        terms=("producer", "niles", "telegram", "alias", "creative file resolver"),
        original_text_excerpt="Producer and Creative File Resolver are aliases for Niles unless a future lane justifies a separate role.",
        world_hint="music_art",
        agent_hint="niles",
        lane_hint="music_art_production",
        intent_category="music_project_request",
        suggested_next_question="Should Producer stay an alias for Niles, or do you want a separate Telegram-facing creative lane later?",
        suggested_next_lane="Niles Producer Source Lane Review v0",
        default_status="deferred",
        default_confidence="medium",
    ),
    DroppedIntentSeed(
        key="automatic_file_watcher_daemon",
        title="Automatic file watcher daemon",
        short_summary="File Event Queue is snapshot-based; a daemon/background watcher remains explicitly future-gated.",
        terms=("file watcher", "watcher daemon", "daemon", "snapshot", "manual rescan"),
        original_text_excerpt="File Event Queue v0 records snapshots, not a daemon; automatic watching remains a future lane.",
        world_hint="operations",
        agent_hint="chief",
        lane_hint="system_orchestration",
        intent_category="file_event_request",
        suggested_next_question="Do you want to turn the snapshot File Event Queue into an approved watcher/daemon later?",
        suggested_next_lane="File Watcher Daemon v0",
        default_status="deferred",
        default_confidence="high",
    ),
    DroppedIntentSeed(
        key="mission_control_read_model_refresh",
        title="Mission Control read-model refresh",
        short_summary="Display newer generated read-model surfaces in Mission Control as read-only system layers.",
        terms=("mission control", "read-model refresh", "system layers", "surface substrate read models"),
        original_text_excerpt="Mission Control read-model refresh should surface newer read-models as read-only views.",
        world_hint="operations",
        agent_hint="chief",
        lane_hint="system_orchestration",
        intent_category="mission_control_read_model",
        suggested_next_question="Is the current read-only Mission Control read-model refresh sufficient, or should polish continue?",
        suggested_next_lane="Mission Control Polish v0.1",
        default_status="built",
        default_confidence="high",
    ),
    DroppedIntentSeed(
        key="report_bridge_sample_package",
        title="Report Bridge Sample Package v0",
        short_summary="Create and import one synthetic Report Bridge package through the E-drive inbox to prove the path end-to-end.",
        terms=("report bridge sample package", "synthetic package", "node_uplink", "inbox"),
        original_text_excerpt="Report Bridge Sample Package v0 should prove the E-drive package path without real client data.",
        world_hint="operations",
        agent_hint="report_bridge",
        lane_hint="node_report_intake",
        intent_category="report_bridge_request",
        suggested_next_question="Do you want to run a synthetic Report Bridge package through the E-drive inbox?",
        suggested_next_lane="Report Bridge Sample Package v0",
        default_status="deferred",
        default_confidence="medium",
    ),
)


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


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _short_excerpt(text: str) -> str:
    normalized = _normalize_text(text)
    if len(normalized) <= MAX_EXCERPT_CHARS:
        return normalized
    return normalized[: MAX_EXCERPT_CHARS - 3].rstrip() + "..."


def _lower_words(text: str) -> str:
    return re.sub(r"[^a-z0-9_]+", " ", text.lower()).strip()


def _path_is_no_go(path: str | Path) -> bool:
    lower = Path(path).as_posix().lower()
    return any(part in lower for part in NO_GO_PATH_PARTS)


def _safe_read_text(path: Path) -> str | None:
    if _path_is_no_go(path):
        return None
    try:
        if not path.is_file():
            return None
        if path.stat().st_size > MAX_SOURCE_BYTES:
            return None
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _sql_statements() -> tuple[str, ...]:
    return (
        """
CREATE TABLE IF NOT EXISTS dropped_intent_runs (
  run_id TEXT PRIMARY KEY,
  registry_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  source_count INTEGER NOT NULL DEFAULT 0,
  candidate_count INTEGER NOT NULL DEFAULT 0,
  unresolved_count INTEGER NOT NULL DEFAULT 0,
  built_count INTEGER NOT NULL DEFAULT 0,
  deferred_count INTEGER NOT NULL DEFAULT 0,
  rejected_count INTEGER NOT NULL DEFAULT 0,
  superseded_count INTEGER NOT NULL DEFAULT 0,
  unknown_review_count INTEGER NOT NULL DEFAULT 0,
  raw_body_stored INTEGER NOT NULL DEFAULT 0,
  notification_sent INTEGER NOT NULL DEFAULT 0,
  action_created INTEGER NOT NULL DEFAULT 0,
  execution_allowed INTEGER NOT NULL DEFAULT 0,
  agent_activation_allowed INTEGER NOT NULL DEFAULT 0,
  network_authority INTEGER NOT NULL DEFAULT 0,
  model_call_allowed INTEGER NOT NULL DEFAULT 0,
  raw_private_scan_allowed INTEGER NOT NULL DEFAULT 0,
  file_move_allowed INTEGER NOT NULL DEFAULT 0,
  file_delete_allowed INTEGER NOT NULL DEFAULT 0,
  notes TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS dropped_intents (
  dropped_intent_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  short_summary TEXT NOT NULL,
  original_text_excerpt TEXT NOT NULL,
  source_path TEXT,
  source_ref TEXT NOT NULL,
  source_kind TEXT NOT NULL,
  source_hash TEXT,
  first_observed_at TEXT,
  observed_in_run_id TEXT NOT NULL,
  world_hint TEXT NOT NULL,
  agent_hint TEXT NOT NULL,
  lane_hint TEXT NOT NULL,
  intent_category TEXT NOT NULL,
  current_status TEXT NOT NULL,
  status_confidence TEXT NOT NULL,
  evidence_basis TEXT NOT NULL,
  suggested_next_question TEXT NOT NULL,
  suggested_next_lane TEXT NOT NULL,
  approval_required INTEGER NOT NULL DEFAULT 1,
  action_created INTEGER NOT NULL DEFAULT 0,
  notification_sent INTEGER NOT NULL DEFAULT 0,
  raw_body_stored INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (observed_in_run_id) REFERENCES dropped_intent_runs(run_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS dropped_intent_evidence_links (
  evidence_link_id TEXT PRIMARY KEY,
  dropped_intent_id TEXT NOT NULL,
  source_kind TEXT NOT NULL,
  source_path TEXT,
  source_ref TEXT NOT NULL,
  source_hash TEXT,
  evidence_summary TEXT NOT NULL,
  raw_body_stored INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY (dropped_intent_id) REFERENCES dropped_intents(dropped_intent_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS dropped_intent_status_links (
  status_link_id TEXT PRIMARY KEY,
  dropped_intent_id TEXT NOT NULL,
  status_kind TEXT NOT NULL,
  status_source TEXT NOT NULL,
  status_summary TEXT NOT NULL,
  status_confidence TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (dropped_intent_id) REFERENCES dropped_intents(dropped_intent_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS dropped_intent_resolution_candidates (
  resolution_candidate_id TEXT PRIMARY KEY,
  dropped_intent_id TEXT NOT NULL,
  candidate_status TEXT NOT NULL,
  suggested_next_question TEXT NOT NULL,
  suggested_next_lane TEXT NOT NULL,
  approval_required INTEGER NOT NULL DEFAULT 1,
  action_created INTEGER NOT NULL DEFAULT 0,
  notification_sent INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  FOREIGN KEY (dropped_intent_id) REFERENCES dropped_intents(dropped_intent_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS dropped_intent_query_receipts (
  query_receipt_id TEXT PRIMARY KEY,
  report TEXT NOT NULL,
  run_id TEXT,
  item_count INTEGER NOT NULL,
  raw_body_stored INTEGER NOT NULL DEFAULT 0,
  notification_sent INTEGER NOT NULL DEFAULT 0,
  action_created INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
)
""".strip(),
        "CREATE INDEX IF NOT EXISTS idx_dropped_intents_status ON dropped_intents(current_status)",
        "CREATE INDEX IF NOT EXISTS idx_dropped_intents_agent ON dropped_intents(agent_hint)",
        "CREATE INDEX IF NOT EXISTS idx_dropped_intents_world ON dropped_intents(world_hint)",
        "CREATE INDEX IF NOT EXISTS idx_dropped_intents_category ON dropped_intents(intent_category)",
    )


def init_dropped_intent_schema(db_path: str | Path | None = None) -> str:
    path = str(db_path or DEFAULT_DB_PATH)
    parent = Path(path).parent
    if parent and not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)
    init_business_ops_ledger(path)
    init_intent_router_schema(path)
    conn = sqlite3.connect(path)
    try:
        for statement in _sql_statements():
            conn.execute(statement)
        conn.commit()
    finally:
        conn.close()
    return path


def dropped_intent_table_names(db_path: str | Path | None = None) -> tuple[str, ...]:
    path = init_dropped_intent_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            """
SELECT name
FROM sqlite_master
WHERE type = 'table' AND name LIKE 'dropped_intent%'
ORDER BY name
""".strip()
        ).fetchall()
        return tuple(row[0] for row in rows)
    finally:
        conn.close()


def _latest_markdown_run_id(conn: sqlite3.Connection) -> str | None:
    try:
        row = conn.execute(
            """
SELECT run_id
FROM markdown_atlas_runs
ORDER BY completed_at DESC, created_at DESC, run_id DESC
LIMIT 1
""".strip()
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    return row[0] if row else None


def _safe_markdown_paths_from_atlas(conn: sqlite3.Connection) -> list[str]:
    run_id = _latest_markdown_run_id(conn)
    if not run_id:
        return []
    try:
        rows = conn.execute(
            """
SELECT relative_path
FROM markdown_documents
WHERE run_id = ?
  AND sensitivity_status = 'normal_internal'
  AND retrieval_policy IN ('agent_retrievable', 'generated_surface_only')
  AND (
    relative_path LIKE 'docs/operations/%.md'
    OR relative_path LIKE 'generated/read_models/%.md'
    OR relative_path LIKE 'generated/read_models/%.txt'
    OR relative_path LIKE 'generated/context_packets/%.md'
  )
ORDER BY relative_path
""".strip(),
            (run_id,),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [row[0] for row in rows if not _path_is_no_go(row[0])]


def _source_kind_for_path(relative_path: str) -> str:
    if relative_path.startswith("generated/read_models/"):
        return "generated_read_model"
    if relative_path.startswith("generated/context_packets/"):
        return "context_packet"
    if relative_path.startswith("generated/project_capsules/"):
        return "project_capsule"
    return "markdown_doc"


def _collect_file_sources(repo_root: Path, conn: sqlite3.Connection) -> list[SafeSource]:
    sources: list[SafeSource] = []
    seen: set[str] = set()

    atlas_paths = _safe_markdown_paths_from_atlas(conn)
    if not atlas_paths:
        docs_root = repo_root / "docs" / "operations"
        if docs_root.is_dir():
            atlas_paths = sorted(
                path.relative_to(repo_root).as_posix()
                for path in docs_root.glob("*.md")
                if not _path_is_no_go(path.relative_to(repo_root))
            )

    for relative_path in atlas_paths:
        path = repo_root / relative_path
        text = _safe_read_text(path)
        if text is None:
            continue
        seen.add(relative_path)
        sources.append(
            SafeSource(
                source_kind=_source_kind_for_path(relative_path),
                source_path=relative_path,
                source_ref=relative_path,
                text=text,
                source_hash=_text_hash(text),
            )
        )

    for root, extensions, source_kind in (
        (repo_root / "generated" / "read_models", {".json", ".md", ".txt"}, "generated_read_model"),
        (repo_root / "generated" / "context_packets", {".json", ".md"}, "context_packet"),
    ):
        if not root.is_dir():
            continue
        for path in sorted(root.iterdir()):
            if path.name in {JSON_EXPORT_NAME, OPERATOR_EXPORT_NAME}:
                continue
            if path.suffix.lower() not in extensions:
                continue
            relative_path = path.relative_to(repo_root).as_posix()
            if relative_path in seen or _path_is_no_go(relative_path):
                continue
            text = _safe_read_text(path)
            if text is None:
                continue
            seen.add(relative_path)
            sources.append(
                SafeSource(
                    source_kind=source_kind,
                    source_path=relative_path,
                    source_ref=relative_path,
                    text=text,
                    source_hash=_text_hash(text),
                )
            )
    return sources


def _collect_intent_record_sources(conn: sqlite3.Connection) -> list[SafeSource]:
    try:
        rows = conn.execute(
            """
SELECT intent_id, intent_text_preview, next_safe_move, intent_category,
       routed_agent_id, world_hint, created_at
FROM intent_records
ORDER BY created_at DESC, intent_id DESC
LIMIT 100
""".strip()
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    sources: list[SafeSource] = []
    for row in rows:
        text = (
            f"{row['intent_text_preview']}\n"
            f"Category: {row['intent_category']}; agent={row['routed_agent_id']}; world={row['world_hint']}.\n"
            f"Next safe move: {row['next_safe_move']}"
        )
        sources.append(
            SafeSource(
                source_kind="intent_record",
                source_path=None,
                source_ref=row["intent_id"],
                text=text,
                source_hash=_text_hash(text),
                first_observed_at=row["created_at"],
            )
        )
    return sources


def collect_safe_sources(
    *,
    db_path: str | Path | None = None,
    repo_root: str | Path = ROOT,
) -> list[SafeSource]:
    path = init_dropped_intent_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        root = Path(repo_root)
        sources = _collect_file_sources(root, conn)
        sources.extend(_collect_intent_record_sources(conn))
        return sources
    finally:
        conn.close()


def _find_source_for_seed(seed: DroppedIntentSeed, sources: Iterable[SafeSource]) -> SafeSource | None:
    terms = tuple(term.lower() for term in seed.terms)
    best: tuple[int, SafeSource] | None = None
    for source in sources:
        lower = source.text.lower()
        score = sum(1 for term in terms if term in lower)
        if score == 0:
            continue
        if best is None or score > best[0]:
            best = (score, source)
    return best[1] if best else None


def _matching_excerpt(seed: DroppedIntentSeed, source: SafeSource | None) -> str:
    if not source:
        return seed.original_text_excerpt
    terms = tuple(term.lower() for term in seed.terms)
    for line in source.text.splitlines():
        line_lower = line.lower()
        if any(term in line_lower for term in terms):
            stripped = line.strip()
            if stripped:
                return _short_excerpt(stripped)
    return _short_excerpt(source.text)


def _repo_has(path: Path, relative_path: str) -> bool:
    return (path / relative_path).exists()


def _status_for_seed(seed: DroppedIntentSeed, repo_root: Path, sources: Iterable[SafeSource]) -> tuple[str, str, str]:
    source_text = "\n".join(source.text.lower() for source in sources)
    status = seed.default_status
    confidence = seed.default_confidence
    basis = "operator-seeded dropped-intent candidate with deterministic current-substrate check"

    if seed.key == "legacy_github_repo_intake_live":
        if _repo_has(repo_root, "legacy_repo_intake.py"):
            return (
                "deferred",
                "high",
                "Legacy intake placeholder/module exists, but live legacy repo import remains not imported/non-canonical.",
            )
    elif seed.key == "project_capsule_real_template_workflow":
        if _repo_has(repo_root, "project_capsule.py") and _repo_has(repo_root, "generated/project_capsules/demo_project_capsule_v0/capsule.json"):
            return (
                "deferred",
                "high",
                "Project Capsule v0 and synthetic template exist; real client/project generator remains a next-lane item.",
            )
    elif seed.key == "mission_control_action_request_writing":
        if "mission control remains read-only" in source_text or "no action buttons" in source_text:
            return (
                "unresolved",
                "high",
                "Backend Operator Action Inbox exists, but Mission Control remains read-only and app-side request writing is not built.",
            )
    elif seed.key == "recent_file_context_resolver":
        if _repo_has(repo_root, "file_event_queue.py"):
            return (
                "unresolved",
                "high",
                "File Event Queue exists, but resolving vague phrases like 'that new file' still requires a separate resolver.",
            )
    elif seed.key == "telegram_chief_bridge":
        if "no telegram api" in source_text or "telegram is represented" in source_text:
            return (
                "deferred",
                "high",
                "Telegram is represented as source metadata only; no Telegram API, polling, or sending is wired.",
            )
    elif seed.key == "niles_producer_telegram_lane":
        if "aliases for niles" in source_text or "producer" in source_text:
            return (
                "deferred",
                "medium",
                "Producer is currently an alias for Niles; a separate Telegram-facing lane is not justified or wired yet.",
            )
    elif seed.key == "automatic_file_watcher_daemon":
        if _repo_has(repo_root, "file_event_queue.py"):
            return (
                "deferred",
                "high",
                "File Event Queue v0 is snapshot-based and explicitly not a daemon.",
            )
    elif seed.key == "mission_control_read_model_refresh":
        if "mission control remains read-only" in source_text and "system layers" in source_text:
            return (
                "built",
                "high",
                "Mission Control read-only system layers were implemented; further work is polish, not the original missing feature.",
            )
    elif seed.key == "report_bridge_sample_package":
        if _repo_has(repo_root, "report_bridge.py"):
            return (
                "deferred",
                "medium",
                "Report Bridge exists, but no production/synthetic sample package import is recorded as the next proof step.",
            )

    return status, confidence, basis


def _generic_status_for_excerpt(excerpt: str) -> tuple[str, str, str]:
    lower = excerpt.lower()
    if "built" in lower or "complete" in lower or "exists" in lower:
        return "built", "medium", "excerpt contains built/existing status wording"
    if "deferred" in lower or "future lane" in lower or "later" in lower or "eventually" in lower:
        return "deferred", "medium", "excerpt contains deferred/future wording"
    if "superseded" in lower or "replaced" in lower:
        return "superseded", "medium", "excerpt contains superseded wording"
    if "reject" in lower:
        return "rejected", "medium", "excerpt contains rejection wording"
    if "we should" in lower or "should build" in lower or "i want" in lower or "needs to" in lower:
        return "unresolved", "low", "excerpt contains unresolved desire wording"
    return "unknown_review", "low", "generic intent candidate requires review"


def _generic_agent_world_category(excerpt: str) -> tuple[str, str, str, str]:
    lower = excerpt.lower()
    if "telegram" in lower or "message" in lower or "summary" in lower:
        return "cassandra", "operator_comms", "communications", "communication_summary_request"
    if "niles" in lower or "producer" in lower or "logic" in lower or "music" in lower:
        return "niles", "music_art_production", "music_art", "music_project_request"
    if "safe" in lower or "risk" in lower or "guardian" in lower or "secret" in lower:
        return "guardian", "safety_security", "security", "safety_review_request"
    if "report bridge" in lower or "node_uplink" in lower:
        return "report_bridge", "node_report_intake", "operations", "report_bridge_request"
    if "project capsule" in lower or "client" in lower:
        return "chief", "system_orchestration", "business_development", "project_capsule_request"
    return "chief", "system_orchestration", "operations", "unknown_review"


def _generic_title(excerpt: str) -> str:
    cleaned = re.sub(r"^[#*\-\s>`]+", "", excerpt).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if len(cleaned) <= 72:
        return cleaned or "Dropped intent candidate"
    return cleaned[:69].rstrip() + "..."


def _candidate_lines_from_source(source: SafeSource) -> list[str]:
    lines: list[str] = []
    for line in source.text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(('"', "{", "[", "}", "]")):
            continue
        lower = line.lower()
        if any(phrase in lower for phrase in INTENT_PHRASES):
            excerpt = _short_excerpt(line)
            if excerpt and len(excerpt) > 8:
                lines.append(excerpt)
    return lines


def _records_from_sources(
    *,
    sources: list[SafeSource],
    repo_root: Path,
    run_id: str,
    now: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seed_keys: set[str] = set()
    for seed in KNOWN_INTENT_SEEDS:
        source = _find_source_for_seed(seed, sources)
        status, confidence, basis = _status_for_seed(seed, repo_root, sources)
        excerpt = _matching_excerpt(seed, source)
        source_kind = source.source_kind if source else "operator_note"
        source_path = source.source_path if source else None
        source_ref = source.source_ref if source else f"{DROPPED_INTENT_VERSION}:{seed.key}"
        source_hash = source.source_hash if source else _text_hash(seed.original_text_excerpt)
        record = {
            "dropped_intent_id": _row_id("dropintent", seed.key),
            "title": seed.title,
            "short_summary": seed.short_summary,
            "original_text_excerpt": excerpt,
            "source_path": source_path,
            "source_ref": source_ref,
            "source_kind": source_kind,
            "source_hash": source_hash,
            "first_observed_at": source.first_observed_at if source else None,
            "observed_in_run_id": run_id,
            "world_hint": seed.world_hint,
            "agent_hint": seed.agent_hint,
            "lane_hint": seed.lane_hint,
            "intent_category": seed.intent_category,
            "current_status": status,
            "status_confidence": confidence,
            "evidence_basis": basis,
            "suggested_next_question": seed.suggested_next_question,
            "suggested_next_lane": seed.suggested_next_lane,
            "created_at": now,
            "updated_at": now,
        }
        records.append(record)
        seed_keys.add(seed.key)

    generic_count = 0
    seen_excerpts = {record["original_text_excerpt"].lower() for record in records}
    for source in sources:
        if source.source_kind not in {"markdown_doc", "context_packet", "intent_record"}:
            continue
        if source.source_kind == "context_packet" and not (source.source_path or "").endswith(".md"):
            continue
        for excerpt in _candidate_lines_from_source(source):
            if generic_count >= MAX_GENERIC_CANDIDATES:
                return records
            lower = excerpt.lower()
            if lower in seen_excerpts:
                continue
            if any(any(term in lower for term in seed.terms) for seed in KNOWN_INTENT_SEEDS):
                continue
            status, confidence, basis = _generic_status_for_excerpt(excerpt)
            agent, lane, world, category = _generic_agent_world_category(excerpt)
            title = _generic_title(excerpt)
            intent_id = _row_id("dropintent", "generic", source.source_ref, excerpt)
            records.append(
                {
                    "dropped_intent_id": intent_id,
                    "title": title,
                    "short_summary": f"Detected dropped-intent candidate from `{source.source_ref}`.",
                    "original_text_excerpt": excerpt,
                    "source_path": source.source_path,
                    "source_ref": source.source_ref,
                    "source_kind": source.source_kind,
                    "source_hash": source.source_hash,
                    "first_observed_at": source.first_observed_at,
                    "observed_in_run_id": run_id,
                    "world_hint": world,
                    "agent_hint": agent,
                    "lane_hint": lane,
                    "intent_category": category,
                    "current_status": status,
                    "status_confidence": confidence,
                    "evidence_basis": basis,
                    "suggested_next_question": f"Do you still want to pursue this thread: {title}",
                    "suggested_next_lane": "Operator Review",
                    "created_at": now,
                    "updated_at": now,
                }
            )
            seen_excerpts.add(lower)
            generic_count += 1
    return records


def _source_digest(sources: Iterable[SafeSource]) -> str:
    payload = [(source.source_kind, source.source_ref, source.source_hash) for source in sources]
    return hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()[:20]


def _insert_record(conn: sqlite3.Connection, record: dict[str, Any]) -> None:
    conn.execute(
        """
INSERT INTO dropped_intents (
  dropped_intent_id, title, short_summary, original_text_excerpt,
  source_path, source_ref, source_kind, source_hash, first_observed_at,
  observed_in_run_id, world_hint, agent_hint, lane_hint, intent_category,
  current_status, status_confidence, evidence_basis, suggested_next_question,
  suggested_next_lane, approval_required, action_created, notification_sent,
  raw_body_stored, created_at, updated_at
) VALUES (
  :dropped_intent_id, :title, :short_summary, :original_text_excerpt,
  :source_path, :source_ref, :source_kind, :source_hash, :first_observed_at,
  :observed_in_run_id, :world_hint, :agent_hint, :lane_hint, :intent_category,
  :current_status, :status_confidence, :evidence_basis, :suggested_next_question,
  :suggested_next_lane, 1, 0, 0, 0, :created_at, :updated_at
)
ON CONFLICT(dropped_intent_id) DO UPDATE SET
  title = excluded.title,
  short_summary = excluded.short_summary,
  original_text_excerpt = excluded.original_text_excerpt,
  source_path = excluded.source_path,
  source_ref = excluded.source_ref,
  source_kind = excluded.source_kind,
  source_hash = excluded.source_hash,
  first_observed_at = excluded.first_observed_at,
  observed_in_run_id = excluded.observed_in_run_id,
  world_hint = excluded.world_hint,
  agent_hint = excluded.agent_hint,
  lane_hint = excluded.lane_hint,
  intent_category = excluded.intent_category,
  current_status = excluded.current_status,
  status_confidence = excluded.status_confidence,
  evidence_basis = excluded.evidence_basis,
  suggested_next_question = excluded.suggested_next_question,
  suggested_next_lane = excluded.suggested_next_lane,
  approval_required = 1,
  action_created = 0,
  notification_sent = 0,
  raw_body_stored = 0,
  updated_at = excluded.updated_at
""".strip(),
        record,
    )
    now = record["updated_at"]
    conn.execute(
        """
INSERT INTO dropped_intent_evidence_links (
  evidence_link_id, dropped_intent_id, source_kind, source_path, source_ref,
  source_hash, evidence_summary, raw_body_stored, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
ON CONFLICT(evidence_link_id) DO UPDATE SET
  evidence_summary = excluded.evidence_summary,
  raw_body_stored = 0
""".strip(),
        (
            _row_id("dropev", record["dropped_intent_id"], record["source_ref"]),
            record["dropped_intent_id"],
            record["source_kind"],
            record["source_path"],
            record["source_ref"],
            record["source_hash"],
            record["original_text_excerpt"],
            now,
        ),
    )
    conn.execute(
        """
INSERT INTO dropped_intent_status_links (
  status_link_id, dropped_intent_id, status_kind, status_source,
  status_summary, status_confidence, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(status_link_id) DO UPDATE SET
  status_summary = excluded.status_summary,
  status_confidence = excluded.status_confidence
""".strip(),
        (
            _row_id("dropstatus", record["dropped_intent_id"], record["current_status"]),
            record["dropped_intent_id"],
            record["current_status"],
            "deterministic_registry_status_match",
            record["evidence_basis"],
            record["status_confidence"],
            now,
        ),
    )
    conn.execute(
        """
INSERT INTO dropped_intent_resolution_candidates (
  resolution_candidate_id, dropped_intent_id, candidate_status,
  suggested_next_question, suggested_next_lane, approval_required,
  action_created, notification_sent, created_at
) VALUES (?, ?, ?, ?, ?, 1, 0, 0, ?)
ON CONFLICT(resolution_candidate_id) DO UPDATE SET
  candidate_status = excluded.candidate_status,
  suggested_next_question = excluded.suggested_next_question,
  suggested_next_lane = excluded.suggested_next_lane,
  approval_required = 1,
  action_created = 0,
  notification_sent = 0
""".strip(),
        (
            _row_id("dropres", record["dropped_intent_id"]),
            record["dropped_intent_id"],
            record["current_status"],
            record["suggested_next_question"],
            record["suggested_next_lane"],
            now,
        ),
    )


def build_dropped_intent_registry(
    *,
    db_path: str | Path | None = None,
    repo_root: str | Path = ROOT,
    run_id: str | None = None,
) -> DroppedIntentBuildResult:
    path = init_dropped_intent_schema(db_path)
    sources = collect_safe_sources(db_path=path, repo_root=repo_root)
    resolved_run_id = run_id or f"dropped_intents_{_source_digest(sources)}"
    now = utc_now()
    root = Path(repo_root)
    records = _records_from_sources(sources=sources, repo_root=root, run_id=resolved_run_id, now=now)
    counts = Counter(record["current_status"] for record in records)

    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            """
INSERT INTO dropped_intent_runs (
  run_id, registry_version, created_at, completed_at, source_count,
  candidate_count, unresolved_count, built_count, deferred_count,
  rejected_count, superseded_count, unknown_review_count, raw_body_stored,
  notification_sent, action_created, execution_allowed, agent_activation_allowed,
  network_authority, model_call_allowed, raw_private_scan_allowed,
  file_move_allowed, file_delete_allowed, notes
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, ?)
ON CONFLICT(run_id) DO UPDATE SET
  completed_at = excluded.completed_at,
  source_count = excluded.source_count,
  candidate_count = excluded.candidate_count,
  unresolved_count = excluded.unresolved_count,
  built_count = excluded.built_count,
  deferred_count = excluded.deferred_count,
  rejected_count = excluded.rejected_count,
  superseded_count = excluded.superseded_count,
  unknown_review_count = excluded.unknown_review_count,
  raw_body_stored = 0,
  notification_sent = 0,
  action_created = 0,
  execution_allowed = 0,
  agent_activation_allowed = 0,
  network_authority = 0,
  model_call_allowed = 0,
  raw_private_scan_allowed = 0,
  file_move_allowed = 0,
  file_delete_allowed = 0,
  notes = excluded.notes
""".strip(),
            (
                resolved_run_id,
                DROPPED_INTENT_VERSION,
                now,
                now,
                len(sources),
                len(records),
                counts.get("unresolved", 0),
                counts.get("built", 0),
                counts.get("deferred", 0),
                counts.get("rejected", 0),
                counts.get("superseded", 0),
                counts.get("unknown_review", 0),
                "Dropped-intent registry build; safe excerpts only, no notifications, no action creation, no execution.",
            ),
        )
        conn.execute("DELETE FROM dropped_intents WHERE observed_in_run_id = ?", (resolved_run_id,))
        for record in records:
            _insert_record(conn, record)
        conn.commit()
    finally:
        conn.close()

    return DroppedIntentBuildResult(
        run_id=resolved_run_id,
        db_path=path,
        total_count=len(records),
        counts_by_status=dict(sorted(counts.items())),
        source_count=len(sources),
    )


REPORT_SECTIONS = {
    "summary",
    "unresolved",
    "built",
    "deferred",
    "superseded",
    "unknown-review",
}


def _dict_rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _latest_run(conn: sqlite3.Connection) -> dict[str, Any] | None:
    row = conn.execute(
        """
SELECT *
FROM dropped_intent_runs
ORDER BY completed_at DESC, created_at DESC, run_id DESC
LIMIT 1
""".strip()
    ).fetchone()
    return dict(row) if row else None


def _item_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "dropped_intent_id": row["dropped_intent_id"],
        "title": row["title"],
        "short_summary": row["short_summary"],
        "original_text_excerpt": row["original_text_excerpt"],
        "source_path": row["source_path"],
        "source_ref": row["source_ref"],
        "source_kind": row["source_kind"],
        "world_hint": row["world_hint"],
        "agent_hint": row["agent_hint"],
        "lane_hint": row["lane_hint"],
        "intent_category": row["intent_category"],
        "current_status": row["current_status"],
        "status_confidence": row["status_confidence"],
        "evidence_basis": row["evidence_basis"],
        "suggested_next_question": row["suggested_next_question"],
        "suggested_next_lane": row["suggested_next_lane"],
        "approval_required": bool(row["approval_required"]),
        "action_created": bool(row["action_created"]),
        "notification_sent": bool(row["notification_sent"]),
        "raw_body_stored": bool(row["raw_body_stored"]),
        "updated_at": row["updated_at"],
    }


def build_dropped_intent_report(
    *,
    db_path: str | Path | None = None,
    report: str = "summary",
    agent: str | None = None,
    world: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    if report not in REPORT_SECTIONS:
        raise ValueError(f"unknown dropped intent report: {report}")
    path = init_dropped_intent_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        latest = _latest_run(conn)
        run_filter = ""
        run_params: tuple[Any, ...] = ()
        if latest:
            run_filter = "WHERE observed_in_run_id = ?"
            run_params = (latest["run_id"],)
        rows = _dict_rows(
            conn,
            f"""
SELECT *
FROM dropped_intents
{run_filter}
ORDER BY
  CASE current_status
    WHEN 'unresolved' THEN 0
    WHEN 'unknown_review' THEN 1
    WHEN 'deferred' THEN 2
    WHEN 'superseded' THEN 3
    WHEN 'built' THEN 4
    ELSE 5
  END,
  title
""".strip(),
            run_params,
        )
        if agent:
            normalized_agent = agent.strip().lower().replace(" ", "_")
            rows = [row for row in rows if row["agent_hint"] == normalized_agent]
        if world:
            normalized_world = world.strip().lower().replace(" ", "_")
            rows = [row for row in rows if row["world_hint"] == normalized_world]
        if report != "summary":
            status = "unknown_review" if report == "unknown-review" else report
            rows = [row for row in rows if row["current_status"] == status]

        all_rows = _dict_rows(conn, f"SELECT * FROM dropped_intents {run_filter}".strip(), run_params)
        status_counts = Counter(row["current_status"] for row in all_rows)
        agent_counts = Counter(row["agent_hint"] for row in all_rows)
        world_counts = Counter(row["world_hint"] for row in all_rows)
        category_counts = Counter(row["intent_category"] for row in all_rows)
        now = utc_now()
        receipt_id = _row_id("dropquery", report, agent or "", world or "", latest["run_id"] if latest else "")
        conn.execute(
            """
INSERT INTO dropped_intent_query_receipts (
  query_receipt_id, report, run_id, item_count, raw_body_stored,
  notification_sent, action_created, created_at
) VALUES (?, ?, ?, ?, 0, 0, 0, ?)
ON CONFLICT(query_receipt_id) DO UPDATE SET
  item_count = excluded.item_count,
  raw_body_stored = 0,
  notification_sent = 0,
  action_created = 0
""".strip(),
            (receipt_id, report, latest["run_id"] if latest else None, len(rows), now),
        )
        conn.commit()
        return {
            "registry_version": DROPPED_INTENT_VERSION,
            "status": "ok",
            "report": report,
            "db_path": _display_path(path),
            "latest_run": latest,
            "counts": {
                "total": len(all_rows),
                "by_status": dict(sorted(status_counts.items())),
                "by_agent": dict(sorted(agent_counts.items())),
                "by_world": dict(sorted(world_counts.items())),
                "by_category": dict(sorted(category_counts.items())),
            },
            "items": [_item_summary(row) for row in rows[:limit]],
            "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        }
    finally:
        conn.close()


def _counts_line(counts: dict[str, int]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items())) or "none"


def format_dropped_intent_report(payload: dict[str, Any]) -> str:
    counts = payload["counts"]
    lines = [
        f"Dropped Intent Registry v0 - {payload['report']}",
        "",
        f"Total: {counts['total']}",
        f"By status: {_counts_line(counts['by_status'])}",
        f"By agent: {_counts_line(counts['by_agent'])}",
        f"By world: {_counts_line(counts['by_world'])}",
        f"By category: {_counts_line(counts['by_category'])}",
        "",
        "Items:",
    ]
    for item in payload.get("items") or []:
        lines.append(
            f"- `{item['dropped_intent_id']}`: {item['current_status']} "
            f"({item['status_confidence']}) - {item['title']} "
            f"[{item['agent_hint']}/{item['world_hint']}]"
        )
        lines.append(f"  Next question: {item['suggested_next_question']}")
    if not payload.get("items"):
        lines.append("- none")
    lines.extend(
        [
            "",
            "Boundary:",
            "- Registry only; no notification, action creation, approval, execution, model call, agent activation, or file move/delete.",
            "- Excerpts are short safe snippets; full raw document bodies are not stored.",
        ]
    )
    return "\n".join(lines)


def build_dropped_intents_read_model(
    *,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    report = build_dropped_intent_report(db_path=db_path, report="summary", limit=1000)
    items = report["items"]
    unresolved = [item for item in items if item["current_status"] == "unresolved"]
    built = [item for item in items if item["current_status"] == "built"]
    deferred = [item for item in items if item["current_status"] == "deferred"]
    unknown_review = [item for item in items if item["current_status"] == "unknown_review"]
    latest_run = report.get("latest_run")
    generated_at = latest_run["completed_at"] if latest_run else "not_available_no_dropped_intent_run"
    return {
        "schema_version": READ_MODEL_VERSION,
        "read_model_version": READ_MODEL_VERSION,
        "mode": "dropped_intent_registry_posture_only",
        "generated_at": generated_at,
        "source_ledger_path": report["db_path"],
        "source_ledger_namespace": "dropped_intent_*",
        "latest_run_id": latest_run["run_id"] if latest_run else None,
        "total_count": report["counts"]["total"],
        "unresolved_count": report["counts"]["by_status"].get("unresolved", 0),
        "built_count": report["counts"]["by_status"].get("built", 0),
        "deferred_count": report["counts"]["by_status"].get("deferred", 0),
        "superseded_count": report["counts"]["by_status"].get("superseded", 0),
        "unknown_review_count": report["counts"]["by_status"].get("unknown_review", 0),
        "counts_by_status": report["counts"]["by_status"],
        "counts_by_agent": report["counts"]["by_agent"],
        "counts_by_world": report["counts"]["by_world"],
        "counts_by_category": report["counts"]["by_category"],
        "top_unresolved_items": unresolved[:10],
        "built_items": built[:10],
        "deferred_items": deferred[:10],
        "unknown_review_items": unknown_review[:10],
        "suggested_next_questions": [
            item["suggested_next_question"] for item in unresolved[:10] + deferred[:5]
        ],
        "source_policy": {
            "safe_sources": [
                "docs/operations Markdown classified safe by Markdown Knowledge Atlas",
                "generated/read_models JSON/Markdown/text",
                "generated/context_packets JSON/Markdown",
                "intent_router metadata rows",
            ],
            "raw_body_stored": False,
            "private_no_go_raw_scan": False,
        },
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
        "claims_not_made": [
            "autonomous_reminder",
            "operator_notification",
            "action_request_creation",
            "approval",
            "execution",
            "agent_activation",
            "model_call",
            "private_raw_scan",
            "file_reorganization",
        ],
    }


def format_dropped_intents_read_model(read_model: dict[str, Any]) -> str:
    lines = [
        "# Dropped Intent Registry Read-Model v0",
        "",
        "What this is:",
        "- A generated read-model over `dropped_intent_*` SQLite rows.",
        "- It surfaces old unresolved, deferred, built, or unknown-review directions so Chief can later ask whether they still matter.",
        "",
        "What this is not:",
        "- It is not autonomous prompting, notification, action creation, approval, execution, model calling, agent activation, or file reorganization.",
        "",
        "Summary:",
        f"- Total dropped-intent candidates: {read_model['total_count']}.",
        f"- Unresolved: {read_model['unresolved_count']}.",
        f"- Deferred: {read_model['deferred_count']}.",
        f"- Built: {read_model['built_count']}.",
        f"- Superseded: {read_model['superseded_count']}.",
        f"- Unknown review: {read_model['unknown_review_count']}.",
        f"- By agent: {_counts_line(read_model['counts_by_agent'])}.",
        f"- By world: {_counts_line(read_model['counts_by_world'])}.",
        "",
        "Top unresolved:",
    ]
    unresolved = read_model.get("top_unresolved_items") or []
    if unresolved:
        for item in unresolved[:8]:
            lines.append(f"- {item['title']}: {item['suggested_next_question']}")
    else:
        lines.append("- none")
    lines.extend(["", "Deferred / built samples:"])
    samples = (read_model.get("deferred_items") or [])[:5] + (read_model.get("built_items") or [])[:5]
    if samples:
        for item in samples[:8]:
            lines.append(f"- {item['current_status']}: {item['title']}")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "Authority boundary:",
            "- notification_allowed=false; autonomous_prompting_allowed=false.",
            "- action_auto_create_allowed=false; action_auto_approve_allowed=false; action_auto_execute_allowed=false.",
            "- agent_activation_allowed=false; network_authority=false; model_call_allowed=false.",
            "- raw_private_scan_allowed=false; file_move_allowed=false; file_delete_allowed=false.",
            "",
            "Next safe move:",
            "- Surface this read-model as Chief planning context; ask before turning any item into a lane or action request.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_dropped_intents_read_model(
    *,
    db_path: str | Path | None = None,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
) -> dict[str, Any]:
    root = _export_root_path(export_root)
    root.mkdir(parents=True, exist_ok=True)
    read_model = build_dropped_intents_read_model(db_path=db_path)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(read_model), encoding="utf-8")
    operator_path.write_text(format_dropped_intents_read_model(read_model), encoding="utf-8")
    return {
        "export_version": READ_MODEL_VERSION,
        "json_path": _display_path(json_path),
        "operator_path": _display_path(operator_path),
        "total_count": read_model["total_count"],
        "unresolved_count": read_model["unresolved_count"],
        "built_count": read_model["built_count"],
        "deferred_count": read_model["deferred_count"],
        "unknown_review_count": read_model["unknown_review_count"],
        **NO_AUTHORITY_FLAGS,
    }


def format_build_result(result: DroppedIntentBuildResult) -> str:
    return "\n".join(
        [
            "Dropped Intent Registry v0",
            "",
            f"Run: `{result.run_id}`",
            f"Sources inspected: {result.source_count}",
            f"Candidates recorded: {result.total_count}",
            f"Counts by status: {_counts_line(result.counts_by_status)}",
            "",
            "Boundary:",
            "- Registry/read-model only; no notifications, action creation, approvals, execution, model calls, agents, or file operations.",
        ]
    )


__all__ = [
    "DROPPED_INTENT_VERSION",
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "READ_MODEL_VERSION",
    "REPORT_SECTIONS",
    "SOURCE_KINDS",
    "build_dropped_intent_registry",
    "build_dropped_intent_report",
    "build_dropped_intents_read_model",
    "collect_safe_sources",
    "dropped_intent_table_names",
    "export_dropped_intents_read_model",
    "format_build_result",
    "format_dropped_intent_report",
    "format_dropped_intents_read_model",
    "init_dropped_intent_schema",
    "stable_json",
]
