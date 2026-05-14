from pathlib import Path


def test_mission_control_refresh_prompt_exists_and_is_read_only():
    path = Path("docs/operations/MISSION_CONTROL_READ_MODEL_REFRESH_V0_PROMPT.md")
    text = path.read_text(encoding="utf-8")

    assert "context_selection.json" in text
    assert "project_capsules.json" in text
    assert "tool_inventory.json" in text
    assert "tool_intake.json" in text
    assert "No backend execution" in text
    assert "No network calls" in text
    assert "No writes" in text
    assert "No action buttons" in text
    assert "No runtime activation" in text
    assert "No agent activation" in text
    assert "No tool activation or tool execution" in text
    assert "Preserve the existing read-only helm overview" in text
    assert "Read generated files only" in text
