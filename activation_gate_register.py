#!/usr/bin/env python3
"""Build the OpenClaw Activation Gate Register.

The register is intentionally descriptive. It records built, off, gated,
blocked, and proposed capabilities without enabling any flag. Optional live
environment reconciliation is read-only, whitelisted, and redacted.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = "activation_gate_register_v0"
DEFAULT_LAST_VERIFIED_AT = "2026-06-26T00:00:00-04:00"
DEFAULT_OUTPUT_DIR = Path("workspaces/openclaw_program")

LIVE_STATE_VALUES = (
    "enabled_verified",
    "disabled_verified",
    "unset_default_off",
    "unknown_requires_operator_verification",
    "not_applicable",
    "conflicting_sources",
    "configured_but_inert",
    "dry_run_verified",
)

LIVE_ENV_WHITELIST = (
    "OPENCLAW_INTERPRETER_LM",
    "OPENCLAW_FRONTDOOR_MODEL_PROFILE",
    "OPENCLAW_CONTINUITY_CAPSULE",
    "OPENCLAW_PACKET_SOURCE",
    "OPENCLAW_POLISH_LOOP_LOCAL_BUILDER",
    "OPENCLAW_POLISH_LOOP_FILE_LEDGER_BRIDGE",
    "OPENCLAW_FREEFORM_CLOUD",
    "OPENCLAW_FRONTDOOR_REPLY_TIMEOUT",
    "OPENCLAW_FRONTDOOR_NUM_PREDICT",
    "OPENCLAW_FRONTDOOR_MODEL_ALLOWLIST",
    "OPENCLAW_FRONTDOOR_MODEL_MAX_GB",
    "OPENROUTER_MODEL",
    "OPENCLAW_EXTERNAL_MODEL",
    "OPENCLAW_CASSANDRA_EXTERNAL_MODEL",
    "CASSANDRA_EXTERNAL_MODEL",
    "OPENROUTER_API_KEY",
)

OPENROUTER_REDACTED_NAMES = (
    "OPENROUTER_API_KEY",
    "OPENROUTER_MODEL",
    "OPENCLAW_EXTERNAL_MODEL",
    "OPENCLAW_CASSANDRA_EXTERNAL_MODEL",
    "CASSANDRA_EXTERNAL_MODEL",
)

TRUTHY_VALUES = {"1", "true", "yes", "on", "enabled"}
FALSEY_VALUES = {"", "0", "false", "no", "off", "disabled"}

CAPABILITY_LIVE_VARIABLES = {
    "interpreter_lm": {
        "primary": ("OPENCLAW_INTERPRETER_LM",),
        "related": (),
    },
    "frontdoor_model_profile": {
        "primary": ("OPENCLAW_FRONTDOOR_MODEL_PROFILE",),
        "related": (
            "OPENCLAW_FRONTDOOR_REPLY_TIMEOUT",
            "OPENCLAW_FRONTDOOR_NUM_PREDICT",
            "OPENCLAW_FRONTDOOR_MODEL_ALLOWLIST",
            "OPENCLAW_FRONTDOOR_MODEL_MAX_GB",
        ),
    },
    "continuity_capsule": {
        "primary": ("OPENCLAW_CONTINUITY_CAPSULE",),
        "related": ("OPENCLAW_PACKET_SOURCE",),
    },
    "polish_loop_local_builder_bridge": {
        "primary": ("OPENCLAW_POLISH_LOOP_LOCAL_BUILDER",),
        "related": (),
    },
    "polish_loop_file_ledger_bridge": {
        "primary": ("OPENCLAW_POLISH_LOOP_FILE_LEDGER_BRIDGE",),
        "related": ("OPENCLAW_POLISH_LOOP_LOCAL_BUILDER",),
    },
    "external_model_openrouter_path": {
        "primary": ("OPENCLAW_FREEFORM_CLOUD",),
        "related": (
            "OPENROUTER_MODEL",
            "OPENCLAW_EXTERNAL_MODEL",
            "OPENCLAW_CASSANDRA_EXTERNAL_MODEL",
            "CASSANDRA_EXTERNAL_MODEL",
            "OPENROUTER_API_KEY",
        ),
    },
}

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
    "polish_loop_file_ledger_bridge",
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


def _not_applicable_live_state() -> dict[str, Any]:
    return {
        "status": "not_applicable",
        "findings": [],
        "confidence": "none",
        "notes": "live environment reconciliation was not requested for this register generation",
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
            flag_or_config=["OPENCLAW_CONTINUITY_CAPSULE", "OPENCLAW_PACKET_SOURCE"],
            default_state="off",
            current_state_if_verifiable=_state(
                "code default off; activation audit reported maestro-listener continuity flag ON, but this generator did not inspect systemd or production env",
                code_default="off unless OPENCLAW_CONTINUITY_CAPSULE is truthy",
                production="unknown_not_reverified; audit_reported_maestro_listener_continuity_on",
                audit_report="activation audit reported maestro-listener continuity flag ON on 2026-06-25",
            ),
            source_files=["maestro_listener.py", "maestro_context_packet.py"],
            tests=["tests/test_continuity_stamp.py", "tests/test_packet_sqlite_flip.py"],
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
            capability_id="polish_loop_file_ledger_bridge",
            display_name="Polish Loop file-loop ledger reconciliation bridge",
            flag_or_config=["OPENCLAW_POLISH_LOOP_FILE_LEDGER_BRIDGE"],
            default_state="default-off",
            current_state_if_verifiable=_state(
                "bridge is built as a default-off candidate to reconcile legacy file-loop results with the SQLite Control Plane ledger",
                code_default="off unless OPENCLAW_POLISH_LOOP_FILE_LEDGER_BRIDGE is explicitly truthy",
                production="not_enabled_by_this_task; production activation prohibited",
                audit_report="POLISH-BLOCKER-002 design identified file-loop/ledger divergence and required a default-off reconciliation bridge",
            ),
            source_files=[
                "polish_loop/orchestrator.py",
                "polish_loop/control_plane.py",
            ],
            tests=["tests/test_polish_loop_file_ledger_reconciliation.py"],
            audits=[
                "/home/openclaw/workspaces/openclaw_program/CODEX_POLISH_BLOCKER_2_RESULT.md",
                "/home/openclaw/workspaces/openclaw_program/CODEX_POLISH_BLOCKER_2_IMPL_RESULT.md",
            ],
            canary_status="synthetic_only; canary required before runtime activation",
            risk_level="medium",
            owner="Opus",
            gate_stage="intentionally_off",
            enabled_by="explicit OPENCLAW_POLISH_LOOP_FILE_LEDGER_BRIDGE only after Opus review, synthetic tests, canary, rollback proof, and operator-approved runtime scope",
            disabled_by="default-off flag; production live loop remains prohibited",
            rollback_note="unset OPENCLAW_POLISH_LOOP_FILE_LEDGER_BRIDGE or set it to 0; revert the bridge branch if synthetic receipts regress",
            next_required_step="Opus review of task-003 implementation, then a separate synthetic/canary authorization task if the factory remains otherwise eligible",
            activation_allowed_now=False,
            operator_approval_required=True,
            reason_if_off="changes runtime reconciliation behavior and Polish Loop remains NOT_READY; canary and Opus/operator approval are required",
            evidence_refs=[
                "polish_loop/orchestrator.py:reconcile_file_loop_result_with_ledger",
                "tests/test_polish_loop_file_ledger_reconciliation.py",
                "/home/openclaw/workspaces/openclaw_program/CODEX_POLISH_BLOCKER_2_RESULT.md",
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
                "OPENCLAW_POLISH_LOOP_FILE_LEDGER_BRIDGE",
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


def _redacted_value_category(variable_name: str, value: Any) -> str:
    if value is None:
        return "unset"
    text = str(value).strip()
    lowered = text.lower()
    if lowered == "sqlite":
        return "set_sqlite"
    if lowered in TRUTHY_VALUES:
        return "set_true"
    if lowered in FALSEY_VALUES:
        return "set_false"
    return "set_other_redacted"


def _source_confidence(source_type: str) -> str:
    if source_type in {"systemd_user_unit", "systemd_user_dropin", "test_source"}:
        return "high"
    if source_type == "process_env":
        return "medium"
    return "low"


def _finding(
    *,
    source_type: str,
    source_ref: str,
    variable_name: str,
    redacted_value_category: str,
    confidence: str,
    notes: str = "",
) -> dict[str, str]:
    return {
        "source_type": source_type,
        "source_ref": source_ref,
        "variable_name": variable_name,
        "redacted_value_category": redacted_value_category,
        "confidence": confidence,
        "notes": notes,
    }


def _unset_finding(variable_name: str, inspected_sources: Sequence[Mapping[str, str]]) -> dict[str, str]:
    source_ref = "inspected_sources"
    if inspected_sources:
        source_ref = ",".join(sorted(str(item["source_ref"]) for item in inspected_sources))
    return _finding(
        source_type="reconciliation_summary",
        source_ref=source_ref,
        variable_name=variable_name,
        redacted_value_category="unset",
        confidence="medium" if inspected_sources else "low",
        notes="variable was not found in inspected whitelisted live-env sources",
    )


def _unknown_finding(variable_name: str, source_errors: Sequence[Mapping[str, str]]) -> dict[str, str]:
    source_ref = "unreadable_or_unavailable_source"
    if source_errors:
        source_ref = ",".join(sorted(str(item["source_ref"]) for item in source_errors))
    return _finding(
        source_type="reconciliation_summary",
        source_ref=source_ref,
        variable_name=variable_name,
        redacted_value_category="unknown",
        confidence="low",
        notes="source could not be safely inspected; operator verification required",
    )


def _parse_whitelisted_assignments(text: str) -> dict[str, str | None]:
    """Return only whitelisted variable assignments from systemd/env text."""

    values: dict[str, str | None] = {}
    whitelist = set(LIVE_ENV_WHITELIST)
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("EnvironmentFile="):
            continue
        tokens: list[str] = []
        if line.startswith("Environment="):
            payload = line.split("=", 1)[1].strip()
            try:
                tokens.extend(shlex.split(payload, posix=True))
            except ValueError:
                tokens.extend(payload.split())
        else:
            tokens.append(line.removeprefix("export ").strip())
        for token in tokens:
            if "=" not in token:
                continue
            name, value = token.split("=", 1)
            name = name.strip()
            if name in whitelist:
                values[name] = value.strip().strip('"').strip("'")
    return values


def _default_systemd_user_paths(home: Path | None = None) -> list[Path]:
    user_home = home or Path.home()
    base = user_home / ".config" / "systemd" / "user"
    service_names = ("maestro-listener.service", "openclaw-request-response.service")
    paths: list[Path] = []
    for service_name in service_names:
        service_path = base / service_name
        if service_path.is_file():
            paths.append(service_path)
        dropin_dir = base / f"{service_name}.d"
        if dropin_dir.is_dir():
            paths.extend(sorted(dropin_dir.glob("*.conf")))
    return paths


def default_live_env_sources(environ: Mapping[str, str] | None = None) -> list[dict[str, Any]]:
    """Build safe read-only source descriptors for optional live reconciliation."""

    env = os.environ if environ is None else environ
    process_values = {name: env[name] for name in LIVE_ENV_WHITELIST if name in env}
    sources: list[dict[str, Any]] = [
        {
            "source_type": "process_env",
            "source_ref": "current_process_env",
            "values": process_values,
            "notes": "only whitelisted variable names were checked from the current process environment",
        }
    ]
    for path in _default_systemd_user_paths():
        source_type = "systemd_user_dropin" if path.suffix == ".conf" else "systemd_user_unit"
        sources.append(
            {
                "source_type": source_type,
                "source_ref": str(path),
                "path": str(path),
                "notes": "read-only parse of whitelisted Environment assignments",
            }
        )
    return sources


def _source_values(source: Mapping[str, Any]) -> tuple[dict[str, str | None], str]:
    if "error" in source:
        return {}, str(source.get("error") or "source_unavailable")
    if "values" in source:
        raw_values = source.get("values") or {}
        values = {
            str(name): (None if value is None else str(value))
            for name, value in dict(raw_values).items()
            if str(name) in LIVE_ENV_WHITELIST
        }
        return values, ""
    if "content" in source:
        return _parse_whitelisted_assignments(str(source.get("content") or "")), ""
    if "path" in source:
        path = Path(str(source["path"]))
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            return {}, exc.__class__.__name__
        return _parse_whitelisted_assignments(text), ""
    return {}, "source_has_no_values_content_or_path"


def _collect_live_env_findings(
    live_env_sources: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    findings: list[dict[str, str]] = []
    source_statuses: list[dict[str, str]] = []
    source_errors: list[dict[str, str]] = []
    for source in live_env_sources:
        source_type = str(source.get("source_type") or "unknown_source")
        source_ref = str(source.get("source_ref") or source.get("path") or "unknown_source")
        values, error = _source_values(source)
        if error:
            status = {
                "source_type": source_type,
                "source_ref": source_ref,
                "status": "unknown_requires_operator_verification",
                "notes": f"source not safely inspected: {error}",
            }
            source_statuses.append(status)
            source_errors.append(status)
            continue
        source_statuses.append(
            {
                "source_type": source_type,
                "source_ref": source_ref,
                "status": "inspected",
                "notes": str(source.get("notes") or "whitelisted variables only; values redacted"),
            }
        )
        for variable_name in sorted(values):
            category = _redacted_value_category(variable_name, values[variable_name])
            notes = "raw value redacted"
            if variable_name in OPENROUTER_REDACTED_NAMES:
                notes = "OpenRouter/model-selection value checked only as set/unset/redacted"
            findings.append(
                _finding(
                    source_type=source_type,
                    source_ref=source_ref,
                    variable_name=variable_name,
                    redacted_value_category=category,
                    confidence=_source_confidence(source_type),
                    notes=notes,
                )
            )
    return findings, source_statuses, source_errors


def _findings_by_variable(findings: Sequence[Mapping[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for finding in findings:
        grouped.setdefault(str(finding["variable_name"]), []).append(dict(finding))
    return grouped


def _explicit_categories(findings: Sequence[Mapping[str, str]]) -> set[str]:
    return {
        str(item["redacted_value_category"])
        for item in findings
        if item["redacted_value_category"] not in {"unset", "unknown"}
    }


def _variable_conflicts(findings: Sequence[Mapping[str, str]]) -> bool:
    categories = _explicit_categories(findings)
    if {"set_true", "set_false"} <= categories:
        return True
    if "set_sqlite" in categories and "set_other_redacted" in categories:
        return True
    return False


def _primary_state(
    variable_name: str,
    grouped_findings: Mapping[str, Sequence[Mapping[str, str]]],
    inspected_sources: Sequence[Mapping[str, str]],
    source_errors: Sequence[Mapping[str, str]],
) -> tuple[str, list[dict[str, str]]]:
    findings = [dict(item) for item in grouped_findings.get(variable_name, [])]
    if _variable_conflicts(findings):
        return "conflicting_sources", findings
    categories = _explicit_categories(findings)
    if "set_true" in categories:
        return "enabled_verified", findings
    if "set_false" in categories:
        return "disabled_verified", findings
    if "set_sqlite" in categories:
        return "enabled_verified", findings
    if "set_other_redacted" in categories:
        return "configured_but_inert", findings
    if source_errors:
        return "unknown_requires_operator_verification", [_unknown_finding(variable_name, source_errors)]
    if inspected_sources:
        return "unset_default_off", [_unset_finding(variable_name, inspected_sources)]
    return "unknown_requires_operator_verification", [_unknown_finding(variable_name, source_errors)]


def _capability_live_state(
    capability: Mapping[str, Any],
    reconciliation: Mapping[str, Any],
) -> dict[str, Any]:
    if not reconciliation.get("enabled"):
        return _not_applicable_live_state()

    variable_spec = CAPABILITY_LIVE_VARIABLES.get(str(capability["capability_id"]))
    if not variable_spec:
        if str(capability["gate_stage"]) == "dry_run":
            return {
                "status": "dry_run_verified",
                "findings": [],
                "confidence": "medium",
                "notes": "capability is static dry-run/synthetic; no live feature flag is defined for reconciliation",
            }
        return {
            "status": "not_applicable",
            "findings": [],
            "confidence": "none",
            "notes": "no whitelisted live variable is mapped to this capability",
        }

    grouped_findings = _findings_by_variable(reconciliation["findings"])
    inspected_sources = [
        dict(item)
        for item in reconciliation["sources_inspected"]
        if item["status"] == "inspected"
    ]
    source_errors = list(reconciliation["source_errors"])
    primary_vars = tuple(variable_spec["primary"])
    related_vars = tuple(variable_spec["related"])

    statuses: list[str] = []
    capability_findings: list[dict[str, str]] = []
    for variable_name in primary_vars:
        status, findings = _primary_state(variable_name, grouped_findings, inspected_sources, source_errors)
        statuses.append(status)
        capability_findings.extend(findings)

    related_findings: list[dict[str, str]] = []
    related_conflict = False
    related_configured = False
    for variable_name in related_vars:
        findings = [dict(item) for item in grouped_findings.get(variable_name, [])]
        if findings:
            related_findings.extend(findings)
            related_configured = True
        if _variable_conflicts(findings):
            related_conflict = True

    if "conflicting_sources" in statuses or related_conflict:
        status = "conflicting_sources"
    elif str(capability["capability_id"]) == "external_model_openrouter_path":
        status = statuses[0]
        if status in {"disabled_verified", "unset_default_off"} and related_configured:
            status = "configured_but_inert"
    else:
        status = statuses[0]

    notes = {
        "enabled_verified": "live source verifies this capability/config is active; this does not grant new activation authority",
        "disabled_verified": "live source explicitly sets the primary flag/config off",
        "unset_default_off": "primary flag/config was absent from inspected sources and defaults off",
        "unknown_requires_operator_verification": "one or more live sources could not be inspected safely",
        "conflicting_sources": "conflicting whitelisted source findings require Opus/operator review",
        "configured_but_inert": "related configuration is present, but the enabling flag/path is off or insufficient",
        "dry_run_verified": "dry-run path remains non-live",
        "not_applicable": "no whitelisted live variable applies",
    }[status]

    return {
        "status": status,
        "findings": capability_findings,
        "related_findings": related_findings,
        "confidence": "high" if capability_findings and status != "unknown_requires_operator_verification" else "low",
        "notes": notes,
    }


def _apply_live_reconciliation(
    capabilities: Sequence[dict[str, Any]],
    reconciliation: Mapping[str, Any],
) -> None:
    for capability in capabilities:
        live_state = _capability_live_state(capability, reconciliation)
        status = str(live_state["status"])
        capability["live_production_state"] = status
        capability["live_state"] = live_state
        validate_live_state(status)
        if not reconciliation.get("enabled") or status == "not_applicable":
            continue
        capability["current_state_if_verifiable"]["production"] = status
        if status == "enabled_verified":
            capability["current_state_if_verifiable"]["summary"] = (
                "live reconciliation verified active/configured state from safe read-only whitelisted source; "
                "activation_allowed_now remains false"
            )
        elif status in {"disabled_verified", "unset_default_off", "configured_but_inert", "conflicting_sources"}:
            capability["current_state_if_verifiable"]["summary"] = (
                f"live reconciliation state is {status}; activation_allowed_now remains false"
            )


def _runtime_context(reconciliation: Mapping[str, Any]) -> dict[str, Any]:
    grouped_findings = _findings_by_variable(reconciliation["findings"])
    packet_findings = [dict(item) for item in grouped_findings.get("OPENCLAW_PACKET_SOURCE", [])]
    categories = _explicit_categories(packet_findings)
    if _variable_conflicts(packet_findings):
        status = "conflicting_sources"
    elif "set_sqlite" in categories:
        status = "enabled_verified"
    elif "set_false" in categories:
        status = "disabled_verified"
    elif "set_other_redacted" in categories:
        status = "configured_but_inert"
    elif reconciliation.get("enabled"):
        status = "unset_default_off"
    else:
        status = "not_applicable"
    return {
        "packet_source": {
            "status": status,
            "findings": packet_findings,
            "notes": "OPENCLAW_PACKET_SOURCE is tracked as related runtime context for continuity/packet sourcing",
        }
    }


def validate_live_state(status: str) -> None:
    if status not in LIVE_STATE_VALUES:
        raise ValueError(f"invalid live production state: {status!r}")


def build_live_env_reconciliation(
    live_env_sources: Sequence[Mapping[str, Any]] | None = None,
    *,
    enabled: bool = False,
) -> dict[str, Any]:
    if live_env_sources is None and not enabled:
        return {
            "enabled": False,
            "whitelisted_names": list(LIVE_ENV_WHITELIST),
            "state_vocabulary": list(LIVE_STATE_VALUES),
            "findings": [],
            "sources_inspected": [],
            "sources_not_inspected": [
                {
                    "source_type": "live_env_reconciliation",
                    "source_ref": "all_live_sources",
                    "reason": "not requested for this deterministic generation",
                }
            ],
            "source_errors": [],
            "runtime_context": {"packet_source": {"status": "not_applicable", "findings": [], "notes": ""}},
            "policy": {
                "read_only": True,
                "whitelist_only": True,
                "raw_values_stored": False,
                "secrets_printed_or_stored": False,
            },
        }

    sources = list(default_live_env_sources() if live_env_sources is None else live_env_sources)
    findings, source_statuses, source_errors = _collect_live_env_findings(sources)
    reconciliation = {
        "enabled": True,
        "whitelisted_names": list(LIVE_ENV_WHITELIST),
        "state_vocabulary": list(LIVE_STATE_VALUES),
        "findings": findings,
        "sources_inspected": source_statuses,
        "sources_not_inspected": [
            {
                "source_type": "systemctl_user_show_environment",
                "source_ref": "systemctl --user show ... -p Environment",
                "reason": "not used because it can dump non-whitelisted environment values",
            },
            {
                "source_type": "secret_env_file",
                "source_ref": ".chief.env and producer.env",
                "reason": "not read wholesale; secret-bearing env files require operator-approved whitelisted grep if needed",
            },
        ],
        "source_errors": source_errors,
        "policy": {
            "read_only": True,
            "whitelist_only": True,
            "raw_values_stored": False,
            "secrets_printed_or_stored": False,
        },
    }
    reconciliation["runtime_context"] = _runtime_context(reconciliation)
    return reconciliation


def _summarize(capabilities: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    def ids_matching(predicate: Any) -> list[str]:
        return sorted(str(item["capability_id"]) for item in capabilities if predicate(item))

    return {
        "total_capabilities": len(capabilities),
        "verified_enabled": ids_matching(lambda item: item.get("live_production_state") == "enabled_verified"),
        "activation_allowed_now": ids_matching(lambda item: item["activation_allowed_now"] is True),
        "currently_off_or_blocked": ids_matching(
            lambda item: item.get("live_production_state") != "enabled_verified"
            and item["gate_stage"] in {"disabled", "intentionally_off", "blocked", "proposed", "unknown"}
        ),
        "ready_for_canary": ids_matching(
            lambda item: item["gate_stage"] == "canary" and item["activation_allowed_now"] is False
        ),
        "blocked": ids_matching(lambda item: item["gate_stage"] == "blocked"),
        "intentionally_off": ids_matching(lambda item: item["gate_stage"] == "intentionally_off"),
        "conflicting_live_state": ids_matching(lambda item: item.get("live_production_state") == "conflicting_sources"),
        "unknown_production_state": ids_matching(
            lambda item: item.get("live_production_state") == "unknown_requires_operator_verification"
            or (
                item.get("live_production_state") in {None, "not_applicable"}
                and "unknown" in json.dumps(item["current_state_if_verifiable"], sort_keys=True)
            )
        ),
    }


def build_activation_gate_register(
    *,
    repo_root: str | Path = ".",
    last_verified_at: str = DEFAULT_LAST_VERIFIED_AT,
    live_env_sources: Sequence[Mapping[str, Any]] | None = None,
    reconcile_live_env: bool = False,
) -> dict[str, Any]:
    repo = Path(repo_root)
    capabilities = sorted(
        _capability_templates(last_verified_at),
        key=lambda item: item["capability_id"],
    )
    live_reconciliation = build_live_env_reconciliation(
        live_env_sources,
        enabled=reconcile_live_env,
    )
    _apply_live_reconciliation(capabilities, live_reconciliation)
    for capability in capabilities:
        validate_capability(capability)

    present_ids = {item["capability_id"] for item in capabilities}
    missing_required = sorted(set(REQUIRED_CAPABILITY_IDS) - present_ids)
    if missing_required:
        raise ValueError(f"missing required capabilities: {missing_required}")
    systemd_read_only = any(
        str(source.get("source_type", "")).startswith("systemd_")
        and source.get("status") == "inspected"
        for source in live_reconciliation["sources_inspected"]
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": last_verified_at,
        "policy": {
            "descriptive_only": True,
            "features_enabled_by_this_register": False,
            "production_flags_changed": False,
            "production_env_files_inspected": False,
            "systemd_inspected_or_modified": systemd_read_only,
            "systemd_user_unit_files_inspected_read_only": systemd_read_only,
            "systemd_modified": False,
            "systemctl_invoked": False,
            "live_env_reconciliation_enabled": bool(live_reconciliation["enabled"]),
            "live_env_reconciliation_read_only": True,
            "live_env_whitelist_only": True,
            "live_env_raw_values_stored": False,
            "live_env_secrets_printed_or_stored": False,
            "live_external_actions_run": False,
            "production_databases_touched": False,
            "classification_rule": "Do not mark a capability enabled or safe to enable unless evidence proves it.",
        },
        "gate_stages": list(GATE_STAGES),
        "live_state_values": list(LIVE_STATE_VALUES),
        "live_env_whitelist": list(LIVE_ENV_WHITELIST),
        "required_fields": list(REQUIRED_FIELDS),
        "capabilities": capabilities,
        "summary": _summarize(capabilities),
        "live_reconciliation": live_reconciliation,
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
            f"- Verified enabled/live: {_format_list(summary['verified_enabled'])}",
            f"- Activation allowed now: {_format_list(summary['activation_allowed_now'])}",
            f"- Ready for canary queue: {_format_list(summary['ready_for_canary'])}",
            f"- Blocked: {_format_list(summary['blocked'])}",
            f"- Intentionally off: {_format_list(summary['intentionally_off'])}",
            f"- Conflicting live state: {_format_list(summary['conflicting_live_state'])}",
            f"- Unknown production state: {_format_list(summary['unknown_production_state'])}",
            "",
            "| Capability | Stage | Live production state | Current state | Activation allowed now | Next required step |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )

    for capability in capabilities:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"{capability['display_name']} (`{capability['capability_id']}`)",
                    f"`{capability['gate_stage']}`",
                    f"`{capability.get('live_production_state', 'not_applicable')}`",
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
                f"- Live production state: `{capability.get('live_production_state', 'not_applicable')}`",
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
        live_state = capability.get("live_state") or _not_applicable_live_state()
        lines.extend(
            [
                "Live-state evidence:",
                f"- Status: `{live_state['status']}`",
                f"- Confidence: `{live_state.get('confidence', 'unknown')}`",
                f"- Notes: {live_state.get('notes', '')}",
            ]
        )
        for finding in live_state.get("findings", []):
            lines.append(
                "- Finding: "
                f"`{finding['variable_name']}` from `{finding['source_type']}` "
                f"`{finding['source_ref']}` -> `{finding['redacted_value_category']}` "
                f"(confidence `{finding['confidence']}`; {finding.get('notes', '')})"
            )
        for finding in live_state.get("related_findings", []):
            lines.append(
                "- Related finding: "
                f"`{finding['variable_name']}` from `{finding['source_type']}` "
                f"`{finding['source_ref']}` -> `{finding['redacted_value_category']}` "
                f"(confidence `{finding['confidence']}`; {finding.get('notes', '')})"
            )
        lines.append("")

    detection = register["verification"]["flag_detection"]
    lines.extend(["## Flag Detection", ""])
    for flag in sorted(detection):
        info = detection[flag]
        lines.append(f"- `{flag}`: `{info['status']}` in {_format_list(info['files'])}")

    live_reconciliation = register["live_reconciliation"]
    packet_context = live_reconciliation["runtime_context"]["packet_source"]
    lines.extend(
        [
            "",
            "## Live Environment Reconciliation",
            "",
            f"- Enabled for this generation: `{_format_bool(bool(live_reconciliation['enabled']))}`",
            f"- Whitelisted names: {_format_list(live_reconciliation['whitelisted_names'])}",
            f"- Packet source runtime context: `{packet_context['status']}`",
        ]
    )
    for finding in packet_context.get("findings", []):
        lines.append(
            "- Packet source finding: "
            f"`{finding['variable_name']}` from `{finding['source_type']}` "
            f"`{finding['source_ref']}` -> `{finding['redacted_value_category']}`"
        )
    lines.extend(["", "Sources inspected:"])
    if live_reconciliation["sources_inspected"]:
        for source in live_reconciliation["sources_inspected"]:
            lines.append(
                f"- `{source['source_type']}` `{source['source_ref']}`: `{source['status']}` ({source['notes']})"
            )
    else:
        lines.append("- none recorded")
    lines.extend(["", "Sources not inspected:"])
    for source in live_reconciliation["sources_not_inspected"]:
        lines.append(
            f"- `{source['source_type']}` `{source['source_ref']}`: {source['reason']}"
        )
    if live_reconciliation["source_errors"]:
        lines.extend(["", "Source errors:"])
        for source in live_reconciliation["source_errors"]:
            lines.append(
                f"- `{source['source_type']}` `{source['source_ref']}`: `{source['status']}` ({source['notes']})"
            )

    missing = register["verification"]["missing_repo_evidence_files"]
    lines.extend(
        [
            "",
            "## Evidence Gaps",
            "",
            f"- Missing repository evidence files referenced by register: {_format_list(missing)}",
            f"- Production env/service state: `{'redacted live reconciliation enabled' if live_reconciliation['enabled'] else 'not inspected by this task'}`",
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
    live_env_sources: Sequence[Mapping[str, Any]] | None = None,
    reconcile_live_env: bool = False,
) -> dict[str, Path]:
    register = build_activation_gate_register(
        repo_root=repo_root,
        last_verified_at=last_verified_at,
        live_env_sources=live_env_sources,
        reconcile_live_env=reconcile_live_env,
    )
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
    parser.add_argument(
        "--reconcile-live-env",
        action="store_true",
        help="Read whitelisted live env/config sources in read-only mode and store redacted state categories.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    paths = write_outputs(
        repo_root=Path(args.repo_root),
        output_dir=Path(args.output_dir),
        last_verified_at=args.last_verified_at,
        reconcile_live_env=bool(args.reconcile_live_env),
    )
    print(f"wrote {paths['markdown']}")
    print(f"wrote {paths['json']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
