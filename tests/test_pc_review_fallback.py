import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
POLISH_LOOP_DIR = ROOT / "polish_loop"

if str(POLISH_LOOP_DIR) not in sys.path:
    sys.path.insert(0, str(POLISH_LOOP_DIR))

import orchestrator  # noqa: E402
import pc_review_fallback as fallback  # noqa: E402


def _build_pc_output(pass_num: int, status: str, changes_block: str, include_reasoning: bool = True) -> str:
    sections = [
        f"PASS: {pass_num}",
        f"STATUS: {status}",
        "",
        "CHANGES:",
        changes_block,
        "",
    ]
    if include_reasoning:
        sections.extend(["REASONING:", "Why these checks matter.", ""])
    sections.extend(
        [
            "ROLLBACK PLAN:",
            "Revert the test file if needed.",
            "",
            "COST:",
            "- Spend unavailable.",
            "",
            "TRUTH:",
            "- Verified: changed file exists.",
            "",
            "HEADROOM:",
            "- Claude: unavailable.",
            "",
            "NOT CHANGED:",
            "Core implementation left untouched.",
            "",
            "VAULT_CHANGES:",
            "NONE",
            "",
            "CONCERNS:",
            "NONE",
            "",
        ]
    )
    return "\n".join(sections)


@pytest.fixture
def isolated_loop(tmp_path, monkeypatch):
    loop_dir = tmp_path / "polish_loop"
    current_dir = loop_dir / "current"
    current_dir.mkdir(parents=True)

    status_file = loop_dir / "status.json"
    task_file = loop_dir / "task.md"
    pc_output = current_dir / "pc_output.md"
    mac_review = current_dir / "mac_review.md"
    closeout = current_dir / "closeout.ok"
    log_file = tmp_path / "orchestrator.log"

    for module in (fallback, orchestrator):
        monkeypatch.setattr(module, "LOOP_DIR", loop_dir, raising=False)
        monkeypatch.setattr(module, "STATUS_FILE", status_file, raising=False)
        monkeypatch.setattr(module, "CURRENT_DIR", current_dir, raising=False)
        monkeypatch.setattr(module, "PC_OUTPUT", pc_output, raising=False)
        monkeypatch.setattr(module, "MAC_REVIEW", mac_review, raising=False)
        monkeypatch.setattr(module, "LOG_FILE", log_file, raising=False)

    monkeypatch.setattr(orchestrator, "CLOSEOUT", closeout, raising=False)
    monkeypatch.setattr(fallback, "TASK_MD", task_file, raising=False)
    monkeypatch.setattr(fallback, "_SUPPRESS_FILE_LOGS", True, raising=False)
    monkeypatch.setattr(fallback, "_LLM_AVAILABLE", False, raising=False)

    def write_status(pass_num: int = 1, status: str = "mac_turn", block_reason=None):
        status_file.write_text(
            json.dumps(
                {
                    "pass": pass_num,
                    "status": status,
                    "task_name": "auto-104-pc-review-unit-tests",
                    "block_reason": block_reason,
                }
            )
        )

    return SimpleNamespace(
        loop_dir=loop_dir,
        current_dir=current_dir,
        status_file=status_file,
        task_file=task_file,
        pc_output=pc_output,
        mac_review=mac_review,
        closeout=closeout,
        write_status=write_status,
    )


def test_structural_review_approves_valid_output_and_writes_orchestrator_readable_review(isolated_loop, tmp_path, monkeypatch):
    changed_file = tmp_path / "claimed_change.py"
    changed_file.write_text("print('ok')\n")

    isolated_loop.write_status(pass_num=1, status="mac_turn")
    isolated_loop.task_file.write_text("verification:\n```bash\npython3 -c \"print('ok')\"\n```\n")
    isolated_loop.pc_output.write_text(
        _build_pc_output(
            pass_num=1,
            status="DONE",
            changes_block=f"- `{changed_file}` - Added focused tests.",
        )
    )
    monkeypatch.setattr(fallback, "_LLM_AVAILABLE", True, raising=False)
    monkeypatch.setattr(fallback, "_get_file_diffs", lambda changed_files: "diff --git a/file.py b/file.py", raising=False)
    monkeypatch.setattr(fallback, "ollama_call", lambda *args, **kwargs: "PASS: changes address the task", raising=False)

    verdict, passes, fails = fallback.structural_review()

    assert verdict == "APPROVED"
    assert not fails
    assert any("changed files verified on disk" in entry for entry in passes)
    assert fallback.run_review() == 0
    assert isolated_loop.closeout.exists()
    assert orchestrator.mac_review_says_approved() is True
    assert orchestrator.mac_review_says_rework() is False


def test_structural_review_rejects_missing_required_sections(isolated_loop, tmp_path):
    changed_file = tmp_path / "claimed_change.py"
    changed_file.write_text("print('ok')\n")

    isolated_loop.write_status(pass_num=1, status="mac_turn")
    isolated_loop.task_file.write_text("title: no verification block\n")
    isolated_loop.pc_output.write_text(
        _build_pc_output(
            pass_num=1,
            status="DONE",
            changes_block=f"- `{changed_file}` - Added focused tests.",
            include_reasoning=False,
        )
    )

    verdict, _, fails = fallback.structural_review()

    assert verdict == "NEEDS_REWORK"
    assert "Missing required section: REASONING:" in fails
    assert fallback.run_review() == 0
    assert orchestrator.mac_review_says_rework() is True


def test_structural_review_rejects_pass_mismatch(isolated_loop, tmp_path):
    changed_file = tmp_path / "claimed_change.py"
    changed_file.write_text("print('ok')\n")

    isolated_loop.write_status(pass_num=2, status="mac_turn")
    isolated_loop.task_file.write_text("title: no verification block\n")
    isolated_loop.pc_output.write_text(
        _build_pc_output(
            pass_num=1,
            status="DONE",
            changes_block=f"- `{changed_file}` - Added focused tests.",
        )
    )

    verdict, _, fails = fallback.structural_review()

    assert verdict == "NEEDS_REWORK"
    assert "PASS mismatch: output says 1, status says 2" in fails


def test_structural_review_rejects_blocked_status(isolated_loop, tmp_path):
    changed_file = tmp_path / "claimed_change.py"
    changed_file.write_text("print('ok')\n")

    isolated_loop.write_status(pass_num=1, status="mac_turn")
    isolated_loop.task_file.write_text("title: no verification block\n")
    isolated_loop.pc_output.write_text(
        _build_pc_output(
            pass_num=1,
            status="BLOCKED",
            changes_block=f"- `{changed_file}` - Added focused tests.",
        )
    )

    verdict, _, fails = fallback.structural_review()

    assert verdict == "NEEDS_REWORK"
    assert "STATUS: BLOCKED — builder reported it could not complete the task" in fails


def test_structural_review_rejects_when_no_claimed_changed_files_exist(isolated_loop):
    missing_file = isolated_loop.loop_dir / "missing.py"

    isolated_loop.write_status(pass_num=1, status="mac_turn")
    isolated_loop.task_file.write_text("title: no verification block\n")
    isolated_loop.pc_output.write_text(
        _build_pc_output(
            pass_num=1,
            status="DONE",
            changes_block=f"- `{missing_file}` - Claimed change that does not exist.",
        )
    )

    verdict, passes, fails = fallback.structural_review()

    assert verdict == "NEEDS_REWORK"
    assert "None of the listed changed files exist on disk" in fails
    assert any(str(missing_file) in entry for entry in passes)


def test_llm_review_unavailable_does_not_pass(monkeypatch):
    monkeypatch.setattr(fallback, "_LLM_AVAILABLE", False, raising=False)
    monkeypatch.setattr(fallback, "_get_file_diffs", lambda changed_files: "diff --git a/file.py b/file.py", raising=False)

    ok, detail = fallback._llm_code_review("summary", ["/home/openclaw/file.py"], "task")

    assert ok is False
    assert detail.startswith("REVIEW_UNAVAILABLE:")


def test_llm_review_ollama_error_does_not_pass(monkeypatch):
    monkeypatch.setattr(fallback, "_LLM_AVAILABLE", True, raising=False)
    monkeypatch.setattr(fallback, "_get_file_diffs", lambda changed_files: "diff --git a/file.py b/file.py", raising=False)

    def fail_call(*args, **kwargs):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(fallback, "ollama_call", fail_call, raising=False)

    ok, detail = fallback._llm_code_review("summary", ["/home/openclaw/file.py"], "task")

    assert ok is False
    assert detail.startswith("REVIEW_UNAVAILABLE:")
    assert "model unavailable" in detail


def test_llm_review_empty_response_does_not_pass(monkeypatch):
    monkeypatch.setattr(fallback, "_LLM_AVAILABLE", True, raising=False)
    monkeypatch.setattr(fallback, "_get_file_diffs", lambda changed_files: "diff --git a/file.py b/file.py", raising=False)
    monkeypatch.setattr(fallback, "ollama_call", lambda *args, **kwargs: "", raising=False)

    ok, detail = fallback._llm_code_review("summary", ["/home/openclaw/file.py"], "task")

    assert ok is False
    assert detail == "REVIEW_UNAVAILABLE: Ollama returned empty response"


def test_llm_review_ambiguous_response_does_not_pass(monkeypatch):
    monkeypatch.setattr(fallback, "_LLM_AVAILABLE", True, raising=False)
    monkeypatch.setattr(fallback, "_get_file_diffs", lambda changed_files: "diff --git a/file.py b/file.py", raising=False)
    monkeypatch.setattr(fallback, "ollama_call", lambda *args, **kwargs: "Looks mostly fine to me.", raising=False)

    ok, detail = fallback._llm_code_review("summary", ["/home/openclaw/file.py"], "task")

    assert ok is False
    assert detail.startswith("INSUFFICIENT_EVIDENCE:")


def test_llm_review_clear_pass_and_fail_behavior(monkeypatch):
    monkeypatch.setattr(fallback, "_LLM_AVAILABLE", True, raising=False)
    monkeypatch.setattr(fallback, "_get_file_diffs", lambda changed_files: "diff --git a/file.py b/file.py", raising=False)

    monkeypatch.setattr(fallback, "ollama_call", lambda *args, **kwargs: "PASS: changes address the task", raising=False)
    ok, detail = fallback._llm_code_review("summary", ["/home/openclaw/file.py"], "task")
    assert ok is True
    assert detail == "LLM review: PASS: changes address the task"

    monkeypatch.setattr(fallback, "ollama_call", lambda *args, **kwargs: "FAIL: syntax error introduced", raising=False)
    ok, detail = fallback._llm_code_review("summary", ["/home/openclaw/file.py"], "task")
    assert ok is False
    assert detail == "LLM review: FAIL: syntax error introduced"


def test_structural_review_blocks_on_llm_review_unavailable(isolated_loop, tmp_path, monkeypatch):
    changed_file = tmp_path / "claimed_change.py"
    changed_file.write_text("print('ok')\n")

    isolated_loop.write_status(pass_num=1, status="mac_turn")
    isolated_loop.task_file.write_text("title: no verification block\n")
    isolated_loop.pc_output.write_text(
        _build_pc_output(
            pass_num=1,
            status="DONE",
            changes_block=f"- `{changed_file}` - Added focused tests.",
        )
    )
    monkeypatch.setattr(fallback, "_LLM_AVAILABLE", True, raising=False)
    monkeypatch.setattr(fallback, "_get_file_diffs", lambda changed_files: "diff --git a/file.py b/file.py", raising=False)
    monkeypatch.setattr(fallback, "ollama_call", lambda *args, **kwargs: "", raising=False)

    verdict, _, fails = fallback.structural_review()

    assert verdict == "NEEDS_REWORK"
    assert "REVIEW_UNAVAILABLE: Ollama returned empty response" in fails


def test_extract_changed_files_strips_trailing_colon():
    """Regression: dash-prefixed lines like '- /path/file.py: description' must not
    retain the trailing colon in the parsed path."""
    content = (
        "PASS: 1\nSTATUS: DONE\n\n"
        "CHANGES:\n"
        "- /home/openclaw/polish_loop/orchestrator.py: added cascade guard\n"
        "- /home/openclaw/chief_watcher_brain.py — extracted helper\n"
        "\n"
        "REASONING:\nWhy.\n"
    )
    paths = fallback._extract_changed_files(content)
    assert "/home/openclaw/polish_loop/orchestrator.py" in paths, f"colon-separated path missing: {paths}"
    assert "/home/openclaw/chief_watcher_brain.py" in paths, f"em-dash path missing: {paths}"
    # Must not contain trailing colon
    for p in paths:
        assert not p.endswith(":"), f"trailing colon not stripped: {p}"


def test_needs_review_true_for_planner_runner_missing_block(isolated_loop):
    isolated_loop.write_status(status="blocked", block_reason="planner_runner_missing")
    assert fallback.needs_review() is True


def test_needs_review_false_for_planner_timeout_block(isolated_loop):
    isolated_loop.write_status(status="blocked", block_reason="planner_timeout_no_review")
    assert fallback.needs_review() is True
