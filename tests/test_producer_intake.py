import pytest
import subprocess
import json

def test_logic_vocal_delay_human_only():
    result = subprocess.run(
        ["python3", "scripts/producer_intake.py", "--text", "make the vocal delay feel wider but keep the words clear in Logic", "--human-only"],
        capture_output=True, text=True
    )
    output = result.stdout
    assert "Niles:" in output
    assert "Logic" in output or "return track" in output
    assert "clear" in output or "clarity" in output
    assert "{" not in output

def test_pretty_json_output():
    result = subprocess.run(
        ["python3", "scripts/producer_intake.py", "--text", "make it dub", "--pretty"],
        capture_output=True, text=True
    )
    data = json.loads(result.stdout)
    assert "producer_contract_version" in data
