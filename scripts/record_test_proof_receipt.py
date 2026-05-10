#!/usr/bin/env python3
"""
Test/Proof Receipt Recorder v0
Runs a local verification command and records a safe receipt into the Business Ops Ledger.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

# Import ledger functions
try:
    from business_ops_ledger import append_event, append_operator_explanation
except ImportError:
    sys.path.append(os.getcwd())
    from business_ops_ledger import append_event, append_operator_explanation

# Import redaction
try:
    from pii_vault import redact_text
except ImportError:
    # Fallback if pii_vault is missing
    def redact_text(text: str) -> tuple[str, Any]:
        return text, None


def get_git_info() -> Dict[str, Any]:
    """Gather current git metadata."""
    def run_git(args: List[str]) -> str:
        try:
            res = subprocess.run(["git"] + args, capture_output=True, text=True, timeout=5)
            return res.stdout.strip() if res.returncode == 0 else "unknown"
        except Exception:
            return "unknown"

    branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    head = run_git(["rev-parse", "--short=8", "HEAD"])
    is_dirty = run_git(["status", "--porcelain"]) != ""

    return {
        "git_branch": branch,
        "git_head": head,
        "git_dirty": is_dirty
    }


def redact_secrets(text: str) -> str:
    """Apply pii_vault redaction and additional safe-guard patterns."""
    # 1. PII Redaction
    redacted, _ = redact_text(text)

    # 2. Basic Secret Patterns (e.g., KEY=val, TOKEN=val)
    # This is a defensive heuristic for command strings and output tails
    secret_patterns = [
        r"(?i)(key|token|password|secret|auth|credential|api[-_]?key)([:=]\s*)['\"]?[a-zA-Z0-9_\-\.]{8,}['\"]?"
    ]
    for pattern in secret_patterns:
        redacted = re.sub(pattern, r"\1\2[REDACTED]", redacted)

    return redacted


def record_receipt(
    label: str,
    command: List[str],
    exit_code: int,
    stdout_stderr: str,
    duration_ms: int,
    git_info: Dict[str, Any],
    db_path: Optional[str] = None
) -> str:
    """Constructs and records the test_proof_receipt event."""

    event_id = f"tpr_{uuid.uuid4().hex[:8]}"

    # Hash full combined output
    output_hash = hashlib.sha256(stdout_stderr.encode("utf-8")).hexdigest()

    # Bounded tail (last 10 lines)
    lines = stdout_stderr.splitlines()
    tail_lines = lines[-10:] if len(lines) > 10 else lines
    output_tail = "\n".join(tail_lines)

    # Redact
    redacted_command = redact_secrets(" ".join(command))
    redacted_tail = redact_secrets(output_tail)
    redaction_marker = (redacted_command != " ".join(command)) or (redacted_tail != output_tail)

    status = "pass" if exit_code == 0 else "fail"

    receipt = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "event_type": "test_proof_receipt",
        "command_label": label,
        "command_string": redacted_command,
        "exit_code": exit_code,
        "status": status,
        "git_branch": git_info["git_branch"],
        "git_head": git_info["git_head"],
        "git_dirty": git_info["git_dirty"],
        "duration_ms": duration_ms,
        "summary": f"{label} {status} (exit {exit_code})",
        "output_hash": output_hash,
        "output_tail": redacted_tail,
        "redaction_marker": redaction_marker,
        "actor_source": "test_proof_recorder_v0"
    }

    # Store JSON in operator_visible_summary (compacted)
    visible_summary = json.dumps(receipt, separators=(',', ':'))

    # Record Event
    success = append_event(
        event_id=event_id,
        event_type="test_proof_receipt",
        actor="test_proof_recorder_v0",
        operator_visible_summary=visible_summary,
        replay_safe=False,
        db_path=db_path
    )

    if success:
        # Record Explanation (Human Readable)
        append_operator_explanation(
            summary=receipt["summary"],
            event_id=event_id,
            safe_for_telegram=True,
            db_path=db_path
        )

    return event_id if success else ""


def main():
    parser = argparse.ArgumentParser(
        description="Run a command and record a test proof receipt to the ledger.",
        usage="python3 %(prog)s --label LABEL -- COMMAND [ARGS...]"
    )
    parser.add_argument("--label", required=True, help="Human-readable label for the check.")
    parser.add_argument("--db", help="Path to the ledger database.")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="The command to run.")

    args = parser.parse_args()

    # argparse.REMAINDER might include the '--' if not handled carefully
    command = args.command
    if command and command[0] == "--":
        command = command[1:]

    if not command:
        print("Error: No command provided.", file=sys.stderr)
        sys.exit(1)

    # Pre-flight git info
    git_info = get_git_info()

    # Execute
    start_time = time.time()
    try:
        # Use subprocess.run with capture_output=True, text=True
        # We combine stdout and stderr as per contract
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=300 # 5 minute default timeout
        )
        exit_code = result.returncode
        stdout_stderr = result.stdout + result.stderr
    except subprocess.TimeoutExpired as e:
        exit_code = 124 # Common timeout exit code
        stdout_stderr = f"Command timed out after 300s.\nSTDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}"
    except Exception as e:
        exit_code = 1
        stdout_stderr = f"Failed to execute command: {str(e)}"

    duration_ms = int((time.time() - start_time) * 1000)

    # Record
    event_id = record_receipt(
        label=args.label,
        command=command,
        exit_code=exit_code,
        stdout_stderr=stdout_stderr,
        duration_ms=duration_ms,
        git_info=git_info,
        db_path=args.db
    )

    if event_id:
        print(f"[Ledger] Test proof recorded: {event_id} ({args.label} -> {exit_code})")
    else:
        print(f"[Ledger] Error: Failed to record test proof for {args.label}", file=sys.stderr)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
