"""Niles X32 lane capability — deterministic intake routing (trust-tier-1).

Bridges the producer intake to the salvaged X32 slice: an input list becomes a
reviewable .scn show profile (showprofile), the scene corpus can be analyzed
read-only (scene_corpus), and setup asks get topology-grounded guidance.

Authority boundary (openclaw_estate_topology_registry, niles_live_engineer_x32):
emulator verification comes before live rack control — so this module NEVER
opens a socket. ``controller_factory``/``allow_network`` exist only so a future
tier-graduated caller can pass an emulator-verified controller explicitly.
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any, Callable

from showprofile import build_scene, parse_input_list

X32_OSC_PORT = 10023  # X32/M32 OSC protocol port (specs/niles-music)
DEFAULT_SHOW_PROFILE_DIR = Path("generated/producer/show_profiles")
DEFAULT_SCENE_CORPUS_DIR = Path("specs/niles-music/scene_corpus")

_DESK_MARKERS = ("x32", "the desk", "mixer", "soundcheck", "monitor desk")
_SETUP_MARKERS = ("set up", "setup", "prep", "flow", "configure", "get ready", "ready")
_STATUS_MARKERS = ("connected", "status", "online", "reachable", "reach", "check the")
_PROFILE_MARKERS = ("input list", "stage plot", "show profile", "patch list")


def _parsed_channels(text: str) -> list[dict[str, Any]]:
    try:
        return parse_input_list(text)
    except Exception:
        return []


def detect_x32_intent(text: str) -> str | None:
    lowered = " " + str(text or "").lower() + " "
    if any(marker in lowered for marker in _PROFILE_MARKERS):
        return "show_profile"
    channels = _parsed_channels(text)
    if len(channels) >= 3 and any(c.get("category") != "other" for c in channels):
        return "show_profile"
    if "scene corpus" in lowered or "analyze the scenes" in lowered or "foundational profile" in lowered:
        return "scene_corpus"
    has_desk = any(marker in lowered for marker in _DESK_MARKERS)
    if not has_desk:
        return None
    if any(marker in lowered for marker in _STATUS_MARKERS):
        return "x32_status"
    if any(marker in lowered for marker in _SETUP_MARKERS):
        return "x32_setup"
    return None


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")[:32]
    return slug or "show"


def _result(intent: str, reply: str, artifacts: list[str] | None = None) -> dict[str, Any]:
    return {
        "handled": True,
        "intent": intent,
        "reply": reply,
        "artifacts": list(artifacts or []),
        "hardware_gated": True,  # tier-1: planning/files only, never the live rack
    }


def _handle_show_profile(text: str, show_profile_dir: Path) -> dict[str, Any]:
    channels = _parsed_channels(text)
    if len(channels) < 2:
        return _result(
            "show_profile",
            "Niles: Ready to build the show profile — paste the input list "
            "(numbered lines like '1. Kick', '2. Snare Top', one channel per line) "
            "and I'll turn it into a reviewable X32 scene.",
        )
    scene_name = f"Show {time.strftime('%m-%d')}"
    scn_text = build_scene(channels, scene_name=scene_name)
    show_profile_dir.mkdir(parents=True, exist_ok=True)
    out_path = show_profile_dir / f"{_slug(channels[0]['name'])}-{len(channels)}ch-{time.strftime('%Y%m%d-%H%M%S')}.scn"
    out_path.write_text(scn_text, encoding="utf-8")
    by_cat: dict[str, int] = {}
    for c in channels:
        by_cat[c["category"]] = by_cat.get(c["category"], 0) + 1
    flagged = [c["name"] for c in channels if c["category"] == "other"]
    lines = [
        f"Niles: Built the show profile — {len(channels)} channels "
        f"({', '.join(f'{v} {k}' for k, v in sorted(by_cat.items()))}).",
        f"Scene file ready for review: {out_path}",
    ]
    if flagged:
        lines.append(
            "Heads up, these didn't match a known category (no color/icon set): "
            + ", ".join(flagged)
        )
    lines.append(
        "Review it, then we load it at the desk — emulator check first, per the house rule."
    )
    return _result("show_profile", "\n".join(lines), [str(out_path)])


def _handle_scene_corpus(scene_corpus_dir: Path) -> dict[str, Any]:
    scn_files = sorted(scene_corpus_dir.glob("*.scn")) if scene_corpus_dir.is_dir() else []
    if not scn_files:
        return _result(
            "scene_corpus",
            f"Niles: No scene corpus found at {scene_corpus_dir} — drop your legacy "
            ".scn files there and I'll build the foundational profile from them.",
        )
    from scene_corpus import analyze_corpus, to_markdown

    agg = analyze_corpus([str(p) for p in scn_files])
    report = to_markdown(agg, title="X32 corpus foundation")
    out_path = scene_corpus_dir / "corpus_foundation.md"
    out_path.write_text(report, encoding="utf-8")
    return _result(
        "scene_corpus",
        f"Niles: Analyzed {len(scn_files)} scenes into a foundational profile — "
        f"summary at {out_path}.",
        [str(out_path)],
    )


def _handle_setup() -> dict[str, Any]:
    reply = (
        "Niles: X32 flow, here's where we stand.\n"
        f"- Desk talks OSC on port {X32_OSC_PORT}; the controller and fake are installed and test-verified.\n"
        "- What I can do right now: turn an input list or stage plot into a reviewable .scn show "
        "profile (icons + house color standard), and analyze your legacy scene corpus into a "
        "foundational profile.\n"
        "- Live rack control is gated until we do the emulator-verified session at the desk "
        "(house rule: emulator before hardware; I don't touch the real desk on my own).\n"
        "Next safe move: paste the input list for the next show and I'll build the scene."
    )
    return _result("x32_setup", reply)


def _handle_status(allow_network: bool, controller_factory: Callable[..., Any] | None) -> dict[str, Any]:
    if not (allow_network and controller_factory is not None):
        return _result(
            "x32_status",
            "Niles: Hardware checks are gated at my trust tier — I don't ping the desk "
            "on my own. The emulator path is ready any time "
            "(python3 -m unittest tests.test_niles_x32 runs the full fake-verified suite), "
            "and we graduate to the real desk together at the next session.",
        )
    try:
        controller = controller_factory()
        info = controller.xinfo() if hasattr(controller, "xinfo") else "connected"
        return _result("x32_status", f"Niles: Desk is reachable — {info}")
    except Exception as exc:
        return _result("x32_status", f"Niles: Desk not reachable ({type(exc).__name__}). Check power/network at the rack.")


def maybe_handle_x32(
    text: str,
    *,
    show_profile_dir: str | Path | None = None,
    scene_corpus_dir: str | Path | None = None,
    controller_factory: Callable[..., Any] | None = None,
    allow_network: bool = False,
) -> dict[str, Any] | None:
    """Detect + handle an X32-lane ask. Returns None (fail-open to the legacy
    producer path) when the ask isn't X32 or anything errors."""
    try:
        intent = detect_x32_intent(text)
        if intent is None:
            return None
        if intent == "show_profile":
            base = Path(show_profile_dir or os.environ.get("NILES_SHOW_PROFILE_DIR", "") or DEFAULT_SHOW_PROFILE_DIR)
            return _handle_show_profile(text, base)
        if intent == "scene_corpus":
            base = Path(scene_corpus_dir or os.environ.get("NILES_SCENE_CORPUS_DIR", "") or DEFAULT_SCENE_CORPUS_DIR)
            return _handle_scene_corpus(base)
        if intent == "x32_status":
            return _handle_status(allow_network, controller_factory)
        return _handle_setup()
    except Exception:
        return None


__all__ = ["detect_x32_intent", "maybe_handle_x32", "X32_OSC_PORT"]
