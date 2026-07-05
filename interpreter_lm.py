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

INVOICE_SEND_INTENT = "invoice_send"

_PLACEHOLDER_INVOICE_CLIENTS = {
    "",
    "right",
    "correct",
    "one",
    "the one",
    "that one",
    "this one",
    "it",
    "them",
    "client",
    "the client",
    "invoice",
    "the invoice",
    "unknown",
    "unsure",
    "ambiguous",
    "tbd",
    "n a",
    "na",
    "none",
    "null",
}


def _normalize_label(value: Any) -> str:
    text = str(value or "").strip().lower().replace("’", "'")
    text = text.replace("'", "")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text)).strip()


def _normalize_interpreter_intent(value: Any) -> str:
    label = _normalize_label(value).replace(" ", "_")
    if label in {INVOICE_SEND_INTENT, "send_invoice", "invoice_email", "email_invoice"}:
        return INVOICE_SEND_INTENT
    return ""


def _invoice_client_registry() -> Mapping[str, Mapping[str, Any]]:
    try:
        from invoice_cockpit_client_registry import DEFAULT_CLARA_INVOICE_CLIENT_REGISTRY
    except Exception:
        return {}
    return DEFAULT_CLARA_INVOICE_CLIENT_REGISTRY


def _client_slug(value: Any) -> str:
    text = str(value or "").strip().lower().replace("_", "-")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def _model_aliases(model: Mapping[str, Any]) -> tuple[Any, ...]:
    aliases = model.get("aliases") or model.get("alias") or ()
    if isinstance(aliases, str):
        return (aliases,)
    if isinstance(aliases, (list, tuple, set)):
        return tuple(aliases)
    return ()


def _invoice_client_entries() -> tuple[dict[str, Any], ...]:
    entries: list[dict[str, Any]] = []
    for key, model in _invoice_client_registry().items():
        if not isinstance(model, Mapping):
            continue
        client_ref = model.get("client_ref") or key
        slug = _client_slug(client_ref)
        if not slug:
            continue
        display_name = model.get("client_display_name") or model.get("display_name") or model.get("client_name")
        candidates = (
            slug,
            client_ref,
            display_name,
            model.get("client"),
            model.get("customer_name"),
            *_model_aliases(model),
        )
        match_labels = frozenset(_normalize_label(item) for item in candidates if _normalize_label(item))
        entries.append(
            {
                "slug": slug,
                "display_name": str(display_name or client_ref),
                "aliases": tuple(str(item) for item in _model_aliases(model) if str(item).strip()),
                "match_labels": match_labels,
            }
        )
    return tuple(entries)


def _normalize_invoice_client(value: Any) -> str:
    label = _normalize_label(value)
    if label in _PLACEHOLDER_INVOICE_CLIENTS:
        return ""
    for entry in _invoice_client_entries():
        if label in entry["match_labels"]:
            return str(entry["slug"])
    return ""


def _invoice_client_prompt_lines() -> str:
    lines: list[str] = []
    for entry in _invoice_client_entries():
        alias_text = ", ".join(entry["aliases"][:6])
        if alias_text:
            lines.append(f'     "{entry["slug"]}" ({entry["display_name"]}; aliases: {alias_text})')
        else:
            lines.append(f'     "{entry["slug"]}" ({entry["display_name"]})')
    if not lines:
        return "     No invoice client registry is loaded; leave client empty."
    return "\n".join(lines)


def _invoice_client_slug_contract() -> str:
    slugs = tuple(entry["slug"] for entry in _invoice_client_entries())
    if not slugs:
        return "<registry-client-slug|>"
    return "<" + "|".join(slugs) + "|>"


def normalize_invoice_client_slug(value: Any) -> str:
    """Return a known invoice client slug, or empty string when unresolved."""
    return _normalize_invoice_client(value)


def is_invoice_client_placeholder(value: Any) -> bool:
    """Return True for literal placeholder words that must not become a client."""
    return _normalize_label(value) in _PLACEHOLDER_INVOICE_CLIENTS


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
    intent: str = ""
    client: str = ""

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

    def is_high_confidence_invoice_send(self) -> bool:
        """True when the interpreter confidently resolved an invoice-send intent."""
        return self.intent == INVOICE_SEND_INTENT and self.confidence >= HIGH_CONFIDENCE_THRESHOLD


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


# ── Fast-lane: direct bounded local 8b for classification ─────────────────────
# The interpreter's only job is routing + read-model selection — non-PII, no external
# egress — so it goes straight to the fast front-door 8b (full GPU offload) instead of
# the slow shared model. Without this, enabling the interpreter reintroduces the 60s
# timeout. Default ON; OPENCLAW_INTERPRETER_FAST_LANE=0 falls back to protected_generate.
import os  # noqa: E402

_DEFAULT_INTERPRETER_MODEL = "qwen3:8b-q4_K_M"


def _interpreter_model(env: Mapping[str, Any] | None = None) -> str:
    e = os.environ if env is None else env
    return str(e.get("OPENCLAW_INTERPRETER_MODEL") or _DEFAULT_INTERPRETER_MODEL).strip()


def _interpreter_fast_lane_enabled(env: Mapping[str, Any] | None = None) -> bool:
    e = os.environ if env is None else env
    return str(e.get("OPENCLAW_INTERPRETER_FAST_LANE", "1")).strip().lower() not in (
        "0", "false", "no", "off", "")


def _interpreter_timeout(env: Mapping[str, Any] | None = None) -> float:
    e = os.environ if env is None else env
    try:
        return float(e.get("OPENCLAW_INTERPRETER_TIMEOUT", "20"))
    except Exception:
        return 20.0


def _fast_interpreter_request_body(prompt: str, env: Mapping[str, Any] | None = None) -> dict:
    return {
        "model": _interpreter_model(env),
        "prompt": prompt,
        "stream": False,
        "think": False,
        "keep_alive": "10m",
        "options": {"num_predict": 220, "num_ctx": 2048, "num_gpu": 999, "temperature": 0},
    }


def _fast_interpreter_generate_fn(prompt: str, **kwargs: Any) -> str:
    """Bounded local-8b classify call (full GPU offload), no external egress. Returns ""
    on any problem so interpret_operator_message falls back to deterministic routing."""
    import json as _json
    import urllib.request as _url

    body = _json.dumps(_fast_interpreter_request_body(prompt)).encode("utf-8")
    req = _url.Request("http://127.0.0.1:11434/api/generate", data=body,
                       headers={"Content-Type": "application/json"})
    try:
        with _url.urlopen(req, timeout=_interpreter_timeout()) as resp:
            return str(_json.loads(resp.read()).get("response", ""))
    except Exception:
        return ""


def _select_interpreter_generate_fn(env: Mapping[str, Any] | None = None):
    """Fast-lane (default) when enabled, else the slow protected_generate gate."""
    return _fast_interpreter_generate_fn if _interpreter_fast_lane_enabled(env) else _default_protected_generate_fn


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
    invoice_clients_list = _invoice_client_prompt_lines()
    invoice_client_contract = _invoice_client_slug_contract()
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

2. Select read-models ONLY when the message CLEARLY needs that specific data to answer
   (e.g. it asks about gigs, invoices/money, the calendar, agent/system status, work items).
   For casual conversation, greetings, small talk, acknowledgements, or anything with no
   clear data need, select NONE — an empty list []. Prefer FEWER; never reach for a
   tangentially-related model. When in doubt, select none. Hard max 3.

3. Rate your confidence 0.00 to 1.00.

4. If the operator is asking to prepare, generate, draft, email, or send a client invoice, set:
   - "intent": "invoice_send"
   - "client": one canonical slug from the invoice client registry below.
   Resolve natural names and aliases to the matching registry slug. If the wording says
   only "the right invoice", "that one", "the invoice", or another placeholder, leave
   "client" empty unless the available context clearly resolves it. Questions like
   "did they pay the invoice?" are NOT invoice_send intents.

INVOICE CLIENT REGISTRY:
{invoice_clients_list}

Respond ONLY with valid JSON, no prose, no markdown fences:
{{
  "route": "<BRAIN|WORKFLOW|ACTION|BLOCKED|UNCERTAIN>",
  "fact_selection": ["<filename>", ...],
  "confidence": <float 0.0-1.0>,
  "reason": "<one sentence>",
  "intent": "<invoice_send|>",
  "client": "{invoice_client_contract}"
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
    intent = _normalize_interpreter_intent(payload.get("intent"))
    client = _normalize_invoice_client(
        payload.get("client")
        or payload.get("client_slug")
        or payload.get("client_id")
        or payload.get("invoice_client")
    )

    return InterpretResult(
        route=raw_route,
        fact_selection=fact_selection,
        confidence=confidence,
        reason=reason,
        intent=intent,
        client=client,
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

    _fn = protected_generate_fn or _select_interpreter_generate_fn()
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
