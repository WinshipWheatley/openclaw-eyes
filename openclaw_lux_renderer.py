"""Deterministic Velvet/Concierge/Steel renderer for grounded packets."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

from openclaw_terminology_adapter import translate_terms
from quiet_luxury_doctrine import critical_facts_in_text, load_quiet_luxury_contract


@dataclass(frozen=True)
class LuxRenderResult:
    text: str
    target_layer: str
    sections: tuple[str, ...]
    critical_facts: tuple[str, ...]
    severity_integrity_passed: bool

    def machine_proof(self) -> dict[str, Any]:
        return {
            "quiet_luxury_renderer_used": True,
            "quiet_luxury_doctrine_ref": load_quiet_luxury_contract()["doctrine_ref"],
            "quiet_luxury_target_layer": self.target_layer,
            "quiet_luxury_sections": list(self.sections),
            "severity_integrity_passed": self.severity_integrity_passed,
            "critical_facts": list(self.critical_facts),
            "render_sha256": "sha256:" + hashlib.sha256(self.text.encode("utf-8")).hexdigest(),
            "model_call_performed": False,
        }


def _packet_parts(packet: Mapping[str, Any] | str | Any) -> tuple[str, str, tuple[str, ...]]:
    if not isinstance(packet, Mapping):
        value = str(packet or "").strip()
        return value, "Review the grounded detail.", (value,) if value else ()
    summary = str(packet.get("summary") or packet.get("text") or "").strip()
    move = str(packet.get("recommended_move") or "Review the grounded detail.").strip()
    raw_facts = packet.get("facts") or ()
    facts = tuple(
        str(item.get("value") if isinstance(item, Mapping) else item).strip()
        for item in raw_facts
        if str(item.get("value") if isinstance(item, Mapping) else item).strip()
    )
    return summary, move, facts


def render_packet_result(
    packet: Mapping[str, Any] | str | Any,
    *,
    target_agent: str = "maestro",
) -> LuxRenderResult:
    contract = load_quiet_luxury_contract()
    target_layer = "client" if str(target_agent).strip().lower() in {"clara", "client"} else "operator"
    summary, move, facts = _packet_parts(packet)
    raw_blob = json.dumps(packet, sort_keys=True, default=str) if isinstance(packet, Mapping) else str(packet or "")
    critical = critical_facts_in_text(raw_blob)
    translated_summary = translate_terms(summary, target_layer=target_layer, context="operator_brief")
    translated_move = translate_terms(move, target_layer=target_layer, context="operator_brief")
    velvet_parts = [*critical, translated_summary, f"Recommended move: {translated_move}"]
    velvet = " ".join(part for part in velvet_parts if part).strip()
    concierge = "Context stays brief; exact facts and authority remain visible below."
    steel = "; ".join(facts) if facts else "No exact facts were supplied."
    lines = (
        f"Velvet: {velvet}",
        f"Concierge: {concierge}",
        f"Steel: {steel}",
    )
    rendered = "\n".join(lines)
    severity_ok = all(fact in rendered for fact in critical)
    return LuxRenderResult(
        text=rendered,
        target_layer=target_layer,
        sections=tuple(contract["progressive_disclosure"]),
        critical_facts=critical,
        severity_integrity_passed=severity_ok,
    )


def render_packet(packet: Mapping[str, Any] | str | Any, *, target_agent: str = "maestro") -> str:
    return render_packet_result(packet, target_agent=target_agent).text


__all__ = ["LuxRenderResult", "render_packet", "render_packet_result"]
