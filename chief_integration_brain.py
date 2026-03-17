"""
chief_integration_brain.py

Reads scout findings and turns them into structured proposals.
Two lanes: new_feature (capability we don't have) or upgrade (improve existing brain).
Never touches code. Writes proposals only.

Triggered by:
  - "integration proposals" / "what can we add" → generate proposals
  - "approve PROP-XXXXXXXX-NNN" → approve a pending proposal
  - "reject PROP-XXXXXXXX-NNN"  → reject a pending proposal
Intent: integration_proposals in chief_router.py

Saves to:
  - /mnt/c/OpenClawShared/album/integration_proposals.json (source of truth)
  - openclaw-vault/Research/Integration Proposals.md (Obsidian)
"""

import json
import re
from datetime import datetime
from pathlib import Path

from chief_llm import ollama_json, ollama_call

# ── Paths ──────────────────────────────────────────────────────────────────────

PROPOSALS_JSON = Path("/mnt/c/OpenClawShared/album/integration_proposals.json")
PROPOSALS_MD   = Path("/mnt/c/OpenClawShared/openclaw-vault/Research/Integration Proposals.md")
SCOUT_JSON     = Path("/mnt/c/OpenClawShared/album/scout_findings.json")

# ── Known brains (for affected_files suggestions) ─────────────────────────────

KNOWN_BRAINS = [
    "chief_album_brain.py",
    "chief_billing_brain.py",
    "chief_marketing_brain.py",
    "chief_approval_brain.py",
    "chief_reporter_brain.py",
    "chief_validator_brain.py",
    "chief_scout_brain.py",
    "chief_integration_brain.py",
    "chief_reflection_brain.py",
    "chief_router.py",
    "chief_llm.py",
    "chief_obsidian_sync.py",
]

# ── Proposal storage ───────────────────────────────────────────────────────────

def _load_proposals() -> dict:
    if PROPOSALS_JSON.exists():
        try:
            return json.loads(PROPOSALS_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"proposals": []}


def _save_proposals(data: dict) -> None:
    PROPOSALS_JSON.parent.mkdir(parents=True, exist_ok=True)
    PROPOSALS_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _new_prop_id() -> str:
    today = datetime.now().strftime("%Y%m%d")
    data  = _load_proposals()
    count = sum(1 for p in data.get("proposals", []) if p["id"].startswith(f"PROP-{today}"))
    return f"PROP-{today}-{count + 1:03d}"


# ── Scout findings loader ──────────────────────────────────────────────────────

def _latest_findings() -> list[dict]:
    """Return findings from the most recent scout run."""
    if not SCOUT_JSON.exists():
        return []
    try:
        data = json.loads(SCOUT_JSON.read_text(encoding="utf-8"))
        runs = data.get("runs", [])
        if runs:
            return runs[-1].get("findings", [])
    except Exception:
        pass
    return []


# ── LLM proposal generation ────────────────────────────────────────────────────

_PROPOSALS_PROMPT = """\
You are an integration strategist for an AI assistant system called OpenClaw.

Current brains in the system:
{brains}

Recent scout findings:
{findings}

Your job: generate integration proposals — one per finding that is actionable.
Split each into one of two lanes:
- new_feature: a capability OpenClaw does not have at all
- upgrade: an existing brain or component that this finding could improve

For each proposal:
- Be specific about WHAT changes (which brain, what new function)
- Estimate effort honestly: quick (< 1 day), medium (2-3 days), large (multi-day)
- Reference the scout finding by name in the source field

Rules:
- Skip findings that are vague, irrelevant to this stack, or not actionable
- Maximum 5 proposals
- Return a JSON array only, no markdown

Each object must have exactly these keys:
  title          — short proposal name (< 10 words)
  lane           — new_feature | upgrade
  source         — name of the scout finding this comes from
  description    — 2-3 sentences on exactly what to build/change
  affected_files — list of filenames that would be touched (from the known brains list)
  effort         — quick | medium | large

Return only the JSON array."""


def _generate_proposals(findings: list[dict]) -> list[dict]:
    if not findings:
        return []

    findings_text = "\n".join(
        f"- {f['name']} [{f['status']}]: {f['summary']}. Why it matters: {f['why_it_matters']}"
        for f in findings
    )
    prompt = _PROPOSALS_PROMPT.format(
        brains="\n".join(f"  - {b}" for b in KNOWN_BRAINS),
        findings=findings_text,
    )
    raw = ollama_json(prompt, timeout=60)
    if not isinstance(raw, list):
        return []

    proposals = []
    for p in raw:
        if not isinstance(p, dict):
            continue
        if p.get("lane") not in ("new_feature", "upgrade"):
            p["lane"] = "new_feature"
        if p.get("effort") not in ("quick", "medium", "large"):
            p["effort"] = "medium"
        if not isinstance(p.get("affected_files"), list):
            p["affected_files"] = []
        proposals.append(p)
    return proposals


# ── Proposal persistence ───────────────────────────────────────────────────────

def _save_new_proposals(raw_proposals: list[dict]) -> list[dict]:
    """Assign IDs, persist to JSON, return the saved proposal objects."""
    data      = _load_proposals()
    saved     = []
    today     = datetime.now().strftime("%Y-%m-%d")
    today_key = datetime.now().strftime("%Y%m%d")
    base_count = sum(1 for p in data.get("proposals", []) if p["id"].startswith(f"PROP-{today_key}"))

    for i, p in enumerate(raw_proposals):
        prop = {
            "id":             f"PROP-{today_key}-{base_count + i + 1:03d}",
            "date":           today,
            "title":          p.get("title", "Untitled"),
            "lane":           p.get("lane", "new_feature"),
            "source":         p.get("source", ""),
            "description":    p.get("description", ""),
            "affected_files": p.get("affected_files", []),
            "effort":         p.get("effort", "medium"),
            "status":         "pending",
            "decided_at":     None,
            "notes":          "",
        }
        data.setdefault("proposals", []).append(prop)
        saved.append(prop)

    _save_proposals(data)
    return saved


# ── Markdown writer ────────────────────────────────────────────────────────────

def _write_proposals_md() -> None:
    data      = _load_proposals()
    proposals = data.get("proposals", [])
    today     = datetime.now().strftime("%Y-%m-%d")

    pending  = [p for p in proposals if p["status"] == "pending"]
    approved = [p for p in proposals if p["status"] == "approved"]
    rejected = [p for p in proposals if p["status"] in ("rejected", "archived")]

    def section(title: str, items: list[str]) -> str:
        if not items:
            return f"## {title}\n\n_(none)_\n"
        return f"## {title}\n\n" + "\n\n".join(items) + "\n"

    def render(p: dict) -> str:
        lane_label  = "New Feature" if p["lane"] == "new_feature" else "Upgrade"
        effort_map  = {"quick": "< 1 day", "medium": "2–3 days", "large": "Multi-day"}
        effort_str  = effort_map.get(p["effort"], p["effort"])
        files_str   = ", ".join(p["affected_files"]) if p["affected_files"] else "TBD"
        decided_str = f"\n- **Decided:** {p['decided_at']}" if p.get("decided_at") else ""
        return (
            f"### {p['id']} — {p['title']}\n"
            f"- **Lane:** {lane_label}  \n"
            f"- **Source:** {p['source']}  \n"
            f"- **Effort:** {effort_str}  \n"
            f"- **Files:** {files_str}{decided_str}\n\n"
            f"{p['description']}"
        )

    content = (
        "---\n"
        "type: integration-proposals\n"
        f"last_updated: {today}\n"
        "---\n\n"
        "# Integration Proposals\n\n"
        "_Managed by `chief_integration_brain.py` — do not edit manually._\n\n"
        + section("Pending",            [render(p) for p in pending])
        + "\n"
        + section("Approved",           [render(p) for p in approved])
        + "\n"
        + section("Rejected / Archived",[render(p) for p in rejected])
    )
    PROPOSALS_MD.write_text(content, encoding="utf-8")


# ── Telegram format ────────────────────────────────────────────────────────────

def _format_proposal_message(p: dict) -> str:
    lane_label = "New Feature" if p["lane"] == "new_feature" else "Upgrade"
    effort_map = {"quick": "< 1 day", "medium": "2–3 days", "large": "Multi-day"}
    return (
        f"🔧 Integration Proposal {p['id']}\n\n"
        f"Type: {lane_label}\n"
        f"Title: {p['title']}\n"
        f"Effort: {effort_map.get(p['effort'], p['effort'])}\n"
        f"Source: {p['source']}\n\n"
        f"{p['description']}\n\n"
        f"Reply \"approve {p['id']}\" or \"reject {p['id']}\""
    )


# ── Approve / reject handlers ──────────────────────────────────────────────────

_PROP_ID_RE = re.compile(r"PROP-\d{8}-\d{3}", re.IGNORECASE)


def _handle_decision(text: str) -> list[str]:
    t = text.lower().strip()
    is_approve = t.startswith("approve")
    is_reject  = t.startswith("reject")

    m = _PROP_ID_RE.search(text.upper())
    if not m:
        return ["Couldn't find a proposal ID. Format: 'approve PROP-XXXXXXXX-NNN'"]

    prop_id = m.group(0)
    data    = _load_proposals()
    match   = next((p for p in data.get("proposals", []) if p["id"] == prop_id), None)

    if not match:
        return [f"Proposal {prop_id} not found."]
    if match["status"] != "pending":
        return [f"{prop_id} is already {match['status']}."]

    new_status        = "approved" if is_approve else "rejected"
    match["status"]   = new_status
    match["decided_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    _save_proposals(data)
    _write_proposals_md()

    icon = "✅" if is_approve else "❌"
    return [f"{icon} {prop_id} marked as {new_status}: {match['title']}"]


# ── Public entry point ─────────────────────────────────────────────────────────

def handle(text: str = "") -> list[str]:
    t = text.lower().strip()

    # Approve / reject decision
    if t.startswith("approve ") or t.startswith("reject "):
        return _handle_decision(text)

    # Generate proposals from latest scout findings
    findings = _latest_findings()
    if not findings:
        return [
            "No scout findings available. Run a scout report first:\n"
            "Try: 'scout report' or 'what's new in AI'"
        ]

    raw_proposals = _generate_proposals(findings)
    if not raw_proposals:
        return ["Couldn't generate proposals from current scout findings. Try running a new scout report."]

    saved = _save_new_proposals(raw_proposals)
    _write_proposals_md()

    replies = [f"Generated {len(saved)} integration proposal(s):\n"]
    for p in saved:
        replies.append(_format_proposal_message(p))

    return replies


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Running integration brain...\n")
    for reply in handle():
        print(reply)
        print()
    print(f"Proposals MD: {PROPOSALS_MD}")
    print(f"Proposals JSON: {PROPOSALS_JSON}")
