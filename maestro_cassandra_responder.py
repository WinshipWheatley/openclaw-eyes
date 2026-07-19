"""Maestro front-door adapter for Cassandra specialist answers.

The adapter is intentionally narrow. It gates intent before calling
``cassandra_brain.handle`` so send/reply/action/Gmail-shaped text stays on the
existing staging/refusal route and never reaches Cassandra's side-effectful
handler through this front-door path.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Any, Callable, Mapping, Sequence

from agent_introspection import (
    classify_agent_introspection,
    inject_turn_self_facts,
    introspection_answer_grounding_gaps,
    normalize_turn_self_facts,
)


# ── Conversation-continuity flag (ADDITIVE, default OFF) ──────────────────────
def _continuity_enabled() -> bool:
    """Return True only when OPENCLAW_CONTINUITY_CAPSULE is "1" or "true"."""
    return os.environ.get("OPENCLAW_CONTINUITY_CAPSULE", "0").lower() in ("1", "true")


def _packet_engine_enabled() -> bool:
    """Return True unless OPENCLAW_PACKET_ENGINE explicitly disables the engine."""
    return os.environ.get("OPENCLAW_PACKET_ENGINE", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


MAC_RENDER_HINT = "COMPACT_WITH_DISCLOSURE"
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_CAPABILITY_LEDGER_PATH = Path(".openclaw/business_ops/ledger.sqlite")
CAPABILITY_INDEX_READ_MODEL = "openclaw_capability_index.json"
AGENT_PRESENCE_READ_MODEL = "agent_presence.json"
CHIEF_STATUS_READ_MODEL = "chief_status_rail.json"
SYNC_HEALTH_READ_MODEL = "sync_health.json"
HELM_ATTENTION_READ_MODEL = "helm_operator_attention_package.json"
RECEIVABLES_MONTH_BOUNDED_READ_MODEL = "receivables_month_bounded.json"
# Task 143: bare-status doctrine. These read-models refresh on a fast (~5min)
# or near-daily cadence -- a value older than this SLA is presented as stale
# rather than silently passed off as current (kills the June-orientation-as-
# now failure class).
BARE_STATUS_FRESHNESS_SLA_DAYS = 3
ALLOWED_SESSION_KEYS = (
    "system_knowledge_repo_root",
    "system_knowledge_ledger_path",
    "system_knowledge_atlas_path",
    "operator_truth_store_path",
    "recurrence_rule_db_path",
    "proposal_ledger_path",
    "guided_review_state_path",
    "guided_review_root",
    "guided_review_read_model_root",
    "guided_review_receipt_root",
    "workflow_package_sqlite_path",
)
CONTRACT_SESSION_SCALAR_KEYS = (
    "source_message_id",
    "status",
    "active_workflow",
    "pending_field",
    "current_question_id",
    "context_type",
    "probe_marker",
    "run_mode",
    "test_run_id",
)
INTERNAL_SESSION_SCALAR_KEYS = (
    "probe_state_namespace",
    "probe_state_contract_status",
)
SESSION_PATH_KEY_ALIASES = {
    "repo_root": "system_knowledge_repo_root",
    "system_knowledge_repo_root": "system_knowledge_repo_root",
    "ledger_path": "system_knowledge_ledger_path",
    "system_knowledge_ledger_path": "system_knowledge_ledger_path",
    "atlas_path": "system_knowledge_atlas_path",
    "system_knowledge_atlas_path": "system_knowledge_atlas_path",
}
PATH_PREFIX_ALLOWLIST = (
    Path("/home/openclaw").resolve(),
    Path("/mnt/e/openclaw").resolve(),
)
FORBIDDEN_PATH_NAMES = frozenset({".chief.env", ".google-secrets"})
FORBIDDEN_PRIVATE_SUFFIXES = (
    "LegalPrivate",
    "FinancePrivate",
    "MusicLawPrivate",
)

_INTERNAL_ONLY_PROOF_KEYS = frozenset(
    {"internal_model_pass_receipts", "original_operator_message"}
)


def _public_proof_value(value: Any) -> Any:
    """Remove internal-only provenance before any result is serialized."""

    if isinstance(value, Mapping):
        return {
            str(key): _public_proof_value(item)
            for key, item in value.items()
            if str(key) not in _INTERNAL_ONLY_PROOF_KEYS
        }
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        return [_public_proof_value(item) for item in value]
    return value


@dataclass(frozen=True)
class MaestroCassandraResult:
    status: str
    intent_class: str
    allowed_to_call_handle: bool
    one_line_answer: str = ""
    plain_summary: str = ""
    mac_render_hint: str = MAC_RENDER_HINT
    route_to_staging_reason: str = ""
    session_forwarded: Mapping[str, Any] | None = None
    machine_proof: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        session = self.session_forwarded if isinstance(self.session_forwarded, Mapping) else {}
        try:
            from probe_state_contract import validate_bound_probe_session

            isolated = validate_bound_probe_session(session)
        except Exception:
            isolated = False
        if not isolated:
            return
        proof = dict(self.machine_proof or {})
        proof.update(
            {
                "probe_state_isolated": True,
                "probe_marker": str(session.get("probe_marker") or ""),
                "run_mode": str(session.get("run_mode") or ""),
                "test_run_id": str(session.get("test_run_id") or ""),
                "probe_state_namespace": str(session.get("probe_state_namespace") or ""),
                "production_state_allowed": False,
            }
        )
        object.__setattr__(self, "machine_proof", proof)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["session_forwarded"] = dict(self.session_forwarded or {})
        payload["machine_proof"] = _public_proof_value(self.machine_proof or {})
        return payload


def typed_contract_trace_for_result(result: MaestroCassandraResult) -> dict[str, Any]:
    """Extract the bounded typed-decision trace already attached to a result."""

    proof = result.machine_proof if isinstance(result.machine_proof, Mapping) else {}
    receipt = proof.get("typed_contract_decision")
    if not isinstance(receipt, Mapping) or not str(receipt.get("decision_id") or ""):
        return {}
    matches = proof.get("typed_contract_matches")
    return {
        "typed_contract_decision": dict(receipt),
        "typed_contract_matches": (
            [str(item) for item in matches if str(item)]
            if isinstance(matches, Sequence) and not isinstance(matches, (bytes, bytearray, str))
            else []
        ),
    }


def _finalize_typed_contract_result(
    result: MaestroCassandraResult,
    trace: Mapping[str, Any] | None,
    *,
    source_text: str = "",
) -> MaestroCassandraResult:
    if not isinstance(trace, Mapping):
        return result
    receipt = trace.get("typed_contract_decision")
    if not isinstance(receipt, Mapping) or not str(receipt.get("decision_id") or ""):
        return result
    proof = dict(result.machine_proof or {})
    proof["typed_contract_decision"] = dict(receipt)
    matches = trace.get("typed_contract_matches")
    proof["typed_contract_matches"] = (
        [str(item) for item in matches if str(item)]
        if isinstance(matches, Sequence) and not isinstance(matches, (bytes, bytearray, str))
        else []
    )
    answer_receipts = proof.get("internal_model_pass_receipts")
    answer_receipts = dict(answer_receipts) if isinstance(answer_receipts, Mapping) else {}
    answer_receipt = answer_receipts.get("answer")
    binding = proof.get("local_model_binding")
    if source_text and isinstance(answer_receipt, Mapping) and isinstance(binding, Mapping):
        try:
            from secret_log_redaction import redact_secrets

            receipt_message = redact_secrets(source_text)
        except Exception:
            receipt_message = source_text
        interpretation_receipt = {
            "pass": "interpretation",
            "original_operator_message": receipt_message,
            "secret_tokenization_applied": receipt_message != source_text,
            "input_sha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
            "binding_id": str(binding.get("binding_id") or ""),
            "model": str(binding.get("model") or ""),
            "decision_id": str(receipt.get("decision_id") or ""),
        }
        answer_receipts["interpretation"] = interpretation_receipt
        proof["internal_model_pass_receipts"] = answer_receipts
        proof["same_model_for_both_passes"] = bool(
            receipt.get("model_called") is True
            and proof.get("protected_generate_called") is True
            and proof.get("model_call_performed") is True
            and interpretation_receipt["binding_id"]
            and interpretation_receipt["binding_id"]
            == str(answer_receipt.get("binding_id") or "")
            and interpretation_receipt["model"]
            == str(answer_receipt.get("model") or "")
        )
    finalized = replace(result, machine_proof=proof)
    try:
        from vote_timeout_clarification import (
            VoteTimeoutDisposition,
            classify_vote_timeout_disposition,
            enforce_vote_timeout_output,
            is_recoverable_outside_session_conversational_failure,
        )

        deterministic_digest_available = bool(
            proof.get("vote_timeout_deterministic_digest") is True
        )
        disposition = classify_vote_timeout_disposition(
            source_text,
            receipt,
            deterministic_digest_available=deterministic_digest_available,
        )
        if disposition is VoteTimeoutDisposition.NONE:
            return finalized
        downstream_model_called = bool(
            proof.get("downstream_model_call_performed") is True
            or proof.get("model_call_performed") is True
        )
        if (
            disposition is VoteTimeoutDisposition.CLARIFY
            and is_recoverable_outside_session_conversational_failure(receipt)
            and proof.get("protected_generate_called") is True
            and downstream_model_called
        ):
            proof["semantic_vote_model_called"] = receipt.get("model_called") is True
            proof["downstream_model_call_performed"] = downstream_model_called
            proof["second_model_call_performed"] = bool(
                receipt.get("model_called") is True and downstream_model_called
            )
            proof["vote_timeout_recovery_applied"] = True
            proof["conversational_vote_failure_recovery_applied"] = True
            proof["vote_timeout_clarification_applied"] = False
            proof["vote_timeout_deterministic_digest"] = False
            proof["vote_timeout_recovery_source"] = (
                "downstream_model"
                if downstream_model_called
                else "protected_response_fallback"
            )
            proof["vote_timeout_post_launder_assertion"] = False
            return replace(finalized, machine_proof=proof)
        visible = enforce_vote_timeout_output(
            source_text,
            finalized.plain_summary,
            receipt,
            deterministic_digest_available=deterministic_digest_available,
        )
    except Exception:
        return finalized
    proof["vote_timeout_post_launder_assertion"] = True
    proof.setdefault("downstream_model_call_performed", False)
    proof.setdefault("second_model_call_performed", False)
    proof["vote_timeout_downstream_violation_detected"] = bool(
        proof.get("downstream_model_call_performed") is True
        or proof.get("second_model_call_performed") is True
        or proof.get("protected_generate_called") is True
    )
    return replace(
        finalized,
        one_line_answer=_one_line_answer(visible),
        plain_summary=visible,
        machine_proof=proof,
    )


HandleFn = Callable[[str, dict[str, Any] | None], Sequence[str]]
ProtectedGenerateFn = Callable[..., Any]
HANDLE_BACKEND_ROUTE = "maestro_cassandra_responder.cassandra_brain.handle"
DATE_BACKEND_ROUTE = "maestro_cassandra_responder.datetime_deterministic"
HERMES_TRUTHFUL_BACKEND_ROUTE = "maestro_cassandra_responder.hermes_truthful_advisory"
HERMES_FALLBACK_AGENT_TARGETS = frozenset(
    {
        "cassandra",
        "chief",
        "guardian",
        "hermes",
        "niles",
        "operator_briefing",
        "operations_router",
        "producer",
        "report_bridge",
    }
)
HERMES_SEND_OR_MONEY_RE = re.compile(
    r"\b(send|email|message|text|telegram|notify|reply|forward|post|deliver|pay|payment|money|wire|ach|transfer|refund|charge)\b"
)
INTERNAL_STATE_LEAK_PATTERNS = (
    re.compile(r"\bInterrupting current task\s*(?:\([^)]*\))?\s*", re.IGNORECASE),
    re.compile(r"\(?(?:iteration|loop)\s+\d+\s*/\s*\d+\)?", re.IGNORECASE),
)
_ANSWER_TOPIC_AMOUNT_RE = re.compile(r"\$[\d,]+(?:\.\d+)?")
_ANSWER_TOPIC_MAX_SENTENCES = 5


def _derived_answer_topic_values(context_packet: Mapping[str, Any] | None) -> tuple[str, ...]:
    if not isinstance(context_packet, Mapping):
        return ()
    facts = context_packet.get("facts", ())
    if not isinstance(facts, Sequence):
        return ()
    values: list[str] = []
    for fact in facts:
        if not isinstance(fact, Mapping):
            continue
        if str(fact.get("provenance") or "") != "derived_answer_topic":
            continue
        value = str(fact.get("value") or "").strip()
        if value:
            values.append(value)
    return tuple(values)


def _sentence_count(text: str) -> int:
    stripped = str(text or "").strip()
    if not stripped:
        return 0
    return len([part for part in re.split(r"(?<=[.!?])\s+", stripped) if part.strip()])


def _enforce_answer_topic_presentation(answer_text: str, context_packet: Mapping[str, Any] | None) -> str:
    """Anti-launder extension (task 132): when the packet carries a derived answer topic
    (money/plate), the reply must carry the topic's rendered lines VERBATIM -- amounts and
    statuses are never paraphrased. Live evidence (msg 1277): the model re-narrated an
    evidenced $1,095 as "amounts still unverified or unknown", dropping the number. Post-check
    the model's reply against the topic's amount strings and against a concise-reply cap; on
    either mismatch, fall back to the deterministic topic text itself (grounded > eloquent)."""
    topic_values = _derived_answer_topic_values(context_packet)
    if not topic_values:
        return answer_text
    required_amounts = tuple(dict.fromkeys(_ANSWER_TOPIC_AMOUNT_RE.findall(" ".join(topic_values))))
    if not required_amounts:
        return answer_text
    amounts_present = all(amount in answer_text for amount in required_amounts)
    concise_enough = _sentence_count(answer_text) <= _ANSWER_TOPIC_MAX_SENTENCES
    if amounts_present and concise_enough:
        return answer_text
    return " ".join(topic_values)


def _default_handle(text: str, session: dict[str, Any] | None = None) -> Sequence[str]:
    from cassandra_brain import handle as cassandra_handle

    return cassandra_handle(text, session)


def backend_route_for_result(result: MaestroCassandraResult) -> str:
    if result.allowed_to_call_handle:
        return HANDLE_BACKEND_ROUTE
    if result.intent_class == "date_awareness":
        return DATE_BACKEND_ROUTE
    if result.intent_class == "maestro_brain_freeform":
        return "maestro_cassandra_responder.protected_generate"
    if result.intent_class == "status_capability_readback":
        if (result.machine_proof or {}).get("protected_generate_called") is True:
            return "maestro_cassandra_responder.protected_generate.status_capability_context"
        return "maestro_cassandra_responder.truthful_status_capability_readback"
    if result.intent_class == "system_health_readback":
        return "maestro_cassandra_responder.chief_system_health_readback"
    if result.intent_class == "hermes_truthful_advisory":
        return HERMES_TRUTHFUL_BACKEND_ROUTE
    if result.intent_class:
        return f"maestro_cassandra_responder.{result.intent_class}"
    return "maestro_cassandra_responder.intent_gate"


def proof_refs_for_result(result: MaestroCassandraResult, *base_refs: str) -> tuple[str, ...]:
    refs: list[str] = [str(ref) for ref in base_refs if str(ref or "").strip()]
    if result.intent_class:
        refs.append(f"maestro_cassandra_responder:{result.intent_class}")
    proof = result.machine_proof or {}
    for key in ("proof_refs", "read_model_refs", "source_truth_refs"):
        value = proof.get(key)
        if isinstance(value, str) and value.strip():
            refs.append(value.strip())
        elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
            refs.extend(str(item).strip() for item in value if str(item).strip())
    write_receipts = proof.get("operator_truth_write_receipts")
    if isinstance(write_receipts, Sequence) and not isinstance(write_receipts, (str, bytes, bytearray)):
        refs.extend(
            str(item.get("receipt_id") or "").strip()
            for item in write_receipts
            if isinstance(item, Mapping) and item.get("status") == "committed"
        )
    return tuple(dict.fromkeys(refs))


def external_llm_invoked_for_result(result: MaestroCassandraResult) -> bool | None:
    proof = result.machine_proof or {}
    if "external_llm_invoked" in proof:
        return proof.get("external_llm_invoked") is True
    if (
        proof.get("semantic_vote_model_called") is True
        and proof.get("downstream_model_call_performed") is False
    ):
        # The typed receipt proves one attempt, not which provider family won
        # the adaptive slot. False would be a fabricated backend assertion.
        return None
    if proof.get("cassandra_handle_called") is not True:
        return False
    return proof.get("external_llm_invoked") is True


def machine_proof_for_result(result: MaestroCassandraResult) -> dict[str, Any]:
    proof = _public_proof_value(result.machine_proof or {})
    proof["external_llm_invoked"] = external_llm_invoked_for_result(result)
    return proof


def result_dict_for_receipt(result: MaestroCassandraResult) -> dict[str, Any]:
    payload = result.to_dict()
    payload["machine_proof"] = machine_proof_for_result(result)
    return payload


def _stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _short_hash_for_packet(*parts: Any) -> str:
    return hashlib.sha256(_stable_json(parts).encode("utf-8")).hexdigest()[:16]


def _protected_generate_receipt_machine_proof(receipt: Mapping[str, Any]) -> dict[str, Any]:
    route = str(receipt.get("route") or "").strip()
    model_selected = str(
        receipt.get("model_selected")
        or receipt.get("model_id")
        or receipt.get("model")
        or ""
    ).strip()
    proof: dict[str, Any] = {
        "model_call_performed": bool(receipt.get("model_call_performed", False)),
        "external_llm_invoked": bool(receipt.get("external_llm_invoked", False)),
        "local_model_invoked": bool(receipt.get("local_model_invoked", False)),
        "deterministic_fallback_used": bool(receipt.get("deterministic_fallback_used", False)),
        "model_call_attempted": bool(receipt.get("model_call_attempted", False)),
        "model_output_delivered": bool(receipt.get("model_output_delivered", False)),
        "delivered_response_source": str(receipt.get("delivered_response_source") or ""),
    }
    if route:
        proof["route"] = route
        proof["protected_generate_route"] = route
    if model_selected:
        proof["model_id"] = model_selected
        proof["protected_generate_model_selected"] = model_selected
    fallback_reason = str(receipt.get("model_fallback_reason") or "").strip()
    if fallback_reason:
        proof["model_fallback_reason"] = fallback_reason
    skills_applied = receipt.get("skills_applied")
    if isinstance(skills_applied, Sequence) and not isinstance(skills_applied, (str, bytes)):
        proof["skills_applied"] = [str(skill) for skill in skills_applied if str(skill).strip()]
    skill_receipts = receipt.get("skill_receipts")
    if isinstance(skill_receipts, Sequence) and not isinstance(skill_receipts, (str, bytes)):
        proof["skill_receipts"] = [dict(item) for item in skill_receipts if isinstance(item, Mapping)]
    return proof


def _packet_engine_delivery_proof(
    *,
    context_packet: Mapping[str, Any],
    receipt: Mapping[str, Any] | None,
    used: bool,
    fallback_used: bool,
    failure_type: str = "",
) -> dict[str, Any]:
    proof: dict[str, Any] = {
        "packet_engine_used": used,
        "packet_engine_fallback_used": fallback_used,
    }
    if receipt:
        proof["packet_engine_receipt_id"] = str(receipt.get("receipt_id") or "")
        proof["packet_engine_receipt_status"] = str(receipt.get("status") or "")
    if failure_type:
        proof["packet_engine_failure_type"] = failure_type

    packet_proof = context_packet.get("machine_proof")
    persona_delivery = context_packet.get("persona_delivery")
    doctrine_ref = ""
    if isinstance(packet_proof, Mapping):
        doctrine_ref = str(packet_proof.get("packet_engine_doctrine_ref") or "").strip()
    if not doctrine_ref and isinstance(persona_delivery, Mapping):
        doctrine_ref = str(persona_delivery.get("doctrine_ref") or "").strip()
    if doctrine_ref:
        proof["packet_engine_doctrine_ref"] = doctrine_ref
    autonomy_rung = ""
    autonomy_classification_only = False
    autonomy_new_authority_conferred = False
    if isinstance(packet_proof, Mapping):
        autonomy_rung = str(packet_proof.get("packet_engine_autonomy_rung") or "").strip()
        autonomy_classification_only = bool(
            packet_proof.get("packet_engine_autonomy_classification_only")
        )
        autonomy_new_authority_conferred = bool(
            packet_proof.get("packet_engine_autonomy_new_authority_conferred")
        )
    if not autonomy_rung and isinstance(persona_delivery, Mapping):
        autonomy_rung = str(persona_delivery.get("autonomy_rung") or "").strip()
        autonomy_classification_only = bool(
            persona_delivery.get("autonomy_classification_only")
        )
        autonomy_new_authority_conferred = bool(
            persona_delivery.get("autonomy_new_authority_conferred")
        )
    if autonomy_rung:
        proof["packet_engine_autonomy_rung"] = autonomy_rung
        proof["packet_engine_autonomy_classification_only"] = autonomy_classification_only
        proof["packet_engine_autonomy_new_authority_conferred"] = (
            autonomy_new_authority_conferred
        )
    return proof


def _receipt_or_packet_has_skill(
    skill_id: str,
    *,
    receipt: Mapping[str, Any],
    context_packet: Mapping[str, Any],
) -> bool:
    expected = str(skill_id or "").strip()
    if not expected:
        return False
    skills_applied = receipt.get("skills_applied")
    if isinstance(skills_applied, Sequence) and not isinstance(skills_applied, (str, bytes)):
        if expected in {str(skill).strip() for skill in skills_applied}:
            return True
    for key in ("skill_receipts", "skills"):
        rows = context_packet.get(key)
        if isinstance(rows, Sequence) and not isinstance(rows, (str, bytes)):
            for row in rows:
                if isinstance(row, Mapping) and str(row.get("skill_id") or "").strip() == expected:
                    return True
    return False


def _is_conversational_status_capability_prompt(text: str) -> bool:
    capability_phrases = (
        "what can you help me with",
        "what can openclaw help me with",
        "what can you do for me",
        "what can you do",
        "what can openclaw do",
        "what are you capable of",
        "how can you help",
        "how can openclaw help",
    )
    return any(phrase in text for phrase in capability_phrases)


def _is_built_vs_on_ledger_prompt(text: str) -> bool:
    return any(
        phrase in text
        for phrase in (
            "what's built and what's actually on",
            "whats built and whats actually on",
            "what is built and what is actually on",
            "what is built versus what is on",
            "built vs on",
            "built versus on",
        )
    )


def _build_typed_contract_status_answer(
    text: str,
    *,
    agent: str,
    session: Mapping[str, Any] | None,
) -> dict[str, Any]:
    normalized = _normalize(text)
    if agent == "maestro" and _is_built_vs_on_ledger_prompt(normalized):
        return build_ledger_capability_answer()
    rich_status_markers = (
        "status readback",
        "who are the agents",
        "what does each agent do",
        "what does each do",
        "agent roster",
        "agent list",
        "system-wide next safe move",
        "system wide next safe move",
        "next safe move",
        "next safest move",
        "safe next move",
    )
    if agent == "maestro" and any(marker in normalized for marker in rich_status_markers):
        return build_truthful_status_capability_answer(
            session=session,
            focus=_status_capability_readback_focus(normalized),
        )
    return build_targeted_bare_status_answer(text, agent=agent, session=session)
def _path_is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _has_forbidden_path_marker(raw_path: str) -> bool:
    normalized = raw_path.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part and part != "."]
    for part in parts:
        if part in FORBIDDEN_PATH_NAMES:
            return True
        if part == "OpenClawLegalPrivate":
            return True
        if any(part.endswith(suffix) for suffix in FORBIDDEN_PRIVATE_SUFFIXES):
            return True
    return False


def _sanitize_session_path(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw or _has_forbidden_path_marker(raw):
        return None
    candidate = Path(raw)
    if not candidate.is_absolute():
        return None
    try:
        resolved = candidate.resolve(strict=False)
    except OSError:
        return None
    if _has_forbidden_path_marker(str(resolved)):
        return None
    allowed_roots = list(PATH_PREFIX_ALLOWLIST)
    try:
        from probe_state_contract import DEFAULT_PROBE_STATE_ROOT

        configured_probe_root = os.environ.get("OPENCLAW_PROBE_STATE_ROOT", "").strip()
        allowed_roots.append(Path(configured_probe_root).resolve() if configured_probe_root else DEFAULT_PROBE_STATE_ROOT.resolve())
    except Exception:
        pass
    if not any(resolved == root or _path_is_under(resolved, root) for root in allowed_roots):
        return None
    return str(resolved)


def _add_safe_session_value(session: dict[str, Any], key: str, value: Any) -> None:
    canonical_key = SESSION_PATH_KEY_ALIASES.get(key)
    if canonical_key is None and key in ALLOWED_SESSION_KEYS:
        canonical_key = key
    if canonical_key is None or value in ("", None):
        return
    safe_value = _sanitize_session_path(value)
    if safe_value is not None:
        session[canonical_key] = safe_value


def _add_safe_contract_scalar(session: dict[str, Any], key: str, value: Any) -> None:
    if key not in (*CONTRACT_SESSION_SCALAR_KEYS, *INTERNAL_SESSION_SCALAR_KEYS) or value in (None, ""):
        return
    if isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, (str, int)):
        text = str(value).strip()
    else:
        return
    if not text or len(text) > 128 or "\n" in text or "\r" in text:
        return
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:@ -]{0,127}", text):
        return
    if key == "status" and text.lower() not in {
        "active",
        "paused",
        "waiting",
        "inactive",
        "completed",
        "cancelled",
        "expired",
    }:
        return
    if key == "run_mode" and text.lower() not in {
        "production",
        "test_dry_run",
        "test_live",
        "probe",
        "replay",
    }:
        return
    session[key] = text


def filtered_session(session: Mapping[str, Any] | None = None) -> dict[str, Any]:
    filtered: dict[str, Any] = {}
    if not session:
        return filtered
    for key in ALLOWED_SESSION_KEYS:
        _add_safe_session_value(filtered, key, session.get(key))
    for key in CONTRACT_SESSION_SCALAR_KEYS:
        _add_safe_contract_scalar(filtered, key, session.get(key))
    for key in INTERNAL_SESSION_SCALAR_KEYS:
        _add_safe_contract_scalar(filtered, key, session.get(key))
    return filtered


def session_from_request(request: Mapping[str, Any]) -> dict[str, Any]:
    session: dict[str, Any] = {}
    for key in SESSION_PATH_KEY_ALIASES:
        _add_safe_session_value(session, key, request.get(key))
    context = request.get("context") if isinstance(request.get("context"), Mapping) else {}
    current_context = request.get("current_context") if isinstance(request.get("current_context"), Mapping) else {}
    request_session = request.get("session") if isinstance(request.get("session"), Mapping) else {}
    for source in (request, request_session, context, current_context):
        for key in SESSION_PATH_KEY_ALIASES:
            _add_safe_session_value(session, key, source.get(key))
        for key in CONTRACT_SESSION_SCALAR_KEYS:
            _add_safe_contract_scalar(session, key, source.get(key))
    try:
        from probe_state_contract import bind_probe_state_session, probe_activation_metadata

        session = bind_probe_state_session(request, session)
    except Exception as exc:
        try:
            activation = probe_activation_metadata(request)
        except Exception:
            activation = {"active": True, "probe_marker": "", "run_mode": "probe", "test_run_id": ""}
        if activation.get("active"):
            session.update(
                {
                    "probe_marker": str(activation.get("probe_marker") or ""),
                    "run_mode": str(activation.get("run_mode") or "probe"),
                    "test_run_id": str(activation.get("test_run_id") or ""),
                }
            )
        session["probe_state_binding_error"] = str(
            getattr(exc, "reason", "probe_state_binding_failed")
        )
    return session


def operator_text_from_request(request: Mapping[str, Any]) -> str:
    text_keys = (
        "operator_text",
        "operatorText",
        "operator_message",
        "operatorMessage",
        "chat_goal",
        "chatGoal",
        "goal_text",
        "goalText",
        "source_text",
        "sourceText",
        "text",
        "message",
    )
    for key in text_keys:
        value = request.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    event = request.get("event") if isinstance(request.get("event"), Mapping) else {}
    for key in text_keys:
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _ledger_resolution_for_text(text: str) -> dict[str, Any]:
    try:
        from maestro_context_packet import resolve_ledger_reference

        return resolve_ledger_reference(text)
    except Exception:
        return {"status": "NO_LEDGER_REFERENCE", "processing_allowed": False, "action_allowed": False}


def build_targeted_bare_status_answer(
    text: str,
    *,
    agent: str,
    session: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Render status in the addressed agent's deterministic lane.

    The Maestro front door is transport, not authorship.  Once the processor
    resolves an explicit target, its status adapter must supply the answer and
    proof; otherwise a correctly routed Hermes request is silently rewritten
    as Maestro at the final composition seam.
    """

    agent_key = str(agent or "maestro").strip().lower()
    if agent_key == "maestro":
        return build_maestro_bare_status_answer(session=session)

    if agent_key == "hermes":
        from agent_contract_renderers import render_hermes_status

        summary = str(render_hermes_status())
    elif agent_key == "niles":
        from agent_contract_renderers import render_niles_status

        summary = str(render_niles_status())
    elif agent_key == "chief":
        from chief_router import build_chief_bare_status_answer

        summary = str(build_chief_bare_status_answer())
    elif agent_key in {"cassandra", "clara"}:
        from cassandra_brain import _handle_ops_status_inquiry

        summary = str(_handle_ops_status_inquiry(text))
    elif agent_key == "guardian":
        summary = (
            "Guardian's approval posture is read-only here; this front-door request "
            "does not carry a current pending-count proof. Send and authority gates "
            "remain closed by default."
        )
    else:
        return build_maestro_bare_status_answer(session=session)

    summary = summary.strip()
    one_line = summary.splitlines()[0] if summary else f"{agent_key.title()} status is unavailable."
    return {
        "one_line_answer": one_line,
        "plain_summary": summary or one_line,
        "machine_proof": {
            "targeted_status_renderer": agent_key,
            "model_call_performed": False,
            "external_llm_invoked": False,
            "protected_generate_called": False,
            "workflow_package_staged": False,
        },
    }


_TEAM_ROSTER_AGENT_IDS = ("maestro", "chief", "cassandra", "guardian", "niles", "hermes")


def _is_team_roster_intent(text: str) -> bool:
    # The roster/org-chart is enumerable truth — never let the model freestyle it.
    lowered = text
    if "roster" in lowered:
        return True
    team_ref = ("my team" in lowered or "the team" in lowered or "on my team" in lowered
                or "my agents" in lowered or "what agents" in lowered or "which agents" in lowered
                or "who does what" in lowered)
    if team_ref:
        return True
    return False


def build_team_roster_answer(text: str) -> dict[str, Any]:
    """Deterministic team roster from agent_lane_registry seeds (the same source
    that authors doctrine SD-4). The model must never invent teammates."""
    try:
        from agent_lane_registry import DEFAULT_AGENT_LANE_SEEDS
        by_id = {s.agent_id: s for s in DEFAULT_AGENT_LANE_SEEDS}
    except Exception:
        by_id = {}
    lines = []
    for agent_id in _TEAM_ROSTER_AGENT_IDS:
        seed = by_id.get(agent_id)
        if seed is None:
            continue
        summary = str(getattr(seed, "role_summary", "") or "").split(". ")[0].rstrip(".")
        label = str(getattr(seed, "lane_label", "") or "")
        lines.append(f"- {seed.display_name} ({label}): {summary}.")
    if len(lines) < 4:
        # Fail closed to the doctrinal roster rather than a partial/confabulated one.
        lines = [
            "- Maestro (Operator Front Door): your main point of contact; understands intent and routes.",
            "- Chief (System Orchestration): coordinates work, plans, and system repair.",
            "- Cassandra / Clara Reid (Business Ops & Comms): money, invoices, client follow-up.",
            "- Guardian (Safety & Security): approvals, privacy, and the final safety boundary.",
            "- Niles (Music & Art Production): your producer/engineer/creative partner.",
            "- Hermes (Advisory Synthesis): observes the system and advises; no direct authority.",
        ]
    plain = "Your team is six agents:\n" + "\n".join(lines)
    one_line = "Your team: Maestro (front door), Chief (orchestration), Cassandra/Clara (business & money), Guardian (safety), Niles (music), Hermes (advisory)."
    return {
        "one_line_answer": one_line,
        "plain_summary": plain,
        "machine_proof": {
            "team_roster_deterministic": True,
            "team_roster_source": "agent_lane_registry_seeds",
            "model_call_performed": False,
            "agent_count": len(_TEAM_ROSTER_AGENT_IDS),
        },
    }


def classify_frontdoor_intent(text: str) -> tuple[str, bool, str]:
    normalized = _normalize(text)
    if not normalized:
        return ("empty", False, "empty_text")
    artifact_surface_intent = _artifact_surface_intent_class(normalized)
    if artifact_surface_intent:
        return (artifact_surface_intent, True, "")
    if _is_hermes_truthful_intent(normalized):
        return ("hermes_truthful_advisory", True, "")
    if _is_recurrence_rule_statement_intent(text):
        # Task 136b#1 (Fable probe 2026-07-07): a rule-shaped statement -- INCLUDING a
        # correction phrasing with schedule words ("actually St Anne's invoices should go
        # out on the 15th") -- must reach the rule store BEFORE the legacy operator-truth-
        # store intake can claim it. Two intakes competing for the same statement violates
        # the no-leftovers doctrine at the intake layer; checked first, unconditionally.
        return ("recurrence_rule_statement", True, "")
    if _is_operator_truth_correction_intent(text):
        return ("operator_truth_correction", True, "")
    if _is_operator_truth_query_intent(normalized):
        return ("operator_truth_query", True, "")
    if _is_system_health_readback_intent(normalized):
        return ("system_health_readback", True, "")
    if _is_advisory_judgment_intent(normalized):
        return ("advisory_judgment", True, "")
    if _is_advisory_interrogative_intent(normalized):
        return ("maestro_brain_freeform", True, "")
    if _is_send_or_reply_intent(normalized):
        return ("send_reply_email_action", False, "send_reply_email_action_intent_routes_to_staging")
    if _is_inbox_metadata_intent(normalized):
        return ("inbox_gmail_metadata", False, "gmail_metadata_queries_use_existing_staging_path_for_truthful_proof")
    if _is_calendar_or_briefing_intent(normalized):
        return ("calendar_or_briefing", False, "calendar_or_briefing_routes_to_staging")
    # Task 142: dispatch instructions ("...needs to go out — get it to the right
    # agent") route to staging BEFORE ledger-reference resolution can claim them
    # as freeform — an instruction must never end in the overview digest.
    if _is_dispatch_instruction_intent(normalized):
        return ("workflow_or_business_action", False, "workflow_or_business_action_routes_to_staging")
    ledger_resolution = _ledger_resolution_for_text(normalized)
    if ledger_resolution.get("status") == "NEEDS_CLARIFICATION":
        return ("ledger_reference_clarification", True, "")
    if ledger_resolution.get("status") == "RESOLVED" and ledger_resolution.get("blocked_action_requested") is not True:
        return ("maestro_brain_freeform", True, "")
    if _is_workflow_or_business_action_intent(normalized) and not _is_general_question_shape(normalized):
        return ("workflow_or_business_action", False, "workflow_or_business_action_routes_to_staging")
    if _is_date_awareness_intent(normalized):
        return ("date_awareness", True, "")
    if _is_status_capability_intent(normalized):
        return ("status_capability_readback", True, "")
    if _is_team_roster_intent(normalized):
        return ("team_roster", True, "")
    if _is_people_intent(normalized):
        return ("people_reference_query", True, "")
    if _is_system_knowledge_intent(normalized):
        return ("system_knowledge", True, "")
    return ("maestro_brain_freeform", True, "")


def _try_calendar(text: str, forwarded_session: Mapping[str, Any]) -> "MaestroCassandraResult | None":
    """Route a calendar READ/CREATE request to the live Google broker. Returns an answer
    result, or None to fall through to staging (briefings, delete, or broker unavailable).
    Delete is Guardian-gated and blocks on approval, so it stays on staging for now."""
    try:
        from calendar_router import detect_calendar_intent, route_calendar
    except Exception:
        return None
    intent = detect_calendar_intent(text)
    if intent is None:
        return None
    if intent == "delete":
        # Async Guardian-gated delete: parse the event, send the operator an approval,
        # reply immediately (the listener's CALDEL callback fires the actual delete).
        try:
            from calendar_router import _default_parse_event
            from calendar_delete_approval import request_calendar_delete

            parsed = _default_parse_event(text) or {}
            if not (parsed.get("title") and parsed.get("start_iso")):
                reply = "Tell me which event (title and time) and I'll send you a Guardian approval to delete it."
            else:
                _res = request_calendar_delete(
                    {"title": parsed["title"], "start_iso": parsed["start_iso"]}, agent="maestro"
                )
                reply = (
                    f"I've sent you a Guardian approval to delete “{parsed['title']}”. "
                    "Approve it and I'll remove it."
                    if _res.get("ok")
                    else f"I couldn't set that delete up ({_res.get('error', '')})."
                )
        except Exception:
            return None
    else:
        try:
            from google_access_broker import call as _broker_execute
            reply = route_calendar(text, agent="maestro", broker_execute=_broker_execute)
        except Exception:
            return None
    if not reply:
        return None
    return MaestroCassandraResult(
        status="ANSWER_READY",
        intent_class="calendar",
        allowed_to_call_handle=False,
        one_line_answer=_one_line_answer(reply),
        plain_summary=reply,
        mac_render_hint=MAC_RENDER_HINT,
        session_forwarded=forwarded_session,
        machine_proof={
            **_adapter_machine_proof(handle_called=False),
            "calendar_broker_called": True,
            "calendar_intent": intent,
            "protected_generate_called": False,
            "external_llm_invoked": False,
        },
    )


def _probe_state_blocked_result(reason: str) -> MaestroCassandraResult:
    return MaestroCassandraResult(
        status="ANSWER_READY",
        intent_class="probe_state_binding_blocked",
        allowed_to_call_handle=False,
        one_line_answer="Probe replay blocked because isolated state could not be bound.",
        plain_summary=(
            "Probe replay blocked because isolated state could not be bound. "
            "Production state was not used or changed."
        ),
        mac_render_hint=MAC_RENDER_HINT,
        session_forwarded={},
        machine_proof={
            **_adapter_machine_proof(handle_called=False),
            "probe_state_binding_failed": True,
            "probe_state_binding_reason": reason,
            "probe_state_isolated": False,
            "production_state_allowed": False,
            "file_mutation_performed": False,
            "business_state_mutation_performed": False,
        },
    )


def _answer_outside_session_vote_failure(
    text: str,
    *,
    decision: Any,
    session: Mapping[str, Any] | None,
    source_surface: str,
    agent: str,
    _capsule: Any | None,
) -> MaestroCassandraResult | None:
    """Suppress every post-vote model path while preserving its exact receipt."""

    from vote_timeout_clarification import (
        ExplicitDigestIntent,
        VoteTimeoutDisposition,
        WARM_TIMEOUT_CLARIFICATION,
        classify_explicit_digest_intent,
        classify_vote_timeout_disposition,
        enforce_vote_timeout_output,
        is_recoverable_outside_session_conversational_failure,
        unknown_vote_status_receipt,
    )

    receipt = decision.receipt.to_dict()
    deterministic_digest_available = bool(
        str(agent or "").strip().lower() == "maestro"
        and str(source_surface or "").strip() == "operator_maestro_chat"
    )
    disposition = classify_vote_timeout_disposition(
        text,
        receipt,
        deterministic_digest_available=deterministic_digest_available,
    )
    if disposition is VoteTimeoutDisposition.NONE:
        return None
    if (
        disposition is VoteTimeoutDisposition.CLARIFY
        and is_recoverable_outside_session_conversational_failure(receipt)
    ):
        return None

    packet: Mapping[str, Any] = {}
    packet_error = ""
    deterministic_digest_used = False
    digest_kind = classify_explicit_digest_intent(text)
    answer = WARM_TIMEOUT_CLARIFICATION
    if disposition is VoteTimeoutDisposition.DETERMINISTIC_DIGEST:
        try:
            from maestro_context_packet import build_maestro_context_packet

            packet = build_maestro_context_packet(
                question=text,
                session=session,
                source_surface=source_surface,
                require_real_truth=True,
                capsule=_capsule if _continuity_enabled() else None,
            )
        except Exception as exc:
            packet = {}
            packet_error = type(exc).__name__
        from protected_generate import render_explicit_deterministic_digest

        rendered = render_explicit_deterministic_digest(
            text,
            context_packet=packet,
            agent=agent,
        )
        if rendered is not None:
            deterministic_digest_used = True
            rendered_text = str(rendered)
            # Legacy anti-launder requires every derived amount in its packet.
            # The timeout renderer intentionally caps a digest at three facts,
            # so project that assertion to the selected facts instead of
            # letting it reinflate the bounded answer with the entire packet.
            projected_packet = dict(packet)
            projected_facts: list[Mapping[str, Any]] = []
            for fact in packet.get("facts", ()):
                if not isinstance(fact, Mapping):
                    continue
                if str(fact.get("provenance") or "") != "derived_answer_topic":
                    projected_facts.append(fact)
                    continue
                value = str(fact.get("value") or "")
                amounts = _ANSWER_TOPIC_AMOUNT_RE.findall(value)
                if (
                    amounts
                    and all(amount in rendered_text for amount in amounts)
                ) or (
                    not amounts
                    and value.strip().rstrip(".") in rendered_text
                ):
                    projected_facts.append(fact)
            projected_packet["facts"] = tuple(projected_facts)
            answer = _enforce_answer_topic_presentation(
                rendered_text,
                projected_packet,
            )
        answer = enforce_vote_timeout_output(
            text,
            answer,
            receipt,
            deterministic_digest_available=deterministic_digest_used,
        )

    proof_refs = tuple(
        str(ref)
        for ref in packet.get("source_refs", ())
        if str(ref).strip()
    )
    semantic_vote_model_called = receipt.get("model_called") is True
    proof = {
        **_adapter_machine_proof(handle_called=False),
        "typed_contract_decision": receipt,
        "typed_contract_matches": [
            label.value for label in getattr(decision, "matches", ())
        ],
        # This is the one permitted model attempt.  Do not misreport the whole
        # turn as model-free merely because the downstream call was suppressed.
        "semantic_vote_model_called": semantic_vote_model_called,
        "model_call_performed": semantic_vote_model_called,
        "downstream_model_call_performed": False,
        "second_model_call_performed": False,
        "protected_generate_called": False,
        "maestro_context_packet_used": bool(packet),
        "context_packet_id": str(packet.get("packet_id") or ""),
        "proof_refs": proof_refs,
        "source_truth_refs": proof_refs,
        "workflow_package_staged": False,
        "file_mutation_performed": False,
        "business_state_mutation_performed": False,
        "business_action_performed": False,
        "vote_timeout_clarification_applied": not deterministic_digest_used,
        "vote_timeout_deterministic_digest": deterministic_digest_used,
        "vote_timeout_digest_kind": (
            digest_kind.value
            if isinstance(digest_kind, ExplicitDigestIntent)
            else "none"
        ),
        "vote_timeout_status": str(receipt.get("semantic_vote_status") or ""),
        "vote_timeout_post_launder_assertion": True,
        "unrelated_digest_suppressed": not deterministic_digest_used,
    }
    vote_failure_receipt = unknown_vote_status_receipt(receipt)
    if vote_failure_receipt is not None:
        proof["vote_failure_receipt"] = vote_failure_receipt
    if packet_error:
        proof["context_packet_error"] = packet_error
    return MaestroCassandraResult(
        status="ANSWER_READY",
        intent_class=(
            "vote_timeout_deterministic_digest"
            if deterministic_digest_used
            else "vote_timeout_clarification"
        ),
        allowed_to_call_handle=False,
        one_line_answer=_one_line_answer(answer),
        plain_summary=answer,
        mac_render_hint=MAC_RENDER_HINT,
        session_forwarded=filtered_session(session),
        machine_proof=proof,
    )


def _answer_frontdoor_chat_impl(
    text: str,
    *,
    session: Mapping[str, Any] | None = None,
    source_surface: str = "operator_maestro_chat",
    handle_fn: HandleFn | None = None,
    protected_generate_fn: ProtectedGenerateFn | None = None,
    _capsule: Any | None = None,
    agent: str = "maestro",
    _contract_trace_sink: dict[str, Any] | None = None,
    first_touch_receipt: Mapping[str, Any] | None = None,
) -> MaestroCassandraResult:
    from local_model_governance import bind_interactive_model

    session = bind_interactive_model(
        session,
        request_key=str((session or {}).get("source_message_id") or text),
    )
    artifact_surface_intent = _artifact_surface_intent_class(_normalize(text))
    if artifact_surface_intent:
        return _artifact_surface_intent_result(
            artifact_surface_intent,
            session=session,
        )
    # Resolve the shared refusal seam before probe-state binding.  A caller's
    # hash/agent-bound pass marker is reused; otherwise this adapter evaluates
    # exactly once and forwards the resulting pass marker to the full typed
    # contract below.  The typed projection does not re-run the guard.
    from first_touch_decision import attempt_first_touch, valid_pass_through_marker
    from typed_contract_decision import ContractContext, adapt_first_touch_receipt

    _early_contract_context = ContractContext(
        agent=agent,
        surface=source_surface,
        source_message_id=str((session or {}).get("source_message_id") or ""),
        active_session=False,
    )
    _first_touch_reply: str | None = None
    if valid_pass_through_marker(first_touch_receipt, text=text, agent=agent):
        _early_first_touch_receipt = dict(first_touch_receipt or {})
    else:
        _first_touch_outcome = attempt_first_touch(
            text,
            agent=agent,
            surface=source_surface,
        )
        _early_first_touch_receipt = dict(_first_touch_outcome.receipt)
        if _first_touch_outcome.handled and _first_touch_outcome.decision is not None:
            _first_touch_reply = _first_touch_outcome.decision.reply
        elif valid_pass_through_marker(
            _early_first_touch_receipt,
            text=text,
            agent=agent,
        ):
            first_touch_receipt = _early_first_touch_receipt
    _early_contract_decision = adapt_first_touch_receipt(
        text,
        context=_early_contract_context,
        first_touch_receipt=_early_first_touch_receipt,
        reply=_first_touch_reply,
    )
    if _contract_trace_sink is not None:
        _contract_trace_sink.update(
            {
                "typed_contract_decision": _early_contract_decision.receipt.to_dict(),
                "typed_contract_matches": [
                    label.value for label in _early_contract_decision.matches
                ],
            }
        )
    if _first_touch_reply is not None:
        _lines = _first_touch_reply.splitlines()
        return MaestroCassandraResult(
            status="ANSWER_READY",
            intent_class="operator_refusal_guard",
            allowed_to_call_handle=False,
            one_line_answer=_lines[0] if _lines else _first_touch_reply,
            plain_summary=_first_touch_reply,
            mac_render_hint=MAC_RENDER_HINT,
            session_forwarded={},
            machine_proof={
                **_adapter_machine_proof(handle_called=False),
                "operator_refusal_guard": True,
                "first_touch_decision": _early_first_touch_receipt,
                "model_call_performed": False,
                "external_llm_invoked": False,
                "local_model_invoked": False,
                "protected_generate_called": False,
                "workflow_package_staged": False,
                "file_mutation_performed": bool(
                    _early_first_touch_receipt.get("file_mutation_performed")
                ),
            },
        )
    if isinstance(session, Mapping) and str(session.get("probe_state_binding_error") or ""):
        return _probe_state_blocked_result(str(session["probe_state_binding_error"]))
    try:
        from probe_state_contract import ProbeStateBindingError, bind_probe_state_session

        session = bind_probe_state_session(session, session)
    except Exception as exc:
        reason = str(getattr(exc, "reason", "probe_state_binding_failed"))
        return _probe_state_blocked_result(reason)
    _introspection_match = classify_agent_introspection(
        text,
        addressed_agent=agent,
    )
    if _introspection_match is not None:
        return _answer_with_maestro_brain(
            text,
            session=session,
            source_surface=source_surface,
            forwarded_session=filtered_session(session),
            protected_generate_fn=protected_generate_fn,
            _capsule=_capsule,
            agent=agent,
            intent_class="agent_introspection",
        )
    if (
        isinstance(session, Mapping)
        and str(session.get("lm1_reused_answer") or "").strip()
        and isinstance(session.get("lm1_reused_model_receipt"), Mapping)
    ):
        return _answer_with_maestro_brain(
            text,
            session=session,
            source_surface=source_surface,
            forwarded_session=filtered_session(session),
            protected_generate_fn=protected_generate_fn,
            _capsule=_capsule,
            agent=agent,
        )
    # Judgment questions are read-only BRAIN work. Resolve this named class before
    # the typed action contract can misread "next step" as a handoff instruction.
    if _is_advisory_judgment_intent(_normalize(text)):
        return _answer_with_maestro_brain(
            text,
            session=session,
            source_surface=source_surface,
            forwarded_session=filtered_session(session),
            protected_generate_fn=protected_generate_fn,
            _capsule=_capsule,
            agent=agent,
            intent_class="advisory_judgment",
        )
    # Task 151: one typed decision contract, adapted at this real Maestro
    # assembly point before legacy regex taps, sessions, digest, or model work.
    # Authority/domain pass-through decisions deliberately continue into their
    # established owners; safe/deterministic answers return here directly.
    _contract_context = None
    _contract_status_answer = None
    _contract_decision = None
    try:
        from first_touch_decision import valid_pass_through_marker

        _refusal_evaluated = valid_pass_through_marker(
            first_touch_receipt,
            text=text,
            agent=agent,
        )
    except Exception:
        _refusal_evaluated = False
    try:
        from typed_contract_decision import (
            ContractContext,
            DecisionAction,
            HandoffResult,
            active_session_from_mapping,
            decide_contract,
            emergency_adapter_error_decision,
            semantic_vote_enabled_for_adapter,
            synthetic_adapter_error_decision,
        )

        _contract_context = ContractContext(
            agent=agent,
            surface=source_surface,
            source_message_id=str((session or {}).get("source_message_id") or ""),
            active_session=active_session_from_mapping(session),
            session_kind=str((session or {}).get("active_workflow") or (session or {}).get("context_type") or ""),
            session_field=str((session or {}).get("pending_field") or (session or {}).get("current_question_id") or ""),
            session_snapshot=dict(session or {}),
        )

        def _status_renderer() -> str:
            nonlocal _contract_status_answer
            if not _explicitly_requests_status(text):
                _contract_status_answer = {
                    "one_line_answer": "I couldn't route that question to a grounded answer.",
                    "plain_summary": (
                        "I couldn't route that question to a grounded answer. "
                        "I will not substitute an unrelated status readback; nothing else ran."
                    ),
                    "machine_proof": {
                        "canned_status_mismatch_blocked": True,
                        "status_intent_mismatch_blocked": True,
                        "status_renderer_called": False,
                    },
                }
                return str(_contract_status_answer["plain_summary"])
            _contract_status_answer = _build_typed_contract_status_answer(
                text,
                agent=agent,
                session=session,
            )
            return str(_contract_status_answer["plain_summary"])

        def _handoff_stager(raw_text: str, _context: ContractContext) -> HandoffResult:
            from workflow_package_queue import (
                DEFAULT_SQLITE_PATH,
                classify_workflow_route,
                render_cassandra_nudge_handoff_reply,
                render_live_arts_handoff_reply,
                stage_cassandra_receivables_nudge_handoff,
                stage_live_arts_invoice_handoff,
            )

            _sqlite_path = Path((session or {}).get("workflow_package_sqlite_path") or DEFAULT_SQLITE_PATH)
            _created_at = str((session or {}).get("contract_created_at") or "") or None
            workflow_ref = classify_workflow_route(raw_text).workflow_ref
            if workflow_ref == "cassandra_receivables_nudge_handoff":
                staged = stage_cassandra_receivables_nudge_handoff(
                    raw_text,
                    source_surface=source_surface,
                    sqlite_path=_sqlite_path,
                    created_at=_created_at,
                )
                _reply = render_cassandra_nudge_handoff_reply(staged)
            elif workflow_ref == "live_arts_md_invoice_workflow":
                staged = stage_live_arts_invoice_handoff(
                    raw_text,
                    source_surface=source_surface,
                    sqlite_path=_sqlite_path,
                    created_at=_created_at,
                )
                _reply = render_live_arts_handoff_reply(staged)
            else:
                raise ValueError("canonical workflow-route owner returned no staged route")
            return HandoffResult(
                reply=_reply,
                receipt_pointer=str(staged["receipt"]["receipt_ref"]),
                package_id=str(staged["package"]["package_id"]),
            )

        _contract_decision = decide_contract(
            text,
            context=_contract_context,
            status_renderer=_status_renderer,
            handoff_stager=_handoff_stager,
            semantic_vote_enabled=semantic_vote_enabled_for_adapter(
                "maestro", default=True
            ),
            first_touch_receipt=first_touch_receipt,
        )
        _refusal_evaluated = True
    except Exception as exc:
        print(
            f"[typed_contract][maestro] {type(exc).__name__}; "
            f"active_session={bool(_contract_context and _contract_context.active_session)}",
            flush=True,
        )
        if _contract_context is None:
            from typed_contract_decision import ContractContext as _ContractContext

            _contract_context = _ContractContext(
                agent=agent,
                surface=source_surface,
                source_message_id=str((session or {}).get("source_message_id") or ""),
                active_session=False,
            )
        try:
            _contract_decision = synthetic_adapter_error_decision(
                text,
                context=_contract_context,
                error_type=type(exc).__name__,
            )
        except Exception as factory_exc:
            _contract_decision = emergency_adapter_error_decision(
                text,
                context=_contract_context,
                error_type=type(exc).__name__,
                factory_error_type=type(factory_exc).__name__,
            )

    if _contract_decision is not None and _contract_trace_sink is not None:
        _contract_trace_sink.update(
            {
                "typed_contract_decision": _contract_decision.receipt.to_dict(),
                "typed_contract_matches": [label.value for label in _contract_decision.matches],
            }
        )

    if _contract_decision is not None:
        _vote_failure_answer = _answer_outside_session_vote_failure(
            text,
            decision=_contract_decision,
            session=session,
            source_surface=source_surface,
            agent=agent,
            _capsule=_capsule,
        )
        if _vote_failure_answer is not None:
            return _vote_failure_answer

    if _contract_decision is not None and _contract_decision.handled:
        _handoff_workflow_ref = ""
        if any(label.value == "route_instruction" for label in _contract_decision.matches):
            try:
                from workflow_package_queue import classify_workflow_route

                _handoff_workflow_ref = str(
                    classify_workflow_route(text).workflow_ref or ""
                )
            except Exception:
                _handoff_workflow_ref = ""
        _intent_by_label = {
            "refusal": "operator_refusal_guard",
            "status": (
                "status_capability_readback"
                if (_contract_status_answer or {}).get("machine_proof", {}).get(
                    "status_capability_readback_performed"
                )
                else "maestro_bare_status_readback"
            ),
            "identity": "identity_persona_core",
            "low_coherence": "gibberish_low_coherence",
            "route_instruction": (
                "cassandra_receivables_nudge_handoff"
                if _handoff_workflow_ref == "cassandra_receivables_nudge_handoff"
                else "live_arts_invoice_handoff"
            ),
            "money_read": "money_read",
            "guardian_gate_narration": "guardian_gate_narration",
            "unresolved": "typed_contract_session_preserved",
        }
        _contract_reply = str(_contract_decision.reply or "").strip()
        _contract_lines = _contract_reply.splitlines()
        _contract_intent_class = _intent_by_label.get(
            _contract_decision.label.value, _contract_decision.label.value
        )
        if _contract_decision.action is DecisionAction.STAGE_HANDOFF:
            _contract_intent_class = (
                "cassandra_receivables_nudge_handoff"
                if _handoff_workflow_ref == "cassandra_receivables_nudge_handoff"
                else "live_arts_invoice_handoff"
            )
        _money_read_proof_refs: tuple[str, ...] = ()
        if _contract_intent_class == "money_read":
            try:
                from money_truth import settled_row_proof_refs

                _money_read_proof_refs = (
                    "generated/read_models/receivables_month_bounded.json",
                    *settled_row_proof_refs(text),
                )
            except Exception:
                _money_read_proof_refs = ()
        return MaestroCassandraResult(
            status="ANSWER_READY",
            intent_class=_contract_intent_class,
            allowed_to_call_handle=False,
            one_line_answer=_contract_lines[0] if _contract_lines else _contract_reply,
            plain_summary=_contract_reply,
            mac_render_hint=MAC_RENDER_HINT,
            session_forwarded=filtered_session(session),
            machine_proof={
                **_adapter_machine_proof(handle_called=False),
                **dict((_contract_status_answer or {}).get("machine_proof") or {}),
                "model_call_performed": _contract_decision.receipt.model_called,
                "external_llm_invoked": False,
                "protected_generate_called": False,
                "maestro_context_packet_used": False,
                "workflow_package_staged": _contract_decision.action is DecisionAction.STAGE_HANDOFF,
                "typed_contract_handoff_workflow_ref": _handoff_workflow_ref,
                "typed_contract_decision": _contract_decision.receipt.to_dict(),
                "typed_contract_matches": [label.value for label in _contract_decision.matches],
                "read_model_refs": list(_money_read_proof_refs),
            },
        )

    # ── Refusal-first guard (task 141) — FIRST tap, before intent
    # classification, workflow-package staging, clarify sessions, or any
    # model call. A refusal returns ANSWER_READY so the processor renders it
    # as the final reply and the staging fallthrough (the pass-1 "$500 send
    # -> gate-smoke diagnostics" path) never runs. Fail-open on guard errors.
    _refusal_text = None
    if not _refusal_evaluated:
        try:
            from operator_refusal_guard import refusal_reply_for_text as _refusal_reply_for_text

            _refusal_text = _refusal_reply_for_text(
                text, agent=agent, surface=source_surface
            )
        except Exception:
            _refusal_text = None
    if _refusal_text is not None:
        _refusal_lines = _refusal_text.splitlines()
        return MaestroCassandraResult(
            status="ANSWER_READY",
            intent_class="operator_refusal_guard",
            allowed_to_call_handle=False,
            one_line_answer=_refusal_lines[0] if _refusal_lines else _refusal_text,
            plain_summary=_refusal_text,
            mac_render_hint=MAC_RENDER_HINT,
            session_forwarded=filtered_session(session),
            machine_proof={
                "cassandra_handle_called": False,
                "model_call_performed": False,
                "external_llm_invoked": False,
                "protected_generate_called": False,
                "maestro_context_packet_used": False,
                "operator_refusal_guard": True,
                "workflow_package_staged": False,
            },
        )

    # ── Bare-status short-circuit (task 143) — SECOND tap, before intent
    # classification, workflow-package staging, or any model call. A bare
    # "status?" has no co-occurring qualifier term for classify_frontdoor_intent's
    # status_capability_readback matcher to catch, so without this it falls all
    # the way through to maestro_brain_freeform / the gate-smoke staging
    # fallback (pass-1 finding: "staged as diagnostic_package_gate_smoke").
    # Hit by both live callers of answer_frontdoor_chat regardless of
    # source_surface, since it runs before that check too.
    if _is_bare_status_query(text):
        _status_answer = build_targeted_bare_status_answer(
            text,
            agent=agent,
            session=session,
        )
        return MaestroCassandraResult(
            status="ANSWER_READY",
            intent_class=f"{agent}_bare_status_readback",
            allowed_to_call_handle=False,
            one_line_answer=_status_answer["one_line_answer"],
            plain_summary=_status_answer["plain_summary"],
            mac_render_hint=MAC_RENDER_HINT,
            session_forwarded=filtered_session(session),
            machine_proof=_status_answer["machine_proof"],
        )

    # ── Task 142 (classification-time) unclassified-input contract ──────────
    # THIRD tap, still before intent classification, ledger/fact resolution,
    # and answer-topic matching. Live probe proof: "blorp fizzle invoice
    # quantum?" carried the bare "invoice" substring, fact resolution derived a
    # money answer topic, and _enforce_answer_topic_presentation stamped the
    # full attention/money digest over the reply — so coherence and identity
    # must be decided HERE. The same checks inside protected_generate's
    # grounded fallback remain as belt-and-braces. Fail-open on import errors.
    _contract_intent: str | None = None
    _contract_answer: str | None = None
    try:
        from protected_generate import (
            identity_persona_reply,
            is_identity_question,
            is_low_coherence_text,
            low_coherence_reply_line,
        )

        if is_identity_question(text):
            _contract_intent = "identity_persona_core"
            _contract_answer = identity_persona_reply(agent)
        elif is_low_coherence_text(text):
            _contract_intent = "gibberish_low_coherence"
            _contract_answer = low_coherence_reply_line(agent)
    except Exception:
        _contract_intent = None
        _contract_answer = None
    if _contract_answer is not None and _contract_intent is not None:
        return MaestroCassandraResult(
            status="ANSWER_READY",
            intent_class=_contract_intent,
            allowed_to_call_handle=False,
            one_line_answer=_one_line_answer(_contract_answer),
            plain_summary=_contract_answer,
            mac_render_hint=MAC_RENDER_HINT,
            session_forwarded=filtered_session(session),
            machine_proof={
                "cassandra_handle_called": False,
                "model_call_performed": False,
                "external_llm_invoked": False,
                "protected_generate_called": False,
                "maestro_context_packet_used": False,
                "unclassified_input_contract": _contract_intent,
                "workflow_package_staged": False,
            },        )

    intent_class, allowed, reason = classify_frontdoor_intent(text)
    forwarded_session = filtered_session(session)
    if intent_class in {
        "artifact_authenticity_challenge",
        "surface_message_deletion_request",
        "artifact_authenticity_and_surface_deletion_request",
    }:
        return _artifact_surface_intent_result(intent_class, session=forwarded_session)
    if intent_class == "calendar_or_briefing":
        _cal = _try_calendar(text, forwarded_session)
        if _cal is not None:
            return _cal
    if not allowed:
        return MaestroCassandraResult(
            status="ROUTE_TO_STAGING",
            intent_class=intent_class,
            allowed_to_call_handle=False,
            route_to_staging_reason=reason,
            session_forwarded=forwarded_session,
            machine_proof=_adapter_machine_proof(handle_called=False),
        )

    if intent_class == "operator_truth_correction":
        from operator_truth_store import capture_operator_truth_from_text

        truth_store_path = (
            (session or {}).get("operator_truth_store_path")
            if isinstance(session, Mapping)
            else None
        )
        records = capture_operator_truth_from_text(
            text,
            source_surface=source_surface,
            source_ref=str((session or {}).get("source_message_id") or ""),
            path=truth_store_path,
        )
        committed_records = [
            record
            for record in records
            if isinstance(record.get("write_receipt"), Mapping)
            and record["write_receipt"].get("status") == "committed"
        ]
        labels = [
            str(record.get("label") or record.get("entity_key"))
            for record in committed_records
        ]
        write_receipts = [dict(record["write_receipt"]) for record in committed_records]
        if labels:
            label_text = ", ".join(labels)
            answer = f"Operator truth updated for {label_text}. The shared store now outranks stale finance or reality context."
        else:
            answer = "I did not find a bounded entity correction to store. No action was taken."
        return MaestroCassandraResult(
            status="ANSWER_READY",
            intent_class=intent_class,
            allowed_to_call_handle=False,
            one_line_answer=answer,
            plain_summary=answer,
            mac_render_hint=MAC_RENDER_HINT,
            session_forwarded=forwarded_session,
            machine_proof={
                **_adapter_machine_proof(handle_called=False),
                "operator_truth_store_written": bool(committed_records),
                "operator_truth_entities": labels,
                "operator_truth_write_receipts": write_receipts,
                "file_mutation_performed": any(
                    receipt.get("file_mutation_performed") is True
                    for receipt in write_receipts
                ),
                "business_state_mutation_performed": any(
                    receipt.get("business_state_mutation_performed") is True
                    for receipt in write_receipts
                ),
            },
        )

    if intent_class == "recurrence_rule_statement":
        from recurrence_rule_intake import capture_recurrence_rule_statement
        from recurrence_rule_store import DEFAULT_DB_PATH as _DEFAULT_RULE_DB_PATH
        from recurrence_rule_store import RecurrenceRuleStore

        rule_db_path = (
            (session or {}).get("recurrence_rule_db_path") if isinstance(session, Mapping) else None
        ) or _DEFAULT_RULE_DB_PATH
        with RecurrenceRuleStore(rule_db_path) as store:
            capture = capture_recurrence_rule_statement(text, store=store, source_ref=source_surface)
        if capture is None:
            answer = "I couldn't quite parse that as a recurring rule. No rule was recorded."
            captured = False
            needs_review = False
        else:
            answer = str(capture["reply"])
            captured = capture["status"] == "captured"
            needs_review = capture["status"] == "needs_operator_review"
        return MaestroCassandraResult(
            status="ANSWER_READY",
            intent_class=intent_class,
            allowed_to_call_handle=False,
            one_line_answer=answer,
            plain_summary=answer,
            mac_render_hint=MAC_RENDER_HINT,
            session_forwarded=forwarded_session,
            machine_proof={
                **_adapter_machine_proof(handle_called=False),
                "recurrence_rule_captured": captured,
                "recurrence_rule_needs_operator_review": needs_review,
                "protected_generate_called": False,
                "external_llm_invoked": False,
                "local_model_invoked": False,
            },
        )

    if intent_class == "operator_truth_query":
        from operator_truth_store import find_operator_truth_for_text

        truth_store_path = (
            (session or {}).get("operator_truth_store_path")
            if isinstance(session, Mapping)
            else None
        )
        match = find_operator_truth_for_text(text, path=truth_store_path)
        if match is None:
            answer = "I do not have a matching operator-truth record for that query. No model call was made."
            entity_key = ""
            label = ""
            value = ""
        else:
            entity_key, record = match
            label = str(record.get("label") or entity_key)
            value = " ".join(str(record.get("value") or "").split()).strip()
            answer = f"Yes. The operator truth store has {label}: {value}"
        return MaestroCassandraResult(
            status="ANSWER_READY",
            intent_class=intent_class,
            allowed_to_call_handle=False,
            one_line_answer=_one_line_answer(answer),
            plain_summary=answer,
            mac_render_hint=MAC_RENDER_HINT,
            session_forwarded=forwarded_session,
            machine_proof={
                **_adapter_machine_proof(handle_called=False),
                "operator_truth_query_performed": True,
                "operator_truth_store_read": True,
                "operator_truth_record_found": match is not None,
                "operator_truth_entity_key": entity_key,
                "operator_truth_label": label,
                "protected_generate_called": False,
                "maestro_context_packet_used": False,
                "external_llm_invoked": False,
            },
        )

    # Date queries are answered deterministically: the current date is a known
    # fact, not something to ask a language model to guess (it hallucinates it).
    if intent_class == "date_awareness":
        from datetime import datetime
        _now = datetime.now()
        _answer = f"Today is {_now.strftime('%Y-%m-%d')} ({_now.strftime('%A')})."
        return MaestroCassandraResult(
            status="ANSWER_READY",
            intent_class=intent_class,
            allowed_to_call_handle=False,
            one_line_answer=_answer,
            plain_summary=_answer,
            mac_render_hint=MAC_RENDER_HINT,
            session_forwarded=forwarded_session,
            machine_proof=_adapter_machine_proof(handle_called=False),
        )

    if intent_class == "system_health_readback":
        answer = build_chief_system_health_answer(session=session)
        return MaestroCassandraResult(
            status="ANSWER_READY",
            intent_class=intent_class,
            allowed_to_call_handle=False,
            one_line_answer=answer["one_line_answer"],
            plain_summary=answer["plain_summary"],
            mac_render_hint=MAC_RENDER_HINT,
            session_forwarded=forwarded_session,
            machine_proof=_adapter_machine_proof(handle_called=False) | answer["machine_proof"],
        )

    if intent_class == "status_capability_readback" and _is_built_vs_on_ledger_prompt(_normalize(text)):
        answer = build_ledger_capability_answer()
        return MaestroCassandraResult(
            status="ANSWER_READY",
            intent_class=intent_class,
            allowed_to_call_handle=False,
            one_line_answer=answer["one_line_answer"],
            plain_summary=answer["plain_summary"],
            mac_render_hint=MAC_RENDER_HINT,
            session_forwarded=forwarded_session,
            machine_proof=_adapter_machine_proof(handle_called=False) | answer["machine_proof"],
        )

    if intent_class == "status_capability_readback" and _is_conversational_status_capability_prompt(_normalize(text)):
        return _answer_status_capability_with_brain(
            text,
            session=session,
            source_surface=source_surface,
            forwarded_session=forwarded_session,
            protected_generate_fn=protected_generate_fn,
            agent=agent,
        )

    if intent_class == "status_capability_readback":
        answer = build_truthful_status_capability_answer(
            session=session,
            focus=_status_capability_readback_focus(_normalize(text)),
        )
        return MaestroCassandraResult(
            status="ANSWER_READY",
            intent_class=intent_class,
            allowed_to_call_handle=False,
            one_line_answer=answer["one_line_answer"],
            plain_summary=answer["plain_summary"],
            mac_render_hint=MAC_RENDER_HINT,
            session_forwarded=forwarded_session,
            machine_proof=_adapter_machine_proof(handle_called=False) | answer["machine_proof"],
        )

    if intent_class == "team_roster":
        answer = build_team_roster_answer(text)
        return MaestroCassandraResult(
            status="ANSWER_READY",
            intent_class=intent_class,
            allowed_to_call_handle=False,
            one_line_answer=answer["one_line_answer"],
            plain_summary=answer["plain_summary"],
            mac_render_hint=MAC_RENDER_HINT,
            session_forwarded=forwarded_session,
            machine_proof=_adapter_machine_proof(handle_called=False) | answer["machine_proof"],
        )

    if intent_class == "people_reference_query":
        return _answer_people_query(
            text,
            session=session,
            source_surface=source_surface,
            forwarded_session=forwarded_session,
            protected_generate_fn=protected_generate_fn,
            _capsule=_capsule,
            agent=agent,
        )

    if intent_class == "hermes_truthful_advisory":
        answer = build_hermes_truthful_advisory_answer(text)
        return MaestroCassandraResult(
            status="ANSWER_READY",
            intent_class=intent_class,
            allowed_to_call_handle=False,
            one_line_answer=answer["one_line_answer"],
            plain_summary=answer["plain_summary"],
            mac_render_hint=MAC_RENDER_HINT,
            session_forwarded=forwarded_session,
            machine_proof=_adapter_machine_proof(handle_called=False) | answer["machine_proof"],
        )

    if intent_class == "ledger_reference_clarification":
        answer = (
            "Which ledger do you mean: the bank/finance ledger or a system/control ledger? "
            "I can process a finance-ledger readback through the graded LIGHT gate, but I will not mutate a ledger."
        )
        return MaestroCassandraResult(
            status="ANSWER_READY",
            intent_class=intent_class,
            allowed_to_call_handle=False,
            one_line_answer=_one_line_answer(answer),
            plain_summary=answer,
            mac_render_hint=MAC_RENDER_HINT,
            session_forwarded=forwarded_session,
            machine_proof={
                **_adapter_machine_proof(handle_called=False),
                "ledger_reference_clarification_performed": True,
                "protected_generate_called": False,
                "maestro_context_packet_used": False,
                "external_llm_invoked": False,
            },
        )

    if intent_class == "maestro_brain_freeform":
        if source_surface != "operator_maestro_chat":
            return MaestroCassandraResult(
                status="ROUTE_TO_STAGING",
                intent_class=intent_class,
                allowed_to_call_handle=False,
                route_to_staging_reason="maestro_brain_freeform_requires_operator_maestro_chat_surface",
                session_forwarded=forwarded_session,
                machine_proof={
                    **_adapter_machine_proof(handle_called=False),
                    "protected_generate_called": False,
                    "maestro_context_packet_used": False,
                    "external_llm_invoked": False,
                },
            )
        return _answer_with_maestro_brain(
            text,
            session=session,
            source_surface=source_surface,
            forwarded_session=forwarded_session,
            protected_generate_fn=protected_generate_fn,
            _capsule=_capsule,
            agent=agent,
        )

    replies = list((handle_fn or _default_handle)(text, forwarded_session))
    plain_summary = _strip_internal_state_leaks(_plain_summary(replies))
    return MaestroCassandraResult(
        status="ANSWER_READY",
        intent_class=intent_class,
        allowed_to_call_handle=True,
        one_line_answer=_one_line_answer(plain_summary),
        plain_summary=plain_summary,
        mac_render_hint=MAC_RENDER_HINT,
        session_forwarded=forwarded_session,
        machine_proof=_adapter_machine_proof(handle_called=True),
    )


def answer_frontdoor_chat(
    text: str,
    *,
    session: Mapping[str, Any] | None = None,
    source_surface: str = "operator_maestro_chat",
    handle_fn: HandleFn | None = None,
    protected_generate_fn: ProtectedGenerateFn | None = None,
    _capsule: Any | None = None,
    agent: str = "maestro",
    first_touch_receipt: Mapping[str, Any] | None = None,
) -> MaestroCassandraResult:
    """Run the responder once and attach its one typed receipt to every result."""

    trace: dict[str, Any] = {}
    result = _answer_frontdoor_chat_impl(
        text,
        session=session,
        source_surface=source_surface,
        handle_fn=handle_fn,
        protected_generate_fn=protected_generate_fn,
        _capsule=_capsule,
        agent=agent,
        _contract_trace_sink=trace,
        first_touch_receipt=first_touch_receipt,
    )
    return _finalize_typed_contract_result(
        result,
        trace,
        source_text=text,
    )


def _answer_status_capability_with_brain(
    text: str,
    *,
    session: Mapping[str, Any] | None,
    source_surface: str,
    forwarded_session: Mapping[str, Any],
    protected_generate_fn: ProtectedGenerateFn | None,
    agent: str = "maestro",
) -> MaestroCassandraResult:
    focus = _status_capability_readback_focus(_normalize(text))
    readback = build_truthful_status_capability_answer(session=session, focus=focus)
    base_proof = dict(readback["machine_proof"])
    source_refs = tuple(str(ref) for ref in base_proof.get("source_truth_refs", ()) if str(ref).strip())
    fact_value = str(readback.get("plain_summary") or readback.get("one_line_answer") or "").strip()
    fact = {
        "fact_id": f"status_capability:{_short_hash_for_packet(text, fact_value, source_refs)}",
        "topic": "status_capability",
        "label": "Truthful status and capability readback",
        "value": fact_value,
        "provenance": "generated_read_model_summary",
        "source_ref": ", ".join(source_refs) or CAPABILITY_INDEX_READ_MODEL,
        "pii_tier": "PUBLIC",
    }
    packet_engine_used = False
    packet_engine_fallback_used = False
    packet_engine_receipt: Mapping[str, Any] | None = None
    packet_engine_failure_type = ""
    try:
        from maestro_context_packet import build_maestro_context_packet

        if _packet_engine_enabled():
            try:
                from packet_engine import build_agent_packet

                context_packet = dict(
                    build_agent_packet(
                        agent=agent,
                        question=text,
                        question_class="status_capability_readback",
                        authority={
                            "source_surface": source_surface,
                            "send_hold": True,
                        },
                        session=session,
                        source_surface=source_surface,
                        require_real_truth=True,
                    )
                )
                packet_engine_receipt = dict(context_packet.get("packet_engine_receipt") or {})
                failures = packet_engine_receipt.get("failures") or ()
                if context_packet.get("status") == "PACKET_ENGINE_BUILD_FAILED" or failures:
                    packet_engine_fallback_used = True
                    if failures:
                        first_failure = next(iter(failures), {})
                        if isinstance(first_failure, Mapping):
                            packet_engine_failure_type = str(first_failure.get("type") or "")
                    context_packet = dict(
                        build_maestro_context_packet(
                            question=text,
                            session=session,
                            source_surface=source_surface,
                            require_real_truth=True,
                        )
                    )
                else:
                    packet_engine_used = True
            except Exception as exc:  # noqa: BLE001 - fail open to old packet path
                packet_engine_fallback_used = True
                packet_engine_failure_type = type(exc).__name__
                try:
                    from packet_engine import build_fallback_receipt

                    packet_engine_receipt = build_fallback_receipt(
                        agent=agent,
                        question_class="status_capability_readback",
                        failure=exc,
                    )
                except Exception:  # noqa: BLE001
                    packet_engine_receipt = None
                context_packet = dict(
                    build_maestro_context_packet(
                        question=text,
                        session=session,
                        source_surface=source_surface,
                        require_real_truth=True,
                    )
                )
        else:
            context_packet = dict(
                build_maestro_context_packet(
                    question=text,
                    session=session,
                    source_surface=source_surface,
                    require_real_truth=True,
                )
            )
        facts = [row for row in context_packet.get("facts", ()) if isinstance(row, Mapping)]
        context_packet["facts"] = [fact, *facts]
        refs = list(context_packet.get("source_refs", ()))
        refs.extend(source_refs)
        context_packet["source_refs"] = tuple(dict.fromkeys(str(ref) for ref in refs if str(ref).strip()))
        context_packet["packet_text"] = "\n".join(
            part
            for part in (
                str(context_packet.get("packet_text") or "").strip(),
                "STATUS/CAPABILITY FACTS FOR THIS ANSWER:",
                fact_value,
            )
            if part
        )
        context_packet["status_capability_focus"] = focus
    except Exception:
        context_packet = {
            "schema_version": "status_capability_context_packet_v0",
            "packet_id": f"status_capability_{_short_hash_for_packet(text, fact_value, source_refs)}",
            "question": text,
            "source_surface": source_surface,
            "facts": [fact] if fact_value else [],
            "source_refs": source_refs,
            "packet_text": "\n".join(
                part
                for part in (
                    "STATUS/CAPABILITY FACTS FOR THIS ANSWER:",
                    fact_value,
                )
                if part
            ),
        }

    if protected_generate_fn is None:
        from protected_generate import protected_generate_with_receipt
        from local_model_governance import interactive_model_from_session

        outcome = protected_generate_with_receipt(
            text,
            context_packet=context_packet,
            agent=agent,
            model_selected=interactive_model_from_session(session),
        )
    else:
        outcome = protected_generate_fn(text, context_packet=context_packet)

    if hasattr(outcome, "text") and hasattr(outcome, "receipt"):
        answer_text = str(outcome.text)
        receipt = dict(outcome.receipt)
    elif isinstance(outcome, Mapping):
        answer_text = str(outcome.get("text") or outcome.get("answer") or "")
        receipt = dict(outcome.get("receipt") or {})
    else:
        answer_text = str(outcome or "")
        receipt = {
            "status": "ANSWER_READY",
            "decision": "INJECTED_PROTECTED_GENERATE",
            "external_llm_invoked": False,
            "local_model_invoked": True,
            "model_call_performed": True,
        }
    if receipt.get("model_call_performed") is not True:
        fallback_readback = str(readback.get("plain_summary") or readback.get("one_line_answer") or "").strip()
        if fallback_readback:
            agent_label = str(agent or "maestro").strip().capitalize()
            answer_text = (
                f"{agent_label} capability/status readback: {fallback_readback}"
                if agent_label.lower() != "maestro"
                else fallback_readback
            )
    answer_text = _strip_internal_state_leaks(answer_text).strip()
    if not answer_text:
        answer_text = str(readback.get("plain_summary") or readback.get("one_line_answer") or "").strip()

    proof_refs = tuple(str(ref) for ref in context_packet.get("source_refs", ()) if str(ref).strip())
    packet_engine_proof = _packet_engine_delivery_proof(
        context_packet=context_packet,
        receipt=packet_engine_receipt,
        used=packet_engine_used,
        fallback_used=packet_engine_fallback_used,
        failure_type=packet_engine_failure_type,
    )
    return MaestroCassandraResult(
        status="ANSWER_READY",
        intent_class="status_capability_readback",
        allowed_to_call_handle=False,
        one_line_answer=_one_line_answer(answer_text),
        plain_summary=answer_text,
        mac_render_hint=MAC_RENDER_HINT,
        session_forwarded=forwarded_session,
        machine_proof={
            **_adapter_machine_proof(handle_called=False),
            **base_proof,
            **_protected_generate_receipt_machine_proof(receipt),
            "protected_generate_called": True,
            "maestro_context_packet_used": True,
            "context_packet_id": str(context_packet.get("packet_id") or ""),
            "status_capability_facts_injected": True,
            "status_capability_readback_performed": False,
            "status_capability_readback_available_as_facts": True,
            "source_truth_refs": proof_refs,
            "protected_generate_receipt_id": str(receipt.get("receipt_id") or ""),
            "protected_generate_audit_ref": str(receipt.get("audit_ref") or ""),
            "protected_generate_decision": str(receipt.get("decision") or ""),
            "send_hold_boundary_visible": True,
            "claims_trace_to_packet": True,
            **packet_engine_proof,
        },
    )


def _adapter_machine_proof(*, handle_called: bool) -> dict[str, Any]:
    return {
        "maestro_cassandra_adapter_invoked": True,
        "cassandra_handle_called": handle_called,
        "intent_gate_before_handle": True,
        "gmail_metadata_queries_route_to_staging": True,
        "send_reply_action_intent_routes_to_staging": True,
        "status_capability_readback_performed": False,
        "capability_index_used": False,
        "agent_presence_used": False,
        "chief_status_rail_used": False,
        "email_send_performed": False,
        "telegram_send_triggered": False,
        "agent_dispatch_performed": False,
        "worker_dispatch_performed": False,
        "gmail_reply_sent": False,
        "gmail_metadata_read_performed": False,
        "browser_access_performed": False,
        "coupa_access_performed": False,
        "portal_submitted": False,
        "ledger_mutation_performed": False,
        "workbook_mutation_performed": False,
        "pdf_export_performed": False,
        "paid_marking_performed": False,
        "runtime_execution_triggered": False,
        "send_authority_added": False,
        "used_ad_hoc_memory_as_authority": False,
        "text_response_only": True,
    }


def _answer_people_query(
    text: str,
    *,
    session: Mapping[str, Any] | None,
    source_surface: str,
    forwarded_session: Mapping[str, Any],
    protected_generate_fn: ProtectedGenerateFn | None,
    _capsule: Any | None = None,
    agent: str = "maestro",
) -> MaestroCassandraResult:
    registry_answer = _answer_people_query_from_contacts_registry(text)
    if registry_answer is not None:
        answer, proof = registry_answer
        return MaestroCassandraResult(
            status="ANSWER_READY",
            intent_class="people_reference_query",
            allowed_to_call_handle=False,
            one_line_answer=_one_line_answer(answer),
            plain_summary=answer,
            mac_render_hint=MAC_RENDER_HINT,
            session_forwarded=forwarded_session,
            machine_proof={
                **_adapter_machine_proof(handle_called=False),
                **proof,
                "people_reference_query_performed": True,
                "operator_truth_store_read": False,
                "operator_truth_record_found": False,
                "protected_generate_called": False,
                "maestro_context_packet_used": False,
                "external_llm_invoked": False,
            },
        )

    from operator_truth_store import find_operator_truth_for_text
    from probe_state_contract import validate_bound_probe_session

    truth_store_path = None
    if validate_bound_probe_session(session):
        truth_store_path = str((session or {}).get("operator_truth_store_path") or "") or None
    match = find_operator_truth_for_text(text, path=truth_store_path)
    if match is not None:
        entity_key, record = match
        label = str(record.get("label") or entity_key)
        value = " ".join(str(record.get("value") or "").split()).strip()
        answer = f"{label}: {value}" if value else f"I found {label}, but the truth record has no value."
        return MaestroCassandraResult(
            status="ANSWER_READY",
            intent_class="people_reference_query",
            allowed_to_call_handle=False,
            one_line_answer=_one_line_answer(answer),
            plain_summary=answer,
            mac_render_hint=MAC_RENDER_HINT,
            session_forwarded=forwarded_session,
            machine_proof={
                **_adapter_machine_proof(handle_called=False),
                "people_reference_query_performed": True,
                "contacts_registry_read": True,
                "contacts_registry_record_found": False,
                "operator_truth_store_read": True,
                "operator_truth_record_found": True,
                "operator_truth_entity_key": entity_key,
                "operator_truth_label": label,
                "protected_generate_called": False,
                "maestro_context_packet_used": False,
                "external_llm_invoked": False,
            },
        )

    fallback = _answer_with_maestro_brain(
        text,
        session=session,
        source_surface=source_surface,
        forwarded_session=forwarded_session,
        protected_generate_fn=protected_generate_fn,
        _capsule=_capsule,
        agent=agent,
    )
    proof = {
        **dict(fallback.machine_proof or {}),
        "people_reference_query_performed": True,
        "contacts_registry_read": True,
        "contacts_registry_record_found": False,
        "operator_truth_store_read": True,
        "operator_truth_record_found": False,
        "people_reference_fell_through_to_protected_generate": bool(
            (fallback.machine_proof or {}).get("protected_generate_called")
        ),
    }
    return MaestroCassandraResult(
        status=fallback.status,
        intent_class="people_reference_query",
        allowed_to_call_handle=False,
        one_line_answer=fallback.one_line_answer,
        plain_summary=fallback.plain_summary,
        mac_render_hint=fallback.mac_render_hint,
        route_to_staging_reason=fallback.route_to_staging_reason,
        session_forwarded=fallback.session_forwarded,
        machine_proof=proof,
    )


def _contacts_db_path() -> str:
    try:
        from contacts_registry import DEFAULT_CONTACTS_DB_PATH

        return os.environ.get("OPENCLAW_CONTACTS_DB_PATH") or DEFAULT_CONTACTS_DB_PATH
    except Exception:
        return os.environ.get("OPENCLAW_CONTACTS_DB_PATH") or ""


def _contact_text_key(value: Any) -> str:
    text = str(value or "").lower().replace("'", "")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _contact_query_client_slugs(text: str, contacts: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    query_key = f" {_contact_text_key(text)} "
    slugs: list[str] = []
    for contact in contacts:
        clients = contact.get("connected_clients") or contact.get("connected_client") or ()
        if isinstance(clients, str):
            clients = (clients,)
        for client in clients:
            slug = str(client or "").strip()
            if not slug:
                continue
            terms = {
                _contact_text_key(slug),
                _contact_text_key(slug.replace("-", " ")),
                _contact_text_key(slug.replace("-", "")),
            }
            if any(term and f" {term} " in query_key for term in terms) and slug not in slugs:
                slugs.append(slug)
    return tuple(slugs)


def _format_contact_for_people_answer(contact: Mapping[str, Any], *, client_slug: str) -> str:
    name = str(contact.get("name") or contact.get("id") or "Contact").strip()
    role = str(contact.get("role") or "contact").strip()
    return f"{name} ({role}; client: {client_slug})"


def _answer_people_query_from_contacts_registry(text: str) -> tuple[str, dict[str, Any]] | None:
    db_path = _contacts_db_path()
    proof: dict[str, Any] = {
        "contacts_registry_read": False,
        "contacts_registry_record_found": False,
        "contacts_registry_ref": f"contacts_registry:{db_path}" if db_path else "contacts_registry",
        "contacts_registry_client_slug": "",
        "contacts_registry_contact_ids": [],
    }
    try:
        from contacts_registry import ContactsRegistry

        registry = ContactsRegistry(db_path, seed=True)
        all_contacts = registry.list_contacts()
        proof["contacts_registry_read"] = True
        slugs = _contact_query_client_slugs(text, all_contacts)
        if not slugs:
            return None
        client_slug = slugs[0]
        contacts = registry.get_contacts_for_client(client_slug)
    except Exception as exc:
        proof["contacts_registry_error"] = str(exc)
        return None

    if not contacts:
        return None

    proof["contacts_registry_record_found"] = True
    proof["contacts_registry_client_slug"] = client_slug
    proof["contacts_registry_contact_ids"] = [str(contact.get("id") or "") for contact in contacts]
    contact_text = "; ".join(
        _format_contact_for_people_answer(contact, client_slug=client_slug)
        for contact in contacts
    )
    answer = f"Contacts registry for {client_slug}: {contact_text}."
    return answer, proof


def _answer_with_maestro_brain(
    text: str,
    *,
    session: Mapping[str, Any] | None,
    source_surface: str,
    forwarded_session: Mapping[str, Any],
    protected_generate_fn: ProtectedGenerateFn | None,
    _capsule: Any | None = None,
    agent: str = "maestro",
    intent_class: str = "maestro_brain_freeform",
) -> MaestroCassandraResult:
    introspection_match = (
        classify_agent_introspection(text, addressed_agent=agent)
        if intent_class == "agent_introspection"
        else None
    )
    introspection_facts = (
        normalize_turn_self_facts(
            agent=agent,
            source_request_id=str((session or {}).get("source_message_id") or ""),
            session=session,
        )
        if introspection_match is not None
        else None
    )
    reused_answer = ""
    reused_receipt: Mapping[str, Any] = {}
    if isinstance(session, Mapping):
        reused_answer = str(session.get("lm1_reused_answer") or "").strip()
        candidate_receipt = session.get("lm1_reused_model_receipt")
        if isinstance(candidate_receipt, Mapping):
            reused_receipt = candidate_receipt
    reused_external_receipt = reused_receipt.get(
        "external_brain_route_receipt"
    ) or reused_receipt.get("external_brain")
    reused_self_facts_delivered = bool(
        reused_receipt.get("turn_self_facts_in_prompt") is True
        or (
            isinstance(reused_external_receipt, Mapping)
            and reused_external_receipt.get("turn_self_facts_in_prompt") is True
        )
    )
    reuse_candidate = bool(
        reused_answer
        and reused_receipt.get("model_call_performed") is True
        and reused_receipt.get("original_message_present_in_submitted_prompt") is True
    )
    if intent_class == "agent_introspection":
        reuse_candidate = bool(
            reuse_candidate
            and introspection_match is not None
            and reused_self_facts_delivered
        )
    if reuse_candidate:
        answer_text = _strip_internal_state_leaks(reused_answer)
        reuse_grounding_gaps: tuple[str, ...] = ()
        reuse_final_facts = introspection_facts
        if introspection_match is not None:
            reuse_final_facts = normalize_turn_self_facts(
                agent=agent,
                source_request_id=str((session or {}).get("source_message_id") or ""),
                session=session,
                route_receipt=reused_receipt,
            )
            reuse_grounding_gaps = introspection_answer_grounding_gaps(
                answer_text,
                match=introspection_match,
                facts=reuse_final_facts,
            )
        if not reuse_grounding_gaps:
            reuse_introspection_proof = (
                {
                    "turn_self_facts": dict(reuse_final_facts or {}),
                    "turn_self_facts_delivered": True,
                    "answer_grounded_in_turn_self_facts": True,
                    "answer_grounding_missing_fields": (),
                }
                if introspection_match is not None
                else {}
            )
            return MaestroCassandraResult(
                status="ANSWER_READY",
                intent_class=intent_class,
                allowed_to_call_handle=False,
                one_line_answer=_one_line_answer(answer_text),
                plain_summary=answer_text,
                mac_render_hint=MAC_RENDER_HINT,
                session_forwarded=forwarded_session,
                machine_proof={
                    **_adapter_machine_proof(handle_called=False),
                    **_protected_generate_receipt_machine_proof(reused_receipt),
                    "protected_generate_called": True,
                    "maestro_context_packet_used": False,
                    "lm1_reused_for_lm2": True,
                    "workflow_package_staged": False,
                    "send_hold_boundary_visible": True,
                    **reuse_introspection_proof,
                },
            )

    packet_session = dict(session or {})
    packet_session["interpreter_route"] = "BRAIN"
    # ── INTERPRETER-LM fact selection bridge (flag-gated, ADDITIVE) ──────────
    # When OPENCLAW_INTERPRETER_LM is on AND the raw session carries an
    # "interpreter_fact_selection" hint (injected upstream by the interpreter
    # divert in openclaw_request_processor), forward it to the packet builder so
    # the interpreter-selected read-models are elevated. When the flag is OFF or
    # no hint is present: _fact_selection stays None → byte-identical pre-edit
    # behaviour. This is advisory-only ordering: it never drops or rewrites facts.
    _fact_selection = None
    try:
        from interpreter_lm import _interpreter_enabled

        if _interpreter_enabled() and isinstance(session, Mapping):
            _raw_selection = session.get("interpreter_fact_selection")
            if isinstance(_raw_selection, (list, tuple)) and _raw_selection:
                _fact_selection = [str(item) for item in _raw_selection if str(item).strip()]
    except Exception:  # noqa: BLE001 — never break the brain path on a hint
        _fact_selection = None
    # ─────────────────────────────────────────────────────────────────────────
    packet_engine_used = False
    packet_engine_fallback_used = False
    packet_engine_receipt: Mapping[str, Any] | None = None
    packet_engine_failure_type = ""
    try:
        from maestro_context_packet import build_maestro_context_packet

        # ── CONTINUITY CAPSULE threading (flag-gated, ADDITIVE) ──────────────
        # When ON and a capsule is provided, pass it to build_maestro_context_packet
        # so it can populate packet_entity_aliases + packet_source_revision (Edit 2).
        # When OFF or no capsule: call is identical to pre-edit (capsule=None default).
        _capsule_arg = _capsule if _continuity_enabled() else None
        if _packet_engine_enabled():
            try:
                from packet_engine import build_agent_packet

                context_packet = build_agent_packet(
                    agent=agent,
                    question=text,
                    question_class=intent_class,
                    authority={
                        "source_surface": source_surface,
                        "send_hold": True,
                    },
                    session=packet_session,
                    source_surface=source_surface,
                    require_real_truth=True,
                    capsule=_capsule_arg,
                    fact_selection=_fact_selection,
                    turn_self_facts=introspection_facts,
                )
                packet_engine_receipt = dict(context_packet.get("packet_engine_receipt") or {})
                failures = packet_engine_receipt.get("failures") or ()
                if context_packet.get("status") == "PACKET_ENGINE_BUILD_FAILED" or failures:
                    packet_engine_fallback_used = True
                    if failures:
                        first_failure = next(iter(failures), {})
                        if isinstance(first_failure, Mapping):
                            packet_engine_failure_type = str(first_failure.get("type") or "")
                    context_packet = build_maestro_context_packet(
                        question=text,
                        session=packet_session,
                        source_surface=source_surface,
                        require_real_truth=True,
                        capsule=_capsule_arg,
                        fact_selection=_fact_selection,
                    )
                else:
                    packet_engine_used = True
            except Exception as exc:  # noqa: BLE001 - fail open to old packet path
                packet_engine_fallback_used = True
                packet_engine_failure_type = type(exc).__name__
                try:
                    from packet_engine import build_fallback_receipt

                    packet_engine_receipt = build_fallback_receipt(
                        agent=agent,
                        question_class=intent_class,
                        failure=exc,
                    )
                except Exception:  # noqa: BLE001
                    packet_engine_receipt = None
                context_packet = build_maestro_context_packet(
                    question=text,
                    session=packet_session,
                    source_surface=source_surface,
                    require_real_truth=True,
                    capsule=_capsule_arg,
                    fact_selection=_fact_selection,
                )
        else:
            context_packet = build_maestro_context_packet(
                question=text,
                session=packet_session,
                source_surface=source_surface,
                require_real_truth=True,
                capsule=_capsule_arg,
                fact_selection=_fact_selection,
            )
    except Exception as exc:
        answer = (
            "I don't have a grounded Maestro packet for that yet. "
            "I will not invent the answer; Chief can review the missing truth input."
        )
        return MaestroCassandraResult(
            status="ANSWER_READY",
            intent_class=intent_class,
            allowed_to_call_handle=False,
            one_line_answer=_one_line_answer(answer),
            plain_summary=answer,
            mac_render_hint=MAC_RENDER_HINT,
            route_to_staging_reason=f"context_packet_unavailable:{type(exc).__name__}",
            session_forwarded=forwarded_session,
            machine_proof={
                **_adapter_machine_proof(handle_called=False),
                "maestro_context_packet_used": False,
                "protected_generate_called": False,
                "context_packet_error": type(exc).__name__,
                "external_llm_invoked": False,
                "local_model_invoked": False,
                "model_call_performed": False,
                "workflow_package_staged": False,
            },
        )

    if introspection_facts is not None and context_packet.get("turn_self_facts") is None:
        context_packet = inject_turn_self_facts(context_packet, introspection_facts)

    # ── PACKET-DELTA hook (flag-gated OPENCLAW_PACKET_DELTA, default off, FAIL-OPEN) ──
    # Integration point for cross-turn fact de-dup, keyed on the capsule's
    # (conversation_id, agent). KEEP OFF on this path — and here's the honest why:
    #   • The front-door local model is STATELESS: protected_generate builds the prompt
    #     fresh from this single packet every call and retains nothing between calls.
    #     So "drop_seen" would STARVE the model of facts it still needs each turn.
    #   • "prioritize" (the safe default) only reorders; build_frontdoor_prompt then
    #     re-ranks facts by relevance tier + lexical overlap, using original order only
    #     as a deep tiebreak — so the reorder is ~a no-op here. The live budgeter is
    #     already the real bloat control.
    # Packet-delta's real payoff is for STATEFUL consumers (sessions/agents that retain
    # prior turns). This hook stays wired (tested, fail-open) for that future; default off.
    try:
        from packet_delta import maybe_apply_packet_delta

        _conv_id = getattr(_capsule, "conversation_id", "") if _capsule is not None else ""
        _delta_agent = getattr(_capsule, "agent_id", "") or "maestro"
        context_packet, _delta_stats = maybe_apply_packet_delta(
            context_packet, conversation_id=_conv_id, agent=_delta_agent,
        )
        if _delta_stats.get("deduped"):
            print(f"[maestro] packet-delta: {_delta_stats}", flush=True)
    except Exception:  # noqa: BLE001 — never break the brain on the delta layer
        pass
    # ─────────────────────────────────────────────────────────────────────────

    weather_read_receipt: dict[str, Any] = {}
    try:
        from weather_read_capability import is_weather_request, read_weather

        if is_weather_request(text):
            weather = read_weather(text)
            weather_read_receipt = dict(weather.receipt)
            context_packet = dict(context_packet)
            context_packet["weather_read"] = {
                "status": weather.status,
                "location": weather.location,
                "summary": weather.summary,
            }
            weather_fact = {
                "fact_id": str(weather.receipt.get("receipt_id") or "weather-read"),
                "topic": "weather_current",
                "label": "Current weather read",
                "value": weather.summary,
                "provenance": "allowlisted_weather_get",
                "current_truth": weather.status == "READY",
            }
            context_packet["facts"] = [
                *list(context_packet.get("facts") or ()),
                weather_fact,
            ]
            weather_ref = str(weather.receipt.get("receipt_id") or "")
            if weather_ref:
                context_packet["source_refs"] = tuple(
                    dict.fromkeys(
                        [
                            *(
                                str(ref)
                                for ref in context_packet.get("source_refs", ())
                                if str(ref).strip()
                            ),
                            weather_ref,
                        ]
                    )
                )
            context_packet["packet_text"] = "\n".join(
                part
                for part in (
                    str(context_packet.get("packet_text") or "").strip(),
                    "WEATHER READ FOR THIS ANSWER:",
                    weather.summary,
                )
                if part
            )
    except Exception as exc:
        weather_read_receipt = {
            "status": "UNAVAILABLE",
            "error_type": type(exc).__name__,
            "network_performed": False,
            "external_action_performed": False,
        }

    if protected_generate_fn is None:
        from protected_generate import protected_generate_with_receipt
        from local_model_governance import interactive_model_from_session

        outcome = protected_generate_with_receipt(
            text,
            context_packet=context_packet,
            agent=agent,
            model_selected=interactive_model_from_session(session),
        )
    else:
        outcome = protected_generate_fn(text, context_packet=context_packet)

    if hasattr(outcome, "text") and hasattr(outcome, "receipt"):
        answer_text = str(outcome.text)
        receipt = dict(outcome.receipt)
    elif isinstance(outcome, Mapping):
        answer_text = str(outcome.get("text") or outcome.get("answer") or "")
        receipt = dict(outcome.get("receipt") or {})
    else:
        answer_text = str(outcome or "")
        receipt = {
            "status": "ANSWER_READY",
            "decision": "INJECTED_PROTECTED_GENERATE",
            "external_llm_invoked": False,
            "local_model_invoked": True,
            "model_call_performed": True,
        }
    if _receipt_or_packet_has_skill("music_law_advisory", receipt=receipt, context_packet=context_packet):
        try:
            from chief_musiclaw_brain import _ensure_musiclaw_safety

            answer_text = _ensure_musiclaw_safety(answer_text)
        except Exception:
            pass
    answer_text = _strip_internal_state_leaks(answer_text) or (
        "I don't have that in the current Maestro packet."
    )
    answer_text = _enforce_answer_topic_presentation(answer_text, context_packet)
    canned_status_mismatch_blocked = False
    if _is_canned_status_answer(answer_text) and not _explicitly_requests_status(text):
        answer_text = (
            "I couldn't route that question to a grounded answer. "
            "I will not substitute an unrelated status readback; nothing else ran."
        )
        canned_status_mismatch_blocked = True
    # ── SELF-IMPROVEMENT LOOP ─────────────────────────────────────────────────
    # If the operator just agreed to an improvement the agent recommended last turn, file it
    # as a REAL build request (-> PROPOSED + Guardian). Otherwise, if they're talking about
    # the agent / its improvements, record the one concrete gap so a "yeah do it" next turn
    # files it. Grounded (only curated gaps file) + fail-open.
    try:
        _conv_id = getattr(_capsule, "conversation_id", "") if _capsule is not None else ""
        if _conv_id:
            from self_improvement_request import maybe_file_on_agreement, record_recommendation

            _filed = maybe_file_on_agreement(_conv_id, text, agent=agent)
            if _filed and _filed.get("filed"):
                answer_text = (answer_text.rstrip() +
                               " — on it; I've put that in, you'll get a Guardian approval to build it.")
            else:
                from social_intent import is_self_referential

                if is_self_referential(text):
                    from self_knowledge import next_improvement

                    _nxt = next_improvement()
                    if _nxt:
                        record_recommendation(_conv_id, _nxt["id"])
    except Exception:
        pass
    # NOTE: jargon teaching + comedy-as-diagnostic + claim detection were CONSOLIDATED into the
    # single author-aware operator-surface pipeline (_enrich_operator_surface in
    # openclaw_request_processor) so EVERY agent voice gets them on the FINAL operator_message —
    # not just this Maestro brain path. They no longer run here (would double-process the surface).
    # Live dankifier hook: score the packet just used + queue grounded gaps, so the system
    # gets danker the more it's used. Never blocks or alters the answer (already finalized
    # above) — observe_packet_dankness swallows all errors; enrichment runs in a separate drain.
    try:
        from packet_dankness_critic import observe_packet_dankness

        # COVERAGE: observe as the ACTUAL agent being answered (was hardcoded "maestro", which made
        # the dankifier loop churn on maestro alone and never enrich the other 5 agents' packets).
        if not isinstance(receipt.get("packet_dankness"), Mapping):
            observe_packet_dankness(context_packet, text, agent)
    except Exception:
        pass
    # Defense-in-depth (persona-voice layer): flag if any machine-contract leaked past the
    # strip above. Observability only — never alters or blocks the reply. Surfaces strip gaps.
    try:
        from operator_surface_guard import check_machine_contract_leak

        _leak = check_machine_contract_leak(answer_text, audience="ELIWINSHIP")
        if _leak.is_leak:
            print(f"[maestro] operator-surface leak survived strip: {_leak.reasons}", flush=True)
    except Exception:
        pass
    # (Claim detection now runs centrally in _enrich_operator_surface on the FINAL operator_message
    # for every agent — see the consolidation note above.)
    from local_model_governance import binding_from_session
    from secret_log_redaction import redact_secrets

    model_binding = binding_from_session(session)
    receipt_message = redact_secrets(text)
    input_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
    answer_model = str(
        receipt.get("model_selected")
        or receipt.get("model_id")
        or receipt.get("model")
        or model_binding.get("model")
        or ""
    )
    answer_pass_receipt = {
        "pass": "answer",
        "original_operator_message": receipt_message,
        "secret_tokenization_applied": receipt_message != text,
        "input_sha256": input_sha256,
        "binding_id": str(model_binding.get("binding_id") or ""),
        "model": answer_model,
        "packet_id": str(context_packet.get("packet_id") or ""),
        "receipt_id": str(receipt.get("receipt_id") or ""),
    }
    proof_refs = tuple(str(ref) for ref in context_packet.get("source_refs", ()) if str(ref).strip())
    packet_engine_proof = _packet_engine_delivery_proof(
        context_packet=context_packet,
        receipt=packet_engine_receipt,
        used=packet_engine_used,
        fallback_used=packet_engine_fallback_used,
        failure_type=packet_engine_failure_type,
    )
    introspection_proof: dict[str, Any] = {}
    if introspection_match is not None:
        final_introspection_facts = normalize_turn_self_facts(
            agent=agent,
            source_request_id=str((session or {}).get("source_message_id") or ""),
            session=session,
            route_receipt=receipt,
        )
        answer_grounding_gaps = introspection_answer_grounding_gaps(
            answer_text,
            match=introspection_match,
            facts=final_introspection_facts,
        )
        original_message_included = bool(
            receipt.get("original_message_present_in_submitted_prompt") is True
            or receipt.get("original_message_present_in_prompt") is True
        )
        if not original_message_included:
            answer_grounding_gaps = tuple(
                dict.fromkeys((*answer_grounding_gaps, "original_message"))
            )
        answer_grounded = not answer_grounding_gaps
        if not answer_grounded:
            answer_text = (
                "My generated self-report did not match this turn's machine proof, "
                "so I am not presenting it as fact."
            )
        introspection_proof = {
            "turn_self_facts": final_introspection_facts,
            "turn_self_facts_delivered": bool(context_packet.get("turn_self_facts")),
            "answer_grounded_in_turn_self_facts": answer_grounded,
            "answer_grounding_missing_fields": answer_grounding_gaps,
        }
    return MaestroCassandraResult(
        status="ANSWER_READY",
        intent_class=intent_class,
        allowed_to_call_handle=False,
        one_line_answer=_one_line_answer(answer_text),
        plain_summary=answer_text,
        mac_render_hint=MAC_RENDER_HINT,
        session_forwarded=forwarded_session,
        machine_proof={
            **_adapter_machine_proof(handle_called=False),
            **_protected_generate_receipt_machine_proof(receipt),
            "protected_generate_called": True,
            "maestro_context_packet_used": True,
            "context_packet_id": str(context_packet.get("packet_id") or ""),
            "proof_refs": proof_refs,
            "source_truth_refs": proof_refs,
            "protected_generate_receipt_id": str(receipt.get("receipt_id") or ""),
            "protected_generate_audit_ref": str(receipt.get("audit_ref") or ""),
            "protected_generate_decision": str(receipt.get("decision") or ""),
            "local_model_binding": model_binding,
            "internal_model_pass_receipts": {"answer": answer_pass_receipt},
            "weather_read_receipt": weather_read_receipt,
            "workflow_package_staged": False,
            "send_hold_boundary_visible": True,
            "claims_trace_to_packet": True,
            "canned_status_mismatch_blocked": canned_status_mismatch_blocked,
            # Interpreter-LM traceability (advisory only — None/empty when off):
            "interpreter_fact_selection_applied": list(_fact_selection or []),
            "interpreter_fact_selection_used": bool(_fact_selection),
            **packet_engine_proof,
            **introspection_proof,
        },
    )


def build_hermes_truthful_advisory_answer(text: str) -> dict[str, Any]:
    normalized = _normalize(text)
    mode = _hermes_truthful_mode(normalized)
    target = _route_target(normalized)
    target_candidate = _route_target_candidate(normalized)
    base_proof = {
        "hermes_truthful_advisory_performed": True,
        "hermes_reply_mode": mode,
        "hermes_real_agent_bridge_available": False,
        "hermes_route_receipt_written": False,
        "hermes_local_helpers_are_not_agent_bridges": True,
        "hermes_skill_guess_performed": False,
        "hermes_gateway_started": False,
        "agent_dispatch_performed": False,
        "worker_dispatch_performed": False,
        "email_send_performed": False,
        "external_send_performed": False,
        "send_hold_boundary_visible": True,
        "source_truth_refs": (
            ".claude/commands/hermes.md",
            "openclaw_hermes_sidecar.py",
            "templates/agent/hermes_advisory_packet_template.json",
        ),
    }
    if mode == "route_request":
        target_label = target or target_candidate or "the requested agent"
        one_line = f"Hermes cannot route this to {target_label} from this surface."
        detail = (
            "That route target is not a canonical OpenClaw agent route."
            if not target and target_candidate
            else "Hermes is advisory here: it can describe adapter/protocol boundaries and recommend a safe review packet."
        )
        plain = "\n".join(
            [
                one_line,
                detail,
                "No agent handoff ran, no route receipt was written, and no message was sent.",
                "A real handoff needs a sanctioned bridge with a receipt; local helper tools are not agent bridges.",
                "SEND_HOLD remains in force.",
            ]
        )
        base_proof["requested_route_target"] = target_label
        base_proof["requested_route_target_is_canonical_agent"] = bool(target)
    elif mode == "send_money_denial":
        one_line = "Hermes cannot send messages, trigger payments, or move money from this surface."
        plain = "\n".join(
            [
                one_line,
                "This request is denied for live action and can only be staged for an operator-controlled review path.",
                "No external send, payment, ledger mutation, route receipt, service start, or agent dispatch occurred.",
                "SEND_HOLD remains in force.",
            ]
        )
        base_proof["requested_route_target"] = target_candidate or ""
        base_proof["requested_route_target_is_canonical_agent"] = False
    elif mode == "route_inventory":
        one_line = "Hermes has no proven live agent-routing bridge from this surface."
        plain = "\n".join(
            [
                one_line,
                "Real agent bridges available to Hermes here: none proven.",
                "Local helper tools and read-model sidecars may support advisory review, but they are not dispatch routes.",
                "Hermes can recommend or stage an advisory packet; it cannot send, enqueue, start services, or bypass SEND_HOLD.",
                "SEND_HOLD remains in force.",
            ]
        )
    else:
        one_line = "Hermes is an advisory boundary reviewer, not a live routing or send gateway."
        plain = "\n".join(
            [
                one_line,
                "Current scope: adapter/protocol boundary review, bridge posture, connector wrapper readiness, sidecar inventory, and authority-fit checks.",
                "Hard no: no external send, Gmail/Coupa/browser access, ledger/workbook/PDF mutation, service start, model-provider fallback, or agent dispatch from this surface.",
                "Hermes can describe or recommend a bounded review packet; Chief/operator-controlled promotion is required for any action.",
                "SEND_HOLD remains in force.",
            ]
        )
    # Hermes context packet — grounded posture facts (canonical route targets, blocked
    # output kinds, SEND_HOLD posture, authority flags hard-False) from real config.
    # READ-ONLY, additive; adds no send/execute capability. Failures silently skipped.
    try:
        from hermes_context_packet import build_hermes_context_packet
        _hpt = str(build_hermes_context_packet(question=text).get("packet_text") or "").strip()
    except Exception:
        _hpt = ""
    if _hpt:
        if len(_hpt) > 900:  # keep the operator reply under the Telegram cap
            _hpt = _hpt[:900].rstrip() + " …"
        plain = f"{plain}\n\n{_hpt}"
        base_proof["hermes_context_packet_used"] = True
    return {
        "one_line_answer": _one_line_answer(one_line),
        "plain_summary": _strip_internal_state_leaks(plain),
        "machine_proof": base_proof,
    }


_BARE_STATUS_PHRASES = frozenset(
    {
        "status",
        "status update",
        "status check",
        "status please",
        "quick status",
        "whats the status",
        "what is the status",
        "give me a status",
        "give me a status update",
    }
)


def _is_bare_status_query(text: str) -> bool:
    """Task 143: a bare status ask ("status?", "what's the status") -- distinct from the
    longer capability-transparency phrasing that routes to status_capability_readback."""
    stripped = str(text or "").strip().rstrip("?!.").strip()
    normalized = _normalize(stripped).replace("'", "")
    return normalized in _BARE_STATUS_PHRASES


def _is_canned_status_answer(text: str) -> bool:
    normalized = " ".join(str(text or "").strip().lower().split())
    return normalized.startswith("fleet:") and "agents online" in normalized


def _explicitly_requests_status(text: str) -> bool:
    normalized = _normalize(text)
    return bool(
        _is_bare_status_query(text)
        or _is_status_capability_intent(normalized)
        or _is_system_health_readback_intent(normalized)
    )


def _read_model_stale_days(payload: Mapping[str, Any]) -> int | None:
    """Return the age in days of a read-model's own generated_at/as_of timestamp, or None
    when no timestamp is present (caller should treat unknown as "cannot verify freshness",
    not as fresh)."""
    from read_model_freshness_audit import _parse_date, _timestamp_from_payload, _today

    if not payload:
        return None
    parsed = _parse_date(_timestamp_from_payload(payload))
    if parsed is None:
        return None
    return (_today() - parsed).days


def build_maestro_bare_status_answer(*, session: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Task 143 (CLASS #4): terse, current, Maestro-scoped bare-status readback -- 2-4 short
    lines built deterministically from live read-models (no model call). Stale sources are
    flagged rather than presented as current (STALENESS RULE)."""
    root = _read_model_root_from_session(session)
    helm_payload, helm_path = _read_json_read_model(root, HELM_ATTENTION_READ_MODEL)
    receivables_payload, receivables_path = _read_json_read_model(root, RECEIVABLES_MONTH_BOUNDED_READ_MODEL)
    presence_payload, presence_path = _read_json_read_model(root, AGENT_PRESENCE_READ_MODEL)

    lines: list[str] = []
    proof_refs: list[str] = []
    freshness_excluded_sources: list[str] = []
    stale_sources: list[str] = []
    unverifiable_sources: list[str] = []

    def _usability(payload: Mapping[str, Any]) -> tuple[bool, str]:
        """Return ``(usable, exclusion_reason)`` for a present read model.

        Missing/empty payloads have nothing to flag. A present payload without a
        parseable source timestamp is unverifiable, never implicitly fresh.
        """
        if not payload:
            return False, ""
        days = _read_model_stale_days(payload)
        if days is None:
            return False, "unverifiable"
        if days > BARE_STATUS_FRESHNESS_SLA_DAYS:
            return False, "stale"
        return True, ""

    def _record_exclusion(source: str, reason: str) -> None:
        if not reason:
            return
        freshness_excluded_sources.append(source)
        if reason == "stale":
            stale_sources.append(source)
        else:
            unverifiable_sources.append(source)

    helm_usable, helm_exclusion = _usability(helm_payload)
    if helm_usable:
        plate_count = len(helm_payload.get("primary_cards") or ())
        lines.append(f"Plate: {plate_count} headline item{'s' if plate_count != 1 else ''}.")
        proof_refs.append(helm_path.as_posix())
    else:
        _record_exclusion(HELM_ATTENTION_READ_MODEL, helm_exclusion)

    receivables_usable, receivables_exclusion = _usability(receivables_payload)
    if receivables_usable:
        open_by_client = receivables_payload.get("summary", {}).get("open_minor_units_by_client", {})
        open_count = sum(1 for amount in open_by_client.values() if isinstance(amount, (int, float)) and amount > 0)
        lines.append(f"Money: {open_count} client{'s' if open_count != 1 else ''} with open amounts.")
        proof_refs.append(receivables_path.as_posix())
    else:
        _record_exclusion(RECEIVABLES_MONTH_BOUNDED_READ_MODEL, receivables_exclusion)

    presence_usable, presence_exclusion = _usability(presence_payload)
    if presence_usable:
        online = presence_payload.get("online_count")
        total = presence_payload.get("agent_count")
        lines.append(f"Fleet: {online}/{total} agents online.")
        proof_refs.append(presence_path.as_posix())
    else:
        _record_exclusion(AGENT_PRESENCE_READ_MODEL, presence_exclusion)

    if not lines:
        lines.append(
            "I don't have current status data to report -- the usual read models are missing, stale, or unverifiable."
        )
    if freshness_excluded_sources:
        # ── Task 174 (per Task 164 human-alias doctrine): the operator-visible
        # note shows a COUNT, never raw internal source filenames
        # ("helm_operator_attention_package.json" is machine vocabulary — the
        # MT1/MT2 filename leak). Exact source names stay in the receipt
        # channel below (machine_proof.freshness_excluded_sources et al.).
        _excluded_count = len(freshness_excluded_sources)
        lines.append(
            f"({_excluded_count} stale source{'s' if _excluded_count != 1 else ''} excluded)"
        )
    plain = "\n".join(lines)

    return {
        "one_line_answer": _one_line_answer(plain),
        "plain_summary": plain,
        "machine_proof": {
            "maestro_bare_status_readback_performed": True,
            "source_truth_refs": tuple(proof_refs),
            # Backward-compatible aggregate: this historical key represents
            # every source excluded by the freshness gate, including undated
            # sources that cannot be verified as fresh.
            "stale_sources_excluded": tuple(freshness_excluded_sources),
            "freshness_excluded_sources": tuple(freshness_excluded_sources),
            "actually_stale_sources_excluded": tuple(stale_sources),
            "unverifiable_sources_excluded": tuple(unverifiable_sources),
            "external_llm_invoked": False,
            "protected_generate_called": False,
            "workflow_package_staged": False,
        },
    }


def build_ledger_capability_answer(
    *,
    ledger_path: str | Path | None = None,
) -> dict[str, Any]:
    """Answer built-vs-on from the canonical ledger mirror without a model or runtime probe."""

    path = Path(ledger_path or DEFAULT_CAPABILITY_LEDGER_PATH)
    rows: list[sqlite3.Row] = []
    if path.is_file():
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            has_table = conn.execute(
                "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='capability_activations'"
            ).fetchone()[0] == 1
            if has_table:
                rows = conn.execute(
                    "SELECT * FROM capability_activations ORDER BY machine, capability_id"
                ).fetchall()
        finally:
            conn.close()
    registered = [row for row in rows if str(row["register_stage"]) != "unregistered"]
    artifact_present = [row for row in registered if row["artifact_present"] == 1]
    artifact_unknown = [row for row in registered if row["artifact_present"] is None]
    configured = [row for row in rows if row["configured"] == 1]
    running = [
        row
        for row in rows
        if row["runtime_confirmed"] == 1 and str(row["runtime_state"]) == "running"
    ]
    running_unregistered = [row for row in running if str(row["register_stage"]) == "unregistered"]
    authorized = [row for row in rows if row["authority_granted"] == 1]
    drifted = [row for row in rows if row["drift_flag"] == 1]
    running_by_machine = {
        machine: sum(1 for row in running if str(row["machine"]) == machine)
        for machine in ("pc", "mac")
    }

    def _noun(count: int, singular: str, plural: str | None = None) -> str:
        return singular if count == 1 else (plural or singular + "s")

    if not rows:
        one_line = "Ledger-only capability readback is unavailable because the capability mirror has no rows."
        plain = one_line
    else:
        one_line = (
            "Ledger-only capability readback: "
            f"{len(artifact_present)} registered {_noun(len(artifact_present), 'artifact')} "
            f"{_noun(len(artifact_present), 'is', 'are')} present, "
            f"{len(running)} runtime {_noun(len(running), 'row')} "
            f"{_noun(len(running), 'is', 'are')} confirmed on, and "
            f"{len(running_unregistered)} running {_noun(len(running_unregistered), 'row')} "
            f"{_noun(len(running_unregistered), 'is', 'are')} unregistered."
        )
        lines = [
            one_line,
            f"Configured rows: {len(configured)}. Capability activation authority recorded: {len(authorized)}.",
            f"Confirmed on by machine: PC {running_by_machine['pc']}; Mac {running_by_machine['mac']}.",
            f"Registered artifact proof unknown: {len(artifact_unknown)}. Drifted rows: {len(drifted)}.",
        ]
        bridge_rows = [row for row in rows if str(row["capability_id"]) == "runtime.bridge.openclaw-e"]
        if bridge_rows:
            try:
                health = json.loads(str(bridge_rows[0]["health_json"] or "{}"))
            except json.JSONDecodeError:
                health = {}
            if health:
                lines.append(
                    "Mac bridge: "
                    f"mount {'confirmed' if health.get('mount_present') else 'not confirmed'}, "
                    f"{health.get('free_gib', 'unknown')} GiB free, "
                    f"{health.get('used_percent', 'unknown')}% used."
                )
        plain = "\n".join(lines)
    return {
        "one_line_answer": _one_line_answer(one_line),
        "plain_summary": plain,
        "machine_proof": {
            "status_capability_readback_performed": True,
            "capability_ledger_only": True,
            "capability_activations_used": bool(rows),
            "capability_activation_row_count": len(rows),
            "registered_artifact_present_count": len(artifact_present),
            "registered_artifact_unknown_count": len(artifact_unknown),
            "configured_count": len(configured),
            "runtime_confirmed_count": len(running),
            "running_unregistered_count": len(running_unregistered),
            "authority_granted_count": len(authorized),
            "drift_count": len(drifted),
            "source_truth_refs": (f"{path}#capability_activations",),
            "read_model_used": False,
            "runtime_collection_performed": False,
            "protected_generate_called": False,
            "external_llm_invoked": False,
            "external_send_performed": False,
            "runtime_execution_triggered": False,
        },
    }


def build_truthful_status_capability_answer(
    *,
    session: Mapping[str, Any] | None = None,
    focus: str = "status",
) -> dict[str, Any]:
    root = _read_model_root_from_session(session)
    capability_payload, capability_path = _read_json_read_model(root, CAPABILITY_INDEX_READ_MODEL)
    presence_payload, presence_path = _read_json_read_model(root, AGENT_PRESENCE_READ_MODEL)
    chief_payload, chief_path = _read_json_read_model(root, CHIEF_STATUS_READ_MODEL)
    readback_focus = _normalize_readback_focus(focus)

    freshness_excluded_sources: list[str] = []
    stale_sources: list[str] = []
    unverifiable_sources: list[str] = []

    def _age_gate(payload: Mapping[str, Any], source: str) -> dict[str, Any]:
        if not payload:
            return {}
        days = _read_model_stale_days(payload)
        if days is None:
            freshness_excluded_sources.append(source)
            unverifiable_sources.append(source)
            return {}
        if days > BARE_STATUS_FRESHNESS_SLA_DAYS:
            freshness_excluded_sources.append(source)
            stale_sources.append(source)
            return {}
        return dict(payload)

    capability_payload = _age_gate(capability_payload, CAPABILITY_INDEX_READ_MODEL)
    presence_payload = _age_gate(presence_payload, AGENT_PRESENCE_READ_MODEL)
    chief_payload = _age_gate(chief_payload, CHIEF_STATUS_READ_MODEL)

    capabilities = [
        row
        for row in capability_payload.get("generic_capabilities", ())
        if isinstance(row, Mapping)
    ]
    live_capabilities = [
        row
        for row in capabilities
        if str(row.get("capability_status") or "") == "LIVE_IMPLEMENTED"
    ]
    nonexecuting_capabilities = [
        row
        for row in capabilities
        if str(row.get("capability_status") or "") in {"IMPLEMENTED_NON_EXECUTING", "READ_MODEL_ONLY"}
    ]
    blocked_or_future = [
        row
        for row in capabilities
        if str(row.get("capability_status") or "")
        in {"CONTRACT_ONLY", "FUTURE_GATED", "BLOCKED_UNSAFE", "PROPOSED_CANDIDATE"}
    ]
    agents = [
        row
        for row in presence_payload.get("agents", ())
        if isinstance(row, Mapping)
    ]
    online_agents = [
        row
        for row in agents
        if str(row.get("actual_state") or "").lower() == "online"
    ]
    roster_entries = _agent_roster_entries(agents, limit=8)
    next_safe_move = _next_safe_move(presence_payload, agents)
    proof_refs = tuple(
        path.as_posix()
        for payload, path in (
            (capability_payload, capability_path),
            (presence_payload, presence_path),
            (chief_payload, chief_path),
        )
        if payload
    )

    if not capability_payload:
        one_line = (
            "I cannot truthfully list capabilities yet because a current capability index "
            "read model is unavailable."
        )
        lines = [
            one_line,
            "",
            "I will not invent a capability list. Ask again after `generated/read_models/openclaw_capability_index.json` is present and freshness-verifiable.",
        ]
        if freshness_excluded_sources:
            lines.append(
                "Stale or unverifiable sources excluded: "
                f"{', '.join(freshness_excluded_sources)}."
            )
        plain = "\n".join(lines)
    else:
        online_phrase = (
            f"{len(online_agents)} agents are online in the presence read model"
            if presence_payload
            else "agent presence is unverified in this readback"
        )
        live_names = _capability_names(live_capabilities, limit=5)
        nonexec_names = _capability_names(nonexecuting_capabilities, limit=5)
        blocked_names = _capability_names(blocked_or_future, limit=4)
        chief_summary = _chief_status_summary(chief_payload)
        one_line = _status_capability_one_line(
            readback_focus=readback_focus,
            online_phrase=online_phrase,
            live_count=len(live_capabilities),
            nonexecuting_count=len(nonexecuting_capabilities),
            live_names=live_names,
            roster_entries=roster_entries,
            next_safe_move=next_safe_move,
        )
        lines = [
            "Here is the truthful readback from current generated state.",
            "",
            f"- Status: {online_phrase}.",
            f"- Proven live-implemented rails: {_join_names(live_names)}.",
            f"- Safe non-executing readback rails: {_join_names(nonexec_names)}.",
        ]
        if freshness_excluded_sources:
            lines.append(
                "- Stale or unverifiable sources excluded: "
                f"{', '.join(freshness_excluded_sources)}."
            )
        if roster_entries:
            lines.append(f"- Agent roster: {_join_names(roster_entries)}.")
        if next_safe_move:
            lines.append(f"- Next safe move: {next_safe_move}.")
        if chief_summary:
            lines.append(f"- Chief: {chief_summary}.")
        if blocked_names:
            lines.append(f"- Not claimed as usable here: {_join_names(blocked_names)}.")
        lines.extend(
            [
                "- From this chat, I can answer status and capability questions from those read models.",
                "- I cannot claim email send, Gmail read, browser/Coupa access, workflow execution, deploy, restart, merge, payment, or ledger mutation from this front door.",
                f"- Proof refs: {_join_names(proof_refs)}.",
            ]
        )
        plain = "\n".join(lines)

    return {
        "one_line_answer": _one_line_answer(one_line),
        "plain_summary": plain,
        "machine_proof": {
            "status_capability_readback_performed": True,
            "readback_focus": readback_focus,
            "capability_index_used": bool(capability_payload),
            "agent_presence_used": bool(presence_payload),
            "agent_roster_summarized": bool(roster_entries),
            "chief_status_rail_used": bool(chief_payload),
            "source_truth_refs": proof_refs,
            "freshness_excluded_sources": tuple(freshness_excluded_sources),
            # Keep the established aggregate name aligned with bare status:
            # undated sources are freshness-excluded even though the precise
            # reason is recorded separately below.
            "stale_sources_excluded": tuple(freshness_excluded_sources),
            "actually_stale_sources_excluded": tuple(stale_sources),
            "unverifiable_sources_excluded": tuple(unverifiable_sources),
            "freshness_sla_days": BARE_STATUS_FRESHNESS_SLA_DAYS,
            "live_implemented_capability_count": len(live_capabilities),
            "nonexecuting_capability_count": len(nonexecuting_capabilities),
            "blocked_or_future_capability_count": len(blocked_or_future),
            "live_implemented_capability_ids": tuple(
                str(row.get("capability_id") or "") for row in live_capabilities
            ),
            "nonexecuting_capability_ids": tuple(
                str(row.get("capability_id") or "") for row in nonexecuting_capabilities
            ),
            "blocked_or_future_capability_ids_not_claimed": tuple(
                str(row.get("capability_id") or "") for row in blocked_or_future
            ),
            "capability_claims_derived_from_read_models": True,
            "unverified_capability_claims_filtered": True,
            "external_send_performed": False,
            "runtime_execution_triggered": False,
        },
    }


def build_chief_system_health_answer(
    *,
    session: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    root = _read_model_root_from_session(session)
    presence_payload, presence_path = _read_json_read_model(root, AGENT_PRESENCE_READ_MODEL)
    chief_payload, chief_path = _read_json_read_model(root, CHIEF_STATUS_READ_MODEL)
    sync_payload, sync_path = _read_json_read_model(root, SYNC_HEALTH_READ_MODEL)

    agents = [
        row
        for row in presence_payload.get("agents", ())
        if isinstance(row, Mapping)
    ]
    agent_lines: list[str] = []
    online_agents: list[str] = []
    degraded_or_offline: list[str] = []
    for row in agents:
        agent_id = str(row.get("agent_id") or row.get("display_name") or "unknown").strip()
        display = str(row.get("display_name") or agent_id).strip()
        state = str(row.get("actual_state") or "unknown").strip().lower() or "unknown"
        label = agent_id or display
        if state == "online":
            online_agents.append(label)
        elif state != "metadata_available":
            degraded_or_offline.append(f"{label}:{state}")
        agent_lines.append(f"{display}: {state}")

    total_agents = int(presence_payload.get("agent_count") or len(agents) or 0)
    online_count = int(presence_payload.get("online_count") or len(online_agents) or 0)
    chief_status = str(chief_payload.get("chief_current_status") or chief_payload.get("rail_status") or "unknown").strip()
    chief_summary = _chief_status_summary(chief_payload) or "Chief status rail unavailable"
    mirror_status = str(sync_payload.get("mirror_status") or "unknown").strip()
    display_status = str(sync_payload.get("display_status") or "unknown").strip()
    trust_status = str(sync_payload.get("trust_status") or "unknown").strip()
    last_mac = sync_payload.get("last_mac_completion") if isinstance(sync_payload.get("last_mac_completion"), Mapping) else {}
    last_mac_time = str(last_mac.get("time") or "").strip()
    last_mac_status = str(last_mac.get("status") or "").strip()

    source_refs = tuple(
        path.as_posix()
        for payload, path in (
            (presence_payload, presence_path),
            (chief_payload, chief_path),
            (sync_payload, sync_path),
        )
        if payload
    )
    one_line = (
        f"Chief system health: front door={chief_status or 'unknown'}; "
        f"agent response stack={online_count}/{total_agents} online; "
        f"sync mirror={mirror_status}, display={display_status}."
    )
    lines = [
        "Chief system health readback from current read models.",
        f"- Front door: {chief_summary}.",
        f"- Agent response stack: {_join_names(agent_lines)}.",
        f"- Sync: mirror={mirror_status}, display={display_status}, trust={trust_status}.",
    ]
    if last_mac_time:
        lines.append(f"- Last Mac sync: {last_mac_time} ({last_mac_status or 'unknown'}).")
    if degraded_or_offline:
        lines.append(f"- Degraded/offline agents: {_join_names(degraded_or_offline)}.")
    lines.extend(
        [
            "- Sources: " + _join_names(source_refs) + ".",
            "- Boundaries: no model call, no send, no repair, no restart, no dispatch, no ledger mutation.",
        ]
    )
    return {
        "one_line_answer": _one_line_answer(one_line),
        "plain_summary": "\n".join(lines),
        "machine_proof": {
            "system_health_readback_performed": True,
            "agent_presence_used": bool(presence_payload),
            "chief_status_rail_used": bool(chief_payload),
            "sync_health_used": bool(sync_payload),
            "source_truth_refs": source_refs,
            "online_agent_count": online_count,
            "agent_count": total_agents,
            "online_agents": tuple(online_agents),
            "degraded_or_offline_agents": tuple(degraded_or_offline),
            "frontdoor_status": chief_status,
            "sync_mirror_status": mirror_status,
            "sync_display_status": display_status,
            "protected_generate_called": False,
            "model_call_performed": False,
            "local_model_invoked": False,
            "external_llm_invoked": False,
            "maestro_context_packet_used": False,
            "runtime_execution_triggered": False,
            "agent_dispatch_performed": False,
        },
    }


def _read_model_root_from_session(session: Mapping[str, Any] | None) -> Path:
    if isinstance(session, Mapping):
        for key in ("read_model_root", "read_model_root_path", "generated_read_model_root"):
            value = session.get(key)
            if isinstance(value, str) and value.strip():
                return Path(value)
    return DEFAULT_READ_MODEL_ROOT


def _read_json_read_model(root: Path, filename: str) -> tuple[dict[str, Any], Path]:
    path = root / filename
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, path
    return (payload if isinstance(payload, dict) else {}), path


def _capability_names(rows: Sequence[Mapping[str, Any]], *, limit: int) -> tuple[str, ...]:
    names = [
        str(row.get("capability_name") or row.get("capability_id") or "").strip()
        for row in rows
        if str(row.get("capability_name") or row.get("capability_id") or "").strip()
    ]
    return tuple(names[:limit])


def _join_names(names: Sequence[str]) -> str:
    return ", ".join(str(name) for name in names if str(name).strip()) or "none verified"


def _normalize_readback_focus(focus: str) -> str:
    normalized = _normalize(focus).replace("-", "_").replace(" ", "_")
    if normalized in {"capability", "capabilities"}:
        return "capability"
    if normalized in {"agent_roster", "agents", "roster"}:
        return "agent_roster"
    if normalized in {"next_safe_move", "safe_move", "next_move"}:
        return "next_safe_move"
    return "status"


def _agent_roster_entries(rows: Sequence[Mapping[str, Any]], *, limit: int) -> tuple[str, ...]:
    entries: list[str] = []
    for row in rows:
        display = str(row.get("display_name") or row.get("agent_id") or "").strip()
        if not display:
            continue
        state = str(row.get("actual_state") or "unknown").strip() or "unknown"
        lane = str(row.get("lane_id") or "").strip()
        role = str(row.get("role") or row.get("reason") or "").strip()
        details = "; ".join(part for part in (state, lane, role) if part)
        entries.append(f"{display} ({details})" if details else display)
        if len(entries) >= limit:
            break
    return tuple(entries)


def _next_safe_move(
    presence_payload: Mapping[str, Any],
    agents: Sequence[Mapping[str, Any]],
) -> str:
    top_level = str(presence_payload.get("next_safe_move") or "").strip()
    if top_level:
        return top_level.rstrip(".")
    for row in agents:
        move = str(row.get("next_safe_move") or "").strip()
        if move and move.lower() != "no recovery needed.":
            return move.rstrip(".")
    return "Use the readback rails only; no runtime action is authorized from this front door"


def _status_capability_one_line(
    *,
    readback_focus: str,
    online_phrase: str,
    live_count: int,
    nonexecuting_count: int,
    live_names: Sequence[str],
    roster_entries: Sequence[str],
    next_safe_move: str,
) -> str:
    if readback_focus == "agent_roster":
        return f"Agent roster: {_join_names(roster_entries)}."
    if readback_focus == "next_safe_move":
        return f"Next safe move: {next_safe_move}."
    if readback_focus == "capability":
        return (
            f"I can help with truthful readbacks such as {_join_names(live_names)}; "
            "sends, Gmail, calendar, browser, deploy, and workflow actions stay gated."
        )
    return (
        f"OpenClaw status: {online_phrase}; "
        f"{live_count} live-implemented rails and "
        f"{nonexecuting_count} non-executing readback rails are listed."
    )


def _chief_status_summary(payload: Mapping[str, Any]) -> str:
    if not payload:
        return ""
    status = str(payload.get("chief_current_status") or payload.get("rail_status") or "").strip()
    role = payload.get("chief_current_proven_role")
    role_summary = str(role.get("role_summary") or "").strip() if isinstance(role, Mapping) else ""
    if status and role_summary:
        return f"{status}; {role_summary}"
    return status or role_summary


def _plain_summary(replies: Sequence[str]) -> str:
    lines = [str(reply).strip() for reply in replies if str(reply).strip()]
    return "\n".join(lines) or "Maestro did not receive a Cassandra answer."


def _one_line_answer(text: str) -> str:
    first_line = next((line.strip("- ").strip() for line in text.splitlines() if line.strip()), text.strip())
    words = first_line.split()
    if len(words) <= 30:
        return " ".join(words)
    return " ".join(words[:29] + ["..."])


def _normalize(text: str) -> str:
    return " ".join(str(text or "").lower().strip().replace("’", "'").split())


def _is_hermes_addressed(text: str) -> bool:
    return bool(re.search(r"\bhermes\b", text))


def _is_hermes_route_request(text: str) -> bool:
    return bool(
        _is_hermes_addressed(text)
        and re.search(r"\b(?:route|send|handoff|hand off|pass|forward|dispatch)\b.{0,50}\bto\b", text)
    )


def _is_hermes_route_inventory_request(text: str) -> bool:
    inventory_phrases = (
        "what can you route to",
        "who can you route to",
        "what agents can you route to",
        "which agents can you route",
        "route inventory",
        "routing inventory",
        "real agent bridges",
        "agent bridges",
    )
    return _is_hermes_addressed(text) and any(phrase in text for phrase in inventory_phrases)


def _is_hermes_capability_prompt(text: str) -> bool:
    status_readback_phrases = (
        "what's going on",
        "whats going on",
        "what is going on",
        "what's happening",
        "whats happening",
        "what is happening",
    )
    if any(phrase in text for phrase in status_readback_phrases):
        return False
    capability_phrases = (
        "what's your job",
        "whats your job",
        "what is your job",
        "what do you do",
        "what can you do",
        "what are you",
        "what is hermes",
        "who are you",
    )
    return _is_hermes_addressed(text) and any(phrase in text for phrase in capability_phrases)


def _is_hermes_truthful_intent(text: str) -> bool:
    return (
        _is_hermes_route_request(text)
        or _is_hermes_route_inventory_request(text)
        or _is_hermes_capability_prompt(text)
    )


def _hermes_truthful_mode(text: str) -> str:
    if _is_hermes_route_inventory_request(text):
        return "route_inventory"
    if _is_hermes_route_request(text) and _route_target(text):
        return "route_request"
    if _is_hermes_addressed(text) and _is_hermes_send_or_money_action(text):
        return "send_money_denial"
    if _is_hermes_route_request(text):
        return "route_request"
    return "capability"


def _hermes_agent_route_targets() -> frozenset[str]:
    try:
        from agent_lane_registry import DEFAULT_AGENT_LANE_SEEDS

        targets: set[str] = set()
        for seed in DEFAULT_AGENT_LANE_SEEDS:
            targets.add(str(seed.agent_id).strip().lower())
            targets.add(str(seed.display_name).strip().lower().replace(" ", "_"))
            targets.update(str(alias).strip().lower() for alias in seed.aliases)
        return frozenset(target for target in targets if target)
    except Exception:
        return HERMES_FALLBACK_AGENT_TARGETS


def _route_target_candidate(text: str) -> str:
    match = re.search(r"\bto\s+([a-z][a-z0-9_-]{1,40})\b", text)
    if not match:
        return ""
    target = match.group(1).strip().lower()
    if target in {"me", "you", "this", "that", "the"}:
        return ""
    return target


def _route_target(text: str) -> str:
    target = _route_target_candidate(text)
    return target if target in _hermes_agent_route_targets() else ""


def _is_hermes_send_or_money_action(text: str) -> bool:
    return bool(HERMES_SEND_OR_MONEY_RE.search(text))


def _strip_internal_state_leaks(text: str) -> str:
    cleaned = str(text or "")
    for pattern in INTERNAL_STATE_LEAK_PATTERNS:
        cleaned = pattern.sub("", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip() or "Maestro response was withheld because it contained internal worker state."


def _is_date_awareness_intent(text: str) -> bool:
    date_phrases = (
        "what's today's date",
        "what is today's date",
        "whats today's date",
        "what day is it",
        "what is the date",
        "current date",
        "today's date",
        "todays date",
        "what's the date",
        "whats the date",
        "the date today",
    )
    return any(phrase in text for phrase in date_phrases)


def _is_artifact_authenticity_challenge(text: str) -> bool:
    artifact_terms = ("artifact", "invoice", "preview", "image", "pdf", "workbook", "export")
    challenge_terms = (
        "not an exported",
        "not exported",
        "not authentic",
        "isn't authentic",
        "is not authentic",
        "not real",
        "is that real",
        "authenticity",
    )
    return any(term in text for term in artifact_terms) and any(
        term in text for term in challenge_terms
    )


def _is_surface_message_deletion_request(text: str) -> bool:
    return bool(
        any(term in text for term in ("delete", "remove", "take down"))
        and any(term in text for term in ("message", "image", "preview", "photo", "telegram", "channel"))
    )


def _artifact_surface_intent_class(text: str) -> str:
    authenticity = _is_artifact_authenticity_challenge(text)
    deletion = _is_surface_message_deletion_request(text)
    if authenticity and deletion:
        return "artifact_authenticity_and_surface_deletion_request"
    if authenticity:
        return "artifact_authenticity_challenge"
    if deletion:
        return "surface_message_deletion_request"
    return ""


def _artifact_surface_intent_result(
    intent_class: str,
    *,
    session: Mapping[str, Any] | None,
) -> MaestroCassandraResult:
    authenticity = "artifact_authenticity" in intent_class
    deletion = "surface_deletion" in intent_class
    lines: list[str] = []
    if authenticity:
        lines.append(
            "You're right to challenge the artifact. I will call an invoice authentic only when "
            "its source-workbook export and displayed file are hash-verified; a rendered card is only a preview."
        )
    if deletion:
        lines.append(
            "I recognized the request to remove the surface message, but this turn has no bound owned-message "
            "deletion receipt and deletion authority is closed, so nothing was deleted."
        )
    answer = " ".join(lines)
    return MaestroCassandraResult(
        status="ANSWER_READY",
        intent_class=intent_class,
        allowed_to_call_handle=False,
        one_line_answer=_one_line_answer(answer),
        plain_summary=answer,
        mac_render_hint=MAC_RENDER_HINT,
        session_forwarded=filtered_session(session),
        machine_proof={
            **_adapter_machine_proof(handle_called=False),
            "artifact_authenticity_challenge_recognized": authenticity,
            "surface_message_deletion_request_recognized": deletion,
            "source_workbook_hash_proof_required": authenticity,
            "surface_message_deleted": False,
            "protected_generate_called": False,
            "external_llm_invoked": False,
        },
    )


def _is_system_knowledge_intent(text: str) -> bool:
    direct_phrases = (
        "system knowledge registry",
        "self knowledge registry",
        "self-knowledge registry",
        "system self knowledge",
        "system self-knowledge",
        "what is in orbit",
        "what's in orbit",
        "whats in orbit",
        "floating in orbit",
    )
    if any(phrase in text for phrase in direct_phrases):
        return True
    return (
        any(term in text for term in ("system", "openclaw", "registry"))
        and any(term in text for term in ("shape", "know", "known", "unknown", "capability", "component", "orbit", "orphan"))
    )


def _is_status_capability_intent(text: str) -> bool:
    direct_phrases = (
        "what's built and what's actually on",
        "whats built and whats actually on",
        "what is built and what is actually on",
        "what is built versus what is on",
        "built vs on",
        "built versus on",
        "what's going on",
        "whats going on",
        "what is going on",
        "what's happening",
        "whats happening",
        "what is happening",
        "what can you do",
        "what can openclaw do",
        "what are you capable of",
        "what can you do now",
        "what can you do for me",
        "what can you help me with",
        "what can openclaw help me with",
        "what can the agents do",
        "who are the agents",
        "what does each agent do",
        "what does each do",
        "agent roster",
        "agent list",
        "which agents are live",
        "which agents are online",
        "system-wide next safe move",
        "system wide next safe move",
        "next safe move",
        "next safest move",
        "safe next move",
        "status readback",
        "give me a status readback",
        "what is live",
        "what's live",
        "whats live",
        "who is online",
        "agent status",
        "system status",
        "openclaw status",
        "capability status",
    )
    if any(phrase in text for phrase in direct_phrases):
        return True
    return (
        any(term in text for term in ("status", "capability", "capabilities", "online", "blocked", "roster"))
        and any(term in text for term in ("openclaw", "agents", "agent", "you", "can", "do"))
    )


def _is_system_health_readback_intent(text: str) -> bool:
    direct_phrases = (
        "system-health read",
        "system health read",
        "system-health status",
        "system health status",
        "system-health check",
        "system health check",
        "front door and agent response stack",
        "agent response stack",
        "service health",
        "agent/service health",
    )
    if any(phrase in text for phrase in direct_phrases):
        return True
    return (
        any(term in text for term in ("system-health", "system health", "service health", "health read"))
        and any(term in text for term in ("openclaw", "front door", "agent", "agents", "stack"))
    )


def _is_recurrence_rule_statement_intent(text: str) -> bool:
    """Task 136a: 'I send St Anne's a new invoice on the first of every month' is an operator
    STATEMENT of a recurring business rule -- a third category, distinct from both a question
    and an instruction. Checked early, before advisory/action/question classification, so it
    is never mistaken for either."""
    from recurrence_rule_intake import detect_recurrence_rule_statement

    return detect_recurrence_rule_statement(text) is not None


def _status_capability_readback_focus(text: str) -> str:
    if any(
        phrase in text
        for phrase in (
            "who are the agents",
            "agent roster",
            "agent list",
            "what does each agent do",
            "what does each do",
            "which agents",
        )
    ):
        return "agent_roster"
    if any(
        phrase in text
        for phrase in (
            "system-wide next safe move",
            "system wide next safe move",
            "next safe move",
            "next safest move",
            "safe next move",
        )
    ):
        return "next_safe_move"
    if any(
        phrase in text
        for phrase in (
            "what can you help me with",
            "what can you do",
            "what can openclaw do",
            "what are you capable of",
            "capability",
            "capabilities",
        )
    ):
        return "capability"
    return "status"


def _is_people_intent(text: str) -> bool:
    return bool(
        re.search(
            r"\b("
            r"who is|who's|"
            r"who do i talk to|"
            r"contact for|point of contact|who should i contact|"
            r"relationship|team member|person|people"
            r")\b",
            text,
        )
    )


def _is_operator_truth_correction_intent(text: str) -> bool:
    try:
        from operator_truth_store import extract_operator_truth_candidates

        return bool(extract_operator_truth_candidates(text, source_surface="operator_maestro_chat"))
    except Exception:
        return False


def _is_operator_truth_query_intent(text: str) -> bool:
    return bool(
        re.search(
            r"\b("
            r"did you (?:store|save|record|remember)|"
            r"what have you recorded about|"
            r"what (?:did|do) you (?:store|save|record|remember)|"
            r"do you (?:have|remember|know) .* truth|"
            r"is .* (?:in your truth|stored|saved|recorded|remembered)"
            r")\b",
            text,
        )
    )


def _is_inbox_metadata_intent(text: str) -> bool:
    try:
        from email_intent import email_intent_requires_read

        return email_intent_requires_read(text)
    except Exception:
        return False


def _is_calendar_or_briefing_intent(text: str) -> bool:
    return bool(
        re.search(r"\b(calendar|meetings?|schedule|morning briefing|daily briefing|briefing)\b", text)
    )


def _is_send_or_reply_intent(text: str) -> bool:
    try:
        from email_intent import email_intent_requires_draft

        return email_intent_requires_draft(text)
    except Exception:
        return False


def _is_advisory_interrogative_intent(text: str) -> bool:
    """True for advice-seeking questions that mention send/pay words without requesting an action."""
    if re.search(r"^\s*(send|reply|respond|forward|email|mail|message|text|draft|pay|submit|approve)\b", text):
        return False
    return bool(
        re.search(
            r"\b("
            r"before i (?:send|pay|reply|respond|forward|email|mail|message|text|submit)|"
            r"what should i (?:check|verify|look for|watch for|do)|"
            r"what do i need to (?:check|verify|look for|watch for)|"
            r"how (?:do|should) i (?:check|verify|make sure|avoid|protect|handle)|"
            r"is it safe to|"
            r"should i (?:send|pay|reply|respond|forward|email|mail|message|text|submit|approve)|"
            r"can i safely"
            r")\b",
            text,
        )
    )


def _is_advisory_judgment_intent(text: str) -> bool:
    """Recognize asks for judgment that must never become action staging."""

    if re.search(r"^\s*(send|reply|forward|email|draft|pay|submit|approve|run|build|fix)\b", text):
        return False
    return bool(
        re.search(
            r"\b("
            r"what do you think|"
            r"what(?:'s| is) your (?:take|opinion|recommendation|judgment)|"
            r"what would you recommend|"
            r"what (?:is|would be) the next correct step|"
            r"what should (?:we|i) do next"
            r")\b",
            text,
        )
    )


def _is_dispatch_instruction_intent(text: str) -> bool:
    try:
        from workflow_package_queue import classify_workflow_route

        return bool(classify_workflow_route(text).workflow_ref)
    except Exception:
        return False


def _is_workflow_or_business_action_intent(text: str) -> bool:
    action_terms = (
        "do it",
        "make it so",
        "approve",
        "deny",
        "submit",
        "pay",
        "mark paid",
        "create invoice",
        "make invoice",
        "generate invoice",
        "open browser",
        "coupa",
        "workbook",
        "spreadsheet",
        "ledger",
        "deploy",
        "restart",
        "merge",
        "push",
        "run the workflow",
        "stage plan",
        "schedule",
        "book",
        "create calendar",
    )
    return any(term in text for term in action_terms)


_GENERAL_QUESTION_OPENERS = (
    "who", "what", "when", "where", "which", "how",
    "does", "did", "is", "are", "can",
)


def _is_general_question_shape(text: str) -> bool:
    """Task 133: a question-shaped text (interrogative opener or trailing '?') must never be
    classified as a business action just because it contains an action-shaped word --
    'did St Anne's pay us?' contains 'pay' but asks about status, not a payment request."""
    normalized = str(text or "").strip()
    if not normalized:
        return False
    if normalized.endswith("?"):
        return True
    first_word = normalized.split(" ", 1)[0].rstrip("?,.!;:")
    return first_word in _GENERAL_QUESTION_OPENERS
