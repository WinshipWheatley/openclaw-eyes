"""Chief Dynamic Workflow deferred build packet.

This packet stores the intention to build the Chief workflow compiler, deterministic orchestration,
and known unknowns ledger once Codex 5.5 credits return. It does not execute live workflow actions,
send email, or run unverified scripts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = "chief_dynamic_workflow_deferred_build_v0"
READ_MODEL_ID = "chief_dynamic_workflow_deferred_build"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"

@dataclass(frozen=True)
class KnownUnknownsLedgerSpec:
    required_facts: tuple[str, ...]
    proven_facts: tuple[str, ...]
    assumptions: tuple[str, ...]
    missing_proof: tuple[str, ...]
    unsafe_claims: tuple[str, ...]
    operator_decisions_required: tuple[str, ...]
    capability_gaps: tuple[str, ...]
    next_package_that_resolves_each_unknown: tuple[str, ...]

@dataclass(frozen=True)
class WorkerPackageContractSpec:
    task_ref_required: bool = True
    target_repo_options: tuple[str, ...] = ("PC", "MAC", "BOTH", "AUDIT_ONLY")
    priority_required: bool = True
    model_class_recommended_required: bool = True
    exact_files_to_inspect_required: bool = True
    allowed_changes_required: bool = True
    forbidden_changes_required: bool = True
    expected_output_required: bool = True
    required_receipts_required: bool = True
    stop_condition_required: bool = True
    collision_scope_required: bool = True
    can_run_parallel_required: bool = True
    human_trial_after_required: bool = True

@dataclass(frozen=True)
class DeferredBuildPacket:
    packet_ref: str
    mission_ref: str
    title: str
    status: str
    resume_after_operator_time: str
    timezone_assumption: str
    preferred_model: str
    fallback_models: dict[str, str]
    why_deferred: str
    current_context_summary: str
    existing_supporting_components: tuple[str, ...]
    missing_components: tuple[str, ...]
    first_codex_task: str
    next_prompt_for_codex_5_5: str
    allowed_prework_before_resume: tuple[str, ...]
    forbidden_prework_before_resume: tuple[str, ...]
    right_sized_package_plan: str
    known_unknowns_ledger: KnownUnknownsLedgerSpec
    validation_plan: tuple[str, ...]
    risk_register: tuple[str, ...]
    proof_refs: tuple[str, ...]
    operator_summary: str
    customer_visibility: str
    developer_visibility: str

def generate_deferred_build_packet() -> dict[str, Any]:
    packet = DeferredBuildPacket(
        packet_ref="deferred_build:chief_dynamic_workflow:v0",
        mission_ref="mission:live_arts_md_invoice_chaos_resolution",
        title="Chief Dynamic Workflow - Deterministic Orchestration & Known Unknowns Ledger",
        status="DEFERRED_WAITING_FOR_CODEX_5_5_CAPACITY",
        resume_after_operator_time="Saturday, May 30, 2026 at 5:11 PM",
        timezone_assumption="America/New_York",
        preferred_model="GPT-5.5 Codex",
        fallback_models={
            "Gemini 3.1 Pro": "audit/design only",
            "Gemini 3.5 Flash": "bounded implementation/triage",
            "GPT-5.3-Codex-Spark": "small surgical UI/parser fixes only",
        },
        why_deferred="Codex 5.5 credits exhausted during Live Arts MD chaos; critical workflow infrastructure must be built with a strong coding orchestrator.",
        current_context_summary="Manual send happened outside OpenClaw for Live Arts MD. OpenClaw needs execution venue tracking, manual-send proof capture, and Chief/Hermes to enforce critical path focus to prevent credit burn.",
        existing_supporting_components=(
            "hermes_mission_sentinel.py",
            "hermes_chief_build_handoff.py",
            "purpose_bound_automation_charter.py",
            "hermes_gravity_controller.py",
            "delegated_package_graph.py",
            "operator_action_event_journal.py",
            "client_invoice_workflow_framework.py"
        ),
        missing_components=(
            "chief_dynamic_workflow_manifest.py",
            "known_unknowns_ledger.py",
            "worker_package_contract.py",
            "automated_mac_pdf_export_rail"
        ),
        first_codex_task="chief_dynamic_workflow_manifest.py",
        next_prompt_for_codex_5_5=(
            "Chief Dynamic Workflow Manifest v0 \u2014 Deterministic Orchestration + Known Unknowns Ledger\n\n"
            "Please implement chief_dynamic_workflow_manifest.py, known_unknowns_ledger.py, and "
            "worker_package_contract.py with tests and generated read-models. Do not execute live "
            "workers or mutate state. Start with deterministic JSON manifest outputs only."
        ),
        allowed_prework_before_resume=(
            "Audit existing framework files",
            "Draft deferred build structures",
            "Small UI/parser fixes with Spark",
        ),
        forbidden_prework_before_resume=(
            "Running live agents",
            "Sending emails",
            "Creating Gmail drafts",
            "Using browser or Coupa",
            "Reading workbook cells",
            "Generating or exporting invoices",
            "Mutating ledgers or production state",
            "Starting Repo B",
            "Pushing code to git"
        ),
        right_sized_package_plan="Split work into PC/Mac/audit-only tasks. Avoid duplicate work. Default 4 workers, 8 for safe audit-only, 16 max isolated.",
        known_unknowns_ledger=KnownUnknownsLedgerSpec(
            required_facts=("Live Arts MD manual send proof capture",),
            proven_facts=("Manual send executed outside OpenClaw", "Codex credits exhausted"),
            assumptions=("Mac Excel PDF export is promising edge rail",),
            missing_proof=("Live Arts MD manual send receipt",),
            unsafe_claims=("Invoice sent", "Ledger updated"),
            operator_decisions_required=("Approve final workflow orchestrator rules",),
            capability_gaps=("Gmail/Safari DOM automation is low confidence",),
            next_package_that_resolves_each_unknown=("chief_dynamic_workflow_manifest.py",)
        ),
        validation_plan=(
            "Tests check deferred packet existence and parsing",
            "Verify resume time and preferred model",
            "Verify Spark is restricted and Gemini is audit-only",
            "Verify customer mode hides packet",
            "Validate known unknowns ledger fields"
        ),
        risk_register=(
            "Uncontrolled agent swarms if max_parallel is ignored",
            "Burn of new Codex credits if tasks aren't bounded",
        ),
        proof_refs=("operator_action_event_journal.json",),
        operator_summary="Deferred build packet created to resume Chief Dynamic Workflow construction when Codex 5.5 credits return.",
        customer_visibility="hidden",
        developer_visibility="visible",
    )

    return asdict(packet)


def write_models(export_root: Path) -> None:
    export_root.mkdir(parents=True, exist_ok=True)
    payload = generate_deferred_build_packet()

    json_path = export_root / JSON_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")

    operator_path = export_root / OPERATOR_EXPORT_NAME
    md = [
        f"# {payload['title']}",
        f"**Status**: {payload['status']}",
        f"**Resume After**: {payload['resume_after_operator_time']} ({payload['timezone_assumption']})",
        f"**Preferred Model**: {payload['preferred_model']}",
        "",
        "## Why Deferred",
        payload["why_deferred"],
        "",
        "## Prompt for GPT-5.5 Codex",
        "```text",
        payload["next_prompt_for_codex_5_5"],
        "```",
        "",
        "## Prework",
        "**Allowed**:",
        *("- " + a for a in payload["allowed_prework_before_resume"]),
        "",
        "**Forbidden**:",
        *("- " + f for f in payload["forbidden_prework_before_resume"]),
    ]
    operator_path.write_text("\n".join(md) + "\n", encoding="utf-8")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--export-dir", type=str, default=str(DEFAULT_EXPORT_ROOT))
    args = parser.parse_args()
    write_models(Path(args.export_dir))
