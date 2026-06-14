"""
chief_trinity_brain.py

Scans all brains, groups by domain, flags singletons/pairs, proposes
missing thirds, and optionally routes gap proposals to integration brain.

The "trinity" principle: every domain should have exactly 3 brains —
typically a Creator, a Coordinator, and a QA/Validator.

Triggered by:
  - "trinity check" / "system audit" / "brain audit" / "trinity status"
Intent: trinity_check in chief_router.py

Saves to:
  - openclaw-vault/System/Trinity Audit.md
"""

from datetime import datetime
from pathlib import Path

from chief_llm import ollama_call

# ── Domain map ────────────────────────────────────────────────────────────────
# Each domain: list of filenames (present = exists, None = proposed/missing).
# Domains with 3 = complete; <3 = needs attention.

DOMAIN_MAP = {
    "Website": {
        "members": [
            "chief_website_creative.py",
            "chief_website_coordinator.py",
            "chief_website_qa.py",
        ],
        "description": "Creative copy, section coordination, QA auditing",
    },
    "Communications": {
        "members": [
            "chief_email_brain.py",
            "chief_sms_brain.py",
            "chief_phone_brain.py",
        ],
        "description": "Email drafts/send, SMS drafts/send, phone call logging",
    },
    "Business Consulting": {
        "members": [
            "chief_cpa_brain.py",
            "chief_musiclaw_brain.py",
            "chief_publishing_brain.py",
        ],
        "description": "Tax/accounting, music law, publishing/royalties",
    },
    "Research Intelligence": {
        "members": [
            "chief_scout_brain.py",
            "chief_reflection_brain.py",
            "chief_integration_brain.py",
        ],
        "description": "Market scouting, self-reflection, integration proposals",
    },
    "System Health": {
        "members": [
            "chief_reporter_brain.py",
            "chief_validator_brain.py",
            "chief_watcher_brain.py",
        ],
        "description": "Daily reporting, reply validation, activity watching",
    },
    "Fundo": {
        "members": [
            "chief_fundo_identity.py",
            "chief_fundo_session.py",
            "chief_fundo_release.py",
        ],
        "description": "Identity/lore, production session coaching, release strategy",
    },
    "Album Production": {
        "members": [
            "chief_album_brain.py",
            "chief_album_io.py",
            "chief_album_mixer.py",
        ],
        "description": "Session tracking, file I/O, mix session briefs",
    },
    "Infrastructure": {
        "members": [
            "chief_calendar_brain.py",
            "chief_queue_brain.py",
            "chief_backup_brain.py",
        ],
        "description": "Calendar/scheduling, task queue, repo backup",
    },
    "Finance Operations": {
        "members": [
            "chief_billing_brain.py",
            "chief_invoice_brain.py",
            "chief_financial_brain.py",
        ],
        "description": "Billing intake, invoice generation, financial reporting (P&L, outstanding, tax projection)",
    },
    "Analytics": {
        "members": [
            "chief_analytics_brain.py",
            "chief_goals_brain.py",
            "chief_momentum_brain.py",
        ],
        "description": "Weekly metrics, goal tracking, activity momentum",
    },
    "Marketing": {
        "members": [
            "chief_marketing_brain.py",
            "chief_content_brain.py",
            "chief_brand_brain.py",
        ],
        "description": "Marketing ideas/drafts, content calendar, brand voice",
    },
    "Brainstorm": {
        "members": [
            "chief_brainstorm_brain.py",
            "chief_brainstorm_router.py",
            "chief_brainstorm_watcher.py",
        ],
        "description": "Idea capture/synthesis, routing to destinations, condition-based watching",
    },
    "Focus & Approvals": {
        "members": [
            "chief_focus_shield.py",
            "chief_approval_bridge.py",
            "chief_focus_reporter.py",
        ],
        "description": "Work block interruption gating, multi-choice Telegram approval bridge, end-of-day focus/approval digest",
    },
}

BRAIN_DIR = Path(__file__).resolve().parent
AUDIT_MD  = Path("/mnt/c/OpenClawShared/openclaw-vault/System/Trinity Audit.md")


# ── Scanner ────────────────────────────────────────────────────────────────────

def _scan() -> dict:
    """Check each domain member against disk. Returns enriched domain data."""
    results = {}
    for domain, cfg in DOMAIN_MAP.items():
        present = []
        missing_slots = 0
        for member in cfg["members"]:
            if member is None:
                missing_slots += 1
            elif (BRAIN_DIR / member).exists():
                present.append(member)
            else:
                missing_slots += 1  # defined but not yet built

        total_slots = len(cfg["members"])
        results[domain] = {
            "present": present,
            "present_count": len(present),
            "total_slots": total_slots,
            "missing_slots": missing_slots,
            "description": cfg["description"],
            "proposed_third": cfg.get("proposed_third"),
            "complete": missing_slots == 0,
        }
    return results


def _status_icon(r: dict) -> str:
    if r["complete"]:
        return "✓"
    if r["present_count"] == 0:
        return "✗"
    if r["present_count"] >= r["total_slots"] - 1:
        return "⚠"
    return "✗"


# ── Report builder ─────────────────────────────────────────────────────────────

def _build_report(scan: dict) -> str:
    complete = [(d, r) for d, r in scan.items() if r["complete"]]
    incomplete = [(d, r) for d, r in scan.items() if not r["complete"]]

    lines = [
        f"**Trinity Audit — {datetime.now().strftime('%Y-%m-%d %H:%M')}**",
        f"Domains complete: {len(complete)}/{len(scan)}",
        "",
    ]

    if complete:
        lines.append("**Complete Trinities** ✓")
        for domain, r in complete:
            lines.append(f"  {domain}: {', '.join(r['present'])}")
        lines.append("")

    if incomplete:
        lines.append("**Incomplete Domains** ⚠")
        for domain, r in incomplete:
            icon = _status_icon(r)
            present_str = ", ".join(r["present"]) if r["present"] else "none"
            lines.append(f"\n  {icon} {domain} ({r['present_count']}/{r['total_slots']})")
            lines.append(f"    Present: {present_str}")
            lines.append(f"    Role: {r['description']}")
            if r["proposed_third"]:
                lines.append(f"    Missing: {r['proposed_third']}")

    return "\n".join(lines)


# ── Vault write ────────────────────────────────────────────────────────────────

def _write_audit_md(report: str, narrative: str = "") -> None:
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    content = (
        "---\n"
        "type: trinity-audit\n"
        f"last_updated: {today}\n"
        "---\n\n"
        "# Trinity Audit\n\n"
        "_Managed by `chief_trinity_brain.py`. Run 'trinity check' to refresh._\n\n"
    )
    if narrative and narrative != "(narrative unavailable)":
        content += f"## Analysis\n\n{narrative}\n\n"
    content += report.replace("**", "").replace("✓", "✓").replace("⚠", "⚠") + "\n"
    AUDIT_MD.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_MD.write_text(content, encoding="utf-8")


# ── LLM narrative ─────────────────────────────────────────────────────────────

_NARRATIVE_PROMPT = """\
You are analyzing the OpenClaw AI music management system's "trinity" architecture.
The system uses brain trilogies — each domain should have exactly 3 specialist brains.

Here is the current audit:

{report}

Write a 3-5 sentence executive summary:
- Which domains are fully operational
- Which gaps are most impactful to fix next
- Any patterns worth noting

Be concise and direct. No bullet points. No markdown headers."""


def _build_narrative(report: str) -> str:
    prompt = _NARRATIVE_PROMPT.format(report=report)
    try:
        result = ollama_call(prompt, timeout=30, task_class="chief_structured_plan").strip()
    except Exception:
        result = ""
    return result if result else _fallback_narrative(report)


def _fallback_narrative(report: str) -> str:
    """Deterministic summary for audit runs when local narrative generation is unavailable."""
    complete_line = "Domains complete: unknown"
    gaps = []
    for line in report.splitlines():
        stripped = line.strip()
        if stripped.startswith("Domains complete:"):
            complete_line = stripped
        elif stripped.startswith(("⚠ ", "✗ ")):
            gaps.append(stripped.split(" (", 1)[0].lstrip("⚠✗ ").strip())

    if gaps:
        gap_text = ", ".join(gaps)
        return (
            f"{complete_line}. Remaining Trinity gaps: {gap_text}. "
            "Prioritize the incomplete domains that affect operator visibility or approval flow first."
        )
    return f"{complete_line}. All tracked Trinity domains are complete; keep monitoring for drift."


# ── Integration brain bridge ───────────────────────────────────────────────────

def _propose_gaps_to_integration(scan: dict) -> list[str]:
    """Convert incomplete domains into integration proposals."""
    try:
        from chief_integration_brain import handle as integration_handle
    except ImportError:
        return ["Integration brain unavailable — proposals not queued."]

    incomplete = [(d, r) for d, r in scan.items() if not r["complete"] and r["proposed_third"]]
    if not incomplete:
        return ["All gaps already have proposals queued."]

    queued = []
    for domain, r in incomplete:
        text = (
            f"integration proposals: Trinity gap in {domain} domain. "
            f"Need: {r['proposed_third']}. "
            f"This completes the {domain} trinity ({r['present_count']}/{r['total_slots']} present)."
        )
        integration_handle(text)
        queued.append(f"Queued proposal for {domain}: {r['proposed_third'][:60]}...")

    return queued


# ── Public handlers ────────────────────────────────────────────────────────────

def _handle_check() -> list[str]:
    scan = _scan()
    report = _build_report(scan)
    narrative = _build_narrative(report)
    _write_audit_md(report, narrative)

    complete_count = sum(1 for r in scan.values() if r["complete"])
    total = len(scan)
    incomplete = [(d, r) for d, r in scan.items() if not r["complete"]]

    reply_lines = [
        f"Trinity Audit: {complete_count}/{total} domains complete.",
        "",
        narrative,
    ]

    if incomplete:
        reply_lines.append("\nGaps:")
        for domain, r in incomplete:
            icon = _status_icon(r)
            reply_lines.append(f"  {icon} {domain} ({r['present_count']}/{r['total_slots']}): {r.get('proposed_third', 'no proposal yet')[:70]}")

    reply_lines.append("\nAudit saved to vault/System/Trinity Audit.md")
    return ["\n".join(reply_lines)]


def _handle_propose() -> list[str]:
    """Push all gaps to integration brain as proposals."""
    scan = _scan()
    results = _propose_gaps_to_integration(scan)
    return ["\n".join(["Trinity gaps queued to integration brain:"] + results)]


# ── Public entry point ─────────────────────────────────────────────────────────

def handle(text: str = "") -> list[str]:
    t = text.lower().strip()

    if "propose" in t or "queue gaps" in t:
        return _handle_propose()

    # Default: run the audit
    return _handle_check()


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "trinity check"
    print(f"Running trinity brain: '{text}'\n")
    for line in handle(text):
        print(line)
