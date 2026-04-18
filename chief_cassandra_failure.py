"""
chief_cassandra_failure.py

Deterministic Chief-side reporting for Cassandra timeouts/failures.
Keeps policy-denial checks ahead of deeper runtime investigation.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from chief_notify import send as notify_chief

_APPROVAL_PENDING = Path("/mnt/c/OpenClaw/logs/approval_pending.json")
_CASSANDRA_CONVO_LOG = Path("/mnt/c/OpenClaw/logs/cassandra_conversations.jsonl")
_CASSANDRA_CORRESPONDENCE_LOG = Path("/mnt/c/OpenClaw/logs/cassandra_correspondence.jsonl")
_CASSANDRA_LISTENER_LOG = Path("/mnt/c/OpenClaw/logs/cassandra_listener.out")
_POLISH_TASKS_DIR = Path("/home/openclaw/polish_loop/tasks")
_APPROVAL_TIMEOUT_S = 86400


def _truncate(text: str, limit: int) -> str:
    clean = " ".join(str(text or "").split()).strip()
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 1)].rstrip() + "…"


def _request_summary(text: str) -> str:
    first_line = next((line.strip() for line in str(text or "").splitlines() if line.strip()), "")
    return _truncate(first_line or "(empty request)", 120)


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_recent_jsonl(path: Path, limit: int = 40) -> list[dict]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[-limit:]
    except Exception:
        return []
    rows: list[dict] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def _fresh_pending_approval() -> dict:
    data = _load_json(_APPROVAL_PENDING)
    if not data or data.get("status") != "pending":
        return {}
    requested_at = data.get("requested_at", "")
    if not requested_at:
        return data
    try:
        requested_dt = datetime.strptime(requested_at, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return data
    if (datetime.now() - requested_dt).total_seconds() > _APPROVAL_TIMEOUT_S:
        return {}
    return data


def _latest_email_gate_signal(within_minutes: int = 10) -> dict:
    cutoff = datetime.now() - timedelta(minutes=within_minutes)
    for entry in reversed(_load_recent_jsonl(_CASSANDRA_CORRESPONDENCE_LOG, limit=80)):
        try:
            entry_dt = datetime.strptime(entry.get("ts", ""), "%Y-%m-%d %H:%M:%S")
        except Exception:
            continue
        if entry_dt < cutoff:
            break
        if entry.get("route") != "email_send":
            continue
        state = str(entry.get("state", ""))
        if state in {"awaiting_approval", "blocked", "send_failed"}:
            return entry
    return {}


def _latest_listener_error_line() -> str:
    try:
        lines = _CASSANDRA_LISTENER_LOG.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return ""
    for line in reversed(lines[-120:]):
        stripped = line.strip()
        if not stripped:
            continue
        if "[cassandra_listener] error:" in stripped or "Traceback" in stripped:
            return stripped
    return ""


def _queue_failure_task(summary: str) -> str | None:
    try:
        _POLISH_TASKS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        task_name = f"chief-cassandra-failure-{timestamp}"
        body = (
            f"title: {task_name}\n"
            f"profile: quick\n"
            f"goal: Investigate why Cassandra timed out or failed for the operator\n"
            f"scope:\n"
            f"- Request summary: {summary}\n"
            f"- Check /mnt/c/OpenClaw/logs/cassandra_listener.out\n"
            f"- Check /mnt/c/OpenClaw/logs/cassandra_conversations.jsonl\n"
            f"- Check /mnt/c/OpenClaw/logs/cassandra_correspondence.jsonl\n"
            f"success:\n"
            f"- Root cause identified or bounded\n"
            f"- Exact next step recorded\n"
            f"generated_by: chief_cassandra_failure\n"
            f"generated_at: {datetime.now().isoformat()}\n"
        )
        (_POLISH_TASKS_DIR / f"{task_name}.md").write_text(body, encoding="utf-8")
        return task_name
    except Exception:
        return None


def _build_report(summary: str) -> str:
    pending = _fresh_pending_approval()
    if pending:
        action = _truncate(str(pending.get("action", "approval request")), 140)
        return (
            f"Chief investigated Cassandra's failure for: {summary}\n\n"
            f"Outcome: Winship must fix it manually\n"
            f"What failed: Cassandra is waiting on Guardian approval before she can continue.\n"
            f"Where it failed: Approval gate for {action}.\n"
            f"Likely cause: This request needs your explicit approval, so Cassandra cannot complete it on her own.\n"
            f"Exact next step: Approve or deny the pending Guardian request."
        )

    gate_signal = _latest_email_gate_signal()
    if gate_signal:
        detail = _truncate(str(gate_signal.get("detail", "approval gate blocked the send step")), 160)
        state = str(gate_signal.get("state", "blocked"))
        if state == "awaiting_approval":
            outcome = "Winship must fix it manually"
            likely = "The send step is waiting on your Guardian approval."
            next_step = "Approve or deny the Guardian request so the send step can finish."
        else:
            outcome = "Cassandra cannot do this because it is outside her lane / permission / scope"
            likely = "Guardian or a deterministic trust/policy gate denied the action."
            next_step = "Review the Guardian denial detail and decide whether to adjust policy or rerun the request differently."
        return (
            f"Chief investigated Cassandra's failure for: {summary}\n\n"
            f"Outcome: {outcome}\n"
            f"What failed: Cassandra could not complete the email send step.\n"
            f"Where it failed: Cassandra email send state `{state}`.\n"
            f"Likely cause: {likely} Detail: {detail}\n"
            f"Exact next step: {next_step}"
        )

    error_line = _latest_listener_error_line()
    task_name = _queue_failure_task(summary)
    next_step = (
        f"I queued {task_name} to inspect the latest Cassandra logs and failure path."
        if task_name
        else "Inspect the latest Cassandra listener and conversation logs."
    )
    likely_cause = (
        f"Latest listener evidence: {_truncate(error_line, 180)}"
        if error_line
        else "No policy denial was active. Cassandra appears to have stalled inside her processing path or an upstream model/tool call."
    )
    return (
        f"Chief investigated Cassandra's failure for: {summary}\n\n"
        f"Outcome: Chief can queue/autonomously fix it\n"
        f"What failed: Cassandra did not produce a real result within 60 seconds.\n"
        f"Where it failed: Cassandra listener while waiting on cassandra_brain.handle().\n"
        f"Likely cause: {likely_cause}\n"
        f"Exact next step: {next_step}"
    )


def investigate_cassandra_timeout(user_text: str, session_meta: dict | None = None) -> None:
    del session_meta  # reserved for future narrowing without changing the call surface
    summary = _request_summary(user_text)
    notify_chief(f"Chief is working on Cassandra's failure for: {summary}")
    notify_chief(_build_report(summary))
