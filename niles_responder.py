"""Deterministic Niles front-door responder.

Niles answers identity, status, capability, and music-rig inventory questions
from static/read-model truth. Action-shaped prompts are staged or denied with
explicit no-action language. No model, send, hardware, DAW, OSC, or MIDI path is
called from this module.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any

import niles_rig_kb


MAC_RENDER_HINT = "COMPACT_WITH_DISCLOSURE"


@dataclass(frozen=True)
class NilesFrontdoorResult:
    status: str
    intent_class: str
    allowed_to_reply_directly: bool
    one_line_answer: str = ""
    plain_summary: str = ""
    mac_render_hint: str = MAC_RENDER_HINT
    route_to_staging_reason: str = ""
    machine_proof: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["machine_proof"] = dict(self.machine_proof or {})
        return payload


def _normalize(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def _one_line(text: str, *, word_limit: int = 30) -> str:
    words = " ".join(text.split()).split()
    if len(words) <= word_limit:
        return " ".join(words)
    return " ".join(words[:word_limit]).rstrip(".,;:") + "..."


def _base_machine_proof() -> dict[str, Any]:
    return {
        "niles_frontdoor_responder_invoked": True,
        "text_response_only": True,
        "send_hold_boundary_visible": True,
        "rig_kb_used": False,
        "model_call_performed": False,
        "external_llm_invoked": False,
        "hardware_control_performed": False,
        "osc_message_sent": False,
        "midi_message_sent": False,
        "daw_control_performed": False,
        "obs_control_performed": False,
        "app_launch_performed": False,
        "audio_file_mutation_performed": False,
        "project_file_mutation_performed": False,
        "external_send_performed": False,
        "email_send_performed": False,
        "telegram_send_triggered_by_responder": False,
        "credential_handling_performed": False,
        "secret_value_read_or_printed": False,
    }


def _is_identity_intent(normalized: str) -> bool:
    return normalized in {
        "who are you",
        "who are you?",
        "who is niles",
        "who is niles?",
        "identify yourself",
        "what are you",
    } or normalized.startswith("tell me who you are")


def _is_status_intent(normalized: str) -> bool:
    return any(
        phrase in normalized
        for phrase in (
            "status",
            "are you online",
            "are you live",
            "give me your readback",
            "give me a readback",
        )
    )


def _is_capability_intent(normalized: str) -> bool:
    return any(
        phrase in normalized
        for phrase in (
            "what can you help",
            "what can you do",
            "capabilities",
            "capability",
            "help me with",
            "what are you good at",
        )
    )


def _is_rig_inventory_intent(normalized: str) -> bool:
    return any(
        phrase in normalized
        for phrase in (
            "what gear",
            "gear do you control",
            "gear do i have",
            "what rig",
            "my rig",
            "x32",
            "driverack",
            "drive rack",
            "dl32",
            "push 2",
            "fcb1010",
            "ableton",
            "logic pro",
            "mainstage",
            "obs",
        )
    )


def _is_rig_question_intent(normalized: str) -> bool:
    return normalized.startswith(
        (
            "what gear",
            "what rig",
            "what equipment",
            "which gear",
            "which rig",
            "list my gear",
            "show my gear",
        )
    ) or any(
        phrase in normalized
        for phrase in (
            "gear do you control",
            "gear do i have",
            "my rig inventory",
            "rig inventory",
        )
    )


def _is_action_intent(normalized: str) -> bool:
    action_patterns = (
        r"\b(send|email|reply|text|message)\b",
        r"\b(set|change|turn|raise|lower|mute|unmute|route|patch|arm|record|launch|start|open|fire)\b",
        r"\b(control|connect to|push to|write to|run|execute)\b",
        r"\b(fader|channel|bus|main|mute|osc|midi|logic|ableton|mainstage|obs|x32)\b.*\b(to|on|off|up|down)\b",
    )
    return any(re.search(pattern, normalized) for pattern in action_patterns)


def classify_niles_intent(text: str) -> tuple[str, bool, str]:
    normalized = _normalize(text)
    if not normalized:
        return ("empty", False, "empty_text")
    if _is_identity_intent(normalized):
        return ("identity", True, "")
    if _is_rig_question_intent(normalized):
        return ("rig_inventory", True, "")
    if _is_status_intent(normalized):
        return ("status", True, "")
    if _is_capability_intent(normalized):
        return ("capability", True, "")
    if _is_action_intent(normalized):
        return ("hardware_or_external_action", False, "no_hardware_or_external_action_without_explicit_operator_confirmation")
    if _is_rig_inventory_intent(normalized):
        return ("rig_inventory", True, "")
    return ("unapproved_conversation", False, "conversation_not_in_niles_safe_subset")


def _identity_answer() -> tuple[str, str, dict[str, Any]]:
    one = "I'm Niles, Winship's music, creative-production, and rig-context agent."
    plain = "\n".join(
        [
            one,
            "I can speak as Niles about music planning, setlists, album/session context, and the rig-control knowledge base.",
            "I can describe the X32/OSC starting point and what needs confirmation, but no hardware action runs from this front door.",
            "Winship is the operator; I will refer to him as Winship or you depending on the surface.",
        ]
    )
    return one, plain, _base_machine_proof()


def _capability_answer() -> tuple[str, str, dict[str, Any]]:
    one = "I can help with music planning, safe rig readbacks, and X32 OSC control research."
    plain = "\n".join(
        [
            one,
            "Safe work: setlist planning, album/session notes, source-ref navigation, rig inventory, and control-path research.",
            "Rig knowledge: two X32 Rack units, X32 Edit App, DriveRack PA2, DL32, MIDI controllers, Logic, Ableton, MainStage, TH-U, EBOSuite, OBS, and NDI.",
            "No hardware action, OSC/MIDI message, DAW control, OBS control, file mutation, send, or external action runs without explicit operator confirmation.",
            "Next safe move: use the KB to answer what exists and what control path should be tested in X32 Edit before touching real hardware.",
        ]
    )
    return one, plain, _base_machine_proof() | {"rig_kb_used": True}


def _status_answer() -> tuple[str, str, dict[str, Any]]:
    one = "Niles' safe front door is deterministic: readbacks are available, control remains gated."
    plain = "\n".join(
        [
            one,
            "Music lane scope: creative planning, safe rig readbacks, and control-path research only.",
            "Telegram listener code can read NILES_BOT_TOKEN at runtime, but this build does not require or print the token.",
            "Current safe status: I can answer identity, capability, status, and rig inventory/control-path questions.",
            "Current hold: no hardware action, OSC/MIDI send, DAW/OBS control, external send, money movement, deploy, restart, or service mutation.",
        ]
    )
    return one, plain, _base_machine_proof() | {"rig_kb_used": True}


def _rig_inventory_answer() -> tuple[str, str, dict[str, Any]]:
    one = "Your rig includes two X32 Rack units, X32 Edit, DriveRack PA2, DL32, MIDI controllers, and music software."
    lines = [
        one,
        "",
        *[f"- {line}" for line in niles_rig_kb.device_summary_lines()],
        "",
        *[f"- {line}" for line in niles_rig_kb.x32_control_summary_lines()],
        "",
        "- I will not autonomously control the rig. Any OSC, MIDI, DAW, OBS, or hardware operation needs explicit operator confirmation.",
    ]
    return one, "\n".join(lines), _base_machine_proof() | {"rig_kb_used": True}


def _staging_result(intent_class: str, reason: str) -> NilesFrontdoorResult:
    one = "No rig or external action ran; this needs explicit operator confirmation."
    plain = "\n".join(
        [
            one,
            "I can stage or describe the next safe test plan, but I cannot send OSC/MIDI, control hardware, launch apps, mutate sessions, or send messages from this front door.",
            "SEND_HOLD and the hardware-control hold remain in force.",
        ]
    )
    return NilesFrontdoorResult(
        status="ROUTE_TO_STAGING",
        intent_class=intent_class,
        allowed_to_reply_directly=False,
        one_line_answer=one,
        plain_summary=plain,
        route_to_staging_reason=reason,
        machine_proof=_base_machine_proof(),
    )


def answer_niles_frontdoor(text: str) -> NilesFrontdoorResult:
    intent_class, allowed, reason = classify_niles_intent(text)
    if not allowed:
        return _staging_result(intent_class, reason)
    if intent_class == "identity":
        one, plain, proof = _identity_answer()
    elif intent_class == "status":
        one, plain, proof = _status_answer()
    elif intent_class == "capability":
        one, plain, proof = _capability_answer()
    elif intent_class == "rig_inventory":
        one, plain, proof = _rig_inventory_answer()
    else:
        return _staging_result(intent_class, "conversation_not_in_niles_safe_subset")
    return NilesFrontdoorResult(
        status="ANSWER_READY",
        intent_class=intent_class,
        allowed_to_reply_directly=True,
        one_line_answer=_one_line(one),
        plain_summary=plain,
        machine_proof=proof,
    )
