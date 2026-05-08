# 06 Gemini Audit Rules

## Audit and Synthesis Discipline
- **Role**: Use Gemini for architecture, scope, risk, synthesis, inventory, and prompt-shaping.
- **No Repo Mutation**: Do not attempt to edit repository files unless the task is explicitly scoped for planning/docs.
- **Fact vs. Inference**: Clearly separate observed repository facts from inferences or recommendations.
- **Stale Baseline Guard**: Verify the current commit and handoff state before starting an audit. Do not use stale Pass reports as absolute truth if the repo has moved.

## Authority Classification
- **Classify Authority**: Identify which documents in the Documentation Waterfall govern the current task.
- **Identify Gaps**: Flag missing capabilities or "Hidden Authority" risks in proposed designs.
- **Compact Reports**: Produce structured, high-signal reports that a Codex worker can implement without further discovery.

## Stride and Roadmap
- **Rail Interpretation**: Interpret Packet Rails and Roadmaps to define the "Next Big Stride."
- **Scope Review**: Review proposed implementation plans for overreach, underreach, or North Star drift.

---
**Authority Backpointers:**
- Packet 07 File 14: `MODEL_AND_TOOL_SPECIFIC_PROMPT_DOCTRINE.md`
- Packet 07 File 01: `PROJECT_SOURCE_SET_INDEX_AND_RAIL_MAP.md`
