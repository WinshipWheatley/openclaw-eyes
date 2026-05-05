# Handoff Prompt: Mac-to-PC Operator Harness Import

Use the following prompt to execute the actual import phase once authorized.

---

**PROMPT BEGIN**

I am ready to perform the surgical import of Operator Harness materials from the Mac `OpenClaw_Watch` environment to the PC WSL repository.

**Execution Requirements:**
1. **Follow the Map**: Use `docs/planning/launch_ladder/mac_import_planning/02_PC_DESTINATION_MAP.md` for all source-to-destination mappings.
2. **Docs-Only First**: Prioritize the foundational documentation and doctrine papers as outlined in the Priority Map (Phase 1 and 2).
3. **No Raw Assets**: Do NOT import raw screenshots or raw capture logs.
4. **Strict Sanitization**: Ensure no sensitive, financial, or private data is included in any imported files.
5. **No Code Import**: Do NOT import implementation code into `src/` at this stage. Code candidates must go to a research/review directory first.
6. **Verification**: After each import step:
   - Run `git status` to verify untracked files.
   - Run `git diff --check` to ensure no whitespace or formatting issues.
   - Run `launch_ladder_contract_check.py` to ensure repo integrity.
7. **Reporting**: Provide a summary of changed files and a preview of key imported content.

**Safety Boundaries:**
- Do NOT touch anything listed in `docs/planning/launch_ladder/mac_import_planning/04_DO_NOT_IMPORT_BOUNDARIES.md`.
- No commits.

**Ready to proceed with Phase 1 of the Import Priority and Sequence.**

**PROMPT END**
