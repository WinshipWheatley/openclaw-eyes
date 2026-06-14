"""Proof Meter Normalization V0.

Turns backend proof fields on dynamic_card_packet_v1 cards into compact,
operator-readable proof meters for Mission Control. Meters are UI indicators
and proof-drawer entry points; they never grant authority or imply execution.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Proof Meter Normalization.md")

SCHEMA_VERSION = "proof_meter_normalization_v0"
READ_MODEL_ID = "proof_meter_normalization"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "PROOF_METER_NORMALIZATION_READY"
NOT_READY_STATUS = "PROOF_METER_NORMALIZATION_NOT_READY"

METER_REFS = ("truth", "freshness", "authority", "evidence", "sync", "risk")

TRUTH_STATES = (
    "receipt_backed",
    "artifact_hash",
    "trusted_current",
    "operator_reported",
    "candidate_evidence",
    "generated_summary",
    "inferred",
    "needs_verification",
    "test_only",
    "rejected",
    "unknown",
)
FRESHNESS_STATES = ("current", "waiting_external", "needs_verification", "superseded", "historical", "unknown")
AUTHORITY_STATES = ("verified_control", "approval_required", "blocked_gate", "no_grant", "needs_verification", "rejected")
EVIDENCE_STATES = (
    "receipt_present",
    "artifact_hash_present",
    "candidate_evidence",
    "operator_reported",
    "no_evidence",
    "test_only",
    "rejected",
)
SYNC_STATES = ("bridge_synced", "local_only", "bridge_stale", "needs_mount", "mismatch", "unknown")
RISK_STATES = ("calm", "watch", "pileup_risk", "blocked", "protected", "unknown")

METER_STATES = {
    "truth": TRUTH_STATES,
    "freshness": FRESHNESS_STATES,
    "authority": AUTHORITY_STATES,
    "evidence": EVIDENCE_STATES,
    "sync": SYNC_STATES,
    "risk": RISK_STATES,
}

HUMAN_LABELS = {
    "truth": {
        "receipt_backed": "Receipt backed",
        "artifact_hash": "Artifact hash",
        "trusted_current": "Trusted current",
        "operator_reported": "Operator reported",
        "candidate_evidence": "Candidate evidence",
        "generated_summary": "Generated summary",
        "inferred": "Inferred",
        "needs_verification": "Needs verification",
        "test_only": "Test only",
        "rejected": "Rejected",
        "unknown": "Unknown",
    },
    "freshness": {
        "current": "Current",
        "waiting_external": "Waiting external",
        "needs_verification": "Needs verification",
        "superseded": "Superseded",
        "historical": "Historical",
        "unknown": "Unknown",
    },
    "authority": {
        "verified_control": "Verified control",
        "approval_required": "Approval required",
        "blocked_gate": "Blocked gate",
        "no_grant": "No grant",
        "needs_verification": "Needs verification",
        "rejected": "Rejected",
    },
    "evidence": {
        "receipt_present": "Receipt present",
        "artifact_hash_present": "Artifact hash present",
        "candidate_evidence": "Candidate evidence",
        "operator_reported": "Operator reported",
        "no_evidence": "No evidence",
        "test_only": "Test only",
        "rejected": "Rejected",
    },
    "sync": {
        "bridge_synced": "Bridge synced",
        "local_only": "Local only",
        "bridge_stale": "Bridge stale",
        "needs_mount": "Needs mount",
        "mismatch": "Mismatch",
        "unknown": "Unknown",
    },
    "risk": {
        "calm": "Calm",
        "watch": "Watch",
        "pileup_risk": "Pileup risk",
        "blocked": "Blocked",
        "protected": "Protected",
        "unknown": "Unknown",
    },
}

TONE_BY_STATE = {
    "receipt_backed": "good",
    "artifact_hash": "good",
    "trusted_current": "good",
    "operator_reported": "watch",
    "candidate_evidence": "watch",
    "generated_summary": "neutral",
    "inferred": "watch",
    "needs_verification": "warning",
    "test_only": "neutral",
    "rejected": "blocked",
    "unknown": "unknown",
    "current": "good",
    "waiting_external": "watch",
    "superseded": "neutral",
    "historical": "neutral",
    "verified_control": "good",
    "approval_required": "protected",
    "blocked_gate": "blocked",
    "no_grant": "neutral",
    "receipt_present": "good",
    "artifact_hash_present": "good",
    "no_evidence": "warning",
    "bridge_synced": "good",
    "local_only": "neutral",
    "bridge_stale": "warning",
    "needs_mount": "warning",
    "mismatch": "blocked",
    "calm": "calm",
    "watch": "watch",
    "pileup_risk": "warning",
    "blocked": "blocked",
    "protected": "protected",
}

MUST_NEVER_IMPLY = {
    "truth": [
        "LM output is truth.",
        "Generated summary overrides receipts, hashes, or source rows.",
        "Payment-processing evidence means paid.",
    ],
    "freshness": [
        "External systems were checked live.",
        "A stale read model overrides a newer receipt.",
    ],
    "authority": [
        "The app, LM, incoming request text, or operator identity granted authority.",
        "Approval means business execution.",
    ],
    "evidence": [
        "Candidate evidence is verified truth.",
        "Raw sensitive detail is safe to show.",
        "Paid, sent, or ledger state changed.",
    ],
    "sync": [
        "External system sync occurred.",
        "Email, Coupa, Gmail, browser, ledger, or workbook access happened.",
    ],
    "risk": [
        "Calm UI copy means protected action safety.",
        "Risk tone is real-world severity beyond recorded proof.",
    ],
}

PRECONDITIONS = {
    "operator_controller_design_brief": {
        "filename": "operator_controller_design_brief.json",
        "accepted_statuses": ["OPERATOR_CONTROLLER_DESIGN_BRIEF_READY"],
    },
    "dynamic_card_packet_v1": {
        "filename": "dynamic_card_packet_latest.json",
        "accepted_statuses": ["DYNAMIC_CARD_PACKET_V1_READY", "DYNAMIC_CARD_PACKET_READY"],
    },
    "evidence_confidence_scoring": {
        "filename": "evidence_confidence_scoring.json",
        "accepted_statuses": ["EVIDENCE_CONFIDENCE_SCORING_READY"],
    },
    "gate_decision_ledger": {
        "filename": "gate_decision_ledger.json",
        "accepted_statuses": ["GATE_DECISION_LEDGER_READY"],
    },
    "verified_evidence_intake": {
        "filename": "evidence_intake_status.json",
        "accepted_statuses": ["VERIFIED_EVIDENCE_INTAKE_READY", "EVIDENCE_INTAKE_LIVE_ROUTE_READY", "EVIDENCE_INTAKE_READY"],
    },
    "universal_receipt_envelope": {
        "filename": "universal_receipt_envelope_status.json",
        "accepted_statuses": ["UNIVERSAL_RECEIPT_ENVELOPE_READY"],
    },
}

UNSAFE_TRUE_KEYS = {
    "authority_granted",
    "authority_grant_allowed",
    "business_action_allowed",
    "business_action_performed",
    "paid",
    "paid_marking_allowed",
    "paid_marking_performed",
    "ledger_mutation_allowed",
    "ledger_mutation_performed",
    "ledger_posting_allowed",
    "email_send_allowed",
    "email_send_performed",
    "coupa_allowed",
    "coupa_submit_performed",
    "portal_submit_allowed",
    "workbook_mutation_allowed",
    "workbook_mutation_performed",
    "pdf_export_allowed",
    "pdf_export_performed",
    "git_push_allowed",
    "worker_spawn_allowed",
    "external_action_allowed",
    "incoming_authority_granted_accepted",
    "meters_imply_execution",
}

AUTHORITY_BOUNDARY = {
    "authority_grant_allowed": False,
    "business_action_allowed": False,
    "email_send_allowed": False,
    "gmail_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_mutation_allowed": False,
    "ledger_posting_allowed": False,
    "paid": False,
    "paid_marking_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "git_push_allowed": False,
    "worker_spawn_allowed": False,
    "external_action_allowed": False,
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path) -> Path:
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


def _source_ref(filename: str) -> str:
    return f"generated/read_models/{filename}"


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


def _preconditions(read_model_root: Path) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows: list[dict[str, Any]] = []
    for ref, contract in PRECONDITIONS.items():
        filename = str(contract["filename"])
        payload = _load_json(root / filename)
        observed = str(payload.get("status") or payload.get("contract_status") or "")
        accepted = [str(status) for status in contract["accepted_statuses"]]
        rows.append(
            {
                "precondition_ref": ref,
                "source_ref": _source_ref(filename),
                "observed_status": observed,
                "accepted_statuses": accepted,
                "ready": observed in accepted,
            }
        )
    return rows


def _proof(card: Mapping[str, Any]) -> Mapping[str, Any]:
    proof = card.get("proof")
    return proof if isinstance(proof, Mapping) else {}


def _refs(card: Mapping[str, Any], proof_key: str) -> list[str]:
    proof = _proof(card)
    values = proof.get(proof_key)
    if isinstance(values, list):
        return [str(value) for value in values if str(value)]
    return []


def _action_slots(card: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    slots = card.get("action_slots")
    if not isinstance(slots, Mapping):
        return []
    return [slot for slot in slots.values() if isinstance(slot, Mapping)]


def _has_enabled_action(card: Mapping[str, Any]) -> bool:
    return any(slot.get("enabled") is True for slot in _action_slots(card))


def _has_disabled_protected_action(card: Mapping[str, Any]) -> bool:
    for slot in _action_slots(card):
        if slot.get("enabled") is False and str(slot.get("disabled_reason") or ""):
            text = " ".join([str(slot.get("label") or ""), str(slot.get("disabled_reason") or "")]).lower()
            if any(token in text for token in ("coupa", "ledger", "paid", "send", "submit", "merge", "push", "worker", "authority")):
                return True
    return False


def _is_gate_lock(card: Mapping[str, Any]) -> bool:
    card_family = str(card.get("card_family") or "")
    text = " ".join(
        [
            str(card.get("card_id") or ""),
            card_family,
            str(card.get("card_type") or ""),
            str(card.get("headline") or ""),
            str(card.get("status_label") or ""),
            str(card.get("tone") or ""),
        ]
    ).lower()
    return "gate" in text or "approval" in text or "blocked" in text or card_family in {"gate_lock_card", "approval_request_card"}


def normalize_truth_state(card: Mapping[str, Any]) -> str:
    if card.get("_proof_meter_missing_source_refs"):
        return "needs_verification"
    trust = str(card.get("trust_state") or "").lower()
    confidence = str(card.get("confidence_class") or "").lower()
    lifecycle = str(card.get("lifecycle_state") or "").lower()
    freshness = str(card.get("freshness_state") or "").lower()
    proof = _proof(card)
    if "rejected" in (trust, confidence, lifecycle):
        return "rejected"
    if "test" in trust or "test" in confidence or "test" in str(card.get("status_label") or "").lower():
        return "test_only"
    if trust == "needs_verification" or confidence == "needs_verification" or freshness == "needs_verification":
        return "needs_verification"
    if trust == "candidate_evidence":
        return "candidate_evidence"
    if trust == "operator_reported":
        return "operator_reported"
    if trust == "trusted_current":
        return "trusted_current"
    if _refs(card, "hash_refs"):
        return "artifact_hash"
    if _refs(card, "receipt_refs"):
        return "receipt_backed"
    if proof.get("redacted_summary") and not _refs(card, "receipt_refs"):
        return "generated_summary"
    if confidence == "inferred":
        return "inferred"
    return "unknown"


def normalize_freshness_state(card: Mapping[str, Any]) -> str:
    if card.get("_proof_meter_missing_source_refs"):
        return "needs_verification"
    freshness = str(card.get("freshness_state") or "").lower()
    lifecycle = str(card.get("lifecycle_state") or "").lower()
    if freshness == "waiting_on_external":
        return "waiting_external"
    if freshness in FRESHNESS_STATES:
        return freshness
    if lifecycle == "resolved" or lifecycle == "archived":
        return "historical"
    if lifecycle == "stale":
        return "superseded"
    if lifecycle == "needs_operator":
        return "needs_verification"
    return "unknown"


def normalize_authority_state(card: Mapping[str, Any]) -> str:
    truth = normalize_truth_state(card)
    if truth == "rejected":
        return "rejected"
    if truth == "needs_verification":
        return "needs_verification"
    if _is_gate_lock(card):
        if str(card.get("card_family") or "") == "approval_request_card":
            return "blocked_gate"
        if "requires" in str(card.get("headline") or "").lower() or "approval" in str(card.get("status_label") or "").lower():
            return "approval_required"
        return "blocked_gate"
    return "no_grant"


def normalize_evidence_state(card: Mapping[str, Any]) -> str:
    truth = normalize_truth_state(card)
    if truth == "rejected":
        return "rejected"
    if truth == "test_only":
        return "test_only"
    if truth == "candidate_evidence":
        return "candidate_evidence"
    if truth == "operator_reported":
        return "operator_reported"
    if _refs(card, "hash_refs"):
        return "artifact_hash_present"
    if _refs(card, "receipt_refs"):
        return "receipt_present"
    if _refs(card, "artifact_refs"):
        return "artifact_hash_present"
    return "no_evidence"


def normalize_sync_state(card: Mapping[str, Any], *, bridge_equal: bool | None) -> str:
    if bridge_equal is True:
        return "bridge_synced"
    if bridge_equal is False:
        return "mismatch"
    source_refs = [str(ref) for ref in card.get("source_read_model_refs") or []]
    if source_refs:
        return "unknown"
    return "local_only"


def normalize_risk_state(card: Mapping[str, Any]) -> str:
    authority = normalize_authority_state(card)
    truth = normalize_truth_state(card)
    freshness = normalize_freshness_state(card)
    card_family = str(card.get("card_family") or "")
    tone = str(card.get("tone") or "").lower()
    text = " ".join(
        [
            str(card.get("headline") or ""),
            str(card.get("plain_summary") or ""),
            str(card.get("status_label") or ""),
            " ".join(str(line) for line in card.get("supporting_lines") or []),
        ]
    ).lower()
    if authority in {"blocked_gate", "approval_required"} or tone == "blocked" or card_family in {"approval_request_card", "gate_lock_card"}:
        return "protected" if card_family == "approval_request_card" else "blocked"
    if truth in {"needs_verification", "rejected"} or freshness in {"needs_verification", "superseded"}:
        return "blocked" if truth == "rejected" else "watch"
    if "pileup" in text:
        return "pileup_risk"
    if "watch" in text or "waiting" in text or truth in {"operator_reported", "candidate_evidence"} or freshness == "waiting_external":
        return "watch"
    if tone in {"warning", "watch"}:
        return "watch"
    if tone == "neutral" and card_family in {"memory_candidate_card", "artifact_proof_card"}:
        return "watch"
    return "calm"


def _source_fields_for(meter_ref: str) -> list[str]:
    fields = {
        "truth": [
            "card.trust_state",
            "card.confidence_class",
            "card.confidence_score",
            "card.proof.receipt_refs",
            "card.proof.hash_refs",
            "card.source_read_model_refs",
        ],
        "freshness": [
            "card.freshness_state",
            "card.lifecycle_state",
            "card.source_generated_at",
            "card.source_content_hash",
            "card.replacement_card_ref",
            "card.resolved_by_receipt_ref",
        ],
        "authority": [
            "card.action_slots.*.enabled",
            "card.action_slots.*.requires_operator_envelope",
            "card.action_slots.*.receipt_required",
            "card.action_slots.*.authority_boundary",
            "gate_decision_ledger.status",
        ],
        "evidence": [
            "card.proof.receipt_refs",
            "card.proof.artifact_refs",
            "card.proof.hash_refs",
            "card.proof.sqlite_refs",
            "card.proof.redacted_summary",
            "evidence_intake_status.latest_record",
        ],
        "sync": [
            "local.proof_meter_normalization.json",
            "bridge.proof_meter_normalization.json",
            "source_content_hash",
        ],
        "risk": [
            "card.tone",
            "card.status_label",
            "card.operator_attention_required",
            "card.action_slots.*.disabled_reason",
            "card.authority_boundary",
            "gate_decision_ledger.decisions",
        ],
    }
    return fields[meter_ref]


def _source_refs_for(meter_ref: str, card: Mapping[str, Any]) -> list[str]:
    refs = list(dict.fromkeys(str(ref) for ref in card.get("source_read_model_refs") or [] if str(ref)))
    extras = {
        "truth": [
            _source_ref("operator_controller_design_brief.json"),
            _source_ref("evidence_confidence_scoring.json"),
            _source_ref("universal_receipt_envelope_status.json"),
        ],
        "freshness": [
            _source_ref("dynamic_card_packet_latest.json"),
            _source_ref("dynamic_card_lifecycle_policy.json"),
        ],
        "authority": [
            _source_ref("gate_decision_ledger.json"),
            _source_ref("operator_controller_protocol.json"),
            _source_ref("first_class_operator_envelope_status.json"),
        ],
        "evidence": [
            _source_ref("evidence_intake_status.json"),
            _source_ref("evidence_confidence_scoring.json"),
            _source_ref("universal_receipt_envelope_status.json"),
        ],
        "sync": [
            _source_ref("dynamic_card_packet_latest.json"),
            _source_ref("sync_health.json"),
        ],
        "risk": [
            _source_ref("gate_decision_ledger.json"),
            _source_ref("workroom_wip_limits.json"),
            _source_ref("operator_action_payloads.json"),
        ],
    }
    return list(dict.fromkeys([*refs, *extras[meter_ref]]))


def _missing_source_refs(card: Mapping[str, Any], read_model_root: Path) -> list[str]:
    root = _rooted(read_model_root)
    missing: list[str] = []
    for ref in card.get("source_read_model_refs") or []:
        source_ref = str(ref)
        if not source_ref.startswith("generated/read_models/"):
            continue
        relative = source_ref.split("generated/read_models/", 1)[1].split("#", 1)[0]
        if relative and not (root / relative).exists():
            missing.append(source_ref)
    return missing


def _opens_details(meter_ref: str, meter_state: str, card: Mapping[str, Any]) -> bool:
    if meter_ref == "truth":
        return meter_state not in {"trusted_current"}
    if meter_ref == "freshness":
        return meter_state in {"waiting_external", "needs_verification", "superseded", "historical", "unknown"}
    if meter_ref == "authority":
        return meter_state in {"approval_required", "blocked_gate", "needs_verification", "rejected"}
    if meter_ref == "evidence":
        return meter_state in {"candidate_evidence", "operator_reported", "no_evidence", "test_only", "rejected"} or bool(
            (_proof(card) or {}).get("raw_detail_available")
        )
    if meter_ref == "sync":
        return meter_state in {"bridge_stale", "needs_mount", "mismatch", "unknown", "local_only"}
    if meter_ref == "risk":
        return meter_state in {"watch", "pileup_risk", "blocked", "protected", "unknown"}
    return True


def _explanation(meter_ref: str, meter_state: str, card: Mapping[str, Any]) -> str:
    headline = str(card.get("headline") or card.get("card_id") or "This card")
    if meter_ref == "truth":
        return f"{headline}: truth is `{meter_state}` based on card trust, confidence, receipts, hashes, and source read models."
    if meter_ref == "freshness":
        return f"{headline}: freshness is `{meter_state}` from card freshness/lifecycle fields and source timestamps."
    if meter_ref == "authority":
        return f"{headline}: authority is `{meter_state}`; controller actions do not accept incoming grants or execute protected work."
    if meter_ref == "evidence":
        return f"{headline}: evidence is `{meter_state}` from categorized proof refs, candidate evidence state, and artifact/hash refs."
    if meter_ref == "sync":
        return f"{headline}: sync is `{meter_state}` for the generated local/bridge read model path."
    if meter_ref == "risk":
        return f"{headline}: risk is `{meter_state}` from gate state, disabled actions, waiting/protected status, and attention needs."
    return f"{headline}: meter state is `{meter_state}`."


def build_meter(card: Mapping[str, Any], meter_ref: str, *, bridge_equal: bool | None = None) -> dict[str, Any]:
    normalizers = {
        "truth": normalize_truth_state,
        "freshness": normalize_freshness_state,
        "authority": normalize_authority_state,
        "evidence": normalize_evidence_state,
        "risk": normalize_risk_state,
    }
    if meter_ref == "sync":
        meter_state = normalize_sync_state(card, bridge_equal=bridge_equal)
    else:
        meter_state = normalizers[meter_ref](card)
    if meter_state not in METER_STATES[meter_ref]:
        meter_state = "unknown"
    return {
        "meter_ref": meter_ref,
        "card_id": str(card.get("card_id") or ""),
        "human_label": HUMAN_LABELS[meter_ref][meter_state],
        "meter_state": meter_state,
        "tone": TONE_BY_STATE.get(meter_state, "unknown"),
        "source_fields": _source_fields_for(meter_ref),
        "source_refs": _source_refs_for(meter_ref, card),
        "opens_details": _opens_details(meter_ref, meter_state, card),
        "must_never_imply": list(MUST_NEVER_IMPLY[meter_ref]),
        "explanation": _explanation(meter_ref, meter_state, card),
    }


def build_card_meter_set(
    card: Mapping[str, Any],
    *,
    bridge_equal: bool | None = None,
    read_model_root: Path | None = None,
) -> dict[str, Any]:
    normalized_card = dict(card)
    if read_model_root is not None:
        normalized_card["_proof_meter_missing_source_refs"] = _missing_source_refs(card, read_model_root)
    meters = [build_meter(normalized_card, meter_ref, bridge_equal=bridge_equal) for meter_ref in METER_REFS]
    return {
        "card_id": str(normalized_card.get("card_id") or ""),
        "card_family": str(normalized_card.get("card_family") or ""),
        "headline": str(normalized_card.get("headline") or ""),
        "missing_source_refs": list(normalized_card.get("_proof_meter_missing_source_refs") or []),
        "meters": meters,
        "meter_map": {meter["meter_ref"]: meter for meter in meters},
    }


def validate_meter(meter: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    meter_ref = str(meter.get("meter_ref") or "")
    if meter_ref not in METER_REFS:
        errors.append(f"unknown_meter_ref:{meter_ref}")
        return errors
    if str(meter.get("meter_state") or "") not in METER_STATES[meter_ref]:
        errors.append(f"{meter_ref}:unknown_meter_state:{meter.get('meter_state')}")
    for field in (
        "meter_ref",
        "card_id",
        "human_label",
        "meter_state",
        "tone",
        "source_fields",
        "source_refs",
        "opens_details",
        "must_never_imply",
        "explanation",
    ):
        if field not in meter:
            errors.append(f"{meter_ref}:missing_field:{field}")
    if meter.get("opens_details") is not True and meter.get("opens_details") is not False:
        errors.append(f"{meter_ref}:opens_details_not_bool")
    return errors


def _bridge_equal(local_path: Path, bridge_path: Path) -> bool | None:
    local_path = _rooted(local_path)
    if not local_path.exists():
        return None
    if not bridge_path.exists():
        return None
    return local_path.read_bytes() == bridge_path.read_bytes()


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    root = _rooted(read_model_root)
    packet = _load_json(root / "dynamic_card_packet_latest.json")
    preconditions = _preconditions(read_model_root)
    cards = packet.get("cards") if isinstance(packet.get("cards"), list) else []
    bridge_equal = _bridge_equal(root / "dynamic_card_packet_latest.json", DEFAULT_BRIDGE_EXPORT_ROOT / "dynamic_card_packet_latest.json")
    card_meter_sets = [
        build_card_meter_set(card, bridge_equal=bridge_equal, read_model_root=read_model_root)
        for card in cards
        if isinstance(card, Mapping)
    ]
    meters = [meter for card_set in card_meter_sets for meter in card_set["meters"]]
    validation_errors: list[str] = []
    for meter in meters:
        validation_errors.extend(validate_meter(meter))
    preconditions_ready = all(row["ready"] for row in preconditions)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS if preconditions_ready and not validation_errors and meters else NOT_READY_STATUS,
        "generated_at": generated_at,
        "source_packet_ref": _source_ref("dynamic_card_packet_latest.json"),
        "source_packet_content_hash": _content_hash(packet),
        "card_count": len(card_meter_sets),
        "meter_count": len(meters),
        "meters_per_card": len(METER_REFS),
        "meter_refs": list(METER_REFS),
        "meter_states": {key: list(values) for key, values in METER_STATES.items()},
        "card_meter_sets": card_meter_sets,
        "meters": meters,
        "preconditions": preconditions,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "rules": [
            "Proof meters are operator-readable.",
            "Proof meters do not imply execution.",
            "Payment-processing evidence does not imply paid.",
            "Approval does not imply business action.",
            "LM output does not imply truth.",
            "Meter clicks open details/proof.",
        ],
        "machine_proof": {
            "preconditions_ready": preconditions_ready,
            "meter_validation_errors": validation_errors,
            "meters_operator_readable": True,
            "meters_imply_execution": False,
            "payment_processing_evidence_implies_paid": False,
            "approval_implies_business_action": False,
            "lm_output_implies_truth": False,
            "meter_clicks_open_details_or_proof": all(meter.get("opens_details") in (True, False) for meter in meters),
            "business_action_performed": False,
            "paid_marking_performed": False,
            "ledger_mutation_performed": False,
            "email_send_performed": False,
            "coupa_submit_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "incoming_authority_granted_accepted": False,
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
        "# Proof Meter Normalization",
        "",
        "Status: " + str(read_model["status"]),
        "",
        "Proof Meter Normalization V0 turns backend proof fields into operator-readable controller meters. Meters summarize proof posture and open details; they do not grant authority or execute anything.",
        "",
        "## Meters",
        "",
    ]
    states = read_model.get("meter_states") if isinstance(read_model.get("meter_states"), Mapping) else {}
    for meter_ref in METER_REFS:
        lines.append(f"- `{meter_ref}`: " + ", ".join(f"`{state}`" for state in states.get(meter_ref, [])))
    lines.extend(
        [
            "",
            "## Rules",
            "",
        ]
    )
    for rule in read_model.get("rules") or []:
        lines.append(f"- {rule}")
    lines.extend(
        [
            "",
            "## Cards",
            "",
        ]
    )
    for card_set in read_model.get("card_meter_sets") or []:
        meter_map = card_set.get("meter_map") if isinstance(card_set.get("meter_map"), Mapping) else {}
        summary = ", ".join(
            f"{meter_ref}={meter_map.get(meter_ref, {}).get('meter_state', 'unknown')}" for meter_ref in METER_REFS
        )
        lines.append(f"- `{card_set.get('card_id')}`: {summary}")
    lines.extend(
        [
            "",
            "## Proof",
            "",
            f"- Card count: `{read_model.get('card_count')}`",
            f"- Meter count: `{read_model.get('meter_count')}`",
            f"- Unsafe true grants absent: `{str((read_model.get('machine_proof') or {}).get('unsafe_true_grants_absent')).lower()}`",
            "",
        ]
    )
    return "\n".join(lines)


def export_proof_meter_normalization(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_read_model(read_model_root=read_model_root, generated_at=generated_at)
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    export_path = export_root / JSON_EXPORT_NAME
    _write_json(export_path, read_model)

    bridge_path = ""
    if bridge_export_root is not None:
        bridge_export_root.mkdir(parents=True, exist_ok=True)
        bridge = bridge_export_root / JSON_EXPORT_NAME
        shutil.copy2(export_path, bridge)
        bridge_path = bridge.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(read_model), encoding="utf-8")
    return {
        "status": str(read_model["status"]),
        "read_model_path": export_path.as_posix(),
        "bridge_read_model_path": bridge_path,
        "wiki_path": wiki_path.as_posix(),
        "card_count": str(read_model["card_count"]),
        "meter_count": str(read_model["meter_count"]),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish Proof Meter Normalization V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_proof_meter_normalization(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    if args.format == "json":
        print(stable_json(result), end="")
    else:
        print(f"{result['status']}: {result['read_model_path']}")
    return 0 if result["status"] == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
