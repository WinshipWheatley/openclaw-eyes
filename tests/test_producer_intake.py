import pytest
import subprocess
import json

def test_boring_spacious_human_only():
    result = subprocess.run(
        ["python3", "scripts/producer_intake.py", "--text", "this chorus feels boring but I want it to stay spacious", "--human-only"],
        capture_output=True, text=True
    )
    output = result.stdout
    assert "arrival point" in output or "clutter" in output
    assert "Niles:" in output
    assert "{" not in output # Verify no JSON

def test_pretty_json_output():
    result = subprocess.run(
        ["python3", "scripts/producer_intake.py", "--text", "make it dub", "--pretty"],
        capture_output=True, text=True
    )
    data = json.loads(result.stdout)
    assert "producer_contract_version" in data
