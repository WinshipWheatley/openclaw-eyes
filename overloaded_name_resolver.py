"""Pure overloaded-name resolver for front-door entity references."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence


RESOLVED = "RESOLVED"
AMBIGUOUS = "AMBIGUOUS"
AMBIGUOUS_SENSITIVE = "AMBIGUOUS_SENSITIVE"

ROOT = Path(__file__).resolve().parent
DEFAULT_REGISTRY_PATH = ROOT / "generated/system_knowledge/entity_name_registry.json"

SENSITIVE_VAULT = "sensitive-vault"
LEDGER_NAME = "ledger"
INBOX_NAME = "inbox"


@dataclass(frozen=True)
class Resolution:
    status: str
    name: str
    resolved_referent_id: str | None = None
    candidates: tuple[Mapping[str, Any], ...] = ()
    reason: str = ""
    prompt: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["candidates"] = [dict(candidate) for candidate in self.candidates]
        return payload


def resolve_overloaded_name(name: str, context: Mapping[str, Any] | None = None) -> Resolution:
    """Resolve an overloaded operator noun from text plus safe context.

    The function reads only the generated JSON registry. It does not open any
    ledger database and does not construct a vault path.
    """

    text = _normalize(name)
    context = context or {}
    registry = _load_registry()
    name_key = _name_key(text, context, registry)
    if not name_key:
        return Resolution(
            status=AMBIGUOUS,
            name="",
            candidates=(),
            reason="no_overloaded_name_detected",
            prompt="No overloaded entity name was detected.",
        )

    candidates = tuple(_public_candidate(row) for row in registry.get("names", {}).get(name_key, ()))
    if not candidates:
        return Resolution(
            status=AMBIGUOUS,
            name=name_key,
            candidates=(),
            reason="name_not_in_registry",
            prompt=f"I do not have a registry entry for {name_key}.",
        )

    explicit = _explicit_candidate(name_key, text, context, candidates)
    if explicit is not None:
        if _is_sensitive(explicit):
            return Resolution(
                status=AMBIGUOUS_SENSITIVE,
                name=name_key,
                candidates=(explicit,),
                reason="sensitive_vault_requires_operator_proof",
                prompt=_prompt(name_key, (explicit,), sensitive=True),
            )
        return Resolution(
            status=RESOLVED,
            name=name_key,
            resolved_referent_id=str(explicit["referent_id"]),
            candidates=(explicit,),
            reason="explicit_qualifier",
            prompt=f"I resolved {name_key} to {explicit['display_name']}.",
        )

    contextual = _context_candidate(name_key, context, candidates)
    if contextual is not None:
        if _is_sensitive(contextual):
            return Resolution(
                status=AMBIGUOUS_SENSITIVE,
                name=name_key,
                candidates=(contextual,),
                reason="sensitive_vault_requires_operator_proof",
                prompt=_prompt(name_key, (contextual,), sensitive=True),
            )
        return Resolution(
            status=RESOLVED,
            name=name_key,
            resolved_referent_id=str(contextual["referent_id"]),
            candidates=(contextual,),
            reason="context_signal",
            prompt=f"I resolved {name_key} to {contextual['display_name']} from context.",
        )

    status = AMBIGUOUS_SENSITIVE if any(_is_sensitive(candidate) for candidate in candidates) else AMBIGUOUS
    reason = (
        "name_is_ambiguous_and_sensitive_ask_to_disambiguate"
        if status == AMBIGUOUS_SENSITIVE
        else "name_is_ambiguous_ask_to_disambiguate"
    )
    return Resolution(
        status=status,
        name=name_key,
        candidates=candidates,
        reason=reason,
        prompt=_prompt(name_key, candidates, sensitive=status == AMBIGUOUS_SENSITIVE),
    )


def disambiguation_options(resolution: Resolution) -> tuple[dict[str, Any], ...]:
    options: list[dict[str, Any]] = []
    for candidate in resolution.candidates:
        options.append(
            {
                "referent_id": candidate.get("referent_id"),
                "display_name": candidate.get("display_name"),
                "namespace": candidate.get("namespace"),
                "sensitivity": candidate.get("sensitivity"),
                "default_surface": candidate.get("default_surface"),
                "read_authority": candidate.get("read_authority"),
            }
        )
    return tuple(options)


def _load_registry() -> dict[str, Any]:
    if not DEFAULT_REGISTRY_PATH.exists():
        return {"names": {}}
    payload = json.loads(DEFAULT_REGISTRY_PATH.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {"names": {}}


def _normalize(value: Any) -> str:
    text = str(value or "").lower()
    text = text.replace("_", " ")
    text = text.replace("'", "")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _name_key(text: str, context: Mapping[str, Any], registry: Mapping[str, Any]) -> str:
    context_name = _normalize(context.get("name") or context.get("entity_name") or "")
    for key in registry.get("names", {}):
        if _contains_word(text, key) or context_name == key:
            return str(key)
    return ""


def _contains_word(text: str, term: str) -> bool:
    return bool(re.search(rf"\b{re.escape(term)}\b", text))


def _public_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "referent_id": candidate.get("referent_id"),
        "display_name": candidate.get("display_name"),
        "namespace": candidate.get("namespace"),
        "location": candidate.get("location"),
        "default_surface": candidate.get("default_surface"),
        "aliases": tuple(candidate.get("aliases") or ()),
        "sensitivity": candidate.get("sensitivity"),
        "read_authority": candidate.get("read_authority"),
        "source_refs": tuple(candidate.get("source_refs") or ()),
    }


def _explicit_candidate(
    name_key: str,
    text: str,
    context: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    explicit = _normalize(context.get("explicit_qualifier") or context.get("qualifier") or "")
    haystack = f"{text} {explicit}".strip()
    for candidate in candidates:
        if _candidate_has_qualifier(candidate, haystack):
            return candidate
    if name_key == LEDGER_NAME:
        if _contains_any(haystack, ("bank", "finance", "financial", "vault")):
            return _candidate_by_id(candidates, "bank_finance_vault")
        if _contains_any(haystack, ("business ops", "businessops", "business op", "ops")):
            return _candidate_by_id(candidates, "business_ops")
        if _contains_any(haystack, ("control plane", "polish loop")):
            return _candidate_by_id(candidates, "control_plane")
        if _contains_any(haystack, ("gate decision", "governance", "gate")):
            return _candidate_by_id(candidates, "gate_decision")
        if _contains_any(haystack, ("receipt", "receipts", "proof")):
            return _candidate_by_id(candidates, "receipts")
        if _contains_any(haystack, ("gig", "invoice", "work log", "capital hilton", "st anne", "st annes")):
            return _candidate_by_id(candidates, "gig_invoice")
    if name_key == INBOX_NAME:
        if _contains_any(haystack, ("gmail", "email", "mail")):
            return _candidate_by_id(candidates, "gmail_inbox")
        if _contains_any(haystack, ("bus", "mission control", "missioncontrol")):
            return _candidate_by_id(candidates, "bus_inbox")
        if _contains_any(haystack, ("operator action", "action inbox")):
            return _candidate_by_id(candidates, "operator_action_inbox")
    return None


def _candidate_has_qualifier(candidate: Mapping[str, Any], text: str) -> bool:
    referent = _normalize(candidate.get("referent_id") or "")
    namespace = _normalize(candidate.get("namespace") or "")
    if referent and _contains_phrase(text, referent):
        return True
    if namespace and _contains_phrase(text, namespace):
        return True
    for alias in candidate.get("aliases") or ():
        if _contains_phrase(text, _normalize(alias)):
            return True
    return False


def _contains_phrase(text: str, phrase: str) -> bool:
    if not phrase:
        return False
    return bool(re.search(rf"\b{re.escape(phrase)}\b", text))


def _contains_any(text: str, phrases: Sequence[str]) -> bool:
    return any(_contains_phrase(text, _normalize(phrase)) for phrase in phrases)


def _candidate_by_id(
    candidates: Sequence[Mapping[str, Any]],
    referent_id: str,
) -> Mapping[str, Any] | None:
    for candidate in candidates:
        if candidate.get("referent_id") == referent_id:
            return candidate
    return None


def _context_candidate(
    name_key: str,
    context: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    active_surface = _normalize(
        context.get("active_surface_ref")
        or context.get("activeSurfaceRef")
        or context.get("source_surface")
        or ""
    )
    world = _normalize(
        context.get("current_world_ref")
        or context.get("currentWorldRef")
        or context.get("world_ref")
        or context.get("worldRef")
        or context.get("world")
        or ""
    )
    client = _normalize(context.get("client_ref") or context.get("clientRef") or "")
    workflow = _normalize(context.get("workflow_ref") or context.get("workflowRef") or "")
    thread = _normalize(
        context.get("current_thread_ref")
        or context.get("currentThreadRef")
        or context.get("thread_ref")
        or context.get("threadRef")
        or ""
    )
    context_blob = " ".join(part for part in (active_surface, world, client, workflow, thread) if part)

    if name_key == LEDGER_NAME:
        if _contains_any(context_blob, ("polish loop", "polishloop")):
            return _candidate_by_id(candidates, "control_plane")
        if world == "finance" and _contains_any(context_blob, ("capital hilton", "capitalhilton", "st anne", "st annes", "invoice", "work log")):
            return _candidate_by_id(candidates, "gig_invoice")
    if name_key == INBOX_NAME:
        if _contains_any(context_blob, ("operator action", "action inbox")):
            return _candidate_by_id(candidates, "operator_action_inbox")
        if _contains_any(context_blob, ("mission control", "missioncontrol", "bus")):
            return _candidate_by_id(candidates, "bus_inbox")
        if _contains_any(context_blob, ("gmail", "email", "mail")):
            return _candidate_by_id(candidates, "gmail_inbox")
    return None


def _is_sensitive(candidate: Mapping[str, Any]) -> bool:
    return str(candidate.get("sensitivity") or "").lower() == SENSITIVE_VAULT


def _prompt(name_key: str, candidates: Sequence[Mapping[str, Any]], *, sensitive: bool) -> str:
    labels = ", ".join(str(candidate.get("display_name") or candidate.get("referent_id")) for candidate in candidates)
    if sensitive:
        return (
            f"{name_key} is ambiguous and includes a sensitive-vault referent. "
            f"Please specify which one: {labels}. I recorded the request; no action ran."
        )
    return f"{name_key} is ambiguous. Please specify which one: {labels}."
