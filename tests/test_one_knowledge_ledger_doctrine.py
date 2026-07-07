from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCTRINE = ROOT / "Operator" / "ONE-KNOWLEDGE-LEDGER-DOCTRINE.md"


def test_one_knowledge_ledger_layers_are_marked_live_not_future_work():
    text = DOCTRINE.read_text(encoding="utf-8")

    assert "Runtime self-heal guard (to build)" not in text
    assert "Self-repair loop (to wire" not in text
    assert "Runtime self-heal guard (LIVE" in text
    assert "Self-repair loop (LIVE" in text
    assert "protected_generate.py:1152-1162" in text
    assert "repair loop" in text
