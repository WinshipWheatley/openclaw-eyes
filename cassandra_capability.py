"""
cassandra_capability.py

Code-level capability gates for Cassandra. Two-stage enforcement:

  Stage 1 — Pre-generation (capability_context)
    Injects a ground-truth capability state block into every prompt immediately
    before the user query. The model sees explicit facts, not rule instructions.

  Stage 2 — Post-generation (gate_reply)
    Scans the LLM reply for forbidden capability claims.
    Gate priority is strict: first matching gate wins.
    - Calendar, payment, file, email: full replacement (the violation IS the premise)
    - Future-action: sentence-level correction when violation is incidental in a
      multi-sentence reply; full replacement only for single-sentence replies.

Capability flags
----------------
All False until a real integration is wired in.
Set to True ONLY when the actual integration exists and is tested.

Restart note
------------
Changes to this module only take effect after a process restart.
cassandra_listener.py, cassandra_watcher.py, and cassandra_briefing_scheduler.py
all import this at startup — running processes cache the old version.
"""

import random
import re

# ── Capability flags ──────────────────────────────────────────────────────────

CALENDAR_CONNECTED         = True   # google.calendar.read via google_access_broker.py
PAYMENT_EXTERNAL_CONNECTED = False  # no live bank or payment processor connection
PAYMENT_METADATA_CONNECTED = True   # Gmail payment metadata + income-log check
FILE_VERIFY_CONNECTED      = True   # tools/file_verify.py wired via cassandra_brain._handle_file_verification_request
EMAIL_DRAFT_CONNECTED      = True   # google.gmail.draft.create via google_access_broker.py (Class B / Tier 1)
EMAIL_SEND_CONNECTED       = False  # no direct/autonomous send; brokered send is Class C / Tier 2 if requested
INVOICE_PDF_CONNECTED = True  # reportlab PDF invoice generation via Cassandra
FUTURE_ACTION_CONNECTED    = True   # dispatch via cassandra_watcher.py, enqueue via cassandra_brain.py
FINANCIAL_LOG_CONNECTED    = True   # expense_log.json write via chief_cpa_brain.log_entry / log_expense_from_text
GMAIL_METADATA_CONNECTED   = True   # google.gmail.read.metadata via google_access_broker.py
CONTACTS_CONNECTED         = True   # google.contacts.read via google_access_broker.py
PII_VAULT_CONNECTED        = True   # activated 2026-04-03 — vault key in .chief.env, vault file at .pii_vault.enc
VOICE_NOTE_CONNECTED       = True   # Telegram voice note sending via cassandra_sender.send_voice_note

# ── Source state labels ───────────────────────────────────────────────────────

SOURCE_INFERRED    = "inferred from notes"
SOURCE_LOGGED      = "found in log"
SOURCE_DRAFTED     = "drafted, not sent"
SOURCE_VERIFIED    = "externally verified"
SOURCE_UNAVAILABLE = "not connected"

# ── Forbidden patterns ────────────────────────────────────────────────────────
# Matched on lowercased reply text.
# Principle: cover both direct and soft paraphrase forms;
# do NOT add patterns that also fire on correct honest phrasings.

_CAL_PATTERNS = [
    # Direct assertion / display
    r"opening (the |your |a )?calendar( app)?",
    r"(launch|open|starting) (the |your )?calendar",
    r"\bcalendar app\b",
    r"(your|the) calendar shows",
    r"according to (your|the) calendar",
    r"(your |the )?schedule shows",
    r"(is |are )(on your calendar|in your calendar|on your schedule)",
    r"calendar (entry|event|appointment|item|slot)",
    # Past/present inspection
    r"(check(ed|ing)|pull(ed|ing) up|look(ed|ing) at) (your )?calendar",
    r"i see (you have|a booking|an? (appointment|event|booking|meeting|slot))",
    r"you have .{0,60} (on your calendar|scheduled today|booked today|coming up)",
    # Soft future inspection — "let me" and "I'll" forms
    # (take a (quick )?|...) handles "take a quick look" specifically
    r"let me (take a (quick )?|have a (quick )?|quick )?(look|check|peek|pull) (at )?(your )?calendar",
    r"let me (grab|get|pull up) (your )?calendar",
    r"i('ll| will) (take a (quick )?|have a (quick )?|quick )?(look|check|peek) (at )?(your )?calendar",
    r"i('ll| will) (check|open|pull up|look at|get|grab) (your )?calendar",
    r"i('ll| will) (have a |take a )(quick )?look at (your )?calendar",
    r"i('ll| will) get back to you with calendar",
    r"i('ll| will) (pull|check) (that |your )?schedule",
    # Inferred scheduling claims
    r"(you('ve| have)|looks like you('ve| have)) (a |an )?(meeting|appointment|call|booking|event) (at|on|tomorrow|today|this)",
]

_PAY_PATTERNS = [
    # Hard clearance / arrival claims
    r"hasn'?t (cleared|come through|processed|posted|landed|arrived)",
    r"has not (cleared|come through|processed|posted|landed|arrived)",
    r"(deposit|payment) (hasn'?t|has not)",
    r"(not (yet |)(cleared|processed|posted|landed|arrived|received))",
    # Pending / outstanding / overdue
    r"(deposit|payment|invoice|transfer) (is |)(still |)(pending|overdue|outstanding|uncleared)",
    r"(still |)(pending|overdue|outstanding) (deposit|payment|invoice|transfer)",
    r"payment (is |)(not received|not cleared|not processed|not arrived)",
    # "not received / not arrived" family
    r"(deposit|payment|invoice|transfer) (still |)(not |never )(received|arrived|come in|shown up|come through)",
    r"no (deposit|payment) (yet|received|has arrived|has come)",
    r"(payment|deposit) (has |)(not |never )(arrived|come in|shown up|come through|been received)",
    r"still (waiting|no sign) (on|for|of) (the )?(deposit|payment|funds|transfer)",
    r"(funds|money|transfer) (still |)(not |hasn'?t |has not )(arrived|cleared|come through|landed)",
]

_FILE_PATTERNS = [
    r"(the |that )?file (does(n'?t| not) exist|doesn'?t exist)",
    r"\bno such file\b",
    r"\bfile not found\b",
    r"(the |that )?path (does(n'?t| not) exist|doesn'?t exist)",
    r"\b(file|path) is (not there|missing|not present)\b",
    r"(checked?|verified?|confirmed?) (the |that )?(file|path|document)\b",
    r"(the|that) (file|path|document) (exists?|is (there|present|found))\b",
]

_EMAIL_PATTERNS = [
    r"i('ll| will| can) send (that|it|the email|the message|this)",
    r"(email|message) (sent|has been sent|was sent|going out)",
    r"sending (that|it|the email|the message|now|out)",
    r"i('ll| will)? fire that off",
    r"i (sent|have sent|just sent) (the|it|that|them|this)",
    r"sent (it|that|the email|this) (for you|out|off)",
    r"i('ll| will) (fire|shoot|blast) (that|it) (off|out)",
]

# Future-action patterns: only clearly-external autonomous execution promises.
# Vague catch-alls ("I'll handle that", "I'll take care of it") are intentionally
# excluded — Cassandra legitimately handles drafting, logging, and surfacing.
_FUTURE_ACTION_PATTERNS = [
    # Autonomous future checking at a specific time (implies external polling)
    r"i('ll| will) (check|look) (again|one more time|back|on that|on this) (tomorrow|later|this week|next|in the morning|tonight)",
    r"i('ll| will) check (back|again|on that|on this) (and |)(let you know|update you|report back|confirm)",
    # Sending reminder / message promises (email gate handles generic send; this catches scheduling)
    r"i('ll| will) send (a |the )?(final |follow.?up |another |scheduled )?(reminder|alert)",
    r"i('ll| will) remind (you|them) (tomorrow|later|next|on|about)",
    r"i('ll| will) keep an eye on (that|this|it) and (remind|alert|ping|let you know)",
    # External follow-up / outreach (unambiguously implies reaching out to someone)
    r"i('ll| will) follow.?up (from here|directly|with them|on that) (and |)(send|let|ping|contact)",
    r"i('ll| will) follow.?up from here",
    r"i('ll| will) reach out (to|and)",
    r"i('ll| will) (contact|ping|message|email) (them|him|her|the team|the client)",
]

# ── Honest-prefix guard ───────────────────────────────────────────────────────
# These words in the 40-char prefix of a regex match indicate the reply is
# already a correct disclaimer, not a false claim — skip that match.
# IMPORTANT: do NOT include "isn't connected" / "not connected" here.
# Those words can appear early in a sentence that still makes a false claim
# in its second clause ("Calendar isn't connected, but I'll check your schedule").
_HONEST_PREFIXES = (
    "whether ", "can't confirm", "cannot confirm",
    "can't verify", "cannot verify", "not able to", "unable to",
    "don't know if", "do not know if", "can't check", "cannot check",
    "can't do", "cannot do", "can't follow", "cannot follow",
    "can't autonomously", "cannot autonomously",
)

# ── Gate responses ─────────────────────────────────────────────────────────────
# Each gate has a small set of stylistic variants. random.choice() picks one per
# invocation — same truth / same limits, different surface phrasing.
# Inline variants: used when correcting an incidental promise in a longer reply.

_CAL_RESPONSES = (
    "Calendar isn't connected from here — I can't see what's on your schedule. "
    "The notes and Ops log are what I have. "
    "Anything time-sensitive needs a direct check.",

    "No live calendar access from here. "
    "I can work from what's been logged in Ops. "
    "Anything against your actual schedule needs a direct look.",

    "I don't have calendar access — only what's in the notes. "
    "If it's in the log, that's a record of what was written, not a confirmed slot. "
    "Worth a direct check before you commit.",
)

_PAY_RESPONSES = (
    "Payment status isn't something I can check externally. "
    "The Payment Follow-ups log has what was recorded. "
    "The account is the only way to confirm clearance.",

    "I can't verify deposit or payment status — no external access. "
    "What I have is the log entry. "
    "The account is the source of truth.",

    "External payment data isn't accessible from here. "
    "The follow-ups log shows what was recorded — that's what I can surface. "
    "Clearance status needs a direct account check.",
)

_FILE_RESPONSES = (
    "I can't verify file or path existence from here. "
    "That's a direct check on your end.",

    "Path existence isn't something I can confirm from here. "
    "Direct check only.",

    "I can't verify that path from here. "
    "Direct check on your end.",
)

_EMAIL_RESPONSES = (
    "I can create a Gmail draft for review — direct sending isn't set up on my end. "
    "You review and send it from the configured Gmail review inbox.",

    "Draft, yes. Direct send, no — I can prepare the Gmail draft and you review it before dispatch.",

    "Writing is on my side. Direct sending isn't. "
    "I'll draft it in Gmail for your review.",
)

_FUTURE_ACTION_RESPONSES = (
    "I can't check back or send on my own — not from here. "
    "I can draft the message, log it to Ops Actions, or hold it for your next check-in. "
    "What works?",

    "Checking back and sending aren't in my reach from here. "
    "I can write the draft, log a note, or hold it for the next check-in. "
    "What's useful?",

    "Autonomous checking and outreach aren't in my toolkit. "
    "I can draft it, add a note to Ops Actions, or hold it for your next check-in. "
    "Just say which.",
)

# Shape patterns — ONLY used when user intent is clearly future_action.
# Catch honest-but-generic refusals ("I'm not able to...") that slip past the standard
# patterns and need to be replaced with the Cassandra-style bounded response.
# The honest-prefix guard is intentionally NOT applied here: for future_action intent,
# a generic honest refusal is still the wrong response — it needs to be shaped.
_FUTURE_ACTION_SHAPE_PATTERNS = [
    r"(i'?m not able|i am not able) to (check|follow.?up|send|remind|schedule|reach out|do that autonomously|autonomously)",
    r"(i can'?t|i cannot) (schedule|set up|send a reminder|follow.?up|reach out|check back|remind you|do that) (for you|automatically|autonomously|on my own|from here)",
    r"(don'?t|do not) have (the |)(ability|access|way|integration|mechanism) to (autonomously |automatically )?(check|follow|send|remind|schedule) (that|this|back|up|you)",
    r"(not (able|set up|wired|connected|built|designed) to) (autonomously |automatically )?(check|follow|remind|send|reach|schedule)",
    r"(can'?t|cannot) (automatically|autonomously) (check|follow|remind|send|monitor|track|schedule)",
    r"(no (way|mechanism|integration|ability|direct way) (to |)(autonomously|automatically) (check|follow|remind|send))",
]

# Shorter inline variants — used when correcting a trailing promise
# in an otherwise valid multi-sentence reply.
_FUTURE_ACTION_INLINES = (
    "I can't follow through on that from here — "
    "but I can draft a note or hold it for your next check-in.",

    "I can't do that autonomously — "
    "but I can draft it or log it.",

    "Autonomous follow-through isn't in my toolkit — "
    "I can draft it or log it.",
)


# ── Query intent detection for gate selection ─────────────────────────────────
# Used to route the correct gate for the user's actual request type.
# future_action is tested before calendar to avoid mis-routing "check again tomorrow."

_CALENDAR_INTENT_WORDS = (
    "calendar", "schedule", "scheduled", "appointment", "meeting",
    "tomorrow morning", "tomorrow afternoon", "my schedule",
    "what's on", "what do i have", "what's tomorrow",
)

_FILE_INTENT_WORDS = (
    "file", "path", "folder", "directory", "exist", "exists",
    "/home", "/mnt", ".py", ".md", ".json", ".sh",
)

_PAYMENT_INTENT_WORDS = (
    "deposit", "payment", "invoice", "paid", "cleared", "transfer",
    "funds", "check if it cleared", "came in", "come through",
)

_FUTURE_ACTION_INTENT_WORDS = (
    "remind me", "reminder", "check again", "check back", "check tomorrow",
    "follow up", "follow-up", "check later", "send a reminder",
    "send a final reminder", "check next", "revisit", "check on it",
)


def _detect_query_intent(query: str) -> str | None:
    """
    Detect the primary domain intent of the user's query.
    Returns: 'calendar' | 'file' | 'payment' | 'future_action' | None.
    future_action is tested first — "check again tomorrow" is not a calendar question.
    """
    t = query.lower()
    if any(w in t for w in _FUTURE_ACTION_INTENT_WORDS):
        return "future_action"
    if any(w in t for w in _CALENDAR_INTENT_WORDS):
        return "calendar"
    if any(w in t for w in _FILE_INTENT_WORDS):
        return "file"
    if any(w in t for w in _PAYMENT_INTENT_WORDS):
        return "payment"
    return None


# ── Stage 1: prompt injection ─────────────────────────────────────────────────

def capability_context() -> str:
    """
    Ground-truth capability state block injected immediately before the User: line.
    Format: state on the line, behavioral rule as a complete sentence after a period.
    This makes rules legible as instructions for smaller models, not as metadata.
    """
    def cap_line(label: str, connected: bool, off_rule: str) -> str:
        if connected:
            return f"{label}: CONNECTED"
        return f"{label}: NOT CONNECTED. {off_rule}"

    lines = [
        "[CAPABILITY STATE — follow these rules exactly]",
        cap_line("calendar_access",   CALENDAR_CONNECTED,
                 "Never say 'your calendar shows' or imply a schedule was checked. Use log data only."),
        cap_line("payment_external",  PAYMENT_EXTERNAL_CONNECTED,
                 "Never state deposit or payment clearance as an external bank fact."),
        cap_line("payment_metadata",  PAYMENT_METADATA_CONNECTED,
                 "You can check recent Gmail notifications for payment receipts, but you cannot check bank clearance."),
        cap_line("file_verification", FILE_VERIFY_CONNECTED,
                 "Never confirm or deny that a file or path exists."),
        cap_line("email_draft",       EMAIL_DRAFT_CONNECTED,
                 "Email draft creation is not connected.")
        + " Brokered Gmail Draft object creation requires Tier 1 approval.",
        cap_line("email_send",        EMAIL_SEND_CONNECTED,
                 "Gmail send is not direct or autonomous. If requested, send is only brokered Class C / Tier 2."),
        cap_line("future_exec",       FUTURE_ACTION_CONNECTED,
                 "You cannot check, send, or follow up autonomously. You can draft, log, or surface."),
        cap_line("financial_log",     FINANCIAL_LOG_CONNECTED,
                 "You cannot log financial events. Direct Winship to Chief for expense and income logging."),
        cap_line("gmail_metadata",    GMAIL_METADATA_CONNECTED,
                 "gmail metadata not connected — cannot check inbox"),
        cap_line("contacts_read",     CONTACTS_CONNECTED,
                 "contacts not connected — cannot look up phone numbers or emails"),
        cap_line("pii_vault",         PII_VAULT_CONNECTED,
                 "PII vault not connected. Never state, infer, or repeat SSN, tax info, or personal financial data."),
        cap_line("invoice_pdf",       INVOICE_PDF_CONNECTED,
                 "invoice_pdf not connected — cannot generate PDF invoices."),
    ]
    return "\n".join(lines)


# ── Stage 2: post-generation gate ─────────────────────────────────────────────

def _has_assertion(text: str, patterns: list[str]) -> bool:
    """
    Return True if any pattern matches AND the match is not preceded by
    an honest-disclaimer word within the prior 40 characters.
    """
    for p in patterns:
        m = re.search(p, text)
        if not m:
            continue
        prefix = text[max(0, m.start() - 40): m.start()]
        if any(hint in prefix for hint in _HONEST_PREFIXES):
            continue
        return True
    return False


def _sentence_correct(reply: str, patterns: list[str], inline: str) -> str | None:
    """
    Try sentence-level correction: replace only violating sentence(s) with inline.
    Returns corrected reply string if successful, None if reply is a single sentence
    (caller should fall back to full replacement in that case).
    """
    parts = re.split(r"(?<=[.!?…])\s+", reply.strip())
    if len(parts) <= 1:
        return None

    corrected = []
    any_violation = False
    for sent in parts:
        if _has_assertion(sent.lower(), patterns):
            corrected.append(inline)
            any_violation = True
        else:
            corrected.append(sent)

    if not any_violation:
        return None
    return " ".join(corrected)


# Full-replacement gates in priority order.
# First match wins — later gates do not run once one fires.
# This prevents a file-check reply from also tripping the future_action gate.
_FULL_GATES = [
    ("calendar", lambda: CALENDAR_CONNECTED,         _CAL_PATTERNS,  _CAL_RESPONSES),
    ("payment",  lambda: PAYMENT_METADATA_CONNECTED, _PAY_PATTERNS,  _PAY_RESPONSES),
    ("file",     lambda: FILE_VERIFY_CONNECTED,      _FILE_PATTERNS, _FILE_RESPONSES),
    ("email",    lambda: EMAIL_SEND_CONNECTED,        _EMAIL_PATTERNS, _EMAIL_RESPONSES),
]


def gate_reply(reply: str, user_query: str = "",
               has_registry_context: bool = False) -> str:
    """
    Post-generation capability gate. Returns the original reply if clean.

    When user_query is provided, intent is detected from the query so that
    the correct gate fires for the user's actual request type — not just
    whichever pattern happens to match first in the LLM output.

    has_registry_context=True signals that a [REGISTRY LOOKUP] block was
    injected into this prompt. In that case the LLM is answering about
    another actor's capability, NOT making a self-capability claim, so all
    core domain gates (file/calendar/payment/email) are bypassed. The
    future_action gate still runs — Cassandra may still promise autonomous
    action even inside a cross-agent answer.

    Intent-aware rules (when has_registry_context=False):
      - future_action intent  → future_action gate runs first; core gates skipped
      - calendar/file/payment → only the matching core gate runs; other core gates
                                 are skipped to prevent cross-domain misfires
      - no detected intent    → original priority order (calendar→payment→file→email)

    Future-action (sentence-level or full) is always checked after the primary
    intent gate, since an otherwise correct reply may end with an action promise.
    Each gate selects randomly from its response variants.
    """
    t = reply.lower()
    intent = _detect_query_intent(user_query) if user_query else None

    def _check_future_action() -> str | None:
        """Returns corrected reply string if future_action gate fires, else None."""
        if not FUTURE_ACTION_CONNECTED and _has_assertion(t, _FUTURE_ACTION_PATTERNS):
            corrected = _sentence_correct(reply, _FUTURE_ACTION_PATTERNS,
                                          random.choice(_FUTURE_ACTION_INLINES))
            if corrected is not None:
                print("[capability_gate] blocked: future_action (inline)", flush=True)
                return corrected
            print("[capability_gate] blocked: future_action (full)", flush=True)
            return random.choice(_FUTURE_ACTION_RESPONSES)
        return None

    # Cross-agent / registry-grounded answer: skip all core domain gates.
    # The LLM is answering about another actor's capability from registry facts,
    # not making a self-capability claim — running the file/calendar/payment gates
    # here would replace a correct cross-agent answer with the wrong canned response.
    # Future-action gate still runs: Cassandra might still promise autonomous action.
    if has_registry_context:
        fa = _check_future_action()
        if fa:
            return fa
        return reply

    # future_action intent: check future_action gate first, skip unrelated core gates
    if intent == "future_action":
        fa = _check_future_action()
        if fa:
            return fa
        # Also catch honest-but-generic refusals that need Cassandra-style shaping.
        # Bypasses the honest-prefix guard intentionally — for future_action intent,
        # a generic "I'm not able to" response is still the wrong shape.
        if not FUTURE_ACTION_CONNECTED and any(re.search(p, t) for p in _FUTURE_ACTION_SHAPE_PATTERNS):
            print("[capability_gate] blocked: future_action/shape", flush=True)
            parts = re.split(r"(?<=[.!?…])\s+", reply.strip())
            if len(parts) > 1:
                corrected = [
                    random.choice(_FUTURE_ACTION_INLINES)
                    if any(re.search(p, s.lower()) for p in _FUTURE_ACTION_SHAPE_PATTERNS)
                    else s
                    for s in parts
                ]
                return " ".join(corrected)
            return random.choice(_FUTURE_ACTION_RESPONSES)
        return reply

    # Calendar / file / payment intent: run only the matching core gate
    _INTENT_GATE_MAP = {"calendar": "calendar", "file": "file", "payment": "payment"}
    if intent in _INTENT_GATE_MAP:
        target = _INTENT_GATE_MAP[intent]
        for cap_name, connected_fn, patterns, responses in _FULL_GATES:
            if cap_name == target:
                if not connected_fn() and _has_assertion(t, patterns):
                    print(f"[capability_gate] blocked: {cap_name}/intent", flush=True)
                    return random.choice(responses)
                break  # primary gate checked — don't run other core gates
        fa = _check_future_action()
        if fa:
            return fa
        return reply

    # No detected intent — original priority order: calendar→payment→file→email
    for cap_name, connected_fn, patterns, responses in _FULL_GATES:
        if not connected_fn() and _has_assertion(t, patterns):
            print(f"[capability_gate] blocked: {cap_name}", flush=True)
            return random.choice(responses)

    fa = _check_future_action()
    if fa:
        return fa

    return reply
