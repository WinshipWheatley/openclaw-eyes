"""
Per-contact topic-sensitivity policy for Cassandra inner-circle contacts.
Source of truth: polish_loop/spec-inner-circle-correspondence.md § CONTACT TRUST MODEL

classify_topic(query, contact_nickname) -> "allowed" | "caution" | "escalate"

Priority: escalate > caution > allowed (strictest lane wins).
Unknown contact nickname -> "escalate" (maximum safety).
"""

import re

# ── Per-contact lane definitions ──────────────────────────────────────────────
# Each contact has three lists of topic categories:
#   allowed   — answer directly
#   caution   — hold, notify Winship
#   escalate  — escalate, notify Winship, do not answer
#
# Any topic NOT in allowed or caution that is detected goes to caution by default.
# Escalation topics always win regardless of contact.

_CONTACT_LANES: dict[str, dict[str, list[str]]] = {
    "dad": {
        "allowed": ["financial", "scheduling", "general"],
        "caution": ["financial_detail"],
        "escalate": ["action_on_behalf", "pii"],
    },
    "mom": {
        "allowed": ["general", "family", "scheduling"],
        "caution": ["financial", "financial_detail", "financial_personal", "project_work"],
        "escalate": ["action_on_behalf", "pii"],
    },
    "draper": {
        "allowed": ["operational", "scheduling", "project_work", "general"],
        "caution": ["family"],
        "escalate": ["action_on_behalf", "pii", "financial", "financial_detail", "financial_personal"],
    },
}

# ── Topic detection patterns ──────────────────────────────────────────────────
# Each entry is a list of regex patterns (case-insensitive).
# Pattern count is kept deliberately narrow to limit false positives.

_TOPIC_PATTERNS: dict[str, list[str]] = {
    # PII — always escalate
    "pii": [
        r"\bssn\b",
        r"\bsocial\s+security\b",
        r"\btax\s+id\b",
        r"\bein\b",
        r"\baccount\s+number\b",
        r"\brouting\s+number\b",
        r"\bpassword\b",
        r"\bcredential",
        r"\bpin\s+number\b",
        r"\bdob\b",
        r"\bdate\s+of\s+birth\b",
    ],
    # Action on behalf — always escalate
    "action_on_behalf": [
        r"\btell\s+\w+\s+to\b",
        r"\bsend\s+money\b",
        r"\btransfer\s+funds?\b",
        r"\bpay\s+(?:him|her|them|me|us|dad|mom|draper|the\s+(?:bill|invoice|deposit|fee|balance))\b",
        r"\bsign\s+(this|the|an|a)\b",
        r"\bcommit\s+to\b",
        r"\bauthorize\b",
        r"\bagree\s+to\b",
        r"\bapprove\s+on\s+(his|my|winship'?s?)\s+behalf\b",
        r"\bact\s+on\s+(his|my|winship'?s?)\s+behalf\b",
    ],
    # Financial detail — granular figures, margins, taxes
    "financial_detail": [
        r"\btotal\s+revenue\b",
        r"\btotal\s+income\b",
        r"\bmargin\b",
        r"\bprofit\b",
        r"\bgross\s+(pay|income|revenue|profit)\b",
        r"\bnet\s+(pay|income|revenue|profit)\b",
        r"\btax\s+prep\b",
        r"\btax\s+return\b",
        r"\bquarterly\s+earnings?\b",
        r"\bannual\s+earnings?\b",
        r"\bbalance\s+sheet\b",
    ],
    # Financial personal — Winship's personal money / salary
    "financial_personal": [
        r"\bsalary\b",
        r"\bhow\s+much\s+(does|did|is)\s+(winship|he)\s+(make|earn|get|paid)\b",
        r"\bwhat\s+(does|did)\s+(winship|he)\s+make\b",
        r"\bhis\s+(income|earnings?|salary|savings?|net\s+worth)\b",
        r"\btax\s+situation\b",
        r"\bsavings?\s+account\b",
        r"\bpersonal\s+finances?\b",
    ],
    # Financial — general payment/invoice mentions
    "financial": [
        r"\bpayment\b",
        r"\binvoice\b",
        r"\bpaid\b",
        r"\bbalance\s+(due|owed)\b",
        r"\bhow\s+much\b",
        r"\bowe\b",
        r"\bgig\s+pay\b",
        r"\bgig\s+paid\b",
        r"\bcheck\s+(arrived|cleared|come\s+through)\b",
        r"\bdirect\s+deposit\b",
    ],
    # Scheduling — calendar/meeting mentions
    "scheduling": [
        r"\bschedule\b",
        r"\bcalendar\b",
        r"\bmeeting\b",
        r"\bappointment\b",
        r"\bwhen\s+is\b",
        r"\bwhat\s+time\b",
        r"\bavailable\b",
        r"\bbook\b",
        r"\bset\s+up\s+a\b",
        r"\bremind\b",
        r"\bthursday|friday|monday|tuesday|wednesday|saturday|sunday\b",
        r"\btomorrow\b",
        r"\bnext\s+week\b",
    ],
    # Family — personal/family matters
    "family": [
        r"\bfamily\b",
        r"\bmom\b",
        r"\bdad\b",
        r"\bbrother\b",
        r"\bsister\b",
        r"\bparents?\b",
        r"\bhome\b",
        r"\bhealth\b",
        r"\bsick\b",
        r"\bpersonal\s+(life|matter|issue)\b",
        r"\bhow('?s|\s+is)\s+(he|winship|everyone)\s+doing\b",
        r"\bhow'?s?\s+the\s+family\b",
    ],
    # Project/work — business, clients, gigs, album
    "project_work": [
        r"\bproject\b",
        r"\bclient\b",
        r"\bgig\b",
        r"\bbusiness\b",
        r"\balbum\b",
        r"\btrack\b",
        r"\brelease\b",
        r"\bdeal\b",
        r"\bcontract\b",
        r"\brecord(ing)?\b",
        r"\blabel\b",
        r"\bstudio\b",
    ],
    # Operational — system/deployment/task status
    "operational": [
        r"\btask\b",
        r"\bstatus\b",
        r"\bdeployment\b",
        r"\bsystem\b",
        r"\bserver\b",
        r"\bstack\b",
        r"\bbot\b",
        r"\bupdate\b",
        r"\bprogress\b",
    ],
}


def _detect_topics(query: str) -> set[str]:
    """Return all topic categories that match patterns in query."""
    q = query.lower()
    found: set[str] = set()
    for topic, patterns in _TOPIC_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, q):
                found.add(topic)
                break
    return found


def classify_topic(query: str, contact_nickname: str) -> str:
    """Classify a query for a given contact into allowed/caution/escalate.

    Args:
        query: The message text (already stripped of bot prefix).
        contact_nickname: Lowercase nickname from contact_nicknames.json (e.g. "dad").

    Returns:
        "allowed"  — proceed normally
        "caution"  — hold, notify Winship
        "escalate" — escalate, notify Winship, do not answer
    """
    nick = contact_nickname.lower().strip() if contact_nickname else ""

    # Unknown contact = maximum safety
    if nick not in _CONTACT_LANES:
        return "escalate"

    lanes = _CONTACT_LANES[nick]
    topics = _detect_topics(query)

    # Priority 1: escalation wins unconditionally
    for t in topics:
        if t in lanes.get("escalate", []):
            return "escalate"

    # Priority 2: caution wins over allowed
    for t in topics:
        if t in lanes.get("caution", []):
            return "caution"

    # Priority 3: if no topics detected OR all detected are in allowed list
    return "allowed"
