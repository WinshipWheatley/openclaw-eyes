from __future__ import annotations

import ast
import inspect
from pathlib import Path

import service_inventory_audit
from service_inventory_audit import build_service_inventory_audit


REPO_ROOT = Path(__file__).resolve().parents[1]
FREEZE_DOC = REPO_ROOT / "docs" / "operations" / "OPENCLAW_SERVICE_MANAGEMENT_FREEZE.md"
SYSTEMD_USER_DIR = REPO_ROOT / "systemd" / "user"
DASHBOARD_GEN = REPO_ROOT / "dashboard_gen.py"
DRIFT_CONTROL_SCANNER = REPO_ROOT / "drift_control_scanner.py"
VALIDATION_MAP = REPO_ROOT / "docs" / "testing" / "VALIDATION_MAP.md"
INSTALLER_AND_LAUNCHER_PATHS = (
    REPO_ROOT / "scripts" / "install_openclaw_stack.sh",
    REPO_ROOT / "scripts" / "install_hermes_gateway_service.sh",
    REPO_ROOT / "scripts" / "start_all.sh",
    REPO_ROOT / "start_chief.sh",
    REPO_ROOT / "start_openclaw_brains.sh",
)

DRIFT_CONTROL_UNITS = (
    "openclaw-drift-control-scan.timer",
    "openclaw-drift-control-scan.service",
)


def _freeze_text() -> str:
    return FREEZE_DOC.read_text(encoding="utf-8")


def _scheduler_report() -> dict[str, object]:
    return build_service_inventory_audit(repo_root=REPO_ROOT)["drift_control_scheduler"]


def test_no_drift_control_systemd_templates_are_present() -> None:
    template_names = {path.name for path in SYSTEMD_USER_DIR.iterdir() if path.is_file()}

    for unit_name in DRIFT_CONTROL_UNITS:
        assert f"{unit_name}.in" not in template_names


def test_repo_sources_record_dashboard_cron_scheduler_path_without_claiming_owner() -> None:
    dashboard_source = DASHBOARD_GEN.read_text(encoding="utf-8")
    scanner_source = DRIFT_CONTROL_SCANNER.read_text(encoding="utf-8")

    assert "def _check_cron_jobs() -> None:" in dashboard_source
    assert 'Path("/home/openclaw/.openclaw/cron/jobs.json")' in dashboard_source
    assert "_check_cron_jobs()" in dashboard_source

    assert 'CRON_JOB_ID = "drift-control-scan"' in scanner_source
    assert "def _register_cron_job() -> None:" in scanner_source
    assert '"command": f"python3 {BASE}/drift_control_scanner.py --scan"' in scanner_source
    assert "_register_cron_job()" in scanner_source


def test_freeze_doc_records_frozen_pending_scheduler_contract() -> None:
    freeze = _freeze_text().lower()

    assert "slice 7 records scheduler-owner classification only" in freeze
    assert "canonical scheduler owner: none selected in this source set" in freeze
    assert "dashboard_cron_jobs_json" in freeze
    assert ".openclaw/cron/jobs.json" in freeze
    assert "drift-control-scan" in freeze
    assert "frozen_pending_owner_decision" in freeze
    assert "running both drift-control cron and timer scheduling paths" in freeze
    assert "installed somewhere is not sufficient scheduler ownership evidence" in freeze


def test_service_inventory_audit_reports_frozen_pending_scheduler_classification() -> None:
    scheduler = _scheduler_report()
    paths = {item["path"]: item for item in scheduler["paths"]}  # type: ignore[index]

    assert scheduler["scheduler_id"] == "drift-control-scan"
    assert scheduler["canonical_scheduler_owner"] is None
    assert scheduler["classification_values"] == [
        "canonical_scheduler_owner",
        "disabled_deprecated_scheduler_path",
        "frozen_pending_owner_decision",
        "unknown_unowned_finding",
    ]
    assert scheduler["dual_scheduler_risk"] is True
    assert scheduler["live_scheduler_inspection_allowed"] is False
    assert scheduler["scheduler_mutation_allowed"] is False

    assert set(paths) == {
        "installed_systemd_timer",
        "installed_systemd_service",
        "dashboard_cron_jobs_json",
    }
    for path in paths.values():
        assert path["classification"] == "frozen_pending_owner_decision"


def test_installers_and_legacy_launchers_do_not_claim_drift_control_scheduler_ownership() -> None:
    forbidden_fragments = (
        "openclaw-drift-control-scan",
        "drift-control",
        "drift_control",
    )

    for path in INSTALLER_AND_LAUNCHER_PATHS:
        source = path.read_text(encoding="utf-8").lower()
        for fragment in forbidden_fragments:
            assert fragment not in source


def test_validation_map_indexes_drift_control_scheduler_static_contract() -> None:
    source = VALIDATION_MAP.read_text(encoding="utf-8")

    assert "Drift-control scheduler-owner static classification" in source
    assert "tests/test_drift_control_scheduler_static_contract.py" in source


def test_service_inventory_audit_and_static_contract_test_have_no_live_scheduler_surfaces() -> None:
    for source in (inspect.getsource(service_inventory_audit), Path(__file__).read_text(encoding="utf-8")):
        tree = ast.parse(source)
        imported_modules = set()
        called_names = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module.split(".")[0])
            elif isinstance(node, ast.Call):
                called = node.func
                if isinstance(called, ast.Name):
                    called_names.add(called.id)
                elif isinstance(called, ast.Attribute):
                    called_names.add(called.attr)

        assert "subprocess" not in imported_modules
        assert "os" not in imported_modules
        assert called_names.isdisjoint({
            "check_call",
            "check_output",
            "connect",
            "open_url",
            "popen",
            "run",
            "system",
            "urlopen",
        })