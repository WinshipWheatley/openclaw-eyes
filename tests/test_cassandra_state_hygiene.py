from __future__ import annotations

import json
import shutil
import stat
from pathlib import Path

import cassandra_state_hygiene as hygiene
import pytest


RAW_CUE = "CASS-DEEP-07 compact recovery check: answer one sentence only."


def _dirty_state() -> dict:
    return {
        "human_cues": [
            {"cue": "tired", "at": "2026-07-11 12:00:00"},
            {"cue": RAW_CUE, "at": "2026-07-11 12:01:00"},
        ],
        "project_mood": "degraded recovery health probe",
        "recurring_concerns": ["invoice timing", RAW_CUE],
        "session_fact_overrides": {
            "capital_hilton": {
                "summary": RAW_CUE,
                "source_text": RAW_CUE,
                "at": "2026-07-11T12:00:00+00:00",
            },
            "live_arts_md": {
                "summary": "Live Arts payment remains unconfirmed.",
                "at": "2026-07-11T12:00:00+00:00",
            },
            RAW_CUE: {"summary": "unsafe dynamic key"},
        },
        "future_prompt_items": [
            {"text": "safe operator preference"},
            {"text": RAW_CUE},
        ],
        "chirp_log": [{"type": "status", "at": "2026-07-11"}],
        "pending_income_followup": {"entry_id": "income-1", "amount": 1095.0},
        "unrelated_archive": {"verbatim": RAW_CUE},
    }


def test_schema_aware_sanitizer_quarantines_only_prompt_fed_leaves() -> None:
    dirty = _dirty_state()

    result = hygiene.sanitize_cassandra_state(dirty, stage="assembly")

    assert result.changed is True
    assert result.state["human_cues"] == [
        {"cue": "tired", "at": "2026-07-11 12:00:00"}
    ]
    assert result.state["project_mood"] == "neutral"
    assert result.state["recurring_concerns"] == ["invoice timing"]
    assert "capital_hilton" not in result.state["session_fact_overrides"]
    assert result.state["session_fact_overrides"]["live_arts_md"]["summary"] == (
        "Live Arts payment remains unconfirmed."
    )
    assert RAW_CUE not in result.state["session_fact_overrides"]
    assert result.state["future_prompt_items"] == [
        {"text": "safe operator preference"}
    ]
    assert result.state["chirp_log"] == dirty["chirp_log"]
    assert result.state["pending_income_followup"] == dirty["pending_income_followup"]
    # Schema-aware means unrelated archival state is not globally scrubbed.
    assert result.state["unrelated_archive"] == dirty["unrelated_archive"]
    assert dirty["human_cues"][1]["cue"] == RAW_CUE


def test_receipt_contains_hashes_and_reason_codes_but_never_raw_cues_or_dynamic_keys() -> None:
    result = hygiene.sanitize_cassandra_state(_dirty_state(), stage="assembly")
    receipt_json = json.dumps(result.receipt.to_dict(), sort_keys=True)

    assert RAW_CUE not in receipt_json
    assert "CASS-DEEP" not in receipt_json
    assert result.receipt.quarantined_count >= 6
    assert result.receipt.raw_values_included is False
    assert all(finding.leaf_sha256.startswith("sha256:") for finding in result.receipt.findings)
    assert any("<key#" in finding.field_path for finding in result.receipt.findings)


def test_future_prompt_lists_reset_wrong_types_and_sanitize_nested_dynamic_fields() -> None:
    dynamic_root = f"{RAW_CUE}_prompt_items"
    dynamic_nested = f"{RAW_CUE}_context_items"
    nested_wrong_type = "next_turn_instructions"
    state = {
        dynamic_root: {"wrong": "shape"},
        "container": {
            dynamic_nested: [{"text": RAW_CUE}],
            "nested_prompt_items": [
                {"text": RAW_CUE},
                {nested_wrong_type: {"wrong": "shape"}},
                {"text": "safe operator preference"},
            ]
        },
    }

    result = hygiene.sanitize_cassandra_state(state, stage="assembly")

    assert dynamic_root not in result.state
    assert dynamic_nested not in result.state["container"]
    nested = result.state["container"]["nested_prompt_items"]
    assert nested == [
        {nested_wrong_type: []},
        {"text": "safe operator preference"},
    ]
    receipt_json = json.dumps(result.receipt.to_dict(), sort_keys=True)
    assert RAW_CUE not in receipt_json
    assert dynamic_root not in receipt_json
    assert dynamic_nested not in receipt_json
    assert nested_wrong_type not in receipt_json
    assert "schema_type_mismatch" in receipt_json
    assert "<key#" in receipt_json


def test_second_sanitization_is_idempotent() -> None:
    first = hygiene.sanitize_cassandra_state(_dirty_state(), stage="assembly")
    second = hygiene.sanitize_cassandra_state(first.state, stage="assembly")

    assert second.changed is False
    assert second.state == first.state
    assert second.receipt.quarantined_count == 0
    assert second.receipt.source_state_sha256 == second.receipt.sanitized_state_sha256


def test_classifier_failure_drops_selected_leaf_without_echoing_exception_or_value() -> None:
    def failed_classifier(_text: str):
        raise RuntimeError(f"offline while reading {RAW_CUE}")

    result = hygiene.sanitize_cassandra_state(
        {"human_cues": [{"cue": RAW_CUE, "at": "now"}], "safe": RAW_CUE},
        stage="assembly",
        classifier=failed_classifier,
    )

    assert result.state["human_cues"] == []
    assert result.state["safe"] == RAW_CUE
    encoded = json.dumps(result.receipt.to_dict(), sort_keys=True)
    assert RAW_CUE not in encoded
    assert "offline while reading" not in encoded
    assert "classifier_unavailable" in encoded


def test_load_repairs_dirty_file_with_exact_content_addressed_backup_and_receipt(
    tmp_path: Path,
) -> None:
    path = tmp_path / "cassandra_state.json"
    original = json.dumps(_dirty_state(), indent=2).encode("utf-8")
    path.write_bytes(original)

    loaded = hygiene.load_sanitized_cassandra_state(path, default_factory=dict)

    assert RAW_CUE not in json.dumps(loaded.state["session_fact_overrides"])
    assert loaded.backup_path is not None
    assert loaded.backup_path.read_bytes() == original
    assert loaded.receipt_path is not None and loaded.receipt_path.is_file()
    assert RAW_CUE not in loaded.receipt_path.read_text(encoding="utf-8")
    assert json.loads(loaded.receipt_path.read_text(encoding="utf-8"))["status"] == (
        "committed"
    )
    assert json.loads(path.read_text(encoding="utf-8")) == loaded.state
    assert list(tmp_path.glob("*.tmp")) == []


def test_clean_second_load_creates_no_second_backup_or_receipt(tmp_path: Path) -> None:
    path = tmp_path / "cassandra_state.json"
    path.write_text(json.dumps(_dirty_state()), encoding="utf-8")
    first = hygiene.load_sanitized_cassandra_state(path, default_factory=dict)
    backup_count = len(list((tmp_path / ".cassandra_state_quarantine" / "backups").glob("*.json")))
    receipt_count = len(list((tmp_path / ".cassandra_state_quarantine" / "receipts").glob("*.json")))

    second = hygiene.load_sanitized_cassandra_state(path, default_factory=dict)

    assert first.receipt is not None
    assert second.receipt is not None
    assert second.receipt.quarantined_count == 0
    assert len(list((tmp_path / ".cassandra_state_quarantine" / "backups").glob("*.json"))) == backup_count
    assert len(list((tmp_path / ".cassandra_state_quarantine" / "receipts").glob("*.json"))) == receipt_count


def test_restored_dirty_backup_is_sanitized_again_and_forensic_bytes_are_reused(
    tmp_path: Path,
) -> None:
    path = tmp_path / "cassandra_state.json"
    path.write_text(json.dumps(_dirty_state(), sort_keys=True), encoding="utf-8")
    first = hygiene.load_sanitized_cassandra_state(path, default_factory=dict)
    assert first.backup_path is not None
    first_backup = first.backup_path
    shutil.copyfile(first_backup, path)

    restored = hygiene.load_sanitized_cassandra_state(path, default_factory=dict)

    assert restored.backup_path == first_backup
    assert restored.backup_reused is True
    assert RAW_CUE not in json.dumps(restored.state["session_fact_overrides"])
    receipt_files = list((tmp_path / ".cassandra_state_quarantine" / "receipts").glob("*.json"))
    assert len(receipt_files) == 2


def test_save_never_places_contaminated_candidate_in_canonical_state(tmp_path: Path) -> None:
    path = tmp_path / "cassandra_state.json"
    path.write_text(json.dumps({"human_cues": []}), encoding="utf-8")

    saved = hygiene.save_sanitized_cassandra_state(path, _dirty_state())

    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert RAW_CUE not in json.dumps(on_disk["session_fact_overrides"])
    assert saved.receipt.quarantined_count >= 6
    assert saved.backup_path is not None
    assert RAW_CUE in saved.backup_path.read_text(encoding="utf-8")


@pytest.mark.parametrize("operation", ["load", "save"])
def test_receipt_is_prepared_before_canonical_replace_then_committed(
    tmp_path: Path,
    monkeypatch,
    operation: str,
) -> None:
    path = tmp_path / f"{operation}.json"
    original_atomic_write = hygiene._atomic_write
    writes: list[str] = []

    def ordered_atomic_write(write_path: Path, payload: bytes) -> None:
        if write_path == path:
            writes.append("canonical")
        elif write_path.parent.name == "backups":
            writes.append("backup")
        elif write_path.parent.name == "receipts":
            writes.append(json.loads(payload.decode("utf-8"))["status"])
        original_atomic_write(write_path, payload)

    monkeypatch.setattr(hygiene, "_atomic_write", ordered_atomic_write)
    if operation == "load":
        path.write_text(json.dumps(_dirty_state()), encoding="utf-8")
        hygiene.load_sanitized_cassandra_state(path, default_factory=dict)
    else:
        hygiene.save_sanitized_cassandra_state(path, _dirty_state())

    assert writes == ["backup", "prepared", "canonical", "committed"]


def test_post_replace_commit_failure_leaves_durable_prepared_receipt(
    tmp_path: Path,
    monkeypatch,
) -> None:
    path = tmp_path / "cassandra_state.json"
    original_atomic_write = hygiene._atomic_write
    writes: list[str] = []

    def fail_commit(write_path: Path, payload: bytes) -> None:
        if write_path == path:
            writes.append("canonical")
        elif write_path.parent.name == "backups":
            writes.append("backup")
        elif write_path.parent.name == "receipts":
            status = json.loads(payload.decode("utf-8"))["status"]
            writes.append(status)
            if status == "committed":
                raise OSError("simulated receipt commit failure")
        original_atomic_write(write_path, payload)

    monkeypatch.setattr(hygiene, "_atomic_write", fail_commit)

    with pytest.raises(OSError, match="receipt commit failure"):
        hygiene.save_sanitized_cassandra_state(path, _dirty_state())

    assert writes == ["backup", "prepared", "canonical", "committed"]
    canonical = json.loads(path.read_text(encoding="utf-8"))
    assert RAW_CUE not in json.dumps(canonical["session_fact_overrides"])
    assert RAW_CUE not in json.dumps(canonical["human_cues"])
    # Archival, non-prompt state is intentionally outside this schema seam.
    assert canonical["unrelated_archive"]["verbatim"] == RAW_CUE
    receipt_files = list(
        (tmp_path / ".cassandra_state_quarantine" / "receipts").glob("*.json")
    )
    assert len(receipt_files) == 1
    prepared = json.loads(receipt_files[0].read_text(encoding="utf-8"))
    assert prepared["status"] == "prepared"
    assert prepared["committed_at"] is None
    assert RAW_CUE not in json.dumps(prepared, sort_keys=True)


def test_clean_save_preserves_and_receipts_dirty_existing_canonical(
    tmp_path: Path,
) -> None:
    path = tmp_path / "cassandra_state.json"
    existing = json.dumps(_dirty_state(), sort_keys=True).encode("utf-8")
    path.write_bytes(existing)
    clean_candidate = {
        "human_cues": [],
        "project_mood": "neutral",
        "recurring_concerns": [],
        "session_fact_overrides": {},
    }

    saved = hygiene.save_sanitized_cassandra_state(path, clean_candidate)

    assert json.loads(path.read_text(encoding="utf-8")) == clean_candidate
    assert saved.backup_path is not None
    assert saved.backup_path.read_bytes() == existing
    assert saved.receipt_path is not None
    receipt = json.loads(saved.receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"] == "committed"
    assert [item["role"] for item in receipt["backups"]] == [
        "canonical_before_save"
    ]
    assert RAW_CUE not in json.dumps(receipt, sort_keys=True)


def test_dirty_existing_and_dirty_candidate_are_preserved_as_separate_inputs(
    tmp_path: Path,
) -> None:
    path = tmp_path / "cassandra_state.json"
    existing_state = _dirty_state()
    existing_bytes = json.dumps(existing_state, sort_keys=True).encode("utf-8")
    path.write_bytes(existing_bytes)
    candidate = _dirty_state()
    candidate["human_cues"].append({"cue": RAW_CUE, "at": "later"})

    saved = hygiene.save_sanitized_cassandra_state(path, candidate)

    backups = list(
        (tmp_path / ".cassandra_state_quarantine" / "backups").glob("*.json")
    )
    assert len(backups) == 2
    assert saved.receipt_path is not None
    receipt = json.loads(saved.receipt_path.read_text(encoding="utf-8"))
    assert [item["role"] for item in receipt["backups"]] == [
        "canonical_before_save",
        "candidate",
    ]
    assert {item["sha256"] for item in receipt["backups"]} == {
        "sha256:" + item.stem for item in backups
    }
    assert RAW_CUE not in json.dumps(receipt, sort_keys=True)


def test_canonical_parent_is_not_chmodded_and_hygiene_artifacts_are_private(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state_parent = tmp_path / "operator-owned"
    state_parent.mkdir(mode=0o755)
    state_parent.chmod(0o755)
    path = state_parent / "cassandra_state.json"
    path.write_text(json.dumps(_dirty_state()), encoding="utf-8")
    original_chmod = Path.chmod
    chmod_calls: list[tuple[Path, int]] = []

    def chmod_spy(chmod_path: Path, mode: int, *args, **kwargs) -> None:
        chmod_calls.append((chmod_path, mode))
        original_chmod(chmod_path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "chmod", chmod_spy)

    loaded = hygiene.load_sanitized_cassandra_state(path, default_factory=dict)

    assert stat.S_IMODE(state_parent.stat().st_mode) == 0o755
    assert all(chmod_path != state_parent for chmod_path, _mode in chmod_calls)
    lock_path = state_parent / ".cassandra_state.json.hygiene.lock"
    assert stat.S_IMODE(lock_path.stat().st_mode) == 0o600
    quarantine = state_parent / ".cassandra_state_quarantine"
    for directory in [quarantine, quarantine / "backups", quarantine / "receipts"]:
        assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert loaded.backup_path is not None
    assert loaded.receipt_path is not None
    assert stat.S_IMODE(loaded.backup_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(loaded.receipt_path.stat().st_mode) == 0o600


def test_missing_file_defaults_are_deep_copied_between_loads(tmp_path: Path) -> None:
    path = tmp_path / "missing.json"
    default = {"human_cues": [], "session_fact_overrides": {}}

    first = hygiene.load_sanitized_cassandra_state(path, default_factory=lambda: default)
    first.state["human_cues"].append({"cue": "tired"})
    second = hygiene.load_sanitized_cassandra_state(path, default_factory=lambda: default)

    assert second.state["human_cues"] == []
    assert default["human_cues"] == []


def test_corrupt_json_is_backed_up_repaired_and_receipted_without_raw_echo(
    tmp_path: Path,
) -> None:
    path = tmp_path / "cassandra_state.json"
    corrupt = b'{"human_cues": ["CASS-DEEP-07"'
    path.write_bytes(corrupt)

    loaded = hygiene.load_sanitized_cassandra_state(
        path,
        default_factory=lambda: {"human_cues": [], "session_fact_overrides": {}},
    )

    assert loaded.backup_path is not None
    assert loaded.backup_path.read_bytes() == corrupt
    assert loaded.receipt_path is not None
    receipt_text = loaded.receipt_path.read_text(encoding="utf-8")
    assert "invalid_json" in receipt_text
    assert "CASS-DEEP" not in receipt_text
    assert json.loads(path.read_text(encoding="utf-8")) == loaded.state
    assert loaded.receipt.changed is True


def test_cassandra_load_and_context_assembly_use_the_same_sanitizer(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import cassandra_brain

    path = tmp_path / "cassandra_state.json"
    path.write_text(json.dumps(_dirty_state()), encoding="utf-8")
    monkeypatch.setattr(cassandra_brain, "_STATE_PATH", path)

    loaded = cassandra_brain.load_state()
    snapshot = cassandra_brain.build_context_snapshot(_dirty_state())

    assert RAW_CUE not in json.dumps(loaded["session_fact_overrides"])
    assert RAW_CUE not in snapshot
    assert "Live Arts payment remains unconfirmed" in snapshot
    assert "invoice timing" in snapshot
    assert list((tmp_path / ".cassandra_state_quarantine" / "backups").glob("*.json"))


def test_direct_finance_override_lookup_cannot_bypass_state_hygiene(monkeypatch) -> None:
    import cassandra_brain

    monkeypatch.setattr(cassandra_brain, "detect_finance_status_intent", lambda _text: True)
    monkeypatch.setattr(
        cassandra_brain,
        "get_finance_status_answer",
        lambda _text: "Capital Hilton payment remains unconfirmed.",
    )

    reply = cassandra_brain._handle_finance_status_request(
        "any sign of the hilton payment landing yet?",
        _dirty_state(),
    )

    assert reply == (
        "Stored finance read-model says (not live-confirmed): "
        "Capital Hilton payment remains unconfirmed. If that's stale, tell me what to change."
    )
    assert RAW_CUE not in reply
