#!/usr/bin/env python3
"""Run the ignored Hermes gateway runtime through tracked OpenClaw policy."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
from typing import Callable, Mapping, MutableMapping, Any

REPO_ROOT = Path(__file__).resolve().parents[1]
HERMES_ROOT = REPO_ROOT / "sidecars" / "hermes"
OPENCLAW_GATEWAY_ENV_DEFAULTS = {
    "HERMES_OPENCLAW_MODE": "gateway",
    "HERMES_OPENCLAW_GATEWAY": "1",
    "HERMES_OPENCLAW_DISABLE_EXTERNAL_FALLBACK": "1",
    "HERMES_OPENCLAW_GATEWAY_REPLY_TIMEOUT_SECONDS": "45",
    "HERMES_OPENCLAW_GATEWAY_NO_CHUNK_TIMEOUT_SECONDS": "20",
    "HERMES_OPENCLAW_GATEWAY_MAX_STREAM_RETRIES": "1",
    "HERMES_OPENCLAW_GATEWAY_STALE_CARRYOVER_POLICY": "sanitize-and-fail-short",
}


def _configure_import_paths() -> None:
    for path in (REPO_ROOT, HERMES_ROOT):
        value = str(path)
        if value not in sys.path:
            sys.path.insert(0, value)


def configure_gateway_environment() -> dict[str, str]:
    """Install OpenClaw Hermes safety defaults without overriding operator pins."""

    for key, value in OPENCLAW_GATEWAY_ENV_DEFAULTS.items():
        os.environ.setdefault(key, value)
    return {key: os.environ[key] for key in OPENCLAW_GATEWAY_ENV_DEFAULTS}


def _load_hermes_runtime_environment() -> None:
    """Load the vendor-owned runtime env without rendering any value."""

    hermes_home = Path(os.environ.get("HERMES_HOME", REPO_ROOT / "sidecars" / "hermes_home"))
    env_path = hermes_home / ".env"
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path, override=False)
    except Exception as exc:
        print(
            f"[hermes_listener] runtime environment load failed ({exc.__class__.__name__}); "
            "identity preflight will fail closed if HERMES_BOT_TOKEN is unavailable.",
            file=sys.stderr,
        )


def preflight_hermes_bot_identity(
    *,
    environ: MutableMapping[str, str] | None = None,
    fetch_json: Callable[[str], Mapping[str, Any]] | None = None,
) -> None:
    """Verify canonical Hermes identity, then remap for the vendor adapter.

    The vendored Hermes Telegram adapter reads generic TELEGRAM_BOT_TOKEN.  It
    is never allowed to select that generic name itself: this tracked launcher
    requires HERMES_BOT_TOKEN, validates it against HERMES_EXPECTED_BOT_USERNAME
    through getMe, and only then replaces the vendor variable in-process.
    """

    values = os.environ if environ is None else environ
    from telegram_listener_integrity import preflight_bot_token_identity, resolve_role_bot_token

    token = resolve_role_bot_token("hermes", environ=values)
    preflight_bot_token_identity(
        token,
        "hermes",
        environ=values,
        fetch_json=fetch_json,
    )
    # Explicit compatibility remap after proof; never log either value.
    values["TELEGRAM_BOT_TOKEN"] = token
    if values is not os.environ:
        os.environ["TELEGRAM_BOT_TOKEN"] = token


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run OpenClaw-patched Hermes gateway.")
    parser.add_argument("--replace", action="store_true", help="Replace an existing Hermes gateway instance.")
    parser.add_argument("-v", "--verbose", action="count", default=0)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    if not HERMES_ROOT.is_dir():
        print(f"ERROR: missing Hermes runtime directory: {HERMES_ROOT}", file=sys.stderr)
        return 2

    configure_gateway_environment()

    _configure_import_paths()
    _load_hermes_runtime_environment()
    try:
        preflight_hermes_bot_identity()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3

    from openclaw_hermes_gateway_policy import install_gateway_policy_patch

    install_gateway_policy_patch()

    from hermes_cli.gateway import run_gateway

    try:
        run_gateway(verbose=args.verbose, quiet=args.quiet, replace=args.replace)
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        return int(code) if isinstance(code, int) else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
