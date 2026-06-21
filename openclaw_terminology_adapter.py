"""Quiet Luxury terminology adapter.

This module is intentionally deterministic.  The editable vocabulary lives in
``generated/read_models/quiet_luxury_terms.json`` so adding a phrase does not
require code changes.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parent
DEFAULT_TERMINOLOGY_PATH = ROOT / "generated/read_models/quiet_luxury_terms.json"
SCHEMA_VERSION = "quiet_luxury_terms_v0"
READ_MODEL_ID = "quiet_luxury_terms"

MONEY_RE = re.compile(r"(?<![\w])\$\s*\d[\d,]*(?:\.\d{2})?")
TARGET_LAYER_ALIASES = {
    "maestro": "maestro_layer",
    "maestro_layer": "maestro_layer",
    "internal": "maestro_layer",
    "operator": "maestro_layer",
    "client": "client_layer",
    "clara": "client_layer",
    "external": "client_layer",
    "client_layer": "client_layer",
    "machine": "machine_code",
    "machine_code": "machine_code",
}


def _stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)


def normalize_target_layer(target_layer: str | None) -> str:
    raw = str(target_layer or "maestro_layer").strip().lower()
    return TARGET_LAYER_ALIASES.get(raw, raw if raw.endswith("_layer") else "maestro_layer")


@lru_cache(maxsize=16)
def load_terminology(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path is not None else DEFAULT_TERMINOLOGY_PATH
    with target.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    if payload.get("read_model_id") != READ_MODEL_ID:
        raise ValueError(f"Unexpected terminology read_model_id: {payload.get('read_model_id')!r}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"Unexpected terminology schema_version: {payload.get('schema_version')!r}")
    return payload


def terminology_rows(path: str | Path | None = None) -> tuple[Mapping[str, Any], ...]:
    payload = load_terminology(path)
    rows = payload.get("terms")
    if not isinstance(rows, list):
        raise ValueError("quiet_luxury_terms.json must contain a terms list")
    return tuple(row for row in rows if isinstance(row, Mapping))


def _aliases_for(row: Mapping[str, Any]) -> tuple[str, ...]:
    aliases: list[str] = []
    machine_code = str(row.get("machine_code") or "").strip()
    if machine_code:
        aliases.append(machine_code)
    raw_aliases = row.get("aliases")
    if isinstance(raw_aliases, Sequence) and not isinstance(raw_aliases, (str, bytes, bytearray)):
        aliases.extend(str(item).strip() for item in raw_aliases if str(item).strip())
    return tuple(dict.fromkeys(aliases))


def _replacement_for(row: Mapping[str, Any], target_layer: str) -> str:
    machine_code = str(row.get("machine_code") or "").strip()
    if target_layer == "machine_code":
        return machine_code
    replacement = str(row.get(target_layer) or "").strip()
    if not replacement:
        replacement = machine_code
    if row.get("severity_locked") is True and machine_code and machine_code not in replacement:
        return f"{machine_code}: {replacement}"
    return replacement


def _replace_alias(text: str, alias: str, replacement: str) -> str:
    if not alias or alias == replacement:
        return text
    if re.fullmatch(r"[A-Z0-9_]+", alias):
        return re.sub(rf"\b{re.escape(alias)}\b", replacement, text)
    return text.replace(alias, replacement)


def _apply_money_policy(text: str, payload: Mapping[str, Any]) -> str:
    if "Project investment:" in text and "Total price:" in text:
        return text
    money_policy = payload.get("money_policy") if isinstance(payload.get("money_policy"), Mapping) else {}
    template = str(
        money_policy.get("dual_label_template")
        or "Project investment: {amount} / Total price: {amount}"
    )

    def repl(match: re.Match[str]) -> str:
        amount = match.group(0).replace("$ ", "$")
        return template.format(amount=amount)

    return MONEY_RE.sub(repl, text)


def translate_terms(raw_text: Any, target_layer: str = "maestro_layer", *, terminology_path: str | Path | None = None) -> str:
    """Translate known machine terms and money amounts for the requested layer."""

    if raw_text is None:
        return ""
    text = raw_text if isinstance(raw_text, str) else _stable_json(raw_text)
    payload = load_terminology(terminology_path)
    layer = normalize_target_layer(target_layer)
    result = str(text)
    for row in terminology_rows(terminology_path):
        replacement = _replacement_for(row, layer)
        for alias in _aliases_for(row):
            result = _replace_alias(result, alias, replacement)
    return _apply_money_policy(result, payload)


__all__ = [
    "DEFAULT_TERMINOLOGY_PATH",
    "READ_MODEL_ID",
    "SCHEMA_VERSION",
    "load_terminology",
    "normalize_target_layer",
    "terminology_rows",
    "translate_terms",
]
