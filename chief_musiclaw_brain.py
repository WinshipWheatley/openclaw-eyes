"""
chief_musiclaw_brain.py

Music industry legal advisor. Knows industry fundamentals — contracts,
publishing rights, master vs composition, work-for-hire, co-writing splits.

Active case: Ten Fingers / Log Rhythm Records dispute.

Always flags when a real entertainment lawyer is needed.

Triggered by:
  - "music law" / "legal question" / "my rights"
  - "ten fingers" / "log rhythm" / "what are my options"
  - "add case note [text]"
Intent: musiclaw_query in chief_router.py

Saves to:
  - /mnt/c/OpenClawShared/business/musiclaw_log.json  (source of truth)
  - openclaw-vault/Business/Music Law Log.md           (Obsidian)
"""

import json
import re
from datetime import datetime
from pathlib import Path

from chief_llm import ollama_call

# ── Paths ──────────────────────────────────────────────────────────────────────

BUSINESS_DIR   = Path("/mnt/c/OpenClawShared/business")
MUSICLAW_JSON  = BUSINESS_DIR / "musiclaw_log.json"
MUSICLAW_MD    = Path("/mnt/c/OpenClawShared/openclaw-vault/Business/Music Law Log.md")

# ── Active case: Ten Fingers ───────────────────────────────────────────────────

TEN_FINGERS_CASE = """
ACTIVE CASE: Ten Fingers

Song: "Ten Fingers"
Current distributor: DistroKid
Released under: Log Rhythm Records
Controlling party on release: Renae Timmi Jenkins

Winship Wheatley IV's position:
- Was verbally told he was a co-owner of Log Rhythm Records
- His name appeared in an internal company document without his signature
- He is NOT listed on the Maryland business entity registry for Log Rhythm Records
- No signed co-ownership agreement exists
- No signed co-writing agreement exists for this song

Key questions:
1. Does verbal co-ownership claim hold any legal weight without registry listing?
2. What rights does Winship have to the song composition vs the master recording?
3. Can Renae Timmi Jenkins distribute and monetize "Ten Fingers" through Log Rhythm Records without Winship's consent?
4. What is the significance of his name appearing in an internal document?
5. What remedies are available?
"""

# ── Knowledge base (baked into system prompt) ─────────────────────────────────

MUSIC_LAW_KNOWLEDGE = """
MUSIC INDUSTRY LEGAL FUNDAMENTALS:

1. MASTER vs COMPOSITION RIGHTS
   - Master recording: the actual recorded audio file. Owned by whoever paid for the recording session, unless assigned.
   - Composition: the underlying song (melody + lyrics). Owned by the songwriter(s).
   - These are separate rights. You can own the composition but not the master, and vice versa.

2. CO-WRITING SPLITS
   - Default split when no agreement exists: equal shares among all co-writers (50/50 for two writers).
   - A co-writing agreement should be signed before or immediately after creating the song.
   - Without a signed agreement, disputes often rely on who can prove contribution.

3. WORK-FOR-HIRE
   - If a creator was paid as an employee or contractor under a work-for-hire agreement, the commissioning party owns the copyright.
   - Must be in writing and signed to be enforceable for most music works.

4. BUSINESS CO-OWNERSHIP
   - Being verbally told you are a co-owner of an LLC or company has NO legal standing without:
     a) Being listed on the state business registry (Maryland in this case), OR
     b) A signed operating agreement naming you as a member/owner.
   - Appearing in an internal document you did not sign does NOT create ownership.

5. DISTRIBUTION RIGHTS
   - DistroKid distributes on behalf of whoever controls the release. If Renae controls the Log Rhythm Records DistroKid account, she controls distribution and royalty collection for that release.
   - The party who uploads controls metadata, ISRC codes, and where royalties flow.

6. PUBLISHING RIGHTS
   - Publishing rights = the right to collect royalties from composition (sync, mechanical, performance).
   - PRO registration (ASCAP/BMI) determines who collects performance royalties.
   - If Winship co-wrote the song, he should register his share with his PRO regardless of the master dispute.

7. REMEDIES FOR MUSIC RIGHTS DISPUTES
   - Cease and desist letter (from an entertainment lawyer)
   - DMCA takedown (if copyright is registered and infringed)
   - Demand for accounting (if royalties are being withheld)
   - Negotiated settlement / buyout
   - Litigation (last resort — expensive)

8. WHEN TO GET A LAWYER — ALWAYS FOR:
   - Any active dispute over ownership or royalties
   - Reviewing or signing any contract
   - Sending any formal legal notice
   - Copyright registration issues
   - Anything involving money over ~$500
"""

# ── Storage ────────────────────────────────────────────────────────────────────

def _load_log() -> dict:
    if MUSICLAW_JSON.exists():
        try:
            return json.loads(MUSICLAW_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"case_notes": [], "queries": []}


def _save_log(data: dict) -> None:
    BUSINESS_DIR.mkdir(parents=True, exist_ok=True)
    MUSICLAW_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _append_query(question: str, answer: str) -> None:
    data = _load_log()
    data.setdefault("queries", []).append({
        "date":     datetime.now().strftime("%Y-%m-%d %H:%M"),
        "question": question[:200],
        "answer":   answer[:1000],
    })
    # Keep last 50 queries
    data["queries"] = data["queries"][-50:]
    _save_log(data)
    _write_musiclaw_md(data)


def _append_case_note(note: str) -> None:
    data = _load_log()
    data.setdefault("case_notes", []).append({
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "note": note,
    })
    _save_log(data)
    _write_musiclaw_md(data)


# ── LLM advisor ───────────────────────────────────────────────────────────────

_ADVICE_PROMPT = """\
You are a music industry legal advisor for Winship Wheatley IV (artist: Winship Live, label: Deep Pocket Records).

{knowledge}

{case}

Question from Winship: {question}

Rules:
- Answer clearly and specifically based on the knowledge above
- Always flag if this situation requires a real entertainment lawyer
- Never give specific legal advice — give information and options
- Keep your answer under 250 words
- End with a one-line "⚠️ Bottom line:" summary
- Plain text only, no markdown headers

Answer:"""

_OPTIONS_PROMPT = """\
You are a music industry legal advisor for Winship Wheatley IV.

{knowledge}

{case}

Summarize the options available to Winship regarding the Ten Fingers / Log Rhythm Records situation.
Focus on practical next steps he can take, from least to most aggressive.
Keep each option to 1-2 sentences. List 4-5 options maximum.
End with: "⚠️ Recommendation: Consult an entertainment lawyer before taking any action."
Plain text only, no markdown."""


def _ask_llm(question: str) -> str:
    prompt = _ADVICE_PROMPT.format(
        knowledge=MUSIC_LAW_KNOWLEDGE,
        case=TEN_FINGERS_CASE,
        question=question,
    )
    result = ollama_call(prompt, timeout=45).strip()
    if not result:
        return (
            "Unable to generate advice right now. "
            "For urgent music law questions, contact an entertainment attorney. "
            "musiclawyer.com and NOLO.com have useful general resources."
        )
    return result


def _options_summary() -> str:
    prompt = _OPTIONS_PROMPT.format(
        knowledge=MUSIC_LAW_KNOWLEDGE,
        case=TEN_FINGERS_CASE,
    )
    result = ollama_call(prompt, timeout=45).strip()
    if not result:
        return (
            "Options for Ten Fingers dispute:\n"
            "1. Register your composition share with ASCAP/BMI now.\n"
            "2. Document all evidence of co-ownership claim (texts, emails, the internal document).\n"
            "3. Send a cease and desist via an entertainment lawyer.\n"
            "4. Negotiate a settlement or formal split agreement.\n"
            "⚠️ Recommendation: Consult an entertainment lawyer before taking any action."
        )
    return result


# ── Markdown writer ────────────────────────────────────────────────────────────

def _write_musiclaw_md(data: dict | None = None) -> None:
    if data is None:
        data = _load_log()
    today = datetime.now().strftime("%Y-%m-%d")

    case_notes = data.get("case_notes", [])
    queries    = data.get("queries", [])

    note_rows = "\n".join(
        f"| {n['date']} | {n['note'][:120]} |"
        for n in reversed(case_notes[-20:])
    ) or "| — | (none yet) |"

    query_rows = "\n".join(
        f"| {q['date']} | {q['question'][:80]} |"
        for q in reversed(queries[-10:])
    ) or "| — | (none yet) |"

    content = (
        "---\n"
        "type: music-law-log\n"
        f"last_updated: {today}\n"
        "---\n\n"
        "# Music Law Log\n\n"
        "_Managed by `chief_musiclaw_brain.py` — do not edit manually._\n\n"
        "## Active Case: Ten Fingers / Log Rhythm Records\n\n"
        "| Field | Detail |\n|---|---|\n"
        "| Song | Ten Fingers |\n"
        "| Released under | Log Rhythm Records (DistroKid) |\n"
        "| Controlling party | Renae Timmi Jenkins |\n"
        "| Winship's claim | Verbal co-ownership of Log Rhythm Records |\n"
        "| Registry status | **NOT listed on Maryland business registry** |\n"
        "| Signed agreement | **None** |\n"
        "| Evidence | Name in internal document (unsigned) |\n\n"
        "## Case Notes\n\n"
        "| Date | Note |\n|---|---|\n"
        + note_rows + "\n\n"
        "## Recent Queries\n\n"
        "| Date | Question |\n|---|---|\n"
        + query_rows + "\n\n"
        "## Quick Reference\n\n"
        "- **Master vs Composition:** Separate rights — own one without the other\n"
        "- **Co-writing default:** 50/50 split with no agreement\n"
        "- **Verbal co-ownership:** No legal standing without registry or signed operating agreement\n"
        "- **PRO registration:** Register composition share at ASCAP/BMI regardless of dispute\n"
        "- **Always consult a lawyer** for active disputes, contracts, and formal notices\n"
    )
    MUSICLAW_MD.parent.mkdir(parents=True, exist_ok=True)
    MUSICLAW_MD.write_text(content, encoding="utf-8")


# ── Public entry point ─────────────────────────────────────────────────────────

def handle(text: str = "") -> list[str]:
    t = text.lower().strip()

    # ── Add case note ──────────────────────────────────────────────────────────
    if t.startswith("add case note") or t.startswith("case note:"):
        note = re.sub(r"^(add case note|case note:)\s*", "", text, flags=__import__("re").IGNORECASE).strip()
        if not note:
            return ["What's the case note? Try: 'add case note [details]'"]
        _append_case_note(note)
        return [f"Case note added: {note}"]

    # ── Options for Ten Fingers ────────────────────────────────────────────────
    if any(k in t for k in ("what are my options", "my options", "options for ten fingers", "what can i do")):
        answer = _options_summary()
        _append_query(text, answer)
        return [answer]

    # ── Ten Fingers / Log Rhythm specific ─────────────────────────────────────
    if any(k in t for k in ("ten fingers", "log rhythm", "log rhythm records", "renae")):
        answer = _ask_llm(text)
        _append_query(text, answer)
        return [answer]

    # ── General music law Q&A ──────────────────────────────────────────────────
    answer = _ask_llm(text)
    _append_query(text, answer)
    return [answer]


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "what are my options"
    print(f"Running music law brain: '{text}'\n")
    for line in handle(text):
        print(line)
    print(f"\nMusic Law MD: {MUSICLAW_MD}")
    print(f"Music Law JSON: {MUSICLAW_JSON}")
