"""IB-3 glue — the single entrypoint the listener calls with the operator's message.

If there's no active cockpit session, it only engages when the message is an invoice-send trigger;
otherwise it returns handled=False so normal routing continues. Once a session is active, every
operator message drives the state machine until the flow ends. State is persisted between messages
via the injected store.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping
from typing import Any

import interpreter_lm
import invoice_cockpit_executor as ex
import invoice_send_workflow as wf
from invoice_cockpit_client_registry import DEFAULT_CLIENT_MODELS

REFUSED = "refused"
UNKNOWN_CLIENT = "unknown_client"
AWAITING_INVOICE_CLIENT = "awaiting_invoice_client"

_INTERPRETER_NO_TRIGGER = object()
_INTERPRETER_NEEDS_CLIENT = object()

# "send the St Anne's invoice", "email the Capital Hilton invoice", "invoice for Draper" ...
# Must be an IMPERATIVE command, not a casual mention or a question.
_TRIGGER = re.compile(
    r"^\s*(?:please\s+|hey[, ]+|ok(?:ay)?[, ]+)?(?:send|e-?mail|generate|prepare|create|draft|make)\b[^?\n]{0,80}\binvoice\b",
    re.IGNORECASE,
)

_FUZZY_EMAIL_TRIGGER = re.compile(
    r"^\s*(?:please\s+|hey[, ]+|ok(?:ay)?[, ]+)?"
    r"(?:test|draft|prepare|create|generate|make|send)\b\s+"
    r"(?:the\s+)?(?P<client>[^?\n]{2,80}?)\s+"
    r"(?:invoice\s+)?(?:e-?mail|message|draft)\b",
    re.IGNORECASE,
)

_MISSING_EMAIL_MARKERS = {"", "unknown", "missing", "none", "null", "n/a", "na", "tbd"}


def _detect_invoice_trigger(text: str) -> str | None:
    t = str(text or "")
    if not _TRIGGER.search(t):
        return None
    m = re.search(r"\bthe\s+(.+?)\s+invoice\b", t, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(
        r"^\s*(?:please\s+|hey[, ]+|ok(?:ay)?[, ]+)?"
        r"(?:send|e-?mail|generate|prepare|create|draft|make)\s+"
        r"(.+?)\s+invoice\b",
        t,
        re.IGNORECASE,
    )
    if m:
        return m.group(1).strip()
    m = re.search(r"\binvoice\s+(?:for|to)\s+(.+)$", t, re.IGNORECASE)
    if m:
        return m.group(1).strip().rstrip(".!?")
    return "the client"


def _detect_fuzzy_email_trigger(text: str) -> str | None:
    t = str(text or "")
    if "?" in t:
        return None
    match = _FUZZY_EMAIL_TRIGGER.search(t)
    if not match:
        return None
    return match.group("client").strip().rstrip(".!,")


def _client_match_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold().replace("&", "and"))


def _client_ref_slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").casefold()).strip("_")


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _model_aliases(model: Mapping[str, Any]) -> tuple[Any, ...]:
    aliases = model.get("aliases") or model.get("alias") or ()
    if isinstance(aliases, str):
        return (aliases,)
    if isinstance(aliases, Iterable):
        return tuple(aliases)
    return ()


def _iter_client_models(
    client_models: Mapping[str, Mapping[str, Any]] | Iterable[Mapping[str, Any]] | None,
) -> Iterable[dict[str, Any]]:
    if client_models is None:
        yield from (dict(model) for model in DEFAULT_CLIENT_MODELS)
        return
    if isinstance(client_models, Mapping):
        for key, model in client_models.items():
            merged = dict(model)
            merged.setdefault("client_ref", str(key))
            merged["client_ref"] = _client_ref_slug(merged.get("client_ref"))
            merged.setdefault("display_name", merged.get("client_display_name") or merged.get("client_name"))
            yield merged
        return
    for model in client_models:
        merged = dict(model)
        if "client_ref" in merged:
            merged["client_ref"] = _client_ref_slug(merged.get("client_ref"))
        merged.setdefault("display_name", merged.get("client_display_name") or merged.get("client_name"))
        yield merged


def resolve_client_model(
    requested_client: str,
    client_models: Mapping[str, Mapping[str, Any]] | Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any] | None:
    requested_key = _client_match_key(requested_client)
    if not requested_key:
        return None
    best: dict[str, Any] | None = None
    best_len = -1
    for model in _iter_client_models(client_models):
        candidates = [
            model.get("client_ref"),
            model.get("slug"),
            model.get("client"),
            model.get("client_name"),
            model.get("client_display_name"),
            model.get("display_name"),
            *_model_aliases(model),
        ]
        for candidate in candidates:
            candidate_key = _client_match_key(candidate)
            if not candidate_key:
                continue
            if requested_key == candidate_key or candidate_key in requested_key:
                if len(candidate_key) > best_len:
                    best = model
                    best_len = len(candidate_key)
    if best is None:
        return None
    resolved = dict(best)
    if "client_ref" in resolved:
        resolved["client_ref"] = _client_ref_slug(resolved.get("client_ref"))
    resolved.setdefault("display_name", resolved.get("client_display_name") or requested_client)
    resolved["requested_client_text"] = requested_client
    resolved["coupa_or_po_implied"] = bool(
        re.search(r"\b(coupa|p\.?o\.?|po|purchase\s+order|portal)\b", requested_client, re.IGNORECASE)
    )
    return resolved


def _safe_telegram_message(ops: Any, text: str) -> dict[str, Any]:
    try:
        return ops.telegram_message(text)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "text": text}


def _ask_which_client(ops: Any) -> dict[str, Any]:
    result = _safe_telegram_message(ops, "Which client should I prepare the invoice for?")
    return {"handled": True, "stage": AWAITING_INVOICE_CLIENT, "results": [result]}


def _is_placeholder_client(value: Any) -> bool:
    return interpreter_lm.is_invoice_client_placeholder(value)


def _canonical_invoice_client(value: Any) -> str:
    return interpreter_lm.normalize_invoice_client_slug(value)


def _interpreter_invoice_trigger(text: str) -> str | object | None:
    if not interpreter_lm._interpreter_enabled():
        return None
    try:
        result = interpreter_lm.interpret_operator_message(text)
    except Exception:
        return None

    if result.route == interpreter_lm.ROUTE_UNCERTAIN:
        return None

    if result.is_high_confidence_invoice_send():
        client = _canonical_invoice_client(result.client)
        if client:
            return client
        return _INTERPRETER_NEEDS_CLIENT

    if result.confidence >= interpreter_lm.HIGH_CONFIDENCE_THRESHOLD:
        return _INTERPRETER_NO_TRIGGER

    return None


def _coupa_or_po_path_implied(client_model: Mapping[str, Any]) -> bool:
    if _truthy(client_model.get("coupa_or_po_implied")):
        return True
    if any(
        _truthy(client_model.get(key))
        for key in (
            "po_required",
            "purchase_order_required",
            "coupa_requires_purchase_order",
            "portal_required",
            "portal_required_for_all",
        )
    ):
        return True
    invoice_sources = client_model.get("invoice_sources") or client_model.get("invoice_source") or ()
    if isinstance(invoice_sources, Mapping):
        source_text = " ".join(f"{key} {value}" for key, value in invoice_sources.items())
    elif isinstance(invoice_sources, Iterable) and not isinstance(invoice_sources, (str, bytes)):
        source_text = " ".join(str(item) for item in invoice_sources)
    else:
        source_text = str(invoice_sources or "")
    path_text = " ".join(
        str(client_model.get(key) or "")
        for key in ("invoice_path", "route_path", "send_state", "send_status", "status")
    )
    path_text = f"{path_text} {source_text}".casefold()
    return any(token in path_text for token in ("coupa only", "po only", "purchase order only", "portal only"))


def _preflight_client_route(client_model: Mapping[str, Any], ops: Any) -> tuple[str, list[dict[str, Any]]] | None:
    send_state = str(
        client_model.get("send_state")
        or client_model.get("send_status")
        or client_model.get("status")
        or ""
    ).upper()
    status = str(client_model.get("status") or "").casefold()
    action = str(client_model.get("action") or client_model.get("send_action") or "").strip().casefold()

    if _truthy(client_model.get("send_block")) or send_state == "DO_NOT_SEND":
        text = str(client_model.get("refusal_message") or "This client is blocked from invoice sending.")
        return REFUSED, [_safe_telegram_message(ops, text)]

    if status == "paid_no_invoice_sent":
        text = str(
            client_model.get("refusal_message")
            or "This client is already paid; no invoice will be sent now."
        )
        return REFUSED, [_safe_telegram_message(ops, text)]

    if action in {"refuse", "blocked", "do_not_send"}:
        text = str(client_model.get("refusal_message") or "This client is blocked from invoice sending.")
        return REFUSED, [_safe_telegram_message(ops, text)]

    if action and action not in {"invoice_cockpit", "prepare_invoice", "excel_invoice", "send_invoice"}:
        text = str(
            client_model.get("action_message")
            or f"This client routes through {action}; I am not starting the invoice cockpit."
        )
        return REFUSED, [_safe_telegram_message(ops, text)]

    if _coupa_or_po_path_implied(client_model):
        note = str(client_model.get("dual_path_note") or "")
        text = f"{note} Coupa/PO path is implied, so I am not starting the Excel invoice cockpit.".strip()
        return REFUSED, [_safe_telegram_message(ops, text)]

    return None


def _missing_recipient(value: Any) -> bool:
    recipient = str(value or "").strip()
    if recipient.casefold() in _MISSING_EMAIL_MARKERS:
        return True
    return "@" not in recipient


def _rollback_stage(state: dict[str, Any], previous_stage: str | None) -> None:
    if previous_stage:
        state["stage"] = previous_stage


def _notify_send_failure(
    *,
    ops: Any,
    results: list[dict[str, Any]],
    state: dict[str, Any],
    previous_stage: str | None,
    reason: str,
) -> None:
    _rollback_stage(state, previous_stage)
    message = f"that send failed: {reason} - nothing was sent"
    results.append({"ok": False, "error": message})
    results.append(_safe_telegram_message(ops, message))


def handle_invoice_cockpit_message(
    text: str,
    *,
    ops: Any,
    store: Any,
    client_models: Mapping[str, Mapping[str, Any]] | Iterable[Mapping[str, Any]] | None = None,
    client_resolver: Callable[[str], Mapping[str, Any] | None] | None = None,
) -> dict[str, Any]:
    session = store.load()
    if session is not None and re.search(
        r"\b(cancel|nevermind|never mind|forget it|stop the invoice|quit)\b",
        str(text or ""),
        re.IGNORECASE,
    ):
        store.clear()
        _safe_telegram_message(ops, "Okay - cancelled the invoice flow. Nothing was sent.")
        return {"handled": True, "stage": "cancelled"}

    previous_stage = None
    pre_results: list[dict[str, Any]] = []
    if session is None:
        interpreted = _interpreter_invoice_trigger(text)
        if interpreted is _INTERPRETER_NO_TRIGGER:
            return {"handled": False}
        if interpreted is _INTERPRETER_NEEDS_CLIENT:
            return _ask_which_client(ops)

        requested_client = (
            str(interpreted)
            if isinstance(interpreted, str)
            else (_detect_invoice_trigger(text) or _detect_fuzzy_email_trigger(text))
        )
        if not requested_client:
            return {"handled": False}
        if _is_placeholder_client(requested_client):
            return _ask_which_client(ops)

        client_model = (
            dict(client_resolver(requested_client) or {})
            if client_resolver is not None
            else resolve_client_model(requested_client, client_models)
        )
        if not client_model:
            result = _safe_telegram_message(
                ops,
                f"I don't have that client in the invoice registry: {requested_client}.",
            )
            return {"handled": True, "stage": UNKNOWN_CLIENT, "results": [result]}
        if "client_ref" in client_model:
            client_model["client_ref"] = _client_ref_slug(client_model.get("client_ref"))
        client_model.setdefault("display_name", client_model.get("client_display_name") or requested_client)
        client_model.setdefault("requested_client_text", requested_client)
        client_model.setdefault(
            "coupa_or_po_implied",
            bool(
                re.search(
                    r"\b(coupa|p\.?o\.?|po|purchase\s+order|portal)\b",
                    requested_client,
                    re.IGNORECASE,
                )
            ),
        )

        preflight = _preflight_client_route(client_model, ops)
        if preflight is not None:
            stage, results = preflight
            return {"handled": True, "stage": stage, "client_model": client_model, "results": results}

        for note_key in ("operator_note", "dual_path_note", "routing_note", "status_note"):
            note = str(client_model.get(note_key) or "").strip()
            if note:
                pre_results.append(_safe_telegram_message(ops, note))

        try:
            invoice_data, pdf_path, digest = ops.prepare_invoice(client_model)
        except Exception as exc:
            return {"handled": True, "error": f"could not prepare the invoice: {exc}"}
        client_name = str(client_model.get("display_name") or requested_client)
        state, actions = wf.start_invoice_send(client_name, invoice_data, pdf_path, digest)
        state["client_ref"] = str(client_model.get("client_ref") or "")
        state["client_model"] = dict(client_model)
    else:
        previous_stage = str(session.get("stage") or "")
        state, actions = wf.handle_reply(session, text)

    results: list[dict[str, Any]] = list(pre_results)
    for action in actions:
        if action.get("kind") == wf.APPLY_EDIT:
            result = ops.apply_edit(state.get("invoice_data"), action.get("instruction"))
            results.append(result)
            if result.get("ok") and result.get("changed") and isinstance(result.get("invoice_data"), dict):
                state["invoice_data"] = result["invoice_data"]
                state["client_email"] = str(result["invoice_data"].get("client_email") or state.get("client_email") or "")
                if result.get("pdf_path"):
                    state["pdf_path"] = result["pdf_path"]
                if result.get("attachment_sha256"):
                    state["attachment_sha256"] = result["attachment_sha256"]
                results.append(
                    ops.telegram_pdf(
                        state.get("pdf_path"),
                        "Updated invoice preview. Reply with any change, or 'looks good' to draft it.",
                    )
                )
            else:
                note = result.get("note") or result.get("error") or "I couldn't parse that edit. Please say what line, date, and amount to change."
                results.append(_safe_telegram_message(ops, note))
            continue

        if action.get("kind") in (wf.TEST_SEND, wf.REAL_SEND) and _missing_recipient(action.get("to")):
            _notify_send_failure(
                ops=ops,
                results=results,
                state=state,
                previous_stage=previous_stage,
                reason="missing client email",
            )
            continue

        result = ex.execute_action(action, ops)
        if action.get("kind") in (wf.ASK_CLARIFY, wf.SEND_MESSAGE) and isinstance(result, dict):
            result = dict(result)
            result.setdefault("text", action.get("text") or "")
        results.append(result)
        if action.get("kind") in (wf.TEST_SEND, wf.REAL_SEND) and isinstance(result, dict) and result.get("ok") is False:
            reason = str(result.get("error") or result.get("reason") or "unknown error")
            _notify_send_failure(
                ops=ops,
                results=results,
                state=state,
                previous_stage=previous_stage,
                reason=reason,
            )

    if state.get("stage") in (wf.SENT, wf.CANCELLED):
        store.clear()
    else:
        store.save(state)
    return {"handled": True, "stage": state.get("stage"), "results": results}


__all__ = [
    "AWAITING_INVOICE_CLIENT",
    "DEFAULT_CLIENT_MODELS",
    "REFUSED",
    "UNKNOWN_CLIENT",
    "handle_invoice_cockpit_message",
    "resolve_client_model",
    "_detect_invoice_trigger",
]
