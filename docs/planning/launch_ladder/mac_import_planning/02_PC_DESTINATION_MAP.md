# PC Destination Map

Proposed mapping from Mac source candidates to PC repository destinations. Destinations favor the existing canonical structure.

| Mac Source Candidate | Proposed PC Destination |
| :--- | :--- |
| `visual_brainstorm_packets/operator_harness_north_star_v1/` | `docs/planning/launch_ladder/visual/` |
| `docs/planning/operator_harness/` (Doctrine Papers) | `docs/planning/launch_ladder/operator_harness_research/` |
| `operator_harness_knowledge_substrate/` | `docs/planning/launch_ladder/knowledge_substrate/` |
| `consolidation_packets/` | `docs/planning/launch_ladder/mac_side_consolidation/` (or `docs/handoffs/` if durable) |
| `06_ledger_invoice_steel_thread/` | `docs/planning/launch_ladder/ledger_invoice_steel_thread/` (Planning only) |

## Note on Code
Implementation code identified in the Mac environment (e.g., `bank_csv_to_reconciliation_report.py`) is NOT mapped to `src/` yet. It will be mapped to a dedicated research/review directory within `docs/` before any integration into the main application source.
