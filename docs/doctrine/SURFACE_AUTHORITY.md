# Surface Authority

This doctrine defines the hierarchy of truth surfaces in the OpenClaw repository and resolves ambiguity between mirrors.

## 1. Authority Classes

| Class | Description | Authority |
| :--- | :--- | :--- |
| **Canonical** | The primary source of truth for runtime data and state. | Repository Root (`/home/openclaw/`) |
| **Working Note** | Active operational logs and handoff surfaces. | `/mnt/c/Users/Winship/OpenClaw_Watch/` |
| **Mirror** | Read-only or unreliable replicas of canonical surfaces. | Mac-local folders |
| **Archive** | Historical residue; no longer governing. | `archive/` folders |

## 2. Canonical Anchors

Agents MUST treat the following paths as the absolute authority for their respective data types:

- **Logs & State**: `/mnt/c/OpenClaw/logs/` and `/home/openclaw/OpenClaw/state/`.
- **The Vault**: `/mnt/c/OpenClawShared/openclaw-vault/`.
- **Operational Logic**: The Python modules in `/home/openclaw/`.
- **Running Notes**: `/mnt/c/Users/Winship/OpenClaw_Watch/Cassandra_Chief_Model.md`.

## 3. The Mirror Rule
Mac-local folders (e.g., `mac_eyes/`) are **Mirrors**. 
- Agents MUST NOT use Mac-local mirrors as a source of truth for repository state or operational laws.
- Agents MUST NOT attempt to sync changes FROM a mirror back to a Canonical surface unless explicitly instructed by the operator.

## 4. Working Note Authority
The PC-side "Watch" folder is the designated **Working Note** surface. 
- All agents working on the "Watch" task MUST use the file in `/mnt/c/Users/Winship/OpenClaw_Watch/` as the canonical running note.
- Do not check or update the Mac-side equivalent unless specifically tasked.
