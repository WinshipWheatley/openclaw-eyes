"""Worker Routing Intelligence v0.

This deterministic read-model decides which worker lane a chat/request packet
belongs to. It produces a route decision and package recommendation only. It
does not auto-dispatch workers, execute packages, call models, run workflows,
access external systems, handle credentials, ingest raw private bodies, mutate
Mission Control Swift, run Mac sync/import, or push.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-25T00:00:00+00:00"

SCHEMA_VERSION = "worker_routing_intelligence_v0"
READ_MODEL_ID = "worker_routing_intelligence"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_EXECUTING_WORKER_ROUTING_INTELLIGENCE"

WORKER_TYPES = (
    "MAC_CODEX",
    "PC_CODEX",
    "GEMINI_AGY",
    "LOCAL_OLLAMA",
    "GUARDIAN",
    "CASSANDRA",
    "UNKNOWN_NEEDS_ROUTING",
)

MACHINES = (
    "MAC",
    "PC_WSL",
    "LOCAL_ONLY",
    "EXTERNAL_MODEL",
    "UNKNOWN",
)

CONFIDENCE_VALUES = ("HIGH", "MEDIUM", "LOW", "UNKNOWN_FAIL_CLOSED")

BLOCKER_TYPES = (
    "WRONG_WORKER_SELECTED",
    "WRONG_MACHINE_SELECTED",
    "AUTHORITY_TOO_BROAD",
    "EXTERNAL_ACTION_INCLUDED",
    "RAW_PII_IN_PACKAGE",
    "CREDENTIAL_IN_PACKAGE",
    "MISSING_CONTEXT",
    "AMBIGUOUS_REQUEST",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
    "live_auto_dispatch_allowed": False,
    "live_worker_execution_allowed": False,
    "live_cross_machine_send_allowed": False,
    "live_agent_dispatch_allowed": False,
    "live_model_call_allowed": False,
    "live_workflow_run_allowed": False,
    "live_external_action_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_allowed": False,
    "email_send_allowed": False,
    "coupa_access_allowed": False,
    "browser_automation_allowed": False,
    "approval_submission_allowed": False,
    "mission_control_swift_change_allowed": False,
    "mac_sync_import_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

EXPECTED_RETURN_FORMAT = (
    "STATUS",
    "SUMMARY",
    "RESULT",
    "VALIDATION",
    "COMMIT",
    "BOUNDARY CHECK",
)

COMMON_EXCLUDED_CONTEXT = (
    "credentials",
    "tokens",
    "cookies",
    "raw private bodies",
    "protected evidence bodies",
    "external account contents",
    "private document bodies",
)

MAC_PATTERNS = (
    "swiftui",
    "appkit",
    "xcode",
    "mission control ui",
    "macos app",
    "app layout",
    "composer",
    "cards inside the chat",
    "card render inside chat",
    "screenshot validation",
    "app build",
    "build/run validation",
    "entitlements",
    "sandboxing",
    "mac-local",
    "mac readback package",
    "mounted volume",
    "file picker",
    "document picker",
    "screen capture",
    "logic pro",
    "ableton",
    "final cut",
    "davinci resolve",
    "mail",
    "calendar",
    "contacts",
    "messages",
    "telegram desktop",
    "mac app",
)

PC_PATTERNS = (
    "repo a",
    "backend",
    "python",
    "sqlite",
    "receipt",
    "read-model",
    "read model",
    "tests",
    "pytest",
    "script",
    "contract",
    "pc-to-mac",
    "to mac package",
    "shuttle package",
    "package the readback",
    "pc package",
    "post office",
    "router intake",
    "router/readback",
    "readback card mirror",
    "workflow package compiler",
    "package compiler",
    "worker routing intelligence",
    "pii",
    "tokenization",
    "protected evidence contract",
    "work terrain",
    "build cue",
    "capital hilton backend",
)

GEMINI_PATTERNS = (
    "audit",
    "scout",
    "critique",
    "taste",
    "architecture review",
    "prompt shaping",
    "what should codex do next",
    "gotcha",
    "read-only report",
)

GUARDIAN_PATTERNS = (
    "approval",
    "protected evidence",
    "sensitive boundary",
    "security posture",
    "should this be allowed",
    "guardian",
)

CASSANDRA_PATTERNS = (
    "communication drafting",
    "draft email",
    "review packet language",
    "invoice-facing copy",
    "email-facing copy",
    "operator-facing follow-up",
    "cassandra",
)

LOCAL_OLLAMA_PATTERNS = (
    "local summarization",
    "local classification",
    "low-risk reasoning",
    "offline chat support",
    "local model",
    "ollama",
)

EXTERNAL_ACTION_PATTERNS = (
    "send the invoice",
    "send email",
    "submit invoice",
    "submit to coupa",
    "coupa submit",
    "gmail send",
    "mail send",
    "approval submission",
    "use credentials",
    "log in",
)


@dataclass(frozen=True)
class WorkerRoutingIntelligence:
    router_id: str
    doctrine: tuple[str, ...]
    supported_workers: tuple[str, ...]
    routing_rules: tuple[dict[str, Any], ...]
    confidence_policy: tuple[str, ...]
    ambiguity_policy: tuple[str, ...]
    authority_policy: tuple[str, ...]
    package_policy: tuple[str, ...]
    readback_policy: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class WorkerRouteDecision:
    decision_id: str
    source_chat_ref: str
    operator_request_summary: str
    selected_worker_type: str
    selected_machine: str
    selected_environment: str
    task_type: str
    confidence: str
    route_reason: str
    alternate_workers: tuple[str, ...]
    blocked_workers: tuple[str, ...]
    handoff_required: bool
    package_required: bool
    next_safe_move: str


@dataclass(frozen=True)
class WorkerRoutingRule:
    rule_id: str
    worker_type: str
    machine: str
    match_patterns: tuple[str, ...]
    task_types: tuple[str, ...]
    positive_examples: tuple[str, ...]
    negative_examples: tuple[str, ...]
    allowed_actions: tuple[str, ...]
    forbidden_actions: tuple[str, ...]
    confidence_boost: str
    next_safe_move: str


@dataclass(frozen=True)
class WorkerPackageRecommendation:
    recommendation_id: str
    route_decision_ref: str
    package_type: str
    package_title: str
    target_worker_type: str
    target_machine: str
    context_needed: tuple[str, ...]
    context_excluded: tuple[str, ...]
    validation_required: tuple[str, ...]
    expected_return_format: tuple[str, ...]
    operator_card_summary: str
    next_safe_move: str


@dataclass(frozen=True)
class WorkerRoutingBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    elioperator_warning: str
    fail_closed: bool
    next_safe_move: str


REQUIRED_INTELLIGENCE_FIELDS = tuple(WorkerRoutingIntelligence.__dataclass_fields__.keys())
REQUIRED_DECISION_FIELDS = tuple(WorkerRouteDecision.__dataclass_fields__.keys())
REQUIRED_RULE_FIELDS = tuple(WorkerRoutingRule.__dataclass_fields__.keys())
REQUIRED_RECOMMENDATION_FIELDS = tuple(WorkerPackageRecommendation.__dataclass_fields__.keys())
REQUIRED_BLOCKER_FIELDS = tuple(WorkerRoutingBlocker.__dataclass_fields__.keys())


def stable_json(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clean = json.loads(stable_json(payload))
    clean.get("machine_proof", {}).pop("content_hash", None)
    return hashlib.sha256(stable_json(clean).encode("utf-8")).hexdigest()


def _contains_any(text: str, patterns: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(pattern in lowered for pattern in patterns)


def _source_ref(summary: str) -> str:
    digest = hashlib.sha256(summary.lower().encode("utf-8")).hexdigest()[:12]
    return f"operator_chat_{digest}"


def _task_type_for_mac(summary: str) -> str:
    lowered = summary.lower()
    if any(term in lowered for term in ("logic pro", "ableton", "final cut", "davinci resolve")):
        return "APPLE_APP_INTEGRATION_SCOUT_OR_UI"
    if "mail" in lowered and "send" in lowered:
        return "MAC_MAIL_BOUNDARY_REVIEW"
    if "import" in lowered and ("package" in lowered or "readback" in lowered):
        return "MAC_PACKAGE_IMPORT_RENDER"
    return "SWIFTUI_APP_UI"


def _task_type_for_pc(summary: str) -> str:
    lowered = summary.lower()
    if "package" in lowered and "mac" in lowered:
        return "SHUTTLE_PACKAGE"
    if "compiler" in lowered:
        return "BACKEND_PACKAGE_COMPILER"
    if "consume" in lowered and "request" in lowered:
        return "BACKEND_INTAKE"
    return "BACKEND_READMODEL"


def route_request(operator_request_summary: str, *, source_chat_ref: str | None = None) -> WorkerRouteDecision:
    summary = " ".join(operator_request_summary.split())
    source = source_chat_ref or _source_ref(summary)
    lowered = summary.lower()

    if not summary or lowered in {"make it better", "make it better.", "fix it", "help"}:
        return WorkerRouteDecision(
            decision_id=f"decision_unknown_{hashlib.sha256(summary.encode()).hexdigest()[:10]}",
            source_chat_ref=source,
            operator_request_summary=summary,
            selected_worker_type="UNKNOWN_NEEDS_ROUTING",
            selected_machine="UNKNOWN",
            selected_environment="none",
            task_type="UNKNOWN_NEEDS_FRAMING",
            confidence="LOW",
            route_reason="Request is too broad to choose a worker, machine, files, or success criteria safely.",
            alternate_workers=("MAC_CODEX", "PC_CODEX", "GEMINI_AGY", "GUARDIAN", "CASSANDRA"),
            blocked_workers=(),
            handoff_required=False,
            package_required=False,
            next_safe_move="Ask whether this is Mac app work, Repo A backend work, read-only scouting, comms drafting, or safety review.",
        )

    if _contains_any(lowered, GEMINI_PATTERNS):
        return WorkerRouteDecision(
            decision_id=f"decision_gemini_agy_{hashlib.sha256(summary.encode()).hexdigest()[:10]}",
            source_chat_ref=source,
            operator_request_summary=summary,
            selected_worker_type="GEMINI_AGY",
            selected_machine="EXTERNAL_MODEL",
            selected_environment="read-only scout packet",
            task_type="READ_ONLY_AUDIT",
            confidence="HIGH",
            route_reason="The request is read-only scouting, critique, architecture review, gotcha discovery, or prompt shaping.",
            alternate_workers=("PC_CODEX for implementation after scout", "MAC_CODEX for Mac UI implementation after scout"),
            blocked_workers=("workers with file edit authority", "workers with external action authority"),
            handoff_required=True,
            package_required=True,
            next_safe_move="Prepare a read-only scout package with edits, commits, execution, credentials, and external action forbidden.",
        )

    if _contains_any(lowered, GUARDIAN_PATTERNS) and not ("mission control" in lowered or "swiftui" in lowered):
        return WorkerRouteDecision(
            decision_id=f"decision_guardian_{hashlib.sha256(summary.encode()).hexdigest()[:10]}",
            source_chat_ref=source,
            operator_request_summary=summary,
            selected_worker_type="GUARDIAN",
            selected_machine="LOCAL_ONLY",
            selected_environment="Guardian approval/protected-boundary lane",
            task_type="APPROVAL_OR_PROTECTED_BOUNDARY_REVIEW",
            confidence="HIGH",
            route_reason="The request asks for approval, protected evidence, safety posture, or should-this-be-allowed review.",
            alternate_workers=("PC_CODEX for implementation after approval", "CASSANDRA for draft language after approval"),
            blocked_workers=("workers with direct external action authority",),
            handoff_required=True,
            package_required=True,
            next_safe_move="Prepare a Guardian review package; do not approve or execute from the router.",
        )

    if _contains_any(lowered, CASSANDRA_PATTERNS) and not _contains_any(lowered, EXTERNAL_ACTION_PATTERNS):
        return WorkerRouteDecision(
            decision_id=f"decision_cassandra_{hashlib.sha256(summary.encode()).hexdigest()[:10]}",
            source_chat_ref=source,
            operator_request_summary=summary,
            selected_worker_type="CASSANDRA",
            selected_machine="LOCAL_ONLY",
            selected_environment="Cassandra communications drafting lane",
            task_type="COMMUNICATION_DRAFTING",
            confidence="HIGH",
            route_reason="The request asks for communications drafting or operator-facing follow-up language.",
            alternate_workers=("GUARDIAN for approval boundary", "PC_CODEX for backend packet generation"),
            blocked_workers=("workers with send authority",),
            handoff_required=True,
            package_required=True,
            next_safe_move="Prepare a drafting package with send authority excluded.",
        )

    if _contains_any(lowered, LOCAL_OLLAMA_PATTERNS):
        return WorkerRouteDecision(
            decision_id=f"decision_local_ollama_{hashlib.sha256(summary.encode()).hexdigest()[:10]}",
            source_chat_ref=source,
            operator_request_summary=summary,
            selected_worker_type="LOCAL_OLLAMA",
            selected_machine="LOCAL_ONLY",
            selected_environment="local model responder lane",
            task_type="LOCAL_SUMMARY_OR_CLASSIFICATION",
            confidence="MEDIUM",
            route_reason="The request is bounded local summarization/classification or low-risk reasoning.",
            alternate_workers=("PC_CODEX if backend implementation is required",),
            blocked_workers=("cloud or external model for sensitive context unless explicitly approved",),
            handoff_required=True,
            package_required=True,
            next_safe_move="Prepare a local-only context package if an approved local model path exists.",
        )

    if _contains_any(lowered, MAC_PATTERNS):
        is_authority_broad = _contains_any(lowered, EXTERNAL_ACTION_PATTERNS)
        return WorkerRouteDecision(
            decision_id=f"decision_mac_codex_{hashlib.sha256(summary.encode()).hexdigest()[:10]}",
            source_chat_ref=source,
            operator_request_summary=summary,
            selected_worker_type="MAC_CODEX",
            selected_machine="MAC",
            selected_environment="Mission Control Mac repo",
            task_type=_task_type_for_mac(summary),
            confidence="HIGH" if not is_authority_broad else "MEDIUM",
            route_reason="The request involves Apple/Mac-side app behavior, UI, validation, local import/render, or Apple app integration.",
            alternate_workers=("GEMINI_AGY for read-only critique", "GUARDIAN for approval boundary if external action is involved"),
            blocked_workers=("PC_CODEX for direct Swift/Mac UI edits", "any worker with live send/submit authority"),
            handoff_required=True,
            package_required=True,
            next_safe_move="Prepare a Mac Codex package with external authority stripped and gated.",
        )

    if _contains_any(lowered, PC_PATTERNS):
        return WorkerRouteDecision(
            decision_id=f"decision_pc_codex_{hashlib.sha256(summary.encode()).hexdigest()[:10]}",
            source_chat_ref=source,
            operator_request_summary=summary,
            selected_worker_type="PC_CODEX",
            selected_machine="PC_WSL",
            selected_environment="/home/openclaw",
            task_type=_task_type_for_pc(summary),
            confidence="HIGH",
            route_reason="The request involves canonical Repo A backend, Python, read-models, tests, scripts, package/shuttle generation, or router/intake/readback work.",
            alternate_workers=("GEMINI_AGY for read-only audit",),
            blocked_workers=("MAC_CODEX for canonical backend mutation",),
            handoff_required=True,
            package_required=True,
            next_safe_move="Prepare a PC Codex package with Repo A validation requirements.",
        )

    return WorkerRouteDecision(
        decision_id=f"decision_unknown_{hashlib.sha256(summary.encode()).hexdigest()[:10]}",
        source_chat_ref=source,
        operator_request_summary=summary,
        selected_worker_type="UNKNOWN_NEEDS_ROUTING",
        selected_machine="UNKNOWN",
        selected_environment="none",
        task_type="UNKNOWN_NEEDS_FRAMING",
        confidence="LOW",
        route_reason="No deterministic worker rule matched with enough confidence.",
        alternate_workers=("MAC_CODEX", "PC_CODEX", "GEMINI_AGY", "GUARDIAN", "CASSANDRA", "LOCAL_OLLAMA"),
        blocked_workers=(),
        handoff_required=False,
        package_required=False,
        next_safe_move="Ask a clarifying question and offer routing options.",
    )


def build_routing_rules() -> tuple[WorkerRoutingRule, ...]:
    return (
        WorkerRoutingRule(
            rule_id="rule_mac_codex_mac_app",
            worker_type="MAC_CODEX",
            machine="MAC",
            match_patterns=MAC_PATTERNS,
            task_types=("SWIFTUI_APP_UI", "APPLE_APP_INTEGRATION_SCOUT_OR_UI", "MAC_PACKAGE_IMPORT_RENDER", "MAC_MAIL_BOUNDARY_REVIEW"),
            positive_examples=(
                "Fix the Mission Control chat UI so cards render inside the chat.",
                "Add Logic Pro project recognition to the Mac app.",
                "Import this Mac readback package.",
            ),
            negative_examples=("Build the backend read-model.", "Generate the PC-to-Mac package."),
            allowed_actions=("Swift/Mac app edits", "Xcode build/test", "screenshot validation", "bounded Mac file copy/import from approved shuttle packages", "Mac-local UI inspection"),
            forbidden_actions=("Repo A backend mutation", "PC/WSL canonical state writes", "external Gmail/Coupa/browser actions", "credential handling", "live send/submit", "broad filesystem scans", "hidden watchers/daemons", "arbitrary AppleScript/JXA automation", "DAW/media-app mutation without explicit approval/backup/receipt posture"),
            confidence_boost="HIGH when Apple/Mac-side UI, validation, or integration terms appear.",
            next_safe_move="Prepare a Mac Codex package; strip external action authority.",
        ),
        WorkerRoutingRule(
            rule_id="rule_pc_codex_repo_a_backend",
            worker_type="PC_CODEX",
            machine="PC_WSL",
            match_patterns=PC_PATTERNS,
            task_types=("BACKEND_READMODEL", "BACKEND_INTAKE", "BACKEND_PACKAGE_COMPILER", "SHUTTLE_PACKAGE"),
            positive_examples=(
                "Build the backend read-model.",
                "Consume this Mac request.",
                "Generate the PC-to-Mac package.",
                "Add the package compiler.",
            ),
            negative_examples=("Fix the SwiftUI app layout.", "Take a screenshot of the Mac app."),
            allowed_actions=("Python edits", "pytest", "generated read-models", "bounded SQLite/receipt work when explicitly scoped", "package/shuttle generation", "authority/PII scans"),
            forbidden_actions=("Mac Swift edits", "Mac app UI changes", "external account access", "Gmail/Coupa/browser/Telegram actions", "credential handling", "raw private body ingestion", "live send/submit/approval"),
            confidence_boost="HIGH when Repo A, backend, Python, read-model, router, compiler, or shuttle terms appear.",
            next_safe_move="Prepare a PC Codex package with validation commands and generated read-model targets.",
        ),
        WorkerRoutingRule(
            rule_id="rule_gemini_agy_read_only_scout",
            worker_type="GEMINI_AGY",
            machine="EXTERNAL_MODEL",
            match_patterns=GEMINI_PATTERNS,
            task_types=("READ_ONLY_AUDIT", "PROMPT_SHAPING", "DESIGN_CRITIQUE"),
            positive_examples=("Audit whether the chat-first pivot should reuse existing card contracts.", "What should Codex do next?"),
            negative_examples=("Edit the Python file.", "Commit the SwiftUI fix."),
            allowed_actions=("read-only scout", "audit", "visual/taste critique", "architecture review", "prompt shaping", "gotcha discovery"),
            forbidden_actions=("file edits", "commits", "live execution", "external action", "credential access"),
            confidence_boost="HIGH when the request is explicitly scout/audit/critique/prompt shaping.",
            next_safe_move="Prepare a sanitized read-only scout packet.",
        ),
        WorkerRoutingRule(
            rule_id="rule_local_ollama_local_reasoning",
            worker_type="LOCAL_OLLAMA",
            machine="LOCAL_ONLY",
            match_patterns=LOCAL_OLLAMA_PATTERNS,
            task_types=("LOCAL_SUMMARY_OR_CLASSIFICATION",),
            positive_examples=("Summarize this low-risk local note with a local model.",),
            negative_examples=("Edit Repo A backend files.", "Send the invoice."),
            allowed_actions=("bounded local summarization", "classification", "low-risk reasoning"),
            forbidden_actions=("external action", "sensitive external capability", "credential access", "tool execution"),
            confidence_boost="MEDIUM unless an approved local model path is known.",
            next_safe_move="Prepare local-only context if the local model rail exists.",
        ),
        WorkerRoutingRule(
            rule_id="rule_guardian_boundary",
            worker_type="GUARDIAN",
            machine="LOCAL_ONLY",
            match_patterns=GUARDIAN_PATTERNS,
            task_types=("APPROVAL_OR_PROTECTED_BOUNDARY_REVIEW",),
            positive_examples=("Should this be allowed?", "Review protected evidence boundary."),
            negative_examples=("Implement the backend module.", "Fix the SwiftUI layout."),
            allowed_actions=("approval review", "protected evidence boundary review", "security posture review"),
            forbidden_actions=("live approval submission", "external action", "credential access", "raw protected body exposure"),
            confidence_boost="HIGH for approval/protected/safety-boundary language.",
            next_safe_move="Prepare a Guardian review package.",
        ),
        WorkerRoutingRule(
            rule_id="rule_cassandra_comms",
            worker_type="CASSANDRA",
            machine="LOCAL_ONLY",
            match_patterns=CASSANDRA_PATTERNS,
            task_types=("COMMUNICATION_DRAFTING",),
            positive_examples=("Draft the invoice follow-up language for review.",),
            negative_examples=("Send the invoice now.", "Build the backend read-model."),
            allowed_actions=("communication drafting", "review packet language", "operator-facing follow-up"),
            forbidden_actions=("send", "approval bypass", "credential handling", "external action"),
            confidence_boost="HIGH for drafting/review-language requests without send authority.",
            next_safe_move="Prepare a drafting package with send authority excluded.",
        ),
        WorkerRoutingRule(
            rule_id="rule_unknown_needs_routing",
            worker_type="UNKNOWN_NEEDS_ROUTING",
            machine="UNKNOWN",
            match_patterns=("make it better", "fix it", "help"),
            task_types=("UNKNOWN_NEEDS_FRAMING",),
            positive_examples=("Make it better.",),
            negative_examples=("Fix the Mission Control chat UI.", "Build the backend read-model."),
            allowed_actions=("ask clarifying question", "show routing options"),
            forbidden_actions=("worker dispatch", "file edits", "external action"),
            confidence_boost="LOW; ask for target surface and outcome.",
            next_safe_move="Ask what surface and outcome the operator means.",
        ),
    )


def build_intelligence(rules: tuple[WorkerRoutingRule, ...]) -> WorkerRoutingIntelligence:
    return WorkerRoutingIntelligence(
        router_id="worker_routing_intelligence_v0",
        doctrine=(
            "One chat window is the operator surface.",
            "The router chooses the right worker.",
            "The package carries the right context.",
            "The worker acts only inside its lane.",
            "The result returns to the same chat.",
            "Truth comes from receipts/readbacks.",
            "Routing is not dispatch.",
        ),
        supported_workers=WORKER_TYPES,
        routing_rules=tuple(asdict(rule) for rule in rules),
        confidence_policy=(
            "HIGH when deterministic domain and machine patterns clearly match one worker.",
            "MEDIUM when a worker lane is clear but authority must be stripped or reviewed.",
            "LOW when target surface or success criteria are ambiguous.",
            "Unknowns fail closed into clarification.",
        ),
        ambiguity_policy=(
            "Do not guess hidden scope.",
            "Route vague requests to UNKNOWN_NEEDS_ROUTING.",
            "Ask whether the request is Mac app work, Repo A backend work, read-only scouting, communications drafting, or safety review.",
        ),
        authority_policy=(
            "No route grants live execution.",
            "External action language is stripped or blocked.",
            "Credentials and raw private bodies are excluded from packages.",
            "Send/submit/approval requires future governed adapters and receipts.",
        ),
        package_policy=(
            "Route decisions produce package recommendations only.",
            "Context is scoped to worker and task.",
            "Package recommendations include validation and expected return format.",
            "Cross-machine send remains false in this contract.",
        ),
        readback_policy=(
            "Worker results return to the same chat as readbacks/cards.",
            "Worker claims are not truth without receipts/readbacks.",
            "Blocked routes explain the next safe move in human language.",
        ),
        next_safe_move="Use deterministic route decisions to prepare a package recommendation, then wait for explicit operator send.",
    )


def _package_type_for_decision(decision: WorkerRouteDecision) -> str:
    if decision.selected_worker_type == "MAC_CODEX":
        return "MAC_WORKER_PACKAGE"
    if decision.selected_worker_type == "PC_CODEX":
        return "PC_WORKER_PACKAGE"
    if decision.selected_worker_type == "GEMINI_AGY":
        return "READ_ONLY_SCOUT_PACKAGE"
    if decision.selected_worker_type == "GUARDIAN":
        return "GUARDIAN_REVIEW_PACKAGE"
    if decision.selected_worker_type == "CASSANDRA":
        return "COMMUNICATION_DRAFT_PACKAGE"
    if decision.selected_worker_type == "LOCAL_OLLAMA":
        return "LOCAL_MODEL_CONTEXT_PACKAGE"
    return "UNKNOWN_NEEDS_ROUTING"


def _context_needed_for_decision(decision: WorkerRouteDecision) -> tuple[str, ...]:
    if decision.selected_worker_type == "MAC_CODEX":
        return ("operator goal", "Mac app surface", "approved shuttle package refs if relevant", "expected build/test/screenshot validation")
    if decision.selected_worker_type == "PC_CODEX":
        return ("operator goal", "Repo A file scope", "source read-model refs", "validation commands", "commit policy")
    if decision.selected_worker_type == "GEMINI_AGY":
        return ("sanitized summaries", "specific audit question", "read-only source excerpts", "desired report format")
    if decision.selected_worker_type == "GUARDIAN":
        return ("approval question", "protected boundary summary", "risk posture", "required receipts")
    if decision.selected_worker_type == "CASSANDRA":
        return ("draft purpose", "recipient/contact posture", "tone constraints", "send authority exclusion")
    if decision.selected_worker_type == "LOCAL_OLLAMA":
        return ("sanitized local prompt", "classification/summarization scope", "sensitivity boundary")
    return ("target surface", "desired outcome", "allowed files or lane", "success criteria")


def build_package_recommendation(decision: WorkerRouteDecision) -> WorkerPackageRecommendation:
    return WorkerPackageRecommendation(
        recommendation_id=f"recommendation_{decision.decision_id}",
        route_decision_ref=decision.decision_id,
        package_type=_package_type_for_decision(decision),
        package_title=f"{decision.selected_worker_type} package for {decision.task_type}",
        target_worker_type=decision.selected_worker_type,
        target_machine=decision.selected_machine,
        context_needed=_context_needed_for_decision(decision),
        context_excluded=COMMON_EXCLUDED_CONTEXT,
        validation_required=("focused validation for the worker lane", "authority scan", "PII/secret scan"),
        expected_return_format=EXPECTED_RETURN_FORMAT,
        operator_card_summary=(
            f"Route to {decision.selected_worker_type} on {decision.selected_machine}: {decision.route_reason}"
        ),
        next_safe_move=decision.next_safe_move,
    )


def build_blockers() -> tuple[WorkerRoutingBlocker, ...]:
    details = {
        "WRONG_WORKER_SELECTED": (
            "A request is routed to a worker that cannot safely own the surface.",
            "This looks like the wrong worker. Pick the worker that owns the actual surface.",
        ),
        "WRONG_MACHINE_SELECTED": (
            "A request is routed to the wrong machine environment.",
            "This belongs on the other machine. Re-route before packaging.",
        ),
        "AUTHORITY_TOO_BROAD": (
            "A route or prompt includes authority beyond the worker lane.",
            "The package is too broad. Strip execution/send/submit authority and keep only the lane-safe work.",
        ),
        "EXTERNAL_ACTION_INCLUDED": (
            "The request includes Gmail/Coupa/browser/send/approval/external action authority.",
            "External action is not part of worker routing. Keep it locked behind governed adapters.",
        ),
        "RAW_PII_IN_PACKAGE": (
            "The package includes raw private identifiers or private bodies.",
            "Use sanitized summaries and metadata-only refs.",
        ),
        "CREDENTIAL_IN_PACKAGE": (
            "The package includes credentials or credential-like material.",
            "Remove credentials and fail closed.",
        ),
        "MISSING_CONTEXT": (
            "The request lacks target surface, desired outcome, or validation criteria.",
            "Ask for the missing context before routing.",
        ),
        "AMBIGUOUS_REQUEST": (
            "The request is too vague to route safely.",
            "Ask whether this is Mac app work, Repo A backend work, scout work, comms, or safety review.",
        ),
        "UNKNOWN_FAIL_CLOSED": (
            "The router cannot classify the request.",
            "Fail closed and ask a clarifying question.",
        ),
    }
    blockers = []
    for blocker_type, (condition, warning) in details.items():
        blockers.append(
            WorkerRoutingBlocker(
                blocker_id=f"worker_routing_blocker_{blocker_type.lower()}",
                blocker_type=blocker_type,
                condition=condition,
                severity="CRITICAL" if blocker_type == "UNKNOWN_FAIL_CLOSED" else "HIGH",
                elioperator_warning=warning,
                fail_closed=True,
                next_safe_move="Return a human-readable routing blocker and do not dispatch a worker.",
            )
        )
    return tuple(blockers)


def _example(summary: str, source_ref: str) -> dict[str, Any]:
    decision = route_request(summary, source_chat_ref=source_ref)
    recommendation = build_package_recommendation(decision)
    active_blockers: tuple[str, ...] = ()
    if decision.selected_worker_type == "UNKNOWN_NEEDS_ROUTING":
        active_blockers = ("AMBIGUOUS_REQUEST", "MISSING_CONTEXT")
    if _contains_any(summary.lower(), EXTERNAL_ACTION_PATTERNS):
        active_blockers = (*active_blockers, "AUTHORITY_TOO_BROAD", "EXTERNAL_ACTION_INCLUDED")
    return {
        "input": summary,
        "route_decision": asdict(decision),
        "package_recommendation": asdict(recommendation),
        "active_blockers": active_blockers,
    }


def build_examples() -> dict[str, Any]:
    swift_summary = "Fix the Mission Control chat UI so cards render inside the chat and the composer is bottom anchored."
    wrong_decision = route_request(swift_summary, source_chat_ref="operator_chat_wrong_worker_swiftui")
    wrong = {
        "input": swift_summary,
        "attempted_worker_type": "PC_CODEX",
        "attempted_machine": "PC_WSL",
        "expected_worker_type": wrong_decision.selected_worker_type,
        "expected_machine": wrong_decision.selected_machine,
        "active_blockers": ("WRONG_WORKER_SELECTED", "WRONG_MACHINE_SELECTED"),
        "elioperator_warning": "This is Mac app work. Route it to Mac Codex, not PC Codex.",
        "next_safe_move": "Prepare a Mac Codex package with SwiftUI scope and no external authority.",
    }
    authority_summary = "Make the Mission Control UI call Gmail and Coupa and send the invoice."
    authority = _example(authority_summary, "operator_chat_authority_too_broad")
    authority["active_blockers"] = ("AUTHORITY_TOO_BROAD", "EXTERNAL_ACTION_INCLUDED")
    authority["elioperator_warning"] = "This UI route includes external send/Coupa authority. Strip that authority and keep only UI/boundary review."

    return {
        "mac_codex_ui": _example(swift_summary, "operator_chat_mac_ui"),
        "mac_codex_apple_app_integration": _example("Add Logic Pro project recognition to the Mac app.", "operator_chat_logic_pro"),
        "mac_codex_mail_boundary": _example("Make Mail send the invoice.", "operator_chat_mail_send_invoice"),
        "pc_codex_backend": _example("Build the chat readback card mirror from router readbacks.", "operator_chat_pc_backend"),
        "pc_codex_package": _example("Package the readback mirror to Mac.", "operator_chat_pc_package"),
        "gemini_agy_audit": _example("Audit whether the chat-first pivot should reuse existing card contracts.", "operator_chat_gemini_audit"),
        "unknown_make_it_better": _example("Make it better.", "operator_chat_unknown_make_it_better"),
        "wrong_worker_blocker": wrong,
        "authority_too_broad_blocker": authority,
    }


def _model_schemas() -> dict[str, Any]:
    return {
        "worker_routing_intelligence": {"required_fields": list(REQUIRED_INTELLIGENCE_FIELDS)},
        "worker_route_decision": {"required_fields": list(REQUIRED_DECISION_FIELDS)},
        "worker_routing_rule": {"required_fields": list(REQUIRED_RULE_FIELDS)},
        "worker_package_recommendation": {"required_fields": list(REQUIRED_RECOMMENDATION_FIELDS)},
        "worker_routing_blocker": {"required_fields": list(REQUIRED_BLOCKER_FIELDS)},
    }


def _all_authority_flags_false(payload: dict[str, Any]) -> bool:
    return not any(payload["authority_boundary"].values())


def _machine_proof(payload: dict[str, Any]) -> dict[str, Any]:
    examples = payload["examples"]
    blocker_types = {
        blocker["blocker_type"]
        for blocker in payload["worker_routing_blockers_by_id"].values()
    }
    return {
        "worker_routing_intelligence_model_present": True,
        "worker_route_decision_model_present": True,
        "worker_routing_rule_model_present": True,
        "worker_package_recommendation_model_present": True,
        "worker_routing_blocker_model_present": True,
        "supported_workers_present": set(WORKER_TYPES).issubset(payload["supported_workers"]),
        "machines_present": set(MACHINES).issubset(payload["machines"]),
        "mac_codex_ui_routes_correctly": examples["mac_codex_ui"]["route_decision"]["selected_worker_type"] == "MAC_CODEX"
        and examples["mac_codex_ui"]["route_decision"]["selected_machine"] == "MAC"
        and examples["mac_codex_ui"]["route_decision"]["task_type"] == "SWIFTUI_APP_UI",
        "apple_app_integration_routes_correctly": examples["mac_codex_apple_app_integration"]["route_decision"]["selected_worker_type"] == "MAC_CODEX"
        and examples["mac_codex_apple_app_integration"]["route_decision"]["task_type"] == "APPLE_APP_INTEGRATION_SCOUT_OR_UI",
        "mac_mail_boundary_blocks_send": "EXTERNAL_ACTION_INCLUDED" in examples["mac_codex_mail_boundary"]["active_blockers"],
        "pc_codex_backend_routes_correctly": examples["pc_codex_backend"]["route_decision"]["selected_worker_type"] == "PC_CODEX"
        and examples["pc_codex_backend"]["route_decision"]["task_type"] == "BACKEND_READMODEL",
        "pc_codex_package_routes_correctly": examples["pc_codex_package"]["route_decision"]["selected_worker_type"] == "PC_CODEX"
        and examples["pc_codex_package"]["route_decision"]["task_type"] == "SHUTTLE_PACKAGE",
        "gemini_agy_routes_correctly": examples["gemini_agy_audit"]["route_decision"]["selected_worker_type"] == "GEMINI_AGY"
        and examples["gemini_agy_audit"]["route_decision"]["task_type"] == "READ_ONLY_AUDIT",
        "unknown_routes_to_clarification": examples["unknown_make_it_better"]["route_decision"]["selected_worker_type"] == "UNKNOWN_NEEDS_ROUTING",
        "wrong_worker_blocker_exists": "WRONG_WORKER_SELECTED" in examples["wrong_worker_blocker"]["active_blockers"],
        "authority_too_broad_blocker_exists": "AUTHORITY_TOO_BROAD" in examples["authority_too_broad_blocker"]["active_blockers"],
        "blockers_present": set(BLOCKER_TYPES).issubset(blocker_types),
        "all_live_authority_flags_false": _all_authority_flags_false(payload),
        "auto_dispatch_performed": False,
        "worker_execution_performed": False,
        "cross_machine_send_performed": False,
        "model_call_performed": False,
        "agent_dispatch_performed": False,
        "workflow_run_performed": False,
        "external_action_performed": False,
        "credentials_or_secrets_included": False,
        "raw_private_bodies_included": False,
        "raw_pii_in_packages": False,
        "network_used": False,
        "mac_sync_import_run": False,
        "mission_control_swift_changed": False,
        "git_push_pull_fetch_run": False,
        "content_hash": None,
    }


def build_worker_routing_intelligence(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    rules = build_routing_rules()
    intelligence = build_intelligence(rules)
    blockers = build_blockers()
    examples = build_examples()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "operator_markdown_mode": "ELIOPERATOR",
        "supported_workers": WORKER_TYPES,
        "machines": MACHINES,
        "confidence_values": CONFIDENCE_VALUES,
        "model_schemas": _model_schemas(),
        "worker_routing_intelligence": asdict(intelligence),
        "worker_routing_rules_by_id": {rule.rule_id: asdict(rule) for rule in rules},
        "examples": examples,
        "worker_routing_blockers_by_id": {
            blocker.blocker_id: asdict(blocker)
            for blocker in blockers
        },
        "relationship_refs": {
            "cross_machine_worker_dispatch_package": "uses the same worker/machine lane vocabulary and package boundary posture",
            "workflow_execution_package_compiler": "consumes route decisions as package target recommendations",
            "agent_execution_packet_compiler_contract": "downstream worker package authority filtering",
            "agent_conversation_handoff_step_packet_contract": "same-chat worker result/readback return shape",
            "conversational_workflow_router_contract": "upstream chat/workflow classification",
            "conversational_workflow_router_intake": "Mac chat request intake source",
            "openclaw_sensitive_policy": "privacy and credential exclusion posture",
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
        "allowed_scope": (
            "deterministic route classification",
            "package recommendation",
            "generated read-model",
            "tests",
            "ELIOPERATOR report",
        ),
    }
    payload["machine_proof"] = _machine_proof(payload)
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_markdown(payload: dict[str, Any]) -> str:
    examples = payload["examples"]
    return "\n".join(
        [
            "# Worker Routing Intelligence v0",
            "",
            "ELIOPERATOR: One chat can ask for work without the operator manually choosing the worker. This read-model chooses the right lane and prepares a package recommendation. It does not dispatch anyone.",
            "",
            "## Routes",
            "",
            "- Mac Codex: Apple/Mac-side app work, SwiftUI, Xcode, screenshots, Mac package import/render, and Apple app integration boundaries.",
            "- PC Codex: Repo A backend, Python, read-models, scripts, tests, router/intake/readback, package compiler, and PC-to-Mac shuttle packages.",
            "- Gemini/Agy: read-only scouting, audit, critique, prompt shaping, and gotcha discovery.",
            "- Guardian: approval, protected evidence, security posture, and sensitive-boundary review.",
            "- Cassandra: communications drafting and operator-facing follow-up language.",
            "- Unknown: asks for clarification instead of guessing.",
            "",
            "## Examples",
            "",
            f"- Mac UI -> `{examples['mac_codex_ui']['route_decision']['selected_worker_type']}` / `{examples['mac_codex_ui']['route_decision']['task_type']}`",
            f"- Apple integration -> `{examples['mac_codex_apple_app_integration']['route_decision']['selected_worker_type']}` / `{examples['mac_codex_apple_app_integration']['route_decision']['task_type']}`",
            f"- PC backend -> `{examples['pc_codex_backend']['route_decision']['selected_worker_type']}` / `{examples['pc_codex_backend']['route_decision']['task_type']}`",
            f"- PC package -> `{examples['pc_codex_package']['route_decision']['selected_worker_type']}` / `{examples['pc_codex_package']['route_decision']['task_type']}`",
            f"- Gemini/Agy -> `{examples['gemini_agy_audit']['route_decision']['selected_worker_type']}` / `{examples['gemini_agy_audit']['route_decision']['task_type']}`",
            f"- Unknown -> `{examples['unknown_make_it_better']['route_decision']['selected_worker_type']}`",
            "",
            "## Blockers",
            "",
            "- Wrong worker or wrong machine fails closed.",
            "- External action language is stripped or blocked.",
            "- Credentials, raw private bodies, and raw PII are excluded.",
            "- Vague requests ask for clarification.",
            "",
            "## Boundary",
            "",
            "No live auto-dispatch, worker execution, cross-machine send, model call, agent dispatch, workflow run, external action, credential handling, raw-body ingestion, Mac sync/import, Swift change, or push was added.",
            "",
            f"Next safe move: {payload['worker_routing_intelligence']['next_safe_move']}",
            "",
        ]
    )


def write_exports(payload: dict[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return json_path, operator_path


def build_summary(payload: dict[str, Any], json_path: Path | None, operator_path: Path | None) -> dict[str, Any]:
    proof = payload["machine_proof"]
    examples = payload["examples"]
    return {
        "schema_version": payload["schema_version"],
        "read_model_id": payload["read_model_id"],
        "contract_status": payload["contract_status"],
        "json_path": str(json_path) if json_path else None,
        "operator_path": str(operator_path) if operator_path else None,
        "routes": {
            key: {
                "worker": value["route_decision"]["selected_worker_type"],
                "machine": value["route_decision"]["selected_machine"],
                "task_type": value["route_decision"]["task_type"],
            }
            for key, value in examples.items()
            if "route_decision" in value
        },
        "mac_codex_ui_routes_correctly": proof["mac_codex_ui_routes_correctly"],
        "pc_codex_backend_routes_correctly": proof["pc_codex_backend_routes_correctly"],
        "pc_codex_package_routes_correctly": proof["pc_codex_package_routes_correctly"],
        "gemini_agy_routes_correctly": proof["gemini_agy_routes_correctly"],
        "unknown_routes_to_clarification": proof["unknown_routes_to_clarification"],
        "all_live_authority_flags_false": proof["all_live_authority_flags_false"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export worker routing intelligence read-model.")
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--format", choices=("summary", "json"), default="json")
    args = parser.parse_args(argv)

    payload = build_worker_routing_intelligence()
    json_path, operator_path = write_exports(payload, args.export_root)
    output = payload if args.format == "json" else build_summary(payload, json_path, operator_path)
    sys.stdout.write(stable_json(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
