import json
import re
from pathlib import Path

import active_machinery_gemini_verification as verifier
from scripts.verify_active_machinery_gemini_output import main as cli_main


FIXED_NOW = "2026-05-17T12:00:00+00:00"


def _write_json(path: Path, payload) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _sample_inputs(tmp_path: Path):
    root = tmp_path / "openclaw"
    shard_root = root / "generated" / "audit_shards" / "active_machinery_v0" / "shards"
    worker_path = (
        root
        / "generated"
        / "audit_shards"
        / "active_machinery_v0"
        / "mock_worker_outputs"
        / "full_classification.json"
    )
    dry_run_path = root / "generated" / "audit_shards" / "active_machinery_v0" / "privacy_inclusion_dry_run.json"

    shard = {
        "schema_version": "active_machinery_classification_shard_v0",
        "shard_id": "active_machinery_v0_shard_0001",
        "items": [
            {
                "repo_root": root.as_posix(),
                "repo_role": "canonical_repo_a",
                "relative_path": "chief_listener.py",
                "source_role": "source_code",
                "source_category": "source_code",
                "content_header_excerpt": "import time\n\ndef listen():\n    while True:\n        time.sleep(1)\n",
                "header_lines_read": 5,
                "body_read_allowed": False,
                "why_included": "test shard",
                "no_execution": True,
            },
            {
                "repo_root": root.as_posix(),
                "repo_role": "canonical_repo_a",
                "relative_path": "mystery.py",
                "source_role": "source_code",
                "source_category": "source_code",
                "content_header_excerpt": "def helper():\n    return 'plain metadata only'\n",
                "header_lines_read": 2,
                "body_read_allowed": False,
                "why_included": "test shard",
                "no_execution": True,
            },
            {
                "repo_root": root.as_posix(),
                "repo_role": "canonical_repo_a",
                "relative_path": "generated/read_models/status.json",
                "source_role": "generated_read_model",
                "source_category": "generated_artifact",
                "content_header_excerpt": "{\"status\": \"ok\"}\n",
                "header_lines_read": 1,
                "body_read_allowed": False,
                "why_included": "test shard",
                "no_execution": True,
            },
            {
                "repo_root": root.as_posix(),
                "repo_role": "canonical_repo_a",
                "relative_path": "hitl_action_service.py",
                "source_role": "source_code",
                "source_category": "source_code",
                "content_header_excerpt": "def request_approval(approval_id):\n    return {'hitl': approval_id}\n",
                "header_lines_read": 2,
                "body_read_allowed": False,
                "why_included": "test shard",
                "no_execution": True,
            },
        ],
    }
    worker = {
        "schema_version": "active_machinery_worker_output_v0",
        "worker_model": "Gemini 3.1 Pro",
        "shard_id": "all_shards",
        "llm_or_worker_calls_made": True,
        "raw_private_content_read": False,
        "repo_b_executed": False,
        "items": [
            {
                "repo_root": "unknown",
                "repo_role": "unknown",
                "relative_path": "chief_listener.py",
                "is_active_machinery": True,
                "machinery_type": "daemon_listener",
                "source_fate": "operator_review",
                "reads": "unknown",
                "writes": "unknown",
                "executes": "daemon_loop",
                "sends_external": "none",
                "touches_private_data": "unknown",
                "authority_risk": "high",
                "recommended_fate": "wrap",
                "confidence": 0.8,
                "one_sentence_evidence": "hypothesis",
            },
            {
                "repo_root": "unknown",
                "repo_role": "unknown",
                "relative_path": "mystery.py",
                "is_active_machinery": True,
                "machinery_type": "daemon_listener",
                "source_fate": "operator_review",
                "reads": "unknown",
                "writes": "unknown",
                "executes": "unknown",
                "sends_external": "none",
                "touches_private_data": "unknown",
                "authority_risk": "high",
                "recommended_fate": "operator_review",
                "confidence": 0.8,
                "one_sentence_evidence": "hypothesis",
            },
            {
                "repo_root": "unknown",
                "repo_role": "unknown",
                "relative_path": "generated/read_models/status.json",
                "is_active_machinery": False,
                "machinery_type": "generated_read_model_artifact",
                "source_fate": "generated_artifact",
                "reads": "generated_read_model",
                "writes": "none",
                "executes": "none",
                "sends_external": "none",
                "touches_private_data": "no",
                "authority_risk": "low",
                "recommended_fate": "keep",
                "confidence": 0.7,
                "one_sentence_evidence": "hypothesis",
            },
            {
                "repo_root": "unknown",
                "repo_role": "unknown",
                "relative_path": "hitl_action_service.py",
                "is_active_machinery": True,
                "machinery_type": "approval_hitl",
                "source_fate": "operator_review",
                "reads": "json_state",
                "writes": "json_state",
                "executes": "unknown",
                "sends_external": "none",
                "touches_private_data": "unknown",
                "authority_risk": "medium",
                "recommended_fate": "shadow",
                "confidence": 0.7,
                "one_sentence_evidence": "hypothesis",
            },
            {
                "repo_root": "unknown",
                "repo_role": "unknown",
                "relative_path": "private/secret.py",
                "is_active_machinery": True,
                "machinery_type": "unknown_operator_review",
                "source_fate": "operator_review",
                "reads": "unknown",
                "writes": "unknown",
                "executes": "unknown",
                "sends_external": "unknown",
                "touches_private_data": "unknown",
                "authority_risk": "high",
                "recommended_fate": "operator_review",
                "confidence": 0.1,
                "one_sentence_evidence": "hypothesis",
            },
        ],
    }
    dry_run = {
        "schema_version": "active_machinery_privacy_inclusion_dry_run_v0",
        "candidates": [
            {
                "repo_root": "/home/openclaw_external/openclaw-runtime",
                "repo_role": "pre_split_capability_tree_reference_only",
                "relative_path": ".",
                "eligibility": "reference_only",
            }
        ],
    }
    _write_json(shard_root / "active_machinery_v0_shard_0001.json", shard)
    _write_json(worker_path, worker)
    _write_json(dry_run_path, dry_run)
    return root, worker_path, shard_root, dry_run_path


def test_reconciles_unknown_gemini_repo_metadata_from_shards(tmp_path):
    root, worker_path, shard_root, dry_run_path = _sample_inputs(tmp_path)
    payload = verifier.build_verification_payload(
        worker_output_path=worker_path,
        shard_root=shard_root,
        dry_run_path=dry_run_path,
        generated_at=FIXED_NOW,
    )

    verified = payload["groups"]["verified_high_risk_active_machinery"]["items"]
    chief = next(item for item in verified if item["relative_path"] == "chief_listener.py")
    assert chief["repo_root"] == root.as_posix()
    assert chief["repo_role"] == "canonical_repo_a"
    assert chief["reconciliation_status"] == "matched_shard_metadata"
    assert chief["verified_as_high_risk_active_machinery"] is True


def test_high_risk_hypothesis_needs_deterministic_signal_before_verification(tmp_path):
    _root, worker_path, shard_root, dry_run_path = _sample_inputs(tmp_path)
    payload = verifier.build_verification_payload(
        worker_output_path=worker_path,
        shard_root=shard_root,
        dry_run_path=dry_run_path,
        generated_at=FIXED_NOW,
    )

    likely = payload["groups"]["likely_active_machinery_needing_operator_review"]["items"]
    mystery = next(item for item in likely if item["relative_path"] == "mystery.py")
    assert mystery["verified_as_high_risk_active_machinery"] is False
    assert mystery["verification_status"] == "hypothesis_needs_operator_review"


def test_repo_b_stays_reference_only_and_private_unmatched_item_is_not_read(tmp_path):
    _root, worker_path, shard_root, dry_run_path = _sample_inputs(tmp_path)
    payload = verifier.build_verification_payload(
        worker_output_path=worker_path,
        shard_root=shard_root,
        dry_run_path=dry_run_path,
        generated_at=FIXED_NOW,
    )

    repo_b = payload["groups"]["repo_b_reference_only_machinery"]["items"]
    assert repo_b
    assert repo_b[0]["repo_role"] == "pre_split_capability_tree_reference_only"
    unknown = payload["groups"]["likely_active_machinery_needing_operator_review"]["items"]
    private = next(item for item in unknown if item["relative_path"] == "private/secret.py")
    assert private["reconciliation_status"] == "missing_shard_metadata_operator_review"
    assert payload["boundaries"]["raw_private_content_read"] is False
    assert payload["boundaries"]["repo_b_executed"] is False


def test_run_verification_writes_json_operator_doc_and_clear_groups(tmp_path):
    root, worker_path, shard_root, dry_run_path = _sample_inputs(tmp_path)
    read_model_root = root / "generated" / "read_models"
    doc_path = root / "docs" / "operations" / "ACTIVE_MACHINERY_GEMINI_VERIFICATION_V0.md"

    summary = verifier.run_verification(
        worker_output_path=worker_path,
        shard_root=shard_root,
        dry_run_path=dry_run_path,
        read_model_root=read_model_root,
        doc_path=doc_path,
        generated_at=FIXED_NOW,
    )

    assert summary["gemini_output_treated_as_truth"] is False
    assert (read_model_root / "active_machinery_gemini_verification.json").is_file()
    operator = (read_model_root / "active_machinery_gemini_verification_OPERATOR.md").read_text(encoding="utf-8")
    doc = doc_path.read_text(encoding="utf-8")
    for text in (operator, doc):
        assert "Verified High-Risk Active Machinery" in text
        assert "Likely Active Machinery Needing Operator Review" in text
        assert "False Positives / Safe Docs And Generated Files" in text
        assert "Repo B Reference-Only Machinery" in text
        assert "Approval/HITL Surfaces" in text


def test_cli_outputs_summary_json(tmp_path, capsys):
    root, worker_path, shard_root, dry_run_path = _sample_inputs(tmp_path)
    code = cli_main(
        [
            "--worker-output",
            worker_path.as_posix(),
            "--shard-root",
            shard_root.as_posix(),
            "--dry-run",
            dry_run_path.as_posix(),
            "--read-model-root",
            (root / "generated" / "read_models").as_posix(),
            "--doc-path",
            (root / "docs" / "operations" / "ACTIVE_MACHINERY_GEMINI_VERIFICATION_V0.md").as_posix(),
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["verified_high_risk_count"] == 1
    assert payload["repo_b_executed"] is False
    assert payload["raw_private_content_read"] is False


def test_verifier_source_does_not_import_or_call_execution_network_or_shell_tools():
    source_paths = [
        Path("active_machinery_gemini_verification.py"),
        Path("scripts/verify_active_machinery_gemini_output.py"),
    ]
    source = "\n".join(path.read_text(encoding="utf-8") for path in source_paths)
    forbidden_patterns = [
        r"^\s*import\s+subprocess\b",
        r"^\s*from\s+subprocess\b",
        r"^\s*import\s+requests\b",
        r"^\s*from\s+requests\b",
        r"^\s*import\s+socket\b",
        r"os\.system\s*\(",
        r"subprocess\.",
        r"Popen\s*\(",
        r"shell\s*=\s*True",
    ]
    for pattern in forbidden_patterns:
        assert re.search(pattern, source, flags=re.MULTILINE) is None
