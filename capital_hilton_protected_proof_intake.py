"""Capital Hilton Protected Proof Intake v0 for OpenClaw.

This read-model turns the Capital Hilton missing-proof posture into bounded
proof-intake questions, answer candidates, protected evidence requirements,
Guardian gates, and quieting rules. It is metadata only: no Coupa, browser,
Gmail/calendar, account, credential, invoice, ledger, email, tool, agent,
model, queue, runtime, network, Mac sync/import, or Mission Control app action
is created.
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

SCHEMA_VERSION = "capital_hilton_protected_proof_intake_v0"
JSON_EXPORT_NAME = "capital_hilton_protected_proof_intake.json"
OPERATOR_EXPORT_NAME = "capital_hilton_protected_proof_intake_OPERATOR.md"

PROOF_STATUSES = (
    "MISSING",
    "CANDIDATE_ONLY",
    "OPERATOR_MEMORY_ONLY",
    "PROTECTED_REFERENCE_REQUIRED",
    "SOURCE_CARD_REQUIRED",
    "RECEIPT_REQUIRED",
    "PROOF_METADATA_LINKED",
    "RESOLVED_QUIET",
    "REJECTED_OR_OBSOLETE",
    "UNKNOWN_FAIL_CLOSED",
)

ALLOWED_ANSWER_MODALITIES = (
    "text_answer",
    "yes_no",
    "structured_form",
    "screenshot_reference",
    "file_reference",
    "source_card_reference",
    "protected_evidence_reference",
    "receipt_reference",
    "i_dont_know",
    "park_this",
    "needs_discovery",
    "reject_obsolete",
)

ANSWER_STATUSES = (
    "UNANSWERED",
    "ANSWER_CAPTURED_MEMORY_CANDIDATE",
    "ANSWER_POINTS_TO_PROTECTED_REFERENCE",
    "ANSWER_POINTS_TO_SOURCE_CARD",
    "ANSWER_POINTS_TO_RECEIPT",
    "ANSWER_STILL_NEEDS_PROOF",
    "ANSWER_REJECTS_CANDIDATE",
    "ANSWER_PARKS_ITEM",
    "UNKNOWN_FAIL_CLOSED",
)

PROTECTED_SURFACES = (
    "excel_workbook_reference",
    "pdf_invoice_reference",
    "coupa_reference_metadata",
    "email_or_ap_route_metadata",
    "contract_or_rate_source_reference",
    "payment_or_po_reference_metadata",
)

NO_AUTHORITY_FLAGS = {
    "coupa_access_allowed": False,
    "browser_oauth_allowed": False,
    "gmail_calendar_access_allowed": False,
    "email_account_access_allowed": False,
    "account_access_allowed": False,
    "credential_handling_allowed": False,
    "excel_raw_body_ingestion_allowed": False,
    "raw_finance_body_ingestion_allowed": False,
    "raw_private_body_ingestion_allowed": False,
    "invoice_generation_allowed": False,
    "send_submit_approval_allowed": False,
    "ledger_write_allowed": False,
    "email_dispatch_allowed": False,
    "model_call_allowed": False,
    "model_api_execution_allowed": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "queue_execution_allowed": False,
    "runtime_dispatch_allowed": False,
    "planner_builder_execution_allowed": False,
    "network_operation_allowed": False,
    "mac_sync_or_import_triggered": False,
    "mission_control_app_changes_included": False,
    "repo_b_mutation_allowed": False,
    "repo_b_body_inspection_allowed": False,
    "file_move_allowed": False,
    "file_delete_allowed": False,
    "automatic_activation_allowed": False,
    "automatic_cross_off_allowed": False,
}

BLOCKED_ACTIONS = (
    "Coupa access",
    "browser/OAuth/account access",
    "credential/token/cookie/API key handling",
    "Gmail/calendar/email account access",
    "raw Excel body ingestion",
    "raw PDF body ingestion",
    "raw email body ingestion",
    "raw finance/private body ingestion",
    "invoice generation",
    "ledger write",
    "email dispatch",
    "send/submit/approval",
    "live model call",
    "agent activation",
    "tool execution",
    "queue/autonomy",
)

SHARED_FIX_PATH_ID = "protected_finance_proof_metadata_intake"


@dataclass(frozen=True)
class CapitalHiltonProofIntakeItem:
    proof_item_id: str
    display_name: str
    eliwinship_question: str
    why_it_matters: str
    proof_class: str
    candidate_value: Any
    proof_status: str
    protected_proof_required: bool
    allowed_answer_modalities: list[str]
    operator_answer_becomes: str
    protected_evidence_reference_required: bool
    guardian_gate_required: bool
    operator_confirmation_required: bool
    source_card_required: bool
    receipt_required: bool
    what_would_satisfy_this: list[str]
    what_would_not_satisfy_this: list[str]
    quiet_condition: str
    blocked_actions: list[str]
    next_safe_move: str


@dataclass(frozen=True)
class CapitalHiltonOperatorAnswerCandidate:
    answer_candidate_id: str
    proof_item_id: str
    question_text: str
    answer_modality: str
    answer_status: str
    memory_candidate_required: bool
    proof_metadata_required: bool
    protected_reference_required: bool
    guardian_gate_required: bool
    operator_review_required: bool
    can_quiet_question: bool
    can_satisfy_proof: bool
    next_safe_move: str


@dataclass(frozen=True)
class CapitalHiltonProtectedEvidenceRequirement:
    protected_requirement_id: str
    proof_item_id: str
    protected_surface: str
    allowed_reference_shape: str
    raw_body_allowed: bool
    metadata_only: bool
    redaction_required: bool
    hash_or_receipt_required: bool
    guardian_gate_required: bool
    operator_final_authority_required: bool
    blocked_material: list[str]
    next_safe_move: str


@dataclass(frozen=True)
class CapitalHiltonGuardianGateRequirement:
    gate_id: str
    proof_item_ids: list[str]
    gate_reason: str
    sensitivity_class: str
    redaction_required: bool
    allowed_output: list[str]
    blocked_output: list[str]
    operator_review_required: bool
    next_safe_move: str


@dataclass(frozen=True)
class CapitalHiltonProofQuietingRule:
    proof_item_id: str
    current_attention_state: str
    quiet_condition: str
    if_answered_without_proof: str
    if_proof_metadata_linked: str
    if_rejected_or_obsolete: str
    promotion_destination: str
    attention_class: str
    next_safe_move: str


@dataclass(frozen=True)
class CapitalHiltonProtectedProofIntakeExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    proof_intake_item_count: int
    missing_proof_count: int
    protected_proof_required: bool
    action_authority_granted: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clone = dict(payload)
    machine = dict(clone.get("machine_proof", {}))
    machine["content_hash"] = None
    clone["machine_proof"] = machine
    return hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _item(
    proof_item_id: str,
    display_name: str,
    question: str,
    why: str,
    proof_class: str,
    candidate_value: Any,
    proof_status: str,
    *,
    protected: bool,
    source_card: bool,
    receipt: bool,
    satisfies: list[str],
    not_enough: list[str],
    quiet: str,
) -> CapitalHiltonProofIntakeItem:
    return CapitalHiltonProofIntakeItem(
        proof_item_id=proof_item_id,
        display_name=display_name,
        eliwinship_question=question,
        why_it_matters=why,
        proof_class=proof_class,
        candidate_value=candidate_value,
        proof_status=proof_status,
        protected_proof_required=protected,
        allowed_answer_modalities=list(ALLOWED_ANSWER_MODALITIES),
        operator_answer_becomes="memory_candidate_receipt_unless_linked_to_proof_metadata",
        protected_evidence_reference_required=protected,
        guardian_gate_required=protected,
        operator_confirmation_required=True,
        source_card_required=source_card,
        receipt_required=receipt,
        what_would_satisfy_this=satisfies,
        what_would_not_satisfy_this=not_enough,
        quiet_condition=quiet,
        blocked_actions=list(BLOCKED_ACTIONS),
        next_safe_move=SHARED_FIX_PATH_ID,
    )


def build_proof_intake_items() -> list[CapitalHiltonProofIntakeItem]:
    return [
        _item(
            "performance_date_2026_05_08_proof",
            "May 8 performance proof",
            "Can we point to protected proof that the May 8, 2026 Capital Hilton performance happened?",
            "A future invoice packet cannot treat the May 8 service date as billable until a protected source reference or receipt backs it.",
            "performance_date",
            "2026-05-08",
            "PROTECTED_REFERENCE_REQUIRED",
            protected=True,
            source_card=True,
            receipt=True,
            satisfies=[
                "protected evidence reference for the May 8 performance",
                "approved source-card metadata with a receipt",
                "Guardian-reviewed calendar, contract, AP, or event proof metadata",
            ],
            not_enough=[
                "operator memory alone",
                "a raw email/calendar body",
                "a candidate date copied from an old packet without a receipt",
            ],
            quiet="Quiet only after protected proof metadata or a valid rejected/obsolete receipt is linked.",
        ),
        _item(
            "performance_date_2026_05_15_proof",
            "May 15 performance proof",
            "Can we point to protected proof that the May 15, 2026 Capital Hilton performance happened?",
            "The second service date affects subtotal, one-invoice posture, and whether the lane can move toward Finance.",
            "performance_date",
            "2026-05-15",
            "PROTECTED_REFERENCE_REQUIRED",
            protected=True,
            source_card=True,
            receipt=True,
            satisfies=[
                "protected evidence reference for the May 15 performance",
                "approved source-card metadata with a receipt",
                "Guardian-reviewed calendar, contract, AP, or event proof metadata",
            ],
            not_enough=[
                "operator memory alone",
                "a raw email/calendar body",
                "a candidate date copied from an old packet without a receipt",
            ],
            quiet="Quiet only after protected proof metadata or a valid rejected/obsolete receipt is linked.",
        ),
        _item(
            "rate_400_per_gig_proof",
            "Rate proof",
            "Can we point to proof that the agreed rate was $400 per gig?",
            "The rate drives the invoice math and must be source-backed before any future invoice generation can be considered.",
            "rate",
            "$400 per gig",
            "PROTECTED_REFERENCE_REQUIRED",
            protected=True,
            source_card=True,
            receipt=True,
            satisfies=[
                "contract/rate source-card metadata",
                "protected reference to a rate agreement",
                "Guardian-reviewed AP or packet metadata that states the rate",
            ],
            not_enough=[
                "operator memory alone",
                "raw contract/email text",
                "a candidate rate without source metadata",
            ],
            quiet="Quiet only after rate proof metadata is linked or the candidate rate is rejected with a receipt.",
        ),
        _item(
            "subtotal_800_proof",
            "Subtotal math proof",
            "Can deterministic math prove 2 gigs x $400 = $800 from accepted source facts?",
            "The subtotal can be proven by deterministic math only after the date count and rate are accepted source facts.",
            "deterministic_math",
            "$800",
            "RECEIPT_REQUIRED",
            protected=False,
            source_card=False,
            receipt=True,
            satisfies=[
                "deterministic math receipt using two accepted performance dates and accepted $400 rate",
                "receipt showing source fact refs used for the calculation",
            ],
            not_enough=[
                "operator says the subtotal is $800",
                "math based on candidate-only facts",
                "raw spreadsheet body",
            ],
            quiet="Quiet after a deterministic math receipt links accepted date and rate proof.",
        ),
        _item(
            "one_invoice_posture_proof",
            "One-invoice posture proof",
            "Should these two dates be billed together on one invoice, and what proof supports that?",
            "Invoice shape affects future packet generation and must not be inferred from convenience alone.",
            "invoice_posture",
            "candidate one-invoice posture",
            "SOURCE_CARD_REQUIRED",
            protected=True,
            source_card=True,
            receipt=True,
            satisfies=[
                "source-card or AP instruction metadata supporting one invoice",
                "operator answer plus source/protected reference",
                "receipt rejecting one-invoice posture if it is wrong",
            ],
            not_enough=[
                "operator preference without source context",
                "implicit grouping because dates are close together",
                "raw AP/email body",
            ],
            quiet="Quiet after one-invoice posture is source-backed, parked with reason, or rejected with receipt.",
        ),
        _item(
            "coupa_po_payment_reference_metadata",
            "Coupa/PO/payment reference metadata",
            "Is there a Coupa, PO, payment, or reference number that needs to appear on the invoice packet?",
            "A future invoice packet may need a PO or payment reference, but Coupa/account access is blocked now.",
            "protected_finance_reference",
            None,
            "PROTECTED_REFERENCE_REQUIRED",
            protected=True,
            source_card=True,
            receipt=True,
            satisfies=[
                "metadata-only Coupa/PO/payment reference",
                "Guardian-reviewed protected evidence reference",
                "receipt that no PO/payment reference is needed",
            ],
            not_enough=[
                "Coupa login/session data",
                "raw portal screenshot body",
                "guessing no reference is needed",
            ],
            quiet="Quiet after protected metadata identifies the reference or a receipt states none is required.",
        ),
        _item(
            "excel_workbook_or_invoice_source_reference",
            "Workbook/source artifact reference",
            "Is there an Excel workbook, invoice template, or source artifact that should be referenced without ingesting the raw body?",
            "Workbook or invoice-template context can guide future packet shape, but raw spreadsheet/PDF body ingestion is blocked.",
            "source_artifact_reference",
            None,
            "SOURCE_CARD_REQUIRED",
            protected=True,
            source_card=True,
            receipt=True,
            satisfies=[
                "metadata-only file/source-card reference",
                "hash or receipt for the artifact reference",
                "Guardian-reviewed redaction posture",
            ],
            not_enough=[
                "raw workbook cells",
                "raw PDF body",
                "unscoped filename memory without receipt",
            ],
            quiet="Quiet after source artifact metadata is linked or the artifact is rejected as irrelevant with a receipt.",
        ),
        _item(
            "ap_recipient_route_metadata",
            "AP route metadata",
            "What is the approved AP route or recipient path, without sending anything yet?",
            "Recipient route affects future send/submit decisions, which remain blocked until explicit future authority exists.",
            "ap_route_metadata",
            None,
            "PROTECTED_REFERENCE_REQUIRED",
            protected=True,
            source_card=True,
            receipt=True,
            satisfies=[
                "metadata-only AP route/source-card",
                "protected recipient route reference",
                "receipt that route is unknown and needs discovery",
            ],
            not_enough=[
                "raw email body",
                "account access",
                "email dispatch",
                "operator memory without source reference",
            ],
            quiet="Quiet after the AP route is protected-metadata linked, parked for discovery, or rejected with reason.",
        ),
        _item(
            "tax_vendor_handling_metadata",
            "Tax/vendor/payment handling metadata",
            "Are there tax, vendor, W-9, entity, or payment-handling details that affect the invoice packet?",
            "Tax/vendor/payment handling may change packet requirements and requires protected metadata boundaries.",
            "tax_vendor_payment_metadata",
            None,
            "PROTECTED_REFERENCE_REQUIRED",
            protected=True,
            source_card=True,
            receipt=True,
            satisfies=[
                "metadata-only vendor/tax/payment handling reference",
                "Guardian-reviewed protected reference",
                "receipt that this detail is not needed for the packet",
            ],
            not_enough=[
                "bank/check/remit raw data",
                "credentials or account data",
                "operator memory without a protected reference",
            ],
            quiet="Quiet after protected metadata resolves relevance or a rejection/obsolete receipt is linked.",
        ),
        _item(
            "future_invoice_generation_receipt_requirement",
            "Future invoice receipt requirement",
            "What receipt would prove a future invoice was generated correctly, if invoice generation is ever approved later?",
            "Even if future invoice generation is approved, it needs a deterministic receipt shape before any action lane can run.",
            "future_action_receipt",
            None,
            "RECEIPT_REQUIRED",
            protected=False,
            source_card=False,
            receipt=True,
            satisfies=[
                "future invoice generation receipt contract",
                "source fact refs, math refs, artifact hash, operator/Guardian gates, and blocked send status",
                "Security Delta or Security Repass approval for any future action class",
            ],
            not_enough=[
                "a generated invoice file alone",
                "an operator statement that it looks right",
                "send/submit/approval proof because those actions are blocked now",
            ],
            quiet="Quiet only as a future receipt requirement; it does not authorize invoice generation.",
        ),
    ]


def build_answer_candidates(items: list[CapitalHiltonProofIntakeItem]) -> list[CapitalHiltonOperatorAnswerCandidate]:
    candidates: list[CapitalHiltonOperatorAnswerCandidate] = []
    for item in items:
        candidates.append(
            CapitalHiltonOperatorAnswerCandidate(
                answer_candidate_id=f"{item.proof_item_id}_answer_candidate",
                proof_item_id=item.proof_item_id,
                question_text=item.eliwinship_question,
                answer_modality="structured_form",
                answer_status="UNANSWERED",
                memory_candidate_required=True,
                proof_metadata_required=True,
                protected_reference_required=item.protected_evidence_reference_required,
                guardian_gate_required=item.guardian_gate_required,
                operator_review_required=True,
                can_quiet_question=False,
                can_satisfy_proof=False,
                next_safe_move=(
                    "Capture answer as a Memory Candidate Receipt; link protected/source/receipt refs separately."
                ),
            )
        )
    return candidates


def build_protected_evidence_requirements() -> list[CapitalHiltonProtectedEvidenceRequirement]:
    blocked_material = [
        "raw Excel body",
        "raw PDF body",
        "raw email body",
        "credentials",
        "OAuth/session cookies",
        "bank/check/remit data unless protected-reference only",
        "Coupa login/session data",
        "customer/private content not needed for metadata",
    ]
    return [
        CapitalHiltonProtectedEvidenceRequirement(
            protected_requirement_id="excel_workbook_reference_requirement",
            proof_item_id="excel_workbook_or_invoice_source_reference",
            protected_surface="excel_workbook_reference",
            allowed_reference_shape="metadata-only filename/source-card/hash/receipt reference; no cells or formulas",
            raw_body_allowed=False,
            metadata_only=True,
            redaction_required=True,
            hash_or_receipt_required=True,
            guardian_gate_required=True,
            operator_final_authority_required=True,
            blocked_material=blocked_material,
            next_safe_move="create protected evidence reference metadata",
        ),
        CapitalHiltonProtectedEvidenceRequirement(
            protected_requirement_id="pdf_invoice_reference_requirement",
            proof_item_id="future_invoice_generation_receipt_requirement",
            protected_surface="pdf_invoice_reference",
            allowed_reference_shape="future metadata-only PDF artifact hash/receipt after authority exists",
            raw_body_allowed=False,
            metadata_only=True,
            redaction_required=True,
            hash_or_receipt_required=True,
            guardian_gate_required=True,
            operator_final_authority_required=True,
            blocked_material=blocked_material,
            next_safe_move="park until invoice generation authority exists",
        ),
        CapitalHiltonProtectedEvidenceRequirement(
            protected_requirement_id="coupa_reference_metadata_requirement",
            proof_item_id="coupa_po_payment_reference_metadata",
            protected_surface="coupa_reference_metadata",
            allowed_reference_shape="PO/payment/reference number metadata only; no portal session",
            raw_body_allowed=False,
            metadata_only=True,
            redaction_required=True,
            hash_or_receipt_required=True,
            guardian_gate_required=True,
            operator_final_authority_required=True,
            blocked_material=blocked_material,
            next_safe_move="record Coupa/PO metadata only after Guardian gate",
        ),
        CapitalHiltonProtectedEvidenceRequirement(
            protected_requirement_id="email_or_ap_route_metadata_requirement",
            proof_item_id="ap_recipient_route_metadata",
            protected_surface="email_or_ap_route_metadata",
            allowed_reference_shape="AP route metadata/source-card; no email account access or body",
            raw_body_allowed=False,
            metadata_only=True,
            redaction_required=True,
            hash_or_receipt_required=True,
            guardian_gate_required=True,
            operator_final_authority_required=True,
            blocked_material=blocked_material,
            next_safe_move="capture AP route as protected metadata or park for discovery",
        ),
        CapitalHiltonProtectedEvidenceRequirement(
            protected_requirement_id="contract_or_rate_source_reference_requirement",
            proof_item_id="rate_400_per_gig_proof",
            protected_surface="contract_or_rate_source_reference",
            allowed_reference_shape="rate source-card/protected reference metadata only",
            raw_body_allowed=False,
            metadata_only=True,
            redaction_required=True,
            hash_or_receipt_required=True,
            guardian_gate_required=True,
            operator_final_authority_required=True,
            blocked_material=blocked_material,
            next_safe_move="link rate proof metadata before subtotal proof",
        ),
        CapitalHiltonProtectedEvidenceRequirement(
            protected_requirement_id="payment_or_po_reference_metadata_requirement",
            proof_item_id="tax_vendor_handling_metadata",
            protected_surface="payment_or_po_reference_metadata",
            allowed_reference_shape="vendor/tax/payment handling metadata only; no bank/remit body",
            raw_body_allowed=False,
            metadata_only=True,
            redaction_required=True,
            hash_or_receipt_required=True,
            guardian_gate_required=True,
            operator_final_authority_required=True,
            blocked_material=blocked_material,
            next_safe_move="classify protected finance metadata before any future packet action",
        ),
    ]


def build_guardian_gates() -> list[CapitalHiltonGuardianGateRequirement]:
    return [
        CapitalHiltonGuardianGateRequirement(
            gate_id="protected_finance_metadata_gate",
            proof_item_ids=[
                "performance_date_2026_05_08_proof",
                "performance_date_2026_05_15_proof",
                "rate_400_per_gig_proof",
                "one_invoice_posture_proof",
                "excel_workbook_or_invoice_source_reference",
            ],
            gate_reason="Capital Hilton proof references may contain protected finance/client material.",
            sensitivity_class="protected_finance_metadata",
            redaction_required=True,
            allowed_output=["metadata-only source refs", "redaction posture", "receipt refs"],
            blocked_output=["raw finance bodies", "account/session data", "invoice/send controls"],
            operator_review_required=True,
            next_safe_move="Guardian reviews metadata shape before promotion.",
        ),
        CapitalHiltonGuardianGateRequirement(
            gate_id="coupa_reference_metadata_gate",
            proof_item_ids=["coupa_po_payment_reference_metadata"],
            gate_reason="Coupa/PO data must remain metadata-only and cannot imply portal access.",
            sensitivity_class="account_finance_reference",
            redaction_required=True,
            allowed_output=["PO/reference metadata", "source-card refs", "receipt refs"],
            blocked_output=["Coupa login/session data", "browser/OAuth", "credential material"],
            operator_review_required=True,
            next_safe_move="Capture only scoped reference metadata.",
        ),
        CapitalHiltonGuardianGateRequirement(
            gate_id="ap_route_or_email_metadata_gate",
            proof_item_ids=["ap_recipient_route_metadata"],
            gate_reason="AP route may involve private recipient or email metadata.",
            sensitivity_class="private_route_metadata",
            redaction_required=True,
            allowed_output=["route metadata", "source-card refs", "receipt refs"],
            blocked_output=["raw email body", "mailbox access", "send action"],
            operator_review_required=True,
            next_safe_move="Classify route metadata without account access.",
        ),
        CapitalHiltonGuardianGateRequirement(
            gate_id="tax_vendor_payment_handling_gate",
            proof_item_ids=["tax_vendor_handling_metadata"],
            gate_reason="Tax/vendor/payment handling can involve sensitive entity and payment details.",
            sensitivity_class="tax_vendor_payment_metadata",
            redaction_required=True,
            allowed_output=["metadata-only classification", "protected reference refs", "receipt refs"],
            blocked_output=["bank/check/remit bodies", "tax forms body", "account credentials"],
            operator_review_required=True,
            next_safe_move="Keep protected finance metadata scoped and receipted.",
        ),
        CapitalHiltonGuardianGateRequirement(
            gate_id="future_invoice_generation_gate",
            proof_item_ids=["future_invoice_generation_receipt_requirement"],
            gate_reason="Future invoice generation remains blocked until security and action authority exist.",
            sensitivity_class="future_finance_action",
            redaction_required=True,
            allowed_output=["future receipt requirements", "blocked-action posture", "gate list", "receipt refs"],
            blocked_output=["invoice generation", "ledger write", "send/submit/approval"],
            operator_review_required=True,
            next_safe_move="Route future action request to Security Delta or Security Repass.",
        ),
    ]


def build_quieting_rules(items: list[CapitalHiltonProofIntakeItem]) -> list[CapitalHiltonProofQuietingRule]:
    rules: list[CapitalHiltonProofQuietingRule] = []
    for item in items:
        rules.append(
            CapitalHiltonProofQuietingRule(
                proof_item_id=item.proof_item_id,
                current_attention_state="NEEDS_PROOF",
                quiet_condition=item.quiet_condition,
                if_answered_without_proof="Convert to proof-needed or memory-candidate state; do not quiet as proven.",
                if_proof_metadata_linked="Promote to quiet-with-proof candidate through protected_finance_proof_metadata_intake.",
                if_rejected_or_obsolete="Quiet only with reason, source ref, and rejection/obsolete receipt.",
                promotion_destination=SHARED_FIX_PATH_ID,
                attention_class="NEEDS_PROOF",
                next_safe_move=SHARED_FIX_PATH_ID,
            )
        )
    return rules


def build_capital_hilton_protected_proof_intake(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    del repo_root
    generated_at = generated_at or utc_now()
    items = build_proof_intake_items()
    answer_candidates = build_answer_candidates(items)
    protected_requirements = build_protected_evidence_requirements()
    guardian_gates = build_guardian_gates()
    quieting_rules = build_quieting_rules(items)
    candidate_facts = {
        "target_world": "Finance",
        "current_phase": "HELM_THRESHOLD_LANE",
        "lane_destiny": "MOVE_TO_WORLD_ACTION",
        "missing_proof_count": 10,
        "protected_proof_required": True,
        "candidate_completed_dates": ["2026-05-08", "2026-05-15"],
        "candidate_rate": "$400 per gig",
        "candidate_subtotal": "$800",
        "candidate_one_invoice_posture": True,
        "candidate_facts_proven": False,
        "action_authority_granted": False,
    }
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": "capital_hilton_protected_proof_intake",
        "contract_id": "capital_hilton_protected_proof_intake_v0",
        "generated_at": generated_at,
        **NO_AUTHORITY_FLAGS,
        "contract_status": "deterministic_protected_proof_intake_metadata_only",
        "operator_summary": (
            "Capital Hilton has ten missing proof items. This contract asks bounded "
            "ELIWINSHIP questions, records answers as memory candidates unless they "
            "link to proof metadata, and keeps all finance/account/action authority blocked."
        ),
        "core_doctrine": {
            "operator_answers_are_not_proof": True,
            "protected_files_are_not_ingested": True,
            "raw_finance_bodies_are_not_stored": True,
            "source_or_proof_references_may_be_requested": True,
            "protected_proof_metadata_requirements_may_be_recorded": True,
            "quieting_conditions_may_be_defined": True,
            "coupa_browser_gmail_calendar_excel_credentials_invoice_ledger_email_access_blocked": True,
        },
        "capital_hilton_current_facts": candidate_facts,
        "proof_statuses": list(PROOF_STATUSES),
        "allowed_answer_modalities": list(ALLOWED_ANSWER_MODALITIES),
        "answer_statuses": list(ANSWER_STATUSES),
        "protected_surfaces": list(PROTECTED_SURFACES),
        "proof_intake_items": [asdict(item) for item in items],
        "operator_answer_candidates": [asdict(candidate) for candidate in answer_candidates],
        "protected_evidence_requirements": [asdict(requirement) for requirement in protected_requirements],
        "guardian_gate_requirements": [asdict(gate) for gate in guardian_gates],
        "proof_quieting_rules": [asdict(rule) for rule in quieting_rules],
        "shared_fix_path": {
            "fix_path_id": SHARED_FIX_PATH_ID,
            "display_name": "Protected Finance Proof Metadata Intake",
            "linked_lanes": ["Capital Hilton", "Cassandra", "Finance World", "Guardian gate", "Package Preview"],
            "solving_once_can_update_multiple_lanes": True,
            "execution_allowed": False,
            "requires_receipts_and_gates_before_any_future_promotion": True,
        },
        "operator_answer_capture_policy": {
            "text_answers_can_clarify": True,
            "text_answers_can_prove": False,
            "operator_answers_become": "Memory Candidate Receipts",
            "screenshot_file_source_card_or_protected_reference_can_point_toward_proof": True,
            "sensitive_reference_requires_guardian_review": True,
            "answers_can_trigger_invoice_generation": False,
            "answers_can_trigger_send_submit_approval": False,
            "answers_can_trigger_browser_or_account_access": False,
        },
        "quieting_policy": {
            "answered_without_proof_quiets_item": False,
            "protected_proof_metadata_linked_can_quiet": True,
            "valid_rejected_or_obsolete_receipt_can_quiet": True,
            "future_invoice_action_remains_blocked": True,
            "shared_fix_path": SHARED_FIX_PATH_ID,
        },
        "authority_boundary": {
            **NO_AUTHORITY_FLAGS,
            "all_authority_flags_false": all(value is False for value in NO_AUTHORITY_FLAGS.values()),
            "blocked_actions": list(BLOCKED_ACTIONS),
            "valid_current_actions": [
                "read-model export",
                "operator markdown digest",
                "proof-intake question display",
                "metadata-only protected evidence requirement display",
                "Guardian gate requirement display",
                "quieting rule display",
            ],
        },
        "source_contract_refs": [
            "generated/read_models/capital_hilton_proof_metadata_packet.json",
            "generated/read_models/security_pass_contract.json",
            "generated/read_models/security_audit_readiness_packet.json",
            "generated/read_models/operator_attention_promotion_contract.json",
            "generated/read_models/chief_test_harness_cross_off_receipt_contract.json",
            "generated/read_models/memory_candidate_receipt_contract.json",
            "generated/read_models/protected_evidence_reference_receipt.json",
            "generated/read_models/package_preview_receipt_contract.json",
            "generated/read_models/tool_adapter_receipt_contract.json",
        ],
        "stable_map_integration": {
            "summary_included_in_stable_map_now": False,
            "reason": "stable map refresh is a separate lane",
            "safe_summary_for_next_refresh": {
                "contract_id": "capital_hilton_protected_proof_intake_v0",
                "proof_item_count": len(items),
                "missing_proof_count": candidate_facts["missing_proof_count"],
                "protected_proof_required": True,
                "operator_answers_are_not_proof": True,
                "action_authority_granted": False,
                "shared_fix_path": SHARED_FIX_PATH_ID,
            },
        },
        "machine_proof": {
            "proof_intake_item_count": len(items),
            "missing_proof_count": candidate_facts["missing_proof_count"],
            "target_world": candidate_facts["target_world"],
            "candidate_facts_proven": candidate_facts["candidate_facts_proven"],
            "action_authority_granted": False,
            "operator_answers_are_memory_candidates_not_proof": True,
            "protected_references_metadata_only": all(
                requirement.raw_body_allowed is False and requirement.metadata_only is True
                for requirement in protected_requirements
            ),
            "guardian_gate_count": len(guardian_gates),
            "raw_bodies_blocked": True,
            "coupa_browser_email_account_credentials_blocked": True,
            "invoice_generation_blocked": True,
            "send_submit_approval_blocked": True,
            "shared_fix_path_exists": True,
            "raw_private_body_included": False,
            "credential_or_secret_included": False,
            "network_git_sync_mac_app_mutation_authority_added": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_capital_hilton_protected_proof_intake(payload: dict[str, Any]) -> str:
    facts = payload["capital_hilton_current_facts"]
    lines = [
        "# Capital Hilton Protected Proof Intake v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        "Capital Hilton has ten proof gaps. This packet turns them into concrete questions Winship can answer or point toward, while keeping the answer separate from proof. A text answer can help the system know where to look; it does not prove the invoice facts by itself.",
        "",
        "## Candidate Facts",
        "",
        f"- Target world: `{facts['target_world']}`",
        f"- Current phase: `{facts['current_phase']}`",
        f"- Lane destiny: `{facts['lane_destiny']}`",
        f"- Missing proof count: `{facts['missing_proof_count']}`",
        f"- Protected proof required: `{str(facts['protected_proof_required']).lower()}`",
        f"- Candidate dates: `{', '.join(facts['candidate_completed_dates'])}`",
        f"- Candidate rate: `{facts['candidate_rate']}`",
        f"- Candidate subtotal: `{facts['candidate_subtotal']}`",
        f"- Candidate one-invoice posture: `{str(facts['candidate_one_invoice_posture']).lower()}`",
        f"- Candidate facts proven: `{str(facts['candidate_facts_proven']).lower()}`",
        "",
        "## What Winship Can Provide Or Point To",
        "",
    ]
    for item in payload["proof_intake_items"]:
        lines.append(f"- `{item['proof_item_id']}`: {item['eliwinship_question']}")
    lines.extend(
        [
            "",
            "## Answers Versus Proof",
            "",
            "- Text answers become Memory Candidate Receipts.",
            "- Screenshot, file, source-card, protected-reference, or receipt answers can point toward proof.",
            "- Protected references still need Guardian review before promotion.",
            "- Nothing here generates an invoice or accesses Coupa, browser, email, Excel, accounts, credentials, ledgers, or send/submit/approval paths.",
            "",
            "## What Quiets Items",
            "",
        ]
    )
    for rule in payload["proof_quieting_rules"]:
        lines.append(f"- `{rule['proof_item_id']}`: {rule['quiet_condition']}")
    lines.extend(
        [
            "",
            "## Shared Fix Path",
            "",
            f"- `{payload['shared_fix_path']['fix_path_id']}`",
            "- Solving one protected finance proof metadata intake can update Capital Hilton, Cassandra, Finance World, Guardian, and Package Preview posture after receipts/gates exist.",
            "",
            "## Still Blocked",
            "",
        ]
    )
    for action in payload["authority_boundary"]["blocked_actions"]:
        lines.append(f"- {action}")
    lines.extend(
        [
            "",
            "## Next Safest Move",
            "",
            "- Capture answers as memory candidates, then link actual source-card/protected evidence/receipt metadata through Guardian-gated proof intake.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_capital_hilton_protected_proof_intake(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> CapitalHiltonProtectedProofIntakeExportResult:
    payload = build_capital_hilton_protected_proof_intake(
        repo_root=repo_root,
        generated_at=generated_at,
    )
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_capital_hilton_protected_proof_intake(payload), encoding="utf-8")
    return CapitalHiltonProtectedProofIntakeExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        proof_intake_item_count=payload["machine_proof"]["proof_intake_item_count"],
        missing_proof_count=payload["machine_proof"]["missing_proof_count"],
        protected_proof_required=True,
        action_authority_granted=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Capital Hilton Protected Proof Intake read-model.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_capital_hilton_protected_proof_intake(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    summary = {
        "schema_version": result.schema_version,
        "json_path": result.json_path,
        "operator_path": result.operator_path,
        "proof_intake_item_count": result.proof_intake_item_count,
        "missing_proof_count": result.missing_proof_count,
        "protected_proof_required": result.protected_proof_required,
        "action_authority_granted": result.action_authority_granted,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        print(f"Capital Hilton Protected Proof Intake: `{result.schema_version}`")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
    return 0


__all__ = [
    "ALLOWED_ANSWER_MODALITIES",
    "ANSWER_STATUSES",
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "PROOF_STATUSES",
    "PROTECTED_SURFACES",
    "SCHEMA_VERSION",
    "SHARED_FIX_PATH_ID",
    "build_capital_hilton_protected_proof_intake",
    "build_proof_intake_items",
    "export_capital_hilton_protected_proof_intake",
    "format_capital_hilton_protected_proof_intake",
    "stable_json",
]
