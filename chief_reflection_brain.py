"""
chief_reflection_brain.py

Closes the feedback loop. Reads vault logs and data files to assess
what's working, what's stalled, and what needs attention.

Triggered by: "reflection report", "what's working", "monthly report",
              "usage report", "system reflection"
Intent: reflection_report in chief_router.py

Saves to:
  - /mnt/c/OpenClawShared/album/reflection_log.json (source of truth)
  - openclaw-vault/Research/Reflection Log.md (Obsidian)
"""

import csv
import json
from datetime import datetime
from pathlib import Path

from chief_llm import ollama_json, ollama_call

# ── Paths ──────────────────────────────────────────────────────────────────────

REFLECTION_JSON = Path("/mnt/c/OpenClawShared/album/reflection_log.json")
REFLECTION_MD   = Path("/mnt/c/OpenClawShared/openclaw-vault/Research/Reflection Log.md")

VAULT           = Path("/mnt/c/OpenClawShared/openclaw-vault")
VALIDATION_LOG  = VAULT / "System" / "Validation Log.md"
APPROVAL_LOG    = VAULT / "System" / "Approval Log.md"
DAILY_REPORT    = VAULT / "System" / "Daily Report.md"
SCOUT_LOG       = VAULT / "Research" / "Scout Log.md"
PROPOSALS_MD    = VAULT / "Research" / "Integration Proposals.md"
CONTENT_LOG_MD  = VAULT / "Marketing" / "Content Log.md"

SCOUT_JSON      = Path("/mnt/c/OpenClawShared/album/scout_findings.json")
PROPOSALS_JSON  = Path("/mnt/c/OpenClawShared/album/integration_proposals.json")
CONTENT_LOG_JSON = Path("/mnt/c/OpenClawShared/album/content_log.json")
ALBUM_CSV       = Path("/mnt/c/OpenClawShared/album/album_work_log.csv")

_MAX_STORED_RUNS = 10


# ── Data collectors ────────────────────────────────────────────────────────────

def _tail(path: Path, n: int = 200) -> str:
    """Return last n lines of a file, or empty string if missing."""
    if not path.exists():
        return ""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        return "\n".join(lines[-n:])
    except Exception:
        return ""


def _count_validation_issues() -> dict:
    """Count entries in validation log by issue type."""
    text = _tail(VALIDATION_LOG, 500)
    counts = {"empty_reply": 0, "traceback": 0, "code_fence": 0, "truncated": 0, "total": 0}
    for line in text.splitlines():
        lower = line.lower()
        if "empty" in lower or "no reply" in lower:
            counts["empty_reply"] += 1
        elif "traceback" in lower or "error" in lower:
            counts["traceback"] += 1
        elif "code fence" in lower or "code_fence" in lower:
            counts["code_fence"] += 1
        elif "truncat" in lower:
            counts["truncated"] += 1
        if "intent:" in lower:
            counts["total"] += 1
    return counts


def _count_approvals() -> dict:
    """Count approval outcomes from approval log."""
    text = _tail(APPROVAL_LOG, 500)
    counts = {"approved": 0, "denied": 0, "timed_out": 0}
    for line in text.splitlines():
        lower = line.lower()
        if "approved" in lower:
            counts["approved"] += 1
        elif "denied" in lower:
            counts["denied"] += 1
        elif "timed out" in lower or "timeout" in lower:
            counts["timed_out"] += 1
    return counts


def _scout_summary() -> dict:
    """How many scout runs, latest date."""
    if not SCOUT_JSON.exists():
        return {"runs": 0, "latest": None}
    try:
        data = json.loads(SCOUT_JSON.read_text(encoding="utf-8"))
        runs = data.get("runs", [])
        return {
            "runs": len(runs),
            "latest": runs[-1]["date"] if runs else None,
        }
    except Exception:
        return {"runs": 0, "latest": None}


def _proposals_summary() -> dict:
    """Count proposals by status."""
    if not PROPOSALS_JSON.exists():
        return {"total": 0, "pending": 0, "approved": 0, "rejected": 0}
    try:
        data = json.loads(PROPOSALS_JSON.read_text(encoding="utf-8"))
        proposals = data.get("proposals", [])
        return {
            "total": len(proposals),
            "pending": sum(1 for p in proposals if p["status"] == "pending"),
            "approved": sum(1 for p in proposals if p["status"] == "approved"),
            "rejected": sum(1 for p in proposals if p["status"] in ("rejected", "archived")),
        }
    except Exception:
        return {"total": 0, "pending": 0, "approved": 0, "rejected": 0}


def _content_summary() -> dict:
    """Count content log entries by status."""
    if not CONTENT_LOG_JSON.exists():
        return {"total": 0, "suggested": 0, "in_progress": 0, "posted": 0}
    try:
        data = json.loads(CONTENT_LOG_JSON.read_text(encoding="utf-8"))
        entries = data.get("entries", [])
        return {
            "total": len(entries),
            "suggested": sum(1 for e in entries if e["status"] == "suggested"),
            "in_progress": sum(1 for e in entries if e["status"] == "in_progress"),
            "posted": sum(1 for e in entries if e["status"] == "posted"),
        }
    except Exception:
        return {"total": 0, "suggested": 0, "in_progress": 0, "posted": 0}


def _album_summary() -> dict:
    """Overall album progress from CSV."""
    if not ALBUM_CSV.exists():
        return {"songs_tracked": 0, "avg_completion": 0, "locked": 0}
    try:
        rows = []
        with ALBUM_CSV.open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            return {"songs_tracked": 0, "avg_completion": 0, "locked": 0}
        pcts = []
        locked = 0
        for r in rows:
            try:
                pcts.append(int(r.get("completion_pct", 0) or 0))
            except ValueError:
                pass
            if str(r.get("version_locked", "")).lower() in ("yes", "true", "locked"):
                locked += 1
        avg = int(sum(pcts) / len(pcts)) if pcts else 0
        return {"songs_tracked": len(rows), "avg_completion": avg, "locked": locked}
    except Exception:
        return {"songs_tracked": 0, "avg_completion": 0, "locked": 0}


def _build_snapshot() -> dict:
    """Collect all metrics into a snapshot dict."""
    return {
        "date":        datetime.now().strftime("%Y-%m-%d"),
        "validation":  _count_validation_issues(),
        "approvals":   _count_approvals(),
        "scout":       _scout_summary(),
        "proposals":   _proposals_summary(),
        "content":     _content_summary(),
        "album":       _album_summary(),
        "daily_report_tail": _tail(DAILY_REPORT, 60),
    }


# ── LLM synthesis ──────────────────────────────────────────────────────────────

_REFLECTION_PROMPT = """\
You are a system health analyst for OpenClaw, an AI assistant for an independent music artist.

Here is the current usage snapshot:

VALIDATION (LLM output quality checks):
- Total issues caught: {val_total}
- Empty replies: {val_empty}, Tracebacks: {val_tb}, Code fences: {val_code}, Truncated: {val_trunc}

APPROVALS (irreversible actions gate):
- Approved: {appr_approved}, Denied: {appr_denied}, Timed out: {appr_timed}

SCOUT (research / tech digest):
- Total runs: {scout_runs}
- Latest run: {scout_latest}

INTEGRATION PROPOSALS:
- Total: {prop_total} | Pending: {prop_pending} | Approved: {prop_approved} | Rejected: {prop_rejected}

CONTENT (marketing pipeline):
- Total entries: {cont_total} | Suggested: {cont_sug} | In Progress: {cont_ip} | Posted: {cont_posted}

ALBUM PRODUCTION:
- Songs tracked: {alb_songs} | Avg completion: {alb_avg}% | Version locked: {alb_locked}

LATEST DAILY REPORT EXCERPT:
{daily_report}

Your job: write a reflection assessment with exactly 3 sections.
Return a JSON object with these keys:
  working_well    — array of 2-3 one-sentence observations on what's functioning
  pain_points     — array of 2-3 one-sentence observations on friction or stalled areas
  recommended_focus — array of 2-3 concrete, specific action suggestions

Rules:
- Be honest and specific — reference actual numbers where relevant
- If data sources are mostly empty/zero, note that the system is new and needs more usage data
- Keep each item under 20 words
- Return only valid JSON, no markdown

JSON:"""


def _synthesize(snapshot: dict) -> dict:
    val   = snapshot["validation"]
    appr  = snapshot["approvals"]
    scout = snapshot["scout"]
    prop  = snapshot["proposals"]
    cont  = snapshot["content"]
    alb   = snapshot["album"]

    prompt = _REFLECTION_PROMPT.format(
        val_total=val["total"],
        val_empty=val["empty_reply"],
        val_tb=val["traceback"],
        val_code=val["code_fence"],
        val_trunc=val["truncated"],
        appr_approved=appr["approved"],
        appr_denied=appr["denied"],
        appr_timed=appr["timed_out"],
        scout_runs=scout["runs"],
        scout_latest=scout["latest"] or "never",
        prop_total=prop["total"],
        prop_pending=prop["pending"],
        prop_approved=prop["approved"],
        prop_rejected=prop["rejected"],
        cont_total=cont["total"],
        cont_sug=cont["suggested"],
        cont_ip=cont["in_progress"],
        cont_posted=cont["posted"],
        alb_songs=alb["songs_tracked"],
        alb_avg=alb["avg_completion"],
        alb_locked=alb["locked"],
        daily_report=snapshot["daily_report_tail"] or "(no report yet)",
    )

    result = ollama_json(prompt, timeout=60)
    if not isinstance(result, dict):
        return {
            "working_well": ["System is operational."],
            "pain_points": ["LLM synthesis unavailable — check Ollama."],
            "recommended_focus": ["Run a scout report to populate research data."],
        }

    for key in ("working_well", "pain_points", "recommended_focus"):
        if not isinstance(result.get(key), list):
            result[key] = []

    return result


# ── Storage ────────────────────────────────────────────────────────────────────

def _load_reflection_json() -> dict:
    if REFLECTION_JSON.exists():
        try:
            return json.loads(REFLECTION_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"runs": []}


def _save_reflection_json(data: dict) -> None:
    REFLECTION_JSON.parent.mkdir(parents=True, exist_ok=True)
    REFLECTION_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _append_run(snapshot: dict, assessment: dict) -> None:
    data = _load_reflection_json()
    run = {
        "date":       snapshot["date"],
        "snapshot":   {k: v for k, v in snapshot.items() if k != "daily_report_tail"},
        "assessment": assessment,
    }
    runs = data.get("runs", [])
    runs.append(run)
    data["runs"] = runs[-_MAX_STORED_RUNS:]
    _save_reflection_json(data)


def _write_reflection_md() -> None:
    data = _load_reflection_json()
    runs = data.get("runs", [])
    today = datetime.now().strftime("%Y-%m-%d")

    lines = [
        "---",
        "type: reflection-log",
        f"last_updated: {today}",
        "---\n",
        "# Reflection Log\n",
        "_Managed by `chief_reflection_brain.py` — do not edit manually._\n",
    ]

    for run in reversed(runs):
        a = run.get("assessment", {})
        s = run.get("snapshot", {})
        lines.append(f"## {run['date']} — System Reflection\n")

        # Compact stats line
        scout = s.get("scout", {})
        prop  = s.get("proposals", {})
        cont  = s.get("content", {})
        alb   = s.get("album", {})
        lines.append(
            f"_Scout runs: {scout.get('runs',0)} | "
            f"Proposals: {prop.get('total',0)} ({prop.get('approved',0)} approved) | "
            f"Content posted: {cont.get('posted',0)} | "
            f"Album avg: {alb.get('avg_completion',0)}%_\n"
        )

        if a.get("working_well"):
            lines.append("### Working Well\n")
            for item in a["working_well"]:
                lines.append(f"- {item}")
            lines.append("")

        if a.get("pain_points"):
            lines.append("### Pain Points\n")
            for item in a["pain_points"]:
                lines.append(f"- {item}")
            lines.append("")

        if a.get("recommended_focus"):
            lines.append("### Recommended Focus\n")
            for item in a["recommended_focus"]:
                lines.append(f"- {item}")
            lines.append("")

        lines.append("---\n")

    REFLECTION_MD.write_text("\n".join(lines), encoding="utf-8")


# ── Telegram format ────────────────────────────────────────────────────────────

def _format_telegram(snapshot: dict, assessment: dict) -> str:
    date   = snapshot["date"]
    scout  = snapshot["scout"]
    prop   = snapshot["proposals"]
    cont   = snapshot["content"]
    alb    = snapshot["album"]

    stats = (
        f"Scout: {scout['runs']} run(s), latest {scout['latest'] or 'never'}  |  "
        f"Proposals: {prop['total']} ({prop['approved']} approved)  |  "
        f"Content: {cont['posted']} posted  |  "
        f"Album: {alb['avg_completion']}% avg"
    )

    def bullets(items: list) -> str:
        return "\n".join(f"• {i}" for i in items) if items else "• (none)"

    return (
        f"🔁 Reflection Report — {date}\n"
        f"_{stats}_\n\n"
        f"Working Well\n{bullets(assessment.get('working_well', []))}\n\n"
        f"Pain Points\n{bullets(assessment.get('pain_points', []))}\n\n"
        f"Recommended Focus\n{bullets(assessment.get('recommended_focus', []))}"
    )


# ── Public entry point ─────────────────────────────────────────────────────────

def handle(text: str = "") -> list[str]:
    """Run a reflection assessment. Returns list of reply strings."""
    snapshot   = _build_snapshot()
    assessment = _synthesize(snapshot)

    _append_run(snapshot, assessment)
    _write_reflection_md()

    return [_format_telegram(snapshot, assessment)]


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Running reflection...\n")
    for line in handle():
        print(line)
    print(f"\nReflection MD: {REFLECTION_MD}")
    print(f"Reflection JSON: {REFLECTION_JSON}")
