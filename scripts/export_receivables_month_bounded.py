#!/usr/bin/env python3
"""Export receivables_month_bounded.json."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import receivables_month_bounded


def export_receivables_month_bounded_read_model(
    *,
    g2c_db_path: str | Path = receivables_month_bounded.DEFAULT_G2C_DB_PATH,
    facts_path: str | Path | None = None,
    export_root: str | Path = receivables_month_bounded.DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> dict:
    return receivables_month_bounded.export_receivables_month_bounded(
        g2c_db_path=g2c_db_path,
        facts_path=facts_path,
        output_path=Path(export_root) / receivables_month_bounded.READ_MODEL_FILENAME,
        generated_at=generated_at,
    )


def main(argv: list[str] | None = None) -> int:
    return receivables_month_bounded.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
