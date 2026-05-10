"""
capability_registry.py

Shared machine-readable capability registry for the OpenClaw stack.

Records what each actor/service can and cannot do, whether each capability
is connected and tested, and what scope it carries.

Used by Cassandra (and future bots) to answer cross-agent capability
questions truthfully — without guessing, implying, or over-promising.

Extension guide
---------------
Add a new capability  : append a Capability entry to the actor's list.
Add a new actor       : add a new Actor entry to REGISTRY.
Mark as connected     : set connected=True ONLY when the integration is
                        actually wired and tested end-to-end.
Add a domain keyword  : add to _DOMAIN_KEYWORDS so queries route to it.
"""

from dataclasses import dataclass, field
from typing import Optional
import re

# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class Capability:
    name: str           # machine key,  e.g. "calendar_read"
    domain: str         # broad bucket, e.g. "calendar", "file", "payment"
    description: str    # one-line human label
    connected: bool     # True = wired and tested; False = not connected
    scope: list         # e.g. ["read"], ["read", "write"], ["execute"]
    caveats: str = ""   # why not connected, or partial-support notes


@dataclass
class Actor:
    name: str           # machine key,  e.g. "cassandra"
    role: str           # e.g. "executive_assistant"
    description: str    # one-sentence summary
    capabilities: list  = field(default_factory=list)
    notes: str = ""     # actor-level caveats


# ── Registry ──────────────────────────────────────────────────────────────────

REGISTRY: dict = {

    "cassandra": Actor(
        name="cassandra",
        role="executive_assistant",
        description=(
            "Personal executive assistant for OpenClaw Studios. "
            "Owns orientation, priorities, context, relational continuity, and well-being nudges. "
            "Defers to Chief for routing, approvals, album workflows, billing, and execution."
        ),
        capabilities=[
            Capability(
                "ops_log_write", "logging",
                "Log items to Ops Actions vault file",
                connected=True, scope=["read", "write"],
            ),
            Capability(
                "ops_payment_read", "payment_log",
                "Read the Payment Follow-ups log",
                connected=True, scope=["read"],
                caveats="Log read only — cannot verify external payment status",
            ),
            Capability(
                "ops_notes_read", "notes",
                "Read Ops Notes vault file",
                connected=True, scope=["read"],
            ),
            Capability(
                "calendar_read", "calendar",
                "Read live calendar events from Google Calendar",
                connected=True, scope=["read"],
                caveats="Read-only via google_access_broker.py — next 7 days, metadata and event titles only",
            ),
            Capability(
                "payment_verify", "payment",
                "Verify external deposit or payment clearance status",
                connected=True, scope=["read"],
                caveats=(
                    "Grounded against recent Gmail payment notifications and income logs only; "
                    "not a direct bank, Stripe, or payment processor connection"
                ),
            ),
            Capability(
                "file_verify", "file",
                "Verify file or path existence on the filesystem",
                connected=True, scope=["read"],
                caveats="Bounded file/path existence checks only — not file content review",
            ),
            Capability(
                "email_draft", "email",
                "Draft email text",
                connected=True, scope=["write"],
                caveats=(
                    "Brokered Gmail Draft object creation is Class B / Tier 1; "
                    "drafts are prepared for review in the configured review inbox "
                    "and CC that mailbox"
                ),
            ),
            Capability(
                "gmail_metadata", "email",
                "Read Gmail inbox metadata (sender, subject, date)",
                connected=True, scope=["read"],
                caveats="Metadata only via google_access_broker.py — no body content access",
            ),
            Capability(
                "contacts_read", "contacts",
                "Read Google Contacts",
                connected=True, scope=["read"],
            ),
            Capability(
                "email_send", "email_send",
                "Send email via SMTP or API",
                connected=False, scope=[],
                caveats=(
                    "No direct or autonomous send; Gmail send is only brokered "
                    "Class C / Tier 2 if requested after draft review"
                ),
            ),
            Capability(
                "future_exec", "automation",
                "Autonomously check, send, or follow up at a scheduled future time",
                connected=False, scope=[],
                caveats="No cron, scheduler, or autonomous execution wired in",
            ),
            Capability(
                "tts_voice", "voice",
                "Speak replies aloud via TTS (Kokoro / Piper)",
                connected=True, scope=["execute"],
            ),
            Capability(
                "briefing_recall", "briefing",
                "Recall logged morning, afternoon, and evening briefings",
                connected=True, scope=["read"],
            ),
        ],
    ),

    "chief": Actor(
        name="chief",
        role="operations_router",
        description=(
            "Operations router and workflow engine for OpenClaw Studios. "
            "Owns message routing, album sessions, billing workflows, "
            "approval gating, and all execution-heavy system work."
        ),
        capabilities=[
            Capability(
                "ops_intake", "routing",
                "Route and handle operational requests via Telegram",
                connected=True, scope=["read", "execute"],
            ),
            Capability(
                "album_workflow", "album",
                "Manage album session intake and tracking workflows",
                connected=True, scope=["read", "write", "execute"],
            ),
            Capability(
                "billing_workflow", "billing",
                "Handle billing, invoice, and payment intake workflows",
                connected=True, scope=["read", "write", "execute"],
            ),
            Capability(
                "approval_gate", "approval",
                "Gate irreversible actions (file delete, force push, etc.)",
                connected=True, scope=["read", "execute"],
            ),
            Capability(
                "vault_sync", "obsidian",
                "Sync notes and logs to the Obsidian vault",
                connected=True, scope=["read", "write"],
            ),
            Capability(
                "llm_routing", "llm",
                "Route queries to local Ollama models (7b / 14b)",
                connected=True, scope=["execute"],
            ),
            Capability(
                "calendar_read", "calendar",
                "Read live calendar events from Google Calendar",
                connected=False, scope=[],
                caveats="OAuth credentials not yet set up (gcal_credentials.json missing)",
            ),
            Capability(
                "file_verify", "file",
                "Verify file or path existence on the filesystem",
                connected=False, scope=[],
                caveats=(
                    "MCP filesystem server is available as a tool but is not wired "
                    "into Chief's response routing"
                ),
            ),
            Capability(
                "email_send", "email_send",
                "Send email via SMTP or API",
                connected=False, scope=[],
                caveats="No email send integration wired in",
            ),
            Capability(
                "payment_verify", "payment",
                "Verify payment receipts via Gmail metadata and income logs",
                connected=True, scope=["read"],
                caveats=(
                    "Grounded against recent Gmail payment notifications and income logs only; "
                    "not a direct bank, Stripe, or payment processor connection"
                ),
            ),
        ],
        notes=(
            "Chief's MCP filesystem tools exist but are not wired into "
            "live response routing as of v1."
        ),
    ),

}


# ── Lookup helpers ────────────────────────────────────────────────────────────

def get_actor(name: str) -> Optional[Actor]:
    return REGISTRY.get(name.lower().strip())


def get_capabilities_by_domain(actor_name: str, domain: str) -> list:
    actor = get_actor(actor_name)
    if not actor:
        return []
    return [c for c in actor.capabilities if c.domain == domain]


def describe_actor_capability(actor_name: str, domain: str) -> str:
    """
    Return a factual one-line description of an actor's capability in a domain.
    Suitable for direct injection into a Cassandra prompt.
    """
    actor = get_actor(actor_name)
    if not actor:
        return (
            f"'{actor_name}' is not in the capability registry. "
            f"I can't confirm what it can or can't do."
        )

    caps = [c for c in actor.capabilities if c.domain == domain]
    if not caps:
        return (
            f"{actor.name.capitalize()} has no '{domain}' capability registered. "
            f"That path is unconfirmed from my side."
        )

    cap = caps[0]
    status = "CONNECTED" if cap.connected else "NOT CONNECTED"
    cav = f" ({cap.caveats})" if cap.caveats else ""
    return (
        f"{actor.name.capitalize()} / {cap.name}: {cap.description}. "
        f"Status: {status}{cav}."
    )


# ── Cross-agent query detection ───────────────────────────────────────────────
# Maps domain names to the keywords that suggest a query is about that domain.

_DOMAIN_KEYWORDS: dict = {
    "file":       ("file", "path", "exist", "directory", "folder", "/mnt", "/home",
                   ".py", ".md", ".json", ".sh", ".txt", ".csv"),
    "calendar":   ("calendar", "schedule", "appointment", "meeting", "event",
                   "tomorrow morning", "tomorrow afternoon", "this week"),
    "payment":    ("payment", "deposit", "invoice", "billing", "paid", "cleared",
                   "transfer", "funds"),
    "email":      ("email", "send", "message", "mail", "smtp"),
    "email_send": ("send an email", "fire that off", "send it", "send this"),
    "album":      ("album", "session", "song", "track", "mix", "master"),
    "approval":   ("approve", "approval", "gate", "permission", "authorize"),
    "automation": ("remind", "reminder", "check again", "follow up", "follow-up",
                   "check back", "check tomorrow", "check next"),
    "billing":    ("billing", "invoice", "receipt"),
    "routing":    ("route", "handle that", "process that", "manage that"),
}

_ACTOR_KEYWORDS: dict = {
    "chief":     ("chief",),
    "cassandra": ("cassandra",),
}


def registry_context_for_query(query: str) -> Optional[str]:
    """
    If the query asks about another actor's capability, return a factual
    [REGISTRY LOOKUP] block for injection into the Cassandra prompt.
    Returns None if no cross-agent capability question is detected.

    Cassandra uses this to answer "Can Chief do X?" questions from confirmed
    registry state rather than from assumption.
    """
    t = query.lower()

    # Detect mentioned actors
    mentioned = [a for a, kws in _ACTOR_KEYWORDS.items() if any(k in t for k in kws)]
    if not mentioned:
        return None  # no actor named → no cross-agent lookup

    # Detect mentioned domains
    domains = [d for d, kws in _DOMAIN_KEYWORDS.items() if any(k in t for k in kws)]

    lines = ["[REGISTRY LOOKUP — answer from this, not from assumption]"]

    if not domains:
        # Actor named but no specific domain — return connected/not-connected summary
        for actor_name in mentioned:
            actor = get_actor(actor_name)
            if not actor:
                lines.append(f"{actor_name}: not in registry.")
                continue
            on  = [c.name for c in actor.capabilities if c.connected]
            off = [c.name for c in actor.capabilities if not c.connected]
            lines.append(
                f"{actor.name.capitalize()} ({actor.role}):\n"
                f"  Connected    : {', '.join(on) or 'none'}\n"
                f"  Not connected: {', '.join(off) or 'none'}"
            )
    else:
        # Actor + domain named → targeted lookup
        for actor_name in mentioned:
            for domain in domains:
                lines.append(describe_actor_capability(actor_name, domain))

    return "\n".join(lines)
