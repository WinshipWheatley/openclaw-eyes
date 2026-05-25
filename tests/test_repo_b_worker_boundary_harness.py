import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import repo_b_worker_boundary_harness as harness
from scripts.export_repo_b_worker_boundary_harness import main as export_main


FIXED_NOW = "2026-05-25T21:00:00+00:00"


def _payload() -> dict:
    return harness.build_payload(generated_at=FIXED_NOW)


def _candidate(payload: dict, candidate_id: str) -> dict:
    return next(row for row in payload["worker_candidates"] if row["candidate_id"] == candidate_id)


def _readback(payload: dict, candidate_id: str) -> dict:
    return next(row for row in payload["worker_output_readbacks"] if row["worker_candidate_ref"] == candidate_id)


def test_required_models_exist():
    for name in [
        "RepoBWorkerBoundaryHarness",
        "LegacyWorkerCandidate",
        "WorkerInputPackage",
        "WorkerOutputReadback",
        "WorkerTimeoutPolicy",
        "WorkerAuthorityBoundary",
        "WorkerQuarantineBlocker",
        "RepoBWorkerBoundaryElioperatorReport",
    ]:
        assert hasattr(harness, name)


def test_worker_postures_and_invocation_modes_exist():
    assert "WRAP_AS_WORKER" in harness.RECOMMENDED_POSTURES
    assert "BRIDGE_READ_ONLY" in harness.RECOMMENDED_POSTURES
    assert "DRAFT_ONLY" in harness.RECOMMENDED_POSTURES
    assert "COMPUTE_ONLY" in harness.RECOMMENDED_POSTURES
    assert "UNSAFE_DO_NOT_CONNECT" in harness.RECOMMENDED_POSTURES
    assert "FIXTURE_ONLY" in harness.INVOCATION_MODES
    assert "READ_ONLY_BRIDGE" in harness.INVOCATION_MODES
    assert "DRAFT_ONLY_BRIDGE" in harness.INVOCATION_MODES
    assert "COMPUTE_ONLY_BRIDGE" in harness.INVOCATION_MODES


def test_chief_example_exists_as_offline_candidate_worker():
    payload = _payload()
    chief = _candidate(payload, "repo_b_candidate_chief_offline_reasoning")
    readback = _readback(payload, chief["candidate_id"])

    assert chief["worker_family"] == "CHIEF_ROUTER"
    assert chief["recommended_posture"] == "WRAP_AS_WORKER"
    assert chief["allowed_invocation_mode"] == "FIXTURE_ONLY"
    assert "Telegram output" in " ".join(chief["forbidden_invocation_modes"])
    assert readback["status"] == "FIXTURE_READBACK_READY"


def test_cassandra_draft_only_example_exists():
    payload = _payload()
    cassandra = _candidate(payload, "repo_b_candidate_cassandra_draft_only")

    assert cassandra["worker_family"] == "CASSANDRA_DRAFT"
    assert cassandra["recommended_posture"] == "DRAFT_ONLY"
    assert cassandra["allowed_invocation_mode"] == "DRAFT_ONLY_BRIDGE"
    assert cassandra["required_wrapper"] == "cassandra_draft_worker_wrapper.py"
    assert "send" in " ".join(cassandra["forbidden_invocation_modes"]).lower()


def test_google_read_only_broker_example_exists():
    payload = _payload()
    google = _candidate(payload, "repo_b_candidate_google_read_broker")

    assert google["worker_family"] == "GOOGLE_READ_BROKER"
    assert google["recommended_posture"] == "BRIDGE_READ_ONLY"
    assert google["allowed_invocation_mode"] == "READ_ONLY_BRIDGE"
    assert google["required_wrapper"] == "google_broker_readonly_wrapper.py"
    assert "Gmail send" in google["forbidden_invocation_modes"]


def test_cpa_budget_compute_example_exists():
    payload = _payload()
    cpa = _candidate(payload, "repo_b_candidate_cpa_budget_compute")

    assert cpa["worker_family"] == "CPA_BUDGET"
    assert cpa["recommended_posture"] == "COMPUTE_ONLY"
    assert cpa["allowed_invocation_mode"] == "COMPUTE_ONLY_BRIDGE"
    assert "bank login" in cpa["forbidden_invocation_modes"]


def test_niles_music_creative_example_exists():
    payload = _payload()
    niles = _candidate(payload, "repo_b_candidate_niles_music_creative")

    assert niles["worker_family"] == "NILES_MUSIC_CREATIVE"
    assert niles["recommended_posture"] == "WRAP_AS_WORKER"
    assert "DAW mutation" in niles["forbidden_invocation_modes"]


def test_telegram_outbound_and_watchdog_repair_are_blocked():
    payload = _payload()
    telegram = _candidate(payload, "repo_b_candidate_telegram_listener_intake")
    watchdog = _candidate(payload, "repo_b_candidate_watchdog_repair")
    telegram_readback = _readback(payload, telegram["candidate_id"])
    watchdog_readback = _readback(payload, watchdog["candidate_id"])
    blockers = {row["blocker_type"] for row in payload["worker_quarantine_blockers"]}

    assert telegram["recommended_posture"] == "REFERENCE_ONLY"
    assert telegram["allowed_invocation_mode"] == "NONE"
    assert telegram_readback["status"] == "BLOCKED_UNSAFE_WORKER"
    assert watchdog["recommended_posture"] == "UNSAFE_DO_NOT_CONNECT"
    assert watchdog_readback["status"] == "BLOCKED_UNSAFE_WORKER"
    assert "TELEGRAM_OUTBOUND_ATTEMPTED" in blockers
    assert "WATCHDOG_REPAIR_ATTEMPTED" in blockers


def test_timeout_policy_exists_and_requires_terminal_readback():
    payload = _payload()
    policy = payload["worker_timeout_policy"]

    assert policy["default_timeout_ms"] == 5000
    assert policy["kill_on_timeout"] is True
    assert policy["timeout_readback_required"] is True


def test_authority_boundaries_default_false():
    payload = _payload()

    assert payload["machine_proof"]["all_live_authority_false"] is True
    for key, value in payload["authority_boundary"].items():
        assert value is False, key
    for boundary in payload["worker_authority_boundaries"]:
        assert boundary["external_action_allowed"] is False
        assert boundary["network_allowed"] is False
        assert boundary["credential_handling_allowed"] is False
        assert boundary["raw_body_ingestion_allowed"] is False
        assert boundary["file_mutation_allowed"] is False
        assert boundary["send_allowed"] is False
        assert boundary["submit_allowed"] is False


def test_input_packages_are_scoped_and_exclude_sensitive_material():
    payload = _payload()
    for package in payload["worker_input_packages"]:
        exclusions = " ".join(package["excluded_context"]).lower()
        flags = package["environment_flags"]
        assert package["source_context_package_ref"]
        assert "raw credentials" in exclusions
        assert "raw private bodies" in exclusions
        assert flags["OPENCLAW_SEND_ALLOWED"] == "0"
        assert flags["OPENCLAW_CREDENTIALS_ALLOWED"] == "0"
        assert flags["OPENCLAW_RAW_BODY_ALLOWED"] == "0"
        assert package["timeout_ms"] == 5000


def test_export_writes_json_and_operator_markdown(tmp_path, capsys):
    assert export_main(["--export-root", str(tmp_path), "--generated-at", FIXED_NOW, "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads((tmp_path / harness.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (tmp_path / harness.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert summary["candidate_count"] >= 7
    assert payload["schema_version"] == harness.SCHEMA_VERSION
    assert "Repo B Worker Boundary Harness" in operator
    assert "No Repo B worker executed" in operator


def test_generated_outputs_have_no_credentials_or_private_bodies(tmp_path):
    payload = _payload()
    harness.write_exports(payload, tmp_path)
    text = "\n".join(path.read_text(encoding="utf-8") for path in tmp_path.iterdir())

    assert "GMAIL_APP_PASSWORD" not in text
    assert "CASSANDRA_BOT_TOKEN" not in text
    assert "SMTP_PASSWORD" not in text
    assert "BEGIN OPENSSH PRIVATE KEY" not in text
    assert "raw body value" not in text.lower()
    assert not __import__("re").search(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", text)


def test_source_does_not_run_repo_b_or_unsafe_live_calls():
    source = Path("repo_b_worker_boundary_harness.py").read_text(encoding="utf-8").lower()
    forbidden = [
        "subprocess.run",
        "from chief_",
        "import chief_",
        "from cassandra_",
        "import cassandra_",
        "google_access_broker.call",
        "send_message(",
        "request_approval(",
        "smtplib",
        "requests.",
        "httpx.",
        "urllib.request",
        "os.system",
        "shell=true",
    ]
    for token in forbidden:
        assert token not in source
