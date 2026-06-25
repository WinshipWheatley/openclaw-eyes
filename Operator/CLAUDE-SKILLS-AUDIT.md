# Claude Agent Skills Integration Audit

## 1. Agent-by-Agent Assessment

| Agent | 1. Runtime | 2. Native Skill Discovery | 3. Git Repo Access | 4. `/run` or `/verify` Materiality | 5. Recommended Access Model |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **PC-Claude** | Claude Code / API | Yes (if CLI) | Yes | High | Request builder (or use directly if CLI) |
| **Sonnet builders** | Claude Code | **Yes** | Yes | **Critical** | **Use skill directly** |
| **Chief** | Custom Python | No | Yes | High | Request builder / Receive verified result |
| **Maestro** | Custom Python | No | Yes | Low | No access |
| **Guardian** | Custom Python | No | Yes | Medium | Receive verified result only |
| **Cassandra** | Custom Python | No | Yes | Low | Receive verified result only |
| **Niles** | Custom Python | No | Yes | Low | Receive verified result only |
| **Hermes** | Custom Python | No | Yes | Medium | Receive verified result only |
| **AGY (Gemini)**| Antigravity CLI | No | Yes | Medium | Request builder |
| **Mac-Desktop-Claude**| Claude Desktop | No (Needs MCP) | Yes | Medium | Request builder |

---

## 2. Which Agents Should Receive Skill Access

Only **Sonnet Builders** (running as native Claude Code instances in `.claude/worktrees/`) should receive direct access to execute skills. 
Custom Python agents (Chief, Guardian, Cassandra, Niles, Hermes) and desktop apps lack the native runtime environment to safely discover and sandbox these skills. They should act strictly as **orchestrators, requesters, or reviewers**—delegating execution to a builder and consuming the verified output.

A run skill belongs **authoritatively in `.claude/skills/`**. It should NOT be copied into custom agent logic.

---

## 3. Packet Architecture (What to Add)

**Do NOT copy the entire `SKILL.md` into every packet.** This wastes context tokens, duplicates truth, and encourages unauthorized execution attempts by non-native agents.

Packets should act as a lightweight permission bridge containing only:
* **Skill name and version** (e.g., `run_linter v1.2`)
* **Repo and working directory**
* **Authorized Invokers** (e.g., restricted to specific Sonnet builders)
* **Allowed Task Types** (e.g., `verify_only`)
* **Safety Restrictions** (e.g., `network_authority: false`, `db_mutation: false`)
* **Expected Evidence** (The exact format of the receipt or stdout expected back)
* **Terminal States** (Success/failure/timeout definitions)

---

## 4. Safety Implications & Control Plane Integration

### Safety Implications
Generated run skills carry extreme risk if unsupervised, as they can execute arbitrary bash commands. 
* **Safe / Auto-Invoke**: Read-only verification, linting, or local data extraction. Builders may invoke these automatically.
* **Manual / HITL-Only**: Any skill that starts production services, consumes real queues, sends Telegram messages, modifies SQLite ledgers, uses paid APIs, or exposes secrets.

### `control_plane.py` Integration
`control_plane.py` **should** dispatch and track skill-backed tasks. 
Currently, the control plane is strictly deterministic and tracks tasks via a generic JSON `payload`. To integrate skills safely:
1. Extend the `payload` schema to officially include `skill_name` and `skill_version`.
2. Map the skill's output (stdout/exit code) directly into the existing `candidate_evidence` field for the task attempt.
3. Keep the control plane completely ignorant of the skill's internal bash logic—it should only track the request, the lease, and the resulting evidence.

---

## 5. Safest Pilot Implementation

To prove this model without risking production data or rogue execution:

* **Safe Repo**: `/home/openclaw/polish_loop/` (isolated, non-client data).
* **Claude Code Builder**: A single restricted worktree (e.g., `agent-a45e958004010069c`).
* **Generated Run Skill**: A harmless, read-only Python syntax checker or linter.
* **Controlled Test**: Chief proposes a `READY` task in `control_plane.py` specifying the lint skill. The Sonnet builder claims the lease, executes `/verify` natively via the skill, and writes the stdout back to `candidate_evidence`.
* **Side Effects**: Zero. No production dispatch, no SQLite writes (beyond the control plane ledger itself), no network calls.

---

## 6. VERDICT

**GO WITH CONDITIONS.**

This architecture strictly enhances the fleet's verification loop, provided the following conditions are met:
1. **No Duplication**: Skills live exclusively in `.claude/skills/`. Packets hold only references and boundaries.
2. **Execution Isolation**: Only Claude Code natively runs the skills; all other agents only read the receipts.
3. **Control Plane Governance**: `control_plane.py` acts as the ledger for skill dispatch, ensuring timeouts, attempt limits, and safety limits (like the existing `DETECTOR_FORBIDDEN_ACTION_TEXT` checks) are enforced.
