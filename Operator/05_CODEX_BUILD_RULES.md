# 05 Codex Build Rules

## Implementation Discipline
- **Inspect First**: Check repository branch, cleanliness, and existing conventions before touching code.
- **Bounded Mutation**: Only modify files within the authorized scope. Avoid broad refactors or "adjacent cleanup" unless explicitly requested.
- **Diff and Test**: Every behavioral change must be accompanied by focused tests.
- **Validation Receipts**: Use `./scripts/openclaw_receipts.py` to validate your work before reporting completion.

## Commit and Review
- **No Push**: Never push to a remote repository.
- **No Hidden Staging**: Do not stage or commit unless explicitly asked.
- **READY_TO_COMMIT**: Only propose a commit after a successful implementation review.
- **Concise Reporting**: Provide a concise summary of changed files, tests run, and validation results.

## Quality Standards
- **Local-First**: Prioritize durable, local-first logic over vendor-specific or cloud-reliant patterns.
- **Small and Durable**: Favor explicit composition and delegation over complex inheritance.
- **Safe by Design**: Implement hard gates and boundaries at the logic level, not just in prompts.

---
**Authority Backpointers:**
- Packet 07 File 14: `MODEL_AND_TOOL_SPECIFIC_PROMPT_DOCTRINE.md`
- `scripts/openclaw_receipts.py` (Validation Authority)
