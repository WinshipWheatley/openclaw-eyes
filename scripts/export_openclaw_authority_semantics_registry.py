#!/usr/bin/env python3
"""Export the OpenClaw Authority Semantics Registry read-models."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import openclaw_authority_semantics_registry as registry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-model-root", type=Path, default=registry.DEFAULT_READ_MODEL_ROOT)
    parser.add_argument("--system-knowledge-root", type=Path, default=registry.DEFAULT_SYSTEM_KNOWLEDGE_ROOT)
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args(argv)

    payload, json_path, operator_path, sqlite_path, schema_path, seed_path = (
        registry.export_openclaw_authority_semantics_registry(
            read_model_root=args.read_model_root,
            system_knowledge_root=args.system_knowledge_root,
            generated_at=args.generated_at,
        )
    )
    print(
        registry.stable_json(
            {
                "read_model_id": payload["read_model_id"],
                "json_path": json_path.as_posix(),
                "operator_path": operator_path.as_posix(),
                "sqlite_path": sqlite_path.as_posix(),
                "schema_path": schema_path.as_posix(),
                "seed_path": seed_path.as_posix(),
                "field_semantics_count": len(payload["authority_field_semantics"]),
                "positive_template_count": len(payload["positive_occupation_templates"]),
                "golden_fixture_count": len(payload["golden_path_fixtures"]),
                "no_policy_allows_silent_deletion": payload["machine_proof"]["no_policy_allows_silent_deletion"],
            }
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
