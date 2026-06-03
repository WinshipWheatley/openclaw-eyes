"""OpenClaw Operating Picture Latest V0.

This read model summarizes Track A and Track B into one compact operator
surface. It reads local generated read models only and does not execute,
submit, send, mutate business state, spawn workers, or grant authority.
"""

from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/OpenClaw Operating Picture Latest.md")

SCHEMA_VERSION = "openclaw_operating_picture_latest_v0"
READ_MODEL_ID = "openclaw_operating_picture_latest"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
STATUS_READY = "OPENCLAW_OPERATING_PICTURE_READY"
STATUS_NOT_READY = "OPENCLAW_OPERATING_PICTURE_NOT_READY"

SECTION_ORDER = [
    "executive_summary",
    "operator_ready_workflows",
    "operator_assist_workflows",
    "developer_mode_workflows",
    "blocked_protected_workflows",
    "workrooms_status",
    "review_packets_needing_attention",
    "approval_requests_pending",
    "dead_letters_failures",
    "evidence_confidence_summary",
    "memory_candidates_needing_promotion",
    "current_next_safe_action",
    "can_run_while_winship_sleeps",
    "must_wait_for_explicit_approval",
    "recommended_next_build_lane",
]

REQUIRED_PRECONDITIONS = {
    "track_a_workroom_backbone": {
        "filename": "track_a_workroom_backbone_status.json",
        "accepted_statuses": ["TRACK_A_WORKROOM_BACKBONE_READY"],
    },
    "track_b_governance_memory_cutover": {
        "filename": "track_b_governance_memory_cutover_status.json",
        "accepted_statuses": ["TRACK_B_GOVERNANCE_MEMORY_CUTOVER_READY"],
    },
}

SOURCE_READ_MODELS = [
    "track_a_workroom_backbone_status.json",
    "track_b_governance_memory_cutover_status.json",
    "openclaw_workroom_registry.json",
    "openclaw_workroom_activity_feed.json",
    "workroom_review_packet_index.json",
    "workroom_review_decision_status.json",
    "chief_build_backlog.json",
    "operator_next_decision.json",
    "approval_request_queue.json",
    "gate_decision_ledger.json",
    "artifact_lineage_registry.json",
    "evidence_confidence_scoring.json",
    "operator_memory_distillation.json",
    "memory_promotion_gate.json",
    "lane_graduation_criteria.json",
    "operator_mode_cutover_board.json",
    "teamroom_e2e_smoke_plan.json",
    "backend_queue_recovery_status.json",
    "dead_letter_queue.json",
]

AUTHORITY_BOUNDARY = {
    "email_send_allowed": False,
    "ledger_posting_allowed": False,
    "ledger_mutation_allowed": False,
    "browser_access_allowed": False,
    "gmail_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "worker_spawn_allowed": False,
    "worker_execution_allowed": False,
    "external_provider_allowed": False,
    "external_llm_allowed": False,
    "local_model_runtime_allowed": False,
    "git_push_allowed": False,
    "business_action_allowed": False,
    "business_action_performed": False,
    "sent": False,
    "paid": False,
}

PROTECTED_ACTIONS = [
    "email send",
    "Coupa submit",
    "ledger post or mark-paid",
    "source workbook mutation",
    "PDF export",
    "provider/browser/Gmail access",
    "worker spawn or child-agent execution",
    "git push",
]


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
    path = _rooted(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path = _rooted(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _source_ref(filename: str) -> str:
    return f"generated/read_models/{filename}"


def _status(payload: Mapping[str, Any]) -> str:
    return str(payload.get("status") or payload.get("contract_status") or "")


def _preconditions(read_model_root: Path) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows: list[dict[str, Any]] = []
    for ref, contract in REQUIRED_PRECONDITIONS.items():
        filename = str(contract["filename"])
        observed = _status(_load_json(root / filename))
        accepted = [status.lstrip(":") for status in contract["accepted_statuses"]]
        rows.append(
            {
                "precondition_ref": ref,
                "observed_status": observed,
                "accepted_statuses": accepted,
                "ready": observed in accepted,
                "source_ref": _source_ref(filename),
            }
        )
    return rows


def _items_from_workflows(workflows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for workflow in workflows:
        display_name = str(workflow.get("display_name") or workflow.get("workflow_ref") or "Workflow")
        items.append(
            {
                "label": display_name,
                "status": str(workflow.get("cutover_status") or workflow.get("status") or "unknown"),
                "summary": str(workflow.get("plain_summary") or workflow.get("summary") or ""),
                "owner_speaker_ref": str(workflow.get("owner_speaker_ref") or workflow.get("speaker_ref") or "openclaw"),
                "business_action_performed": False,
                "proof_refs_collapsed": True,
            }
        )
    return items


def _workflows_by_status(cutover_board: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    raw_workflows = [workflow for workflow in cutover_board.get("workflows") or [] if isinstance(workflow, Mapping)]
    grouped: dict[str, list[Mapping[str, Any]]] = {
        "operator_ready": [],
        "operator_assist_ready": [],
        "developer_mode": [],
        "blocked": [],
    }
    for workflow in raw_workflows:
        status = str(workflow.get("cutover_status") or workflow.get("status") or "")
        if status in grouped:
            grouped[status].append(workflow)
    return {key: _items_from_workflows(value) for key, value in grouped.items()}


def _pending_approval_items(queue: Mapping[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for request in queue.get("approval_requests") or []:
        if not isinstance(request, Mapping):
            continue
        if str(request.get("status") or "").lower() != "pending":
            continue
        items.append(
            {
                "requested_action": str(request.get("requested_action") or "approval"),
                "owner_speaker_ref": str(request.get("owner_speaker_ref") or "guardian"),
                "gate_ref": str(request.get("gate_ref") or ""),
                "plain_summary": str(request.get("plain_summary") or ""),
                "business_action_performed": False,
                "proof_refs_collapsed": True,
            }
        )
    return items


def _dead_letter_items(dead_letter_queue: Mapping[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in dead_letter_queue.get("dead_letters") or []:
        if not isinstance(row, Mapping):
            continue
        items.append(
            {
                "failure_kind": str(row.get("failure_kind") or "unknown"),
                "owner_speaker_ref": str(row.get("owner_speaker_ref") or "chief"),
                "recoverability": str(row.get("recoverability") or "investigate"),
                "plain_summary": str(row.get("plain_summary") or ""),
                "raw_body_stored": bool(row.get("raw_body_stored") is True),
                "business_action_performed": False,
                "proof_refs_collapsed": True,
            }
        )
    return items


def _review_attention_items(packet_index: Mapping[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for packet in packet_index.get("packets") or []:
        if not isinstance(packet, Mapping):
            continue
        status = str(packet.get("status") or "")
        needs_operator = packet.get("operator_decision_required") is True
        completed = packet.get("completed") is True
        visible = packet.get("visible_by_default")
        if needs_operator and not completed and visible is not False and status not in {
            "OPERATOR_REVIEW_RECORDED",
            "INFORMATIONAL_REVIEW_CLOSED",
        }:
            items.append(
                {
                    "label": "Workroom review packet",
                    "status": status or "REVIEW_PACKET_READY",
                    "summary": str(packet.get("human_summary") or "A Workroom review packet needs operator attention."),
                    "channel_ref": str(packet.get("channel_ref") or ""),
                    "decision_options": [
                        "approve for record",
                        "request rework",
                        "mark informational",
                    ],
                    "business_action_performed": False,
                    "proof_refs_collapsed": True,
                }
            )
    return items


def _memory_items(memory_gate: Mapping[str, Any]) -> list[dict[str, Any]]:
    entries = memory_gate.get("promotion_entries") or memory_gate.get("memory_entries") or []
    items: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        status = str(entry.get("promotion_status") or entry.get("status") or "candidate")
        if status not in {"candidate", "needs_more_proof", "operator_review"}:
            continue
        items.append(
            {
                "summary": str(entry.get("candidate_summary") or entry.get("plain_summary") or "Memory candidate needs review."),
                "promotion_status": status,
                "operator_approval_required": entry.get("operator_approval_required") is True,
                "privacy_class": str(entry.get("privacy_class") or "local_context"),
                "business_action_performed": False,
                "proof_refs_collapsed": True,
            }
        )
    return items


def _evidence_summary(scoring: Mapping[str, Any]) -> dict[str, Any]:
    facts = [fact for fact in scoring.get("facts") or [] if isinstance(fact, Mapping)]
    by_class = Counter(str(fact.get("confidence_class") or "unknown") for fact in facts)
    return {
        "fact_count": int(scoring.get("fact_count") or len(facts)),
        "confidence_classes": dict(sorted(by_class.items())),
        "summary": "Evidence is labeled before UI surfaces use it as primary truth.",
        "paid_truth_rule": "Paid truth stays false unless separate payment evidence exists.",
        "sent_truth_rule": "Sent truth requires explicit sent or manual-send evidence.",
        "proof_refs_collapsed": True,
    }


def _current_next_action(decision: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "headline": str(decision.get("headline") or "No urgent action"),
        "plain_summary": str(decision.get("plain_summary") or "No active operator action is required."),
        "speaker_ref": str(decision.get("speaker_ref") or "openclaw"),
        "voice_profile_ref": str(decision.get("voice_profile_ref") or f"agent_voice_profile:{decision.get('speaker_ref') or 'openclaw'}"),
        "voice_mode": str(decision.get("voice_mode") or "operator_calm"),
        "action_label": str(decision.get("action_label") or "Open workboard"),
        "action_type": str(decision.get("action_type") or "open_workboard"),
        "target_world_ref": str(decision.get("target_world_ref") or ""),
        "target_thread_ref": str(decision.get("target_thread_ref") or ""),
        "priority": str(decision.get("priority") or "normal"),
        "business_action": False,
        "business_action_performed": False,
        "proof_refs_collapsed": True,
    }


def _section(
    *,
    section_ref: str,
    title: str,
    headline: str,
    summary: str,
    items: list[dict[str, Any]] | None = None,
    proof_refs: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "section_ref": section_ref,
        "title": title,
        "headline": headline,
        "summary": summary,
        "items": items or [],
        "proof_refs": proof_refs or [],
        "proof_collapsed_by_default": True,
        "business_action_performed": False,
    }


def _mac_render_next(backlog: Mapping[str, Any]) -> dict[str, Any]:
    mac_items = [
        item
        for item in backlog.get("backlog_items") or []
        if isinstance(item, Mapping) and str(item.get("recommended_worker") or "").lower() == "mac_codex"
    ]
    first_goal = str(mac_items[0].get("goal") or "") if mac_items else ""
    return {
        "lane_ref": "mac_helm_workroom_rendering",
        "headline": "Render Track A+B in Helm and Workroom",
        "summary": (
            "Mac should render the operating picture, operator cutover board, review packet controls, "
            "and teamroom smoke plan without adding send, submit, ledger, worker-spawn, or live-provider controls."
        ),
        "recommended_worker": "mac_codex",
        "starter_packet_hint": first_goal or "Render Workroom review decisions and operating-picture summaries.",
        "business_action_performed": False,
        "proof_refs_collapsed": True,
    }


def _backend_lane_next() -> dict[str, Any]:
    return {
        "lane_ref": "pc_sqlite_unknown_classification_and_workroom_dry_run",
        "headline": "Classify SQLite unknowns and dry-run Workroom routing",
        "summary": (
            "Next backend work should stay local: classify remaining unknown SQLite concepts, refine dead-letter recovery, "
            "and plan Workroom dry-runs without providers or worker execution."
        ),
        "recommended_worker": "pc_codex",
        "business_action_performed": False,
        "proof_refs_collapsed": True,
    }


def build_operating_picture(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    root = _rooted(read_model_root)
    sources = {filename: _load_json(root / filename) for filename in SOURCE_READ_MODELS}
    preconditions = _preconditions(root)
    preconditions_ready = all(row["ready"] for row in preconditions)

    cutover_groups = _workflows_by_status(sources["operator_mode_cutover_board.json"])
    approval_items = _pending_approval_items(sources["approval_request_queue.json"])
    dead_letters = _dead_letter_items(sources["dead_letter_queue.json"])
    review_attention = _review_attention_items(sources["workroom_review_packet_index.json"])
    memory_items = _memory_items(sources["memory_promotion_gate.json"])
    evidence = _evidence_summary(sources["evidence_confidence_scoring.json"])
    current_next = _current_next_action(sources["operator_next_decision.json"])
    mac_next = _mac_render_next(sources["chief_build_backlog.json"])
    backend_next = _backend_lane_next()

    counts = {
        "operator_ready": len(cutover_groups["operator_ready"]),
        "operator_assist": len(cutover_groups["operator_assist_ready"]),
        "developer_mode": len(cutover_groups["developer_mode"]),
        "blocked": len(cutover_groups["blocked"]),
        "pending_approvals": len(approval_items),
        "guardian_approvals": sum(1 for item in approval_items if item.get("owner_speaker_ref") == "guardian"),
        "dead_letters": len(dead_letters),
        "review_packets_needing_attention": len(review_attention),
        "memory_candidates": len(memory_items),
        "memory_candidates_requiring_operator_approval": sum(
            1 for item in memory_items if item.get("operator_approval_required") is True
        ),
    }

    executive_summary = {
        "headline": "OpenClaw has a local teamroom and governance backbone.",
        "plain_text": (
            "Track A gives the teamroom path a review, handoff, staging, backlog, and Workroom question backbone. "
            "Track B gives protected gates, approvals, dead letters, artifact lineage, evidence confidence, memory "
            "promotion, lane graduation, cutover status, and an end-to-end smoke plan. Business actions remain gated."
        ),
        "proof_refs_collapsed": True,
        "business_action_performed": False,
    }

    can_run_items = [
        {"label": "Refresh generated read models", "summary": "Local summaries and indexes can update from existing evidence only."},
        {"label": "Run gate and unsafe scans", "summary": "Guardian-style checks can classify risk without granting authority."},
        {"label": "Distill memory candidates", "summary": "Candidate memories can be prepared, but promotion waits for the gate."},
        {"label": "Audit dead letters", "summary": "Failures can be grouped for recovery without retrying providers."},
        {"label": "Plan teamroom smoke", "summary": "The smoke plan can be refined; live smoke execution waits for approval."},
    ]
    for item in can_run_items:
        item["business_action_performed"] = False
        item["proof_refs_collapsed"] = True

    wait_items = [
        {"label": action, "summary": "This remains behind Guardian approval and a separate executor gate."}
        for action in PROTECTED_ACTIONS
    ]
    for item in wait_items:
        item["business_action_performed"] = False
        item["proof_refs_collapsed"] = True

    workroom_items = [
        {
            "label": "Workroom registry and activity feed",
            "summary": "Workrooms, activity posts, handoffs, review packets, decision recording, and package staging are locally modeled.",
            "status": sources["track_a_workroom_backbone_status.json"].get("status", "unknown"),
            "business_action_performed": False,
            "proof_refs_collapsed": True,
        },
        {
            "label": "Review packet attention",
            "summary": (
                "One review packet needs operator attention."
                if review_attention
                else "No unresolved review packet is the primary operator item."
            ),
            "status": "attention_needed" if review_attention else "clear",
            "business_action_performed": False,
            "proof_refs_collapsed": True,
        },
    ]

    sections = {
        "executive_summary": _section(
            section_ref="executive_summary",
            title="Executive summary",
            headline=executive_summary["headline"],
            summary=executive_summary["plain_text"],
            proof_refs=[
                _source_ref("track_a_workroom_backbone_status.json"),
                _source_ref("track_b_governance_memory_cutover_status.json"),
            ],
        ),
        "operator_ready_workflows": _section(
            section_ref="operator_ready_workflows",
            title="Operator-ready workflows",
            headline=f"{counts['operator_ready']} workflows are operator-ready.",
            summary="These can be shown as normal operator surfaces without protected action authority.",
            items=cutover_groups["operator_ready"],
            proof_refs=[_source_ref("operator_mode_cutover_board.json")],
        ),
        "operator_assist_workflows": _section(
            section_ref="operator_assist_workflows",
            title="Operator-assist workflows",
            headline=f"{counts['operator_assist']} workflows are operator-assist.",
            summary="These can guide the operator but protected provider or artifact steps remain gated.",
            items=cutover_groups["operator_assist_ready"],
            proof_refs=[_source_ref("operator_mode_cutover_board.json")],
        ),
        "developer_mode_workflows": _section(
            section_ref="developer_mode_workflows",
            title="Developer-mode workflows",
            headline=f"{counts['developer_mode']} workflow remains developer-mode.",
            summary="These need more hardening before Helm should present them as operator-ready.",
            items=cutover_groups["developer_mode"],
            proof_refs=[_source_ref("operator_mode_cutover_board.json")],
        ),
        "blocked_protected_workflows": _section(
            section_ref="blocked_protected_workflows",
            title="Blocked/protected workflows",
            headline=f"{counts['blocked']} workflows are blocked or protected.",
            summary="Guardian keeps these behind explicit approval and separate execution gates.",
            items=cutover_groups["blocked"],
            proof_refs=[_source_ref("operator_mode_cutover_board.json"), _source_ref("gate_decision_ledger.json")],
        ),
        "workrooms_status": _section(
            section_ref="workrooms_status",
            title="Workrooms status",
            headline="The Workroom backbone is ready locally.",
            summary="OpenClaw can record review decisions, handoffs, staged worker package stubs, activity, and Chief backlog items without running workers.",
            items=workroom_items,
            proof_refs=[
                _source_ref("openclaw_workroom_registry.json"),
                _source_ref("openclaw_workroom_activity_feed.json"),
                _source_ref("workroom_review_packet_index.json"),
            ],
        ),
        "review_packets_needing_attention": _section(
            section_ref="review_packets_needing_attention",
            title="Review packets needing attention",
            headline=(
                "One Workroom review packet needs attention."
                if review_attention
                else "No Workroom review packet needs attention."
            ),
            summary="Review choices are record-only: approve for record, request rework, or mark informational.",
            items=review_attention,
            proof_refs=[_source_ref("workroom_review_packet_index.json")],
        ),
        "approval_requests_pending": _section(
            section_ref="approval_requests_pending",
            title="Approval requests pending",
            headline=f"{counts['pending_approvals']} approval requests are pending.",
            summary="The queue centralizes approval decisions but does not execute them.",
            items=approval_items,
            proof_refs=[_source_ref("approval_request_queue.json")],
        ),
        "dead_letters_failures": _section(
            section_ref="dead_letters_failures",
            title="Dead letters / failures",
            headline=f"{counts['dead_letters']} dead-letter classes are visible.",
            summary="Malformed, stale, unsafe, or missing-file requests can be inspected without retries or provider calls.",
            items=dead_letters,
            proof_refs=[_source_ref("dead_letter_queue.json")],
        ),
        "evidence_confidence_summary": _section(
            section_ref="evidence_confidence_summary",
            title="Evidence confidence summary",
            headline=f"{evidence['fact_count']} facts have confidence labels.",
            summary="Confidence labels separate proven, generated, inferred, stale, rejected, test-only, and unknown facts.",
            items=[
                {
                    "label": key,
                    "count": value,
                    "business_action_performed": False,
                    "proof_refs_collapsed": True,
                }
                for key, value in evidence["confidence_classes"].items()
            ],
            proof_refs=[_source_ref("evidence_confidence_scoring.json")],
        ),
        "memory_candidates_needing_promotion": _section(
            section_ref="memory_candidates_needing_promotion",
            title="Memory candidates needing promotion",
            headline=f"{counts['memory_candidates']} memory candidates are waiting at the promotion gate.",
            summary="Distilled memory can inform future context only after the promotion rules allow it.",
            items=memory_items,
            proof_refs=[_source_ref("operator_memory_distillation.json"), _source_ref("memory_promotion_gate.json")],
        ),
        "current_next_safe_action": _section(
            section_ref="current_next_safe_action",
            title="Current next safe action",
            headline=current_next["headline"],
            summary=current_next["plain_summary"],
            items=[current_next],
            proof_refs=[_source_ref("operator_next_decision.json")],
        ),
        "can_run_while_winship_sleeps": _section(
            section_ref="can_run_while_winship_sleeps",
            title="What can run while Winship sleeps",
            headline="Local planning and status refresh can run safely.",
            summary="Only local read-model, wiki, generated metadata, audit, and planning work belongs in the overnight lane.",
            items=can_run_items,
            proof_refs=[
                _source_ref("teamroom_e2e_smoke_plan.json"),
                _source_ref("backend_queue_recovery_status.json"),
            ],
        ),
        "must_wait_for_explicit_approval": _section(
            section_ref="must_wait_for_explicit_approval",
            title="What must wait for explicit approval",
            headline="Protected actions stay blocked until Winship approves them.",
            summary="Approval queues can describe protected work, but they do not perform it.",
            items=wait_items,
            proof_refs=[_source_ref("approval_request_queue.json"), _source_ref("gate_decision_ledger.json")],
        ),
        "recommended_next_build_lane": _section(
            section_ref="recommended_next_build_lane",
            title="Recommended next build lane",
            headline=mac_next["headline"],
            summary=(
                "Mac should render the operator-facing Track A+B surfaces next; PC should follow with local SQLite "
                "classification and Workroom dry-run planning."
            ),
            items=[mac_next, backend_next],
            proof_refs=[_source_ref("chief_build_backlog.json"), _source_ref("teamroom_e2e_smoke_plan.json")],
        ),
    }

    payload = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": STATUS_READY if preconditions_ready else STATUS_NOT_READY,
        "generated_at": generated_at,
        "surface_ref": "openclaw_operating_picture_latest",
        "speaker_ref": "cassandra",
        "voice_profile_ref": "agent_voice_profile:cassandra",
        "voice_mode": "operator_calm",
        "section_order": list(SECTION_ORDER),
        "sections": {key: sections[key] for key in SECTION_ORDER},
        "executive_summary": executive_summary,
        "operator_ready_workflows": sections["operator_ready_workflows"],
        "operator_assist_workflows": sections["operator_assist_workflows"],
        "developer_mode_workflows": sections["developer_mode_workflows"],
        "blocked_protected_workflows": sections["blocked_protected_workflows"],
        "workrooms_status": sections["workrooms_status"],
        "review_packets_needing_attention": sections["review_packets_needing_attention"],
        "approval_requests_pending": sections["approval_requests_pending"],
        "dead_letters_failures": sections["dead_letters_failures"],
        "evidence_confidence_summary": evidence,
        "memory_candidates_needing_promotion": sections["memory_candidates_needing_promotion"],
        "current_next_safe_action": current_next,
        "can_run_while_winship_sleeps": sections["can_run_while_winship_sleeps"],
        "must_wait_for_explicit_approval": sections["must_wait_for_explicit_approval"],
        "recommended_next_build_lane": mac_next,
        "what_mac_should_render_next": mac_next,
        "backend_lane_should_come_next": backend_next,
        "counts": counts,
        "proof_refs": [
            _source_ref("track_a_workroom_backbone_status.json"),
            _source_ref("track_b_governance_memory_cutover_status.json"),
            _source_ref("operator_mode_cutover_board.json"),
            _source_ref("approval_request_queue.json"),
            _source_ref("memory_promotion_gate.json"),
        ],
        "proof_collapsed_by_default": True,
        "history_policy": {
            "show_full_history_by_default": False,
            "proof_collapsed_by_default": True,
            "raw_request_bodies_visible_by_default": False,
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "preconditions_ready": preconditions_ready,
            "preconditions": preconditions,
            "source_read_models": [_source_ref(filename) for filename in SOURCE_READ_MODELS],
            "no_new_business_truth": True,
            "no_authority_grants": True,
            "business_action_performed": False,
            "ledger_truth_from_non_ledger_sources": False,
            "send_submit_paid_inferred_from_drafts_or_proposals": False,
        },
    }
    return payload


def render_wiki(payload: Mapping[str, Any]) -> str:
    counts = payload.get("counts") if isinstance(payload.get("counts"), Mapping) else {}
    current_next = payload.get("current_next_safe_action")
    if not isinstance(current_next, Mapping):
        current_next = {}
    mac_next = payload.get("what_mac_should_render_next")
    if not isinstance(mac_next, Mapping):
        mac_next = {}

    lines = [
        "# OpenClaw Operating Picture Latest",
        "",
        f"Status: `{payload.get('status', STATUS_NOT_READY)}`",
        "",
        "## Executive summary",
        "",
        str(payload.get("executive_summary", {}).get("plain_text", "")) if isinstance(payload.get("executive_summary"), Mapping) else "",
        "",
        "## What is working",
        "",
        f"- Operator-ready workflows: {counts.get('operator_ready', 0)}",
        f"- Operator-assist workflows: {counts.get('operator_assist', 0)}",
        f"- Workroom review and handoff backbone: ready locally",
        f"- Governance, approval, dead-letter, evidence, and memory gates: ready locally",
        "",
        "## Current next safe action",
        "",
        f"- {current_next.get('action_label', 'Open workboard')}: {current_next.get('plain_summary', '')}",
        "",
        "## Protected actions",
        "",
    ]
    for action in PROTECTED_ACTIONS:
        lines.append(f"- {action}: waits for explicit Guardian approval and a separate executor gate.")
    lines.extend(
        [
            "",
            "## What can run while Winship sleeps",
            "",
            "- Local read-model refresh, gate scans, dead-letter audits, memory candidate distillation, and planning-only teamroom smoke preparation.",
            "",
            "## Recommended next build lane",
            "",
            f"- Mac: {mac_next.get('summary', '')}",
            f"- PC: {payload.get('backend_lane_should_come_next', {}).get('summary', '') if isinstance(payload.get('backend_lane_should_come_next'), Mapping) else ''}",
            "",
            "Proof refs are collapsed by default. This surface grants no send, submit, ledger, workbook, PDF, worker-spawn, push, or paid authority.",
            "",
        ]
    )
    return "\n".join(lines)


def export_operating_picture(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path = DEFAULT_BRIDGE_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    payload = build_operating_picture(read_model_root=read_model_root, generated_at=generated_at)
    export_root = _rooted(export_root)
    bridge_export_root = _rooted(bridge_export_root)
    read_model_path = export_root / JSON_EXPORT_NAME
    bridge_path = bridge_export_root / JSON_EXPORT_NAME

    _write_json(read_model_path, payload)
    bridge_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(read_model_path, bridge_path)
    _write_text(wiki_path, render_wiki(payload))

    return {
        "status": str(payload["status"]),
        "read_model_path": str(read_model_path),
        "bridge_read_model_path": str(bridge_path),
        "wiki_path": str(_rooted(wiki_path)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish the latest OpenClaw operating picture read model.")
    parser.add_argument("--read-model-root", type=Path, default=DEFAULT_READ_MODEL_ROOT)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--bridge-export-root", type=Path, default=DEFAULT_BRIDGE_EXPORT_ROOT)
    parser.add_argument("--wiki-path", type=Path, default=DEFAULT_WIKI_PATH)
    args = parser.parse_args()

    result = export_operating_picture(
        read_model_root=args.read_model_root,
        export_root=args.export_root,
        bridge_export_root=args.bridge_export_root,
        wiki_path=args.wiki_path,
    )
    print(stable_json(result), end="")


if __name__ == "__main__":
    main()
