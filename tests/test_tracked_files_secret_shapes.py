"""Guard: no credential-shaped strings may live in git-tracked files.

openclaw-eyes is published on GitHub, and generated read-models, receipts, and
docs are tracked on purpose. This test scans every tracked text file for the
shapes real provider secrets take (Anthropic, OpenAI, OpenRouter, Google,
Telegram, GitHub, AWS, Slack, Twilio, Stripe, GoCardless, private keys) so a
secret cannot be committed by accident. It never prints a matched value.

Runtime secrets belong in ``.chief.env`` / ``.google-secrets/`` (untracked).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
MAX_FILE_BYTES = 4 * 1024 * 1024

# Paths that intentionally carry a fake credential shape (fixtures, docs).
# Add an entry with a reason instead of weakening a pattern.
ALLOWLIST: dict[str, str] = {}

SECRET_SHAPES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("anthropic_api_key", re.compile(r"(?<![A-Za-z0-9])sk-ant-[A-Za-z0-9_-]{20,}")),
    ("openrouter_api_key", re.compile(r"(?<![A-Za-z0-9])sk-or-v1-[0-9a-f]{40,}")),
    ("openai_api_key", re.compile(r"(?<![A-Za-z0-9_-])sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}")),
    ("google_api_key", re.compile(r"(?<![A-Za-z0-9])AIza[0-9A-Za-z_-]{35}(?![A-Za-z0-9_-])")),
    ("google_oauth_client_secret", re.compile(r"(?<![A-Za-z0-9])GOCSPX-[A-Za-z0-9_-]{20,}")),
    ("google_oauth_access_token", re.compile(r"(?<![A-Za-z0-9])ya29\.[A-Za-z0-9_-]{30,}")),
    ("google_oauth_refresh_token", re.compile(r"(?<![A-Za-z0-9/])1//0[A-Za-z0-9_-]{30,}")),
    ("telegram_bot_token", re.compile(r"(?<![0-9A-Za-z])[0-9]{8,10}:[A-Za-z0-9_-]{35}(?![A-Za-z0-9_-])")),
    ("github_token", re.compile(r"(?<![A-Za-z0-9])gh[pousr]_[A-Za-z0-9]{36,}")),
    ("github_fine_grained_pat", re.compile(r"(?<![A-Za-z0-9])github_pat_[A-Za-z0-9_]{80,}")),
    ("aws_access_key_id", re.compile(r"(?<![A-Z0-9])(?:AKIA|ASIA)[0-9A-Z]{16}(?![A-Z0-9])")),
    ("slack_token", re.compile(r"(?<![A-Za-z0-9])xox[baprs]-[0-9A-Za-z-]{10,}")),
    ("twilio_account_sid", re.compile(r"(?<![A-Za-z0-9])AC[0-9a-f]{32}(?![A-Za-z0-9])")),
    ("stripe_live_key", re.compile(r"(?<![A-Za-z0-9])[sr]k_live_[A-Za-z0-9]{20,}")),
    (
        "private_key_block",
        re.compile(
            r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----\r?\n\s*[A-Za-z0-9+/=]{16,}",
        ),
    ),
)

# GoCardless live tokens are ``live_`` plus ~40 mixed-case base64url characters.
# OpenClaw also uses ``live_`` as a snake_case identifier prefix (lower-case words,
# timestamps, lower-case hex), which is why GitHub secret scanning raised a false
# positive on a request id. Only flag a ``live_`` string whose body carries the
# upper-case letters a real token has and an identifier never does.
GOCARDLESS_CANDIDATE = re.compile(r"(?<![A-Za-z0-9])live_[A-Za-z0-9_-]{35,}")
GOCARDLESS_MIN_UPPER_CHARS = 4


def _looks_like_gocardless_token(candidate: str) -> bool:
    body = candidate[len("live_"):]
    return sum(1 for ch in body if ch.isupper()) >= GOCARDLESS_MIN_UPPER_CHARS


def find_secret_shapes(text: str) -> list[tuple[str, int]]:
    """Return ``(shape_name, line_number)`` for every credential-shaped match."""
    findings: list[tuple[str, int]] = []
    for name, pattern in SECRET_SHAPES:
        for match in pattern.finditer(text):
            findings.append((name, text.count("\n", 0, match.start()) + 1))
    for match in GOCARDLESS_CANDIDATE.finditer(text):
        if _looks_like_gocardless_token(match.group(0)):
            findings.append(("gocardless_live_token", text.count("\n", 0, match.start()) + 1))
    return findings


def tracked_text_files() -> list[Path]:
    raw = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    ).stdout
    files: list[Path] = []
    for rel in raw.decode("utf-8", errors="surrogateescape").split("\0"):
        if not rel or rel in ALLOWLIST:
            continue
        path = REPO_ROOT / rel
        if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
            continue
        with path.open("rb") as handle:
            head = handle.read(8192)
        if b"\0" in head:
            continue
        files.append(path)
    return files


def test_no_secret_shapes_in_tracked_files() -> None:
    offenders: list[str] = []
    for path in tracked_text_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for name, line in find_secret_shapes(text):
            offenders.append(f"{path.relative_to(REPO_ROOT).as_posix()}:{line} [{name}]")
    assert not offenders, (
        "credential-shaped strings found in tracked files (value withheld); "
        "move the secret to .chief.env or an untracked secrets path and rotate it:\n  "
        + "\n  ".join(offenders)
    )


def test_allowlist_entries_are_tracked_files() -> None:
    for rel in ALLOWLIST:
        assert (REPO_ROOT / rel).is_file(), f"stale ALLOWLIST entry: {rel}"


# --- scanner self-checks: synthetic samples are assembled at runtime so this
# file never contains a literal that looks like a credential.


@pytest.mark.parametrize(
    ("shape", "sample"),
    [
        ("anthropic_api_key", "sk-ant-" + "api03-" + "A1" * 24),
        ("openrouter_api_key", "sk-or-v1-" + "0a" * 32),
        ("openai_api_key", "sk-proj-" + "Zq9" * 16),
        ("google_api_key", "AIza" + "Sy" + "D0" * 16 + "_"),
        ("google_oauth_client_secret", "GOCSPX-" + "Ab1" * 8),
        ("google_oauth_access_token", "ya29." + "a0" * 20),
        ("google_oauth_refresh_token", "1//0" + "g" * 40),
        ("telegram_bot_token", "12345678" + "9:" + "A" * 35),
        ("github_token", "ghp_" + "x" * 36),
        ("github_fine_grained_pat", "github_pat_" + "1" * 82),
        ("aws_access_key_id", "AKIA" + "ABCDEFGH12345678"),
        ("slack_token", "xoxb-" + "1234567890-" + "abcdef"),
        ("twilio_account_sid", "AC" + "0f" * 16),
        ("stripe_live_key", "sk_live_" + "Q1" * 12),
        ("private_key_block", "-----BEGIN PRIVATE KEY-----\n" + "MIIE" + "A" * 40 + "\n"),
        ("gocardless_live_token", "live_" + "Zx9" * 14),
    ],
)
def test_scanner_detects_each_shape(shape: str, sample: str) -> None:
    text = f"token = '{sample}'\n"
    assert shape in {name for name, _ in find_secret_shapes(text)}


@pytest.mark.parametrize(
    "benign",
    [
        "phase_c_task_id: task-028d12136c84b878d69ad97f2e7fde8",  # 'sk-' inside 'task-'
        "request_id: live_controller_event_router_status_readback_v0_phase_two",
        "live_arts_candidate_status_contract_ready_packet_extension",
        "live_controller_event_1750000000000_9f8e7d6c5b4a_readback_receipt",
        'forbidden_patterns = ("-----BEGIN PRIVATE KEY-----", "Bearer ")',
        "sha256:b3190e6a519ab661aa407c29e5874d3640c74955e95c08fbbbef9cc4cbbee286",
        "commit 4ca4ed42171c23d60ef89493559808ef2789a19e",
    ],
)
def test_scanner_ignores_identifiers_and_hashes(benign: str) -> None:
    assert find_secret_shapes(benign + "\n") == []
