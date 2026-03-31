title: env-001-spec-tools
goal: Produce implementable specs for the requested tools so build work can start without ambiguity.
scope:
- Define purpose, input, output, and acceptance criteria for:
  - scraper
  - search
  - mcporter
  - skill_loader
  - Skill Vetter
- Add one concrete usage example per tool.
success condition:
- All five tools have clear, testable specs with no unresolved behavior ambiguity.
- A builder can start implementation directly from the spec.
blockers/dependencies:
- Product/owner decisions for intended behavior and boundaries.
- No existing in-repo definitions for these tools; requirements must be provided explicitly.