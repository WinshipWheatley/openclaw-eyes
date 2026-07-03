#!/usr/bin/env python3
"""local_builder.py — Thin agent wrapper for local Ollama models.

Drop-in replacement for `ollama run model < prompt`. Instead of piping text,
this script uses the Ollama chat API with tool definitions so the model can
read files, run safe commands, and write pc_output.md.

Usage:
    python3 polish_loop/local_builder.py --model gemma4:e4b --timeout 3600
    python3 polish_loop/local_builder.py --model gemma4:31b --timeout 3600

Exit codes:
    0  — pc_output.md was written and passes orchestrator validation
    1  — model failed to produce valid pc_output.md
    124 — timeout
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────

def _initial_work_dir() -> Path:
    if os.environ.get("OPENCLAW_BUILDER_WORK_DIR"):
        return Path(os.environ["OPENCLAW_BUILDER_WORK_DIR"]).resolve()
    if os.environ.get("PHASE_C_TASK_MD"):
        task_path = Path(os.environ["PHASE_C_TASK_MD"]).resolve()
        if len(task_path.parents) >= 2:
            return task_path.parents[1]
    return Path("/home/openclaw").resolve()


WORK_DIR = _initial_work_dir()
LOOP_DIR = WORK_DIR / "polish_loop"
PC_OUTPUT = Path(os.environ.get("PHASE_C_PC_OUTPUT", str(LOOP_DIR / "current" / "pc_output.md"))).resolve()
TASK_MD = Path(os.environ.get("PHASE_C_TASK_MD", str(LOOP_DIR / "task.md"))).resolve()
STATUS_JSON = LOOP_DIR / "status.json"
PC_CONTEXT = LOOP_DIR / "pc_context.md"
MAC_REVIEW = LOOP_DIR / "current" / "mac_review.md"
PROMPT_FILE = LOOP_DIR / "POLISH_PROMPT.md"
LOG_FILE = LOOP_DIR / "local_builder.log"
OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

# ── Limits ───────────────────────────────────────────────────────────────────

MAX_TURNS = 40              # generous for 31B multi-step tasks
MAX_TOOL_CALLS = 15         # hard cap — force write_file or abort after this many
MAX_READ_LINES = 500        # per file read
MAX_READ_CHARS = 8000       # cap read_file result in conversation state
MAX_CMD_OUTPUT = 6000       # chars per command
STALL_LIMIT = 3             # consecutive no-tool turns → abort
MAX_NUDGES = 2              # don't spam nudge messages
API_TIMEOUT = 900           # per-turn Ollama HTTP timeout (seconds)
CONTEXT_BUDGET_CHARS = 200_000  # rough char budget before trimming old turns

SHELL_CONTROL_TOKENS = ("&&", "||", ";", "|", "`", "$(", "+", "\n", "\r")
ALLOWED_GIT_SUBCOMMANDS = frozenset({"status", "diff", "log", "show"})
ALLOWED_INSPECTION_PROGRAMS = frozenset(
    {"cat", "head", "tail", "ls", "wc", "grep", "stat", "test"}
)
ALLOWED_PYTHON_MODULES = frozenset({"pytest", "py_compile"})

# Only this file may be written in read-only mode.
WRITABLE_PATHS = frozenset({PC_OUTPUT})


def _configure_runtime_paths(
    work_dir: str | Path,
    *,
    pc_output_path: str | Path | None = None,
    task_path: str | Path | None = None,
) -> None:
    """Point builder file tools and commands at an isolated repo worktree."""

    global WORK_DIR, LOOP_DIR, PC_OUTPUT, TASK_MD, STATUS_JSON, PC_CONTEXT, MAC_REVIEW, PROMPT_FILE, LOG_FILE, WRITABLE_PATHS

    WORK_DIR = Path(work_dir).resolve()
    LOOP_DIR = WORK_DIR / "polish_loop"
    PC_OUTPUT = Path(pc_output_path).resolve() if pc_output_path is not None else LOOP_DIR / "current" / "pc_output.md"
    TASK_MD = Path(task_path).resolve() if task_path is not None else LOOP_DIR / "task.md"
    STATUS_JSON = LOOP_DIR / "status.json"
    PC_CONTEXT = LOOP_DIR / "pc_context.md"
    MAC_REVIEW = LOOP_DIR / "current" / "mac_review.md"
    PROMPT_FILE = LOOP_DIR / "POLISH_PROMPT.md"
    LOG_FILE = LOOP_DIR / "local_builder.log"
    WRITABLE_PATHS = frozenset({PC_OUTPUT})


def _copy_runtime_file(live_root: Path, worktree: Path, relative_path: str) -> None:
    src = live_root / relative_path
    if not src.exists() or not src.is_file():
        return
    dest = worktree / relative_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def _copy_runtime_inputs_to_worktree(live_root: Path, worktree: Path) -> None:
    for relative_path in (
        "polish_loop/POLISH_PROMPT.md",
        "polish_loop/task.md",
        "polish_loop/status.json",
        "polish_loop/pc_context.md",
        "polish_loop/current/mac_review.md",
    ):
        _copy_runtime_file(live_root, worktree, relative_path)


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _resolve_tool_path(path_str: str) -> Path:
    p = Path(path_str)
    if not p.is_absolute():
        p = WORK_DIR / p
    return p.resolve()


@contextmanager
def _isolated_builder_worktree(repo_root: str | Path):
    """Create and clean up a detached throwaway worktree for builder execution."""

    root = Path(repo_root).resolve()
    if os.environ.get("OPENCLAW_LOCAL_BUILDER_DISABLE_WORKTREE", "").strip().lower() in {"1", "true", "yes", "on"}:
        yield root
        return

    worktree_parent = Path(
        os.environ.get("OPENCLAW_LOCAL_BUILDER_WORKTREE_ROOT", "/tmp/openclaw-local-builder-worktrees")
    )
    worktree_parent.mkdir(parents=True, exist_ok=True)
    worktree_path = Path(tempfile.mkdtemp(prefix="local-builder-", dir=str(worktree_parent)))
    shutil.rmtree(worktree_path)
    try:
        subprocess.run(
            ["git", "worktree", "add", "--detach", str(worktree_path), "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
        )
        _copy_runtime_inputs_to_worktree(root, worktree_path)
        yield worktree_path
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree_path)],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if worktree_path.exists():
            shutil.rmtree(worktree_path, ignore_errors=True)


# ── Logging ──────────────────────────────────────────────────────────────────


def _log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [local_builder] {msg}"
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ── Tool definitions for Ollama chat API ─────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read a file from the filesystem. Returns up to 500 lines. "
                "Use an absolute path starting with /home/openclaw/."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path under the configured builder worktree.",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": (
                "Run a safe argv-tokenized command and return stdout+stderr. "
                "Allowed: git status/diff/log/show, python -m pytest, pytest, and narrow inspection commands. "
                "Shell control, chaining, and unrecognized commands are refused."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to run.",
                    }
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Write content to pc_output.md. This is how you submit your pass output. "
                "The path MUST be the configured pc_output.md path. "
                "The content MUST start with 'PASS: <number>' on the first line."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Must be the configured pc_output.md path.",
                    },
                    "content": {
                        "type": "string",
                        "description": "The full content to write to the file.",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "insert_block",
            "description": (
                "Insert a block of text into an existing file after an exact anchor line. "
                "Safer than sed for multi-line Python edits. The anchor must appear exactly once "
                "in the file. Use this for adding imports, new functions, or new test cases."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the file to edit.",
                    },
                    "anchor": {
                        "type": "string",
                        "description": "Exact text of the line to insert after. Must match exactly one line.",
                    },
                    "content": {
                        "type": "string",
                        "description": "The block of text to insert after the anchor line.",
                    },
                },
                "required": ["path", "anchor", "content"],
            },
        },
    },
]


# ── Tool execution ───────────────────────────────────────────────────────────

# Tracks basenames of files successfully read — used to block redundant rediscovery.
_confirmed_files: set[str] = set()

# Tracks successful insert_block operations this run — prevents duplicate insertions after context trim.
_completed_inserts: set[tuple[str, str]] = set()


def _is_queue_path(path_str: str) -> bool:
    """Block reads/commands targeting the task queue — active task is already injected."""
    s = path_str.rstrip("/")
    return "/polish_loop/tasks" in s


def _exec_read_file(args: dict) -> str:
    path_str = args.get("path", "")
    if not path_str:
        return "ERROR: path is required"
    if _is_queue_path(path_str):
        return "BLOCKED: task queue is off-limits. The active task from task.md is already in your context. Execute it directly."
    p = _resolve_tool_path(path_str)
    if not _is_under(p, WORK_DIR):
        return f"ERROR: read denied outside builder worktree: {p}"
    # Block re-reading any already-confirmed file (same path = redundant, different path = wandering)
    basename = p.name
    if str(p) in _confirmed_files:
        return f"BLOCKED: {p.name} was already read and is in your context. Do not reread it. Use the content you already have."
    if basename in _confirmed_files:
        return f"BLOCKED: {basename} was already read from a confirmed path. Do not re-discover it. Execute the task."
    if not p.exists():
        return f"ERROR: file not found: {p}"
    if not p.is_file():
        return f"ERROR: not a file: {p}"
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        # Track successful read by both basename and full path
        _confirmed_files.add(basename)
        _confirmed_files.add(str(p))
        if len(lines) > MAX_READ_LINES:
            lines = lines[:MAX_READ_LINES]
        text = "\n".join(lines)
        if len(text) > MAX_READ_CHARS:
            text = text[:MAX_READ_CHARS] + f"\n... (truncated at {MAX_READ_CHARS} chars, {len(lines)} lines total)"
        return text
    except Exception as e:
        return f"ERROR: {e}"


def _is_scouting_command(cmd: str) -> bool:
    """Block broad orientation/discovery or redundant verification commands."""
    # Block task-queue inspection
    if _is_queue_path(cmd):
        return True

    # Block recursive listing of the loop directory itself
    if "ls -R" in cmd and "polish_loop" in cmd:
        return True

    # Block any ls targeting the workspace root (generic startup scouting)
    if cmd.startswith("ls ") and "/home/openclaw" in cmd:
        parts = cmd.split()
        target = parts[-1].rstrip("/")
        if target == "/home/openclaw":
            return True

    # Block re-verifying already-confirmed files with shell inspection commands
    # (sed -i is exempt — it's a write, not a read)
    # (grep is exempt — it returns narrow matches, needed when read_file truncates large files)
    inspect_prefixes = (
        "ls ", "cat ", "head ", "tail ",
        "wc ", "stat ", "test "
    )
    if cmd.startswith(inspect_prefixes):
        for confirmed in _confirmed_files:
            if confirmed in cmd:
                return True
    if cmd.startswith("sed ") and not cmd.startswith("sed -i"):
        for confirmed in _confirmed_files:
            if confirmed in cmd:
                return True

    # Block Python one-liners that simulate or re-check writes against confirmed files
    if cmd.startswith(("python -c ", "python3 -c ")):
        for confirmed in _confirmed_files:
            if confirmed in cmd:
                return True
        suspicious = (
            "Path(", ".read_text(", ".write_text(", "open(", "exists(", "is_file("
        )
        if any(token in cmd for token in suspicious):
            return True

    return False


def _contains_shell_control(cmd: str) -> bool:
    return any(token in cmd for token in SHELL_CONTROL_TOKENS)


def _program_name(argv0: str) -> str:
    return Path(argv0).name


def _is_allowed_argv(argv: list[str]) -> bool:
    if not argv:
        return False

    program = _program_name(argv[0])
    if program == "git":
        return len(argv) >= 2 and argv[1] in ALLOWED_GIT_SUBCOMMANDS

    if program in {"python", "python3", _program_name(sys.executable)}:
        return (
            len(argv) >= 3
            and argv[1] == "-m"
            and argv[2] in ALLOWED_PYTHON_MODULES
        )

    if program == "pytest":
        return True

    return program in ALLOWED_INSPECTION_PROGRAMS


def _tokenize_allowed_command(cmd: str) -> tuple[list[str] | None, str | None]:
    if _contains_shell_control(cmd):
        return None, "shell control metacharacters are not allowed"
    try:
        argv = shlex.split(cmd)
    except ValueError as exc:
        return None, f"could not parse command: {exc}"
    if not _is_allowed_argv(argv):
        return None, "command argv is not on the explicit allowlist"
    return argv, None


def _exec_run_command(args: dict) -> str:
    cmd = args.get("command", "").strip()
    if not cmd:
        return "ERROR: command is required"
    argv, deny_reason = _tokenize_allowed_command(cmd)
    if argv is None:
        return f"ERROR: command not allowed: {deny_reason}"
    if _is_scouting_command(cmd):
        return "BLOCKED: scouting not allowed. The active task is already in your context. Execute it directly — read the files it names, run the commands it specifies, then write pc_output.md."
    try:
        result = subprocess.run(
            argv, shell=False, capture_output=True, text=True,
            timeout=120, cwd=str(WORK_DIR),
        )
        output = (result.stdout + result.stderr).strip()
        if len(output) > MAX_CMD_OUTPUT:
            output = output[:MAX_CMD_OUTPUT] + f"\n... (truncated at {MAX_CMD_OUTPUT} chars)"
        exit_note = f"[exit code: {result.returncode}]"
        return f"{output}\n{exit_note}" if output else exit_note
    except subprocess.TimeoutExpired:
        return "ERROR: command timed out after 120s"
    except Exception as e:
        return f"ERROR: {e}"


def _exec_write_file(args: dict) -> str:
    path_str = args.get("path", "")
    content = args.get("content", "")
    if not path_str:
        return "ERROR: path is required"
    p = _resolve_tool_path(path_str)
    if p not in WRITABLE_PATHS and not _is_under(p, WORK_DIR / "tests"):
        return f"ERROR: write denied. Writable: {PC_OUTPUT} and files under {WORK_DIR}/tests/"
    if not content.strip():
        return "ERROR: content is empty"
    # Guard: refuse to replace an existing file with drastically shorter content
    if p.exists() and p not in WRITABLE_PATHS:
        existing_size = p.stat().st_size
        if existing_size > 200 and len(content) < existing_size * 0.5:
            return (
                f"ERROR: write refused — new content ({len(content)} bytes) is less than "
                f"half the existing file ({existing_size} bytes). Use insert_block for small "
                f"edits instead of rewriting the entire file."
            )
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"OK: wrote {len(content)} bytes to {p}"
    except Exception as e:
        return f"ERROR: {e}"


def _exec_insert_block(args: dict) -> str:
    path_str = args.get("path", "")
    anchor = args.get("anchor", "")
    content = args.get("content", "")
    if not path_str or not anchor or not content:
        return "ERROR: path, anchor, and content are all required"
    # Refuse duplicate insert on same path+anchor within one run
    insert_key = (path_str, anchor.strip())
    if insert_key in _completed_inserts:
        return f"BLOCKED: insert_block already succeeded for this anchor in this run. Move to the next step."
    p = _resolve_tool_path(path_str)
    if not _is_under(p, WORK_DIR / "tests"):
        return f"ERROR: insert_block only allowed for files under {WORK_DIR}/tests/"
    if not p.exists():
        return f"ERROR: file not found: {p}"
    try:
        lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
    except Exception as e:
        return f"ERROR: {e}"
    # Find exact anchor (stripped match to tolerate trailing whitespace)
    anchor_stripped = anchor.strip()
    matches = [i for i, line in enumerate(lines) if line.strip() == anchor_stripped]
    if len(matches) == 0:
        return f"ERROR: anchor not found: {anchor!r}"
    if len(matches) > 1:
        return f"ERROR: anchor is ambiguous ({len(matches)} matches). Use a more unique line."
    idx = matches[0]
    # Ensure inserted content ends with newline
    insert = content if content.endswith("\n") else content + "\n"
    lines.insert(idx + 1, insert)
    try:
        p.write_text("".join(lines), encoding="utf-8")
        _completed_inserts.add(insert_key)
        return f"OK: inserted {len(insert)} chars after line {idx + 1} in {p.name}"
    except Exception as e:
        return f"ERROR: {e}"


TOOL_DISPATCH = {
    "read_file": _exec_read_file,
    "run_command": _exec_run_command,
    "write_file": _exec_write_file,
    "insert_block": _exec_insert_block,
}


# ── Ollama chat API ──────────────────────────────────────────────────────────


def _chat(model: str, messages: list[dict]) -> dict:
    """Call Ollama /api/chat and return the response dict."""
    import urllib.request

    payload = json.dumps({
        "model": model,
        "messages": messages,
        "tools": TOOLS,
        "stream": False,
        "options": {"num_ctx": 16384},
    }).encode()

    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=API_TIMEOUT) as resp:
        return json.loads(resp.read())


# ── Context management ───────────────────────────────────────────────────────


def _estimate_context_chars(messages: list[dict]) -> int:
    total = 0
    for m in messages:
        total += len(m.get("content", ""))
        for tc in m.get("tool_calls", []):
            total += len(json.dumps(tc.get("function", {}).get("arguments", {})))
    return total


def _trim_context(messages: list[dict]) -> list[dict]:
    """Drop the oldest tool result turns (not system/initial user) to fit budget."""
    if _estimate_context_chars(messages) <= CONTEXT_BUDGET_CHARS:
        return messages
    # Keep: system (index 0), initial user (index 1), last 10 messages
    protected = 2
    keep_tail = 10
    if len(messages) <= protected + keep_tail:
        return messages
    trimmed = messages[:protected] + messages[-(keep_tail):]
    _log(f"context trimmed: {len(messages)} → {len(trimmed)} messages")
    return trimmed


# ── Build initial context ────────────────────────────────────────────────────


def _read_pass_number() -> int:
    try:
        with open(STATUS_JSON) as f:
            return int(json.load(f).get("pass", 1))
    except Exception:
        return 1


def _build_system_prompt(pass_num: int) -> str:
    return (
        "You are a builder agent for the OpenClaw polish loop. "
        "You have three tools: read_file, run_command, write_file.\n\n"
        "EXECUTION DISCIPLINE:\n"
        "- task.md is ALREADY LOADED in your first user message below. It is the SOLE authority. "
        "Do NOT re-read task.md, search for task.md, or inspect the tasks/ queue directory.\n"
        "- Your FIRST tool call must be the direct action implied by the task "
        "(e.g. run_command for a test, read_file for a specific file named in the task). "
        "Do NOT scout, list directories, or orient first.\n"
        "- Do NOT use ls, find, or broad inspection unless a prior direct command FAILED "
        "and the error evidence requires path discovery.\n"
        "- Once a path is confirmed working, never re-verify it.\n"
        "- You have a HARD BUDGET of 15 tool calls total. Use them surgically.\n"
        "- Ideal flow: 1-2 reads, 1 run_command, 1 write_file. Exploration is waste.\n"
        "- If you cannot complete the task, write pc_output.md with STATUS: BLOCKED "
        "and the exact error evidence. Do NOT wander looking for workarounds.\n\n"
        "RULES:\n"
        "1. Do NOT hallucinate file contents or test results. Use read_file and run_command to get real data.\n"
        "2. When you are done, you MUST call write_file to write pc_output.md. "
        "Your pass is not complete until pc_output.md is written.\n"
        "3. If you cannot complete the task, write pc_output.md with STATUS: BLOCKED and explain why.\n\n"
        f"CRITICAL FORMAT for pc_output.md (plain text, no markdown headers, no emojis):\n\n"
        f"PASS: {pass_num}\n"
        "STATUS: DONE\n\n"
        "CHANGES:\n"
        "- [list files changed, or 'No files changed']\n\n"
        "REASONING:\n"
        "[why you made these choices]\n\n"
        "ROLLBACK PLAN:\n"
        "[how to revert, or 'Nothing to revert']\n\n"
        "COST:\n"
        "- Unavailable (local model)\n\n"
        "TRUTH:\n"
        "- Verified: [what you actually ran/checked with real tool output]\n"
        "- Unavailable: [what you could not check]\n\n"
        "HEADROOM:\n"
        "- Ollama: local runner, no provider limits\n\n"
        "CONCERNS:\n"
        "[any issues, or NONE]\n\n"
        "The file MUST start with 'PASS: ' followed by the pass number on the very first line. "
        "Do NOT use markdown headers (#), tables, or emojis. Plain text only. "
        "Do NOT wrap content in code fences."
    )


def _build_initial_user_message(pass_num: int) -> str:
    """Pre-read the key context files and inject them so the model starts with real data."""
    parts = []

    if PROMPT_FILE.exists():
        parts.append("=== POLISH PROMPT ===\n" + PROMPT_FILE.read_text(encoding="utf-8").strip())

    if TASK_MD.exists():
        parts.append(
            "=== TASK AUTHORITY ===\n"
            "Ignore any session goals, ACTIVE TASK labels, or queue references in pc_context.md above.\n"
            "The ONE task for this pass is the TASK block below.\n"
            "Do not replace it with any other task or search for another task file.\n\n"
            "=== TASK ===\n" + TASK_MD.read_text(encoding="utf-8").strip()
        )

    if STATUS_JSON.exists():
        try:
            status_data = json.loads(STATUS_JSON.read_text(encoding="utf-8"))
            status_data.pop("task_name", None)
            parts.append("=== STATUS ===\n" + json.dumps(status_data, indent=2))
        except (json.JSONDecodeError, OSError):
            pass

    if pass_num > 1 and MAC_REVIEW.exists():
        review = MAC_REVIEW.read_text(encoding="utf-8").strip()
        if len(review) > 3000:
            review = review[:3000] + "\n... (truncated)"
        parts.append("=== MAC REVIEW (address these issues first) ===\n" + review)

    if PC_CONTEXT.exists():
        ctx = PC_CONTEXT.read_text(encoding="utf-8").strip()
        if len(ctx) > 2000:
            ctx = ctx[:2000] + "\n... (truncated)"
        parts.append("=== PC CONTEXT ===\n" + ctx)

    parts.append(
        "\n=== INSTRUCTIONS ===\n"
        "Complete the task described above using your tools.\n"
        "1. Read any files mentioned in the task.\n"
        "2. Run the verification commands specified in the task.\n"
        "3. Write pc_output.md with the results using the exact format from the system prompt.\n"
        "Start now."
    )
    return "\n\n".join(parts)


# ── Output validation ────────────────────────────────────────────────────────


def _validate_pc_output(pass_num: int) -> tuple[bool, str]:
    """Quick local check that pc_output.md will pass orchestrator validation."""
    if not PC_OUTPUT.exists():
        return False, "file missing"
    text = PC_OUTPUT.read_text(encoding="utf-8").strip()
    if not text:
        return False, "file empty"

    # Must start with PASS: N (possibly after RUNNER: header)
    lines = text.splitlines()
    first = lines[0].strip()
    if first.upper().startswith("RUNNER:") and len(lines) > 1:
        first = lines[1].strip()
    if not first.upper().startswith("PASS:"):
        return False, f"first line is '{first[:40]}', expected 'PASS: {pass_num}'"
    try:
        found_pass = int(first.split(":", 1)[1].strip())
    except (ValueError, IndexError):
        return False, f"cannot parse pass number from '{first}'"
    if found_pass != pass_num:
        return False, f"PASS: {found_pass} but expected {pass_num}"

    # Must have STATUS:
    if not any(line.strip().upper().startswith("STATUS:") for line in lines):
        return False, "missing STATUS: line"

    # Must have CHANGES: and REASONING: sections
    full = text.upper()
    for section in ("CHANGES:", "REASONING:"):
        if section not in full:
            return False, f"missing {section} section"

    return True, "ok"


# ── Main agent loop ──────────────────────────────────────────────────────────


def run(model: str, timeout: int) -> int:
    live_work_dir = WORK_DIR
    live_pc_output = PC_OUTPUT
    live_task_md = TASK_MD

    with _isolated_builder_worktree(live_work_dir) as builder_worktree:
        _configure_runtime_paths(
            builder_worktree,
            pc_output_path=live_pc_output,
            task_path=builder_worktree / "polish_loop" / "task.md",
        )
        try:
            _log(f"isolated worktree={builder_worktree}")
            return _run_configured(model, timeout)
        finally:
            _configure_runtime_paths(
                live_work_dir,
                pc_output_path=live_pc_output,
                task_path=live_task_md,
            )


def _run_configured(model: str, timeout: int) -> int:
    _confirmed_files.clear()
    _completed_inserts.clear()
    deadline = time.time() + timeout
    if not TASK_MD.exists():
        _log("ABORT: task.md does not exist — nothing to execute")
        return 1
    pass_num = _read_pass_number()
    _log(f"pass={pass_num}, model={model}, timeout={timeout}s")

    messages: list[dict] = [
        {"role": "system", "content": _build_system_prompt(pass_num)},
        {"role": "user", "content": _build_initial_user_message(pass_num)},
    ]

    stall_count = 0
    nudge_count = 0
    budget_nudge_count = 0
    pc_output_written = False
    total_tool_calls = 0

    for turn in range(MAX_TURNS):
        remaining = deadline - time.time()
        if remaining <= 0:
            _log(f"timeout after {timeout}s at turn {turn + 1}")
            return 124

        _log(f"turn {turn + 1}/{MAX_TURNS}, {remaining:.0f}s remaining, context ~{_estimate_context_chars(messages)//1000}k chars")

        # Trim context if it's getting too large
        messages = _trim_context(messages)

        try:
            response = _chat(model, messages)
        except Exception as e:
            _log(f"API error: {e}")
            # Retry once after a brief pause — ollama can be slow to respond for large models
            if "timed out" in str(e).lower() or "timeout" in str(e).lower():
                _log("retrying after API timeout...")
                time.sleep(5)
                try:
                    response = _chat(model, messages)
                except Exception as e2:
                    _log(f"API error on retry: {e2}")
                    return 1
            else:
                return 1

        msg = response.get("message", {})
        content = msg.get("content", "")
        tool_calls = msg.get("tool_calls") or []

        messages.append(msg)

        if content:
            _log(f"assistant: {content[:200]}{'...' if len(content) > 200 else ''}")

        if not tool_calls:
            stall_count += 1

            # Auto-persist: if model emitted pc_output content as text during forced finalization
            if budget_nudge_count > 0 and not pc_output_written and content.strip().startswith("PASS:"):
                _log("auto-persisting assistant text as pc_output.md (budget-forced finalization)")
                try:
                    PC_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
                    PC_OUTPUT.write_text(content.strip(), encoding="utf-8")
                    pc_output_written = True
                except Exception as e:
                    _log(f"auto-persist failed: {e}")

            if pc_output_written:
                _log("pc_output.md written and model stopped calling tools — checking validity")
                valid, reason = _validate_pc_output(pass_num)
                if valid:
                    _log(f"pc_output.md valid — success ({total_tool_calls} tool calls)")
                    return 0
                else:
                    _log(f"pc_output.md written but invalid: {reason}")
                    # Give model a chance to fix it
                    pc_output_written = False
                    messages.append({
                        "role": "user",
                        "content": (
                            f"Your pc_output.md is invalid: {reason}. "
                            "Call write_file again with corrected content. "
                            f"The file MUST start with 'PASS: {pass_num}' on the very first line."
                        ),
                    })
                    continue

            if stall_count >= STALL_LIMIT:
                _log(f"{STALL_LIMIT} consecutive stalls without pc_output — aborting")
                return 1

            if nudge_count < MAX_NUDGES:
                nudge_count += 1
                messages.append({
                    "role": "user",
                    "content": (
                        "You need to use your tools to complete the task. "
                        "Call read_file, run_command, or write_file now. "
                        "If you are done with the work, call write_file to write pc_output.md."
                    ),
                })
            continue

        stall_count = 0

        # ── Tool budget enforcement ──
        if total_tool_calls >= MAX_TOOL_CALLS and not pc_output_written:
            budget_nudge_count += 1
            if budget_nudge_count > 2:
                _log(f"tool budget exhausted and model ignored {budget_nudge_count - 1} write demands — aborting")
                return 1
            _log(f"tool budget exhausted ({total_tool_calls}/{MAX_TOOL_CALLS}) — forcing write (attempt {budget_nudge_count})")
            messages.append({
                "role": "user",
                "content": (
                    f"You have used {total_tool_calls} tool calls (budget: {MAX_TOOL_CALLS}). "
                    "You MUST call write_file NOW to write pc_output.md with whatever "
                    "results you have. Use STATUS: BLOCKED if the task is incomplete."
                ),
            })
            continue

        for tc in tool_calls:
            fn_name = tc.get("function", {}).get("name", "")
            fn_args = tc.get("function", {}).get("arguments", {})
            if isinstance(fn_args, str):
                try:
                    fn_args = json.loads(fn_args)
                except json.JSONDecodeError:
                    fn_args = {}

            handler = TOOL_DISPATCH.get(fn_name)
            if handler is None:
                result = f"ERROR: unknown tool '{fn_name}'"
                _log(f"unknown tool: {fn_name}")
            else:
                _log(f"tool: {fn_name}({json.dumps(fn_args)[:120]})")
                result = handler(fn_args)
                if result.startswith("BLOCKED"):
                    _log(f"  → BLOCKED (not counted against budget)")
                else:
                    total_tool_calls += 1

            if fn_name == "write_file" and result.startswith("OK:"):
                write_path = str(fn_args.get("path", ""))
                if str(PC_OUTPUT) in write_path:
                    pc_output_written = True
                else:
                    # Repo edit succeeded — aggressively trim to free context for verification + closeout
                    protected = 2  # system + initial user
                    keep_tail = 6  # recent messages only
                    if len(messages) > protected + keep_tail:
                        messages = messages[:protected] + messages[-(keep_tail):]
                        _log(f"post-edit context trim: kept {len(messages)} messages")

            if fn_name == "insert_block" and result.startswith("OK:"):
                    protected = 2
                    keep_tail = 6
                    if len(messages) > protected + keep_tail:
                        messages = messages[:protected] + messages[-(keep_tail):]
                        _log(f"post-edit context trim: kept {len(messages)} messages")

            messages.append({"role": "tool", "content": result})

    # Exhausted turns
    if pc_output_written:
        valid, reason = _validate_pc_output(pass_num)
        if valid:
            _log(f"max turns but pc_output valid — success ({total_tool_calls} tool calls)")
            return 0
        _log(f"max turns and pc_output invalid: {reason}")
        return 1

    _log(f"max turns ({MAX_TURNS}) exhausted, no valid pc_output.md — fail")
    return 1


# ── Entry point ──────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Local Ollama builder wrapper")
    parser.add_argument("--model", default="ornith:9b", help="Ollama model to use")
    parser.add_argument("--timeout", type=int, default=3600, help="Timeout in seconds")
    args = parser.parse_args()

    PC_OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    _log(f"starting model={args.model} timeout={args.timeout}s")
    rc = run(args.model, args.timeout)
    _log(f"exiting with code {rc}")
    sys.exit(rc)


if __name__ == "__main__":
    main()
