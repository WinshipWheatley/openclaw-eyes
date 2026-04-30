#!/usr/bin/env python3
"""Bounded 1AM end-of-day Chief review and task queueing."""

from __future__ import annotations

import csv
import datetime as dt
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from chief_llm import OLLAMA_URL, resolve_local_model
from agent_task_proposals import auto_promote_safe_retest, save_proposals

REVIEW_DIR = Path("/mnt/c/OpenClaw/logs/chief_end_of_day")
ARCHIVE_DIR = Path("/home/openclaw/polish_loop/archive")
STATUS_FILE = Path("/home/openclaw/polish_loop/status.json")
SESSION_FILE = Path("/home/openclaw/OpenClaw/state/chief_session.json")
APPROVAL_PENDING = Path("/mnt/c/OpenClaw/logs/approval_pending.json")
ROUTE_LOG = Path("/mnt/c/OpenClaw/logs/route_log.csv")
PC_OUTPUT = Path("/home/openclaw/polish_loop/current/pc_output.md")
MAC_REVIEW = Path("/home/openclaw/polish_loop/current/mac_review.md")
ORCH_LOG = Path("/mnt/c/OpenClaw/logs/orchestrator.log")
BUILDER_LOG = Path("/mnt/c/OpenClaw/logs/builder_watcher.out")
CONTINUITY_PATH = Path("/mnt/c/OpenClawShared/openclaw-vault/System/Chief Continuity.md")
ACTIVE_ROUTE_WINDOW_MINUTES = 45
FRESH_APPROVAL_WINDOW_SECONDS = 900
MAX_FINDINGS = 5
MAX_PROPOSALS = 3


def _env_int(name: str, default: int, *, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.environ.get(name, str(default))))
    except ValueError:
        return default


FAST_REVIEW_TIMEOUT_SECONDS = _env_int("OPENCLAW_EOD_FAST_TIMEOUT_SECONDS", 120, minimum=10)
STRONG_REVIEW_TIMEOUT_SECONDS = _env_int("OPENCLAW_EOD_STRONG_TIMEOUT_SECONDS", 420, minimum=60)


def _now_est() -> dt.datetime:
    try:
        from zoneinfo import ZoneInfo

        return dt.datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return dt.datetime.now()


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _last_route_at() -> dt.datetime | None:
    if not ROUTE_LOG.exists():
        return None
    try:
        with open(ROUTE_LOG, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        for row in reversed(rows[1:]):
            if not row:
                continue
            return dt.datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None
    return None


def active_user_reasons(now: dt.datetime | None = None) -> list[str]:
    now = now or _now_est()
    reasons: list[str] = []

    session = _read_json(SESSION_FILE)
    if session.get("status") == "active":
        reasons.append(f"chief_session active ({session.get('active_workflow') or 'workflow'})")

    status = _read_json(STATUS_FILE)
    loop_status = str(status.get("status", "")).strip().lower()
    if loop_status and loop_status != "idle":
        reasons.append(f"ops loop status is {loop_status}")

    approval = _read_json(APPROVAL_PENDING)
    if approval.get("status") == "pending":
        requested_at = str(approval.get("requested_at", "")).strip()
        try:
            parsed = dt.datetime.fromisoformat(requested_at)
            age = (now.replace(tzinfo=None) - parsed.replace(tzinfo=None)).total_seconds()
            if age <= FRESH_APPROVAL_WINDOW_SECONDS:
                reasons.append("fresh approval pending")
        except Exception:
            reasons.append("approval pending")

    last_route = _last_route_at()
    if last_route is not None:
        age_minutes = (now.replace(tzinfo=None) - last_route).total_seconds() / 60.0
        if age_minutes <= ACTIVE_ROUTE_WINDOW_MINUTES:
            reasons.append(f"recent operator message {int(age_minutes)}m ago")

    return reasons


def user_actively_working(now: dt.datetime | None = None) -> bool:
    return bool(active_user_reasons(now))


def _recent_repo_changes() -> str:
    try:
        result = subprocess.run(
            ["git", "-C", "/home/openclaw", "status", "--short"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        text = (result.stdout or "").strip()
        return text or "(no uncommitted repo changes reported)"
    except Exception as e:
        return f"(git status unavailable: {e})"


def _recent_archive_items(limit: int = 8) -> str:
    if not ARCHIVE_DIR.exists():
        return "(archive unavailable)"
    files = sorted(ARCHIVE_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    if not files:
        return "(no recent archived task artifacts)"
    return "\n".join(f"- {p.name}" for p in files)


def _tail_text(path: Path, limit: int = 12) -> str:
    if not path.exists():
        return f"({path.name} unavailable)"
    try:
        return "\n".join(path.read_text(errors="replace").splitlines()[-limit:])
    except Exception as e:
        return f"({path.name} unreadable: {e})"


def build_review_context(*, compact: bool = False) -> str:
    pc_limit = 1600 if compact else 3000
    review_limit = 1200 if compact else 3000
    log_limit = 8 if compact else 12
    archive_limit = 5 if compact else 8
    parts = [
        "RECENT REPO CHANGES",
        _recent_repo_changes(),
        "",
        "RECENT ARCHIVE ITEMS",
        _recent_archive_items(limit=archive_limit),
        "",
        "CURRENT PC OUTPUT",
        PC_OUTPUT.read_text(errors="replace")[:pc_limit] if PC_OUTPUT.exists() else "(pc_output unavailable)",
        "",
        "CURRENT MAC REVIEW",
        MAC_REVIEW.read_text(errors="replace")[:review_limit] if MAC_REVIEW.exists() else "(mac_review unavailable)",
        "",
        "ORCHESTRATOR LOG TAIL",
        _tail_text(ORCH_LOG, limit=log_limit),
        "",
        "BUILDER LOG TAIL",
        _tail_text(BUILDER_LOG, limit=log_limit),
    ]
    return "\n".join(parts)


def _extract_json(text: str) -> dict:
    raw = (text or "").strip()
    if not raw:
        return {}
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1] if lines and lines[-1].strip() == "```" else lines[1:])
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return {}
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}


def _review_prompt(context: str, *, compact: bool = False) -> str:
    intro = (
        "You are Chief performing a bounded end-of-day implementation review.\n"
        "Inspect what was built or changed, identify concrete bugs, gaps, hardening needs, "
        "and polish opportunities, then propose at most 3 advisory-only work requests.\n"
        "Return JSON only with keys summary, findings, proposals.\n"
        "findings must be a list of short strings.\n"
        "proposals must be a list of objects with exactly these keys:\n"
        "title, target_flow, reason, urgency_lane, required_gate, required_harness_mode, success_evidence, work_kind.\n"
        "urgency_lane must be now|next|later.\n"
        "required_gate must be operator_review|planner_review|guardian_approval|none.\n"
        "required_harness_mode must be none|dry-run|staging-replay|recorded-replay.\n"
        "work_kind must be build|repair|harness-new-flow|retest.\n"
        "These are advisory only. Do not propose direct execution or live mutation.\n"
    )
    if compact:
        intro += (
            "Keep summary to 2 short sentences, findings to at most 3 bullets, and proposals to at most 2 items.\n"
        )
    return f"{intro}\n{context}\n\nChief:"


def _single_shot_local(prompt: str, *, lane: str, timeout: int) -> str:
    model, _ = resolve_local_model(prompt, lane=lane)
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return str(data.get("response", "") or "").strip()
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError):
        return ""


def _run_review_model(context: str) -> dict:
    fast_prompt = _review_prompt(context, compact=True)
    fast_raw = _single_shot_local(
        fast_prompt,
        lane="fast",
        timeout=FAST_REVIEW_TIMEOUT_SECONDS,
    )
    parsed = _extract_json(fast_raw)
    if parsed.get("summary") or parsed.get("findings") or parsed.get("proposals"):
        parsed["_review_meta"] = {
            "structured_output_lane": "fast",
            "fast_attempt_structured": True,
            "strong_attempt_structured": False,
            "empty_output_cause": None,
        }
        return parsed

    strong_prompt = _review_prompt(context, compact=True)
    strong_raw = _single_shot_local(
        strong_prompt,
        lane="deep",
        timeout=STRONG_REVIEW_TIMEOUT_SECONDS,
    )
    parsed = _extract_json(strong_raw)
    if parsed.get("summary") or parsed.get("findings") or parsed.get("proposals"):
        parsed["_review_meta"] = {
            "structured_output_lane": "strong",
            "fast_attempt_structured": False,
            "strong_attempt_structured": True,
            "strong_model_lane": "deep",
            "empty_output_cause": None,
        }
        return parsed

    return {
        "summary": "Chief review fallback: local model did not return structured output tonight.",
        "findings": [
            "A bounded advisory review was attempted, but no structured local-model output arrived within the short runtime budget."
        ],
        "proposals": [],
        "_review_meta": {
            "structured_output_lane": "fallback",
            "fast_attempt_structured": False,
            "strong_attempt_structured": False,
            "empty_output_cause": "empty_or_unparseable_fast_and_strong",
        },
    }


def _fallback_advisory_proposal() -> dict:
    return {
        "title": "Morning brief harness retest",
        "target_flow": "morning_brief",
        "reason": (
            "Retest the proven morning brief harness path under dry-run execution so the overnight-safe "
            "retest lane leaves clear harness evidence artifacts."
        ),
        "urgency_lane": "next",
        "required_gate": "none",
        "required_harness_mode": "dry-run",
        "success_evidence": [
            "A fresh morning brief harness run directory is created",
            "harness_run.json, harness_run_stdout.txt, and harness_run_stderr.txt are written for the task"
        ],
        "work_kind": "retest",
    }


def run_review(now: dt.datetime | None = None) -> dict:
    now = now or _now_est()
    started = now
    t0 = time.monotonic()
    context = build_review_context(compact=True)
    parsed = _run_review_model(context)
    review_meta = parsed.get("_review_meta") if isinstance(parsed.get("_review_meta"), dict) else {}
    findings = [str(x).strip() for x in parsed.get("findings", []) if str(x).strip()][:MAX_FINDINGS]
    proposals = [p for p in parsed.get("proposals", []) if isinstance(p, dict)][:MAX_PROPOSALS]
    if not proposals:
        proposals = [_fallback_advisory_proposal()]
    saved = save_proposals(proposals, source_agent="chief", now=now) if proposals else []
    auto_promoted = auto_promote_safe_retest([proposal["id"] for proposal in saved], now=now) if saved else None
    finished = _now_est()
    duration_ms = int((time.monotonic() - t0) * 1000)

    artifact = {
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_ms": duration_ms,
        "summary": str(parsed.get("summary", "")).strip(),
        "findings": findings,
        "proposal_ids": [proposal["id"] for proposal in saved],
        "proposal_count": len(saved),
        "auto_promoted_task": auto_promoted["task_name"] if auto_promoted else None,
        "auto_promoted_proposal_id": auto_promoted["proposal_id"] if auto_promoted else None,
        "structured_output_lane": str(review_meta.get("structured_output_lane") or "unknown"),
        "fast_attempt_structured": bool(review_meta.get("fast_attempt_structured")),
        "strong_attempt_structured": bool(review_meta.get("strong_attempt_structured")),
        "empty_output_cause": review_meta.get("empty_output_cause"),
    }
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    day_key = now.date().isoformat()
    (REVIEW_DIR / f"{day_key}.json").write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    md = [
        f"# Chief End-of-Day Review — {day_key}",
        "",
        f"- Started: {artifact['started_at']}",
        f"- Finished: {artifact['finished_at']}",
        f"- Duration ms: {artifact['duration_ms']}",
        f"- Structured output lane: {artifact['structured_output_lane']}",
        f"- Fast lane structured: {artifact['fast_attempt_structured']}",
        f"- Strong lane structured: {artifact['strong_attempt_structured']}",
        f"- Empty-output cause: {artifact['empty_output_cause'] or '(none)'}",
        "",
        "## Summary",
        artifact["summary"] or "(empty)",
        "",
        "## Findings",
    ]
    md.extend(f"- {item}" for item in findings) if findings else md.append("- (none)")
    md.append("")
    md.append("## Advisory Proposals")
    md.extend(f"- {item}" for item in artifact["proposal_ids"]) if artifact["proposal_ids"] else md.append("- (none)")
    md.append("")
    md.append("## Auto-Promotion")
    if artifact["auto_promoted_task"]:
        md.append(f"- proposal: {artifact['auto_promoted_proposal_id']}")
        md.append(f"- task: {artifact['auto_promoted_task']}")
    else:
        md.append("- (none)")
    (REVIEW_DIR / f"{day_key}.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    # Write Chief Continuity.md
    CONTINUITY_PATH.parent.mkdir(parents=True, exist_ok=True)
    continuity_md = [
        "# Chief Continuity & Carry-Forward State",
        f"_Generated: {now.strftime('%Y-%m-%d %H:%M:%S')}_",
        "",
        "## 🌙 Nightly Summary",
        artifact["summary"] or "(empty)",
        "",
        "## ✅ Verified",
        "- (Not explicitly tracked in current prompt, reserving for future)",
        "",
        "## 🤔 Inferred",
        "- (Not explicitly tracked in current prompt, reserving for future)",
        "",
        "## 📋 Actionable Tasks Queued",
    ]
    if artifact["proposal_ids"]:
        for proposal in saved:
            continuity_md.append(f"- [{proposal['id']}]: {proposal.get('title', 'untitled')} ({proposal.get('work_kind', 'unknown')} -> {proposal.get('target_flow', 'unknown')})")
    else:
        continuity_md.append("- (none)")

    # Also include findings in continuity
    if findings:
        continuity_md.extend(["", "## 🔍 Findings & Observations"])
        continuity_md.extend(f"- {item}" for item in findings)

    CONTINUITY_PATH.write_text("\n".join(continuity_md) + "\n", encoding="utf-8")

    return artifact
