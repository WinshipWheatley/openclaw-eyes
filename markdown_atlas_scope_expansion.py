"""Markdown Atlas Scope Expansion v0.

This read-model audits Markdown Atlas coverage and proposes a safe,
metadata-only root expansion posture. It does not scan broad private folders,
read Markdown bodies, move files, create vectors, invoke models, or grant any
runtime authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_LEDGER_PATH = Path(".openclaw/business_ops/ledger.sqlite")

SCHEMA_VERSION = "markdown_atlas_scope_expansion_v0"
READ_MODEL_ID = "markdown_atlas_scope_expansion"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"

ROOT_SCOPE_STATUSES = (
    "CURRENTLY_COVERED",
    "CANDIDATE_METADATA_ONLY",
    "REQUIRES_OPERATOR_APPROVAL",
    "BLOCKED_PRIVATE",
    "BLOCKED_SYSTEM",
    "BLOCKED_C_DRIVE",
    "UNKNOWN_FAIL_CLOSED",
)

RECOMMENDATION_OPTIONS = (
    "NO_RUN_NEEDED_CURRENT_ATLAS_SUFFICIENT",
    "RUN_METADATA_ONLY_ON_EXISTING_REGISTERED_ROOTS",
    "ADD_APPROVED_REPO_ROOTS_THEN_METADATA_ONLY",
    "ASK_OPERATOR_FOR_ROOTS_FIRST",
    "DEFER_UNTIL_SECURITY_DELTA",
    "UNKNOWN_FAIL_CLOSED",
)

GAP_IDS = (
    "repo_a_known_markdown",
    "repo_b_reference_markdown",
    "mac_app_markdown",
    "handoff_markdown",
    "old_prompt_markdown",
    "doctrine_markdown",
    "generated_operator_markdown",
    "personal_notes_unknown",
    "external_drive_unknown",
    "desktop_downloads_unknown",
)

AUTHORITY_BOUNDARY = {
    "metadata_only_posture": True,
    "broad_raw_markdown_body_ingestion_allowed": False,
    "broad_private_filesystem_scan_allowed": False,
    "private_root_approval_by_default": False,
    "c_drive_scan_allowed": False,
    "file_move_allowed": False,
    "file_delete_allowed": False,
    "file_rename_allowed": False,
    "file_reorganization_allowed": False,
    "vector_index_creation_allowed": False,
    "ai_semantic_review_allowed_now": False,
    "truth_promotion_allowed": False,
    "mission_control_app_mutation_allowed": False,
    "mac_sync_import_allowed": False,
    "network_operation_allowed": False,
    "git_push_pull_fetch_allowed": False,
    "model_api_execution_allowed": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "runtime_dispatch_allowed": False,
    "queue_autonomy_allowed": False,
    "credential_account_access_allowed": False,
}

OPERATOR_QUESTIONS = (
    "Which roots should be considered part of Winship's Markdown universe?",
    "Are Mac Desktop, Documents, and Downloads included or excluded?",
    "Are external drives included or excluded?",
    "Is Repo B Markdown reference-only?",
    "Should old prompts be preserved as history, candidate doctrine, or residue?",
    "Which Markdown folders are sensitive/private?",
    "Should generated read-model/operator Markdown be excluded from human-authored Markdown analysis?",
)


@dataclass(frozen=True)
class MarkdownRootScopeRecord:
    root_path: str
    current_status: str
    reason: str
    allowed_indexing: str
    body_ingestion_allowed: bool
    operator_approval_required: bool
    next_safe_move: str
    root_id: str | None = None
    root_kind: str | None = None
    source: str = "scope_plan"


@dataclass(frozen=True)
class MarkdownUniverseGapRecord:
    gap_id: str
    description: str
    known_or_inferred: str
    current_coverage_status: str
    safe_next_step: str
    requires_operator_root_approval: bool
    body_ingestion_allowed: bool
    semantic_review_allowed_now: bool
    promotion_policy: str


@dataclass(frozen=True)
class MarkdownAtlasScopeExpansionExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    sqlite_present: bool
    markdown_documents_count: int
    corpus_roots_count: int
    recommended_next_run: str
    action_authority_granted: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _resolve_repo_path(repo_root: str | Path, path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return Path(repo_root) / candidate


def _connect_readonly(db_path: Path) -> sqlite3.Connection | None:
    if not db_path.exists():
        return None
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _safe_count(conn: sqlite3.Connection | None, table_name: str) -> int:
    if conn is None or not _table_exists(conn, table_name):
        return 0
    return int(conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


def _registered_roots(conn: sqlite3.Connection | None) -> list[dict[str, Any]]:
    if conn is None or not _table_exists(conn, "corpus_roots"):
        return []
    rows = conn.execute(
        """
SELECT root_id, absolute_root, root_kind, host_kind, owner_scope, status, root_label
FROM corpus_roots
ORDER BY root_id
""".strip()
    ).fetchall()
    return [dict(row) for row in rows]


def _latest_markdown_source_roots(conn: sqlite3.Connection | None) -> tuple[set[str], str | None]:
    if conn is None or not _table_exists(conn, "markdown_atlas_runs"):
        return set(), None
    row = conn.execute(
        """
SELECT run_id, source_corpus_runs_json
FROM markdown_atlas_runs
ORDER BY completed_at DESC, created_at DESC, run_id DESC
LIMIT 1
""".strip()
    ).fetchone()
    if row is None:
        return set(), None
    try:
        source_runs = json.loads(row["source_corpus_runs_json"]).get("corpus_runs", [])
    except (TypeError, json.JSONDecodeError):
        source_runs = []
    return {item.get("root_id", "") for item in source_runs if item.get("root_id")}, row["run_id"]


def _generated_markdown_read_models(repo_root: Path) -> list[str]:
    root = repo_root / DEFAULT_EXPORT_ROOT
    if not root.exists() or not root.is_dir():
        return []
    terrain_terms = ("markdown", "corpus", "terrain", "atlas", "evidence")
    names: list[str] = []
    for path in root.iterdir():
        if path.is_file() and any(term in path.name.lower() for term in terrain_terms):
            names.append(path.name)
    return sorted(names)


def _current_coverage(repo_root: Path, conn: sqlite3.Connection | None, db_path: Path) -> dict[str, Any]:
    generated = _generated_markdown_read_models(repo_root)
    return {
        "sqlite_present": conn is not None,
        "ledger_path": db_path.as_posix(),
        "corpus_roots_count": _safe_count(conn, "corpus_roots"),
        "corpus_paths_count": _safe_count(conn, "corpus_paths"),
        "corpus_path_labels_count": _safe_count(conn, "corpus_path_labels"),
        "markdown_atlas_run_count": _safe_count(conn, "markdown_atlas_runs"),
        "markdown_documents_count": _safe_count(conn, "markdown_documents"),
        "markdown_classifications_count": _safe_count(conn, "markdown_document_classifications"),
        "markdown_links_count": _safe_count(conn, "markdown_document_links"),
        "reorg_candidates_count": _safe_count(conn, "markdown_document_reorg_candidates"),
        "supersession_count": _safe_count(conn, "markdown_document_supersession"),
        "evidence_sources_count": _safe_count(conn, "markdown_evidence_sources"),
        "evidence_items_count": _safe_count(conn, "markdown_evidence_items"),
        "known_generated_read_models_related_to_markdown_terrain": generated,
        "coverage_status": (
            "METADATA_ONLY_REGISTERED_ROOT_COVERAGE_PRESENT"
            if conn is not None
            else "NO_SQLITE_LEDGER_PRESENT_FAIL_CLOSED"
        ),
    }


def _registered_root_scope_record(root: dict[str, Any], covered_root_ids: set[str]) -> MarkdownRootScopeRecord:
    root_id = root.get("root_id") or "unknown"
    root_path = root.get("absolute_root") or "unknown"
    status = root.get("status") or "unknown"
    root_kind = root.get("root_kind") or "unknown"
    if root_id in covered_root_ids:
        return MarkdownRootScopeRecord(
            root_id=root_id,
            root_kind=root_kind,
            root_path=root_path,
            current_status="CURRENTLY_COVERED",
            reason="Registered corpus root included in the latest Markdown Atlas source run.",
            allowed_indexing="existing_metadata_only_path_classification",
            body_ingestion_allowed=False,
            operator_approval_required=False,
            next_safe_move="Re-run metadata-only Atlas on existing registered roots if a refresh is needed.",
            source="corpus_roots",
        )
    if status == "future_placeholder":
        return MarkdownRootScopeRecord(
            root_id=root_id,
            root_kind=root_kind,
            root_path=root_path,
            current_status="REQUIRES_OPERATOR_APPROVAL",
            reason="Registered as a placeholder, not as an indexed Markdown source.",
            allowed_indexing="none_until_explicit_root_allowlist",
            body_ingestion_allowed=False,
            operator_approval_required=True,
            next_safe_move="Ask operator whether this root belongs in the Markdown universe before any metadata run.",
            source="corpus_roots",
        )
    return MarkdownRootScopeRecord(
        root_id=root_id,
        root_kind=root_kind,
        root_path=root_path,
        current_status="UNKNOWN_FAIL_CLOSED",
        reason="Registered root exists but is not part of the latest Markdown Atlas source set.",
        allowed_indexing="none_until_reconciled",
        body_ingestion_allowed=False,
        operator_approval_required=True,
        next_safe_move="Reconcile root status before any expansion run.",
        source="corpus_roots",
    )


def _root_scope_plan(repo_root: Path, conn: sqlite3.Connection | None) -> list[dict[str, Any]]:
    roots = _registered_roots(conn)
    covered_root_ids, _ = _latest_markdown_source_roots(conn)
    records = [_registered_root_scope_record(root, covered_root_ids) for root in roots]
    known_registered_paths = {record.root_path for record in records}

    e_drive_openclaw = Path("/mnt/e/openclaw")
    if e_drive_openclaw.exists() and e_drive_openclaw.as_posix() not in known_registered_paths:
        records.append(
            MarkdownRootScopeRecord(
                root_id="pc_e_drive_openclaw_candidate",
                root_kind="known_openclaw_shuttle_or_mirror_root",
                root_path=e_drive_openclaw.as_posix(),
                current_status="CANDIDATE_METADATA_ONLY",
                reason="Specific known OpenClaw E-drive path exists, but it is not registered in current corpus roots.",
                allowed_indexing="metadata_only_after_explicit_root_allowlist",
                body_ingestion_allowed=False,
                operator_approval_required=True,
                next_safe_move="Ask operator whether this exact root should be added to the corpus root allowlist.",
            )
        )

    records.extend(
        [
            MarkdownRootScopeRecord(
                root_id="broad_operator_home_blocked",
                root_kind="broad_private_root",
                root_path="operator_home_wide",
                current_status="BLOCKED_PRIVATE",
                reason="Whole home folders are too broad and may contain private unrelated material.",
                allowed_indexing="none",
                body_ingestion_allowed=False,
                operator_approval_required=True,
                next_safe_move="Require explicit narrow subfolder approval before metadata indexing.",
            ),
            MarkdownRootScopeRecord(
                root_id="mac_desktop_documents_downloads_blocked",
                root_kind="mac_personal_surface",
                root_path="mac_desktop_documents_downloads",
                current_status="REQUIRES_OPERATOR_APPROVAL",
                reason="Mac personal folders require explicit operator root approval and Mac-side manifest handling.",
                allowed_indexing="none_until_operator_approved_manifest",
                body_ingestion_allowed=False,
                operator_approval_required=True,
                next_safe_move="Ask operator whether these surfaces are included or excluded.",
            ),
            MarkdownRootScopeRecord(
                root_id="windows_c_drive_blocked",
                root_kind="windows_system_drive",
                root_path="windows_c_drive_mount",
                current_status="BLOCKED_C_DRIVE",
                reason="C-drive indexing is blocked in this lane.",
                allowed_indexing="none",
                body_ingestion_allowed=False,
                operator_approval_required=True,
                next_safe_move="Do not scan; require a separate explicit approval path if ever reconsidered.",
            ),
            MarkdownRootScopeRecord(
                root_id="system_roots_blocked",
                root_kind="system_root",
                root_path="system_roots_wide",
                current_status="BLOCKED_SYSTEM",
                reason="System-wide roots are unrelated to the Markdown Atlas scope and too broad.",
                allowed_indexing="none",
                body_ingestion_allowed=False,
                operator_approval_required=True,
                next_safe_move="Keep blocked.",
            ),
        ]
    )
    return [asdict(record) for record in records]


def _markdown_universe_gap_model() -> list[dict[str, Any]]:
    gap_specs = {
        "repo_a_known_markdown": (
            "Repo A Markdown already visible through registered corpus/Markdown Atlas metadata.",
            "known",
            "PARTIALLY_COVERED_BY_REGISTERED_ROOTS",
            "Refresh metadata-only Atlas on existing registered roots.",
            False,
            "Do not promote as truth without source-card/proof review.",
        ),
        "repo_b_reference_markdown": (
            "Repo B Markdown may exist as reference terrain but is outside this lane.",
            "inferred",
            "NOT_COVERED_FAIL_CLOSED",
            "Require explicit Repo B root approval and reference-only policy.",
            True,
            "Reference-only until security delta and operator approval.",
        ),
        "mac_app_markdown": (
            "Mac app Markdown is represented only through imported manifest metadata.",
            "known",
            "COVERED_AS_IMPORTED_METADATA_ONLY_WHEN_REGISTERED",
            "Keep Mac-side body access blocked; use manifest/root receipts only.",
            True,
            "App docs remain metadata until explicit Mac-side approval.",
        ),
        "handoff_markdown": (
            "Handoff Markdown may contain operational memory and stale instructions.",
            "known_or_inferred",
            "PARTIALLY_COVERED_METADATA_ONLY",
            "Classify by path metadata first; do not treat as current doctrine.",
            False,
            "Candidate memory/proof only after reconciliation.",
        ),
        "old_prompt_markdown": (
            "Old prompts are useful history but can conflict with current law.",
            "known_or_inferred",
            "PARTIALLY_COVERED_METADATA_ONLY",
            "Label as history/candidate doctrine/residue before semantic review.",
            False,
            "Never promote stale prompts without proof and operator review.",
        ),
        "doctrine_markdown": (
            "Doctrine Markdown may be canonical, stale, superseded, or duplicate.",
            "known",
            "PARTIALLY_COVERED_METADATA_ONLY",
            "Use current runtime law and receipts as promotion gates.",
            False,
            "Canonical only after deterministic source-card/security review.",
        ),
        "generated_operator_markdown": (
            "Generated read-model/operator Markdown is machine output, not human-authored doctrine.",
            "known",
            "COVERED_AS_GENERATED_OUTPUT_METADATA",
            "Exclude from human-authored Markdown analysis unless specifically requested.",
            False,
            "Generated-surface-only; do not mine as personal memory.",
        ),
        "personal_notes_unknown": (
            "Personal notes may exist outside approved roots.",
            "inferred",
            "UNKNOWN_FAIL_CLOSED",
            "Ask operator for explicit narrow roots and sensitivity boundaries.",
            True,
            "Blocked until root approval; answers become memory candidates, not proof.",
        ),
        "external_drive_unknown": (
            "External-drive Markdown may exist but is not approved by this lane.",
            "inferred",
            "UNKNOWN_FAIL_CLOSED",
            "Ask operator for exact root allowlist before metadata indexing.",
            True,
            "Blocked until exact root approval and metadata-only policy.",
        ),
        "desktop_downloads_unknown": (
            "Desktop/Downloads Markdown may include private or transient files.",
            "inferred",
            "UNKNOWN_FAIL_CLOSED",
            "Ask whether these areas are included or excluded.",
            True,
            "Blocked unless explicitly scoped.",
        ),
    }
    records = []
    for gap_id in GAP_IDS:
        description, known, coverage, safe_step, requires_approval, policy = gap_specs[gap_id]
        records.append(
            MarkdownUniverseGapRecord(
                gap_id=gap_id,
                description=description,
                known_or_inferred=known,
                current_coverage_status=coverage,
                safe_next_step=safe_step,
                requires_operator_root_approval=requires_approval,
                body_ingestion_allowed=False,
                semantic_review_allowed_now=False,
                promotion_policy=policy,
            )
        )
    return [asdict(record) for record in records]


def _recommended_next_expansion(root_scope_plan: list[dict[str, Any]]) -> dict[str, Any]:
    existing_root_ids = [
        record["root_id"]
        for record in root_scope_plan
        if record["current_status"] == "CURRENTLY_COVERED" and record.get("source") == "corpus_roots"
    ]
    candidate_roots = [
        record["root_path"]
        for record in root_scope_plan
        if record["current_status"] == "CANDIDATE_METADATA_ONLY"
    ]
    return {
        "recommendation": "RUN_METADATA_ONLY_ON_EXISTING_REGISTERED_ROOTS",
        "why": "It refreshes the already-approved metadata surface before adding broader roots.",
        "include_root_ids": existing_root_ids,
        "do_not_include_without_operator_approval": candidate_roots
        + ["operator_home_wide", "mac_desktop_documents_downloads", "windows_c_drive_mount"],
        "allowed_indexing": "path_metadata_filenames_extensions_timestamps_sizes_existing_corpus_metadata_only",
        "body_ingestion_allowed": False,
        "private_or_broad_root_scan_allowed": False,
        "vector_index_creation_allowed": False,
        "semantic_review_allowed_now": False,
        "next_safe_move": "Run metadata-only on existing registered roots; ask one root-allowlist question before adding any new root.",
    }


def _future_ai_judgment_policy() -> dict[str, Any]:
    return {
        "allowed_later_only_after_metadata_classification": [
            "summarize selected allowlisted docs",
            "classify canonical vs stale vs residue",
            "detect duplicate doctrine",
            "recommend source-card promotion",
            "recommend stable-map summary",
            "recommend archive/reorg candidates without moving files",
        ],
        "blocked_now": [
            "broad body summarization",
            "turning old notes into truth",
            "moving/deleting files",
            "creating vector memory from all docs",
            "using private notes without approval",
        ],
        "promotion_rule": "AI judgment can recommend after metadata classification, but cannot promote, move, delete, or claim truth.",
        "operator_answers_become": "memory_candidates_not_proof",
    }


def build_markdown_atlas_scope_expansion(
    *,
    repo_root: str | Path = ROOT,
    db_path: str | Path = DEFAULT_LEDGER_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    repo = Path(repo_root)
    ledger_path = _resolve_repo_path(repo, db_path)
    conn = _connect_readonly(ledger_path)
    try:
        current_coverage = _current_coverage(repo, conn, ledger_path)
        root_scope_plan = _root_scope_plan(repo, conn)
        gap_model = _markdown_universe_gap_model()
        recommendation = _recommended_next_expansion(root_scope_plan)
        latest_roots, latest_markdown_run_id = _latest_markdown_source_roots(conn)
    finally:
        if conn is not None:
            conn.close()

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at or utc_now(),
        "contract_status": "metadata_only_scope_expansion_plan",
        "core_doctrine": {
            "planning_lane_only": True,
            "broad_markdown_body_reading_allowed": False,
            "private_directory_scan_allowed": False,
            "path_metadata_only": True,
            "operator_answers_are_memory_candidates_not_proof": True,
            "old_markdown_is_not_promoted_as_truth": True,
        },
        "current_markdown_atlas_coverage": current_coverage,
        "markdown_root_scope_plan": root_scope_plan,
        "markdown_universe_gap_model": gap_model,
        "recommended_next_atlas_expansion": recommendation,
        "future_ai_judgment_policy": _future_ai_judgment_policy(),
        "operator_questions": [
            {
                "question_id": f"markdown_scope_question_{index:02d}",
                "question_text": question,
                "answer_becomes": "memory_candidate_not_proof",
            }
            for index, question in enumerate(OPERATOR_QUESTIONS, start=1)
        ],
        "authority_boundary": {
            **AUTHORITY_BOUNDARY,
            "all_action_authority_flags_false": all(
                value is False for key, value in AUTHORITY_BOUNDARY.items() if key != "metadata_only_posture"
            ),
        },
        "machine_proof": {
            "metadata_only_posture": True,
            "no_broad_body_ingestion": True,
            "no_private_root_approval_by_default": True,
            "no_c_drive_scanning": True,
            "no_file_moves_deletes_renames": True,
            "no_vector_indexing": True,
            "no_ai_semantic_review_now": True,
            "current_coverage_counts_represented": current_coverage["sqlite_present"],
            "root_statuses_fail_closed": all(
                record["current_status"] in ROOT_SCOPE_STATUSES for record in root_scope_plan
            ),
            "recommendation_is_bounded": recommendation["recommendation"] in RECOMMENDATION_OPTIONS
            and recommendation["body_ingestion_allowed"] is False,
            "operator_questions_exist": len(OPERATOR_QUESTIONS) == 7,
            "credential_or_secret_included": False,
            "raw_private_body_included": False,
            "network_git_sync_mac_app_mutation_authority_added": False,
            "latest_markdown_run_id": latest_markdown_run_id,
            "latest_markdown_source_root_ids": sorted(latest_roots),
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_markdown_atlas_scope_expansion(payload: dict[str, Any]) -> str:
    coverage = payload["current_markdown_atlas_coverage"]
    recommendation = payload["recommended_next_atlas_expansion"]
    lines = [
        "# Markdown Atlas Scope Expansion v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        "This report maps what the Markdown Atlas already knows and how to expand it safely. It is metadata-only: paths, filenames, counts, roots, and existing ledger facts. It does not read Markdown bodies, scan private folders, reorganize files, create vectors, or ask an AI to judge old notes yet.",
        "",
        "## Current Coverage",
        "",
        f"- SQLite ledger present: `{str(coverage['sqlite_present']).lower()}`",
        f"- Ledger path: `{coverage['ledger_path']}`",
        f"- Corpus roots: `{coverage['corpus_roots_count']}`",
        f"- Corpus paths: `{coverage['corpus_paths_count']}`",
        f"- Corpus path labels: `{coverage['corpus_path_labels_count']}`",
        f"- Markdown Atlas runs: `{coverage['markdown_atlas_run_count']}`",
        f"- Markdown documents: `{coverage['markdown_documents_count']}`",
        f"- Markdown classifications: `{coverage['markdown_classifications_count']}`",
        f"- Markdown links: `{coverage['markdown_links_count']}`",
        f"- Reorg candidates: `{coverage['reorg_candidates_count']}`",
        f"- Supersession rows: `{coverage['supersession_count']}`",
        f"- Evidence sources/items: `{coverage['evidence_sources_count']}` / `{coverage['evidence_items_count']}`",
        "",
        "## Root Scope",
        "",
    ]
    for record in payload["markdown_root_scope_plan"]:
        lines.append(
            f"- `{record['current_status']}` `{record['root_path']}`: {record['next_safe_move']}"
        )
    lines.extend(
        [
            "",
            "## Markdown Universe Gaps",
            "",
        ]
    )
    for gap in payload["markdown_universe_gap_model"]:
        lines.append(f"- `{gap['gap_id']}`: {gap['safe_next_step']}")
    lines.extend(
        [
            "",
            "## Recommended Next Expansion",
            "",
            f"- Recommendation: `{recommendation['recommendation']}`",
            f"- Include registered root ids: `{', '.join(recommendation['include_root_ids']) or 'none'}`",
            "- Keep body ingestion, private broad roots, vectors, and semantic review blocked.",
            "- Ask for explicit root approval before adding new roots.",
            "",
            "## Future AI Judgment Policy",
            "",
            "- Later, after metadata classification, AI may summarize selected allowlisted docs and recommend canonical/stale/residue labels.",
            "- AI may recommend source-card promotion, stable-map summaries, or archive/reorg candidates without moving files.",
            "- Blocked now: broad body summarization, truth promotion from old notes, file moves/deletes, vector memory from all docs, and private-note use without approval.",
            "",
            "## Operator Questions",
            "",
        ]
    )
    for question in payload["operator_questions"]:
        lines.append(f"- {question['question_text']}")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- No broad raw Markdown body ingestion.",
            "- No private root approval by default.",
            "- No file moves, deletes, renames, vector indexing, model calls, network, Git sync, Mac sync/import, or Mission Control app mutation.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_markdown_atlas_scope_expansion(
    *,
    repo_root: str | Path = ROOT,
    db_path: str | Path = DEFAULT_LEDGER_PATH,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> MarkdownAtlasScopeExpansionExportResult:
    payload = build_markdown_atlas_scope_expansion(
        repo_root=repo_root,
        db_path=db_path,
        generated_at=generated_at,
    )
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_markdown_atlas_scope_expansion(payload), encoding="utf-8")
    coverage = payload["current_markdown_atlas_coverage"]
    return MarkdownAtlasScopeExpansionExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        sqlite_present=coverage["sqlite_present"],
        markdown_documents_count=coverage["markdown_documents_count"],
        corpus_roots_count=coverage["corpus_roots_count"],
        recommended_next_run=payload["recommended_next_atlas_expansion"]["recommendation"],
        action_authority_granted=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Markdown Atlas Scope Expansion read-model.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--db", default=DEFAULT_LEDGER_PATH.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_markdown_atlas_scope_expansion(
        repo_root=args.repo_root,
        db_path=args.db,
        export_root=args.export_root,
    )
    summary = {
        "schema_version": result.schema_version,
        "json_path": result.json_path,
        "operator_path": result.operator_path,
        "sqlite_present": result.sqlite_present,
        "corpus_roots_count": result.corpus_roots_count,
        "markdown_documents_count": result.markdown_documents_count,
        "recommended_next_run": result.recommended_next_run,
        "action_authority_granted": result.action_authority_granted,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        print(f"Markdown Atlas Scope Expansion: `{result.schema_version}`")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
        print(f"- Recommended next run: `{result.recommended_next_run}`")
    return 0


__all__ = [
    "AUTHORITY_BOUNDARY",
    "GAP_IDS",
    "JSON_EXPORT_NAME",
    "OPERATOR_EXPORT_NAME",
    "OPERATOR_QUESTIONS",
    "READ_MODEL_ID",
    "RECOMMENDATION_OPTIONS",
    "ROOT_SCOPE_STATUSES",
    "SCHEMA_VERSION",
    "build_markdown_atlas_scope_expansion",
    "export_markdown_atlas_scope_expansion",
    "format_markdown_atlas_scope_expansion",
    "stable_json",
]
