import os

def test_receipt_taxonomy_exists():
    path = "docs/operations/OPENCLAW_RECEIPT_TAXONOMY_V0.md"
    assert os.path.exists(path), f"{path} should exist"

def test_receipt_taxonomy_sections():
    path = "docs/operations/OPENCLAW_RECEIPT_TAXONOMY_V0.md"
    with open(path, "r") as f:
        content = f.read()

    required_sections = [
        "## 1. Receipt Purpose",
        "## 2. Event Type Conventions",
        "## 3. Receipt Classes",
        "## 4. Minimum Safe Fields",
        "## 5. Sensitive-Data Boundaries",
        "## 6. Promotion Doctrine",
        "## 7. Future Event-Type Examples (Non-Implemented)",
        "## 8. Explicit Non-Goals"
    ]

    for section in required_sections:
        assert section in content, f"Taxonomy doc missing required section: {section}"
