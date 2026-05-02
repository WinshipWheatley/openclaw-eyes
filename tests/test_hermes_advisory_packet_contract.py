import ast
import copy
import inspect

import hermes_advisory_packet as contract
from hermes_advisory_packet import (
    HERMES_AUTHORITY_LEVEL,
    HERMES_OUTPUT_KIND,
    HERMES_PROMOTION_REQUIRED,
    NON_CANONICAL_NOTICE,
    REQUIRED_WITHHELD_SURFACES,
    build_hermes_advisory_memo,
    build_hermes_advisory_packet,
    check_hermes_advisory_memo,
    check_hermes_advisory_packet,
)


def _valid_packet(**overrides):
    packet = build_hermes_advisory_packet(
        packet_id="hermes-advisory-service-freeze-001",
        purpose="Review a bounded service-freeze closure source packet and propose advisory critique only.",
        source_set_name="service_freeze_closure_static_docs",
        allowed_read_surfaces=(
            "docs/operations/OPENCLAW_SERVICE_MANAGEMENT_FREEZE.md",
            "docs/testing/VALIDATION_MAP.md",
            "tests/test_hermes_gateway_installer_safety.py",
        ),
    )
    packet.update(overrides)
    return packet


def _valid_memo(packet=None, **overrides):
    source_packet = packet or _valid_packet()
    memo = build_hermes_advisory_memo(
        observations=("The freeze contract names service owner boundaries and forbidden controls.",),
        risks=("A future trial could overread live services unless the input packet stays explicit.",),
        suggested_next_slices=("Operator reviews the memo and manually promotes accepted critique.",),
        evidence_refs=("docs/operations/OPENCLAW_SERVICE_MANAGEMENT_FREEZE.md",),
        assumptions=("The packet contains only static docs and tests.",),
        withheld_surfaces=source_packet["withheld_surfaces"],
    )
    memo.update(overrides)
    return memo


def test_valid_advisory_packets_pass():
    packet = _valid_packet()

    assert check_hermes_advisory_packet(packet) == {"passed": True, "violations": [], "recommended_action": "pass"}
    assert packet["authority_level"] == HERMES_AUTHORITY_LEVEL
    assert packet["output_kind"] == HERMES_OUTPUT_KIND
    assert packet["promotion_required"] == HERMES_PROMOTION_REQUIRED
    assert packet["execution_allowed"] is False
    assert packet["canonical_write_allowed"] is False
    assert packet["queue_mutation_allowed"] is False
    assert packet["approval_authority_allowed"] is False
    assert packet["provider_fallback_allowed"] is False
    assert packet["live_service_inspection_allowed"] is False
    assert packet["private_data_allowed"] is False


def test_missing_authority_fields_fail_closed():
    packet = _valid_packet()
    del packet["authority_level"]

    check = check_hermes_advisory_packet(packet)

    assert check["passed"] is False
    assert check["recommended_action"] == "reject"
    assert "missing_required_field:authority_level" in check["violations"]
    assert "authority_not_advisory_only" in check["violations"]


def test_any_permission_set_true_fails_closed():
    permission_fields = (
        "execution_allowed",
        "canonical_write_allowed",
        "queue_mutation_allowed",
        "approval_authority_allowed",
        "provider_fallback_allowed",
        "live_service_inspection_allowed",
        "private_data_allowed",
    )
    for field in permission_fields:
        packet = _valid_packet(**{field: True})
        check = check_hermes_advisory_packet(packet)

        assert check["passed"] is False
        assert f"permission_not_false:{field}" in check["violations"]


def test_packet_contract_names_withheld_surfaces():
    packet = _valid_packet()

    assert tuple(packet["withheld_surfaces"]) == REQUIRED_WITHHELD_SURFACES
    assert check_hermes_advisory_packet(packet)["passed"] is True

    missing_logs = copy.deepcopy(packet)
    missing_logs["withheld_surfaces"] = [surface for surface in missing_logs["withheld_surfaces"] if surface != "logs"]

    check = check_hermes_advisory_packet(missing_logs)

    assert check["passed"] is False
    assert "missing_withheld_surface:logs" in check["violations"]


def test_protected_or_broad_allowed_read_surfaces_fail_closed():
    broad = _valid_packet(allowed_read_surfaces=["/home/openclaw"])
    protected = _valid_packet(allowed_read_surfaces=["sidecar runtime state snapshot"])

    broad_check = check_hermes_advisory_packet(broad)
    protected_check = check_hermes_advisory_packet(protected)

    assert broad_check["passed"] is False
    assert "allowed_surface_too_broad:/home/openclaw" in broad_check["violations"]
    assert protected_check["passed"] is False
    assert "allowed_surface_protected:sidecar runtime state snapshot" in protected_check["violations"]


def test_valid_advisory_outputs_pass():
    packet = _valid_packet()
    memo = _valid_memo(packet)

    assert check_hermes_advisory_memo(memo, packet=packet) == {"passed": True, "violations": [], "recommended_action": "pass"}
    assert memo["output_kind"] == HERMES_OUTPUT_KIND
    assert memo["authority_level"] == HERMES_AUTHORITY_LEVEL
    assert memo["non_canonical_notice"] == NON_CANONICAL_NOTICE
    assert memo["commands_executed"] is False
    assert memo["decisions_made"] is False
    assert memo["canonical_writes_made"] is False


def test_outputs_missing_non_canonical_notice_fail_closed():
    memo = _valid_memo(non_canonical_notice="")

    check = check_hermes_advisory_memo(memo, packet=_valid_packet())

    assert check["passed"] is False
    assert "missing_or_invalid_non_canonical_notice" in check["violations"]


def test_outputs_implying_decisions_execution_or_canonical_writes_fail_closed():
    packet = _valid_packet()

    for field, violation in (
        ("commands_executed", "commands_executed_not_false"),
        ("decisions_made", "decisions_made_not_false"),
        ("canonical_writes_made", "canonical_writes_made_not_false"),
    ):
        memo = _valid_memo(packet, **{field: True})
        check = check_hermes_advisory_memo(memo, packet=packet)
        assert check["passed"] is False
        assert violation in check["violations"]

    implied = _valid_memo(packet, observations=("Hermes approved the service restart as final.",))
    implied_check = check_hermes_advisory_memo(implied, packet=packet)
    assert implied_check["passed"] is False
    assert "memo_implies_execution_decision_or_canonical_write" in implied_check["violations"]


def test_memo_must_carry_packet_withheld_surfaces():
    packet = _valid_packet()
    memo = _valid_memo(packet)
    memo["withheld_surfaces"] = [surface for surface in memo["withheld_surfaces"] if surface != "queues"]

    check = check_hermes_advisory_memo(memo, packet=packet)

    assert check["passed"] is False
    assert "memo_missing_packet_withheld_surface:queues" in check["violations"]


def test_helper_has_no_live_runtime_imports_or_calls():
    source = inspect.getsource(contract)
    tree = ast.parse(source)
    imported_modules = set()
    called_names = set()
    attribute_names = set()
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
        elif isinstance(node, ast.Attribute):
            attribute_names.add(node.attr)

    assert imported_modules <= {"__future__", "re", "typing"}
    assert called_names.isdisjoint({
        "open",
        "Popen",
        "system",
        "urlopen",
        "Request",
        "systemctl",
        "exec",
    })
    assert attribute_names.isdisjoint({
        "system",
        "popen",
        "urlopen",
        "exec",
    })
    forbidden_live_import_or_call_text = (
        "subprocess",
        "os.system",
        "shell=True",
        "requests.",
        "httpx.",
        "urllib.",
        "googleapiclient",
        "google.auth",
        "google.oauth",
        "gmail_api",
        "gmail_client",
        "telegram_bot",
        "telegram_send",
        "guardian_send",
        "openrouter",
        "model_execute",
        "provider_execute",
        "provider_call(",
        "run_agent",
        "hermes_cli",
        "gateway.run",
        "SessionStore",
        "sidecars/hermes_home/",
        "runtime.db",
        "gateway.out",
    )
    for text in forbidden_live_import_or_call_text:
        assert text not in source


def test_hermes_remains_sidecar_advisory_only():
    packet = _valid_packet()
    memo = _valid_memo(packet)

    assert packet["authority_level"] == "advisory_only"
    assert memo["authority_level"] == "advisory_only"
    assert packet["output_kind"] == "non_canonical_advisory_memo"
    assert packet["promotion_required"] == "explicit_human_or_chief_controlled_promotion"
    assert all(packet[field] is False for field in contract.FALSE_PERMISSION_FIELDS)


def test_no_dependency_on_hermes_home_or_runtime_state():
    source = inspect.getsource(contract)

    assert "sidecars/hermes_home" not in source
    assert "HERMES_HOME" not in source
    assert "runtime.db" not in source
    assert "gateway.out" not in source
    assert "sqlite" not in source.lower()
    assert not hasattr(contract, "write_hermes_advisory_packet")
    assert not hasattr(contract, "save_hermes_advisory_packet")