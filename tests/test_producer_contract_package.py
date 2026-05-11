import json
import yaml
from pathlib import Path

EXPECTED_FILES = [
    "docs/producer/PRODUCER_ARCHETYPE.md",
    "docs/producer/PRODUCER_MACHINE_CONTRACT.md",
    "docs/producer/PRODUCER_AGENT_FLOW.md",
    "docs/producer/PRODUCER_TOOL_BRIDGE_CONTRACT.md",
    "config/producer/producer_rubric.yaml",
    "config/producer/producer_reference_map.yaml",
    "config/producer/producer_environment_targets.yaml",
    "templates/producer/producer_review_template.json",
]

def test_producer_contract_files_exist():
    for f in EXPECTED_FILES:
        assert Path(f).exists(), f"Missing file: {f}"

def test_producer_template_json_validity():
    p = Path("templates/producer/producer_review_template.json")
    data = json.loads(p.read_text(encoding="utf-8"))
    
    assert "no_side_effects" in data, "no_side_effects must be in template"
    assert data["no_side_effects"] is True, "no_side_effects must be true"
    assert "optional_tool_intent_packet" in data, "optional_tool_intent_packet must exist"

def test_producer_rubric_hard_flags():
    p = Path("config/producer/producer_rubric.yaml")
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    
    assert "hard_flags" in data, "hard_flags must be in producer_rubric.yaml"
    assert isinstance(data["hard_flags"], list), "hard_flags must be a list"
    assert len(data["hard_flags"]) > 0, "hard_flags must not be empty"

def test_producer_environment_targets():
    p = Path("config/producer/producer_environment_targets.yaml")
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    
    assert "environment_targets" in data, "environment_targets must be in producer_environment_targets.yaml"
    targets = data["environment_targets"]
    
    expected_targets = ["ableton_live", "logic_pro", "x32_rack", "dl16", "unknown"]
    for tgt in expected_targets:
        assert tgt in targets, f"Environment target {tgt} is missing"

def test_producer_docs_boundaries():
    archetype_path = Path("docs/producer/PRODUCER_ARCHETYPE.md")
    content = archetype_path.read_text(encoding="utf-8").lower()
    
    # Check for keywords indicating boundaries
    assert "evidence" in content or "receipt" in content, "Docs must mention evidence or receipts."
    assert "execute" in content or "execution" in content, "Docs must discuss the non-execution boundary."
