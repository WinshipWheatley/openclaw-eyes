"""
chief_file_io.py

Centralized file I/O for all Chief brain modules.

Replaces scattered Path-based append logic across ops, billing, approval,
and any future brain that writes to vault markdown or JSON state files.

Public API
----------
load_json(path, default)          -- read JSON with error fallback
save_json(path, data)             -- write JSON, creating parent dirs
ensure_md_file(path)              -- create markdown file with YAML frontmatter if missing
append_md_entry(path, ts, text)   -- append  - [ts] text
append_md_tagged(path, ts, tag, text) -- append  - [ts] [tag] text
"""

import json
from pathlib import Path


# ── JSON helpers ───────────────────────────────────────────────────────────────

def load_json(path: Path, default):
    """Load JSON from path; return default if missing or corrupt."""
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default


def save_json(path: Path, data) -> None:
    """Write data as pretty-printed JSON, creating parent dirs if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ── Markdown file helpers ──────────────────────────────────────────────────────

def ensure_md_file(path: Path) -> None:
    """Create a markdown log file with YAML frontmatter if it does not exist."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"---\ntype: ops-log\n---\n\n# {path.stem}\n\n",
            encoding="utf-8",
        )


def append_md_entry(path: Path, ts: str, text: str) -> None:
    """Append a timestamped entry: `- [ts] text`"""
    ensure_md_file(path)
    with path.open("a", encoding="utf-8") as f:
        f.write(f"- [{ts}] {text}\n")


def append_md_tagged(path: Path, ts: str, tag: str, text: str) -> None:
    """Append a timestamped, tagged entry: `- [ts] [tag] text`"""
    ensure_md_file(path)
    with path.open("a", encoding="utf-8") as f:
        f.write(f"- [{ts}] [{tag}] {text}\n")
