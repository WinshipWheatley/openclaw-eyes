import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import openclaw_workroom_activity_feed as feed


FIXED_NOW = "2026-06-03T17:00:00+00:00"
RAW_MARKER = "RAW_PROMPT_BODY_SHOULD_NOT_APPEAR"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    _write_json(
        root / "openclaw_workroom_registry.json",
        {
            "status": "OPENCLAW_WORKROOM_REGISTRY_READY",
            "channels": [
                {"channel_ref": "finance_st_annes"},
                {"channel_ref": "finance_capital_hilton"},
                {"channel_ref": "business_development_capital_hilton"},
                {"channel_ref": "build_mission_control_mac"},
                {"channel_ref": "build_openclaw_backend"},
                {"channel_ref": "architecture_hermes"},
                {"channel_ref": "security_guardian_gates"},
                {"channel_ref": "operations_chief_workboard"},
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
                    "trigger_condition": "A work-log item needs a package.",
                    "package_type": "package_request_handoff_packet",
                },
                {
                    "handoff_ref": "chief_to_guardian_protected_authority",
                    "from_agent": "chief",
                    "to_agent_or_worker": "guardian",
                    "channel_ref": "security_guardian_gates",
                    "trigger_condition": "A package asks for submit or ledger authority.",
                    "package_type": "protected_package_gate_packet",
                },
                {
                    "handoff_ref": "chief_to_pc_codex_backend_implementation",
                    "from_agent": "chief",
                    "to_agent_or_worker": "pc_codex",
                    "channel_ref": "build_openclaw_backend",
                    "trigger_condition": "A backend packet is ready for PC_CODEX review output.",
                    "package_type": "pc_codex_backend_worker_packet",
                },
                {
                    "handoff_ref": "chief_to_mac_codex_ui_excel_gui_operator_assist",
                    "from_agent": "chief",
                    "to_agent_or_worker": "mac_codex",
                    "channel_ref": "build_mission_control_mac",
                    "trigger_condition": "Mission Control UI work is ready for MAC_CODEX review output.",
                    "package_type": "mac_codex_operator_assist_worker_packet",
                },
                {
                    "handoff_ref": "hermes_to_chief_build_packet",
                    "from_agent": "hermes",
                    "to_agent_or_worker": "chief",
                    "channel_ref": "operations_chief_workboard",
                    "trigger_condition": "An architecture recommendation becomes concrete build work.",
                    "package_type": "architecture_to_build_packet",
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
                    "example_ref": "pc_backend_package_review",
                    "worker_ref": "pc_codex",
                    "channel_ref": "build_openclaw_backend",
                    "package_id": "pkg:example:backend",
                    "state_path": ["PACKAGE_STAGED", "RESULT_READY", "REVIEW_PACKET_READY"],
                    "review_packet_summary": {
                        "human_summary": "PC_CODEX returned backend validation proof for review.",
                        "next_safe_action": "Review backend validation refs.",
                        "receipts": ["generated/read_models/pc_backend_review_receipt.json"],
                        "screenshots": [],
                    },
                },
                {
                    "example_ref": "mac_ui_package_review",
                    "worker_ref": "mac_codex",
                    "channel_ref": "build_mission_control_mac",
                    "package_id": "pkg:example:mission_control_ui",
                    "state_path": ["PACKAGE_STAGED", "RESULT_READY", "REVIEW_PACKET_READY"],
                    "review_packet_summary": {
                        "human_summary": "MAC_CODEX returned Mission Control UI review output.",
                        "next_safe_action": "Inspect screenshot proof before approval.",
                        "receipts": ["generated/read_models/mac_ui_review_receipt.json"],
                        "screenshots": ["generated/screenshots/mac_ui_review.png"],
                    },
                },
            ],
        },
    )
    _write_json(
        root / "package_event_index.json",
        {
            "status": "PACKAGE_EVENT_INDEX_READY",
            "events": [
                {
                    "event_id": "package_event:st_annes",
                    "workflow_ref": "st_annes_work_log_event",
                    "package_id": "workflow_package:st_annes",
                    "package_status": "OPERATOR_REVIEW_REQUIRED",
                    "action_status": "OPERATOR_REVIEW_REQUIRED",
                    "created_at": "2026-06-03T16:00:00+00:00",
                    "target_world_ref": "finance",
                    "target_thread_ref": "st_annes",
                    "proof_refs": ["protected_text_hash:sha256:stannes", "workflow_package:st_annes"],
                    "linked_read_models": ["generated/read_models/st_annes_work_log_events.json"],
                    "raw_request_body_stored": False,
                    "source_text": RAW_MARKER,
                    "authority_summary": {
                        "business_action_performed": False,
                        "business_action_source": "none",
                        "does_not_create_new_business_truth": True,
                    },
                },
                {
                    "event_id": "package_event:capital_invoice",
                    "workflow_ref": "capital_hilton_invoice_operator_assist",
                    "package_id": "workflow_package:capital_invoice",
                    "package_status": "PROVIDER_GATE_REQUIRED",
                    "action_status": "PROVIDER_GATE_REQUIRED",
                    "created_at": "2026-06-03T16:01:00+00:00",
                    "target_world_ref": "finance",
                    "target_thread_ref": "capital_hilton",
                    "proof_refs": ["protected_text_hash:sha256:invoice", "workflow_package:capital_invoice"],
                    "linked_read_models": ["generated/read_models/capital_hilton_invoice_operator_run_status.json"],
                    "raw_request_body": RAW_MARKER,
                    "authority_summary": {
                        "business_action_performed": True,
                        "business_action_source": "existing_operator_ingested_read_model",
                        "does_not_create_new_business_truth": True,
                    },
                },
                {
                    "event_id": "package_event:capital_proposal",
                    "workflow_ref": "capital_hilton_proposal_followup",
                    "package_id": "workflow_package:capital_proposal",
                    "package_status": "OPERATOR_REVIEW_REQUIRED",
                    "action_status": "OPERATOR_REVIEW_REQUIRED",
                    "created_at": "2026-06-03T16:02:00+00:00",
                    "target_world_ref": "business_development",
                    "target_thread_ref": "capital_hilton",
                    "proof_refs": ["protected_text_hash:sha256:proposal", "workflow_package:capital_proposal"],
                    "linked_read_models": ["generated/read_models/capital_hilton_business_development_proposal.json"],
                    "operator_message": RAW_MARKER,
                    "authority_summary": {
                        "business_action_performed": True,
                        "business_action_source": "existing_operator_ingested_read_model",
                        "does_not_create_new_business_truth": True,
                    },
                },
            ],
        },
    )
    _write_json(
        root / "operator_conversation_journal.json",
        {
            "status": "OPERATOR_CONVERSATION_JOURNAL_READY",
            "entries": [
                {
                    "journal_entry_id": "operator_conversation_journal:st_annes",
                    "timestamp": "2026-06-03T16:03:00+00:00",
                    "headline": "Workflow package staged",
                    "short_summary": "OpenClaw recorded this as a dry-run workflow package.",
                    "speaker_ref": "openclaw",
                    "package_status": "OPERATOR_REVIEW_REQUIRED",
                    "target_world_ref": "finance",
                    "target_thread_ref": "st_annes",
                    "proof_refs": [{"ref": "workflow_package:st_annes"}, {"ref": "protected_text_hash:sha256:stannes"}],
                    "raw_request_body_stored": False,
                    "source_text": RAW_MARKER,
                }
            ],
        },
    )
    _write_json(
        root / "operator_next_decision.json",
        {
            "read_model_id": "operator_next_decision",
            "status": "READY",
            "generated_at": "2026-06-03T16:04:00+00:00",
            "headline": "Watch Capital Hilton payment",
            "plain_summary": "Ledger stays untouched until payment proof arrives.",
            "action_label": "Open Capital Hilton",
            "action_type": "navigate",
            "target_world_ref": "finance",
            "target_thread_ref": "capital_hilton",
            "business_action": False,
            "proof_refs": ["generated/read_models/package_event_index.json"],
        },
    )
    _write_json(
        root / "helm_action_lifecycle_status.json",
        {
            "read_model_id": "helm_action_lifecycle_status",
            "status": "HELM_ACTION_LIFECYCLE_READY",
            "generated_at": "2026-06-03T16:05:00+00:00",
            "primary_next_action": {
                "action_id": "capital_hilton_payment_watch",
                "label": "Open Finance / Capital Hilton",
                "reason": "Helm selected the next visible local action.",
                "target_world_ref": "finance",
                "target_thread_ref": "capital_hilton",
                "payload_ref": "generated/read_models/capital_hilton_invoice_operator_run_status.json",
            },
            "proof_refs": ["generated/read_models/helm_actionability_surface.json"],
        },
    )
    return root


def _posts(read_model: dict, channel_ref: str, post_type: str | None = None) -> list[dict]:
    rows = [post for post in read_model["posts"] if post["channel_ref"] == channel_ref]
    if post_type is not None:
        rows = [post for post in rows if post["post_type"] == post_type]
    return rows


def _walk_values(payload):
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield key, value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_values(value)


def test_finance_st_annes_channel_receives_work_log_posts(tmp_path):
    read_model = feed.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)

    posts = _posts(read_model, "finance_st_annes")
    assert read_model["status"] == feed.FEED_STATUS
    assert posts
    assert any(post["package_id"] == "workflow_package:st_annes" for post in posts)
    assert any("St Anne's work-log" in post["headline"] for post in posts)
    assert all(post["show_machine_details_by_default"] is False for post in posts)


def test_finance_capital_hilton_receives_invoice_operator_assist_posts(tmp_path):
    read_model = feed.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)

    posts = _posts(read_model, "finance_capital_hilton")
    assert any(post["package_id"] == "workflow_package:capital_invoice" for post in posts)
    invoice = next(post for post in posts if post["package_id"] == "workflow_package:capital_invoice")
    assert invoice["speaker_ref"] == "chief"
    assert invoice["post_type"] == "blocker"
    assert invoice["status_label"] == "Provider Gate Required"
    assert invoice["business_action_performed"] is True
    assert "previously ingested operator-assisted truth" in invoice["plain_summary"]


def test_business_development_capital_hilton_receives_proposal_posts(tmp_path):
    read_model = feed.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)

    posts = _posts(read_model, "business_development_capital_hilton")
    assert any(post["package_id"] == "workflow_package:capital_proposal" for post in posts)
    proposal = next(post for post in posts if post["package_id"] == "workflow_package:capital_proposal")
    assert proposal["speaker_ref"] == "cassandra"
    assert "do not infer paid or send" in proposal["next_safe_action"]


def test_build_mission_control_mac_receives_mac_codex_review_output(tmp_path):
    read_model = feed.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)

    posts = _posts(read_model, "build_mission_control_mac", post_type="review_packet")
    assert posts
    mac = next(post for post in posts if post["speaker_ref"] == "mac_codex")
    assert mac["package_id"] == "pkg:example:mission_control_ui"
    assert mac["status_label"] == "Review Packet Ready"
    assert "Mission Control UI review output" in mac["plain_summary"]
    assert "generated/screenshots/mac_ui_review.png" in mac["proof_refs"]


def test_required_mapping_channels_receive_backend_architecture_guardian_and_chief_posts(tmp_path):
    read_model = feed.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)

    assert _posts(read_model, "build_openclaw_backend", post_type="review_packet")
    assert _posts(read_model, "architecture_hermes")
    assert _posts(read_model, "security_guardian_gates", post_type="handoff")
    assert _posts(read_model, "operations_chief_workboard", post_type="handoff")
    assert all(read_model["required_channels_with_posts"].values())


def test_posts_use_required_schema_and_collapse_proof_refs(tmp_path):
    read_model = feed.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)
    required_fields = {
        "post_id",
        "channel_ref",
        "timestamp",
        "speaker_ref",
        "post_type",
        "headline",
        "plain_summary",
        "status_label",
        "next_safe_action",
        "target_world_ref",
        "target_thread_ref",
        "package_id",
        "proof_refs",
        "show_machine_details_by_default",
        "business_action_performed",
    }

    assert read_model["display_policy"]["proof_refs_collapsed_by_default"] is True
    for post in read_model["posts"]:
        assert required_fields == set(post)
        assert post["show_machine_details_by_default"] is False
        assert isinstance(post["proof_refs"], list)
        assert post["speaker_ref"] in feed.ALLOWED_SPEAKERS


def test_raw_prompt_bodies_are_absent(tmp_path):
    read_model = feed.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)
    rendered = json.dumps(read_model)

    assert RAW_MARKER not in rendered
    assert "source_text" not in rendered
    assert "operator_message" not in rendered
    assert read_model["machine_proof"]["raw_prompt_bodies_included"] is False
    assert read_model["machine_proof"]["raw_request_bodies_included"] is False


def test_no_unsafe_true_grants(tmp_path):
    read_model = feed.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)
    unsafe_keys = {
        "slack_connect_allowed",
        "telegram_live_connect_allowed",
        "message_send_allowed",
        "email_send_allowed",
        "gmail_allowed",
        "browser_access_allowed",
        "coupa_allowed",
        "portal_submit_allowed",
        "ledger_posting_allowed",
        "ledger_mutation_allowed",
        "workbook_mutation_allowed",
        "pdf_export_allowed",
        "paid_marking_allowed",
        "submit_allowed",
        "git_push_allowed",
        "worker_spawn_allowed",
        "agent_loop_allowed",
        "external_llm_allowed",
        "live_provider_allowed",
        "business_action_allowed",
        "sent",
        "paid",
    }

    assert not [key for key, value in _walk_values(read_model) if key in unsafe_keys and value is True]
    assert read_model["machine_proof"]["slack_connected"] is False
    assert read_model["machine_proof"]["message_send_performed"] is False
    assert read_model["machine_proof"]["ledger_mutation_performed"] is False
    assert read_model["machine_proof"]["git_push_performed"] is False


def test_export_writes_json_parseable_local_and_bridge_equal(tmp_path):
    result = feed.export_openclaw_workroom_activity_feed(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "OpenClaw Workroom Activity Feed.md",
        generated_at=FIXED_NOW,
    )

    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    assert local == bridge
    assert local["status"] == feed.FEED_STATUS
    assert local["post_count"] > 0
    assert Path(result["wiki_path"]).exists()
