#!/usr/bin/env python3
"""Build the OpenClaw Activation Gate Register.

The register is intentionally descriptive. It records built, off, gated,
blocked, and proposed capabilities without enabling any flag or probing live
runtime state.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = "activation_gate_register_v0"
DEFAULT_LAST_VERIFIED_AT = "2026-06-26T00:00:00-04:00"
DEFAULT_OUTPUT_DIR = Path("workspaces/openclaw_program")

REQUIRED_FIELDS = (
    "capability_id",
    "display_name",
    "flag_or_config",
    "default_state",
    "current_state_if_verifiable",
    "source_files",
    "tests",
    "audits",
    "canary_status",
    "risk_level",
    "owner",
    "gate_stage",
    "enabled_by",
    "disabled_by",
    "rollback_note",
    "next_required_step",
    "activation_allowed_now",
    "operator_approval_required",
    "reason_if_off",
    "last_verified_at",
    "evidence_refs",
)

GATE_STAGES = (
    "disabled",
    "dry_run",
    "synthetic",
    "canary",
    "operator_approved_live",
    "whitelisted_autonomous",
    "intentionally_off",
    "blocked",
    "proposed",
    "unknown",
)

REQUIRED_CAPABILITY_IDS = (
    "interpreter_lm",
    "frontdoor_model_profile",
    "continuity_capsule",
    "polish_loop_local_builder_bridge",
    "draft_only_email_adapter",
    "cassandra_telegram_delivery",
    "external_model_openrouter_path",
    "computer_use_worker_gateway",
    "legal_sealed_ingestion",
    "polish_loop_factory_mode",
)

SENSITIVE_BLOCKED_CAPABILITY_IDS = (
    "cassandra_telegram_delivery",
    "draft_only_email_adapter",
    "gated_email_send_rail",
    "legal_sealed_ingestion",
    "polish_loop_factory_mode",
)

UPPER_FLAG_RE = re.compile(r"^[A-Z][A-Z0-9_]+$")


def _state(
    summary: str,
    *,
    code_default: str = "unknown",
    production: str = "unknown_not_read_from_env_files_or_services",
    audit_report: str = "",
) -> dict[str, str]:
    return {
        "summary": summary,
        "code_default": code_default,
        "production": production,
        "audit_report": audit_report,
    }


def _capability(
    *,
    capability_id: str,
    display_name: str,
    flag_or_config: Sequence[str],
    default_state: str,
    current_state_if_verifiable: Mapping[str, str],
    source_files: Sequence[str],
    tests: Sequence[str],
    audits: Sequence[str],
    canary_status: str,
    risk_level: str,
    owner: str,
    gate_stage: str,
    enabled_by: str,
    disabled_by: str,
    rollback_note: str,
    next_required_step: str,
    activation_allowed_now: bool,
    operator_approval_required: bool,
    reason_if_off: str,
    evidence_refs: Sequence[str],
    last_verified_at: str,
) -> dict[str, Any]:
    capability = {
        "capability_id": capability_id,
        "display_name": display_name,
        "flag_or_config": list(flag_or_config),
        "default_state": default_state,
        "current_state_if_verifiable": dict(current_state_if_verifiable),
        "source_files": list(source_files),
        "tests": list(tests),
        "audits": list(audits),
        "canary_status": canary_status,
        "risk_level": risk_level,
        "owner": owner,
        "gate_stage": gate_stage,
        "enabled_by": enabled_by,
        "disabled_by": disabled_by,
        "rollback_note": rollback_note,
        "next_required_step": next_required_step,
        "activation_allowed_now": bool(activation_allowed_now),
        "operator_approval_required": bool(operator_approval_required),
        "reason_if_off": reason_if_off,
        "last_verified_at": last_verified_at,
        "evidence_refs": list(evidence_refs),
    }
    validate_capability(capability)
    return capability


def _capability_templates(last_verified_at: str) -> list[dict[str, Any]]:
    return [
        _capability(
            capability_id="interpreter_lm",
            display_name="Interpreter-LM",
            flag_or_config=["OPENCLAW_INTERPRETER_LM"],
            default_state="off",
            current_state_if_verifiable=_state(
                "code default off; production state unknown because production env files/services were not inspected",
                code_default="off unless OPENCLAW_INTERPRETER_LM is truthy",
                audit_report="reported built and default-off; only tests enable the flag",
            ),
            source_files=["interpreter_lm.py", "maestro_listener.py"],
            tests=["tests/test_continuity_stamp.py"],
            audits=[
                "/home/openclaw/workspaces/openclaw_program/OPUS_REENTRY_FINAL_REPORT.md",
                "/home/openclaw/workspaces/openclaw_program/CODEX_OVERNIGHT_RUN_REPORT.md",
            ],
            canary_status="not_run",
            risk_level="medium",
            owner="Opus",
            gate_stage="disabled",
            enabled_by="explicit operator approval after audit and canary evidence",
            disabled_by="OPENCLAW_INTERPRETER_LM default 0",
            rollback_note="unset OPENCLAW_INTERPRETER_LM or set it to 0; deterministic fallback remains available",
            next_required_step="integrated-state audit and bounded canary plan before any live activation",
            activation_allowed_now=False,
            operator_approval_required=True,
            reason_if_off="built flag remains default-off; no live activation evidence is recorded in this register",
            evidence_refs=[
                "interpreter_lm.py:_interpreter_enabled",
                "tests/test_continuity_stamp.py:interpreter flag test coverage",
            ],
            last_verified_at=last_verified_at,
        ),
        _capability(
            capability_id="frontdoor_model_profile",
            display_name="Front-door model profile",
            flag_or_config=[
                "OPENCLAW_FRONTDOOR_MODEL_PROFILE",
                "OPENCLAW_FRONTDOOR_REPLY_TIMEOUT",
                "OPENCLAW_FRONTDOOR_NUM_PREDICT",
                "OPENCLAW_FRONTDOOR_MODEL_ALLOWLIST",
                "OPENCLAW_FRONTDOOR_MODEL_MAX_GB",
            ],
            default_state="off",
            current_state_if_verifiable=_state(
                "code default off; production state unknown; prior audit says canary remained blocked by load/integrated-state review",
                code_default="off unless OPENCLAW_FRONTDOOR_MODEL_PROFILE is truthy and packet is a Maestro front-door packet",
                audit_report="CODEX front-door integration result reports default-off integration and no live enablement",
            ),
            source_files=["protected_generate.py", "chief_llm.py"],
            tests=["tests/test_frontdoor_model_profile.py"],
            audits=[
                "/home/openclaw/workspaces/openclaw_program/FRONT-DOOR-LOCAL-MODEL-PROFILE-SPEC.md",
                "/home/openclaw/workspaces/openclaw_program/CODEX_FRONTDOOR_MODEL_INTEGRATION_RESULT.md",
                "/home/openclaw/workspaces/openclaw_program/CODEX_OVERNIGHT_RUN_REPORT.md",
            ],
            canary_status="queued_for_contained_canary; not_run_due_to_load_and_audit_gap",
            risk_level="medium",
            owner="Opus",
            gate_stage="canary",
            enabled_by="OPENCLAW_FRONTDOOR_MODEL_PROFILE plus operator-approved canary envelope",
            disabled_by="OPENCLAW_FRONTDOOR_MODEL_PROFILE default 0",
            rollback_note="unset OPENCLAW_FRONTDOOR_MODEL_PROFILE; protected_generate falls back to deterministic/non-profile path",
            next_required_step="run a contained front-door canary only after load is acceptable and Opus approves the envelope",
            activation_allowed_now=False,
            operator_approval_required=True,
            reason_if_off="built but canary evidence is incomplete; not production-safe to enable from this register",
            evidence_refs=[
                "protected_generate.py:_frontdoor_model_profile_flag_enabled",
                "chief_llm.py:select_frontdoor_model",
                "tests/test_frontdoor_model_profile.py",
            ],
            last_verified_at=last_verified_at,
        ),
        _capability(
            capability_id="continuity_capsule",
            display_name="Continuity Capsule",
            flag_or_config=["OPENCLAW_CONTINUITY_CAPSULE"],
            default_state="off",
            current_state_if_verifiable=_state(
                "code default off; activation audit reported maestro-listener continuity flag ON, but this generator did not inspect systemd or production env",
                code_default="off unless OPENCLAW_CONTINUITY_CAPSULE is truthy",
                production="unknown_not_reverified; audit_reported_maestro_listener_continuity_on",
                audit_report="activation audit reported maestro-listener continuity flag ON on 2026-06-25",
            ),
            source_files=["maestro_listener.py"],
            tests=["tests/test_continuity_stamp.py"],
            audits=[
                "/home/openclaw/workspaces/openclaw_program/ACTIVATION_AND_WIRING_AUDIT.md",
                "/home/openclaw/workspaces/openclaw_program/OPUS_REENTRY_FINAL_REPORT.md",
            ],
            canary_status="audit_reported_running_flag_on; not_reverified_by_this_task",
            risk_level="low",
            owner="Opus",
            gate_stage="unknown",
            enabled_by="operator-controlled runtime environment",
            disabled_by="OPENCLAW_CONTINUITY_CAPSULE default 0",
            rollback_note="unset OPENCLAW_CONTINUITY_CAPSULE or set it to 0 and restart only through approved service-management procedure",
            next_required_step="Opus should verify current runtime env without exposing secrets and record whether it remains approved live",
            activation_allowed_now=False,
            operator_approval_required=True,
            reason_if_off="current production state was not reverified here; code default is off",
            evidence_refs=[
                "maestro_listener.py:_continuity_enabled",
                "tests/test_continuity_stamp.py",
            ],
            last_verified_at=last_verified_at,
        ),
        _capability(
            capability_id="polish_loop_local_builder_bridge",
            display_name="Polish Loop local builder bridge",
            flag_or_config=["OPENCLAW_POLISH_LOOP_LOCAL_BUILDER"],
            default_state="candidate default-off; not present in this base branch",
            current_state_if_verifiable=_state(
                "candidate built on isolated polish-loop-closure branch; current base branch does not contain the flag; production not enabled",
                code_default="not present in current base; candidate branch default-off",
                production="not_enabled_by_this_task; production_state_unknown_not_read",
                audit_report="CODEX_POLISH_LOOP_CLOSURE_RESULT.md reports synthetic-only fix for blocker #1 on isolated branch",
            ),
            source_files=[
                "polish_loop/orchestrator.py",
                "polish_loop/worker_runtime.py",
                "polish_loop/control_plane.py",
            ],
            tests=["tests/test_polish_loop_closure_bridge.py"],
            audits=[
                "/home/openclaw/workspaces/openclaw_program/POLISH_LOOP_FACTORY_AUDIT.md",
                "/home/openclaw/workspaces/openclaw_program/CODEX_POLISH_LOOP_CLOSURE_RESULT.md",
            ],
            canary_status="synthetic_only_on_isolated_branch; no live loop",
            risk_level="high",
            owner="Opus",
            gate_stage="blocked",
            enabled_by="explicit OPENCLAW_POLISH_LOOP_LOCAL_BUILDER after Opus integration review, remaining blockers, and switch criteria",
            disabled_by="flag absent/off; live loop prohibited",
            rollback_note="leave the flag unset; revert/disable bridge branch before any live dispatch if receipts regress",
            next_required_step="Opus review/integration of closure branch, then blockers #2 and #3 and all 10 switch criteria",
            activation_allowed_now=False,
            operator_approval_required=True,
            reason_if_off="blocker #1 candidate exists but factory remains NOT_READY and this base branch lacks the bridge flag",
            evidence_refs=[
                "polish_loop/worker_runtime.py:run_local_builder_worker",
                "/home/openclaw/workspaces/openclaw_program/CODEX_POLISH_LOOP_CLOSURE_RESULT.md",
            ],
            last_verified_at=last_verified_at,
        ),
        _capability(
            capability_id="draft_only_email_adapter",
            display_name="Draft-only email adapter",
            flag_or_config=["no_live_send_flag; draft adapter is deterministic/no-send", "unknown_live_wiring_flag"],
            default_state="unwired/no-send",
            current_state_if_verifiable=_state(
                "adapter exists as deterministic local artifact generator; live draft and send authority are false; production wiring unknown",
                code_default="no live email send, Gmail draft, Apple Mail draft, network, credential, or workflow authority",
                audit_report="activation audit classifies as ready_synthetic and unwired Level-1 draft-only candidate",
            ),
            source_files=["gated_email_draft_adapter.py"],
            tests=["tests/test_gated_email_draft_adapter.py"],
            audits=["/home/openclaw/workspaces/openclaw_program/ACTIVATION_AND_WIRING_AUDIT.md"],
            canary_status="synthetic_ready; no live email canary",
            risk_level="high",
            owner="Opus",
            gate_stage="synthetic",
            enabled_by="future explicit draft-only router binding plus operator approval; never send authority",
            disabled_by="no router binding and authority_boundary live send/draft fields false",
            rollback_note="remove the router binding and keep generated local artifacts only",
            next_required_step="wire only a synthetic/operator-review draft lane with receipts; do not create live Gmail/Mail drafts",
            activation_allowed_now=False,
            operator_approval_required=True,
            reason_if_off="built local draft artifact path is not live-wired; live email and provider actions remain prohibited",
            evidence_refs=[
                "gated_email_draft_adapter.py:AUTHORITY_BOUNDARY",
                "tests/test_gated_email_draft_adapter.py",
            ],
            last_verified_at=last_verified_at,
        ),
        _capability(
            capability_id="cassandra_telegram_delivery",
            display_name="Cassandra / Telegram delivery",
            flag_or_config=[
                "CASSANDRA_TELEGRAM_DELIVERY_ENABLED",
                "/mnt/c/OpenClaw/logs/cassandra_telegram_delivery_enabled.flag",
                "TELEGRAM_AUTHORIZED_USER_ID",
            ],
            default_state="dry_run/off",
            current_state_if_verifiable=_state(
                "code default dry-run/off; production toggle and authorized user were not inspected",
                code_default="off unless env toggle or flag file is enabled",
                audit_report="activation audit classifies delivery as intentionally disabled by safety",
            ),
            source_files=["cassandra_telegram_delivery.py"],
            tests=["tests/test_cassandra_telegram_delivery.py"],
            audits=["/home/openclaw/workspaces/openclaw_program/ACTIVATION_AND_WIRING_AUDIT.md"],
            canary_status="not_run_live; dry-run tests only",
            risk_level="high",
            owner="Cassandra lane / Opus",
            gate_stage="intentionally_off",
            enabled_by="explicit operator approval plus documented toggle for authorized internal Telegram only",
            disabled_by="default toggle false and dry-run receipt path",
            rollback_note="unset CASSANDRA_TELEGRAM_DELIVERY_ENABLED and remove the enabled flag file",
            next_required_step="keep disabled unless Opus defines an operator-watched internal-only canary",
            activation_allowed_now=False,
            operator_approval_required=True,
            reason_if_off="live Telegram is an external action surface and remains intentionally off",
            evidence_refs=[
                "cassandra_telegram_delivery.py:TOGGLE_ENV_VAR",
                "cassandra_telegram_delivery.py:TelegramDeliveryReceipt",
                "tests/test_cassandra_telegram_delivery.py",
            ],
            last_verified_at=last_verified_at,
        ),
        _capability(
            capability_id="external_model_openrouter_path",
            display_name="External model / OpenRouter path",
            flag_or_config=[
                "OPENCLAW_FREEFORM_CLOUD",
                "OPENROUTER_API_KEY",
                "OPENROUTER_MODEL",
                "OPENCLAW_EXTERNAL_MODEL",
                "OPENCLAW_CASSANDRA_EXTERNAL_MODEL",
                "CASSANDRA_EXTERNAL_MODEL",
            ],
            default_state="fail_closed/no_external_call",
            current_state_if_verifiable=_state(
                "code requires explicit cloud flag, configured model/key, and safety eligibility; secret values and production env were not inspected",
                code_default="off/fail-closed without OPENCLAW_FREEFORM_CLOUD and OpenRouter configuration",
                audit_report="OpenRouter docs/backlog say support is optional guarded plumbing, not default runtime authority",
            ),
            source_files=["protected_generate.py", "chief_llm.py", "openclaw_lm_consult_spine.py"],
            tests=["tests/test_chief_llm_router.py"],
            audits=[
                "docs/operations/OPENROUTER_KEY_STORAGE.md",
                "docs/planning/OPENCLAW_LANE_A_OPENROUTER_SCOUT_BACKLOG.md",
            ],
            canary_status="not_run_live",
            risk_level="high",
            owner="Opus",
            gate_stage="intentionally_off",
            enabled_by="explicit operator approval, safe classification, cloud flag, and provider configuration",
            disabled_by="no explicit OPENCLAW_FREEFORM_CLOUD enablement in this task; fail-closed if key/model missing",
            rollback_note="unset OPENCLAW_FREEFORM_CLOUD and OpenRouter model/provider variables; remove provider credentials through approved secret process",
            next_required_step="keep unwired for live use until cloud policy, privacy routing, and audit/canary evidence are recorded",
            activation_allowed_now=False,
            operator_approval_required=True,
            reason_if_off="external model calls can cross privacy boundaries and require explicit policy approval",
            evidence_refs=[
                "protected_generate.py:OPENCLAW_FREEFORM_CLOUD",
                "chief_llm.py:OPENROUTER_API_KEY",
                "chief_llm.py:_external_model_configured",
            ],
            last_verified_at=last_verified_at,
        ),
        _capability(
            capability_id="computer_use_worker_gateway",
            display_name="Computer Use Worker Gateway",
            flag_or_config=["unknown"],
            default_state="not_built/proposed",
            current_state_if_verifiable=_state(
                "proposed only; no production flag or built gateway was verified in this branch",
                code_default="unknown",
                production="not_applicable_proposed_only",
            ),
            source_files=[],
            tests=[],
            audits=["user task scope: required proposed capability"],
            canary_status="not_applicable",
            risk_level="high",
            owner="Opus",
            gate_stage="proposed",
            enabled_by="future design, audit, canary, and explicit operator approval",
            disabled_by="no implementation or activation flag verified",
            rollback_note="do not create worker bindings until an approved design names rollback and receipts",
            next_required_step="write a design/proposal before implementation; do not grant desktop/browser authority",
            activation_allowed_now=False,
            operator_approval_required=True,
            reason_if_off="not implemented in this evidence pass; proposed only",
            evidence_refs=["required by activation gate register task"],
            last_verified_at=last_verified_at,
        ),
        _capability(
            capability_id="legal_sealed_ingestion",
            display_name="Legal Sealed ingestion",
            flag_or_config=["OPENCLAW_LEGAL_PRIVATE_ROOT", "legal-console synthetic_only bridge"],
            default_state="blocked/no_real_matter_ingestion",
            current_state_if_verifiable=_state(
                "local legal policies and console bridge are synthetic/local-only; real sealed/private ingestion remains blocked",
                code_default="synthetic-only validation paths; no real legal private-root ingestion",
                audit_report="legal validation protocols are planning-only and do not authorize real matter access",
            ),
            source_files=[
                "legal/local_capability_policy.py",
                "legal/path_guard.py",
                "apps/legal-console-spike/src-tauri/src/run.rs",
            ],
            tests=[
                "tests/test_alternative_methods.py",
                "tests/test_support_packet.py",
                "tests/test_legal_mock_discovery_demo.py",
                "tests/test_legal_synthetic_stress_pack.py",
            ],
            audits=[
                "docs/planning/openclaw_legal/law_program/OPENCLAW_LEGAL_REAL_MATTER_LOCAL_ONLY_VALIDATION_PROTOCOL.md",
                "docs/planning/openclaw_legal/law_program/OPENCLAW_LEGAL_REAL_MATTER_MAC_BRIDGE_VALIDATION_PROTOCOL.md",
                "docs/planning/openclaw_legal/law_program/LEGAL_VAULT_PATH_CONTRACT.md",
            ],
            canary_status="blocked; no real matter canary",
            risk_level="critical",
            owner="Legal lane / Opus",
            gate_stage="blocked",
            enabled_by="future explicit legal authorization, sealed-data protocol, audit, and operator approval",
            disabled_by="synthetic-only bridge and path guard constraints",
            rollback_note="keep legal private roots inaccessible; revert any bridge that can touch real sealed material",
            next_required_step="complete legal authorization and sealed-ingestion design before any implementation or test with real material",
            activation_allowed_now=False,
            operator_approval_required=True,
            reason_if_off="legal evidence and sealed/private matter ingestion are explicitly not ready",
            evidence_refs=[
                "legal/local_capability_policy.py",
                "legal/path_guard.py",
                "apps/legal-console-spike/src-tauri/src/run.rs:synthetic_only",
            ],
            last_verified_at=last_verified_at,
        ),
        _capability(
            capability_id="polish_loop_factory_mode",
            display_name="Polish Loop factory mode",
            flag_or_config=[
                "OPENCLAW_POLISH_LOOP_LOCAL_BUILDER",
                "OPENCLAW_POLISH_MAX_PARALLEL_LANES",
                "OPENCLAW_POLISH_LANE_WORKER_CMD",
                "OPENCLAW_TEST_MODE",
                "OPENCLAW_SEND_HOLD",
            ],
            default_state="not_ready/off",
            current_state_if_verifiable=_state(
                "factory remains NOT_READY; no live loop was run or enabled",
                code_default="not a default-on production loop; launch paths set test/send-hold guards for lane workers",
                audit_report="Polish Loop audit switch criteria passed 2/10 and blockers #2/#3 remain",
            ),
            source_files=[
                "polish_loop/orchestrator.py",
                "polish_loop/lane_launcher.py",
                "polish_loop/control_plane.py",
                "builder_watcher.sh",
            ],
            tests=["tests/test_polish_loop_self_scaling.py"],
            audits=[
                "/home/openclaw/workspaces/openclaw_program/POLISH_LOOP_FACTORY_AUDIT.md",
                "/home/openclaw/workspaces/openclaw_program/CODEX_POLISH_LOOP_CLOSURE_RESULT.md",
            ],
            canary_status="blocked; no live loop",
            risk_level="high",
            owner="Opus",
            gate_stage="blocked",
            enabled_by="only after blockers #2 and #3 and all 10 switch criteria pass re-audit",
            disabled_by="audit NOT_READY verdict and live-loop prohibition",
            rollback_note="do not start orchestrator loop; keep production queues/ledgers untouched",
            next_required_step="repair blockers #2 and #3, re-audit all 10 switch criteria, then separately approve activation",
            activation_allowed_now=False,
            operator_approval_required=True,
            reason_if_off="Blocker #1 candidate is not enough; factory mode remains NOT_READY",
            evidence_refs=[
                "/home/openclaw/workspaces/openclaw_program/POLISH_LOOP_FACTORY_AUDIT.md:10-point switch criteria",
                "polish_loop/orchestrator.py",
            ],
            last_verified_at=last_verified_at,
        ),
        _capability(
            capability_id="runtime_module_activation_gate",
            display_name="Runtime / Module Activation Gate v0",
            flag_or_config=["scripted gate report; no enable flag"],
            default_state="blocked",
            current_state_if_verifiable=_state(
                "v0 gate always blocks runtime/module activation and claims no runtime health",
                code_default="activation_allowed false",
                audit_report="test coverage proves no runtime side effects or SQLite touch",
            ),
            source_files=["scripts/check_runtime_activation_gate.py"],
            tests=["tests/test_runtime_activation_gate.py"],
            audits=[],
            canary_status="not_applicable; readiness contract only",
            risk_level="medium",
            owner="Opus",
            gate_stage="blocked",
            enabled_by="future explicit prerequisites: approval, rollback, manifest, boundary, receipt, dry-run proof",
            disabled_by="blocked_v0_contract",
            rollback_note="keep using the v0 blocked report until a new audited gate version exists",
            next_required_step="satisfy and record all gate prerequisites before runtime/module activation",
            activation_allowed_now=False,
            operator_approval_required=True,
            reason_if_off="the gate is intentionally a blocker, not an activator",
            evidence_refs=[
                "scripts/check_runtime_activation_gate.py:build_activation_gate_report",
                "tests/test_runtime_activation_gate.py",
            ],
            last_verified_at=last_verified_at,
        ),
        _capability(
            capability_id="gated_email_send_rail",
            display_name="Gated email send rail",
            flag_or_config=["approval receipt inputs only; no live provider flag"],
            default_state="blocked/no-send",
            current_state_if_verifiable=_state(
                "send rail exists as a deterministic fail-closed receipt surface; live provider/network authority is false",
                code_default="no live SMTP/Gmail/Mail/provider/network authority",
                audit_report="not in scope for activation; included because it is a built sensitive off capability",
            ),
            source_files=["gated_email_send_adapter.py"],
            tests=["tests/test_gated_email_send_adapter.py"],
            audits=[],
            canary_status="not_run; live send prohibited",
            risk_level="critical",
            owner="Opus",
            gate_stage="intentionally_off",
            enabled_by="not enabled by this register; any future send path requires separate approval and legal/comms policy",
            disabled_by="AUTHORITY_BOUNDARY live send/provider fields false",
            rollback_note="keep provider send calls absent; remove any caller binding that attempts live send",
            next_required_step="do not activate; use draft-only review rail instead",
            activation_allowed_now=False,
            operator_approval_required=True,
            reason_if_off="email sending is an external action and remains outside this task",
            evidence_refs=[
                "gated_email_send_adapter.py:AUTHORITY_BOUNDARY",
                "tests/test_gated_email_send_adapter.py",
            ],
            last_verified_at=last_verified_at,
        ),
        _capability(
            capability_id="cassandra_telegram_dryrun_inbox",
            display_name="Cassandra Telegram dry-run inbox",
            flag_or_config=["local JSON dry-run inbox paths; no live Telegram credential flag"],
            default_state="dry_run",
            current_state_if_verifiable=_state(
                "dry-run inbox is local-only and denies Telegram live connection, credentials, send, email, browser, and ledger posting",
                code_default="dry-run only with authority flags false",
                audit_report="synthetic dry-run inbox; no live Telegram",
            ),
            source_files=["cassandra_telegram_dryrun_inbox.py"],
            tests=["tests/test_cassandra_telegram_dryrun_inbox.py"],
            audits=[],
            canary_status="synthetic_only",
            risk_level="medium",
            owner="Cassandra lane / Opus",
            gate_stage="dry_run",
            enabled_by="local synthetic fixture processing only",
            disabled_by="authority boundary blocks live Telegram and external actions",
            rollback_note="delete local dry-run fixture binding; no live Telegram state exists to roll back",
            next_required_step="keep as a synthetic proof source; do not connect to Telegram",
            activation_allowed_now=False,
            operator_approval_required=True,
            reason_if_off="live Telegram delivery remains disabled even though dry-run inbox can process local fixtures",
            evidence_refs=[
                "cassandra_telegram_dryrun_inbox.py:AUTHORITY_BOUNDARY",
                "tests/test_cassandra_telegram_dryrun_inbox.py",
            ],
            last_verified_at=last_verified_at,
        ),
        _capability(
            capability_id="active_machinery_classification",
            display_name="Active Machinery classification orchestrator",
            flag_or_config=["dry_run mode; Gemini worker dispatch operator-gated"],
            default_state="dry_run",
            current_state_if_verifiable=_state(
                "classification orchestrator exists with dry-run/mock classification and no autonomous worker dispatch",
                code_default="dry-run/mock classification path",
                audit_report="activation audit classifies as ready_synthetic",
            ),
            source_files=["active_machinery_classification_orchestrator.py"],
            tests=["tests/test_active_machinery_classification_orchestrator.py"],
            audits=["/home/openclaw/workspaces/openclaw_program/ACTIVATION_AND_WIRING_AUDIT.md"],
            canary_status="synthetic_ready",
            risk_level="medium",
            owner="Opus",
            gate_stage="dry_run",
            enabled_by="future operator-approved Gemini verification dispatch",
            disabled_by="dry-run mode and operator gate",
            rollback_note="leave worker dispatch disabled; keep mock classification only",
            next_required_step="record a synthetic-to-canary plan before any Gemini worker dispatch",
            activation_allowed_now=False,
            operator_approval_required=True,
            reason_if_off="built as synthetic classification; live worker dispatch remains gated",
            evidence_refs=[
                "active_machinery_classification_orchestrator.py",
                "tests/test_active_machinery_classification_orchestrator.py",
            ],
            last_verified_at=last_verified_at,
        ),
        _capability(
            capability_id="agent_package_preview_contract",
            display_name="Agent package preview contract",
            flag_or_config=["contract toggles: runtime/model/agent/tool/package send authority false"],
            default_state="intentionally disabled",
            current_state_if_verifiable=_state(
                "metadata-only preview contract exists; all dispatch/external authority toggles are false",
                code_default="operator_final_authority only; no runtime/model/agent/tool execution authority",
                audit_report="activation audit classifies as intentionally_disabled_safety",
            ),
            source_files=["agent_package_preview_contract.py"],
            tests=["tests/test_agent_package_preview_contract.py"],
            audits=["/home/openclaw/workspaces/openclaw_program/ACTIVATION_AND_WIRING_AUDIT.md"],
            canary_status="synthetic_ready; no dispatch canary",
            risk_level="medium",
            owner="Opus",
            gate_stage="intentionally_off",
            enabled_by="future explicit operator approval for any dispatch-capable successor",
            disabled_by="contract authority flags false",
            rollback_note="keep metadata-only contract; reject any package preview that becomes dispatch",
            next_required_step="use as review artifact only; do not grant package send authority",
            activation_allowed_now=False,
            operator_approval_required=True,
            reason_if_off="preview is intentionally not an activation or dispatch mechanism",
            evidence_refs=[
                "agent_package_preview_contract.py",
                "tests/test_agent_package_preview_contract.py",
            ],
            last_verified_at=last_verified_at,
        ),
        _capability(
            capability_id="niles_album_evidence_intake_boundary",
            display_name="Niles album evidence intake boundary",
            flag_or_config=["metadata-only intake contract; no live private-root flag"],
            default_state="synthetic/metadata-only",
            current_state_if_verifiable=_state(
                "metadata-only boundary exists; raw audio, DAW contents, broad drive scans, automation, and mutation are blocked",
                code_default="no real metadata recorded unless operator-supplied through bounded metadata fields",
                audit_report="activation audit classifies as ready_synthetic",
            ),
            source_files=["niles_album_evidence_intake_boundary.py"],
            tests=["tests/test_niles_album_evidence_intake_boundary.py"],
            audits=["/home/openclaw/workspaces/openclaw_program/ACTIVATION_AND_WIRING_AUDIT.md"],
            canary_status="synthetic_ready; no real album evidence ingest",
            risk_level="medium",
            owner="Niles lane / Opus",
            gate_stage="synthetic",
            enabled_by="operator-supplied metadata only under approved intake boundary",
            disabled_by="blocked raw/private evidence types and no broad scan authority",
            rollback_note="reject metadata packets and keep raw/private evidence inaccessible",
            next_required_step="if needed, run only synthetic metadata tests or operator-supplied metadata review",
            activation_allowed_now=False,
            operator_approval_required=True,
            reason_if_off="real album/private evidence ingestion is not activated; only metadata boundary exists",
            evidence_refs=[
                "niles_album_evidence_intake_boundary.py:NO_AUTHORITY_FLAGS",
                "tests/test_niles_album_evidence_intake_boundary.py",
            ],
            last_verified_at=last_verified_at,
        ),
        _capability(
            capability_id="lm_consult_spine",
            display_name="Advisory LM consult spine",
            flag_or_config=[
                "OPENCLAW_ENABLE_LM_CONSULTS",
                "OPENCLAW_LM_PROVIDER",
                "OPENCLAW_GEMINI_MODEL",
                "OPENCLAW_GEMINI_FORM_MODEL",
                "GOOGLE_API_KEY",
                "GEMINI_API_KEY",
                "GOOGLE_GENERATIVE_AI_API_KEY",
            ],
            default_state="provider_config_required/off",
            current_state_if_verifiable=_state(
                "advisory-only consult spine is built; provider credentials/config and production env were not inspected",
                code_default="blocked unless approved provider config is present and consults are enabled",
                audit_report="watch-desk status language records blocked provider config as the safe default",
            ),
            source_files=["openclaw_lm_consult_spine.py"],
            tests=[],
            audits=[],
            canary_status="not_run_by_this_task",
            risk_level="high",
            owner="Opus",
            gate_stage="intentionally_off",
            enabled_by="explicit operator approval and approved provider configuration; advisory-only",
            disabled_by="provider config required and no runtime mutation authority",
            rollback_note="unset OPENCLAW_ENABLE_LM_CONSULTS and provider/model variables",
            next_required_step="keep advisory-only and record any provider probe evidence separately without exposing credentials",
            activation_allowed_now=False,
            operator_approval_required=True,
            reason_if_off="external/provider-backed consults require explicit approval and credential-safe verification",
            evidence_refs=[
                "openclaw_lm_consult_spine.py:GENERIC_ENABLE_ENV",
                "openclaw_lm_consult_spine.py:AUTHORITY_FALSE",
            ],
            last_verified_at=last_verified_at,
        ),
    ]


def validate_capability(capability: Mapping[str, Any]) -> None:
    missing = [field for field in REQUIRED_FIELDS if field not in capability]
    if missing:
        raise ValueError(f"capability {capability.get('capability_id', '<unknown>')} missing fields: {missing}")
    gate_stage = str(capability["gate_stage"])
    if gate_stage not in GATE_STAGES:
        raise ValueError(f"capability {capability['capability_id']} has invalid gate_stage {gate_stage!r}")
    if capability["activation_allowed_now"] and not capability["operator_approval_required"]:
        raise ValueError(f"capability {capability['capability_id']} cannot be activation-ready without approval tracking")
    if capability["activation_allowed_now"] and str(capability["canary_status"]).startswith(("not_", "blocked")):
        raise ValueError(f"capability {capability['capability_id']} cannot be activation-ready without canary evidence")


def _flags_from_capability(capability: Mapping[str, Any]) -> list[str]:
    flags: list[str] = []
    for item in capability["flag_or_config"]:
        text = str(item)
        if UPPER_FLAG_RE.match(text):
            flags.append(text)
    return flags


def _read_text_if_small(path: Path, *, max_bytes: int = 2_000_000) -> str:
    if not path.is_file():
        return ""
    try:
        if path.stat().st_size > max_bytes:
            return ""
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _iter_scan_paths(capability: Mapping[str, Any]) -> Iterable[str]:
    for key in ("source_files", "tests"):
        for raw in capability[key]:
            text = str(raw)
            if text and not text.startswith("/"):
                yield text


def detect_flags(repo_root: Path, capabilities: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Detect listed uppercase flags in the capability source/test paths."""

    all_flags = sorted({flag for capability in capabilities for flag in _flags_from_capability(capability)})
    scan_paths = sorted({path for capability in capabilities for path in _iter_scan_paths(capability)})
    file_texts = {
        path: _read_text_if_small(repo_root / path)
        for path in scan_paths
        if (repo_root / path).is_file()
    }

    detection: dict[str, dict[str, Any]] = {}
    for flag in all_flags:
        found = sorted(path for path, text in file_texts.items() if flag in text)
        detection[flag] = {
            "status": "found" if found else "not_found_in_scanned_repo_paths",
            "files": found,
        }
    return detection


def _missing_repo_files(repo_root: Path, capabilities: Sequence[Mapping[str, Any]]) -> list[str]:
    missing: set[str] = set()
    for capability in capabilities:
        for key in ("source_files", "tests"):
            for raw in capability[key]:
                path = str(raw)
                if path and not path.startswith("/") and not (repo_root / path).exists():
                    missing.add(path)
    return sorted(missing)


def _summarize(capabilities: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    def ids_matching(predicate: Any) -> list[str]:
        return sorted(str(item["capability_id"]) for item in capabilities if predicate(item))

    return {
        "total_capabilities": len(capabilities),
        "activation_allowed_now": ids_matching(lambda item: item["activation_allowed_now"] is True),
        "currently_off_or_blocked": ids_matching(
            lambda item: item["gate_stage"] in {"disabled", "intentionally_off", "blocked", "proposed", "unknown"}
        ),
        "ready_for_canary": ids_matching(
            lambda item: item["gate_stage"] == "canary" and item["activation_allowed_now"] is False
        ),
        "blocked": ids_matching(lambda item: item["gate_stage"] == "blocked"),
        "intentionally_off": ids_matching(lambda item: item["gate_stage"] == "intentionally_off"),
        "unknown_production_state": ids_matching(
            lambda item: "unknown" in json.dumps(item["current_state_if_verifiable"], sort_keys=True)
        ),
    }


def build_activation_gate_register(
    *,
    repo_root: str | Path = ".",
    last_verified_at: str = DEFAULT_LAST_VERIFIED_AT,
) -> dict[str, Any]:
    repo = Path(repo_root)
    capabilities = sorted(
        _capability_templates(last_verified_at),
        key=lambda item: item["capability_id"],
    )
    for capability in capabilities:
        validate_capability(capability)

    present_ids = {item["capability_id"] for item in capabilities}
    missing_required = sorted(set(REQUIRED_CAPABILITY_IDS) - present_ids)
    if missing_required:
        raise ValueError(f"missing required capabilities: {missing_required}")

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": last_verified_at,
        "policy": {
            "descriptive_only": True,
            "features_enabled_by_this_register": False,
            "production_flags_changed": False,
            "production_env_files_inspected": False,
            "systemd_inspected_or_modified": False,
            "live_external_actions_run": False,
            "production_databases_touched": False,
            "classification_rule": "Do not mark a capability enabled or safe to enable unless evidence proves it.",
        },
        "gate_stages": list(GATE_STAGES),
        "required_fields": list(REQUIRED_FIELDS),
        "capabilities": capabilities,
        "summary": _summarize(capabilities),
        "verification": {
            "flag_detection": detect_flags(repo, capabilities),
            "missing_repo_evidence_files": _missing_repo_files(repo, capabilities),
        },
    }


def stable_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _format_list(values: Sequence[str]) -> str:
    if not values:
        return "none recorded"
    return ", ".join(f"`{value}`" for value in values)


def _format_bool(value: bool) -> str:
    return "yes" if value else "no"


def _state_summary(state: Mapping[str, str]) -> str:
    return str(state.get("summary") or "unknown")


def render_markdown(register: Mapping[str, Any]) -> str:
    capabilities = list(register["capabilities"])
    lines = [
        "# Activation Gate Register",
        "",
        f"Schema: `{register['schema_version']}`",
        f"Generated: `{register['generated_at']}`",
        "",
        "This register is descriptive only. It does not enable features, edit production config, inspect secrets, touch systemd, run canaries, or perform live external actions.",
        "",
        "## Policy",
        "",
    ]
    policy = register["policy"]
    for key in sorted(policy):
        value = policy[key]
        lines.append(f"- `{key}`: `{str(value).lower() if isinstance(value, bool) else value}`")

    summary = register["summary"]
    lines.extend(
        [
            "",
            "## Summary",
            "",
            f"- Total capabilities registered: `{summary['total_capabilities']}`",
            f"- Activation allowed now: {_format_list(summary['activation_allowed_now'])}",
            f"- Ready for canary queue: {_format_list(summary['ready_for_canary'])}",
            f"- Blocked: {_format_list(summary['blocked'])}",
            f"- Intentionally off: {_format_list(summary['intentionally_off'])}",
            f"- Unknown production state: {_format_list(summary['unknown_production_state'])}",
            "",
            "| Capability | Stage | Current state | Activation allowed now | Next required step |",
            "| --- | --- | --- | --- | --- |",
        ]
    )

    for capability in capabilities:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"{capability['display_name']} (`{capability['capability_id']}`)",
                    f"`{capability['gate_stage']}`",
                    _state_summary(capability["current_state_if_verifiable"]).replace("|", "\\|"),
                    _format_bool(bool(capability["activation_allowed_now"])),
                    str(capability["next_required_step"]).replace("|", "\\|"),
                ]
            )
            + " |"
        )

    lines.extend(["", "## Capabilities", ""])
    for capability in capabilities:
        state = capability["current_state_if_verifiable"]
        lines.extend(
            [
                f"### {capability['display_name']} (`{capability['capability_id']}`)",
                "",
                f"- Flag/config: {_format_list(capability['flag_or_config'])}",
                f"- Default state: `{capability['default_state']}`",
                f"- Current state if verifiable: {_state_summary(state)}",
                f"- Production state: `{state.get('production', 'unknown')}`",
                f"- Gate stage: `{capability['gate_stage']}`",
                f"- Canary status: `{capability['canary_status']}`",
                f"- Risk level: `{capability['risk_level']}`",
                f"- Owner: `{capability['owner']}`",
                f"- Activation allowed now: `{_format_bool(bool(capability['activation_allowed_now']))}`",
                f"- Operator approval required: `{_format_bool(bool(capability['operator_approval_required']))}`",
                f"- Reason if off: {capability['reason_if_off']}",
                f"- Enabled by: {capability['enabled_by']}",
                f"- Disabled by: {capability['disabled_by']}",
                f"- Rollback: {capability['rollback_note']}",
                f"- Next required step: {capability['next_required_step']}",
                f"- Source files: {_format_list(capability['source_files'])}",
                f"- Tests: {_format_list(capability['tests'])}",
                f"- Audits: {_format_list(capability['audits'])}",
                f"- Evidence refs: {_format_list(capability['evidence_refs'])}",
                f"- Last verified at: `{capability['last_verified_at']}`",
                "",
            ]
        )

    detection = register["verification"]["flag_detection"]
    lines.extend(["## Flag Detection", ""])
    for flag in sorted(detection):
        info = detection[flag]
        lines.append(f"- `{flag}`: `{info['status']}` in {_format_list(info['files'])}")

    missing = register["verification"]["missing_repo_evidence_files"]
    lines.extend(
        [
            "",
            "## Evidence Gaps",
            "",
            f"- Missing repository evidence files referenced by register: {_format_list(missing)}",
            "- Production env/service state: `not inspected by this task`",
            "- Feature activation performed by this task: `no`",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(
    *,
    repo_root: str | Path = ".",
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    last_verified_at: str = DEFAULT_LAST_VERIFIED_AT,
) -> dict[str, Path]:
    register = build_activation_gate_register(repo_root=repo_root, last_verified_at=last_verified_at)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    json_path = output / "activation_gate_register.json"
    markdown_path = output / "ACTIVATION_GATE_REGISTER.md"
    json_path.write_text(stable_json(register), encoding="utf-8")
    markdown_path.write_text(render_markdown(register), encoding="utf-8")
    return {"json": json_path, "markdown": markdown_path}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the OpenClaw Activation Gate Register.")
    parser.add_argument("--repo-root", default=".", help="Repository root to scan for named evidence files.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for ACTIVATION_GATE_REGISTER.md and activation_gate_register.json.",
    )
    parser.add_argument(
        "--last-verified-at",
        default=DEFAULT_LAST_VERIFIED_AT,
        help="Deterministic timestamp written into register records.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    paths = write_outputs(
        repo_root=Path(args.repo_root),
        output_dir=Path(args.output_dir),
        last_verified_at=args.last_verified_at,
    )
    print(f"wrote {paths['markdown']}")
    print(f"wrote {paths['json']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
