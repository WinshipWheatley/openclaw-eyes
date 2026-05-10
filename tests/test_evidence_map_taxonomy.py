import os

def test_evidence_map_exists():
    path = "docs/operations/OPENCLAW_EVIDENCE_SUFFICIENCY_MAP_V0.md"
    assert os.path.exists(path), f"{path} should exist"

def test_evidence_map_sections():
    path = "docs/operations/OPENCLAW_EVIDENCE_SUFFICIENCY_MAP_V0.md"
    with open(path, "r") as f:
        content = f.read()

    required_sections = [
        "## 1. Evidence Classes (Train Cars)",
        "## 2. Confidence Levels",
        "## 3. Current Coverage (v0)",
        "## 4. Grounding Rule",
        "## 5. Morning Brief Growth Path",
        "## 6. Future Growth Pattern",
        "## 7. Explicit Non-Goals"
    ]

    for section in required_sections:
        assert section in content, f"Evidence Map doc missing required section: {section}"
