"""
syscat_synchronizer.py — Unit 3: Consumers + pipeline orchestration.

Imports Unit 1 (SystemCatalogStore) and Unit 2 (discovery_scan) and wires
the 9-step run_discovery_scan pipeline:
  1. Load registry
  2. Capture each repo + worktrees
  3. Parse repo metadata
  4. Generate ONE immutable scan_id
  5. begin_scan (status='RUNNING'), record_* all rows
  6. rebuild_graphify (from catalog rows)
  7. rebuild_map_room (from catalog rows)
  8. build_scan_receipt
  9. finalize_scan (COMPLETE/PARTIAL); PARTIAL-block: do NOT promote

HARD RULES (binding per spec §A):
- Metadata-only: NEVER store/surface business/invoice/PII/message bodies.
- Read-only discovery: NEVER write/modify a scanned repo.
- honor excluded_paths.
- NO network/send/money behavior.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from system_catalog_store import SystemCatalogStore
import discovery_scan as ds

logger = logging.getLogger(__name__)

_DEFAULT_DB = "/home/openclaw/state/system_catalog/system_catalog.sqlite3"
_DEFAULT_MAP_ROOM = "openclaw_filesystem_map_room_terrain.json"
_DEFAULT_GRAPHIFY = "openclaw_filesystem_graphiffy.json"


# ---------------------------------------------------------------------------
# Public: Scan receipt builder
# ---------------------------------------------------------------------------

def build_scan_receipt(
    scan_id: str,
    now_iso: str,
    tool_version: str,
    repo_states: list[dict],
    coverage_gaps: list[str],
    excluded_paths: list[str],
) -> dict:
    """
    Build the Scan Receipt dict that matches the audit contract shape:
    {
      scan_id, timestamp, tool_version,
      repositories: [{path, branch, head_commit, worktrees, dirty, coverage}],
      failures, coverage_gaps, excluded_paths
    }
    repo_states is the list of captured repo dicts (from capture_repo_state + parse
    enrichment), each expected to have: repo_path, branch, head_commit, dirty,
    coverage, worktrees (list of worktree dicts).
    Metadata-only: no business/PII columns.
    """
    repositories = []
    failures = []
    for rs in repo_states:
        repo_path = rs.get("repo_path", rs.get("path", ""))
        coverage = rs.get("coverage", "UNAVAILABLE")
        if coverage == "UNAVAILABLE":
            failures.append({"path": repo_path, "reason": "UNAVAILABLE"})
        wt_paths = [wt.get("worktree_path", wt.get("path", "")) for wt in rs.get("worktrees", [])]
        repositories.append(
            {
                "path": repo_path,
                "branch": rs.get("branch", ""),
                "head_commit": rs.get("head_commit", ""),
                "worktrees": wt_paths,
                "dirty": bool(rs.get("dirty", False)),
                "coverage": coverage,
            }
        )
    return {
        "scan_id": scan_id,
        "timestamp": now_iso,
        "tool_version": tool_version,
        "repositories": repositories,
        "failures": failures,
        "coverage_gaps": coverage_gaps,
        "excluded_paths": excluded_paths,
    }


# ---------------------------------------------------------------------------
# Public: Map Room rebuilder (from catalog rows, NOT filesystem)
# ---------------------------------------------------------------------------

def rebuild_map_room(
    store: SystemCatalogStore,
    scan_id: str,
    out_path: str = _DEFAULT_MAP_ROOM,
) -> dict:
    """
    Rebuild the Map Room terrain JSON strictly from catalog rows.
    The terrain view reflects the catalog snapshot (not a live filesystem walk).
    Writes the JSON to out_path and returns the dict.
    Embeds scan_id + generated_utc for freshness tracking (spec §E).
    Metadata-only: no business/invoice/PII columns.
    """
    generated_utc = datetime.now(timezone.utc).isoformat()

    repos = store.list_repositories(scan_id)
    worktrees = store.list_worktrees(scan_id)
    components = store.list_components(scan_id)
    capabilities = store.list_capabilities(scan_id)
    queues = store.list_queues(scan_id)
    handoffs = store.list_handoffs(scan_id)
    tests = store.list_tests(scan_id)

    # Build a repo-keyed terrain map
    terrain: dict[str, Any] = {}
    for repo in repos:
        rp = repo["repo_path"]
        terrain[rp] = {
            "repo_path": rp,
            "branch": repo.get("branch", ""),
            "head_commit": repo.get("head_commit", ""),
            "dirty": bool(repo.get("dirty", 0)),
            "coverage": repo.get("coverage", "UNAVAILABLE"),
            "is_root": bool(repo.get("is_root", 0)),
            "worktrees": [],
            "components": [],
            "capabilities": [],
            "queues": [],
            "handoffs": [],
            "tests": [],
        }

    # Attach worktrees
    for wt in worktrees:
        rp = wt.get("repo_path", "")
        if rp in terrain:
            terrain[rp]["worktrees"].append(
                {
                    "worktree_path": wt.get("worktree_path", ""),
                    "branch": wt.get("branch", ""),
                    "head_commit": wt.get("head_commit", ""),
                    "dirty": bool(wt.get("dirty", 0)),
                }
            )

    # Attach components (metadata pointers only)
    for comp in components:
        rp = comp.get("repo_path", "")
        if rp in terrain:
            terrain[rp]["components"].append(
                {
                    "component_id": comp.get("component_id", ""),
                    "name": comp.get("name", ""),
                    "kind": comp.get("kind", ""),
                    "source_ref": comp.get("source_ref", ""),
                }
            )

    # Attach capabilities (metadata pointers only)
    for cap in capabilities:
        rp = cap.get("repo_path", "")
        if rp in terrain:
            terrain[rp]["capabilities"].append(
                {
                    "capability_id": cap.get("capability_id", ""),
                    "name": cap.get("name", ""),
                    "status": cap.get("status", ""),
                    "source_ref": cap.get("source_ref", ""),
                }
            )

    # Attach queues (metadata only — no raw message content)
    for q in queues:
        rp = q.get("repo_path", "")
        if rp in terrain:
            terrain[rp]["queues"].append(
                {
                    "queue_path": q.get("queue_path", ""),
                    "item_count": q.get("item_count", 0),
                    "states_json": q.get("states_json", "{}"),
                }
            )

    # Attach handoffs
    for hd in handoffs:
        rp = hd.get("repo_path", "")
        if rp in terrain:
            terrain[rp]["handoffs"].append(
                {
                    "handoff_path": hd.get("handoff_path", ""),
                    "checkpoint": hd.get("checkpoint", ""),
                    "updated_utc": hd.get("updated_utc", ""),
                }
            )

    # Attach tests (metadata pointer only)
    for t in tests:
        rp = t.get("repo_path", "")
        if rp in terrain:
            terrain[rp]["tests"].append(
                {
                    "test_path": t.get("test_path", ""),
                    "count": t.get("count", 0),
                }
            )

    terrain_list = list(terrain.values())
    output = {
        "scan_id": scan_id,
        "generated_utc": generated_utc,
        # `repositories` is the catalog-traceable repo list (each entry carries
        # repo_path), per the consumer-rebuild contract (F-6). `terrain` is kept
        # as the richer nested view for existing Map Room readers (spec D4).
        "repositories": terrain_list,
        "terrain": terrain_list,
    }
    _write_json(out_path, output)
    logger.info("Map Room written to %s (scan_id=%s)", out_path, scan_id)
    return output


# ---------------------------------------------------------------------------
# Public: Graphify rebuilder (relationship index from catalog, NOT filesystem)
# ---------------------------------------------------------------------------

def rebuild_graphify(
    store: SystemCatalogStore,
    scan_id: str,
    out_path: str = _DEFAULT_GRAPHIFY,
) -> dict:
    """
    Rebuild the Graphify relationship index JSON strictly from catalog nodes.
    No raw domain/PII. Embeds scan_id + generated_utc.
    Writes the JSON to out_path and returns the dict.
    The graph nodes are metadata pointers; edges express catalog-derivable
    containment and cross-repo relationships (repo->component, repo->worktree,
    component->capability, queue->repo, handoff->repo).
    """
    generated_utc = datetime.now(timezone.utc).isoformat()

    repos = store.list_repositories(scan_id)
    worktrees = store.list_worktrees(scan_id)
    components = store.list_components(scan_id)
    capabilities = store.list_capabilities(scan_id)
    queues = store.list_queues(scan_id)
    handoffs = store.list_handoffs(scan_id)
    tests = store.list_tests(scan_id)

    nodes: list[dict] = []
    edges: list[dict] = []

    # Repo nodes
    for repo in repos:
        rp = repo["repo_path"]
        nodes.append(
            {
                "id": _node_id("repo", rp),
                "type": "repository",
                "label": rp,
                "branch": repo.get("branch", ""),
                "head_commit": repo.get("head_commit", ""),
                "dirty": bool(repo.get("dirty", 0)),
                "coverage": repo.get("coverage", "UNAVAILABLE"),
                "is_root": bool(repo.get("is_root", 0)),
            }
        )

    # Worktree nodes + edges (repo -> worktree)
    for wt in worktrees:
        rp = wt.get("repo_path", "")
        wtp = wt.get("worktree_path", "")
        nodes.append(
            {
                "id": _node_id("worktree", wtp),
                "type": "worktree",
                "label": wtp,
                "branch": wt.get("branch", ""),
                "head_commit": wt.get("head_commit", ""),
                "dirty": bool(wt.get("dirty", 0)),
            }
        )
        edges.append(
            {
                "from": _node_id("repo", rp),
                "to": _node_id("worktree", wtp),
                "relation": "has_worktree",
            }
        )

    # Component nodes + edges (repo -> component)
    for comp in components:
        rp = comp.get("repo_path", "")
        cid = comp.get("component_id", "")
        nodes.append(
            {
                "id": _node_id("component", cid),
                "type": "component",
                "label": comp.get("name", cid),
                "kind": comp.get("kind", ""),
                "source_ref": comp.get("source_ref", ""),
            }
        )
        edges.append(
            {
                "from": _node_id("repo", rp),
                "to": _node_id("component", cid),
                "relation": "contains_component",
            }
        )

    # Capability nodes + edges (repo -> capability)
    for cap in capabilities:
        rp = cap.get("repo_path", "")
        cap_id = cap.get("capability_id", "")
        nodes.append(
            {
                "id": _node_id("capability", cap_id),
                "type": "capability",
                "label": cap.get("name", cap_id),
                "status": cap.get("status", ""),
                "source_ref": cap.get("source_ref", ""),
            }
        )
        edges.append(
            {
                "from": _node_id("repo", rp),
                "to": _node_id("capability", cap_id),
                "relation": "exposes_capability",
            }
        )

    # Queue nodes + edges (repo -> queue)
    for q in queues:
        rp = q.get("repo_path", "")
        qp = q.get("queue_path", "")
        nodes.append(
            {
                "id": _node_id("queue", qp),
                "type": "queue",
                "label": qp,
                "item_count": q.get("item_count", 0),
                # states_json is aggregate metadata only; not message content
            }
        )
        edges.append(
            {
                "from": _node_id("repo", rp),
                "to": _node_id("queue", qp),
                "relation": "owns_queue",
            }
        )

    # Handoff nodes + edges (repo -> handoff)
    for hd in handoffs:
        rp = hd.get("repo_path", "")
        hp = hd.get("handoff_path", "")
        nodes.append(
            {
                "id": _node_id("handoff", hp),
                "type": "handoff",
                "label": hp,
                "checkpoint": hd.get("checkpoint", ""),
                "updated_utc": hd.get("updated_utc", ""),
            }
        )
        edges.append(
            {
                "from": _node_id("repo", rp),
                "to": _node_id("handoff", hp),
                "relation": "tracks_handoff",
            }
        )

    # Test nodes + edges (repo -> test)
    for t in tests:
        rp = t.get("repo_path", "")
        tp = t.get("test_path", "")
        nodes.append(
            {
                "id": _node_id("test", tp),
                "type": "test",
                "label": tp,
                "count": t.get("count", 0),
            }
        )
        edges.append(
            {
                "from": _node_id("repo", rp),
                "to": _node_id("test", tp),
                "relation": "has_tests",
            }
        )

    output = {
        "scan_id": scan_id,
        "generated_utc": generated_utc,
        "nodes": nodes,
        "edges": edges,
    }
    _write_json(out_path, output)
    logger.info("Graphify written to %s (scan_id=%s)", out_path, scan_id)
    return output


# ---------------------------------------------------------------------------
# Public: Main 9-step pipeline
# ---------------------------------------------------------------------------

def run_discovery_scan(
    registry_path: str,
    *,
    catalog_db: str = _DEFAULT_DB,
    now_iso: str,
    tool_version: str = "syscat-v1",
    map_room_path: str = _DEFAULT_MAP_ROOM,
    graphify_path: str = _DEFAULT_GRAPHIFY,
    excluded_paths: list[str] | None = None,
) -> dict:
    """
    Execute the full 9-step discovery + catalog pipeline.

    Steps:
      1. load_registry -> repo list
      2. capture_repo_state per repo + worktrees
      3. parse_repo_metadata per repo
      4. generate_scan_id (deterministic from capture, injected now_iso)
      5. begin_scan (status=RUNNING), record all rows into SystemCatalogStore
      6. rebuild_graphify FROM catalog rows
      7. rebuild_map_room FROM catalog rows
      8. build_scan_receipt
      9. PARTIAL-block + finalize_scan (COMPLETE|PARTIAL)

    PARTIAL rule (spec §A-4 / §D-9): if ANY repo coverage==UNAVAILABLE the scan
    finalizes as PARTIAL and get_current_scan() must still return the prior COMPLETE
    (the store enforces this by only promoting COMPLETE scans as current).

    Returns the scan receipt dict.
    """
    if excluded_paths is None:
        excluded_paths = []

    # -----------------------------------------------------------------------
    # Step 1: Discover — load registry
    # -----------------------------------------------------------------------
    logger.info("[SYSCAT] Step 1: loading registry from %s", registry_path)
    registry_entries = ds.load_registry(registry_path)
    logger.info("[SYSCAT] Registry loaded: %d entries", len(registry_entries))

    # -----------------------------------------------------------------------
    # Step 2: Capture — read-only git state per repo + worktrees
    # -----------------------------------------------------------------------
    logger.info("[SYSCAT] Step 2: capturing repo states")
    repo_states: list[dict] = []
    for entry in registry_entries:
        repo_path = entry["repo_path"]
        # §A.5 / §F-9 — read-only, bounded discovery: a registered repo that
        # falls under an excluded/blocked prefix is NOT scanned, captured, or
        # catalogued. We skip it entirely (never run git on it) rather than
        # recording it as VERIFIED. It is an intentional exclusion, not an
        # UNAVAILABLE gap, so it does not force the scan to PARTIAL.
        if _is_under_excluded(repo_path, excluded_paths):
            logger.info("[SYSCAT] Skipping excluded repo: %s", repo_path)
            continue
        state = ds.capture_repo_state(repo_path)
        state["repo_path"] = repo_path
        state["is_root"] = bool(entry.get("is_root", False))
        repo_states.append(state)
        logger.debug("[SYSCAT] Captured %s coverage=%s", repo_path, state.get("coverage"))

    # -----------------------------------------------------------------------
    # Step 3: Parse — durable specs, queues, tests, components, capabilities
    # -----------------------------------------------------------------------
    logger.info("[SYSCAT] Step 3: parsing repo metadata")
    parsed_meta: dict[str, dict] = {}
    for state in repo_states:
        repo_path = state["repo_path"]
        if state.get("coverage") == "UNAVAILABLE":
            parsed_meta[repo_path] = {
                "components": [], "capabilities": [], "queues": [],
                "handoffs": [], "tests": [],
            }
        else:
            try:
                parsed_meta[repo_path] = ds.parse_repo_metadata(
                    repo_path, excluded_paths=excluded_paths
                )
            except Exception as exc:
                logger.warning("[SYSCAT] parse_repo_metadata failed for %s: %s", repo_path, exc)
                parsed_meta[repo_path] = {
                    "components": [], "capabilities": [], "queues": [],
                    "handoffs": [], "tests": [],
                }

    # -----------------------------------------------------------------------
    # Step 4: Generate ONE immutable scan_id
    # -----------------------------------------------------------------------
    logger.info("[SYSCAT] Step 4: generating scan_id")
    scan_id = ds.generate_scan_id(repo_states, now_iso)
    logger.info("[SYSCAT] scan_id=%s", scan_id)

    # -----------------------------------------------------------------------
    # Step 5: Populate catalog transactionally
    # -----------------------------------------------------------------------
    logger.info("[SYSCAT] Step 5: populating catalog (scan_id=%s)", scan_id)
    coverage_gaps: list[str] = []

    with SystemCatalogStore(catalog_db) as store:
        store.begin_scan_with_id(scan_id=scan_id, tool_version=tool_version, now_iso=now_iso)

        for state in repo_states:
            repo_path = state["repo_path"]
            coverage = state.get("coverage", "UNAVAILABLE")

            if coverage == "UNAVAILABLE":
                coverage_gaps.append(repo_path)

            store.record_repository(
                scan_id=scan_id,
                repo_path=repo_path,
                branch=state.get("branch", ""),
                head_commit=state.get("head_commit", ""),
                dirty=bool(state.get("dirty", False)),
                coverage=coverage,
                is_root=bool(state.get("is_root", False)),
            )

            # Record worktrees
            for wt in state.get("worktrees", []):
                wt_path = wt.get("worktree_path", wt.get("path", ""))
                store.record_worktree(
                    scan_id=scan_id,
                    repo_path=repo_path,
                    worktree_path=wt_path,
                    branch=wt.get("branch", ""),
                    head_commit=wt.get("head_commit", ""),
                    dirty=bool(wt.get("dirty", False)),
                )

            # Record parsed metadata
            meta = parsed_meta.get(repo_path, {})

            for comp in meta.get("components", []):
                store.record_component(
                    scan_id=scan_id,
                    repo_path=repo_path,
                    component_id=comp.get("component_id", ""),
                    name=comp.get("name", ""),
                    kind=comp.get("kind", ""),
                    source_ref=comp.get("source_ref", ""),
                )

            for cap in meta.get("capabilities", []):
                store.record_capability(
                    scan_id=scan_id,
                    repo_path=repo_path,
                    capability_id=cap.get("capability_id", ""),
                    name=cap.get("name", ""),
                    status=cap.get("status", ""),
                    source_ref=cap.get("source_ref", ""),
                )

            for q in meta.get("queues", []):
                store.record_queue(
                    scan_id=scan_id,
                    repo_path=repo_path,
                    queue_path=q.get("queue_path", ""),
                    item_count=int(q.get("item_count", 0)),
                    states_json=q.get("states_json", "{}"),
                )

            for hd in meta.get("handoffs", []):
                store.record_handoff(
                    scan_id=scan_id,
                    repo_path=repo_path,
                    handoff_path=hd.get("handoff_path", ""),
                    checkpoint=hd.get("checkpoint", ""),
                    updated_utc=hd.get("updated_utc", ""),
                )

            for t in meta.get("tests", []):
                store.record_test(
                    scan_id=scan_id,
                    repo_path=repo_path,
                    test_path=t.get("test_path", ""),
                    count=int(t.get("count", 0)),
                )

        # -------------------------------------------------------------------
        # Step 6: Rebuild Graphify FROM catalog rows (inside the store context
        #         so store is open; pass it directly)
        # -------------------------------------------------------------------
        logger.info("[SYSCAT] Step 6: rebuilding Graphify")
        rebuild_graphify(store, scan_id, out_path=graphify_path)

        # -------------------------------------------------------------------
        # Step 7: Rebuild Map Room FROM catalog rows
        # -------------------------------------------------------------------
        logger.info("[SYSCAT] Step 7: rebuilding Map Room")
        rebuild_map_room(store, scan_id, out_path=map_room_path)

        # -------------------------------------------------------------------
        # Step 8: Build Scan Receipt
        # -------------------------------------------------------------------
        logger.info("[SYSCAT] Step 8: building scan receipt")
        receipt = build_scan_receipt(
            scan_id=scan_id,
            now_iso=now_iso,
            tool_version=tool_version,
            repo_states=repo_states,
            coverage_gaps=coverage_gaps,
            excluded_paths=excluded_paths,
        )

        # -------------------------------------------------------------------
        # Step 9: PARTIAL-block + finalize_scan
        # -------------------------------------------------------------------
        any_unavailable = any(
            s.get("coverage", "UNAVAILABLE") == "UNAVAILABLE" for s in repo_states
        )
        final_status = "PARTIAL" if any_unavailable else "COMPLETE"
        logger.info("[SYSCAT] Step 9: finalizing scan status=%s", final_status)

        # Unit1 finalize_scan computes repo_count/dirty_count from DB rows.
        store.finalize_scan(
            scan_id=scan_id,
            status=final_status,
            coverage_gaps=coverage_gaps,
            excluded_paths=excluded_paths,
            receipt_json=json.dumps(receipt),
        )

    if any_unavailable:
        logger.warning(
            "[SYSCAT] Scan %s finalized as PARTIAL — %d unavailable repos. "
            "Not promoted as current. Prior COMPLETE scan remains current.",
            scan_id,
            len(coverage_gaps),
        )
    else:
        logger.info("[SYSCAT] Scan %s finalized as COMPLETE.", scan_id)

    return receipt


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_under_excluded(repo_path: str, excluded_paths: list[str]) -> bool:
    """
    True if repo_path equals or is nested under any excluded/blocked prefix.
    Uses resolved absolute paths and a path-component boundary so that
    '/a/excluded' does not spuriously match '/a/excluded_other'.
    """
    if not excluded_paths:
        return False
    try:
        target = Path(repo_path).resolve()
    except (OSError, ValueError):
        target = Path(repo_path)
    for ex in excluded_paths:
        if not ex:
            continue
        try:
            ex_resolved = Path(ex).resolve()
        except (OSError, ValueError):
            ex_resolved = Path(ex)
        if target == ex_resolved:
            return True
        try:
            target.relative_to(ex_resolved)
            return True
        except ValueError:
            continue
    return False


def _node_id(kind: str, value: str) -> str:
    """Stable, deterministic node ID string for Graphify nodes."""
    return f"{kind}:{value}"


def _write_json(out_path: str, data: dict) -> None:
    """Write JSON to out_path, creating parent dirs as needed. Atomic-ish via
    write-to-path (no tmp+rename needed for catalog consumers; they read after
    finalize)."""
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
