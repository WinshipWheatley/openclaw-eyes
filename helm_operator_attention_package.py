"""Backend-owned Helm operator attention package v0.

This read-model is the product-facing attention decision for Mission Control
Helm. It consumes existing proof/readiness surfaces and decides what should be
primary, collapsed, proof-only, or hidden by default. It does not enable live
models, tools, agents, workflow execution, sends, ledger writes, or production
state mutation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from openclaw_substrate_utils import stable_json, utc_now


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "helm_operator_attention_package_v0"
READ_MODEL_ID = "helm_operator_attention_package"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"

HELM_MODE_CHAT_FIRST = "CHAT_FIRST"
HELM_MODE_DIAGNOSTIC_DETAIL = "DIAGNOSTIC_DETAIL"
HELM_MODE_PROOF_INSPECTION = "PROOF_INSPECTION"

CHECK_QUIET = "QUIET"
CHECK_WARNING = "WARNING"
CHECK_ACTION_REQUIRED = "ACTION_REQUIRED"

VISIBILITY_PRIMARY = "PRIMARY"
VISIBILITY_COLLAPSED = "COLLAPSED"
VISIBILITY_PROOF_ONLY = "PROOF_ONLY"
VISIBILITY_HIDDEN = "HIDDEN"

ACTION_NONE = "NONE"
ACTION_REVIEW = "REVIEW"
ACTION_APPROVE = "APPROVE"
ACTION_DECIDE = "DECIDE"
ACTION_FIX_REQUIRED = "FIX_REQUIRED"

SOURCE_REFS = {
    "declutter": "generated/read_models/operator_mission_priority_helm_declutter.json",
    "health": "generated/read_models/system_health_lights_taxonomy.json",
    "floor": "generated/read_models/floor_gap_reconciliation.json",
    "lm_readiness": "generated/read_models/lm_readiness_dashboard.json",
    "operator_surface": "generated/read_models/operator_readiness_surface.json",
    "bridge": "generated/read_models/request_response_bridge_readiness.json",
    "request_response_service": "generated/read_models/openclaw_request_response_service_status.json",
    "stable_map": "generated/read_models/openclaw_map_manifest.json",
    "security_pass": "generated/read_models/security_pass_contract.json",
    "package_preview": "generated/read_models/package_preview_receipt_contract.json",
    "agent_council": "generated/read_models/agent_terrain_awareness_readback_contract.json",
    "gate1": "generated/read_models/gate1_operational_snapshot.json",
    "gate2": "generated/read_models/intent_ingest_gate.json",
    "gate3": "generated/read_models/role_package_gate.json",
}

AUTHORITY_BOUNDARY = {
    "live_lm_call_allowed": False,
    "model_api_integration_allowed": False,
    "network_allowed": False,
    "provider_key_material_access_allowed": False,
    "agent_dispatch_allowed": False,
    "worker_dispatch_allowed": False,
    "tool_execution_allowed": False,
    "workflow_execution_allowed": False,
    "external_action_allowed": False,
    "send_submit_allowed": False,
    "approval_execution_allowed": False,
    "ledger_posting_allowed": False,
    "production_state_mutation_allowed": False,
    "workbook_body_read_allowed": False,
    "spreadsheet_cell_read_allowed": False,
    "ocr_allowed": False,
    "pdf_generation_allowed": False,
}

BACKEND_SLUDGE_TERMS = (
    "source_request_id",
    "sqlite",
    "gate 2",
    "gate 3",
    "request contract",
    "stable map hash",
    "backend execution blocked",
    "no command path",
    "request marker only",
    "fixture source",
)

ACTIVE_STATUSES = {"ON", "WARNING", "ACTION_REQUIRED", "BLOCKED", "DEGRADED", "STALE"}
QUIET_STATUSES = {"QUIET", "OFF", "OK", "READY", "ON_NORMAL", "INFO"}
ACTION_REQUIRED_STATUSES = {"ACTION_REQUIRED", "BLOCKED", "NEEDS_APPROVAL", "APPROVAL_REQUIRED"}


def _rooted(path: str | Path, *, repo_root: str | Path = ROOT) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return Path(repo_root) / candidate


def _read_json(path: str | Path, *, repo_root: str | Path = ROOT) -> dict[str, Any]:
    target = _rooted(path, repo_root=repo_root)
    if not target.is_file() or target.suffix.lower() != ".json":
        return {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _nested(mapping: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    value: Any = mapping
    for key in keys:
        if not isinstance(value, Mapping):
            return default
        value = value.get(key)
    return default if value is None else value


def _hash_payload(payload: Mapping[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    machine = clone.get("machine_proof")
    if isinstance(machine, dict):
        machine.pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _status(value: Any, default: str = "UNKNOWN") -> str:
    return str(value or default).upper()


def _explicit_bool(mapping: Mapping[str, Any], keys: Iterable[str]) -> bool | None:
    for key in keys:
        if key in mapping and isinstance(mapping[key], bool):
            return mapping[key]
    return None


def _operator_action_required(signal: Mapping[str, Any], missing_fields: list[dict[str, Any]]) -> bool:
    explicit = _explicit_bool(
        signal,
        (
            "operator_action_required",
            "operator_action_required_now",
            "requires_operator_action",
            "approval_required",
        ),
    )
    signal_ref = str(signal.get("signal_ref") or signal.get("light_id") or signal.get("surface_ref") or "unknown")
    if explicit is not None:
        return explicit
    missing_fields.append(
        {
            "source_ref": signal_ref,
            "missing_field": "operator_action_required",
            "derived_from": "status/severity/approval/auto_fix posture",
        }
    )
    status = _status(signal.get("status") or signal.get("current_status") or signal.get("severity"))
    severity = _status(signal.get("severity") or signal.get("current_status") or status)
    auto_fix = bool(signal.get("auto_fix_possible", False))
    if status in ACTION_REQUIRED_STATUSES or severity in ACTION_REQUIRED_STATUSES:
        return True
    if status == "WARNING" and not auto_fix:
        return True
    return False


def _severity_from_status(status: str) -> str:
    if status in ACTION_REQUIRED_STATUSES:
        return CHECK_ACTION_REQUIRED
    if status in ACTIVE_STATUSES:
        return CHECK_WARNING
    if status in QUIET_STATUSES:
        return CHECK_QUIET
    return CHECK_WARNING if status != "UNKNOWN" else CHECK_QUIET


def _plain_summary_for_light(name: str, status: str) -> str:
    if status == CHECK_QUIET:
        return f"{name} is quiet."
    if status == CHECK_ACTION_REQUIRED:
        return f"{name} needs attention."
    return f"{name} has a warning."


def _source_inputs(repo_root: str | Path = ROOT) -> dict[str, dict[str, Any]]:
    return {key: _read_json(path, repo_root=repo_root) for key, path in SOURCE_REFS.items()}


def _connection_state(inputs: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    bridge = inputs.get("bridge", {})
    service = inputs.get("request_response_service", {})
    health = inputs.get("health", {})
    bridge_ready = str(bridge.get("readiness_status") or "").upper() in {
        "READY_FOR_LIVE_REVIEW",
        "READY",
        "SHADOW_READY",
    }
    transmission = _status(_nested(health, "current_light_states", "check_transmission", default="UNKNOWN"))
    bridge_healthy = bridge_ready and transmission in {"QUIET", "OK", "READY", "ON_NORMAL"}
    service_machine = service.get("machine_proof") if isinstance(service.get("machine_proof"), dict) else {}
    response_service_healthy = bool(
        service_machine.get("response_path_present")
        or service_machine.get("per_request_response_written")
        or _nested(bridge, "machine_proof", "per_request_response_written", default=False)
    )
    connected = bool(bridge_ready or response_service_healthy)
    return {
        "openclaw_connected": connected,
        "bridge_healthy": bridge_healthy,
        "response_service_healthy": response_service_healthy,
        "operator_copy": "OpenClaw is connected." if connected else "OpenClaw needs attention.",
        "proof_refs": [
            SOURCE_REFS["bridge"],
            SOURCE_REFS["request_response_service"],
            SOURCE_REFS["health"],
        ],
    }


def _health_signals(inputs: Mapping[str, Mapping[str, Any]], missing_fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    health = inputs.get("health", {})
    lights = health.get("lights") if isinstance(health.get("lights"), list) else []
    signals: list[dict[str, Any]] = []
    for light in lights:
        if not isinstance(light, Mapping):
            continue
        light_id = str(light.get("light_id") or light.get("display_name") or "unknown").lower().replace(" ", "_")
        status = _status(light.get("current_status") or light.get("status"))
        severity = _severity_from_status(status)
        raw_signal = {
            "signal_ref": f"health_light:{light_id}",
            "lane_ref": str(light.get("opens_lane") or light.get("owner") or "system_health"),
            "display_name": str(light.get("display_name") or light_id),
            "status": status,
            "severity": severity,
            "operator_action_required": light.get("operator_action_required"),
            "auto_fix_possible": bool(light.get("auto_fix_possible", False)),
            "safe_next_move": str(light.get("safe_next_move") or "No action needed."),
            "forbidden_actions": list(light.get("forbidden_actions") or ()),
            "required_receipts": list(light.get("required_receipts") or ()),
            "proof_refs": list(light.get("evidence_inputs") or (SOURCE_REFS["health"],)),
            "last_seen_at": health.get("generated_at"),
            "freshness": "current_read_model" if health else "missing_source",
        }
        required = _operator_action_required(raw_signal, missing_fields)
        raw_signal["operator_action_required"] = required
        signals.append(raw_signal)
    if signals:
        return signals

    states = health.get("current_light_states") if isinstance(health.get("current_light_states"), dict) else {}
    for light_id, raw_status in sorted(states.items()):
        status = _status(raw_status)
        signal = {
            "signal_ref": f"health_light:{light_id}",
            "lane_ref": "system_health",
            "display_name": light_id.replace("_", " ").title(),
            "status": status,
            "severity": _severity_from_status(status),
            "auto_fix_possible": False,
            "safe_next_move": "No action needed." if status in QUIET_STATUSES else "Review the warning.",
            "forbidden_actions": [],
            "required_receipts": [],
            "proof_refs": [SOURCE_REFS["health"]],
            "last_seen_at": health.get("generated_at"),
            "freshness": "current_read_model",
        }
        signal["operator_action_required"] = _operator_action_required(signal, missing_fields)
        signals.append(signal)
    return signals


def _declutter_signals(inputs: Mapping[str, Mapping[str, Any]], missing_fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    declutter = inputs.get("declutter", {})
    items = declutter.get("classification_items") if isinstance(declutter.get("classification_items"), list) else []
    signals: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        item_id = str(item.get("item_id") or "unknown")
        bucket = str(item.get("bucket") or "proof_detail")
        status = _status(item.get("current_status_from_source") or "PARKED")
        if bucket == "proof_detail":
            severity = "PROOF_ONLY"
        elif bucket in {"future_gated", "parked", "worlds"} or status == "PARKED":
            severity = "PARKED"
        else:
            severity = _severity_from_status(status)
        signal = {
            "signal_ref": f"declutter:{item_id}",
            "lane_ref": bucket,
            "display_name": str(item.get("display_name") or item_id),
            "status": status,
            "severity": severity,
            "auto_fix_possible": False,
            "safe_next_move": str(item.get("next_safe_move") or "Keep this collapsed unless it becomes relevant."),
            "forbidden_actions": [],
            "required_receipts": [],
            "proof_refs": list(item.get("source_refs") or (SOURCE_REFS["declutter"],)),
            "last_seen_at": declutter.get("generated_at"),
            "freshness": "current_read_model" if declutter else "missing_source",
        }
        signal["operator_action_required"] = _operator_action_required(signal, missing_fields)
        signals.append(signal)
    return signals


def _production_blocker_signals(inputs: Mapping[str, Mapping[str, Any]], missing_fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    floor = inputs.get("floor", {})
    blockers = _nested(floor, "dashboard_honesty", "next_blockers", default=())
    signals: list[dict[str, Any]] = []
    for blocker in blockers if isinstance(blockers, list) else []:
        signal = {
            "signal_ref": f"live_blocker:{blocker}",
            "lane_ref": "production_live_blockers",
            "display_name": str(blocker).replace("_", " "),
            "status": "NOT_ACTIVE",
            "severity": "PROOF_ONLY",
            "operator_action_required": False,
            "auto_fix_possible": False,
            "safe_next_move": "Keep live production authority off until real receipts exist.",
            "forbidden_actions": ["enable live production authority from Helm attention package"],
            "required_receipts": [str(blocker)],
            "proof_refs": [SOURCE_REFS["floor"]],
            "last_seen_at": floor.get("generated_at"),
            "freshness": "current_read_model" if floor else "missing_source",
        }
        _operator_action_required(signal, missing_fields)
        signals.append(signal)
    return signals


def _awareness_matrix(inputs: Mapping[str, Mapping[str, Any]], missing_fields: list[dict[str, Any]]) -> dict[str, Any]:
    signals = [
        *_health_signals(inputs, missing_fields),
        *_declutter_signals(inputs, missing_fields),
        *_production_blocker_signals(inputs, missing_fields),
    ]
    active = [s for s in signals if s["status"] in ACTIVE_STATUSES or s["severity"] in {CHECK_WARNING, CHECK_ACTION_REQUIRED}]
    operator_required = [s for s in signals if bool(s.get("operator_action_required"))]
    auto_fixable = [s for s in signals if bool(s.get("auto_fix_possible"))]
    parked = [s for s in signals if s["severity"] == "PARKED" or s["lane_ref"] in {"parked", "worlds", "future_gated"}]
    proof_only = [s for s in signals if s["severity"] == "PROOF_ONLY" or s["lane_ref"] == "proof_detail"]
    stale = [s for s in signals if str(s.get("freshness")) != "current_read_model"]
    return {
        "summary_only": True,
        "active_signals": active[:8],
        "parked_signals": parked[:8],
        "proof_only_signals": proof_only[:12],
        "operator_required_signals": operator_required[:5],
        "auto_fixable_signals": auto_fixable[:5],
        "stale_signals": stale[:5],
        "counts": {
            "total_signals_considered": len(signals),
            "active": len(active),
            "parked": len(parked),
            "proof_only": len(proof_only),
            "operator_required": len(operator_required),
            "auto_fixable": len(auto_fixable),
            "stale": len(stale),
        },
    }


def _button_suggestions_for_signal(signal: Mapping[str, Any]) -> list[dict[str, Any]]:
    if not signal.get("operator_action_required"):
        return []
    return [
        {
            "button_ref": "review_issue",
            "label": "Review Issue",
            "meaning": "Open the plain issue summary.",
            "enables_action": False,
        },
        {
            "button_ref": "view_proof",
            "label": "View Proof",
            "meaning": "Show evidence behind this warning.",
            "enables_action": False,
        },
        {
            "button_ref": "not_now",
            "label": "Not now",
            "meaning": "Leave this unchanged.",
            "enables_action": False,
        },
    ]


def _primary_cards(matrix: Mapping[str, Any]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    candidates = list(matrix.get("operator_required_signals") or [])
    for signal in candidates[:1]:
        severity = str(signal.get("severity") or CHECK_WARNING)
        actionability = ACTION_FIX_REQUIRED if severity in {CHECK_ACTION_REQUIRED, CHECK_WARNING} else ACTION_REVIEW
        cards.append(
            {
                "card_ref": f"primary:{signal['signal_ref']}",
                "title": str(signal.get("display_name") or "OpenClaw needs attention"),
                "operator_summary": _plain_summary_for_light(str(signal.get("display_name") or "OpenClaw"), severity),
                "actionability": actionability,
                "severity": severity,
                "safe_next_move": str(signal.get("safe_next_move") or "Review the issue."),
                "button_suggestions": _button_suggestions_for_signal(signal),
                "proof_refs": list(signal.get("proof_refs") or ()),
            }
        )
    return cards


def _check_engine(matrix: Mapping[str, Any], primary_cards: list[dict[str, Any]]) -> dict[str, Any]:
    active_count = int(_nested(matrix, "counts", "active", default=0))
    if primary_cards:
        status = CHECK_ACTION_REQUIRED
        summary = "Check Engine needs attention."
        next_move = primary_cards[0]["safe_next_move"]
        action_required = True
        auto_fix_possible = False
        primary_ref = primary_cards[0]["card_ref"]
    elif active_count:
        status = CHECK_WARNING
        summary = "Check Engine has a warning."
        next_move = "OpenClaw can keep the proof available while Helm stays calm."
        action_required = False
        auto_fix_possible = False
        primary_ref = None
    else:
        status = CHECK_QUIET
        summary = "Check Engine is quiet."
        next_move = "No action needed."
        action_required = False
        auto_fix_possible = False
        primary_ref = None
    return {
        "status": status,
        "active_count": active_count,
        "primary_signal_ref": primary_ref,
        "operator_summary": summary,
        "why_it_matters": "Helm should show only the issue the operator can decide, approve, correct, or understand now.",
        "safe_next_move": next_move,
        "operator_action_required": action_required,
        "auto_fix_possible": auto_fix_possible,
        "proof_refs": [
            SOURCE_REFS["health"],
            SOURCE_REFS["declutter"],
            SOURCE_REFS["floor"],
        ],
    }


def _hidden_or_collapsed_surfaces(primary_cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    primary_refs = {card["card_ref"] for card in primary_cards}
    return [
        {
            "surface_ref": "agent_council",
            "visibility": VISIBILITY_COLLAPSED if "primary:agent_council" not in primary_refs else VISIBILITY_PRIMARY,
            "reason": "Agent details are informational unless an agent lane needs operator review.",
            "operator_action_required": False,
            "proof_refs": [SOURCE_REFS["agent_council"]],
        },
        {
            "surface_ref": "package_preview_bay",
            "visibility": VISIBILITY_COLLAPSED,
            "reason": "Package previews help inspection, but they are not the default Helm issue.",
            "operator_action_required": False,
            "proof_refs": [SOURCE_REFS["package_preview"]],
        },
        {
            "surface_ref": "stable_map_proof",
            "visibility": VISIBILITY_PROOF_ONLY,
            "reason": "Current map proof is audit evidence, not primary operator work.",
            "operator_action_required": False,
            "proof_refs": [SOURCE_REFS["stable_map"]],
        },
        {
            "surface_ref": "security_pass_details",
            "visibility": VISIBILITY_PROOF_ONLY,
            "reason": "Security details stay available behind disclosure unless they require action.",
            "operator_action_required": False,
            "proof_refs": [SOURCE_REFS["security_pass"]],
        },
        {
            "surface_ref": "proof_strip",
            "visibility": VISIBILITY_PROOF_ONLY,
            "reason": "Receipts and proof are available when asked.",
            "operator_action_required": False,
            "proof_refs": [SOURCE_REFS["declutter"], SOURCE_REFS["health"]],
        },
        {
            "surface_ref": "boundary_proof",
            "visibility": VISIBILITY_PROOF_ONLY,
            "reason": "Authority boundaries are proof shelf material unless violated.",
            "operator_action_required": False,
            "proof_refs": [SOURCE_REFS["floor"], SOURCE_REFS["operator_surface"]],
        },
        {
            "surface_ref": "readiness_internals",
            "visibility": VISIBILITY_PROOF_ONLY,
            "reason": "Readiness internals are useful proof, not chat-first Helm copy.",
            "operator_action_required": False,
            "proof_refs": [SOURCE_REFS["lm_readiness"], SOURCE_REFS["operator_surface"]],
        },
        {
            "surface_ref": "awareness_matrix_details",
            "visibility": VISIBILITY_COLLAPSED,
            "reason": "Helm receives a summary of signals instead of a full matrix wall.",
            "operator_action_required": False,
            "proof_refs": [SOURCE_REFS["declutter"]],
        },
    ]


def _proof_shelf() -> list[dict[str, Any]]:
    return [
        {"proof_ref": SOURCE_REFS["declutter"], "proof_kind": "declutter_policy", "default_visibility": VISIBILITY_PROOF_ONLY},
        {"proof_ref": SOURCE_REFS["health"], "proof_kind": "health_lights", "default_visibility": VISIBILITY_PROOF_ONLY},
        {"proof_ref": SOURCE_REFS["floor"], "proof_kind": "readiness_floor", "default_visibility": VISIBILITY_PROOF_ONLY},
        {"proof_ref": SOURCE_REFS["lm_readiness"], "proof_kind": "lm_readiness", "default_visibility": VISIBILITY_PROOF_ONLY},
        {"proof_ref": SOURCE_REFS["operator_surface"], "proof_kind": "operator_readiness_surface", "default_visibility": VISIBILITY_PROOF_ONLY},
        {"proof_ref": SOURCE_REFS["bridge"], "proof_kind": "bridge_readiness", "default_visibility": VISIBILITY_PROOF_ONLY},
        {"proof_ref": SOURCE_REFS["stable_map"], "proof_kind": "stable_map", "default_visibility": VISIBILITY_PROOF_ONLY},
        {"proof_ref": SOURCE_REFS["security_pass"], "proof_kind": "security_pass", "default_visibility": VISIBILITY_PROOF_ONLY},
        {"proof_ref": SOURCE_REFS["package_preview"], "proof_kind": "package_preview", "default_visibility": VISIBILITY_PROOF_ONLY},
        {"proof_ref": SOURCE_REFS["agent_council"], "proof_kind": "agent_council", "default_visibility": VISIBILITY_PROOF_ONLY},
    ]


def _attention_policy() -> dict[str, Any]:
    return {
        "primary_only_if": [
            "operator_action_required=true",
            "approval is needed",
            "severity=ACTION_REQUIRED",
            "status=WARNING and auto_fix_possible=false",
            "user opened diagnostic/proof mode",
        ],
        "collapsed_or_proof_only_if": [
            "proof exists but no action is needed",
            "data is diagnostic",
            "package preview is informational",
            "agent council is informational",
            "stable map is current",
            "receipt exists only for audit",
        ],
        "max_primary_cards": 3,
        "default_helm_mode": HELM_MODE_CHAT_FIRST,
        "mac_should_not_infer_attention_from_raw_proof": True,
    }


def _operator_copy(check_engine: Mapping[str, Any], connection: Mapping[str, Any]) -> dict[str, Any]:
    if check_engine["status"] == CHECK_ACTION_REQUIRED:
        status_line = "Check Engine needs attention."
    elif check_engine["status"] == CHECK_WARNING:
        status_line = "Check Engine has a warning."
    else:
        status_line = "Check Engine is quiet."
    return {
        "headline": status_line,
        "connection": connection["operator_copy"],
        "body": "Proof is available.",
        "safe_next_move": str(check_engine["safe_next_move"]),
        "empty_state": "No action needed.",
        "preferred_phrases": [
            "OpenClaw is connected.",
            "No action needed.",
            "Action needs approval.",
            "I need one more detail.",
            "Proof is available.",
            "Check Engine is quiet.",
            "Check Engine needs attention.",
        ],
    }


def _operator_copy_is_clean(operator_copy: Mapping[str, Any]) -> bool:
    text = json.dumps(operator_copy, sort_keys=True).lower()
    return not any(term in text for term in BACKEND_SLUDGE_TERMS)


def build_helm_operator_attention_package(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
    helm_mode: str = HELM_MODE_CHAT_FIRST,
) -> dict[str, Any]:
    inputs = _source_inputs(repo_root)
    missing_fields: list[dict[str, Any]] = []
    matrix = _awareness_matrix(inputs, missing_fields)
    primary_cards = _primary_cards(matrix)
    check_engine = _check_engine(matrix, primary_cards)
    connection = _connection_state(inputs)
    operator_copy = _operator_copy(check_engine, connection)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at or utc_now(),
        "helm_mode": helm_mode,
        "connection_state": connection,
        "check_engine": check_engine,
        "primary_cards": primary_cards[:3],
        "hidden_or_collapsed_surfaces": _hidden_or_collapsed_surfaces(primary_cards),
        "proof_shelf": _proof_shelf(),
        "operator_copy": operator_copy,
        "attention_policy": _attention_policy(),
        "awareness_matrix": matrix,
        "missing_upstream_fields": missing_fields,
        "input_refs": dict(SOURCE_REFS),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "backend_decides_operator_attention": True,
            "chat_first_default": helm_mode == HELM_MODE_CHAT_FIRST,
            "primary_card_count": len(primary_cards[:3]),
            "primary_card_limit_respected": len(primary_cards[:3]) <= 3,
            "agent_council_not_primary_without_action": all(
                item["surface_ref"] != "agent_council" or item["visibility"] != VISIBILITY_PRIMARY
                for item in _hidden_or_collapsed_surfaces(primary_cards)
            ),
            "proof_shelf_available": True,
            "operator_copy_backend_sludge_free": _operator_copy_is_clean(operator_copy),
            "awareness_matrix_summarized": True,
            "all_authority_boundary_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "live_lm_call_performed": False,
            "tool_execution_performed": False,
            "external_action_performed": False,
            "production_state_mutation_performed": False,
            "content_hash": "",
        },
    }
    payload["machine_proof"]["content_hash"] = _hash_payload(payload)
    return payload


def format_helm_operator_attention_package(payload: Mapping[str, Any]) -> str:
    copy = payload["operator_copy"]
    check = payload["check_engine"]
    lines = [
        "# Helm Operator Attention Package",
        "",
        f"Mode: {payload['helm_mode']}",
        f"Status: {check['status']}",
        "",
        "## Operator Summary",
        f"- {copy['connection']}",
        f"- {copy['headline']}",
        f"- {copy['body']}",
        f"- Next safe move: {copy['safe_next_move']}",
        "",
        "## Primary Cards",
    ]
    cards = payload["primary_cards"]
    if cards:
        lines.extend(f"- {card['title']}: {card['operator_summary']}" for card in cards)
    else:
        lines.append("- None. No action needed.")
    lines.extend(["", "## Collapsed / Proof Only"])
    for surface in payload["hidden_or_collapsed_surfaces"]:
        lines.append(f"- {surface['surface_ref']}: {surface['visibility']}.")
    lines.extend(
        [
            "",
            "## Boundary",
            "- This package is read-model output only. It does not enable models, tools, sends, approvals, ledger posting, or production mutation.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def export_helm_operator_attention_package(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
    helm_mode: str = HELM_MODE_CHAT_FIRST,
) -> dict[str, Any]:
    root = Path(repo_root)
    out_dir = _rooted(export_root, repo_root=root)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_helm_operator_attention_package(
        repo_root=root,
        generated_at=generated_at,
        helm_mode=helm_mode,
    )
    json_path = out_dir / JSON_EXPORT_NAME
    operator_path = out_dir / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_helm_operator_attention_package(payload), encoding="utf-8")
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "json_path": json_path.as_posix(),
        "operator_path": operator_path.as_posix(),
        "helm_mode": payload["helm_mode"],
        "check_engine_status": payload["check_engine"]["status"],
        "primary_card_count": len(payload["primary_cards"]),
        "authority_boundary_all_false": payload["machine_proof"]["all_authority_boundary_false"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Helm operator attention package read-model.")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--generated-at")
    parser.add_argument(
        "--helm-mode",
        choices=(HELM_MODE_CHAT_FIRST, HELM_MODE_DIAGNOSTIC_DETAIL, HELM_MODE_PROOF_INSPECTION),
        default=HELM_MODE_CHAT_FIRST,
    )
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    args = parser.parse_args(argv)

    summary = export_helm_operator_attention_package(
        repo_root=args.repo_root,
        export_root=args.export_root,
        generated_at=args.generated_at,
        helm_mode=args.helm_mode,
    )
    if args.format == "json":
        payload = _read_json(summary["json_path"], repo_root=args.repo_root)
        print(stable_json(payload), end="")
    else:
        print(stable_json(summary), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
