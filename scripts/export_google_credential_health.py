#!/usr/bin/env python3
"""Export the Google access health read-model.

Probes live Google broker access and publishes the result at
generated/read_models/google_credential_health.json, where Chief's
check-engine posture lane picks it up as observed evidence.

SAFETY: Read-only. Makes one Class A capability call (gmail.read.metadata,
which auto-proceeds and never prompts) purely to prove the authorisation still
answers. Stores status and remedy text only — never authorisation material,
message content, or sender data. Does not refresh, re-issue, or repair
anything: that is interactive and belongs to the operator.

INTERPRETER: the Google client libraries live in the runtime environment
(/home/openclaw/chief_env/bin/python), not in the system python. Run under an
interpreter that lacks them and the probe honestly reports
GOOGLE_ACCESS_DEPS_MISSING — which still lights the check-engine lamp, but as a
"could not look" warning rather than the real account status. Schedule this
with the runtime interpreter so the signal reflects the account, not the venv.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from google_credential_health import (  # noqa: E402
    STATUS_DEPS_MISSING,
    check_google_credentials,
    export_read_model,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--generated-at",
        default=None,
        help="ignored; the probe always stamps its own observation time",
    )
    parser.add_argument("--format", default="json", choices=("json",))
    args = parser.parse_args(argv)

    health = check_google_credentials()
    path = export_read_model(health)
    print(json.dumps({"path": str(path), "status": health["status"]}, indent=2))

    if health["status"] == STATUS_DEPS_MISSING:
        print(
            "WARNING: probed from an interpreter without the Google client libraries, "
            "so this reflects the environment rather than the account.",
            file=sys.stderr,
        )
    # Exit 0 even when access is down: the export succeeded, and the unhealthy
    # status is the payload. A non-zero exit would read as "the exporter broke".
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
