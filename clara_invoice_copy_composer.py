"""Bounded local-model compose seam for Clara invoice copy.

The model may propose subject/body text from an immutable fact packet. It cannot
change invoice truth, transaction state, authority, attachments, or delivery.
Every candidate is checked against the same Clara voice and workflow closure
contract used by the deterministic draft builder before it can be selected.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from agent_voice_profiles import (
    immutable_persona_core_for_speaker,
    persona_fidelity_note_for_speaker,
    require_clara_copy_conformance,
)
from packet_dankness_critic import score_packet_dankness


COMPOSE_SCHEMA_VERSION = "clara_invoice_copy_compose_v1"
TASTE_CONSUMER_ID = "clara_invoice_copy_taste_pass"
DEFAULT_ATTEMPTS = 3
MAX_BODY_WORDS = 140

_MACHINE_TERMS = (
    "workflow milestone",
    "milestone_ref",
    "packet",
    "receipt id",
    "receipt rail",
    "receipt_ref",
    "validation receipt",
    "proof receipt",
    "source receipt",
    "send_hold",
    "backend",
    "immutable envelope",
    "approval gate",
    "artifact hash",
    "operator approval",
    "validated invoice",
)
_UNPROVEN_ACTION_TERMS = (
    "i sent",
    "we sent",
    "has been sent",
    "was sent",
    "has been delivered",
    "was delivered",
    "has been submitted",
)
_CLIENT_COPY_LEAK_PATTERNS = (
    ("markdown_marker", re.compile(r"(?:\*\*|```|^\s*[-*]\s+)", re.MULTILINE)),
    ("citation_label", re.compile(r"\bcitations?\s*:", re.IGNORECASE)),
    ("attachment_metadata", re.compile(r"\[\s*attachment\s*:", re.IGNORECASE)),
    ("hash_metadata", re.compile(r"\b(?:sha-?256|[0-9a-f]{32,})\b", re.IGNORECASE)),
    ("source_path", re.compile(r"(?:operator/|generated/|/mnt/|\.json\b|\.py#)", re.IGNORECASE)),
)


class ClaraCopyComposeError(ValueError):
    """Raised with critic telemetry when no model take is selectable."""

    def __init__(self, result: Mapping[str, Any]) -> None:
        self.result = dict(result)
        super().__init__("No Clara model candidate passed the immutable copy contract")


def _stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _default_generator(prompt: str) -> Mapping[str, Any]:
    from adaptive_model_call import adaptive_ollama_text

    result = adaptive_ollama_text(
        prompt,
        timeout=90,
        task_class="cassandra_user_reply",
        lane="cassandra_user_reply",
        attempts=1,
        think=False,
        num_predict=320,
        options={"temperature": 0.45, "top_p": 0.85},
        keep_alive="10m",
        return_metadata=True,
        retry=True,
    )
    return dict(result) if isinstance(result, Mapping) else {"text": str(result or "")}


def _candidate_from_text(raw: str) -> dict[str, str]:
    text = re.sub(r"<think>.*?</think>", "", str(raw or ""), flags=re.DOTALL | re.IGNORECASE).strip()
    fenced = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE).strip()
    decoder = json.JSONDecoder()
    decoded_candidates: list[Mapping[str, Any]] = []
    for match in re.finditer(r"\{", fenced):
        try:
            payload, _end = decoder.raw_decode(fenced[match.start() :])
            if isinstance(payload, Mapping):
                decoded_candidates.append(payload)
        except (json.JSONDecodeError, TypeError):
            continue
    for payload in reversed(decoded_candidates):
        if payload.get("subject") or payload.get("body"):
            return {
                "subject": str(payload.get("subject") or "").strip(),
                "body": str(payload.get("body") or "").strip(),
            }
    match = re.search(
        r"(?:^|\n)SUBJECT:\s*(?P<subject>[^\n]+)\s*\nBODY:\s*(?P<body>.+)$",
        fenced,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if match:
        return {
            "subject": match.group("subject").strip(),
            "body": match.group("body").strip(),
        }
    loose = re.search(
        r"(?:^|\n)\*{0,2}Subject\*{0,2}:\s*(?P<subject>[^\n]+)\s*\n+(?:\*{0,2}Body\*{0,2}:\s*)?(?P<body>.+)$",
        fenced,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if loose:
        return {
            "subject": loose.group("subject").strip(),
            "body": loose.group("body").strip(),
        }
    return {"subject": "", "body": ""}


def _candidate_violations(
    candidate: Mapping[str, Any],
    *,
    contract: Mapping[str, Any],
) -> tuple[list[str], dict[str, Any] | None]:
    subject = str(candidate.get("subject") or "").strip()
    body = str(candidate.get("body") or "").strip()
    violations: list[str] = []
    if not subject:
        violations.append("missing_subject")
    if not body:
        violations.append("missing_body")
        return violations, None

    required_subject_atoms = tuple(str(item) for item in contract.get("required_subject_atoms", ()) if str(item))
    required_body_atoms = tuple(str(item) for item in contract.get("required_body_atoms", ()) if str(item))
    exactly_once_body_atoms = tuple(
        str(item) for item in contract.get("exactly_once_body_atoms", ()) if str(item)
    )
    required_any_groups = tuple(
        tuple(str(item) for item in group if str(item))
        for group in contract.get("required_any_body_atom_groups", ())
        if isinstance(group, (list, tuple))
    )
    forbidden_claims = tuple(str(item) for item in contract.get("forbidden_claims", ()) if str(item))
    for atom in required_subject_atoms:
        if atom.casefold() not in subject.casefold():
            violations.append(f"missing_subject_atom:{atom}")
    for atom in required_body_atoms:
        if body.count(atom) < 1:
            violations.append(f"missing_body_atom:{atom}")
    for atom in exactly_once_body_atoms:
        if body.count(atom) != 1:
            violations.append(f"exact_body_atom_count:{atom}:{body.count(atom)}")
    for group in required_any_groups:
        if group and not any(atom.casefold() in body.casefold() for atom in group):
            violations.append("missing_body_atom_group:" + "|".join(group))
    lowered = body.casefold()
    for phrase in (*_MACHINE_TERMS, *_UNPROVEN_ACTION_TERMS, *forbidden_claims):
        if phrase.casefold() in lowered:
            violations.append(f"forbidden_claim:{phrase}")
    if len(body.split()) > MAX_BODY_WORDS:
        violations.append(f"body_too_long:{len(body.split())}")
    for code, pattern in _CLIENT_COPY_LEAK_PATTERNS:
        if pattern.search(subject) or pattern.search(body):
            violations.append(f"client_copy_leak:{code}")

    conformance: dict[str, Any] | None = None
    try:
        conformance = require_clara_copy_conformance(
            body,
            workflow_ref=str(contract.get("workflow_ref") or ""),
            client_ref=str(contract.get("client_ref") or ""),
        )
    except Exception as exc:
        result = getattr(exc, "result", None)
        conformance = dict(result) if isinstance(result, Mapping) else None
        if conformance:
            for item in conformance.get("violations", ()):
                if isinstance(item, Mapping):
                    violations.append(f"voice:{item.get('code')}:{item.get('detail')}")
        else:
            violations.append(f"voice_conformance_error:{type(exc).__name__}")
    return violations, conformance


def _apply_structural_wrapper(
    candidate: Mapping[str, Any],
    *,
    contract: Mapping[str, Any],
) -> dict[str, str]:
    """Apply the canonical signoff outside model-authored prose."""

    subject = str(candidate.get("subject") or "").strip()
    body = str(candidate.get("body") or "").strip()
    canonical_subject = str(contract.get("canonical_subject") or "").strip()
    if canonical_subject:
        subject = canonical_subject
    signoff = str(contract.get("canonical_signoff") or "").strip()
    if not body or not signoff:
        return {"subject": subject, "body": body}
    lines = body.splitlines()
    for index, line in enumerate(lines):
        if re.match(
            r"^(best|regards|warmly|sincerely|thanks|thank you)[,!]?\s*$",
            line.strip(),
            flags=re.IGNORECASE,
        ):
            lines = lines[:index]
            break
    body = "\n".join(lines).rstrip() + "\n\n" + signoff
    subject = subject.strip("* _\t")
    return {"subject": subject, "body": body}


def _taste_score(
    candidate: Mapping[str, Any],
    *,
    contract: Mapping[str, Any],
    violations: list[str],
) -> dict[str, float]:
    body = str(candidate.get("body") or "")
    greeting = str(contract.get("greeting") or "")
    required = tuple(str(item) for item in contract.get("required_body_atoms", ()) if str(item))
    exact = tuple(str(item) for item in contract.get("exactly_once_body_atoms", ()) if str(item))
    required_any_groups = tuple(
        tuple(str(item) for item in group if str(item))
        for group in contract.get("required_any_body_atom_groups", ())
        if isinstance(group, (list, tuple))
    )
    groups_present = all(
        not group or any(atom.casefold() in body.casefold() for atom in group)
        for group in required_any_groups
    )
    signoff = str(contract.get("canonical_signoff") or "").strip()
    persona_fidelity_failed = any(
        "voice:persona_fidelity_anti_pattern:" in item for item in violations
    )
    loop_closure_present = bool(
        exact
        and all(body.count(item) == 1 for item in exact)
        and not persona_fidelity_failed
    )
    client_surface_clean = bool(
        signoff
        and body.count(signoff) == 1
        and body.count("Clara Reid") == 1
        and not any(item.startswith("client_copy_leak:") for item in violations)
        and not any(item.startswith("forbidden_claim:") for item in violations)
    )
    dimensions = {
        "voice": 1.0 if not any(item.startswith("voice:") for item in violations) else 0.0,
        "truth": 1.0 if required and all(body.count(item) >= 1 for item in required) and all(body.count(item) == 1 for item in exact) and groups_present else 0.0,
        "human": 1.0 if greeting and body.startswith(greeting) and not any(term in body.casefold() for term in _MACHINE_TERMS) else 0.0,
        "warmth": 1.0 if loop_closure_present else 0.0,
        "persona_fidelity": 1.0 if not persona_fidelity_failed else 0.0,
        "concise": 1.0 if 25 <= len(body.split()) <= MAX_BODY_WORDS else 0.5 if len(body.split()) <= MAX_BODY_WORDS else 0.0,
        "action_integrity": 1.0 if not any(term in body.casefold() for term in _UNPROVEN_ACTION_TERMS) else 0.0,
        "non_repetitive": 1.0 if all(body.count(item) == 1 for item in required) else 0.5,
        "client_surface_clean": 1.0 if client_surface_clean else 0.0,
    }
    dimensions["overall"] = round(sum(dimensions.values()) / len(dimensions), 4)
    return dimensions


def _prompt_for_attempt(
    *,
    raw_operator_ask: str,
    packet_aid: Mapping[str, Any],
    contract: Mapping[str, Any],
    prior_rejections: tuple[str, ...],
) -> str:
    persona_core = immutable_persona_core_for_speaker("clara")
    persona_fidelity = persona_fidelity_note_for_speaker("clara")
    persona = {
        "identity": persona_core["identity"],
        "prompt_descriptor": persona_core["prompt_descriptor"],
        "style_traits": persona_core["style_traits"],
        "copy_rules": persona_core["copy_rules"],
        "guardrails": persona_core["guardrails"],
        "persona_fidelity": persona_fidelity,
    }
    model_packet = {
        "facts": [
            {
                "topic": str(fact.get("topic") or ""),
                "label": str(fact.get("label") or ""),
                "value": str(fact.get("value") or ""),
            }
            for fact in packet_aid.get("facts", ())
            if isinstance(fact, Mapping)
        ],
        "authority": dict(packet_aid.get("authority") or {}),
    }
    model_contract = {
        key: value
        for key, value in contract.items()
        if key
        not in {
            "copy_fact_citations",
            "deterministic_fallback_subject_sha256",
            "deterministic_fallback_body_sha256",
        }
    }
    correction = ""
    if prior_rejections:
        correction = (
            "\nThe prior take was rejected for: "
            + "; ".join(prior_rejections[-8:])
            + ". Fix those issues without changing any fact.\n"
        )
    return (
        "Compose one client-facing invoice email as Clara Reid. Return ONLY JSON with keys "
        '"subject" and "body". The deterministic packet is an aid, never authority. '
        "Use only the allowed facts. Do not mention systems, packets, hashes, approvals, gates, "
        "workflows, internal status, source paths, citations, attachment metadata, or hashes. "
        "Use plain text with no markdown. Do not claim the email was sent, delivered, or submitted. "
        "Keep it concise, natural, and professionally human. Clara is quietly confident: grace comes "
        "through poise and brevity. The closing ask and its human reason ARE the warmth. Add no "
        "solicitous pleasantry, eagerness to please, filler thanks, or well-wish. Preserve every required exact "
        "fact at least once and every structural atom exactly once, including the closing ask and its human reason. Do not write a signoff; "
        "the system appends Clara's canonical signoff after generation.\n"
        f"Canonical Clara persona:\n{_stable_json(persona)}"
        f"Raw operator ask:\n{raw_operator_ask}\n"
        f"Deterministic packet aid:\n{_stable_json(model_packet)}"
        f"Immutable copy contract:\n{_stable_json(model_contract)}"
        f"{correction}"
    )


def compose_invoice_copy(
    raw_operator_ask: str,
    deterministic_packet_aid: Mapping[str, Any],
    immutable_copy_contract: Mapping[str, Any],
    *,
    generator_fn: Callable[[str], Any] | None = None,
    attempts: int = DEFAULT_ATTEMPTS,
    minimum_score: float = 0.8,
) -> dict[str, Any]:
    """Generate and critic-select bounded Clara copy with immutable facts."""

    packet_aid = dict(deterministic_packet_aid)
    contract = dict(immutable_copy_contract)
    run_id = "clara-copy-taste:" + _short_hash(
        raw_operator_ask,
        _stable_json(packet_aid),
        _stable_json(contract),
    )
    packet_score = score_packet_dankness(packet_aid, raw_operator_ask)
    generate = generator_fn or _default_generator
    attempt_rows: list[dict[str, Any]] = []
    selected: dict[str, Any] | None = None
    prior_rejections: list[str] = []

    for index in range(1, max(1, min(int(attempts), DEFAULT_ATTEMPTS)) + 1):
        prompt = _prompt_for_attempt(
            raw_operator_ask=raw_operator_ask,
            packet_aid=packet_aid,
            contract=contract,
            prior_rejections=tuple(prior_rejections),
        )
        generated = generate(prompt)
        metadata = dict(generated) if isinstance(generated, Mapping) else {"text": str(generated or "")}
        candidate = _apply_structural_wrapper(
            _candidate_from_text(str(metadata.get("text") or metadata.get("response") or "")),
            contract=contract,
        )
        violations, conformance = _candidate_violations(candidate, contract=contract)
        if str(metadata.get("done_reason") or "").casefold() == "length":
            violations.append("model_output_truncated")
        taste = _taste_score(candidate, contract=contract, violations=violations)
        accepted = bool(
            not violations
            and taste["overall"] >= float(minimum_score)
            and taste["voice"] == 1.0
            and taste["truth"] == 1.0
            and taste["human"] == 1.0
            and taste["warmth"] == 1.0
            and taste["persona_fidelity"] == 1.0
            and taste["action_integrity"] == 1.0
            and taste["client_surface_clean"] == 1.0
        )
        row = {
            "attempt": index,
            "accepted": accepted,
            "model": str(metadata.get("model") or "injected_generator"),
            "status": str(metadata.get("status") or ("success" if candidate["body"] else "empty")),
            "done_reason": metadata.get("done_reason"),
            "elapsed_ms": metadata.get("elapsed_ms"),
            "subject_sha256": _sha256_text(candidate["subject"]),
            "body_sha256": _sha256_text(candidate["body"]),
            "word_count": len(candidate["body"].split()),
            "violations": violations,
            "taste_score": taste,
            "voice_conformance": conformance,
            "raw_model_output_included": False,
        }
        attempt_rows.append(row)
        if accepted and (selected is None or taste["overall"] > selected["taste_score"]["overall"]):
            selected = {**candidate, "attempt": index, "taste_score": taste, "voice_conformance": conformance}
        if violations:
            prior_rejections = violations

    if selected is None:
        raise ClaraCopyComposeError(
            {
                "schema_version": COMPOSE_SCHEMA_VERSION,
                "taste_pass_id": run_id,
                "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "status": "REJECTED_ALL_MODEL_COPY_ATTEMPTS",
                "attempts": attempt_rows,
                "attempt_count": len(attempt_rows),
                "rejected_attempt_count": len(attempt_rows),
                "packet_score": {
                    "overall": packet_score.overall,
                    "grounded": packet_score.grounded,
                    "current": packet_score.current,
                    "useful": packet_score.useful,
                    "lane_rich": packet_score.lane_rich,
                    "right_sized": packet_score.right_sized,
                    "fact_count": packet_score.fact_count,
                    "source_fact_count": packet_score.source_fact_count,
                    "gap_kinds": [str(item.get("kind") or "") for item in packet_score.gaps],
                },
                "raw_operator_ask_sha256": _sha256_text(raw_operator_ask),
                "packet_aid_sha256": _sha256_text(_stable_json(packet_aid)),
                "copy_contract_sha256": _sha256_text(_stable_json(contract)),
                "copy_fact_citations": list(contract.get("copy_fact_citations", ())),
                "authority_boundary": {
                    "provider_draft_created": False,
                    "email_send_performed": False,
                    "business_ledger_posted": False,
                },
            }
        )

    return {
        "schema_version": COMPOSE_SCHEMA_VERSION,
        "taste_pass_id": run_id,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": "SELECTED_MODEL_COPY",
        "subject": selected["subject"],
        "body": selected["body"],
        "selected_attempt": selected["attempt"],
        "selected_model": attempt_rows[selected["attempt"] - 1]["model"],
        "voice_profile_ref": "agent_voice_profile:clara",
        "persona_fidelity": persona_fidelity_note_for_speaker("clara"),
        "voice_conformance": selected["voice_conformance"],
        "critic_score": selected["taste_score"],
        "packet_score": {
            "overall": packet_score.overall,
            "grounded": packet_score.grounded,
            "current": packet_score.current,
            "useful": packet_score.useful,
            "lane_rich": packet_score.lane_rich,
            "right_sized": packet_score.right_sized,
            "fact_count": packet_score.fact_count,
            "source_fact_count": packet_score.source_fact_count,
            "gap_kinds": [str(item.get("kind") or "") for item in packet_score.gaps],
        },
        "attempts": attempt_rows,
        "attempt_count": len(attempt_rows),
        "rejected_attempt_count": sum(1 for row in attempt_rows if not row["accepted"]),
        "raw_operator_ask_sha256": _sha256_text(raw_operator_ask),
        "packet_aid_sha256": _sha256_text(_stable_json(packet_aid)),
        "copy_contract_sha256": _sha256_text(_stable_json(contract)),
        "copy_fact_citations": list(contract.get("copy_fact_citations", ())),
        "authority_boundary": {
            "model_can_change_facts": False,
            "model_can_change_transaction": False,
            "model_can_change_attachment": False,
            "model_can_grant_authority": False,
            "provider_draft_created": False,
            "email_send_performed": False,
            "business_ledger_posted": False,
        },
    }


def record_invoice_copy_taste_pass(result: Mapping[str, Any], *, path: Any = None) -> None:
    """Append one model-copy taste record to the existing packet critic read model."""

    from packet_dankness_enricher import (
        SCORE_LOG_PATH,
        SCORE_LOG_SCHEMA_VERSION,
        _append_read_model_record,
    )

    record = {
        "at": str(result.get("generated_at") or ""),
        "agent_id": "clara",
        "consumer_id": TASTE_CONSUMER_ID,
        "stable_id": str(result.get("taste_pass_id") or ""),
        "packet_id": str(result.get("taste_pass_id") or ""),
        **dict(result.get("packet_score") or {}),
        "copy_critic_score": dict(result.get("critic_score") or {}),
        "persona_fidelity": dict(result.get("persona_fidelity") or {}),
        "selected_attempt": result.get("selected_attempt"),
        "selected_model": result.get("selected_model"),
        "attempt_count": result.get("attempt_count"),
        "rejected_attempt_count": result.get("rejected_attempt_count"),
        "attempts": list(result.get("attempts") or ()),
        "raw_question_included": False,
        "raw_copy_included": False,
    }
    _append_read_model_record(
        SCORE_LOG_PATH if path is None else path,
        record,
        read_model_id="packet_dankness_log",
        schema_version=SCORE_LOG_SCHEMA_VERSION,
        collection_key="records",
    )


__all__ = [
    "ClaraCopyComposeError",
    "COMPOSE_SCHEMA_VERSION",
    "DEFAULT_ATTEMPTS",
    "TASTE_CONSUMER_ID",
    "compose_invoice_copy",
    "record_invoice_copy_taste_pass",
]
