#!/usr/bin/env python3
"""Run the ignored Hermes gateway runtime through tracked OpenClaw policy."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
HERMES_ROOT = REPO_ROOT / "sidecars" / "hermes"


def _configure_import_paths() -> None:
    for path in (REPO_ROOT, HERMES_ROOT):
        value = str(path)
        if value not in sys.path:
            sys.path.insert(0, value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run OpenClaw-patched Hermes gateway.")
    parser.add_argument("--replace", action="store_true", help="Replace an existing Hermes gateway instance.")
    parser.add_argument("-v", "--verbose", action="count", default=0)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    if not HERMES_ROOT.is_dir():
        print(f"ERROR: missing Hermes runtime directory: {HERMES_ROOT}", file=sys.stderr)
        return 2

    os.environ.setdefault("HERMES_OPENCLAW_MODE", "gateway")
    os.environ.setdefault("HERMES_OPENCLAW_GATEWAY", "1")
    os.environ.setdefault("HERMES_OPENCLAW_DISABLE_EXTERNAL_FALLBACK", "1")

    _configure_import_paths()

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
