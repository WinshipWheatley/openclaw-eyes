from __future__ import annotations

import ast
import inspect
from pathlib import Path

import service_inventory_audit
from service_inventory_audit import build_service_inventory_audit


REPO_ROOT = Path(__file__).resolve().parents[1]
FREEZE_DOC = REPO_ROOT / "docs" / "operations" / "OPENCLAW_SERVICE_MANAGEMENT_FREEZE.md"
SYSTEMD_USER_DIR = REPO_ROOT / "systemd" / "user"
INSTALLER_AND_LAUNCHER_PATHS = (
    REPO_ROOT / "scripts" / "install_openclaw_stack.sh",
    REPO_ROOT / "scripts" / "install_hermes_gateway_service.sh",
    REPO_ROOT / "scripts" / "start_all.sh",
    REPO_ROOT / "start_chief.sh",
    REPO_ROOT / "start_openclaw_brains.sh",
)
VALIDATION_MAP = REPO_ROOT / "docs" / "testing" / "VALIDATION_MAP.md"

FROZEN_PENDING_UNITS = (
    "openclaw-gateway.service",
    "openclaw-drift-control-scan.timer",
    "openclaw-drift-control-scan.service",
)


def _freeze_text() -> str:
    return FREEZE_DOC.read_text(encoding="utf-8")


def _classification_by_item() -> dict[str, dict[str, object]]:
    report = build_service_inventory_audit(repo_root=REPO_ROOT)
    return {item["item"]: item for item in report["owner_classifications"]}


def test_no_repo_templates_exist_for_frozen_pending_gateway_and_drift_control_units():
    template_names = {path.name for path in SYSTEMD_USER_DIR.iterdir() if path.is_file()}

    for unit_name in FROZEN_PENDING_UNITS:
        assert f"{unit_name}.in" not in template_names


def test_freeze_doc_records_frozen_pending_owner_decisions_not_repo_templates():
    freeze = _freeze_text().lower()

    assert "installed somewhere is not sufficient ownership evidence" in freeze
    for unit_name in FROZEN_PENDING_UNITS:
        assert unit_name in freeze
    assert "openclaw-gateway.service` - systemd-owned as an installed unit, with no repo template in this source set" in _freeze_text()
    assert "openclaw-drift-control-scan.timer` and `openclaw-drift-control-scan.service` - systemd-owned as installed units, with no repo templates in this source set" in _freeze_text()
    assert "frozen pending documented external owner or future repo template decision" in freeze


def test_owner_classification_marks_frozen_pending_units_without_unknown_unowned():
    classifications = _classification_by_item()

    for unit_name in FROZEN_PENDING_UNITS:
        assert classifications[unit_name]["repo_template_present"] is False
        assert classifications[unit_name]["documented_external_owner"] is False
        assert classifications[unit_name]["frozen_pending_template_decision"] is True
        assert classifications[unit_name]["unknown_unowned"] is False


def test_repo_template_units_are_classified_as_repo_template_present():
    classifications = _classification_by_item()

    for unit_name in (
        "openclaw-stack.target",
        "hermes-gateway.service",
        "chief-listener.service",
        "cassandra-listener.service",
    ):
        assert classifications[unit_name]["repo_template_present"] is True
        assert classifications[unit_name]["unknown_unowned"] is False


def test_installers_and_legacy_launchers_do_not_silently_claim_openclaw_gateway_or_drift_control():
    forbidden_fragments = (
        "openclaw-gateway",
        "openclaw-drift-control-scan",
        "drift-control",
        "drift_control",
    )

    for path in INSTALLER_AND_LAUNCHER_PATHS:
        source = path.read_text(encoding="utf-8").lower()
        for fragment in forbidden_fragments:
            assert fragment not in source


def test_service_inventory_audit_owner_classification_has_no_live_surfaces():
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


def test_validation_map_indexes_service_owner_classification_static_contract():
    source = VALIDATION_MAP.read_text(encoding="utf-8")

    assert "openclaw-gateway.service" in source
    assert "openclaw-drift-control-scan.timer" in source
    assert "tests/test_service_owner_classification_static_contract.py" in source