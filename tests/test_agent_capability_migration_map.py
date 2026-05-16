import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "generated" / "read_models" / "agent_capability_migration_map.json"
MARKDOWN_PATH = ROOT / "docs" / "operations" / "AGENT_CAPABILITY_MIGRATION_MAP_V0.md"
DOCTRINE_PATH = ROOT / "docs" / "operations" / "OPENCLAW_APPROVED_MODULE_AND_CLIENT_BUNDLE_DOCTRINE_V0.md"
SPEC_PATH = ROOT / "docs" / "operations" / "NEXT_AGENT_MIGRATION_IMPLEMENTATION_SPEC_V0.md"
READY_PACKET_PATH = ROOT / "docs" / "operations" / "STAGE_2_READY_PACKET.json"

CONTROLLED_MIGRATION_TYPES = {
    "already_covered",
    "port_logic_only",
    "wrap_as_dumb_intake",
    "superseded",
    "block_no_go",
    "defer",
    "operator_review_required",
}

REQUIRED_RECORD_KEYS = {
    "id",
    "agent_or_system",
    "legacy_surface",
    "capability",
    "migration_type",
    "new_home",
    "risk_level",
    "value_level",
    "reusable_module_candidate",
    "client_safe_candidate",
    "requires_guardian",
    "requires_operator_decision",
    "blocked_reason",
}


def _load_map():
    return json.loads(MAP_PATH.read_text(encoding="utf-8"))


def test_machine_map_uses_controlled_vocabulary_and_no_authority():
    payload = _load_map()

    assert payload["schema_version"] == "agent_capability_migration_map_v0"
    assert payload["created_by"] == "codex"
    assert payload["runtime_authority"] is False
    assert payload["repo_b_execution_allowed"] is False
    assert payload["client_bundle_generation_allowed"] is False
    assert set(payload["controlled_migration_types"]) == CONTROLLED_MIGRATION_TYPES
    assert payload["records"]

    for record in payload["records"]:
        assert REQUIRED_RECORD_KEYS <= set(record)
        assert record["migration_type"] in CONTROLLED_MIGRATION_TYPES
        assert isinstance(record["reusable_module_candidate"], bool)
        assert isinstance(record["client_safe_candidate"], bool)
        assert isinstance(record["requires_guardian"], bool)
        assert isinstance(record["requires_operator_decision"], bool)


def test_blocked_legacy_runtime_surfaces_stay_blocked():
    payload = _load_map()
    by_id = {record["id"]: record for record in payload["records"]}

    for record_id in {
        "chief_daemon_workers",
        "chief_direct_sender",
        "cassandra_watchers",
        "planner_builder_watchdogs",
        "planner_polish_orchestrator",
    }:
        record = by_id[record_id]
        assert record["migration_type"] in {"block_no_go", "superseded"}
        assert record["blocked_reason"]
        assert record["requires_guardian"] is True


def test_stage_1_docs_include_required_boundaries_and_spine():
    markdown = MARKDOWN_PATH.read_text(encoding="utf-8")
    doctrine = DOCTRINE_PATH.read_text(encoding="utf-8")
    spec = SPEC_PATH.read_text(encoding="utf-8")

    for text in (markdown, doctrine, spec):
        assert "OpenClaw Core" in text
        assert "runtime_authority=false" in text

    for required in (
        "no Repo B execution",
        "no daemon/watchdog resurrection",
        "no raw shell/eval",
        "no direct Telegram send",
        "no SMTP send",
        "no raw client/private data export",
        "no ad hoc CSV/log state as authority",
        "no unapproved web/API/model execution",
        "no generated client repo creation in Stage 2",
    ):
        assert required in markdown

    assert "intake -> intent/action record -> Work Board / Agent Work Packet -> Guardian approval when needed -> receipt/read-model -> Mission Control" in markdown
    assert "Client systems may process their sensitive data locally" in doctrine
    assert "Mission Control shows module and bundle posture" in doctrine
    assert "module_registry.py" in spec
    assert "bundle_blueprint_planner.py" in spec
    assert "governed_intake_spine.py" in spec


def test_stage_2_readiness_packet_is_explicit_and_bounded():
    packet = json.loads(READY_PACKET_PATH.read_text(encoding="utf-8"))

    assert packet["schema_version"] == "stage_2_ready_packet_v0"
    assert packet["stage_2_ready"] is True
    assert packet["validation_passed"] is True
    assert packet["recommended_stage_2_lane"] == "Modular Capability Migration Substrate v0"
    assert packet["commit_hash"] is None or isinstance(packet["commit_hash"], str)

    must_not_do = set(packet["must_not_do"])
    for required in {
        "execute Repo B",
        "inspect secrets or env files",
        "send Telegram, SMTP, Gmail, Calendar, or portal messages",
        "call external APIs or models",
        "create client/customer repos",
        "deploy anything",
        "activate daemons, watchdogs, listeners, or runtime services",
        "add arbitrary command execution",
        "bypass Guardian or operator approval",
        "modify Mission Control",
        "touch polish_loop/tasks",
    }:
        assert required in must_not_do
