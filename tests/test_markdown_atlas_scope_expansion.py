import json
import sqlite3
from pathlib import Path

import markdown_atlas_scope_expansion as scope
from scripts.export_markdown_atlas_scope_expansion import main as export_main


FIXED_NOW = "2026-05-23T12:00:00+00:00"


def _fixture_db(tmp_path: Path) -> Path:
    db = tmp_path / "ledger.sqlite"
    conn = sqlite3.connect(db)
    try:
        conn.executescript(
            """
CREATE TABLE corpus_roots (
  root_id TEXT,
  absolute_root TEXT,
  root_kind TEXT,
  host_kind TEXT,
  owner_scope TEXT,
  status TEXT,
  root_label TEXT
);
CREATE TABLE corpus_atlas_runs (run_id TEXT);
CREATE TABLE corpus_paths (path_id TEXT);
CREATE TABLE corpus_path_labels (path_id TEXT, label TEXT);
CREATE TABLE markdown_atlas_runs (
  run_id TEXT,
  completed_at TEXT,
  created_at TEXT,
  source_corpus_runs_json TEXT
);
CREATE TABLE markdown_documents (markdown_document_id TEXT);
CREATE TABLE markdown_document_classifications (classification_id TEXT);
CREATE TABLE markdown_document_links (link_id TEXT);
CREATE TABLE markdown_document_reorg_candidates (candidate_id TEXT);
CREATE TABLE markdown_document_supersession (supersession_id TEXT);
CREATE TABLE markdown_evidence_sources (source_id TEXT);
CREATE TABLE markdown_evidence_items (item_id TEXT);
"""
        )
        conn.executemany(
            "INSERT INTO corpus_roots VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "pc_wsl_home_openclaw",
                    "/home/openclaw",
                    "operating_home_repo",
                    "pc_wsl",
                    "internal_platform",
                    "active_metadata_root",
                    "PC WSL root",
                ),
                (
                    "github_legacy_openclaw",
                    "not_imported://github/legacy_openclaw",
                    "legacy_git_repo",
                    "github",
                    "internal_platform",
                    "future_placeholder",
                    "Legacy repo",
                ),
            ],
        )
        conn.execute("INSERT INTO corpus_atlas_runs VALUES ('run1')")
        conn.executemany("INSERT INTO corpus_paths VALUES (?)", [(f"path{i}",) for i in range(4)])
        conn.executemany(
            "INSERT INTO corpus_path_labels VALUES (?, ?)",
            [(f"path{i}", "markdown") for i in range(6)],
        )
        conn.execute(
            "INSERT INTO markdown_atlas_runs VALUES (?, ?, ?, ?)",
            (
                "mdatlas_test",
                "2026-05-23T00:00:00+00:00",
                "2026-05-23T00:00:00+00:00",
                json.dumps({"corpus_runs": [{"root_id": "pc_wsl_home_openclaw", "run_id": "run1"}]}),
            ),
        )
        for table, count in [
            ("markdown_documents", 3),
            ("markdown_document_classifications", 5),
            ("markdown_document_links", 7),
            ("markdown_document_reorg_candidates", 2),
            ("markdown_document_supersession", 1),
            ("markdown_evidence_sources", 2),
            ("markdown_evidence_items", 4),
        ]:
            conn.executemany(f"INSERT INTO {table} VALUES (?)", [(f"{table}_{i}",) for i in range(count)])
        conn.commit()
    finally:
        conn.close()
    return db


def _build(tmp_path: Path) -> dict:
    db = _fixture_db(tmp_path)
    return scope.build_markdown_atlas_scope_expansion(
        repo_root=tmp_path,
        db_path=db,
        generated_at=FIXED_NOW,
    )


def test_contract_is_deterministic_and_metadata_only(tmp_path):
    first = _build(tmp_path)
    second = scope.build_markdown_atlas_scope_expansion(
        repo_root=tmp_path,
        db_path=tmp_path / "ledger.sqlite",
        generated_at=FIXED_NOW,
    )

    assert scope.stable_json(first) == scope.stable_json(second)
    assert first["schema_version"] == scope.SCHEMA_VERSION
    assert first["read_model_id"] == scope.READ_MODEL_ID
    assert first["contract_status"] == "metadata_only_scope_expansion_plan"
    assert first["core_doctrine"]["path_metadata_only"] is True
    assert first["core_doctrine"]["broad_markdown_body_reading_allowed"] is False
    assert first["core_doctrine"]["private_directory_scan_allowed"] is False
    assert first["machine_proof"]["metadata_only_posture"] is True


def test_current_coverage_counts_are_represented_from_sqlite_metadata(tmp_path):
    payload = _build(tmp_path)
    coverage = payload["current_markdown_atlas_coverage"]

    assert coverage["sqlite_present"] is True
    assert coverage["corpus_roots_count"] == 2
    assert coverage["corpus_paths_count"] == 4
    assert coverage["corpus_path_labels_count"] == 6
    assert coverage["markdown_atlas_run_count"] == 1
    assert coverage["markdown_documents_count"] == 3
    assert coverage["markdown_classifications_count"] == 5
    assert coverage["markdown_links_count"] == 7
    assert coverage["reorg_candidates_count"] == 2
    assert coverage["supersession_count"] == 1
    assert coverage["evidence_sources_count"] == 2
    assert coverage["evidence_items_count"] == 4
    assert coverage["coverage_status"] == "METADATA_ONLY_REGISTERED_ROOT_COVERAGE_PRESENT"
    assert payload["machine_proof"]["current_coverage_counts_represented"] is True


def test_root_scope_statuses_are_bounded_and_fail_closed(tmp_path):
    payload = _build(tmp_path)
    roots = {record["root_id"]: record for record in payload["markdown_root_scope_plan"]}

    assert roots["pc_wsl_home_openclaw"]["current_status"] == "CURRENTLY_COVERED"
    assert roots["pc_wsl_home_openclaw"]["body_ingestion_allowed"] is False
    assert roots["github_legacy_openclaw"]["current_status"] == "REQUIRES_OPERATOR_APPROVAL"
    assert roots["github_legacy_openclaw"]["operator_approval_required"] is True
    assert roots["windows_c_drive_blocked"]["current_status"] == "BLOCKED_C_DRIVE"
    assert roots["windows_c_drive_blocked"]["allowed_indexing"] == "none"
    assert roots["broad_operator_home_blocked"]["current_status"] == "BLOCKED_PRIVATE"
    assert roots["system_roots_blocked"]["current_status"] == "BLOCKED_SYSTEM"
    assert payload["machine_proof"]["root_statuses_fail_closed"] is True


def test_markdown_universe_gap_model_blocks_body_ingestion_and_semantic_review(tmp_path):
    payload = _build(tmp_path)
    gaps = {gap["gap_id"]: gap for gap in payload["markdown_universe_gap_model"]}

    assert set(gaps) == set(scope.GAP_IDS)
    assert gaps["repo_b_reference_markdown"]["requires_operator_root_approval"] is True
    assert gaps["personal_notes_unknown"]["current_coverage_status"] == "UNKNOWN_FAIL_CLOSED"
    assert gaps["external_drive_unknown"]["body_ingestion_allowed"] is False
    assert gaps["desktop_downloads_unknown"]["semantic_review_allowed_now"] is False
    assert gaps["generated_operator_markdown"]["promotion_policy"] == "Generated-surface-only; do not mine as personal memory."
    for gap in gaps.values():
        assert gap["body_ingestion_allowed"] is False
        assert gap["semantic_review_allowed_now"] is False


def test_recommended_next_expansion_is_bounded_metadata_only(tmp_path):
    payload = _build(tmp_path)
    recommendation = payload["recommended_next_atlas_expansion"]

    assert recommendation["recommendation"] == "RUN_METADATA_ONLY_ON_EXISTING_REGISTERED_ROOTS"
    assert "pc_wsl_home_openclaw" in recommendation["include_root_ids"]
    assert recommendation["body_ingestion_allowed"] is False
    assert recommendation["private_or_broad_root_scan_allowed"] is False
    assert recommendation["vector_index_creation_allowed"] is False
    assert recommendation["semantic_review_allowed_now"] is False
    assert payload["machine_proof"]["recommendation_is_bounded"] is True


def test_future_ai_judgment_policy_blocks_now_and_only_recommends_later(tmp_path):
    payload = _build(tmp_path)
    policy = payload["future_ai_judgment_policy"]

    assert "summarize selected allowlisted docs" in policy["allowed_later_only_after_metadata_classification"]
    assert "classify canonical vs stale vs residue" in policy["allowed_later_only_after_metadata_classification"]
    assert "broad body summarization" in policy["blocked_now"]
    assert "turning old notes into truth" in policy["blocked_now"]
    assert "moving/deleting files" in policy["blocked_now"]
    assert "creating vector memory from all docs" in policy["blocked_now"]
    assert policy["operator_answers_become"] == "memory_candidates_not_proof"
    assert payload["machine_proof"]["no_ai_semantic_review_now"] is True


def test_operator_questions_exist_and_answers_are_memory_candidates_not_proof(tmp_path):
    payload = _build(tmp_path)

    assert len(payload["operator_questions"]) == 7
    assert payload["machine_proof"]["operator_questions_exist"] is True
    for question in payload["operator_questions"]:
        assert question["answer_becomes"] == "memory_candidate_not_proof"
    assert any("Repo B Markdown reference-only" in q["question_text"] for q in payload["operator_questions"])


def test_authority_boundary_blocks_runtime_scans_reorg_vectors_and_network(tmp_path):
    payload = _build(tmp_path)
    boundary = payload["authority_boundary"]

    assert boundary["metadata_only_posture"] is True
    for key in [
        "broad_raw_markdown_body_ingestion_allowed",
        "broad_private_filesystem_scan_allowed",
        "private_root_approval_by_default",
        "c_drive_scan_allowed",
        "file_move_allowed",
        "file_delete_allowed",
        "file_rename_allowed",
        "file_reorganization_allowed",
        "vector_index_creation_allowed",
        "ai_semantic_review_allowed_now",
        "mission_control_app_mutation_allowed",
        "mac_sync_import_allowed",
        "network_operation_allowed",
        "git_push_pull_fetch_allowed",
        "model_api_execution_allowed",
        "agent_activation_allowed",
        "tool_execution_allowed",
        "runtime_dispatch_allowed",
        "queue_autonomy_allowed",
        "credential_account_access_allowed",
    ]:
        assert boundary[key] is False, key
    assert boundary["all_action_authority_flags_false"] is True


def test_no_credentials_raw_private_bodies_or_literal_c_drive_paths_are_included(tmp_path):
    payload = _build(tmp_path)
    text = scope.stable_json(payload)

    assert payload["machine_proof"]["credential_or_secret_included"] is False
    assert payload["machine_proof"]["raw_private_body_included"] is False
    assert payload["machine_proof"]["network_git_sync_mac_app_mutation_authority_added"] is False
    assert "/" + "mnt" + "/" + "c" not in text
    assert "c:" + "\\" not in text.lower()
    assert "sk-" not in text
    assert "BEGIN PRIVATE KEY" not in text


def test_exporter_writes_json_and_operator_markdown(tmp_path):
    db = _fixture_db(tmp_path)
    result = export_main(
        [
            "--repo-root",
            tmp_path.as_posix(),
            "--db",
            db.as_posix(),
            "--export-root",
            "generated/read_models",
            "--format",
            "summary",
        ]
    )

    assert result == 0
    json_path = tmp_path / "generated" / "read_models" / scope.JSON_EXPORT_NAME
    md_path = tmp_path / "generated" / "read_models" / scope.OPERATOR_EXPORT_NAME
    assert json_path.exists()
    assert md_path.exists()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    operator = md_path.read_text(encoding="utf-8")
    assert payload["schema_version"] == scope.SCHEMA_VERSION
    assert payload["recommended_next_atlas_expansion"]["body_ingestion_allowed"] is False
    assert "ELIWINSHIP Summary" in operator
    assert "Recommended Next Expansion" in operator
    assert "Operator Questions" in operator


def test_source_does_not_contain_broad_scan_or_mutation_calls():
    text = Path("markdown_atlas_scope_expansion.py").read_text(encoding="utf-8").lower()
    forbidden = [
        "os.walk",
        ".rglob(",
        ".glob(",
        "read_text(",
        "subprocess",
        "shutil.rmtree",
        "shutil.move",
        ".unlink(",
        ".rename(",
        "openai",
        "requests.",
    ]
    for token in forbidden:
        assert token not in text
