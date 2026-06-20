from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import openclaw_system_knowledge_registry as registry
from scripts.export_openclaw_system_knowledge_registry import main as export_main
from scripts.query_system_knowledge_registry import main as query_main


REQUIRED_COMPONENTS = {
    "cassandra",
    "chief",
    "guardian",
    "niles",
    "hermes",
    "watch_desk",
    "universal_intake",
    "context_switchboard",
    "guided_review_coach",
    "data_room_form_fill_lane",
    "model_work_package_router",
    "assignment_loop_contract",
    "worker_run_manager",
    "reference_data_hydration",
    "artifact_link_normalizer",
    "pc_mac_sync",
    "invoice_ledger_discovery",
    "voice_kokoro_caveat",
    "compose_gate_pipeline",
    "orbit_brain_map",
    "gig_intake_flow",
    "correspondence_agent_plan",
    "approval_gate_convergence",
    "the_spine",
    "maestro_protected_brain",
    "self_healing_polish_loop",
    "cross_agent_truth_propagation",
    "polish_loop_self_scaling",
    "sqlite_ledger_core",
    "backend_package_request_schema",
    "conversational_workflow_router_contract",
    "map_room_markdown_atlas",
    "system_knowledge_query",
}


def test_registry_has_required_tables_and_no_sqlite_prefixes() -> None:
    payload = registry.build_registry(Path.cwd())

    assert tuple(payload["required_tables"]) == registry.REQUIRED_TABLES
    assert set(payload["sqlite_contract"]["required_tables"]) == set(registry.REQUIRED_TABLES)
    assert not any(table.startswith("sqlite_") for table in registry.REQUIRED_TABLES)
    assert payload["sqlite_contract"]["explicit_sqlite_internal_tables_defined"] is False


def test_registry_includes_required_current_components() -> None:
    payload = registry.build_registry(Path.cwd())
    components = {component["component_id"]: component for component in payload["component_inventory"]}

    assert REQUIRED_COMPONENTS <= set(components)
    assert "unsafe_to_start" in components["hermes"]["authority_boundary"]
    assert "logical/spawned" in components["niles"]["summary"]
    assert "does not execute business logic" in components["guardian"]["authority_boundary"]
    assert "read-only" in components["system_knowledge_query"]["authority_boundary"]
    assert "seven-step deterministic front door" in components["the_spine"]["summary"]
    assert "cannot set send/money/action authority" in components["maestro_protected_brain"]["authority_boundary"]
    assert "only acceptance gates may mark work DONE" in components["self_healing_polish_loop"]["authority_boundary"]


def test_spine_steps_and_router_registry_are_queryable_contracts() -> None:
    payload = registry.build_registry(Path.cwd())
    steps = payload["spine_steps"]
    routers = {item["family_name"]: item for item in payload["router_registry"]}

    assert payload["spine"]["canonical_name"] == "The Spine"
    assert payload["coverage_assessment"]["spine_step_count"] == 7
    assert [step["step_number"] for step in steps] == [1, 2, 3, 4, 5, 6, 7]
    assert [step["step_name"] for step in steps] == [
        "Intake Front Door",
        "PII Gate",
        "Intent LM Gate",
        "SQLite Packet Maker",
        "Approval / Guardian Gate",
        "LM2 Responder / Executor",
        "Final Output Gate / Receipt",
    ]
    assert set(routers) == {
        "Chat",
        "FileMetadata",
        "EvidenceIntake",
        "WorkflowPackages",
        "LocalSurface",
        "OperatorEvents",
    }
    assert "Approval / Guardian Gate" in routers["Chat"]["next_safe_move"]
    assert routers["FileMetadata"]["authority_boundary"] == "Map Room lookup is read-only and cannot perform cleanup."
    assert "green-gate proof" in routers["LocalSurface"]["authority_boundary"]


def test_authority_boundary_blocks_live_and_sensitive_actions() -> None:
    payload = registry.build_registry(Path.cwd())
    boundary = payload["authority_boundary"]

    assert boundary["documentation_read_model_sqlite_only"] is True
    for key, value in boundary.items():
        if key != "documentation_read_model_sqlite_only":
            assert value is False, key


def test_known_unknowns_and_build_tasks_present() -> None:
    payload = registry.build_registry(Path.cwd())
    unknowns = {item["unknown_id"] for item in payload["known_unknowns"]}
    tasks = {item["task_id"] for item in payload["build_tasks"]}

    assert "unknown_missing_prior_commit" in unknowns
    assert "unknown_live_chatgpt55_adapter" in unknowns
    assert "unknown_external_repo_a" in unknowns
    assert "unknown_external_repo_b" in unknowns
    assert "unknown_mac_map_import_agent" in unknowns
    assert "unknown_confirmed_reference_data" in unknowns
    assert "unknown_registry_pr_source" in unknowns
    assert "task_verify_mac_patch_apply" in tasks
    assert "task_promote_confirmed_reference_data" in tasks
    assert "task_correspondence_watcher" in tasks
    assert "task_email_send_executor_scaffold" in tasks
    assert "task_land_reynolds_gig" in tasks
    assert "task_refresh_graphiffy_atlas" in tasks
    assert "task_wire_nervous_system" in tasks
    unknown_statuses = {item["unknown_id"]: item["unknown_status"] for item in payload["known_unknowns"]}
    assert unknown_statuses["unknown_graphiffy_atlas_staleness"] == "RESOLVED_PC17"


def test_orbit_brain_map_is_landed_as_structured_registry_records() -> None:
    payload = registry.build_registry(Path.cwd())
    brains = {item["brain_id"]: item for item in payload["brain_route_inventory"]}

    assert payload["coverage_assessment"]["brain_route_record_count"] == len(registry.ORBIT_BRAIN_ROUTE_RECORDS)
    assert brains["chief_invoice_brain"]["disposition_action"] == "RETIRE"
    assert brains["chief_watcher_brain"]["disposition_action"] == "VERIFY"
    assert brains["chief_billing_brain"]["disposition_action"] == "PARK_FOR_GATED_BILLING_FLOW"
    assert brains["chief_email_brain"]["compose_status"] == "g3_convergence_metadata_added"
    assert brains["read_only_orbit_brain_group"]["compose_status"] == "pc12_categories_added"
    assert "no executor registered" in brains["chief_email_brain"]["boundary"]


def test_orchestration_decisions_are_machine_readable_and_send_hold_safe() -> None:
    payload = registry.build_registry(Path.cwd())
    decisions = {item["decision_id"]: item for item in payload["orchestration_decisions"]}

    assert payload["coverage_assessment"]["orchestration_decision_count"] == len(registry.ORCHESTRATION_DECISIONS)
    assert decisions["decision_compose_front_door"]["status"] == "accepted"
    assert decisions["decision_send_hold_active"]["status"] == "active_boundary"
    assert "No external sends" in decisions["decision_send_hold_active"]["decision"]
    assert "No Square publish/send" in decisions["decision_square_payment_rail"]["boundary"]


def test_exporter_writes_artifacts_and_sqlite_tables(tmp_path: Path) -> None:
    assert export_main(["--repo-root", str(tmp_path), "--format", "paths"]) == 0
    paths = registry.generated_paths(tmp_path)

    for path in paths.values():
        assert path.exists(), path

    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    operator_markdown = paths["operator_markdown"].read_text(encoding="utf-8")
    schema_sql = paths["schema_sql"].read_text(encoding="utf-8")
    seed_sql = paths["seed_sql"].read_text(encoding="utf-8")

    assert payload["schema_version"] == registry.SCHEMA_VERSION
    assert payload["live_projection"]["source_mode"] == "read_only_ledger_and_atlas_metadata"
    assert "## Components" in operator_markdown
    assert "## The Spine" in operator_markdown
    assert "## Router Registry" in operator_markdown
    assert "## Known Unknowns" in operator_markdown
    assert "## Authority Boundaries" in operator_markdown
    assert "CREATE TABLE IF NOT EXISTS system_component" in schema_sql
    assert "CREATE TABLE IF NOT EXISTS spine_step" in schema_sql
    assert "CREATE TABLE IF NOT EXISTS router_family" in schema_sql
    assert "INSERT INTO system_component" in seed_sql
    assert "INSERT INTO spine_step" in seed_sql
    assert "INSERT INTO router_family" in seed_sql

    with sqlite3.connect(paths["sqlite"]) as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        }
        component_count = conn.execute("SELECT COUNT(*) FROM system_component").fetchone()[0]
        spine_steps = conn.execute(
            "SELECT step_number, step_name FROM spine_step ORDER BY step_number"
        ).fetchall()
        router_count = conn.execute("SELECT COUNT(*) FROM router_family").fetchone()[0]

    assert integrity == "ok"
    assert set(registry.REQUIRED_TABLES) <= tables
    assert not any(table.startswith("sqlite_") for table in tables if table in registry.REQUIRED_TABLES)
    assert component_count == len(payload["component_inventory"])
    assert [row[1] for row in spine_steps] == [step["step_name"] for step in registry.SPINE_STEPS]
    assert router_count == len(registry.ROUTER_FAMILIES)


def test_source_has_no_live_action_imports_or_calls() -> None:
    source_paths = [
        Path("openclaw_system_knowledge_registry.py"),
        Path("scripts/export_openclaw_system_knowledge_registry.py"),
    ]
    forbidden_fragments = (
        "import requests",
        "from requests",
        "subprocess",
        "webbrowser",
        "smtplib",
        "googleapiclient",
        "openai",
        "anthropic",
        "ollama",
        "os.system",
        ".unlink(",
        ".rename(",
        "shutil.move",
        "shutil.rmtree",
    )
    for path in source_paths:
        text = path.read_text(encoding="utf-8")
        for fragment in forbidden_fragments:
            assert fragment not in text, f"{fragment} found in {path}"


def test_registry_declares_safe_posture() -> None:
    payload = registry.build_registry(Path.cwd())
    posture_ids = {item["posture_id"] for item in payload["current_safety_posture"]}

    assert payload["current_status"] == "OPENCLAW_SYSTEM_KNOWLEDGE_REGISTRY_REBUILT"
    assert payload["safety_assertions"]["no_runtime_mutation"] is True
    assert payload["safety_assertions"]["no_external_calls"] is True
    assert "posture_no_external_calls" in posture_ids
    assert "posture_no_live_grants" in posture_ids


def test_live_projection_reads_ledger_and_atlas_metadata(tmp_path: Path) -> None:
    from business_ops_ledger import append_event, init_business_ops_ledger

    ledger_path = tmp_path / "ledger.sqlite"
    atlas_path = tmp_path / "atlas.json"
    init_business_ops_ledger(str(ledger_path))
    append_event("evt_projection", "test_event", "tester", db_path=str(ledger_path))
    atlas_path.write_text(
        json.dumps(
            {
                "summary": {"root_count": 1, "directory_count": 2, "priority_file_count": 1},
                "directories": [],
            }
        ),
        encoding="utf-8",
    )

    projection = registry.build_live_registry_projection(
        tmp_path,
        ledger_path=ledger_path,
        atlas_path=atlas_path,
    )

    assert projection["source_mode"] == "read_only_ledger_and_atlas_metadata"
    assert projection["ledger_counts"]["events"] == 1
    assert projection["atlas_summary"]["priority_file_count"] == 1
    assert projection["authority_boundary"]["read_only"] is True
    assert projection["authority_boundary"]["external_call"] is False


def test_query_system_knowledge_registry_answers_shape_unknowns_and_orbit(tmp_path: Path) -> None:
    atlas_path = tmp_path / "atlas.json"
    atlas_path.write_text(
        json.dumps({"summary": {"root_count": 1, "directory_count": 1}, "directories": []}),
        encoding="utf-8",
    )

    shape = registry.query_system_knowledge_registry(
        "what is the shape of the system?",
        repo_root=tmp_path,
        atlas_path=atlas_path,
    )
    unknowns = registry.query_system_knowledge_registry(
        "what does it not know yet?",
        repo_root=tmp_path,
        atlas_path=atlas_path,
    )
    orbit = registry.query_system_knowledge_registry(
        "what is floating in orbit?",
        repo_root=tmp_path,
        atlas_path=atlas_path,
    )

    assert shape["answer_type"] == "system_shape"
    assert "components" in shape["items"]
    assert shape["authority_boundary"]["model_call"] is False
    assert unknowns["answer_type"] == "known_unknowns"
    assert any(item["unknown_id"] == "unknown_correspondence_gmail_scope" for item in unknowns["items"])
    assert orbit["answer_type"] == "orbit_and_atlas"
    assert orbit["items"]["atlas_summary"]["root_count"] == 1


def test_query_system_knowledge_registry_answers_spine_and_router_questions(tmp_path: Path) -> None:
    spine = registry.query_system_knowledge_registry(
        "what is The Spine seven step front door?",
        repo_root=tmp_path,
    )
    routers = registry.query_system_knowledge_registry(
        "show the router registry routing options and next safe move",
        repo_root=tmp_path,
    )
    combined = registry.query_system_knowledge_registry(
        "how does the Spine route through the router registry?",
        repo_root=tmp_path,
    )

    assert spine["answer_type"] == "spine_flow"
    assert [step["step_number"] for step in spine["items"]["spine_steps"]] == [1, 2, 3, 4, 5, 6, 7]
    assert spine["source_refs"]["spine_lock_ref"].endswith("SYSTEM-SPINE-7-STEP-FLOW.md")
    assert routers["answer_type"] == "router_registry"
    assert {item["family_name"] for item in routers["items"]} >= {"Chat", "WorkflowPackages", "LocalSurface"}
    assert combined["answer_type"] == "spine_and_router_registry"

    rendered = registry.format_system_knowledge_answer(combined)
    assert "OpenClaw The Spine" in rendered
    assert "1. Intake Front Door" in rendered
    assert "Router families:" in rendered
    assert "no model call" in rendered


def test_combined_system_self_knowledge_query_answers_all_sections(tmp_path: Path) -> None:
    atlas_path = tmp_path / "atlas.json"
    atlas_path.write_text(
        json.dumps({"summary": {"root_count": 1, "directory_count": 2}, "directories": []}),
        encoding="utf-8",
    )

    answer = registry.query_system_knowledge_registry(
        "what's the system's shape / what does it know / not know / in orbit?",
        repo_root=tmp_path,
        atlas_path=atlas_path,
    )
    rendered = registry.format_system_knowledge_answer(answer)

    assert answer["answer_type"] == "system_self_knowledge"
    assert "system_shape" in answer["items"]
    assert "known_unknowns" in answer["items"]
    assert "orbit_and_atlas" in answer["items"]
    assert answer["items"]["orbit_and_atlas"]["atlas_summary"]["root_count"] == 1
    assert any(
        item["unknown_id"] == "unknown_live_business_ops_ledger_missing"
        for item in answer["items"]["known_unknowns"]
    )
    assert "Shape:" in rendered
    assert "Knows:" in rendered
    assert "Does not know:" in rendered
    assert "In orbit:" in rendered
    assert "no model call" in rendered


def test_query_system_knowledge_registry_cli_json_and_operator(capsys, tmp_path: Path) -> None:
    atlas_path = tmp_path / "atlas.json"
    atlas_path.write_text(
        json.dumps({"summary": {"root_count": 1, "directory_count": 3}, "directories": []}),
        encoding="utf-8",
    )

    assert query_main(
        [
            "--repo-root",
            str(tmp_path),
            "--atlas-path",
            str(atlas_path),
            "--format",
            "json",
            "--question",
            "what's the system's shape / what does it know / not know / in orbit?",
        ]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["answer_type"] == "system_self_knowledge"

    assert query_main(
        [
            "--repo-root",
            str(tmp_path),
            "--atlas-path",
            str(atlas_path),
            "--format",
            "operator",
            "what is in orbit",
        ]
    ) == 0
    output = capsys.readouterr().out
    assert "OpenClaw Orbit" in output
    assert "read-only" in output
