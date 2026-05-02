from __future__ import annotations

import ast
import inspect
from pathlib import Path

import service_inventory_audit
from service_inventory_audit import build_service_inventory_audit


REPO_ROOT = Path(__file__).resolve().parents[1]
FREEZE_DOC = REPO_ROOT / "docs" / "operations" / "OPENCLAW_SERVICE_MANAGEMENT_FREEZE.md"
VALIDATION_MAP = REPO_ROOT / "docs" / "testing" / "VALIDATION_MAP.md"

EXPECTED_DISPOSITIONED_SURFACES = {
    "scripts/start_all.sh",
    "start_chief.sh",
    "start_openclaw_brains.sh",
    "scripts/install_openclaw_stack.sh",
    "scripts/install_hermes_gateway_service.sh",
    "start_album_brain.sh",
    "start_cassandra_core.sh",
    "orchestrator.py --loop",
    "polish_loop/start_orchestrator.sh",
    "builder_watcher.sh",
    "loop_supervisor.sh",
    "dashboard_gen.py",
    "loop_dashboard_watchdog.sh",
    "ceo_briefing_worker.py",
    "chief_album_brain.py",
    "chief_billing_brain.py",
    "drift_control_scanner.py --scan",
    "openclaw-gateway.service",
    "openclaw-drift-control-scan.timer",
    "openclaw-drift-control-scan.service",
    "scripts/audit_openclaw_services.sh",
}

GUARDED_REFUSAL_SURFACES = {
    "scripts/start_all.sh",
    "start_chief.sh",
    "start_openclaw_brains.sh",
}

GATED_DRY_RUN_SURFACES = {
    "scripts/install_openclaw_stack.sh",
    "scripts/install_hermes_gateway_service.sh",
}

LIVE_CAPABLE_FROZEN_SURFACES = {
    "start_album_brain.sh",
    "orchestrator.py --loop",
    "polish_loop/start_orchestrator.sh",
    "builder_watcher.sh",
    "loop_supervisor.sh",
    "dashboard_gen.py",
    "loop_dashboard_watchdog.sh",
    "ceo_briefing_worker.py",
    "chief_album_brain.py",
    "chief_billing_brain.py",
    "drift_control_scanner.py --scan",
    "scripts/audit_openclaw_services.sh",
}


def _freeze_text() -> str:
    return FREEZE_DOC.read_text(encoding="utf-8")


def _dispositions() -> dict[str, dict[str, str]]:
    report = build_service_inventory_audit(repo_root=REPO_ROOT)
    return {row["surface"]: row for row in report["legacy_ownership_dispositions"]}


def test_all_slice_8_surfaces_have_definitive_disposition_rows() -> None:
    report = build_service_inventory_audit(repo_root=REPO_ROOT)
    dispositions = {row["surface"] for row in report["legacy_ownership_dispositions"]}

    assert EXPECTED_DISPOSITIONED_SURFACES <= dispositions
    assert report["legacy_ownership_disposition_findings"] == []
    assert all(
        row["disposition_class"] in report["legacy_ownership_disposition_classes"]
        for row in report["legacy_ownership_dispositions"]
    )
    assert all(row["runtime_mutation_allowed"] == "false" for row in report["legacy_ownership_dispositions"])
    assert all(row["live_inspection_required"] == "false" for row in report["legacy_ownership_dispositions"])


def test_freeze_doc_legacy_manual_and_deprecated_script_surfaces_are_dispositioned() -> None:
    report = build_service_inventory_audit(repo_root=REPO_ROOT)
    dispositions = {row["surface"] for row in report["legacy_ownership_dispositions"]}

    assert set(report["legacy_manual"]) <= dispositions
    deprecated_script_surfaces = {
        item for item in report["deprecated_frozen_controls"]
        if item.endswith(".sh") or item.startswith("scripts/")
    }
    assert deprecated_script_surfaces <= dispositions


def test_guarded_launchers_and_installers_are_retained_as_refusal_or_dry_run_only() -> None:
    dispositions = _dispositions()

    for surface in GUARDED_REFUSAL_SURFACES:
        row = dispositions[surface]
        source = (REPO_ROOT / surface).read_text(encoding="utf-8")
        assert row["disposition_class"] == "retained_manual_only_refusal_or_dry_run"
        assert "report_refusal" in source
        assert "No live" in source
        assert "no live" in row["allowed_control_path"].lower() or "report-only" in row["allowed_control_path"].lower()

    for surface in GATED_DRY_RUN_SURFACES:
        row = dispositions[surface]
        source = (REPO_ROOT / surface).read_text(encoding="utf-8")
        assert row["disposition_class"] == "retained_manual_only_refusal_or_dry_run"
        assert "report_plan" in source
        assert "No files will be written and no service commands will be run." in source
        assert "dry-run" in row["allowed_control_path"].lower()


def test_live_capable_legacy_surfaces_are_frozen_not_retained_as_safe_launch_paths() -> None:
    dispositions = _dispositions()

    for surface in LIVE_CAPABLE_FROZEN_SURFACES:
        assert dispositions[surface]["disposition_class"] == "frozen_pending_owner_decision"
        assert dispositions[surface]["allowed_control_path"].startswith("No run path in Slice 8")

    assert dispositions["start_cassandra_core.sh"]["disposition_class"] == "replaced_by_systemd_owned_path"
    assert dispositions["start_cassandra_core.sh"]["allowed_control_path"].startswith(
        "Use repo-owned Cassandra systemd templates"
    )


def test_installed_only_gateway_and_drift_units_remain_frozen_pending_owner_decision() -> None:
    dispositions = _dispositions()

    for surface in (
        "openclaw-gateway.service",
        "openclaw-drift-control-scan.timer",
        "openclaw-drift-control-scan.service",
    ):
        row = dispositions[surface]
        assert row["disposition_class"] == "frozen_pending_owner_decision"
        assert "template" in row["forbidden_control_path"].lower()
        assert row["runtime_mutation_allowed"] == "false"
        assert row["live_inspection_required"] == "false"


def test_disposition_contract_has_no_maybe_language() -> None:
    section = _freeze_text().split("## Legacy Ownership Disposition Contract", 1)[1]
    section = section.split("## Drift-Control Scheduler Classification", 1)[0]

    assert "maybe still useful" not in section.lower()
    assert "maybe safe" not in section.lower()
    assert "runtime mutation allowed | live inspection required" in section
    assert "unknown_unowned_finding" in section


def test_service_inventory_disposition_parser_has_no_live_runtime_surfaces() -> None:
    source = inspect.getsource(service_inventory_audit)
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

    assert imported_modules <= {"__future__", "pathlib", "re", "typing"}
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
    for forbidden in (
        "subprocess",
        "systemctl",
        "journalctl",
        "provider/model calls",
        "messaging calls",
        "/mnt/c/openclaw/logs",
        "/mnt/c/openclawlegalprivate",
    ):
        assert forbidden not in source.lower()


def test_validation_map_indexes_legacy_ownership_disposition_static_contract() -> None:
    source = VALIDATION_MAP.read_text(encoding="utf-8")

    assert "Legacy ownership/disposition static contract" in source
    assert "tests/test_legacy_ownership_disposition_static_contract.py" in source