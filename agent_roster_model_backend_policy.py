"""Agent Roster + Model Backend Ontology v0.

This deterministic read-model separates OpenClaw crew agents from model
backends, worker backends, tools/adapters, packages, and authority boundaries.
It is contract/read-model only. It does not call models, dispatch agents or
workers, execute workflows, access external systems, handle credentials, ingest
raw bodies, mutate Mission Control Swift, or push.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-25T00:00:00+00:00"

SCHEMA_VERSION = "agent_roster_model_backend_policy_v0"
READ_MODEL_ID = "agent_roster_model_backend_policy"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_AGENT_ROSTER_MODEL_BACKEND_POLICY_NO_EXECUTION"

AGENT_ROLES = ("CASSANDRA", "CHIEF", "NILES", "GUARDIAN", "HERMES")
SYSTEM_IDENTITIES = ("OPENCLAW_SYSTEM",)

PROVIDER_FAMILIES = (
    "OPENAI_CODEX",
    "OPENAI_GPT",
    "GEMINI_AGY",
    "GEMINI_FLASH",
    "CLAUDE",
    "LOCAL_OLLAMA",
    "LOCAL_SMALL_MODEL",
    "FUTURE_PROVIDER",
    "UNKNOWN_FAIL_CLOSED",
)

WORKER_TYPES = (
    "PC_CODEX_WORKER",
    "MAC_CODEX_WORKER",
    "GEMINI_AGY_ADVISORY_WORKER",
    "LOCAL_OLLAMA_INTERPRETER",
    "REPO_B_WRAPPED_WORKER",
    "MANUAL_OPERATOR",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
    "live_model_call_allowed": False,
    "live_agent_dispatch_allowed": False,
    "live_worker_dispatch_allowed": False,
    "live_workflow_run_allowed": False,
    "live_external_action_allowed": False,
    "live_send_submit_allowed": False,
    "live_tool_use_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_allowed": False,
    "live_browser_allowed": False,
    "live_coupa_access_allowed": False,
    "live_email_send_allowed": False,
    "live_secret_reveal_allowed": False,
    "live_candidate_promotion_allowed": False,
    "mission_control_swift_change_allowed": False,
    "mac_sync_import_allowed": False,
    "git_push_pull_fetch_allowed": False,
}


@dataclass(frozen=True)
class AgentRosterPolicy:
    policy_id: str
    doctrine: tuple[str, ...]
    agent_roles: tuple[str, ...]
    system_identities: tuple[str, ...]
    model_backend_roles: tuple[str, ...]
    worker_backend_roles: tuple[str, ...]
    separation_policy: tuple[str, ...]
    forbidden_conflations: tuple[str, ...]
    legacy_migration_notes: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class OpenClawAgentProfile:
    agent_role: str
    display_name: str
    primary_domain: str
    role_purpose: str
    voice_profile_ref: str
    vibe_profile_ref: str
    allowed_task_types: tuple[str, ...]
    forbidden_task_types: tuple[str, ...]
    default_model_policy_ref: str
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class SystemIdentityProfile:
    system_identity_ref: str
    display_name: str
    purpose: str
    allowed_surfaces: tuple[str, ...]
    forbidden_persona_behavior: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class ModelBackendProfile:
    model_backend_ref: str
    provider_family: str
    display_name: str
    suitable_task_types: tuple[str, ...]
    strengths: tuple[str, ...]
    weaknesses: tuple[str, ...]
    local_or_cloud: str
    privacy_class_allowed: tuple[str, ...]
    credit_cost_class: str
    latency_class: str
    context_window_class: str
    json_schema_reliability: str
    code_quality_score: str
    creative_quality_score: str
    reasoning_quality_score: str
    tool_support_class: str
    blocked_contexts: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class ModelSelectionPolicy:
    model_selection_id: str
    agent_role: str
    task_type: str
    candidate_model_backends: tuple[str, ...]
    preferred_model_backend: str
    fallback_model_backend: str
    local_or_cloud_preference: str
    privacy_class: str
    credit_cost_class: str
    latency_requirement: str
    context_window_need: str
    tool_support_need: str
    json_schema_reliability_need: str
    creative_quality_need: str
    code_quality_need: str
    reasoning_quality_need: str
    selected_reason: str
    blocked_models: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class WorkerBackendType:
    worker_backend_ref: str
    worker_type: str
    description: str
    allowed_task_types: tuple[str, ...]
    target_machine: str
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class LegacyOntologyFinding:
    finding_id: str
    source_file: str
    legacy_pattern: str
    risk: str
    recommended_replacement: str
    migration_status: str
    next_safe_move: str


@dataclass(frozen=True)
class AgentModelBindingExample:
    example_id: str
    agent_role: str
    task_type: str
    selected_model_backend: str
    selected_worker_type: str
    allowed_tools: tuple[str, ...]
    forbidden_tools: tuple[str, ...]
    authority_boundary: dict[str, bool]
    why_this_is_correct: str
    bad_example: str
    why_bad: str
    next_safe_move: str


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clean = json.loads(stable_json(payload))
    clean.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clean).encode("utf-8")).hexdigest()


def _model_schema(cls: type[Any]) -> dict[str, tuple[str, ...]]:
    return {cls.__name__: tuple(field.name for field in fields(cls))}


def _voice_ref(role: str) -> str:
    return f"voice:{role.lower()}:policy"


def _vibe_ref(role: str) -> str:
    return f"vibe:{role.lower()}:policy"


def build_agent_profiles() -> tuple[OpenClawAgentProfile, ...]:
    boundary = dict(AUTHORITY_BOUNDARY)
    return (
        OpenClawAgentProfile(
            agent_role="CASSANDRA",
            display_name="Cassandra",
            primary_domain="communications / executive assistant / outward-facing coordination",
            role_purpose="Draft-aware, recipient-aware, tactful communications support.",
            voice_profile_ref="voice:cassandra:communications",
            vibe_profile_ref="vibe:cassandra:executive_calm",
            allowed_task_types=("OUTBOUND_MESSAGE_DRAFT", "COMMUNICATION_REVIEW", "RELATIONSHIP_CONTEXT_READBACK"),
            forbidden_task_types=("SEND_EMAIL_WITHOUT_GATE", "SUBMIT_PORTAL_ACTION", "SECRET_REVEAL"),
            default_model_policy_ref="model_selection:cassandra:draft",
            authority_boundary=boundary,
            next_safe_move="Prepare drafts and review language; keep send authority explicitly gated.",
        ),
        OpenClawAgentProfile(
            agent_role="CHIEF",
            display_name="Chief",
            primary_domain="operations / routing / command / status",
            role_purpose="Concise operational routing, status, and next-safe-move command.",
            voice_profile_ref="voice:chief:operational",
            vibe_profile_ref="vibe:chief:command_center",
            allowed_task_types=("ANSWER_STATUS", "WORKER_ROUTING", "WORKFLOW_READBACK", "BUILD_STATUS_READBACK"),
            forbidden_task_types=("AUTONOMOUS_EXECUTION", "UNAPPROVED_SEND_SUBMIT", "HIDDEN_WORKFLOW_RUN"),
            default_model_policy_ref="model_selection:chief:planning_code_backend",
            authority_boundary=boundary,
            next_safe_move="Name status, route, blocker, and next safe move without executing.",
        ),
        OpenClawAgentProfile(
            agent_role="NILES",
            display_name="Niles",
            primary_domain="music / creative / project flow",
            role_purpose="Funny, low-pressure creative planning and music/project flow support.",
            voice_profile_ref="voice:niles:creative_flow",
            vibe_profile_ref="vibe:niles:creative_flow",
            allowed_task_types=("CREATIVE_IDEATION", "MUSIC_PROJECT_PLANNING", "SOURCE_REF_NAVIGATION"),
            forbidden_task_types=("DAW_FILE_MUTATION_WITHOUT_GATE", "AUDIO_SESSION_MUTATION", "FAKE_CREATIVE_PROGRESS"),
            default_model_policy_ref="model_selection:niles:creative",
            authority_boundary=boundary,
            next_safe_move="Support creative flow through source refs and planning only.",
        ),
        OpenClawAgentProfile(
            agent_role="GUARDIAN",
            display_name="Guardian",
            primary_domain="proof / risk / approval / protected boundaries",
            role_purpose="Strict, gate-aware proof and protected-boundary authority readback.",
            voice_profile_ref="voice:guardian:proof_gate",
            vibe_profile_ref="vibe:guardian:strict_proof",
            allowed_task_types=("APPROVAL_GATE_REVIEW", "PROOF_CHECK", "SECRET_BOUNDARY_REVIEW", "RISK_READBACK"),
            forbidden_task_types=("SOFTEN_BLOCKERS", "APPROVE_OWN_OUTPUT", "REVEAL_SECRET"),
            default_model_policy_ref="model_selection:guardian:explanation",
            authority_boundary=boundary,
            next_safe_move="Preserve blockers and require deterministic proof/approval receipts.",
        ),
        OpenClawAgentProfile(
            agent_role="HERMES",
            display_name="Hermes",
            primary_domain="systems auditor / architecture critic / strategic advisor",
            role_purpose="Pattern-aware, skeptical advisory critique that answers what is missing.",
            voice_profile_ref="voice:hermes:audit",
            vibe_profile_ref="vibe:hermes:architecture_critic",
            allowed_task_types=("ARCHITECTURE_AUDIT", "SYSTEMS_CRITIQUE", "STRATEGIC_REVIEW", "MISSING_RAIL_ANALYSIS"),
            forbidden_task_types=("PRETEND_EXECUTION", "SELF_APPROVAL", "REPLACE_GUARDIAN", "CLAIM_BUILD_AUTHORITY"),
            default_model_policy_ref="model_selection:hermes:audit",
            authority_boundary=boundary,
            next_safe_move="Return advisory critique and route any implementation through deterministic build gates.",
        ),
    )


def build_system_identities() -> tuple[SystemIdentityProfile, ...]:
    return (
        SystemIdentityProfile(
            system_identity_ref="system_identity:openclaw_system",
            display_name="OpenClaw System",
            purpose="Neutral machine/system identity for raw structural readbacks, file intake, and system failures.",
            allowed_surfaces=("FILE_METADATA_INTAKE", "RAW_SQLITE_READBACK", "STRUCTURAL_FAILURE", "GENERIC_SYSTEM_STATUS"),
            forbidden_persona_behavior=("charm", "lore", "personal voice", "fake agency", "crew persona"),
            authority_boundary=dict(AUTHORITY_BOUNDARY),
            next_safe_move="Use sterile system wording when persona would create ambiguity or false agency.",
        ),
    )


def build_model_backend_profiles() -> tuple[ModelBackendProfile, ...]:
    return (
        ModelBackendProfile(
            "model_backend:openai_codex",
            "OPENAI_CODEX",
            "Codex",
            ("CODE_IMPLEMENTATION", "TEST_FIX", "REPO_READBACK", "BUILD_VALIDATION"),
            ("code edits", "test repair", "repo-local reasoning", "structured implementation"),
            ("not an agent", "no authority by itself", "tool use only when package grants it"),
            "CLOUD_OR_LOCAL_PRODUCT_SURFACE",
            ("repo_metadata", "generated_readmodel_refs"),
            "MEDIUM",
            "MEDIUM",
            "HIGH",
            "HIGH",
            "HIGH",
            "LOW",
            "HIGH",
            "PACKAGE_GRANTED_ONLY",
            ("raw private bodies", "credentials", "unapproved external action"),
            "Use as selected_model_backend or selected_worker_type, never as agent_role.",
        ),
        ModelBackendProfile(
            "model_backend:openai_gpt",
            "OPENAI_GPT",
            "GPT",
            ("PLANNING", "DRAFTING", "REASONING", "JSON_STRUCTURING"),
            ("general reasoning", "writing", "schema shaping"),
            ("cloud privacy gate required", "no authority by itself"),
            "CLOUD",
            ("public_or_repo_safe", "sanitized_context_refs"),
            "MEDIUM",
            "LOW",
            "HIGH",
            "HIGH",
            "MEDIUM",
            "HIGH",
            "HIGH",
            "PACKAGE_GRANTED_ONLY",
            ("credentials", "raw private bodies", "protected evidence bodies"),
            "Use only when privacy and credit gates allow.",
        ),
        ModelBackendProfile(
            "model_backend:gemini_agy",
            "GEMINI_AGY",
            "Gemini/Agy",
            ("ARCHITECTURE_AUDIT", "SCOUTING", "SECOND_OPINION", "PROMPT_SHAPING"),
            ("long-context audit", "pattern critique", "gotcha discovery"),
            ("advisory only", "no edits or execution", "cloud privacy gate required"),
            "CLOUD",
            ("public_or_repo_safe", "sanitized_readonly_refs"),
            "MEDIUM",
            "MEDIUM",
            "HIGH",
            "MEDIUM",
            "MEDIUM",
            "MEDIUM",
            "HIGH",
            "READ_ONLY_BY_DEFAULT",
            ("credentials", "raw private bodies", "client private payloads without gate"),
            "Use as Hermes or Chief audit backend only after privacy/credit gates.",
        ),
        ModelBackendProfile(
            "model_backend:claude",
            "CLAUDE",
            "Claude",
            ("LONG_FORM_DRAFTING", "REASONING", "CRITIQUE"),
            ("long-form analysis", "writing", "policy critique"),
            ("cloud privacy gate required", "no tools without package grant"),
            "CLOUD",
            ("public_or_repo_safe", "sanitized_context_refs"),
            "MEDIUM",
            "MEDIUM",
            "HIGH",
            "MEDIUM",
            "LOW",
            "HIGH",
            "HIGH",
            "PACKAGE_GRANTED_ONLY",
            ("credentials", "raw private bodies", "external action"),
            "Use as fallback writing or critique backend when allowed.",
        ),
        ModelBackendProfile(
            "model_backend:local_ollama",
            "LOCAL_OLLAMA",
            "Local Ollama",
            ("LOCAL_CLASSIFICATION", "SENSITIVE_SUMMARY", "LOW_RISK_REASONING"),
            ("local-first privacy posture", "low marginal cost"),
            ("quality varies by local model", "tool support not assumed"),
            "LOCAL",
            ("sensitive_private_refs", "local_metadata", "protected_refs_without_raw_secret"),
            "LOW",
            "MEDIUM",
            "MEDIUM",
            "MEDIUM",
            "LOW",
            "MEDIUM",
            "MEDIUM",
            "NO_TOOLS_BY_DEFAULT",
            ("secret reveal", "raw credential handling", "external action"),
            "Prefer for sensitive/private explanation when adequate.",
        ),
        ModelBackendProfile(
            "model_backend:future_provider",
            "FUTURE_PROVIDER",
            "Future Provider",
            ("UNKNOWN_FUTURE_TASK",),
            ("not assumed",),
            ("unknown authority", "unknown privacy", "unknown cost"),
            "UNKNOWN_FAIL_CLOSED",
            ("none_until_profiled",),
            "UNKNOWN_FAIL_CLOSED",
            "UNKNOWN_FAIL_CLOSED",
            "UNKNOWN_FAIL_CLOSED",
            "UNKNOWN_FAIL_CLOSED",
            "UNKNOWN_FAIL_CLOSED",
            "UNKNOWN_FAIL_CLOSED",
            "UNKNOWN_FAIL_CLOSED",
            "UNKNOWN_FAIL_CLOSED",
            ("all live contexts until profiled",),
            "Fail closed until a provider profile, privacy gate, and authority policy exist.",
        ),
    )


def build_model_selection_policies() -> tuple[ModelSelectionPolicy, ...]:
    boundary = dict(AUTHORITY_BOUNDARY)
    return (
        ModelSelectionPolicy(
            "model_selection:chief:planning_code_backend",
            "CHIEF",
            "operations planning / build status",
            ("model_backend:openai_codex", "model_backend:openai_gpt", "model_backend:gemini_agy"),
            "model_backend:openai_codex",
            "model_backend:openai_gpt",
            "HYBRID_WITH_PRIVACY_GATE",
            "repo_metadata_or_generated_readmodel_refs",
            "MEDIUM",
            "MEDIUM",
            "MEDIUM",
            "code/read-model/test support only when package grants it",
            "HIGH",
            "LOW",
            "HIGH",
            "HIGH",
            "Chief may use Codex/GPT/Gemini for planning or code lanes, but Chief remains the agent.",
            ("cloud backend without privacy gate", "backend with ungranted tools"),
            boundary,
            "Keep model output candidate until deterministic validation.",
        ),
        ModelSelectionPolicy(
            "model_selection:hermes:audit",
            "HERMES",
            "architecture audit / strategic critique",
            ("model_backend:gemini_agy", "model_backend:openai_gpt", "model_backend:claude"),
            "model_backend:gemini_agy",
            "model_backend:openai_gpt",
            "CLOUD_ALLOWED_ONLY_WITH_PRIVACY_AND_CREDIT_GATE",
            "sanitized_readonly_refs",
            "MEDIUM",
            "MEDIUM",
            "HIGH",
            "read-only context refs; no execution tools",
            "MEDIUM",
            "MEDIUM",
            "MEDIUM",
            "HIGH",
            "Hermes may use Gemini/Agy for audit, but Hermes remains advisory.",
            ("raw private bodies", "credentials", "tool-enabled execution backend"),
            boundary,
            "Return critique as advisory candidate guidance.",
        ),
        ModelSelectionPolicy(
            "model_selection:cassandra:draft",
            "CASSANDRA",
            "outbound message draft",
            ("model_backend:openai_gpt", "model_backend:claude", "model_backend:local_ollama"),
            "model_backend:openai_gpt",
            "model_backend:local_ollama",
            "HYBRID_WITH_PRIVACY_GATE",
            "recipient_context_refs_only",
            "MEDIUM",
            "LOW",
            "MEDIUM",
            "draft tools only; no send tools",
            "HIGH",
            "HIGH",
            "LOW",
            "MEDIUM",
            "Cassandra may use a writing backend for drafts; send authority remains false.",
            ("models with send tools", "cloud model for raw private bodies"),
            boundary,
            "Draft for review and keep outward movement locked.",
        ),
        ModelSelectionPolicy(
            "model_selection:niles:creative",
            "NILES",
            "creative ideation / music planning",
            ("model_backend:openai_gpt", "model_backend:claude", "model_backend:local_ollama"),
            "model_backend:openai_gpt",
            "model_backend:local_ollama",
            "HYBRID_WITH_PRIVACY_GATE",
            "creative_metadata_source_refs",
            "LOW",
            "LOW",
            "MEDIUM",
            "no DAW/file mutation tools",
            "MEDIUM",
            "HIGH",
            "LOW",
            "MEDIUM",
            "Niles may use a creative backend for ideation; files and DAW sessions remain locked.",
            ("mutation-capable project tools", "cloud model for raw session files"),
            boundary,
            "Keep output as planning/source-ref guidance.",
        ),
        ModelSelectionPolicy(
            "model_selection:guardian:deterministic_first",
            "GUARDIAN",
            "proof/risk/approval explanation",
            ("model_backend:local_ollama", "model_backend:openai_gpt"),
            "model_backend:local_ollama",
            "model_backend:openai_gpt",
            "LOCAL_FIRST_WHEN_ADEQUATE",
            "sensitive_or_protected_refs",
            "LOW",
            "MEDIUM",
            "MEDIUM",
            "read-only proof refs; no approval execution tools",
            "HIGH",
            "LOW",
            "LOW",
            "HIGH",
            "Guardian deterministic gates beat model output; LM explanation is optional and advisory.",
            ("cloud model for secrets", "approval execution tools", "secret reveal"),
            boundary,
            "Explain the gate; do not approve or reveal.",
        ),
    )


def build_worker_backend_types() -> tuple[WorkerBackendType, ...]:
    boundary = dict(AUTHORITY_BOUNDARY)
    return (
        WorkerBackendType("worker_backend:pc_codex", "PC_CODEX_WORKER", "Repo A backend implementation worker surface.", ("CODE_IMPLEMENTATION", "TESTS", "READMODEL_EXPORT"), "PC_WSL", boundary, "Use only through bounded local package requirements."),
        WorkerBackendType("worker_backend:mac_codex", "MAC_CODEX_WORKER", "Mac-side app/UI/build validation worker surface.", ("MAC_UI", "XCODE_BUILD_FUTURE", "SCREENSHOT_VALIDATION_FUTURE"), "MAC", boundary, "Use only through a Mac handoff package; PC does not execute it."),
        WorkerBackendType("worker_backend:gemini_agy", "GEMINI_AGY_ADVISORY_WORKER", "Read-only advisory audit/scout surface.", ("ARCHITECTURE_AUDIT", "CRITIQUE", "PROMPT_SHAPING"), "EXTERNAL_MODEL", boundary, "Use sanitized read-only packages only."),
        WorkerBackendType("worker_backend:local_ollama", "LOCAL_OLLAMA_INTERPRETER", "Local model interpretation or explanation surface.", ("LOCAL_CLASSIFICATION", "SENSITIVE_SUMMARY"), "LOCAL_ONLY", boundary, "Use local-only context and deterministic validation."),
        WorkerBackendType("worker_backend:repo_b_wrapped", "REPO_B_WRAPPED_WORKER", "Future wrapped worker surface from Repo B lanes.", ("FUTURE_GATED_WORKER",), "REPO_B_OR_LOCAL", boundary, "Fail closed until wrapped package and authority profile exist."),
        WorkerBackendType("worker_backend:manual_operator", "MANUAL_OPERATOR", "Human operator decision/action surface.", ("APPROVAL", "CLARIFICATION", "MANUAL_ACTION"), "HUMAN", boundary, "Ask the operator for exact approval or missing context."),
        WorkerBackendType("worker_backend:unknown", "UNKNOWN_FAIL_CLOSED", "Unknown worker backend.", ("UNKNOWN_FAIL_CLOSED",), "UNKNOWN", boundary, "Ask clarification and do not dispatch."),
    )


def _file_contains(repo_root: Path, source_file: str, pattern: str) -> bool:
    path = repo_root / source_file
    if not path.exists() or not path.is_file():
        return False
    try:
        return pattern in path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False


def build_legacy_findings(repo_root: Path = Path(".")) -> tuple[LegacyOntologyFinding, ...]:
    checks = (
        (
            "legacy:request_processor:codex_responder_future",
            "openclaw_request_processor.py",
            "CODEX_RESPONDER_FUTURE",
            "Responder target name can be misread as an agent instead of a backend/worker adapter.",
            "CODEX_WORKER_BACKEND or OPENAI_CODEX_MODEL_BACKEND",
        ),
        (
            "legacy:request_processor:gemini_responder_future",
            "openclaw_request_processor.py",
            "GEMINI_RESPONDER_FUTURE",
            "Responder target name can be misread as a crew member instead of an advisory model/backend adapter.",
            "GEMINI_AGY_ADVISORY_WORKER or GEMINI_AGY_MODEL_BACKEND",
        ),
        (
            "legacy:scoped_context:target_agent_roles",
            "scoped_context_package_compiler_contract.py",
            "TARGET_AGENT_ROLES",
            "Field name target_agent_role currently carries worker backends such as MAC_CODEX, PC_CODEX, and GEMINI_AGY.",
            "target_worker_type plus agent_role when an actual crew agent exists",
        ),
        (
            "legacy:worker_router:gemini_patterns",
            "worker_routing_intelligence.py",
            "GEMINI_PATTERNS",
            "Gemini/Agy routing is valid as a worker/backend route, but should not be rendered as a persona agent.",
            "selected_worker_type=GEMINI_AGY_ADVISORY_WORKER with agent_role=HERMES or CHIEF when needed",
        ),
        (
            "legacy:agent_phrases:codex_gemini",
            "intent_router.py",
            "AGENT_PHRASES",
            "Legacy phrase maps could route Codex/Gemini as crew members if introduced later.",
            "Do not include Codex/Gemini in crew AGENT_PHRASES; use backend/worker fields.",
        ),
        (
            "legacy:agent_role_enum:codex",
            "agent_voice_response_layer.py",
            '"CODEX"',
            "Codex previously appeared in agent role enums; current schema must keep it under model_backends only.",
            "Keep CODEX out of agent_roles and named_agent_roles.",
        ),
    )
    findings: list[LegacyOntologyFinding] = []
    for finding_id, source_file, pattern, risk, replacement in checks:
        present = _file_contains(repo_root, source_file, pattern)
        if source_file == "agent_voice_response_layer.py":
            migration_status = "MIGRATED_TO_MODEL_BACKEND" if present else "NOT_PRESENT"
        elif source_file == "intent_router.py" and not (repo_root / source_file).exists():
            migration_status = "SOURCE_FILE_NOT_PRESENT"
        else:
            migration_status = "FOUND_LEGACY_COMPATIBILITY_NAME" if present else "NOT_PRESENT"
        findings.append(
            LegacyOntologyFinding(
                finding_id=finding_id,
                source_file=source_file,
                legacy_pattern=pattern,
                risk=risk,
                recommended_replacement=replacement,
                migration_status=migration_status,
                next_safe_move="Treat as compatibility naming only; future schemas should use separated agent/model/worker fields.",
            )
        )
    return tuple(findings)


def build_binding_examples() -> tuple[AgentModelBindingExample, ...]:
    boundary = dict(AUTHORITY_BOUNDARY)
    return (
        AgentModelBindingExample(
            "example:chief_uses_code_backend",
            "CHIEF",
            "operations planning / code-build lane status",
            "model_backend:openai_codex",
            "PC_CODEX_WORKER",
            ("repo_read", "local_tests", "generated_readmodel_write_when_package_grants"),
            ("external_action", "send_submit", "credential_access"),
            boundary,
            "Chief remains the agent; Codex is only the code/build backend.",
            "Codex is the agent and can execute because the model chose it.",
            "It conflates agent identity with backend and invents authority.",
            "Validate the package and authority boundary before any worker action.",
        ),
        AgentModelBindingExample(
            "example:hermes_uses_gemini_agy",
            "HERMES",
            "architecture audit",
            "model_backend:gemini_agy",
            "GEMINI_AGY_ADVISORY_WORKER",
            ("read_only_context_refs",),
            ("file_edit", "commit", "approval_execution", "external_action"),
            boundary,
            "Hermes remains the advisory agent; Gemini/Agy is an audit backend.",
            "Gemini approved the architecture and started the build.",
            "Model/backend output cannot approve or execute.",
            "Return advisory findings and route build work through deterministic gates.",
        ),
        AgentModelBindingExample(
            "example:cassandra_draft_model",
            "CASSANDRA",
            "OUTBOUND_MESSAGE_DRAFT",
            "model_backend:openai_gpt",
            "CASSANDRA",
            ("draft_readback_only",),
            ("email_send", "contact_private_body_exposure", "portal_submit"),
            boundary,
            "Cassandra may use a writing backend for reviewable drafts, with send authority false.",
            "The writing model sent the draft.",
            "A draft backend cannot grant send authority.",
            "Prepare draft text and wait for exact gated send approval.",
        ),
        AgentModelBindingExample(
            "example:niles_creative_model",
            "NILES",
            "creative ideation / music planning",
            "model_backend:openai_gpt",
            "NILES",
            ("creative_planning_only", "source_ref_navigation"),
            ("daw_mutation", "session_file_save", "external_action"),
            boundary,
            "Niles can use creative reasoning without mutating files or sessions.",
            "The creative model updated the DAW session.",
            "Creative model output cannot mutate files or claim project edits.",
            "Ask for source refs and keep ideation non-mutating.",
        ),
        AgentModelBindingExample(
            "example:guardian_deterministic_first",
            "GUARDIAN",
            "proof / approval / protected boundary",
            "model_backend:local_ollama",
            "GUARDIAN",
            ("proof_ref_readback_only",),
            ("approval_execution", "secret_reveal", "send_submit"),
            boundary,
            "Guardian deterministic gates decide authority; LM explanation is optional and advisory.",
            "The LM said approved enough.",
            "No model may approve or soften Guardian gates.",
            "Use proof receipts and exact approval packets.",
        ),
        AgentModelBindingExample(
            "example:openclaw_system_file_intake",
            "SYSTEM_IDENTITY:OPENCLAW_SYSTEM",
            "file metadata intake",
            "model_backend:none_deterministic",
            "OPENCLAW_SYSTEM",
            ("metadata_readback",),
            ("persona_lore", "file_body_read", "file_analysis_claim"),
            boundary,
            "OpenClaw System is a neutral system identity, not a persona agent.",
            "OpenClaw System cheerfully analyzed the file.",
            "It invents persona and file body analysis.",
            "Use sterile metadata-only readback.",
        ),
        AgentModelBindingExample(
            "bad_example:codex_as_agent",
            "INVALID:CODEX",
            "code/build lane",
            "model_backend:openai_codex",
            "PC_CODEX_WORKER",
            (),
            ("agent_role=CODEX", "self_authorized_execution"),
            boundary,
            "Invalid fixture included to prove Codex is backend/worker/model only.",
            "Codex is an OpenClaw agent.",
            "Codex is not one of the five named agents.",
            "Use agent_role=CHIEF or HERMES with selected_model_backend=model_backend:openai_codex when appropriate.",
        ),
        AgentModelBindingExample(
            "bad_example:model_backend_grants_authority",
            "INVALID:GEMINI_AGY",
            "advisory audit",
            "model_backend:gemini_agy",
            "GEMINI_AGY_ADVISORY_WORKER",
            (),
            ("authority_granted_by_model", "tool_use_without_package", "external_action"),
            boundary,
            "Invalid fixture included to prove model backends never grant authority.",
            "Gemini/Agy granted approval and dispatched the worker.",
            "A model backend cannot grant authority, approve, dispatch, or execute.",
            "Keep output candidate until deterministic validation and human/Guardian gates.",
        ),
    )


def build_policy(
    agent_profiles: tuple[OpenClawAgentProfile, ...],
    system_identities: tuple[SystemIdentityProfile, ...],
    model_backends: tuple[ModelBackendProfile, ...],
    worker_backends: tuple[WorkerBackendType, ...],
    findings: tuple[LegacyOntologyFinding, ...],
) -> AgentRosterPolicy:
    return AgentRosterPolicy(
        policy_id="agent_roster_model_backend_policy_v0",
        doctrine=(
            "Agent = role + doctrine + memory/context + permissions + voice/vibe + task lane.",
            "Model backend = reasoning engine selected for a specific task.",
            "Worker backend = runtime/execution environment or advisory worker surface.",
            "Plugin/tool/adapter = bounded capability granted by a deterministic package.",
            "Package = deterministic script/context/tools/authority/output schema.",
        ),
        agent_roles=tuple(profile.agent_role for profile in agent_profiles),
        system_identities=tuple(identity.system_identity_ref for identity in system_identities),
        model_backend_roles=tuple(backend.model_backend_ref for backend in model_backends),
        worker_backend_roles=tuple(worker.worker_backend_ref for worker in worker_backends),
        separation_policy=(
            "agent_role, system_identity, selected_model_backend, selected_worker_type, allowed_tools/plugins/adapters, authority_boundary, and credit/budget/privacy policy are separate fields.",
            "Model selection does not grant authority.",
            "Selected model cannot use tools unless a deterministic package grants them.",
            "Model output remains candidate until deterministic validation.",
            "Provider/model/backend cannot self-authorize.",
        ),
        forbidden_conflations=(
            "Codex as agent role",
            "Gemini/Agy as agent role",
            "OpenClaw System as persona agent",
            "model backend implies tool authority",
            "worker route implies workflow execution",
            "provider output implies approval",
        ),
        legacy_migration_notes=tuple(f"{finding.source_file}:{finding.legacy_pattern}:{finding.migration_status}" for finding in findings),
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move="Use this roster policy as the compatibility map before live LM intent interpretation.",
    )


def build_payload(generated_at: str = DEFAULT_GENERATED_AT, *, repo_root: Path = Path(".")) -> dict[str, Any]:
    agent_profiles = build_agent_profiles()
    system_identities = build_system_identities()
    model_backends = build_model_backend_profiles()
    model_selection = build_model_selection_policies()
    worker_backends = build_worker_backend_types()
    findings = build_legacy_findings(repo_root)
    examples = build_binding_examples()
    policy = build_policy(agent_profiles, system_identities, model_backends, worker_backends, findings)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "agent_roles": AGENT_ROLES,
        "system_identities": SYSTEM_IDENTITIES,
        "provider_families": PROVIDER_FAMILIES,
        "worker_types": WORKER_TYPES,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "model_schemas": {
            **_model_schema(AgentRosterPolicy),
            **_model_schema(OpenClawAgentProfile),
            **_model_schema(SystemIdentityProfile),
            **_model_schema(ModelBackendProfile),
            **_model_schema(ModelSelectionPolicy),
            **_model_schema(WorkerBackendType),
            **_model_schema(LegacyOntologyFinding),
            **_model_schema(AgentModelBindingExample),
        },
        "policy": asdict(policy),
        "agent_profiles": tuple(asdict(profile) for profile in agent_profiles),
        "system_identity_profiles": tuple(asdict(identity) for identity in system_identities),
        "model_backend_profiles": tuple(asdict(backend) for backend in model_backends),
        "model_selection_policies": tuple(asdict(policy_row) for policy_row in model_selection),
        "worker_backend_types": tuple(asdict(worker) for worker in worker_backends),
        "legacy_ontology_findings": tuple(asdict(finding) for finding in findings),
        "binding_examples": tuple(asdict(example) for example in examples),
        "operator_summary": (
            "OpenClaw has five persona agents: Cassandra, Chief, Niles, Guardian, and Hermes. "
            "OpenClaw System is a neutral system identity. Codex, Gemini/Agy, GPT, Claude, Ollama, and future providers are backends."
        ),
        "next_safe_move": "Wire future intent validation to this ontology before allowing live LM interpretation.",
    }
    valid_agents = {profile["agent_role"] for profile in payload["agent_profiles"]}
    invalid_examples = {example["example_id"] for example in payload["binding_examples"] if str(example["example_id"]).startswith("bad_example:")}
    payload["machine_proof"] = {
        "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        "five_required_agents_present": valid_agents == set(AGENT_ROLES),
        "openclaw_system_is_system_identity_not_agent": "OPENCLAW_SYSTEM" not in valid_agents and SYSTEM_IDENTITIES == ("OPENCLAW_SYSTEM",),
        "codex_is_not_agent": "CODEX" not in valid_agents,
        "gemini_agy_is_not_agent": "GEMINI_AGY" not in valid_agents,
        "ollama_is_not_agent": "LOCAL_OLLAMA" not in valid_agents,
        "hermes_profile_present": "HERMES" in valid_agents,
        "model_backend_profiles_present": bool(payload["model_backend_profiles"]),
        "model_selection_policy_present": bool(payload["model_selection_policies"]),
        "worker_backend_types_present": bool(payload["worker_backend_types"]),
        "legacy_findings_present": bool(payload["legacy_ontology_findings"]),
        "codex_as_agent_bad_example_invalid": "bad_example:codex_as_agent" in invalid_examples,
        "model_backend_grants_authority_bad_example_invalid": "bad_example:model_backend_grants_authority" in invalid_examples,
        "model_call_performed": False,
        "agent_dispatch_performed": False,
        "worker_dispatch_performed": False,
        "workflow_run_performed": False,
        "external_action_performed": False,
        "send_submit_performed": False,
        "tool_use_performed": False,
        "credential_handling_performed": False,
        "raw_body_ingestion_performed": False,
        "mac_sync_import_performed": False,
        "swift_change_performed": False,
        "git_push_performed": False,
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Agent Roster + Model Backend Policy",
        "",
        "## Roster",
        f"- Agents: {', '.join(payload['agent_roles'])}",
        f"- System identities: {', '.join(payload['system_identities'])}",
        "",
        "## Model Backends",
    ]
    for backend in payload["model_backend_profiles"]:
        lines.append(f"- {backend['provider_family']}: {backend['display_name']} - {backend['next_safe_move']}")
    lines += ["", "## Worker Backends"]
    for worker in payload["worker_backend_types"]:
        lines.append(f"- {worker['worker_type']}: {worker['description']}")
    lines += ["", "## Legacy Findings"]
    for finding in payload["legacy_ontology_findings"]:
        lines.append(f"- {finding['source_file']} / {finding['legacy_pattern']}: {finding['migration_status']}")
    lines += [
        "",
        "## Boundary",
        "No live model call, no agent dispatch, no worker dispatch, no workflow run, no external action, no send/submit, no tool use, no credential handling, no raw-body ingestion.",
        "",
        f"Next safe move: {payload['next_safe_move']}",
        "",
    ]
    return "\n".join(lines)


def write_exports(payload: dict[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return json_path, operator_path


def build_summary(payload: dict[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> dict[str, Any]:
    return {
        "read_model_id": payload["read_model_id"],
        "contract_status": payload["contract_status"],
        "agent_count": len(payload["agent_profiles"]),
        "system_identity_count": len(payload["system_identity_profiles"]),
        "model_backend_count": len(payload["model_backend_profiles"]),
        "model_selection_policy_count": len(payload["model_selection_policies"]),
        "worker_backend_count": len(payload["worker_backend_types"]),
        "legacy_finding_count": len(payload["legacy_ontology_findings"]),
        "codex_is_not_agent": payload["machine_proof"]["codex_is_not_agent"],
        "gemini_agy_is_not_agent": payload["machine_proof"]["gemini_agy_is_not_agent"],
        "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
        "json_export": str(export_root / JSON_EXPORT_NAME),
        "operator_export": str(export_root / OPERATOR_EXPORT_NAME),
    }


def build_and_export(
    *,
    generated_at: str = DEFAULT_GENERATED_AT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    repo_root: Path = Path("."),
    format_name: str = "summary",
) -> dict[str, Any]:
    payload = build_payload(generated_at=generated_at, repo_root=repo_root)
    write_exports(payload, export_root)
    return payload if format_name == "json" else build_summary(payload, export_root)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Agent Roster + Model Backend Policy read-model.")
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--format", choices=("json", "summary"), default="summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = build_and_export(
        generated_at=args.generated_at,
        export_root=Path(args.export_root),
        repo_root=Path(args.repo_root),
        format_name=args.format,
    )
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
