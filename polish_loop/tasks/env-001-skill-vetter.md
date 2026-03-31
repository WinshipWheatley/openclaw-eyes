title: env-001-skill-vetter
goal: Implement a first runnable PC-only Skill Vetter that validates normalized skill records against minimum quality checks and returns deterministic per-skill results per the current spec.
scope:
- Build a local vetter entrypoint that accepts normalized `skills`, optional `ruleset`, and `strict_mode`.
- Validate each skill record and emit exactly one result per input skill.
- Return structured output with `results`, `summary`, and optional `errors`.
- Include per-skill result fields: `skill_id`, `status`, and `reasons`.
- Implement strict/non-strict behavior:
  - strict: fail run when any skill fails vetting
  - non-strict: return all per-skill results without aborting on first failure
- Keep implementation PC-local and read-only.
success condition:
- Every input skill gets exactly one deterministic vetting result.
- Failed skills include explicit reason codes and human-readable messages.
- Strict mode exits as failure when failed > 0.
- Non-strict mode returns complete per-skill results.
- Output schema matches the current `Skill Vetter` section in env-001-spec-tools.md.
blockers/dependencies:
- Canonical reason code list is still partially TBD.
- Warning/severity model is still TBD and may be omitted in first pass.
- Input normalized skill records must exist from the loader stage.
exact files likely to be touched first:
- skill_vetter.py
- tests/test_skill_vetter.py
