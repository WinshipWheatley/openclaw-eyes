import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend_data_contract import (
    ACTOR_PROFILE_ACTOR_CLASSES,
    ACTOR_PROFILE_SENSITIVITY_CEILINGS,
    ACTOR_PROFILE_STATUSES,
    ContractDecision,
    ContractLabel,
    ContractState,
    ENVIRONMENT_INTELLIGENCE_AUTHORIZATION_SCOPE_STATUSES,
    ENVIRONMENT_INTELLIGENCE_AUTHORIZED_ENTITY_FAMILIES,
    ENVIRONMENT_INTELLIGENCE_NODE_ROLES,
    ENVIRONMENT_INTELLIGENCE_NODE_SOURCE_LINK_STATUSES,
    ENVIRONMENT_INTELLIGENCE_TRUST_STATUSES,
    EntityFamily,
    KnowledgeLayer,
    ALLOWED_LAYERS_BY_ENTITY_FAMILY,
    ALLOWED_STATES_BY_ENTITY_FAMILY,
    REQUIRED_LABEL_BUNDLES_BY_LAYER,
    REQUIRED_SCHEMA_CONTRACT_SURFACES,
    REQUIRED_SQLITE_TABLE_CONCEPTS,
    REQUIRED_WRITE_BACK_CAPTURE_LABELS,
    RUNTIME_PRESENCE_CAPABILITY_STATUSES,
    RUNTIME_PRESENCE_COMPONENT_ROLES,
    RUNTIME_PRESENCE_COMPONENT_STATUSES,
    RUNTIME_PRESENCE_HEALTH_STATUSES,
    SCHEMA_CONTRACT_FORBIDDEN_BEHAVIOR,
    SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR,
    STORAGE_INTELLIGENCE_ALLOWED_SOURCE_MODES,
    STORAGE_INTELLIGENCE_DISCOVERY_STATUSES,
    STORAGE_INTELLIGENCE_EXECUTION_STATUSES,
    STORAGE_INTELLIGENCE_INVENTORY_STATUSES,
    STORAGE_INTELLIGENCE_OPERATOR_CLASSIFICATIONS,
    STORAGE_INTELLIGENCE_SAFETY_TIERS,
    SchemaContractSurface,
    SemanticRecordProposal,
    SQLiteTableConcept,
    allowed_layers_for_entity_family,
    allowed_states_for_entity_family,
    classify_record_state,
    classify_semantic_record,
    entity_family_decision,
    is_accepted_knowledge,
    is_entity_family_excluded,
    is_entity_family_known,
    is_entity_record_accepted_knowledge,
    is_implementation_forbidden,
    is_schema_surface_known,
    is_sqlite_table_concept_known,
    normalize_entity_family,
    normalize_schema_surface_name,
    normalize_sqlite_table_concept_name,
    missing_required_labels,
    missing_write_back_capture_labels,
    required_labels_for_layer,
    required_schema_surface_fields,
    required_sqlite_table_concept_fields,
    schema_contract_surface,
    schema_contract_surfaces,
    schema_surface_names,
    semantic_records_table_preserves_synthesis_not_truth,
    sqlite_table_concept,
    sqlite_table_concept_names,
    sqlite_table_concepts,
    sqlite_table_concepts_keep_receipts_and_promotion_separate,
    table_concept_can_directly_imply_accepted_truth,
    validate_sqlite_table_concept_definition,
    validate_schema_surface_definition,
    validate_entity_family_record,
    validate_field_bundle,
)


FULL_LABELS = frozenset(
    {
        ContractLabel.PROVENANCE,
        ContractLabel.FRESHNESS,
        ContractLabel.CONFIDENCE,
        ContractLabel.SENSITIVITY,
        ContractLabel.AUTHORITY,
        ContractLabel.REVIEW_STATUS,
    }
)


def test_core_vocabulary_preserves_knowledge_compiler_layers_and_labels():
    assert {layer.value for layer in KnowledgeLayer} == {
        "raw layer",
        "compiled/wiki layer",
        "relationship layer",
        "synthesis layer",
        "write-back/capture layer",
    }

    assert REQUIRED_WRITE_BACK_CAPTURE_LABELS == frozenset(
        {
            ContractLabel.PROVENANCE,
            ContractLabel.FRESHNESS,
            ContractLabel.CONFIDENCE,
            ContractLabel.SENSITIVITY,
            ContractLabel.AUTHORITY,
            ContractLabel.REVIEW_STATUS,
        }
    )
    assert REQUIRED_WRITE_BACK_CAPTURE_LABELS == FULL_LABELS

    assert {state.value for state in ContractState} >= {
        "confirmed",
        "inferred",
        "excluded",
        "unknown",
        "blocked",
        "stale",
        "confirmed-as-interpretation",
        "draft",
        "needs review",
    }


def test_each_layer_has_required_field_bundle_labels():
    assert set(REQUIRED_LABEL_BUNDLES_BY_LAYER) == set(KnowledgeLayer)

    for layer in KnowledgeLayer:
        assert required_labels_for_layer(layer) == FULL_LABELS
        assert REQUIRED_LABEL_BUNDLES_BY_LAYER[layer] == FULL_LABELS


def test_forbidden_implementation_concepts_are_not_authorized():
    forbidden_uses = (
        "build a CLI command",
        "create SQLite persistence",
        "define API endpoints",
        "invoke an MCP tool",
        "provider model call",
        "start an ingestion job",
        "run runtime services",
        "generate embeddings and indexing",
        "create frontend app code",
    )

    for proposed_use in forbidden_uses:
        assert is_implementation_forbidden(proposed_use) is True
        assert (
            classify_record_state(
                KnowledgeLayer.RAW,
                ContractState.CONFIRMED,
                proposed_use=proposed_use,
            )
            is ContractDecision.IMPLEMENTATION_FORBIDDEN
        )


def test_record_state_classifier_preserves_allowed_unknown_and_excluded_results():
    assert (
        classify_record_state(KnowledgeLayer.RAW, ContractState.CONFIRMED)
        is ContractDecision.ALLOWED
    )
    assert (
        classify_record_state(KnowledgeLayer.RAW, ContractState.UNKNOWN)
        is ContractDecision.UNKNOWN
    )
    assert (
        classify_record_state(KnowledgeLayer.RAW, ContractState.EXCLUDED)
        is ContractDecision.EXCLUDED
    )
    assert classify_record_state("new mystery layer", "confirmed") is ContractDecision.UNKNOWN


def test_write_back_capture_requires_labels_and_promotion_before_allowed():
    partial_labels = {
        ContractLabel.PROVENANCE,
        ContractLabel.FRESHNESS,
        ContractLabel.AUTHORITY,
    }
    assert missing_write_back_capture_labels(partial_labels) == frozenset(
        {
            ContractLabel.CONFIDENCE,
            ContractLabel.SENSITIVITY,
            ContractLabel.REVIEW_STATUS,
        }
    )

    assert (
        classify_record_state(
            KnowledgeLayer.WRITE_BACK_CAPTURE,
            ContractState.CONFIRMED_WITH_RECEIPT,
            labels=partial_labels,
            promoted_by_operator=True,
        )
        is ContractDecision.UNKNOWN
    )

    assert (
        classify_record_state(
            KnowledgeLayer.WRITE_BACK_CAPTURE,
            ContractState.CONFIRMED_WITH_RECEIPT,
            labels=REQUIRED_WRITE_BACK_CAPTURE_LABELS,
        )
        is ContractDecision.UNKNOWN
    )

    assert (
        classify_record_state(
            KnowledgeLayer.WRITE_BACK_CAPTURE,
            ContractState.CONFIRMED_WITH_RECEIPT,
            labels=REQUIRED_WRITE_BACK_CAPTURE_LABELS,
            promoted_by_operator=True,
        )
        is ContractDecision.ALLOWED
    )


def test_valid_minimal_records_pass_field_bundle_validation():
    records = (
        SemanticRecordProposal(
            layer=KnowledgeLayer.RAW,
            state=ContractState.CONFIRMED,
            labels=FULL_LABELS,
        ),
        SemanticRecordProposal(
            layer=KnowledgeLayer.COMPILED_WIKI,
            state=ContractState.CONFIRMED_AS_INTERPRETATION,
            labels=FULL_LABELS,
        ),
        SemanticRecordProposal(
            layer=KnowledgeLayer.RELATIONSHIP,
            state=ContractState.CONFIRMED,
            labels=FULL_LABELS,
        ),
        SemanticRecordProposal(
            layer=KnowledgeLayer.SYNTHESIS,
            state=ContractState.INFERRED,
            labels=FULL_LABELS,
        ),
        SemanticRecordProposal(
            layer=KnowledgeLayer.WRITE_BACK_CAPTURE,
            state=ContractState.CONFIRMED_WITH_RECEIPT,
            labels=FULL_LABELS,
            promoted_by_operator=True,
        ),
    )

    for record in records:
        result = validate_field_bundle(record)
        assert result.ok is True
        assert result.reasons == ()


def test_missing_layer_labels_fail_with_useful_reasons():
    partial_labels = FULL_LABELS - {
        ContractLabel.CONFIDENCE,
        ContractLabel.REVIEW_STATUS,
    }
    record = SemanticRecordProposal(
        layer=KnowledgeLayer.RAW,
        state=ContractState.CONFIRMED,
        labels=partial_labels,
    )

    assert missing_required_labels(KnowledgeLayer.RAW, partial_labels) == frozenset(
        {ContractLabel.CONFIDENCE, ContractLabel.REVIEW_STATUS}
    )

    result = validate_field_bundle(record)
    assert result.ok is False
    assert result.decision is ContractDecision.UNKNOWN
    assert result.reasons == (
        "missing required labels for raw layer: confidence, review status",
    )


def test_synthesis_is_not_confirmed_truth_by_default():
    synthesis = SemanticRecordProposal(
        layer=KnowledgeLayer.SYNTHESIS,
        state=ContractState.INFERRED,
        labels=FULL_LABELS,
    )

    assert classify_semantic_record(synthesis) is ContractDecision.ALLOWED
    assert validate_field_bundle(synthesis).ok is True
    assert is_accepted_knowledge(synthesis) is False

    overstated_synthesis = SemanticRecordProposal(
        layer=KnowledgeLayer.SYNTHESIS,
        state=ContractState.CONFIRMED,
        labels=REQUIRED_WRITE_BACK_CAPTURE_LABELS,
        promoted_by_operator=True,
    )
    assert classify_semantic_record(overstated_synthesis) is ContractDecision.UNKNOWN
    assert is_accepted_knowledge(overstated_synthesis) is False

    captured = SemanticRecordProposal(
        layer=KnowledgeLayer.WRITE_BACK_CAPTURE,
        state=ContractState.CONFIRMED_WITH_RECEIPT,
        labels=REQUIRED_WRITE_BACK_CAPTURE_LABELS,
        promoted_by_operator=True,
    )
    assert classify_semantic_record(captured) is ContractDecision.ALLOWED
    assert is_accepted_knowledge(captured) is True


def test_write_back_capture_needs_promotion_for_valid_record_and_acceptance():
    unpromoted = SemanticRecordProposal(
        layer=KnowledgeLayer.WRITE_BACK_CAPTURE,
        state=ContractState.CONFIRMED_WITH_RECEIPT,
        labels=FULL_LABELS,
    )

    result = validate_field_bundle(unpromoted)
    assert result.ok is False
    assert result.decision is ContractDecision.UNKNOWN
    assert result.reasons == (
        "write-back/capture confirmed receipt requires operator promotion",
    )
    assert is_accepted_knowledge(unpromoted) is False


def test_forbidden_implementation_concepts_fail_field_bundle_validation():
    record = SemanticRecordProposal(
        layer=KnowledgeLayer.WRITE_BACK_CAPTURE,
        state=ContractState.CONFIRMED_WITH_RECEIPT,
        labels=FULL_LABELS,
        proposed_use="define API routes for a runtime service",
        promoted_by_operator=True,
    )

    result = validate_field_bundle(record)
    assert result.ok is False
    assert result.decision is ContractDecision.IMPLEMENTATION_FORBIDDEN
    assert result.reasons == (
        "implementation-forbidden proposed use cannot be accepted",
    )
    assert is_accepted_knowledge(record) is False


def test_unknown_and_excluded_states_cannot_confirm_accidentally():
    unknown = SemanticRecordProposal(
        layer=KnowledgeLayer.RAW,
        state=ContractState.UNKNOWN,
        labels=FULL_LABELS,
        promoted_by_operator=True,
    )
    excluded = SemanticRecordProposal(
        layer=KnowledgeLayer.RAW,
        state=ContractState.EXCLUDED,
        labels=FULL_LABELS,
        promoted_by_operator=True,
    )

    unknown_result = validate_field_bundle(unknown)
    assert unknown_result.ok is False
    assert unknown_result.decision is ContractDecision.UNKNOWN
    assert "unknown-style state cannot be treated as confirmed" in unknown_result.reasons

    excluded_result = validate_field_bundle(excluded)
    assert excluded_result.ok is False
    assert excluded_result.decision is ContractDecision.EXCLUDED
    assert "excluded-style state cannot be treated as confirmed" in excluded_result.reasons


def test_private_sensitive_promotion_requires_sensitivity_and_authority_labels():
    record = SemanticRecordProposal(
        layer=KnowledgeLayer.COMPILED_WIKI,
        state=ContractState.SENSITIVE_LOCAL_ONLY,
        labels=FULL_LABELS - {ContractLabel.SENSITIVITY, ContractLabel.AUTHORITY},
        promoted_by_operator=True,
    )

    result = validate_field_bundle(record)
    assert result.ok is False
    assert result.decision is ContractDecision.UNKNOWN
    assert "private/sensitive promotion requires labels: authority, sensitivity" in result.reasons


def test_known_entity_families_normalize_correctly():
    assert {family.value for family in EntityFamily} >= {
        "person",
        "organization",
        "client",
        "job",
        "invoice",
        "payment",
        "project",
        "music work",
        "legal matter",
        "tax matter",
        "source material",
        "compiled page",
        "relationship",
        "synthesis",
        "follow-up action",
        "approval",
        "blocker",
        "system artifact",
    }

    assert normalize_entity_family("music-work") is EntityFamily.MUSIC_WORK
    assert normalize_entity_family("song") is EntityFamily.MUSIC_WORK
    assert normalize_entity_family("follow_up_action") is EntityFamily.FOLLOW_UP_ACTION
    assert normalize_entity_family("compiled/wiki page") is EntityFamily.COMPILED_PAGE
    assert normalize_entity_family("tax") is EntityFamily.TAX_MATTER


def test_unknown_and_excluded_entity_families_remain_distinct():
    assert entity_family_decision("mystery obligation") is ContractDecision.UNKNOWN
    assert entity_family_decision("private root") is ContractDecision.EXCLUDED
    assert is_entity_family_known(EntityFamily.INVOICE) is True
    assert is_entity_family_excluded("private data") is True

    unknown_result = validate_entity_family_record(
        "mystery obligation",
        KnowledgeLayer.WRITE_BACK_CAPTURE,
        ContractState.CONFIRMED_WITH_RECEIPT,
        labels=FULL_LABELS,
        promoted_by_operator=True,
    )
    excluded_result = validate_entity_family_record(
        "private data",
        KnowledgeLayer.WRITE_BACK_CAPTURE,
        ContractState.CONFIRMED_WITH_RECEIPT,
        labels=FULL_LABELS,
        promoted_by_operator=True,
    )

    assert unknown_result.decision is ContractDecision.UNKNOWN
    assert unknown_result.reasons[0] == "unknown entity family: mystery obligation"
    assert excluded_result.decision is ContractDecision.EXCLUDED
    assert excluded_result.reasons[0] == (
        "excluded entity family cannot be accepted: private data"
    )
    assert (
        is_entity_record_accepted_knowledge(
            "mystery obligation",
            KnowledgeLayer.WRITE_BACK_CAPTURE,
            ContractState.CONFIRMED_WITH_RECEIPT,
            labels=FULL_LABELS,
            promoted_by_operator=True,
        )
        is False
    )


def test_entity_family_layer_and_state_maps_are_explicit():
    assert set(ALLOWED_LAYERS_BY_ENTITY_FAMILY) == set(EntityFamily)
    assert set(ALLOWED_STATES_BY_ENTITY_FAMILY) == set(EntityFamily)
    assert allowed_layers_for_entity_family(EntityFamily.INVOICE) == frozenset(
        {
            KnowledgeLayer.RAW,
            KnowledgeLayer.COMPILED_WIKI,
            KnowledgeLayer.RELATIONSHIP,
            KnowledgeLayer.WRITE_BACK_CAPTURE,
        }
    )
    assert ContractState.CONFIRMED in allowed_states_for_entity_family(
        EntityFamily.PAYMENT
    )
    assert ContractState.PACKET_PREPARED in allowed_states_for_entity_family(
        EntityFamily.FOLLOW_UP_ACTION
    )


def test_valid_entity_family_layer_state_combinations_pass():
    valid_records = (
        (EntityFamily.PERSON, KnowledgeLayer.RAW, ContractState.CONFIRMED, False),
        (EntityFamily.INVOICE, KnowledgeLayer.RAW, ContractState.CONFIRMED, False),
        (
            EntityFamily.PAYMENT,
            KnowledgeLayer.RELATIONSHIP,
            ContractState.INFERRED,
            False,
        ),
        (
            EntityFamily.FOLLOW_UP_ACTION,
            KnowledgeLayer.COMPILED_WIKI,
            ContractState.DRAFT,
            False,
        ),
        (
            EntityFamily.APPROVAL,
            KnowledgeLayer.WRITE_BACK_CAPTURE,
            ContractState.CONFIRMED_WITH_RECEIPT,
            True,
        ),
        (
            EntityFamily.SYNTHESIS,
            KnowledgeLayer.SYNTHESIS,
            ContractState.INFERRED,
            False,
        ),
    )

    for family, layer, state, promoted in valid_records:
        result = validate_entity_family_record(
            family,
            layer,
            state,
            labels=FULL_LABELS,
            promoted_by_operator=promoted,
        )
        assert result.ok is True
        assert result.reasons == ()


def test_invalid_entity_family_combinations_fail_with_reasons():
    invoice_result = validate_entity_family_record(
        EntityFamily.INVOICE,
        KnowledgeLayer.SYNTHESIS,
        ContractState.INFERRED,
        labels=FULL_LABELS,
    )
    approval_result = validate_entity_family_record(
        EntityFamily.APPROVAL,
        KnowledgeLayer.RAW,
        ContractState.CONFIRMED,
        labels=FULL_LABELS,
    )

    assert invoice_result.ok is False
    assert invoice_result.decision is ContractDecision.UNKNOWN
    assert any(
        reason.startswith("family invoice is not allowed in synthesis layer")
        for reason in invoice_result.reasons
    )

    assert approval_result.ok is False
    assert approval_result.decision is ContractDecision.UNKNOWN
    assert any(
        reason.startswith("family approval is not allowed in raw layer")
        for reason in approval_result.reasons
    )
    assert "state confirmed is not allowed for approval" in approval_result.reasons


def test_receivables_families_support_accountability_without_auto_sending():
    invoice = validate_entity_family_record(
        EntityFamily.INVOICE,
        KnowledgeLayer.RAW,
        ContractState.CONFIRMED,
        labels=FULL_LABELS,
        proposed_use="track evidence-backed receivable for operator review",
    )
    payment = validate_entity_family_record(
        EntityFamily.PAYMENT,
        KnowledgeLayer.RELATIONSHIP,
        ContractState.INFERRED,
        labels=FULL_LABELS,
        proposed_use="connect payment responsibility to invoice evidence",
    )
    follow_up = validate_entity_family_record(
        EntityFamily.FOLLOW_UP_ACTION,
        KnowledgeLayer.COMPILED_WIKI,
        ContractState.DRAFT,
        labels=FULL_LABELS,
        proposed_use="prepare follow-up action for operator review",
    )
    forbidden_follow_up = validate_entity_family_record(
        EntityFamily.FOLLOW_UP_ACTION,
        KnowledgeLayer.WRITE_BACK_CAPTURE,
        ContractState.CONFIRMED_WITH_RECEIPT,
        labels=FULL_LABELS,
        proposed_use="automated sending harassment collection action",
        promoted_by_operator=True,
    )

    assert invoice.ok is True
    assert payment.ok is True
    assert follow_up.ok is True
    assert forbidden_follow_up.decision is ContractDecision.IMPLEMENTATION_FORBIDDEN
    assert forbidden_follow_up.reasons == (
        "implementation-forbidden proposed use cannot be accepted",
    )


def test_legal_tax_and_music_families_do_not_authorize_private_or_provider_use():
    assert normalize_entity_family("legal matter") is EntityFamily.LEGAL_MATTER
    assert normalize_entity_family("tax matter") is EntityFamily.TAX_MATTER
    assert normalize_entity_family("music work") is EntityFamily.MUSIC_WORK

    legal_private = validate_entity_family_record(
        EntityFamily.LEGAL_MATTER,
        KnowledgeLayer.RAW,
        ContractState.CONFIRMED,
        labels=FULL_LABELS,
        proposed_use="private root inspection",
    )
    tax_private = validate_entity_family_record(
        EntityFamily.TAX_MATTER,
        KnowledgeLayer.COMPILED_WIKI,
        ContractState.INFERRED,
        labels=FULL_LABELS,
        proposed_use="private data inspection",
    )
    music_provider = validate_entity_family_record(
        EntityFamily.MUSIC_WORK,
        KnowledgeLayer.SYNTHESIS,
        ContractState.INFERRED,
        labels=FULL_LABELS,
        proposed_use="provider model call",
    )

    assert legal_private.decision is ContractDecision.IMPLEMENTATION_FORBIDDEN
    assert tax_private.decision is ContractDecision.IMPLEMENTATION_FORBIDDEN
    assert music_provider.decision is ContractDecision.IMPLEMENTATION_FORBIDDEN


def test_operator_life_families_stay_bounded_by_authority():
    project = validate_entity_family_record(
        EntityFamily.PROJECT,
        KnowledgeLayer.RAW,
        ContractState.CONFIRMED,
        labels=FULL_LABELS,
        proposed_use="track travel logistics and ordinary-life admin for operator review",
    )
    follow_up = validate_entity_family_record(
        EntityFamily.FOLLOW_UP_ACTION,
        KnowledgeLayer.COMPILED_WIKI,
        ContractState.DRAFT,
        labels=FULL_LABELS,
        proposed_use="prepare a next safe action for operator review",
    )
    blocker = validate_entity_family_record(
        EntityFamily.BLOCKER,
        KnowledgeLayer.RELATIONSHIP,
        ContractState.BLOCKED,
        labels=FULL_LABELS,
    )
    forbidden_project = validate_entity_family_record(
        EntityFamily.PROJECT,
        KnowledgeLayer.RAW,
        ContractState.CONFIRMED,
        labels=FULL_LABELS,
        proposed_use="provider model call for private-root inspection",
    )

    assert project.ok is True
    assert follow_up.ok is True
    assert blocker.decision is ContractDecision.EXCLUDED
    assert is_entity_record_accepted_knowledge(
        EntityFamily.BLOCKER,
        KnowledgeLayer.RELATIONSHIP,
        ContractState.BLOCKED,
        labels=FULL_LABELS,
    ) is False
    assert forbidden_project.decision is ContractDecision.IMPLEMENTATION_FORBIDDEN


def test_synthesis_family_is_not_accepted_truth_by_default():
    result = validate_entity_family_record(
        EntityFamily.SYNTHESIS,
        KnowledgeLayer.SYNTHESIS,
        ContractState.INFERRED,
        labels=FULL_LABELS,
    )

    assert result.ok is True
    assert (
        is_entity_record_accepted_knowledge(
            EntityFamily.SYNTHESIS,
            KnowledgeLayer.SYNTHESIS,
            ContractState.INFERRED,
            labels=FULL_LABELS,
        )
        is False
    )


def test_entity_write_back_capture_requires_labels_and_operator_promotion():
    missing_labels = validate_entity_family_record(
        EntityFamily.SYNTHESIS,
        KnowledgeLayer.WRITE_BACK_CAPTURE,
        ContractState.CONFIRMED_WITH_RECEIPT,
        labels=FULL_LABELS - {ContractLabel.CONFIDENCE},
        promoted_by_operator=True,
    )
    missing_promotion = validate_entity_family_record(
        EntityFamily.SYNTHESIS,
        KnowledgeLayer.WRITE_BACK_CAPTURE,
        ContractState.CONFIRMED_WITH_RECEIPT,
        labels=FULL_LABELS,
    )

    assert missing_labels.ok is False
    assert (
        "missing required labels for write-back/capture layer: confidence"
        in missing_labels.reasons
    )
    assert missing_promotion.ok is False
    assert missing_promotion.reasons == (
        "write-back/capture confirmed receipt requires operator promotion",
    )
    assert (
        is_entity_record_accepted_knowledge(
            EntityFamily.SYNTHESIS,
            KnowledgeLayer.WRITE_BACK_CAPTURE,
            ContractState.CONFIRMED_WITH_RECEIPT,
            labels=FULL_LABELS,
            promoted_by_operator=True,
        )
        is True
    )


def test_required_schema_contract_surfaces_exist():
    assert schema_surface_names() == REQUIRED_SCHEMA_CONTRACT_SURFACES
    assert schema_surface_names() == (
        "semantic_record",
        "semantic_label",
        "semantic_relationship",
        "provenance_ref",
        "validation_receipt",
        "operator_promotion",
        "context_filter_receipt",
        "source_registry",
        "source_discovery_queue",
        "source_exclusion",
        "file_inventory",
        "storage_operation_receipt",
        "openclaw_node",
        "node_source_link",
        "source_authorization_scope",
        "runtime_component",
        "component_capability",
        "node_heartbeat",
        "component_heartbeat",
        "component_health_snapshot",
        "performance_session",
        "setlist",
        "setlist_item",
        "song_cue",
        "section_cue",
        "performance_action_receipt",
        "manual_override_event",
        "highlight_marker",
        "actor_profile",
        "agent_context_profile",
        "context_export_receipt",
    )

    surfaces = schema_contract_surfaces()
    assert all(isinstance(surface, SchemaContractSurface) for surface in surfaces)
    assert tuple(surface.name for surface in surfaces) == REQUIRED_SCHEMA_CONTRACT_SURFACES


def test_schema_surface_names_normalize_correctly():
    assert normalize_schema_surface_name(" Semantic Record ") == "semantic_record"
    assert normalize_schema_surface_name("semantic-record") == "semantic_record"
    assert normalize_schema_surface_name("semantic record") == "semantic_record"
    assert normalize_schema_surface_name("record labels") == "semantic_label"
    assert normalize_schema_surface_name("operator promotions") == "operator_promotion"
    assert normalize_schema_surface_name("context filter receipts") == (
        "context_filter_receipt"
    )
    assert normalize_schema_surface_name("source registry") == "source_registry"
    assert normalize_schema_surface_name("source discovery") == (
        "source_discovery_queue"
    )
    assert normalize_schema_surface_name("source exclusions") == "source_exclusion"
    assert normalize_schema_surface_name("file inventory") == "file_inventory"
    assert normalize_schema_surface_name("storage operation receipts") == (
        "storage_operation_receipt"
    )
    assert normalize_schema_surface_name("openclaw nodes") == "openclaw_node"
    assert normalize_schema_surface_name("node source links") == "node_source_link"
    assert normalize_schema_surface_name("source authorization scopes") == (
        "source_authorization_scope"
    )
    assert normalize_schema_surface_name("runtime components") == "runtime_component"
    assert normalize_schema_surface_name("component capabilities") == (
        "component_capability"
    )
    assert normalize_schema_surface_name("node heartbeats") == "node_heartbeat"
    assert normalize_schema_surface_name("component heartbeats") == (
        "component_heartbeat"
    )
    assert normalize_schema_surface_name("component health snapshots") == (
        "component_health_snapshot"
    )
    assert normalize_schema_surface_name("unknown table") is None
    assert is_schema_surface_known("semantic records") is True
    assert is_schema_surface_known("runtime table") is False


def test_schema_surfaces_expose_required_conceptual_fields():
    assert required_schema_surface_fields("semantic_record") >= frozenset(
        {
            "record_id",
            "entity_family",
            "knowledge_layer",
            "contract_state",
            "provenance_refs",
            "freshness_refs",
            "confidence_label",
            "sensitivity_label",
            "authority_label",
            "review_status_label",
            "validator_decision",
        }
    )
    assert required_schema_surface_fields("operator promotion") >= frozenset(
        {
            "promotion_id",
            "target_record_id",
            "operator_decision",
            "receipt_ref",
            "promotion_scope",
            "promoted_by_operator",
        }
    )
    assert required_schema_surface_fields("validation_receipt") >= frozenset(
        {
            "receipt_id",
            "validated_target",
            "validator_name",
            "validation_result",
            "failure_reasons",
        }
    )


def test_missing_schema_surface_fields_fail_with_useful_reasons():
    result = validate_schema_surface_definition(
        "semantic record",
        {
            "record_id",
            "entity_family",
            "knowledge_layer",
            "contract_state",
        },
        forbidden_implementation_behavior=SCHEMA_CONTRACT_FORBIDDEN_BEHAVIOR,
    )

    assert result.ok is False
    assert result.decision is ContractDecision.UNKNOWN
    assert result.reasons == (
        "schema surface semantic_record missing conceptual fields: "
        "accepted_knowledge_derived, authority_label, confidence_label, "
        "freshness_refs, provenance_refs, review_status_label, sensitivity_label, "
        "synthesis_not_truth, validator_decision",
    )


def test_missing_schema_surface_forbidden_boundaries_fail_closed():
    result = validate_schema_surface_definition(
        "semantic_label",
        required_schema_surface_fields("semantic_label"),
    )

    assert result.ok is False
    assert result.decision is ContractDecision.UNKNOWN
    assert result.reasons == (
        "schema surface semantic_label missing forbidden implementation behavior: "
        "API route, Hermes, MCP, SQL DDL, SQLite implementation, database connection, "
        "embedding, file I/O, fixture, indexing, ingestion, migration, persistence, "
        "private-root inspection, provider/model call, runtime service",
    )


def test_schema_contract_layer_does_not_authorize_forbidden_implementation_terms():
    forbidden_uses = (
        "SQLite implementation",
        "SQL DDL",
        "migration",
        "persistence",
        "API route",
        "ingestion",
        "indexing",
        "embedding",
        "runtime service",
        "fixture",
        "provider/model call",
        "Hermes",
        "MCP",
        "private-root inspection",
        "file I/O",
        "database connection",
    )

    combined_forbidden = " ".join(
        " ".join(surface.forbidden_implementation_behavior)
        for surface in schema_contract_surfaces()
    ).lower()

    for forbidden_use in forbidden_uses:
        assert is_implementation_forbidden(forbidden_use) is True
        assert forbidden_use.lower() in combined_forbidden


def test_semantic_record_surface_preserves_layers_and_families_without_truth_flattening():
    surface = schema_contract_surface("semantic_record")

    assert surface is not None
    assert surface.knowledge_layers == frozenset(KnowledgeLayer)
    assert set(surface.entity_families) == set(EntityFamily)
    assert "synthesis_not_truth" in surface.required_conceptual_fields
    assert "accepted_knowledge_derived" in surface.required_conceptual_fields

    synthesis_record = SemanticRecordProposal(
        layer=KnowledgeLayer.SYNTHESIS,
        state=ContractState.INFERRED,
        labels=FULL_LABELS,
    )
    assert validate_field_bundle(synthesis_record).ok is True
    assert is_accepted_knowledge(synthesis_record) is False


def test_operator_promotion_and_validation_receipt_remain_separate_schema_surfaces():
    promotion = schema_contract_surface("operator_promotion")
    receipt = schema_contract_surface("validation_receipt")

    assert promotion is not None
    assert receipt is not None
    assert promotion.name != receipt.name
    assert "operator_decision" in promotion.required_conceptual_fields
    assert "validator_name" in receipt.required_conceptual_fields
    assert "validation_result" in receipt.required_conceptual_fields
    assert "operator_decision" not in receipt.required_conceptual_fields


def test_schema_contract_helpers_are_pure_lookup_and_validation_only():
    for surface_name in schema_surface_names():
        result = validate_schema_surface_definition(
            surface_name,
            required_schema_surface_fields(surface_name),
            forbidden_implementation_behavior=SCHEMA_CONTRACT_FORBIDDEN_BEHAVIOR,
        )
        assert result.ok is True
        assert result.reasons == ()

    unknown = validate_schema_surface_definition("runtime table", {"id"})
    assert unknown.decision is ContractDecision.UNKNOWN
    assert unknown.reasons == ("unknown schema surface: runtime table",)

    forbidden_helper_names = {
        "open",
        "read",
        "read_text",
        "write",
        "write_text",
        "sqlite3",
        "connect",
        "request",
        "requests",
        "httpx",
        "openai",
        "anthropic",
        "subprocess",
        "socket",
    }
    helpers = (
        normalize_schema_surface_name,
        is_schema_surface_known,
        schema_contract_surface,
        schema_contract_surfaces,
        schema_surface_names,
        required_schema_surface_fields,
        validate_schema_surface_definition,
    )

    for helper in helpers:
        assert forbidden_helper_names.isdisjoint(helper.__code__.co_names)


def test_required_sqlite_table_concepts_exist():
    assert sqlite_table_concept_names() == REQUIRED_SQLITE_TABLE_CONCEPTS
    assert sqlite_table_concept_names() == (
        "semantic_records",
        "semantic_labels",
        "semantic_relationships",
        "provenance_refs",
        "validation_receipts",
        "operator_promotions",
        "context_filter_receipts",
        "source_registry",
        "source_discovery_queue",
        "source_exclusions",
        "file_inventory",
        "storage_operation_receipts",
        "openclaw_nodes",
        "node_source_links",
        "source_authorization_scopes",
        "runtime_components",
        "component_capabilities",
        "node_heartbeats",
        "component_heartbeats",
        "component_health_snapshots",
        "performance_sessions",
        "setlists",
        "setlist_items",
        "song_cues",
        "section_cues",
        "performance_action_receipts",
        "manual_override_events",
        "highlight_markers",
        "actor_profiles",
        "agent_context_profiles",
        "context_export_receipts",
    )

    table_concepts = sqlite_table_concepts()
    assert all(isinstance(concept, SQLiteTableConcept) for concept in table_concepts)
    assert tuple(concept.name for concept in table_concepts) == (
        REQUIRED_SQLITE_TABLE_CONCEPTS
    )


def test_sqlite_table_concept_names_normalize_correctly():
    assert normalize_sqlite_table_concept_name(" Semantic Records ") == (
        "semantic_records"
    )
    assert normalize_sqlite_table_concept_name("semantic-record") == (
        "semantic_records"
    )
    assert normalize_sqlite_table_concept_name("semantic record") == (
        "semantic_records"
    )
    assert normalize_sqlite_table_concept_name("operator promotion") == (
        "operator_promotions"
    )
    assert normalize_sqlite_table_concept_name("validation receipt") == (
        "validation_receipts"
    )
    assert normalize_sqlite_table_concept_name("context-filter-receipts") == (
        "context_filter_receipts"
    )
    assert normalize_sqlite_table_concept_name("source registry") == (
        "source_registry"
    )
    assert normalize_sqlite_table_concept_name("source discovery") == (
        "source_discovery_queue"
    )
    assert normalize_sqlite_table_concept_name("source exclusions") == (
        "source_exclusions"
    )
    assert normalize_sqlite_table_concept_name("file inventory") == "file_inventory"
    assert normalize_sqlite_table_concept_name("storage operation receipt") == (
        "storage_operation_receipts"
    )
    assert normalize_sqlite_table_concept_name("openclaw node") == "openclaw_nodes"
    assert normalize_sqlite_table_concept_name("node source link") == (
        "node_source_links"
    )
    assert normalize_sqlite_table_concept_name("source authorization scope") == (
        "source_authorization_scopes"
    )
    assert normalize_sqlite_table_concept_name("runtime component") == (
        "runtime_components"
    )
    assert normalize_sqlite_table_concept_name("component capability") == (
        "component_capabilities"
    )
    assert normalize_sqlite_table_concept_name("node heartbeat") == "node_heartbeats"
    assert normalize_sqlite_table_concept_name("component heartbeat") == (
        "component_heartbeats"
    )
    assert normalize_sqlite_table_concept_name("component health snapshot") == (
        "component_health_snapshots"
    )
    assert normalize_sqlite_table_concept_name("runtime table") is None
    assert is_sqlite_table_concept_known("provenance references") is True
    assert is_sqlite_table_concept_known("sqlite runtime") is False


def test_each_sqlite_table_concept_maps_to_expected_schema_surface():
    expected = {
        "semantic_records": "semantic_record",
        "semantic_labels": "semantic_label",
        "semantic_relationships": "semantic_relationship",
        "provenance_refs": "provenance_ref",
        "validation_receipts": "validation_receipt",
        "operator_promotions": "operator_promotion",
        "context_filter_receipts": "context_filter_receipt",
        "source_registry": "source_registry",
        "source_discovery_queue": "source_discovery_queue",
        "source_exclusions": "source_exclusion",
        "file_inventory": "file_inventory",
        "storage_operation_receipts": "storage_operation_receipt",
        "openclaw_nodes": "openclaw_node",
        "node_source_links": "node_source_link",
        "source_authorization_scopes": "source_authorization_scope",
        "runtime_components": "runtime_component",
        "component_capabilities": "component_capability",
        "node_heartbeats": "node_heartbeat",
        "component_heartbeats": "component_heartbeat",
        "component_health_snapshots": "component_health_snapshot",
        "actor_profiles": "actor_profile",
    }

    for table_name, surface_name in expected.items():
        concept = sqlite_table_concept(table_name)
        assert concept is not None
        assert concept.related_schema_contract_surface == surface_name
        assert is_schema_surface_known(surface_name) is True


def test_sqlite_table_concepts_expose_required_conceptual_fields():
    assert required_sqlite_table_concept_fields("semantic_records") >= frozenset(
        {
            "record_id",
            "entity_family",
            "knowledge_layer",
            "contract_state",
            "validator_decision",
            "synthesis_not_truth",
            "accepted_knowledge_derived",
            "provenance_refs",
            "freshness_refs",
            "confidence_label",
            "sensitivity_label",
            "authority_label",
            "review_status_label",
        }
    )
    assert required_sqlite_table_concept_fields("operator_promotions") >= frozenset(
        {
            "promotion_id",
            "target_record_id",
            "operator_decision",
            "receipt_ref",
            "promotion_scope",
            "promoted_by_operator",
            "complete_label_set",
        }
    )
    assert required_sqlite_table_concept_fields("context_filter_receipts") >= frozenset(
        {
            "context_filter_receipt_id",
            "context_package_ref",
            "filter_scope",
            "checked_inputs",
            "withheld_surfaces",
            "filter_outcome",
            "finding_summary",
            "review_route",
        }
    )
    assert required_sqlite_table_concept_fields("source_registry") >= frozenset(
        {
            "source_id",
            "device_identity",
            "last_known_mount_path",
            "source_mode",
            "operator_classification",
            "approval_receipt_ref",
            "freshness_timestamp",
        }
    )
    assert required_sqlite_table_concept_fields("file_inventory") >= frozenset(
        {
            "inventory_id",
            "source_id",
            "relative_path",
            "file_size",
            "mtime",
            "hash_heuristic",
            "inventory_status",
            "last_seen_timestamp",
            "source_confidence",
        }
    )
    assert required_sqlite_table_concept_fields(
        "storage_operation_receipts"
    ) >= frozenset(
        {
            "operation_id",
            "operation_type",
            "source_inventory_id",
            "target_path",
            "safety_tier",
            "checksum_verification",
            "operator_approval_ref",
            "execution_status",
        }
    )
    assert required_sqlite_table_concept_fields("openclaw_nodes") >= frozenset(
        {
            "node_id",
            "node_identity",
            "node_fingerprint",
            "trust_status",
            "identity_verified_at",
            "node_role",
            "tenant_id",
            "agent_version",
            "status",
            "operator_approval_ref",
            "first_seen",
            "last_seen",
        }
    )
    assert required_sqlite_table_concept_fields("node_source_links") >= frozenset(
        {
            "link_id",
            "node_id",
            "source_id",
            "tenant_id",
            "status",
            "linked_at",
            "last_seen",
            "operator_approval_ref",
        }
    )
    assert required_sqlite_table_concept_fields(
        "source_authorization_scopes"
    ) >= frozenset(
        {
            "scope_id",
            "source_id",
            "tenant_id",
            "authorized_entity_family",
            "authorized_entity_id",
            "operator_approval_ref",
            "expiration_timestamp",
            "status",
        }
    )
    assert required_sqlite_table_concept_fields("runtime_components") >= frozenset(
        {
            "component_id",
            "node_id",
            "tenant_id",
            "component_name",
            "component_instance_id",
            "component_role",
            "component_version",
            "status",
            "approval_receipt_ref",
            "registered_at",
            "last_seen",
        }
    )
    assert required_sqlite_table_concept_fields("component_capabilities") >= frozenset(
        {
            "capability_id",
            "component_id",
            "tenant_id",
            "capability_name",
            "capability_scope",
            "status",
            "approval_receipt_ref",
        }
    )
    assert required_sqlite_table_concept_fields("node_heartbeats") >= frozenset(
        {
            "heartbeat_id",
            "node_id",
            "tenant_id",
            "reported_at",
            "heartbeat_ttl_seconds",
            "health_status",
            "status_message",
            "last_known_state",
        }
    )
    assert required_sqlite_table_concept_fields("component_heartbeats") >= frozenset(
        {
            "heartbeat_id",
            "component_id",
            "node_id",
            "tenant_id",
            "reported_at",
            "heartbeat_ttl_seconds",
            "health_status",
            "status_message",
            "last_known_state",
        }
    )
    assert required_sqlite_table_concept_fields(
        "component_health_snapshots"
    ) >= frozenset(
        {
            "snapshot_id",
            "component_id",
            "node_id",
            "tenant_id",
            "captured_at",
            "health_status",
            "degraded_reason",
            "capabilities_reported",
            "version_reported",
            "last_known_state",
        }
    )


def test_storage_intelligence_static_value_surfaces_are_explicit():
    assert STORAGE_INTELLIGENCE_ALLOWED_SOURCE_MODES == (
        "ignore",
        "guided_review",
        "inventory_only",
        "metadata_safe",
        "content_allowed",
        "private_vault",
    )
    assert {"camera", "field_recorder", "music_projects", "unknown"} <= set(
        STORAGE_INTELLIGENCE_OPERATOR_CLASSIFICATIONS
    )
    assert "pending_approval" in STORAGE_INTELLIGENCE_DISCOVERY_STATUSES
    assert {"discovered", "inventoried", "stale", "missing"} <= set(
        STORAGE_INTELLIGENCE_INVENTORY_STATUSES
    )
    assert STORAGE_INTELLIGENCE_SAFETY_TIERS == (
        "read_only",
        "reversible_copy",
        "move_after_verified_copy",
        "destructive_or_reformat",
    )
    assert {"dry_run", "approved", "executed", "blocked", "failed"} <= set(
        STORAGE_INTELLIGENCE_EXECUTION_STATUSES
    )


def test_environment_intelligence_static_value_surfaces_are_explicit():
    assert ENVIRONMENT_INTELLIGENCE_NODE_ROLES == (
        "primary",
        "worker",
        "observer",
        "mobile",
        "source_only",
        "firm_workstation",
    )
    assert ENVIRONMENT_INTELLIGENCE_TRUST_STATUSES == (
        "unknown",
        "pending_approval",
        "approved",
        "revoked",
        "stale",
    )
    assert ENVIRONMENT_INTELLIGENCE_NODE_SOURCE_LINK_STATUSES == (
        "pending",
        "active",
        "revoked",
        "stale",
    )
    assert ENVIRONMENT_INTELLIGENCE_AUTHORIZATION_SCOPE_STATUSES == (
        "active",
        "expired",
        "revoked",
    )
    assert {"legal_matter", "client_delivery", "system"} <= set(
        ENVIRONMENT_INTELLIGENCE_AUTHORIZED_ENTITY_FAMILIES
    )


def test_runtime_presence_static_value_surfaces_are_explicit():
    assert {"pending_approval", "active", "revoked", "degraded", "unknown"} <= set(
        RUNTIME_PRESENCE_COMPONENT_STATUSES
    )
    assert {
        "storage_runner",
        "hermes_sidecar",
        "web_capture_runner",
        "mobile_bridge",
        "control_surface_runner",
        "environment_runner",
        "discovery_runner",
        "unknown",
    } <= set(RUNTIME_PRESENCE_COMPONENT_ROLES)
    assert RUNTIME_PRESENCE_CAPABILITY_STATUSES == (
        "pending",
        "approved",
        "revoked",
        "stale",
    )
    assert RUNTIME_PRESENCE_HEALTH_STATUSES == (
        "healthy",
        "degraded",
        "stale",
        "critical",
        "unknown",
    )


def test_actor_profile_static_value_surfaces_are_advisory_and_open_ended():
    assert {
        "canonical",
        "advisory_sidecar",
        "build_worker",
        "cloud_sidecar",
        "local_sidecar",
        "human_operator",
        "future_actor",
        "unknown",
    } <= set(ACTOR_PROFILE_ACTOR_CLASSES)
    assert {
        "public",
        "non_sensitive",
        "sanitized",
        "sensitive_local",
        "private_strict",
        "tenant_strict",
        "unknown",
    } <= set(ACTOR_PROFILE_SENSITIVITY_CEILINGS)
    assert ACTOR_PROFILE_STATUSES == (
        "active",
        "inactive",
        "revoked",
        "pending",
        "archived",
    )


def test_missing_sqlite_table_concept_fields_fail_with_useful_reasons():
    result = validate_sqlite_table_concept_definition(
        "semantic records",
        {
            "record_id",
            "entity_family",
            "knowledge_layer",
            "contract_state",
        },
        forbidden_implementation_behavior=SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR,
    )

    assert result.ok is False
    assert result.decision is ContractDecision.UNKNOWN
    assert result.reasons == (
        "SQLite table concept semantic_records missing conceptual fields: "
        "accepted_knowledge_derived, authority_label, confidence_label, "
        "freshness_refs, provenance_refs, review_status_label, sensitivity_label, "
        "synthesis_not_truth, validator_decision",
    )


def test_missing_sqlite_table_concept_forbidden_boundaries_fail_closed():
    result = validate_sqlite_table_concept_definition(
        "semantic_labels",
        required_sqlite_table_concept_fields("semantic_labels"),
    )

    assert result.ok is False
    assert result.decision is ContractDecision.UNKNOWN
    expected_reason = (
        "SQLite table concept semantic_labels missing forbidden implementation behavior: "
        "API route, DB connections, Hermes, MCP, SQL DDL execution, SQLite implementation, "
        "SQLite runtime, app behavior, database connection, embedding, extraction, "
        "file I/O, fixture, frontend/app behavior, indexing, ingestion, migration, "
        "persistence, private-root inspection, provider/model call, runtime service, "
        "source-set generation, sqlite3, sync"
    )
    assert result.reasons == (expected_reason,)


def test_sqlite_table_concepts_do_not_authorize_forbidden_implementation_terms():
    forbidden_uses = (
        "SQLite runtime",
        "SQLite implementation",
        "sqlite3",
        "SQL DDL execution",
        "migrations",
        "persistence",
        "DB connections",
        "file I/O",
        "API routes",
        "ingestion",
        "extraction",
        "indexing",
        "embeddings",
        "fixtures",
        "runtime services",
        "frontend/app behavior",
        "provider/model calls",
        "Hermes",
        "MCPs",
        "sync",
        "source-set generation",
        "private-root inspection",
        "app behavior",
    )

    combined_forbidden = " ".join(
        " ".join(concept.forbidden_implementation_behavior)
        for concept in sqlite_table_concepts()
    ).lower()

    for forbidden_use in forbidden_uses:
        assert is_implementation_forbidden(forbidden_use) is True
        assert forbidden_use.lower().removesuffix("s") in combined_forbidden


def test_semantic_records_table_preserves_layer_separation_without_truth_flattening():
    concept = sqlite_table_concept("semantic_records")

    assert concept is not None
    assert concept.knowledge_layers == frozenset(KnowledgeLayer)
    assert "synthesis_not_truth" in concept.required_conceptual_fields
    assert "accepted_knowledge_derived" in concept.required_conceptual_fields
    assert semantic_records_table_preserves_synthesis_not_truth() is True
    assert table_concept_can_directly_imply_accepted_truth("semantic_records") is False

    synthesis_record = SemanticRecordProposal(
        layer=KnowledgeLayer.SYNTHESIS,
        state=ContractState.INFERRED,
        labels=FULL_LABELS,
    )
    captured_record = SemanticRecordProposal(
        layer=KnowledgeLayer.WRITE_BACK_CAPTURE,
        state=ContractState.CONFIRMED_WITH_RECEIPT,
        labels=FULL_LABELS,
        promoted_by_operator=True,
    )

    assert validate_field_bundle(synthesis_record).ok is True
    assert is_accepted_knowledge(synthesis_record) is False
    assert is_accepted_knowledge(captured_record) is True


def test_receipt_promotion_and_provenance_tables_remain_distinct():
    promotion = sqlite_table_concept("operator_promotions")
    validation = sqlite_table_concept("validation_receipts")
    provenance = sqlite_table_concept("provenance_refs")
    context_filter = sqlite_table_concept("context_filter_receipts")

    assert promotion is not None
    assert validation is not None
    assert provenance is not None
    assert context_filter is not None
    assert sqlite_table_concepts_keep_receipts_and_promotion_separate() is True
    assert {promotion.name, validation.name, provenance.name, context_filter.name} == {
        "operator_promotions",
        "validation_receipts",
        "provenance_refs",
        "context_filter_receipts",
    }
    assert "operator_decision" in promotion.required_conceptual_fields
    assert "validation_result" in validation.required_conceptual_fields
    assert "source_basis" in provenance.required_conceptual_fields
    assert "filter_outcome" in context_filter.required_conceptual_fields
    assert "operator_decision" not in validation.required_conceptual_fields


def test_sqlite_table_concept_helpers_are_pure_lookup_and_validation_only():
    for table_name in sqlite_table_concept_names():
        result = validate_sqlite_table_concept_definition(
            table_name,
            required_sqlite_table_concept_fields(table_name),
            forbidden_implementation_behavior=SQLITE_TABLE_CONCEPT_FORBIDDEN_BEHAVIOR,
        )
        assert result.ok is True
        assert result.reasons == ()

    unknown = validate_sqlite_table_concept_definition("runtime table", {"id"})
    assert unknown.decision is ContractDecision.UNKNOWN
    assert unknown.reasons == ("unknown SQLite table concept: runtime table",)

    forbidden_helper_names = {
        "open",
        "read",
        "read_text",
        "write",
        "write_text",
        "sqlite3",
        "connect",
        "request",
        "requests",
        "httpx",
        "openai",
        "anthropic",
        "subprocess",
        "socket",
    }
    helpers = (
        normalize_sqlite_table_concept_name,
        is_sqlite_table_concept_known,
        sqlite_table_concept,
        sqlite_table_concepts,
        sqlite_table_concept_names,
        required_sqlite_table_concept_fields,
        validate_sqlite_table_concept_definition,
        semantic_records_table_preserves_synthesis_not_truth,
        table_concept_can_directly_imply_accepted_truth,
        sqlite_table_concepts_keep_receipts_and_promotion_separate,
    )

    for helper in helpers:
        assert forbidden_helper_names.isdisjoint(helper.__code__.co_names)
