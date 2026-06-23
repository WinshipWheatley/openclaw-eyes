#!/usr/bin/env python3
"""Comedy relevance scoping — fire comedy ONLY when the diagnostic signal relates to the answer.

The comedy signal-facts come from GLOBAL system state. A joke about a global condition appended to
an unrelated answer is a non-sequitur. This gates the final comedy hint on whether its diagnostic
signal actually relates to what the operator is asking/being told about — so comedy-as-diagnostic
illuminates the situation at hand, not a random global condition.

Pure + deterministic. Conservative: if a signal has no relevance keywords or none appear in the
question/answer, comedy does NOT fire (no joke beats a non-sequitur).
"""
from __future__ import annotations

# diagnostic_signal code -> substrings that indicate the answer/question is about that situation.
SIGNAL_RELEVANCE: dict[str, tuple[str, ...]] = {
    "APPROVAL_DEPENDENCY_CYCLE": ("approv", "sign-off", "sign off", "clearance", "blocked", "block",
                                  "waiting", "stuck", "hold", "gate", "deadlock", "circular"),
    "REDUNDANT_GATE_CHAIN": ("gate", "approv", "check", "review", "step", "process", "redundan"),
    "PROCESS_EXCEEDS_TASK": ("approv", "process", "gate", "step", "bureaucr", "overhead"),
    "CONFIDENCE_EVIDENCE_GAP": ("confiden", "complete", "done", "finish", "verif", "sure", "certain",
                                "success", "ready", "proven"),
    "PREMATURE_SUCCESS": ("complete", "done", "success", "finish", "ready", "shipped"),
    "RETRY_WITHOUT_PROGRESS": ("retr", "attempt", "again", "stuck", "loop", "tried", "keeps failing"),
    "LITERAL_SCOPE_MISMATCH": ("scope", "all of", "every", "label", "match", "filter", "select",
                               "named", "name"),
    "BOUNDARY_LITERALISM": ("threshold", "limit", "boundary", "exactly", "edge", "cutoff", "greater",
                            "less than", "at least"),
    "WORDING_INTENT_MISMATCH": ("name", "label", "alias", "wording", "call it", "called", "spelled"),
    "TYPE_CATEGORY_COLLISION": ("type", "category", "kind", "format", "mismatch", "wrong type"),
    "MUTUALLY_EXCLUSIVE_CONSTRAINTS": ("constraint", "conflict", "both", "impossible", "incompatible",
                                       "can't have", "contradic"),
    "ORDER_OF_MAGNITUDE_ANOMALY": ("restart", "count", "spike", "times", "many", "huge", "way more",
                                   "way too"),
}


def is_comedy_relevant(diagnostic_signal, question: str, answer: str) -> bool:
    """True only if the hint's diagnostic signal relates to what this answer/question is about."""
    if not diagnostic_signal:
        return False
    keywords = SIGNAL_RELEVANCE.get(str(diagnostic_signal).upper(), ())
    if not keywords:
        return False
    text = f"{question or ''} {answer or ''}".lower()
    return any(kw in text for kw in keywords)
