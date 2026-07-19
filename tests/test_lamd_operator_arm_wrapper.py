from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/arm_lamd_monthly_autosend_operator.sh"


def test_arm_wrapper_defaults_to_plan_only_without_mutation() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "PLAN ONLY" in result.stdout
    assert "not_before_service_month=2026-08" in result.stdout
    assert "No files, services, brake state, sends, money, or ledgers were changed." in result.stdout


def test_arm_wrapper_has_one_apply_surface_and_no_send_path() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "usage: $0 [--apply]" in source
    assert "operator-authenticated root" in source
    assert "expected_generation=5" in source
    assert "not_before_service_month=2026-08" in source
    assert "systemctl enable --now openclaw-lamd-monthly-autosend.timer" in source
    assert "lamd_monthly_autosend_runner.py --execute" not in source
    assert "google.gmail.send" not in source
    assert source.count('pass_gate "') == 5
