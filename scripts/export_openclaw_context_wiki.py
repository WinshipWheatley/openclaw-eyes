#!/usr/bin/env python3
"""Export the OpenClaw evidence-grounded context wiki."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openclaw_context_wiki_compiler import compile_openclaw_context_wiki, stable_json


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export generated OpenClaw context wiki pages.")
    parser.add_argument("--read-model-root", default="generated/read_models")
    parser.add_argument("--system-knowledge-root", default="generated/system_knowledge")
    parser.add_argument("--external-registry-root", default="generated/external_registries")
    parser.add_argument("--wiki-root", default="generated/wiki/openclaw")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    summary = compile_openclaw_context_wiki(
        read_model_root=args.read_model_root,
        system_knowledge_root=args.system_knowledge_root,
        external_registry_root=args.external_registry_root,
        wiki_root=args.wiki_root,
    )
    if args.format == "json":
        print(stable_json({key: value for key, value in summary.items() if key != "operator_summary"}), end="")
    else:
        print(summary["operator_summary"], end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
