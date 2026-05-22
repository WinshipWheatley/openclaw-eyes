"""Parked Autonomous Capital Pipeline R&D Experiment v0.

This read-model preserves a future R&D thought experiment as parked,
non-executing architecture material. It is not a business plan, investment
strategy, execution lane, automated money-making system, live finance workflow,
queue item, security-approved action, spend permission, or authority to create
accounts, assets, ads, acquisitions, payouts, ledgers, or runtime behavior.
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

SCHEMA_VERSION = "parked_autonomous_capital_pipeline_experiment_v0"
READ_MODEL_ID = "parked_autonomous_capital_pipeline_experiment"
EXPERIMENT_NAME = "autonomous_capital_pipeline_r_and_d_experiment"
EXPERIMENT_STATUS = "PARKED_HIGH_RISK_R_AND_D_EXPERIMENT"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"

NO_ACTION_AUTHORITY_FLAGS = {
    "capital_spend_allowed": False,
    "domain_purchase_allowed": False,
    "ad_purchase_allowed": False,
    "marketplace_scrape_allowed": False,
    "asset_deployment_allowed": False,
    "checkout_creation_allowed": False,
    "cloud_compute_allocation_allowed": False,
    "api_key_management_allowed": False,
    "account_creation_allowed": False,
    "financial_account_access_allowed": False,
    "banking_access_allowed": False,
    "crypto_wallet_access_allowed": False,
    "payout_allowed": False,
    "acquisition_allowed": False,
    "contract_execution_allowed": False,
    "customer_communication_allowed": False,
    "ledger_write_allowed": False,
    "invoice_generation_allowed": False,
    "model_call_allowed": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "queue_execution_allowed": False,
    "runtime_dispatch_allowed": False,
    "network_operation_allowed": False,
    "browser_oauth_allowed": False,
    "credential_handling_allowed": False,
}

REQUIRED_FUTURE_GATES = {
    "security_pass_vnext_required": True,
    "operator_budget_token_required": True,
    "legal_compliance_review_required": True,
    "tax_accounting_review_required": True,
    "external_account_policy_required": True,
    "payment_processor_policy_required": True,
    "marketplace_terms_review_required": True,
    "ad_platform_terms_review_required": True,
    "open_source_license_review_required": True,
    "data_privacy_review_required": True,
    "guardian_gate_required": True,
    "operator_final_approval_required": True,
    "chief_test_harness_required": True,
    "hermes_architecture_review_required": True,
    "full_trust_clearance_required": True,
}

TOKEN_TYPES = (
    "compute_token",
    "llm_token",
    "operator_attention_token",
    "sandbox_budget_token",
    "security_review_token",
    "experiment_timebox_token",
)

CURRENT_ALLOWED = (
    "read-only modeling",
    "preview-only modeling",
    "parked breadcrumb",
    "security stress-test artifact",
    "future-lane reference",
)

CURRENT_BLOCKED = (
    "all execution",
    "all spending",
    "all external accounts",
    "all financial movement",
    "all deployment",
    "all marketplace/ad activity",
    "all acquisition",
    "all payout",
    "all autonomous queueing",
)

STRESS_TEST_AREAS = (
    "budget authority",
    "external account boundaries",
    "marketplace/API terms",
    "autonomous deployment limits",
    "payment/payout systems",
    "invoice/ledger controls",
    "tool/model/agent execution gates",
    "worker-output intake",
    "Chief/Hermes/Guardian/Operator roles",
    "FULL_TRUST_CLEARANCE",
    "kill-switch posture",
)


@dataclass(frozen=True)
class ArchitectureTrack:
    track_id: str
    display_name: str
    purpose: str
    current_status: str
    blocked_actions: tuple[str, ...]
    authority_summary: str


@dataclass(frozen=True)
class ExperimentPhase:
    phase_id: str
    display_name: str
    conceptual_scope: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    current_status: str
    next_safe_move: str


@dataclass(frozen=True)
class AllowedTokenConcept:
    token_type: str
    status: str
    current_authority: str
    rules: tuple[str, ...]


@dataclass(frozen=True)
class ExperimentSafetyQuestion:
    question_id: str
    question_text: str
    question_class: str
    answer_status: str
    answer_becomes: str
    proof_status: str


@dataclass(frozen=True)
class ParkedExperimentExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    experiment_name: str
    status: str
    phase_count: int
    authority_flags_false: bool
    required_future_gate_count: int
    token_count: int
    action_authority_granted: bool


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _generated_at(value: str | None) -> str:
    return value or datetime.now(timezone.utc).isoformat(timespec="seconds")


def _architecture_tracks() -> list[ArchitectureTrack]:
    return [
        ArchitectureTrack(
            track_id="zero_human_control_experiment",
            display_name="Zero Human Control Experiment",
            purpose="Pure machine execution with a dual-agent verification concept.",
            current_status="BLOCKED_CONCEPT_ONLY",
            blocked_actions=(
                "deployment",
                "marketplace activity",
                "account creation",
                "spend",
                "revenue action",
                "runtime execution",
            ),
            authority_summary="No deployment, marketplace, account, spend, or revenue action exists.",
        ),
        ArchitectureTrack(
            track_id="hybrid_human_variable_experiment",
            display_name="Hybrid Human Variable Experiment",
            purpose="Machine execution plus a human exception gate for macro-risk, ethical, and capital-direction guidance.",
            current_status="BLOCKED_CONCEPT_ONLY",
            blocked_actions=("external action", "account access", "spend", "deployment", "runtime execution"),
            authority_summary="No external action exists; human guidance is only a future study variable.",
        ),
        ArchitectureTrack(
            track_id="meta_ceo_differential_layer",
            display_name="Meta CEO Differential Layer",
            purpose="Compare machine-only and hybrid outcomes across adaptability, efficiency, and human-utility delta.",
            current_status="CONCEPTUAL_ONLY",
            blocked_actions=("authority delegation", "queue decisions", "capital routing", "runtime execution"),
            authority_summary="No authority delegation exists.",
        ),
        ArchitectureTrack(
            track_id="business_3_sovereign_shell_capstone",
            display_name="Business 3 Sovereign Shell Capstone",
            purpose="Long-horizon synthesis concept for macro-scale problem solving.",
            current_status="SPECULATIVE_PARKED",
            blocked_actions=("implementation", "capital allocation", "external operations", "runtime execution"),
            authority_summary="Speculative capstone only; no implementation authority exists.",
        ),
    ]


def _phases() -> list[ExperimentPhase]:
    return [
        ExperimentPhase(
            phase_id="zero_infrastructure_bootstrapping",
            display_name="Phase 1: Zero Infrastructure Bootstrapping",
            conceptual_scope=("conceptual $20 sandboxed capital pool", "digital micro-assets"),
            blocked_actions=(
                "spending",
                "domain purchase",
                "ad purchase",
                "deployment",
                "checkout creation",
                "account creation",
            ),
            current_status="BLOCKED_FUTURE_GATED",
            next_safe_move="Keep as parked stress-test material until budget, legal, account, and security gates exist.",
        ),
        ExperimentPhase(
            phase_id="micro_saas_self_hosted_compute",
            display_name="Phase 2: Micro SaaS / Self-Hosted Compute",
            conceptual_scope=("small SaaS surfaces", "APIs", "self-hosted or paid compute evaluation"),
            blocked_actions=("cloud accounts", "API keys", "CI/CD", "paid compute", "rollback automation"),
            current_status="BLOCKED_FUTURE_GATED",
            next_safe_move="Define compute and deployment policy before any implementation.",
        ),
        ExperimentPhase(
            phase_id="portfolio_diversification_automated_acquisition",
            display_name="Phase 3: Portfolio Diversification / Automated Acquisition",
            conceptual_scope=("micro-business consolidation", "acquisition evaluation"),
            blocked_actions=("brokerage crawling", "acquisitions", "contracts", "payments", "external account access"),
            current_status="BLOCKED_FUTURE_GATED",
            next_safe_move="Require legal, finance, account, and operator gates before any acquisition-related work.",
        ),
        ExperimentPhase(
            phase_id="autonomous_treasury_dividend_routing",
            display_name="Phase 4: Autonomous Treasury / Dividend Routing",
            conceptual_scope=("treasury routing model", "payout-routing thought experiment"),
            blocked_actions=("payouts", "crypto addresses", "banking", "yield loops", "outbound financial transfers"),
            current_status="BLOCKED_FUTURE_GATED",
            next_safe_move="Keep as blocked until payment, tax, legal, security, and kill-switch policy exist.",
        ),
        ExperimentPhase(
            phase_id="business_3_sovereign_shell",
            display_name="Phase 5: Business 3 Sovereign Shell",
            conceptual_scope=("long-horizon capstone", "macro-scale synthesis"),
            blocked_actions=("implementation", "capital movement", "external operations", "runtime execution"),
            current_status="SPECULATIVE_NOT_ACTIONABLE",
            next_safe_move="Park as speculative future-lane material.",
        ),
    ]


def _allowed_tokens() -> list[AllowedTokenConcept]:
    rules = (
        "tokens_do_not_exist_yet",
        "tokens_do_not_grant_external_spend",
        "tokens_do_not_grant_account_access",
        "tokens_do_not_bypass_guardian_or_operator_gates",
        "tokens_must_be_scoped",
        "tokens_must_be_receipted",
        "tokens_must_be_revocable",
        "tokens_must_be_capped",
    )
    return [
        AllowedTokenConcept(
            token_type=token_type,
            status="FUTURE_CONCEPT_ONLY",
            current_authority="NONE",
            rules=rules,
        )
        for token_type in TOKEN_TYPES
    ]


def _safety_questions() -> list[ExperimentSafetyQuestion]:
    questions = [
        ("legal_tax_compliance_boundary", "What is the legal/tax/compliance boundary for any revenue experiment?", "legal_compliance"),
        ("maximum_sandbox_budget", "What is the maximum sandbox budget and who approves it?", "budget_authority"),
        ("allowed_account_payment_surfaces", "What account/payment surfaces are allowed, if any?", "external_account_policy"),
        ("allowed_digital_assets", "What types of digital assets are allowed or blocked?", "asset_policy"),
        ("allowed_marketplaces_platforms", "What marketplaces/platforms are allowed or blocked?", "platform_policy"),
        ("spam_scraping_tos_boundary", "What counts as spam, scraping abuse, or ToS violation?", "terms_and_abuse_boundary"),
        ("proof_before_publish", "What proof is required before any product is published?", "proof_requirement"),
        ("rollback_kill_switch", "What rollback/kill switch is required?", "safety_control"),
        ("success_besides_money", "What does success mean besides money?", "experiment_metric"),
        ("failure_stop_condition", "What does failure/stop condition look like?", "stop_condition"),
        ("human_utility_metric", "What is the human-utility metric being measured?", "human_utility"),
        ("human_only_boundary", "What must always remain human-only?", "human_only_boundary"),
    ]
    return [
        ExperimentSafetyQuestion(
            question_id=question_id,
            question_text=question_text,
            question_class=question_class,
            answer_status="UNANSWERED",
            answer_becomes="MEMORY_CANDIDATE_RECEIPT",
            proof_status="OPERATOR_ANSWER_IS_NOT_PROOF",
        )
        for question_id, question_text, question_class in questions
    ]


def _all_authority_flags_false() -> bool:
    return all(value is False for value in NO_ACTION_AUTHORITY_FLAGS.values())


def build_parked_autonomous_capital_pipeline_experiment(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    del repo_root
    architecture_tracks = [asdict(item) for item in _architecture_tracks()]
    phases = [asdict(item) for item in _phases()]
    allowed_tokens = [asdict(item) for item in _allowed_tokens()]
    safety_questions = [asdict(item) for item in _safety_questions()]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "experiment_name": EXPERIMENT_NAME,
        "experiment_status": EXPERIMENT_STATUS,
        "generated_at": _generated_at(generated_at),
        "contract_type": "parked_r_and_d_thought_experiment",
        "core_human_summary": (
            "Future experiment comparing machine-only execution against hybrid human-guided execution "
            "to study where human intuition creates value over pure automation. It begins conceptually "
            "with a tiny sandboxed budget, but no budget authority exists now."
        ),
        "not_currently": {
            "active_business_plan": False,
            "execution_lane": False,
            "investment_strategy": False,
            "automated_money_making_system": False,
            "live_finance_workflow": False,
            "queue_item": False,
            "security_approved_action": False,
            "permission_to_spend_money": False,
            "permission_to_create_assets_accounts_ads_acquisitions_payouts": False,
        },
        "parking_conditions": {
            "must_remain_parked_until_security_pass_vnext": True,
            "must_remain_parked_until_budget_capital_token_authority": True,
            "must_remain_parked_until_external_account_payment_gates": True,
            "must_remain_parked_until_legal_compliance_tax_review": True,
            "must_remain_parked_until_model_tool_agent_execution_gates": True,
            "must_remain_parked_until_chief_hermes_guardian_operator_review_flow": True,
            "must_remain_parked_until_full_trust_clearance_for_task_class": True,
            "must_remain_parked_until_sandboxed_r_and_d_boundaries": True,
        },
        "conceptual_architecture": architecture_tracks,
        "five_phase_roadmap": phases,
        "no_action_authority_matrix": dict(NO_ACTION_AUTHORITY_FLAGS),
        "required_future_gates": dict(REQUIRED_FUTURE_GATES),
        "allowed_tokens": {
            "status": "FUTURE_CONCEPT_ONLY",
            "tokens_exist_now": False,
            "tokens_grant_external_spend": False,
            "tokens_grant_account_access": False,
            "tokens_bypass_guardian_operator_gates": False,
            "tokens_must_be_scoped_receipted_revocable_capped": True,
            "token_types": allowed_tokens,
        },
        "experiment_safety_questions": {
            "operator_answers_become_memory_candidates": True,
            "operator_answers_are_proof": False,
            "questions": safety_questions,
        },
        "security_stress_test_classification": {
            "is_security_stress_test_artifact": True,
            "current_security_relevance": "HIGH",
            "stress_test_areas": list(STRESS_TEST_AREAS),
            "useful_for_future_security_review": True,
            "authorizes_action": False,
        },
        "relationship_to_current_security_pass": {
            "current_allowed": list(CURRENT_ALLOWED),
            "current_blocked": list(CURRENT_BLOCKED),
            "read_only_preview_modeling_allowed": True,
            "parked_breadcrumb_allowed": True,
            "security_stress_test_artifact_allowed": True,
            "future_lane_reference_allowed": True,
            "action_authority_granted": False,
            "runtime_execution_authority_granted": False,
            "tool_execution_authority_granted": False,
            "model_execution_authority_granted": False,
            "queue_execution_authority_granted": False,
            "account_authority_granted": False,
            "financial_authority_granted": False,
            "spend_authority_granted": False,
            "deployment_authority_granted": False,
        },
        "post_security_governance_batch_relationship": {
            "batch_id": "post_security_governance_batch_v0",
            "prompt_index": 1,
            "batch_role": "parked_high_risk_r_and_d_experiment_reference",
            "stable_map_refresh_deferred": True,
            "commit_deferred_until_prompt_5": True,
            "action_authority_granted": False,
            "next_batch_lane": "security_delta_review_contract",
        },
        "next_safe_move": (
            "Preserve as a parked high-risk R&D stress-test reference; do not implement until future "
            "security, legal/compliance, account, payment, tax, budget-token, Guardian, Chief, Hermes, "
            "Operator, and FULL_TRUST_CLEARANCE gates exist."
        ),
        "machine_proof": {
            "experiment_status_is_parked_high_risk": EXPERIMENT_STATUS == "PARKED_HIGH_RISK_R_AND_D_EXPERIMENT",
            "architecture_track_count": len(architecture_tracks),
            "phase_count": len(phases),
            "all_authority_flags_false": _all_authority_flags_false(),
            "no_spending_authority": NO_ACTION_AUTHORITY_FLAGS["capital_spend_allowed"] is False,
            "no_financial_account_authority": NO_ACTION_AUTHORITY_FLAGS["financial_account_access_allowed"] is False,
            "no_account_creation_authority": NO_ACTION_AUTHORITY_FLAGS["account_creation_allowed"] is False,
            "no_network_authority": NO_ACTION_AUTHORITY_FLAGS["network_operation_allowed"] is False,
            "no_model_tool_agent_runtime_authority": all(
                NO_ACTION_AUTHORITY_FLAGS[key] is False
                for key in (
                    "model_call_allowed",
                    "agent_activation_allowed",
                    "tool_execution_allowed",
                    "runtime_dispatch_allowed",
                )
            ),
            "no_queue_autonomy_authority": NO_ACTION_AUTHORITY_FLAGS["queue_execution_allowed"] is False,
            "no_deployment_acquisition_payout_authority": all(
                NO_ACTION_AUTHORITY_FLAGS[key] is False
                for key in ("asset_deployment_allowed", "acquisition_allowed", "payout_allowed")
            ),
            "allowed_tokens_are_future_concepts_only": True,
            "required_future_gates_all_true": all(REQUIRED_FUTURE_GATES.values()),
            "operator_answers_are_memory_candidates_not_proof": True,
            "security_stress_test_artifact": True,
            "credentials_or_secrets_included": False,
            "external_urls_or_api_calls_required": False,
            "raw_private_bodies_included": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_markdown(payload: dict[str, Any]) -> str:
    proof = payload["machine_proof"]
    tokens = payload["allowed_tokens"]
    lines = [
        "# Parked Autonomous Capital Pipeline R&D Experiment v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        "This preserves a high-risk future thought experiment: compare pure machine execution against a hybrid version where human judgment can change macro-risk, ethics, and capital direction. It is interesting as a way to study human utility against automation, not as an active business plan. It is parked.",
        "",
        "## Status",
        "",
        f"- Experiment name: `{payload['experiment_name']}`.",
        f"- Status: `{payload['experiment_status']}`.",
        "- Current authority: none.",
        "- Current budget authority: none.",
        "- Current external account authority: none.",
        "",
        "## Architecture Preserved",
        "",
    ]
    for track in payload["conceptual_architecture"]:
        lines.append(f"- `{track['track_id']}`: {track['purpose']} Status: `{track['current_status']}`.")
    lines.extend(
        [
            "",
            "## Five Parked Phases",
            "",
        ]
    )
    for phase in payload["five_phase_roadmap"]:
        lines.append(f"- `{phase['phase_id']}`: `{phase['current_status']}`. Blocked actions: {', '.join(phase['blocked_actions'])}.")
    lines.extend(
        [
            "",
            "## Why High Risk",
            "",
            "- It touches future spending, accounts, marketplace terms, deployment, payments, payouts, contracts, tax, legal/compliance, and autonomous execution boundaries.",
            "- Those are exactly the areas OpenClaw must not improvise.",
            "- No part of this read-model implies this will make money or is ready to run.",
            "",
            "## What Must Exist First",
            "",
        ]
    )
    for gate, required in payload["required_future_gates"].items():
        lines.append(f"- `{gate}` = `{str(required).lower()}`")
    lines.extend(
        [
            "",
            "## Tokens",
            "",
            f"- Token status: `{tokens['status']}`.",
            f"- Tokens exist now: `{str(tokens['tokens_exist_now']).lower()}`.",
            f"- Tokens grant external spend: `{str(tokens['tokens_grant_external_spend']).lower()}`.",
            f"- Tokens grant account access: `{str(tokens['tokens_grant_account_access']).lower()}`.",
            "- Future tokens would have to be scoped, receipted, revocable, and capped.",
            "",
            "## Absolutely Blocked Now",
            "",
        ]
    )
    for key, value in payload["no_action_authority_matrix"].items():
        lines.append(f"- `{key}` = `{str(value).lower()}`")
    lines.extend(
        [
            "",
            "## Safety Questions",
            "",
            "- Operator answers become Memory Candidate Receipts, not proof.",
        ]
    )
    for question in payload["experiment_safety_questions"]["questions"]:
        lines.append(f"- {question['question_text']}")
    lines.extend(
        [
            "",
            "## Security Stress-Test Value",
            "",
            "- This is useful because it pressures the exact future gates OpenClaw needs before any external autonomy: budget authority, account boundaries, terms review, deployment limits, payment controls, worker-output intake, Chief/Hermes/Guardian/Operator review, FULL_TRUST_CLEARANCE, and kill-switch posture.",
            "",
            "## Current Security Pass Relationship",
            "",
            "- Allowed now: read-only/preview-only modeling, parked breadcrumb, security stress-test artifact, future-lane reference.",
            "- Blocked now: execution, spending, external accounts, financial movement, deployment, marketplace/ad activity, acquisition, payout, and autonomous queueing.",
            "",
            "## Post-Security Governance Batch",
            "",
            "- This is Prompt 1 material in `post_security_governance_batch_v0`.",
            "- The batch keeps several PC-only backend/read-model lanes together before one later stable-map refresh and checkpoint.",
            "- Stable-map refresh is deferred until Prompt 5.",
            "- Commit is deferred until Prompt 5.",
            "- Next batch lane: `security_delta_review_contract`.",
            "",
            "## Machine Proof",
            "",
            f"- All authority flags false: `{str(proof['all_authority_flags_false']).lower()}`.",
            f"- Allowed tokens are future concepts only: `{str(proof['allowed_tokens_are_future_concepts_only']).lower()}`.",
            f"- Security stress-test artifact: `{str(proof['security_stress_test_artifact']).lower()}`.",
            f"- Content hash: `{proof['content_hash']}`.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_parked_autonomous_capital_pipeline_experiment(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> ParkedExperimentExportResult:
    payload = build_parked_autonomous_capital_pipeline_experiment(repo_root=repo_root, generated_at=generated_at)
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return ParkedExperimentExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        experiment_name=EXPERIMENT_NAME,
        status=EXPERIMENT_STATUS,
        phase_count=len(payload["five_phase_roadmap"]),
        authority_flags_false=payload["machine_proof"]["all_authority_flags_false"],
        required_future_gate_count=len(payload["required_future_gates"]),
        token_count=len(payload["allowed_tokens"]["token_types"]),
        action_authority_granted=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export the parked Autonomous Capital Pipeline R&D experiment read-model.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_parked_autonomous_capital_pipeline_experiment(repo_root=args.repo_root, export_root=args.export_root)
    summary = {
        "schema_version": result.schema_version,
        "json_path": result.json_path,
        "operator_path": result.operator_path,
        "experiment_name": result.experiment_name,
        "status": result.status,
        "phase_count": result.phase_count,
        "authority_flags_false": result.authority_flags_false,
        "required_future_gate_count": result.required_future_gate_count,
        "token_count": result.token_count,
        "action_authority_granted": result.action_authority_granted,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        print(f"Parked R&D experiment: `{result.status}`")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
    return 0


__all__ = [
    "EXPERIMENT_NAME",
    "EXPERIMENT_STATUS",
    "JSON_EXPORT_NAME",
    "NO_ACTION_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "READ_MODEL_ID",
    "REQUIRED_FUTURE_GATES",
    "SCHEMA_VERSION",
    "TOKEN_TYPES",
    "build_parked_autonomous_capital_pipeline_experiment",
    "export_parked_autonomous_capital_pipeline_experiment",
    "format_operator_markdown",
    "main",
    "stable_json",
]
