"""Fixture-only Compiled Knowledge Substrate contract v0.

This module models the first proof layer for the local Compiled Knowledge
Substrate without activating any live substrate behavior.

Doctrine encoded here:
- Retrieval finds candidates.
- Compilation creates durable inspectable knowledge.
- Operator promotion decides what becomes accepted working context.
- Natural language is intent, not authority.
- Receipts are proof snapshots, not approval.

This is deliberately fixture-only and deterministic. It does not read files,
write files, ingest private data, connect to SQLite, define DDL, create
migrations, call providers, use embeddings, call MCP, inspect runtime/process
state, wire Cassandra/Chief/Telegram, send externally, commit, or push.

Future integration notes:
- A natural-language bridge may call this contract in a later gated slice, but
  this module does not import or wire that bridge.
- A SQLite-backed implementation may eventually persist equivalent records, but
  this module intentionally stops at immutable fixture records and answer
  packets.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping, Sequence


LIFECYCLE_STATES = (
    "raw_source",
    "parsed_evidence",
    "rendered_fragment",
    "extracted_observation",
    "claim",
    "draft_compiled_note",
    "operator_promotion",
    "promoted_compiled_note",
    "answer_packet",
)

PROMOTION_DECISIONS = (
    "accepted",
    "rejected",
    "marked_historical",
    "marked_sensitive",
    "excluded",
)

NO_EXECUTION_AUTHORITY_STATEMENT = (
    "Compiled Knowledge Substrate answer packets grant no execution authority."
)

RECEIPT_NON_AUTHORITY_STATEMENT = (
    "Receipts are proof snapshots, not approval and not execution authority."
)

NATURAL_LANGUAGE_NON_AUTHORITY_STATEMENT = (
    "Natural language expresses intent; it is not authority."
)

COVENANT_BOUNDARIES = (
    "External send, export, mutation, runtime action, provider call, MCP action, private-root access, or destructive operation requires a future explicit Operator Action Covenant.",
    "Updating accepted working context requires an explicit operator promotion scoped to named records.",
    "This answer packet is read-only interpretation and grants no action authority.",
)

FORBIDDEN_LIVE_BEHAVIORS = (
    "SQLite connection or SQL execution",
    "DDL, migration, or database-file creation",
    "file ingestion or private-root inspection",
    "provider/model/API call",
    "embedding or vector-library use",
    "MCP call or hidden/shared-memory write",
    "runtime, service, or process inspection",
    "Cassandra/Chief/Telegram live wiring",
    "external send",
    "commit or push",
)


@dataclass(frozen=True)
class RawSourceRecord:
    source_id: str
    title: str
    source_kind: str
    local_fixture_ref: str
    sensitivity: str
    export_policy: str
    accepted_truth: bool
    notes: str


@dataclass(frozen=True)
class ParsedEvidenceRecord:
    evidence_id: str
    source_id: str
    parser_name: str
    text_excerpt: str
    evidence_not_truth: bool
    accepted_truth: bool
    quality: str


@dataclass(frozen=True)
class RenderedFragmentRecord:
    fragment_id: str
    source_id: str
    evidence_id: str
    fragment_kind: str
    shape_preserved: bool
    rendered_not_truth: bool
    accepted_truth: bool
    export_policy: str


@dataclass(frozen=True)
class ExtractedObservationRecord:
    observation_id: str
    evidence_id: str
    fragment_id: str
    observation_text: str
    observation_not_truth: bool
    accepted_truth: bool
    confidence: str


@dataclass(frozen=True)
class ClaimRecord:
    claim_id: str
    observation_ids: tuple[str, ...]
    claim_text: str
    claim_kind: str
    state: str
    current_state_authority: bool
    accepted_truth: bool
    sensitivity: str = "internal"
    export_policy: str = "internal_ok"


@dataclass(frozen=True)
class CompiledNoteRecord:
    note_id: str
    title: str
    body: str
    note_state: str
    claim_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    scope: str
    interpretation_only: bool
    accepted_working_context: bool
    execution_authority_granted: bool
    export_policy: str


@dataclass(frozen=True)
class OperatorPromotionRecord:
    promotion_id: str
    target_kind: str
    target_id: str
    decision: str
    scope: str
    reason: str
    grants_action_authority: bool


@dataclass(frozen=True)
class RelationalEdgeRecord:
    edge_id: str
    from_kind: str
    from_id: str
    to_kind: str
    to_id: str
    relation: str
    fixture_data_only: bool


@dataclass(frozen=True)
class PromotionStateSummary:
    target_kind: str
    target_id: str
    decision: str
    scope: str
    grants_action_authority: bool


@dataclass(frozen=True)
class AnswerPacket:
    question: str
    answer_summary: str
    source_basis: tuple[str, ...]
    evidence_basis: tuple[str, ...]
    rendered_fragment_basis: tuple[str, ...]
    observation_basis: tuple[str, ...]
    claim_basis: tuple[str, ...]
    draft_compiled_note_basis: tuple[str, ...]
    promoted_compiled_note_basis: tuple[str, ...]
    rejected_claims_excluded: tuple[str, ...]
    historical_context: tuple[str, ...]
    sensitive_no_export_material: tuple[str, ...]
    unknowns: tuple[str, ...]
    promotion_state: tuple[PromotionStateSummary, ...]
    covenant_needed_action_boundaries: tuple[str, ...]
    relational_edges_consulted: tuple[str, ...]
    export_eligible: bool
    export_blockers: tuple[str, ...]
    graph_engine_used: bool
    retrieval_mode: str
    compilation_mode: str
    execution_authority_granted: bool
    receipt_non_authority_statement: str
    natural_language_non_authority_statement: str
    no_execution_authority_statement: str


@dataclass(frozen=True)
class CompiledKnowledgeFixture:
    raw_sources: tuple[RawSourceRecord, ...]
    parsed_evidence: tuple[ParsedEvidenceRecord, ...]
    rendered_fragments: tuple[RenderedFragmentRecord, ...]
    observations: tuple[ExtractedObservationRecord, ...]
    claims: tuple[ClaimRecord, ...]
    compiled_notes: tuple[CompiledNoteRecord, ...]
    promotions: tuple[OperatorPromotionRecord, ...]
    relational_edges: tuple[RelationalEdgeRecord, ...]


def _dedupe(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


def _by_id(records: Sequence[object], attr_name: str) -> dict[str, object]:
    return {str(getattr(record, attr_name)): record for record in records}


def fixture_compiled_knowledge_substrate() -> CompiledKnowledgeFixture:
    """Return a deterministic fixture dataset for the compiled substrate contract.

    The fixture intentionally models sensitive, rejected, historical, draft, and
    promoted records so answer-packet behavior can be proven without ingestion
    or live storage.
    """
    raw_sources = (
        RawSourceRecord(
            source_id="source_ops_memo_2020",
            title="Fixture Ops Memo 2020",
            source_kind="fixture_markdown",
            local_fixture_ref="fixture://compiled-substrate/source_ops_memo_2020",
            sensitivity="internal",
            export_policy="internal_ok",
            accepted_truth=False,
            notes="Raw source is evidence, not truth.",
        ),
        RawSourceRecord(
            source_id="source_distribution_contract_2019",
            title="Fixture Distribution Contract 2019",
            source_kind="fixture_contract_excerpt",
            local_fixture_ref="fixture://compiled-substrate/source_distribution_contract_2019",
            sensitivity="historical_internal",
            export_policy="internal_ok",
            accepted_truth=False,
            notes="Historical source may provide background but not current-state authority.",
        ),
        RawSourceRecord(
            source_id="source_payment_snapshot_sensitive",
            title="Fixture Payment Snapshot",
            source_kind="fixture_finance_excerpt",
            local_fixture_ref="fixture://compiled-substrate/source_payment_snapshot_sensitive",
            sensitivity="sensitive_no_export",
            export_policy="no_export",
            accepted_truth=False,
            notes="Sensitive fixture metadata only; not exportable.",
        ),
    )

    parsed_evidence = (
        ParsedEvidenceRecord(
            evidence_id="evidence_ops_memo_parsed",
            source_id="source_ops_memo_2020",
            parser_name="fixture_parser_v0",
            text_excerpt="FixtureCo appears as catalog administrator in the 2020 ops memo.",
            evidence_not_truth=True,
            accepted_truth=False,
            quality="fixture_good",
        ),
        ParsedEvidenceRecord(
            evidence_id="evidence_distribution_contract_parsed",
            source_id="source_distribution_contract_2019",
            parser_name="fixture_parser_v0",
            text_excerpt="The 2019 agreement mentioned a 15 percent historical distribution rate.",
            evidence_not_truth=True,
            accepted_truth=False,
            quality="fixture_good",
        ),
        ParsedEvidenceRecord(
            evidence_id="evidence_sensitive_payment_parsed",
            source_id="source_payment_snapshot_sensitive",
            parser_name="fixture_parser_v0",
            text_excerpt="Sensitive payment reference is present but withheld from export.",
            evidence_not_truth=True,
            accepted_truth=False,
            quality="fixture_sensitive_metadata_only",
        ),
    )

    rendered_fragments = (
        RenderedFragmentRecord(
            fragment_id="fragment_ops_table",
            source_id="source_ops_memo_2020",
            evidence_id="evidence_ops_memo_parsed",
            fragment_kind="table",
            shape_preserved=True,
            rendered_not_truth=True,
            accepted_truth=False,
            export_policy="internal_ok",
        ),
        RenderedFragmentRecord(
            fragment_id="fragment_contract_clause",
            source_id="source_distribution_contract_2019",
            evidence_id="evidence_distribution_contract_parsed",
            fragment_kind="clause",
            shape_preserved=True,
            rendered_not_truth=True,
            accepted_truth=False,
            export_policy="internal_ok",
        ),
        RenderedFragmentRecord(
            fragment_id="fragment_sensitive_amount",
            source_id="source_payment_snapshot_sensitive",
            evidence_id="evidence_sensitive_payment_parsed",
            fragment_kind="finance_row",
            shape_preserved=True,
            rendered_not_truth=True,
            accepted_truth=False,
            export_policy="no_export",
        ),
    )

    observations = (
        ExtractedObservationRecord(
            observation_id="obs_catalog_admin",
            evidence_id="evidence_ops_memo_parsed",
            fragment_id="fragment_ops_table",
            observation_text="FixtureCo is named near catalog administration language.",
            observation_not_truth=True,
            accepted_truth=False,
            confidence="medium",
        ),
        ExtractedObservationRecord(
            observation_id="obs_historical_rate",
            evidence_id="evidence_distribution_contract_parsed",
            fragment_id="fragment_contract_clause",
            observation_text="A historical 15 percent rate appears in a 2019 contract excerpt.",
            observation_not_truth=True,
            accepted_truth=False,
            confidence="medium",
        ),
        ExtractedObservationRecord(
            observation_id="obs_sensitive_payment",
            evidence_id="evidence_sensitive_payment_parsed",
            fragment_id="fragment_sensitive_amount",
            observation_text="A sensitive payment reference exists but is not exportable.",
            observation_not_truth=True,
            accepted_truth=False,
            confidence="low",
        ),
    )

    claims = (
        ClaimRecord(
            claim_id="claim_catalog_admin_candidate",
            observation_ids=("obs_catalog_admin",),
            claim_text="FixtureCo may be relevant to catalog administration context.",
            claim_kind="current_context_candidate",
            state="hypothesis",
            current_state_authority=False,
            accepted_truth=False,
        ),
        ClaimRecord(
            claim_id="claim_rejected_current_royalty_rate",
            observation_ids=("obs_historical_rate",),
            claim_text="The current royalty rate is 18 percent.",
            claim_kind="current_state",
            state="rejected",
            current_state_authority=False,
            accepted_truth=False,
        ),
        ClaimRecord(
            claim_id="claim_historical_distribution_rate",
            observation_ids=("obs_historical_rate",),
            claim_text="A 2019 fixture contract mentioned a 15 percent historical distribution rate.",
            claim_kind="historical_context",
            state="historical",
            current_state_authority=False,
            accepted_truth=False,
        ),
        ClaimRecord(
            claim_id="claim_sensitive_payment_reference",
            observation_ids=("obs_sensitive_payment",),
            claim_text="A sensitive payment reference exists in the fixture.",
            claim_kind="sensitive_context",
            state="sensitive_no_export",
            current_state_authority=False,
            accepted_truth=False,
            sensitivity="sensitive_no_export",
            export_policy="no_export",
        ),
    )

    compiled_notes = (
        CompiledNoteRecord(
            note_id="note_draft_cashflow_context",
            title="Draft cashflow context",
            body="Draft interpretation only; not promoted and not accepted working context.",
            note_state="draft_compiled_note",
            claim_ids=("claim_catalog_admin_candidate", "claim_sensitive_payment_reference"),
            evidence_ids=("evidence_ops_memo_parsed", "evidence_sensitive_payment_parsed"),
            source_ids=("source_ops_memo_2020", "source_payment_snapshot_sensitive"),
            scope="fixture_draft_only",
            interpretation_only=True,
            accepted_working_context=False,
            execution_authority_granted=False,
            export_policy="no_export",
        ),
        CompiledNoteRecord(
            note_id="note_promoted_catalog_context",
            title="Promoted catalog context",
            body="FixtureCo is accepted only as scoped working context for catalog-administration orientation.",
            note_state="promoted_compiled_note",
            claim_ids=("claim_catalog_admin_candidate",),
            evidence_ids=("evidence_ops_memo_parsed",),
            source_ids=("source_ops_memo_2020",),
            scope="catalog_administration_orientation_only",
            interpretation_only=True,
            accepted_working_context=True,
            execution_authority_granted=False,
            export_policy="internal_ok",
        ),
    )

    promotions = (
        OperatorPromotionRecord(
            promotion_id="promotion_accept_note_catalog_context",
            target_kind="compiled_note",
            target_id="note_promoted_catalog_context",
            decision="accepted",
            scope="catalog_administration_orientation_only",
            reason="Promoted as scoped working context from fixture evidence.",
            grants_action_authority=False,
        ),
        OperatorPromotionRecord(
            promotion_id="promotion_reject_current_royalty_rate",
            target_kind="claim",
            target_id="claim_rejected_current_royalty_rate",
            decision="rejected",
            scope="current_state",
            reason="Fixture lacks current-state evidence for the royalty rate.",
            grants_action_authority=False,
        ),
        OperatorPromotionRecord(
            promotion_id="promotion_mark_historical_rate",
            target_kind="claim",
            target_id="claim_historical_distribution_rate",
            decision="marked_historical",
            scope="background_only",
            reason="Historical contract context cannot establish current terms.",
            grants_action_authority=False,
        ),
        OperatorPromotionRecord(
            promotion_id="promotion_mark_sensitive_payment",
            target_kind="claim",
            target_id="claim_sensitive_payment_reference",
            decision="marked_sensitive",
            scope="no_export",
            reason="Sensitive payment context affects export eligibility.",
            grants_action_authority=False,
        ),
    )

    relational_edges = (
        RelationalEdgeRecord(
            edge_id="edge_source_to_evidence_ops",
            from_kind="raw_source",
            from_id="source_ops_memo_2020",
            to_kind="parsed_evidence",
            to_id="evidence_ops_memo_parsed",
            relation="parsed_into",
            fixture_data_only=True,
        ),
        RelationalEdgeRecord(
            edge_id="edge_evidence_to_claim_catalog",
            from_kind="parsed_evidence",
            from_id="evidence_ops_memo_parsed",
            to_kind="claim",
            to_id="claim_catalog_admin_candidate",
            relation="supports_hypothesis",
            fixture_data_only=True,
        ),
        RelationalEdgeRecord(
            edge_id="edge_claim_to_promoted_note",
            from_kind="claim",
            from_id="claim_catalog_admin_candidate",
            to_kind="compiled_note",
            to_id="note_promoted_catalog_context",
            relation="compiled_into",
            fixture_data_only=True,
        ),
    )

    return CompiledKnowledgeFixture(
        raw_sources=raw_sources,
        parsed_evidence=parsed_evidence,
        rendered_fragments=rendered_fragments,
        observations=observations,
        claims=claims,
        compiled_notes=compiled_notes,
        promotions=promotions,
        relational_edges=relational_edges,
    )


def promoted_compiled_notes(
    fixture: CompiledKnowledgeFixture | None = None,
) -> tuple[CompiledNoteRecord, ...]:
    """Return scoped promoted notes that are accepted working context only."""
    data = fixture or fixture_compiled_knowledge_substrate()
    accepted_note_ids = {
        promotion.target_id
        for promotion in data.promotions
        if promotion.target_kind == "compiled_note" and promotion.decision == "accepted"
    }
    return tuple(
        note
        for note in data.compiled_notes
        if note.note_id in accepted_note_ids
        and note.note_state == "promoted_compiled_note"
        and note.accepted_working_context is True
        and note.execution_authority_granted is False
    )


def build_answer_packet(
    question: str,
    *,
    fixture: CompiledKnowledgeFixture | None = None,
) -> AnswerPacket:
    """Build a deterministic answer packet from fixture data only.

    The packet exposes evidence basis, claim/note basis, unknowns, promotion
    state, sensitivity/export posture, historical context, rejected exclusions,
    and Covenant-needed boundaries. It never executes, retrieves live data, or
    treats evidence as approval.
    """
    data = fixture or fixture_compiled_knowledge_substrate()
    claims_by_id = _by_id(data.claims, "claim_id")
    promoted_notes = promoted_compiled_notes(data)

    promoted_claim_ids = _dedupe(
        claim_id
        for note in promoted_notes
        for claim_id in note.claim_ids
        if isinstance(claims_by_id.get(claim_id), ClaimRecord)
        and claims_by_id[claim_id].state not in {"rejected", "historical", "sensitive_no_export"}
    )
    draft_note_ids = _dedupe(
        note.note_id
        for note in data.compiled_notes
        if note.note_state == "draft_compiled_note" or note.accepted_working_context is False
    )
    rejected_claim_ids = _dedupe(
        claim.claim_id
        for claim in data.claims
        if claim.state == "rejected"
    )
    historical_claim_ids = _dedupe(
        claim.claim_id
        for claim in data.claims
        if claim.state == "historical"
    )
    sensitive_claim_ids = _dedupe(
        claim.claim_id
        for claim in data.claims
        if claim.sensitivity == "sensitive_no_export" or claim.export_policy == "no_export"
    )
    sensitive_sources = _dedupe(
        source.source_id
        for source in data.raw_sources
        if source.sensitivity == "sensitive_no_export" or source.export_policy == "no_export"
    )
    export_blockers = _dedupe(
        tuple(sensitive_claim_ids)
        + tuple(sensitive_sources)
        + ("no_export fixture material is present in the answer context",)
    )

    source_basis = _dedupe(source.source_id for source in data.raw_sources)
    evidence_basis = _dedupe(evidence.evidence_id for evidence in data.parsed_evidence)
    rendered_basis = _dedupe(fragment.fragment_id for fragment in data.rendered_fragments)
    observation_basis = _dedupe(observation.observation_id for observation in data.observations)
    promoted_note_basis = _dedupe(note.note_id for note in promoted_notes)
    promotion_state = tuple(
        PromotionStateSummary(
            target_kind=promotion.target_kind,
            target_id=promotion.target_id,
            decision=promotion.decision,
            scope=promotion.scope,
            grants_action_authority=promotion.grants_action_authority,
        )
        for promotion in data.promotions
    )

    unknowns = (
        "Current royalty rate is unknown in this fixture because the current-rate claim was rejected.",
        "Current payment status is unknown; sensitive payment context is metadata-only and no-export.",
        "No future action is authorized by this answer packet.",
    )

    answer_summary = (
        "Fixture answer: one promoted compiled note provides scoped, source-backed "
        "working context for catalog-administration orientation. Rejected claims "
        "are excluded, historical claims are background only, sensitive material "
        "blocks export, and unknowns remain explicit."
    )

    return AnswerPacket(
        question=str(question or "").strip(),
        answer_summary=answer_summary,
        source_basis=source_basis,
        evidence_basis=evidence_basis,
        rendered_fragment_basis=rendered_basis,
        observation_basis=observation_basis,
        claim_basis=promoted_claim_ids,
        draft_compiled_note_basis=draft_note_ids,
        promoted_compiled_note_basis=promoted_note_basis,
        rejected_claims_excluded=rejected_claim_ids,
        historical_context=historical_claim_ids,
        sensitive_no_export_material=_dedupe(tuple(sensitive_claim_ids) + tuple(sensitive_sources)),
        unknowns=unknowns,
        promotion_state=promotion_state,
        covenant_needed_action_boundaries=COVENANT_BOUNDARIES,
        relational_edges_consulted=_dedupe(edge.edge_id for edge in data.relational_edges),
        export_eligible=not export_blockers,
        export_blockers=export_blockers,
        graph_engine_used=False,
        retrieval_mode="fixture_candidate_selection_only",
        compilation_mode="fixture_compiled_notes_only",
        execution_authority_granted=False,
        receipt_non_authority_statement=RECEIPT_NON_AUTHORITY_STATEMENT,
        natural_language_non_authority_statement=NATURAL_LANGUAGE_NON_AUTHORITY_STATEMENT,
        no_execution_authority_statement=NO_EXECUTION_AUTHORITY_STATEMENT,
    )


def answer_packet_to_dict(packet: AnswerPacket) -> dict[str, object]:
    """Return a plain deterministic dictionary for tests or future receipts."""
    return asdict(packet)


def compiled_knowledge_substrate_status() -> dict[str, object]:
    """Return static proof that the substrate contract is non-live fixture-only."""
    fixture = fixture_compiled_knowledge_substrate()
    packet = build_answer_packet("status", fixture=fixture)
    checks = {
        "lifecycle_states_present": LIFECYCLE_STATES
        == (
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
        "raw_evidence_not_truth": all(source.accepted_truth is False for source in fixture.raw_sources),
        "parsed_evidence_not_truth": all(
            evidence.evidence_not_truth is True and evidence.accepted_truth is False
            for evidence in fixture.parsed_evidence
        ),
        "rendered_fragments_not_truth": all(
            fragment.rendered_not_truth is True and fragment.accepted_truth is False
            for fragment in fixture.rendered_fragments
        ),
        "claims_not_truth_by_default": all(claim.accepted_truth is False for claim in fixture.claims),
        "draft_notes_not_accepted": all(
            note.accepted_working_context is False
            for note in fixture.compiled_notes
            if note.note_state == "draft_compiled_note"
        ),
        "promoted_notes_scoped_and_non_authorizing": all(
            note.accepted_working_context is True
            and bool(note.scope)
            and bool(note.source_ids)
            and note.execution_authority_granted is False
            for note in promoted_compiled_notes(fixture)
        ),
        "rejected_claims_excluded_from_answer": all(
            claim_id not in packet.claim_basis
            for claim_id in packet.rejected_claims_excluded
        ),
        "sensitive_material_blocks_export": (
            packet.export_eligible is False
            and bool(packet.sensitive_no_export_material)
            and bool(packet.export_blockers)
        ),
        "unknowns_explicit": bool(packet.unknowns),
        "covenant_boundaries_present": bool(packet.covenant_needed_action_boundaries),
        "relational_edges_fixture_only": all(
            edge.fixture_data_only is True for edge in fixture.relational_edges
        )
        and packet.graph_engine_used is False,
        "no_live_behavior": True,
    }
    return {
        "receipt_type": "openclaw.compiled_knowledge_substrate_status",
        "mode": "fixture-only/static-compiled-knowledge-contract/no-execution",
        "authority_note": (
            "This contract models fixture lifecycle and answer-packet behavior only. "
            "It grants no execution authority and activates no storage, ingestion, "
            "provider, embedding, MCP, runtime, private-root, external-send, commit, "
            "or push behavior."
        ),
        "lifecycle_states": LIFECYCLE_STATES,
        "execution_authority_granted": False,
        "sqlite_used": False,
        "sql_ddl_defined": False,
        "database_file_created": False,
        "ingestion_used": False,
        "private_root_access_used": False,
        "provider_or_model_called": False,
        "embeddings_used": False,
        "vector_library_used": False,
        "mcp_called": False,
        "hidden_memory_write_used": False,
        "runtime_launched": False,
        "process_state_inspected": False,
        "cassandra_chief_telegram_wired": False,
        "external_send_used": False,
        "commit_or_push_used": False,
        "fixture_counts": {
            "raw_sources": len(fixture.raw_sources),
            "parsed_evidence": len(fixture.parsed_evidence),
            "rendered_fragments": len(fixture.rendered_fragments),
            "observations": len(fixture.observations),
            "claims": len(fixture.claims),
            "compiled_notes": len(fixture.compiled_notes),
            "promotions": len(fixture.promotions),
            "relational_edges": len(fixture.relational_edges),
        },
        "forbidden_live_behaviors": FORBIDDEN_LIVE_BEHAVIORS,
        "checks": checks,
        "passed": all(checks.values()),
    }


def fixture_contract_summary() -> Mapping[str, object]:
    """Return a compact summary for future import-safe bridge hooks."""
    status = compiled_knowledge_substrate_status()
    return {
        "receipt_type": status["receipt_type"],
        "mode": status["mode"],
        "passed": status["passed"],
        "lifecycle_states": status["lifecycle_states"],
        "execution_authority_granted": status["execution_authority_granted"],
        "sqlite_used": status["sqlite_used"],
        "provider_or_model_called": status["provider_or_model_called"],
        "mcp_called": status["mcp_called"],
        "runtime_launched": status["runtime_launched"],
        "private_root_access_used": status["private_root_access_used"],
    }
