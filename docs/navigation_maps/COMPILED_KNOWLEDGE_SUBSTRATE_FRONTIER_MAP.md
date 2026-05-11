# Compiled Knowledge Substrate Frontier Map

**Artifact Type:** Frontier Map
**Territory/Lane:** compiled_knowledge_substrate
**Current Frontier Commit:** 656d08d

## Built Territory
*These items are completed and cite exact proof.*
- **North Star spec:** `docs/planning/operator_harness/COMPILED_KNOWLEDGE_SUBSTRATE_NORTH_STAR.md`
- **Fixture-only compiled substrate contract:** `compiled_knowledge_substrate.py`
- **Lifecycle states:** Modeled in `compiled_knowledge_substrate.py`
- **Answer packet:** `AnswerPacket` implemented in `compiled_knowledge_substrate.py`
- **Rejected/historical/sensitive/no-export behavior:** Managed in `compiled_knowledge_substrate.py`
- **Static status function:** `compiled_knowledge_substrate_status` in `compiled_knowledge_substrate.py`
- **Operator-frontier-map-status receipt command:** Built and verified via `./scripts/openclaw_receipts.py operator-frontier-map-status`
- **Agent Packet Doctrine Inventory:** Managed in `docs/operations/OPENCLAW_AGENT_PACKET_DOCTRINE_INVENTORY_V0.md`
- **Cassandra Machine Contract:** `docs/operations/CASSANDRA_MACHINE_CONTRACT.md`

## Partial Territory
- **backend_knowledge_packet.py context/export fit review:** Substrate not yet fully integrated into existing context/export surfaces.
- **operator_question_response.py substrate answer packet consumption/adaptation:** Question-response consumption is unproven and needs adaptation.

## Not-Built / Future-Gated
- SQLite authority spine
- Ingestion
- Embeddings/vector retrieval
- PageIndex/tree retrieval implementation
- Graph engine
- Provider/model calls
- MCP integration
- Runtime/Cassandra/Chief/Telegram live wiring
- Private-root/legal/invoice/finance traversal

## Next Unfinished Edges
- Review `backend_knowledge_packet.py` context/export fit before creating any new bridge.
- Decide/define import-safe substrate answer packet adapter for `operator_question_response.py`.
- Keep SQLite authority spine future-gated until map/receipt/bridge-fit truth is durable.
