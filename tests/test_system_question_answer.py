import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import system_question_answer as sqa


FIXED_NOW = "2026-06-02T08:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_sources(root: Path, sqlite_root: Path) -> None:
    _write_json(
        root / "workflow_package_queue_contract.json",
        {
            "packages": [
                {
                    "workflow_ref": "capital_hilton_invoice_operator_assist",
                    "status": "PROVIDER_GATE_REQUIRED",
                    "capability_gate_result": {
                        "status": "PROVIDER_GATE_REQUIRED",
                        "reason": "Operator-assist provider and final Submit gate are not explicitly staged.",
                    },
                }
            ],
            "authority_boundary_default": {
                "email_send_allowed": False,
                "ledger_posting_allowed": False,
                "browser_access_allowed": False,
                "gmail_allowed": False,
                "coupa_allowed": False,
                "portal_submit_allowed": False,
                "sent": False,
                "paid": False,
            },
        },
    )
    _write_json(
        root / "automation_permission_registry.json",
        {
            "permission_statuses": {
                "gmail_send": "blocked_until_explicit_send_gate",
                "coupa_submit": "blocked_until_explicit_submit_gate",
                "ledger_post": "blocked",
                "paid_marking": "blocked",
            },
            "authority_boundary": {
                "email_send_allowed": False,
                "ledger_posting_allowed": False,
                "browser_access_allowed": False,
                "gmail_allowed": False,
                "coupa_allowed": False,
                "portal_submit_allowed": False,
                "sent": False,
                "paid": False,
            },
        },
    )
    _write_json(root / "operator_assist_provider_registry.json", {"status": "OPERATOR_ASSIST_PROVIDER_REGISTRY_READY"})
    _write_json(root / "agent_voice_routing_contract.json", {"status": "AGENT_VOICE_ROUTING_V0_READY"})
    _write_json(root / "agent_voice_profiles.json", {"status": "AGENT_VOICE_PROFILES_V0_READY"})
    _write_json(root / "operator_conversation_journal.json", {"status": "OPERATOR_CONVERSATION_JOURNAL_READY"})
    _write_json(root / "overnight_workboard.json", {"mode": "planning_only"})
    _write_json(
        root / "st_annes_work_log_events.json",
        {
            "event_count": 1,
            "staged_events": [
                {
                    "event_id": "st_annes_work_log:fixture",
                    "description": "RAW_SECRET_ROW_SHOULD_NOT_APPEAR",
                }
            ],
        },
    )
    _write_json(root / "st_annes_monthly_work_log_contract.json", {"status": "ST_ANNES_MONTHLY_WORK_LOG_CONTRACT_READY"})
    _write_json(root / "operator_human_readability_surface.json", {"status": "OPERATOR_HUMAN_READABILITY_SURFACE_READY"})
    _write_json(root / "openclaw_lm_child_package_gate.json", {"status": "CHILD_PACKAGE_GATE_CONTRACT_READY"})
    _write_json(root / "role_package_gate.json", {"status": "ROLE_PACKAGE_GATE_READY"})
    _write_json(
        root / "package_event_index.json",
        {
            "status": "PACKAGE_EVENT_INDEX_READY",
            "source_systems": {
                "business_ledger": {
                    "included": False,
                    "policy": "excluded",
                }
            },
        },
    )
    _write_json(
        root / "openclaw_workroom_registry.json",
        {
            "status": "OPENCLAW_WORKROOM_REGISTRY_READY",
            "channels": [
                {
                    "channel_ref": "build_mission_control_mac",
                    "display_name": "Build - Mission Control Mac",
                    "world_ref": "build",
                    "thread_ref": "workroom:build_mission_control_mac:main",
                    "primary_agent": "chief",
                },
                {
                    "channel_ref": "build_openclaw_backend",
                    "display_name": "Build - OpenClaw Backend",
                    "world_ref": "build",
                    "thread_ref": "workroom:build_openclaw_backend:main",
                    "primary_agent": "chief",
                },
                {
                    "channel_ref": "operations_chief_workboard",
                    "display_name": "Operations - Chief Workboard",
                    "world_ref": "operations",
                    "thread_ref": "workroom:operations_chief_workboard:main",
                    "primary_agent": "chief",
                },
            ],
        },
    )
    _write_json(
        root / "agent_handoff_registry.json",
        {
            "status": "AGENT_HANDOFF_REGISTRY_READY",
            "handoffs": [
                {
                    "handoff_ref": "cassandra_to_chief_package_needed",
                    "from_agent": "cassandra",
                    "to_agent_or_worker": "chief",
                    "channel_ref": "operations_chief_workboard",
                    "package_type": "package_request_handoff_packet",
                },
                {
                    "handoff_ref": "hermes_to_chief_build_packet",
                    "from_agent": "hermes",
                    "to_agent_or_worker": "chief",
                    "channel_ref": "operations_chief_workboard",
                    "package_type": "architecture_to_build_packet",
                },
                {
                    "handoff_ref": "chief_to_mac_codex_ui_excel_gui_operator_assist",
                    "from_agent": "chief",
                    "to_agent_or_worker": "mac_codex",
                    "channel_ref": "build_mission_control_mac",
                    "package_type": "mac_codex_operator_assist_worker_packet",
                },
                {
                    "handoff_ref": "chief_to_pc_codex_backend_implementation",
                    "from_agent": "chief",
                    "to_agent_or_worker": "pc_codex",
                    "channel_ref": "build_openclaw_backend",
                    "package_type": "pc_codex_backend_worker_packet",
                },
            ],
        },
    )
    _write_json(
        root / "spawned_worker_package_lifecycle.json",
        {
            "status": "SPAWNED_WORKER_PACKAGE_LIFECYCLE_READY",
            "examples": [
                {
                    "example_ref": "mac_ui_package_review",
                    "worker_ref": "mac_codex",
                    "channel_ref": "build_mission_control_mac",
                    "package_id": "pkg:example:mission_control_ui_patch",
                    "review_packet_summary": {
                        "human_summary": "MAC_CODEX returned Mission Control UI review output.",
                        "screenshots": ["generated/screenshots/example_mission_control_review.png"],
                    },
                }
            ],
        },
    )
    _write_json(
        root / "openclaw_workroom_activity_feed.json",
        {
            "status": "OPENCLAW_WORKROOM_ACTIVITY_FEED_READY",
            "posts": [
                {
                    "post_id": "workroom_post:mac_review",
                    "channel_ref": "build_mission_control_mac",
                    "speaker_ref": "mac_codex",
                    "headline": "MAC_CODEX review packet ready",
                    "plain_summary": "MAC_CODEX returned UI work with screenshot proof for operator review.",
                    "business_action_performed": False,
                },
                {
                    "post_id": "workroom_post:pc_review",
                    "channel_ref": "build_openclaw_backend",
                    "speaker_ref": "pc_codex",
                    "headline": "PC_CODEX review packet ready",
                    "plain_summary": "PC_CODEX returned backend validation proof for operator review.",
                    "business_action_performed": False,
                },
            ],
        },
    )
    _write_json(
        root / "workroom_review_packet_index.json",
        {
            "status": "WORKROOM_REVIEW_PACKET_INDEX_READY",
            "packets": [
                {
                    "review_packet_id": "review_packet:mac_done",
                    "package_id": "pkg:example:mission_control_ui_patch",
                    "worker_ref": "mac_codex",
                    "channel_ref": "build_mission_control_mac",
                    "status": "OPERATOR_REVIEW_RECORDED",
                    "human_summary": "MAC_CODEX returned UI work with screenshot proof for operator review.",
                    "screenshots": ["generated/screenshots/example_mission_control_review.png"],
                    "operator_decision_required": False,
                    "visible_by_default": False,
                    "completed": True,
                    "business_action_performed": False,
                    "git_push_performed": False,
                    "proof_refs": ["generated/read_models/spawned_worker_package_lifecycle.json#mac_ui_package_review"],
                },
                {
                    "review_packet_id": "review_packet:pc_ready",
                    "package_id": "pkg:example:backend_registry_patch",
                    "worker_ref": "pc_codex",
                    "channel_ref": "build_openclaw_backend",
                    "status": "REVIEW_PACKET_READY",
                    "human_summary": "PC_CODEX changed backend code and returned local validation proof for operator review.",
                    "operator_decision_required": True,
                    "visible_by_default": True,
                    "completed": False,
                    "business_action_performed": False,
                    "git_push_performed": False,
                    "proof_refs": ["generated/read_models/spawned_worker_package_lifecycle.json#pc_backend_package_review"],
                },
            ],
        },
    )
    _write_json(root / "worker_package_staging_status.json", {"status": "WORKER_PACKAGE_STAGING_READY"})
    _write_json(root / "chief_build_backlog.json", {"status": "CHIEF_BUILD_BACKLOG_READY", "backlog_items": []})
    _write_json(
        root / "capital_hilton_invoice_operator_run_status.json",
        {
            "status": "CAPITAL_HILTON_OPERATOR_RUN_RECORDED",
            "coupa_submitted": True,
            "coupa_submission_recorded": True,
            "coupa_submission_status": "processing",
            "coupa_status_observed": "Processing",
            "payment_received_recorded": False,
            "paid": False,
            "ledger_mutation_performed": False,
        },
    )
    _write_json(
        root / "operator_action_payloads.json",
        {
            "status": "OPERATOR_ACTION_PAYLOADS_READY",
            "action_payloads": [
                {
                    "action_id": "capital_hilton.payment.open_finance",
                    "label": "Open Finance / Capital Hilton",
                    "enabled": True,
                    "business_action": False,
                    "safe_to_render_button": True,
                    "authority_boundary": {"ledger_mutation_allowed": False, "coupa_allowed": False},
                }
            ],
        },
    )
    _write_json(
        root / "lm_bounded_operator_orchestration_latest.json",
        {
            "status": "READY",
            "readiness_status": "LM_BOUNDED_OPERATOR_ORCHESTRATION_READY",
            "lm_recommended_action": {
                "action_id": "capital_hilton.payment.open_finance",
                "label": "Open Finance / Capital Hilton",
            },
        },
    )
    _write_json(
        root / "finance_thread_index.json",
        {
            "status": "FINANCE_THREAD_INDEX_READY",
            "threads": [
                {"world_ref": "finance", "thread_ref": "capital_hilton"},
                {"world_ref": "finance", "thread_ref": "st_annes"},
            ],
        },
    )
    _write_json(
        root / "operator_next_decision.json",
        {
            "status": "READY",
            "target_world_ref": "build",
            "target_thread_ref": "build_openclaw_backend",
            "review_packet_id": "review_packet:pc_ready",
            "worker_ref": "pc_codex",
            "plain_summary": "PC_CODEX changed backend code and returned local validation proof for operator review.",
        },
    )
    _write_json(
        root / "capital_hilton_business_development_proposal.json",
        {
            "client_ref": "capital_hilton",
            "client_review_pending": True,
            "proposal_status": "SENT_FOR_CLIENT_REVIEW",
            "email_send_allowed": False,
            "finance_handoff_allowed": False,
            "ledger_posting_allowed": False,
            "paid": False,
        },
    )
    _write_json(
        root / "sqlite_governance_registry.json",
        {
            "status": "SQLITE_GOVERNANCE_REGISTRY_READY",
            "database_count": 8,
            "classification_counts": {
                "canonical_workflow_state": 3,
                "generated_evidence": 2,
                "generated_status": 1,
                "test_harness": 1,
                "protected_business_ledger": 1,
                "unknown_needs_review": 1,
            },
            "protected_ledger_count": 1,
            "unknown_review_count": 1,
            "databases": [
                {
                    "path": "generated/system_knowledge/workflow_package_queue.sqlite",
                    "classification": "canonical_workflow_state",
                    "owner_lane": "workflow_package_queue",
                    "consolidation_risk": "low",
                    "canonical_truth_allowed": True,
                    "consolidation_candidate": False,
                },
                {
                    "path": "generated/system_knowledge/operator_conversation_journal.sqlite",
                    "classification": "canonical_workflow_state",
                    "owner_lane": "operator_conversation",
                    "consolidation_risk": "medium",
                    "canonical_truth_allowed": True,
                    "consolidation_candidate": False,
                },
                {
                    "path": "generated/system_knowledge/st_annes_monthly_work_log.sqlite",
                    "classification": "generated_evidence",
                    "owner_lane": "invoice_operations",
                    "consolidation_risk": "medium",
                    "canonical_truth_allowed": False,
                    "consolidation_candidate": True,
                },
                {
                    "path": ".openclaw/business_ops/ledger.sqlite",
                    "classification": "protected_business_ledger",
                    "owner_lane": "business_ops",
                    "consolidation_risk": "forbidden",
                    "canonical_truth_allowed": True,
                    "consolidation_candidate": False,
                },
            ],
        },
    )
    _write_json(
        root / "canonical_state_map.json",
        {
            "status": "CANONICAL_STATE_MAP_READY",
            "domains": [
                {
                    "domain_ref": "package_queue",
                    "canonical_source": {
                        "source_ref": "generated/read_models/workflow_package_queue_contract.json",
                        "truth_scope": "Package definitions and package statuses.",
                    },
                },
                {
                    "domain_ref": "st_annes_work_log",
                    "canonical_source": {
                        "source_ref": "generated/read_models/st_annes_work_log_events.json",
                        "truth_scope": "St Anne's work-log events.",
                    },
                },
                {
                    "domain_ref": "business_ledger",
                    "canonical_source": {
                        "source_ref": "generated/read_models/sqlite_governance_registry.json",
                        "truth_scope": "Ledger location and isolation truth.",
                    },
                },
            ],
        },
    )
    _write_json(
        root / "sqlite_consolidation_plan.json",
        {
            "status": "SQLITE_CONSOLIDATION_PLAN_READY",
            "do_not_touch_databases": [
                {"category": "protected_business_ledger", "count": 1},
                {"category": "legacy_archives", "count": 0},
                {"category": "unknown_needs_review", "count": 1},
                {"category": "protected_evidence", "count": 1},
                {"category": "token_secret_credential_stores", "count": 1},
            ],
            "keep_isolated_databases": [
                {"category": "test_harness", "count": 1},
                {"category": "generated_proof_status_dbs", "count": 3},
                {"category": "one_off_read_model_proof_dbs", "count": 1},
                {"category": "dry_run_warmup_dbs", "count": 1},
            ],
            "consolidation_candidates": [
                {"candidate_ref": "package_queue_event_concepts", "migration_allowed_now": False},
                {"candidate_ref": "request_response_index_concepts", "migration_allowed_now": False},
                {"candidate_ref": "operator_conversation_index_concepts", "migration_allowed_now": False},
                {"candidate_ref": "work_log_staging_if_safe", "migration_allowed_now": False},
            ],
            "recommended_first_low_risk_move": {
                "summary": "Create views/indexes over existing package/event/journal refs, not a data migration; use package_event_index as the cross-reference layer.",
                "write_allowed_now": False,
            },
            "migration_requirements_before_any_consolidation": [
                {"requirement_ref": "backup"},
                {"requirement_ref": "schema_diff"},
                {"requirement_ref": "row_count_proof"},
                {"requirement_ref": "checksum_or_sample_row_proof"},
                {"requirement_ref": "rollback_plan"},
                {"requirement_ref": "focused_tests"},
                {"requirement_ref": "no_business_ledger_mixing"},
                {"requirement_ref": "operator_approval"},
            ],
            "never_consolidate": [
                "Never consolidate ledger into package DB.",
                "Never consolidate secrets/tokens into read models.",
                "Never consolidate raw prompt bodies into operator journal.",
                "Never consolidate test harness into canonical state.",
            ],
            "unknown_db_policy": {
                "summary": "unknown_needs_review stays read-only; no deletion or migration is allowed.",
                "delete_allowed_now": False,
                "migration_allowed_now": False,
            },
        },
    )

    sqlite_root.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sqlite_root / "st_annes_monthly_work_log.sqlite")
    try:
        conn.execute("CREATE TABLE work_log_events (event_id TEXT, description TEXT)")
        conn.execute(
            "INSERT INTO work_log_events VALUES (?, ?)",
            ("event_1", "RAW_SECRET_ROW_SHOULD_NOT_APPEAR"),
        )
        conn.execute("CREATE TABLE review_actions (review_id TEXT)")
        conn.commit()
    finally:
        conn.close()


def _answer(
    question: str,
    tmp_path: Path,
    *,
    current_world_ref: str = "",
    current_thread_ref: str = "",
) -> dict:
    read_model_root = tmp_path / "read_models"
    sqlite_root = tmp_path / "sqlite"
    _fixture_sources(read_model_root, sqlite_root)
    return sqa.answer_system_question(
        question,
        current_world_ref=current_world_ref,
        current_thread_ref=current_thread_ref,
        read_model_root=read_model_root,
        sqlite_root=sqlite_root,
    )


def _walk_values(payload):
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield key, value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_values(value)


def test_chief_vs_spawned_worker_answer_explains_role_vs_package_worker(tmp_path):
    payload = _answer("What is the difference between Chief and a spawned worker?", tmp_path)
    text = json.dumps(payload)

    assert payload["workflow_ref"] == "system_question_answer"
    assert payload["speaker_ref"] in {"hermes", "chief"}
    assert "Chief is a named OpenClaw role" in text
    assert "package-bound execution thread" in text
    assert payload["machine_proof"]["child_agent_spawned"] is False
    assert payload["machine_proof"]["external_llm_called"] is False


def test_contextual_finance_capital_hilton_returns_payment_watch_answer(tmp_path):
    payload = _answer(
        "What should I do here?",
        tmp_path,
        current_world_ref="finance",
        current_thread_ref="capital_hilton",
    )

    assert payload["speaker_ref"] in {"chief", "cassandra"}
    assert payload["answer"]["headline"] == "Stay on payment watch"
    assert payload["answer"]["plain_summary"] == (
        "Coupa is processing. Wait for payment evidence before anything touches the ledger."
    )
    assert payload["answer"]["next_safe_action"] == "Watch for payment proof."
    assert payload["contextual_route"]["source_priority"] == "current_lane_first"
    assert payload["machine_proof"]["package_staged"] is False
    assert payload["machine_proof"]["diagnostic_queue_routed"] is False
    assert payload["machine_proof"]["coupa_access_performed"] is False
    assert payload["machine_proof"]["ledger_mutation_performed"] is False


def test_contextual_business_development_capital_hilton_returns_followup_no_send(tmp_path):
    payload = _answer(
        "What's next here?",
        tmp_path,
        current_world_ref="business_development",
        current_thread_ref="capital_hilton",
    )
    text = json.dumps(payload)

    assert payload["speaker_ref"] == "cassandra"
    assert payload["answer"]["headline"] == "Proposal follow-up is review-only"
    assert "Draft or stage a follow-up only for review" in payload["answer"]["plain_summary"]
    assert "do not send" in payload["answer"]["plain_summary"].lower()
    assert "SENT_FOR_CLIENT_REVIEW" in text
    assert payload["authority_boundary"]["email_send_allowed"] is False
    assert payload["machine_proof"]["email_send_performed"] is False


def test_contextual_build_lane_returns_review_packet_no_merge_or_push(tmp_path):
    payload = _answer(
        "What do I do with this?",
        tmp_path,
        current_world_ref="build",
        current_thread_ref="build_openclaw_backend",
    )
    text = json.dumps(payload)

    assert payload["speaker_ref"] == "chief"
    assert payload["answer"]["headline"] == "Review packet needs local decision"
    assert "review_packet:pc_ready" in text
    assert "review controls only" in payload["answer"]["plain_summary"].lower()
    assert payload["answer"]["next_safe_action"] == "Use review controls only; do not merge or push."
    assert payload["authority_boundary"]["merge_allowed"] is False
    assert payload["authority_boundary"]["git_push_allowed"] is False
    assert payload["machine_proof"]["merge_performed"] is False
    assert payload["machine_proof"]["git_push_performed"] is False


def test_contextual_missing_context_falls_back_safely(tmp_path):
    payload = _answer("What should I do here?", tmp_path)

    assert "contextual_route" not in payload
    assert payload["answer"]["headline"] == "No local answer found"
    assert payload["answer"]["unknown"]
    assert payload["machine_proof"]["live_execution_performed"] is False


def test_capital_hilton_submit_block_explains_provider_and_submit_gate(tmp_path):
    payload = _answer("Why did Submit Capital Hilton invoice block?", tmp_path)
    text = json.dumps(payload)

    assert payload["speaker_ref"] == "chief"
    assert payload["voice_mode"] == "diagnostic"
    assert "PROVIDER_GATE_REQUIRED" in text
    assert "final Submit gate" in text
    assert "No Coupa action" in text
    assert payload["authority_boundary"]["coupa_allowed"] is False


def test_email_authority_question_routes_to_guardian_and_blocks_send(tmp_path):
    payload = _answer("Can this send email?", tmp_path)
    text = json.dumps(payload)

    assert payload["speaker_ref"] == "guardian"
    assert payload["voice_mode"] == "safety_gate"
    assert "No email can be sent" in text
    assert "blocked_until_explicit_send_gate" in text
    assert payload["authority_boundary"]["email_send_allowed"] is False
    assert payload["machine_proof"]["email_send_performed"] is False


def test_sqlite_work_log_answer_summarizes_metadata_without_dumping_rows(tmp_path):
    payload = _answer("What does SQLite know about St. Anne's work logs?", tmp_path)
    text = json.dumps(payload)

    assert payload["speaker_ref"] == "chief"
    assert payload["voice_mode"] == "diagnostic"
    assert "work_log_events" in text
    assert "review_actions" in text
    assert "table counts" in text.lower()
    assert "RAW_SECRET_ROW_SHOULD_NOT_APPEAR" not in text
    assert payload["answer"]["unknown"]


def test_database_inventory_question_summarizes_classifications(tmp_path):
    payload = _answer("What are all these databases?", tmp_path)
    text = json.dumps(payload)

    assert payload["speaker_ref"] == "chief"
    assert payload["voice_mode"] == "diagnostic"
    assert "classifies 8 databases" in text
    assert "canonical_workflow_state=3" in text
    assert "protected_business_ledger=1" in text
    assert "RAW_SECRET_ROW_SHOULD_NOT_APPEAR" not in text
    assert payload["answer"]["show_machine_details_by_default"] is False


def test_sqlite_consolidation_question_says_plan_only_and_first_safe_step(tmp_path):
    payload = _answer("Can we consolidate SQLite?", tmp_path)
    text = json.dumps(payload)

    assert payload["speaker_ref"] == "hermes"
    assert payload["voice_mode"] == "recommendation"
    assert "plan-only" in text
    assert "Do not consolidate yet" in text
    assert "views/indexes" in text
    assert "not a data migration" in text
    assert "package_event_index" in text
    assert "checksum_or_sample_row_proof" in text
    assert payload["machine_proof"]["ledger_mutation_performed"] is False


def test_ledger_mixed_question_routes_to_guardian_and_keeps_ledger_isolated(tmp_path):
    payload = _answer("Is the ledger mixed into this?", tmp_path)
    text = json.dumps(payload)

    assert payload["speaker_ref"] == "guardian"
    assert payload["voice_mode"] == "safety_gate"
    assert "Ledger stays isolated" in text
    assert "protected_business_ledger" in text
    assert "consolidation risk is forbidden" in text
    assert "Paid truth never comes from proposal" in text
    assert payload["authority_boundary"]["ledger_posting_allowed"] is False


def test_never_merge_question_routes_to_guardian_and_lists_forbidden_merges(tmp_path):
    payload = _answer("What should never be merged?", tmp_path)
    text = json.dumps(payload)

    assert payload["speaker_ref"] == "guardian"
    assert payload["voice_mode"] == "safety_gate"
    assert "Protected stores must never merge" in text
    assert "ledger into package DB" in text
    assert "secrets/tokens into read models" in text
    assert "raw prompt bodies into operator journal" in text
    assert "test harness into canonical state" in text
    assert payload["authority_boundary"]["ledger_posting_allowed"] is False


def test_st_annes_work_log_owner_question_names_canonical_source(tmp_path):
    payload = _answer("Which database owns St. Anne's work logs?", tmp_path)
    text = json.dumps(payload)

    assert payload["speaker_ref"] == "chief"
    assert payload["voice_mode"] == "diagnostic"
    assert "st_annes_work_log_events.json" in text
    assert "st_annes_monthly_work_log.sqlite" in text
    assert "do not become invoice truth until operator confirmation" in text


def test_safe_cleanup_question_does_not_approve_delete_or_move(tmp_path):
    payload = _answer("What is safe to clean up?", tmp_path)
    text = json.dumps(payload)

    assert payload["speaker_ref"] == "guardian"
    assert payload["voice_mode"] == "safety_gate"
    assert "Nothing is safe to delete" in text
    assert "Do-not-touch buckets" in text
    assert "unknown_needs_review stays read-only" in text
    assert "does not authorize deletes" in text
    assert payload["machine_proof"]["live_execution_performed"] is False


def test_where_team_is_working_summarizes_workrooms(tmp_path):
    payload = _answer("Where is the team working?", tmp_path)
    text = json.dumps(payload)

    assert payload["speaker_ref"] == "chief"
    assert payload["voice_mode"] == "diagnostic"
    assert "Build - Mission Control Mac" in text
    assert "Build - OpenClaw Backend" in text
    assert "operations_chief_workboard" in text
    assert payload["answer"]["show_machine_details_by_default"] is False


def test_build_mission_control_mac_question_names_channel_and_packets(tmp_path):
    payload = _answer("What is in Build / Mission Control Mac?", tmp_path)
    text = json.dumps(payload)

    assert payload["speaker_ref"] == "chief"
    assert payload["voice_mode"] == "diagnostic"
    assert "build_mission_control_mac" in text
    assert "MAC_CODEX returned UI work" in text
    assert "OPERATOR_REVIEW_RECORDED" in text


def test_mac_codex_output_answer_summarizes_review_packet_without_raw_dump(tmp_path):
    payload = _answer("What did MAC_CODEX produce?", tmp_path)
    text = json.dumps(payload)

    assert payload["speaker_ref"] == "chief"
    assert "Mission Control UI" in text
    assert "generated/screenshots/example_mission_control_review.png" in text
    assert "RAW_SECRET_ROW_SHOULD_NOT_APPEAR" not in text
    assert payload["machine_proof"]["child_agent_spawned"] is False


def test_review_packets_need_attention_answer_filters_open_packets(tmp_path):
    payload = _answer("What review packets need my attention?", tmp_path)
    text = json.dumps(payload)

    assert payload["speaker_ref"] == "chief"
    assert "review_packet:pc_ready" in text
    assert "PC_CODEX changed backend code" in text
    assert "review_packet:mac_done" not in payload["answer"]["confirmed"][0]
    assert payload["machine_proof"]["live_execution_performed"] is False


def test_cassandra_handoff_question_routes_to_hermes(tmp_path):
    payload = _answer("Who does Cassandra hand off to?", tmp_path)
    text = json.dumps(payload)

    assert payload["speaker_ref"] == "hermes"
    assert payload["voice_mode"] == "recommendation"
    assert "cassandra_to_chief_package_needed" in text
    assert "operations_chief_workboard" in text


def test_hermes_build_recommendation_question_routes_to_hermes(tmp_path):
    payload = _answer("What happens when Hermes recommends a build?", tmp_path)
    text = json.dumps(payload)

    assert payload["speaker_ref"] == "hermes"
    assert "hermes_to_chief_build_packet" in text
    assert "local build packet" in text
    assert payload["machine_proof"]["external_llm_called"] is False


def test_pc_codex_push_question_routes_guardian_and_blocks_push(tmp_path):
    payload = _answer("Can PC_CODEX push this?", tmp_path)
    text = json.dumps(payload)

    assert payload["speaker_ref"] == "guardian"
    assert payload["voice_mode"] == "safety_gate"
    assert "PC_CODEX cannot push" in text
    assert "git_push_allowed=false" in text
    assert payload["machine_proof"]["submit_performed"] is False


def test_unknown_question_returns_safe_fallback_with_unknowns_and_proof_refs(tmp_path):
    payload = _answer("What does OpenClaw know about the purple submarine?", tmp_path)

    assert payload["speaker_ref"] == "openclaw"
    assert payload["answer"]["headline"] == "No local answer found"
    assert payload["answer"]["unknown"]
    assert payload["answer"]["proof_refs"]
    assert payload["machine_proof"]["live_execution_performed"] is False


def test_contract_exports_local_and_bridge_json_equal(tmp_path):
    read_model_root = tmp_path / "read_models"
    sqlite_root = tmp_path / "sqlite"
    _fixture_sources(read_model_root, sqlite_root)

    result = sqa.export_system_question_answer(
        read_model_root=read_model_root,
        sqlite_root=sqlite_root,
        export_root=tmp_path / "exported",
        bridge_export_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "System Question Answering.md",
        generated_at=FIXED_NOW,
    )

    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    assert local == bridge
    assert local["status"] == sqa.CONTRACT_STATUS
    assert local["workflow_ref"] == "system_question_answer"
    assert local["privacy"]["privacy_impact"] == "local_only"
    assert len(local["examples"]) == len(sqa.EXAMPLE_QUESTIONS)
    assert Path(result["wiki_path"]).exists()


def test_no_unsafe_true_grants(tmp_path):
    payload = _answer("Can this send email?", tmp_path)
    unsafe_keys = {
        "email_send_allowed",
        "ledger_posting_allowed",
        "browser_access_allowed",
        "gmail_allowed",
        "coupa_allowed",
        "portal_submit_allowed",
        "sent",
        "paid",
    }
    assert not [
        key
        for key, value in _walk_values(payload)
        if key in unsafe_keys and value is True
    ]
    assert payload["machine_proof"]["unsafe_true_grants_absent"] is True
