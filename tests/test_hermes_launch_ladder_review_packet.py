import json
from pathlib import Path

import hermes_advisory_packet as contract
from hermes_advisory_packet import (
    HERMES_OUTPUT_KIND,
    NON_CANONICAL_NOTICE,
    check_hermes_advisory_memo,
    check_hermes_advisory_packet,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
PACKET_PATH = FIXTURES / "hermes_launch_ladder_review_packet.json"
MEMO_SHAPE_PATH = FIXTURES / "hermes_launch_ladder_review_expected_memo_shape.json"

EXPECTED_ALLOWED_READ_SURFACES = (
    "docs/operations/HERMES_ADVISORY_PACKET_CONTRACT.md",
    "docs/planning/HERMES_FIRST_ADVISORY_TRIAL_PLAN.md",
    "hermes_advisory_packet.py",
    "tests/test_hermes_advisory_packet_contract.py",
    "docs/planning/launch_ladder/LAUNCH_LADDER_INDEX.md",
    "docs/planning/launch_ladder/00_NORTH_STAR.md",
    "docs/planning/launch_ladder/01_RUNTIME_MAP.md",
    "docs/planning/launch_ladder/02_CAPABILITY_AUTHORITY_AND_READINESS.md",
    "docs/planning/launch_ladder/03_GOAL_HORIZONS.md",
    "docs/planning/launch_ladder/04_LAUNCH_LADDER_MODEL.md",
    "docs/planning/launch_ladder/05_EVIDENCE_AND_FRESHNESS.md",
    "docs/planning/launch_ladder/06_ROUTING_AND_WORKSPACES.md",
    "docs/planning/launch_ladder/07_SECURITY_AND_AUTHORITY.md",
    "docs/planning/launch_ladder/08_SOURCE_SET_REFRESH_SYSTEM.md",
    "docs/planning/launch_ladder/09_MAC_IOS_APP_BUILD_BRIEF.md",
    "docs/planning/launch_ladder/10_PRODUCTIZATION_PROFILES.md",
    "docs/planning/launch_ladder/11_NEXT_IMPLEMENTATION_SEQUENCE.md",
)

EXPECTED_REVIEW_FOCUS = {
    "slop_risk",
    "authority_drift",
    "missing_product_primitives",
    "stale_source_set_risk",
    "unclear_operator_control",
    "missing_evidence_freshness_model",
    "unsafe_launch_semantics",
    "local_first_operator_controlled_alignment",
    "personal_openclaw_and_future_client_deployment_support",
    "multi_openclaw_command_atlas_horizon",
    "launch_ladder_replaces_vague_lanes",
    "route_compression_and_compact_buttons",
    "parallel_step_bundles",
    "routing_workspace_model",
    "security_authority_boundary",
    "mac_ios_app_build_brief",
    "productization_profiles",
    "source_set_refresh_discipline",
}

FORBIDDEN_ALLOWED_SURFACE_FRAGMENTS = (
    "/home/openclaw",
    "sidecars/hermes_home",
    "runtime_state",
    "logs",
    "secret",
    "vault",
    "legal",
    "private matter",
    "gmail",
    "queue",
    "provider",
    ".mcp.json",
)


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _packet():
    return _load_json(PACKET_PATH)


def _memo_shape():
    return _load_json(MEMO_SHAPE_PATH)


def test_launch_ladder_packet_validates_under_contract():
    packet = _packet()

    assert check_hermes_advisory_packet(packet) == {"passed": True, "violations": [], "recommended_action": "pass"}
    assert packet["packet_id"] == "hermes-launch-ladder-review-001"
    assert packet["output_kind"] == HERMES_OUTPUT_KIND
    assert packet["authority_level"] == "advisory_only"


def test_expected_memo_shape_validates_under_contract():
    packet = _packet()
    memo_shape = _memo_shape()

    assert memo_shape["fixture_kind"] == "static_expected_shape_only_non_canonical_not_actual_hermes_memo"
    assert memo_shape["sample_status"] == "shape_fixture_only_not_a_hermes_result"
    assert memo_shape["non_canonical_notice"] == NON_CANONICAL_NOTICE
    assert any("Launch Ladder-specific planning/spec files are present" in item for item in memo_shape["assumptions"])
    assert check_hermes_advisory_memo(memo_shape, packet=packet) == {
        "passed": True,
        "violations": [],
        "recommended_action": "pass",
    }


def test_allowed_read_surfaces_are_explicit_bounded_and_existing():
    packet = _packet()
    allowed = tuple(packet["allowed_read_surfaces"])

    assert allowed == EXPECTED_ALLOWED_READ_SURFACES
    assert all(surface and surface not in {"/", ".", "*", "repo", "repository"} for surface in allowed)
    for surface in allowed:
        lowered = surface.lower()
        assert not any(fragment in lowered for fragment in FORBIDDEN_ALLOWED_SURFACE_FRAGMENTS)
        assert (ROOT / surface).is_file(), surface


def test_withheld_surfaces_cover_private_runtime_provider_and_service_boundaries():
    packet = _packet()
    memo_shape = _memo_shape()
    withheld = set(packet["withheld_surfaces"])
    withheld_text = "\n".join(sorted(withheld))

    assert set(contract.REQUIRED_WITHHELD_SURFACES).issubset(withheld)
    assert memo_shape["withheld_surfaces"] == packet["withheld_surfaces"]
    for marker in (
        "private",
        "logs",
        "legal",
        "vault",
        "runtime",
        "hermes_home",
        "provider",
        "model",
        "service",
    ):
        assert marker in withheld_text


def test_all_execution_and_authority_permissions_are_false():
    packet = _packet()
    memo_shape = _memo_shape()

    for field in contract.FALSE_PERMISSION_FIELDS:
        assert packet[field] is False
    assert packet["execution_allowed"] is False
    assert packet["canonical_write_allowed"] is False
    assert packet["queue_mutation_allowed"] is False
    assert packet["approval_authority_allowed"] is False
    assert packet["provider_fallback_allowed"] is False
    assert packet["live_service_inspection_allowed"] is False
    assert packet["private_data_allowed"] is False
    assert memo_shape["commands_executed"] is False
    assert memo_shape["decisions_made"] is False
    assert memo_shape["canonical_writes_made"] is False


def test_packet_is_later_trial_input_not_a_runtime_request():
    packet = _packet()

    assert packet["packet_kind"] == "first_hermes_advisory_trial_input_candidate"
    assert packet["trial_status"] == "prepared_not_run"
    assert packet["review_target"] == "Launch Ladder planning/spec work"
    assert packet["prepared_for_later_manual_hermes_trial"] is True
    assert packet["requires_operator_approval_before_run"] is True
    assert packet["not_an_execution_request"] is True
    assert packet["launch_ladder_source_files_present_at_packet_creation"] is True
    assert set(packet["review_focus"]) == EXPECTED_REVIEW_FOCUS
    assert any("docs/planning/launch_ladder" in note for note in packet["source_set_refresh_notes"])
    assert any("Refresh this packet" in note for note in packet["source_set_refresh_notes"])


def test_no_stale_missing_launch_ladder_source_language_remains():
    packet_text = PACKET_PATH.read_text(encoding="utf-8")
    memo_shape_text = MEMO_SHAPE_PATH.read_text(encoding="utf-8")
    combined_text = f"{packet_text}\n{memo_shape_text}"

    for stale_phrase in (
        "No docs/planning/launch_ladder directory was present when this packet was prepared.",
        "No non-Legal Launch Ladder planning/spec files were found by the bounded filename/text checks used for this preparation pass.",
        "If Launch Ladder-specific planning/spec files are added later, regenerate this packet before asking Hermes to review the lane.",
        "No Launch Ladder-specific planning/spec files were present in the bounded packet source set at fixture creation time.",
        "missing Launch Ladder-specific source files",
    ):
        assert stale_phrase not in combined_text


def test_review_questions_name_launch_ladder_risks_without_granting_authority():
    packet = _packet()
    question_text = "\n".join(packet["review_questions"]).lower()

    for expected_phrase in (
        "authority",
        "multi-openclaw command atlas",
        "vague lanes",
        "route compression",
        "compact buttons",
        "parallel step bundles",
        "product primitives",
        "source-set drift",
        "operator control",
        "evidence freshness",
        "routing/workspace model",
        "mac/ios app build brief",
        "productization profiles",
        "launch semantics",
        "provider execution",
        "live inspection",
        "service/timer changes",
        "queue mutation",
        "private-data access",
    ):
        assert expected_phrase in question_text
    assert check_hermes_advisory_packet(packet)["passed"] is True
