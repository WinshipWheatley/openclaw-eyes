"""Context-sensitive terminology adapter for the Quiet Luxury doctrine."""

from __future__ import annotations

import re
from typing import Any

from quiet_luxury_doctrine import load_quiet_luxury_contract


MONEY_RE = re.compile(r"(?<![\w])\$\s*\d[\d,]*(?:\.\d{2})?")
TARGET_ALIASES = {
    "maestro": "operator_layer",
    "operator": "operator_layer",
    "operator_layer": "operator_layer",
    "clara": "client_layer",
    "client": "client_layer",
    "external": "client_layer",
    "client_layer": "client_layer",
    "machine": "machine_code",
    "machine_code": "machine_code",
}


def normalize_target_layer(target_layer: str | None) -> str:
    return TARGET_ALIASES.get(str(target_layer or "operator").strip().lower(), "operator_layer")


def _replace_exact_code(text: str, code: str, replacement: str) -> str:
    return re.sub(rf"\b{re.escape(code)}\b", replacement, text)


def _translate_money(text: str, *, context: str, terminology: dict[str, Any]) -> str:
    if context not in terminology["money_dual_label_contexts"]:
        return text
    if "Project investment:" in text and "Total price:" in text:
        return text
    template = str(terminology["money_dual_label_template"])

    def replace(match: re.Match[str]) -> str:
        amount = match.group(0).replace("$ ", "$")
        return template.format(amount=amount)

    return MONEY_RE.sub(replace, text)


def translate_terms(raw_text: Any, *, target_layer: str = "operator", context: str) -> str:
    text = str(raw_text or "")
    contract = load_quiet_luxury_contract()
    terminology = dict(contract["terminology"])
    layer = normalize_target_layer(target_layer)
    result = text
    for row in terminology["terms"]:
        code = str(row["machine_code"])
        if context not in row["allowed_contexts"] or code not in result:
            continue
        replacement = code if layer == "machine_code" else str(row[layer])
        if row["severity_locked"] and code not in replacement:
            replacement = f"{code}: {replacement}"
        result = _replace_exact_code(result, code, replacement)
    return _translate_money(result, context=context, terminology=terminology)


__all__ = ["normalize_target_layer", "translate_terms"]
