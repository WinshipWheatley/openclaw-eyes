#!/usr/bin/env python3
"""Query the OpenClaw System Knowledge Registry from agents or shell."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openclaw_system_knowledge_registry import (  # noqa: E402
    format_system_knowledge_answer,
    query_system_knowledge_registry,
    stable_json,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Answer system self-knowledge questions from the local registry.")
    parser.add_argument("question_words", nargs="*", help="Question text, if --question is not supplied.")
    parser.add_argument("--question", help="Question text to answer.")
    parser.add_argument("--repo-root", default=str(ROOT), help="Repository root to query.")
    parser.add_argument("--ledger-path", help="Optional business_ops ledger SQLite path.")
    parser.add_argument("--atlas-path", help="Optional filesystem atlas JSON path.")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    args = parser.parse_args(argv)

    question = args.question or " ".join(args.question_words)
    if not question.strip():
        parser.error("provide a question as positional text or --question")

    answer = query_system_knowledge_registry(
        question,
        repo_root=Path(args.repo_root),
        ledger_path=args.ledger_path,
        atlas_path=args.atlas_path,
    )
    if args.format == "json":
        print(stable_json(answer), end="")
    else:
        print(format_system_knowledge_answer(answer))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
