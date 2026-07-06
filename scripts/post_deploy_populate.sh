#!/usr/bin/env bash
# post_deploy_populate.sh — ANTI-BRITTLE #3
# Idempotent data-population run for AFTER a deploy, so the live system is never
# "code-live-but-data-empty" (the class that made orient return empty + the send say "Hello").
#
# Every data-backed feature registers its populate step HERE. Deploy's last step runs this.
# All steps must be IDEMPOTENT (safe to re-run). Failures are reported but don't abort the others.
#
# Usage: scripts/post_deploy_populate.sh   (run from repo root after ff + service restart)
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
PY="/home/openclaw/chief_env/bin/python"
REAL_LEDGER="/home/openclaw/.openclaw/business_ops/ledger.sqlite"
ok=0; fail=0
step() { echo "[populate] $1"; }
run() { if "$@"; then ok=$((ok+1)); else fail=$((fail+1)); echo "  ⚠ step failed (continuing): $*"; fi; }

step "contacts registry seed (idempotent)"
run "$PY" - <<PYEOF
import sys; sys.path.insert(0,'/home/openclaw'); import chief_env; chief_env.load_env()
import contacts_registry as CR
reg=CR.ContactsRegistry(CR.DEFAULT_CONTACTS_DB_PATH); CR.seed_default_contacts(reg)
n=len(reg.get_contacts_for_client('st-annes'))
assert n>0, "contacts seed produced 0 st-annes contacts"
print(f"  contacts: st-annes has {n}")
PYEOF

step "self-knowledge graph write (idempotent)"
run "$PY" - <<PYEOF
import sys; sys.path.insert(0,'/home/openclaw'); import chief_env; chief_env.load_env()
import self_knowledge_graph_writer as GW, self_knowledge_orient as O
r=GW.write_graph_to_ledger('/home/openclaw','$REAL_LEDGER',confirm=True)
assert r.get('status')=='written', f"graph write status={r.get('status')}"
res=O.orient(level='high'); assert 'not_yet_crawled' not in str(res), "orient still empty after write"
print(f"  graph: {r.get('node_count') or r.get('nodes')} nodes, orient OK")
PYEOF

# --- register additional populate steps below (new data-backed features add their call here) ---

echo "[populate] done: ${ok} ok, ${fail} failed"
[ "$fail" -eq 0 ] || echo "[populate] NOTE: ${fail} step(s) failed — investigate; live data may be partial."
exit 0
