import os

def test_proof_receipts_contract_exists():
    path = "docs/operations/OPENCLAW_TEST_PROOF_RECEIPTS_V0.md"
    assert os.path.exists(path), f"{path} should exist"

def test_proof_receipts_sections():
    path = "docs/operations/OPENCLAW_TEST_PROOF_RECEIPTS_V0.md"
    with open(path, "r") as f:
        content = f.read()

    required_sections = [
        "## 1. Purpose",
        "## 2. Receipt is Not Truth",
        "## 3. Minimum Safe Fields",
        "## 4. Sensitive Boundaries",
        "## 5. Event Taxonomy",
        "## 6. Failure Receipts",
        "## 7. Future Consumers",
        "## 8. Non-Goals"
    ]

    for section in required_sections:
        assert section in content, f"Test Proof Receipts doc missing required section: {section}"
