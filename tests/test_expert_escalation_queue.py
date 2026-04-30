import ast
import builtins
import inspect
import json
import sys

import pytest

import expert_escalation_queue as queue_module
from expert_escalation_packet import REQUIRED_SENSITIVITY_ATTESTATIONS, build_expert_escalation_packet
from expert_escalation_queue import (
    ExpertEscalationQueueError,
    enqueue_expert_packet,
    ensure_expert_queue_dirs,
    list_pending_expert_packets,
    load_expert_packet,
    mark_expert_packet_done,
    mark_expert_packet_failed,
    mark_expert_packet_running,
)


def _attestation() -> dict[str, bool]:
    return {key: True for key in REQUIRED_SENSITIVITY_ATTESTATIONS}


def _valid_packet(packet_id="expert-20260430-synthetic-review", **overrides):
    packet = build_expert_escalation_packet(
        packet_id=packet_id,
        created_at="2026-04-30T12:00:00Z",
        operator_request_summary="Review a synthetic public parser helper.",
        task_type="code_review",
        data_classification="synthetic_public",
        cloud_allowed=True,
        sensitivity_attestation=_attestation(),
        allowed_paths=("expert_escalation_packet.py", "tests/test_expert_escalation_packet.py"),
        forbidden_paths=("private-vaults", "secret-env-files", "gmail-bodies"),
        prompt="Review this synthetic public parser helper and return risks plus focused test ideas.",
        expected_outputs=("risk_summary", "test_suggestions"),
    )
    for key, value in overrides.items():
        if key == "execution_policy":
            merged = dict(packet["execution_policy"])
            merged.update(value)
            packet[key] = merged
        elif key == "sensitivity_attestation":
            merged = dict(packet["sensitivity_attestation"])
            merged.update(value)
            packet[key] = merged
        else:
            packet[key] = value
    return packet


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_queue_dirs_are_created_under_tmp_path(tmp_path):
    root = tmp_path / "expert_queue"

    dirs = ensure_expert_queue_dirs(root)

    assert set(dirs) == {"pending", "running", "done", "failed", "results"}
    assert all(path.is_dir() for path in dirs.values())
    assert all(tmp_path in path.parents for path in dirs.values())


def test_valid_packet_can_be_enqueued(tmp_path):
    packet = _valid_packet()

    pending_path = enqueue_expert_packet(packet, tmp_path)

    assert pending_path == tmp_path / "pending" / f"{packet['packet_id']}.json"
    assert load_expert_packet(pending_path) == packet


def test_unsafe_packet_is_rejected_and_not_written(tmp_path):
    packet = _valid_packet(cloud_allowed=False)

    with pytest.raises(ExpertEscalationQueueError, match="unsafe_expert_packet"):
        enqueue_expert_packet(packet, tmp_path)

    ensure_expert_queue_dirs(tmp_path)
    assert list((tmp_path / "pending").glob("*.json")) == []


def test_path_traversal_packet_id_is_rejected(tmp_path):
    packet = _valid_packet(packet_id="expert..escape")

    with pytest.raises(ExpertEscalationQueueError, match="unsafe_packet_id"):
        enqueue_expert_packet(packet, tmp_path)

    ensure_expert_queue_dirs(tmp_path)
    assert list((tmp_path / "pending").glob("*.json")) == []


def test_duplicate_enqueue_is_rejected(tmp_path):
    packet = _valid_packet()
    first_path = enqueue_expert_packet(packet, tmp_path)
    original = first_path.read_text(encoding="utf-8")

    with pytest.raises(FileExistsError):
        enqueue_expert_packet(packet, tmp_path)

    assert first_path.read_text(encoding="utf-8") == original


def test_pending_packets_can_be_listed_deterministically(tmp_path):
    for packet_id in ["expert-c", "expert-a", "expert-b"]:
        enqueue_expert_packet(_valid_packet(packet_id=packet_id), tmp_path)

    pending_paths = list_pending_expert_packets(tmp_path)

    assert [path.name for path in pending_paths] == ["expert-a.json", "expert-b.json", "expert-c.json"]


def test_packet_can_move_pending_to_running(tmp_path):
    packet = _valid_packet()
    enqueue_expert_packet(packet, tmp_path)

    running_path = mark_expert_packet_running(packet["packet_id"], tmp_path)

    assert running_path == tmp_path / "running" / f"{packet['packet_id']}.json"
    assert running_path.exists()
    assert not (tmp_path / "pending" / f"{packet['packet_id']}.json").exists()
    assert load_expert_packet(running_path) == packet


def test_packet_can_move_running_to_done_and_write_result(tmp_path):
    packet = _valid_packet()
    enqueue_expert_packet(packet, tmp_path)
    mark_expert_packet_running(packet["packet_id"], tmp_path)

    done_path = mark_expert_packet_done(
        packet["packet_id"],
        tmp_path,
        {
            "summary": "Synthetic review completed.",
            "artifact_paths": ["artifacts/review-summary.md"],
            "stdout_excerpt": "all synthetic",
            "stderr_excerpt": "",
        },
        completed_at="2026-04-30T13:00:00Z",
    )

    assert done_path == tmp_path / "done" / f"{packet['packet_id']}.json"
    assert done_path.exists()
    assert not (tmp_path / "running" / f"{packet['packet_id']}.json").exists()
    assert load_expert_packet(done_path) == packet

    result_path = tmp_path / "results" / f"{packet['packet_id']}.done.json"
    result = _read_json(result_path)
    assert result == {
        "packet_id": packet["packet_id"],
        "status": "done",
        "created_at": packet["created_at"],
        "completed_at": "2026-04-30T13:00:00Z",
        "summary": "Synthetic review completed.",
        "artifact_paths": ["artifacts/review-summary.md"],
        "stdout_excerpt": "all synthetic",
        "stderr_excerpt": "",
    }


def test_packet_can_move_running_to_failed_and_write_result(tmp_path):
    packet = _valid_packet(packet_id="expert-20260430-failed-review")
    enqueue_expert_packet(packet, tmp_path)
    mark_expert_packet_running(packet["packet_id"], tmp_path)

    failed_path = mark_expert_packet_failed(
        packet["packet_id"],
        tmp_path,
        "Manual checker rejected synthetic result metadata.",
        completed_at="2026-04-30T13:05:00Z",
    )

    assert failed_path == tmp_path / "failed" / f"{packet['packet_id']}.json"
    assert failed_path.exists()
    assert not (tmp_path / "running" / f"{packet['packet_id']}.json").exists()
    assert load_expert_packet(failed_path) == packet

    result_path = tmp_path / "results" / f"{packet['packet_id']}.failed.json"
    result = _read_json(result_path)
    assert result["packet_id"] == packet["packet_id"]
    assert result["status"] == "failed"
    assert result["created_at"] == packet["created_at"]
    assert result["completed_at"] == "2026-04-30T13:05:00Z"
    assert result["summary"] == "Manual checker rejected synthetic result metadata."
    assert result["artifact_paths"] == []
    assert result["stdout_excerpt"] == ""
    assert result["stderr_excerpt"] == "Manual checker rejected synthetic result metadata."


def test_done_result_metadata_is_bounded_and_artifact_paths_are_safe(tmp_path):
    packet = _valid_packet(packet_id="expert-20260430-bounded-result")
    enqueue_expert_packet(packet, tmp_path)
    mark_expert_packet_running(packet["packet_id"], tmp_path)

    mark_expert_packet_done(
        packet["packet_id"],
        tmp_path,
        {
            "summary": "s" * 2100,
            "artifact_paths": ["safe/result.md"],
            "stdout_excerpt": "o" * 4100,
            "stderr_excerpt": "e" * 4100,
        },
    )

    result = _read_json(tmp_path / "results" / f"{packet['packet_id']}.done.json")
    assert len(result["summary"]) == 2000
    assert len(result["stdout_excerpt"]) == 4000
    assert len(result["stderr_excerpt"]) == 4000
    assert result["artifact_paths"] == ["safe/result.md"]


def test_unsafe_artifact_path_is_rejected_without_done_move(tmp_path):
    packet = _valid_packet(packet_id="expert-20260430-unsafe-artifact")
    enqueue_expert_packet(packet, tmp_path)
    mark_expert_packet_running(packet["packet_id"], tmp_path)

    with pytest.raises(ExpertEscalationQueueError, match="unsafe_artifact_path"):
        mark_expert_packet_done(packet["packet_id"], tmp_path, {"artifact_paths": ["../secret.txt"]})

    assert (tmp_path / "running" / f"{packet['packet_id']}.json").exists()
    assert not (tmp_path / "done" / f"{packet['packet_id']}.json").exists()


def test_queue_module_does_not_import_or_call_external_surfaces(monkeypatch, tmp_path):
    source = inspect.getsource(queue_module)
    tree = ast.parse(source)
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module.split(".")[0])

    assert imported_modules <= {
        "__future__",
        "datetime",
        "expert_escalation_packet",
        "json",
        "pathlib",
        "re",
        "typing",
    }

    forbidden_modules = {
        "chief_notify",
        "chief_sender",
        "cloud",
        "codex",
        "gateway",
        "hermes_cli",
        "mcp",
        "openai",
        "requests",
        "runner_profiles",
        "runner_registry",
        "run_agent",
        "service",
        "subprocess",
        "telegram",
        "urllib",
    }
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        assert name.split(".")[0] not in forbidden_modules
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    packet = _valid_packet(packet_id="expert-20260430-import-guard")

    pending_path = enqueue_expert_packet(packet, tmp_path)
    assert list_pending_expert_packets(tmp_path) == [pending_path]
    running_path = mark_expert_packet_running(packet["packet_id"], tmp_path)
    assert load_expert_packet(running_path) == packet
    assert "expert_escalation_queue" in sys.modules