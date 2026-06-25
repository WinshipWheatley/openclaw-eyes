"""Interpreter LM — understand-before-fetch (INTERP-v1).

Classifies an operator message BEFORE the deterministic routing and fact-fetch
steps, enabling:

1. ROUTING augmentation: conversational messages that would land in the
   workflow consumer (saved-for-review) can instead be routed to
   answer_frontdoor_chat (the brain).
2. FACT SELECTION: selects which read-models / entities are relevant so
   build_maestro_context_packet assembles a grounded packet instead of a
   keyword guess.

DISCIPLINE
----------
- Flag-gated: _interpreter_enabled() reads env OPENCLAW_INTERPRETER_LM,
  default "0"/off.  OFF → callers see no effect; the interpreter is never
  called.
- Advisory only: route=BRAIN can ADD a brain diversion; it can NEVER block
  the brain, escalate authority, or trigger an action.
- Fallback: any exception from the LM call, a missing protected_generate_fn,
  UNCERTAIN result, or confidence below HIGH_CONFIDENCE_THRESHOLD → caller
  receives an UNCERTAIN result and falls through to the deterministic path.
- The interpreter LM call passes through an INJECTABLE protected_generate_fn
  (tests pass a mock; default is the real protected_generate wrapper).
- NO authority effect: InterpretResult carries NO authority/allow/send field
  and is never consulted by authority_gate.py, action_runtime.py, or any
  SEND_HOLD path.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

# ---------------------------------------------------------------------------
# Flag gate
# ---------------------------------------------------------------------------

def _interpreter_enabled() -> bool:
    """Return True only when OPENCLAW_INTERPRETER_LM is "1" or "true"."""
    return os.environ.get("OPENCLAW_INTERPRETER_LM", "0").lower() in ("1", "true")


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

ROUTE_BRAIN = "BRAIN"
ROUTE_WORKFLOW = "WORKFLOW"
ROUTE_ACTION = "ACTION"
ROUTE_BLOCKED = "BLOCKED"
ROUTE_UNCERTAIN = "UNCERTAIN"

# Confidence threshold: interpreter result is only acted upon when confidence
# is at or above this value.  Lower → falls back to deterministic path.
HIGH_CONFIDENCE_THRESHOLD = 0.75

_VALID_ROUTES = {ROUTE_BRAIN, ROUTE_WORKFLOW, ROUTE_ACTION, ROUTE_BLOCKED, ROUTE_UNCERTAIN}


@dataclass(frozen=True)
class InterpretResult:
    """Pure data — NO authority or action fields by design.

    The presence of route=BRAIN is ADVISORY: it tells the dispatcher that the
    interpreter believes the message is conversational.  Only the dispatcher
    decides whether to act on it; the interpreter itself never authorises a
    send, action, DENY→ALLOW flip, or money movement.

    Routes
    ------
    BRAIN    — conversational; should reach answer_frontdoor_chat.
    WORKFLOW — package/workflow generation; workflow consumer path.
    ACTION   — action proposal; dispatcher consults authority_gate (gate decides).
               The interpreter NEVER decides authority; it only flags the route.
    BLOCKED  — needs operator approval / blocked; surfaces the block to the operator.
    UNCERTAIN — ambiguous or low-confidence; deterministic fallback.
    """

    route: str  # BRAIN | WORKFLOW | ACTION | BLOCKED | UNCERTAIN
    fact_selection: list[str] = field(default_factory=list)
    confidence: float = 0.0
    reason: str = ""

    def is_high_confidence_brain(self) -> bool:
        """True when the interpreter is confident the message is conversational."""
        return self.route == ROUTE_BRAIN and self.confidence >= HIGH_CONFIDENCE_THRESHOLD

    def is_high_confidence_action(self) -> bool:
        """True when the interpreter classifies this as an action proposal with high confidence.

        IMPORTANT: this is advisory routing ONLY.  The authority_gate.decide() call
        (NOT this flag) is what decides ALLOW/HITL_REQUIRED/DENY.  This flag does
        NOT authorize execution — it signals "consult the gate."
        """
        return self.route == ROUTE_ACTION and self.confidence >= HIGH_CONFIDENCE_THRESHOLD

    def is_high_confidence_blocked(self) -> bool:
        """True when the interpreter classifies this as blocked/needs approval, with high confidence."""
        return self.route == ROUTE_BLOCKED and self.confidence >= HIGH_CONFIDENCE_THRESHOLD


# ---------------------------------------------------------------------------
# Default protected_generate wrapper
# ---------------------------------------------------------------------------

def _default_protected_generate_fn(prompt: str, **kwargs: Any) -> Any:
    """Default: call the real protected_generate gate.

    Imported lazily so the module can be imported in test environments where
    protected_generate may not be wired to a live model.
    """
    from protected_generate import protected_generate  # type: ignore[import]

    return protected_generate(prompt, **kwargs)


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

_KNOWN_READ_MODELS = (
    "agent_presence.json",
    "openclaw_capability_index.json",
    "chief_status_rail.json",
    "openclaw_change_sentinel.json",
    "finance_invoice_reconciliation.json",
    "capital_hilton_invoice_operator_readback.json",
    "capital_hilton_invoice_operator_run_status.json",
    "cassandra_email_calendar_delta_detangle.json",
    "work_board.json",
    "orchestration_progress.json",
)


def _build_interpreter_prompt(text: str) -> str:
    read_models_list = "\n".join(f"  - {m}" for m in _KNOWN_READ_MODELS)
    return f"""You are the Maestro Interpreter LM.  Your ONLY job is to classify the operator's message and select relevant read-models.

OPERATOR MESSAGE:
{text}

AVAILABLE READ MODELS:
{read_models_list}

TASK:
1. Decide the route:
   - BRAIN: conversational, status-check, question, or reasoning request → should reach the Maestro brain (answer_frontdoor_chat)
   - WORKFLOW: explicit package/workflow generation or multi-step business task → workflow consumer path
   - ACTION: a concrete action proposal (e.g. "send email", "mark invoice paid") → authority gate will be consulted; never auto-executes
   - BLOCKED: needs operator approval, is gated, or cannot proceed without a human decision → surfaces block to operator
   - UNCERTAIN: ambiguous or impossible to classify with high confidence → safe deterministic fallback

2. Select the 0-5 most relevant read-models from the list above (by exact filename) that would help answer this message.

3. Rate your confidence 0.00 to 1.00.

Respond ONLY with valid JSON, no prose, no markdown fences:
{{
  "route": "<BRAIN|WORKFLOW|ACTION|BLOCKED|UNCERTAIN>",
  "fact_selection": ["<filename>", ...],
  "confidence": <float 0.0-1.0>,
  "reason": "<one sentence>"
}}"""


# ---------------------------------------------------------------------------
# LM output parser
# ---------------------------------------------------------------------------

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_interpreter_output(raw: str) -> InterpretResult:
    """Parse LM output into InterpretResult.  Returns UNCERTAIN on any error."""
    try:
        # Strip markdown fences if the model ignores the instruction
        match = _JSON_BLOCK_RE.search(str(raw or ""))
        if not match:
            return InterpretResult(route=ROUTE_UNCERTAIN, reason="no_json_found")
        payload = json.loads(match.group(0))
    except (json.JSONDecodeError, TypeError, ValueError):
        return InterpretResult(route=ROUTE_UNCERTAIN, reason="json_parse_error")

    if not isinstance(payload, dict):
        return InterpretResult(route=ROUTE_UNCERTAIN, reason="non_dict_payload")

    # Route — only accept the five known values
    raw_route = str(payload.get("route") or "").strip().upper()
    if raw_route not in _VALID_ROUTES:
        return InterpretResult(route=ROUTE_UNCERTAIN, reason=f"unknown_route:{raw_route}")

    # Fact selection — list of strings; filter to known read-models only
    raw_selection = payload.get("fact_selection")
    if isinstance(raw_selection, list):
        fact_selection = [
            str(item).strip()
            for item in raw_selection
            if isinstance(item, str) and str(item).strip() in _KNOWN_READ_MODELS
        ]
    else:
        fact_selection = []

    # Confidence — clamp to [0.0, 1.0]
    try:
        confidence = float(payload.get("confidence") or 0.0)
        confidence = max(0.0, min(1.0, confidence))
    except (TypeError, ValueError):
        confidence = 0.0

    reason = str(payload.get("reason") or "").strip()[:500]

    return InterpretResult(
        route=raw_route,
        fact_selection=fact_selection,
        confidence=confidence,
        reason=reason,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def interpret_operator_message(
    text: str,
    *,
    session: Mapping[str, Any] | None = None,
    protected_generate_fn: Callable[..., Any] | None = None,
) -> InterpretResult:
    """Classify an operator message and select relevant read-models.

    Parameters
    ----------
    text:
        Raw operator message text.
    session:
        Optional session mapping (passed through for future caching keys;
        not used in the LM call itself to avoid leaking session state).
    protected_generate_fn:
        Injectable generator function.  Tests pass a mock that never calls a
        real model.  Default (None) → _default_protected_generate_fn (the real
        protected_generate gate).

    Returns
    -------
    InterpretResult with route, fact_selection, confidence, reason.  On ANY
    error (no fn, exception, bad output) → UNCERTAIN so the caller falls
    through to the deterministic path.

    NOTE: this function has NO authority effect.  It cannot authorize sends,
    actions, or DENY→ALLOW flips.  It cannot be called by authority_gate.py.
    """
    if not text or not text.strip():
        return InterpretResult(route=ROUTE_UNCERTAIN, reason="empty_text")

    _fn = protected_generate_fn or _default_protected_generate_fn
    if _fn is None:
        return InterpretResult(route=ROUTE_UNCERTAIN, reason="no_protected_generate_fn")

    try:
        prompt = _build_interpreter_prompt(text)
        raw_result = _fn(prompt)
        # protected_generate returns a ProtectedGenerateOutcome or str-like
        if hasattr(raw_result, "text"):
            raw_text = str(raw_result.text or "")
        else:
            raw_text = str(raw_result or "")
        return _parse_interpreter_output(raw_text)
    except Exception:  # noqa: BLE001 — never worse than deterministic baseline
        return InterpretResult(route=ROUTE_UNCERTAIN, reason="interpreter_exception")
