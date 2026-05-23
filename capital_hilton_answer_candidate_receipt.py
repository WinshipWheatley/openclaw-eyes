"""Capital Hilton Answer Candidate Receipt Contract v0.

This read-model defines how operator answers to Capital Hilton proof questions
are captured as candidate receipts. Answers can clarify, reject, park, or point
toward proof, but they do not prove invoice facts by themselves and they do not
grant finance, account, browser, send, model, tool, queue, or runtime authority.
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

from capital_hilton_protected_proof_intake import (
    BLOCKED_ACTIONS as INTAKE_BLOCKED_ACTIONS,
    SHARED_FIX_PATH_ID,
    build_proof_intake_items,
)


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "capital_hilton_answer_candidate_receipt_v0"
READ_MODEL_ID = "capital_hilton_answer_candidate_receipt"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"

SOURCE_READ_MODEL_REF = "generated/read_models/capital_hilton_protected_proof_intake.json"
SOURCE_OPERATOR_REF = "generated/read_models/capital_hilton_protected_proof_intake_OPERATOR.md"

ALLOWED_ANSWER_MODALITIES = (
    "TEXT",
    "YES_NO",
    "STRUCTURED_FORM",
    "SCREENSHOT_REFERENCE",
    "FILE_REFERENCE",
    "SOURCE_CARD_REFERENCE",
    "PROTECTED_EVIDENCE_REFERENCE",
    "RECEIPT_REFERENCE",
    "I_DONT_KNOW",
    "PARK_THIS",
    "REJECT_OBSOLETE",
    "NEEDS_DISCOVERY",
)

ALLOWED_ANSWER_STATUSES = (
    "UNANSWERED",
    "ANSWER_CAPTURED_MEMORY_CANDIDATE",
    "ANSWER_POINTS_TO_SOURCE_CARD",
    "ANSWER_POINTS_TO_PROTECTED_REFERENCE",
    "ANSWER_POINTS_TO_RECEIPT",
    "ANSWER_STILL_NEEDS_PROOF",
    "ANSWER_REJECTS_CANDIDATE",
    "ANSWER_PARKS_ITEM",
    "ANSWER_NEEDS_DISCOVERY",
    "UNKNOWN_FAIL_CLOSED",
)

NO_AUTHORITY_FLAGS = {
    "invoice_generation_allowed": False,
    "coupa_access_allowed": False,
    "browser_oauth_allowed": False,
    "account_access_allowed": False,
    "gmail_calendar_email_access_allowed": False,
    "credential_handling_allowed": False,
    "raw_excel_body_ingestion_allowed": False,
    "raw_pdf_body_ingestion_allowed": False,
    "raw_email_body_ingestion_allowed": False,
    "raw_finance_body_ingestion_allowed": False,
    "ledger_write_allowed": False,
    "send_submit_approval_allowed": False,
    "model_call_allowed": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "queue_execution_allowed": False,
    "runtime_dispatch_allowed": False,
}

BLOCKED_ACTIONS = tuple(
    dict.fromkeys(
        (
            *INTAKE_BLOCKED_ACTIONS,
            "proof satisfaction by operator answer alone",
            "automatic quieting",
            "protected reference promotion without Guardian gate",
        )
    )
)


@dataclass(frozen=True)
class CapitalHiltonAnswerCandidateReceipt:
    answer_receipt_id: str
    proof_item_id: str
    proof_item_display_name: str
    question_text: str
    answer_modality: str
    answer_status: str
    operator_supplied_summary: str | None
    memory_candidate_created: bool
    memory_candidate_ref: str | None
    source_card_ref: str | None
    protected_reference_ref: str | None
    receipt_ref: str | None
    rejection_reason: str | None
    park_reason: str | None
    needs_discovery_reason: str | None
    proof_metadata_required: bool
    protected_reference_required: bool
    guardian_gate_required: bool
    operator_review_required: bool
    can_clarify: bool
    can_satisfy_proof: bool
    can_quiet_item: bool
    quieting_blockers: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class AnswerCandidateExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    default_answer_candidate_count: int
    example_count: int
    action_authority_granted: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _default_quieting_blockers(protected_required: bool) -> tuple[str, ...]:
    blockers = [
        "proof_metadata_not_linked",
        "validated_receipt_not_linked",
        "valid_rejection_reason_not_recorded",
    ]
    if protected_required:
        blockers.append("guardian_gate_not_satisfied")
    return tuple(blockers)


def build_default_answer_candidate_receipts() -> list[CapitalHiltonAnswerCandidateReceipt]:
    receipts: list[CapitalHiltonAnswerCandidateReceipt] = []
    for item in build_proof_intake_items():
        receipts.append(
            CapitalHiltonAnswerCandidateReceipt(
                answer_receipt_id=f"{item.proof_item_id}_answer_candidate_receipt",
                proof_item_id=item.proof_item_id,
                proof_item_display_name=item.display_name,
                question_text=item.eliwinship_question,
                answer_modality="STRUCTURED_FORM",
                answer_status="UNANSWERED",
                operator_supplied_summary=None,
                memory_candidate_created=False,
                memory_candidate_ref=None,
                source_card_ref=None,
                protected_reference_ref=None,
                receipt_ref=None,
                rejection_reason=None,
                park_reason=None,
                needs_discovery_reason=None,
                proof_metadata_required=True,
                protected_reference_required=item.protected_evidence_reference_required,
                guardian_gate_required=item.guardian_gate_required,
                operator_review_required=True,
                can_clarify=True,
                can_satisfy_proof=False,
                can_quiet_item=False,
                quieting_blockers=_default_quieting_blockers(item.protected_evidence_reference_required),
                blocked_actions=BLOCKED_ACTIONS,
                next_safe_move="capture_answer_as_candidate_receipt_without_proof_promotion",
            )
        )
    return receipts


def _example(
    *,
    answer_receipt_id: str,
    proof_item_id: str,
    display_name: str,
    question_text: str,
    modality: str,
    status: str,
    summary: str | None,
    memory_ref: str | None = None,
    source_card_ref: str | None = None,
    protected_reference_ref: str | None = None,
    receipt_ref: str | None = None,
    rejection_reason: str | None = None,
    park_reason: str | None = None,
    needs_discovery_reason: str | None = None,
    protected_required: bool = False,
    guardian_required: bool = False,
    can_quiet_item: bool = False,
    next_safe_move: str,
) -> CapitalHiltonAnswerCandidateReceipt:
    return CapitalHiltonAnswerCandidateReceipt(
        answer_receipt_id=answer_receipt_id,
        proof_item_id=proof_item_id,
        proof_item_display_name=display_name,
        question_text=question_text,
        answer_modality=modality,
        answer_status=status,
        operator_supplied_summary=summary,
        memory_candidate_created=memory_ref is not None,
        memory_candidate_ref=memory_ref,
        source_card_ref=source_card_ref,
        protected_reference_ref=protected_reference_ref,
        receipt_ref=receipt_ref,
        rejection_reason=rejection_reason,
        park_reason=park_reason,
        needs_discovery_reason=needs_discovery_reason,
        proof_metadata_required=True,
        protected_reference_required=protected_required,
        guardian_gate_required=guardian_required,
        operator_review_required=True,
        can_clarify=True,
        can_satisfy_proof=False,
        can_quiet_item=can_quiet_item,
        quieting_blockers=_default_quieting_blockers(protected_required)
        if not can_quiet_item
        else ("proof_or_rejection_receipt_policy_required",),
        blocked_actions=BLOCKED_ACTIONS,
        next_safe_move=next_safe_move,
    )


def build_answer_outcome_examples() -> list[CapitalHiltonAnswerCandidateReceipt]:
    questions = {item.proof_item_id: item for item in build_proof_intake_items()}
    return [
        _example(
            answer_receipt_id="text_clarifies_rate_but_not_proof",
            proof_item_id="rate_400_per_gig_proof",
            display_name=questions["rate_400_per_gig_proof"].display_name,
            question_text=questions["rate_400_per_gig_proof"].eliwinship_question,
            modality="TEXT",
            status="ANSWER_CAPTURED_MEMORY_CANDIDATE",
            summary="Operator says the rate was $400, but no source reference is linked.",
            memory_ref="memory_candidate://capital_hilton/rate_operator_memory",
            next_safe_move="ask_for_source_card_or_protected_rate_reference",
        ),
        _example(
            answer_receipt_id="source_card_points_to_rate_proof",
            proof_item_id="rate_400_per_gig_proof",
            display_name=questions["rate_400_per_gig_proof"].display_name,
            question_text=questions["rate_400_per_gig_proof"].eliwinship_question,
            modality="SOURCE_CARD_REFERENCE",
            status="ANSWER_POINTS_TO_SOURCE_CARD",
            summary="Operator points toward a source card for the rate.",
            source_card_ref="source_card://capital_hilton/rate_reference",
            next_safe_move="validate_source_card_and_receipt_before_proof_promotion",
        ),
        _example(
            answer_receipt_id="protected_excel_reference_for_workbook",
            proof_item_id="excel_workbook_or_invoice_source_reference",
            display_name=questions["excel_workbook_or_invoice_source_reference"].display_name,
            question_text=questions["excel_workbook_or_invoice_source_reference"].eliwinship_question,
            modality="PROTECTED_EVIDENCE_REFERENCE",
            status="ANSWER_POINTS_TO_PROTECTED_REFERENCE",
            summary="Operator points toward a workbook reference without raw body ingestion.",
            protected_reference_ref="protected_reference://capital_hilton/workbook_metadata_only",
            protected_required=True,
            guardian_required=True,
            next_safe_move="route_placeholder_to_guardian_review_before_promotion",
        ),
        _example(
            answer_receipt_id="operator_rejects_one_invoice_posture",
            proof_item_id="one_invoice_posture_proof",
            display_name=questions["one_invoice_posture_proof"].display_name,
            question_text=questions["one_invoice_posture_proof"].eliwinship_question,
            modality="REJECT_OBSOLETE",
            status="ANSWER_REJECTS_CANDIDATE",
            summary="Operator rejects the one-invoice candidate posture.",
            rejection_reason="operator_rejects_candidate_invoice_shape",
            can_quiet_item=False,
            next_safe_move="require_rejection_reason_and_receipt_policy_before_quieting",
        ),
        _example(
            answer_receipt_id="operator_parks_tax_vendor_handling",
            proof_item_id="tax_vendor_handling_metadata",
            display_name=questions["tax_vendor_handling_metadata"].display_name,
            question_text=questions["tax_vendor_handling_metadata"].eliwinship_question,
            modality="PARK_THIS",
            status="ANSWER_PARKS_ITEM",
            summary="Operator parks tax/vendor handling until more context exists.",
            park_reason="needs_later_vendor_or_tax_context",
            protected_required=True,
            guardian_required=True,
            next_safe_move="keep_item_parked_visible_and_proof_needed",
        ),
    ]


def build_capital_hilton_answer_candidate_receipt(
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    default_receipts = build_default_answer_candidate_receipts()
    examples = build_answer_outcome_examples()
    proof_item_ids = [receipt.proof_item_id for receipt in default_receipts]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_id": "capital_hilton_answer_candidate_receipt_v0",
        "generated_at": generated_at or utc_now(),
        **NO_AUTHORITY_FLAGS,
        "contract_status": "deterministic_answer_candidate_receipt_metadata_only",
        "operator_summary": (
            "Operator answers to Capital Hilton proof questions are captured as candidate "
            "receipts. They can clarify or point toward proof, but they do not prove invoice "
            "facts or grant action authority."
        ),
        "source_linkage": {
            "source_read_model_ref": SOURCE_READ_MODEL_REF,
            "source_operator_ref": SOURCE_OPERATOR_REF,
            "shared_execution_path_id": SHARED_FIX_PATH_ID,
            "extends_existing_intake_without_replacing_it": True,
        },
        "current_capital_hilton_truth": {
            "target_world": "Finance",
            "current_phase": "HELM_THRESHOLD_LANE",
            "lane_destiny": "MOVE_TO_WORLD_ACTION",
            "proof_item_count": 10,
            "missing_proof_count": 10,
            "protected_proof_required": True,
            "candidate_facts_proven": False,
            "action_authority_granted": False,
            "guardian_gates_present": True,
            "operator_answer_candidates_present": True,
            "protected_evidence_requirements_present": True,
        },
        "core_rule": {
            "operator_answers_can_clarify": True,
            "operator_answers_do_not_prove": True,
            "answers_may_point_toward_proof": True,
            "answers_may_trigger_guardian_requirement": True,
            "answers_may_keep_item_proof_needed": True,
            "answers_must_not_quiet_without_proof_metadata_valid_receipt_or_valid_rejection": True,
        },
        "allowed_answer_modalities": list(ALLOWED_ANSWER_MODALITIES),
        "allowed_answer_statuses": list(ALLOWED_ANSWER_STATUSES),
        "answer_candidate_receipts": [asdict(receipt) for receipt in default_receipts],
        "answer_outcome_examples": [asdict(example) for example in examples],
        "answer_classification_rules": {
            "text_yes_no_structured_form": {
                "can_clarify": True,
                "can_satisfy_proof": False,
                "becomes": "memory_candidate_receipt_unless_linked_to_proof_ref",
            },
            "source_card_protected_reference_receipt": {
                "can_point_toward_proof": True,
                "can_satisfy_proof_without_validation": False,
                "requires_validation": True,
            },
            "protected_reference": {
                "guardian_gate_required": True,
                "raw_body_allowed": False,
                "metadata_only": True,
            },
            "reject_obsolete": {
                "can_quiet_item_by_itself": False,
                "requires_rejection_reason_and_receipt_policy": True,
            },
            "park_this": {
                "proves_item": False,
                "completion_status": "parked_visible_not_completed",
            },
            "unknown_fail_closed": {
                "can_quiet_item": False,
                "next_safe_move": "ask_for_clarification_or_keep_proof_needed",
            },
        },
        "authority_boundary": {
            **NO_AUTHORITY_FLAGS,
            "all_authority_flags_false": all(value is False for value in NO_AUTHORITY_FLAGS.values()),
            "blocked_actions": list(BLOCKED_ACTIONS),
        },
        "batch_relationship": {
            "batch_id": "capital_hilton_proof_resolution_batch_v0",
            "prompt_index": 1,
            "stable_map_refresh_deferred": True,
            "commit_deferred_until_final_prompt": True,
            "next_lane": "capital_hilton_protected_reference_placeholder",
        },
        "machine_proof": {
            "default_answer_candidate_count": len(default_receipts),
            "all_10_proof_item_ids_represented": proof_item_ids
            == [
                "performance_date_2026_05_08_proof",
                "performance_date_2026_05_15_proof",
                "rate_400_per_gig_proof",
                "subtotal_800_proof",
                "one_invoice_posture_proof",
                "coupa_po_payment_reference_metadata",
                "excel_workbook_or_invoice_source_reference",
                "ap_recipient_route_metadata",
                "tax_vendor_handling_metadata",
                "future_invoice_generation_receipt_requirement",
            ],
            "default_records_unanswered": all(
                receipt.answer_status == "UNANSWERED" for receipt in default_receipts
            ),
            "text_answers_can_clarify_but_not_prove": True,
            "source_protected_receipt_refs_do_not_automatically_satisfy_proof": True,
            "protected_reference_answers_require_guardian": True,
            "operator_answers_are_memory_candidates_unless_linked_to_proof_refs": True,
            "can_quiet_item_false_by_default": all(
                receipt.can_quiet_item is False for receipt in default_receipts
            ),
            "authority_flags_false": all(value is False for value in NO_AUTHORITY_FLAGS.values()),
            "raw_bodies_blocked": True,
            "credential_or_secret_included": False,
            "raw_private_body_included": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_capital_hilton_answer_candidate_receipt(payload: dict[str, Any]) -> str:
    lines = [
        "# Capital Hilton Answer Candidate Receipt v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        "An answer candidate is a safe receipt for what Winship says or points to while resolving a Capital Hilton proof question. It can clarify memory, reject a candidate, park an item, or point toward a source card, protected reference, or receipt. It does not prove the invoice facts by itself.",
        "",
        "## Why Answers Clarify But Do Not Prove",
        "",
        "- Text, yes/no, and structured-form answers become memory candidates unless linked to proof refs.",
        "- Source-card, protected-reference, and receipt answers point toward proof but still need validation.",
        "- Protected references need Guardian review before promotion.",
        "- Text answers do not quiet proof because memory is not source proof.",
        "",
        "## Default Answer Candidates",
        "",
    ]
    for receipt in payload["answer_candidate_receipts"]:
        lines.append(f"- `{receipt['proof_item_id']}`: `{receipt['answer_status']}`")
    lines.extend(
        [
            "",
            "## Parked, Rejected, Or Unknown Answers",
            "",
            "- Parked items stay visible as parked, not completed.",
            "- Rejected candidates can quiet only with a reason and receipt policy.",
            "- Unknown states fail closed and keep the proof item proof-needed.",
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
            "## Next Backend Batch Lane",
            "",
            "- Prompt 2 will define protected proof reference placeholders. It still will not access protected files or raw finance bodies.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_capital_hilton_answer_candidate_receipt(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> AnswerCandidateExportResult:
    payload = build_capital_hilton_answer_candidate_receipt(generated_at=generated_at)
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_capital_hilton_answer_candidate_receipt(payload), encoding="utf-8")
    return AnswerCandidateExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        default_answer_candidate_count=payload["machine_proof"]["default_answer_candidate_count"],
        example_count=len(payload["answer_outcome_examples"]),
        action_authority_granted=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Capital Hilton Answer Candidate Receipt read-model.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_capital_hilton_answer_candidate_receipt(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    summary = {
        "schema_version": result.schema_version,
        "json_path": result.json_path,
        "operator_path": result.operator_path,
        "default_answer_candidate_count": result.default_answer_candidate_count,
        "example_count": result.example_count,
        "action_authority_granted": result.action_authority_granted,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        print(f"Capital Hilton Answer Candidate Receipt: `{result.schema_version}`")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
    return 0


__all__ = [
    "ALLOWED_ANSWER_MODALITIES",
    "ALLOWED_ANSWER_STATUSES",
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "READ_MODEL_ID",
    "SCHEMA_VERSION",
    "SOURCE_OPERATOR_REF",
    "SOURCE_READ_MODEL_REF",
    "build_answer_outcome_examples",
    "build_capital_hilton_answer_candidate_receipt",
    "build_default_answer_candidate_receipts",
    "export_capital_hilton_answer_candidate_receipt",
    "format_capital_hilton_answer_candidate_receipt",
    "stable_json",
]
