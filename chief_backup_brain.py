"""
chief_backup_brain.py

Verifies the GitHub repo is current: checks for uncommitted changes,
staged but unpushed commits, and when the last push happened. Can
trigger a backup push (git add -A + commit + push) on request.

Triggered by:
  - "backup status" / "check backup" / "git status"
  - "backup now" / "push backup" — triggers a backup commit+push
Intent: backup_status in chief_router.py

Also runs on a daily schedule (called from chief_watcher_brain or cron).

Saves to:
  - openclaw-vault/System/Backup Status.md
"""

import subprocess
from datetime import datetime
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

REPO_DIR    = Path("/home/openclaw")
BACKUP_MD   = Path("/mnt/c/OpenClawShared/openclaw-vault/System/Backup Status.md")


# ── Git helpers ───────────────────────────────────────────────────────────────

def _run(cmd: list[str], cwd: Path = REPO_DIR) -> tuple[int, str, str]:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(cwd))
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def _get_status() -> dict:
    """Collect git status data."""
    info = {}

    # Uncommitted changes
    code, out, _ = _run(["git", "status", "--porcelain"])
    info["uncommitted_lines"] = [l for l in out.splitlines() if l.strip()] if out else []
    info["has_uncommitted"] = len(info["uncommitted_lines"]) > 0

    # Unpushed commits
    code, out, _ = _run(["git", "log", "origin/master..HEAD", "--oneline"])
    info["unpushed"] = [l for l in out.splitlines() if l.strip()] if out else []
    info["has_unpushed"] = len(info["unpushed"]) > 0

    # Last commit info
    code, out, _ = _run(["git", "log", "-1", "--format=%H|%s|%ci"])
    if out and "|" in out:
        parts = out.split("|", 2)
        info["last_commit_hash"] = parts[0][:8]
        info["last_commit_msg"]  = parts[1]
        info["last_commit_date"] = parts[2][:19] if len(parts) > 2 else "unknown"
    else:
        info["last_commit_hash"] = "unknown"
        info["last_commit_msg"]  = "unknown"
        info["last_commit_date"] = "unknown"

    # Last push (last commit on origin/master)
    code, out, _ = _run(["git", "log", "origin/master", "-1", "--format=%ci"])
    info["last_push_date"] = out[:19] if out else "unknown"

    # Current branch
    code, out, _ = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    info["branch"] = out or "unknown"

    # Ahead/behind count
    code, out, _ = _run(["git", "rev-list", "--left-right", "--count", "HEAD...origin/master"])
    if out and "\t" in out:
        ahead, behind = out.split("\t")
        info["commits_ahead"]  = int(ahead.strip())
        info["commits_behind"] = int(behind.strip())
    else:
        info["commits_ahead"]  = 0
        info["commits_behind"] = 0

    return info


# ── Report builder ────────────────────────────────────────────────────────────

def _build_report(info: dict) -> str:
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"**Backup Status — {today}**", ""]

    # Overall health indicator
    if not info["has_uncommitted"] and not info["has_unpushed"]:
        lines.append("✓ Repo is clean and current.")
    else:
        if info["has_uncommitted"]:
            lines.append(f"⚠ {len(info['uncommitted_lines'])} uncommitted change(s)")
        if info["has_unpushed"]:
            lines.append(f"⚠ {len(info['unpushed'])} unpushed commit(s)")

    lines += [
        "",
        f"Branch: {info['branch']}",
        f"Last commit: [{info['last_commit_hash']}] {info['last_commit_msg']} ({info['last_commit_date']})",
        f"Last push: {info['last_push_date']}",
        f"Ahead of origin: {info['commits_ahead']} | Behind: {info['commits_behind']}",
    ]

    if info["uncommitted_lines"]:
        lines.append("\nUncommitted:")
        for l in info["uncommitted_lines"][:10]:
            lines.append(f"  {l}")
        if len(info["uncommitted_lines"]) > 10:
            lines.append(f"  ... and {len(info['uncommitted_lines']) - 10} more")

    if info["unpushed"]:
        lines.append("\nUnpushed commits:")
        for l in info["unpushed"][:5]:
            lines.append(f"  {l}")

    return "\n".join(lines)


# ── Vault write ───────────────────────────────────────────────────────────────

def _write_backup_md(report: str) -> None:
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    content = (
        "---\n"
        "type: backup-status\n"
        f"last_updated: {today}\n"
        "---\n\n"
        "# Backup Status\n\n"
        "_Managed by `chief_backup_brain.py`. Say 'backup status' to refresh._\n\n"
        + report.replace("**", "") + "\n"
    )
    BACKUP_MD.parent.mkdir(parents=True, exist_ok=True)
    BACKUP_MD.write_text(content, encoding="utf-8")


# ── Backup push ───────────────────────────────────────────────────────────────

def _do_backup_push() -> list[str]:
    """Stage all changes, commit with timestamp, push."""
    info = _get_status()

    if not info["has_uncommitted"] and not info["has_unpushed"]:
        return ["Repo is already clean. Nothing to backup."]

    results = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    if info["has_uncommitted"]:
        code, out, err = _run(["git", "add", "-A"])
        if code != 0:
            return [f"git add failed: {err}"]

        msg = f"chore(backup): auto-backup {now}"
        code, out, err = _run(["git", "commit", "-m", msg])
        if code != 0:
            return [f"git commit failed: {err}"]
        results.append(f"Committed: {msg}")

    if info["has_unpushed"] or info["has_uncommitted"]:
        code, out, err = _run(["git", "push"])
        if code != 0:
            return results + [f"git push failed: {err}"]
        results.append("Pushed to origin/master.")

    _write_backup_md(_build_report(_get_status()))
    return results or ["Backup complete."]


# ── Public entry point ────────────────────────────────────────────────────────

def handle(text: str = "") -> list[str]:
    t = text.lower().strip()

    if any(k in t for k in ("backup now", "push backup", "do backup", "backup push")):
        return _do_backup_push()

    # Default: status check
    info = _get_status()
    report = _build_report(info)
    _write_backup_md(report)
    return [report + "\n\nSay 'backup now' to commit and push all changes."]


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "backup status"
    for line in handle(text):
        print(line)
