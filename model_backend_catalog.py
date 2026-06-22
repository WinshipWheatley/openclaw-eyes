"""model_backend_catalog.py — Concrete vendor model catalog for OpenClaw.

Maps abstract model CLASS names from model_selection_policy_contract.py to
concrete vendor model strings, context windows, and availability status as of
2026-06-22.

Design contract:
- READ-ONLY: this catalog stores model names + classes + availability only.
- NEVER stores, echoes, or derives provider API keys.
- NEVER initiates model calls, web scraping, or service starts.
- Integrates as a read-model input to openclaw_hermes_sidecar.py so Hermes
  KNOWS what models the system runs, without switching any production model.
- Availability DEPRECATED / UNAVAILABLE entries are flagged explicitly.

Abstract model classes (from model_selection_policy_contract.py):
  local_small_fast        — private, fast, low-resource local inference
  local_reasoning         — private deeper local reasoning
  local_sensitive         — private/offline for sensitive data
  external_fast_worker    — cheap/fast cloud worker
  external_deep_reasoner  — high-depth cloud reasoning
  external_code_worker    — scoped code/test cloud worker
  external_multimodal     — visual/audio/document cloud worker
  human_operator          — final human authority (not a model)
  blocked_no_model        — safe fail-closed result
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
SCHEMA_VERSION = "model_backend_catalog_v0"
READ_MODEL_ID = "model_backend_catalog"
CATALOG_AS_OF = "2026-06-22"

# ---------------------------------------------------------------------------
# Availability sentinels
# ---------------------------------------------------------------------------

AVAILABLE = "available"
DEPRECATED = "deprecated"
PREVIEW = "preview"
COMING_SOON = "coming_soon"
DISABLED = "disabled"

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelEntry:
    model_id: str
    display_name: str
    vendor: str
    model_class: str          # abstract class from model_selection_policy_contract
    context_window_tokens: int | None
    availability: str         # AVAILABLE / DEPRECATED / PREVIEW / COMING_SOON / DISABLED
    availability_note: str    # human-readable; required for DEPRECATED/DISABLED
    hosting: str              # "cloud" | "local" | "either"
    api_key_required: bool    # True if a provider API key is needed (no key stored here)


@dataclass(frozen=True)
class ModelBackendCatalogResult:
    schema_version: str
    read_model_id: str
    catalog_as_of: str
    generated_at: str
    entry_count: int
    available_count: int
    deprecated_or_disabled_count: int


# ---------------------------------------------------------------------------
# Catalog entries (as of CATALOG_AS_OF)
# ---------------------------------------------------------------------------

MODEL_CATALOG: tuple[ModelEntry, ...] = (
    # -----------------------------------------------------------------------
    # ARCHITECT tier — highest-depth reasoning
    # -----------------------------------------------------------------------
    ModelEntry(
        model_id="gpt-5.5",
        display_name="GPT-5.5",
        vendor="OpenAI",
        model_class="external_deep_reasoner",
        context_window_tokens=None,          # not publicly confirmed
        availability=AVAILABLE,
        availability_note="",
        hosting="cloud",
        api_key_required=True,
    ),
    ModelEntry(
        model_id="claude-opus-4-8",
        display_name="Claude Opus 4.8",
        vendor="Anthropic",
        model_class="external_deep_reasoner",
        context_window_tokens=200_000,
        availability=AVAILABLE,
        availability_note="",
        hosting="cloud",
        api_key_required=True,
    ),

    # -----------------------------------------------------------------------
    # BALANCED tier — quality + speed
    # -----------------------------------------------------------------------
    ModelEntry(
        model_id="claude-sonnet-4-6",
        display_name="Claude Sonnet 4.6",
        vendor="Anthropic",
        model_class="external_fast_worker",
        context_window_tokens=200_000,
        availability=AVAILABLE,
        availability_note="",
        hosting="cloud",
        api_key_required=True,
    ),
    ModelEntry(
        model_id="gemini-3.5-flash",
        display_name="Gemini 3.5 Flash",
        vendor="Google",
        model_class="external_fast_worker",
        context_window_tokens=1_000_000,
        availability=AVAILABLE,
        availability_note="",
        hosting="cloud",
        api_key_required=True,
    ),

    # -----------------------------------------------------------------------
    # WORKER / cheap tier — high-volume / low-cost
    # -----------------------------------------------------------------------
    ModelEntry(
        model_id="gpt-5.4-mini",
        display_name="GPT-5.4 Mini",
        vendor="OpenAI",
        model_class="external_fast_worker",
        context_window_tokens=None,
        availability=AVAILABLE,
        availability_note="",
        hosting="cloud",
        api_key_required=True,
    ),
    ModelEntry(
        model_id="gemini-3.1-flash-lite",
        display_name="Gemini 3.1 Flash-Lite",
        vendor="Google",
        model_class="external_fast_worker",
        context_window_tokens=1_000_000,
        availability=AVAILABLE,
        availability_note="",
        hosting="cloud",
        api_key_required=True,
    ),
    ModelEntry(
        model_id="kimi-k2.6",
        display_name="Kimi K2.6",
        vendor="Moonshot",
        model_class="external_fast_worker",
        context_window_tokens=128_000,
        availability=AVAILABLE,
        availability_note="",
        hosting="cloud",
        api_key_required=True,
    ),
    ModelEntry(
        model_id="minimax-m3",
        display_name="MiniMax M3",
        vendor="MiniMax",
        model_class="external_fast_worker",
        context_window_tokens=None,
        availability=AVAILABLE,
        availability_note="Also available as a local model.",
        hosting="either",
        api_key_required=True,
    ),
    ModelEntry(
        model_id="deepseek-v4-flash",
        display_name="DeepSeek V4 Flash",
        vendor="DeepSeek",
        model_class="external_fast_worker",
        context_window_tokens=128_000,
        availability=AVAILABLE,
        availability_note="",
        hosting="cloud",
        api_key_required=True,
    ),

    # -----------------------------------------------------------------------
    # CODING tier — specialised code generation
    # -----------------------------------------------------------------------
    ModelEntry(
        model_id="kimi-k2.7-code",
        display_name="Kimi K2.7 Code",
        vendor="Moonshot",
        model_class="external_code_worker",
        context_window_tokens=128_000,
        availability=AVAILABLE,
        availability_note="",
        hosting="cloud",
        api_key_required=True,
    ),
    ModelEntry(
        model_id="qwen3-coder",
        display_name="Qwen3-Coder",
        vendor="Alibaba",
        model_class="external_code_worker",
        context_window_tokens=128_000,
        availability=AVAILABLE,
        availability_note="Also available as a local model.",
        hosting="either",
        api_key_required=True,
    ),

    # -----------------------------------------------------------------------
    # LOCAL / private tier — on-device, no cloud exposure
    # -----------------------------------------------------------------------
    ModelEntry(
        model_id="qwen3.6-35b-a3b",
        display_name="Qwen3.6-35B-A3B",
        vendor="Alibaba",
        model_class="local_reasoning",
        context_window_tokens=128_000,
        availability=AVAILABLE,
        availability_note="",
        hosting="local",
        api_key_required=False,
    ),
    ModelEntry(
        model_id="qwen3-coder-local",
        display_name="Qwen3-Coder (local)",
        vendor="Alibaba",
        model_class="local_small_fast",
        context_window_tokens=128_000,
        availability=AVAILABLE,
        availability_note="Same weights as cloud variant; local-hosted for privacy.",
        hosting="local",
        api_key_required=False,
    ),
    ModelEntry(
        model_id="llama-4-scout",
        display_name="Llama 4 Scout",
        vendor="Meta",
        model_class="local_small_fast",
        context_window_tokens=128_000,
        availability=AVAILABLE,
        availability_note="",
        hosting="local",
        api_key_required=False,
    ),
    ModelEntry(
        model_id="llama-4-maverick",
        display_name="Llama 4 Maverick",
        vendor="Meta",
        model_class="local_reasoning",
        context_window_tokens=128_000,
        availability=AVAILABLE,
        availability_note="",
        hosting="local",
        api_key_required=False,
    ),
    ModelEntry(
        model_id="qwen3.6-35b-a3b-sensitive",
        display_name="Qwen3.6-35B-A3B (sensitive posture)",
        vendor="Alibaba",
        model_class="local_sensitive",
        context_window_tokens=128_000,
        availability=AVAILABLE,
        availability_note=(
            "Same weights as qwen3.6-35b-a3b; classified local_sensitive to serve as "
            "the private/offline posture for finance, legal, client, and protected metadata work."
        ),
        hosting="local",
        api_key_required=False,
    ),
    ModelEntry(
        model_id="minimax-m3-local",
        display_name="MiniMax M3 (local)",
        vendor="MiniMax",
        model_class="local_small_fast",
        context_window_tokens=None,
        availability=AVAILABLE,
        availability_note="Local-hosted variant of MiniMax M3.",
        hosting="local",
        api_key_required=False,
    ),
    ModelEntry(
        model_id="minimax-m2.7",
        display_name="MiniMax M2.7",
        vendor="MiniMax",
        model_class="local_small_fast",
        context_window_tokens=None,
        availability=AVAILABLE,
        availability_note="",
        hosting="local",
        api_key_required=False,
    ),
    ModelEntry(
        model_id="nvidia-nemotron-3-ultra",
        display_name="NVIDIA Nemotron 3 Ultra",
        vendor="NVIDIA",
        model_class="local_reasoning",
        context_window_tokens=128_000,
        availability=AVAILABLE,
        availability_note="",
        hosting="local",
        api_key_required=False,
    ),
    ModelEntry(
        model_id="nvidia-nemotron-3-super",
        display_name="NVIDIA Nemotron 3 Super",
        vendor="NVIDIA",
        model_class="local_small_fast",
        context_window_tokens=128_000,
        availability=AVAILABLE,
        availability_note="",
        hosting="local",
        api_key_required=False,
    ),

    # -----------------------------------------------------------------------
    # DEPRECATED / UNAVAILABLE — flagged, must NOT be used
    # -----------------------------------------------------------------------
    ModelEntry(
        model_id="claude-fable-5",
        display_name="Claude Fable 5",
        vendor="Anthropic",
        model_class="external_deep_reasoner",
        context_window_tokens=None,
        availability=DISABLED,
        availability_note=(
            "DISABLED 2026-06-12 by US government directive. "
            "NOT deployable. Do not route any workloads to this model."
        ),
        hosting="cloud",
        api_key_required=True,
    ),
    ModelEntry(
        model_id="gpt-4o",
        display_name="GPT-4o",
        vendor="OpenAI",
        model_class="external_fast_worker",
        context_window_tokens=128_000,
        availability=DEPRECATED,
        availability_note="Deprecated; superseded by GPT-5.x series. Do not use for new workloads.",
        hosting="cloud",
        api_key_required=True,
    ),
    ModelEntry(
        model_id="claude-3-5-sonnet",
        display_name="Claude 3.5 Sonnet",
        vendor="Anthropic",
        model_class="external_fast_worker",
        context_window_tokens=200_000,
        availability=DEPRECATED,
        availability_note="Not current; superseded by Claude Sonnet 4.6.",
        hosting="cloud",
        api_key_required=True,
    ),
    ModelEntry(
        model_id="deepseek-v4",
        display_name="DeepSeek V4",
        vendor="DeepSeek",
        model_class="external_fast_worker",
        context_window_tokens=128_000,
        availability=PREVIEW,
        availability_note="Preview / not production-ready; use DeepSeek V4 Flash instead.",
        hosting="cloud",
        api_key_required=True,
    ),
    ModelEntry(
        model_id="gemini-3.5-pro",
        display_name="Gemini 3.5 Pro",
        vendor="Google",
        model_class="external_deep_reasoner",
        context_window_tokens=None,
        availability=COMING_SOON,
        availability_note="Coming-soon; not yet generally available as of 2026-06-22.",
        hosting="cloud",
        api_key_required=True,
    ),
)


# ---------------------------------------------------------------------------
# Authority boundary — catalog is a read-only data structure
# ---------------------------------------------------------------------------

CATALOG_AUTHORITY = {
    "runtime_authority": False,
    "model_call_authority": False,
    "routing_execution_authority": False,
    "stores_api_keys": False,
    "stores_credentials": False,
    "may_switch_production_model": False,
    "web_scraping_enabled": False,
    "hermes_launch_authority": False,
}


# ---------------------------------------------------------------------------
# Build / export helpers
# ---------------------------------------------------------------------------


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def build_model_backend_catalog(
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build the full catalog payload. Read-only: no model calls, no key access."""
    generated = generated_at or utc_now()
    entries = [_entry_record(e) for e in MODEL_CATALOG]
    available = [e for e in entries if e["availability"] == AVAILABLE]
    deprecated_or_disabled = [
        e for e in entries if e["availability"] in (DEPRECATED, DISABLED)
    ]
    by_class: dict[str, list[str]] = {}
    for entry in entries:
        cls = entry["model_class"]
        by_class.setdefault(cls, []).append(entry["model_id"])

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "catalog_as_of": CATALOG_AS_OF,
        "generated_at": generated,
        **CATALOG_AUTHORITY,
        "summary": {
            "total_entries": len(entries),
            "available_count": len(available),
            "deprecated_or_disabled_count": len(deprecated_or_disabled),
            "model_classes_covered": sorted(by_class.keys()),
        },
        "entries_by_class": {cls: ids for cls, ids in sorted(by_class.items())},
        "entries": entries,
        "deprecated_and_disabled": deprecated_or_disabled,
        "machine_proof": {
            "read_model_only": True,
            "api_keys_stored": False,
            "model_calls_made": False,
            "web_scraping_performed": False,
            "hermes_launched": False,
            "content_hash": "",
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def _entry_record(e: ModelEntry) -> dict[str, Any]:
    return {
        "model_id": e.model_id,
        "display_name": e.display_name,
        "vendor": e.vendor,
        "model_class": e.model_class,
        "context_window_tokens": e.context_window_tokens,
        "availability": e.availability,
        "availability_note": e.availability_note,
        "hosting": e.hosting,
        "api_key_required": e.api_key_required,
        "deployable": e.availability == AVAILABLE,
    }


def export_model_backend_catalog(
    *,
    export_root: str | Path = Path("generated/read_models"),
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> ModelBackendCatalogResult:
    """Write the catalog to generated/read_models/model_backend_catalog.json."""
    payload = build_model_backend_catalog(generated_at=generated_at)
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / "model_backend_catalog.json"
    temp_path = json_path.with_suffix(".json.tmp")
    temp_path.write_text(stable_json(payload), encoding="utf-8")
    temp_path.replace(json_path)
    summary = payload["summary"]
    return ModelBackendCatalogResult(
        schema_version=SCHEMA_VERSION,
        read_model_id=READ_MODEL_ID,
        catalog_as_of=CATALOG_AS_OF,
        generated_at=payload["generated_at"],
        entry_count=summary["total_entries"],
        available_count=summary["available_count"],
        deprecated_or_disabled_count=summary["deprecated_or_disabled_count"],
    )


def get_deployable_models(model_class: str | None = None) -> list[dict[str, Any]]:
    """Return catalog entries that are deployable (availability=available).

    Optionally filtered to a specific abstract model_class.
    READ-ONLY: does not call any model.
    """
    payload = build_model_backend_catalog()
    entries = payload["entries"]
    result = [e for e in entries if e["deployable"]]
    if model_class:
        result = [e for e in result if e["model_class"] == model_class]
    return result


def get_disabled_models() -> list[dict[str, Any]]:
    """Return all disabled / deprecated entries (must NOT be used for routing)."""
    payload = build_model_backend_catalog()
    return payload["deprecated_and_disabled"]


__all__ = [
    "AVAILABLE",
    "CATALOG_AS_OF",
    "CATALOG_AUTHORITY",
    "COMING_SOON",
    "DEPRECATED",
    "DISABLED",
    "MODEL_CATALOG",
    "PREVIEW",
    "READ_MODEL_ID",
    "SCHEMA_VERSION",
    "ModelBackendCatalogResult",
    "ModelEntry",
    "build_model_backend_catalog",
    "export_model_backend_catalog",
    "get_deployable_models",
    "get_disabled_models",
    "stable_json",
]
