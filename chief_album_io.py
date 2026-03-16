import csv
import re
from pathlib import Path

ALBUM_DIR = Path("/mnt/c/OpenClawShared/album")
SONGS_DIR = ALBUM_DIR / "songs"
CSV_PATH = ALBUM_DIR / "album_work_log.csv"
ARC_PATH = ALBUM_DIR / "album_arc.md"

BASE_CSV_FIELDS = [
    "song_title",
    "completion_pct",
    "completion_blocker",
    "version_locked",
    "structure_pass",
    "vocals_pass",
    "drums_pass",
    "bass_pass",
    "guitars_pass",
    "keys_pass",
    "mix_readiness",
    "mix_prep_done",
    "needs_rerecord",
    "rerecord_reason",
    "batch_days",
    "blocker",
    "status",
    "vocal_archetype_primary",
    "vocal_archetype_influences",
]

# Canonical section names in song markdown files
MD_SECTIONS = [
    "Vibe / Feel",
    "Structure Notes",
    "Vocals / Lyrics",
    "Vocal Archetype",
    "Drums",
    "Bass",
    "Guitars",
    "Keys / Synths / Electronica / World Rhythm",
    "Mix Notes",
    "Technical Notes",
    "Suno Reference",
    "Lyrics",
    "Session History",
]


# ── CSV ───────────────────────────────────────────────────────────────────────

def _current_fields() -> list[str]:
    """Return the current CSV column list (base + any dynamic columns added)."""
    if not CSV_PATH.exists():
        return list(BASE_CSV_FIELDS)
    with CSV_PATH.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
            return header if header else list(BASE_CSV_FIELDS)
        except StopIteration:
            return list(BASE_CSV_FIELDS)


def ensure_csv() -> None:
    """Create the CSV with the base schema if it doesn't exist or has old schema."""
    if CSV_PATH.exists():
        fields = _current_fields()
        if fields and fields[0] == "song_title":
            return  # Already new schema — nothing to do
        # Old schema detected — back it up and start fresh
        backup = CSV_PATH.with_suffix(".old.csv")
        backup.write_bytes(CSV_PATH.read_bytes())
        print(f"Old schema backed up to {backup.name}")

    with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=BASE_CSV_FIELDS)
        writer.writeheader()


def load_all_rows() -> list[dict]:
    ensure_csv()
    with CSV_PATH.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def upsert_csv_row(data: dict) -> None:
    """Insert or update a CSV row matched on song_title."""
    ensure_csv()
    fields = _current_fields()
    # Add any new keys from data that aren't in the current fields
    for key in data:
        if key not in fields:
            fields.append(key)

    rows = load_all_rows()
    found = False
    new_rows = []
    for row in rows:
        if row.get("song_title", "").strip().lower() == data.get("song_title", "").strip().lower():
            merged = {f: row.get(f, "") for f in fields}
            merged.update(data)
            new_rows.append(merged)
            found = True
        else:
            new_rows.append({f: row.get(f, "") for f in fields})

    if not found:
        new_rows.append({f: data.get(f, "") for f in fields})

    with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(new_rows)


def add_dynamic_column(column_name: str) -> bool:
    """Add a new column to the CSV. Returns True if added, False if already exists."""
    ensure_csv()
    fields = _current_fields()
    if column_name in fields:
        return False
    fields.append(column_name)
    rows = load_all_rows()
    with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            row[column_name] = ""
            writer.writerow({f: row.get(f, "") for f in fields})
    return True


def list_all_songs() -> list[str]:
    """Return song titles from the songs directory."""
    if not SONGS_DIR.exists():
        return []
    return sorted(p.stem for p in SONGS_DIR.glob("*.md"))


# ── Markdown ──────────────────────────────────────────────────────────────────

def _song_path(song_title: str) -> Path:
    return SONGS_DIR / f"{song_title}.md"


def load_song_md(song_title: str) -> dict:
    """
    Load a song's markdown file into a dict keyed by section name.
    Returns empty sections if file doesn't exist.
    """
    path = _song_path(song_title)
    sections = {s: "" for s in MD_SECTIONS}

    if not path.exists():
        return sections

    content = path.read_text(encoding="utf-8")
    # Split on ## headers (level 2 only)
    parts = re.split(r"\n## ", content)

    for part in parts[1:]:  # skip the title block
        lines = part.split("\n", 1)
        header = lines[0].strip()
        body = lines[1].strip() if len(lines) > 1 else ""
        sections[header] = body

    return sections


def save_song_md(song_title: str, sections: dict) -> None:
    """
    Write a song's sections dict back to its markdown file.
    Preserves any dynamic sections not in MD_SECTIONS.
    """
    path = _song_path(song_title)

    # Build ordered section list: canonical first, then any extras
    ordered = list(MD_SECTIONS)
    for key in sections:
        if key not in ordered:
            ordered.append(key)

    lines = [f"# {song_title}\n"]
    for section in ordered:
        content = sections.get(section, "").strip()
        lines.append(f"\n## {section}\n")
        if content:
            lines.append(f"\n{content}\n")

    path.write_text("\n".join(lines), encoding="utf-8")


def append_session_history(song_title: str, entry: str) -> None:
    """Append a timestamped entry to the Session History section."""
    from datetime import datetime
    sections = load_song_md(song_title)
    existing = sections.get("Session History", "").strip()
    timestamp = datetime.now().strftime("%Y-%m-%d")
    new_entry = f"{timestamp}: {entry}"
    sections["Session History"] = (existing + "\n\n" + new_entry).strip()
    save_song_md(song_title, sections)


def load_arc_md() -> str:
    if ARC_PATH.exists():
        return ARC_PATH.read_text(encoding="utf-8")
    return ""


def save_arc_md(content: str) -> None:
    ARC_PATH.write_text(content, encoding="utf-8")


# ── Completion scorer ─────────────────────────────────────────────────────────

def _is_done(val: str) -> bool:
    return str(val).strip().lower() in {"done", "yes", "true", "locked", "complete", "1"}


def _needs_rerecord(val: str) -> bool:
    return str(val).strip().lower() in {"yes", "true", "needs_rerecord", "needs re-record", "rerecord"}


def score_completion(data: dict) -> tuple[int, str]:
    """
    Score a song's completion percentage using industry production pipeline weights.
    Returns (pct: int, blocker: str).

    Weights:
      version_locked          10%
      all parts recorded      20%   (drums + bass + guitars + keys, 5% each)
      editing / structure     15%   (structure_pass done = 15%)
      lead vocals final       15%   (vocals_pass done)
      BGVs done               10%   (vocals_pass done AND no re-records)
      no re-records pending   10%   (needs_rerecord != yes)
      mix prep complete       10%   (mix_prep_done yes)
      mixed                    5%   (mix_readiness == mixed/ready or status == mixed)
      mastered                 5%   (status == mastered)

    Re-records pending hard-caps the score at 50%.
    """
    score = 0
    blockers = []

    rerecord = _needs_rerecord(data.get("needs_rerecord", ""))

    # version locked — 10%
    if _is_done(data.get("version_locked", "")):
        score += 10
    else:
        blockers.append("version not locked")

    # all parts recorded — 20% (5% per instrument)
    instruments = ["drums_pass", "bass_pass", "guitars_pass", "keys_pass"]
    parts_done = sum(1 for f in instruments if _is_done(data.get(f, "")))
    score += parts_done * 5
    if parts_done < 4:
        missing = [f.replace("_pass", "") for f in instruments if not _is_done(data.get(f, ""))]
        blockers.append(f"parts not recorded: {', '.join(missing)}")

    # editing / structure — 15%
    if _is_done(data.get("structure_pass", "")):
        score += 15
    else:
        blockers.append("structure/editing not complete")

    # lead vocals final — 15%
    vocals_done = _is_done(data.get("vocals_pass", ""))
    if vocals_done:
        score += 15
    else:
        blockers.append("lead vocals not final")

    # BGVs done — 10% (only if vocals done and no re-records pending)
    if vocals_done and not rerecord:
        score += 10
    elif not vocals_done:
        blockers.append("BGVs pending lead vocals")
    else:
        blockers.append("re-records blocking BGV sign-off")

    # no re-records pending — 10%
    if not rerecord:
        score += 10
    else:
        blockers.append(f"re-record needed: {data.get('rerecord_reason', 'see notes')}")

    # mix prep complete — 10%
    if _is_done(data.get("mix_prep_done", "")):
        score += 10
    else:
        blockers.append("mix prep not complete")

    # mixed — 5%
    mix_r = str(data.get("mix_readiness", "")).strip().lower()
    status = str(data.get("status", "")).strip().lower()
    if mix_r in {"mixed", "ready"} or status in {"mixed", "mastered"}:
        score += 5
    else:
        blockers.append("not mixed")

    # mastered — 5%
    if status == "mastered":
        score += 5
    else:
        blockers.append("not mastered")

    # hard cap if re-records pending
    if rerecord:
        score = min(score, 50)

    blocker_line = blockers[0] if blockers else "none"
    return max(0, min(100, score)), blocker_line


# ── Batch day deriver ─────────────────────────────────────────────────────────

BATCH_DAY_MAP = [
    ("drums day",     lambda d: not _is_done(d.get("drums_pass", ""))),
    ("bass day",      lambda d: not _is_done(d.get("bass_pass", ""))),
    ("guitars day",   lambda d: not _is_done(d.get("guitars_pass", ""))),
    ("vocals day",    lambda d: not _is_done(d.get("vocals_pass", "")) or _needs_rerecord(d.get("needs_rerecord", ""))),
    ("keys day",      lambda d: not _is_done(d.get("keys_pass", ""))),
    ("mix prep day",  lambda d: not _is_done(d.get("mix_prep_done", ""))),
    ("mixing day",    lambda d: str(d.get("mix_readiness", "")).strip().lower() not in {"mixed", "ready"} and _is_done(d.get("mix_prep_done", ""))),
    ("mastering day", lambda d: str(d.get("status", "")).strip().lower() != "mastered" and str(d.get("mix_readiness", "")).strip().lower() in {"mixed", "ready"}),
]


def derive_batch_days(data: dict) -> list[str]:
    """Return list of batch days this song still needs."""
    return [label for label, check in BATCH_DAY_MAP if check(data)]
