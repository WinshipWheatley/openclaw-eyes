import json
from dataclasses import dataclass
from pathlib import Path
from typing import List

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
SYSTEM_REGISTRY_JSON_PATH = Path("generated/read_models/openclaw_system_knowledge_registry.json")
SYSTEM_REGISTRY_OPERATOR_PATH = Path("generated/read_models/openclaw_system_knowledge_registry_OPERATOR.md")
SYSTEM_REGISTRY_SQLITE_PATH = Path("generated/system_knowledge/openclaw_system_knowledge_registry.sqlite")
SPINE_FLOW_PATH = Path("/mnt/e/openclaw/orchestration/SYSTEM-SPINE-7-STEP-FLOW.md")
MARKDOWN_ATLAS_PATH = Path("generated/read_models/markdown_atlas_scope_expansion.json")

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
    durable_truth_sources = [
        str(REVIEW_JSON_PATH),
        str(SYSTEM_REGISTRY_JSON_PATH),
        str(SYSTEM_REGISTRY_OPERATOR_PATH),
        str(SYSTEM_REGISTRY_SQLITE_PATH),
        str(SPINE_FLOW_PATH),
        str(MARKDOWN_ATLAS_PATH),
    ]
    return {
        "status": "active",
        "passed": True,
        "read_only": True,
        "cleanup_authority_granted": False,
        "cassandra_integration": False,
        "system_walk_enabled": False,
        "mcp_enabled": False,
        "durable_truth_sources": durable_truth_sources,
        "known_lookup_surfaces": [
            "file_territory",
            "openclaw_system_knowledge_registry",
            "the_spine",
            "router_registry",
            "markdown_atlas",
        ],
        "spine_discoverability": {
            "canonical_name": "The Spine",
            "flow_ref": str(SPINE_FLOW_PATH),
            "registry_json": str(SYSTEM_REGISTRY_JSON_PATH),
            "registry_sqlite": str(SYSTEM_REGISTRY_SQLITE_PATH),
        },
        "authority_boundary": {
            "read_only": True,
            "cleanup_allowed": False,
            "runtime_mutation": False,
            "external_call": False,
        },
    }
