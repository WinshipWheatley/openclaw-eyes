"""
chief_obsidian_sync.py

Syncs album production data → Obsidian vault.

  - Rewrites YAML frontmatter in each vault song file from the CSV
  - Rewrites the completion table in Album Overview.md
  - Copies album_arc.md content into Album/Album Arc.md

Safe to run at any time. Called automatically from chief_album_brain
after _finalize() and handle_quick_update().
"""

import csv
import re
from datetime import datetime
from pathlib import Path

VAULT = Path("/mnt/c/OpenClawShared/openclaw-vault")
SONGS_DIR = VAULT / "Album" / "Songs"
OVERVIEW_PATH = VAULT / "Album" / "Album Overview.md"
ARC_VAULT_PATH = VAULT / "Album" / "Album Arc.md"
CSV_PATH = Path("/mnt/c/OpenClawShared/album/album_work_log.csv")
ARC_SRC_PATH = Path("/mnt/c/OpenClawShared/album/album_arc.md")

ALBUM_SONGS = [
    "1 In A Million", "A Night To Remember", "Blue Weather", "Built By Stars",
    "Can You Feel It", "Count On Your Faith", "I Cry Over Love", "Im Somebody",
    "Kamakazi Of Life", "Slow Me Down", "Ten Fingers", "The Future",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_csv() -> dict:
    data = {}
    if not CSV_PATH.exists():
        return data
    with CSV_PATH.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            title = row.get("song_title", "").strip()
            if title:
                data[title] = row
    return data


def _make_frontmatter(title: str, row: dict) -> str:
    pct = row.get("completion_pct", "0").strip() or "0"
    locked = "true" if str(row.get("version_locked", "")).lower() in ("yes", "true", "locked") else "false"
    rerecord = "true" if str(row.get("needs_rerecord", "")).lower() in ("yes", "true") else "false"
    reason = row.get("rerecord_reason", "").strip()
    batch = row.get("batch_days", "").strip()
    status = row.get("status", "").strip() or "in-progress"
    blocker = row.get("completion_blocker", "").strip()

    tags = ["song"]
    if rerecord == "true":
        tags.append("needs-rerecord")
    try:
        if int(pct) >= 70:
            tags.append("near-ready")
    except ValueError:
        pass

    lines = [
        "---",
        f'title: "{title}"',
        "type: song",
        f"completion: {pct}",
        f"version_locked: {locked}",
        f"needs_rerecord: {rerecord}",
    ]
    if reason:
        lines.append(f'rerecord_reason: "{reason}"')
    if blocker:
        lines.append(f'blocker: "{blocker}"')
    if batch:
        days = [d.strip() for d in batch.split(",") if d.strip()]
        if days:
            lines.append("batch_days:")
            for d in days:
                lines.append(f"  - {d}")
    lines.append(f"status: {status}")
    lines.append(f"tags: [{', '.join(tags)}]")
    lines.append("---")
    return "\n".join(lines)


def _strip_frontmatter(content: str) -> str:
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            return content[end + 4:].lstrip("\n")
    return content


# ── Sync functions ────────────────────────────────────────────────────────────

def sync_song_frontmatter(csv_data: dict) -> int:
    """Rewrite YAML frontmatter in each vault song file. Returns count updated."""
    updated = 0
    for title in ALBUM_SONGS:
        path = SONGS_DIR / f"{title}.md"
        if not path.exists():
            continue
        row = csv_data.get(title, {})
        content = path.read_text(encoding="utf-8")
        body = _strip_frontmatter(content)
        new_fm = _make_frontmatter(title, row)
        new_content = new_fm + "\n" + body
        if new_content != content:
            path.write_text(new_content, encoding="utf-8")
            updated += 1
    return updated


def sync_overview_table(csv_data: dict) -> None:
    """Rewrite the completion table in Album Overview.md."""
    if not OVERVIEW_PATH.exists():
        return

    def row_for(i, title):
        row = csv_data.get(title, {})
        pct = row.get("completion_pct", "—").strip() or "—"
        if pct and pct != "—":
            pct = f"{pct}%"
        locked = "✓" if str(row.get("version_locked", "")).lower() in ("yes", "true", "locked") else "—"
        rerecord = "✓" if str(row.get("needs_rerecord", "")).lower() in ("yes", "true") else "—"
        blocker = row.get("completion_blocker", "no notes yet").strip() or "no notes yet"
        return f"| {i} | [[Songs/{title}]] | {pct} | {locked} | {rerecord} | {blocker} |"

    table_rows = "\n".join(row_for(i + 1, t) for i, t in enumerate(ALBUM_SONGS))
    new_table = (
        "| # | Song | Completion | Locked | Re-record | Blocker |\n"
        "|---|---|---|---|---|---|\n"
        + table_rows
    )

    content = OVERVIEW_PATH.read_text(encoding="utf-8")
    # Replace the table block between the header and the note line
    new_content = re.sub(
        r"\| # \| Song \|.*?(?=\n_This table)",
        new_table,
        content,
        flags=re.DOTALL,
    )
    if new_content != content:
        OVERVIEW_PATH.write_text(new_content, encoding="utf-8")


def sync_arc() -> None:
    """Copy album_arc.md content into vault Album Arc.md, preserving the header."""
    if not ARC_SRC_PATH.exists() or not ARC_VAULT_PATH.exists():
        return
    src = ARC_SRC_PATH.read_text(encoding="utf-8")
    existing = ARC_VAULT_PATH.read_text(encoding="utf-8")

    # Keep the vault frontmatter, replace everything after the second ---
    fm_end = existing.find("\n---\n", 4)
    if fm_end == -1:
        return
    header = existing[: fm_end + 5]  # keep up to and including the closing ---\n

    # Strip the # Album Arc title from src (vault already has it)
    src_body = re.sub(r"^# Album Arc\n", "", src).lstrip("\n")
    new_content = header + "\n" + src_body
    if new_content != existing:
        ARC_VAULT_PATH.write_text(new_content, encoding="utf-8")


# ── Main ──────────────────────────────────────────────────────────────────────

def run_sync() -> str:
    csv_data = _load_csv()
    updated = sync_song_frontmatter(csv_data)
    sync_overview_table(csv_data)
    sync_arc()
    return f"Obsidian sync complete. {updated} song file(s) updated."


if __name__ == "__main__":
    print(run_sync())
