"""OpenClaw Workroom Activity Feed V0.

Builds compact local Workroom channel posts from package events, conversation
journal entries, handoff rules, and spawned worker lifecycle examples. This is
read-model generation only. It does not connect Slack or Telegram, send
messages, call live providers, mutate business state, export PDFs, submit
anything, mark paid, or push git state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/OpenClaw Workroom Activity Feed.md")

SCHEMA_VERSION = "openclaw_workroom_activity_feed_v0"
READ_MODEL_ID = "openclaw_workroom_activity_feed"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
FEED_STATUS = "OPENCLAW_WORKROOM_ACTIVITY_FEED_READY"
FEED_NOT_READY_STATUS = "OPENCLAW_WORKROOM_ACTIVITY_FEED_NOT_READY"

PRECONDITION_FILES = {
    "openclaw_workroom_registry": "openclaw_workroom_registry.json",
    "agent_handoff_registry": "agent_handoff_registry.json",
    "spawned_worker_package_lifecycle": "spawned_worker_package_lifecycle.json",
    "package_event_index": "package_event_index.json",
    "operator_conversation_journal": "operator_conversation_journal.json",
}

PRECONDITION_STATUSES = {
    "openclaw_workroom_registry": "OPENCLAW_WORKROOM_REGISTRY_READY",
    "agent_handoff_registry": "AGENT_HANDOFF_REGISTRY_READY",
    "spawned_worker_package_lifecycle": "SPAWNED_WORKER_PACKAGE_LIFECYCLE_READY",
    "package_event_index": "PACKAGE_EVENT_INDEX_READY",
    "operator_conversation_journal": "OPERATOR_CONVERSATION_JOURNAL_READY",
}

WORKFLOW_CHANNELS = {
    "st_annes_work_log_event": {
        "channel_ref": "finance_st_annes",
        "speaker_ref": "cassandra",
        "headline": "St Anne's work-log package staged",
        "next_safe_action": "Review the work-log proof; do not mutate workbook or invoice state from this feed.",
    },
    "capital_hilton_invoice_operator_assist": {
        "channel_ref": "finance_capital_hilton",
        "speaker_ref": "chief",
        "headline": "Capital Hilton invoice operator-assist gate",
        "next_safe_action": "Review the provider gate and operator-assist proof; do not submit from this feed.",
    },
    "capital_hilton_proposal_followup": {
        "channel_ref": "business_development_capital_hilton",
        "speaker_ref": "cassandra",
        "headline": "Capital Hilton proposal follow-up staged",
        "next_safe_action": "Review proposal follow-up state; do not infer paid or send from this feed.",
    },
    "system_question_answer": {
        "channel_ref": "operations_chief_workboard",
        "speaker_ref": "openclaw",
        "headline": "System question answered",
        "next_safe_action": "Review the local answer proof refs; do not trigger live tools from this feed.",
    },
}

CHANNEL_WORLD_THREAD = {
    "finance_st_annes": ("finance", "st_annes"),
    "finance_capital_hilton": ("finance", "capital_hilton"),
    "business_development_capital_hilton": ("business_development", "capital_hilton"),
    "build_mission_control_mac": ("build", "build_mission_control_mac"),
    "build_openclaw_backend": ("build", "build_openclaw_backend"),
    "architecture_hermes": ("architecture", "architecture_hermes"),
    "security_guardian_gates": ("security", "security_guardian_gates"),
    "operations_chief_workboard": ("operations", "operations_chief_workboard"),
    "helm_daily_desk": ("helm", "helm_daily_desk"),
}

ALLOWED_SPEAKERS = {
    "cassandra",
    "chief",
    "hermes",
    "guardian",
    "niles",
    "openclaw",
    "pc_codex",
    "mac_codex",
}

AUTHORITY_BOUNDARY = {
    "slack_connect_allowed": False,
    "telegram_live_connect_allowed": False,
    "message_send_allowed": False,
    "email_send_allowed": False,
    "gmail_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_posting_allowed": False,
    "ledger_mutation_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "paid_marking_allowed": False,
    "submit_allowed": False,
    "git_push_allowed": False,
    "worker_spawn_allowed": False,
    "agent_loop_allowed": False,
    "external_llm_allowed": False,
    "live_provider_allowed": False,
    "business_action_allowed": False,
    "sent": False,
    "paid": False,
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


def _preconditions(read_model_root: Path) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows: list[dict[str, Any]] = []
    for ref, filename in PRECONDITION_FILES.items():
        payload = _load_json(root / filename)
        observed = str(payload.get("status") or payload.get("contract_status") or "")
        required = PRECONDITION_STATUSES[ref]
        rows.append(
            {
                "precondition_ref": ref,
                "required_status": required,
                "observed_status": observed,
                "ready": observed == required,
                "source_ref": f"generated/read_models/{filename}",
            }
        )
    return rows


def _source_payloads(read_model_root: Path) -> dict[str, dict[str, Any]]:
    root = _rooted(read_model_root)
    payloads = {
        ref: _load_json(root / filename)
        for ref, filename in PRECONDITION_FILES.items()
    }
    payloads["operator_next_decision"] = _load_json(root / "operator_next_decision.json")
    payloads["helm_action_lifecycle_status"] = _load_json(root / "helm_action_lifecycle_status.json")
    return payloads


def _short_hash(parts: list[str]) -> str:
    joined = "\n".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


def _normalize_text(value: Any, fallback: str) -> str:
    text = " ".join(str(value or "").strip().split())
    return text if text else fallback


def _status_label(value: Any) -> str:
    text = str(value or "STATUS").strip()
    if not text:
        return "Status"
    return text.replace("_", " ").title()


def _channel_world_thread(channel_ref: str) -> tuple[str, str]:
    return CHANNEL_WORLD_THREAD.get(channel_ref, ("operations", channel_ref))


def _safe_speaker(value: Any) -> str:
    speaker = str(value or "openclaw").strip().lower()
    return speaker if speaker in ALLOWED_SPEAKERS else "openclaw"


def _proof_ref_value(item: Any) -> str:
    if isinstance(item, Mapping):
        value = item.get("ref") or item.get("path") or item.get("source_ref")
        return str(value or "")
    return str(item or "")


def _proof_refs(*groups: Any, limit: int = 8) -> list[str]:
    refs: list[str] = []
    for group in groups:
        if isinstance(group, list):
            for item in group:
                value = _proof_ref_value(item)
                if value:
                    refs.append(value)
        else:
            value = _proof_ref_value(group)
            if value:
                refs.append(value)
    return list(dict.fromkeys(refs))[:limit]


def _business_action_already_ingested(source: Mapping[str, Any]) -> bool:
    authority = source.get("authority_summary") if isinstance(source.get("authority_summary"), Mapping) else {}
    if source.get("business_action_performed") is not True and authority.get("business_action_performed") is not True:
        return False
    return (
        authority.get("business_action_source") == "existing_operator_ingested_read_model"
        and authority.get("does_not_create_new_business_truth") is True
    )


def _post(
    *,
    source_kind: str,
    source_id: str,
    channel_ref: str,
    timestamp: str,
    speaker_ref: str,
    post_type: str,
    headline: str,
    plain_summary: str,
    status_label: str,
    next_safe_action: str,
    target_world_ref: str,
    target_thread_ref: str,
    package_id: str = "",
    proof_refs: list[str] | None = None,
    business_action_performed: bool = False,
) -> dict[str, Any]:
    return {
        "post_id": f"workroom_post:{_short_hash([source_kind, source_id, channel_ref])}",
        "channel_ref": channel_ref,
        "timestamp": timestamp,
        "speaker_ref": _safe_speaker(speaker_ref),
        "post_type": post_type,
        "headline": _normalize_text(headline, "Workroom status"),
        "plain_summary": _normalize_text(plain_summary, "Local read-model status is available."),
        "status_label": _normalize_text(status_label, "Status"),
        "next_safe_action": _normalize_text(next_safe_action, "Review collapsed proof refs before taking any action."),
        "target_world_ref": target_world_ref,
        "target_thread_ref": target_thread_ref,
        "package_id": str(package_id or ""),
        "proof_refs": list(dict.fromkeys(proof_refs or [])),
        "show_machine_details_by_default": False,
        "business_action_performed": bool(business_action_performed),
    }


def _post_type_for_package(status: Any, workflow_ref: str) -> str:
    status_text = str(status or "").upper()
    if "BLOCK" in status_text or "GATE" in status_text:
        return "blocker"
    if workflow_ref == "system_question_answer":
        return "question_answer"
    return "status"


def _package_event_post(event: Mapping[str, Any]) -> dict[str, Any] | None:
    workflow_ref = str(event.get("workflow_ref") or "")
    mapping = WORKFLOW_CHANNELS.get(workflow_ref)
    if not mapping:
        return None
    channel_ref = str(mapping["channel_ref"])
    target_world_ref = str(event.get("target_world_ref") or _channel_world_thread(channel_ref)[0])
    target_thread_ref = str(event.get("target_thread_ref") or _channel_world_thread(channel_ref)[1])
    status = event.get("package_status") or event.get("action_status")
    source_id = str(event.get("event_id") or event.get("package_id") or workflow_ref)
    proof = _proof_refs(
        event.get("proof_refs"),
        event.get("linked_read_models"),
        f"generated/read_models/package_event_index.json#{source_id}",
    )
    summary = f"{workflow_ref} is {_status_label(status).lower()} in the package event index."
    if _business_action_already_ingested(event):
        summary += " Any business action shown here is previously ingested operator-assisted truth, not new authority."
    return _post(
        source_kind="package_event",
        source_id=source_id,
        channel_ref=channel_ref,
        timestamp=str(event.get("created_at") or utc_now()),
        speaker_ref=str(mapping["speaker_ref"]),
        post_type=_post_type_for_package(status, workflow_ref),
        headline=str(mapping["headline"]),
        plain_summary=summary,
        status_label=_status_label(status),
        next_safe_action=str(mapping["next_safe_action"]),
        target_world_ref=target_world_ref,
        target_thread_ref=target_thread_ref,
        package_id=str(event.get("package_id") or ""),
        proof_refs=proof,
        business_action_performed=_business_action_already_ingested(event),
    )


def _channel_for_world_thread(world_ref: str, thread_ref: str) -> str:
    pair = (world_ref, thread_ref)
    if pair == ("finance", "st_annes"):
        return "finance_st_annes"
    if pair == ("finance", "capital_hilton"):
        return "finance_capital_hilton"
    if pair == ("business_development", "capital_hilton"):
        return "business_development_capital_hilton"
    return "operations_chief_workboard"


def _conversation_post(entry: Mapping[str, Any]) -> dict[str, Any] | None:
    world_ref = str(entry.get("target_world_ref") or "")
    thread_ref = str(entry.get("target_thread_ref") or "")
    channel_ref = _channel_for_world_thread(world_ref, thread_ref)
    source_id = str(entry.get("journal_entry_id") or entry.get("package_id") or entry.get("timestamp") or "")
    if not source_id:
        return None
    status = entry.get("package_status") or entry.get("action_status")
    post_type = "blocker" if "GATE" in str(status or "").upper() or "BLOCK" in str(status or "").upper() else "status"
    return _post(
        source_kind="operator_conversation_journal",
        source_id=source_id,
        channel_ref=channel_ref,
        timestamp=str(entry.get("timestamp") or utc_now()),
        speaker_ref=entry.get("speaker_ref") or "openclaw",
        post_type=post_type,
        headline=entry.get("headline") or "Conversation journal update",
        plain_summary=entry.get("short_summary") or "Operator conversation journal recorded a local status update.",
        status_label=_status_label(status),
        next_safe_action="Review the local package or response proof refs; do not expose raw request bodies.",
        target_world_ref=world_ref or _channel_world_thread(channel_ref)[0],
        target_thread_ref=thread_ref or _channel_world_thread(channel_ref)[1],
        package_id=str(entry.get("package_id") or ""),
        proof_refs=_proof_refs(
            entry.get("proof_refs"),
            f"generated/read_models/operator_conversation_journal.json#{source_id}",
        ),
        business_action_performed=False,
    )


def _handoff_post(handoff: Mapping[str, Any], generated_at: str) -> dict[str, Any]:
    channel_ref = str(handoff.get("channel_ref") or "operations_chief_workboard")
    world_ref, thread_ref = _channel_world_thread(channel_ref)
    from_agent = str(handoff.get("from_agent") or "openclaw")
    to_agent = str(handoff.get("to_agent_or_worker") or "openclaw")
    source_id = str(handoff.get("handoff_ref") or f"{from_agent}_to_{to_agent}")
    return _post(
        source_kind="agent_handoff_registry",
        source_id=source_id,
        channel_ref=channel_ref,
        timestamp=generated_at,
        speaker_ref=from_agent,
        post_type="handoff",
        headline=f"Handoff: {from_agent} to {to_agent}",
        plain_summary=str(handoff.get("trigger_condition") or "A deterministic handoff route is available."),
        status_label="Receipt Required",
        next_safe_action="Create only a local handoff packet with collapsed proof; do not execute or grant authority.",
        target_world_ref=world_ref,
        target_thread_ref=thread_ref,
        package_id="",
        proof_refs=[f"generated/read_models/agent_handoff_registry.json#{source_id}"],
        business_action_performed=False,
    )


def _architecture_handoff_post(handoff: Mapping[str, Any], generated_at: str) -> dict[str, Any] | None:
    if str(handoff.get("from_agent") or "") != "hermes":
        return None
    source_id = str(handoff.get("handoff_ref") or "hermes_architecture_recommendation")
    return _post(
        source_kind="agent_handoff_registry_architecture",
        source_id=source_id,
        channel_ref="architecture_hermes",
        timestamp=generated_at,
        speaker_ref="hermes",
        post_type="handoff",
        headline="Hermes architecture recommendation ready",
        plain_summary=str(handoff.get("trigger_condition") or "An architecture recommendation is ready for review."),
        status_label="Architecture Recommendation",
        next_safe_action="Review the recommendation and route to Chief only as a local build packet.",
        target_world_ref="architecture",
        target_thread_ref="architecture_hermes",
        package_id="",
        proof_refs=[f"generated/read_models/agent_handoff_registry.json#{source_id}"],
        business_action_performed=False,
    )


def _worker_example_post(example: Mapping[str, Any], generated_at: str) -> dict[str, Any]:
    channel_ref = str(example.get("channel_ref") or "operations_chief_workboard")
    world_ref, thread_ref = _channel_world_thread(channel_ref)
    worker_ref = str(example.get("worker_ref") or "openclaw").lower()
    source_id = str(example.get("example_ref") or example.get("package_id") or worker_ref)
    review = example.get("review_packet_summary") if isinstance(example.get("review_packet_summary"), Mapping) else {}
    state_path = example.get("state_path") if isinstance(example.get("state_path"), list) else []
    status = str(state_path[-1] if state_path else "REVIEW_PACKET_READY")
    return _post(
        source_kind="spawned_worker_package_lifecycle",
        source_id=source_id,
        channel_ref=channel_ref,
        timestamp=generated_at,
        speaker_ref=worker_ref,
        post_type="review_packet",
        headline=f"{worker_ref.upper()} review packet ready",
        plain_summary=review.get("human_summary") or example.get("authority_note") or "Worker output is ready for review.",
        status_label=_status_label(status),
        next_safe_action=review.get("next_safe_action") or "Review the packet and approve, request rework, or block by gate.",
        target_world_ref=world_ref,
        target_thread_ref=thread_ref,
        package_id=str(example.get("package_id") or ""),
        proof_refs=_proof_refs(
            review.get("receipts"),
            review.get("screenshots"),
            f"generated/read_models/spawned_worker_package_lifecycle.json#{source_id}",
        ),
        business_action_performed=False,
    )


def _decision_post(decision: Mapping[str, Any]) -> dict[str, Any] | None:
    if not decision:
        return None
    world_ref = str(decision.get("target_world_ref") or "")
    thread_ref = str(decision.get("target_thread_ref") or "")
    if not world_ref or not thread_ref:
        return None
    channel_ref = _channel_for_world_thread(world_ref, thread_ref)
    source_id = str(decision.get("read_model_id") or "operator_next_decision")
    return _post(
        source_kind="operator_next_decision",
        source_id=source_id,
        channel_ref=channel_ref,
        timestamp=str(decision.get("generated_at") or utc_now()),
        speaker_ref="openclaw",
        post_type="decision",
        headline=decision.get("headline") or decision.get("action_label") or "Operator next decision",
        plain_summary=decision.get("plain_summary") or "A local next-decision read model is available.",
        status_label=_status_label(decision.get("status") or decision.get("action_type") or "decision"),
        next_safe_action=str(decision.get("action_label") or "Review the suggested navigation target."),
        target_world_ref=world_ref,
        target_thread_ref=thread_ref,
        package_id="",
        proof_refs=_proof_refs(
            decision.get("proof_refs"),
            "generated/read_models/operator_next_decision.json",
        ),
        business_action_performed=False,
    )


def _helm_lifecycle_post(status_payload: Mapping[str, Any]) -> dict[str, Any] | None:
    action = status_payload.get("primary_next_action") if isinstance(status_payload.get("primary_next_action"), Mapping) else {}
    if not action:
        return None
    world_ref = str(action.get("target_world_ref") or "")
    thread_ref = str(action.get("target_thread_ref") or "")
    if not world_ref or not thread_ref:
        return None
    channel_ref = _channel_for_world_thread(world_ref, thread_ref)
    source_id = str(action.get("action_id") or status_payload.get("read_model_id") or "helm_action_lifecycle_status")
    return _post(
        source_kind="helm_action_lifecycle_status",
        source_id=source_id,
        channel_ref=channel_ref,
        timestamp=str(status_payload.get("generated_at") or utc_now()),
        speaker_ref="openclaw",
        post_type="decision",
        headline=str(action.get("label") or "Helm action lifecycle decision"),
        plain_summary=str(action.get("reason") or "Helm selected a local next action."),
        status_label=_status_label(status_payload.get("status") or "decision"),
        next_safe_action="Navigate only if the operator chooses; this feed grants no business action.",
        target_world_ref=world_ref,
        target_thread_ref=thread_ref,
        package_id="",
        proof_refs=_proof_refs(
            status_payload.get("proof_refs"),
            action.get("payload_ref"),
            "generated/read_models/helm_action_lifecycle_status.json",
        ),
        business_action_performed=False,
    )


def _build_posts(payloads: Mapping[str, dict[str, Any]], generated_at: str) -> list[dict[str, Any]]:
    posts: list[dict[str, Any]] = []
    package_index = payloads.get("package_event_index", {})
    for event in package_index.get("events", []) if isinstance(package_index.get("events"), list) else []:
        if isinstance(event, Mapping):
            post = _package_event_post(event)
            if post:
                posts.append(post)

    journal = payloads.get("operator_conversation_journal", {})
    for entry in journal.get("entries", []) if isinstance(journal.get("entries"), list) else []:
        if isinstance(entry, Mapping):
            post = _conversation_post(entry)
            if post:
                posts.append(post)

    handoff_registry = payloads.get("agent_handoff_registry", {})
    for handoff in handoff_registry.get("handoffs", []) if isinstance(handoff_registry.get("handoffs"), list) else []:
        if isinstance(handoff, Mapping):
            posts.append(_handoff_post(handoff, generated_at))
            architecture_post = _architecture_handoff_post(handoff, generated_at)
            if architecture_post:
                posts.append(architecture_post)

    lifecycle = payloads.get("spawned_worker_package_lifecycle", {})
    for example in lifecycle.get("examples", []) if isinstance(lifecycle.get("examples"), list) else []:
        if isinstance(example, Mapping):
            posts.append(_worker_example_post(example, generated_at))

    decision = _decision_post(payloads.get("operator_next_decision", {}))
    if decision:
        posts.append(decision)
    helm = _helm_lifecycle_post(payloads.get("helm_action_lifecycle_status", {}))
    if helm:
        posts.append(helm)

    posts.sort(key=lambda post: (post["timestamp"], post["post_id"]))
    return posts


def _posts_by_channel(posts: list[dict[str, Any]]) -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    for post in posts:
        rows.setdefault(str(post["channel_ref"]), []).append(str(post["post_id"]))
    return rows


def _channel_post_counts(posts: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for post in posts:
        counts[str(post["channel_ref"])] = counts.get(str(post["channel_ref"]), 0) + 1
    return dict(sorted(counts.items()))


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = _preconditions(read_model_root)
    preconditions_ready = all(item["ready"] for item in preconditions)
    payloads = _source_payloads(read_model_root)
    posts = _build_posts(payloads, generated_at) if preconditions_ready else []
    posts_by_channel = _posts_by_channel(posts)
    required_channels_with_posts = {
        "finance_st_annes": bool(posts_by_channel.get("finance_st_annes")),
        "finance_capital_hilton": bool(posts_by_channel.get("finance_capital_hilton")),
        "business_development_capital_hilton": bool(posts_by_channel.get("business_development_capital_hilton")),
        "build_mission_control_mac": bool(posts_by_channel.get("build_mission_control_mac")),
        "build_openclaw_backend": bool(posts_by_channel.get("build_openclaw_backend")),
        "architecture_hermes": bool(posts_by_channel.get("architecture_hermes")),
        "security_guardian_gates": bool(posts_by_channel.get("security_guardian_gates")),
        "operations_chief_workboard": bool(posts_by_channel.get("operations_chief_workboard")),
    }
    status = FEED_STATUS if preconditions_ready else FEED_NOT_READY_STATUS
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "status": status,
        "purpose": "Compact local Workroom channel posts from package events, conversation journal entries, handoffs, worker review outputs, and local decisions.",
        "mode": "local_read_model_generation_only_no_live_slack",
        "preconditions": preconditions,
        "post_count": len(posts),
        "channel_post_counts": _channel_post_counts(posts),
        "posts_by_channel": posts_by_channel,
        "posts": posts,
        "required_channel_mappings": {
            "st_annes_work_log_events": "finance_st_annes",
            "capital_hilton_invoice_operator_assist": "finance_capital_hilton",
            "capital_hilton_proposal": "business_development_capital_hilton",
            "mac_ui_implementation_results": "build_mission_control_mac",
            "pc_backend_implementation_results": "build_openclaw_backend",
            "hermes_architecture_recommendation": "architecture_hermes",
            "guardian_protected_gate": "security_guardian_gates",
            "chief_work_packets": "operations_chief_workboard",
        },
        "required_channels_with_posts": required_channels_with_posts,
        "display_policy": {
            "proof_refs_collapsed_by_default": True,
            "show_machine_details_by_default": False,
            "raw_prompt_bodies_included": False,
            "raw_request_bodies_included": False,
            "plain_summary_first": True,
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "source_refs": [
            "generated/read_models/openclaw_workroom_registry.json",
            "generated/read_models/agent_handoff_registry.json",
            "generated/read_models/spawned_worker_package_lifecycle.json",
            "generated/read_models/package_event_index.json",
            "generated/read_models/operator_conversation_journal.json",
            "generated/read_models/operator_next_decision.json",
            "generated/read_models/helm_action_lifecycle_status.json",
        ],
        "rules": [
            "Do not dump raw request bodies.",
            "Do not show raw proof by default.",
            "Worker posts are review outputs, not autonomous authority.",
            "Business actions are only recorded if already ingested as operator-assisted truth.",
            "Do not create new business truth.",
            "No send, submit, ledger, push, Slack, Telegram, Gmail, browser, or Coupa authority.",
        ],
        "machine_proof": {
            "local_only": True,
            "read_model_generation_only": True,
            "preconditions_ready": preconditions_ready,
            "proof_refs_collapsed_by_default": True,
            "raw_prompt_bodies_included": False,
            "raw_request_bodies_included": False,
            "new_business_truth_created": False,
            "slack_connected": False,
            "telegram_live_connected": False,
            "message_send_performed": False,
            "email_send_performed": False,
            "gmail_access_performed": False,
            "browser_access_performed": False,
            "coupa_access_performed": False,
            "ledger_mutation_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "submit_performed": False,
            "paid_marking_performed": False,
            "git_push_performed": False,
            "worker_spawn_performed": False,
            "agent_loop_launched": False,
            "external_llm_called": False,
            "unsafe_true_grants_absent": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        },
    }


def build_wiki(read_model: Mapping[str, Any]) -> str:
    lines = [
        "# OpenClaw Workroom Activity Feed",
        "",
        f"Status: `{read_model['status']}`",
        "",
        "This read model turns local package events, conversation journal entries, handoff rules, and worker lifecycle examples into compact Workroom channel posts.",
        "",
        "No Slack connection. No Telegram live connection. No messages are sent.",
        "",
        f"Posts: `{read_model['post_count']}`",
        "",
        "## Channel Counts",
        "",
    ]
    for channel_ref, count in read_model["channel_post_counts"].items():
        lines.append(f"- `{channel_ref}`: `{count}`")
    lines.extend(["", "## Sample Posts", ""])
    for post in list(read_model["posts"])[:12]:
        lines.append(
            f"- `{post['channel_ref']}` / `{post['post_type']}` / `{post['speaker_ref']}`: {post['headline']} - {post['plain_summary']}"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Proof refs are collapsed by default.",
            "- Raw prompt and request bodies are not included.",
            "- Worker posts are review outputs only.",
            "- Business action flags only reflect already-ingested operator-assisted truth.",
            "- No send, submit, ledger, workbook, PDF, Slack, Telegram, Gmail, browser, Coupa, worker spawn, or git push authority.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_openclaw_workroom_activity_feed(
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
    read_model_path = export_root / JSON_EXPORT_NAME
    read_model_path.write_text(stable_json(read_model), encoding="utf-8")

    bridge_path = ""
    if bridge_export_root is not None:
        bridge_export_root.mkdir(parents=True, exist_ok=True)
        bridge_file = bridge_export_root / JSON_EXPORT_NAME
        bridge_file.write_text(stable_json(read_model), encoding="utf-8")
        bridge_path = bridge_file.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(read_model), encoding="utf-8")
    return {
        "status": str(read_model["status"]),
        "read_model_path": read_model_path.as_posix(),
        "bridge_read_model_path": bridge_path,
        "wiki_path": wiki_path.as_posix(),
        "post_count": str(read_model["post_count"]),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export OpenClaw Workroom Activity Feed V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_openclaw_workroom_activity_feed(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
