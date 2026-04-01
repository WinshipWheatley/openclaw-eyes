"""
chief_scout_brain.py

Monitors new AI tools, platforms, APIs, and music tech.
Knows the current OpenClaw stack so it never suggests duplicates.
Delivers a digest rated: ready_now / coming_soon / watch_this_space.

Triggered by: "scout report", "what's new in AI", "tech digest", etc.
Intent: scout_report in chief_router.py

Saves to:
  - /mnt/c/OpenClawShared/album/scout_findings.json (machine-readable)
  - openclaw-vault/Research/Scout Log.md (Obsidian)
"""

import json
from datetime import datetime
from pathlib import Path

from chief_llm import ollama_json

# ── Paths ──────────────────────────────────────────────────────────────────────

SCOUT_JSON  = Path("/mnt/c/OpenClawShared/album/scout_findings.json")
SCOUT_LOG   = Path("/mnt/c/OpenClawShared/openclaw-vault/Research/Scout Log.md")

# ── Rejection ledger guardrail ────────────────────────────────────────────────
# Machine-readable copy of the rejection decisions in:
#   openclaw-vault/Research/Rejection Ledger.md
#
# Rule: Do not propose any integration in a REJECTED_CATEGORIES bucket or whose
# name matches a REJECTED_SOURCES entry. A "Meaningful Change" must be explicitly
# logged in the Rejection Ledger by the Chief before a rejected category can be
# re-evaluated. Update this block only after logging that change.

REJECTED_CATEGORIES: dict = {
    "Legacy LLM": (
        "Technical Debt / Deprecated — replaced by local Qwen/Gemini. "
        "External cloud LLMs add latency, cost, and API dependency with no advantage."
    ),
    "Non-Music Graphics": (
        "Domain Irrelevance — project focus is a 12-song music release. "
        "3D modeling, character generation, and unrelated visual graphics tools are out of scope."
    ),
}

# Specific tool names (lowercase) that are permanently on the rejected list.
REJECTED_SOURCES: frozenset = frozenset({
    "palm 2", "palm2", "google palm", "palm api",   # Legacy LLM
    "daz 3d", "daz3d", "daz",                       # Non-Music Graphics
})

_REJECTED_CONTEXT = "\n".join(
    f"  - {cat}: {reason}" for cat, reason in REJECTED_CATEGORIES.items()
)
_REJECTED_SOURCES_FLAT = ", ".join(sorted(REJECTED_SOURCES))


def _is_rejected(finding: dict) -> bool:
    """Return True if a scout finding matches a rejected source or category."""
    name = finding.get("name", "").lower()
    category = finding.get("category", "").lower()
    if any(src in name for src in REJECTED_SOURCES):
        return True
    # Map scout categories to rejection buckets
    if category == "ai-llm" and "local" not in name and "ollama" not in name:
        # Only reject if it's a cloud/external LLM proposal, not local models
        pass  # let synthesis prompt handle nuance; hard-reject only named sources
    return False


def _filter_rejected(findings: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split findings into (accepted, rejected). Logs any rejections."""
    accepted, blocked = [], []
    for f in findings:
        if _is_rejected(f):
            blocked.append(f)
        else:
            accepted.append(f)
    return accepted, blocked


# ── Known stack (filter out anything we already have) ─────────────────────────

KNOWN_STACK = {
    "llm":            ["qwen2.5-coder:7b", "ollama", "qwen", "local llm"],
    "messaging":      ["telegram", "python-telegram-bot"],
    "storage":        ["obsidian", "csv", "json", "markdown", "sqlite"],
    "brains": [
        "album brain", "billing brain", "marketing brain", "approval brain",
        "reporter brain", "validator brain", "scout brain",
        "integration brain", "reflection brain",
    ],
    "integrations":   ["google calendar", "canva", "duckduckgo"],
    "infrastructure": ["wsl2", "python 3.12", "windows", "linux"],
    "services":       ["deep pocket records", "deeppocketrecords.com"],
}

_STACK_FLAT = " | ".join(
    item for items in KNOWN_STACK.values() for item in items
)

# ── Search queries ─────────────────────────────────────────────────────────────

SEARCH_QUERIES = [
    "AI music production tools 2026",
    "new AI developer APIs tools 2026",
    "music tech startup platform 2026",
    "Telegram bot AI assistant tools",
]

# ── Web search (best-effort) ───────────────────────────────────────────────────

def _web_search(query: str, max_results: int = 4) -> list[dict]:
    """Search DuckDuckGo. Returns list of {title, body, url}. Returns [] on failure."""
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            return [
                {"title": r.get("title", ""), "body": r.get("body", ""), "url": r.get("href", "")}
                for r in ddgs.text(query, max_results=max_results)
            ]
    except Exception:
        return []


def _gather_search_results() -> tuple[list[dict], bool]:
    """Run all search queries. Returns (results, live_search_used)."""
    results = []
    for q in SEARCH_QUERIES:
        hits = _web_search(q)
        results.extend(hits)
    return results, bool(results)

# ── LLM synthesis ──────────────────────────────────────────────────────────────

_SYNTHESIS_PROMPT = """\
You are a technology scout for an independent music artist and AI assistant developer.

Current stack (do NOT report anything already here):
{stack}

Search results from today:
{results}

Your job: identify NEW tools, APIs, platforms, or developments that could be useful for:
1. Music production (AI composition, mixing, mastering, vocal tools)
2. Independent artist business (distribution, royalties, contracts, billing)
3. AI assistant development (better LLMs, APIs, Telegram integrations, local models)
4. Content creation (video, social media, graphics automation)

For each finding, rate it:
- ready_now: available today, can integrate in days
- coming_soon: announced or in beta, available within 3-6 months
- watch_this_space: early stage, worth monitoring

Permanently rejected categories — do NOT propose anything in these buckets:
{rejected}

Rules:
- Return 4-6 findings maximum
- Skip anything already in the current stack
- Skip anything in the rejected categories above
- Only include things that are genuinely new or meaningfully improved
- If search results are empty or unhelpful, use your training knowledge but be honest
- Return a JSON array only, no markdown

Each object must have exactly these keys:
  name           — tool or platform name
  category       — one of: ai-music, ai-llm, developer-api, content-tools, business-tools
  summary        — one sentence description
  why_it_matters — one sentence on relevance to this artist/system
  status         — ready_now | coming_soon | watch_this_space
  url            — best URL or empty string if unknown

Return only the JSON array."""


def _synthesize(results: list[dict], live_search: bool) -> list[dict]:
    results_text = "\n".join(
        f"- {r['title']}: {r['body'][:150]} ({r['url']})"
        for r in results[:20]
    ) or "(no live results — use training knowledge)"

    prompt = _SYNTHESIS_PROMPT.format(
        stack=_STACK_FLAT,
        results=results_text,
        rejected=_REJECTED_CONTEXT,
    )
    findings = ollama_json(prompt, timeout=60)
    if not isinstance(findings, list):
        return []

    valid_statuses = {"ready_now", "coming_soon", "watch_this_space"}
    clean = []
    for f in findings:
        if not isinstance(f, dict):
            continue
        if f.get("status") not in valid_statuses:
            f["status"] = "watch_this_space"
        f.setdefault("url", "")
        clean.append(f)

    accepted, blocked = _filter_rejected(clean)
    if blocked:
        names = ", ".join(b.get("name", "?") for b in blocked)
        print(f"[scout] Rejected {len(blocked)} findings(s) via ledger: {names}")
    return accepted

# ── Storage ────────────────────────────────────────────────────────────────────

_MAX_STORED_RUNS = 5


def _load_scout_json() -> dict:
    if SCOUT_JSON.exists():
        try:
            return json.loads(SCOUT_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"runs": []}


def _save_scout_json(data: dict) -> None:
    SCOUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    SCOUT_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _append_run(findings: list[dict], live_search: bool) -> None:
    data = _load_scout_json()
    run = {
        "date":        datetime.now().strftime("%Y-%m-%d"),
        "live_search": live_search,
        "findings":    findings,
    }
    runs = data.get("runs", [])
    runs.append(run)
    data["runs"] = runs[-_MAX_STORED_RUNS:]
    _save_scout_json(data)


def _write_scout_log(runs: list[dict]) -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [
        "---",
        "type: scout-log",
        f"last_updated: {today}",
        "---\n",
        "# Scout Log\n",
        "_Managed by `chief_scout_brain.py` — last 5 digests kept._\n",
    ]

    status_labels = {
        "ready_now":         "Ready Now",
        "coming_soon":       "Coming Soon",
        "watch_this_space":  "Watch This Space",
    }

    for run in reversed(runs):
        search_note = "" if run.get("live_search") else " _(LLM-only, no live search)_"
        lines.append(f"## {run['date']} — AI & Music Tech Digest{search_note}\n")
        by_status: dict[str, list] = {"ready_now": [], "coming_soon": [], "watch_this_space": []}
        for f in run.get("findings", []):
            s = f.get("status", "watch_this_space")
            by_status.setdefault(s, []).append(f)
        for status, label in status_labels.items():
            items = by_status.get(status, [])
            if items:
                lines.append(f"### {label}\n")
                for f in items:
                    url_part = f"  _Source: {f['url']}_" if f.get("url") else ""
                    lines.append(f"- **{f['name']}** — {f['summary']}")
                    lines.append(f"  _Why it matters:_ {f['why_it_matters']}{url_part}")
                lines.append("")
        lines.append("---\n")

    SCOUT_LOG.write_text("\n".join(lines), encoding="utf-8")

# ── Telegram format ────────────────────────────────────────────────────────────

def _format_telegram(findings: list[dict], live_search: bool) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    search_note = "" if live_search else "\n_(LLM-only — no live search)_"

    by_status: dict[str, list] = {"ready_now": [], "coming_soon": [], "watch_this_space": []}
    for f in findings:
        by_status.setdefault(f.get("status", "watch_this_space"), []).append(f)

    labels = {"ready_now": "Ready Now", "coming_soon": "Coming Soon", "watch_this_space": "Watch This Space"}
    parts = [f"🔍 Scout Report — {today}{search_note}\n"]
    for status, label in labels.items():
        items = by_status.get(status, [])
        if items:
            parts.append(label)
            for f in items:
                parts.append(f"• {f['name']} — {f['summary']}")
            parts.append("")
    parts.append("Full log saved to vault Scout Log.")
    return "\n".join(parts)

# ── Public entry point ─────────────────────────────────────────────────────────

def handle(text: str = "") -> list[str]:
    """Run a scout report. Returns list of reply strings."""
    results, live_search = _gather_search_results()
    findings = _synthesize(results, live_search)

    if not findings:
        return ["Scout ran but found nothing to report. Try again shortly."]

    _append_run(findings, live_search)
    data = _load_scout_json()
    _write_scout_log(data.get("runs", []))

    return [_format_telegram(findings, live_search)]

# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Running scout...\n")
    for line in handle():
        print(line)
    print(f"\nScout log: {SCOUT_LOG}")
    print(f"Scout JSON: {SCOUT_JSON}")
