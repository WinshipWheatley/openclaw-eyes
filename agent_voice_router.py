"""Deterministic agent voice routing for operator-facing OpenClaw responses.

This is contract shaping, not roleplay. It assigns a speaker reference and voice
mode from local workflow context while preserving authority boundaries.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Agent Voice Routing.md")

SCHEMA_VERSION = "agent_voice_routing_v0"
READ_MODEL_ID = "agent_voice_routing_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
CONTRACT_STATUS = "AGENT_VOICE_ROUTING_V0_READY"

SPEAKER_REFS = (
    "openclaw",
    "cassandra",
    "chief",
    "hermes",
    "guardian",
    "niles",
    "clara",
)

VOICE_MODES = (
    "operator_calm",
    "operator_intake",
    "diagnostic",
    "recommendation",
    "safety_gate",
    "client_facing",
    "developer_proof",
)

AUDIENCES = (
    "internal_operator",
    "external_client",
    "developer",
)

OPERATOR_RESPONSE_VOICE_FIELDS = (
    "speaker_ref",
    "voice_mode",
    "audience",
    "headline",
    "plain_summary",
    "next_safe_action",
    "proof_caption",
    "show_machine_details_by_default",
)

GUARDIAN_AUTHORITY_FIELDS = (
    "email_send_allowed",
    "ledger_posting_allowed",
    "ledger_mutation_allowed",
    "browser_access_allowed",
    "browser_automation_allowed",
    "gmail_allowed",
    "gmail_access_allowed",
    "coupa_allowed",
    "coupa_access_allowed",
    "coupa_submit_allowed",
    "portal_submit_allowed",
    "workbook_mutation_allowed",
    "workbook_source_mutation_allowed",
    "excel_automation_allowed",
    "pdf_export_allowed",
    "paid_marking_allowed",
    "payment_marking_allowed",
    "sent",
    "paid",
    "business_action_allowed",
    "external_action_allowed",
)

GUARDIAN_CONTEXT_TERMS = (
    "credential",
    "credentials",
    "password",
    "secret",
    "token",
    "mfa",
    "protected access",
    "access ambiguity",
    "authority requested",
    "send authority",
    "submit authority",
    "ledger authority",
    "mark paid",
)

CHIEF_CONTEXT_TERMS = (
    "check engine",
    "package queue",
    "provider gate",
    "diagnostic",
    "workbench",
    "build status",
    "runbook",
    "route confirmation",
    "route confirmations",
)

HERMES_CONTEXT_TERMS = (
    "architecture",
    "doctrine",
    "lane sequencing",
    "reusable pattern",
    "recommendation",
    "what should we build next",
    "systems coherence",
)

CASSANDRA_CONTEXT_TERMS = (
    "telegram",
    "cassandra",
    "work log",
    "work-log",
    "correspondence",
    "follow up",
    "follow-up",
    "ap reminder",
    "payment reminder",
    "human layer",
)

NILES_CONTEXT_TERMS = (
    "music",
    "art",
    "creative",
    "song",
    "session",
    "album",
    "metadata",
    "art direction",
    "studio",
    "logic pro",
)

CLARA_CONTEXT_TERMS = (
    "external client",
    "client-facing",
    "client facing",
    "proposal email",
    "outreach draft",
    "client-visible",
    "client visible",
)


@dataclass(frozen=True)
class VoiceRoute:
    speaker_ref: str
    voice_mode: str
    audience: str
    routing_reason: str


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def _authority_requested(authority_boundary: Mapping[str, Any] | None) -> bool:
    if not isinstance(authority_boundary, Mapping):
        return False
    return any(authority_boundary.get(field) is True for field in GUARDIAN_AUTHORITY_FIELDS)


def route_agent_voice(
    *,
    workflow_ref: str = "",
    package_status: str = "",
    source_text: str = "",
    source_surface: str = "",
    world: str = "",
    client_ref: str | None = None,
    authority_boundary: Mapping[str, Any] | None = None,
    audience: str = "internal_operator",
    external_client_facing: bool = False,
    blocker: str = "",
) -> VoiceRoute:
    text = " ".join(
        str(item or "")
        for item in (
            workflow_ref,
            package_status,
            source_text,
            source_surface,
            world,
            client_ref,
            blocker,
            audience,
        )
    ).lower()
    requested_audience = "external_client" if external_client_facing or audience == "external_client" else audience

    if _authority_requested(authority_boundary) or _contains_any(text, GUARDIAN_CONTEXT_TERMS):
        return VoiceRoute("guardian", "safety_gate", "internal_operator", "protected authority or access boundary")

    if requested_audience == "external_client" or _contains_any(text, CLARA_CONTEXT_TERMS):
        return VoiceRoute("clara", "client_facing", "external_client", "external client-facing draft copy")

    if package_status == "PROVIDER_GATE_REQUIRED":
        return VoiceRoute("chief", "diagnostic", "internal_operator", "provider gate required")

    if workflow_ref == "diagnostic_package_gate_smoke" or _contains_any(text, CHIEF_CONTEXT_TERMS):
        mode = "diagnostic" if package_status in {"PROVIDER_GATE_REQUIRED", "PERMISSION_REQUIRED", "ARTIFACT_REQUIRED"} or _contains_any(text, ("check engine", "diagnostic", "provider gate")) else "operator_calm"
        return VoiceRoute("chief", mode, "internal_operator", "diagnostic, queue, route, or workbench posture")

    if _contains_any(text, HERMES_CONTEXT_TERMS):
        return VoiceRoute("hermes", "recommendation", "internal_operator", "architecture, doctrine, or systems recommendation")

    if workflow_ref == "st_annes_work_log_event":
        return VoiceRoute("cassandra", "operator_intake", "internal_operator", "work-log intake")

    if workflow_ref == "capital_hilton_proposal_followup" or source_surface in {"telegram", "cassandra"} or _contains_any(text, CASSANDRA_CONTEXT_TERMS):
        return VoiceRoute("cassandra", "operator_calm", "internal_operator", "human-layer coordination or correspondence prep")

    if _contains_any(text, NILES_CONTEXT_TERMS):
        mode = "recommendation" if _contains_any(text, ("recommendation", "art direction")) else "operator_calm"
        return VoiceRoute("niles", mode, "internal_operator", "creative, music, art, or studio context")

    if audience == "developer":
        return VoiceRoute("openclaw", "developer_proof", "developer", "developer proof or implementation status")

    return VoiceRoute("openclaw", "operator_calm", "internal_operator", "neutral cockpit/system orientation")


def route_agent_voice_dict(**kwargs: Any) -> dict[str, str]:
    route = route_agent_voice(**kwargs)
    return {
        "speaker_ref": route.speaker_ref,
        "voice_mode": route.voice_mode,
        "audience": route.audience,
        "voice_routing_reason": route.routing_reason,
    }


def build_contract_read_model(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    examples = [
        {
            "example_id": "st_annes_work_log",
            "source_text": "Mark that I'm at church running sound.",
            "workflow_ref": "st_annes_work_log_event",
            "package_status": "OPERATOR_REVIEW_REQUIRED",
        },
        {
            "example_id": "capital_hilton_proposal_followup",
            "source_text": "Follow up on the Capital Hilton proposal.",
            "workflow_ref": "capital_hilton_proposal_followup",
            "package_status": "OPERATOR_REVIEW_REQUIRED",
        },
        {
            "example_id": "capital_hilton_invoice_operator_assist",
            "source_text": "Submit Capital Hilton invoice.",
            "workflow_ref": "capital_hilton_invoice_operator_assist",
            "package_status": "PROVIDER_GATE_REQUIRED",
        },
        {
            "example_id": "check_engine_warning",
            "source_text": "Check Engine warning",
            "workflow_ref": "diagnostic_package_gate_smoke",
            "package_status": "PACKAGE_STAGED",
        },
        {
            "example_id": "architecture_recommendation",
            "source_text": "What should we build next for reusable lane sequencing?",
            "workflow_ref": "architecture_recommendation",
            "package_status": "OPERATOR_REVIEW_REQUIRED",
        },
        {
            "example_id": "creative_project_session",
            "source_text": "Review the Logic Pro session metadata and art direction.",
            "workflow_ref": "creative_project_session",
            "package_status": "OPERATOR_REVIEW_REQUIRED",
        },
        {
            "example_id": "external_client_draft",
            "source_text": "Prepare a client-facing proposal email draft.",
            "workflow_ref": "capital_hilton_proposal_followup",
            "package_status": "OPERATOR_REVIEW_REQUIRED",
            "external_client_facing": True,
            "audience": "external_client",
        },
        {
            "example_id": "submit_authority_requested",
            "source_text": "Submit Capital Hilton invoice with authority.",
            "workflow_ref": "capital_hilton_invoice_operator_assist",
            "package_status": "OPERATOR_REVIEW_REQUIRED",
            "authority_boundary": {"coupa_submit_allowed": True},
        },
    ]
    routed_examples: list[dict[str, Any]] = []
    for example in examples:
        route = route_agent_voice_dict(
            workflow_ref=str(example.get("workflow_ref") or ""),
            package_status=str(example.get("package_status") or ""),
            source_text=str(example.get("source_text") or ""),
            authority_boundary=example.get("authority_boundary") if isinstance(example.get("authority_boundary"), Mapping) else {},
            audience=str(example.get("audience") or "internal_operator"),
            external_client_facing=bool(example.get("external_client_facing")),
        )
        routed_examples.append({**example, **route})
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "status": CONTRACT_STATUS,
        "purpose": "Deterministic voice-routing contract for operator-facing package responses.",
        "speaker_refs": list(SPEAKER_REFS),
        "voice_modes": list(VOICE_MODES),
        "audiences": list(AUDIENCES),
        "operator_response_voice_fields": list(OPERATOR_RESPONSE_VOICE_FIELDS),
        "routing_priority": [
            "guardian_protected_authority_or_access_boundary",
            "clara_external_client_facing_draft",
            "chief_provider_gate_check_engine_diagnostic_route_status",
            "hermes_architecture_doctrine_recommendation",
            "cassandra_intake_correspondence_human_layer_coordination",
            "niles_creative_music_art_studio",
            "openclaw_neutral_cockpit_fallback",
        ],
        "routed_examples": routed_examples,
        "authority_boundary": {
            "email_send_allowed": False,
            "ledger_posting_allowed": False,
            "browser_access_allowed": False,
            "gmail_allowed": False,
            "coupa_allowed": False,
            "portal_submit_allowed": False,
            "sent": False,
            "paid": False,
        },
        "machine_proof": {
            "deterministic_routing_only": True,
            "roleplay_claimed": False,
            "telegram_connected": False,
            "email_send_performed": False,
            "browser_access_performed": False,
            "coupa_access_performed": False,
            "ledger_mutation_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "paid_marking_performed": False,
            "unsafe_true_grants_absent": True,
        },
    }


def build_operator_wiki(read_model: Mapping[str, Any]) -> str:
    lines = [
        "# Agent Voice Routing",
        "",
        f"Status: `{CONTRACT_STATUS}`",
        "",
        "This contract assigns deterministic speaker references and voice modes for operator-facing package responses. It is machine-contract shaping, not roleplay.",
        "",
        "## Speakers",
        "",
    ]
    lines.extend(f"- `{speaker}`" for speaker in read_model["speaker_refs"])
    lines.extend(
        [
            "",
            "## Routing Priority",
            "",
        ]
    )
    lines.extend(f"- `{item}`" for item in read_model["routing_priority"])
    lines.extend(
        [
            "",
            "## Smoke Mapping",
            "",
        ]
    )
    for example in read_model["routed_examples"]:
        lines.append(
            f"- `{example['example_id']}`: `{example['speaker_ref']}` / `{example['voice_mode']}` / `{example['audience']}`"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- No Telegram live connection.",
            "- No email send.",
            "- No Gmail/browser/Coupa access.",
            "- No workbook mutation or PDF export.",
            "- No ledger mutation.",
            "- No paid or sent marking.",
            "- External client-facing draft copy uses `clara`; internal system names are not for client-visible copy.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_agent_voice_routing(
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_contract_read_model(generated_at=generated_at)
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    read_model_path = export_root / JSON_EXPORT_NAME
    read_model_path.write_text(stable_json(read_model), encoding="utf-8")

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_operator_wiki(read_model), encoding="utf-8")
    return {
        "status": CONTRACT_STATUS,
        "read_model_path": read_model_path.as_posix(),
        "wiki_path": wiki_path.as_posix(),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export Agent Voice Routing V0 contract.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_agent_voice_routing(
        export_root=Path(args.export_root),
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
