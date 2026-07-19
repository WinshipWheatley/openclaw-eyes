from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/install_accept_lamd_autosend_operator.sh"


def test_operator_wrapper_defaults_to_an_exact_non_mutating_plan() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "PLAN ONLY" in result.stdout
    assert "fake provider" in result.stdout
    assert "timer disabled" in result.stdout
    assert "scope unarmed" in result.stdout
    assert "No files, services, brake state, sends, money, or ledgers were changed." in result.stdout


def test_operator_wrapper_has_one_explicit_apply_surface_and_five_gate_labels() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "usage: $0 [--apply]" in source
    assert "operator-authenticated root" in source
    assert "proof_commit=2b5314a57d7107ae1b67a4304e02e3b8d7dfa8ab" in source
    assert "scripts/install_lamd_autosend_brake_linux.sh --apply" in source
    assert 'accept_lamd_autosend_installed.py" --apply' in source
    assert "systemctl disable --now openclaw-lamd-monthly-autosend.timer" in source
    assert source.count('pass_gate "') == 5
