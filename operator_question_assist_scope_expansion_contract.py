"""Operator Question Assist / Scope Expansion Contract v0.

This deterministic read-model defines how OpenClaw turns unfamiliar work into
navigable missions. It is a contract only: it does not implement live UI,
Telegram, model calls, tools, receipt writes, workflow-state mutation, or
runtime authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "operator_question_assist_scope_expansion_contract_v0"
READ_MODEL_ID = "operator_question_assist_scope_expansion_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_EXECUTING_QUESTION_ASSIST_CONTRACT"

PATH_TYPES = (
    "EXPLAIN_TERM",
    "SHOW_EXAMPLES",
    "HELP_ME_CHOOSE",
    "FIND_PROOF",
    "ASK_AGENT_TO_CLARIFY",
    "CREATE_DISCOVERY_PATH",
    "CREATE_GUIDED_CAPTURE_PATH",
    "CREATE_BLOCK_DRAFT_INTENT",
    "PARK_UNTIL_LATER",
    "ESCALATE_TO_GUARDIAN",
    "UNKNOWN_FAIL_CLOSED",
)

SURFACES = (
    "Mission Control",
    "Telegram",
    "Cassandra/Clara conversation",
    "Chief conversation",
    "Guardian review",
    "Hermes advisory",
    "Niles project flow",
    "future agents",
)

REQUIRED_QUESTION_ASSIST_FIELDS = (
    "assist_id",
    "question_ref",
    "workflow_session_ref",
    "block_ref",
    "world",
    "lane",
    "question_text",
    "domain_terms",
    "plain_language_explanation",
    "why_this_matters",
    "valid_answer_types",
    "example_good_answers",
    "common_confusions",
    "proof_or_evidence_needed",
    "if_you_dont_know_options",
    "discovery_path_options",
    "guided_capture_options",
    "agent_assist_options",
    "downstream_effects",
    "authority_boundary",
    "next_safe_move",
)

REQUIRED_DOMAIN_HINT_FIELDS = (
    "hint_id",
    "operator_ref",
    "strong_domains",
    "context_dependent_domains",
    "unfamiliar_or_high_friction_domains",
    "preferred_explanation_modes",
    "analogy_sources",
    "support_style",
    "include_by_default",
    "compact_summary",
    "deeper_support_available",
    "deeper_support_trigger",
    "privacy_boundary",
    "next_safe_move",
)

REQUIRED_SCOPE_MISSION_FIELDS = (
    "mission_id",
    "title",
    "originating_question_ref",
    "target_world",
    "target_lane",
    "unfamiliar_domain",
    "operator_confidence_hint",
    "mission_blocks",
    "system_can_fill_blocks",
    "operator_needed_blocks",
    "recommended_crew",
    "question_assist_refs",
    "proof_or_capture_refs",
    "safety_gates",
    "suggested_first_move",
    "encouragement_style",
    "overreach_warning",
    "next_safe_move",
)

REQUIRED_WORKFLOW_PATH_FIELDS = (
    "path_id",
    "assist_ref",
    "path_label",
    "path_type",
    "what_it_does",
    "operator_input_needed",
    "system_input_needed",
    "agent_support_needed",
    "proof_needed",
    "creates_discovery_substep",
    "creates_guided_capture_path",
    "creates_block_draft_intent",
    "creates_agent_packet_candidate",
    "blocked_actions",
    "authority_boundary",
    "next_safe_move",
)

REQUIRED_AGENT_BEHAVIOR_FIELDS = (
    "behavior_id",
    "agent_ref",
    "surface",
    "question_assist_refs",
    "domain_hint_refs",
    "compact_context_policy",
    "when_to_explain",
    "when_to_use_analogy",
    "when_to_ask_operator",
    "when_to_request_deeper_packet",
    "when_to_stop_and_handoff",
    "allowed_response_shapes",
    "blocked_response_shapes",
    "next_safe_move",
)

AUTHORITY_BOUNDARY = {
    "live_question_assist_execution_allowed": False,
    "agent_response_execution_allowed": False,
    "model_call_allowed": False,
    "tool_execution_allowed": False,
    "mcp_execution_allowed": False,
    "script_execution_allowed": False,
    "hook_execution_allowed": False,
    "receipt_write_allowed": False,
    "state_write_allowed": False,
    "legal_advice_authority": False,
    "financial_advice_authority": False,
    "invoice_generation_allowed": False,
    "email_send_allowed": False,
    "browser_automation_allowed": False,
    "coupa_access_allowed": False,
    "credential_handling_allowed": False,
    "telegram_send_allowed": False,
    "queue_execution_allowed": False,
    "runtime_dispatch_allowed": False,
    "file_write_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_operation_allowed": False,
    "gmail_access_allowed": False,
    "calendar_access_allowed": False,
    "approval_submission_allowed": False,
    "ledger_write_allowed": False,
    "mission_control_swift_change_allowed": False,
    "mac_sync_import_allowed": False,
    "git_push_pull_fetch_allowed": False,
    "file_cleanup_archive_promotion_allowed": False,
}

RELATIONSHIP_REF_PATHS = {
    "workflow_block_intent_live_draft_contract": "generated/read_models/workflow_block_intent_live_draft_contract.json",
    "agent_execution_packet_compiler_contract": "generated/read_models/agent_execution_packet_compiler_contract.json",
    "agent_conversation_handoff_step_packet_contract": (
        "generated/read_models/agent_conversation_handoff_step_packet_contract.json"
    ),
    "bridge_routing_operator_attention_contract": "generated/read_models/bridge_routing_operator_attention_contract.json",
    "operator_solve_path_decision_node_contract": "generated/read_models/operator_solve_path_decision_node_contract.json",
    "guided_capture_protected_evidence_path_contract": (
        "generated/read_models/guided_capture_protected_evidence_path_contract.json"
    ),
    "work_terrain_surface_map_build_cue_scout": "generated/read_models/work_terrain_surface_map_build_cue_scout.json",
    "work_terrain_build_cue_reconciliation_queue": (
        "generated/read_models/work_terrain_build_cue_reconciliation_queue.json"
    ),
}


@dataclass(frozen=True)
class OperatorQuestionAssist:
    assist_id: str
    question_ref: str
    workflow_session_ref: str
    block_ref: str
    world: str
    lane: str
    question_text: str
    domain_terms: tuple[dict[str, str], ...]
    plain_language_explanation: str
    why_this_matters: str
    valid_answer_types: tuple[str, ...]
    example_good_answers: tuple[str, ...]
    common_confusions: tuple[str, ...]
    proof_or_evidence_needed: str
    if_you_dont_know_options: tuple[str, ...]
    discovery_path_options: tuple[str, ...]
    guided_capture_options: tuple[str, ...]
    agent_assist_options: tuple[str, ...]
    downstream_effects: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class OperatorDomainFamiliarityHint:
    hint_id: str
    operator_ref: str
    strong_domains: tuple[str, ...]
    context_dependent_domains: tuple[str, ...]
    unfamiliar_or_high_friction_domains: tuple[str, ...]
    preferred_explanation_modes: tuple[str, ...]
    analogy_sources: tuple[str, ...]
    support_style: tuple[str, ...]
    include_by_default: bool
    compact_summary: str
    deeper_support_available: bool
    deeper_support_trigger: str
    privacy_boundary: str
    next_safe_move: str


@dataclass(frozen=True)
class OperatorScopeExpansionMission:
    mission_id: str
    title: str
    originating_question_ref: str
    target_world: str
    target_lane: str
    unfamiliar_domain: str
    operator_confidence_hint: str
    mission_blocks: tuple[str, ...]
    system_can_fill_blocks: tuple[str, ...]
    operator_needed_blocks: tuple[str, ...]
    recommended_crew: tuple[str, ...]
    question_assist_refs: tuple[str, ...]
    proof_or_capture_refs: tuple[str, ...]
    safety_gates: tuple[str, ...]
    suggested_first_move: str
    encouragement_style: str
    overreach_warning: str
    next_safe_move: str


@dataclass(frozen=True)
class QuestionAssistWorkflowPath:
    path_id: str
    assist_ref: str
    path_label: str
    path_type: str
    what_it_does: str
    operator_input_needed: str
    system_input_needed: str
    agent_support_needed: str
    proof_needed: str
    creates_discovery_substep: bool
    creates_guided_capture_path: bool
    creates_block_draft_intent: bool
    creates_agent_packet_candidate: bool
    blocked_actions: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class AgentQuestionAssistBehavior:
    behavior_id: str
    agent_ref: str
    surface: str
    question_assist_refs: tuple[str, ...]
    domain_hint_refs: tuple[str, ...]
    compact_context_policy: str
    when_to_explain: str
    when_to_use_analogy: str
    when_to_ask_operator: str
    when_to_request_deeper_packet: str
    when_to_stop_and_handoff: str
    allowed_response_shapes: tuple[str, ...]
    blocked_response_shapes: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class OperatorQuestionAssistExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    question_assist_count: int
    domain_hint_count: int
    scope_mission_count: int
    workflow_path_count: int
    agent_behavior_count: int
    action_authority_granted: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _authority_boundary() -> dict[str, bool]:
    return dict(AUTHORITY_BOUNDARY)


def _all_authority_flags_false() -> bool:
    return all(value is False for value in AUTHORITY_BOUNDARY.values())


def _relationship_refs(repo_root: str | Path) -> dict[str, dict[str, Any]]:
    root = Path(repo_root)
    return {
        ref_id: {
            "path": path,
            "present": (root / path).exists(),
        }
        for ref_id, path in RELATIONSHIP_REF_PATHS.items()
    }


def default_question_assists() -> tuple[OperatorQuestionAssist, ...]:
    return (
        OperatorQuestionAssist(
            assist_id="capital_hilton_po_coupa_question_assist",
            question_ref="capital_hilton_po_coupa_help_question",
            workflow_session_ref="capital_hilton_invoice_workflow_session",
            block_ref="po_or_payment_reference",
            world="Finance",
            lane="Capital Hilton",
            question_text="What should OpenClaw try to find about PO / Coupa / payment reference?",
            domain_terms=(
                {
                    "term": "PO",
                    "precise_term": "purchase order",
                    "plain_explanation": "A payment-routing reference that can tell AP how to match or approve the invoice.",
                },
                {
                    "term": "Coupa",
                    "precise_term": "procurement or invoice portal",
                    "plain_explanation": "The possible portal context where a customer may track purchase orders or invoice references.",
                },
                {
                    "term": "payment reference",
                    "precise_term": "AP metadata",
                    "plain_explanation": "A reference that helps the customer route and pay the invoice correctly.",
                },
            ),
            plain_language_explanation=(
                "Keep the real terms visible: PO means purchase order, Coupa is the possible portal context, "
                "and payment reference means the metadata that helps AP route the invoice."
            ),
            why_this_matters="The right reference can prevent payment delay without forcing Winship to manage portal mechanics.",
            valid_answer_types=(
                "PO number",
                "Coupa invoice reference",
                "AP/payment metadata",
                "no known reference",
                "I do not know yet",
            ),
            example_good_answers=("PO 12345", "No PO, use Capital Hilton AP contact metadata", "I do not know; start discovery."),
            common_confusions=(
                "Operator confirmation is not the same as external proof.",
                "A missing PO is not a dead end; it becomes a discovery path.",
            ),
            proof_or_evidence_needed="Proof may be needed before final send or payment-routing claim.",
            if_you_dont_know_options=(
                "Create PO/reference discovery path",
                "Create guided capture path",
                "Ask Cassandra/Clara later",
                "Park as unknown",
            ),
            discovery_path_options=(
                "look_for_po_number_path",
                "look_for_coupa_reference_path",
                "look_for_ap_payment_metadata_path",
            ),
            guided_capture_options=("capital_hilton_create_po_guided_capture_path",),
            agent_assist_options=("cassandra_capital_hilton_po_question_behavior",),
            downstream_effects=(
                "invoice packet reference field may update",
                "proof-needed block may open",
                "approval/send remains locked",
            ),
            authority_boundary=_authority_boundary(),
            next_safe_move="Pick the reference type if known, or choose a discovery/capture path.",
        ),
        OperatorQuestionAssist(
            assist_id="capital_hilton_rate_confirmation_question_assist",
            question_ref="capital_hilton_rate_confirmation_question",
            workflow_session_ref="capital_hilton_invoice_workflow_session",
            block_ref="rate_confirmation",
            world="Finance",
            lane="Capital Hilton",
            question_text="Is $400 per gig still the correct rate?",
            domain_terms=(
                {
                    "term": "rate",
                    "precise_term": "billing rate per performance",
                    "plain_explanation": "The amount used to calculate subtotal for each gig.",
                },
            ),
            plain_language_explanation="The rate stays visible as a finance term, with the simple meaning beside it: dollars per gig.",
            why_this_matters="The rate drives subtotal, but operator confirmation is not the same as outside proof.",
            valid_answer_types=("confirm current rate", "correct rate", "I do not know", "needs proof"),
            example_good_answers=("$400 per gig is right for this invoice", "Use $450 instead", "I need a proof path."),
            common_confusions=("A remembered rate can be useful but may still need proof before final send.",),
            proof_or_evidence_needed="Rate source may be needed before final send or artifact approval.",
            if_you_dont_know_options=("create rate proof discovery path", "ask Cassandra/Clara to clarify", "park rate"),
            discovery_path_options=("rate_proof_discovery_path",),
            guided_capture_options=("rate_source_guided_capture_path",),
            agent_assist_options=("cassandra_rate_confirmation_behavior",),
            downstream_effects=("subtotal preview changes", "invoice artifact preview becomes stale", "approval remains locked"),
            authority_boundary=_authority_boundary(),
            next_safe_move="Confirm, correct, or create a rate proof discovery path.",
        ),
        OperatorQuestionAssist(
            assist_id="legal_contract_domain_question_assist",
            question_ref="legal_contract_clause_help_question",
            workflow_session_ref="legal_contract_review_scope_expansion_mission",
            block_ref="contract_clause_question",
            world="Legal/Guardian",
            lane="Contract Review",
            question_text="What does this clause mean and what should I worry about?",
            domain_terms=(
                {
                    "term": "clause",
                    "precise_term": "contract provision",
                    "plain_explanation": "A specific section of the agreement with obligations or limits.",
                },
                {
                    "term": "risk",
                    "precise_term": "legal or business exposure",
                    "plain_explanation": "Something that may cost money, create obligation, or limit future options.",
                },
            ),
            plain_language_explanation="The system can summarize terms and identify questions, but it does not provide legal advice.",
            why_this_matters="Legal work is high-friction and should become review blocks with Guardian/Hermes gates.",
            valid_answer_types=("summarize clause", "identify risk", "ask Guardian/Hermes", "park for lawyer review"),
            example_good_answers=("Summarize the payment clause", "Flag any termination risk", "Park this for lawyer review."),
            common_confusions=("Explanation is not legal advice.", "Guardian review is not lawyer approval."),
            proof_or_evidence_needed="Source clause reference is needed; raw private bodies remain outside this contract.",
            if_you_dont_know_options=("ask Guardian/Hermes for review", "park for lawyer review", "create question list"),
            discovery_path_options=("legal_clause_question_list_path",),
            guided_capture_options=(),
            agent_assist_options=("guardian_legal_question_behavior", "hermes_legal_question_behavior"),
            downstream_effects=("review checklist may update", "legal action remains blocked", "approval remains unavailable"),
            authority_boundary=_authority_boundary(),
            next_safe_move="Create a review question or park for qualified review; do not treat this as legal advice.",
        ),
        OperatorQuestionAssist(
            assist_id="chief_build_troubleshooting_question_assist",
            question_ref="chief_build_blocker_question",
            workflow_session_ref="check_engine_diagnostic_session",
            block_ref="current_build_blocker",
            world="Build",
            lane="Check Engine",
            question_text="What is blocking the build?",
            domain_terms=(
                {
                    "term": "blocker",
                    "precise_term": "current failure point",
                    "plain_explanation": "The part of the system that stops the next safe validation or build step.",
                },
                {
                    "term": "upstream/downstream",
                    "precise_term": "dependency direction",
                    "plain_explanation": "Like a live-sound signal path: find where the signal first fails before fixing later stages.",
                },
            ),
            plain_language_explanation="Chief can use signal-path language: find the first failure point, show refs, and stop before repair.",
            why_this_matters="Repair can be unsafe without proof, rollback, and a captain decision.",
            valid_answer_types=("show likely blocker", "show proof refs", "create diagnostic block", "park"),
            example_good_answers=("Show the first failing validation", "Create a safe diagnostic block."),
            common_confusions=("A diagnostic summary is not repair execution.",),
            proof_or_evidence_needed="Focused read-model/test refs are needed; no shell or broad scan is granted.",
            if_you_dont_know_options=("ask Chief for concise blocker briefing", "create diagnostic path", "park"),
            discovery_path_options=("chief_safe_diagnostic_block_path",),
            guided_capture_options=(),
            agent_assist_options=("chief_build_question_behavior",),
            downstream_effects=("Shipyard attention may update", "Bridge only sees captain-level decision if needed"),
            authority_boundary=_authority_boundary(),
            next_safe_move="Ask Chief for a blocker briefing from current refs only.",
        ),
        OperatorQuestionAssist(
            assist_id="monthly_client_recap_scope_question_assist",
            question_ref="monthly_client_recap_new_workflow_question",
            workflow_session_ref="monthly_client_recap_scope_expansion_mission",
            block_ref="new_workflow_outline",
            world="Client Delivery",
            lane="Scope Expansion",
            question_text="Can we set up a monthly client recap?",
            domain_terms=(
                {
                    "term": "recap workflow",
                    "precise_term": "repeating client delivery process",
                    "plain_explanation": "A repeatable set of blocks for collecting updates, drafting a recap, reviewing, and sending later.",
                },
            ),
            plain_language_explanation="This is a new mission, not an instant action. The system can propose blocks first.",
            why_this_matters="New work becomes navigable when the system separates known blocks from operator-needed blocks.",
            valid_answer_types=("review proposed blocks", "let system draft first", "park", "ask for scope help"),
            example_good_answers=("Draft the blocks first", "Review it with me", "Park until next week."),
            common_confusions=("Setting up a workflow does not execute it.",),
            proof_or_evidence_needed="Terrain/source refs may help fill client, cadence, deliverables, and send route.",
            if_you_dont_know_options=("create block draft intent", "ask agent to propose scope", "park"),
            discovery_path_options=("client_recap_scope_discovery_path",),
            guided_capture_options=(),
            agent_assist_options=("cassandra_new_workflow_scope_behavior", "niles_project_scope_behavior"),
            downstream_effects=("new block draft may appear", "no send or runtime action occurs"),
            authority_boundary=_authority_boundary(),
            next_safe_move="Choose whether to review proposed blocks together or let the system draft a preview.",
        ),
        OperatorQuestionAssist(
            assist_id="telegram_po_meaning_question_assist",
            question_ref="telegram_what_does_po_mean_question",
            workflow_session_ref="capital_hilton_invoice_workflow_session",
            block_ref="po_or_payment_reference",
            world="Finance",
            lane="Capital Hilton",
            question_text="What does PO mean here?",
            domain_terms=(
                {
                    "term": "PO",
                    "precise_term": "purchase order",
                    "plain_explanation": "A customer-side reference used to approve, route, or match an invoice.",
                },
            ),
            plain_language_explanation="PO stays named as PO, but Cassandra can say it is the customer reference AP may need.",
            why_this_matters="The answer should give Winship choices, not just a definition.",
            valid_answer_types=("Find PO", "Look in existing packets", "Ask AP/contact later", "Park this"),
            example_good_answers=("Find PO", "Park this"),
            common_confusions=("A definition alone is not enough; there should be a workflow path.",),
            proof_or_evidence_needed="Proof is needed only if the workflow later claims a specific reference.",
            if_you_dont_know_options=("look in existing packets", "ask AP/contact later", "park this"),
            discovery_path_options=("telegram_find_po_path", "telegram_existing_packet_lookup_path"),
            guided_capture_options=("capital_hilton_create_po_guided_capture_path",),
            agent_assist_options=("cassandra_telegram_po_help_behavior",),
            downstream_effects=("may create discovery substep", "may create agent packet candidate", "send remains blocked"),
            authority_boundary=_authority_boundary(),
            next_safe_move="Answer compactly and offer Find PO, Look in existing packets, Ask later, or Park.",
        ),
    )


def default_domain_hints() -> tuple[OperatorDomainFamiliarityHint, ...]:
    return (
        OperatorDomainFamiliarityHint(
            hint_id="winship_compact_domain_familiarity_hint",
            operator_ref="Winship",
            strong_domains=(
                "music production",
                "audio engineering",
                "live sound",
                "video production",
                "creative project workflows",
                "Mac/app workflow thinking",
            ),
            context_dependent_domains=("finance/AP/Coupa", "legal process", "security engineering", "backend systems architecture"),
            unfamiliar_or_high_friction_domains=("finance/AP/Coupa", "legal process", "security engineering"),
            preferred_explanation_modes=(
                "cockpit/ship/captain analogy",
                "studio signal-flow analogy",
                "live-show routing analogy",
                "production pipeline analogy",
            ),
            analogy_sources=("ship/bridge", "studio signal flow", "live-show routing", "production pipeline"),
            support_style=(
                "explain jargon without hiding it",
                "do not patronize",
                "offer help me figure this out paths",
                "use familiar-domain analogies only when useful",
                "turn uncertainty into workflow options",
            ),
            include_by_default=True,
            compact_summary=(
                "Winship is strong in music/audio/video/creative and Mac workflow thinking; use compact analogies "
                "for finance, legal, security, or backend complexity only when useful."
            ),
            deeper_support_available=True,
            deeper_support_trigger="Request only when the current question needs more domain support than the compact hint provides.",
            privacy_boundary="This is a compact support hint, not a personal dossier; do not infer hidden preferences.",
            next_safe_move="Carry the compact hint in packets and request deeper support only on demand.",
        ),
    )


def default_scope_missions() -> tuple[OperatorScopeExpansionMission, ...]:
    return (
        OperatorScopeExpansionMission(
            mission_id="monthly_client_recap_scope_expansion_mission",
            title="Monthly Client Recap Workflow",
            originating_question_ref="monthly_client_recap_new_workflow_question",
            target_world="Client Delivery",
            target_lane="Scope Expansion",
            unfamiliar_domain="repeatable client delivery workflow",
            operator_confidence_hint="Operator can review blocks with familiar production-pipeline framing.",
            mission_blocks=("client", "cadence", "source updates", "recap draft", "review", "send approval"),
            system_can_fill_blocks=("candidate cadence from prompt", "known project/client refs if available"),
            operator_needed_blocks=("client identity", "recap tone", "send route", "approval preference"),
            recommended_crew=("Cassandra/Clara", "Niles", "Hermes"),
            question_assist_refs=("monthly_client_recap_scope_question_assist",),
            proof_or_capture_refs=("terrain source refs if available",),
            safety_gates=("approval bus before send", "receipt-backed state writer future lane"),
            suggested_first_move="Review proposed blocks or let the system draft a preview.",
            encouragement_style="calm grounded support, not hype",
            overreach_warning="No workflow execution, send, or state write occurs from this mission draft.",
            next_safe_move="Create a block draft intent preview if the operator chooses to proceed.",
        ),
        OperatorScopeExpansionMission(
            mission_id="legal_contract_review_scope_expansion_mission",
            title="Contract Question Review Mission",
            originating_question_ref="legal_contract_clause_help_question",
            target_world="Legal/Guardian",
            target_lane="Contract Review",
            unfamiliar_domain="legal process",
            operator_confidence_hint="System can summarize terms and organize questions, while preserving legal-review boundaries.",
            mission_blocks=("source clause ref", "plain summary", "risk questions", "Guardian/Hermes review", "lawyer park option"),
            system_can_fill_blocks=("plain terminology explanation", "question checklist"),
            operator_needed_blocks=("source clause selection", "review depth", "park/escalate choice"),
            recommended_crew=("Guardian", "Hermes"),
            question_assist_refs=("legal_contract_domain_question_assist",),
            proof_or_capture_refs=("source clause reference only; raw private body blocked"),
            safety_gates=("legal advice authority false", "Guardian/Hermes review is not lawyer approval"),
            suggested_first_move="Choose summarize, identify risk, ask Guardian/Hermes, or park for lawyer review.",
            encouragement_style="calm support with precise domain terms preserved",
            overreach_warning="No legal advice, approval, or action authority is granted.",
            next_safe_move="Create a review-question path or park safely.",
        ),
    )


COMMON_BLOCKED_ACTIONS = (
    "live execution",
    "receipt/state write",
    "model/tool/MCP/script/hook execution",
    "invoice/email/send action",
    "browser/Coupa/Gmail/Telegram access",
    "legal or financial advice authority",
)


def default_workflow_paths() -> tuple[QuestionAssistWorkflowPath, ...]:
    return (
        QuestionAssistWorkflowPath(
            path_id="look_for_po_number_path",
            assist_ref="capital_hilton_po_coupa_question_assist",
            path_label="Look for PO number",
            path_type="CREATE_DISCOVERY_PATH",
            what_it_does="Creates a proof/reference discovery substep for a purchase order number.",
            operator_input_needed="Confirm that PO lookup is the desired path.",
            system_input_needed="Existing source-card/proof refs if available.",
            agent_support_needed="Cassandra/Clara may prepare a focused discovery packet later.",
            proof_needed="PO proof/reference before final payment-routing claim.",
            creates_discovery_substep=True,
            creates_guided_capture_path=False,
            creates_block_draft_intent=False,
            creates_agent_packet_candidate=True,
            blocked_actions=COMMON_BLOCKED_ACTIONS,
            authority_boundary=_authority_boundary(),
            next_safe_move="Preview discovery substep; do not access Coupa.",
        ),
        QuestionAssistWorkflowPath(
            path_id="look_for_coupa_reference_path",
            assist_ref="capital_hilton_po_coupa_question_assist",
            path_label="Look for Coupa invoice reference",
            path_type="CREATE_DISCOVERY_PATH",
            what_it_does="Creates a discovery substep for existing Coupa/reference metadata.",
            operator_input_needed="Choose this if Coupa/reference context seems relevant.",
            system_input_needed="Existing read-model/source-card refs only.",
            agent_support_needed="Agent packet candidate may ask what evidence exists.",
            proof_needed="Portal reference proof if a specific reference is claimed later.",
            creates_discovery_substep=True,
            creates_guided_capture_path=False,
            creates_block_draft_intent=False,
            creates_agent_packet_candidate=True,
            blocked_actions=COMMON_BLOCKED_ACTIONS,
            authority_boundary=_authority_boundary(),
            next_safe_move="Create a non-executing discovery candidate.",
        ),
        QuestionAssistWorkflowPath(
            path_id="look_for_ap_payment_metadata_path",
            assist_ref="capital_hilton_po_coupa_question_assist",
            path_label="Look for AP/payment metadata",
            path_type="FIND_PROOF",
            what_it_does="Points the workflow toward existing AP/payment metadata references.",
            operator_input_needed="Choose AP/payment metadata as the likely target.",
            system_input_needed="Safe metadata refs already present in read-models.",
            agent_support_needed="Cassandra/Clara can summarize existing refs later.",
            proof_needed="Proof pointer if metadata affects final artifact.",
            creates_discovery_substep=True,
            creates_guided_capture_path=False,
            creates_block_draft_intent=False,
            creates_agent_packet_candidate=True,
            blocked_actions=COMMON_BLOCKED_ACTIONS,
            authority_boundary=_authority_boundary(),
            next_safe_move="Use existing refs only; ask operator if none are present.",
        ),
        QuestionAssistWorkflowPath(
            path_id="capital_hilton_create_po_guided_capture_path",
            assist_ref="capital_hilton_po_coupa_question_assist",
            path_label="Create guided capture path",
            path_type="CREATE_GUIDED_CAPTURE_PATH",
            what_it_does="Creates a future guided capture candidate for a PO/reference screen or source.",
            operator_input_needed="Confirm that guided capture is the desired path.",
            system_input_needed="Target artifact policy from guided capture contract.",
            agent_support_needed="None now; future agent may prepare capture guidance.",
            proof_needed="Protected evidence receipt in a future lane.",
            creates_discovery_substep=False,
            creates_guided_capture_path=True,
            creates_block_draft_intent=False,
            creates_agent_packet_candidate=False,
            blocked_actions=COMMON_BLOCKED_ACTIONS,
            authority_boundary=_authority_boundary(),
            next_safe_move="Model the guided capture path; do not capture files or screenshots.",
        ),
        QuestionAssistWorkflowPath(
            path_id="rate_proof_discovery_path",
            assist_ref="capital_hilton_rate_confirmation_question_assist",
            path_label="Find rate proof",
            path_type="CREATE_DISCOVERY_PATH",
            what_it_does="Creates a discovery substep for the $400/gig rate source.",
            operator_input_needed="Choose proof discovery if the rate is uncertain.",
            system_input_needed="Existing source-card/proof refs if available.",
            agent_support_needed="Cassandra/Clara may prepare rate-proof packet later.",
            proof_needed="Rate source before final send if required by workflow.",
            creates_discovery_substep=True,
            creates_guided_capture_path=False,
            creates_block_draft_intent=False,
            creates_agent_packet_candidate=True,
            blocked_actions=COMMON_BLOCKED_ACTIONS,
            authority_boundary=_authority_boundary(),
            next_safe_move="Open rate proof discovery as preview only.",
        ),
        QuestionAssistWorkflowPath(
            path_id="legal_guardian_review_path",
            assist_ref="legal_contract_domain_question_assist",
            path_label="Ask Guardian/Hermes for review",
            path_type="ESCALATE_TO_GUARDIAN",
            what_it_does="Creates a review path for a legal/contract question without legal advice authority.",
            operator_input_needed="Choose review or park.",
            system_input_needed="Clause/source reference, not raw private body.",
            agent_support_needed="Guardian/Hermes can later prepare a review packet.",
            proof_needed="Source reference and review receipt in future lanes.",
            creates_discovery_substep=False,
            creates_guided_capture_path=False,
            creates_block_draft_intent=True,
            creates_agent_packet_candidate=True,
            blocked_actions=COMMON_BLOCKED_ACTIONS,
            authority_boundary=_authority_boundary(),
            next_safe_move="Create a review draft path; do not provide legal advice.",
        ),
        QuestionAssistWorkflowPath(
            path_id="client_recap_scope_block_draft_path",
            assist_ref="monthly_client_recap_scope_question_assist",
            path_label="Draft monthly recap blocks",
            path_type="CREATE_BLOCK_DRAFT_INTENT",
            what_it_does="Turns a new workflow request into reviewable blocks.",
            operator_input_needed="Confirm whether to review together or let the system draft first.",
            system_input_needed="Existing terrain/client refs if available.",
            agent_support_needed="Cassandra/Niles can propose blocks later.",
            proof_needed="Project/source refs only if the workflow claims existing facts.",
            creates_discovery_substep=False,
            creates_guided_capture_path=False,
            creates_block_draft_intent=True,
            creates_agent_packet_candidate=True,
            blocked_actions=COMMON_BLOCKED_ACTIONS,
            authority_boundary=_authority_boundary(),
            next_safe_move="Create a draft block chain preview.",
        ),
        QuestionAssistWorkflowPath(
            path_id="telegram_find_po_path",
            assist_ref="telegram_po_meaning_question_assist",
            path_label="Find PO",
            path_type="ASK_AGENT_TO_CLARIFY",
            what_it_does="Lets Cassandra answer compactly and offer a focused PO discovery path.",
            operator_input_needed="Tap or say Find PO later.",
            system_input_needed="Same workflow/session/block shape as Mission Control.",
            agent_support_needed="Cassandra can prepare a focused packet later.",
            proof_needed="Proof only if a specific PO is claimed.",
            creates_discovery_substep=True,
            creates_guided_capture_path=False,
            creates_block_draft_intent=False,
            creates_agent_packet_candidate=True,
            blocked_actions=COMMON_BLOCKED_ACTIONS,
            authority_boundary=_authority_boundary(),
            next_safe_move="Offer compact path choices; do not send or access external systems.",
        ),
    )


def default_agent_behaviors() -> tuple[AgentQuestionAssistBehavior, ...]:
    return (
        AgentQuestionAssistBehavior(
            behavior_id="cassandra_telegram_po_help_behavior",
            agent_ref="Cassandra",
            surface="Telegram",
            question_assist_refs=("telegram_po_meaning_question_assist", "capital_hilton_po_coupa_question_assist"),
            domain_hint_refs=("winship_compact_domain_familiarity_hint",),
            compact_context_policy="Use compact domain hint and current workflow block only.",
            when_to_explain="Explain when the operator asks what a term means or a block is unfamiliar.",
            when_to_use_analogy="Use a routing/signal-flow analogy only if it clarifies payment-routing context.",
            when_to_ask_operator="Ask only for the missing block choice: Find PO, Look in packets, Ask later, or Park.",
            when_to_request_deeper_packet="Only when compact hint plus current block is not enough.",
            when_to_stop_and_handoff="Stop before claiming proof, committing truth, sending, or accessing external systems.",
            allowed_response_shapes=("compact explanation", "workflow path choices", "operator question", "agent packet candidate"),
            blocked_response_shapes=("truth commit", "proof complete", "execution done", "send completed", "passive lecture only"),
            next_safe_move="Answer compactly and map uncertainty into a workflow path.",
        ),
        AgentQuestionAssistBehavior(
            behavior_id="chief_build_question_behavior",
            agent_ref="Chief",
            surface="Chief conversation",
            question_assist_refs=("chief_build_troubleshooting_question_assist",),
            domain_hint_refs=("winship_compact_domain_familiarity_hint",),
            compact_context_policy="Use current diagnostic refs only; keep proof below deck.",
            when_to_explain="Explain build blockers when operator asks what is blocking the build.",
            when_to_use_analogy="Use studio signal-flow analogy for upstream/downstream failure only when useful.",
            when_to_ask_operator="Ask only when a captain-level repair or prioritization decision is needed.",
            when_to_request_deeper_packet="Request deeper support only for a focused diagnostic packet.",
            when_to_stop_and_handoff="Stop before shell, repair, cleanup, broad scan, or state write.",
            allowed_response_shapes=("concise blocker briefing", "safe next diagnostic block", "Engineering Contained status"),
            blocked_response_shapes=("repair executed", "shell output from new command", "truth commit", "broad scan summary"),
            next_safe_move="Brief the blocker or stay Engineering Contained.",
        ),
        AgentQuestionAssistBehavior(
            behavior_id="guardian_legal_question_behavior",
            agent_ref="Guardian/Hermes",
            surface="Guardian review",
            question_assist_refs=("legal_contract_domain_question_assist",),
            domain_hint_refs=("winship_compact_domain_familiarity_hint",),
            compact_context_policy="Use precise legal terms plus plain explanation; no personal dossier.",
            when_to_explain="Explain terms when they block an operator decision.",
            when_to_use_analogy="Use analogy only to clarify process, never to replace legal terms.",
            when_to_ask_operator="Ask whether to summarize, identify risk, escalate, or park.",
            when_to_request_deeper_packet="Only when review scope needs a focused packet.",
            when_to_stop_and_handoff="Stop before legal advice, approval, submission, or action.",
            allowed_response_shapes=("review question", "risk checklist", "park option", "Guardian/Hermes review choices"),
            blocked_response_shapes=("legal advice", "approval granted", "contract action executed", "truth commit"),
            next_safe_move="Turn legal uncertainty into review choices with authority false.",
        ),
    )


def starship_operating_model_alignment() -> dict[str, str]:
    return {
        "captain": "Captain should be able to attempt unfamiliar missions with crew support.",
        "bridge": "Bridge should show help only where it aids current work.",
        "worlds": "Worlds contain domain-specific assistance and workflow paths.",
        "crew": "Crew brief and guide, not spam.",
        "engineering": "Engineering/proof remains below deck.",
        "unknowns": "Unknowns become navigable mission blocks.",
        "operating_radius": "The ship expands the captain's practical operating radius.",
    }


def _asdict_items(items: tuple[Any, ...]) -> list[dict[str, Any]]:
    return [asdict(item) for item in items]


def build_operator_question_assist_scope_expansion_contract(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    assists = _asdict_items(default_question_assists())
    hints = _asdict_items(default_domain_hints())
    missions = _asdict_items(default_scope_missions())
    paths = _asdict_items(default_workflow_paths())
    behaviors = _asdict_items(default_agent_behaviors())

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at or utc_now(),
        "north_star": "OpenClaw turns unfamiliar work into navigable missions.",
        "doctrine": {
            "systems_engineering_not_vibes": True,
            "question_help_is_not_passive_tooltip": True,
            "jargon_explained_without_hiding_terms": True,
            "uncertainty_becomes_workflow_paths": True,
            "non_patronizing_support_required": True,
            "no_live_execution": True,
        },
        "operator_question_assist_schema": {
            "structure": "OperatorQuestionAssist",
            "required_fields": list(REQUIRED_QUESTION_ASSIST_FIELDS),
            "help_must_explain_jargon_without_hiding_it": True,
            "help_must_not_be_patronizing": True,
            "help_must_be_more_than_passive_documentation": True,
            "help_me_figure_this_out_becomes_workflow_options": True,
            "supports_mission_control_and_conversation_agents": True,
            "executes_live_search_or_action": False,
        },
        "operator_domain_familiarity_hint_schema": {
            "structure": "OperatorDomainFamiliarityHint",
            "required_fields": list(REQUIRED_DOMAIN_HINT_FIELDS),
            "agents_should_not_assume_ignorance": True,
            "agents_should_not_flood_personal_dossier": True,
            "compact_hints_may_travel_in_packets": True,
            "deeper_support_on_demand_only": True,
            "analogies_clarify_without_replacing_terms": True,
            "jargon_remains_visible_with_explanation": True,
        },
        "operator_scope_expansion_mission_schema": {
            "structure": "OperatorScopeExpansionMission",
            "required_fields": list(REQUIRED_SCOPE_MISSION_FIELDS),
            "unfamiliar_work_becomes_navigable_mission": True,
            "system_breaks_uncertainty_into_blocks": True,
            "system_fills_known_blocks_from_evidence_when_possible": True,
            "operator_asked_only_what_system_cannot_safely_infer": True,
            "risky_domains_include_safety_gates": True,
            "encouragement_calm_grounded_not_hype": True,
        },
        "question_assist_workflow_path_schema": {
            "structure": "QuestionAssistWorkflowPath",
            "required_fields": list(REQUIRED_WORKFLOW_PATH_FIELDS),
            "path_types": list(PATH_TYPES),
            "help_paths_are_selectable_workflow_paths": True,
            "passive_advice_is_not_enough": True,
            "discovery_claims_need_discovery_options": True,
            "all_paths_preview_only_non_executing": True,
        },
        "agent_question_assist_behavior_schema": {
            "structure": "AgentQuestionAssistBehavior",
            "required_fields": list(REQUIRED_AGENT_BEHAVIOR_FIELDS),
            "surfaces": list(SURFACES),
            "agents_explain_conversationally": True,
            "agents_use_compact_domain_hints": True,
            "agents_request_deeper_support_only_when_needed": True,
            "agents_turn_uncertainty_into_block_choices_not_lectures": True,
            "agents_do_not_invent_operator_preferences": True,
            "agents_do_not_commit_truth_or_execute_action": True,
        },
        "path_types": list(PATH_TYPES),
        "surfaces": list(SURFACES),
        "question_assists": assists,
        "question_assists_by_id": {item["assist_id"]: item for item in assists},
        "domain_familiarity_hints": hints,
        "domain_familiarity_hints_by_id": {item["hint_id"]: item for item in hints},
        "scope_expansion_missions": missions,
        "scope_expansion_missions_by_id": {item["mission_id"]: item for item in missions},
        "workflow_paths": paths,
        "workflow_paths_by_id": {item["path_id"]: item for item in paths},
        "agent_behaviors": behaviors,
        "agent_behaviors_by_id": {item["behavior_id"]: item for item in behaviors},
        "relationship_refs": _relationship_refs(repo_root),
        "starship_operating_model_alignment": starship_operating_model_alignment(),
        "authority_boundary": _authority_boundary(),
        "hard_rule": {
            "read_model_only": True,
            "does_not_implement_live_ui": True,
            "does_not_implement_live_telegram": True,
            "does_not_call_agents_or_models": True,
            "does_not_execute_tools": True,
            "does_not_write_receipts": True,
            "does_not_mutate_workflow_state": True,
            "does_not_create_runtime_authority": True,
            "may_grant_authority": False,
        },
        "machine_proof": {
            "operator_question_assist_model_present": True,
            "operator_domain_familiarity_hint_model_present": True,
            "operator_scope_expansion_mission_model_present": True,
            "question_assist_workflow_path_model_present": True,
            "agent_question_assist_behavior_model_present": True,
            "question_assist_count": len(assists),
            "domain_hint_count": len(hints),
            "scope_mission_count": len(missions),
            "workflow_path_count": len(paths),
            "agent_behavior_count": len(behaviors),
            "capital_hilton_po_coupa_help_present": any(
                item["assist_id"] == "capital_hilton_po_coupa_question_assist" for item in assists
            ),
            "rate_confirmation_help_present": any(
                item["assist_id"] == "capital_hilton_rate_confirmation_question_assist" for item in assists
            ),
            "legal_contract_help_present": any(
                item["assist_id"] == "legal_contract_domain_question_assist" for item in assists
            ),
            "chief_build_troubleshooting_help_present": any(
                item["assist_id"] == "chief_build_troubleshooting_question_assist" for item in assists
            ),
            "new_workflow_scope_expansion_present": any(
                item["assist_id"] == "monthly_client_recap_scope_question_assist" for item in assists
            ),
            "telegram_agent_help_present": any(
                item["assist_id"] == "telegram_po_meaning_question_assist" for item in assists
            ),
            "jargon_explained_without_hidden_terms": all(
                item["domain_terms"] and all(term["term"] and term["plain_explanation"] for term in item["domain_terms"])
                for item in assists
            ),
            "help_paths_become_workflow_options": any(
                item["creates_discovery_substep"] or item["creates_guided_capture_path"] or item["creates_block_draft_intent"]
                for item in paths
            ),
            "guided_capture_option_present": any(item["creates_guided_capture_path"] for item in paths),
            "discovery_option_present": any(item["creates_discovery_substep"] for item in paths),
            "block_draft_option_present": any(item["creates_block_draft_intent"] for item in paths),
            "agent_packet_candidate_present": any(item["creates_agent_packet_candidate"] for item in paths),
            "domain_familiarity_hint_compact": all(len(item["compact_summary"]) <= 240 for item in hints),
            "deeper_support_packet_optional_on_demand": all(item["deeper_support_available"] is True for item in hints),
            "agents_cannot_commit_truth_or_execute": all(
                "truth commit" in item["blocked_response_shapes"] and any("execut" in shape for shape in item["blocked_response_shapes"])
                for item in behaviors
            ),
            "all_authority_flags_false": _all_authority_flags_false(),
            "credentials_or_secrets_included": False,
            "raw_private_bodies_included": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_question_assist_markdown(payload: dict[str, Any]) -> str:
    proof = payload["machine_proof"]
    lines = [
        "# Operator Question Assist / Scope Expansion Contract v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        "OpenClaw turns unfamiliar work into navigable missions.",
        "",
        "Smart question assist is not just a tooltip. It explains the question in the moment, keeps the real domain words visible, and offers useful next paths instead of dumping passive advice.",
        "",
        "If a block asks about PO, Coupa, a rate source, a legal clause, or a build blocker, OpenClaw should preserve the real term and put the plain meaning beside it. That means Winship learns the system language without having to pretend the jargon is not there.",
        "",
        "The important shift is that I do not know becomes an actual route: find proof, create a discovery path, prepare guided capture, ask a crew member to clarify, park it safely, or escalate to Guardian/Hermes when the domain is risky.",
        "",
        "This expands what Winship can responsibly attempt. The system breaks unfamiliar work into blocks, fills what it can from existing evidence, and asks only for what it cannot safely infer.",
        "",
        "Agents can use compact familiarity hints so they explain finance, legal, security, or backend complexity without being patronizing. The hint is small: use familiar analogies when useful, keep precise terms visible, and do not turn the operator into a personal dossier.",
        "",
        "Telegram and Mission Control can render the same help state. Cassandra can answer what PO means with useful path choices, while Mission Control can show the same choices beside the block.",
        "",
        "A calm ship that expands what the captain can responsibly attempt.",
        "",
        "There is no live authority yet. No model call, agent action, search, receipt write, workflow mutation, invoice generation, send, portal access, or legal/financial advice authority exists in this contract.",
        "",
        "## Examples",
        "",
        "- Capital Hilton PO/Coupa: explains PO, Coupa, and payment reference; offers find PO, find Coupa reference, AP metadata, guided capture, ask Cassandra/Clara, or park.",
        "- Rate confirmation: explains that the rate drives subtotal, but confirmation is not external proof; offers proof discovery if unsure.",
        "- Legal/contract: explains terms without pretending to give legal advice; offers summarize, risk checklist, Guardian/Hermes review, or lawyer-review park.",
        "- Chief/build: uses signal-path framing when useful; returns likely blocker, proof refs, or safe diagnostic block with no shell/repair execution.",
        "- New workflow: turns monthly client recap into proposed blocks and a preview path, not execution.",
        "- Telegram agent help: Cassandra answers compactly with path choices, not passive-only explanation.",
        "",
        "## Machine Proof Summary",
        "",
        f"- Question assists: `{proof['question_assist_count']}`.",
        f"- Domain hints: `{proof['domain_hint_count']}`.",
        f"- Scope missions: `{proof['scope_mission_count']}`.",
        f"- Workflow paths: `{proof['workflow_path_count']}`.",
        f"- Agent behaviors: `{proof['agent_behavior_count']}`.",
        f"- Jargon explained without hidden terms: `{str(proof['jargon_explained_without_hidden_terms']).lower()}`.",
        f"- Help paths become workflow options: `{str(proof['help_paths_become_workflow_options']).lower()}`.",
        f"- All authority flags false: `{str(proof['all_authority_flags_false']).lower()}`.",
        f"- Content hash: `{proof['content_hash']}`.",
    ]
    return "\n".join(lines) + "\n"


def export_operator_question_assist_scope_expansion_contract(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> OperatorQuestionAssistExportResult:
    repo_root = Path(repo_root)
    export_path = repo_root / export_root
    export_path.mkdir(parents=True, exist_ok=True)
    payload = build_operator_question_assist_scope_expansion_contract(repo_root=repo_root, generated_at=generated_at)
    json_path = export_path / JSON_EXPORT_NAME
    operator_path = export_path / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_question_assist_markdown(payload), encoding="utf-8")
    proof = payload["machine_proof"]
    return OperatorQuestionAssistExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        question_assist_count=proof["question_assist_count"],
        domain_hint_count=proof["domain_hint_count"],
        scope_mission_count=proof["scope_mission_count"],
        workflow_path_count=proof["workflow_path_count"],
        agent_behavior_count=proof["agent_behavior_count"],
        action_authority_granted=not proof["all_authority_flags_false"],
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export Operator Question Assist / Scope Expansion Contract v0.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    parser.add_argument("--generated-at", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    result = export_operator_question_assist_scope_expansion_contract(
        repo_root=args.repo_root,
        export_root=args.export_root,
        generated_at=args.generated_at,
    )
    if args.format == "json":
        print(stable_json(asdict(result)), end="")
    else:
        print(f"schema_version={result.schema_version}")
        print(f"json_path={result.json_path}")
        print(f"operator_path={result.operator_path}")
        print(f"question_assist_count={result.question_assist_count}")
        print(f"domain_hint_count={result.domain_hint_count}")
        print(f"scope_mission_count={result.scope_mission_count}")
        print(f"workflow_path_count={result.workflow_path_count}")
        print(f"agent_behavior_count={result.agent_behavior_count}")
        print(f"action_authority_granted={str(result.action_authority_granted).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
