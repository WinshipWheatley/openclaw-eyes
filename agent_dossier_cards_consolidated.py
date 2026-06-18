"""Consolidated agent dossier cards read-model.

This module joins existing OpenClaw agent registries into one read-model for
operator/Mission Control display. It reads deterministic local metadata only.
It does not activate agents, call models, inspect secrets, send messages,
restart services, or grant authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import agent_terrain_awareness_readback_contract as terrain_registry
import agent_voice_profiles
import capability_registry
import openclaw_agent_role_registry as role_registry


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "agent_dossier_cards_consolidated_v0"
READ_MODEL_ID = "agent_dossier_cards_consolidated"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "AGENT_DOSSIER_CARDS_CONSOLIDATED_READY"

SOURCE_READ_MODELS = {
    "agent_lanes": "agent_lanes.json",
    "agent_presence": "agent_presence.json",
    "agent_terrain_awareness": "agent_terrain_awareness_readback_contract.json",
    "agent_role_registry": "openclaw_agent_role_registry.json",
    "agent_voice_profiles": "agent_voice_profiles.json",
}

NO_AUTHORITY_FLAGS = {
    "agent_activation_allowed": False,
    "model_call_allowed": False,
    "tool_execution_allowed": False,
    "service_restart_allowed": False,
    "external_send_allowed": False,
    "runtime_mutation_allowed": False,
    "approval_bypass_allowed": False,
    "secret_access_allowed": False,
    "client_deployment_allowed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _rooted(repo_root: str | Path, path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else Path(repo_root) / path


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _index_by(items: Any, key: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not isinstance(items, list):
        return out
    for item in items:
        if isinstance(item, dict) and item.get(key):
            out[str(item[key])] = item
    return out


def _source_presence(repo_root: Path, read_model_root: Path) -> dict[str, dict[str, Any]]:
    sources: dict[str, dict[str, Any]] = {}
    for source_id, filename in SOURCE_READ_MODELS.items():
        path = read_model_root / filename
        payload = _load_json(path)
        sources[source_id] = {
            "path": path.relative_to(repo_root).as_posix() if path.is_absolute() and path.exists() else f"{DEFAULT_READ_MODEL_ROOT.as_posix()}/{filename}",
            "present": path.is_file(),
            "schema_version": payload.get("schema_version") or payload.get("read_model_version"),
            "read_model_id": payload.get("read_model_id"),
        }
    return sources


def _role_payload(generated_at: str) -> dict[str, Any]:
    return role_registry.build_registry(generated_at=generated_at)


def _voice_payload(generated_at: str) -> dict[str, Any]:
    return agent_voice_profiles.build_read_model(generated_at=generated_at)


def _terrain_payload(repo_root: Path, generated_at: str) -> dict[str, Any]:
    return terrain_registry.build_agent_terrain_awareness_readback_contract(
        repo_root=repo_root,
        generated_at=generated_at,
    )


def _capabilities_by_agent() -> dict[str, list[dict[str, Any]]]:
    by_agent: dict[str, list[dict[str, Any]]] = {}
    for actor_id, actor in capability_registry.REGISTRY.items():
        by_agent[str(actor_id)] = [
            {
                "name": cap.name,
                "domain": cap.domain,
                "description": cap.description,
                "connected": bool(cap.connected),
                "scope": list(cap.scope),
                "caveats": cap.caveats,
            }
            for cap in actor.capabilities
        ]
    return by_agent


def _agent_ids(*indexes: Mapping[str, Any]) -> list[str]:
    ids: set[str] = set()
    for index in indexes:
        ids.update(str(key) for key in index.keys() if key)
    return sorted(ids)


def _default_persona_ref(agent_id: str, repo_root: Path) -> list[str]:
    path = repo_root / ".claude" / "commands" / f"{agent_id}.md"
    return [path.relative_to(repo_root).as_posix()] if path.is_file() else []


def _dedupe(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return sorted({str(value) for value in values if value})


def _display_name(agent_id: str, *records: Mapping[str, Any]) -> str:
    for record in records:
        value = record.get("display_name")
        if value:
            return str(value)
    return agent_id.replace("_", " ").title()


def _card(
    agent_id: str,
    *,
    repo_root: Path,
    role_card: Mapping[str, Any],
    lane: Mapping[str, Any],
    presence: Mapping[str, Any],
    terrain: Mapping[str, Any],
    voice: Mapping[str, Any],
    capabilities: list[dict[str, Any]],
) -> dict[str, Any]:
    doc_links = set(_default_persona_ref(agent_id, repo_root))
    doc_links.update(str(ref) for ref in role_card.get("full_context_refs", []) if ref)
    doc_links.update(str(ref) for ref in terrain.get("proof_refs", []) if ref)
    canonical_files = _dedupe(role_card.get("canonical_files"))
    doc_links.update(canonical_files)

    return {
        "agent_id": agent_id,
        "display_name": _display_name(agent_id, role_card, lane, presence, terrain),
        "behavior": {
            "role_summary": role_card.get("role_summary") or lane.get("role_summary") or terrain.get("plain_english_role") or "",
            "owns": _dedupe(role_card.get("owns")),
            "may_request": _dedupe(role_card.get("may_request")),
            "must_route_through": _dedupe(role_card.get("must_route_through")),
            "must_not": _dedupe(role_card.get("must_not")),
            "safety_boundaries": _dedupe(role_card.get("safety_boundaries")),
            "package_context_summary": role_card.get("package_context_summary", ""),
        },
        "capabilities": {
            "registry": capabilities,
            "known": _dedupe(terrain.get("known_capabilities")),
            "partly_known": _dedupe(terrain.get("partly_known_capabilities")),
            "known_unknowns": _dedupe(terrain.get("known_unknowns")),
            "not_discovered": _dedupe(terrain.get("not_discovered")),
        },
        "voice": {
            "voice_profile_ref": voice.get("voice_profile_ref", ""),
            "default_voice_modes": _dedupe(voice.get("default_voice_modes")),
            "tts_profile": voice.get("tts_profile", {}),
            "speaks_when": _dedupe(voice.get("speaks_when")),
            "must_not_speak_when": _dedupe(voice.get("must_not_speak_when")),
        },
        "lane": {
            "lane_id": lane.get("lane_id") or presence.get("lane_id") or terrain.get("agent_id") or "",
            "lane_label": lane.get("lane_label", ""),
            "status": lane.get("status", ""),
            "authority_level": lane.get("authority_level", ""),
            "allowed_worlds": _dedupe(lane.get("allowed_worlds")),
            "routing_hints": _dedupe(lane.get("routing_hints")),
            "approval_required_for": _dedupe(lane.get("approval_required_for")),
            "receipt_required_for": _dedupe(lane.get("receipt_required_for")),
        },
        "status": {
            "desired_state": presence.get("desired_state", ""),
            "actual_state": presence.get("actual_state", ""),
            "presence_source": presence.get("presence_source", ""),
            "recovery_status": presence.get("recovery_status", ""),
            "readiness_state": terrain.get("readiness_state", ""),
            "confidence_state": terrain.get("confidence_state", ""),
            "current_status": terrain.get("current_status", ""),
            "lane_destiny": terrain.get("lane_destiny", {}),
            "quiet_condition": terrain.get("quiet_condition") or terrain.get("what_would_make_lane_quiet", ""),
        },
        "doc_links": sorted(doc_links),
        "source_refs": {
            "role_card": "openclaw_agent_role_registry.py",
            "lane": "agent_lane_registry.py",
            "capability": "capability_registry.py" if capabilities else "",
            "presence": "agent_presence.py" if presence else "",
            "terrain": "agent_terrain_awareness_readback_contract.py" if terrain else "",
            "voice": "agent_voice_profiles.py" if voice else "",
        },
        "authority_boundary": {
            "role": role_card.get("authority_boundary", {}),
            "voice": voice.get("authority_boundary", {}),
            "terrain": terrain.get("authority_boundary", {}),
            **NO_AUTHORITY_FLAGS,
        },
    }


def build_consolidated_agent_manifest(
    *,
    repo_root: str | Path = ROOT,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    repo = Path(repo_root)
    read_root = _rooted(repo, read_model_root)
    generated_at = generated_at or utc_now()

    lanes_payload = _load_json(read_root / SOURCE_READ_MODELS["agent_lanes"])
    presence_payload = _load_json(read_root / SOURCE_READ_MODELS["agent_presence"])
    roles_payload = _role_payload(generated_at)
    terrain_payload = _terrain_payload(repo, generated_at)
    voice_payload = _voice_payload(generated_at)

    lanes = _index_by(lanes_payload.get("agents"), "agent_id")
    presence = _index_by(presence_payload.get("agents"), "agent_id")
    roles = roles_payload.get("role_cards") if isinstance(roles_payload.get("role_cards"), dict) else {}
    terrain = _index_by(terrain_payload.get("agent_dossier_cards"), "agent_id")
    voices = _index_by(voice_payload.get("profiles"), "speaker_ref")
    capabilities = _capabilities_by_agent()

    ids = _agent_ids(lanes, presence, roles, terrain, voices, capabilities)
    cards = [
        _card(
            agent_id,
            repo_root=repo,
            role_card=roles.get(agent_id, {}),
            lane=lanes.get(agent_id, {}),
            presence=presence.get(agent_id, {}),
            terrain=terrain.get(agent_id, {}),
            voice=voices.get(agent_id, {}),
            capabilities=capabilities.get(agent_id, []),
        )
        for agent_id in ids
    ]

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS,
        "generated_at": generated_at,
        "purpose": "One local read-model for rich per-agent cards: behavior, capabilities, voice, lane, status, and doc links.",
        "agent_count": len(cards),
        "agents": cards,
        "source_read_models": _source_presence(repo, read_root),
        "source_modules": [
            "agent_lane_registry.py",
            "openclaw_agent_role_registry.py",
            "capability_registry.py",
            "agent_presence.py",
            "agent_terrain_awareness_readback_contract.py",
            "agent_voice_profiles.py",
        ],
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
        "machine_proof": {
            "builder": "build_consolidated_agent_manifest",
            "agent_ids": [card["agent_id"] for card in cards],
            "source_count": len(SOURCE_READ_MODELS),
            "model_calls_performed": False,
            "tool_execution_performed": False,
            "services_started_or_restarted": False,
            "external_send_performed": False,
            "secret_files_read": False,
        },
    }
    clone = json.loads(stable_json(payload))
    clone["machine_proof"].pop("content_hash", None)
    payload["machine_proof"]["content_hash"] = "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()
    return payload


def export_consolidated_agent_manifest(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    repo = Path(repo_root)
    root = _rooted(repo, export_root)
    root.mkdir(parents=True, exist_ok=True)
    payload = build_consolidated_agent_manifest(
        repo_root=repo,
        read_model_root=read_model_root,
        generated_at=generated_at,
    )
    path = root / JSON_EXPORT_NAME
    path.write_text(stable_json(payload), encoding="utf-8")
    return {
        "json_path": path.relative_to(repo).as_posix() if path.is_relative_to(repo) else path.as_posix(),
        "agent_count": payload["agent_count"],
        "status": payload["status"],
        "content_hash": payload["machine_proof"]["content_hash"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export consolidated agent dossier cards read-model.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--read-model-root", default=DEFAULT_READ_MODEL_ROOT.as_posix())
    args = parser.parse_args(argv)
    print(stable_json(export_consolidated_agent_manifest(**vars(args))), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
