from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from validate_module_manifests import validate_path, validate_paths  # noqa: E402


EXAMPLES_DOC = REPO_ROOT / "docs/module_atlas/OPENCLAW_SYNTHETIC_MODULE_MANIFEST_EXAMPLES_V0.md"


VALID_MANIFEST_SECTION = """## Synthetic Example: test fixture

This synthetic example is inert. It does not describe an active module.

```yaml
module_id: "module_manifest.synthetic_test_fixture"
module_family: "module_manifest"
purpose: "Describe a proposed inert validation fixture."
authority_level: "docs_only"

allowed_inputs:
  - "synthetic manifest fixture docs"

forbidden_inputs:
  - "secrets, tokens, keys, credentials, and .env files"
  - "private data reads"

outputs_artifacts:
  - "validation result summaries"

approval_gates:
  - "manifest_review_required_before_commit"

sensitivity_gates:
  - "local_only_by_default"
  - "private_data_processing_blocked_until_separately_approved"

dependencies:
  docs:
    - "docs/module_atlas/OPENCLAW_MODULE_MANIFEST_DRAFT_SCHEMA_V0.md"
  brokers:
    - "none"
  runtime_services:
    - "none"

tests_required:
  - "schema_required_fields_present"

receipts_required:
  - "validation_receipt"

disable_path: "Remove this synthetic manifest fixture from the reviewed examples."
rollback_path: "Revert the synthetic fixture commit or supersede it with a reviewed replacement."

NOT_READY_boundaries:
  - "runtime activation"
  - "customer deployment"
  - "autonomous action"
  - "sensitive-data processing"
  - "broker connection"
  - "agent wiring"
  - "SQLite write"
  - "live system health claim"
```
"""


def write_temp_doc(text: str) -> Path:
    temp = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8")
    with temp:
        temp.write(text)
    return Path(temp.name)


class ModuleManifestValidationTests(unittest.TestCase):
    def test_committed_synthetic_examples_pass(self) -> None:
        block_count, findings = validate_paths([EXAMPLES_DOC])

        self.assertEqual(block_count, 3)
        self.assertEqual(findings, [])

    def test_missing_required_field_is_reported(self) -> None:
        path = write_temp_doc(VALID_MANIFEST_SECTION.replace("rollback_path:", "rollback_path_missing:"))
        self.addCleanup(path.unlink)

        _, findings = validate_path(path)

        self.assertTrue(
            any("missing required field: rollback_path" in finding.message for finding in findings),
            [finding.format() for finding in findings],
        )

    def test_forbidden_activation_claim_is_reported(self) -> None:
        invalid_doc = VALID_MANIFEST_SECTION.replace(
            "This synthetic example is inert. It does not describe an active module.",
            "This synthetic example says runtime activation is approved.",
        )
        path = write_temp_doc(invalid_doc)
        self.addCleanup(path.unlink)

        _, findings = validate_path(path)

        self.assertTrue(
            any("forbidden permission claim: runtime activation claim" in finding.message for finding in findings),
            [finding.format() for finding in findings],
        )


if __name__ == "__main__":
    unittest.main()
