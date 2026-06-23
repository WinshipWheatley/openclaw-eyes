#!/usr/bin/env python3
"""Term-surface realizer — the live jargon-teaching glue.

Scans a delivered answer for VERIFIED catalog terms, plans teaching per the operator's knowledge
state (plan_term_teaching), and inserts the EXACT verified ELI5 definition adjacent to the first
use of an unknown/learning term. Returns the teaching hints to record AFTER confirmed delivery.

TRUTH FIRST: verified terms only; the inserted text is the EXACT catalog wording (never invented).
Naturally scoped — it teaches only terms that actually appear in the answer. Never raises, so it is
safe to call on the live reply path.
"""
from __future__ import annotations

import re
from typing import Optional

try:  # pragma: no cover
    from jargon_teaching_store import (
        TermRequirement,
        load_operator_term_knowledge,
        load_verified_term_catalog,
        plan_term_teaching,
    )
except Exception:  # pragma: no cover
    load_verified_term_catalog = None  # type: ignore


def realize_term_teaching(answer_text: str, operator_id: str = "winship") -> tuple[str, list]:
    """Return (answer_with_definitions, applied_hints). Never raises."""
    try:
        if load_verified_term_catalog is None or not isinstance(answer_text, str) or not answer_text.strip():
            return (answer_text if isinstance(answer_text, str) else ""), []
        catalog = load_verified_term_catalog()
        if not catalog:
            return answer_text, []
        try:
            knowledge = load_operator_term_knowledge(operator_id)
        except TypeError:
            knowledge = load_operator_term_knowledge()

        lower = answer_text.lower()
        requirements: list = []
        surface_by_term: dict[str, str] = {}
        for term_id, entry in catalog.items():
            if not entry.is_safe_to_teach():
                continue
            for surface in [entry.canonical_surface, *(entry.aliases or [])]:
                if surface and re.search(r"\b" + re.escape(surface.lower()) + r"\b", lower):
                    requirements.append(TermRequirement(
                        term_id=term_id, preferred_surface=surface, necessity="required",
                        supporting_fact_ids=[], plain_replacement=entry.plain_replacement,
                        definition_requested=False,
                    ))
                    surface_by_term[term_id] = surface
                    break
        if not requirements:
            return answer_text, []

        hints = plan_term_teaching(operator_id, requirements, catalog, knowledge)
        out = answer_text
        applied: list = []
        for hint in hints:
            if getattr(hint, "mode", None) not in ("full", "brief"):
                continue
            entry = catalog.get(hint.term_id)
            if entry is None:
                continue
            defn = entry.eli5_full if hint.mode == "full" else entry.eli5_brief
            surface = surface_by_term.get(hint.term_id) or hint.surface_form
            if not (defn and surface):
                continue
            m = re.search(r"\b" + re.escape(surface) + r"\b", out, re.IGNORECASE)
            if m:
                out = out[: m.end()] + f" — {defn}" + out[m.end():]
                applied.append(hint)
        return out, applied
    except Exception:  # noqa: BLE001 — teaching must never break a live answer
        return (answer_text if isinstance(answer_text, str) else ""), []
