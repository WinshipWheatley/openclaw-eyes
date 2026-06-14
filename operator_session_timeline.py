"""Operator Session Timeline V0.

Builds a summarized operator-history timeline from controller events, dynamic
cards, universal receipts, evidence intake, and workroom review decisions. This
records the day as scenes/domains and actors/agents without raw chat dumps.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Operator Session Timeline.md")
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/operator_session_timeline.sqlite")

SCHEMA_VERSION = "operator_session_timeline_v0"
READ_MODEL_ID = "operator_session_timeline"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "OPERATOR_SESSION_TIMELINE_READY"
NOT_READY_STATUS = "OPERATOR_SESSION_TIMELINE_NOT_READY"

SESSION_REF = "operator_session:2026-06-05:pc"
OPERATOR_REF = "operator:winship"
DEVICE_REF = "pc"

TIMELINE_EVENT_TYPES = (
    "session_started",
    "world_entered",
    "lane_entered",
    "controller_event",
    "dynamic_card_shown",
    "proof_attached",
    "evidence_recorded",
    "approval_requested",
    "review_decision_recorded",
    "package_staged",
    "receipt_recorded",
    "card_resolved",
    "session_closed",
)

REQUIRED_EVENT_FIELDS = (
    "timeline_event_id",
    "timestamp",
    "session_ref",
    "operator_ref",
    "device_ref",
    "world_ref",
    "thread_ref",
    "card_id",
    "controller_event_type",
    "receipt_ref",
    "proof_refs",
    "human_summary",
    "hidden_machine_refs",
    "privacy_class",
    "visible_in_history",
    "developer_proof_only",
)

PRECONDITIONS = {
    "operator_controller_event_live_route": {
        "filename": "operator_controller_event_router_contract.json",
        "accepted_statuses": ["OPERATOR_CONTROLLER_EVENT_LIVE_ROUTE_READY", "OPERATOR_CONTROLLER_EVENT_ROUTER_READY"],
    },
    "universal_receipt_envelope": {
        "filename": "universal_receipt_envelope_contract.json",
        "accepted_statuses": ["UNIVERSAL_RECEIPT_ENVELOPE_READY"],
    },
    "dynamic_card_packet_v1": {
        "filename": "dynamic_card_packet_latest.json",
        "accepted_statuses": ["DYNAMIC_CARD_PACKET_V1_READY", "DYNAMIC_CARD_PACKET_READY"],
    },
    "verified_evidence_intake": {
        "filename": "evidence_intake_contract.json",
        "accepted_statuses": ["VERIFIED_EVIDENCE_INTAKE_READY", "EVIDENCE_INTAKE_LIVE_ROUTE_READY", "EVIDENCE_INTAKE_READY"],
    },
    "workroom_review_decision_consumer": {
        "filename": "workroom_review_decision_contract.json",
        "accepted_statuses": ["WORKROOM_REVIEW_DECISION_CONSUMER_READY", "WORKROOM_REVIEW_DECISION_CONTRACT_READY"],
    },
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
    "paid_truth_inferred",
    "ledger_mutation_allowed",
    "ledger_mutation_performed",
    "ledger_truth_inferred",
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
    "timeline_creates_business_truth",
    "prompt_dump_stored",
    "secrets_stored",
}

FORBIDDEN_RAW_KEYS = {
    "raw_prompt",
    "raw_prompt_body",
    "raw_chat",
    "raw_chat_dump",
    "operator_text",
    "operator_message",
    "source_text",
    "prompt",
    "body",
    "secret",
    "token",
    "password",
    "cookie",
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


def _load_first_json(root: Path, *filenames: str) -> dict[str, Any]:
    for filename in filenames:
        payload = _load_json(root / filename)
        if payload:
            return payload
    return {}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")


def _source_ref(filename: str) -> str:
    return f"generated/read_models/{filename}"


def _card_timestamp(card: Mapping[str, Any], fallback_timestamp: str) -> str:
    generated = card.get("source_generated_at")
    if isinstance(generated, Mapping):
        for value in generated.values():
            if str(value):
                return str(value)
        return fallback_timestamp
    return str(generated or fallback_timestamp)


def _short_hash(payload: Any) -> str:
    return hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()[:16]


def _string_list(values: Iterable[Any] | None) -> list[str]:
    if values is None:
        return []
    return list(dict.fromkeys(str(value) for value in values if str(value)))


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


def _contains_forbidden_raw_key(payload: Any) -> bool:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            lowered = str(key).lower()
            if lowered in FORBIDDEN_RAW_KEYS or lowered.endswith("_body") or lowered.startswith("raw_"):
                return True
            if _contains_forbidden_raw_key(value):
                return True
    elif isinstance(payload, list):
        return any(_contains_forbidden_raw_key(value) for value in payload)
    return False


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


def build_timeline_event(
    event_type: str,
    *,
    timestamp: str,
    world_ref: str,
    thread_ref: str,
    card_id: str = "",
    controller_event_type: str = "",
    receipt_ref: str = "",
    proof_refs: Iterable[Any] | None = None,
    human_summary: str,
    hidden_machine_refs: Iterable[Any] | None = None,
    privacy_class: str = "operator_history",
    visible_in_history: bool = True,
    developer_proof_only: bool = False,
    session_ref: str = SESSION_REF,
    operator_ref: str = OPERATOR_REF,
    device_ref: str = DEVICE_REF,
) -> dict[str, Any]:
    if event_type not in TIMELINE_EVENT_TYPES:
        raise ValueError(f"unknown timeline event type: {event_type}")
    seed = {
        "event_type": event_type,
        "timestamp": timestamp,
        "session_ref": session_ref,
        "world_ref": world_ref,
        "thread_ref": thread_ref,
        "card_id": card_id,
        "controller_event_type": controller_event_type,
        "receipt_ref": receipt_ref,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "timeline_event_id": f"timeline_event:{event_type}:{_short_hash(seed)}",
        "timeline_event_type": event_type,
        "timestamp": timestamp,
        "session_ref": session_ref,
        "operator_ref": operator_ref,
        "device_ref": device_ref,
        "world_ref": world_ref,
        "thread_ref": thread_ref,
        "card_id": card_id,
        "controller_event_type": controller_event_type,
        "receipt_ref": receipt_ref,
        "proof_refs": _string_list(proof_refs),
        "human_summary": human_summary,
        "hidden_machine_refs": _string_list(hidden_machine_refs),
        "privacy_class": privacy_class,
        "visible_in_history": visible_in_history,
        "developer_proof_only": developer_proof_only,
    }


def _proof_refs_from_card(card: Mapping[str, Any]) -> list[str]:
    proof = card.get("proof") if isinstance(card.get("proof"), Mapping) else {}
    refs: list[str] = []
    for key in ("receipt_refs", "artifact_refs", "hash_refs", "sqlite_refs", "read_model_refs", "request_refs", "response_refs"):
        values = proof.get(key)
        if isinstance(values, list):
            refs.extend(str(value) for value in values if str(value))
    refs.extend(str(ref) for ref in card.get("source_read_model_refs") or [] if str(ref))
    return list(dict.fromkeys(refs))


def _dynamic_card_events(dynamic_packet: Mapping[str, Any], *, fallback_timestamp: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for card in dynamic_packet.get("cards") or []:
        if not isinstance(card, Mapping):
            continue
        card_id = str(card.get("card_id") or "")
        timestamp = _card_timestamp(card, fallback_timestamp)
        proof_refs = _proof_refs_from_card(card)
        lifecycle = str(card.get("lifecycle_state") or "unknown")
        world_ref = str(card.get("world_ref") or "system")
        thread_ref = str(card.get("thread_ref") or "timeline")
        hidden_refs = [
            _source_ref("dynamic_card_packet_latest.json"),
            *[str(ref) for ref in card.get("source_read_model_refs") or [] if str(ref)],
        ]
        if lifecycle == "resolved":
            events.append(
                build_timeline_event(
                    "card_resolved",
                    timestamp=timestamp,
                    world_ref=world_ref,
                    thread_ref=thread_ref,
                    card_id=card_id,
                    proof_refs=proof_refs,
                    human_summary="Resolved controller card moved to completed history.",
                    hidden_machine_refs=hidden_refs,
                    privacy_class="operator_history",
                    visible_in_history=True,
                )
            )
        elif card.get("visible_by_default") is True:
            events.append(
                build_timeline_event(
                    "dynamic_card_shown",
                    timestamp=timestamp,
                    world_ref=world_ref,
                    thread_ref=thread_ref,
                    card_id=card_id,
                    proof_refs=proof_refs,
                    human_summary=f"Controller showed `{str(card.get('card_family') or 'card')}` for the current scene.",
                    hidden_machine_refs=hidden_refs,
                    privacy_class="operator_history",
                    visible_in_history=True,
                    developer_proof_only=bool((card.get("proof") or {}).get("developer_proof_only") is True),
                )
            )
        if card_id == "dynamic_card.finance.live_arts_md.evidence_intake.payment_processing":
            evidence_refs = proof_refs or [_source_ref("evidence_intake_contract.json")]
            for event_type, summary in (
                ("proof_attached", "Proof was attached as protected local evidence metadata for a finance lane."),
                ("evidence_recorded", "Evidence candidate recorded; paid and ledger truth were not inferred."),
            ):
                events.append(
                    build_timeline_event(
                        event_type,
                        timestamp=timestamp,
                        world_ref="finance",
                        thread_ref="live_arts_md",
                        card_id=card_id,
                        controller_event_type="attach_proof",
                        proof_refs=evidence_refs,
                        human_summary=summary,
                        hidden_machine_refs=[_source_ref("evidence_intake_status.json"), _source_ref("evidence_intake_contract.json")],
                        privacy_class="protected_reference",
                    )
                )
        for action in card.get("actions") or []:
            if not isinstance(action, Mapping):
                continue
            if (
                card.get("world_ref") == "finance"
                and card.get("thread_ref") == "capital_hilton"
                and action.get("controller_event_type") == "ask_why"
            ):
                events.append(
                    build_timeline_event(
                        "controller_event",
                        timestamp=timestamp,
                        world_ref="finance",
                        thread_ref="capital_hilton",
                        card_id=card_id,
                        controller_event_type="ask_why",
                        receipt_ref=str(action.get("payload_ref") or _source_ref("operator_action_payloads.json")),
                        proof_refs=proof_refs,
                        human_summary="Finance / Capital Hilton `ask_why` returned payment-watch context without execution.",
                        hidden_machine_refs=[
                            _source_ref("operator_controller_event_router_status.json"),
                            _source_ref("operator_controller_event_router_contract.json"),
                        ],
                        privacy_class="operator_history",
                    )
                )
    return events


def _receipt_events(universal_receipts: Mapping[str, Any], *, fallback_timestamp: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for receipt in universal_receipts.get("receipts") or []:
        if not isinstance(receipt, Mapping):
            continue
        receipt_type = str(receipt.get("receipt_type") or "")
        event_type = "receipt_recorded"
        if receipt_type == "approval_recorded":
            event_type = "approval_requested"
        elif receipt_type == "package_staged":
            event_type = "package_staged"
        elif receipt_type == "review_decision_recorded":
            event_type = "review_decision_recorded"
        elif receipt_type == "evidence_recorded":
            event_type = "evidence_recorded"
        elif receipt_type == "dynamic_card_emitted":
            event_type = "dynamic_card_shown"
        elif receipt_type == "controller_event_received":
            event_type = "controller_event"
        proof_refs = [
            *[str(ref) for ref in receipt.get("proof_refs") or [] if str(ref)],
            *[str(ref) for ref in receipt.get("artifact_refs") or [] if str(ref)],
            *[str(ref) for ref in receipt.get("hash_refs") or [] if str(ref)],
            *[str(ref) for ref in receipt.get("read_model_refs") or [] if str(ref)],
        ]
        world_ref = str(receipt.get("world_ref") or "system")
        thread_ref = str(receipt.get("thread_ref") or "timeline")
        card_id = str(receipt.get("card_id") or "")
        if receipt_type == "review_decision_recorded" and not card_id:
            card_id = "dynamic_card.build.review_packet.completed_historical_receipt"
        if receipt_type == "evidence_recorded" and not card_id and world_ref == "finance" and thread_ref == "live_arts_md":
            card_id = "dynamic_card.finance.live_arts_md.evidence_intake.payment_processing"
        controller_event_type = (
            str(receipt.get("controller_event_id") or "").split(":", 2)[1]
            if str(receipt.get("controller_event_id") or "").startswith("controller_event:")
            else ""
        )
        if receipt_type == "evidence_recorded" and not controller_event_type:
            controller_event_type = "attach_proof"
        events.append(
            build_timeline_event(
                event_type,
                timestamp=str(receipt.get("created_at") or fallback_timestamp),
                world_ref=world_ref,
                thread_ref=thread_ref,
                card_id=card_id,
                controller_event_type=controller_event_type,
                receipt_ref=str(receipt.get("receipt_id") or ""),
                proof_refs=proof_refs,
                human_summary=_receipt_summary(receipt),
                hidden_machine_refs=[
                    _source_ref("universal_receipt_envelope_status.json"),
                    *[str(ref) for ref in receipt.get("sqlite_refs") or [] if str(ref)],
                ],
                privacy_class="protected_reference" if str(receipt.get("client_ref") or "") else "operator_history",
                visible_in_history=True,
            )
        )
    return events


def _receipt_summary(receipt: Mapping[str, Any]) -> str:
    receipt_type = str(receipt.get("receipt_type") or "")
    if receipt_type == "controller_event_received":
        return "Controller event recorded for the current lane; route stayed safe and non-executing."
    if receipt_type == "evidence_recorded":
        return "Evidence candidate recorded; paid and ledger truth were not inferred."
    if receipt_type == "package_staged":
        return "Package staged for operator review; no send, submit, or business execution."
    if receipt_type == "approval_recorded":
        return "Approval need recorded; approval receipt is not execution proof."
    if receipt_type == "review_decision_recorded":
        return "Workroom review was marked informational and moved to completed history; no merge or push."
    if receipt_type == "gate_blocked":
        return "Protected gate blocked; no authority was granted."
    if receipt_type == "dynamic_card_emitted":
        return "Receipt-backed dynamic card emitted for Mission Control."
    return "Universal receipt recorded as summarized history."


def _controller_event_from_status(status: Mapping[str, Any], *, fallback_timestamp: str) -> list[dict[str, Any]]:
    receipt = status.get("latest_receipt") if isinstance(status.get("latest_receipt"), Mapping) else {}
    if not receipt:
        return []
    card = receipt.get("dynamic_card_response") if isinstance(receipt.get("dynamic_card_response"), Mapping) else {}
    proof = card.get("proof") if isinstance(card.get("proof"), Mapping) else {}
    proof_refs = [
        *[str(ref) for ref in proof.get("proof_refs") or [] if str(ref)],
        *[str(ref) for ref in proof.get("read_model_refs") or [] if str(ref)],
        *[str(ref) for ref in proof.get("receipt_refs") or [] if str(ref)],
    ]
    world_ref = str(receipt.get("current_world_ref") or card.get("target_world_ref") or "system")
    thread_ref = str(receipt.get("current_thread_ref") or card.get("target_thread_ref") or "timeline")
    controller_event_type = str(receipt.get("controller_event_type") or card.get("controller_event_type") or "")
    return [
        build_timeline_event(
            "world_entered",
            timestamp=str(receipt.get("generated_at") or fallback_timestamp),
            world_ref=world_ref,
            thread_ref="world",
            proof_refs=[_source_ref("operator_controller_event_router_status.json")],
            human_summary=f"Entered `{world_ref}` world for controller work.",
            hidden_machine_refs=[_source_ref("operator_controller_event_router_status.json")],
            privacy_class="operator_history",
        ),
        build_timeline_event(
            "lane_entered",
            timestamp=str(receipt.get("generated_at") or fallback_timestamp),
            world_ref=world_ref,
            thread_ref=thread_ref,
            proof_refs=[_source_ref("operator_controller_event_router_status.json")],
            human_summary=f"Entered `{thread_ref}` lane in `{world_ref}`.",
            hidden_machine_refs=[_source_ref("operator_controller_event_router_status.json")],
            privacy_class="operator_history",
        ),
        build_timeline_event(
            "controller_event",
            timestamp=str(receipt.get("generated_at") or fallback_timestamp),
            world_ref=world_ref,
            thread_ref=thread_ref,
            card_id=str(card.get("card_id") or receipt.get("active_entity_ref") or ""),
            controller_event_type=controller_event_type,
            receipt_ref=str(proof.get("receipt_refs", [""])[0]) if isinstance(proof.get("receipt_refs"), list) and proof.get("receipt_refs") else str(receipt.get("receipt_id") or ""),
            proof_refs=proof_refs,
            human_summary="Lane-aware `ask_why` controller event returned payment-watch context without execution."
            if controller_event_type == "ask_why"
            else "Lane-aware controller event recorded without protected execution.",
            hidden_machine_refs=[
                _source_ref("operator_controller_event_router_status.json"),
                _source_ref("operator_controller_event_router_contract.json"),
            ],
            privacy_class="operator_history",
        ),
    ]


def _evidence_events(status: Mapping[str, Any], *, fallback_timestamp: str) -> list[dict[str, Any]]:
    record = status.get("latest_record") if isinstance(status.get("latest_record"), Mapping) else {}
    if not record:
        return []
    artifact = record.get("artifact") if isinstance(record.get("artifact"), Mapping) else {}
    timestamp = str(record.get("created_at") or fallback_timestamp)
    world_ref = str(record.get("current_world_ref") or "finance")
    thread_ref = str(record.get("current_thread_ref") or "evidence_intake")
    artifact_ref = str(record.get("artifact_ref") or artifact.get("artifact_ref") or "")
    proof_refs = [
        _source_ref("evidence_intake_status.json"),
        artifact_ref,
        str(status.get("sqlite_path") or ""),
        str(status.get("artifact_lineage_sqlite_path") or ""),
    ]
    return [
        build_timeline_event(
            "proof_attached",
            timestamp=timestamp,
            world_ref=world_ref,
            thread_ref=thread_ref,
            card_id="dynamic_card.finance.live_arts_md.evidence_intake.payment_processing",
            controller_event_type="attach_proof",
            proof_refs=proof_refs,
            human_summary="Proof was attached as protected local evidence metadata for a finance lane.",
            hidden_machine_refs=[
                _source_ref("evidence_intake_status.json"),
                str(status.get("artifact_lineage_sqlite_path") or ""),
            ],
            privacy_class="protected_reference",
        ),
        build_timeline_event(
            "evidence_recorded",
            timestamp=timestamp,
            world_ref=world_ref,
            thread_ref=thread_ref,
            card_id="dynamic_card.finance.live_arts_md.evidence_intake.payment_processing",
            controller_event_type="attach_proof",
            proof_refs=proof_refs,
            human_summary="Evidence candidate recorded; paid and ledger truth were not inferred.",
            hidden_machine_refs=[
                _source_ref("evidence_intake_status.json"),
                str(status.get("sqlite_path") or ""),
            ],
            privacy_class="protected_reference",
        ),
    ]


def _workroom_events(status: Mapping[str, Any], *, fallback_timestamp: str) -> list[dict[str, Any]]:
    decision = status.get("last_decision") if isinstance(status.get("last_decision"), Mapping) else {}
    if not decision:
        receipts = [receipt for receipt in status.get("example_decision_receipts") or [] if isinstance(receipt, Mapping)]
        decision = next((receipt for receipt in receipts if receipt.get("decision_action") == "mark_review_packet_informational"), {})
    if not decision:
        return []
    contract_receipt = decision.get("contract_receipt") if isinstance(decision.get("contract_receipt"), Mapping) else {}
    receipt_ref = str(decision.get("receipt_id") or contract_receipt.get("receipt_id") or "")
    return [
        build_timeline_event(
            "review_decision_recorded",
            timestamp=str(decision.get("generated_at") or contract_receipt.get("generated_at") or fallback_timestamp),
            world_ref="build",
            thread_ref="workroom_review",
            card_id="dynamic_card.build.review_packet.completed_historical_receipt",
            controller_event_type=str(decision.get("decision_action") or contract_receipt.get("decision_action") or ""),
            receipt_ref=receipt_ref,
            proof_refs=[
                _source_ref("workroom_review_decision_status.json"),
                _source_ref("workroom_review_decision_contract.json"),
                receipt_ref,
            ],
            human_summary="Workroom review was marked informational and moved to completed history; no merge or push.",
            hidden_machine_refs=[
                _source_ref("workroom_review_decision_status.json"),
                _source_ref("workroom_review_packet_index.json"),
            ],
            privacy_class="operator_history",
            visible_in_history=True,
        )
    ]


def build_timeline_events(
    sources: Mapping[str, Mapping[str, Any]],
    *,
    generated_at: str,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = [
        build_timeline_event(
            "session_started",
            timestamp=generated_at,
            world_ref="system",
            thread_ref="session",
            proof_refs=[_source_ref("operator_session_timeline.json")],
            human_summary="Operator session timeline started for PC Mission Control handoff.",
            hidden_machine_refs=[_source_ref("operator_session_timeline.json")],
            privacy_class="session_metadata",
        )
    ]
    events.extend(_controller_event_from_status(sources.get("operator_controller_event_router_status", {}), fallback_timestamp=generated_at))
    events.extend(_dynamic_card_events(sources.get("dynamic_card_packet_latest", {}), fallback_timestamp=generated_at))
    events.extend(_evidence_events(sources.get("evidence_intake_status", {}), fallback_timestamp=generated_at))
    events.extend(_workroom_events(sources.get("workroom_review_decision_status", {}), fallback_timestamp=generated_at))
    events.extend(_receipt_events(sources.get("universal_receipt_envelope_status", {}), fallback_timestamp=generated_at))
    events.append(
        build_timeline_event(
            "session_closed",
            timestamp=generated_at,
            world_ref="system",
            thread_ref="session",
            proof_refs=[_source_ref("operator_session_timeline.json")],
            human_summary="Operator session timeline closed as summarized history.",
            hidden_machine_refs=[_source_ref("operator_session_timeline.json")],
            privacy_class="session_metadata",
        )
    )
    deduped = {event["timeline_event_id"]: event for event in events}
    return sorted(deduped.values(), key=lambda event: (str(event["timestamp"]), str(event["timeline_event_id"])))


def validate_event(event: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in REQUIRED_EVENT_FIELDS:
        if field not in event:
            errors.append(f"missing_field:{field}")
    event_type = str(event.get("timeline_event_type") or "")
    if event_type not in TIMELINE_EVENT_TYPES:
        errors.append(f"unknown_event_type:{event_type}")
    if not isinstance(event.get("proof_refs"), list):
        errors.append("proof_refs_not_list")
    if not isinstance(event.get("hidden_machine_refs"), list):
        errors.append("hidden_machine_refs_not_list")
    if event.get("visible_in_history") is not True and event.get("visible_in_history") is not False:
        errors.append("visible_in_history_not_bool")
    if event.get("developer_proof_only") is not True and event.get("developer_proof_only") is not False:
        errors.append("developer_proof_only_not_bool")
    if _contains_forbidden_raw_key(event):
        errors.append("forbidden_raw_key_present")
    return errors


def _write_sqlite(sqlite_path: Path, events: list[Mapping[str, Any]]) -> int:
    sqlite_path = _rooted(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sqlite_path)
    try:
        conn.execute("DROP TABLE IF EXISTS operator_session_timeline")
        conn.execute(
            """
            CREATE TABLE operator_session_timeline (
              timeline_event_id TEXT PRIMARY KEY,
              timeline_event_type TEXT NOT NULL,
              timestamp TEXT NOT NULL,
              session_ref TEXT NOT NULL,
              operator_ref TEXT NOT NULL,
              device_ref TEXT NOT NULL,
              world_ref TEXT NOT NULL,
              thread_ref TEXT NOT NULL,
              card_id TEXT NOT NULL,
              controller_event_type TEXT NOT NULL,
              receipt_ref TEXT NOT NULL,
              proof_refs_json TEXT NOT NULL,
              human_summary TEXT NOT NULL,
              hidden_machine_refs_json TEXT NOT NULL,
              privacy_class TEXT NOT NULL,
              visible_in_history INTEGER NOT NULL,
              developer_proof_only INTEGER NOT NULL
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO operator_session_timeline (
              timeline_event_id, timeline_event_type, timestamp, session_ref,
              operator_ref, device_ref, world_ref, thread_ref, card_id,
              controller_event_type, receipt_ref, proof_refs_json,
              human_summary, hidden_machine_refs_json, privacy_class,
              visible_in_history, developer_proof_only
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    event["timeline_event_id"],
                    event["timeline_event_type"],
                    event["timestamp"],
                    event["session_ref"],
                    event["operator_ref"],
                    event["device_ref"],
                    event["world_ref"],
                    event["thread_ref"],
                    event["card_id"],
                    event["controller_event_type"],
                    event["receipt_ref"],
                    json.dumps(event["proof_refs"], sort_keys=True),
                    event["human_summary"],
                    json.dumps(event["hidden_machine_refs"], sort_keys=True),
                    event["privacy_class"],
                    1 if event["visible_in_history"] else 0,
                    1 if event["developer_proof_only"] else 0,
                )
                for event in events
            ],
        )
        conn.commit()
        row = conn.execute("SELECT COUNT(*) FROM operator_session_timeline").fetchone()
        return int(row[0])
    finally:
        conn.close()


def sqlite_event_count(sqlite_path: Path = DEFAULT_SQLITE_PATH) -> int:
    conn = sqlite3.connect(_rooted(sqlite_path))
    try:
        row = conn.execute("SELECT COUNT(*) FROM operator_session_timeline").fetchone()
        return int(row[0])
    finally:
        conn.close()


def _load_sources(read_model_root: Path) -> dict[str, dict[str, Any]]:
    root = _rooted(read_model_root)
    return {
        "operator_controller_event_router_status": _load_first_json(
            root, "operator_controller_event_router_status.json", "operator_controller_event_router_contract.json"
        ),
        "universal_receipt_envelope_status": _load_first_json(
            root, "universal_receipt_envelope_status.json", "universal_receipt_envelope_contract.json"
        ),
        "dynamic_card_packet_latest": _load_json(root / "dynamic_card_packet_latest.json"),
        "evidence_intake_status": _load_first_json(root, "evidence_intake_status.json", "evidence_intake_contract.json"),
        "workroom_review_decision_status": _load_first_json(
            root, "workroom_review_decision_status.json", "workroom_review_decision_contract.json"
        ),
    }


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    sources = _load_sources(read_model_root)
    preconditions = _preconditions(read_model_root)
    events = build_timeline_events(sources, generated_at=generated_at)
    validation_errors = [error for event in events for error in validate_event(event)]
    sqlite_row_count = _write_sqlite(sqlite_path, events)
    event_type_counts = {event_type: 0 for event_type in TIMELINE_EVENT_TYPES}
    for event in events:
        event_type_counts[str(event["timeline_event_type"])] += 1
    completed_history_count = event_type_counts.get("card_resolved", 0)
    preconditions_ready = all(row["ready"] for row in preconditions)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS if preconditions_ready and not validation_errors and sqlite_row_count == len(events) else NOT_READY_STATUS,
        "generated_at": generated_at,
        "session_ref": SESSION_REF,
        "operator_ref": OPERATOR_REF,
        "device_ref": DEVICE_REF,
        "event_count": len(events),
        "sqlite_row_count": sqlite_row_count,
        "event_type_counts": event_type_counts,
        "completed_history_event_count": completed_history_count,
        "timeline_events": events,
        "preconditions": preconditions,
        "sqlite_path": str(_rooted(sqlite_path)),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "rules": [
            "No raw prompt dumps.",
            "No secrets.",
            "No client PII beyond protected refs.",
            "History is summarized and receipt-backed.",
            "Resolved cards move to completed/history.",
            "Timeline does not create business truth.",
            "Ledger and paid truth remain separate.",
        ],
        "machine_proof": {
            "preconditions_ready": preconditions_ready,
            "validation_errors": validation_errors,
            "sqlite_row_count_matches_json": sqlite_row_count == len(events),
            "prompt_dump_stored": False,
            "secrets_stored": False,
            "client_pii_beyond_protected_refs_stored": False,
            "timeline_creates_business_truth": False,
            "paid_truth_inferred": False,
            "ledger_truth_inferred": False,
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
        "# Operator Session Timeline",
        "",
        "Status: " + str(read_model["status"]),
        "",
        "Operator Session Timeline V0 records the day as summarized scenes/domains, controller events, cards, receipts, evidence, and review decisions. It does not store raw chat dumps.",
        "",
        "## Rules",
        "",
    ]
    for rule in read_model.get("rules") or []:
        lines.append(f"- {rule}")
    lines.extend(["", "## Event Counts", ""])
    for event_type, count in (read_model.get("event_type_counts") or {}).items():
        lines.append(f"- `{event_type}`: `{count}`")
    lines.extend(["", "## Timeline", ""])
    for event in read_model.get("timeline_events") or []:
        if not event.get("visible_in_history"):
            continue
        lines.append(
            f"- `{event['timestamp']}` `{event['timeline_event_type']}` {event['world_ref']}/{event['thread_ref']}: {event['human_summary']}"
        )
    lines.extend(
        [
            "",
            "## Proof",
            "",
            f"- SQLite: `{read_model.get('sqlite_path')}`",
            f"- JSON events: `{read_model.get('event_count')}`",
            f"- SQLite rows: `{read_model.get('sqlite_row_count')}`",
            f"- Unsafe true grants absent: `{str((read_model.get('machine_proof') or {}).get('unsafe_true_grants_absent')).lower()}`",
            "",
        ]
    )
    return "\n".join(lines)


def export_operator_session_timeline(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_read_model(read_model_root=read_model_root, sqlite_path=sqlite_path, generated_at=generated_at)
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
        "sqlite_path": str(_rooted(sqlite_path)),
        "wiki_path": wiki_path.as_posix(),
        "event_count": str(read_model["event_count"]),
        "sqlite_row_count": str(read_model["sqlite_row_count"]),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish Operator Session Timeline V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT))
    parser.add_argument("--sqlite-path", default=str(DEFAULT_SQLITE_PATH))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_operator_session_timeline(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
        sqlite_path=Path(args.sqlite_path),
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
