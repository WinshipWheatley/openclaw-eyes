import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List

@dataclass
class FileTerritoryLookup:
    matched_term: str
    known_surfaces: List[str]
    classification_buckets: List[str]
    dependency_posture: str
    move_safety_posture: str
    proof_sources_consulted: List[str]
    next_safe_step: str
    cleanup_allowed: bool
    manual_review_required: bool

REVIEW_JSON_PATH = Path("reports/file_path_dependency_scan/DEPENDENCY_OWNER_REVIEW.json")
SYSTEM_REGISTRY_SQLITE_PATH = Path("generated/system_knowledge/openclaw_system_knowledge_registry.sqlite")

_COMPONENT_COLUMNS = (
    "component_id",
    "display_name",
    "component_type",
    "evidence_status",
    "summary",
    "authority_boundary",
)
_CAPABILITY_COLUMNS = (
    "capability_id",
    "component_id",
    "capability_name",
    "evidence_status",
    "evidence_basis",
    "boundary",
)
_KNOWN_UNKNOWN_COLUMNS = (
    "unknown_id",
    "subject",
    "unknown_status",
    "reason",
    "next_safe_check",
)


def _authority_boundary() -> dict[str, bool]:
    return {
        "read_only": True,
        "runtime_mutation": False,
        "model_call": False,
        "external_call": False,
        "business_action": False,
    }


def _unavailable(question: str, sqlite_path: Path, reason: str) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "query": question,
        "answer_type": "unavailable",
        "summary": f"Map-room registry unavailable: {reason}.",
        "items": [],
        "source_refs": {"sqlite_path": str(sqlite_path)},
        "authority_boundary": _authority_boundary(),
    }


def _answer_kind(question: str) -> tuple[str, str, tuple[str, ...]]:
    text = str(question or "").lower()
    if any(term in text for term in ("unknown", "missing", "doesn't know", "does not know", "not know")):
        return "known_unknowns", "known_unknown", _KNOWN_UNKNOWN_COLUMNS
    if "capability" in text or "capabilities" in text:
        return "capabilities", "capability", _CAPABILITY_COLUMNS
    return "components", "system_component", _COMPONENT_COLUMNS


def _read_registry_rows(sqlite_path: Path, table: str, columns: tuple[str, ...]) -> list[dict[str, Any]] | None:
    if not sqlite_path.is_file():
        return None
    uri = f"file:{sqlite_path.as_posix()}?mode=ro"
    column_sql = ", ".join(columns)
    try:
        with sqlite3.connect(uri, uri=True) as conn:
            conn.row_factory = sqlite3.Row
            table_exists = conn.execute(
                "select 1 from sqlite_master where type = 'table' and name = ?",
                (table,),
            ).fetchone()
            if table_exists is None:
                return None
            rows = conn.execute(f"select {column_sql} from {table} order by 1").fetchall()
    except sqlite3.Error:
        return None
    return [dict(row) for row in rows]


def query_map_room(
    question: str,
    *,
    sqlite_path: str | Path = SYSTEM_REGISTRY_SQLITE_PATH,
) -> dict[str, Any]:
    """Answer system-shape questions from the SQLite registry, read-only."""
    db_path = Path(sqlite_path)
    answer_type, table, columns = _answer_kind(question)
    rows = _read_registry_rows(db_path, table, columns)
    if not rows:
        return _unavailable(str(question), db_path, f"no readable rows for {table}")
    return {
        "status": "ok",
        "query": question,
        "answer_type": answer_type,
        "summary": f"{len(rows)} {answer_type.replace('_', ' ')} row(s) returned from the system knowledge registry.",
        "items": rows,
        "source_refs": {"sqlite_path": str(db_path), "table": table},
        "authority_boundary": _authority_boundary(),
    }

def _load_review_data() -> dict:
    if REVIEW_JSON_PATH.exists():
        with open(REVIEW_JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def lookup_file_territory(query: str) -> FileTerritoryLookup:
    data = _load_review_data()
    classifications_map = data.get("classifications", {})
    
    found_buckets = []
    for bucket, items in classifications_map.items():
        if query in items:
            found_buckets.append(bucket)
            
    bucket_display_names = {
        "active_dependency_owner": "active dependency owner",
        "historical_archive_reference": "historical/archive reference",
        "generated_output_reference": "generated-output reference",
        "source_authority_reference": "source-authority reference",
        "unsafe_to_move": "unsafe to move",
        "unknown_manual_review": "unknown/manual review"
    }
    
    display_buckets = [bucket_display_names.get(b, b) for b in found_buckets]
    cleanup_allowed = False
    manual_review_required = False
    move_safety_posture = ""
    dependency_posture = ""
    next_safe_step = ""
    known_surfaces = [query]
    
    # Pre-checks for specific types not explicitly in json or needing explicit overrides based on rules
    if query in ["TARGETED_DRY_RUN_CANDIDATE_MOVE_PLAN_V0", "DEPENDENCY_OWNER_REVIEW", "reports/file_path_dependency_scan"]:
        if not display_buckets:
            display_buckets = ["generated-output reference", "safe candidate after validation"]
        move_safety_posture = "safe candidate after validation"
        dependency_posture = "generated-output reference"
        next_safe_step = "maintain as durable truth"
    elif found_buckets:
        if "active_dependency_owner" in found_buckets and "generated_output_reference" in found_buckets:
            dependency_posture = "generated-output plus active dependency owner"
            move_safety_posture = "unsafe to move"
            next_safe_step = "dependency decoupling or manual review"
            manual_review_required = True
        elif "unsafe_to_move" in found_buckets or "active_dependency_owner" in found_buckets:
            dependency_posture = "active dependency owner"
            move_safety_posture = "unsafe to move"
            next_safe_step = "dependency decoupling or manual review"
        elif "unknown_manual_review" in found_buckets:
            dependency_posture = "unknown"
            move_safety_posture = "unknown/manual review"
            manual_review_required = True
            next_safe_step = "manual review required"
        elif "generated_output_reference" in found_buckets:
            dependency_posture = "generated-output reference"
            move_safety_posture = "candidate-only after validation"
            next_safe_step = "await explicit authorization"
            if "safe candidate after validation" not in display_buckets:
                display_buckets.append("safe candidate after validation")
    else:
        # Not found in JSON
        if "Private" in query or "Shared" in query or query.startswith("/mnt/"):
            display_buckets = ["unknown/manual review"]
            dependency_posture = "unknown"
            move_safety_posture = "private-root off-limits"
            manual_review_required = True
            next_safe_step = "manual review required"
        else:
            display_buckets = ["not found"]
            dependency_posture = "unknown"
            move_safety_posture = "unknown/manual review"
            manual_review_required = True
            next_safe_step = "manual review required"

    proof_sources = []
    if REVIEW_JSON_PATH.exists():
        proof_sources.append(str(REVIEW_JSON_PATH))
    else:
        proof_sources.append("fallback_logic")
        
    return FileTerritoryLookup(
        matched_term=query,
        known_surfaces=known_surfaces,
        classification_buckets=display_buckets,
        dependency_posture=dependency_posture,
        move_safety_posture=move_safety_posture,
        proof_sources_consulted=proof_sources,
        next_safe_step=next_safe_step,
        cleanup_allowed=cleanup_allowed,
        manual_review_required=manual_review_required
    )

def map_room_query_status() -> dict[str, object]:
    return {
        "status": "active",
        "passed": True,
        "read_only": True,
        "cleanup_authority_granted": False,
        "cassandra_integration": False,
        "system_walk_enabled": False,
        "mcp_enabled": False,
        "durable_truth_sources": [str(REVIEW_JSON_PATH)]
    }
