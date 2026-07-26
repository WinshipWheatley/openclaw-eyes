"""Question-relevant grounding for Niles.

Niles owns real knowledge — a gear KB covering the X32 rack, DriveRack, stage
box, MIDI controllers, and the studio software stack (Logic Pro X, Ableton
Live, TH-U, MainStage) — plus the shared read-model library. None of it was
reachable when answering a question: the listener only had a status renderer,
a subprocess intake parser, and introspection.

This selects the relevant slice of both, deterministically (harness-owned
token match, never a model guess), and returns "" when nothing is relevant so
an unrelated question pulls no noise into the prompt.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import read_model_demand_index
from read_model_demand_index import age_label

DEFAULT_GEAR_LIMIT = 4


def _gear_devices() -> tuple[Any, ...]:
    try:
        from niles_rig_kb import seed_devices

        return tuple(seed_devices())
    except Exception:
        return ()


def _software_context_lines() -> tuple[str, ...]:
    """The studio software stack Niles is expected to reason about."""

    try:
        from niles_rig_kb import x32_control_summary_lines

        return tuple(x32_control_summary_lines())
    except Exception:
        return ()


def _device_text(device: Any) -> str:
    fields = (
        "device_id",
        "category",
        "manufacturer",
        "model_name",
        "role",
        "gig_role",
        "control_surface",
        "notes",
    )
    return " ".join(str(getattr(device, name, "") or "") for name in fields)


def _device_line(device: Any) -> str:
    ident = str(getattr(device, "device_id", "") or "").strip()
    maker = str(getattr(device, "manufacturer", "") or "").strip()
    model = str(getattr(device, "model_name", "") or "").strip()
    role = str(getattr(device, "role", "") or "").strip()
    control = str(getattr(device, "control_surface", "") or "").strip()
    head = " ".join(part for part in (maker, model) if part) or ident
    detail = "; ".join(part for part in (role, control) if part)
    return f"- {ident}: {head}" + (f" — {detail}" if detail else "")


def select_gear_context(
    question: str, *, limit: int = DEFAULT_GEAR_LIMIT
) -> tuple[str, ...]:
    """Gear/software lines relevant to ``question``; ``()`` when none are."""

    tokens = read_model_demand_index._tokenize(question)
    if not tokens:
        return ()
    scored: list[tuple[int, str, str]] = []
    for device in _gear_devices():
        overlap = len(tokens & read_model_demand_index._tokenize(_device_text(device)))
        if overlap:
            ident = str(getattr(device, "device_id", "") or "")
            scored.append((overlap, ident, _device_line(device)))
    lines = [line for _, _, line in sorted(scored, key=lambda item: (-item[0], item[1]))]

    for summary in _software_context_lines():
        if tokens & read_model_demand_index._tokenize(summary):
            lines.append(f"- {summary}")

    return tuple(lines[:limit])


NILES_SYSTEM_PROMPT = (
    "You are Niles, Winship's studio and live-rig producer agent. You know his "
    "gear and his software stack (Logic Pro X, Ableton Live, TH-U, MainStage, "
    "the X32 rack and his MIDI controllers). Answer only from the knowledge "
    "given below. If it does not cover the question, say plainly what you do "
    "not know instead of guessing. Be concise and practical."
)


def _default_model_call(prompt: str) -> str:
    from adaptive_model_call import adaptive_ollama_text

    return adaptive_ollama_text(prompt, timeout=90, task_class="niles_user_reply")


def answer_with_grounding(
    question: str,
    *,
    model_call: Any = None,
    read_model_root: str | Path = Path("generated/read_models"),
) -> str | None:
    """Answer ``question`` from Niles' own knowledge, or return ``None``.

    Returns ``None`` — never a guess — when nothing relevant is known or the
    model fails, so the caller keeps its existing honest fallback.
    """

    try:
        grounding = str(
            niles_engine_packet(question, read_model_root=read_model_root).get(
                "packet_text"
            )
            or ""
        ).strip()
    except Exception:
        # A packet failure must never leave Niles less grounded than before.
        grounding = build_niles_grounding(question, read_model_root=read_model_root)
    if not grounding:
        return None
    prompt = (
        f"{NILES_SYSTEM_PROMPT}\n\n"
        f"What you know:\n{grounding}\n\n"
        f"User: {question}\n"
        f"Niles:"
    )
    caller = model_call or _default_model_call
    try:
        reply = caller(prompt)
    except Exception:
        return None
    reply = str(reply or "").strip()
    return reply or None


def niles_engine_packet(
    question: str,
    *,
    read_model_root: str | Path = Path("generated/read_models"),
) -> dict:
    """Build Niles' packet through the shared engine.

    Niles had no packet builder at all, so the engine — persona, build receipt,
    dankness scoring — could never wrap it. This puts Niles on the same path as
    every other agent.
    """
    from niles_context_packet import build_niles_context_packet
    from packet_engine import build_agent_packet

    return build_agent_packet(
        agent="niles",
        question=question,
        legacy_builder=build_niles_context_packet,
        read_model_root=read_model_root,
    )


def build_niles_grounding(
    question: str,
    *,
    read_model_root: str | Path = Path("generated/read_models"),
) -> str:
    """Gear knowledge plus question-relevant read-models. ``""`` when nothing fits."""

    sections: list[str] = []

    gear = select_gear_context(question)
    if gear:
        sections.append("Relevant rig/software:\n" + "\n".join(gear))

    selection = read_model_demand_index.select_demand_read_models(
        read_model_root, question=question
    )
    if selection.rows and not selection.error:
        import json as _json

        rows: list[str] = []
        for row in selection.rows:
            path = Path(read_model_root) / row.relative_path
            try:
                payload = _json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            rows.append(
                f"- {row.id}{age_label(row)}: "
                f"{_json.dumps(payload, sort_keys=True)[:900]}"
            )
        if rows:
            sections.append("Question-relevant read-models:\n" + "\n".join(rows))

    return "\n\n".join(sections)


# Producer intake is a routing parser: it recognises production intents and
# otherwise reports it could not route. Those replies are where Niles used to
# dead-end on real rig/software questions it actually has knowledge for, so
# they get one grounded retry from its own gear KB + read-models.
INTAKE_UNROUTED_MARKERS = (
    "didn't return a usable routing decision",
    "did not return a usable routing decision",
    "Producer returned no output",
)


def intake_failed_to_route(result: str) -> bool:
    text = str(result or "")
    return any(marker in text for marker in INTAKE_UNROUTED_MARKERS)


def apply_grounded_fallback(result: str, question: str, **kwargs: Any) -> str:
    """Retry an unroutable intake reply from Niles' own knowledge.

    Strictly an upgrade of a dead end: a routed reply is never replaced, and
    with no relevant knowledge (or on model failure) the original honest reply
    is returned untouched.
    """
    if not intake_failed_to_route(result):
        return result
    try:
        grounded = answer_with_grounding(question, **kwargs)
    except Exception:
        return result
    return grounded or result
