"""Security Audit Readiness Packet v0 Pass 1 for OpenClaw.

This read-model defines provenance, operator answer capture, question
quieting, shared execution paths, helm focus guidance, and Capital Hilton
security-readiness posture. It is metadata only: no security approval, model
call, tool execution, actor activation, account access, answer popup, UI
implementation, queue/autonomy, Mac sync/import, network operation, Repo B
inspection, raw private body ingestion, or PC system-drive write authority is
created.
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

SCHEMA_VERSION = "security_audit_readiness_packet_v0_pass_1"
JSON_EXPORT_NAME = "security_audit_readiness_packet.json"
OPERATOR_EXPORT_NAME = "security_audit_readiness_packet_OPERATOR.md"

NO_AUTHORITY_FLAGS = {
    "coupa_access_allowed": False,
    "browser_oauth_allowed": False,
    "credential_handling_allowed": False,
    "gmail_calendar_access_allowed": False,
    "excel_raw_body_ingestion_allowed": False,
    "raw_finance_body_ingestion_allowed": False,
    "invoice_generation_allowed": False,
    "send_submit_approval_allowed": False,
    "account_access_allowed": False,
    "model_call_allowed": False,
    "model_api_execution_allowed": False,
    "model_router_runtime_allowed": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "queue_execution_allowed": False,
    "runtime_dispatch_allowed": False,
    "planner_builder_execution_allowed": False,
    "hidden_memory_allowed": False,
    "external_retained_memory_allowed": False,
    "broad_filesystem_indexing_allowed": False,
    "broad_private_file_inspection_allowed": False,
    "repo_b_mutation_allowed": False,
    "repo_b_body_inspection_allowed": False,
    "mission_control_app_changes_included": False,
    "mac_sync_or_import_triggered": False,
    "network_operation_allowed": False,
    "pc_c_drive_artifact_write_allowed": False,
    "security_approval_granted": False,
    "operator_final_authority": True,
}

VERIFICATION_STATUSES = (
    "PROVEN",
    "CANDIDATE",
    "MISSING_PROOF",
    "NEEDS_VERIFICATION",
    "BLOCKED",
    "STALE",
    "UNKNOWN_FAIL_CLOSED",
)

ANSWER_MODALITIES = (
    "text",
    "yes_no",
    "multiple_choice",
    "structured_form",
    "screenshot_ref",
    "file_ref",
    "source_card_ref",
    "receipt_ref",
    "protected_proof_metadata_ref",
    "i_dont_know",
    "park_this",
    "needs_discovery",
    "ask_me_later",
    "move_to_world",
    "reject_obsolete",
)

QUESTION_CLASSES = (
    "memory_only_clarification",
    "proof_needed",
    "protected_proof_needed",
    "security_gate_needed",
    "world_transition_needed",
    "repo_discovery_needed",
    "package_contract_needed",
)

QUESTION_STATES = (
    "UNANSWERED",
    "ANSWER_CAPTURED",
    "MEMORY_CANDIDATE_CREATED",
    "PROOF_STILL_REQUIRED",
    "PROOF_METADATA_LINKED",
    "RESOLVED_QUIET",
    "PARKED",
    "REJECTED",
    "NEEDS_DISCOVERY",
    "UNKNOWN_FAIL_CLOSED",
)

ISSUE_TYPES = (
    "SINGLE_LANE_ISSUE",
    "SHARED_FIX_PATH",
    "SECURITY_GATE_ISSUE",
    "PROOF_GAP_ISSUE",
    "OPERATOR_QUESTION_ISSUE",
    "WORLD_TRANSITION_ISSUE",
    "SYSTEM_HEALTH_ISSUE",
)

SOURCE_READ_MODEL_REFS = (
    "generated/read_models/openclaw_map_snapshot.json",
    "generated/read_models/openclaw_map_manifest.json",
    "generated/read_models/capital_hilton_proof_metadata_packet.json",
    "generated/read_models/package_preview_receipt_contract.json",
    "generated/read_models/tool_adapter_receipt_contract.json",
    "generated/read_models/model_selection_receipt_contract.json",
    "generated/read_models/memory_candidate_receipt_contract.json",
    "generated/read_models/agent_memory_scope_contract.json",
    "generated/read_models/agent_terrain_awareness_readback_contract.json",
    "generated/read_models/operator_threshold_map_contract.json",
)

CAPITAL_HILTON_PROOF_IDS = (
    "performance_date_proof_metadata",
    "rate_proof_metadata",
    "subtotal_proof_metadata",
    "coupa_po_or_payment_reference_metadata",
    "excel_workbook_reference_metadata",
    "invoice_source_card_metadata",
    "ap_recipient_route_metadata",
    "guardian_protected_access_gate_metadata",
    "operator_confirmation_metadata",
    "future_invoice_generation_receipt_requirement",
)

REQUIRED_CONTEXT_EXCLUSIONS = (
    "raw finance bodies",
    "Coupa/browser/account sessions",
    "credentials/tokens/cookies/API keys",
    "raw email/calendar bodies",
    "raw Excel bodies",
    "send/submit/approval authority",
)

BLOCKED_ACTIONS = (
    "Coupa access",
    "browser/OAuth/account access",
    "credential/token/cookie/API key handling",
    "Gmail/calendar/email account access",
    "Excel raw body ingestion",
    "raw finance/private body ingestion",
    "invoice generation",
    "send/submit/approval",
    "live model calls",
    "model/API execution",
    "actor/agent activation",
    "tool execution",
    "planner/builder/queue/autonomy execution",
    "Repo B mutation/body inspection",
    "Mac sync/import",
)


@dataclass(frozen=True)
class MapToTerrainProvenance:
    claim_id: str
    display_name: str
    source_read_model_refs: list[str]
    receipt_refs: list[str]
    ledger_refs: list[str]
    source_card_refs: list[str]
    proof_metadata_refs: list[str]
    stable_map_generation_id: str
    bundle_hash: str
    candidate_status: str
    verification_status: str
    missing_proof: list[str]
    authority_boundary: dict[str, bool]


@dataclass(frozen=True)
class PackageMapSliceRule:
    map_slice_ref: str
    source_read_model_refs: list[str]
    receipt_refs: list[str]
    proof_metadata_refs: list[str]
    stable_map_generation_id: str
    bundle_hash: str
    freshness_status: str
    candidate_claims: list[str]
    proven_claims: list[str]
    missing_proof: list[str]
    excluded_context: list[str]
    authority_boundary: dict[str, bool]


@dataclass(frozen=True)
class HelmWorldResponsibilityBoundary:
    boundary_id: str
    helm_owns: list[str]
    worlds_own: list[str]
    capital_hilton_helm_owns: list[str]
    finance_world_may_show: list[str]
    bifurcation_avoidance_rule: str
    authority_boundary: dict[str, bool]


@dataclass(frozen=True)
class OperatorAnswerCaptureContract:
    question_id: str
    lane_id: str
    world_id: str
    question_text: str
    question_class: str
    answer_required_for: list[str]
    answer_type: str
    allowed_answer_modalities: list[str]
    proof_required_after_answer: bool
    memory_candidate_receipt_required: bool
    operator_action_required: bool
    what_happens_when_answered: str
    quieting_effect: str
    shared_execution_path_id: str | None
    status: str


@dataclass(frozen=True)
class QuestionQuietingRule:
    rule_id: str
    question_states: list[str]
    when_answered: list[str]
    active_helm_removal_rule: str
    proof_detail_rule: str
    shared_execution_path_rule: str
    authority_boundary: dict[str, bool]


@dataclass(frozen=True)
class SharedExecutionPathConsolidation:
    shared_execution_path_id: str
    display_name: str
    linked_lanes: list[str]
    linked_worlds: list[str]
    linked_questions: list[str]
    required_proof: list[str]
    required_memory_candidates: list[str]
    required_gates: list[str]
    authority_boundary: dict[str, bool]
    current_status: str
    next_safe_move: str
    what_solving_this_updates: list[str]
    quieting_effects: list[str]
    blocked_actions: list[str]
    future_gated_actions: list[str]


@dataclass(frozen=True)
class HelmIssueFocusMode:
    issue_focus_id: str
    display_title: str
    eli5_summary: str
    why_it_matters: str
    issue_type: str
    linked_lanes: list[str]
    linked_worlds: list[str]
    linked_questions: list[str]
    shared_execution_path_id: str | None
    affected_cards: list[str]
    visible_when_selected: list[str]
    hidden_when_selected: list[str]
    proof_refs: list[str]
    missing_proof: list[str]
    operator_questions: list[str]
    required_gates: list[str]
    blocked_actions: list[str]
    future_gated_actions: list[str]
    next_safe_move: str
    package_preview_ref: str | None
    machine_contract_refs: list[str]
    quiet_condition: str
    what_solving_this_updates: list[str]


@dataclass(frozen=True)
class CapitalHiltonSecurityReadiness:
    provenance_status: str
    missing_proof_count: int
    protected_proof_required: bool
    shared_execution_path_id: str
    candidate_facts_proven: bool
    finance_world_preview_exists: bool
    security_pass_complete: bool
    action_authority_granted: bool
    readiness_status: str
    what_blocks_security_readiness: list[str]
    what_blocks_action_readiness: list[str]


@dataclass(frozen=True)
class SecurityAuditReadinessPacketExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    provenance_claim_count: int
    operator_question_count: int
    shared_execution_path_count: int
    helm_issue_focus_count: int
    capital_hilton_missing_proof_count: int
    security_approval_granted: bool
    live_authority_added: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _read_json_if_present(repo_root: str | Path, relative_path: str) -> dict[str, Any]:
    path = Path(repo_root) / relative_path
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _authority_boundary() -> dict[str, bool]:
    return dict(NO_AUTHORITY_FLAGS)


def _dangerous_authority_flags_false() -> bool:
    return all(value is False for key, value in NO_AUTHORITY_FLAGS.items() if key != "operator_final_authority")


def _capital_hilton_summary(repo_root: str | Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    snapshot = _read_json_if_present(repo_root, "generated/read_models/openclaw_map_snapshot.json")
    manifest = _read_json_if_present(repo_root, "generated/read_models/openclaw_map_manifest.json")
    packet = _read_json_if_present(repo_root, "generated/read_models/capital_hilton_proof_metadata_packet.json")
    stable_summary = snapshot.get("capital_hilton_proof_metadata") if isinstance(snapshot.get("capital_hilton_proof_metadata"), dict) else {}
    return stable_summary, manifest, packet


def _map_generation_id(snapshot_summary: dict[str, Any], manifest: dict[str, Any]) -> str:
    return str(
        manifest.get("map_generation_id")
        or snapshot_summary.get("map_generation_id")
        or "map_generation_missing_fail_closed"
    )


def _bundle_hash(manifest: dict[str, Any]) -> str:
    return str(manifest.get("bundle_hash") or "bundle_hash_missing_fail_closed")


def _candidate_facts(summary: dict[str, Any], packet: dict[str, Any]) -> list[dict[str, Any]]:
    facts = summary.get("candidate_facts")
    if isinstance(facts, list):
        return [fact for fact in facts if isinstance(fact, dict)]
    packet_facts = packet.get("capital_hilton_candidate_facts")
    if isinstance(packet_facts, list):
        return [fact for fact in packet_facts if isinstance(fact, dict)]
    return []


def _operator_questions(summary: dict[str, Any], packet: dict[str, Any]) -> list[dict[str, Any]]:
    questions = summary.get("operator_memory_questions")
    if isinstance(questions, list):
        return [item for item in questions if isinstance(item, dict)]
    packet_questions = packet.get("operator_memory_questions")
    if isinstance(packet_questions, list):
        return [item for item in packet_questions if isinstance(item, dict)]
    return []


def _missing_proof(summary: dict[str, Any], packet: dict[str, Any]) -> list[str]:
    missing = summary.get("missing_proof")
    if isinstance(missing, list) and missing:
        return [str(item) for item in missing]
    checklist = packet.get("missing_proof_checklist")
    if isinstance(checklist, list) and checklist:
        return [str(item) for item in checklist]
    return list(CAPITAL_HILTON_PROOF_IDS)


def _missing_proof_count(summary: dict[str, Any], packet: dict[str, Any]) -> int:
    if isinstance(summary.get("missing_proof_count"), int):
        return int(summary["missing_proof_count"])
    machine = packet.get("machine_proof") if isinstance(packet.get("machine_proof"), dict) else {}
    if isinstance(machine.get("missing_proof_count"), int):
        return int(machine["missing_proof_count"])
    return len(_missing_proof(summary, packet))


def _protected_proof_required(summary: dict[str, Any], packet: dict[str, Any]) -> bool:
    if isinstance(summary.get("protected_proof_required"), bool):
        return bool(summary["protected_proof_required"])
    machine = packet.get("machine_proof") if isinstance(packet.get("machine_proof"), dict) else {}
    if isinstance(machine.get("protected_proof_required"), bool):
        return bool(machine["protected_proof_required"])
    return True


def _candidate_facts_proven(facts: list[dict[str, Any]], summary: dict[str, Any]) -> bool:
    if isinstance(summary.get("all_candidate_facts_marked_not_proven"), bool):
        return not bool(summary["all_candidate_facts_marked_not_proven"])
    if not facts:
        return False
    return all(fact.get("machine_proven") is True and bool(fact.get("proof_ref")) for fact in facts)


def _fact_by_id(facts: list[dict[str, Any]], fact_id: str) -> dict[str, Any]:
    for fact in facts:
        if fact.get("fact_id") == fact_id:
            return fact
    return {}


def _claim_provenance(
    *,
    claim_id: str,
    display_name: str,
    fact: dict[str, Any],
    missing_proof: list[str],
    generation_id: str,
    bundle_hash: str,
) -> MapToTerrainProvenance:
    proof_ref = fact.get("proof_ref")
    source_ref = fact.get("source_reference")
    machine_proven = fact.get("machine_proven") is True and bool(proof_ref)
    status = "PROVEN" if machine_proven else "CANDIDATE" if fact else "MISSING_PROOF"
    return MapToTerrainProvenance(
        claim_id=claim_id,
        display_name=display_name,
        source_read_model_refs=[
            "generated/read_models/capital_hilton_proof_metadata_packet.json",
            "generated/read_models/openclaw_map_snapshot.json",
        ],
        receipt_refs=[
            "generated/read_models/package_preview_receipt_contract.json",
            "generated/read_models/tool_adapter_receipt_contract.json",
            "generated/read_models/model_selection_receipt_contract.json",
        ],
        ledger_refs=[],
        source_card_refs=[str(source_ref)] if source_ref else [],
        proof_metadata_refs=[str(proof_ref)] if proof_ref else [],
        stable_map_generation_id=generation_id,
        bundle_hash=bundle_hash,
        candidate_status="candidate_not_machine_proven" if not machine_proven else "machine_proven_with_ref",
        verification_status=status,
        missing_proof=missing_proof if not machine_proven else [],
        authority_boundary=_authority_boundary(),
    )


def _build_map_to_terrain_provenance(
    facts: list[dict[str, Any]],
    missing_proof: list[str],
    generation_id: str,
    bundle_hash: str,
) -> list[dict[str, Any]]:
    records = [
        _claim_provenance(
            claim_id="capital_hilton_completed_performance_dates",
            display_name="Capital Hilton completed performance dates",
            fact=_fact_by_id(facts, "completed_performance_dates"),
            missing_proof=["performance_date_proof_metadata"],
            generation_id=generation_id,
            bundle_hash=bundle_hash,
        ),
        _claim_provenance(
            claim_id="capital_hilton_rate",
            display_name="Capital Hilton candidate rate",
            fact=_fact_by_id(facts, "rate"),
            missing_proof=["rate_proof_metadata"],
            generation_id=generation_id,
            bundle_hash=bundle_hash,
        ),
        _claim_provenance(
            claim_id="capital_hilton_subtotal",
            display_name="Capital Hilton candidate subtotal posture",
            fact=_fact_by_id(facts, "subtotal"),
            missing_proof=["subtotal_proof_metadata"],
            generation_id=generation_id,
            bundle_hash=bundle_hash,
        ),
        _claim_provenance(
            claim_id="capital_hilton_one_invoice_posture",
            display_name="Capital Hilton one-invoice posture",
            fact=_fact_by_id(facts, "invoice_shape_one_invoice_posture"),
            missing_proof=["invoice_source_card_metadata", "operator_confirmation_metadata"],
            generation_id=generation_id,
            bundle_hash=bundle_hash,
        ),
        MapToTerrainProvenance(
            claim_id="capital_hilton_missing_proof_count",
            display_name="Capital Hilton missing proof count",
            source_read_model_refs=[
                "generated/read_models/capital_hilton_proof_metadata_packet.json",
                "generated/read_models/openclaw_map_snapshot.json",
            ],
            receipt_refs=["generated/read_models/openclaw_map_manifest.json"],
            ledger_refs=[],
            source_card_refs=[],
            proof_metadata_refs=[],
            stable_map_generation_id=generation_id,
            bundle_hash=bundle_hash,
            candidate_status="read_model_reported_missing_proof_posture",
            verification_status="MISSING_PROOF" if missing_proof else "PROVEN",
            missing_proof=missing_proof,
            authority_boundary=_authority_boundary(),
        ),
    ]
    return [asdict(record) for record in records]


def _build_package_map_slice_rule(
    missing_proof: list[str],
    generation_id: str,
    bundle_hash: str,
) -> dict[str, Any]:
    return asdict(
        PackageMapSliceRule(
            map_slice_ref="openclaw_map_snapshot.capital_hilton_proof_metadata",
            source_read_model_refs=[
                "generated/read_models/capital_hilton_proof_metadata_packet.json",
                "generated/read_models/package_preview_receipt_contract.json",
                "generated/read_models/tool_adapter_receipt_contract.json",
                "generated/read_models/model_selection_receipt_contract.json",
                "generated/read_models/agent_memory_scope_contract.json",
            ],
            receipt_refs=[
                "generated/read_models/openclaw_map_manifest.json",
                "generated/read_models/sync_health.json#app_visible_map_status",
            ],
            proof_metadata_refs=[],
            stable_map_generation_id=generation_id,
            bundle_hash=bundle_hash,
            freshness_status="stable_map_current_but_not_source_truth",
            candidate_claims=[
                "dates",
                "rate",
                "subtotal",
                "one-invoice posture",
                "Capital Hilton target world Finance",
            ],
            proven_claims=[
                "stable map generation id and bundle hash identify the app-facing snapshot",
                "authority flags are explicitly false in the map slice",
            ],
            missing_proof=missing_proof,
            excluded_context=list(REQUIRED_CONTEXT_EXCLUSIONS),
            authority_boundary=_authority_boundary(),
        )
    )


def _build_helm_world_boundary() -> dict[str, Any]:
    return asdict(
        HelmWorldResponsibilityBoundary(
            boundary_id="helm_world_responsibility_boundary_v0_pass_1",
            helm_owns=[
                "system health",
                "proof gaps",
                "security readiness",
                "missing operator answers",
                "shared execution paths",
                "cross-lane consolidation",
                "whether a lane is quiet, blocked, parked, or world-ready",
            ],
            worlds_own=[
                "domain context",
                "domain-specific preview",
                "eventual domain work after security gates",
                "domain-specific proof/status presentation",
            ],
            capital_hilton_helm_owns=[
                "not ready posture",
                "10 missing proof items",
                "protected proof required",
                "candidate facts not proven",
                "security audit not passed",
                "no invoice action",
                "shared fix path if other lanes need the same proof/capture",
            ],
            finance_world_may_show=[
                "Capital Hilton preview",
                "target world Finance",
                "protected proof-needed posture",
                "blocked invoice authority",
            ],
            bifurcation_avoidance_rule=(
                "Helm owns cross-cutting readiness and quieting while worlds show domain context; "
                "a lane may appear in both only when the map says why and keeps one shared proof path."
            ),
            authority_boundary=_authority_boundary(),
        )
    )


def _question_text(question: dict[str, Any]) -> str:
    return str(question.get("question_text") or question.get("question") or "")


def _question_class(question: dict[str, Any]) -> str:
    value = str(question.get("question_class") or question.get("classification") or "proof_needed")
    return value if value in QUESTION_CLASSES else "proof_needed"


def _shared_path_for_question(question_class: str) -> str:
    if question_class in {"protected_proof_needed", "security_gate_needed", "world_transition_needed", "proof_needed"}:
        return "protected_finance_proof_metadata_intake"
    return "operator_memory_question_capture"


def _build_operator_answer_capture(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not questions:
        questions = [
            {
                "question_id": "capital_hilton_missing_operator_confirmation",
                "question": "What operator memory would clarify the Capital Hilton proof path?",
                "classification": "memory_only_clarification",
            }
        ]
    records: list[dict[str, Any]] = []
    for raw in questions:
        question_id = str(raw.get("question_id") or f"question_{len(records) + 1}")
        question_class = _question_class(raw)
        shared_path = _shared_path_for_question(question_class)
        records.append(
            asdict(
                OperatorAnswerCaptureContract(
                    question_id=question_id,
                    lane_id="capital_hilton",
                    world_id="Finance",
                    question_text=_question_text(raw),
                    question_class=question_class,
                    answer_required_for=[
                        "lane quieting",
                        "protected proof metadata routing",
                        "future Finance World action readiness",
                    ],
                    answer_type="memory_candidate_or_proof_reference_capture",
                    allowed_answer_modalities=list(ANSWER_MODALITIES),
                    proof_required_after_answer=True,
                    memory_candidate_receipt_required=True,
                    operator_action_required=True,
                    what_happens_when_answered=(
                        "Answer is captured as a Memory Candidate Receipt or proof reference candidate; "
                        "it does not become machine proof by itself."
                    ),
                    quieting_effect=(
                        "The original question may leave active helm only when the replacement proof-needed, "
                        "parked, rejected, or resolved state is explicit."
                    ),
                    shared_execution_path_id=shared_path,
                    status="UNANSWERED",
                )
            )
        )
    return records


def _build_question_quieting_rule() -> dict[str, Any]:
    return asdict(
        QuestionQuietingRule(
            rule_id="question_quieting_rule_v0_pass_1",
            question_states=list(QUESTION_STATES),
            when_answered=[
                "mark question as ANSWER_CAPTURED",
                "require MEMORY_CANDIDATE_CREATED when answer carries operator memory",
                "update lane posture",
                "remove from active helm only if no longer blocking",
                "keep receipt/proof available in drill-down",
                "replace answered question with PROOF_STILL_REQUIRED when proof is still missing",
                "mark obsolete/rejected/parked if the answer invalidates the lane",
                "update shared execution path if the answer resolves multiple lanes",
            ],
            active_helm_removal_rule=(
                "A captured answer quiets the question, not the underlying proof gap; proof gaps stay visible "
                "until linked proof metadata exists or the lane is parked/rejected."
            ),
            proof_detail_rule="Captured answers and receipts remain available in proof/detail and are never silently promoted to proof.",
            shared_execution_path_rule="One answered shared question updates all linked lanes through its shared_execution_path_id.",
            authority_boundary=_authority_boundary(),
        )
    )


def _build_shared_execution_paths(question_records: list[dict[str, Any]], missing_proof: list[str]) -> list[dict[str, Any]]:
    question_ids = [record["question_id"] for record in question_records]
    paths = [
        SharedExecutionPathConsolidation(
            shared_execution_path_id="protected_finance_proof_metadata_intake",
            display_name="Protected Finance Proof Metadata Intake",
            linked_lanes=["capital_hilton", "cassandra_finance_review"],
            linked_worlds=["Finance"],
            linked_questions=[
                q["question_id"]
                for q in question_records
                if q["shared_execution_path_id"] == "protected_finance_proof_metadata_intake"
            ],
            required_proof=missing_proof,
            required_memory_candidates=["operator_confirmation_metadata"],
            required_gates=["Guardian protected access gate", "Operator final path approval after security pass"],
            authority_boundary=_authority_boundary(),
            current_status="proof_needed_preview_only",
            next_safe_move="Capture operator answers as memory candidates and define protected proof metadata refs.",
            what_solving_this_updates=[
                "Capital Hilton security-readiness posture",
                "Cassandra Finance preview",
                "Finance World proof-needed lane",
                "future security audit packet inputs",
            ],
            quieting_effects=[
                "Capital Hilton proof questions can quiet or convert into proof-needed items",
                "Finance World can show a cleaner preview",
                "Helm can collapse duplicate finance-proof asks",
            ],
            blocked_actions=list(BLOCKED_ACTIONS),
            future_gated_actions=[
                "protected proof metadata intake",
                "future invoice generation receipt",
                "future Coupa/PO route proof",
            ],
        ),
        SharedExecutionPathConsolidation(
            shared_execution_path_id="operator_memory_question_capture",
            display_name="Operator Memory Question Capture",
            linked_lanes=["terrain_awareness", "capital_hilton", "hermes", "repo_b_leftovers"],
            linked_worlds=["Helm", "Finance"],
            linked_questions=question_ids,
            required_proof=[],
            required_memory_candidates=question_ids,
            required_gates=["Memory Candidate Receipt review"],
            authority_boundary=_authority_boundary(),
            current_status="capture_only_not_proof",
            next_safe_move="Capture answers as Memory Candidate Receipts; classify whether proof is still needed.",
            what_solving_this_updates=[
                "terrain unknowns",
                "Capital Hilton operator-memory posture",
                "future missing-proof and holding-cell inputs",
            ],
            quieting_effects=[
                "answered questions leave active helm when replaced with proof-needed or quiet-with-proof state",
                "operator memory stops being repeated as a question once captured",
            ],
            blocked_actions=list(BLOCKED_ACTIONS),
            future_gated_actions=["Tell System What's Missing capture path"],
        ),
        SharedExecutionPathConsolidation(
            shared_execution_path_id="stable_map_receipt_readback",
            display_name="Stable Map Receipt Readback",
            linked_lanes=["check_transmission", "stable_map_app_visibility"],
            linked_worlds=["Helm"],
            linked_questions=[],
            required_proof=["map_generation_id", "bundle_hash", "Mac receipt matching PC bundle"],
            required_memory_candidates=[],
            required_gates=[],
            authority_boundary=_authority_boundary(),
            current_status="current_when_generation_and_receipt_match",
            next_safe_move="Keep app-facing stable map state primary; keep raw mirror mismatch in proof/detail.",
            what_solving_this_updates=[
                "Check Transmission quiet/current display",
                "app-visible stable map proof",
                "raw mirror detail classification",
            ],
            quieting_effects=[
                "Check Transmission can become quiet",
                "raw mirror mismatch remains secondary proof/detail",
            ],
            blocked_actions=list(BLOCKED_ACTIONS),
            future_gated_actions=["Mac import is separate and explicit; this packet does not trigger it"],
        ),
    ]
    return [asdict(path) for path in paths]


def _build_helm_issue_focus_modes(missing_proof: list[str], question_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    question_ids = [record["question_id"] for record in question_records]
    focus_modes = [
        HelmIssueFocusMode(
            issue_focus_id="focus_capital_hilton_missing_proof",
            display_title="Capital Hilton Needs Protected Proof",
            eli5_summary="The Finance preview is visible, but the invoice lane still needs proof metadata before security or action.",
            why_it_matters="This prevents the system from treating candidate invoice details as proven finance truth.",
            issue_type="PROOF_GAP_ISSUE",
            linked_lanes=["capital_hilton", "cassandra_finance_review"],
            linked_worlds=["Finance"],
            linked_questions=question_ids,
            shared_execution_path_id="protected_finance_proof_metadata_intake",
            affected_cards=["Capital Hilton", "Cassandra", "Guardian", "Finance World"],
            visible_when_selected=[
                "Capital Hilton candidate facts",
                "missing proof checklist",
                "operator questions",
                "Guardian gate requirements",
                "next safe move",
            ],
            hidden_when_selected=[
                "unrelated helm cards",
                "live dispatch controls",
                "tool execution controls",
                "account/browser/Coupa/Gmail/calendar controls",
                "send/submit/approval controls",
            ],
            proof_refs=[
                "generated/read_models/capital_hilton_proof_metadata_packet.json",
                "generated/read_models/openclaw_map_snapshot.json#capital_hilton_proof_metadata",
            ],
            missing_proof=missing_proof,
            operator_questions=question_ids,
            required_gates=["Guardian protected proof gate", "Security pass", "Operator final path"],
            blocked_actions=list(BLOCKED_ACTIONS),
            future_gated_actions=[
                "protected proof metadata intake",
                "Finance World action after security pass",
            ],
            next_safe_move="Capture operator answers as memory candidates and link protected proof metadata refs.",
            package_preview_ref="generated/read_models/package_preview_receipt_contract.json#cassandra_capital_hilton_invoice_review",
            machine_contract_refs=[
                "capital_hilton_proof_metadata_packet",
                "package_preview_receipt_contract",
                "tool_adapter_receipt_contract",
                "model_selection_receipt_contract",
                "memory_candidate_receipt_contract",
            ],
            quiet_condition="All proof gaps are linked, parked, rejected, or moved into Finance World with no live action authority.",
            what_solving_this_updates=[
                "Capital Hilton security-readiness",
                "Finance World preview state",
                "future security audit readiness inputs",
            ],
        ),
        HelmIssueFocusMode(
            issue_focus_id="focus_operator_answer_capture",
            display_title="Answer Missing Operator Questions",
            eli5_summary="Winship can answer guided questions later; answers become memory candidates, not proof.",
            why_it_matters="This keeps useful operator memory visible without silently promoting it to trusted finance evidence.",
            issue_type="OPERATOR_QUESTION_ISSUE",
            linked_lanes=["capital_hilton", "terrain_awareness"],
            linked_worlds=["Helm", "Finance"],
            linked_questions=question_ids,
            shared_execution_path_id="operator_memory_question_capture",
            affected_cards=["Capital Hilton", "Terrain Awareness", "Memory Candidate Inbox"],
            visible_when_selected=[
                "unanswered questions",
                "allowed answer modalities",
                "memory candidate receipt requirement",
                "proof still required after answer",
            ],
            hidden_when_selected=[
                "unrelated helm cards",
                "live answer popups",
                "auto-promotion controls",
                "queue execution controls",
            ],
            proof_refs=["generated/read_models/memory_candidate_receipt_contract.json"],
            missing_proof=[],
            operator_questions=question_ids,
            required_gates=["Memory Candidate Receipt review"],
            blocked_actions=list(BLOCKED_ACTIONS),
            future_gated_actions=["Tell System What's Missing capture path"],
            next_safe_move="Define read-only capture fields in a later lane; do not implement UI here.",
            package_preview_ref=None,
            machine_contract_refs=["memory_candidate_receipt_contract", "agent_terrain_awareness_readback_contract"],
            quiet_condition="Question is captured, replaced by proof-needed state if necessary, or parked/rejected.",
            what_solving_this_updates=["operator memory candidate posture", "helm noise level", "future proof questions"],
        ),
        HelmIssueFocusMode(
            issue_focus_id="focus_stable_map_receipt_readback",
            display_title="Stable Map Receipt Is Current",
            eli5_summary="The app-facing stable map can be quiet when generation and receipt match, even if raw mirror detail is stale.",
            why_it_matters="It keeps Check Transmission from drowning the helm in raw file-count churn.",
            issue_type="SYSTEM_HEALTH_ISSUE",
            linked_lanes=["check_transmission", "stable_map_app_visibility"],
            linked_worlds=["Helm"],
            linked_questions=[],
            shared_execution_path_id="stable_map_receipt_readback",
            affected_cards=["Check Transmission", "Stable Map"],
            visible_when_selected=[
                "map generation id",
                "bundle hash",
                "receipt match",
                "raw mirror proof/detail status",
            ],
            hidden_when_selected=[
                "unrelated helm cards",
                "Mac sync controls",
                "raw-file sync loop prompts",
            ],
            proof_refs=[
                "generated/read_models/openclaw_map_manifest.json",
                "generated/read_models/sync_health.json#app_visible_map_status",
            ],
            missing_proof=[],
            operator_questions=[],
            required_gates=[],
            blocked_actions=list(BLOCKED_ACTIONS),
            future_gated_actions=[],
            next_safe_move="Keep stable map current status primary and raw mirror mismatch in proof/detail.",
            package_preview_ref=None,
            machine_contract_refs=["operator_map_bundle_contract", "sync_health"],
            quiet_condition="Receipt and PC bundle match; no operator action required for app-facing map.",
            what_solving_this_updates=["Check Transmission quiet display", "stable map app visibility"],
        ),
    ]
    return [asdict(mode) for mode in focus_modes]


def _build_capital_hilton_security_readiness(
    summary: dict[str, Any],
    packet: dict[str, Any],
    facts: list[dict[str, Any]],
    missing_count: int,
    protected_required: bool,
) -> dict[str, Any]:
    finance_preview_exists = bool(summary.get("finance_world_preview") or summary.get("target_world") == "Finance")
    readiness = CapitalHiltonSecurityReadiness(
        provenance_status="CANDIDATE_WITH_MISSING_PROOF",
        missing_proof_count=missing_count,
        protected_proof_required=protected_required,
        shared_execution_path_id="protected_finance_proof_metadata_intake",
        candidate_facts_proven=_candidate_facts_proven(facts, summary),
        finance_world_preview_exists=finance_preview_exists,
        security_pass_complete=False,
        action_authority_granted=False,
        readiness_status="NOT_READY_FOR_SECURITY_PASS_ACTION",
        what_blocks_security_readiness=[
            "10 proof metadata items remain missing",
            "protected proof requires Guardian gate",
            "candidate facts are not machine-proven",
            "operator answers are memory candidates, not proof",
            "security pass is incomplete",
        ],
        what_blocks_action_readiness=[
            "security approval not granted",
            "action authority not granted",
            "invoice generation not allowed",
            "Coupa/browser/email/account access not allowed",
            "send/submit/approval not allowed",
            "tool/model/agent/queue execution not allowed",
        ],
    )
    return asdict(readiness)


def build_security_audit_readiness_packet(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    cap_summary, manifest, cap_packet = _capital_hilton_summary(repo_root)
    generation_id = _map_generation_id(cap_summary, manifest)
    bundle_hash = _bundle_hash(manifest)
    facts = _candidate_facts(cap_summary, cap_packet)
    questions = _operator_questions(cap_summary, cap_packet)
    missing_proof = _missing_proof(cap_summary, cap_packet)
    missing_count = _missing_proof_count(cap_summary, cap_packet)
    protected_required = _protected_proof_required(cap_summary, cap_packet)
    question_records = _build_operator_answer_capture(questions)

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": "security_audit_readiness_packet",
        "pass_id": "pass_1_active_helm_readiness",
        "generated_at": generated_at,
        **NO_AUTHORITY_FLAGS,
        "contract_status": "deterministic_security_audit_readiness_pass_1_metadata_only",
        "operator_summary": (
            "Security Audit Readiness Packet Pass 1 defines how app-facing map claims point back to proof, "
            "how operator answers are captured as memory candidates, how questions quiet, how shared fix paths "
            "consolidate duplicate helm noise, and why Capital Hilton is security-readiness work rather than action."
        ),
        "scope": {
            "pass_1_owns": [
                "map-to-terrain provenance",
                "package map slice rules",
                "Helm vs World responsibility",
                "operator answer capture",
                "question quieting",
                "shared execution path consolidation",
                "Helm Issue Focus Mode",
                "Capital Hilton v0 security-readiness status",
            ],
            "pass_2_not_implemented_here": [
                "coverage gap / unmapped terrain registry",
                "parked breadcrumb review",
                "final security pass readiness criteria",
            ],
            "security_audit_readiness_is_not_security_approval": True,
            "security_readiness_is_not_action_readiness": True,
        },
        "authority_boundary": {
            **NO_AUTHORITY_FLAGS,
            "allowed_current_actions": [
                "deterministic read-model export",
                "operator markdown digest",
                "focused tests",
                "metadata-only provenance/readiness classification",
            ],
            "blocked_current_actions": list(BLOCKED_ACTIONS),
        },
        "verification_statuses": list(VERIFICATION_STATUSES),
        "map_to_terrain_provenance": _build_map_to_terrain_provenance(
            facts=facts,
            missing_proof=missing_proof,
            generation_id=generation_id,
            bundle_hash=bundle_hash,
        ),
        "map_to_terrain_rule": {
            "stable_map_is_app_facing_reflection_not_source_truth": True,
            "claims_without_provenance_must_not_render_as_proven": True,
            "incomplete_provenance_allowed_statuses": [
                "CANDIDATE",
                "MISSING_PROOF",
                "NEEDS_VERIFICATION",
                "BLOCKED",
                "STALE",
                "UNKNOWN_FAIL_CLOSED",
            ],
            "capital_hilton_required_result": {
                "dates_rate_subtotal_one_invoice_are_candidate_unless_proof_refs_exist": True,
                "missing_proof_count": missing_count,
                "protected_proof_required": protected_required,
                "raw_finance_body_included": False,
                "coupa_browser_account_email_authority_exists": False,
            },
        },
        "package_map_slice_rule": _build_package_map_slice_rule(
            missing_proof=missing_proof,
            generation_id=generation_id,
            bundle_hash=bundle_hash,
        ),
        "helm_world_responsibility_boundary": _build_helm_world_boundary(),
        "operator_answer_capture_contract": question_records,
        "allowed_answer_modalities": list(ANSWER_MODALITIES),
        "question_classes": list(QUESTION_CLASSES),
        "question_quieting_rule": _build_question_quieting_rule(),
        "shared_execution_paths": _build_shared_execution_paths(question_records, missing_proof),
        "helm_issue_focus_modes": _build_helm_issue_focus_modes(missing_proof, question_records),
        "capital_hilton_security_readiness": _build_capital_hilton_security_readiness(
            cap_summary,
            cap_packet,
            facts,
            missing_count,
            protected_required,
        ),
        "capital_hilton_current_stable_map_posture": {
            "section_key": "capital_hilton_proof_metadata",
            "stable_map_generation_id": generation_id,
            "bundle_hash": bundle_hash,
            "current_phase": cap_summary.get("current_phase", "HELM_THRESHOLD_LANE"),
            "target_world": cap_summary.get("target_world", "Finance"),
            "lane_destiny": cap_summary.get("lane_destiny", "MOVE_TO_WORLD_ACTION"),
            "missing_proof_count": missing_count,
            "protected_proof_required": protected_required,
            "candidate_facts_are_not_machine_proven": not _candidate_facts_proven(facts, cap_summary),
            "operator_questions_count": len(question_records),
            "all_live_authority_flags_false": _dangerous_authority_flags_false(),
            "no_invoice_generation": True,
            "no_coupa_browser_email_account_controls": True,
            "no_direct_per_packet_read_model_dependency_in_app": True,
        },
        "mission_control_guidance": {
            "show_later": [
                "ELI5 map-to-terrain provenance",
                "package map slice source/proof refs",
                "Helm vs Finance World boundary",
                "operator answer capture items",
                "question quieting state",
                "shared execution path cards",
                "Helm Issue Focus Mode cards",
                "Capital Hilton security-readiness status",
            ],
            "hide_or_block": [
                "live answer popups",
                "security approval controls",
                "invoice generation controls",
                "model/tool/agent launch controls",
                "browser/OAuth/account prompts",
                "Gmail/calendar/Coupa/Telegram controls",
                "send/submit/approval controls",
                "raw private context",
                "fake proven-truth display for operator memory",
            ],
            "focus_mode_behavior": [
                "unrelated helm cards collapse when an issue is selected",
                "related lanes remain visible",
                "proof/details stay behind disclosure",
                "affected worlds appear as linked destinations",
                "next safe move is prominent",
                "no live execution controls appear",
            ],
        },
        "stable_map_integration": {
            "contract_generated_as_read_model": True,
            "summary_included_in_stable_map_now": False,
            "reason_not_included_now": "Pass 1 is standalone; stable-map refresh is a separate lane.",
            "next_map_bundle_refresh_requirement": "Next stable-map refresh should include Security Audit Readiness Packet Pass 1 summary.",
            "safe_summary_for_next_refresh": {
                "contract_id": "security_audit_readiness_packet",
                "pass_id": "pass_1_active_helm_readiness",
                "map_to_terrain_provenance_claims": 5,
                "operator_answer_capture_items": len(question_records),
                "shared_execution_paths": 3,
                "helm_issue_focus_modes": 3,
                "capital_hilton_missing_proof_count": missing_count,
                "security_approval_granted": False,
                "live_authority_added": False,
            },
        },
        "recommended_next_lanes": [
            {
                "lane_id": "security_audit_readiness_packet_pass_2",
                "title": "Security Audit Readiness Packet v0 Pass 2",
                "purpose": "coverage gap / unmapped terrain registry, parked breadcrumb review, final security pass readiness criteria",
                "boundary": "audit/readback only; no security approval or action authority",
            },
            {
                "lane_id": "stable_map_refresh_security_readiness_pass_1",
                "title": "Stable Map Refresh with Security Audit Readiness Pass 1 Summary",
                "purpose": "make Pass 1 visible to Mission Control through the stable map",
                "boundary": "app-facing summary only; no Mac sync/import in this lane",
            },
        ],
        "machine_proof": {
            "source_read_model_refs": list(SOURCE_READ_MODEL_REFS),
            "map_generation_id": generation_id,
            "bundle_hash": bundle_hash,
            "map_to_terrain_provenance_count": 5,
            "operator_answer_capture_count": len(question_records),
            "shared_execution_path_count": 3,
            "helm_issue_focus_mode_count": 3,
            "capital_hilton_missing_proof_count": missing_count,
            "capital_hilton_protected_proof_required": protected_required,
            "capital_hilton_candidate_facts_proven": _candidate_facts_proven(facts, cap_summary),
            "security_approval_granted": False,
            "security_readiness_is_not_action_readiness": True,
            "all_dangerous_authority_flags_false": _dangerous_authority_flags_false(),
            "operator_final_authority": NO_AUTHORITY_FLAGS["operator_final_authority"],
            "raw_private_body_included": False,
            "credential_or_secret_included": False,
            "mission_control_app_code_touched": False,
            "pass_2_included": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_markdown(payload: dict[str, Any]) -> str:
    cap = payload["capital_hilton_security_readiness"]
    map_rule = payload["map_to_terrain_rule"]["capital_hilton_required_result"]
    lines = [
        "# Security Audit Readiness Packet v0 Pass 1",
        "",
        "## ELI5 Summary",
        "",
        "This packet proves OpenClaw can explain where app-facing claims came from, what still needs proof, how Winship answers should be captured, and how the helm can get quieter without pretending the system is safe to act. It does not grant security approval or execution authority.",
        "",
        "## Map-To-Terrain Provenance",
        "",
        "- The stable map is the app-facing reflection, not source truth.",
        "- Claims must point back to read-models, receipts, source cards, ledgers, or proof metadata.",
        "- Missing or incomplete provenance renders as candidate, missing proof, blocked, stale, or fail-closed, not proven truth.",
        f"- Capital Hilton missing proof count: `{map_rule['missing_proof_count']}`.",
        f"- Capital Hilton protected proof required: `{str(map_rule['protected_proof_required']).lower()}`.",
        "",
        "## Package Map Slice Rule",
        "",
        "- Packages may use stable-map slices for orientation.",
        "- Packages must carry source/proof refs and must not treat the map as final truth.",
        "- Raw finance bodies, Coupa/browser/account sessions, credentials, raw email/calendar bodies, raw Excel bodies, and send/submit/approval authority are excluded.",
        "",
        "## Helm vs World",
        "",
        "- Helm owns proof gaps, security readiness, missing operator answers, shared fix paths, and quiet/block/park/world-ready decisions.",
        "- Worlds own domain context and preview; Finance may show Capital Hilton, but Helm owns the not-ready posture.",
        "",
        "## Operator Answer Capture",
        "",
        "- Operator answers become Memory Candidate Receipts, not proof.",
        "- Allowed answer modes include text, yes/no, structured form, screenshot/source/proof refs, I-don't-know, park-this, ask-me-later, move-to-world, and reject-obsolete.",
        "- If proof is still missing after an answer, the question turns into a proof-needed item instead of vanishing.",
        "",
        "## Question Quieting",
        "",
        "- Answered questions leave active helm only when they no longer block, are replaced with proof-needed items, or are parked/rejected/resolved.",
        "- Receipts and proof stay in drill-down.",
        "- Shared answers can update multiple linked lanes.",
        "",
        "## Shared Execution Paths",
        "",
    ]
    for path in payload["shared_execution_paths"]:
        lines.append(f"- `{path['shared_execution_path_id']}`: {path['display_name']} -> {path['next_safe_move']}")
    lines.extend(
        [
            "",
            "## Helm Issue Focus Mode",
            "",
            "- Mission Control may later let Winship select one concise issue and collapse unrelated helm noise.",
            "- Related lanes, worlds, questions, proof, gates, and next safe move remain visible.",
            "- No live execution controls appear.",
            "",
            "## Capital Hilton Security Readiness",
            "",
            f"- Provenance status: `{cap['provenance_status']}`.",
            f"- Missing proof count: `{cap['missing_proof_count']}`.",
            f"- Protected proof required: `{str(cap['protected_proof_required']).lower()}`.",
            f"- Candidate facts proven: `{str(cap['candidate_facts_proven']).lower()}`.",
            f"- Security pass complete: `{str(cap['security_pass_complete']).lower()}`.",
            f"- Action authority granted: `{str(cap['action_authority_granted']).lower()}`.",
            "",
            "## What Remains Blocked",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in BLOCKED_ACTIONS)
    lines.extend(
        [
            "",
            "## Next Safe Move",
            "",
            "- Run Security Audit Readiness Packet Pass 2 later for coverage gaps, parked breadcrumb review, and final security pass readiness criteria.",
            "- Next stable-map refresh should include Security Audit Readiness Packet Pass 1 summary.",
            "",
            "## Authority Flags",
            "",
        ]
    )
    for key, value in NO_AUTHORITY_FLAGS.items():
        lines.append(f"- `{key}` = `{value}`")
    return "\n".join(lines) + "\n"


def export_security_audit_readiness_packet(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> SecurityAuditReadinessPacketExportResult:
    payload = build_security_audit_readiness_packet(repo_root=repo_root, generated_at=generated_at)
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return SecurityAuditReadinessPacketExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        provenance_claim_count=len(payload["map_to_terrain_provenance"]),
        operator_question_count=len(payload["operator_answer_capture_contract"]),
        shared_execution_path_count=len(payload["shared_execution_paths"]),
        helm_issue_focus_count=len(payload["helm_issue_focus_modes"]),
        capital_hilton_missing_proof_count=payload["capital_hilton_security_readiness"]["missing_proof_count"],
        security_approval_granted=payload["machine_proof"]["security_approval_granted"],
        live_authority_added=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export the Security Audit Readiness Packet v0 Pass 1 read-model.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_security_audit_readiness_packet(repo_root=args.repo_root, export_root=args.export_root)
    summary = {
        "schema_version": result.schema_version,
        "json_path": result.json_path,
        "operator_path": result.operator_path,
        "provenance_claim_count": result.provenance_claim_count,
        "operator_question_count": result.operator_question_count,
        "shared_execution_path_count": result.shared_execution_path_count,
        "helm_issue_focus_count": result.helm_issue_focus_count,
        "capital_hilton_missing_proof_count": result.capital_hilton_missing_proof_count,
        "security_approval_granted": result.security_approval_granted,
        "live_authority_added": result.live_authority_added,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        print(f"Security Audit Readiness Packet: `{result.schema_version}`")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
    return 0


__all__ = [
    "ANSWER_MODALITIES",
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "QUESTION_CLASSES",
    "QUESTION_STATES",
    "SCHEMA_VERSION",
    "VERIFICATION_STATUSES",
    "build_security_audit_readiness_packet",
    "export_security_audit_readiness_packet",
    "format_operator_markdown",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
