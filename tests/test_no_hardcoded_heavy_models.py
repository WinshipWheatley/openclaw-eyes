"""No production call site may hardcode a known-oversized model (2026-07-09 incident).

chief_router.py carried a pre-doctrine `model="qwen3.6:latest"` (27G) on the
interactive reply lane for months; the moment that path fired it swap-killed
the box. The adaptive fit wall now demotes such calls at runtime — this test
kills the pattern at the source so it can never be written back.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Models known to exceed the async (15G) ceiling on this box — never valid as a
# hardcoded model= argument in production code. chief_llm's ceiling comments and
# tests may of course name them.
_HEAVY = ("qwen3.6", "gemma4:26b", "gemma4:31b", "nemotron-3-nano:30b")

_MODEL_ARG = re.compile(r"""model\s*=\s*["'](%s)""" % "|".join(re.escape(m) for m in _HEAVY))


def test_no_tracked_production_file_hardcodes_a_heavy_model() -> None:
    tracked = subprocess.run(
        ["git", "ls-files", "*.py"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()

    offenders: list[str] = []
    for rel in tracked:
        if rel.startswith("tests/"):
            continue
        path = REPO / rel
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if _MODEL_ARG.search(line):
                offenders.append(f"{rel}:{lineno}: {line.strip()}")

    assert not offenders, (
        "hardcoded heavy-model call site(s) found — route through the adaptive "
        "selector instead (see 2026-07-09 swap-death incident):\n" + "\n".join(offenders)
    )
