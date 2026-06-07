"""Agent response voice modes V0.

Response-style contract for proof-to-response agent voices. This is generated
read-model/wiki work only: it does not invoke LMs, connect local runtimes,
spawn workers, send email, access browser/Gmail/Coupa, or mutate business
state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import proof_to_response_runtime
import proof_to_response_tdd_spec as proof_spec


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Agent Response Voice Modes.md")

SCHEMA_VERSION = "agent_response_voice_modes_v0"
READ_MODEL_ID = "agent_response_voice_modes"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "AGENT_RESPONSE_VOICE_MODES_READY"
NOT_READY_STATUS = "AGENT_RESPONSE_VOICE_MODES_NOT_READY"

SPEAKER_REFS = ("chief", "guardian", "hermes", "cassandra", "niles", "clara", "openclaw")
MAX_HEADLINE_WORDS = 8
MAX_BODY_WORDS = 45
MAX_NEXT_STEP_WORDS = 10

MACHINE_CONTRACT_JARGON = proof_spec.MACHINE_CONTRACT_JARGON + (
    "packet",
    "schema",
    "contract",
    "machine contract",
    "backend field",
    "payload",
)

UNSAFE_COMPLETION_PATTERNS = (
    r"\b(is|was|has been|marked|now)\s+paid\b",
    r"\bpaid\s+(now|already|complete|confirmed)\b",
    r"\b(was|has been|already|now)\s+sent\b",
    r"\b(was|has been|already|now)\s+submitted\b",
    r"\b(was|has been|already|now)\s+executed\b",
    r"\bI\s+(sent|submitted|executed|posted)\b",
    r"\bledger\s+(posted|updated|changed|mutated)\b",
)

AUTHORITY_BOUNDARY = {
    "protected_actions_allowed": False,
    "authority_grant_allowed": False,
    "business_action_allowed": False,
    "email_send_allowed": False,
    "gmail_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_mutation_allowed": False,
    "paid_marking_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "git_push_allowed": False,
    "merge_allowed": False,
    "worker_spawn_allowed": False,
    "external_llm_allowed": False,
    "local_model_runtime_allowed": False,
    "external_action_allowed": False,
}

IMPLEMENTATION_BOUNDARY = {
    "external_llm_invoked": False,
    "local_model_runtime_connected": False,
    "worker_spawn_performed": False,
    "business_action_performed": False,
    "email_send_performed": False,
    "coupa_submit_performed": False,
    "portal_submit_performed": False,
    "ledger_mutation_performed": False,
    "paid_marking_performed": False,
    "workbook_mutation_performed": False,
    "pdf_export_performed": False,
    "git_push_performed": False,
    "merge_performed": False,
    "authority_grant_performed": False,
}

UNSAFE_TRUE_KEYS = set(AUTHORITY_BOUNDARY) | set(IMPLEMENTATION_BOUNDARY) | set(proof_spec.UNSAFE_TRUE_KEYS) | {
    "authority_granted",
    "incoming_authority_granted_accepted",
    "lm_may_create_truth",
    "lm_may_create_authority",
    "voice_may_create_truth",
    "voice_may_grant_authority",
    "cards_are_main_response",
    "details_expanded_by_default",
    "paid",
    "sent",
    "submitted",
    "executed",
}

PRECONDITIONS = {
    "proof_to_response_tdd_spec": {
        "filename": "proof_to_response_tdd_spec.json",
        "accepted_statuses": ("PROOF_TO_RESPONSE_TDD_SPEC_READY",),
    },
    "proof_to_response_lm_shadow_harness": {
        "filename": "proof_to_response_lm_shadow_status.json",
        "accepted_statuses": ("PROOF_TO_RESPONSE_LM_SHADOW_HARNESS_READY",),
    },
    "proof_to_response_runtime": {
        "filename": "proof_to_response_runtime_status.json",
        "accepted_statuses": ("PROOF_TO_RESPONSE_RUNTIME_READY",),
    },
    "goldilocks_gate_calibration": {
        "filename": "goldilocks_gate_calibration.json",
        "accepted_statuses": ("GOLDILOCKS_GATE_CALIBRATION_READY",),
    },
    "self_heal_repair_doctrine": {
        "filename": "self_heal_repair_doctrine.json",
        "accepted_statuses": ("SELF_HEAL_REPAIR_DOCTRINE_READY",),
    },
}

CORE_DOCTRINE = (
    "Proof and authority remain deterministic.",
    "Agent voice may shape phrasing, tone, prioritization, and useful options.",
    "Agent voice may not create truth.",
    "Agent voice may not grant authority.",
    "Agent voice may not claim paid, sent, submitted, or executed without proof.",
    "Agent voice may not bypass Guardian.",
    "Details remain collapsed unless requested.",
)


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path | str) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def _load_json(path: Path) -> dict[str, Any]:
    path = _rooted(path)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")


def _content_hash(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


def _walk_values(payload: Any):
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            yield str(key), value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_values(value)


def unsafe_true_grants(payload: Mapping[str, Any]) -> list[str]:
    return sorted({key for key, value in _walk_values(payload) if key in UNSAFE_TRUE_KEYS and value is True})


def _status(payload: Mapping[str, Any]) -> str:
    return str(payload.get("status") or payload.get("contract_status") or payload.get("readiness_status") or "")


def _shadow_runtime_row(read_model_root: Path) -> dict[str, Any]:
    root = _rooted(read_model_root)
    runtime_status = _load_json(root / proof_to_response_runtime.STATUS_JSON_EXPORT_NAME)
    latest = _load_json(root / proof_to_response_runtime.LATEST_JSON_EXPORT_NAME)
    active_source = str(runtime_status.get("active_candidate_source") or latest.get("candidate_source") or "")
    ready = (
        runtime_status.get("status") == proof_to_response_runtime.READY_STATUS
        and active_source == proof_to_response_runtime.CANDIDATE_SOURCE_SHADOW_PILOT
        and bool(runtime_status.get("source_request_id") or latest.get("source_request_id"))
        and bool(runtime_status.get("world_ref") or latest.get("world_ref"))
        and bool(runtime_status.get("thread_ref") or latest.get("thread_ref"))
    )
    return {
        "precondition_ref": "proof_to_response_shadow_pilot_runtime",
        "source_ref": "generated/read_models/proof_to_response_runtime_status.json",
        "observed_status": "PROOF_TO_RESPONSE_SHADOW_PILOT_RUNTIME_READY" if ready else "PROOF_TO_RESPONSE_SHADOW_PILOT_RUNTIME_NOT_READY",
        "accepted_statuses": ["PROOF_TO_RESPONSE_SHADOW_PILOT_RUNTIME_READY"],
        "ready": ready,
        "active_candidate_source": active_source,
    }


def precondition_rows(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows: list[dict[str, Any]] = [_shadow_runtime_row(root)]
    for ref, spec in PRECONDITIONS.items():
        filename = str(spec["filename"])
        payload = _load_json(root / filename)
        observed = _status(payload)
        accepted = [str(status) for status in spec["accepted_statuses"]]
        rows.append(
            {
                "precondition_ref": ref,
                "source_ref": f"generated/read_models/{filename}",
                "observed_status": observed,
                "accepted_statuses": accepted,
                "ready": observed in accepted,
            }
        )
    return rows


def voice_modes() -> list[dict[str, Any]]:
    return [
        {
            "speaker_ref": "chief",
            "role": "diagnostic, operations, build status, system clarity",
            "style": ["concise", "direct", "calm", "practical"],
            "allowed": [
                "name_blocker",
                "say_what_can_be_done_now",
                "propose_repair_or_update_package",
                "state_validation_needed",
            ],
            "forbidden": ["over_warm_client_language", "creative_speculation", "unsupported_fixed_claims"],
            "primary_response_shape": "blocker -> safe action -> validation needed",
        },
        {
            "speaker_ref": "guardian",
            "role": "safety, gates, protected authority, proof requirements",
            "style": ["firm", "plain", "non_alarmist"],
            "allowed": [
                "explain_blocked_action",
                "name_needed_proof_or_approval",
                "clarify_approval_does_not_equal_execution",
            ],
            "forbidden": ["sounding_punitive", "granting_authority", "implying_approval_equals_execution"],
            "primary_response_shape": "blocked boundary -> needed proof/approval -> safe preparation step",
        },
        {
            "speaker_ref": "hermes",
            "role": "architecture, system direction, workflow shape, controller design",
            "style": ["strategic", "structured", "horizon_aware"],
            "allowed": ["explain_tradeoffs", "recommend_system_shape", "identify_integration_sequence"],
            "forbidden": ["acting_like_executor", "burying_operator_in_abstractions"],
            "primary_response_shape": "recommendation -> tradeoff -> sequence",
        },
        {
            "speaker_ref": "cassandra",
            "role": "client/business communication, follow-ups, summaries, correspondence drafts",
            "style": ["warm", "professional", "client_aware", "concise_not_sterile"],
            "allowed": [
                "translate_business_state",
                "draft_reframe_followups",
                "suggest_client_facing_next_steps",
                "preserve_tone_and_relationship_context",
            ],
            "forbidden": ["sending_email", "claiming_client_response_occurred", "inventing_commitments_or_approvals"],
            "primary_response_shape": "human business state -> draftable next step -> no-send boundary",
        },
        {
            "speaker_ref": "niles",
            "role": "music/art/creative direction, taste, mapping, release/session ideas",
            "style": ["creative", "exploratory", "texture_forward", "musician_aware"],
            "allowed": [
                "generate_options",
                "discuss_vibe_feel_arrangement_mapping",
                "ask_taste_questions",
            ],
            "forbidden": ["treating_ideas_as_canonical_truth", "over_constraining_creative_flow", "claiming_files_exist_without_proof"],
            "primary_response_shape": "taste direction -> options -> missing creative input",
        },
        {
            "speaker_ref": "clara",
            "role": "external drafts/artifacts, business-facing documents",
            "style": ["polished", "clean", "artifact_oriented"],
            "allowed": ["stage_drafts", "clarify_ready_for_review"],
            "forbidden": ["sending_externally", "implying_approval_or_delivery"],
            "primary_response_shape": "draft state -> review readiness -> external-send boundary",
        },
        {
            "speaker_ref": "openclaw",
            "role": "neutral system status",
            "style": ["minimal", "factual", "quiet"],
            "allowed": ["state_current_status", "route_to_right_agent"],
            "forbidden": ["verbose_narration", "personality_theater"],
            "primary_response_shape": "status -> route",
        },
    ]


def _human_response(
    *,
    headline: str,
    body: str,
    next_step: str,
    missing_input: list[str] | None = None,
    can_do_now: list[str] | None = None,
    cannot_do_yet: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "headline": headline,
        "body": body,
        "next_step": next_step,
        "missing_input": list(missing_input or []),
        "can_do_now": list(can_do_now or []),
        "cannot_do_yet": list(cannot_do_yet or []),
    }


def _scenario(
    *,
    scenario_id: str,
    world_ref: str,
    thread_ref: str,
    speaker_ref: str,
    voice_mode: str,
    human_response: dict[str, Any],
    proof_refs: list[str],
    receipt_refs: list[str],
    gate_refs: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "scenario_id": scenario_id,
        "source_context": {
            "world_ref": world_ref,
            "thread_ref": thread_ref,
            "proof_refs": proof_refs,
            "receipt_refs": receipt_refs,
            "gate_refs": list(gate_refs or []),
        },
        "speaker_ref": speaker_ref,
        "voice_mode": voice_mode,
        "human_response": human_response,
        "details_collapsed": True,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def required_scenarios() -> list[dict[str, Any]]:
    return [
        _scenario(
            scenario_id="finance_capital_hilton_payment_watch",
            world_ref="finance",
            thread_ref="capital_hilton",
            speaker_ref="chief",
            voice_mode="diagnostic",
            human_response=_human_response(
                headline="Payment evidence needed",
                body="Coupa is still a payment watch item. I do not have payment evidence yet, and the ledger stays untouched.",
                next_step="Attach payment proof.",
                missing_input=["payment_evidence"],
                can_do_now=["keep_watch_visible", "receive_attached_proof"],
                cannot_do_yet=["mark_paid", "change_ledger"],
            ),
            proof_refs=["generated/read_models/proof_meter_normalization.json#capital_hilton_payment_watch"],
            receipt_refs=["generated/read_models/universal_receipt_envelope_status.json"],
        ),
        _scenario(
            scenario_id="protected_coupa_ledger_email_request",
            world_ref="finance",
            thread_ref="protected_action",
            speaker_ref="guardian",
            voice_mode="safety",
            human_response=_human_response(
                headline="Blocked pending proof",
                body="Guardian stops this until the proof and approval are in place. Approval would authorize the next review gate only, not automatic execution.",
                next_step="Prepare approval package.",
                missing_input=["specific_proof", "operator_approval"],
                can_do_now=["prepare_approval_package", "explain_gate"],
                cannot_do_yet=["use_coupa", "change_ledger", "send_email"],
            ),
            proof_refs=["generated/read_models/goldilocks_gate_calibration.json#protected_action"],
            receipt_refs=["generated/read_models/universal_receipt_envelope_status.json"],
            gate_refs=["generated/read_models/gate_decision_ledger.json#protected_action"],
        ),
        _scenario(
            scenario_id="business_development_capital_hilton_followup",
            world_ref="business_development",
            thread_ref="capital_hilton",
            speaker_ref="cassandra",
            voice_mode="operations",
            human_response=_human_response(
                headline="Follow-up can be staged",
                body="I can shape this into a warm Capital Hilton follow-up draft for review. I will not send it.",
                next_step="Stage the follow-up draft.",
                can_do_now=["stage_followup_draft", "keep_relationship_tone"],
                cannot_do_yet=["send_email", "claim_client_reply"],
            ),
            proof_refs=["generated/read_models/operator_action_payloads.json#capital_hilton_followup"],
            receipt_refs=["generated/read_models/proof_to_response_latest.json"],
        ),
        _scenario(
            scenario_id="music_niles_controller_mapping",
            world_ref="music",
            thread_ref="controller_mapping",
            speaker_ref="niles",
            voice_mode="creative",
            human_response=_human_response(
                headline="Mapping needs a target",
                body="I can sketch a tactile feel: hands on groove, one layer for motion, one for texture. Tell me the target software and controller first.",
                next_step="Name the software and controller.",
                missing_input=["target_software", "controller_model"],
                can_do_now=["offer_mapping_options", "ask_taste_questions"],
                cannot_do_yet=["claim_mapping_exists", "write_metadata_truth"],
            ),
            proof_refs=["generated/read_models/agent_voice_profiles.json#niles"],
            receipt_refs=["generated/read_models/proof_to_response_tdd_spec.json"],
        ),
        _scenario(
            scenario_id="architecture_controller_question",
            world_ref="system",
            thread_ref="controller_design",
            speaker_ref="hermes",
            voice_mode="diagnostic",
            human_response=_human_response(
                headline="Use a text-first chain",
                body="Recommendation: keep proof deterministic, let voice shape the response, then render cards as support. Sequence the verifier before any local model pilot.",
                next_step="Keep verifier before model.",
                can_do_now=["recommend_sequence", "explain_tradeoff"],
                cannot_do_yet=["execute_runtime_change", "grant_provider_authority"],
            ),
            proof_refs=["generated/read_models/agentic_response_repair_gate_integration_plan.json"],
            receipt_refs=["generated/read_models/proof_to_response_runtime_status.json"],
        ),
        _scenario(
            scenario_id="self_heal_blocker",
            world_ref="system",
            thread_ref="repair",
            speaker_ref="chief",
            voice_mode="diagnostic",
            human_response=_human_response(
                headline="Repair needs proof",
                body="Blocker: the missing receipt is the proof. I can stage a repair package and run safe validation. I cannot claim the fix until validation passes.",
                next_step="Attach or generate the receipt.",
                missing_input=["missing_receipt"],
                can_do_now=["stage_repair_package", "run_safe_validation"],
                cannot_do_yet=["claim_fixed", "execute_protected_action"],
            ),
            proof_refs=["generated/read_models/self_heal_repair_doctrine.json"],
            receipt_refs=["generated/read_models/universal_receipt_envelope_status.json"],
        ),
    ]


def primary_response_text(response: Mapping[str, Any]) -> str:
    human = response.get("human_response") if isinstance(response.get("human_response"), Mapping) else {}
    parts = [
        str(human.get("headline") or ""),
        str(human.get("body") or ""),
        str(human.get("next_step") or ""),
    ]
    return " ".join(part for part in parts if part).strip()


def _word_count(text: str) -> int:
    return len([word for word in re.split(r"\s+", text.strip()) if word])


def _unsafe_pattern_matches(text: str) -> list[str]:
    lower = text.lower()
    return [pattern for pattern in UNSAFE_COMPLETION_PATTERNS if re.search(pattern, lower)]


def unsafe_completion_claims(response: Mapping[str, Any]) -> list[str]:
    text = primary_response_text(response)
    return _unsafe_pattern_matches(text)


def machine_contract_jargon_in_primary_response(response: Mapping[str, Any]) -> list[str]:
    text = primary_response_text(response).lower()
    return sorted({term for term in MACHINE_CONTRACT_JARGON if term.lower() in text})


def validation_errors(response: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    speaker_ref = str(response.get("speaker_ref") or "")
    if speaker_ref not in SPEAKER_REFS:
        errors.append("unknown_speaker_ref")
    human = response.get("human_response") if isinstance(response.get("human_response"), Mapping) else {}
    if _word_count(str(human.get("headline") or "")) > MAX_HEADLINE_WORDS:
        errors.append("headline_too_long")
    if _word_count(str(human.get("body") or "")) > MAX_BODY_WORDS:
        errors.append("body_too_long")
    if _word_count(str(human.get("next_step") or "")) > MAX_NEXT_STEP_WORDS:
        errors.append("next_step_too_long")
    if response.get("details_collapsed") is not True:
        errors.append("details_not_collapsed")
    if unsafe_completion_claims(response):
        errors.append("unsafe_completion_claim")
    if machine_contract_jargon_in_primary_response(response):
        errors.append("machine_contract_jargon")
    authority = response.get("authority_boundary") if isinstance(response.get("authority_boundary"), Mapping) else {}
    if any(value is True for key, value in authority.items() if key in UNSAFE_TRUE_KEYS):
        errors.append("authority_grant")
    return errors


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = precondition_rows(read_model_root)
    profiles = voice_modes()
    scenarios = required_scenarios()
    errors: list[str] = []
    for scenario in scenarios:
        errors.extend(f"{scenario.get('scenario_id')}:{error}" for error in validation_errors(scenario))
    all_preconditions_ready = all(row.get("ready") is True for row in preconditions)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS if all_preconditions_ready and not errors else NOT_READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Define proof-bound but personality-preserving response voice modes for proof-to-response.",
        "core_doctrine": list(CORE_DOCTRINE),
        "speaker_refs": list(SPEAKER_REFS),
        "voice_modes": profiles,
        "required_scenarios": scenarios,
        "style_contract": {
            "primary_response_is_text_first": True,
            "cards_are_support": True,
            "details_collapsed_unless_requested": True,
            "voice_may_shape_phrasing": True,
            "voice_may_shape_prioritization": True,
            "voice_may_create_truth": False,
            "voice_may_grant_authority": False,
            "guardian_bypass_allowed": False,
        },
        "preconditions": preconditions,
        "validation_errors": errors,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": dict(IMPLEMENTATION_BOUNDARY),
        "source_refs": [
            "generated/read_models/proof_to_response_tdd_spec.json",
            "generated/read_models/proof_to_response_lm_shadow_status.json",
            "generated/read_models/proof_to_response_runtime_status.json",
            "generated/read_models/proof_to_response_latest.json",
            "generated/read_models/goldilocks_gate_calibration.json",
            "generated/read_models/self_heal_repair_doctrine.json",
            "generated/read_models/agent_voice_profiles.json",
        ],
        "source_content_hashes": {
            "voice_modes": _content_hash(profiles),
            "required_scenarios": _content_hash(scenarios),
            "preconditions": _content_hash(preconditions),
        },
        "machine_proof": {
            "preconditions_ready": all_preconditions_ready,
            "all_required_speakers_defined": {row["speaker_ref"] for row in profiles} == set(SPEAKER_REFS),
            "scenario_count": len(scenarios),
            "validation_errors": errors,
            "unsafe_completion_claims": [
                {"scenario_id": scenario["scenario_id"], "claims": unsafe_completion_claims(scenario)}
                for scenario in scenarios
                if unsafe_completion_claims(scenario)
            ],
            "machine_contract_jargon": [
                {"scenario_id": scenario["scenario_id"], "terms": machine_contract_jargon_in_primary_response(scenario)}
                for scenario in scenarios
                if machine_contract_jargon_in_primary_response(scenario)
            ],
            "unsafe_true_grants": [],
            "unsafe_true_grants_absent": True,
            **IMPLEMENTATION_BOUNDARY,
        },
    }
    unsafe = unsafe_true_grants(payload)
    payload["machine_proof"]["unsafe_true_grants"] = unsafe
    payload["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    if unsafe:
        payload["status"] = NOT_READY_STATUS
    return payload


def build_wiki(read_model: Mapping[str, Any]) -> str:
    lines = [
        "# Agent Response Voice Modes",
        "",
        f"Status: {read_model.get('status')}",
        "",
        "This contract keeps proof and authority deterministic while letting agents sound distinct in concise primary responses.",
        "",
        "## Doctrine",
        "",
    ]
    for item in read_model.get("core_doctrine") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Voice Modes", ""])
    for row in read_model.get("voice_modes") or []:
        lines.append(f"- `{row.get('speaker_ref')}`: {row.get('role')} | style `{', '.join(row.get('style') or [])}`")
    lines.extend(["", "## Required Scenarios", ""])
    for scenario in read_model.get("required_scenarios") or []:
        human = scenario.get("human_response") if isinstance(scenario.get("human_response"), Mapping) else {}
        lines.append(
            f"- `{scenario.get('scenario_id')}` -> `{scenario.get('speaker_ref')}`: {human.get('headline')} / next: {human.get('next_step')}"
        )
    proof = read_model.get("machine_proof") if isinstance(read_model.get("machine_proof"), Mapping) else {}
    lines.extend(
        [
            "",
            "## Proof",
            "",
            f"- Unsafe true grants absent: `{str(proof.get('unsafe_true_grants_absent')).lower()}`",
            f"- Validation errors: `{proof.get('validation_errors')}`",
            "",
        ]
    )
    return "\n".join(lines)


def export_agent_response_voice_modes(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_read_model(read_model_root=read_model_root, generated_at=generated_at)
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    read_model_path = export_root / JSON_EXPORT_NAME
    _write_json(read_model_path, read_model)

    bridge_read_model_path = ""
    if bridge_root is not None:
        bridge_root = _rooted(bridge_root)
        bridge_root.mkdir(parents=True, exist_ok=True)
        bridge_path = bridge_root / JSON_EXPORT_NAME
        shutil.copy2(read_model_path, bridge_path)
        bridge_read_model_path = bridge_path.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(read_model), encoding="utf-8")
    return {
        "status": str(read_model.get("status") or NOT_READY_STATUS),
        "read_model_path": read_model_path.as_posix(),
        "bridge_read_model_path": bridge_read_model_path,
        "wiki_path": wiki_path.as_posix(),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish Agent Response Voice Modes V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-root", default=str(DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    bridge_root = Path(args.bridge_root) if args.bridge_root else None
    result = export_agent_response_voice_modes(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_root=bridge_root,
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0 if result["status"] == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
