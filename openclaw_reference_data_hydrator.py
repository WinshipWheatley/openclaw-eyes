"""Hydrate Winship-confirmed Data Room reference records into safe read models.

This module is intentionally conservative. It only hydrates records that carry
the explicit confirmation fields required by the Data Room review path, and it
blocks or skips records that look provisional, source-less, or sensitive.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STATUS_READY = "OPENCLAW_REFERENCE_DATA_HYDRATION_READY"
STATUS_BLOCKED_NO_CONFIRMED_DATA = "OPENCLAW_REFERENCE_DATA_HYDRATION_BLOCKED_NO_CONFIRMED_DATA"
STATUS_BLOCKED = "OPENCLAW_REFERENCE_DATA_HYDRATION_BLOCKED"

PRIMARY_CONFIRMED_REFERENCE_DATA_PATH = Path(
    "/tmp/openclaw-mission-control/operator_skill_factory_v0/openclaw_confirmed_reference_data_v0.json"
)
DURABLE_CONFIRMED_REFERENCE_DATA_PATH = Path(
    "/home/openclaw/generated/system_knowledge/operator_skill_factory/openclaw_confirmed_reference_data_v0.json"
)
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")

OUTPUT_FILES = {
    "rate_card": "openclaw_reference_rate_card.json",
    "client_roster": "openclaw_reference_client_roster.json",
    "venue_roster": "openclaw_reference_venue_roster.json",
    "expense_categories": "openclaw_reference_expense_categories.json",
    "persona_policy": "openclaw_reference_persona_policy.json",
    "business_identity": "openclaw_reference_business_identity.json",
    "payment_privacy_policy": "openclaw_reference_payment_privacy_policy.json",
    "contact_requirements": "openclaw_reference_contact_requirements.json",
    "skill_context": "openclaw_reference_skill_context.json",
}
MANIFEST_FILE = "openclaw_reference_hydration_manifest.json"

CONFIRMED_REVIEW_STATUS = "confirmed_by_winship"
FORBIDDEN_REVIEW_STATUS_MARKERS = (
    "sleepy",
    "provisional",
    "needs_source",
    "needs_correction",
    "deferred",
)
RAW_SECRET_KEY_MARKERS = (
    "api_key",
    "apikey",
    "password",
    "secret",
    "token",
    "credential",
)
SENSITIVE_TEXT_PATTERNS = (
    re.compile(r"\brouting\s*(?:number|#)?\D{0,20}\d{9}\b", re.IGNORECASE),
    re.compile(r"\baccount\s*(?:number|#)?\D{0,20}\d{6,17}\b", re.IGNORECASE),
    re.compile(r"\b(?:ssn|social security)\D{0,20}\d{3}-?\d{2}-?\d{4}\b", re.IGNORECASE),
    re.compile(r"\b(?:ein|tax\s*id|tax\s*identifier)\D{0,20}\d{2}-?\d{7}\b", re.IGNORECASE),
    re.compile(r"\braw\s+private\s+note\b", re.IGNORECASE),
)

CATEGORY_MUST_NOT = {
    "rate_card": ["do not invent rates"],
    "client_roster": ["do not create contacts or send email"],
    "venue_roster": ["mileage-only locations are not confirmed venues unless promoted"],
    "expense_categories": ["no tax advice", "no deductibility claims"],
    "persona_policy": ["do not use persona for legal/tax/billing identity unless confirmed"],
    "business_identity": ["do not expose home address/phone unless trust policy confirms"],
    "payment_privacy_policy": ["no raw account/routing details"],
    "contact_requirements": ["do not infer emails"],
}

CATEGORY_OWNER_DEFAULTS = {
    "rate_card": ("cassandra", "cassandra_finance"),
    "client_roster": ("cassandra", "cassandra_business"),
    "venue_roster": ("cassandra", "cassandra_business"),
    "expense_categories": ("cassandra", "cassandra_finance"),
    "persona_policy": ("chief", "chief_identity"),
    "business_identity": ("cassandra", "cassandra_business"),
    "payment_privacy_policy": ("cassandra", "cassandra_finance"),
    "contact_requirements": ("cassandra", "cassandra_business"),
}


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _content_hash(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_stable_json(payload), encoding="utf-8")


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, set):
        return sorted(value)
    if value == "":
        return []
    return [value]


def _as_text_list(value: Any) -> list[str]:
    return [str(item) for item in _as_list(value) if str(item).strip()]


def _first_value(record: dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return default


def _dedupe_text(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return result


def _source_refs(record: dict[str, Any]) -> list[str]:
    refs: list[Any] = []
    for key in (
        "source_refs",
        "source_ref",
        "source_artifact_refs",
        "source_artifact_ref",
        "source_read_model_refs",
        "source_receipt_refs",
    ):
        refs.extend(_as_list(record.get(key)))
    return _dedupe_text(refs)


def _record_id(record: dict[str, Any], fallback_index: int | None = None) -> str:
    value = _first_value(
        record,
        "source_record_id",
        "record_id",
        "id",
        "reference_id",
        "row_id",
        default="",
    )
    if value:
        return str(value)
    if fallback_index is not None:
        return f"unidentified_record_{fallback_index}"
    return "unidentified_record"


def _category_token(record: dict[str, Any]) -> str:
    token = _first_value(
        record,
        "hydration_category",
        "target_read_model",
        "read_model",
        "category",
        "record_type",
        "type",
        default="",
    )
    return str(token).lower().replace("-", "_").replace(" ", "_")


def _normalize_category(record: dict[str, Any]) -> str | None:
    token = _category_token(record)
    if not token:
        return None
    if "payment_privacy" in token or ("payment" in token and "privacy" in token):
        return "payment_privacy_policy"
    if "business_identity" in token or ("business" in token and "identity" in token):
        return "business_identity"
    if "contact_requirement" in token or ("contact" in token and "requirement" in token):
        return "contact_requirements"
    if "expense" in token:
        return "expense_categories"
    if "persona" in token or ("signature" in token and "identity" in token):
        return "persona_policy"
    if "client" in token or "payer" in token:
        return "client_roster"
    if "venue" in token:
        return "venue_roster"
    if "rate" in token:
        return "rate_card"
    return None


def _contains_sensitive_raw_pattern(value: Any, key_path: tuple[str, ...] = ()) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key).lower()
            if any(marker in key_text for marker in RAW_SECRET_KEY_MARKERS) and child not in (None, "", []):
                return True
            if key_text in {"raw_private_note", "raw_private_notes"} and child not in (None, "", []):
                return True
            if _contains_sensitive_raw_pattern(child, (*key_path, key_text)):
                return True
        return False
    if isinstance(value, list):
        return any(_contains_sensitive_raw_pattern(item, key_path) for item in value)
    if isinstance(value, str):
        return any(pattern.search(value) for pattern in SENSITIVE_TEXT_PATTERNS)
    return False


def _extract_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("records", "confirmed_records", "reference_records", "review_records"):
        records = payload.get(key)
        if isinstance(records, list):
            return [item for item in records if isinstance(item, dict)]
    return []


def load_confirmed_reference_data(
    primary_path: Path | str = PRIMARY_CONFIRMED_REFERENCE_DATA_PATH,
    fallback_path: Path | str = DURABLE_CONFIRMED_REFERENCE_DATA_PATH,
) -> dict[str, Any]:
    """Load confirmed reference data from the primary path or durable fallback."""

    candidates = [Path(primary_path), Path(fallback_path)]
    for path in candidates:
        if path.exists():
            return {
                "status": "loaded",
                "path": str(path),
                "payload": json.loads(path.read_text(encoding="utf-8")),
            }
    return {
        "status": STATUS_BLOCKED_NO_CONFIRMED_DATA,
        "path": None,
        "payload": None,
        "checked_paths": [str(path) for path in candidates],
    }


def _skip(record: dict[str, Any], reason: str, index: int) -> dict[str, str]:
    return {
        "source_record_id": _record_id(record, index),
        "category": _category_token(record),
        "reason": reason,
    }


def validate_confirmed_records(payload: Any) -> dict[str, Any]:
    """Validate and normalize only confirmed records eligible for hydration."""

    source_records = _extract_records(payload)
    valid_records: list[dict[str, Any]] = []
    skipped_records: list[dict[str, str]] = []

    for index, record in enumerate(source_records):
        category_token = _category_token(record)
        review_status = str(record.get("review_status", "")).lower()

        if category_token == "do_not_import" or record.get("do_not_import") is True:
            skipped_records.append(_skip(record, "do_not_import", index))
            continue
        if record.get("authoritative") is not True:
            skipped_records.append(_skip(record, "not_authoritative", index))
            continue
        if str(record.get("provisional_marker", "")).strip() == "*":
            skipped_records.append(_skip(record, "provisional_marker", index))
            continue
        if review_status != CONFIRMED_REVIEW_STATUS:
            reason = "review_status_not_confirmed"
            if any(marker in review_status for marker in FORBIDDEN_REVIEW_STATUS_MARKERS):
                reason = "provisional_review_status"
            skipped_records.append(_skip(record, reason, index))
            continue
        if not record.get("safe_usage_scope"):
            skipped_records.append(_skip(record, "missing_safe_usage_scope", index))
            continue
        if not _source_refs(record):
            skipped_records.append(_skip(record, "missing_source_refs", index))
            continue
        if not _as_text_list(record.get("must_not")):
            skipped_records.append(_skip(record, "missing_must_not", index))
            continue
        if _contains_sensitive_raw_pattern(record):
            skipped_records.append(_skip(record, "sensitive_raw_pattern", index))
            continue

        category = _normalize_category(record)
        if not category:
            skipped_records.append(_skip(record, "unsupported_category", index))
            continue

        normalized = dict(record)
        normalized["_source_record_id"] = _record_id(record, index)
        normalized["_hydration_category"] = category
        normalized["_source_refs"] = _source_refs(record)
        valid_records.append(normalized)

    skipped_counts = dict(sorted(Counter(item["reason"] for item in skipped_records).items()))
    category_counts = dict(sorted(Counter(item["_hydration_category"] for item in valid_records).items()))
    return {
        "source_record_count": len(source_records),
        "valid_records": valid_records,
        "hydrated_record_count": len(valid_records),
        "hydrated_counts_by_category": category_counts,
        "skipped_records": skipped_records,
        "skipped_record_count": len(skipped_records),
        "skipped_counts_by_reason": skipped_counts,
    }


def _common_record(record: dict[str, Any], hydrated_at_utc: str) -> dict[str, Any]:
    category = record["_hydration_category"]
    owner_agent, owner_lane = CATEGORY_OWNER_DEFAULTS.get(category, ("openclaw", "reference_data"))
    source_refs = record["_source_refs"]
    must_not = _dedupe_text(_as_text_list(record.get("must_not")) + CATEGORY_MUST_NOT.get(category, []))
    return {
        "source_record_id": record["_source_record_id"],
        "confirmed_at_utc": str(
            _first_value(record, "confirmed_at_utc", "confirmed_at", "reviewed_at_utc", "updated_at_utc", default="")
        ),
        "hydrated_at_utc": hydrated_at_utc,
        "source_artifact_ref": source_refs[0],
        "source_refs": source_refs,
        "confidence": _first_value(record, "confidence", "confidence_class", default="confirmed"),
        "safe_usage_scope": record.get("safe_usage_scope"),
        "owner_agent": _first_value(record, "owner_agent", default=owner_agent),
        "owner_lane": _first_value(record, "owner_lane", default=owner_lane),
        "allowed_uses": _as_text_list(record.get("allowed_uses")),
        "must_not": must_not,
        "review_status": "hydrated_from_confirmed_reference",
        "authoritative": True,
        "runtime_mutation_performed": False,
        "external_calls_performed": False,
    }


def _hydrate_rate_card(record: dict[str, Any], hydrated_at_utc: str) -> dict[str, Any]:
    item = _common_record(record, hydrated_at_utc)
    item.update(
        {
            "service": _first_value(record, "service", "service_name", "label"),
            "default_rate": _first_value(record, "default_rate", "rate", "amount"),
            "rate_type": _first_value(record, "rate_type", "unit", default=""),
            "currency": _first_value(record, "currency", default="USD"),
            "quote_ready": bool(record.get("quote_ready", False)),
            "planning_estimate": bool(record.get("planning_estimate", False)),
        }
    )
    return item


def _hydrate_client_roster(record: dict[str, Any], hydrated_at_utc: str) -> dict[str, Any]:
    item = _common_record(record, hydrated_at_utc)
    item.update(
        {
            "canonical_name": _first_value(record, "canonical_name", "client", "payer", "name"),
            "aliases": _as_text_list(record.get("aliases")),
            "billing_email": _first_value(record, "billing_email", default=""),
            "contact_names": _as_text_list(record.get("contact_names")),
            "terms": _first_value(record, "terms", "payment_terms", default=""),
            "portal_or_coupa": _first_value(record, "portal_or_coupa", "portal", default=""),
            "usual_services": _as_text_list(record.get("usual_services")),
            "trust_tier": _first_value(record, "trust_tier", default=""),
        }
    )
    return item


def _hydrate_venue_roster(record: dict[str, Any], hydrated_at_utc: str) -> dict[str, Any]:
    item = _common_record(record, hydrated_at_utc)
    item.update(
        {
            "venue": _first_value(record, "venue", "venue_name", "name"),
            "payer_or_client": _first_value(record, "payer_or_client", "client", "payer", default=""),
            "typical_service": _first_value(record, "typical_service", "service", default=""),
            "usual_rate": _first_value(record, "usual_rate", "rate", default=""),
            "venue_status": _first_value(record, "venue_status", "status", default=""),
        }
    )
    return item


def _hydrate_expense_categories(record: dict[str, Any], hydrated_at_utc: str) -> dict[str, Any]:
    item = _common_record(record, hydrated_at_utc)
    item.update(
        {
            "category_label": _first_value(record, "category_label", "label", "name"),
            "examples": _as_text_list(record.get("examples")),
            "tax_tag_label_only": _first_value(record, "tax_tag_label_only", default=""),
            "cpa_review_recommended": bool(record.get("cpa_review_recommended", True)),
            "tax_advice_given": False,
        }
    )
    return item


def _hydrate_persona_policy(record: dict[str, Any], hydrated_at_utc: str) -> dict[str, Any]:
    item = _common_record(record, hydrated_at_utc)
    item.update(
        {
            "identity": _first_value(record, "identity", "persona", "name"),
            "public_facing": bool(record.get("public_facing", False)),
            "allowed_contexts": _as_text_list(record.get("allowed_contexts")),
            "prohibited_contexts": _as_text_list(record.get("prohibited_contexts")),
            "signature_rules": _first_value(record, "signature_rules", default=""),
            "from_name_rules": _first_value(record, "from_name_rules", default=""),
            "legal_review_recommended": bool(record.get("legal_review_recommended", False)),
        }
    )
    return item


def _hydrate_business_identity(record: dict[str, Any], hydrated_at_utc: str) -> dict[str, Any]:
    item = _common_record(record, hydrated_at_utc)
    item.update(
        {
            "business_name": _first_value(record, "business_name", "name"),
            "invoice_from_name": _first_value(record, "invoice_from_name", default=""),
            "legal_payee_name": _first_value(record, "legal_payee_name", "payee_name", default=""),
            "public_email": _first_value(record, "public_email", default=""),
            "website": _first_value(record, "website", default=""),
            "invoice_terms": _first_value(record, "invoice_terms", default=""),
            "invoice_numbering_policy": _first_value(record, "invoice_numbering_policy", default=""),
        }
    )
    return item


def _hydrate_payment_privacy_policy(record: dict[str, Any], hydrated_at_utc: str) -> dict[str, Any]:
    item = _common_record(record, hydrated_at_utc)
    item.update(
        {
            "zelle_policy": _first_value(record, "zelle_policy", default=""),
            "direct_deposit_policy": _first_value(record, "direct_deposit_policy", default=""),
            "address_policy": _first_value(record, "address_policy", default=""),
            "phone_policy": _first_value(record, "phone_policy", default=""),
            "trust_tiers": _as_text_list(record.get("trust_tiers")),
            "raw_account_routing_imported": False,
        }
    )
    return item


def _hydrate_contact_requirements(record: dict[str, Any], hydrated_at_utc: str) -> dict[str, Any]:
    item = _common_record(record, hydrated_at_utc)
    item.update(
        {
            "account_client": _first_value(record, "account_client", "client", "account", default=""),
            "needed_contacts": _as_text_list(record.get("needed_contacts")),
            "known_contacts": _as_text_list(record.get("known_contacts")),
            "missing_fields": _as_text_list(record.get("missing_fields")),
        }
    )
    return item


HYDRATORS = {
    "rate_card": _hydrate_rate_card,
    "client_roster": _hydrate_client_roster,
    "venue_roster": _hydrate_venue_roster,
    "expense_categories": _hydrate_expense_categories,
    "persona_policy": _hydrate_persona_policy,
    "business_identity": _hydrate_business_identity,
    "payment_privacy_policy": _hydrate_payment_privacy_policy,
    "contact_requirements": _hydrate_contact_requirements,
}


def _read_model_ref(filename: str) -> str:
    return f"generated/read_models/{filename}"


def _build_category_read_model(category: str, records: list[dict[str, Any]], generated_at_utc: str) -> dict[str, Any]:
    return {
        "schema_version": f"openclaw_reference_{category}_v0",
        "generated_at_utc": generated_at_utc,
        "read_model": f"openclaw_reference_{category}",
        "source": "winship_confirmed_data_room_reference_records",
        "record_count": len(records),
        "records": sorted(records, key=lambda item: item["source_record_id"]),
        "runtime_mutation_performed": False,
        "external_calls_performed": False,
        "raw_sensitive_values_imported": False,
    }


def _build_skill_context(read_models: dict[str, dict[str, Any]], generated_at_utc: str) -> dict[str, Any]:
    refs_by_category = {
        category: _read_model_ref(filename)
        for category, filename in OUTPUT_FILES.items()
        if category != "skill_context"
    }
    contexts = {
        "income_payment_log": {
            "source_read_model_refs": [
                refs_by_category["client_roster"],
                refs_by_category["venue_roster"],
                refs_by_category["business_identity"],
                refs_by_category["payment_privacy_policy"],
            ],
            "allowed_context": "Use confirmed payer, venue, business identity, and privacy policy labels only.",
            "must_not": ["do not mark paid", "do not import raw account/routing details"],
        },
        "expense_log": {
            "source_read_model_refs": [refs_by_category["expense_categories"]],
            "allowed_context": "Use expense labels as tags only.",
            "must_not": ["do not give tax advice", "do not claim deductibility"],
        },
        "gig_event_log": {
            "source_read_model_refs": [refs_by_category["client_roster"], refs_by_category["venue_roster"]],
            "allowed_context": "Use confirmed client and venue labels for local event context.",
            "must_not": ["do not promote mileage-only locations to venues"],
        },
        "identity_signature_preference": {
            "source_read_model_refs": [refs_by_category["persona_policy"], refs_by_category["business_identity"]],
            "allowed_context": "Use confirmed persona and business identity labels.",
            "must_not": ["do not use persona as legal/tax/billing identity unless confirmed"],
        },
        "invoice_action": {
            "source_read_model_refs": [
                refs_by_category["rate_card"],
                refs_by_category["client_roster"],
                refs_by_category["business_identity"],
                refs_by_category["payment_privacy_policy"],
            ],
            "allowed_context": "Use confirmed rate, client, identity, and payment privacy labels.",
            "must_not": ["do not send invoices", "do not create Guardian approvals"],
        },
        "ar_followup": {
            "source_read_model_refs": [refs_by_category["client_roster"], refs_by_category["payment_privacy_policy"]],
            "allowed_context": "Use confirmed client and payment privacy labels for planning.",
            "must_not": ["do not send email", "do not submit through Coupa"],
        },
        "niles_creative_prep": {
            "source_read_model_refs": [refs_by_category["persona_policy"], refs_by_category["venue_roster"]],
            "allowed_context": "Use confirmed creative persona and venue labels when relevant.",
            "must_not": ["do not pull unrelated private finance proof into creative context"],
        },
    }
    return {
        "schema_version": "openclaw_reference_skill_context_v0",
        "generated_at_utc": generated_at_utc,
        "read_model": "openclaw_reference_skill_context",
        "contexts": contexts,
        "source_read_model_refs": sorted(refs_by_category.values()),
        "record_counts_by_category": {
            category: read_models[category]["record_count"]
            for category in OUTPUT_FILES
            if category != "skill_context" and category in read_models
        },
        "runtime_mutation_performed": False,
        "external_calls_performed": False,
        "raw_sensitive_values_imported": False,
    }


def hydrate_reference_read_models(
    valid_records: list[dict[str, Any]],
    read_model_root: Path | str = DEFAULT_READ_MODEL_ROOT,
    hydrated_at_utc: str | None = None,
    write: bool = True,
) -> dict[str, Any]:
    """Build and optionally write deterministic reference read models."""

    generated_at = hydrated_at_utc or _now_utc()
    output_root = Path(read_model_root)
    grouped: dict[str, list[dict[str, Any]]] = {category: [] for category in HYDRATORS}
    for record in valid_records:
        category = record["_hydration_category"]
        grouped[category].append(HYDRATORS[category](record, generated_at))

    read_models: dict[str, dict[str, Any]] = {}
    paths: dict[str, str] = {}
    if not valid_records:
        return {
            "read_models": {},
            "hydrated_read_model_paths": {},
            "hydrated_read_model_hashes": {},
            "hydrated_counts_by_category": {},
        }

    for category in HYDRATORS:
        read_model = _build_category_read_model(category, grouped[category], generated_at)
        read_models[category] = read_model
        path = output_root / OUTPUT_FILES[category]
        paths[category] = str(path)
        if write:
            _write_json(path, read_model)

    skill_context = _build_skill_context(read_models, generated_at)
    read_models["skill_context"] = skill_context
    skill_context_path = output_root / OUTPUT_FILES["skill_context"]
    paths["skill_context"] = str(skill_context_path)
    if write:
        _write_json(skill_context_path, skill_context)

    return {
        "read_models": read_models,
        "hydrated_read_model_paths": paths,
        "hydrated_read_model_hashes": {
            category: _content_hash(read_model) for category, read_model in read_models.items()
        },
        "hydrated_counts_by_category": {
            category: read_models[category]["record_count"] for category in HYDRATORS
        },
    }


def write_hydration_manifest(
    *,
    status: str,
    input_artifact_path: str | None,
    validation: dict[str, Any],
    hydration: dict[str, Any],
    read_model_root: Path | str = DEFAULT_READ_MODEL_ROOT,
    hydrated_at_utc: str | None = None,
    checked_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Write the hydration manifest, including blocked/no-data states."""

    generated_at = hydrated_at_utc or _now_utc()
    output_root = Path(read_model_root)
    manifest_path = output_root / MANIFEST_FILE
    manifest = {
        "schema_version": "openclaw_reference_hydration_manifest_v0",
        "status": status,
        "generated_at_utc": generated_at,
        "input_artifact_path": input_artifact_path,
        "checked_input_paths": checked_paths or [],
        "source_record_count": validation.get("source_record_count", 0),
        "hydrated_record_count": validation.get("hydrated_record_count", 0),
        "skipped_record_count": validation.get("skipped_record_count", 0),
        "hydrated_counts_by_category": validation.get("hydrated_counts_by_category", {}),
        "skipped_counts_by_reason": validation.get("skipped_counts_by_reason", {}),
        "skipped_records": validation.get("skipped_records", []),
        "hydrated_read_model_paths": hydration.get("hydrated_read_model_paths", {}),
        "hydrated_read_model_hashes": hydration.get("hydrated_read_model_hashes", {}),
        "runtime_mutation_performed": False,
        "external_calls_performed": False,
        "email_accessed": False,
        "gmail_accessed": False,
        "coupa_accessed": False,
        "ledger_mutated": False,
        "workbook_mutated": False,
        "pdf_exported": False,
        "paid_marking_performed": False,
        "guardian_approval_created": False,
        "tax_advice_given": False,
        "legal_advice_given": False,
        "raw_sensitive_values_imported": False,
    }
    manifest["content_hash"] = _content_hash({k: v for k, v in manifest.items() if k != "content_hash"})
    _write_json(manifest_path, manifest)
    return {"manifest": manifest, "manifest_path": str(manifest_path)}


def run_hydration_once(
    *,
    primary_path: Path | str = PRIMARY_CONFIRMED_REFERENCE_DATA_PATH,
    fallback_path: Path | str = DURABLE_CONFIRMED_REFERENCE_DATA_PATH,
    read_model_root: Path | str = DEFAULT_READ_MODEL_ROOT,
    hydrated_at_utc: str | None = None,
) -> dict[str, Any]:
    """Run one safe reference-data hydration pass."""

    generated_at = hydrated_at_utc or _now_utc()
    loaded = load_confirmed_reference_data(primary_path=primary_path, fallback_path=fallback_path)
    if loaded["status"] == STATUS_BLOCKED_NO_CONFIRMED_DATA:
        validation = {
            "source_record_count": 0,
            "valid_records": [],
            "hydrated_record_count": 0,
            "hydrated_counts_by_category": {},
            "skipped_records": [],
            "skipped_record_count": 0,
            "skipped_counts_by_reason": {"missing_confirmed_input": 1},
        }
        hydration = {
            "read_models": {},
            "hydrated_read_model_paths": {},
            "hydrated_read_model_hashes": {},
            "hydrated_counts_by_category": {},
        }
        manifest_result = write_hydration_manifest(
            status=STATUS_BLOCKED_NO_CONFIRMED_DATA,
            input_artifact_path=None,
            validation=validation,
            hydration=hydration,
            read_model_root=read_model_root,
            hydrated_at_utc=generated_at,
            checked_paths=loaded.get("checked_paths", []),
        )
        return {
            "status": STATUS_BLOCKED_NO_CONFIRMED_DATA,
            "input_artifact_path": None,
            "checked_input_paths": loaded.get("checked_paths", []),
            "validation": validation,
            "hydration": hydration,
            **manifest_result,
        }

    validation = validate_confirmed_records(loaded["payload"])
    status = STATUS_READY if validation["hydrated_record_count"] else STATUS_BLOCKED
    hydration = hydrate_reference_read_models(
        validation["valid_records"],
        read_model_root=read_model_root,
        hydrated_at_utc=generated_at,
        write=bool(validation["hydrated_record_count"]),
    )
    manifest_result = write_hydration_manifest(
        status=status,
        input_artifact_path=loaded["path"],
        validation=validation,
        hydration=hydration,
        read_model_root=read_model_root,
        hydrated_at_utc=generated_at,
        checked_paths=[str(primary_path), str(fallback_path)],
    )
    return {
        "status": status,
        "input_artifact_path": loaded["path"],
        "checked_input_paths": [str(primary_path), str(fallback_path)],
        "validation": validation,
        "hydration": hydration,
        **manifest_result,
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Hydrate confirmed OpenClaw reference data.")
    parser.add_argument("--primary-path", default=str(PRIMARY_CONFIRMED_REFERENCE_DATA_PATH))
    parser.add_argument("--fallback-path", default=str(DURABLE_CONFIRMED_REFERENCE_DATA_PATH))
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--format", choices=("json", "text"), default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    result = run_hydration_once(
        primary_path=args.primary_path,
        fallback_path=args.fallback_path,
        read_model_root=args.read_model_root,
    )
    if args.format == "json":
        print(_stable_json(result), end="")
    else:
        print(result["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
