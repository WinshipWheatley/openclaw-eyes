"""Operator Frontier Map / Explored Territory Guard v0.

This module is a deterministic, read-only territory guard for the Compiled
Knowledge Substrate lane. It answers:

- what has already been built;
- what is partially built;
- what is not built yet;
- whether a proposed next task appears to duplicate existing work;
- what prerequisite should be finished first.

It is not a builder, authority engine, ingestion layer, database layer, runtime
checker, provider caller, bridge activator, or approval surface.

The guard deliberately uses static fixture knowledge about the current lane.
It does not read files, write files, inspect processes, connect to SQLite,
define DDL, ingest private roots, call providers, use embeddings, call MCP,
wire Cassandra/Chief/Telegram, send externally, commit, or push.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping, Sequence


FRONTIER_MAP_RECEIPT_TYPE = "openclaw.operator_frontier_map_status"
FRONTIER_MAP_MODE = "read-only/static-frontier-map/no-execution"

NO_EXECUTION_AUTHORITY_STATEMENT = (
    "The frontier map is a read-only territory guard and grants no execution authority."
)

KNOWN_COMPILED_SUBSTRATE_SURFACES = (
    "docs/planning/operator_harness/COMPILED_KNOWLEDGE_SUBSTRATE_NORTH_STAR.md",
    "compiled_knowledge_substrate.py",
    "tests/test_compiled_knowledge_substrate.py",
)

KNOWN_CONTEXT_EXPORT_BRIDGE_SURFACES = (
    "backend_knowledge_packet.py",
    "AgentContextExportPacket",
    "assemble_agent_context_export",
    "evaluate_actor_agent_context_access",
)

FORBIDDEN_LIVE_BEHAVIORS = (
    "SQLite authority spine implementation",
    "DDL, migration, or database-file creation",
    "file ingestion or private-root traversal",
    "provider/model/API call",
    "embedding or vector retrieval implementation",
    "PageIndex/tree retrieval implementation",
    "graph engine implementation",
    "MCP integration or hidden/shared-memory write",
    "runtime, service, or process inspection",
    "Cassandra/Chief/Telegram live wiring",
    "external send",
    "commit or push",
)


@dataclass(frozen=True)
class FrontierTerritoryItem:
    item_id: str
    label: str
    state: str
    evidence: tuple[str, ...]
    note: str


@dataclass(frozen=True)
class DuplicateWorkFinding:
    duplicate_risk: bool
    finding_code: str
    matched_terms: tuple[str, ...]
    already_built: tuple[str, ...]
    recommendation: str
    prerequisite_to_finish_first: str


@dataclass(frozen=True)
class OperatorFrontierMapStatus:
    receipt_type: str
    mode: str
    lane: str
    authority_note: str
    built: tuple[FrontierTerritoryItem, ...]
    partially_built: tuple[FrontierTerritoryItem, ...]
    not_built: tuple[FrontierTerritoryItem, ...]
    duplicate_work_finding: DuplicateWorkFinding
    next_unfinished_edges: tuple[str, ...]
    forbidden_live_behaviors: tuple[str, ...]
    execution_authority_granted: bool
    provider_or_model_called: bool
    sqlite_used: bool
    ingestion_used: bool
    embeddings_used: bool
    vector_retrieval_used: bool
    pageindex_or_tree_retrieval_used: bool
    graph_engine_used: bool
    mcp_called: bool
    private_root_access_used: bool
    runtime_or_process_inspection_used: bool
    cassandra_chief_telegram_wired: bool
    external_send_used: bool
    commit_or_push_used: bool
    checks: Mapping[str, bool]
    passed: bool


def _dedupe(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


def _plain_normalize(text: str) -> str:
    lowered = str(text or "").lower().strip()
    chars: list[str] = []
    for char in lowered:
        if char.isalnum() or char in {" ", "_", "-"}:
            chars.append(char)
        else:
            chars.append(" ")
    return " ".join("".join(chars).replace("_", " ").replace("-", " ").split())


def _contains_any(normalized_text: str, terms: Sequence[str]) -> tuple[str, ...]:
    matches: list[str] = []
    padded = f" {normalized_text} "
    for term in terms:
        normalized_term = _plain_normalize(term)
        if normalized_term and f" {normalized_term} " in padded:
            matches.append(term)
    return tuple(matches)


def built_territory_items() -> tuple[FrontierTerritoryItem, ...]:
    """Return the Compiled Knowledge Substrate territory already built."""
    return (
        FrontierTerritoryItem(
            item_id="north_star_spec_exists",
            label="North Star spec exists",
            state="built",
            evidence=(
                "docs/planning/operator_harness/COMPILED_KNOWLEDGE_SUBSTRATE_NORTH_STAR.md",
            ),
            note="Doctrine source for the lane exists as a planning/North Star spec.",
        ),
        FrontierTerritoryItem(
            item_id="fixture_contract_exists",
            label="Fixture-only compiled substrate contract exists",
            state="built",
            evidence=("compiled_knowledge_substrate.py",),
            note="The first proof layer is a pure local fixture-backed contract.",
        ),
        FrontierTerritoryItem(
            item_id="lifecycle_states_modeled",
            label="Lifecycle states modeled",
            state="built",
            evidence=(
                "raw_source",
                "parsed_evidence",
                "rendered_fragment",
                "extracted_observation",
                "claim",
                "draft_compiled_note",
                "operator_promotion",
                "promoted_compiled_note",
                "answer_packet",
            ),
            note="The fixture contract models the doctrine lifecycle through answer packets.",
        ),
        FrontierTerritoryItem(
            item_id="answer_packet_exists",
            label="Answer packet exists",
            state="built",
            evidence=("AnswerPacket", "build_answer_packet"),
            note="Deterministic answer packet behavior exists over fixture data.",
        ),
        FrontierTerritoryItem(
            item_id="truth_boundary_behaviors_exist",
            label="Rejected, historical, sensitive, and no-export behavior exists",
            state="built",
            evidence=(
                "rejected_claims_excluded",
                "historical_context",
                "sensitive_no_export_material",
                "export_eligible",
                "export_blockers",
            ),
            note="The answer packet distinguishes rejected claims, historical context, sensitive/no-export material, and export eligibility.",
        ),
        FrontierTerritoryItem(
            item_id="static_status_function_exists",
            label="Static status function exists",
            state="built",
            evidence=("compiled_knowledge_substrate_status",),
            note="The fixture contract has a static non-live status proof.",
        ),
        FrontierTerritoryItem(
            item_id="frontier_map_receipt_command_exists",
            label="Operator Frontier Map receipt command exists",
            state="built",
            evidence=(
                "./scripts/openclaw_receipts.py operator-frontier-map-status",
                "ea23632 feat(receipts): expose operator frontier map status",
            ),
            note="The explored-territory guard is exposed through the receipt/read-model CLI.",
        ),
    )


def partially_built_territory_items() -> tuple[FrontierTerritoryItem, ...]:
    """Return known partial/pending Compiled Knowledge Substrate territory."""
    return (
        FrontierTerritoryItem(
            item_id="context_export_integration_pending",
            label="Substrate not yet integrated into existing context/export surfaces",
            state="partial",
            evidence=KNOWN_CONTEXT_EXPORT_BRIDGE_SURFACES,
            note="Existing agent/context export surfaces should be reviewed before creating a new broad bridge.",
        ),
        FrontierTerritoryItem(
            item_id="operator_question_response_substrate_consumption_unproven",
            label="Operator question response does not yet consume substrate answer packets unless proven otherwise",
            state="partial",
            evidence=("operator_question_response.py", "compiled_knowledge_substrate.py"),
            note="Natural-language response integration remains a future gated slice.",
        ),
    )


def not_built_territory_items() -> tuple[FrontierTerritoryItem, ...]:
    """Return territory explicitly not built in the Compiled Knowledge lane."""
    return (
        FrontierTerritoryItem(
            item_id="sqlite_authority_spine",
            label="SQLite authority spine",
            state="not_built",
            evidence=("no SQLite implementation in fixture contract",),
            note="Do not implement SQLite, DDL, migrations, connections, or database files in this guard.",
        ),
        FrontierTerritoryItem(
            item_id="ingestion",
            label="Ingestion",
            state="not_built",
            evidence=("no file ingestion",),
            note="No source scanning, parsing pipeline, private-root traversal, or fixture loader is active here.",
        ),
        FrontierTerritoryItem(
            item_id="embeddings_vector_retrieval",
            label="Embeddings/vector retrieval",
            state="not_built",
            evidence=("no embeddings", "no vector library",),
            note="Retrieval remains conceptual/fixture-only; no vector implementation is active.",
        ),
        FrontierTerritoryItem(
            item_id="pageindex_tree_retrieval",
            label="PageIndex/tree retrieval implementation",
            state="not_built",
            evidence=("docs-only breadcrumb",),
            note="PageIndex/tree retrieval is future architecture only, not implementation.",
        ),
        FrontierTerritoryItem(
            item_id="graph_engine",
            label="Graph engine",
            state="not_built",
            evidence=("relational edges are fixture data only",),
            note="Relational edges may be represented as fixture records; no graph engine exists.",
        ),
        FrontierTerritoryItem(
            item_id="provider_model_calls",
            label="Provider/model calls",
            state="not_built",
            evidence=("provider_or_model_called=False",),
            note="No provider/model/API calls are part of this lane.",
        ),
        FrontierTerritoryItem(
            item_id="mcp_integration",
            label="MCP integration",
            state="not_built",
            evidence=("mcp_called=False",),
            note="No MCP connector, call, or hidden/shared-memory write is active.",
        ),
        FrontierTerritoryItem(
            item_id="runtime_cassandra_chief_telegram_live_wiring",
            label="Runtime/Telegram/Cassandra/Chief live wiring",
            state="not_built",
            evidence=("runtime_launched=False", "cassandra_chief_telegram_wired=False"),
            note="No runtime launch, daemon, listener, Telegram, Cassandra, or Chief live integration is active.",
        ),
        FrontierTerritoryItem(
            item_id="private_root_legal_invoice_finance_traversal",
            label="Private-root/legal/invoice/finance traversal",
            state="not_built",
            evidence=("private_root_access_used=False",),
            note="No private-root, legal, invoice, finance, client, or sensitive traversal is active.",
        ),
    )


def next_unfinished_edges() -> tuple[str, ...]:
    """Return safe next edge candidates without granting authority."""
    return (
        "Review how substrate answer packets should remain import-safe before any question-response / operator_question_response.py integration.",
        "Review backend_knowledge_packet.py context/export bridge fit before creating any new broad bridge.",
        "Keep SQLite authority spine, ingestion, embeddings, MCP, providers, runtime, and private-root access future-gated.",
    )


def evaluate_frontier_task(proposed_task: str) -> DuplicateWorkFinding:
    """Evaluate whether a proposed task duplicates explored territory.

    The evaluation is string-only and deterministic. It does not inspect files,
    query git, execute receipts, or grant authority.
    """
    normalized = _plain_normalize(proposed_task)
    substrate_terms = (
        "build compiled knowledge substrate",
        "build the compiled knowledge substrate",
        "implement compiled knowledge substrate",
        "create compiled knowledge substrate",
        "compiled knowledge substrate",
    )
    bridge_terms = (
        "build a bridge",
        "build bridge",
        "new bridge",
        "context bridge",
        "export bridge",
        "agent context bridge",
        "substrate bridge",
    )

    substrate_matches = _contains_any(normalized, substrate_terms)
    bridge_matches = _contains_any(normalized, bridge_terms)

    if substrate_matches and any(term in normalized for term in ("build", "implement", "create")):
        return DuplicateWorkFinding(
            duplicate_risk=True,
            finding_code="duplicate_fixture_contract_exists",
            matched_terms=substrate_matches,
            already_built=(
                "compiled_knowledge_substrate.py fixture-only contract",
                "lifecycle dataclasses/records",
                "deterministic answer packet",
                "static non-live status proof",
            ),
            recommendation=(
                "Do not rebuild the fixture contract. Pick the next unfinished edge: "
                "receipt command, import-safe question-response integration review, "
                "or context/export bridge fit review."
            ),
            prerequisite_to_finish_first=(
                "Confirm the existing fixture contract and tests remain the baseline, "
                "then choose one narrow pending edge instead of rebuilding the substrate."
            ),
        )

    if bridge_matches:
        return DuplicateWorkFinding(
            duplicate_risk=True,
            finding_code="possible_bridge_overlap_review_required",
            matched_terms=bridge_matches,
            already_built=KNOWN_CONTEXT_EXPORT_BRIDGE_SURFACES,
            recommendation=(
                "Do not create a broad new bridge before reviewing existing "
                "backend_knowledge_packet.py agent/context export bridge surfaces "
                "and deciding whether a narrow adapter is actually needed."
            ),
            prerequisite_to_finish_first=(
                "Review AgentContextExportPacket, assemble_agent_context_export, "
                "and evaluate_actor_agent_context_access for fit with substrate answer packets."
            ),
        )

    if "sqlite" in normalized or "database" in normalized:
        return DuplicateWorkFinding(
            duplicate_risk=False,
            finding_code="future_sqlite_spine_blocked_by_prerequisites",
            matched_terms=_dedupe(("sqlite" if "sqlite" in normalized else "", "database" if "database" in normalized else "")),
            already_built=("fixture-only contract",),
            recommendation=(
                "SQLite authority spine is not built and should remain future-gated "
                "until fixture, receipt, and bridge-fit proofs are reviewed."
            ),
            prerequisite_to_finish_first=(
                "Finish the read-only frontier/receipt proof and integration design before any SQLite schema or runtime work."
            ),
        )

    return DuplicateWorkFinding(
        duplicate_risk=False,
        finding_code="no_duplicate_detected",
        matched_terms=(),
        already_built=(),
        recommendation=(
            "No duplicate-work risk detected by static terms. Keep the task bounded "
            "and verify it does not cross live, private, provider, MCP, SQLite, or runtime gates."
        ),
        prerequisite_to_finish_first=(
            "Read the frontier map built/partial/not-built sections and choose the smallest unfinished edge."
        ),
    )


def operator_frontier_map_status(
    proposed_task: str | None = None,
) -> OperatorFrontierMapStatus:
    """Return a deterministic Compiled Knowledge Substrate frontier map status."""
    built = built_territory_items()
    partial = partially_built_territory_items()
    missing = not_built_territory_items()
    duplicate = evaluate_frontier_task(proposed_task or "")

    built_ids = tuple(item.item_id for item in built)
    partial_ids = tuple(item.item_id for item in partial)
    missing_ids = tuple(item.item_id for item in missing)

    checks = {
        "built_items_present": built_ids
        == (
            "north_star_spec_exists",
            "fixture_contract_exists",
            "lifecycle_states_modeled",
            "answer_packet_exists",
            "truth_boundary_behaviors_exist",
            "static_status_function_exists",
            "frontier_map_receipt_command_exists",
        ),
        "partial_items_present": partial_ids
        == (
            "context_export_integration_pending",
            "operator_question_response_substrate_consumption_unproven",
        ),
        "not_built_items_present": missing_ids
        == (
            "sqlite_authority_spine",
            "ingestion",
            "embeddings_vector_retrieval",
            "pageindex_tree_retrieval",
            "graph_engine",
            "provider_model_calls",
            "mcp_integration",
            "runtime_cassandra_chief_telegram_live_wiring",
            "private_root_legal_invoice_finance_traversal",
        ),
        "duplicate_guard_available": bool(
            evaluate_frontier_task("build the compiled knowledge substrate").duplicate_risk
        ),
        "bridge_overlap_guard_available": bool(
            evaluate_frontier_task("build a bridge").duplicate_risk
        ),
        "next_unfinished_edges_present": bool(next_unfinished_edges()),
        "non_live_flags_false": True,
    }

    return OperatorFrontierMapStatus(
        receipt_type=FRONTIER_MAP_RECEIPT_TYPE,
        mode=FRONTIER_MAP_MODE,
        lane="compiled_knowledge_substrate",
        authority_note=NO_EXECUTION_AUTHORITY_STATEMENT,
        built=built,
        partially_built=partial,
        not_built=missing,
        duplicate_work_finding=duplicate,
        next_unfinished_edges=next_unfinished_edges(),
        forbidden_live_behaviors=FORBIDDEN_LIVE_BEHAVIORS,
        execution_authority_granted=False,
        provider_or_model_called=False,
        sqlite_used=False,
        ingestion_used=False,
        embeddings_used=False,
        vector_retrieval_used=False,
        pageindex_or_tree_retrieval_used=False,
        graph_engine_used=False,
        mcp_called=False,
        private_root_access_used=False,
        runtime_or_process_inspection_used=False,
        cassandra_chief_telegram_wired=False,
        external_send_used=False,
        commit_or_push_used=False,
        checks=checks,
        passed=all(checks.values()),
    )


def frontier_map_status_to_dict(status: OperatorFrontierMapStatus) -> dict[str, object]:
    """Return a plain deterministic dictionary for tests or future receipts."""
    return asdict(status)


def operator_frontier_map_status_dict(
    proposed_task: str | None = None,
) -> dict[str, object]:
    """Convenience wrapper returning a plain deterministic status dictionary."""
    return frontier_map_status_to_dict(operator_frontier_map_status(proposed_task))
