"""
chief_brainstorm_brain.py

Captures raw brainstorm ideas and synthesizes them into structured entries.

Flow:
  1. "brainstorm [text]" — inline capture
  2. "brainstorm" alone — asks for idea, captures next message
  3. LLM synthesizes: title, summary, domain, complexity, timing, next step
  4. Calls chief_brainstorm_router.route() to assign destination
  5. Saves to JSON + vault

Triggered by:
  - "brainstorm" / "capture idea" / "new idea" / "idea:"
Intent: brainstorm_capture in chief_router.py

Saves to:
  - /mnt/c/OpenClawShared/album/brainstorm_log.json
  - openclaw-vault/System/Brainstorm Log.md
"""

import json
import re
from datetime import datetime
from pathlib import Path

from chief_llm import ollama_call, nemotron_call
from chief_session_manager import (
    set_workflow,
    set_workflow_state,
    get_workflow_state,
    reset_session,
)

BRAINSTORM_JSON = Path("/mnt/c/OpenClawShared/album/brainstorm_log.json")
BRAINSTORM_MD   = Path("/mnt/c/OpenClawShared/openclaw-vault/System/Brainstorm Log.md")

_SYNTHESIS_PROMPT = """\
You are analyzing a raw brainstorm idea for a music producer / business owner running \
an AI-assisted management system called OpenClaw.

Raw idea:
{raw_text}

Context: The system manages album production, Fundo (Afrobeats project), marketing, \
finance, communications, scheduling, website, and research.

Return ONLY a valid JSON object with these exact fields:
{{
  "title": "5-8 word title",
  "summary": "2-3 sentence summary of what this idea is and why it matters",
  "domain": "album|fundo|marketing|finance|infrastructure|scheduler|website|research|communications|other",
  "complexity": "low|medium|high",
  "estimated_time": "e.g. 30min, 2hrs, half day",
  "timing_class": "now|soon|later|watch|archive",
  "trigger_condition": "only if timing_class=watch — what must happen first, otherwise empty string",
  "dependencies": ["list of existing brains or systems this touches"],
  "recommended_next_step": "one specific actionable next step",
  "idea_type": "new_project|task_within_existing_project|unclear"
}}

Timing class guide:
  now     = do today, clearly unblocked
  soon    = do within a week, not urgent right now
  later   = do eventually, no urgency
  watch   = wait for a specific condition before acting
  archive = interesting but not currently actionable

Idea type guide:
  new_project                = standalone initiative with its own scope, identity, and outcome
                               (examples: website deployment, new bot, new integration)
  task_within_existing_project = specific improvement, fix, or feature inside an existing system
                               (examples: fix a bug in Chief, complete album data, patch approval gate)
  unclear                    = spans multiple systems, under-defined, or cannot be classified yet

Return only valid JSON, no markdown fences."""


# ── Storage ───────────────────────────────────────────────────────────────────

def _load_items() -> list[dict]:
    if BRAINSTORM_JSON.exists():
        try:
            return json.loads(BRAINSTORM_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_items(items: list[dict]) -> None:
    BRAINSTORM_JSON.parent.mkdir(parents=True, exist_ok=True)
    BRAINSTORM_JSON.write_text(json.dumps(items, indent=2), encoding="utf-8")


def _next_id(items: list[dict]) -> str:
    return f"BS-{len(items) + 1:04d}"


# ── Cloud routing privacy check ───────────────────────────────────────────────
#
# SECURITY-CRITICAL BOUNDARY.
# This function is the sole privacy gate for cloud routing of brainstorm synthesis.
# Loosening any pattern (removing a blocker, raising the length limit, adding an
# exception) is a privacy policy change and requires the same review as
# chief_approval_policy.py. Do not treat this as an ordinary code quality edit.
#
def _brainstorm_cloud_safe(raw_text: str) -> bool:
    """Return True only if raw brainstorm input contains no personal, financial,
    or credential-identifying content. Fails closed — ambiguous input routes local.
    """
    t = raw_text.lower()
    _blockers = [
        r"\$[\d,]+",                                          # dollar amounts
        r"\b\d{3,}\.?\d*\s*(dollars?|usd)\b",                # spelled-out amounts
        r"invoice|billing|payment\s+from|paid\s+by",
        r"\.chief\.env|api.?key|bot.?token|secret|credential|oauth",
        r"client\s+name|from\s+[A-Z][a-z]+\s+[A-Z][a-z]+",  # name patterns
        r"parish|church|school|studio\s+name",               # known client-class terms
        r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b.{0,30}(meeting|session|call|gig)",
        r"at\s+\d+\s*(am|pm)|scheduled\s+for",
    ]
    for pattern in _blockers:
        if re.search(pattern, t, re.IGNORECASE):
            return False
    if len(raw_text) > 500:
        return False
    return True


# ── LLM synthesis ─────────────────────────────────────────────────────────────

def _synthesize(raw_text: str) -> dict:
    prompt = _SYNTHESIS_PROMPT.format(raw_text=raw_text)

    # ── Cloud routing: privacy-gated ─────────────────────────────────────────
    # Route to Nemotron cloud only when _brainstorm_cloud_safe() confirms no
    # personal/financial/credential content in the input. Any failure (check
    # blocked, cloud error, empty response) falls back to local without raising.
    result = ""
    if _brainstorm_cloud_safe(raw_text):
        result = nemotron_call(prompt, timeout=30).strip()
        if result:
            print("[brainstorm] synthesis routed to Nemotron cloud", flush=True)
        else:
            print("[brainstorm] cloud call failed or returned empty, falling back to local", flush=True)
    else:
        print("[brainstorm] privacy check blocked cloud routing, using local", flush=True)

    if not result:
        # Local Ollama fallback — used when privacy check blocks cloud routing,
        # or when Nemotron call fails. Does NOT send blocked content to any cloud.
        # ollama_call() auto-escalates to 14b for synthesis-length prompts.
        result = ollama_call(prompt, timeout=60).strip()
    result = re.sub(r"^```[a-z]*\n?", "", result)
    result = re.sub(r"\n?```$", "", result.strip())
    try:
        data = json.loads(result)
        required = ("title", "summary", "domain", "complexity", "timing_class", "recommended_next_step", "idea_type")
        if all(k in data for k in required):
            return data
    except Exception:
        pass
    return {
        "title":                 raw_text[:60].strip(),
        "summary":               raw_text,
        "domain":                "other",
        "complexity":            "medium",
        "estimated_time":        "unknown",
        "timing_class":          "later",
        "trigger_condition":     "",
        "dependencies":          [],
        "recommended_next_step": "Review and classify manually",
        "idea_type":             "unclear",
    }


# ── Vault writer ──────────────────────────────────────────────────────────────

def _write_vault_md(items: list[dict]) -> None:
    BRAINSTORM_MD.parent.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "---",
        "type: brainstorm-log",
        f"last_updated: {today}",
        "---",
        "",
        "# Brainstorm Log",
        "",
        "_Managed by `chief_brainstorm_brain.py`. Say 'brainstorm' to capture a new idea._",
        "",
        f"**Total:** {len(items)}",
        "",
    ]
    by_timing: dict[str, list[dict]] = {}
    for item in items:
        by_timing.setdefault(item.get("timing_class", "later"), []).append(item)

    for tc in ("now", "soon", "later", "watch", "archive"):
        group = by_timing.get(tc, [])
        if not group:
            continue
        lines += [f"## {tc.capitalize()}", ""]
        for item in group:
            lines += [
                f"### {item['idea_id']}: {item.get('title', '—')}",
                f"**Status:** {item.get('status', 'new')} | "
                f"**Domain:** {item.get('domain', '—')} | "
                f"**Complexity:** {item.get('complexity', '—')} | "
                f"**Est:** {item.get('estimated_time', '—')}",
                "",
                item.get("summary", ""),
                "",
            ]
            if item.get("trigger_condition"):
                lines += [f"**Trigger:** {item['trigger_condition']}", ""]
            lines += [f"**Next step:** {item.get('recommended_next_step', '—')}", ""]

    BRAINSTORM_MD.write_text("\n".join(lines), encoding="utf-8")


# ── Core capture ──────────────────────────────────────────────────────────────

def capture_and_synthesize(raw_text: str) -> list[str]:
    """Capture, synthesize, route, save. Returns Telegram reply."""
    items    = _load_items()
    idea_id  = _next_id(items)
    synthesis = _synthesize(raw_text)

    item = {
        "idea_id":               idea_id,
        "title":                 synthesis.get("title", raw_text[:60]),
        "raw_capture":           raw_text,
        "summary":               synthesis.get("summary", ""),
        "source":                "telegram",
        "timestamp":             datetime.now().strftime("%Y-%m-%d %H:%M"),
        "domain":                synthesis.get("domain", "other"),
        "status":                "new",
        "timing_class":          synthesis.get("timing_class", "later"),
        "trigger_condition":     synthesis.get("trigger_condition", ""),
        "dependencies":          synthesis.get("dependencies", []),
        "complexity":            synthesis.get("complexity", "medium"),
        "estimated_time":        synthesis.get("estimated_time", "unknown"),
        "recommended_next_step": synthesis.get("recommended_next_step", ""),
        "route_target":          "",
        "notes":                 [],
    }

    try:
        from chief_brainstorm_router import route
        item = route(item)
    except Exception:
        pass

    items.append(item)
    _save_items(items)
    _write_vault_md(items)

    tc         = item["timing_class"]
    route_line = f"\n→ Routed to: {item['route_target']}" if item.get("route_target") else ""
    cond_line  = f" — _{item['trigger_condition']}_" if item.get("trigger_condition") else ""

    # ── Focus shield: hold non-urgent items during active work blocks ──────────
    try:
        from chief_focus_shield import classify_timing, is_focus_active, hold_item, should_surface
        shield_timing = classify_timing(tc)
        if not should_surface(item):
            hold_item(item, shield_timing)
            return [
                f"💡 *{idea_id}: {item['title']}* — captured.\n"
                f"Held until: *{shield_timing}* (focus block active)\n"
                f"Say 'focus held' to see queue."
            ]
    except Exception:
        pass

    return [
        f"💡 *{idea_id}: {item['title']}*\n\n"
        f"{item['summary']}\n\n"
        f"Domain: {item['domain']} | Complexity: {item['complexity']} | Est: {item['estimated_time']}\n"
        f"Timing: *{tc}*{cond_line}\n"
        f"Next step: {item['recommended_next_step']}"
        f"{route_line}"
    ]


# ── Public entry point ────────────────────────────────────────────────────────

def handle(text: str = "") -> list[str]:
    state = get_workflow_state()

    # Second turn: waiting for idea text
    if state and state.get("active") and state.get("phase") == "brainstorm_capture":
        reset_session()
        t = text.strip()
        if not t or len(t) < 3:
            return ["No idea captured. Say 'brainstorm [your idea]' to try again."]
        return capture_and_synthesize(t)

    # Inline: "brainstorm [text]"
    inline = re.sub(
        r"^\s*(brainstorm|capture\s+idea|new\s+idea|idea:)\s*",
        "", text, flags=re.IGNORECASE,
    ).strip()
    if inline and len(inline) > 3:
        return capture_and_synthesize(inline)

    # No inline text — ask for it
    set_workflow("brainstorm", None)
    set_workflow_state({"active": True, "phase": "brainstorm_capture"})
    return ["What's the idea? Dump it in any form — messy is fine."]


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "brainstorm"
    for line in handle(text):
        print(line)
