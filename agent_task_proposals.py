from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


PROPOSALS_JSON = Path("/mnt/c/OpenClaw/logs/agent_task_proposals.json")
VISIBLE_MD = Path("/home/openclaw/polish_loop/current/advisory_task_proposals.md")
TASKS_DIR = Path("/home/openclaw/polish_loop/tasks")
ARCHIVE_DIR = Path("/home/openclaw/polish_loop/archive")

ALLOWED_URGENCY_LANES = ("now", "next", "later")
ALLOWED_REQUIRED_GATES = ("operator_review", "planner_review", "guardian_approval", "none")
ALLOWED_HARNESS_MODES = ("none", "dry-run", "staging-replay", "recorded-replay")
ALLOWED_WORK_KINDS = ("build", "repair", "harness-new-flow", "retest")


def _read_store() -> dict[str, Any]:
    if PROPOSALS_JSON.exists():
        try:
            data = json.loads(PROPOSALS_JSON.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                proposals = data.get("proposals")
                if isinstance(proposals, list):
                    return data
        except Exception:
            pass
    return {"proposals": []}


def _write_store(data: dict[str, Any]) -> None:
    PROPOSALS_JSON.parent.mkdir(parents=True, exist_ok=True)
    PROPOSALS_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _next_id(source_agent: str, now: datetime, offset: int = 1) -> str:
    prefix = f"ATP-{source_agent.upper()}-{now.strftime('%Y%m%d')}"
    data = _read_store()
    existing = sum(
        1
        for proposal in data.get("proposals", [])
        if str(proposal.get("id", "")).startswith(prefix)
    )
    return f"{prefix}-{existing + offset:03d}"


def _normalize_list(values: Any) -> list[str]:
    if isinstance(values, list):
        return [str(item).strip() for item in values if str(item).strip()]
    value = str(values or "").strip()
    return [value] if value else []


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")[:60] or "proposal"


def _task_profile_for(proposal: dict[str, Any]) -> str:
    work_kind = str(proposal.get("work_kind", "")).strip().lower()
    urgency = str(proposal.get("urgency_lane", "")).strip().lower()
    if work_kind == "retest":
        return "quick"
    if urgency == "now":
        return "surgical"
    if work_kind == "harness-new-flow":
        return "architect"
    return "standard"


def _auto_safe_harness_block(proposal: dict[str, Any], promotion_mode: str) -> str:
    if promotion_mode != "auto-safe-retest":
        return ""
    if str(proposal.get("work_kind", "")).strip().lower() != "retest":
        return ""
    if str(proposal.get("required_harness_mode", "")).strip().lower() != "dry-run":
        return ""

    target_flow = str(proposal.get("target_flow", "")).strip() or "unspecified-flow"
    lines = [
        "harness_mode: dry-run",
        "execution_mode: harness-backed-retest",
        "harness_expectation: gather evidence through a dry-run harness path before any live-touching follow-up",
    ]
    if target_flow == "morning_brief":
        lines.extend(
            [
                "harness_entrypoint: python3 /home/openclaw/morning_brief_harness.py --fixture /home/openclaw/staging/morning_brief_harness/fixtures/sample_morning.json",
                "harness_flow: morning_brief",
            ]
        )
    elif target_flow == "chief_end_of_day_review":
        lines.extend(
            [
                "harness_entrypoint: python3 /home/openclaw/chief_eod_harness.py --fixture /home/openclaw/staging/chief_eod_harness/fixtures/sample_eod.json",
                "harness_flow: chief_end_of_day_review",
            ]
        )
    elif target_flow == "guardian_schema_retest":
        lines.extend(
            [
                "harness_entrypoint: python3 /home/openclaw/guardian_schema_harness.py --fixture /home/openclaw/staging/guardian_schema_harness/fixtures/guardian_validation.json",
                "harness_flow: guardian_schema_retest",
            ]
        )
    return "".join(f"{line}\n" for line in lines)


def normalize_proposal(
    raw: dict[str, Any],
    *,
    source_agent: str,
    now: datetime | None = None,
    proposal_id: str | None = None,
) -> dict[str, Any]:
    now = now or datetime.now()
    urgency_lane = str(raw.get("urgency_lane", "next")).strip().lower() or "next"
    if urgency_lane not in ALLOWED_URGENCY_LANES:
        urgency_lane = "next"

    required_gate = str(raw.get("required_gate", "operator_review")).strip().lower() or "operator_review"
    if required_gate not in ALLOWED_REQUIRED_GATES:
        required_gate = "operator_review"

    required_harness_mode = str(raw.get("required_harness_mode", "none")).strip().lower() or "none"
    if required_harness_mode not in ALLOWED_HARNESS_MODES:
        required_harness_mode = "none"

    work_kind = str(raw.get("work_kind", "repair")).strip().lower() or "repair"
    if work_kind not in ALLOWED_WORK_KINDS:
        work_kind = "repair"

    target_flow = str(raw.get("target_flow", "")).strip() or "unspecified-flow"
    reason = str(raw.get("reason", "")).strip() or "No explicit reason provided."
    title = str(raw.get("title", "")).strip() or f"{source_agent.title()} advisory proposal"

    return {
        "id": proposal_id or _next_id(source_agent, now),
        "created_at": now.isoformat(timespec="seconds"),
        "source_agent": source_agent,
        "status": "proposed",
        "advisory_only": True,
        "task_type": "agent_work_request",
        "title": title,
        "target_flow": target_flow,
        "reason": reason,
        "urgency_lane": urgency_lane,
        "required_gate": required_gate,
        "required_harness_mode": required_harness_mode,
        "success_evidence": _normalize_list(raw.get("success_evidence")),
        "work_kind": work_kind,
    }


def save_proposals(raw_proposals: list[dict[str, Any]], *, source_agent: str, now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or datetime.now()
    data = _read_store()
    saved: list[dict[str, Any]] = []
    offset = 1
    for raw in raw_proposals:
        if not isinstance(raw, dict):
            continue
        proposal = normalize_proposal(
            raw,
            source_agent=source_agent,
            now=now,
            proposal_id=_next_id(source_agent, now, offset=offset),
        )
        data.setdefault("proposals", []).append(proposal)
        saved.append(proposal)
        offset += 1
    _write_store(data)
    write_visible_markdown(data.get("proposals", []))
    return saved


def get_open_proposals() -> list[dict[str, Any]]:
    proposals = _read_store().get("proposals", [])
    return [p for p in proposals if str(p.get("status", "proposed")).strip().lower() == "proposed"]


def proposals_by_lane() -> dict[str, list[dict[str, Any]]]:
    grouped = {lane: [] for lane in ALLOWED_URGENCY_LANES}
    for proposal in get_open_proposals():
        lane = str(proposal.get("urgency_lane", "next")).strip().lower()
        if lane not in grouped:
            lane = "next"
        grouped[lane].append(proposal)
    return grouped


def promote_proposal(proposal_id: str, *, now: datetime | None = None) -> dict[str, Any]:
    return _promote_proposal(proposal_id, now=now)


def _promote_proposal(
    proposal_id: str,
    *,
    now: datetime | None = None,
    promotion_mode: str = "manual",
    generated_by: str = "advisory_proposal_promotion",
) -> dict[str, Any]:
    now = now or datetime.now()
    data = _read_store()
    proposals = data.get("proposals", [])
    proposal = next((p for p in proposals if str(p.get("id", "")).strip() == proposal_id), None)
    if not isinstance(proposal, dict):
        raise ValueError(f"proposal not found: {proposal_id}")
    if proposal.get("advisory_only") is not True:
        raise ValueError(f"proposal is not advisory_only: {proposal_id}")
    if str(proposal.get("status", "")).strip().lower() != "proposed":
        raise ValueError(f"proposal is not promotable: {proposal_id}")

    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    task_name = f"{proposal_id.lower()}-{_slug(proposal.get('title', proposal_id))}"
    task_path = TASKS_DIR / f"{task_name}.md"
    if task_path.exists():
        raise ValueError(f"task file already exists for proposal: {task_path.name}")

    success = _normalize_list(proposal.get("success_evidence"))
    success_lines = "\n".join(f"- {item}" for item in success) if success else "- Match the bounded success evidence from the proposal."
    body = (
        f"title: {task_name}\n"
        f"profile: {_task_profile_for(proposal)}\n"
        f"goal: {str(proposal.get('reason', '')).strip() or 'Execute the bounded advisory proposal.'}\n"
        f"{_auto_safe_harness_block(proposal, promotion_mode)}"
        "scope:\n"
        f"- Target flow: {str(proposal.get('target_flow', '')).strip() or 'unspecified-flow'}\n"
        f"- Work kind: {str(proposal.get('work_kind', '')).strip() or 'repair'}\n"
        f"- Proposal provenance: {proposal_id}\n"
        "- Stay bounded to the proposal intent; do not widen scope autonomously.\n"
        "success:\n"
        f"{success_lines}\n"
        f"proposal_id: {proposal_id}\n"
        f"promotion_mode: {promotion_mode}\n"
        f"generated_by: {generated_by}\n"
        f"generated_at: {now.isoformat()}\n"
    )
    task_path.write_text(body, encoding="utf-8")

    proposal["status"] = "promoted"
    proposal["promoted_at"] = now.isoformat(timespec="seconds")
    proposal["promoted_task"] = task_name
    proposal["promotion_mode"] = promotion_mode
    _write_store(data)
    write_visible_markdown(data.get("proposals", []))
    return {"proposal_id": proposal_id, "task_name": task_name, "task_path": str(task_path)}


def auto_promote_safe_retest(
    proposal_ids: list[str],
    *,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    now = now or datetime.now()
    data = _read_store()
    proposals = data.get("proposals", [])
    allowed_ids = {str(item).strip() for item in proposal_ids if str(item).strip()}
    if not allowed_ids:
        return None

    for proposal in proposals:
        proposal_id = str(proposal.get("id", "")).strip()
        if proposal_id not in allowed_ids:
            continue
        if proposal.get("advisory_only") is not True:
            continue
        if str(proposal.get("status", "")).strip().lower() != "proposed":
            continue
        if str(proposal.get("work_kind", "")).strip().lower() != "retest":
            continue
        if str(proposal.get("required_gate", "")).strip().lower() != "none":
            continue
        if str(proposal.get("required_harness_mode", "")).strip().lower() != "dry-run":
            continue
        return _promote_proposal(
            proposal_id,
            now=now,
            promotion_mode="auto-safe-retest",
            generated_by="advisory_proposal_auto_promotion",
        )
    return None


def reconcile_proposals() -> dict[str, Any]:
    """Reconcile the proposal store with the filesystem (tasks/ and archive/)."""
    data = _read_store()
    changed = False
    proposals = data.get("proposals", [])

    # Collect all task identifiers from filesystem for efficient matching
    found_ids = set()
    try:
        # Check tasks/
        for p in TASKS_DIR.glob("atp-*"):
            m = re.match(r"(atp-[a-z0-9-]+)", p.name.lower())
            if m:
                found_ids.add(m.group(1).upper())
        # Check archive/
        for p in ARCHIVE_DIR.glob("*atp-*"):
            m = re.search(r"(atp-[a-z0-9-]+)", p.name.lower())
            if m:
                found_ids.add(m.group(1).upper())
    except Exception:
        pass

    reconciled_count = 0
    for p in proposals:
        if str(p.get("status", "proposed")).strip().lower() == "proposed":
            pid = str(p.get("id", "")).upper()
            if pid in found_ids:
                p["status"] = "promoted"
                p["reconciled_at"] = datetime.now().isoformat()
                changed = True
                reconciled_count += 1

    if changed:
        _write_store(data)

    write_visible_markdown(proposals)
    return {"reconciled": reconciled_count, "total_open": len(get_open_proposals())}


def write_visible_markdown(proposals: list[dict[str, Any]] | None = None) -> None:
    # Always filter to only proposed status on the advisory surface
    raw = proposals if proposals is not None else get_open_proposals()
    open_proposals = [p for p in raw if str(p.get("status", "proposed")).strip().lower() == "proposed"]

    grouped = {lane: [] for lane in ALLOWED_URGENCY_LANES}
    for proposal in open_proposals:
        lane = str(proposal.get("urgency_lane", "next")).strip().lower()
        grouped[lane if lane in grouped else "next"].append(proposal)

    lines = [
        "# Advisory Task Proposals",
        "",
        "_Advisory only. These are not runnable loop tasks and are not read by the orchestrator._",
        "",
    ]
    labels = {"now": "Now", "next": "Next", "later": "Later"}
    for lane in ALLOWED_URGENCY_LANES:
        lines.append(f"## {labels[lane]} ({len(grouped[lane])})")
        if not grouped[lane]:
            lines.append("")
            lines.append("_(none)_")
            lines.append("")
            continue
        lines.append("")
        for proposal in grouped[lane]:
            evidence = "; ".join(proposal.get("success_evidence", [])) or "TBD"
            lines.append(
                f"- {proposal['id']} [{proposal['source_agent']}/{proposal['work_kind']}] "
                f"{proposal['title']} — flow={proposal['target_flow']} — "
                f"gate={proposal['required_gate']} — harness={proposal['required_harness_mode']}"
            )
            lines.append(f"  reason: {proposal['reason']}")
            lines.append(f"  success evidence: {evidence}")
        lines.append("")

    VISIBLE_MD.parent.mkdir(parents=True, exist_ok=True)
    VISIBLE_MD.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Advisory task proposal utilities")
    parser.add_argument("--promote", metavar="PROPOSAL_ID", help="Promote one advisory proposal into a runnable task artifact")
    parser.add_argument("--reconcile", action="store_true", help="Reconcile the proposal store with the filesystem and refresh the advisory surface")
    args = parser.parse_args()

    if args.promote:
        print(json.dumps(promote_proposal(args.promote), indent=2))
        return

    if args.reconcile:
        print(json.dumps(reconcile_proposals(), indent=2))
        return

    parser.print_help()


if __name__ == "__main__":
    main()
