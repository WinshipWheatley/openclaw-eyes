"""Typed response disposition shared by local and remote operator surfaces."""

from __future__ import annotations

from typing import Any, Mapping


SCHEMA_VERSION = "operator_response_disposition_v0"


def surface_class_from_request(request: Mapping[str, Any]) -> str:
    origin_values = " ".join(
        str(request.get(key) or "").strip().lower()
        for key in (
            "origin_surface",
            "source_channel",
            "source_surface",
            "lane",
        )
    )
    if "telegram" in origin_values or "maestro_listener" in origin_values:
        return "telegram"
    if "mac" in origin_values or "mission_control" in origin_values:
        return "mac"
    active_surface = str(request.get("active_surface_ref") or "").strip().lower()
    if "telegram" in active_surface:
        return "telegram"
    if "mac" in active_surface or "mission_control" in active_surface:
        return "mac"
    return "pc"


def delivery_mode_for_surface(active_surface: str, *, has_artifact: bool) -> str:
    if not has_artifact:
        return "text"
    return {
        "telegram": "telegram_photo",
        "mac": "mac_quicklook",
        "pc": "pc_rendered_image_path",
    }.get(str(active_surface or "").lower(), "pc_rendered_image_path")


def build_operator_response_disposition(
    *,
    intent: str,
    addressed_agent: str,
    active_surface: str,
    artifact_variant: str,
    artifact: Mapping[str, Any] | None,
) -> dict[str, Any]:
    has_artifact = isinstance(artifact, Mapping)
    delivery_mode = delivery_mode_for_surface(active_surface, has_artifact=has_artifact)
    return {
        "schema_version": SCHEMA_VERSION,
        "intent": str(intent or "").strip(),
        "addressed_agent": str(addressed_agent or "maestro").strip().lower(),
        "active_surface": str(active_surface or "pc").strip().lower(),
        "artifact_variant": str(artifact_variant or "current").strip().lower(),
        "artifact_id": str((artifact or {}).get("artifact_id") or ""),
        "artifact_sha256": str((artifact or {}).get("sha256") or ""),
        "delivery_mode": delivery_mode,
        "voice_mode": (
            "addressed_agent_kokoro_async_words_over_silence"
            if active_surface == "telegram"
            else "surface_native"
        ),
        "receipt_requirements": [
            "source_request_id",
            "selected_artifact_sha256",
            "rendered_image_sha256",
            "effective_bot_identity",
            "delivered_message_id",
            "delivery_timestamp",
        ] if delivery_mode == "telegram_photo" else ["source_request_id", "artifact_sha256"],
        "processor_external_action_performed": False,
    }


__all__ = [
    "SCHEMA_VERSION",
    "build_operator_response_disposition",
    "delivery_mode_for_surface",
    "surface_class_from_request",
]
