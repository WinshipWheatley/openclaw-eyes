from __future__ import annotations

import ast
import inspect
from pathlib import Path

import service_inventory_audit
from service_inventory_audit import build_service_inventory_audit


REPO_ROOT = Path(__file__).resolve().parents[1]
FREEZE_DOC = REPO_ROOT / "docs" / "operations" / "OPENCLAW_SERVICE_MANAGEMENT_FREEZE.md"


def _freeze_text() -> str:
    return FREEZE_DOC.read_text(encoding="utf-8")


def test_build_service_inventory_audit_extracts_freeze_inventory():
    report = build_service_inventory_audit(
        freeze_text=_freeze_text(),
        template_filenames=["hermes-gateway.service.in", "chief-listener.service.in"],
    )

    assert report["audit_type"] == "openclaw.service_inventory_audit"
    assert report["schema_version"] == 1
    assert report["runtime_neutral"] is True
    assert report["live_service_inspection_allowed"] is False
    assert report["service_mutation_allowed"] is False
    assert "openclaw-stack.target" in report["systemd_owned"]
    assert "chief-listener.service" in report["systemd_owned"]
    assert "openclaw-drift-control-scan.timer" in report["systemd_owned"]
    assert "openclaw-drift-control-scan.service" in report["systemd_owned"]
    assert "chief_album_brain.py" in report["legacy_manual"]
    assert "loop_supervisor.sh" in report["legacy_manual"]
    assert "scripts/start_all.sh" in report["deprecated_frozen_controls"]
    assert "start_chief.sh" in report["deprecated_frozen_controls"]
    assert "blanket enabling all installed services" in report["deprecated_frozen_controls"]
    assert report["runtime_neutral_rule_present"] is True
    assert "retained_manual_only_refusal_or_dry_run" in report["legacy_ownership_disposition_classes"]
    assert any(
        item["surface"] == "start_openclaw_brains.sh"
        and item["disposition_class"] == "retained_manual_only_refusal_or_dry_run"
        for item in report["legacy_ownership_dispositions"]
    )
    assert report["legacy_ownership_disposition_findings"] == []


def test_cleanup_slice_order_is_deterministic_and_starts_with_read_only_inventory():
    report = build_service_inventory_audit(freeze_text=_freeze_text())

    assert [item["slice"] for item in report["cleanup_slice_order"]] == [2, 3, 4, 5, 6, 7, 8]
    assert report["cleanup_slice_order"][0] == {
        "slice": 2,
        "description": "add read-only service inventory/audit check.",
    }
    assert report["cleanup_slice_order"][-1] == {
        "slice": 8,
        "description": "record static legacy polling/loop supervisor ownership disposition.",
    }


def test_pending_template_findings_are_advisory_only():
    report = build_service_inventory_audit(
        freeze_text=_freeze_text(),
        template_filenames=[
            "openclaw-stack.target.in",
            "chief-listener.service.in",
            "hermes-gateway.service.in",
        ],
    )
    findings_by_item = {finding["item"]: finding for finding in report["findings"]}

    assert set(findings_by_item) == {
        "openclaw-gateway.service",
        "openclaw-drift-control-scan.timer",
        "openclaw-drift-control-scan.service",
    }
    for finding in findings_by_item.values():
        assert finding["severity"] == "warning"
        assert finding["finding"] == "documented_installed_unit_without_repo_template"
        assert finding["repo_template_present"] is False
        assert finding["documented_external_owner"] is False
        assert finding["frozen_pending_template_decision"] is True
        assert finding["unknown_unowned"] is False
        assert "Frozen" in finding["cleanup_status"]


def test_repo_root_mode_reads_freeze_doc_and_template_filenames_only():
    report = build_service_inventory_audit(repo_root=REPO_ROOT)
    classifications = {item["item"]: item for item in report["owner_classifications"]}
    scheduler_paths = {item["path"]: item for item in report["drift_control_scheduler"]["paths"]}

    assert report["source"] == "docs/operations/OPENCLAW_SERVICE_MANAGEMENT_FREEZE.md"
    assert "hermes-gateway.service" in report["systemd_owned"]
    assert any(finding["item"] == "openclaw-gateway.service" for finding in report["findings"])
    assert classifications["hermes-gateway.service"]["repo_template_present"] is True
    assert classifications["openclaw-gateway.service"] == {
        "item": "openclaw-gateway.service",
        "repo_template_present": False,
        "documented_external_owner": False,
        "frozen_pending_template_decision": True,
        "unknown_unowned": False,
        "cleanup_status": "Frozen pending documented external owner or future repo template decision",
    }
    assert report["drift_control_scheduler"]["canonical_scheduler_owner"] is None
    assert report["drift_control_scheduler"]["dual_scheduler_risk"] is True
    assert scheduler_paths["installed_systemd_timer"]["classification"] == "frozen_pending_owner_decision"
    assert scheduler_paths["installed_systemd_service"]["classification"] == "frozen_pending_owner_decision"
    assert scheduler_paths["dashboard_cron_jobs_json"]["classification"] == "frozen_pending_owner_decision"
    assert report["live_service_inspection_allowed"] is False
    assert report["service_mutation_allowed"] is False
    assert {row["surface"] for row in report["legacy_ownership_dispositions"]} >= {
        "builder_watcher.sh",
        "loop_supervisor.sh",
        "orchestrator.py --loop",
        "scripts/audit_openclaw_services.sh",
    }


def test_legacy_ownership_disposition_contract_is_static_and_definitive():
    report = build_service_inventory_audit(freeze_text=_freeze_text())
    dispositions = {row["surface"]: row for row in report["legacy_ownership_dispositions"]}

    assert report["legacy_ownership_disposition_classes"] == [
        "retired_dead_entrypoint",
        "frozen_pending_owner_decision",
        "replaced_by_systemd_owned_path",
        "retained_manual_only_refusal_or_dry_run",
        "unknown_unowned_finding",
    ]
    assert dispositions["start_cassandra_core.sh"]["disposition_class"] == "replaced_by_systemd_owned_path"
    assert dispositions["loop_supervisor.sh"]["disposition_class"] == "frozen_pending_owner_decision"
    assert dispositions["scripts/install_openclaw_stack.sh"]["runtime_mutation_allowed"] == "false"
    assert dispositions["scripts/install_hermes_gateway_service.sh"]["live_inspection_required"] == "false"
    assert all(row["runtime_mutation_allowed"] == "false" for row in dispositions.values())
    assert all(row["live_inspection_required"] == "false" for row in dispositions.values())
    assert "maybe still useful" not in _freeze_text().lower()
    assert "maybe safe" not in _freeze_text().lower()


def test_service_inventory_audit_is_deterministic():
    first = build_service_inventory_audit(freeze_text=_freeze_text())
    second = build_service_inventory_audit(freeze_text=_freeze_text())

    assert first == second


def test_service_inventory_audit_module_has_no_live_service_or_external_surfaces():
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
        "provider",
        "telegram",
        "gmail",
        "hermes_home",
        "/mnt/c/openclaw/logs",
        "/mnt/c/openclawlegalprivate",
    ):
        assert forbidden not in source.lower()