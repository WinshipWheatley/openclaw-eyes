"""niles_album_access.py — Niles's read-only album accessor (Track A, tier-1).

REUSES chief_album_io (load_all_rows, load_song_md) — does NOT fork album state.
This is the substrate for "load up the first song": it loads the canonical album.csv
and a song's per-row rich-text .md, and offers a deterministic easy-win suggestion.

Tier-1 / advisory_only: READ-ONLY. No writes, no DAW/file actuation, no model calls.
The easy-win heuristic here is a DETERMINISTIC PLACEHOLDER for Niles's future
model-backed judgment (which song best fits the operator's ADD + current energy);
it exposes the full album so that reasoning has the data it needs.
"""
from __future__ import annotations

from typing import Any

import chief_album_io as _album


def _to_int(v: Any, default: int = 0) -> int:
    try:
        return int(float(str(v).strip()))
    except (TypeError, ValueError):
        return default


def _is_done(row: dict) -> bool:
    status = str(row.get("status", "")).strip().lower()
    locked = str(row.get("version_locked", "")).strip().lower() in ("1", "true", "yes", "y")
    return locked or status in ("done", "complete", "released", "final")


def load_album() -> list[dict]:
    """All song rows from the canonical album.csv (read-only, via chief_album_io)."""
    return _album.load_all_rows()


def load_song_doc(song_title: str) -> dict:
    """The per-song rich-text .md (sections) for a song — the song's living memory."""
    return _album.load_song_md(song_title)


def suggest_easy_win() -> dict:
    """Deterministic 'easy win to accommodate ADD' suggestion + the reasoning.

    PLACEHOLDER heuristic (tier-1): among songs not yet done, pick the one with the
    highest completion_pct (closest to a quick finish), tie-broken by having no blocker.
    Returns the chosen song row + a human-readable rationale + the full ranked list so a
    model-backed Niles can override with better judgment.
    """
    rows = load_album()
    candidates = [r for r in rows if not _is_done(r)]
    if not candidates:
        return {"song": None, "reason": "all songs are done/locked", "ranked": []}

    def score(r: dict) -> tuple[int, int]:
        # higher completion first; then prefer rows with no blocker
        return (_to_int(r.get("completion_pct")), 0 if str(r.get("blocker", "")).strip() else 1)

    ranked = sorted(candidates, key=score, reverse=True)
    pick = ranked[0]
    return {
        "song": pick.get("song_title"),
        "completion_pct": pick.get("completion_pct"),
        "reason": (
            f"closest to a quick win ({pick.get('completion_pct')}% done"
            f"{', no blocker' if not str(pick.get('blocker','')).strip() else ''}); "
            "tier-1 deterministic pick — Niles will refine with judgment once model-backed"
        ),
        "song_doc_ref": pick.get("song_doc_ref") or "(no rich-text doc linked yet)",
        "ranked": [r.get("song_title") for r in ranked],
    }
