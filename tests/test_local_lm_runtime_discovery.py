import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import local_lm_runtime_discovery as discovery


FIXED_NOW = "2026-06-07T05:50:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    _write_json(root / "local_lm_pilot_harness_selection_packet.json", {"status": "LOCAL_LM_PILOT_HARNESS_SELECTION_PACKET_READY"})
    _write_json(root / "local_lm_harness_inventory_receipts.json", {"status": "LOCAL_LM_HARNESS_INVENTORY_RECEIPTS_READY"})
    _write_json(root / "local_lm_proof_to_response_readiness_gate.json", {"status": "LOCAL_LM_PROOF_RESPONSE_READINESS_GATE_READY"})
    _write_json(root / "proof_bundle_builder_redaction_status.json", {"status": "PROOF_BUNDLE_BUILDER_REDACTION_INTEGRATION_READY"})
    return root


def _repo_root(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "proof_to_response_runtime.py").parent.mkdir(parents=True, exist_ok=True)
    (repo / "proof_to_response_runtime.py").write_text("# fixture\n", encoding="utf-8")
    (repo / "proof_to_response_lm_shadow_pilot.py").write_text("# fixture\n", encoding="utf-8")
    (repo / "openclaw_hermes_sidecar.py").write_text("# fixture\n", encoding="utf-8")
    (repo / "live_lm_shadow_trial.py").write_text("# fixture\n", encoding="utf-8")
    return repo


def _which(name: str) -> str | None:
    return {
        "ollama": "/usr/bin/ollama",
        "llama-server": "/usr/local/bin/llama-server",
    }.get(name)


def _read_model(tmp_path: Path) -> dict:
    return discovery.build_read_model(
        read_model_root=_fixture_root(tmp_path),
        repo_root=_repo_root(tmp_path),
        generated_at=FIXED_NOW,
        which=_which,
        process_rows=[
            {"pid": "100", "command": "ollama", "search_text": "ollama serve"},
            {"pid": "101", "command": "llama-server", "search_text": "llama-server --host 127.0.0.1"},
        ],
    )


def _candidate(read_model: dict, runtime_ref: str) -> dict:
    return {
        row["runtime_ref"]: row
        for row in read_model["runtime_candidates"]
    }[runtime_ref]


def test_no_runtime_is_marked_invocation_allowed(tmp_path):
    read_model = _read_model(tmp_path)

    assert read_model["status"] == discovery.READY_STATUS
    for row in read_model["runtime_candidates"]:
        assert row["invocation_allowed"] is False
        assert row["proof_response_pilot_allowed"] is False
        assert row["authority_boundary"]["invocation_allowed"] is False


def test_external_provider_remains_blocked(tmp_path):
    row = _candidate(_read_model(tmp_path), "external_llm_blocked_by_default")

    assert row["invocation_allowed"] is False
    assert row["proof_response_pilot_allowed"] is False
    assert row["authority_boundary"]["external_provider_connect_allowed"] is False
    assert "external_provider_exception_gate_receipt" in row["missing_receipts"]


def test_runtime_presence_does_not_make_pilot_ready(tmp_path):
    read_model = _read_model(tmp_path)
    ollama = _candidate(read_model, "ollama")

    assert ollama["present"] is True
    assert ollama["already_running"] is True
    assert read_model["ready_for_pilot"] is False
    assert read_model["authority_boundary"]["proof_response_pilot_allowed"] is False


def test_missing_receipts_are_listed(tmp_path):
    row = _candidate(_read_model(tmp_path), "local_llm_shadow_mode")

    assert "operator_approval_receipt" in row["missing_receipts"]
    assert "model_invocation_boundary_receipt" in row["missing_receipts"]
    assert "no_external_provider_receipt" in row["missing_receipts"]
    assert "no_tool_authority_receipt" in row["missing_receipts"]
    assert "redacted_proof_bundle_receipt" in row["missing_receipts"]


def test_no_secrets_are_read(tmp_path):
    read_model = _read_model(tmp_path)

    assert read_model["implementation_boundary"]["secret_read"] is False
    assert read_model["implementation_boundary"]["api_key_read"] is False
    assert read_model["machine_proof"]["secrets_read"] is False
    for row in read_model["runtime_candidates"]:
        assert row["discovery_method"]["secret_files_read"] is False
        assert row["discovery_method"]["model_command_run"] is False
        assert row["discovery_method"]["http_endpoint_called"] is False


def test_recommended_candidate_is_shadow_mode_and_not_ready(tmp_path):
    read_model = _read_model(tmp_path)

    assert read_model["recommended_candidate_ref"] == "local_llm_shadow_mode"
    assert read_model["ready_for_pilot"] is False
    assert "No model can see proof bundles yet." in read_model["rules"]


def test_no_unsafe_true_grants(tmp_path):
    read_model = _read_model(tmp_path)

    assert discovery.unsafe_true_grants(read_model) == []
    assert read_model["unsafe_true_grants"] == []
    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True


def test_export_json_bridge_equality_and_wiki(tmp_path):
    result = discovery.export_local_lm_runtime_discovery(
        read_model_root=_fixture_root(tmp_path),
        repo_root=_repo_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "Local LM Runtime Discovery.md",
        generated_at=FIXED_NOW,
    )
    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert result["status"] == discovery.READY_STATUS
    assert result["ready_for_pilot"] == "false"
    assert local == bridge
    assert discovery.unsafe_true_grants(local) == []
    assert wiki.startswith("# Local LM Runtime Discovery")
