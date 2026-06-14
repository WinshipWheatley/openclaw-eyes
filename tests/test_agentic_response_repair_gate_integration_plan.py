import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agentic_response_repair_gate_integration_plan as plan


FIXED_NOW = "2026-06-06T15:00:00+00:00"


def _read_model():
    return plan.build_read_model(generated_at=FIXED_NOW)


def test_plan_is_ready_and_chooses_next_safe_runtime_build():
    read_model = _read_model()

    assert read_model["status"] == plan.READY_STATUS
    assert read_model["next_safe_runtime_build"]["choice"] == "verifier-only response harness"
    assert read_model["next_safe_runtime_build"]["why"] != ""
    assert read_model["machine_proof"]["preconditions_ready"] is True


def test_required_sections_present():
    read_model = _read_model()

    for section in plan.REQUIRED_OUTPUT_SECTIONS:
        assert section in read_model["sections"]
        assert read_model["sections"][section]


def test_deterministic_vs_agentic_split_is_complete():
    split = _read_model()["deterministic_vs_agentic_split"]

    for item in ["truth", "receipts", "authority", "gate decisions", "proof refs", "lifecycle", "protected action blocks", "source hashes", "verification status"]:
        assert item in split["stays_deterministic"]
    for item in ["phrasing", "prioritization", "diagnosis", "repair proposal", "next-step explanation", "missing-proof explanation", "contextual helpfulness", "what can be done now reasoning"]:
        assert item in split["becomes_agentic"]


def test_blocked_actions_stay_blocked():
    blocked = _read_model()["blocked_actions"]

    for action in [
        "email send",
        "Gmail/browser/Coupa access",
        "portal submit",
        "ledger mutation/posting",
        "paid marking",
        "workbook source mutation",
        "PDF export/send",
        "git push/merge",
        "worker spawn",
        "external provider call",
        "live model/runtime expansion",
    ]:
        assert action in blocked


def test_self_heal_flow_has_no_black_box_repair_paths():
    read_model = _read_model()

    assert read_model["self_heal_flow"]["doctrine"] == "no_black_box_repairs"
    for repair_path in read_model["self_heal_flow"]["repair_paths"]:
        for field in [
            "repair_ref",
            "name_blocker",
            "proof_refs",
            "what_can_be_done_now",
            "what_cannot_be_done_yet",
            "smallest_operator_step",
            "stage_repair_package",
            "validation",
            "receipt_required",
        ]:
            assert repair_path[field]
        assert repair_path["authority_boundary"]["protected_actions_allowed"] is False


def test_gate_calibration_allows_useful_agent_work_but_blocks_final_actions():
    gates = _read_model()["gate_calibration_summary"]

    for allowed in [
        "inspect local proof",
        "draft",
        "stage",
        "patch code",
        "run safe tests",
        "prepare approval package",
        "prepare review packet",
        "explain next step",
    ]:
        assert allowed in gates["agents_may"]
    for blocked in [
        "execute protected external action",
        "invent truth",
        "grant authority",
        "bypass Guardian",
        "promote memory to truth",
        "submit/send/post/mark paid/push",
    ]:
        assert blocked in gates["agents_may_not"]


def test_mac_app_surface_is_response_first_not_card_deck():
    mac = _read_model()["mac_app_surface"]

    assert mac["primary_surface"] == "concise agent response first"
    assert mac["one_next_control"] is True
    assert mac["proof_meters"] is True
    assert mac["details_collapsed"] is True
    assert mac["dynamic_card_role"] == "support/display"
    assert mac["card_deck_primary_response"] is False


def test_first_implementation_sequence_is_three_to_five_steps():
    sequence = _read_model()["first_implementation_sequence"]

    assert 3 <= len(sequence) <= 5
    assert sequence[0]["step"] == "Integrate proof bundle builder into controller responses"
    assert sequence[-1]["validation_required"]


def test_tests_required_before_live_lm_include_shadow_and_gate_checks():
    required = _read_model()["tests_required_before_live_lm"]

    for item in [
        "proof bundle redaction tests",
        "verifier publish/block tests",
        "self-heal no-black-box repair tests",
        "Goldilocks gate regression tests",
        "Mac response-first rendering smoke",
        "unsafe true-grant scan",
    ]:
        assert item in required


def test_read_model_export_round_trips(tmp_path):
    result = plan.export_agentic_response_repair_gate_integration_plan(
        read_model_root=ROOT / "generated/read_models",
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        wiki_path=tmp_path / "Agentic Response Repair Gate Integration Plan.md",
        generated_at=FIXED_NOW,
    )
    local_payload = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge_payload = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))

    assert result["status"] == plan.READY_STATUS
    assert local_payload == bridge_payload
    assert local_payload["status"] == plan.READY_STATUS
    assert Path(result["wiki_path"]).read_text(encoding="utf-8").startswith("# Agentic Response Repair Gate Integration Plan")


def test_unsafe_true_grant_scan_clean():
    read_model = _read_model()

    assert plan.unsafe_true_grants(read_model) == []
    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True
