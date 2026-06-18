from pathlib import Path


GREEN_GATE = Path("scripts/green_gate.sh")


def test_green_gate_serializes_full_suite_before_clean_room_checkout():
    script = GREEN_GATE.read_text(encoding="utf-8")

    assert "OPENCLAW_GREEN_GATE_LOCK" in script
    assert 'exec 9>"$LOCK_FILE"' in script
    assert "flock -n 9" in script
    assert "flock 9" in script
    assert "acquired full-suite lock" in script

    lock_open = script.index('exec 9>"$LOCK_FILE"')
    nonblocking_lock = script.index("flock -n 9")
    clean_checkout = script.index('echo "[green-gate] clean-room checkout of $REF ..."')
    worktree_add = script.index('git -C "$REPO" worktree add --detach "$WT" "$REF"')
    pytest_run = script.index('OPENCLAW_TEST_MODE=1 OPENCLAW_SEND_HOLD=1 "$VENV" -m pytest -q')

    assert lock_open < nonblocking_lock < clean_checkout < worktree_add < pytest_run


def test_green_gate_lock_path_defaults_to_shared_tmp_lock():
    script = GREEN_GATE.read_text(encoding="utf-8")

    assert 'LOCK_FILE="${OPENCLAW_GREEN_GATE_LOCK:-${TMPDIR:-/tmp}/openclaw-green-gate.lock}"' in script
    assert 'mkdir -p "$LOCK_DIR"' in script
