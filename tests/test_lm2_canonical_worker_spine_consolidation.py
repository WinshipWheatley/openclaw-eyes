import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import assignment_loop_contract
import codex_work_package_lifecycle as lifecycle
import lm2_canonical_worker_spine_consolidation as consolidation
import model_work_package_router
import openclaw_lm_consult_spine as consult_spine


FIXED_NOW = "2026-06-13T16:00:00+00:00"


def _assignment():
    assignment = assignment_loop_contract.build_assignment_loop(
        requested_by="operator",
        owner_agent="chief",
        worker_type="pc_codex",
        goal="Review a bounded lifecycle contract.",
        sources=["codex_work_package_lifecycle.py", "tests/test_codex_work_package_lifecycle.py"],
        standard="Return a concise review with validation proof refs.",
        proof_required=["pytest receipt", "unsafe scan receipt"],
        stop_condition="Stop after summary; do not push or mutate runtime.",
        current_status="active",
        created_at_utc=FIXED_NOW,
    )
    assignment["expected_output_schema"] = "LM2_CANONICAL_SPINE_SMOKE_RESULT_V0"
    return assignment


def _consult_request():
    return consult_spine.build_lm_consult_request(
        created_at_utc=FIXED_NOW,
        requested_by_agent="cassandra",
        owner_agent="chief",
        source_surface="telegram",
        source_context_ref="guided_review:data_room_reference_review:test",
        task_type="data_room_form_fill",
        consult_kind="form_fill",
        preferred_model_class="external_fast_worker",
        preferred_provider="gemini",
        provider_model_label="gemini-3.5-flash",
        context_refs=["generated/read_models/guided_review_sessions.json#session:test"],
        redacted_context_summary="Current question only.",
        expected_output_schema={"type": "object"},
    )


def test_assignment_loop_can_create_canonical_worker_package(tmp_path):
    result = lifecycle.create_worker_package_from_assignment_loop(
        _assignment(),
        sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite",
        package_root=tmp_path / "packages",
        generated_at=FIXED_NOW,
    )
    state = result["package_state"]
    package = state["package_json"]

    assert result["status"] == "canonical_worker_package_queued"
    assert state["state"] == lifecycle.STATE_AWAITING_WORKER_BRIDGE
    assert package["canonical_worker_spine_schema_version"] == lifecycle.LM2_CANONICAL_SPINE_V0
    assert package["expected_output_schema"] == "LM2_CANONICAL_SPINE_SMOKE_RESULT_V0"
    assert package["assignment_loop_ref"].startswith("assignment_loop:")
    assert package["execution_allowed"] is False
    assert package["runtime_mutation_allowed"] is False
    assert package["permission_boundary"]["execution_allowed"] is False
    assert "codex_work_package_lifecycle.sqlite" in str(tmp_path / "codex_work_package_lifecycle.sqlite")


def test_lm_consult_request_can_create_canonical_worker_package(tmp_path):
    result = lifecycle.create_worker_package_from_lm_consult_request(
        _consult_request(),
        sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite",
        package_root=tmp_path / "packages",
        generated_at=FIXED_NOW,
    )
    package = result["package_state"]["package_json"]

    assert result["status"] == "canonical_worker_package_queued"
    assert result["source_adapter"] == "lm_consult_request"
    assert package["lm_consult_request_ref"].startswith("lm_consult_request:")
    assert package["provider_access_metadata"]["provider"] == "gemini"
    assert package["provider_access_metadata"]["metadata_grants_authority"] is False
    assert package["execution_allowed"] is False
    assert package["runtime_mutation_allowed"] is False
    assert package["tools_allowed"] is False


def test_provider_access_metadata_does_not_grant_authority(tmp_path):
    assignment = _assignment()
    result = lifecycle.create_worker_package_from_assignment_loop(
        assignment,
        worker_kind="fable",
        dispatch_mode="subscription_cli_candidate",
        sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite",
        package_root=tmp_path / "packages",
        generated_at=FIXED_NOW,
    )
    package = result["package_state"]["package_json"]

    assert package["provider_access_metadata"]["worker_kind"] == "fable"
    assert package["provider_access_metadata"]["access_mode"] == "subscription_cli_candidate"
    assert package["provider_access_metadata"]["metadata_grants_authority"] is False
    assert package["authority_boundary"]["external_model_allowed"] is False


def test_proof_verification_required_blocks_missing_bundle(tmp_path):
    result = lifecycle.create_worker_package_from_assignment_loop(
        _assignment(),
        sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite",
        package_root=tmp_path / "packages",
        generated_at=FIXED_NOW,
    )
    package_id = result["package_state"]["package_id"]
    worker_result = {
        "schema_version": lifecycle.PACKAGE_RESULT_SCHEMA,
        "package_id": package_id,
        "worker_kind": "manual_codex_handoff",
        "status": "completed",
        "authority_grant_ref": result["package_state"]["authority_grant_ref"],
        "files_changed": [],
        "commands_run": ["git diff --check"],
        "validation_run": ["git diff --check"],
        "unsafe_scan_summary": {"passed": True, "hits": []},
        "receipt_refs": ["fixture:result"],
        "submitted_at": FIXED_NOW,
        "proof_verification_required": True,
    }

    ingested = lifecycle.ingest_worker_result(
        worker_result,
        sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite",
        generated_at=FIXED_NOW,
    )

    assert ingested["package_state"]["state"] == lifecycle.STATE_VALIDATION_FAILED
    proof = ingested["validation_receipt"]["proof_verification"]
    assert proof["proof_verification_status"] == "blocked"
    assert "proof_verification_blocked" in ingested["validation_receipt"]["validation_errors"]


def test_contract_only_modules_remain_importable_and_point_to_canonical_spine():
    import cross_machine_worker_dispatch_package
    import openclaw_lm_child_package_gate
    import spawned_worker_package_lifecycle

    assert spawned_worker_package_lifecycle.MODULE_ROLE == "contract_only"
    assert cross_machine_worker_dispatch_package.CANONICAL_RUNTIME_SPINE_REF == "codex_work_package_lifecycle.py"
    assert openclaw_lm_child_package_gate.MODULE_ROLE == "contract_only"
    assert model_work_package_router.CANONICAL_RUNTIME_SPINE_REF == "codex_work_package_lifecycle.py"


def test_no_new_sqlite_registry_and_watch_desk_projection(tmp_path):
    result = lifecycle.create_worker_package_from_assignment_loop(
        _assignment(),
        sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite",
        package_root=tmp_path / "packages",
        generated_at=FIXED_NOW,
    )
    read_model = lifecycle.build_read_model(
        sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite",
        package_root=tmp_path / "packages",
        generated_at=FIXED_NOW,
    )

    sqlite_files = sorted(path.name for path in tmp_path.glob("*.sqlite"))
    assert sqlite_files == ["codex_work_package_lifecycle.sqlite"]
    assert read_model["canonical_spine"]["canonical_spine_file"] == "codex_work_package_lifecycle.py"
    assert read_model["watch_desk_items"]
    assert read_model["watch_desk_items"][0]["push_allowed"] is False
    assert result["package_state"]["package_id"] in read_model["package_ids"]


def test_existing_worker_run_manager_cli_still_works(tmp_path):
    lifecycle.create_worker_package_from_assignment_loop(
        _assignment(),
        sqlite_path=tmp_path / "codex_work_package_lifecycle.sqlite",
        package_root=tmp_path / "packages",
        generated_at=FIXED_NOW,
    )
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/openclaw_run.py",
            "--sqlite-path",
            str(tmp_path / "codex_work_package_lifecycle.sqlite"),
            "--package-root",
            str(tmp_path / "packages"),
            "--export-root",
            str(tmp_path / "read_models"),
            "--bridge-root",
            "",
            "--wiki-path",
            str(tmp_path / "wiki.md"),
            "status",
        ],
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert payload["status"] == lifecycle.READY_STATUS
    assert payload["read_model_path"].endswith("codex_work_package_lifecycle.json")


def test_repo_b_legacy_disposition_blocks_unsafe_patterns():
    disposition = consolidation.repo_b_legacy_disposition()
    blocked = " ".join(disposition["unsafe_blocked"] + disposition["blocked_legacy_patterns"]).lower()

    assert disposition["runtime_authority"] == "reference_only"
    assert disposition["repo_b_code_imported"] is False
    assert "oauth" in blocked
    assert "broker" in blocked
    assert "credential" in blocked
    assert "repair" in blocked


def test_consolidation_artifacts_export(tmp_path):
    result = consolidation.export_lm2_canonical_worker_spine(
        system_knowledge_root=tmp_path / "worker_spine_consolidation",
        read_model_path=tmp_path / "read_models" / "lm2_worker_spine_status.json",
        generated_at=FIXED_NOW,
    )
    read_model = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))

    assert result["status"] == consolidation.STATUS_READY
    assert read_model["canonical_spine"]["sqlite_registry_path"].endswith("codex_work_package_lifecycle.sqlite")
    assert read_model["safety_flags"]["new_sqlite_registry_created"] is False
    assert read_model["safety_flags"]["model_api_called"] is False
    assert Path(result["repo_b_json_path"]).exists()


def test_no_model_calls_and_no_unsafe_true_grants_in_artifact():
    payload = consolidation.build_lm2_spine_read_model(generated_at=FIXED_NOW)

    assert payload["safety_flags"]["model_api_called"] is False
    assert payload["safety_flags"]["worker_spawned"] is False
    assert payload["safety_flags"]["confirmed_reference_data_created"] is False
    assert payload["machine_proof"]["no_model_calls"] is True
