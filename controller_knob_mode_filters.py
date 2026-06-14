"""Controller Knobs and Mode Filters V0.

Defines backend-driven controller knobs for Mission Control. Knobs change card
visibility, focus, proof verbosity, and staging depth. They do not grant
protected authority or execute business actions.
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
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Controller Knobs and Mode Filters.md")

SCHEMA_VERSION = "controller_knob_mode_filters_v0"
READ_MODEL_ID = "controller_knob_mode_filters"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "CONTROLLER_KNOB_MODE_FILTERS_READY"
NOT_READY_STATUS = "CONTROLLER_KNOB_MODE_FILTERS_NOT_READY"

ZOOM_LEVELS = ("moment", "task", "lane", "world", "system")
DELEGATION_DEPTHS = ("readback", "plan", "stage", "safe_work", "prepare_approval", "execute_after_approval_blocked")
PROOF_DEPTHS = ("none", "summary", "receipts", "full_developer_proof")
URGENCY_LEVELS = ("park", "normal", "today", "urgent")
OPERATOR_MODES = ("artist", "finance", "build", "business", "creative", "system")

DEFAULT_KNOB_STATE = {
    "zoom_level": "task",
    "delegation_depth": "readback",
    "proof_depth": "summary",
    "urgency": "normal",
    "operator_mode": "system",
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
    "worker_run_performed",
    "external_action_allowed",
    "incoming_authority_granted_accepted",
    "knobs_grant_authority",
    "urgent_bypasses_gates",
    "execute_after_approval_enabled",
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
    "proof_meter_normalization": {
        "filename": "proof_meter_normalization.json",
        "accepted_statuses": ["PROOF_METER_NORMALIZATION_READY"],
    },
}

KNOB_DEFINITIONS = {
    "zoom_level": {
        "allowed_values": list(ZOOM_LEVELS),
        "default": "task",
        "what_it_changes": [
            "How many cards are visible.",
            "Whether focus is one moment, a task set, a lane, a world, or system-level posture.",
            "How much WIP and meter context is included.",
        ],
        "what_it_never_changes": [
            "Authority boundaries.",
            "Card truth or proof values.",
            "Backend source rows, receipts, ledgers, workbooks, or external systems.",
        ],
        "authority_implications": "None. Zoom only changes visibility and focus.",
        "card_filtering_behavior": {
            "moment": "Show exactly one current focus card, with critical blockers allowed only as details.",
            "task": "Show current, waiting, and needs-operator cards; hide resolved history and proof-only developer cards.",
            "lane": "Show current lane cards plus critical blockers for that lane.",
            "world": "Show visible cards in the selected world plus critical authority blockers.",
            "system": "Show WIP, meter, and posture cards, but hide machine-contract cards and developer proof by default.",
        },
        "proof_meter_behavior": "Meter rows remain available as backend data; visible meter count follows proof_depth.",
        "device_suitability": {
            "Mac": ["moment", "task", "lane", "world", "system"],
            "iPad": ["moment", "task", "lane", "world"],
            "iPhone": ["moment", "task"],
        },
    },
    "delegation_depth": {
        "allowed_values": list(DELEGATION_DEPTHS),
        "default": "readback",
        "what_it_changes": [
            "How far a safe controller event may be staged.",
            "Whether the backend returns readback, plan, staged package, safe local work, or approval preparation.",
        ],
        "what_it_never_changes": [
            "Protected-action authority.",
            "Approval-to-execution status.",
            "Business ledgers, workbooks, emails, portals, PDFs, workers, or external LMs.",
        ],
        "authority_implications": "No delegation depth grants protected authority. execute_after_approval remains blocked and future-gated.",
        "card_filtering_behavior": {
            "readback": "Prefer answer, status, and current-focus cards.",
            "plan": "Include workflow composer plan cards.",
            "stage": "Include local package staging affordances only.",
            "safe_work": "Include safe internal work cards only when their action payloads remain non-protected.",
            "prepare_approval": "Include approval request and gate cards without execution.",
            "execute_after_approval_blocked": "Show the blocked/future-gated posture only.",
        },
        "proof_meter_behavior": "Authority and risk meters become more prominent as depth approaches approval preparation.",
        "device_suitability": {
            "Mac": list(DELEGATION_DEPTHS),
            "iPad": ["readback", "plan", "stage", "prepare_approval"],
            "iPhone": ["readback", "plan"],
        },
    },
    "proof_depth": {
        "allowed_values": list(PROOF_DEPTHS),
        "default": "summary",
        "what_it_changes": [
            "Which proof meter labels and proof refs are visible.",
            "Whether receipt refs, hashes, SQLite refs, and developer proof are surfaced.",
        ],
        "what_it_never_changes": [
            "Which business action is allowed.",
            "Which cards match the selected zoom/mode.",
            "Source truth, receipts, ledgers, workbooks, or external systems.",
        ],
        "authority_implications": "None. Proof depth is display-only.",
        "card_filtering_behavior": "Does not add or remove cards. It changes proof visibility for the same card set.",
        "proof_meter_behavior": {
            "none": "Hide compact meters and proof refs.",
            "summary": "Show compact truth, freshness, authority, and risk meter labels.",
            "receipts": "Show compact meters plus receipt/hash refs.",
            "full_developer_proof": "Opt-in only; show all meters and developer proof refs.",
        },
        "device_suitability": {
            "Mac": list(PROOF_DEPTHS),
            "iPad": ["none", "summary", "receipts"],
            "iPhone": ["none", "summary"],
        },
    },
    "urgency": {
        "allowed_values": list(URGENCY_LEVELS),
        "default": "normal",
        "what_it_changes": [
            "How aggressively waiting, due-today, and blocked cards are surfaced.",
            "Whether parked noncritical cards collapse.",
        ],
        "what_it_never_changes": [
            "Gate outcomes.",
            "Authority boundaries.",
            "Proof requirements or protected-action policy.",
        ],
        "authority_implications": "None. urgent never bypasses gates.",
        "card_filtering_behavior": {
            "park": "Keep critical blockers and explicit operator attention; collapse ordinary watch cards.",
            "normal": "Show default current controller cards.",
            "today": "Include current, waiting, and operator-attention cards.",
            "urgent": "Prioritize blockers, protected actions, and waiting cards; gates still block.",
        },
        "proof_meter_behavior": "Risk and authority meters become visible for watch, blocked, and protected states.",
        "device_suitability": {
            "Mac": list(URGENCY_LEVELS),
            "iPad": list(URGENCY_LEVELS),
            "iPhone": ["park", "normal", "today", "urgent"],
        },
    },
    "operator_mode": {
        "allowed_values": list(OPERATOR_MODES),
        "default": "system",
        "what_it_changes": [
            "Which world/lane families are foregrounded.",
            "Which noncritical cards collapse as noise.",
        ],
        "what_it_never_changes": [
            "Guardian blockers.",
            "Authority boundaries.",
            "Proof states or lifecycle states.",
        ],
        "authority_implications": "None. Finance mode does not suppress Guardian or authority blockers; artist mode suppresses business noise unless critical.",
        "card_filtering_behavior": {
            "artist": "Suppress noncritical finance and business-development watch cards unless blocked/protected.",
            "finance": "Show finance cards and all Guardian/authority blockers.",
            "build": "Show build cards and system blockers.",
            "business": "Show business-development cards and protected blockers.",
            "creative": "Show creative/artifact/memory cards and protected blockers.",
            "system": "Show cross-system controller posture.",
        },
        "proof_meter_behavior": "Mode does not hide blocked/protected authority meters.",
        "device_suitability": {
            "Mac": list(OPERATOR_MODES),
            "iPad": list(OPERATOR_MODES),
            "iPhone": ["artist", "finance", "build", "business", "system"],
        },
    },
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


def _meter_map(proof_meter_model: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    card_map: dict[str, dict[str, str]] = {}
    for card_set in proof_meter_model.get("card_meter_sets") or []:
        if not isinstance(card_set, Mapping):
            continue
        meter_map = card_set.get("meter_map") if isinstance(card_set.get("meter_map"), Mapping) else {}
        card_map[str(card_set.get("card_id") or "")] = {
            str(meter_ref): str((meter or {}).get("meter_state") or "unknown")
            for meter_ref, meter in meter_map.items()
            if isinstance(meter, Mapping)
        }
    return card_map


def _card_priority(card: Mapping[str, Any], meters: Mapping[str, str]) -> tuple[int, str]:
    family = str(card.get("card_family") or "")
    lifecycle = str(card.get("lifecycle_state") or "")
    risk = str(meters.get("risk") or "")
    authority = str(meters.get("authority") or "")
    priority = 0
    if family == "current_focus_card":
        priority += 100
    if card.get("operator_attention_required") is True:
        priority += 40
    if lifecycle in {"active", "waiting", "needs_operator"}:
        priority += 20
    if risk in {"blocked", "protected", "pileup_risk"} or authority in {"blocked_gate", "approval_required"}:
        priority += 15
    return (-priority, str(card.get("card_id") or ""))


def _is_machine_contract(card: Mapping[str, Any]) -> bool:
    text = " ".join(
        [
            str(card.get("card_id") or ""),
            str(card.get("card_family") or ""),
            str(card.get("card_type") or ""),
            str(card.get("headline") or ""),
        ]
    ).lower()
    return "machine_contract" in text or "contract_card" in text


def _is_developer_proof(card: Mapping[str, Any]) -> bool:
    proof = card.get("proof") if isinstance(card.get("proof"), Mapping) else {}
    return bool(proof.get("developer_proof_only") is True or str(card.get("card_family") or "") == "artifact_proof_card")


def _is_critical(card: Mapping[str, Any], meters: Mapping[str, str]) -> bool:
    risk = str(meters.get("risk") or "")
    authority = str(meters.get("authority") or "")
    return risk in {"blocked", "protected", "pileup_risk"} or authority in {
        "approval_required",
        "blocked_gate",
        "needs_verification",
        "rejected",
    }


def _is_business_noise(card: Mapping[str, Any], meters: Mapping[str, str]) -> bool:
    world = str(card.get("world_ref") or "")
    family = str(card.get("card_family") or "")
    risk = str(meters.get("risk") or "")
    return world in {"finance", "business_development"} and family in {
        "payment_watch_card",
        "workflow_composer_plan_card",
        "evidence_intake_receipt_card",
        "current_focus_card",
    } and risk in {"watch", "calm"}


def _mode_allows(card: Mapping[str, Any], meters: Mapping[str, str], operator_mode: str) -> bool:
    if _is_critical(card, meters):
        return True
    world = str(card.get("world_ref") or "")
    family = str(card.get("card_family") or "")
    if operator_mode == "system":
        return True
    if operator_mode == "artist":
        return not _is_business_noise(card, meters) and world not in {"business_development"}
    if operator_mode == "finance":
        return world == "finance" or family in {"gate_lock_card", "approval_request_card", "contextual_what_should_i_do_card"}
    if operator_mode == "build":
        return world == "build" or family in {"gate_lock_card", "contextual_what_should_i_do_card"}
    if operator_mode == "business":
        return world == "business_development" or family in {"gate_lock_card", "approval_request_card", "contextual_what_should_i_do_card"}
    if operator_mode == "creative":
        return world in {"creative", "artifact", "memory"} or family in {"gate_lock_card", "contextual_what_should_i_do_card"}
    return True


def _urgency_allows(card: Mapping[str, Any], meters: Mapping[str, str], urgency: str) -> bool:
    if _is_critical(card, meters):
        return True
    lifecycle = str(card.get("lifecycle_state") or "")
    freshness = str(meters.get("freshness") or "")
    risk = str(meters.get("risk") or "")
    if urgency == "park":
        return card.get("operator_attention_required") is True and lifecycle != "resolved"
    if urgency == "today":
        return lifecycle in {"active", "waiting", "needs_operator"} or freshness in {"current", "waiting_external"}
    if urgency == "urgent":
        return card.get("operator_attention_required") is True or risk in {"watch", "blocked", "protected"} or lifecycle in {
            "waiting",
            "needs_operator",
        }
    return lifecycle not in {"archived", "resolved"} and card.get("visible_by_default") is True


def _zoom_filter(
    cards: list[Mapping[str, Any]],
    meter_states: Mapping[str, Mapping[str, str]],
    *,
    zoom_level: str,
    proof_depth: str,
    active_world_ref: str,
    active_thread_ref: str,
) -> list[Mapping[str, Any]]:
    if zoom_level == "moment":
        focus_cards = [card for card in cards if str(card.get("card_family") or "") == "current_focus_card"]
        candidates = focus_cards or [
            card for card in cards if card.get("operator_attention_required") is True and str(card.get("lifecycle_state") or "") == "active"
        ]
        if not candidates:
            candidates = [card for card in cards if str(card.get("lifecycle_state") or "") in {"active", "waiting"}]
        if not candidates:
            candidates = cards
        return sorted(candidates, key=lambda card: _card_priority(card, meter_states.get(str(card.get("card_id") or ""), {})))[:1]

    filtered: list[Mapping[str, Any]] = []
    for card in cards:
        card_id = str(card.get("card_id") or "")
        meters = meter_states.get(card_id, {})
        lifecycle = str(card.get("lifecycle_state") or "")
        world = str(card.get("world_ref") or "")
        thread = str(card.get("thread_ref") or "")
        visible = bool(card.get("visible_by_default") is True)
        critical = _is_critical(card, meters)
        developer_proof = _is_developer_proof(card)
        machine_contract = _is_machine_contract(card)
        include = False
        if zoom_level == "task":
            include = (visible and lifecycle in {"active", "waiting", "needs_operator"}) or critical
        elif zoom_level == "lane":
            include = thread == active_thread_ref and lifecycle != "resolved" and (visible or critical)
        elif zoom_level == "world":
            include = (world == active_world_ref and lifecycle != "resolved" and (visible or critical)) or critical
        elif zoom_level == "system":
            include = lifecycle != "resolved" or critical
        if developer_proof and proof_depth != "full_developer_proof":
            include = False
        if machine_contract:
            include = False
        if include:
            filtered.append(card)
    return sorted(filtered, key=lambda card: _card_priority(card, meter_states.get(str(card.get("card_id") or ""), {})))


def _proof_policy(proof_depth: str) -> dict[str, Any]:
    policies = {
        "none": {
            "visible_meter_refs": [],
            "proof_refs_visible": False,
            "receipt_refs_visible": False,
            "hash_refs_visible": False,
            "sqlite_refs_visible": False,
            "developer_proof_visible": False,
            "requires_explicit_opt_in": False,
        },
        "summary": {
            "visible_meter_refs": ["truth", "freshness", "authority", "risk"],
            "proof_refs_visible": False,
            "receipt_refs_visible": False,
            "hash_refs_visible": False,
            "sqlite_refs_visible": False,
            "developer_proof_visible": False,
            "requires_explicit_opt_in": False,
        },
        "receipts": {
            "visible_meter_refs": ["truth", "freshness", "authority", "evidence", "sync", "risk"],
            "proof_refs_visible": True,
            "receipt_refs_visible": True,
            "hash_refs_visible": True,
            "sqlite_refs_visible": False,
            "developer_proof_visible": False,
            "requires_explicit_opt_in": False,
        },
        "full_developer_proof": {
            "visible_meter_refs": ["truth", "freshness", "authority", "evidence", "sync", "risk"],
            "proof_refs_visible": True,
            "receipt_refs_visible": True,
            "hash_refs_visible": True,
            "sqlite_refs_visible": True,
            "developer_proof_visible": True,
            "requires_explicit_opt_in": True,
        },
    }
    return dict(policies[proof_depth])


def _delegation_policy(delegation_depth: str) -> dict[str, Any]:
    policies = {
        "readback": ("Read current state only.", False, False),
        "plan": ("Return deterministic plan guidance only.", False, False),
        "stage": ("Stage local package/request metadata only.", False, False),
        "safe_work": ("Allow only existing safe internal routes with all protected authority false.", False, False),
        "prepare_approval": ("Prepare approval/gate records only; no execution.", False, False),
        "execute_after_approval_blocked": ("Execution after approval is blocked and future-gated.", True, False),
    }
    description, future_gated, execute_enabled = policies[delegation_depth]
    return {
        "delegation_depth": delegation_depth,
        "description": description,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "execute_after_approval_blocked": delegation_depth == "execute_after_approval_blocked",
        "future_gated": future_gated,
        "execute_after_approval_enabled": execute_enabled,
        "protected_authority_granted": False,
    }


def normalize_knob_state(knobs: Mapping[str, Any] | None = None) -> dict[str, str]:
    state = dict(DEFAULT_KNOB_STATE)
    for key, values in (
        ("zoom_level", ZOOM_LEVELS),
        ("delegation_depth", DELEGATION_DEPTHS),
        ("proof_depth", PROOF_DEPTHS),
        ("urgency", URGENCY_LEVELS),
        ("operator_mode", OPERATOR_MODES),
    ):
        value = str((knobs or {}).get(key) or state[key])
        if value not in values:
            raise ValueError(f"invalid {key}: {value}")
        state[key] = value
    return state


def evaluate_knobs(
    cards: list[Mapping[str, Any]],
    proof_meter_model: Mapping[str, Any],
    knobs: Mapping[str, Any] | None = None,
    *,
    active_world_ref: str = "finance",
    active_thread_ref: str = "capital_hilton",
) -> dict[str, Any]:
    state = normalize_knob_state(knobs)
    meter_states = _meter_map(proof_meter_model)
    mode_and_urgency_cards = [
        card
        for card in cards
        if _mode_allows(card, meter_states.get(str(card.get("card_id") or ""), {}), state["operator_mode"])
        and _urgency_allows(card, meter_states.get(str(card.get("card_id") or ""), {}), state["urgency"])
    ]
    filtered_cards = _zoom_filter(
        mode_and_urgency_cards,
        meter_states,
        zoom_level=state["zoom_level"],
        proof_depth=state["proof_depth"],
        active_world_ref=active_world_ref,
        active_thread_ref=active_thread_ref,
    )
    visible_card_ids = [str(card.get("card_id") or "") for card in filtered_cards]
    machine_contract_card_ids = [str(card.get("card_id") or "") for card in filtered_cards if _is_machine_contract(card)]
    developer_proof_card_ids = [str(card.get("card_id") or "") for card in filtered_cards if _is_developer_proof(card)]
    critical_card_ids = [
        str(card.get("card_id") or "")
        for card in filtered_cards
        if _is_critical(card, meter_states.get(str(card.get("card_id") or ""), {}))
    ]
    return {
        "knob_state": state,
        "active_world_ref": active_world_ref,
        "active_thread_ref": active_thread_ref,
        "visible_card_ids": visible_card_ids,
        "visible_card_count": len(visible_card_ids),
        "critical_card_ids": critical_card_ids,
        "machine_contract_card_ids": machine_contract_card_ids,
        "machine_contract_cards_visible_by_default": False,
        "developer_proof_card_ids": developer_proof_card_ids,
        "proof_policy": _proof_policy(state["proof_depth"]),
        "delegation_policy": _delegation_policy(state["delegation_depth"]),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "knobs_grant_authority": False,
            "urgent_bypasses_gates": False,
            "proof_depth_changes_card_filtering": False,
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


def build_filter_profiles(
    cards: list[Mapping[str, Any]],
    proof_meter_model: Mapping[str, Any],
) -> dict[str, Any]:
    proof_base = {
        "zoom_level": "task",
        "delegation_depth": "readback",
        "urgency": "normal",
        "operator_mode": "finance",
    }
    return {
        "moment_default": evaluate_knobs(cards, proof_meter_model, {"zoom_level": "moment"}),
        "system_zoom": evaluate_knobs(cards, proof_meter_model, {"zoom_level": "system", "operator_mode": "system"}),
        "artist_normal": evaluate_knobs(cards, proof_meter_model, {"operator_mode": "artist", "zoom_level": "task"}),
        "finance_normal": evaluate_knobs(cards, proof_meter_model, {"operator_mode": "finance", "zoom_level": "task"}),
        "urgent_finance": evaluate_knobs(cards, proof_meter_model, {"operator_mode": "finance", "urgency": "urgent", "zoom_level": "world"}),
        "delegation_execute_blocked": evaluate_knobs(
            cards,
            proof_meter_model,
            {"delegation_depth": "execute_after_approval_blocked", "zoom_level": "system"},
        ),
        "proof_none": evaluate_knobs(cards, proof_meter_model, {**proof_base, "proof_depth": "none"}),
        "proof_summary": evaluate_knobs(cards, proof_meter_model, {**proof_base, "proof_depth": "summary"}),
        "proof_receipts": evaluate_knobs(cards, proof_meter_model, {**proof_base, "proof_depth": "receipts"}),
        "proof_full_developer": evaluate_knobs(cards, proof_meter_model, {**proof_base, "proof_depth": "full_developer_proof"}),
    }


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    root = _rooted(read_model_root)
    dynamic_packet = _load_json(root / "dynamic_card_packet_latest.json")
    proof_meters = _load_json(root / "proof_meter_normalization.json")
    cards = [card for card in dynamic_packet.get("cards") or [] if isinstance(card, Mapping)]
    preconditions = _preconditions(read_model_root)
    preconditions_ready = all(row["ready"] for row in preconditions)
    profiles = build_filter_profiles(cards, proof_meters)
    validation_errors: list[str] = []
    for knob_ref, definition in KNOB_DEFINITIONS.items():
        if definition["default"] not in definition["allowed_values"]:
            validation_errors.append(f"{knob_ref}:default_not_allowed")
    if profiles["moment_default"]["visible_card_count"] != 1:
        validation_errors.append("moment_default:visible_card_count_not_one")
    if profiles["system_zoom"]["machine_contract_card_ids"]:
        validation_errors.append("system_zoom:machine_contract_cards_visible")
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS if preconditions_ready and not validation_errors else NOT_READY_STATUS,
        "generated_at": generated_at,
        "source_packet_ref": _source_ref("dynamic_card_packet_latest.json"),
        "source_packet_content_hash": _content_hash(dynamic_packet),
        "proof_meter_ref": _source_ref("proof_meter_normalization.json"),
        "proof_meter_content_hash": _content_hash(proof_meters),
        "default_knob_state": dict(DEFAULT_KNOB_STATE),
        "knob_definitions": KNOB_DEFINITIONS,
        "filter_profiles": profiles,
        "preconditions": preconditions,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "rules": [
            "Knobs change visibility, focus, and staging depth.",
            "Knobs do not grant protected authority.",
            "execute_after_approval remains blocked and future-gated.",
            "proof_depth=full_developer_proof is opt-in.",
            "artist mode suppresses business noise unless critical.",
            "finance mode does not suppress Guardian or authority blockers.",
        ],
        "machine_proof": {
            "preconditions_ready": preconditions_ready,
            "validation_errors": validation_errors,
            "knobs_grant_authority": False,
            "execute_after_approval_enabled": False,
            "urgent_bypasses_gates": False,
            "proof_depth_changes_card_filtering": False,
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
        "# Controller Knobs and Mode Filters",
        "",
        "Status: " + str(read_model["status"]),
        "",
        "Controller knobs let Mission Control act like a controller instead of a dashboard. They change visibility, focus, proof verbosity, and staging depth without granting protected authority.",
        "",
        "## Knobs",
        "",
    ]
    for knob_ref, definition in read_model.get("knob_definitions", {}).items():
        lines.append(f"### {knob_ref}")
        lines.append("")
        lines.append("- Allowed values: " + ", ".join(f"`{value}`" for value in definition["allowed_values"]))
        lines.append(f"- Default: `{definition['default']}`")
        lines.append(f"- Authority implications: {definition['authority_implications']}")
        lines.append("")
    lines.extend(
        [
            "## Filter Profiles",
            "",
        ]
    )
    for profile_ref, profile in read_model.get("filter_profiles", {}).items():
        lines.append(
            f"- `{profile_ref}`: cards=`{profile['visible_card_count']}` proof_depth=`{profile['knob_state']['proof_depth']}` delegation=`{profile['knob_state']['delegation_depth']}`"
        )
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
            "## Proof",
            "",
            f"- Unsafe true grants absent: `{str((read_model.get('machine_proof') or {}).get('unsafe_true_grants_absent')).lower()}`",
            f"- Validation errors: `{len((read_model.get('machine_proof') or {}).get('validation_errors') or [])}`",
            "",
        ]
    )
    return "\n".join(lines)


def export_controller_knob_mode_filters(
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
        "profile_count": str(len(read_model["filter_profiles"])),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish Controller Knobs and Mode Filters V0.")
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
    result = export_controller_knob_mode_filters(
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
