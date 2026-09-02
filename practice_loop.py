"""Practice loop: repertoire, sessions, confidence, streaks, and a daily plan.

Nothing else in OpenClaw models musicianship; every music module manages projects.
This module is the spine for "become the best musician I can be": what to play
today, what was played, and how sure the operator is of each song.

Deterministic, local-only. No model, no network, no DAW, no audio. The store is a
small SQLite file; every path is injectable so tests never touch the operator's
state. Plans are explainable: each slot carries the reason it was chosen.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

SCHEMA_VERSION = "practice_loop_v0"
READ_MODEL_ID = "practice_plan"
DEFAULT_DB_PATH = Path("/home/openclaw/state/practice/practice.sqlite3")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_TARGETS_PATH = Path("config/practice_targets.v1.json")
DEFAULT_PLAN_MINUTES = 45
MIN_SLOT_MINUTES = 10
MAX_SLOT_MINUTES = 20
TARGET_SLOT_MINUTES = 15
CONFIDENCE_MAX = 5
CONFIDENCE_BUMP_MINUTES = 20
STALE_AFTER_DAYS = 14

# The twelve album titles, copied from chief_album_brain._ALBUM_SONGS so this module
# never imports the album brain and its model client.
ALBUM_SONGS = (
    "1 In A Million", "A Night To Remember", "Blue Weather", "Built By Stars",
    "Can You Feel It", "Count On Your Faith", "I Cry Over Love", "Im Somebody",
    "Kamakazi Of Life", "Slow Me Down", "Ten Fingers", "The Future",
)

AUTHORITY_BOUNDARY = {
    "daw_control_performed": False,
    "audio_file_mutation_performed": False,
    "audio_ingested": False,
    "calendar_write_performed": False,
    "send_performed": False,
    "telegram_send_performed": False,
    "external_model_called": False,
    "ledger_mutation_performed": False,
}

_MIGRATIONS: tuple[tuple[int, str, str], ...] = (
    (
        1,
        "practice store v1",
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_utc TEXT NOT NULL,
            description TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS songs (
            normalized_title TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            tags_json TEXT NOT NULL,
            configurations_json TEXT NOT NULL,
            confidence INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            normalized_title TEXT NOT NULL,
            minutes INTEGER NOT NULL,
            practiced_at_utc_iso TEXT NOT NULL,
            configuration TEXT,
            notes TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT 'cli'
        );
        CREATE INDEX IF NOT EXISTS sessions_by_song ON sessions (normalized_title, practiced_at_utc_iso);
        CREATE TABLE IF NOT EXISTS targets (
            name TEXT PRIMARY KEY,
            description TEXT NOT NULL DEFAULT '',
            target_date_iso TEXT,
            song_count_goal INTEGER
        );
        """,
    ),
)


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat()


def _parse_dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(title or "").lower()).strip()


@dataclass(frozen=True)
class SongStatus:
    title: str
    tags: tuple[str, ...]
    configurations: tuple[str, ...]
    confidence: int
    sessions_count: int
    total_minutes: int
    last_practiced_utc_iso: str | None

    def days_since(self, now: datetime) -> int | None:
        if not self.last_practiced_utc_iso:
            return None
        return max(0, (now.date() - _parse_dt(self.last_practiced_utc_iso).date()).days)


class AmbiguousSong(ValueError):
    def __init__(self, query: str, candidates: list[str]) -> None:
        super().__init__(f"ambiguous song: {query}")
        self.query = query
        self.candidates = candidates


class UnknownSong(KeyError):
    pass


class PracticeStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._migrate()

    def close(self) -> None:
        self._conn.close()

    def _migrate(self) -> None:
        self._conn.executescript(_MIGRATIONS[0][2])
        applied = {row[0] for row in self._conn.execute("SELECT version FROM schema_migrations")}
        for version, description, sql in _MIGRATIONS:
            if version in applied:
                continue
            self._conn.executescript(sql)
            self._conn.execute(
                "INSERT INTO schema_migrations (version, applied_utc, description) VALUES (?, ?, ?)",
                (version, _iso(utc_now()), description),
            )
        self._conn.commit()

    # -- songs ---------------------------------------------------------------------------------

    def add_song(
        self,
        title: str,
        *,
        tags: Iterable[str] = (),
        configurations: Iterable[str] = (),
        confidence: int = 0,
        now: datetime | None = None,
    ) -> SongStatus:
        clean = str(title or "").strip()
        key = normalize_title(clean)
        if not key:
            raise ValueError("song title is required")
        existing = self._conn.execute("SELECT * FROM songs WHERE normalized_title = ?", (key,)).fetchone()
        new_tags = sorted({str(t).strip() for t in tags if str(t).strip()})
        new_configs = sorted({str(c).strip() for c in configurations if str(c).strip()})
        if existing is None:
            self._conn.execute(
                "INSERT INTO songs (normalized_title, title, tags_json, configurations_json, confidence, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (key, clean, json.dumps(new_tags), json.dumps(new_configs), max(0, min(CONFIDENCE_MAX, int(confidence))), _iso(now or utc_now())),
            )
        else:
            merged_tags = sorted(set(json.loads(existing["tags_json"])) | set(new_tags))
            merged_configs = sorted(set(json.loads(existing["configurations_json"])) | set(new_configs))
            self._conn.execute(
                "UPDATE songs SET tags_json = ?, configurations_json = ? WHERE normalized_title = ?",
                (json.dumps(merged_tags), json.dumps(merged_configs), key),
            )
        self._conn.commit()
        return self.song_status(clean)

    def resolve_title(self, query: str) -> str:
        """Exact normalized match first, then a unique prefix or word match; never guess."""
        key = normalize_title(query)
        if not key:
            raise UnknownSong(query)
        rows = self._conn.execute("SELECT normalized_title, title FROM songs ORDER BY title").fetchall()
        exact = [row["title"] for row in rows if row["normalized_title"] == key]
        if exact:
            return exact[0]
        partial = [row["title"] for row in rows if row["normalized_title"].startswith(key) or key in row["normalized_title"]]
        if len(partial) == 1:
            return partial[0]
        if len(partial) > 1:
            raise AmbiguousSong(query, partial)
        raise UnknownSong(query)

    def list_songs(self, *, tag: str | None = None) -> list[SongStatus]:
        rows = self._conn.execute("SELECT title FROM songs ORDER BY title").fetchall()
        statuses = [self.song_status(row["title"]) for row in rows]
        if tag:
            statuses = [s for s in statuses if tag in s.tags]
        return statuses

    def song_status(self, title: str) -> SongStatus:
        key = normalize_title(title)
        row = self._conn.execute("SELECT * FROM songs WHERE normalized_title = ?", (key,)).fetchone()
        if row is None:
            raise UnknownSong(title)
        agg = self._conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(minutes), 0) AS total, MAX(practiced_at_utc_iso) AS last"
            " FROM sessions WHERE normalized_title = ?",
            (key,),
        ).fetchone()
        return SongStatus(
            title=row["title"],
            tags=tuple(json.loads(row["tags_json"])),
            configurations=tuple(json.loads(row["configurations_json"])),
            confidence=int(row["confidence"]),
            sessions_count=int(agg["n"]),
            total_minutes=int(agg["total"]),
            last_practiced_utc_iso=agg["last"],
        )

    # -- sessions ------------------------------------------------------------------------------

    def log_session(
        self,
        title: str,
        minutes: int,
        *,
        practiced_at: datetime | None = None,
        configuration: str | None = None,
        notes: str = "",
        source: str = "cli",
    ) -> SongStatus:
        resolved = self.resolve_title(title)
        key = normalize_title(resolved)
        minutes_value = int(minutes)
        if minutes_value <= 0:
            raise ValueError("minutes must be positive")
        when = practiced_at or utc_now()
        self._conn.execute(
            "INSERT INTO sessions (normalized_title, minutes, practiced_at_utc_iso, configuration, notes, source)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (key, minutes_value, _iso(when), configuration, str(notes or ""), source),
        )
        if minutes_value >= CONFIDENCE_BUMP_MINUTES:
            self._conn.execute(
                "UPDATE songs SET confidence = MIN(?, confidence + 1) WHERE normalized_title = ?",
                (CONFIDENCE_MAX, key),
            )
        self._conn.commit()
        return self.song_status(resolved)

    def sessions_since(self, since: datetime) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT s.minutes, s.practiced_at_utc_iso, s.configuration, s.notes, g.title"
            " FROM sessions s JOIN songs g ON g.normalized_title = s.normalized_title"
            " WHERE s.practiced_at_utc_iso >= ? ORDER BY s.practiced_at_utc_iso",
            (_iso(since),),
        ).fetchall()
        return [dict(row) for row in rows]

    # -- targets --------------------------------------------------------------------------------

    def set_target(self, name: str, *, description: str = "", target_date_iso: str | None = None, song_count_goal: int | None = None) -> None:
        if target_date_iso:
            date.fromisoformat(target_date_iso)
        self._conn.execute(
            "INSERT INTO targets (name, description, target_date_iso, song_count_goal) VALUES (?, ?, ?, ?)"
            " ON CONFLICT(name) DO UPDATE SET description = excluded.description,"
            " target_date_iso = excluded.target_date_iso, song_count_goal = excluded.song_count_goal",
            (name, description, target_date_iso, song_count_goal),
        )
        self._conn.commit()

    def list_targets(self) -> list[dict[str, Any]]:
        rows = self._conn.execute("SELECT * FROM targets ORDER BY name").fetchall()
        return [dict(row) for row in rows]

    # -- planning ---------------------------------------------------------------------------------

    def plan(self, *, minutes_budget: int = DEFAULT_PLAN_MINUTES, now: datetime | None = None, tag: str | None = None) -> list[dict[str, Any]]:
        now_value = now or utc_now()
        songs = self.list_songs(tag=tag)
        if not songs or minutes_budget <= 0:
            return []

        def priority(status: SongStatus) -> tuple[int, int, int, str]:
            days = status.days_since(now_value)
            never = 0 if days is None else 1
            return (never, status.confidence, -(days if days is not None else 10**6), status.title.lower())

        ordered = sorted(songs, key=priority)
        slots = max(1, min(len(ordered), round(minutes_budget / TARGET_SLOT_MINUTES)))
        slot_minutes = max(MIN_SLOT_MINUTES, min(MAX_SLOT_MINUTES, minutes_budget // slots))
        plan: list[dict[str, Any]] = []
        remaining = minutes_budget
        for status in ordered:
            if remaining < MIN_SLOT_MINUTES or len(plan) >= slots:
                break
            minutes = min(slot_minutes, remaining)
            plan.append({"title": status.title, "minutes": minutes, "reason": self._reason(status, now_value), "confidence": status.confidence})
            remaining -= minutes
        return plan

    @staticmethod
    def _reason(status: SongStatus, now: datetime) -> str:
        days = status.days_since(now)
        if days is None:
            return "never practiced"
        if status.confidence < CONFIDENCE_MAX and status.confidence <= 2:
            return f"confidence {status.confidence} of {CONFIDENCE_MAX}"
        if days >= 1:
            return f"{days} days since last time"
        return f"confidence {status.confidence} of {CONFIDENCE_MAX}"

    def status_summary(self, *, now: datetime | None = None) -> dict[str, Any]:
        now_value = now or utc_now()
        songs = self.list_songs()
        week_ago = now_value - timedelta(days=7)
        week_minutes = sum(int(s["minutes"]) for s in self.sessions_since(week_ago))
        practiced_days = {
            _parse_dt(row["practiced_at_utc_iso"]).date()
            for row in self._conn.execute("SELECT practiced_at_utc_iso FROM sessions").fetchall()
        }
        streak = 0
        cursor = now_value.date()
        while cursor in practiced_days:
            streak += 1
            cursor -= timedelta(days=1)
        stale = [s.title for s in songs if (s.days_since(now_value) is None) or (s.days_since(now_value) or 0) >= STALE_AFTER_DAYS]
        return {
            "song_count": len(songs),
            "streak_days": streak,
            "minutes_this_week": week_minutes,
            "stale_songs": sorted(stale),
            "average_confidence": round(sum(s.confidence for s in songs) / len(songs), 2) if songs else 0.0,
        }


# -- seeds ---------------------------------------------------------------------------------------


def seed_album_repertoire(store: PracticeStore, *, now: datetime | None = None) -> int:
    added = 0
    for title in ALBUM_SONGS:
        before = len(store.list_songs())
        store.add_song(title, tags=("album",), configurations=("full_rig",), now=now)
        if len(store.list_songs()) > before:
            added += 1
    return added


def seed_targets(store: PracticeStore, path: str | Path = DEFAULT_TARGETS_PATH) -> int:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    targets = payload.get("targets") if isinstance(payload, Mapping) else payload
    count = 0
    for target in targets or ():
        store.set_target(
            str(target["name"]),
            description=str(target.get("description") or ""),
            target_date_iso=target.get("target_date_iso"),
            song_count_goal=target.get("song_count_goal"),
        )
        count += 1
    return count


# -- operator handler --------------------------------------------------------------------------------

_PLAN_RE = re.compile(
    r"^\s*(?:what\s+should\s+i\s+practice(?:\s+today)?|practice(?:\s+plan)?)\s*(?:for\s+)?(?:(\d{1,3})\s*(?:min|mins|minutes))?\s*[?.!]*\s*$",
    re.IGNORECASE,
)
_LOGGED_RE = re.compile(
    r"^\s*(?:i\s+)?practi[cs]ed\s+(?P<song>.+?)\s+(?:for\s+)?(?P<minutes>\d{1,3})\s*(?:min|mins|minutes)"
    r"(?:\s+in\s+(?P<config>[a-z_ ]+?))?\s*(?::\s*(?P<notes>.+))?\s*[.!]*\s*$",
    re.IGNORECASE,
)
_ADD_RE = re.compile(r"^\s*add\s+song\s+(?P<song>.+?)(?:\s+to\s+(?P<tag>[a-z0-9_]+))?\s*[.!]*\s*$", re.IGNORECASE)
_STATUS_RE = re.compile(r"^\s*(?:practice\s+status|repertoire)\s*[?.!]*\s*$", re.IGNORECASE)
_SONGS_FOR_RE = re.compile(r"^\s*songs\s+for\s+(?P<tag>[a-z0-9_]+)\s*[?.!]*\s*$", re.IGNORECASE)


def handle_practice_text(text: str, *, store: PracticeStore, now: datetime | None = None, source: str = "telegram") -> str | None:
    """Answer a practice message, or return None so the caller falls through."""
    now_value = now or utc_now()
    raw = str(text or "").strip()
    if not raw:
        return None

    match = _PLAN_RE.match(raw)
    if match:
        minutes = int(match.group(1) or DEFAULT_PLAN_MINUTES)
        plan = store.plan(minutes_budget=minutes, now=now_value)
        if not plan:
            return "No repertoire yet. Say \"add song <title>\" and I will start planning."
        lines = [f"Practice today, {minutes} minutes:"]
        for slot in plan:
            lines.append(f"{slot['title']}, {slot['minutes']} min ({slot['reason']})")
        summary = store.status_summary(now=now_value)
        if summary["streak_days"] >= 2:
            lines.append(f"Streak: {summary['streak_days']} days.")
        return "\n".join(lines)

    match = _LOGGED_RE.match(raw)
    if match:
        try:
            status = store.log_session(
                match.group("song"),
                int(match.group("minutes")),
                practiced_at=now_value,
                configuration=(match.group("config") or "").strip() or None,
                notes=(match.group("notes") or "").strip(),
                source=source,
            )
        except AmbiguousSong as exc:
            return "Which one: " + ", ".join(exc.candidates) + "?"
        except UnknownSong:
            return f"I do not have \"{match.group('song').strip()}\" yet. Say \"add song {match.group('song').strip()}\" first."
        summary = store.status_summary(now=now_value)
        parts = [f"Logged {match.group('minutes')} minutes on {status.title}. Confidence {status.confidence} of {CONFIDENCE_MAX}."]
        if summary["streak_days"] >= 2:
            parts.append(f"Streak: {summary['streak_days']} days.")
        return " ".join(parts)

    match = _ADD_RE.match(raw)
    if match:
        tag = (match.group("tag") or "").strip().lower()
        status = store.add_song(match.group("song"), tags=(tag,) if tag else (), now=now_value)
        where = f" to {tag}" if tag else ""
        return f"Added {status.title}{where}. {len(store.list_songs())} songs in the repertoire."

    if _STATUS_RE.match(raw):
        summary = store.status_summary(now=now_value)
        if summary["song_count"] == 0:
            return "No repertoire yet. Say \"add song <title>\" to begin."
        stale = summary["stale_songs"]
        stale_text = f" Not touched in {STALE_AFTER_DAYS} days: " + ", ".join(stale[:5]) + ("." if stale else "") if stale else ""
        return (
            f"{summary['song_count']} songs, average confidence {summary['average_confidence']} of {CONFIDENCE_MAX}. "
            f"{summary['minutes_this_week']} minutes this week, streak {summary['streak_days']} days.{stale_text}"
        )

    match = _SONGS_FOR_RE.match(raw)
    if match:
        tag = match.group("tag").lower()
        songs = store.list_songs(tag=tag)
        if not songs:
            return f"No songs tagged {tag} yet."
        return f"{tag}: " + ", ".join(s.title for s in songs) + "."

    return None


# -- read model ------------------------------------------------------------------------------------


def build_practice_plan_read_model(*, db_path: str | Path, now: datetime | None = None, minutes_budget: int = DEFAULT_PLAN_MINUTES) -> dict[str, Any]:
    now_value = now or utc_now()
    store = PracticeStore(db_path)
    try:
        plan = store.plan(minutes_budget=minutes_budget, now=now_value)
        summary = store.status_summary(now=now_value)
        targets = store.list_targets()
        songs = [
            {
                "title": s.title,
                "tags": list(s.tags),
                "confidence": s.confidence,
                "sessions_count": s.sessions_count,
                "total_minutes": s.total_minutes,
                "last_practiced_utc_iso": s.last_practiced_utc_iso,
                "days_since": s.days_since(now_value),
            }
            for s in store.list_songs()
        ]
    finally:
        store.close()
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": _iso(now_value),
        "minutes_budget": minutes_budget,
        "plan": plan,
        "summary": summary,
        "targets": targets,
        "songs": songs,
        "source_refs": [f"practice_store:{Path(db_path).as_posix()}"],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {"model_called": False, "audio_read": False, "plan_is_explainable": all("reason" in slot for slot in plan)},
    }


def format_operator_markdown(payload: Mapping[str, Any]) -> str:
    lines = ["# Practice Plan", ""]
    plan = payload.get("plan") or []
    if plan:
        lines.append(f"Today, {payload.get('minutes_budget')} minutes:")
        for slot in plan:
            lines.append(f"- {slot['title']}: {slot['minutes']} min, {slot['reason']}")
    else:
        lines.append("No repertoire yet. Add songs and the plan appears here.")
    summary = payload.get("summary") or {}
    lines.append("")
    lines.append(
        f"{summary.get('song_count', 0)} songs, streak {summary.get('streak_days', 0)} days, "
        f"{summary.get('minutes_this_week', 0)} minutes this week."
    )
    stale = summary.get("stale_songs") or []
    if stale:
        lines.append("Not touched in two weeks: " + ", ".join(stale[:6]) + ".")
    targets = payload.get("targets") or []
    for target in targets:
        goal = f", goal {target['song_count_goal']} songs" if target.get("song_count_goal") else ""
        when = f", by {target['target_date_iso']}" if target.get("target_date_iso") else ""
        lines.append(f"Target {target['name']}: {target.get('description', '')}{goal}{when}")
    lines.append("")
    lines.append("Boundary: local practice store only; no DAW, audio, calendar, send, or model call.")
    return "\n".join(lines) + "\n"


def export_practice_plan(*, db_path: str | Path, export_root: str | Path = DEFAULT_EXPORT_ROOT, now: datetime | None = None, minutes_budget: int = DEFAULT_PLAN_MINUTES) -> dict[str, Any]:
    payload = build_practice_plan_read_model(db_path=db_path, now=now, minutes_budget=minutes_budget)
    root = Path(export_root)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / f"{READ_MODEL_ID}.json"
    operator_path = root / f"{READ_MODEL_ID}_OPERATOR.md"
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return {"json_path": str(json_path), "operator_path": str(operator_path), "plan_count": len(payload["plan"]), "song_count": payload["summary"]["song_count"]}
