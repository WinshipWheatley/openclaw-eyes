"""tests/test_model_backend_catalog.py — Tests for model_backend_catalog.py (D2).

Tests cover:
1. Catalog builds without errors and returns a valid payload dict.
2. Every abstract model class from model_selection_policy_contract.py is represented.
3. Claude Fable 5 is flagged DISABLED with a clear note.
4. GPT-4o and Claude 3.5 Sonnet are flagged DEPRECATED.
5. Gemini 3.5 Pro is flagged COMING_SOON.
6. DeepSeek V4 (non-flash) is flagged PREVIEW.
7. No API keys are stored in the payload.
8. All non-deprecated/disabled entries are deployable.
9. get_deployable_models() returns only AVAILABLE entries.
10. get_disabled_models() includes claude-fable-5.
11. Hermes sidecar wiring: model_backend_catalog_summary present in build_hermes_sidecar().
12. Hermes sidecar summary says hermes_may_not_switch_models=True.
13. Hermes sidecar summary catalog_present=False when catalog file absent.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import model_backend_catalog as mbc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def build() -> dict[str, Any]:
    return mbc.build_model_backend_catalog()


# ---------------------------------------------------------------------------
# 1. Catalog builds correctly
# ---------------------------------------------------------------------------


class TestCatalogBuild:
    def test_builds_without_error(self):
        payload = build()
        assert isinstance(payload, dict)

    def test_schema_version(self):
        payload = build()
        assert payload["schema_version"] == mbc.SCHEMA_VERSION

    def test_read_model_id(self):
        payload = build()
        assert payload["read_model_id"] == mbc.READ_MODEL_ID

    def test_catalog_as_of_field(self):
        payload = build()
        assert payload["catalog_as_of"] == mbc.CATALOG_AS_OF

    def test_entries_is_list(self):
        payload = build()
        assert isinstance(payload["entries"], list)
        assert len(payload["entries"]) > 0

    def test_summary_counts_are_consistent(self):
        payload = build()
        summary = payload["summary"]
        assert summary["total_entries"] == len(payload["entries"])
        available = [e for e in payload["entries"] if e["availability"] == mbc.AVAILABLE]
        assert summary["available_count"] == len(available)
        dep_dis = [e for e in payload["entries"] if e["availability"] in (mbc.DEPRECATED, mbc.DISABLED)]
        assert summary["deprecated_or_disabled_count"] == len(dep_dis)

    def test_content_hash_present(self):
        payload = build()
        assert payload["machine_proof"]["content_hash"].startswith("sha256:")

    def test_machine_proof_keys(self):
        payload = build()
        proof = payload["machine_proof"]
        assert proof["read_model_only"] is True
        assert proof["api_keys_stored"] is False
        assert proof["model_calls_made"] is False
        assert proof["web_scraping_performed"] is False


# ---------------------------------------------------------------------------
# 2. All abstract model classes are covered
# ---------------------------------------------------------------------------


class TestModelClassCoverage:
    REQUIRED_CLASSES = {
        "local_small_fast",
        "local_reasoning",
        "external_fast_worker",
        "external_deep_reasoner",
        "external_code_worker",
        "local_sensitive",
    }

    def test_all_required_classes_present(self):
        payload = build()
        covered = set(payload["summary"]["model_classes_covered"])
        missing = self.REQUIRED_CLASSES - covered
        assert not missing, f"Missing model classes: {missing}"

    def test_entries_by_class_not_empty(self):
        payload = build()
        by_class = payload["entries_by_class"]
        for cls in self.REQUIRED_CLASSES:
            assert cls in by_class, f"No entries for class {cls!r}"
            assert len(by_class[cls]) > 0, f"Empty entry list for class {cls!r}"


# ---------------------------------------------------------------------------
# 3-6. Specific availability flags
# ---------------------------------------------------------------------------


class TestAvailabilityFlags:
    def _find(self, model_id: str) -> dict[str, Any]:
        payload = build()
        for e in payload["entries"]:
            if e["model_id"] == model_id:
                return e
        pytest.fail(f"Model {model_id!r} not found in catalog")

    def test_claude_fable_5_is_disabled(self):
        e = self._find("claude-fable-5")
        assert e["availability"] == mbc.DISABLED
        note = e["availability_note"].lower()
        assert "disabled" in note or "directive" in note, f"Expected govt directive note, got: {note!r}"
        assert e["deployable"] is False

    def test_claude_fable_5_note_mentions_date_or_directive(self):
        """The note must mention the 2026-06-12 US govt directive."""
        e = self._find("claude-fable-5")
        note = e["availability_note"]
        assert "2026-06-12" in note or "US" in note or "government" in note.lower()

    def test_gpt_4o_is_deprecated(self):
        e = self._find("gpt-4o")
        assert e["availability"] == mbc.DEPRECATED
        assert e["deployable"] is False

    def test_claude_35_sonnet_is_deprecated(self):
        e = self._find("claude-3-5-sonnet")
        assert e["availability"] == mbc.DEPRECATED
        assert e["deployable"] is False

    def test_gemini_35_pro_is_coming_soon(self):
        e = self._find("gemini-3.5-pro")
        assert e["availability"] == mbc.COMING_SOON

    def test_deepseek_v4_base_is_preview(self):
        e = self._find("deepseek-v4")
        assert e["availability"] == mbc.PREVIEW

    def test_deepseek_v4_flash_is_available(self):
        e = self._find("deepseek-v4-flash")
        assert e["availability"] == mbc.AVAILABLE
        assert e["deployable"] is True

    def test_claude_sonnet_46_is_available(self):
        e = self._find("claude-sonnet-4-6")
        assert e["availability"] == mbc.AVAILABLE
        assert e["deployable"] is True

    def test_claude_opus_48_is_available(self):
        e = self._find("claude-opus-4-8")
        assert e["availability"] == mbc.AVAILABLE
        assert e["deployable"] is True


# ---------------------------------------------------------------------------
# 7. No API keys stored
# ---------------------------------------------------------------------------


class TestNoApiKeys:
    def test_no_api_key_strings_in_payload(self):
        """The payload JSON must not contain any key-shaped tokens."""
        payload = build()
        raw = json.dumps(payload)
        # Rudimentary guard: no 'sk-', 'AIza', 'Bearer' or similar patterns
        bad_patterns = ["sk-", "AIza", "Bearer ", "api_key_value"]
        for pat in bad_patterns:
            assert pat not in raw, f"Possible API key pattern {pat!r} found in catalog payload"

    def test_authority_flags_no_key_storage(self):
        payload = build()
        assert payload.get("stores_api_keys") is False
        assert payload.get("stores_credentials") is False
        assert payload.get("may_switch_production_model") is False


# ---------------------------------------------------------------------------
# 8. Deployable flag consistency
# ---------------------------------------------------------------------------


class TestDeployableFlag:
    def test_available_entries_are_deployable(self):
        payload = build()
        for e in payload["entries"]:
            if e["availability"] == mbc.AVAILABLE:
                assert e["deployable"] is True, f"{e['model_id']} is AVAILABLE but deployable=False"

    def test_deprecated_disabled_not_deployable(self):
        payload = build()
        for e in payload["entries"]:
            if e["availability"] in (mbc.DEPRECATED, mbc.DISABLED):
                assert e["deployable"] is False, f"{e['model_id']} is {e['availability']} but deployable=True"


# ---------------------------------------------------------------------------
# 9. get_deployable_models helper
# ---------------------------------------------------------------------------


class TestGetDeployableModels:
    def test_returns_list(self):
        result = mbc.get_deployable_models()
        assert isinstance(result, list)

    def test_all_returned_are_available(self):
        result = mbc.get_deployable_models()
        for e in result:
            assert e["availability"] == mbc.AVAILABLE, f"{e['model_id']} is not AVAILABLE"

    def test_filter_by_class(self):
        result = mbc.get_deployable_models("external_deep_reasoner")
        assert len(result) > 0
        for e in result:
            assert e["model_class"] == "external_deep_reasoner"

    def test_claude_fable_5_not_in_deployable(self):
        result = mbc.get_deployable_models()
        ids = [e["model_id"] for e in result]
        assert "claude-fable-5" not in ids


# ---------------------------------------------------------------------------
# 10. get_disabled_models helper
# ---------------------------------------------------------------------------


class TestGetDisabledModels:
    def test_returns_list(self):
        result = mbc.get_disabled_models()
        assert isinstance(result, list)

    def test_claude_fable_5_in_disabled(self):
        result = mbc.get_disabled_models()
        ids = [e["model_id"] for e in result]
        assert "claude-fable-5" in ids

    def test_gpt_4o_in_disabled(self):
        result = mbc.get_disabled_models()
        ids = [e["model_id"] for e in result]
        assert "gpt-4o" in ids


# ---------------------------------------------------------------------------
# 11-13. Hermes sidecar wiring
# ---------------------------------------------------------------------------


class TestHermesSidecarWiring:
    """Tests that the model backend catalog is surfaced in openclaw_hermes_sidecar."""

    def _fixtures(self, read_root: Path, *, catalog_present: bool = True) -> None:
        """Write minimal fixture read-models so hermes sidecar can build."""
        import openclaw_hermes_sidecar as sidecar

        def write_json(path_value: str, payload: dict) -> None:
            p = read_root / path_value.removeprefix("generated/read_models/")
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        write_json("generated/read_models/openclaw_change_sentinel.json", {
            "schema_version": "openclaw_change_sentinel_read_model_v0",
            "run_status": "NO_MATERIAL_CHANGE",
            "material_change_count": 0,
            "material_changes": [],
        })
        write_json("generated/read_models/openclaw_lane_capability_harvest.json", {
            "schema_version": "openclaw_lane_capability_harvest_read_model_v0",
            "confidence": "HIGH",
            "lanes": [
                {"lane_ref": "live_arts_md_invoice_lane", "status": "ACTIVE_STEEL_THREAD"},
                {"lane_ref": "capital_hilton_invoice_lane", "status": "PARTIAL"},
                {"lane_ref": "st_annes_invoice_lane", "status": "PARTIAL"},
            ],
            "do_not_work_now": [],
            "hermes_recommendation": {
                "recommended_next_lane": "finish_invoice_steel_thread_sequence",
                "chief_build_task_ref": "chief_build_task:finish_invoice_steel_thread_sequence",
                "confidence": "HIGH",
                "reason": "Test fixture.",
                "expected_new_capability": "test",
            },
        })
        write_json("generated/read_models/openclaw_business_object_layer_audit.json", {
            "schema_version": "openclaw_business_object_layer_audit_v0",
            "freshness_status": "FRESH",
        })
        write_json("generated/read_models/openclaw_context_wiki_index.json", {
            "schema_version": "openclaw_context_wiki_index_v0",
            "business_object_audit_freshness_status": "FRESH",
        })
        write_json("generated/read_models/openclaw_authority_semantics_registry.json", {
            "schema_version": "openclaw_authority_semantics_registry_v0",
            "active_drift_signals": [],
        })
        write_json("generated/read_models/openclaw_lm_child_package_gate.json", {
            "schema_version": "openclaw_lm_child_package_gate_v0",
        })
        write_json("generated/read_models/openclaw_estate_topology_registry.json", {
            "schema_version": "openclaw_estate_topology_registry_v0",
        })
        write_json("generated/read_models/openclaw_reference_resolver.json", {
            "schema_version": "openclaw_reference_resolver_v0",
        })

        if catalog_present:
            catalog_payload = mbc.build_model_backend_catalog()
            write_json(
                "generated/read_models/model_backend_catalog.json",
                catalog_payload,
            )

    def test_model_backend_catalog_summary_present_in_payload(self, tmp_path):
        """build_hermes_sidecar() must include model_backend_catalog_summary."""
        import openclaw_hermes_sidecar as sidecar
        read_root = tmp_path / "read_models"
        read_root.mkdir()
        self._fixtures(read_root, catalog_present=True)
        payload = sidecar.build_hermes_sidecar(read_model_root=read_root)
        assert "model_backend_catalog_summary" in payload

    def test_hermes_may_not_switch_models_true(self, tmp_path):
        """The catalog summary must always assert hermes_may_not_switch_models=True."""
        import openclaw_hermes_sidecar as sidecar
        read_root = tmp_path / "read_models"
        read_root.mkdir()
        self._fixtures(read_root, catalog_present=True)
        payload = sidecar.build_hermes_sidecar(read_model_root=read_root)
        summary = payload["model_backend_catalog_summary"]
        assert summary["hermes_may_not_switch_models"] is True
        assert summary["hermes_may_not_call_models"] is True

    def test_catalog_present_true_when_file_exists(self, tmp_path):
        """catalog_present=True when the catalog JSON is on disk."""
        import openclaw_hermes_sidecar as sidecar
        read_root = tmp_path / "read_models"
        read_root.mkdir()
        self._fixtures(read_root, catalog_present=True)
        payload = sidecar.build_hermes_sidecar(read_model_root=read_root)
        summary = payload["model_backend_catalog_summary"]
        assert summary["catalog_present"] is True
        assert summary["available_count"] > 0

    def test_catalog_present_false_when_file_absent(self, tmp_path):
        """catalog_present=False when the catalog JSON is missing (optional input)."""
        import openclaw_hermes_sidecar as sidecar
        read_root = tmp_path / "read_models"
        read_root.mkdir()
        self._fixtures(read_root, catalog_present=False)
        payload = sidecar.build_hermes_sidecar(read_model_root=read_root)
        summary = payload["model_backend_catalog_summary"]
        # model_backend_catalog is optional (required=False), so sidecar remains READY
        assert summary["catalog_present"] is False
        # Boundary still enforced even when catalog absent
        assert summary["hermes_may_not_switch_models"] is True

    def test_disabled_models_surfaced_when_catalog_present(self, tmp_path):
        """disabled_model_ids must include claude-fable-5 when catalog is loaded."""
        import openclaw_hermes_sidecar as sidecar
        read_root = tmp_path / "read_models"
        read_root.mkdir()
        self._fixtures(read_root, catalog_present=True)
        payload = sidecar.build_hermes_sidecar(read_model_root=read_root)
        summary = payload["model_backend_catalog_summary"]
        assert "claude-fable-5" in summary["disabled_model_ids"]
