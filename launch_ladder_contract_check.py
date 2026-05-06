#!/usr/bin/env python3
"""Static contract checker for the Launch Ladder planning package.

This is a docs/test-only helper. It reads Markdown contracts and reports missing
product-contract language; it does not inspect runtime state or generated ingest
folders.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys


REPO_ROOT = Path(__file__).resolve().parent
LAUNCH_LADDER_DIR = REPO_ROOT / "docs" / "planning" / "launch_ladder"
MODULAR_LEDGER = REPO_ROOT / "docs" / "planning" / "OPENCLAW_MODULAR_READINESS_LEDGER.md"
VALIDATION_MAP = REPO_ROOT / "docs" / "testing" / "VALIDATION_MAP.md"
SYNC_OPERATOR_HARNESS = (
    REPO_ROOT / "mac_eyes" / "Launchers" / "sync_operator_harness_to_mac.sh"
)
REFRESH_OPERATOR_HARNESS = (
    REPO_ROOT / "mac_eyes" / "Launchers" / "refresh_operator_harness_ingest.sh"
)

ACTIVE_SOURCE_SET = "CHATGPT_PROJECT_INGEST_OPERATOR_HARNESS/02_MAC_IOS_APP_BUILD"
UPLOAD_AUTHORITY_COMMIT = "df52ff4687d7dd8a32990658d557cb2b4d1371d9"
MISSION_CONTROL_APP_SURFACE = "mac_desktop_mission_control_read_only"
MISSION_CONTROL_SOURCE_SET_BASELINE = "02_MAC_IOS_APP_BUILD"
MISSION_CONTROL_FIXTURE_DIR = (
    LAUNCH_LADDER_DIR / "fixtures" / "mission_control"
)
REQUIRED_MISSION_CONTROL_FIXTURES = (
    "fixture_fresh_navigation_profile.json",
    "fixture_malformed_executable_profile.json",
    "fixture_packet_available_not_approved.json",
    "fixture_approval_receipt_valid.json",
    "fixture_approval_receipt_expired.json",
    "fixture_stale_evidence_route.json",
    "fixture_blocked_missing_authority.json",
    "fixture_ui_claim_without_evidence.json",
    "fixture_operator_experience_golden_overview.json",
)
REQUIRED_FIRST_SCREEN_FIXTURES = (
    "golden_first_screen_default.json",
    "golden_first_screen_local_ahead_of_origin.json",
    "golden_first_screen_knowledge_context_non_ingestive.json",
    "golden_first_screen_unknown_preserved.json",
    "malformed_first_screen_ai_command_center.json",
    "malformed_first_screen_profile_executes_work.json",
    "malformed_first_screen_synced_after_push_failure.json",
)
FIRST_SCREEN_SPEC = LAUNCH_LADDER_DIR / "13_MAC_DESKTOP_FIRST_SCREEN_COMPOSITION_SPEC.md"
FIRST_SCREEN_ZONES = (
    "top_operating_context_band",
    "left_active_lanes_column",
    "center_current_focus_selected_lane",
    "right_next_safe_move_panel",
    "lower_evidence_freshness_drawer",
    "quiet_recent_changes_strip",
    "future_knowledge_context_strip",
)
FIRST_SCREEN_EXTRA_HARD_BOUNDARIES = (
    "no_sqlite_db_created",
    "no_ingestion",
    "no_real_business_file_scanning",
    "no_app_naming",
)
FIRST_SCREEN_ALLOWED_APP_PHRASES = (
    "Mac desktop app",
    "Operator Harness app",
    "personal operator console",
    "Mission Control surface",
)
FIRST_SCREEN_FORBIDDEN_NAMING_FIELDS = (
    "app_name",
    "product_name",
    "brand_name",
    "codename",
    "marketing_name",
)
TASTE_SPEC = LAUNCH_LADDER_DIR / "14_MAC_DESKTOP_TASTE_AND_ATMOSPHERE_SPEC.md"
SOUND_HAPTICS_ADDENDUM = (
    LAUNCH_LADDER_DIR / "15_MAC_DESKTOP_SOUND_HAPTICS_QUIET_FEEDBACK_ADDENDUM.md"
)
MAC_APP_KNOWLEDGE_SOURCE_SET = "03_MAC_APP_KNOWLEDGE_SUBSTRATE"
MAC_APP_KNOWLEDGE_SOURCE_SET_BRIEF = (
    LAUNCH_LADDER_DIR / "16_MAC_APP_KNOWLEDGE_SUBSTRATE_SOURCE_SET_BRIEF.md"
)
BACKEND_DATA_CONTRACT_SOURCE_SET = "04_BACKEND_DATA_CONTRACT_READINESS"
BACKEND_DATA_CONTRACT_PLAN = (
    LAUNCH_LADDER_DIR / "17_BACKEND_DATA_CONTRACT_READINESS_PLAN.md"
)
SOURCE_SET_BRIDGE_DIR = LAUNCH_LADDER_DIR / "source_set_bridges"
OPERATOR_NORTH_STAR_MACHINE_CONTRACT = (
    SOURCE_SET_BRIDGE_DIR / "operator_north_star_machine_contract_20260505.md"
)
BACKEND_DATA_CONTRACT_SEMANTIC_CONTRACT_MATRIX = (
    SOURCE_SET_BRIDGE_DIR / "backend_data_contract_semantic_contract_matrix_20260505.md"
)
BACKEND_DATA_CONTRACT_IMPLEMENTATION_READINESS_CHECKLIST = (
    SOURCE_SET_BRIDGE_DIR / "backend_data_contract_implementation_readiness_checklist_20260505.md"
)
BACKEND_DATA_CONTRACT_FIRST_IMPLEMENTATION_SLICE_READINESS = (
    SOURCE_SET_BRIDGE_DIR
    / "backend_data_contract_first_implementation_slice_readiness_20260505.md"
)
BACKEND_DATA_CONTRACT_MODULE = REPO_ROOT / "backend_data_contract.py"
BACKEND_DATA_CONTRACT_TEST = REPO_ROOT / "tests" / "test_backend_data_contract.py"
BACKEND_DATA_CONTRACT_RECORD_TOPICS = (
    "source file record",
    "extracted text record",
    "rendered fragment record",
    "artifact classification record",
    "claim record",
    "contradiction record",
    "compiled note record",
    "freshness record",
    "operator promotion record",
    "conversation packet record",
    "blocked sensitive source record",
    "unknown/unclassified artifact record",
    "audit/substrate event record",
    "Launch Packet / Approval Receipt linkage record",
)
BACKEND_DATA_CONTRACT_REQUIRED_SECTIONS = (
    "Recommended Next Source-Set Folder Name",
    "Why This Should Be The Next Source Set",
    "What 03_MAC_APP_KNOWLEDGE_SUBSTRATE Answered",
    "What Remains Unresolved Before Backend/Schema Work",
    "Minimum File List The Next Source Set Should Include",
    "Synthetic Fixture/Data-Contract Topics To Cover Later",
    "Static Validation Expectations To Require Later",
    "Boundaries That Remain In Force",
    "Recommended Next Move",
)
BACKEND_DATA_CONTRACT_BOUNDARIES = (
    "Do not implement anything",
    "Do not create source-set folder 04 yet",
    "Do not create SwiftUI/AppKit files",
    "Do not create backend/API/schema files",
    "Do not create SQL DDL",
    "Do not create a SQLite DB",
    "Do not create ingestion scripts",
    "Do not create fixtures yet",
    "Do not scan old business files",
    "Do not inspect private data, vaults, logs, LegalPrivate, secrets, Gmail, cloud drives, or runtime state",
    "Do not call providers/models",
    "Do not mutate runtime, services, approvals, Guardian, Hermes, Telegram, or Gmail",
    "Do not create audio assets, haptics, notifications, sound behavior, or sound settings UI",
    "Do not name the app or invent product names, codenames, mascots, slogans, logos, or brand identity",
)
BACKEND_DATA_CONTRACT_BOUNCE_CLASSIFICATIONS = (
    "Confirmed",
    "Additive",
    "Corrective",
    "Conflicting",
    "Out of scope",
)
BACKEND_DATA_CONTRACT_FIELD_BUNDLES = (
    "Identity",
    "Evidence",
    "Freshness",
    "Provenance",
    "Authority",
    "Sensitivity",
    "Operator surface",
    "State",
    "Context filter",
)
BACKEND_DATA_CONTRACT_STATIC_GATE_DOCS = (
    "operator_north_star_machine_contract_20260505.md",
    "backend_data_contract_semantic_contract_matrix_20260505.md",
    "backend_data_contract_implementation_readiness_checklist_20260505.md",
    "backend_data_contract_first_implementation_slice_readiness_20260505.md",
    "04_backend_data_contract_readiness_context_filter_freshness_bridge_20260505.md",
    "04_CONTEXT_DEVELOPMENT_LIFECYCLE_AND_CONTEXT_FILTER_DOCTRINE.md",
    "30_BACKEND_SOURCE_SET_BRIDGE_AND_EXCLUSION_PLAN.md",
)
BACKEND_DATA_CONTRACT_MODULE_REQUIRED_TERMS = (
    "KnowledgeLayer",
    "raw layer",
    "compiled/wiki layer",
    "relationship layer",
    "synthesis layer",
    "write-back/capture layer",
    "ContractLabel",
    "provenance",
    "freshness",
    "confidence",
    "sensitivity",
    "authority",
    "review status",
    "ContractState",
    "confirmed",
    "inferred",
    "excluded",
    "unknown",
    "blocked",
    "stale",
    "confirmed-as-interpretation",
    "ContractDecision",
    "allowed",
    "implementation-forbidden",
    "ContractValidationResult",
    "EntityFamily",
    "person",
    "organization",
    "client",
    "job",
    "invoice",
    "payment",
    "project",
    "music work",
    "legal matter",
    "tax matter",
    "source material",
    "compiled page",
    "follow-up action",
    "approval",
    "blocker",
    "system artifact",
    "ALLOWED_LAYERS_BY_ENTITY_FAMILY",
    "ALLOWED_STATES_BY_ENTITY_FAMILY",
    "EXCLUDED_ENTITY_FAMILY_NAMES",
    "REQUIRED_CONTRACT_LABELS",
    "REQUIRED_LABEL_BUNDLES_BY_LAYER",
    "REQUIRED_WRITE_BACK_CAPTURE_LABELS",
    "SENSITIVE_OR_PRIVATE_STATES",
    "IMPLEMENTATION_FORBIDDEN_CONCEPTS",
    "UNKNOWN_STYLE_STATES",
    "EXCLUDED_STYLE_STATES",
    "ALLOWED_STATES_BY_LAYER",
    "SemanticRecordProposal",
    "normalize_entity_family",
    "entity_family_decision",
    "is_entity_family_known",
    "is_entity_family_excluded",
    "allowed_layers_for_entity_family",
    "allowed_states_for_entity_family",
    "validate_entity_family_record",
    "is_entity_record_accepted_knowledge",
    "classify_semantic_record",
    "classify_record_state",
    "validate_field_bundle",
    "missing_required_labels",
    "missing_write_back_capture_labels",
    "required_labels_for_layer",
    "is_accepted_knowledge",
    "is_implementation_forbidden",
)
BACKEND_DATA_CONTRACT_TEST_REQUIRED_TERMS = (
    "test_core_vocabulary_preserves_knowledge_compiler_layers_and_labels",
    "test_each_layer_has_required_field_bundle_labels",
    "test_forbidden_implementation_concepts_are_not_authorized",
    "test_write_back_capture_requires_labels_and_promotion_before_allowed",
    "test_valid_minimal_records_pass_field_bundle_validation",
    "test_missing_layer_labels_fail_with_useful_reasons",
    "test_synthesis_is_not_confirmed_truth_by_default",
    "test_write_back_capture_needs_promotion_for_valid_record_and_acceptance",
    "test_forbidden_implementation_concepts_fail_field_bundle_validation",
    "test_unknown_and_excluded_states_cannot_confirm_accidentally",
    "test_private_sensitive_promotion_requires_sensitivity_and_authority_labels",
    "test_known_entity_families_normalize_correctly",
    "test_unknown_and_excluded_entity_families_remain_distinct",
    "test_entity_family_layer_and_state_maps_are_explicit",
    "test_valid_entity_family_layer_state_combinations_pass",
    "test_invalid_entity_family_combinations_fail_with_reasons",
    "test_receivables_families_support_accountability_without_auto_sending",
    "test_legal_tax_and_music_families_do_not_authorize_private_or_provider_use",
    "test_operator_life_families_stay_bounded_by_authority",
    "test_synthesis_family_is_not_accepted_truth_by_default",
    "test_entity_write_back_capture_requires_labels_and_operator_promotion",
    "SQLite persistence",
    "provider model call",
    "runtime services",
    "automated sending harassment collection action",
    "private root inspection",
    "missing required labels",
    "private/sensitive promotion requires labels",
    "write-back/capture confirmed receipt requires operator promotion",
    "promoted_by_operator=True",
)
BACKEND_DATA_CONTRACT_FORBIDDEN_MODULE_IMPORTS = (
    "import sqlite3",
    "from sqlite3",
    "import argparse",
    "import click",
    "import requests",
    "import httpx",
    "from fastapi",
    "import fastapi",
    "from flask",
    "import flask",
    "import subprocess",
    "from subprocess",
    "import socket",
    "from socket",
    "import openai",
    "from openai",
    "import anthropic",
    "from anthropic",
    "if __name__ == \"__main__\"",
)
TASTE_REQUIRED_SECTIONS = (
    "Taste thesis",
    "Visual reference vocabulary",
    "Material and surface language",
    "Typography and density",
    "Motion and interaction feel",
    "Personal-to-Winship signals",
    "Empty states and quiet states",
    "Vibe tests",
    "Anti-vibe tests",
    "Implementation risk warnings for future Codex/Mac work",
    "Next artifact recommendation",
)
TASTE_VIBE_TESTS = (
    "would_open_this_every_morning",
    "cockpit_not_chatbot",
    "studio_console_not_saas",
    "evidence_without_paperwork",
    "blocked_without_panic",
    "personal_without_branding",
    "creative_without_whimsy",
    "knowledge_without_rag_search_box",
    "approval_visible_not_dominant",
    "daily_control_not_project_management",
)
TASTE_ANTI_VIBE_TESTS = (
    "jira_cosplay",
    "ai_orb_centerpiece",
    "startup_dashboard",
    "compliance_portal_mood",
    "neon_command_center",
    "wall_of_status_chips",
    "fake_product_name_energy",
    "overexplained_receipt_drawer",
    "agent_theatre",
    "rag_search_default",
)
SOUND_REQUIRED_SECTIONS = (
    "Sound thesis",
    "Default policy",
    "Allowed sound moments",
    "Forbidden sound patterns",
    "Sonic reference vocabulary",
    "Haptics / tactile feedback posture",
    "Accessibility and operator control",
    "Vibe tests",
    "Anti-vibe tests",
    "Recommendation for Codex artifact",
)
SOUND_VIBE_TESTS = (
    "sound_confirms_visible_state",
    "studio_console_not_notification_pack",
    "blocked_without_alarm",
    "no_hidden_worker_audio",
    "quiet_by_default",
    "daily_use_no_fatigue",
    "sound_optional_not_identity",
)
SOUND_ANTI_VIBE_TESTS = (
    "ai_thinking_blips",
    "sci_fi_sweep",
    "jira_notification_ping",
    "casino_success_chime",
    "dramatic_error_alarm",
    "ambient_agent_hum",
    "startup_brand_sting",
)
MISSION_CONTROL_UI_STATES = (
    "profile_available",
    "packet_available",
    "launch_ready",
    "approved",
    "executed",
    "succeeded",
    "stale",
    "blocked",
    "unknown",
)
MISSION_CONTROL_REQUIRED_HARD_BOUNDARIES = (
    "no_swiftui_appkit_implementation",
    "no_backend_api_schema_implementation",
    "no_runtime_calls",
    "no_service_control",
    "no_provider_model_calls",
    "no_gmail_telegram_actions",
    "no_hermes_runtime_expansion",
    "no_private_data_vault_log_legalprivate_secrets_inspection",
    "no_approval_mutation_guardian_control",
    "no_app_execution",
)
KNOWLEDGE_SUBSTRATE_DIR = LAUNCH_LADDER_DIR / "knowledge_substrate"
REQUIRED_KNOWLEDGE_SUBSTRATE_DOCS = (
    "README.md",
    "01_NORTH_STAR.md",
    "02_SQLITE_LAYER_MODEL.md",
    "03_SAFETY_AND_SENSITIVITY_LEVELS.md",
    "04_APP_CARDS_AND_UI_STATES.md",
    "05_FIXTURE_PLAN.md",
    "06_STATIC_VALIDATION_EXPECTATIONS.md",
    "INDEX.md",
)
KNOWLEDGE_SUBSTRATE_TABLES = (
    "source_files",
    "extracted_text",
    "rendered_fragments",
    "artifact_classifications",
    "entities",
    "entity_links",
    "claims",
    "compiled_notes",
    "freshness",
    "operator_promotions",
    "conversation_packets",
    "audit_events",
    "substrate_events",
)
KNOWLEDGE_SUBSTRATE_SENSITIVITY_LEVELS = (
    "public_or_low_sensitivity",
    "business_internal",
    "client_confidential",
    "financial_tax_accounting",
    "music_law_publishing_sensitive",
    "legal_sensitive",
    "secrets_credentials",
    "unknown_unclassified",
)
KNOWLEDGE_SUBSTRATE_FIXTURE_NAMES = (
    "fixture_source_file_public_note.json",
    "fixture_source_file_business_internal_invoice.json",
    "fixture_source_file_sensitive_contract_blocked.json",
    "fixture_extracted_text_with_warning.json",
    "fixture_rendered_fragment_html_and_plaintext.json",
    "fixture_artifact_classification_unknown.json",
    "fixture_claim_with_evidence.json",
    "fixture_claim_contradicted.json",
    "fixture_compiled_note_historical_business_context.json",
    "fixture_operator_promotion_mark_historical.json",
    "fixture_conversation_packet_safe_summary.json",
    "fixture_blocked_secrets_source.json",
)
KNOWLEDGE_SUBSTRATE_APP_CARDS = (
    "Knowledge Atlas Overview card",
    "Discovered Source card",
    "Extracted Text card",
    "Rendered Fragment card",
    "Artifact Classification card",
    "Claim card",
    "Compiled Note card",
    "Contradiction card",
    "Freshness/Staleness card",
    "Operator Promotion card",
    "Conversation Packet card",
    "Blocked Sensitive Source card",
)
KNOWLEDGE_SUBSTRATE_UI_STATES = (
    "discovered",
    "extracted",
    "classified",
    "compiled",
    "promoted",
    "contradicted",
    "stale",
    "blocked",
    "unknown",
    "excluded",
)
MAC_APP_KNOWLEDGE_SOURCE_SET_FILES = (
    "16_MAC_APP_KNOWLEDGE_SUBSTRATE_SOURCE_SET_BRIEF.md",
    "09_MAC_IOS_APP_BUILD_BRIEF.md",
    "12_MAC_DESKTOP_MISSION_CONTROL_FIXTURE_CONTRACT.md",
    "13_MAC_DESKTOP_FIRST_SCREEN_COMPOSITION_SPEC.md",
    "14_MAC_DESKTOP_TASTE_AND_ATMOSPHERE_SPEC.md",
    "15_MAC_DESKTOP_SOUND_HAPTICS_QUIET_FEEDBACK_ADDENDUM.md",
    "04_LAUNCH_LADDER_MODEL.md",
    "05_EVIDENCE_AND_FRESHNESS.md",
    "06_ROUTING_AND_WORKSPACES.md",
    "07_SECURITY_AND_AUTHORITY.md",
    "08_SOURCE_SET_REFRESH_SYSTEM.md",
    "11_NEXT_IMPLEMENTATION_SEQUENCE.md",
    "KNOWLEDGE_SUBSTRATE_README.md",
    "KNOWLEDGE_SUBSTRATE_01_NORTH_STAR.md",
    "KNOWLEDGE_SUBSTRATE_02_SQLITE_LAYER_MODEL.md",
    "KNOWLEDGE_SUBSTRATE_03_SAFETY_AND_SENSITIVITY_LEVELS.md",
    "KNOWLEDGE_SUBSTRATE_04_APP_CARDS_AND_UI_STATES.md",
    "KNOWLEDGE_SUBSTRATE_05_FIXTURE_PLAN.md",
    "KNOWLEDGE_SUBSTRATE_06_STATIC_VALIDATION_EXPECTATIONS.md",
    "KNOWLEDGE_SUBSTRATE_INDEX.md",
    "VALIDATION_MAP.md",
    "launch_ladder_contract_check.py",
    "test_launch_ladder_static_contract.py",
)


@dataclass(frozen=True)
class ContractCorpus:
    launch_ladder_text: str
    knowledge_substrate_text: str
    ledger_text: str
    validation_map_text: str
    script_text: str

    @property
    def combined_text(self) -> str:
        return "\n".join(
            [
                self.launch_ladder_text,
                self.knowledge_substrate_text,
                self.ledger_text,
                self.validation_map_text,
                self.script_text,
            ]
        )


@dataclass(frozen=True)
class StaticContractReport:
    failures: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.failures


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_corpus(repo_root: Path = REPO_ROOT) -> ContractCorpus:
    launch_dir = repo_root / "docs" / "planning" / "launch_ladder"
    launch_docs = sorted(launch_dir.glob("*.md"))
    launch_text = "\n\n".join(_read_text(path) for path in launch_docs)
    knowledge_dir = launch_dir / "knowledge_substrate"
    knowledge_docs = sorted(knowledge_dir.glob("*.md"))
    knowledge_substrate_text = "\n\n".join(_read_text(path) for path in knowledge_docs)
    ledger_text = _read_text(
        repo_root / "docs" / "planning" / "OPENCLAW_MODULAR_READINESS_LEDGER.md"
    )
    validation_map_text = _read_text(
        repo_root / "docs" / "testing" / "VALIDATION_MAP.md"
    )
    script_text = "\n\n".join(
        _read_text(path)
        for path in (
            repo_root / "mac_eyes" / "Launchers" / "sync_operator_harness_to_mac.sh",
            repo_root / "mac_eyes" / "Launchers" / "refresh_operator_harness_ingest.sh",
        )
    )
    return ContractCorpus(
        launch_ladder_text=launch_text,
        knowledge_substrate_text=knowledge_substrate_text,
        ledger_text=ledger_text,
        validation_map_text=validation_map_text,
        script_text=script_text,
    )


def normalize(text: str) -> str:
    lowered = text.lower().replace("'", "")
    flattened = re.sub(r"[^a-z0-9]+", " ", lowered)
    return re.sub(r"\s+", " ", flattened).strip()


def _contains(haystack: str, needle: str) -> bool:
    return normalize(needle) in haystack


def _require_all(
    failures: list[str], normalized_text: str, section: str, terms: tuple[str, ...]
) -> None:
    missing = [term for term in terms if not _contains(normalized_text, term)]
    if missing:
        failures.append(f"{section}: missing {', '.join(missing)}")


def _require_any(
    failures: list[str],
    normalized_text: str,
    section: str,
    variants: tuple[str, ...],
) -> None:
    if not any(_contains(normalized_text, variant) for variant in variants):
        failures.append(f"{section}: missing one of {', '.join(variants)}")


def _fixture_dir(repo_root: Path = REPO_ROOT) -> Path:
    return repo_root / "docs" / "planning" / "launch_ladder" / "fixtures" / "mission_control"


def load_mission_control_fixtures(repo_root: Path = REPO_ROOT) -> dict[str, dict]:
    fixture_dir = _fixture_dir(repo_root)
    fixtures: dict[str, dict] = {}
    for filename in REQUIRED_MISSION_CONTROL_FIXTURES:
        path = fixture_dir / filename
        fixtures[filename] = json.loads(_read_text(path))
    return fixtures


def load_first_screen_fixtures(repo_root: Path = REPO_ROOT) -> dict[str, dict]:
    fixture_dir = _fixture_dir(repo_root)
    fixtures: dict[str, dict] = {}
    for filename in REQUIRED_FIRST_SCREEN_FIXTURES:
        path = fixture_dir / filename
        fixtures[filename] = json.loads(_read_text(path))
    return fixtures


def _profile_contains_executable_command_field(profile: object) -> bool:
    if not isinstance(profile, dict):
        return False
    return any("executable" in key or key in {"execution_commands", "commands"} for key in profile)


def _navigation_actions_are_clean(profile: dict) -> bool:
    actions = profile.get("allowed_navigation_actions", [])
    if not isinstance(actions, list):
        return False
    forbidden_fragments = ("run", "sync", "commit", "push", "service", "provider", "model", "execute")
    return not any(
        fragment in str(action).lower()
        for action in actions
        for fragment in forbidden_fragments
    )


def mission_control_fixture_failures(repo_root: Path = REPO_ROOT) -> tuple[str, ...]:
    failures: list[str] = []
    fixture_dir = _fixture_dir(repo_root)
    loaded: dict[str, dict] = {}

    for filename in REQUIRED_MISSION_CONTROL_FIXTURES:
        path = fixture_dir / filename
        if not path.is_file():
            failures.append(f"mission control fixtures: missing {path}")
            continue
        try:
            loaded[filename] = json.loads(_read_text(path))
        except json.JSONDecodeError as exc:
            failures.append(f"mission control fixtures: invalid JSON in {path}: {exc}")

    for filename, fixture in loaded.items():
        section = f"mission control fixture {filename}"
        expected_id = filename.removesuffix(".json")
        if fixture.get("fixture_id") != expected_id:
            failures.append(f"{section}: fixture_id must be {expected_id}")
        if fixture.get("app_surface") != MISSION_CONTROL_APP_SURFACE:
            failures.append(f"{section}: app_surface must be {MISSION_CONTROL_APP_SURFACE}")
        if fixture.get("source_set_baseline") != MISSION_CONTROL_SOURCE_SET_BASELINE:
            failures.append(
                f"{section}: source_set_baseline must be {MISSION_CONTROL_SOURCE_SET_BASELINE}"
            )
        if fixture.get("source_manifest_commit") != UPLOAD_AUTHORITY_COMMIT:
            failures.append(f"{section}: source_manifest_commit must be {UPLOAD_AUTHORITY_COMMIT}")
        if fixture.get("ui_state") not in MISSION_CONTROL_UI_STATES:
            failures.append(f"{section}: ui_state must be one of {', '.join(MISSION_CONTROL_UI_STATES)}")

        expected_validation = fixture.get("expected_validation")
        if not isinstance(expected_validation, dict):
            failures.append(f"{section}: expected_validation must be an object")
            continue
        if expected_validation.get("expected_ui_state") != fixture.get("ui_state"):
            failures.append(f"{section}: expected_ui_state must match ui_state")
        if expected_validation.get("app_can_execute") is True:
            failures.append(f"{section}: read-only Mission Control fixture cannot set app_can_execute true")

        hard_boundaries = fixture.get("hard_boundaries")
        if not isinstance(hard_boundaries, dict):
            failures.append(f"{section}: hard_boundaries must be an object")
        else:
            missing_boundaries = [
                boundary
                for boundary in MISSION_CONTROL_REQUIRED_HARD_BOUNDARIES
                if hard_boundaries.get(boundary) is not True
            ]
            if missing_boundaries:
                failures.append(f"{section}: missing true hard boundaries {', '.join(missing_boundaries)}")

        freshness = fixture.get("freshness")
        if not isinstance(freshness, dict):
            failures.append(f"{section}: freshness must be an object")
        else:
            for key in ("source_basis", "generated_at", "reviewed_at", "stale_conditions", "refresh_trigger"):
                if not freshness.get(key):
                    failures.append(f"{section}: freshness missing {key}")
            if expected_validation.get("fixture_valid") is True and freshness.get("source_commit") != UPLOAD_AUTHORITY_COMMIT:
                failures.append(f"{section}: valid fixtures must carry source_commit {UPLOAD_AUTHORITY_COMMIT}")

        evidence_refs = fixture.get("evidence_refs")
        if expected_validation.get("fixture_valid") is True and not evidence_refs:
            failures.append(f"{section}: valid fixtures must include evidence_refs")

        fixture_type = fixture.get("fixture_type")
        if fixture_type == "workspace_launch_profile":
            profile = fixture.get("profile")
            if not isinstance(profile, dict):
                failures.append(f"{section}: workspace fixture missing profile object")
            else:
                contains_exec = _profile_contains_executable_command_field(profile)
                if filename == "fixture_malformed_executable_profile.json":
                    if expected_validation.get("fixture_valid") is not False:
                        failures.append(f"{section}: malformed profile must be expected invalid")
                    if not contains_exec:
                        failures.append(f"{section}: malformed profile must contain a forbidden executable field")
                    if "reason_invalid" not in expected_validation:
                        failures.append(f"{section}: malformed profile must state reason_invalid")
                else:
                    if contains_exec:
                        failures.append(f"{section}: valid profile must not contain executable fields")
                    if not profile.get("required_next_launch_packet_for_execution"):
                        failures.append(f"{section}: profile missing required_next_launch_packet_for_execution")
                    if not _navigation_actions_are_clean(profile):
                        failures.append(f"{section}: profile navigation actions contain execution-looking terms")

        if filename == "fixture_packet_available_not_approved.json":
            packet = fixture.get("launch_packet", {})
            if packet.get("approval_receipt_or_operator_decision") is not None:
                failures.append(f"{section}: packet_available fixture must not include approval")
            if expected_validation.get("authorizes_execution") is not False:
                failures.append(f"{section}: packet_available fixture must not authorize execution")
            if expected_validation.get("must_display_for_review_only") is not True:
                failures.append(f"{section}: packet_available fixture must be review-only")

        if filename == "fixture_approval_receipt_valid.json":
            receipt = fixture.get("approval_receipt", {})
            required_receipt_fields = (
                "receipt_id",
                "launch_packet_id",
                "approved_by_operator",
                "approved_at",
                "approved_scope",
                "approved_action",
                "evidence_snapshot",
                "freshness_snapshot",
                "expiry",
                "replay_policy",
                "consumed_state",
                "lifecycle_state",
                "execution_result_reference",
                "revocation_state",
                "forbidden_scope_expansion",
            )
            missing = [field for field in required_receipt_fields if field not in receipt]
            if missing:
                failures.append(f"{section}: missing receipt fields {', '.join(missing)}")
            if receipt.get("expiry", {}).get("expired_state") is not False:
                failures.append(f"{section}: valid receipt fixture must not be expired")
            if expected_validation.get("authorizes_one_named_packet_action_scope") is not True:
                failures.append(f"{section}: valid receipt must bind one packet/action/scope")

        if filename == "fixture_approval_receipt_expired.json":
            receipt = fixture.get("approval_receipt", {})
            if receipt.get("expiry", {}).get("expired_state") is not True:
                failures.append(f"{section}: expired receipt must set expired_state true")
            if expected_validation.get("authorizes_execution") is not False:
                failures.append(f"{section}: expired receipt must not authorize execution")
            if expected_validation.get("must_display_expired_reason") is not True:
                failures.append(f"{section}: expired receipt must require visible reason")

        if filename == "fixture_stale_evidence_route.json":
            if fixture.get("freshness", {}).get("state") != "stale":
                failures.append(f"{section}: stale route must set freshness.state stale")
            route = fixture.get("launch_route", {})
            if route.get("launch_ready_claim_allowed") is not False:
                failures.append(f"{section}: stale route must block launch-ready claim")
            if expected_validation.get("must_display_stale_reason") is not True:
                failures.append(f"{section}: stale route must display stale reason")

        if filename == "fixture_blocked_missing_authority.json":
            route = fixture.get("launch_route", {})
            if not route.get("blocked_reason"):
                failures.append(f"{section}: blocked route missing blocked_reason")
            if route.get("launch_authorized_claim_allowed") is not False:
                failures.append(f"{section}: missing authority must block launch-authorized claim")
            if expected_validation.get("must_distinguish_launch_ready_from_launch_authorized") is not True:
                failures.append(f"{section}: must distinguish launch-ready from launch-authorized")

        if filename == "fixture_ui_claim_without_evidence.json":
            ui_claim = fixture.get("ui_claim", {})
            claimed_states = set(ui_claim.get("claimed_states", []))
            proof_claims = {"healthy", "current", "tested", "running", "synced"}
            if not claimed_states.intersection(proof_claims):
                failures.append(f"{section}: malformed UI claim must include proof-demanding states")
            if ui_claim.get("source_commit") is not None or ui_claim.get("artifact") is not None or ui_claim.get("evidence_refs"):
                failures.append(f"{section}: negative UI claim must lack source commit, artifact, and evidence")
            if expected_validation.get("fixture_valid") is not False:
                failures.append(f"{section}: UI claim without evidence must be expected invalid")
            if expected_validation.get("must_not_soften_unknown_into_confidence") is not True:
                failures.append(f"{section}: unknown must not soften into confidence")

        if filename == "fixture_operator_experience_golden_overview.json":
            overview = fixture.get("overview", {})
            taste_eval = overview.get("taste_eval", {})
            required_taste_flags = (
                "operator_can_orient_within_seconds",
                "authority_boundaries_visually_obvious",
                "status_copy_exact_and_evidence_backed",
                "calm_sparse_premium_controlled",
                "rejects_fake_intelligence",
                "rejects_chatbot_slop",
                "rejects_generic_admin_panel_energy",
            )
            missing_taste = [flag for flag in required_taste_flags if taste_eval.get(flag) is not True]
            if missing_taste:
                failures.append(f"{section}: missing true taste flags {', '.join(missing_taste)}")
            for visible in ("north_star", "current_route", "authority", "freshness", "evidence", "next_safe_action"):
                if visible not in overview.get("visible_sections", []):
                    failures.append(f"{section}: golden overview must expose {visible}")

    return tuple(failures)


def _fixture_contains_forbidden_naming_field(value: object) -> bool:
    if isinstance(value, dict):
        return any(
            key in FIRST_SCREEN_FORBIDDEN_NAMING_FIELDS
            or _fixture_contains_forbidden_naming_field(nested)
            for key, nested in value.items()
        )
    if isinstance(value, list):
        return any(_fixture_contains_forbidden_naming_field(item) for item in value)
    return False


def _text_contains_forbidden_naming_assignment(text: str) -> str | None:
    for forbidden in FIRST_SCREEN_FORBIDDEN_NAMING_FIELDS:
        if re.search(rf"\b{re.escape(forbidden)}\s*[:=]", text):
            return forbidden
    return None


def first_screen_composition_failures(repo_root: Path = REPO_ROOT) -> tuple[str, ...]:
    failures: list[str] = []
    spec_path = repo_root / "docs" / "planning" / "launch_ladder" / "13_MAC_DESKTOP_FIRST_SCREEN_COMPOSITION_SPEC.md"
    fixture_dir = _fixture_dir(repo_root)

    if not spec_path.is_file():
        failures.append(f"first screen composition: missing {spec_path}")
        spec_text = ""
    else:
        spec_text = _read_text(spec_path)
        spec_normalized = normalize(spec_text)
        _require_all(
            failures,
            spec_normalized,
            "first screen composition spec",
            (
                "first-screen layout thesis",
                "top operating context band",
                "left active lanes column",
                "center current focus selected lane",
                "right next safe move panel",
                "lower evidence freshness drawer",
                "quiet recent changes strip",
                "future knowledge context strip",
                "default visible copy for current project state",
                "card density and hierarchy rules",
                "state color emphasis guidance",
                "what must be tucked away",
                "first-screen golden examples",
                "first-screen malformed examples",
                "boundaries before implementation",
                "calm cockpit personal command desk",
                "evidence-backed, not bureaucratic",
                "personal/operator-specific, not generic SaaS",
                "next safe move, not task-manager sprawl",
                "knowledge context, not a RAG search box",
                "Unknown means unknown",
                "Blocked means protected boundary, not panic",
                "Nothing moves just because it is visible",
                "Do not name the app",
                "No UI implementation",
                "No SwiftUI/AppKit files",
                "No backend/schema/SQLite work",
                "No SQLite database",
                "No ingestion scripts",
                "No old business-file scanning",
                "No private-data inspection",
                "No provider/model calls",
                "No runtime/service/approval mutation",
            ),
        )
        _require_all(
            failures,
            spec_normalized,
            "first screen neutral naming phrases",
            FIRST_SCREEN_ALLOWED_APP_PHRASES,
        )
        _require_all(
            failures,
            spec_normalized,
            "first screen example cards",
            (
                "Active Lane Card",
                "Next Safe Move Card",
                "Evidence/Freshness Card",
                "Recent Commit / Source-Set Card",
                "Knowledge Context Card",
                "Blocked Without Panic Card",
                "Unknown Without Fake Confidence Card",
            ),
        )
        _require_all(
            failures,
            spec_normalized,
            "first screen fixture names",
            REQUIRED_FIRST_SCREEN_FIXTURES,
        )

    loaded: dict[str, dict] = {}
    for filename in REQUIRED_FIRST_SCREEN_FIXTURES:
        path = fixture_dir / filename
        if not path.is_file():
            failures.append(f"first screen fixture: missing {path}")
            continue
        try:
            loaded[filename] = json.loads(_read_text(path))
        except json.JSONDecodeError as exc:
            failures.append(f"first screen fixture: invalid JSON in {path}: {exc}")

    for filename, fixture in loaded.items():
        section = f"first screen fixture {filename}"
        expected_id = filename.removesuffix(".json")
        if fixture.get("fixture_id") != expected_id:
            failures.append(f"{section}: fixture_id must be {expected_id}")
        if fixture.get("fixture_type") != "first_screen_composition":
            failures.append(f"{section}: fixture_type must be first_screen_composition")
        if fixture.get("app_surface") != MISSION_CONTROL_APP_SURFACE:
            failures.append(f"{section}: app_surface must be {MISSION_CONTROL_APP_SURFACE}")
        if fixture.get("source_set_baseline") != MISSION_CONTROL_SOURCE_SET_BASELINE:
            failures.append(
                f"{section}: source_set_baseline must be {MISSION_CONTROL_SOURCE_SET_BASELINE}"
            )
        if fixture.get("source_manifest_commit") != UPLOAD_AUTHORITY_COMMIT:
            failures.append(f"{section}: source_manifest_commit must be {UPLOAD_AUTHORITY_COMMIT}")
        if _fixture_contains_forbidden_naming_field(fixture):
            failures.append(f"{section}: fixture must not introduce app/product/brand/codename fields")

        expected_validation = fixture.get("expected_validation")
        if not isinstance(expected_validation, dict):
            failures.append(f"{section}: expected_validation must be an object")
            continue
        if expected_validation.get("app_can_execute") is not False:
            failures.append(f"{section}: first-screen fixture must set app_can_execute false")

        hard_boundaries = fixture.get("hard_boundaries")
        if not isinstance(hard_boundaries, dict):
            failures.append(f"{section}: hard_boundaries must be an object")
        else:
            required_boundaries = MISSION_CONTROL_REQUIRED_HARD_BOUNDARIES + FIRST_SCREEN_EXTRA_HARD_BOUNDARIES
            missing_boundaries = [
                boundary
                for boundary in required_boundaries
                if hard_boundaries.get(boundary) is not True
            ]
            if missing_boundaries:
                failures.append(f"{section}: missing true hard boundaries {', '.join(missing_boundaries)}")

        freshness = fixture.get("freshness")
        if not isinstance(freshness, dict):
            failures.append(f"{section}: freshness must be an object")
        else:
            for key in ("source_basis", "generated_at", "reviewed_at", "stale_conditions", "refresh_trigger"):
                if not freshness.get(key):
                    failures.append(f"{section}: freshness missing {key}")
            if freshness.get("source_commit") != UPLOAD_AUTHORITY_COMMIT:
                failures.append(f"{section}: freshness.source_commit must be {UPLOAD_AUTHORITY_COMMIT}")

        fixture_valid = expected_validation.get("fixture_valid")
        if filename.startswith("golden_"):
            if fixture_valid is not True:
                failures.append(f"{section}: golden fixture must be valid")
            if expected_validation.get("read_only_app_planning_posture") is not True:
                failures.append(f"{section}: golden fixture must preserve read-only app-planning posture")
            if not fixture.get("evidence_refs"):
                failures.append(f"{section}: golden fixture must include evidence_refs")
            zones = fixture.get("zones")
            if not isinstance(zones, list):
                failures.append(f"{section}: golden fixture must include zones list")
            else:
                missing_zones = [zone for zone in FIRST_SCREEN_ZONES if zone not in zones]
                if missing_zones:
                    failures.append(f"{section}: missing zones {', '.join(missing_zones)}")

        if filename.startswith("malformed_"):
            if fixture_valid is not False:
                failures.append(f"{section}: malformed fixture must be invalid")
            if not expected_validation.get("expected_invalid_reason"):
                failures.append(f"{section}: malformed fixture must include expected_invalid_reason")

        if filename == "golden_first_screen_local_ahead_of_origin.json":
            source_state = fixture.get("source_control_state", {})
            if source_state.get("local_ahead_of_origin") is not True:
                failures.append(f"{section}: must represent local ahead of origin")
            if source_state.get("origin_sync_verified") is not False:
                failures.append(f"{section}: origin sync must not be verified")
            if source_state.get("push_evidence_present") is not False:
                failures.append(f"{section}: push evidence must be absent")
            if expected_validation.get("must_not_claim_synced_or_current") is not True:
                failures.append(f"{section}: must reject synced/current copy")

        if filename == "golden_first_screen_knowledge_context_non_ingestive.json":
            knowledge_context = fixture.get("knowledge_context", {})
            required_false = (
                "active_ingestion",
                "sqlite_database_exists",
                "business_archive_scanned",
                "claims_promoted",
                "business_file_truth_claims",
            )
            false_violations = [key for key in required_false if knowledge_context.get(key) is not False]
            if false_violations:
                failures.append(f"{section}: knowledge context must keep false {', '.join(false_violations)}")
            if knowledge_context.get("future_context_only") is not True:
                failures.append(f"{section}: knowledge context must be future_context_only")
            if knowledge_context.get("knowledge_context_not_rag_search_box") is not True:
                failures.append(f"{section}: knowledge context must not become a RAG search box")
            if expected_validation.get("must_preserve_knowledge_context_non_ingestive") is not True:
                failures.append(f"{section}: expected_validation must preserve non-ingestive posture")

        if filename == "golden_first_screen_unknown_preserved.json":
            unknown_card = fixture.get("unknown_card", {})
            if "unknown" not in str(unknown_card.get("display_rule", "")).lower():
                failures.append(f"{section}: unknown display rule must say unknown")
            if expected_validation.get("must_not_soften_unknown_into_confidence") is not True:
                failures.append(f"{section}: unknown must not soften into confidence")

        if filename == "malformed_first_screen_ai_command_center.json":
            bad_copy = json.dumps(fixture.get("bad_copy", {}), sort_keys=True)
            if "AI Command Center" not in bad_copy:
                failures.append(f"{section}: malformed copy must include AI Command Center anti-pattern")
            for key in (
                "rejects_chatbot_home",
                "rejects_ai_command_center",
                "rejects_business_file_truth_claims",
                "rejects_hidden_intelligence",
            ):
                if expected_validation.get(key) is not True:
                    failures.append(f"{section}: expected_validation missing {key}")

        if filename == "malformed_first_screen_profile_executes_work.json":
            profile_card = fixture.get("profile_card", {})
            if not profile_card.get("on_open_execution"):
                failures.append(f"{section}: malformed profile must include on_open_execution")
            if expected_validation.get("rejects_profile_execution") is not True:
                failures.append(f"{section}: expected_validation must reject profile execution")
            if expected_validation.get("requires_separate_launch_packet_for_execution") is not True:
                failures.append(f"{section}: expected_validation must require separate launch packet")

        if filename == "malformed_first_screen_synced_after_push_failure.json":
            source_state = fixture.get("source_control_state", {})
            if source_state.get("local_ahead_of_origin") is not True:
                failures.append(f"{section}: malformed fixture must model local ahead")
            if source_state.get("push_evidence_present") is not False:
                failures.append(f"{section}: malformed fixture must lack push evidence")
            bad_copy = str(source_state.get("bad_visible_copy", "")).lower()
            if "synced" not in bad_copy or "current" not in bad_copy:
                failures.append(f"{section}: malformed fixture must claim synced/current")
            if expected_validation.get("rejects_fake_synced_current_claims") is not True:
                failures.append(f"{section}: expected_validation must reject fake synced/current claims")

    return tuple(failures)


def taste_and_quiet_feedback_failures(repo_root: Path = REPO_ROOT) -> tuple[str, ...]:
    failures: list[str] = []
    taste_path = repo_root / "docs" / "planning" / "launch_ladder" / "14_MAC_DESKTOP_TASTE_AND_ATMOSPHERE_SPEC.md"
    sound_path = (
        repo_root
        / "docs"
        / "planning"
        / "launch_ladder"
        / "15_MAC_DESKTOP_SOUND_HAPTICS_QUIET_FEEDBACK_ADDENDUM.md"
    )

    if not taste_path.is_file():
        failures.append(f"taste and atmosphere: missing {taste_path}")
        taste_text = ""
    else:
        taste_text = _read_text(taste_path)
        taste_normalized = normalize(taste_text)
        _require_all(
            failures,
            taste_normalized,
            "taste spec required sections",
            TASTE_REQUIRED_SECTIONS,
        )
        _require_all(
            failures,
            taste_normalized,
            "taste spec doctrine",
            (
                "Opening the Mac desktop app should feel like sitting down at a trusted personal command surface",
                "closer to powering on a well-built studio console before a session than launching a productivity app",
                "Target emotional state: centered operational clarity",
                "I know where things stand. I know what is safe. I know what is blocked. I know what deserves my attention.",
                "Dominant blend: quiet instrument panel + studio console + evidence drawer + chart table",
                "Cockpit guides discipline, not decoration",
                "Studio console is the strongest personal metaphor, but do not literalize knobs/faders everywhere",
                "Tactile but not skeuomorphic",
                "Dimensional but not flashy",
                "Evidence-backed but not bureaucratic",
                "Personal but not cute",
                "Creative but not whimsical slop",
                "Minimal purposeful motion only",
                "fake AI thinking animation",
                "hidden-worker theatre",
                "Knowledge substrate must not default to RAG search/chat-with-files UX",
                "No app naming",
                "No implementation authorization",
                "Taste comes from structure, not branding",
                "personal and daily-use-worthy, not merely correct",
            ),
        )
        _require_all(
            failures,
            taste_normalized,
            "taste spec vibe tests",
            TASTE_VIBE_TESTS,
        )
        _require_all(
            failures,
            taste_normalized,
            "taste spec anti-vibe tests",
            TASTE_ANTI_VIBE_TESTS,
        )
        _require_all(
            failures,
            taste_normalized,
            "taste spec no-implementation boundary",
            (
                "Do not",
                "implement UI",
                "create SwiftUI/AppKit files",
                "create source-set folders",
                "create backend/schema files",
                "create SQLite DBs",
                "create ingestion scripts",
                "scan old business files",
                "inspect private data",
                "call providers/models",
                "mutate runtime/services/approvals",
                "create audio assets, haptic implementation, notification behavior, or sound settings UI",
                "introduce app/product/brand/codename/mascot/logo/slogan",
            ),
        )
        _require_all(
            failures,
            taste_normalized,
            "taste spec next artifact",
            (
                "Recommended next artifact: combined source-set generation for the app-planning package",
                "Do not do another broad design pass",
                "15_MAC_DESKTOP_SOUND_HAPTICS_QUIET_FEEDBACK_ADDENDUM.md as a separate addendum",
                "This recommendation does not create source-set folders",
            ),
        )
        _require_all(
            failures,
            taste_normalized,
            "taste spec neutral phrases",
            FIRST_SCREEN_ALLOWED_APP_PHRASES,
        )
        forbidden_assignment = _text_contains_forbidden_naming_assignment(taste_text)
        if forbidden_assignment:
            failures.append(f"taste spec: must not introduce naming assignment {forbidden_assignment}")

    if not sound_path.is_file():
        failures.append(f"sound haptics addendum: missing {sound_path}")
        sound_text = ""
    else:
        sound_text = _read_text(sound_path)
        sound_normalized = normalize(sound_text)
        _require_all(
            failures,
            sound_normalized,
            "sound haptics required sections",
            SOUND_REQUIRED_SECTIONS,
        )
        _require_all(
            failures,
            sound_normalized,
            "sound haptics doctrine",
            (
                "Sound should play a minor, disciplined role",
                "tactile confirmation from a well-built studio surface",
                "soft relay, settled switch, quiet indication that a visible state transition completed",
                "Emotional target: settled confidence, not excitement",
                "should not create anticipation, urgency, mystery",
                "hidden agents are working somewhere offscreen",
                "best sound design is almost forgettable",
                "Sound should be off by default for v1",
                "Quiet feedback mode should be opt-in",
                "Critical information must never be sound-only",
                "short",
                "low-volume",
                "low-frequency",
                "non-melodic",
                "tied only to visible state transitions",
                "Brand/audio identity is deferred",
            ),
        )
        _require_all(
            failures,
            sound_normalized,
            "allowed sound moments",
            (
                "app opened",
                "source-set changed",
                "evidence/proof completed",
                "blocked boundary",
                "unknown/evidence missing",
                "approval needed",
                "local checkpoint committed",
                "push/sync failed",
                "lane selected",
                "drawer opened",
            ),
        )
        _require_all(
            failures,
            sound_normalized,
            "forbidden sound patterns",
            (
                "AI thinking sounds",
                "sci-fi sweeps",
                "startup chimes",
                "notification spam",
                "casino/game pings",
                "dramatic warning alarms",
                "hidden-worker sounds",
                "chatbot message sounds",
                "ambient system is alive hum",
                "anything implying background action without visible evidence",
            ),
        )
        _require_all(
            failures,
            sound_normalized,
            "sonic reference vocabulary",
            (
                "soft relay",
                "muted tape transport",
                "console click",
                "felt switch",
                "low meter tick",
                "subdued room tone as dangerous if continuous",
                "quiet confirmation",
                "boundary thud",
            ),
        )
        _require_all(
            failures,
            sound_normalized,
            "sound haptics vibe tests",
            SOUND_VIBE_TESTS,
        )
        _require_all(
            failures,
            sound_normalized,
            "sound haptics anti-vibe tests",
            SOUND_ANTI_VIBE_TESTS,
        )
        _require_all(
            failures,
            sound_normalized,
            "sound haptics no-implementation boundary",
            (
                "does not create audio assets",
                "sound asset folders",
                "haptic implementation",
                "notification behavior",
                "sound settings UI",
                "Do not generate audio assets",
                "haptic code",
                "notification behavior",
                "sound settings UI",
                "source-set folders",
                "backend/schema files",
                "SQLite DBs",
                "ingestion scripts",
                "runtime hooks",
                "provider/model calls",
                "approval behavior",
                "private-data access",
                "app names",
            ),
        )
        _require_all(
            failures,
            sound_normalized,
            "sound haptics addendum linkage",
            (
                "separate addendum",
                "14_MAC_DESKTOP_TASTE_AND_ATMOSPHERE_SPEC.md",
                "include it in the next combined source-set generation package",
            ),
        )
        forbidden_assignment = _text_contains_forbidden_naming_assignment(sound_text)
        if forbidden_assignment:
            failures.append(f"sound haptics addendum: must not introduce naming assignment {forbidden_assignment}")

    return tuple(failures)


def mac_app_knowledge_source_set_failures(repo_root: Path = REPO_ROOT) -> tuple[str, ...]:
    failures: list[str] = []
    brief_path = (
        repo_root
        / "docs"
        / "planning"
        / "launch_ladder"
        / "16_MAC_APP_KNOWLEDGE_SUBSTRATE_SOURCE_SET_BRIEF.md"
    )
    refresh_path = repo_root / "mac_eyes" / "Launchers" / "refresh_operator_harness_ingest.sh"

    if not brief_path.is_file():
        failures.append(f"mac app knowledge source set: missing {brief_path}")
        brief_text = ""
    else:
        brief_text = _read_text(brief_path)
        brief_normalized = normalize(brief_text)
        _require_all(
            failures,
            brief_normalized,
            "mac app knowledge source-set purpose",
            (
                MAC_APP_KNOWLEDGE_SOURCE_SET,
                "combined ChatGPT Project source set",
                "Mac desktop Mission Control app planning",
                "read-only fixture contracts",
                "first-screen composition",
                "taste/atmosphere posture",
                "sound/haptics/quiet feedback posture",
                "SQLite-backed Compiled Knowledge Substrate planning",
                "not an implementation source set",
                "Mac desktop app first; iOS companion later",
                "personal/custom operator console for Winship/operator first",
            ),
        )
        _require_all(
            failures,
            brief_normalized,
            "mac app knowledge source-set boundaries",
            (
                "Do not name the app",
                "Do not invent product names",
                "Mac desktop app",
                "Operator Harness app",
                "personal operator console",
                "Mission Control surface",
                "No SwiftUI/AppKit implementation",
                "No backend/API/schema implementation",
                "No SQLite DB creation",
                "No ingestion scripts",
                "No real business-file scanning",
                "No provider/model calls",
                "No runtime mutation",
                "No approval mutation or Guardian control",
                "No audio assets, haptic implementation, notification behavior, or sound settings UI",
                "No app/product/brand/codename/mascot/logo/slogan",
            ),
        )
        _require_all(
            failures,
            brief_normalized,
            "mac app knowledge source-set doctrine",
            (
                "SQLite stores the memory; markdown speaks it; HTML preserves shape; FTS finds it; compiled notes make it useful",
                "This is not vanilla RAG",
                "Retrieval finds candidates",
                "SQLite is the canonical future local memory substrate concept",
                "Markdown is an export/handoff surface, not the database authority",
                "HTML/rich fragments preserve source shape",
                "FTS5/search finds records quickly",
                "Raw files are evidence, not truth",
                "Extracted text is parsed evidence, not truth",
                "Compiled notes are interpretation, not truth",
                "Claims are evidence-backed and confidence-bounded",
                "Operator promotions are explicit acceptance",
                "Unknown means unknown and defaults restricted",
                "Sensitive content is local-only by default",
                "No external model access to raw/extracted sensitive content is authorized",
            ),
        )
        _require_all(
            failures,
            brief_normalized,
            "mac app knowledge source-set upload rule",
            (
                "23 content files",
                "1 MANIFEST.md",
                "CHAT_STAY_UP_TO_DATE.md remains adjacent bridge context",
                "must not be copied into 03_MAC_APP_KNOWLEDGE_SUBSTRATE",
                "must not be counted inside the 24 files",
            ),
        )
        forbidden_assignment = _text_contains_forbidden_naming_assignment(brief_text)
        if forbidden_assignment:
            failures.append(
                f"mac app knowledge source set: must not introduce naming assignment {forbidden_assignment}"
            )

    if not refresh_path.is_file():
        failures.append(f"mac app knowledge source set: missing {refresh_path}")
    else:
        refresh_text = _read_text(refresh_path)
        for filename in MAC_APP_KNOWLEDGE_SOURCE_SET_FILES:
            if filename not in refresh_text:
                failures.append(f"mac app knowledge source set: refresh script missing {filename}")
        _require_all(
            failures,
            normalize(refresh_text),
            "mac app knowledge source-set script",
            (
                'FOLDER_3="03_MAC_APP_KNOWLEDGE_SUBSTRATE"',
                "Combined Mac desktop Mission Control and Compiled Knowledge Substrate planning",
                "CONTENT_FILES_PER_FOLDER=23",
                "EXPECTED_FILES_PER_FOLDER=24",
            ),
        )

    return tuple(failures)


def backend_data_contract_readiness_plan_failures(
    repo_root: Path = REPO_ROOT,
) -> tuple[str, ...]:
    failures: list[str] = []
    plan_path = (
        repo_root
        / "docs"
        / "planning"
        / "launch_ladder"
        / "17_BACKEND_DATA_CONTRACT_READINESS_PLAN.md"
    )

    if not plan_path.is_file():
        return (f"backend data contract readiness plan: missing {plan_path}",)

    plan_text = _read_text(plan_path)
    plan_normalized = normalize(plan_text)

    _require_all(
        failures,
        plan_normalized,
        "backend data contract readiness required sections",
        BACKEND_DATA_CONTRACT_REQUIRED_SECTIONS,
    )

    _require_all(
        failures,
        plan_normalized,
        "backend data contract readiness folder recommendation",
        (
            BACKEND_DATA_CONTRACT_SOURCE_SET,
            "safer than 04_BACKEND_AND_DATA_MODEL",
            "Backend/data-model sounds implementation-adjacent",
            "Backend/data-contract readiness keeps the lane focused on records, contract boundaries, synthetic fixture intent, and validation expectations",
            "before actual backend/schema/SQLite work starts",
            "planning, not source-set generation",
        ),
    )

    _require_all(
        failures,
        plan_normalized,
        "backend data contract readiness rationale",
        (
            "03_MAC_APP_KNOWLEDGE_SUBSTRATE answered the app and knowledge direction",
            "next bottleneck is data-contract readiness",
            "records and contract boundaries must exist",
            "knowledge, evidence, freshness, blocked/unknown states, promotions, and packets without lying",
            "not backend implementation",
        ),
    )

    _require_all(
        failures,
        plan_normalized,
        "backend data contract readiness 03 answers",
        (
            "Mac desktop first",
            "iOS companion later",
            "read-only Mission Control surface",
            "personal operator console",
            "not a chatbot, SaaS admin panel, or agent theater",
            "compile-first",
            "not vanilla RAG",
            "SQLite is the future canonical local memory concept",
            "Markdown is an export and handoff surface",
            "HTML/rich fragments preserve source shape",
            "FTS/search finds records",
            "Raw files are evidence, not truth",
            "Extracted text is parsed evidence, not truth",
            "Rendered fragments preserve source shape, not authority",
            "Artifact classifications are reviewed interpretations, not safety guarantees",
            "Claims are evidence-backed and confidence-bounded",
            "Compiled notes are interpretation, not truth",
            "Operator promotions are explicit accept/reject/historical/sensitive/excluded decisions",
            "Freshness must be target-scoped",
            "Conversation packets must be sanitized and non-authorizing",
            "Unknown defaults restricted",
            "Sensitive content is local-only by default",
            "Evidence/freshness must exist before UI or app state claims",
            "Sound/haptics are quiet, optional, and non-authoritative",
            "No app naming yet",
        ),
    )

    _require_all(
        failures,
        plan_normalized,
        "backend data contract readiness unresolved questions",
        (
            "Markdown table contracts vs JSON Schema vs SQL DDL vs staged progression",
            "which conceptual records become first-class contract objects",
            "which synthetic fixture topics become actual JSON fixtures later",
            "where backend/data-contract docs should live",
            "whether operator promotions belong inside the knowledge substrate contract, broader Launch Ladder authority contract, or both",
            "conversation packets are sanitized without accidentally authorizing provider/model use",
            "blocked/unknown/sensitive records are represented to the app without exposing private content",
            "Freshness scoping: source, extraction, rendered fragment, classification, claim, compiled note, packet, promotion, or all",
            "whether Knowledge Atlas remains app-facing language only or becomes backend aggregate contract language",
            "audit events/substrate events relate to Launch Packets, Approval Receipts, and evidence/freshness receipts",
        ),
    )

    _require_all(
        failures,
        plan_normalized,
        "backend data contract readiness candidate files",
        (
            "23 content files plus MANIFEST.md",
            "MANIFEST.md",
            "17_BACKEND_DATA_CONTRACT_READINESS_PLAN.md",
            "16_MAC_APP_KNOWLEDGE_SUBSTRATE_SOURCE_SET_BRIEF.md",
            "11_NEXT_IMPLEMENTATION_SEQUENCE.md",
            "04_LAUNCH_LADDER_MODEL.md",
            "05_EVIDENCE_AND_FRESHNESS.md",
            "06_ROUTING_AND_WORKSPACES.md",
            "07_SECURITY_AND_AUTHORITY.md",
            "08_SOURCE_SET_REFRESH_SYSTEM.md",
            "09_MAC_IOS_APP_BUILD_BRIEF.md",
            "12_MAC_DESKTOP_MISSION_CONTROL_FIXTURE_CONTRACT.md",
            "13_MAC_DESKTOP_FIRST_SCREEN_COMPOSITION_SPEC.md",
            "KNOWLEDGE_SUBSTRATE_README.md",
            "KNOWLEDGE_SUBSTRATE_INDEX.md",
            "KNOWLEDGE_SUBSTRATE_01_NORTH_STAR.md",
            "KNOWLEDGE_SUBSTRATE_02_SQLITE_LAYER_MODEL.md",
            "KNOWLEDGE_SUBSTRATE_03_SAFETY_AND_SENSITIVITY_LEVELS.md",
            "KNOWLEDGE_SUBSTRATE_04_APP_CARDS_AND_UI_STATES.md",
            "KNOWLEDGE_SUBSTRATE_05_FIXTURE_PLAN.md",
            "KNOWLEDGE_SUBSTRATE_06_STATIC_VALIDATION_EXPECTATIONS.md",
            "VALIDATION_MAP.md",
            "launch_ladder_contract_check.py",
            "test_launch_ladder_static_contract.py",
            "lower-priority for 04 because 03 already preserved taste, sound, and app feel",
        ),
    )

    _require_all(
        failures,
        plan_normalized,
        "backend data contract readiness record topics",
        BACKEND_DATA_CONTRACT_RECORD_TOPICS,
    )

    _require_all(
        failures,
        plan_normalized,
        "backend data contract readiness validation expectations",
        (
            "Exact 24-file source set",
            "Manifest commit/timestamps/purpose/stale conditions",
            "No backend/schema/SQLite implementation claims",
            "No ingestion/scanning/provider/private/runtime authorization",
            "Record-state separation",
            "Raw/extracted/rendered/classified/claim/compiled/promoted/freshness/packet/audit separation",
            "Unknown restricted",
            "Sensitive local-only",
            "Conversation packets not implying external-model safety",
            "Promotions target/scope limits",
            "Freshness target-scoping, not whole-system health",
            "Workspace Launch Profiles navigation-only",
            "Launch Packets separate from Approval Receipts",
            "UI/app claims needing evidence/freshness proof",
            "Future fixtures synthetic only",
            "No app naming",
            "No audio/haptic/notification implementation",
        ),
    )

    _require_all(
        failures,
        plan_normalized,
        "backend data contract readiness boundaries",
        BACKEND_DATA_CONTRACT_BOUNDARIES,
    )

    _require_all(
        failures,
        plan_normalized,
        "backend data contract readiness next move",
        (
            "After this artifact is committed, the next move should be source-set generation",
            BACKEND_DATA_CONTRACT_SOURCE_SET,
            "should still be readiness/planning, not backend implementation",
            "Do not generate the 04 source set in this slice",
        ),
    )

    forbidden_assignment = _text_contains_forbidden_naming_assignment(plan_text)
    if forbidden_assignment:
        failures.append(
            "backend data contract readiness plan: "
            f"must not introduce naming assignment {forbidden_assignment}"
        )

    forbidden_authorizing_phrases = (
        "This slice implements backend",
        "This plan implements backend",
        "Generate 04_BACKEND_DATA_CONTRACT_READINESS now",
        "Create 04_BACKEND_DATA_CONTRACT_READINESS now",
        "Create SQL DDL now",
        "Create a SQLite DB now",
        "Create ingestion scripts now",
        "Create fixtures now",
        "Call providers/models now",
        "Name the app now",
    )
    for phrase in forbidden_authorizing_phrases:
        if phrase in plan_text:
            failures.append(
                "backend data contract readiness plan: forbidden authorizing phrase "
                f"{phrase!r}"
            )

    return tuple(failures)


def backend_data_contract_shape_plan_failures(
    repo_root: Path = REPO_ROOT,
) -> tuple[str, ...]:
    failures: list[str] = []
    plan_path = (
        repo_root
        / "docs"
        / "planning"
        / "launch_ladder"
        / "18_BACKEND_DATA_CONTRACT_SHAPE_PLAN.md"
    )

    if not plan_path.is_file():
        return (f"backend data contract shape plan: missing {plan_path}",)

    plan_text = _read_text(plan_path)
    plan_normalized = normalize(plan_text)

    _require_all(
        failures,
        plan_normalized,
        "backend data contract shape required elements",
        (
            "18 plan exists",
            "required record shapes are named",
            "forbidden implementation authorizations are absent",
            "state-separation phrases are preserved",
            "locally confirmed OpenClaw 2026.4.24 CLI help surfaces are present",
            "CLI help caveat is preserved: surfaces only, not audited internal behavior or runtime state",
            "local OpenClaw surfaces are evidence sources for future Mission Control cards, not direct authority to execute actions",
            "unknown restricted and sensitive local-only are preserved",
            "app-facing states require evidence/freshness basis",
            "no source-set 05 generation occurs in this slice",
        ),
    )

    record_shapes = (
        "source file record",
        "extracted text record",
        "rendered fragment record",
        "artifact classification record",
        "claim record",
        "contradiction record",
        "compiled note record",
        "freshness record",
        "operator promotion record",
        "conversation packet record",
        "blocked sensitive source record",
        "unknown/unclassified artifact record",
    )
    _require_all(failures, plan_normalized, "backend data contract shape record shapes", record_shapes)

    local_openclaw_surfaces = (
        "Locally Confirmed OpenClaw 2026.4.24 Surfaces",
        "local CLI path",
        "/home/openclaw/.nvm/versions/node/v24.14.0/bin/openclaw",
        "OpenClaw 2026.4.24",
        "acp",
        "tasks",
        "memory",
        "infer",
        "capability",
        "exec-policy",
        "approvals",
        "sessions",
        "status",
    )
    _require_all(
        failures,
        plan_normalized,
        "backend data contract shape local OpenClaw surfaces",
        local_openclaw_surfaces,
    )

    local_openclaw_caveat = (
        "CLI help-visible local surfaces only",
        "does not confirm audited internal behavior",
        "runtime state",
        "not as direct authority to execute actions",
    )
    _require_all(
        failures,
        plan_normalized,
        "backend data contract shape local OpenClaw caveat",
        local_openclaw_caveat,
    )

    local_openclaw_mapping = (
        "tasks -> future task/worker/flow state cards",
        "sessions -> future conversation/session continuity cards",
        "memory -> future knowledge/evidence/freshness surface, but not truth by itself",
        "infer / capability -> provider-call authority boundary",
        "exec-policy / approvals -> policy/approval state cards",
        "acp -> agent/crew communication lane visibility",
        "status -> system health/status evidence, without overclaiming",
        "Local OpenClaw CLI surfaces should be treated as upstream evidence sources for future Mission Control cards, not as direct authority to execute actions",
    )
    _require_all(
        failures,
        plan_normalized,
        "backend data contract shape local OpenClaw mapping",
        local_openclaw_mapping,
    )

    forbidden_authorizing_phrases = (
        "This slice implements backend",
        "This plan implements backend",
        "Create backend/API/schema files now",
        "Create SQL DDL now",
        "Create a SQLite DB now",
        "Create ingestion scripts now",
        "Create fixtures now",
        "Call providers/models now",
        "Run provider calls now",
        "Inspect private data now",
        "Inspect runtime state now",
        "Mutate runtime now",
        "Create SwiftUI/AppKit files now",
        "Create audio assets now",
        "Create haptics now",
        "Create notifications now",
        "Name the app now",
        "Create source-set folder 05 now",
        "Generate source-set 05 now",
        "Generate 05_ now",
    )
    for phrase in forbidden_authorizing_phrases:
        if phrase in plan_text:
            failures.append(
                "backend data contract shape plan: forbidden authorizing phrase "
                f"{phrase!r}"
            )

    return tuple(failures)


def backend_data_contract_first_implementation_slice_readiness_failures(
    repo_root: Path = REPO_ROOT,
) -> tuple[str, ...]:
    failures: list[str] = []
    bridge_dir = repo_root / "docs" / "planning" / "launch_ladder" / "source_set_bridges"
    plan_path = (
        bridge_dir / "backend_data_contract_first_implementation_slice_readiness_20260505.md"
    )
    north_star_path = bridge_dir / "operator_north_star_machine_contract_20260505.md"

    if not plan_path.is_file():
        return (f"backend first implementation slice readiness: missing {plan_path}",)

    plan_text = _read_text(plan_path)
    plan_normalized = normalize(plan_text)

    _require_all(
        failures,
        plan_normalized,
        "backend first implementation slice readiness required gates",
        (
            "Backend Data Contract First Implementation Slice Readiness",
            "first safe future backend/data-contract implementation slice is static semantic-contract enforcement",
            "durable semantic contract matrix",
            "implementation-readiness checklist",
            "source-set 04 bridge",
            "source-set 04 manifest",
            "Command Atlas context-filter doctrine",
            "doc 30's exclusion/classification-only rule for docs 26/27/28/29",
            "Private roots and private-data surfaces",
            "separate future implementation prompt",
            "Exact Future Allowed Edit Paths",
            "launch_ladder_contract_check.py",
            "tests/test_launch_ladder_static_contract.py",
            "docs/testing/VALIDATION_MAP.md",
            "Forbidden actions remain",
            "Required Future Validation Receipts",
            "python3 launch_ladder_contract_check.py",
            "pytest tests/test_launch_ladder_static_contract.py",
            "python3 -m py_compile launch_ladder_contract_check.py",
        ),
    )

    if not north_star_path.is_file():
        failures.append(
            f"backend first implementation slice North Star alignment: missing {north_star_path}"
        )
    else:
        north_star_normalized = normalize(f"{plan_text}\n\n{_read_text(north_star_path)}")
        _require_all(
            failures,
            north_star_normalized,
            "backend first implementation slice North Star alignment",
            (
                "Operator North Star Machine Contract",
                "Backend/Data-Contract Gates Preserved",
                "receivables/chase-money steel thread",
                "durable backend/data-contract semantic contract matrix remains the semantic gate",
                "implementation-readiness checklist remains the gate before any separate backend/data-contract implementation prompt",
                "Command Atlas context-filter doctrine remains required",
                "docs 26/27/28/29 remain exclusion/classification-only through doc 30",
            ),
        )

    return tuple(failures)


def backend_data_contract_semantic_contract_matrix_failures(
    repo_root: Path = REPO_ROOT,
) -> tuple[str, ...]:
    failures: list[str] = []
    matrix_path = (
        repo_root
        / "docs"
        / "planning"
        / "launch_ladder"
        / "source_set_bridges"
        / "backend_data_contract_semantic_contract_matrix_20260505.md"
    )

    if not matrix_path.is_file():
        return (f"backend semantic contract matrix: missing {matrix_path}",)

    matrix_text = _read_text(matrix_path)
    matrix_normalized = normalize(matrix_text)

    _require_all(
        failures,
        matrix_normalized,
        "backend semantic contract matrix required gates",
        (
            "Backend Data Contract Semantic Contract Matrix",
            "Conceptual Field Bundles",
            "Semantic Entity Matrix",
            "Allowed State Vocabulary",
            "confirmed",
            "inferred",
            "excluded",
            "unknown",
            "Authority And Sensitivity Boundaries",
            "evidence/freshness/provenance",
            "Source Category Matrix",
            "Future Implementation Handoff Requirements",
            "Bounce-Rule Classification",
            "does not implement backend/API/schema/SQLite/ingestion/fixtures/runtime/app code",
        ),
    )
    _require_all(
        failures,
        matrix_normalized,
        "backend semantic contract matrix field bundles",
        BACKEND_DATA_CONTRACT_FIELD_BUNDLES,
    )

    return tuple(failures)


def backend_data_contract_implementation_readiness_checklist_failures(
    repo_root: Path = REPO_ROOT,
) -> tuple[str, ...]:
    failures: list[str] = []
    checklist_path = (
        repo_root
        / "docs"
        / "planning"
        / "launch_ladder"
        / "source_set_bridges"
        / "backend_data_contract_implementation_readiness_checklist_20260505.md"
    )

    if not checklist_path.is_file():
        return (f"backend implementation-readiness checklist: missing {checklist_path}",)

    checklist_text = _read_text(checklist_path)
    checklist_normalized = normalize(checklist_text)

    _require_all(
        failures,
        checklist_normalized,
        "backend implementation-readiness checklist required gates",
        (
            "Backend Data Contract Implementation-Readiness Checklist",
            "Durable Bounce Rule",
            "The comparison must classify the new idea as one of",
            "A future backend/data-contract implementation prompt may be drafted only after every gate",
            "separate prompt explicitly authorizes implementation scope",
            "Source-set 04 bridge",
            "Context-filter receipt",
            "Sensitivity/private-data",
            "26/27/28/29 handling",
        ),
    )
    _require_all(
        failures,
        checklist_normalized,
        "backend implementation-readiness checklist classifications",
        BACKEND_DATA_CONTRACT_BOUNCE_CLASSIFICATIONS,
    )

    return tuple(failures)


def backend_data_contract_module_failures(
    repo_root: Path = REPO_ROOT,
) -> tuple[str, ...]:
    failures: list[str] = []
    module_path = repo_root / "backend_data_contract.py"
    test_path = repo_root / "tests" / "test_backend_data_contract.py"

    if not module_path.is_file():
        return (f"backend data contract module: missing {module_path}",)

    module_text = _read_text(module_path)
    module_normalized = normalize(module_text)
    _require_all(
        failures,
        module_normalized,
        "backend data contract module required vocabulary",
        BACKEND_DATA_CONTRACT_MODULE_REQUIRED_TERMS,
    )

    for forbidden_import in BACKEND_DATA_CONTRACT_FORBIDDEN_MODULE_IMPORTS:
        if forbidden_import in module_text.lower():
            failures.append(
                "backend data contract module: forbidden implementation import or entry "
                f"{forbidden_import!r}"
            )

    if not test_path.is_file():
        failures.append(f"backend data contract module tests: missing {test_path}")
    else:
        test_text = _read_text(test_path)
        _require_all(
            failures,
            normalize(test_text),
            "backend data contract module tests required coverage",
            BACKEND_DATA_CONTRACT_TEST_REQUIRED_TERMS,
        )

    return tuple(failures)


def storage_and_source_registry_readiness_plan_failures(
    repo_root: Path = REPO_ROOT,
) -> tuple[str, ...]:
    failures: list[str] = []
    plan_path = (
        repo_root
        / "docs"
        / "planning"
        / "launch_ladder"
        / "19_STORAGE_AND_SOURCE_REGISTRY_READINESS_PLAN.md"
    )

    if not plan_path.is_file():
        return (f"storage and source registry readiness plan: missing {plan_path}",)

    plan_text = _read_text(plan_path)
    plan_normalized = normalize(plan_text)

    _require_all(
        failures,
        plan_normalized,
        "storage and source registry required elements",
        (
            "inventory before extraction",
            "backup before movement",
            "sensitive/local-only before model access",
            "source registry before sqlite ingestion",
            "operator approval before cleanup",
            "no cloud model access to sensitive data by default",
            "pc c: 246g total, 244g used",
            "c:/openclawlegalprivate",
            "taxes/cpa paths",
            "pip cache",
            "npm cache",
            "gemini tmp",
            "openclaw backup",
            "windows downloads",
            "chrome cache",
        ),
    )

    forbidden_authorizing_phrases = (
        "Do move",
        "Do delete",
        "Do rename",
        "Do install",
        "Do update",
        "Do sync",
        "Do ingest",
        "Do scan contents",
        "Do restructure",
    )
    for phrase in forbidden_authorizing_phrases:
        if phrase in plan_text:
            failures.append(
                "storage and source registry plan: forbidden authorizing phrase "
                f"{phrase!r}"
            )

    return tuple(failures)


def pc_storage_relief_launch_packet_plan_failures(
    repo_root: Path = REPO_ROOT,
) -> tuple[str, ...]:
    failures: list[str] = []
    plan_path = (
        repo_root
        / "docs"
        / "planning"
        / "launch_ladder"
        / "20_PC_STORAGE_RELIEF_LAUNCH_PACKET_PLAN.md"
    )

    if not plan_path.is_file():
        return (f"pc storage relief launch packet plan: missing {plan_path}",)

    plan_text = _read_text(plan_path)
    plan_normalized = normalize(plan_text)

    required_sections = (
        "Purpose",
        "Current Evidence",
        "Risk Posture",
        "No-Touch Zones",
        "Phase 0: Backup/Verification Before Any Change",
        "Phase 1: Low-Risk Immediate Relief Packet",
        "Phase 2: WSL Export/Import Relocation Packet",
        "Phase 3: .wslconfig Memory Policy",
        "Phase 4: External 2TB Bridge Drive Triage",
        "Phase 5: Sensitive Data Relocation Later",
        "Verification Checklist",
        "Operator Approval Gates",
        "Failure/Rollback Plan",
        "Recommended Next Move",
    )
    _require_all(
        failures,
        plan_normalized,
        "pc storage relief required sections",
        required_sections,
    )

    _require_all(
        failures,
        plan_normalized,
        "pc storage relief current evidence",
        (
            "PC C: is critically full: 246G total, 244G used, about 2.5G available, 99% full",
            "PC D: has 229G total, 103G used, and 127G available",
            "PC E: has 932G total, 521G used, and 412G available",
            "WSL root reports 1007G total, 190G used, and 767G available",
            "WSL VHD on C: appears to be the largest C: pressure source, roughly 190GB",
            "Intel i7-6700",
            "memory=28GB",
            "swap=8GB",
            "processors=8",
            "memory=24GB",
        ),
    )

    _require_all(
        failures,
        plan_normalized,
        "pc storage relief risk posture",
        (
            "C: at 99% is a system stability risk",
            "WSL VHD relocation is likely the largest relief path",
            "highest-risk operation",
            "Cache cleanup is lower risk and should come before WSL export/import",
            "Windows 11 upgrade should not be attempted during the storage crisis",
            "Windows 11 official support is unlikely on the i7-6700",
            "bypass upgrade is a separate future risk review",
        ),
    )

    _require_all(
        failures,
        plan_normalized,
        "pc storage relief no-touch zones",
        (
            "tax/CPA/legal/client/private data",
            "C:\\OpenClawLegalPrivate",
            "Mac drives and Mac external drives",
            "8TB BU",
            "Orange/Green",
            "2TB external drive contents until triaged",
            "cloud drives",
            "secrets/vaults/logs/runtime state",
            "OpenClaw runtime mutation surfaces",
        ),
    )

    _require_all(
        failures,
        plan_normalized,
        "pc storage relief plan-only approval boundaries",
        (
            "not execution authority",
            "not executed in this slice",
            "requires explicit operator approval before execution",
            "Plan commands only",
            "wsl --export",
            "wsl --import",
            "Windows Terminal/PowerShell, not inside WSL",
            "Do not unregister the original distro until the imported distro is verified",
            "final cleanup of the old distro/VHD happens only after explicit approval",
            "E: destination should not be compressed or encrypted",
            "account for low C: space and possible temp usage",
        ),
    )

    _require_all(
        failures,
        plan_normalized,
        "pc storage relief cleanup packet",
        (
            "python3 -m pip cache purge",
            "npm cache clean --force",
            "optional Gemini tmp cleanup",
            "Windows Downloads should be handled by manual review only",
            "Chrome cache should be cleared through browser settings",
            "df -h /",
            "Get-PSDrive -PSProvider FileSystem",
        ),
    )

    _require_all(
        failures,
        plan_normalized,
        "pc storage relief bridge drive and sensitive boundary",
        (
            "2TB bridge drive triage",
            "inventory remaining data by path/size only",
            "Do not open sensitive contents",
            "copy and verify preserved data before deletion is considered",
            "Reformat only after explicit operator approval",
            "exFAT",
            "protected local-only storage boundaries",
            "Local models only by default",
            "Cloud models may only receive sanitized/tokenized data",
            "future separate high-security design lane",
        ),
    )

    _require_all(
        failures,
        plan_normalized,
        "pc storage relief approval gates",
        (
            "approve cache cleanup",
            "approve WSL export",
            "approve WSL import",
            "approve default distro switch",
            "approve old distro removal",
            "approve 2TB drive triage",
            "approve 2TB reformat",
            "approve sensitive data relocation",
        ),
    )

    forbidden_authorizing_phrases = (
        "This plan is execution authority",
        "Execute cleanup now",
        "Delete files now",
        "Move files now",
        "Export WSL now",
        "Import WSL now",
        "Unregister WSL now",
        "Reformat drives now",
        "Clean caches now",
        "Install software now",
        "Update software now",
        "Inspect private file contents now",
        "Inspect tax/CPA/legal/client/private documents now",
        "Call providers/models now",
        "Mutate runtime now",
        "Generate source-set 05 now",
        "Create source-set folder 05 now",
    )
    for phrase in forbidden_authorizing_phrases:
        if phrase in plan_text:
            failures.append(
                "pc storage relief launch packet plan: forbidden authorizing phrase "
                f"{phrase!r}"
            )

    return tuple(failures)


def knowledge_substrate_package_failures(repo_root: Path = REPO_ROOT) -> tuple[str, ...]:
    failures: list[str] = []
    package_dir = repo_root / "docs" / "planning" / "launch_ladder" / "knowledge_substrate"
    texts: list[str] = []

    for filename in REQUIRED_KNOWLEDGE_SUBSTRATE_DOCS:
        path = package_dir / filename
        if not path.is_file():
            failures.append(f"knowledge substrate package: missing {path}")
            continue
        texts.append(_read_text(path))

    if not texts:
        return tuple(failures)

    text = "\n\n".join(texts)
    normalized_text = normalize(text)

    _require_all(
        failures,
        normalized_text,
        "knowledge substrate doctrine",
        (
            "Compiled Knowledge Substrate",
            "SQLite stores the memory; markdown speaks it; HTML preserves shape; FTS finds it; compiled notes make it useful",
            "not vanilla RAG",
            "not classic flat chunk-vector RAG",
            "compile-first knowledge substrate",
            "Karpathy-style LLM Wiki thinking",
            "retrieval finds candidates",
            "compilation creates durable inspectable knowledge",
            "SQLite should be treated as the canonical local memory substrate",
            "Markdown is an export and handoff surface, not the database authority",
            "HTML or rich fragments preserve source shape where structure matters",
            "FTS5/search finds relevant records quickly",
            "Compiled notes make recurring knowledge useful",
            "Operator promotions determine what is accepted, rejected, marked historical, marked sensitive, or excluded",
            "Raw files are evidence, not truth",
            "Extracted text is parsed evidence, not truth",
            "Compiled notes are interpretation, not truth",
            "Claims are evidence-backed and confidence-bounded, not truth by default",
            "Unknown means unknown",
        ),
    )

    _require_all(
        failures,
        normalized_text,
        "knowledge substrate sqlite layers",
        KNOWLEDGE_SUBSTRATE_TABLES,
    )

    _require_all(
        failures,
        normalized_text,
        "knowledge substrate sensitivity levels",
        KNOWLEDGE_SUBSTRATE_SENSITIVITY_LEVELS
        + (
            "Unknown defaults restricted",
            "Sensitive content is local-only by default",
            "No external model access to raw/extracted sensitive content unless sanitized through a future explicit approval path",
            "Secrets/credentials must never be summarized into prompts",
            "client names, contracts, payments, tax details, publishing splits, private correspondence, or operational history",
        ),
    )

    _require_all(
        failures,
        normalized_text,
        "knowledge substrate app cards and states",
        KNOWLEDGE_SUBSTRATE_APP_CARDS
        + KNOWLEDGE_SUBSTRATE_UI_STATES
        + (
            "The app displays evidence-backed state",
            "must not imply hidden ingestion, hidden analysis, approval, execution, or truth",
        ),
    )

    _require_all(
        failures,
        normalized_text,
        "knowledge substrate fixture plan",
        KNOWLEDGE_SUBSTRATE_FIXTURE_NAMES
        + (
            "Fixtures are synthetic only",
            "Do not ingest real files",
            "Do not scan user directories",
            "Do not inspect private/vault/legal/business files",
        ),
    )

    _require_all(
        failures,
        normalized_text,
        "knowledge substrate no-implementation boundary",
        (
            "does not authorize ingestion",
            "No real business-file scanning",
            "No external model access to raw or extracted sensitive content",
            "No app or backend runtime implementation",
            "Do not create migrations, SQL DDL, ingestion scripts, fixture loaders, API routes, or app storage code",
            "no commands scan user directories",
            "no private/vault/legal/business files are inspected",
        ),
    )

    return tuple(failures)


def freshness_warnings(corpus: ContractCorpus) -> tuple[str, ...]:
    warnings: list[str] = []
    launch_text = corpus.launch_ladder_text
    internal_commits = sorted(
        set(re.findall(r"Source commit at creation:\s*`([^`]+)`", launch_text))
    )
    package_markers = sorted(
        set(re.findall(r"Package commit:\s*`([^`]+)`", launch_text))
    )
    older_internal_commits = [
        commit for commit in internal_commits if commit != UPLOAD_AUTHORITY_COMMIT
    ]
    stale_markers = older_internal_commits + [
        marker for marker in package_markers if marker == "TBD_AFTER_COMMIT"
    ]
    if stale_markers:
        warnings.append(
            "Freshness normalization TODO: "
            f"the generated MANIFEST.md for {ACTIVE_SOURCE_SET} is "
            f"upload authority and reports source commit {UPLOAD_AUTHORITY_COMMIT}; "
            "canonical Launch Ladder docs still contain package-level freshness "
            f"markers: {', '.join(stale_markers)}. Treat the manifest as source-set "
            "authority and the doc markers as package-level review metadata until "
            "a docs-only freshness normalization pass updates them."
        )

    return tuple(warnings)


def check_contract(corpus: ContractCorpus | None = None) -> StaticContractReport:
    corpus = corpus or load_corpus()
    launch = normalize(corpus.launch_ladder_text)
    combined = normalize(corpus.combined_text)
    validation_map = normalize(corpus.validation_map_text)
    scripts = normalize(corpus.script_text)
    failures: list[str] = []

    _require_all(
        failures,
        launch,
        "launch authorization separation",
        ("launch-ready is not launch-authorized",),
    )

    _require_all(
        failures,
        launch,
        "seven ladder stages",
        (
            "recommendation",
            "planned slice",
            "source set ready",
            "build ready",
            "validation ready",
            "launch ready",
            "launch authorized",
        ),
    )

    _require_all(
        failures,
        launch,
        "route compression fields",
        (
            "Direct Route",
            "Balanced Route",
            "System Route",
            "steps_to_launch",
            "estimated_true_steps",
            "includes",
            "defers",
            "risk",
            "confidence",
            "freshness",
        ),
    )

    _require_all(
        failures,
        launch,
        "ladder compact button fields",
        (
            "label",
            "resulting_step_count",
            "estimated_true_steps",
            "deferred_work_summary",
            "authority_required",
            "stop_condition",
            "evidence_output",
        ),
    )

    _require_all(
        failures,
        launch,
        "parallel step bundle requirements",
        (
            "Parallel Step Bundles",
            "independent lanes",
            "File/workspace collision matrix",
            "Validation commands per lane",
            "Commit boundaries per lane",
            "Stop conditions per lane",
        ),
    )

    _require_all(
        failures,
        launch,
        "view modes",
        ("Bird's Eye", "Route View", "Step View"),
    )

    _require_all(
        failures,
        launch,
        "evidence and freshness fields",
        (
            "source basis",
            "generated/reviewed",
            "source commit",
            "stale conditions",
            "refresh trigger",
        ),
    )

    _require_all(
        failures,
        launch,
        "source-set manifest authority",
        (
            "canonical Launch Ladder docs may contain package-level review/freshness fields",
            "MANIFEST.md is the upload authority",
            "use MANIFEST.md for the uploaded source set",
            "Do not hardcode fast-changing source-set commits across canonical docs",
        ),
    )

    _require_all(
        failures,
        launch,
        "source-set upload rule",
        ("23 content files + MANIFEST.md = 24 total upload files",),
    )

    _require_all(
        failures,
        launch,
        "source-set ladder and delta bridge",
        (
            "Source-Set Ladder",
            "01_CURRENT_PRODUCT_SPEC",
            "02_MAC_IOS_APP_BUILD",
            MAC_APP_KNOWLEDGE_SOURCE_SET,
            "future backend/data-model source set",
            UPLOAD_AUTHORITY_COMMIT,
            "source-set folders are not Launch Ladder steps",
            "When folder 01 is exhausted, move to folder 02",
            "When folder 02 is exhausted, move to folder 03",
            "By folder 03, the system should already propose what folder 04 should contain",
            "CHAT_STAY_UP_TO_DATE.md",
            "not counted in the 24 files",
            "bridge-only upload",
            "full 24-file refresh",
            "current source-set folder",
            "latest repo changes since upload",
            "next likely source-set folder",
            "openclaw_audit_build_readiness",
            "law_program",
            "later lanes",
            "prototype wording only",
        ),
    )

    _require_all(
        failures,
        launch,
        "workspace launch profiles",
        (
            "Workspace Launch Profile",
            "named, evidence-backed view/navigation route",
            "opens the right machine, folder, workspace, files, tabs, and optional prompt only",
            "does not imply permission to mutate repo/runtime state",
            "Opening VS Code/workspace/files is safe navigation",
            "Any execution must be a separate Launch Packet / Launch Ladder action",
            "profile_id",
            "display_name",
            "purpose",
            "owner_lane or domain",
            "target_machine or context",
            "target_root or path",
            "workspace_file or workspace_hint",
            "recommended_files or tabs",
            "optional_prompt_path or prompt_hint",
            "evidence_sources",
            "freshness_fields",
            "allowed_navigation_actions",
            "explicitly_forbidden_execution_actions",
            "required_next_launch_packet_for_execution",
            "tests, sync, commits, service commands, provider/model calls, app execution, runtime mutation, private-data inspection, secrets, logs, vault access, Gmail/Telegram behavior, Hermes runtime expansion, LegalPrivate work, or installed-unit checks",
            "pc_wsl_repo_view",
            "mac_upload_prep_view",
            "mac_desktop_app_planning_view",
            "legal_visual_polish_view",
            "audit_runtime_review_view",
            "hermes_advisory_packet_view",
        ),
    )

    _require_all(
        failures,
        launch,
        "workspace profile to launch packet handoff",
        (
            "Workspace Profile To Launch Packet Handoff",
            "profile-to-packet handoff is explicit and one-way",
            "Workspace Launch Profile opens context only",
            "The profile may point to required_next_launch_packet_for_execution",
            "Launch Packet authorizes a bounded next action",
            "evidence/freshness, operator-readable scope, validation, authority, and stop conditions",
            "Workspace Launch Profile must not contain executable commands",
            "silently authorize them",
            "tests, sync, commit, service command, provider/model call, runtime mutation, app execution, private-data inspection, launcher action",
            "handoff_reason",
            "handoff_evidence_sources",
            "handoff_freshness_fields",
            "handoff_operator_readable_scope",
            "operator_harness_refresh_packet",
            "executable_commands",
            "reason_invalid",
            "A Workspace Launch Profile with executable commands is invalid",
        ),
    )

    _require_all(
        failures,
        launch,
        "launch packet minimum fields",
        (
            "A Launch Packet is the separate execution-authorizing object for one bounded next action",
            "Opening a Workspace Launch Profile never creates, approves, or executes a Launch Packet",
            "packet_id",
            "source_profile_id",
            "bounded_next_action",
            "target_machine",
            "target_workspace",
            "operator_readable_scope",
            "execution_commands or execution_plan",
            "validation_commands",
            "withheld_surfaces",
            "approval_receipt_or_operator_decision",
            "The packet authorizes only the named bounded next action",
        ),
    )

    _require_all(
        failures,
        launch,
        "approval receipt primitive",
        (
            "Action Authorization / Approval Receipt",
            "Launch Packet exists does not equal approved",
            "Approval Receipt records explicit operator authorization",
            "Approval Receipt binds to one Launch Packet/action/scope",
            "visible evidence/freshness state at approval time",
            "expiry/replay rules",
            "consumed_state",
            "permitted",
            "executed",
            "succeeded",
            "failed",
            "expired",
            "revoked",
            "operator-readable",
            "must not broaden the Launch Packet scope",
            "receipt_id",
            "launch_packet_id",
            "approved_by_operator",
            "approved_at",
            "approved_scope",
            "evidence_snapshot",
            "freshness_snapshot",
            "expiry",
            "replay_policy",
            "execution_result_reference",
            "revocation_state",
            "forbidden_scope_expansion",
            "invalid_broadened_receipt",
            "Approval Receipt cannot broaden the Launch Packet scope",
        ),
    )

    _require_all(
        failures,
        launch,
        "ui state claim rules",
        (
            "UI State Claim Rules",
            "Profile available does not mean packet available",
            "Packet available does not mean approved",
            "Approved does not mean executed",
            "Executed does not mean succeeded",
            "Current/fresh requires evidence/freshness proof",
            "Synced/tested/healthy/running cannot be shown unless backed by explicit evidence",
            "configured vs observed",
            "requested vs approved",
            "approved vs executed",
            "executed vs succeeded",
            "current vs stale",
            "Convenience must not collapse navigation, approval, and execution into one hidden action",
            "Opening a Workspace Launch Profile must not auto-approve, auto-run, or auto-consume a Launch Packet",
            "invalid_tests_passed_without_evidence",
            "UI state claim says tests passed without evidence",
            "invalid_profile_open_auto_approves_and_runs",
            "silently approves/runs a packet",
        ),
    )

    _require_all(
        failures,
        launch,
        "product taste operator experience eval spine",
        (
            "Product Taste / Operator Experience Eval Spine",
            "Taste is not decorative polish",
            "operator trust, calm control, clear authority hierarchy, legible evidence, sparse high-confidence actions, and zero fake intelligence",
            "operator can orient within a few seconds",
            "authority boundaries are visually obvious",
            "highest-risk actions cannot be confused with navigation",
            "status copy is exact and evidence-backed",
            "calm, sparse, premium, and controlled",
            "F-22 cockpit discipline",
            "Bugatti material confidence",
            "SpaceX mission-control clarity",
            "high-end music studio ergonomics",
            "Apple-level restraint",
            "fake-futuristic AI slop",
            "generic SaaS admin dashboard",
            "vague chatbot panels",
            "Visual clutter",
            "Vague agent status",
            "Fake intelligence language",
            "Scary controls with unclear blast radius",
            "Hidden authority or hidden execution",
            "Dead generic admin-panel energy",
            "Unclear state hierarchy",
            "Chatbot slop",
            "Over-automation",
            "Evidence buried too deeply",
            "copy/state-language checks",
            "cockpit/instrument hierarchy checks",
            "action safety visibility checks",
            "density/calmness checks",
            "evidence visibility checks",
            "operator trust checks",
            "anti-slop checks",
            "accessibility/legibility checks",
            "golden_calm_mission_control_overview",
            "golden_navigation_only_workspace_card",
            "golden_bounded_packet_card",
            "golden_approval_receipt_card",
            "golden_stale_evidence_warning",
            "golden_blocked_action_with_clear_reason",
            "golden_ready_but_not_approved_action",
            "golden_fresh_evidence_backed_status",
            "invalid_chatbot_i_handled_it_state",
            "invalid_glowing_ai_brain_panel",
            "invalid_one_click_hides_approval",
            "invalid_tests_passed_without_evidence",
            "invalid_healthy_running_without_observation",
            "invalid_dense_admin_table_no_next_action",
            "invalid_profile_card_matches_execution_action",
            "invalid_fake_urgency_or_confidence",
            "app planning source set must preserve this eval spine before implementation",
        ),
    )

    _require_all(
        failures,
        launch,
        "mac desktop mission control fixture contract",
        (
            "Mac Desktop Mission Control Fixture Contract",
            "docs/planning/launch_ladder/fixtures/mission_control",
            "fixture_fresh_navigation_profile.json",
            "fixture_malformed_executable_profile.json",
            "fixture_packet_available_not_approved.json",
            "fixture_approval_receipt_valid.json",
            "fixture_approval_receipt_expired.json",
            "fixture_stale_evidence_route.json",
            "fixture_blocked_missing_authority.json",
            "fixture_ui_claim_without_evidence.json",
            "fixture_operator_experience_golden_overview.json",
            "profile_available",
            "packet_available",
            "launch_ready",
            "approved",
            "executed",
            "succeeded",
            "stale",
            "blocked",
            "unknown",
            "navigation context exists only",
            "bounded action object exists for review only",
            "Approval Receipt permits one named packet/action/scope only",
            "execution result plus validation evidence",
            "do not soften this into confidence",
            "must not collapse profile, packet, approval, execution, and result",
            "Product Taste / Operator Experience Evals must reject AI slop",
            "All nine required fixture files exist and parse as JSON",
            "Workspace Launch Profiles with executable command fields are invalid",
            "Expired receipts cannot authorize execution",
            "healthy, current, tested, running, or synced without evidence are invalid",
        ),
    )

    _require_all(
        failures,
        launch,
        "current source-set posture",
        (
            "active app-planning posture is 03_MAC_APP_KNOWLEDGE_SUBSTRATE",
            "read-only Mac desktop Mission Control fixture contract stays in 02_MAC_IOS_APP_BUILD",
            MAC_APP_KNOWLEDGE_SOURCE_SET,
            "The 04_BACKEND_DATA_CONTRACT_READINESS source set is the next generated ChatGPT Project planning packet",
            "It is not backend/schema implementation",
            "does not create source-set folder 05",
            "does not create app/backend/runtime implementation",
            "does not authorize ingestion",
        ),
    )

    _require_all(
        failures,
        launch,
        "apple platform clarification",
        (
            "Mac/iOS is Apple-platform planning shorthand",
            "Mac desktop app first",
            "iOS companion later",
            "Do not read this brief as iOS-first implementation",
        ),
    )

    _require_all(
        failures,
        launch,
        "prototype bridge retirement",
        (
            "real bridge is this repo-side template",
            "~/OpenClaw_Watch/operator_harness_readiness/CHAT_STAY_UP_TO_DATE.md",
            "/Users/hwinshipwheatley/OpenClaw_Watch/.claude/Chat_Stay Up To Date.md",
            "prototype/example only",
            "not canonical",
            "explicit Mac cleanup step",
            "deletes it or clearly archives it",
            "Do not delete that prototype from this docs/test slice",
        ),
    )

    _require_all(
        failures,
        scripts,
        "operator harness bridge scripts",
        (
            "CHAT_STAY_UP_TO_DATE.md",
            "DELTA_BRIDGE_NAME",
            "adjacent_to_ingest=true",
            "counted_in_24=false",
            "CONTENT_FILES_PER_FOLDER=23",
            "EXPECTED_FILES_PER_FOLDER=24",
        ),
    )

    _require_any(
        failures,
        launch,
        "console/atlas non-authority warning",
        (
            "console/atlas is a window/router/evidence browser, not authority",
            "windows routers and evidence browsers",
        ),
    )

    _require_all(
        failures,
        combined,
        "non-authority and v1 safety warnings",
        (
            "operator remains authority",
            "Guardian may approve/deny",
            "must not handle secrets",
            "No service/runtime mutation in v1",
            "No private/legal/vault/log inspection in v1",
            "No provider/model calls in v1",
        ),
    )

    _require_all(
        failures,
        launch,
        "Multi-OpenClaw Command Atlas horizon",
        ("Multi-OpenClaw Command Atlas", "long-range product horizon"),
    )

    _require_all(
        failures,
        launch,
        "atlas zoom levels",
        (
            "all builds deployments",
            "one build deployment",
            "departments",
            "agents systems subsystems modules",
            "launch goals",
            "launch ladders",
            "steps",
            "evidence artifacts",
            "docs code prompts validation",
        ),
    )

    _require_all(
        failures,
        launch,
        "operator-facing unit of work",
        ("Launch Ladders replace vague lanes",),
    )

    _require_all(
        failures,
        launch,
        "v1 docs/spec-only boundary",
        ("docs/spec only in v1", "does not create generated folders or scripts"),
    )

    _require_all(
        failures,
        validation_map,
        "validation map entry",
        (
            "launch_ladder_contract_check.py",
            "test_launch_ladder_static_contract.py",
            "fixtures mission control",
            "knowledge_substrate",
            "first screen composition",
            "taste atmosphere",
            "quiet feedback",
            "03_MAC_APP_KNOWLEDGE_SUBSTRATE",
            "17_BACKEND_DATA_CONTRACT_READINESS_PLAN.md",
            BACKEND_DATA_CONTRACT_SOURCE_SET,
            "backend data-contract record topics",
            "backend data-contract shape plan conceptual records and relationship rules",
            "backend semantic contract matrix",
            "backend implementation-readiness checklist",
            "backend first implementation slice readiness",
            "backend_data_contract.py",
            "test_backend_data_contract.py",
            "backend data-contract semantic vocabulary and guard helpers",
            "field-bundle validator",
            "entity-family validator",
            "source-set 04 context-filter freshness bridge",
            "doc 30 exclusion/classification-only handling",
            "20_PC_STORAGE_RELIEF_LAUNCH_PACKET_PLAN.md",
            "PC storage relief launch-packet plan",
        ),
    )

    failures.extend(mission_control_fixture_failures())
    failures.extend(first_screen_composition_failures())
    failures.extend(taste_and_quiet_feedback_failures())
    failures.extend(mac_app_knowledge_source_set_failures())
    failures.extend(backend_data_contract_readiness_plan_failures())
    failures.extend(backend_data_contract_shape_plan_failures())
    failures.extend(backend_data_contract_first_implementation_slice_readiness_failures())
    failures.extend(backend_data_contract_semantic_contract_matrix_failures())
    failures.extend(backend_data_contract_implementation_readiness_checklist_failures())
    failures.extend(backend_data_contract_module_failures())
    failures.extend(storage_and_source_registry_readiness_plan_failures())
    failures.extend(pc_storage_relief_launch_packet_plan_failures())
    failures.extend(knowledge_substrate_package_failures())

    return StaticContractReport(
        failures=tuple(failures),
        warnings=freshness_warnings(corpus),
    )


def main() -> int:
    report = check_contract()
    for warning in report.warnings:
        print(f"WARNING: {warning}")
    if report.failures:
        for failure in report.failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    print("Launch Ladder static contract: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
