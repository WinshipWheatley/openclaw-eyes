"""
discovery_scan.py — Unit 2: Read-only repository discovery + capture.

Spec: SYSTEM-CATALOG-SPEC.md §G, 20260625-SYSCAT-v1
Contract: shared interface contract (all 3 units must conform exactly).

HARD RULES enforced here:
  - Metadata-only: no business/invoice/PII/message-body content ever.
  - Read-only: NEVER write/modify a scanned repo. All git commands are read-only.
  - Honor excluded_paths: no traversal inside excluded prefixes.
  - No network/send/money operations.
  - Legal/PII: OUT OF SCOPE.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Internal constants
# ---------------------------------------------------------------------------

_REGISTRY_HEADER_RE = re.compile(r"^\s*\|.*\|\s*$")
_REGISTRY_SEPARATOR_RE = re.compile(r"^\s*\|[-| ]+\|\s*$")

# Metadata files we parse for components/capabilities/queues/handoffs/tests.
# Bounded list — no open-ended walk unless constrained. These are relative
# glob patterns applied inside each repo root.
_COMPONENT_GLOBS = [
    "AGENTS.md",
    "THREE-COMPONENT-SPEC.md",
    "*_capability.py",
    "capability_registry*.py",
    "openclaw_capability_index.py",
]
_CAPABILITY_GLOBS = [
    "capability_registry.py",
    "openclaw_capability_index.py",
    "agent_lane_registry.py",
]
_QUEUE_GLOBS = [
    "approval_request_queue.py",
    "expert_escalation_queue.py",
    "dead_letter_queue.py",
    "workflow_package_queue.py",
]
_HANDOFF_GLOBS = [
    "*_handoff*.py",
    "agent_handoff_registry.py",
    "cross_surface_artifact_handoff_registry_contract.py",
]
_TEST_GLOBS = [
    "tests/",
    "test_*.py",
    "*_test.py",
    "conftest.py",
]

_MAX_METADATA_FILES = 50  # bounded parse — no unbounded walks


# ---------------------------------------------------------------------------
# Public API — load_registry
# ---------------------------------------------------------------------------

def load_registry(registry_path: Any) -> list[dict]:
    """
    Load the authoritative repository registry and return a list of dicts:
      [{repo_path: str, is_root: bool}, ...]

    Accepted inputs (shared Unit-2 contract — all three forms are honored so the
    synchronizer pipeline and tests can drive it):
      1. A pre-parsed list[dict] (for testability) — normalized in-place.
      2. A `.json` file path — a JSON list of entries.
      3. A `REPOSITORY_REGISTRY.md` Markdown pipe-table with columns:
           Repository Path | Purpose | Branch | HEAD Commit | Dirty | Worktrees | Coverage
      4. A plain-line registry: one repo path per non-blank, non-comment (`#`)
         line, with an optional `[ROOT]`/`[root]` marker for the root repo.

    `is_root` is True for the first data row / a row carrying a root marker.
    """
    # Form 1: a pre-parsed list (caller passed the entries directly).
    if isinstance(registry_path, list):
        return _normalize_registry_list(registry_path)

    p = Path(registry_path)

    if not p.exists():
        raise FileNotFoundError(f"Registry not found: {registry_path}")

    content = p.read_text(encoding="utf-8")

    # Form 2: JSON list (used by smoke tests / synthetic fixtures)
    if str(registry_path).endswith(".json"):
        raw = json.loads(content)
        return _normalize_registry_list(raw)

    # Form 3: Markdown pipe-table (if any pipe-table rows are present)
    if any(line.strip().startswith("|") for line in content.splitlines()):
        entries = _parse_markdown_registry(content)
        if entries:
            return entries

    # Form 4: plain one-path-per-line registry
    return _parse_plain_registry(content)


def _normalize_registry_list(raw: list) -> list[dict]:
    """Accept a list of dicts with at least {repo_path} already set."""
    result = []
    for i, entry in enumerate(raw):
        repo_path = entry.get("repo_path") or entry.get("path") or ""
        result.append({"repo_path": str(repo_path), "is_root": entry.get("is_root", i == 0)})
    return result


def _parse_markdown_registry(content: str) -> list[dict]:
    """
    Parse the REPOSITORY_REGISTRY.md Markdown table.

    Expected header row: | Repository Path | Purpose | Branch | ... |
    Returns [{repo_path, is_root}] with is_root=True for the first data row.
    """
    entries: list[dict] = []
    in_table = False
    header_seen = False
    separator_seen = False
    path_col_idx = 0

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue

        # Split on pipes, strip whitespace
        cols = [c.strip() for c in stripped.strip("|").split("|")]

        # Detect header row
        if not header_seen:
            lower_cols = [c.lower() for c in cols]
            if any("repository path" in c or "repo" in c for c in lower_cols):
                header_seen = True
                # Find the column index for repo path
                for idx, c in enumerate(lower_cols):
                    if "repository path" in c or (c.startswith("repo") and "path" in c):
                        path_col_idx = idx
                        break
                in_table = True
            continue

        # Skip separator row (--- cells)
        if header_seen and not separator_seen:
            if all(re.match(r"^[-:]+$", c.strip()) for c in cols if c.strip()):
                separator_seen = True
                continue

        # Data rows
        if in_table and header_seen and separator_seen:
            if len(cols) > path_col_idx:
                raw_path = cols[path_col_idx].strip()
                # Strip any backtick formatting
                raw_path = raw_path.strip("`")
                if raw_path and raw_path != "---":
                    entries.append({
                        "repo_path": raw_path,
                        "is_root": len(entries) == 0,
                    })

    return entries


def _parse_plain_registry(content: str) -> list[dict]:
    """
    Parse a plain one-path-per-line registry.

    Rules:
      - Blank lines and `#`-comment lines (e.g. the `# REPOSITORY_REGISTRY`
        title) are skipped.
      - Markdown table rows (lines starting with `|`) are skipped (handled by
        the table parser).
      - An optional trailing `[ROOT]`/`[root]` marker flags the root repo.
      - Backtick formatting around a path is stripped.
    `is_root` is True for a row carrying a root marker, or — failing any marker —
    the first data row.
    """
    entries: list[dict] = []
    saw_marker = False

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if stripped.startswith("|"):
            continue

        is_root = False
        # Strip an optional [ROOT]/[root] marker
        m = re.search(r"\[root\]\s*$", stripped, flags=re.IGNORECASE)
        if m:
            is_root = True
            saw_marker = True
            stripped = stripped[: m.start()].strip()

        raw_path = stripped.strip("`").strip()
        if not raw_path:
            continue
        entries.append({"repo_path": raw_path, "is_root": is_root})

    # If no explicit marker was found, treat the first entry as the root.
    if entries and not saw_marker:
        entries[0]["is_root"] = True

    return entries


# ---------------------------------------------------------------------------
# Public API — capture_repo_state
# ---------------------------------------------------------------------------

def capture_repo_state(repo_path: str) -> dict:
    """
    Read-only git capture for a single repo root.

    Returns:
      {
        branch: str,
        head_commit: str,
        dirty: bool,
        worktrees: list[dict],   # [{worktree_path, branch, head_commit, dirty}]
        coverage: 'VERIFIED' | 'UNAVAILABLE',
      }

    Never raises — returns coverage='UNAVAILABLE' if the repo is unreadable.
    NEVER writes to the repo. All git operations are read-only.
    """
    rp = Path(repo_path)
    if not rp.exists() or not rp.is_dir():
        return _unavailable_state()

    try:
        # A path that exists but is NOT a git work tree is UNAVAILABLE, not
        # VERIFIED. _run_git raises on a non-zero git exit (e.g. "not a git
        # repository"), which the inner per-field helpers swallow — so probe the
        # work-tree directly here and propagate the failure.
        if _run_git(["rev-parse", "--is-inside-work-tree"], cwd=repo_path) != "true":
            return _unavailable_state()

        branch = _git_branch(repo_path)
        head_commit = _git_head(repo_path)
        dirty = _git_dirty(repo_path)
        worktrees = _git_worktrees(repo_path)
        return {
            "branch": branch,
            "head_commit": head_commit,
            "dirty": dirty,
            "worktrees": worktrees,
            "coverage": "VERIFIED",
        }
    except Exception:
        return _unavailable_state()


def _unavailable_state() -> dict:
    return {
        "branch": "",
        "head_commit": "",
        "dirty": False,
        "worktrees": [],
        "coverage": "UNAVAILABLE",
    }


def _run_git(args: list[str], cwd: str, timeout: int = 10) -> str:
    """
    Run a read-only git command. Returns stdout. Raises on failure.
    NEVER issues write operations (enforced by caller discipline).
    """
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {args[0]} failed in {cwd}: {result.stderr.strip()}")
    return result.stdout.strip()


def _git_branch(repo_path: str) -> str:
    """Get current branch name (read-only)."""
    try:
        # --abbrev-ref HEAD gives branch name; "HEAD" in detached state
        return _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path)
    except Exception:
        return "HEAD"


def _git_head(repo_path: str) -> str:
    """Get the full HEAD commit hash (read-only)."""
    try:
        return _run_git(["rev-parse", "HEAD"], cwd=repo_path)
    except Exception:
        return ""


def _git_dirty(repo_path: str) -> bool:
    """
    True if the working tree has any uncommitted changes (staged or unstaged).
    Uses `git status --porcelain` — read-only.
    """
    try:
        output = _run_git(["status", "--porcelain"], cwd=repo_path)
        return bool(output.strip())
    except Exception:
        return False


def _git_worktrees(repo_path: str) -> list[dict]:
    """
    Return a list of linked worktrees (excluding the main worktree itself).
    Uses `git worktree list --porcelain` — read-only.

    Returns [{worktree_path, branch, head_commit, dirty}]
    """
    try:
        output = _run_git(["worktree", "list", "--porcelain"], cwd=repo_path)
    except Exception:
        return []

    worktrees: list[dict] = []
    blocks = output.strip().split("\n\n")
    main_path = str(Path(repo_path).resolve())

    for block in blocks:
        wt_info: dict[str, str] = {}
        for line in block.strip().splitlines():
            if line.startswith("worktree "):
                wt_info["path"] = line.removeprefix("worktree ").strip()
            elif line.startswith("HEAD "):
                wt_info["head"] = line.removeprefix("HEAD ").strip()
            elif line.startswith("branch "):
                raw_branch = line.removeprefix("branch ").strip()
                # Strip refs/heads/ prefix
                wt_info["branch"] = raw_branch.removeprefix("refs/heads/")
            elif line == "detached":
                wt_info["detached"] = "true"

        wt_path = wt_info.get("path", "")
        if not wt_path:
            continue
        # Skip the main worktree itself
        if str(Path(wt_path).resolve()) == main_path:
            continue

        branch = wt_info.get("branch", "HEAD" if "detached" in wt_info else "")
        head_commit = wt_info.get("head", "")
        dirty = _git_dirty(wt_path) if Path(wt_path).exists() else False

        worktrees.append({
            "worktree_path": wt_path,
            "branch": branch,
            "head_commit": head_commit,
            "dirty": dirty,
        })

    return worktrees


# ---------------------------------------------------------------------------
# Public API — parse_repo_metadata
# ---------------------------------------------------------------------------

def parse_repo_metadata(repo_path: str, excluded_paths: list[str] | None = None) -> dict:
    """
    Parse durable metadata from a repo: components, capabilities, queues,
    handoffs, tests.

    Returns:
      {
        components:   [{component_id, name, kind, source_ref}],
        capabilities: [{capability_id, name, status, source_ref}],
        queues:       [{queue_path, item_count, states_json}],
        handoffs:     [{handoff_path, checkpoint, updated_utc}],
        tests:        [{test_path, count}],
      }

    METADATA-ONLY: never reads message bodies, business domain data,
    invoices, or PII. Bounded by _MAX_METADATA_FILES per category.
    Honor excluded_paths: skip any path that starts with an excluded prefix.
    """
    excluded = [str(Path(e).resolve()) for e in (excluded_paths or [])]
    rp = Path(repo_path)
    if not rp.exists():
        return _empty_metadata()

    return {
        "components":   _parse_components(rp, excluded),
        "capabilities": _parse_capabilities(rp, excluded),
        "queues":       _parse_queues(rp, excluded),
        "handoffs":     _parse_handoffs(rp, excluded),
        "tests":        _parse_tests(rp, excluded),
    }


def _empty_metadata() -> dict:
    return {
        "components":   [],
        "capabilities": [],
        "queues":       [],
        "handoffs":     [],
        "tests":        [],
    }


def _is_excluded(path: Path, excluded: list[str]) -> bool:
    resolved = str(path.resolve())
    return any(resolved.startswith(e) for e in excluded)


def _collect_files(root: Path, globs: list[str], excluded: list[str], limit: int) -> list[Path]:
    """
    Collect files matching any of the glob patterns under root, respecting
    excluded_paths. Bounded to `limit` files.
    """
    found: list[Path] = []
    seen: set[str] = set()

    for pattern in globs:
        if len(found) >= limit:
            break
        try:
            for p in root.glob(pattern):
                if len(found) >= limit:
                    break
                key = str(p.resolve())
                if key in seen:
                    continue
                if _is_excluded(p, excluded):
                    continue
                seen.add(key)
                found.append(p)
        except (OSError, PermissionError):
            continue

    return found[:limit]


def _rel(root: Path, path: Path) -> str:
    """Return path relative to root, or str(path) if not under root."""
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _parse_components(root: Path, excluded: list[str]) -> list[dict]:
    """
    Detect components from well-known metadata files.
    Metadata-only: we record file path + inferred kind. No content ingestion.
    """
    components: list[dict] = []
    files = _collect_files(root, _COMPONENT_GLOBS, excluded, _MAX_METADATA_FILES)
    for f in files:
        rel = _rel(root, f)
        name = f.stem
        kind = _infer_component_kind(f)
        cid = _make_id("comp", rel)
        components.append({
            "component_id": cid,
            "name": name,
            "kind": kind,
            "source_ref": rel,
        })
    return components


def _infer_component_kind(path: Path) -> str:
    name = path.name.lower()
    if "capability" in name:
        return "capability_registry"
    if "agent" in name:
        return "agent"
    if "spec" in name or name.endswith(".md"):
        return "spec"
    return "module"


def _parse_capabilities(root: Path, excluded: list[str]) -> list[dict]:
    """
    Detect capability declarations from well-known metadata files.
    Metadata-only pointer records — no business content.
    """
    capabilities: list[dict] = []
    files = _collect_files(root, _CAPABILITY_GLOBS, excluded, _MAX_METADATA_FILES)
    for f in files:
        rel = _rel(root, f)
        cap_id = _make_id("cap", rel)
        capabilities.append({
            "capability_id": cap_id,
            "name": f.stem,
            "status": "DETECTED",
            "source_ref": rel,
        })
    return capabilities


def _parse_queues(root: Path, excluded: list[str]) -> list[dict]:
    """
    Detect queue modules from well-known patterns.
    Records metadata pointer only (queue_path, item_count=0 as unknown,
    states_json=null at discovery time — live state is in the domain DB).
    """
    queues: list[dict] = []
    files = _collect_files(root, _QUEUE_GLOBS, excluded, _MAX_METADATA_FILES)
    for f in files:
        rel = _rel(root, f)
        queues.append({
            "queue_path": rel,
            "item_count": 0,         # metadata pointer — live count in domain DB
            "states_json": "null",   # not ingested here; domain DB is authoritative
        })
    return queues


def _parse_handoffs(root: Path, excluded: list[str]) -> list[dict]:
    """
    Detect handoff contract / registry files.
    Metadata-only: records file path + mtime as updated_utc. No content.
    """
    handoffs: list[dict] = []
    files = _collect_files(root, _HANDOFF_GLOBS, excluded, _MAX_METADATA_FILES)
    for f in files:
        rel = _rel(root, f)
        try:
            mtime = f.stat().st_mtime
            updated_utc = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
        except OSError:
            updated_utc = ""
        handoffs.append({
            "handoff_path": rel,
            "checkpoint": "",    # checkpoint is domain-specific — out of scope
            "updated_utc": updated_utc,
        })
    return handoffs


def _parse_tests(root: Path, excluded: list[str]) -> list[dict]:
    """
    Detect test files/directories.
    Records metadata pointer only — count is file count (not assertion count).
    """
    tests: list[dict] = []

    # Directories (tests/)
    test_dirs = _collect_files(root, ["tests/"], excluded, 5)
    for d in test_dirs:
        if d.is_dir():
            try:
                count = sum(1 for _ in d.rglob("test_*.py") if not _is_excluded(_, excluded))
            except OSError:
                count = 0
            rel = _rel(root, d)
            tests.append({"test_path": rel, "count": count})

    # Top-level test files
    test_files = _collect_files(root, ["test_*.py", "*_test.py", "conftest.py"], excluded, _MAX_METADATA_FILES)
    for f in test_files:
        if f.is_file():
            rel = _rel(root, f)
            tests.append({"test_path": rel, "count": 1})

    return tests[:_MAX_METADATA_FILES]


# ---------------------------------------------------------------------------
# Public API — generate_scan_id
# ---------------------------------------------------------------------------

def generate_scan_id(captured_summary: Any, now_iso: str) -> str:
    """
    Generate a deterministic, immutable scan_id.

    Format: SYSCAT-<compact_utc>-<short_hash>

    Where:
      compact_utc   = now_iso formatted as YYYYMMDDTHHMMSS (UTC)
      short_hash    = first 8 hex chars of SHA-256 of the canonical JSON
                      of captured_summary (sorted keys, no whitespace)

    `now_iso` is injected for testability.

    captured_summary should be a JSON-serializable structure representing
    the captured set (e.g. a list of {repo_path, head_commit, dirty} dicts).
    This is deliberately content-addressed: same repos + same HEADs + same
    dirty states → same hash fragment.
    """
    # Normalise now_iso to compact UTC format
    compact_utc = _compact_utc(now_iso)

    # Canonical JSON of the summary (deterministic)
    canonical = json.dumps(captured_summary, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:8]

    return f"SYSCAT-{compact_utc}-{digest}"


def _compact_utc(iso_str: str) -> str:
    """
    Convert an ISO-8601 timestamp string to compact all-digit format YYYYMMDDHHMMSS.
    Handles both 'Z' suffix and '+00:00' offset. Falls back gracefully.

    The compact portion is all digits (no 'T' separator) so the scan_id splits
    cleanly on '-' into exactly SYSCAT / <compact_utc> / <short_hash> per the
    Unit-2 contract (test_scan_id_compact_utc_portion_matches_time).
    """
    # Normalise
    s = iso_str.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
        # Convert to UTC
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc)
        return dt.strftime("%Y%m%d%H%M%S")
    except (ValueError, AttributeError):
        # Fallback: keep only digits
        return re.sub(r"[^0-9]", "", iso_str.strip())[:14]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _make_id(prefix: str, source_ref: str) -> str:
    """Stable ID from prefix + source_ref hash."""
    digest = hashlib.sha256(source_ref.encode("utf-8")).hexdigest()[:8]
    slug = re.sub(r"[^a-z0-9_]", "_", Path(source_ref).stem.lower())[:24]
    return f"{prefix}_{slug}_{digest}"
