import ast
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import cross_lane_reusable_block_registry_contract as lane_contract
import cross_surface_artifact_handoff_registry_contract as surface_contract
import generated_read_model_files
import openclaw_substrate_utils as utils
import operator_solve_path_decision_node_contract as solve_contract
import operator_work_mode_schema_bandwidth_policy as work_contract


def test_stable_json_is_deterministic_sorted_indented_and_newlined():
    payload = {"b": 1, "a": {"d": 4, "c": 3}}

    first = utils.stable_json(payload)
    second = utils.stable_json(payload)

    assert first == second
    assert first == '{\n  "a": {\n    "c": 3,\n    "d": 4\n  },\n  "b": 1\n}\n'
    assert first.endswith("\n")
    assert json.loads(first) == payload


def test_utc_now_returns_utc_iso_seconds_without_microseconds():
    value = utils.utc_now()
    parsed = datetime.fromisoformat(value)

    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timezone.utc.utcoffset(parsed)
    assert parsed.microsecond == 0
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00", value)


def test_dataclass_to_dict_uses_standard_asdict():
    @dataclass(frozen=True)
    class Example:
        name: str
        count: int

    assert utils.dataclass_to_dict(Example("alpha", 2)) == {"name": "alpha", "count": 2}


def test_sha256_file_is_integrity_only_and_matches_expected_digest(tmp_path):
    payload = tmp_path / "payload.txt"
    payload.write_text("openclaw\n", encoding="utf-8")

    assert utils.sha256_file(payload) == "fccf76c16e249da322d73865f57ff8a468b008aa1f5dac74aab94e9eb539b1e1"


def test_helper_module_imports_only_standard_library_modules():
    source = Path(utils.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])

    assert imported_roots <= {"__future__", "dataclasses", "datetime", "hashlib", "json", "pathlib", "typing"}


def test_migrated_modules_use_shared_helpers():
    assert work_contract.stable_json is utils.stable_json
    assert solve_contract.stable_json is utils.stable_json
    assert surface_contract.stable_json is utils.stable_json
    assert lane_contract.stable_json is utils.stable_json

    assert work_contract.utc_now is utils.utc_now
    assert solve_contract.utc_now is utils.utc_now
    assert surface_contract.utc_now is utils.utc_now
    assert lane_contract.utc_now is utils.utc_now

    assert generated_read_model_files.sha256_file is utils.sha256_file


def test_migrated_module_fixed_timestamp_exports_remain_deterministic(tmp_path):
    fixed = "2026-05-25T00:00:00+00:00"
    payloads = [
        work_contract.build_operator_work_mode_schema_bandwidth_policy(generated_at=fixed),
        solve_contract.build_operator_solve_path_decision_node_contract(generated_at=fixed),
        surface_contract.build_cross_surface_artifact_handoff_registry_contract(generated_at=fixed),
        lane_contract.build_cross_lane_reusable_block_registry_contract(generated_at=fixed),
    ]

    for index, payload in enumerate(payloads):
        first = utils.stable_json(payload)
        second = utils.stable_json(payload)
        path = tmp_path / f"payload_{index}.json"
        path.write_text(first, encoding="utf-8")

        assert first == second
        parsed = json.loads(path.read_text(encoding="utf-8"))
        assert parsed["schema_version"] == payload["schema_version"]
        assert parsed["read_model_id"] == payload["read_model_id"]
        proof = payload["machine_proof"]
        assert proof.get("all_live_authority_flags_false", proof.get("all_authority_flags_false")) is True


def test_generated_outputs_have_no_raw_pii_secrets_or_private_bodies(tmp_path):
    fixed = "2026-05-25T00:00:00+00:00"
    outputs = {
        "work.json": work_contract.stable_json(
            work_contract.build_operator_work_mode_schema_bandwidth_policy(generated_at=fixed)
        ),
        "solve.json": solve_contract.stable_json(
            solve_contract.build_operator_solve_path_decision_node_contract(generated_at=fixed)
        ),
        "surface.json": surface_contract.stable_json(
            surface_contract.build_cross_surface_artifact_handoff_registry_contract(generated_at=fixed)
        ),
        "lane.json": lane_contract.stable_json(
            lane_contract.build_cross_lane_reusable_block_registry_contract(generated_at=fixed)
        ),
    }
    for name, text in outputs.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    text = "\n".join(path.read_text(encoding="utf-8") for path in tmp_path.iterdir())

    assert "actual secret value" not in text.lower()
    assert "raw private body value" not in text.lower()
    assert "credential value" not in text.lower()
    assert "token value" not in text.lower()
    assert "raw password value" not in text.lower()
    assert "AKIA" not in text
    assert not re.search(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", text)
