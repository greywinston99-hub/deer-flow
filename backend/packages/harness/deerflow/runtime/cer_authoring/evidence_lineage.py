"""Evidence Lineage Graph for CER Authoring.

Builds a directed graph of evidence-to-claim, evidence-to-evidence,
and evidence-to-source relationships from SharedAuthoringState.

Stored in SQLite for persistence and cross-project querying.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Lazy import networkx — fail gracefully if not installed
try:
    import networkx as nx
except ImportError:
    nx = None  # type: ignore


class EvidenceLineageGraph:
    """Directed graph of evidence relationships with SQLite persistence."""

    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else None
        self._g = nx.DiGraph() if nx else None
        self._dirty = False

    # ── Build from state ────────────────────────────────────────────────────────

    def build_from_state(self, state: dict[str, Any]) -> None:
        """Populate graph from a SharedAuthoringState dict."""
        if self._g is None:
            logger.warning("networkx not installed — lineage graph disabled")
            return

        project_id = str(state.get("project_id") or "unknown")
        evidence_registry = state.get("evidence_registry") or []
        claim_ledger = state.get("claim_ledger") or []
        claim_evidence_matrix = state.get("claim_evidence_matrix") or []
        article_appraisal = state.get("article_appraisal") or []
        fulltext_table = state.get("fulltext_acquisition_status_table") or []
        source_inventory = state.get("source_inventory") or []

        # 1. Add evidence nodes
        appraisal_by_id = {str(a.get("evidence_id") or ""): a for a in article_appraisal if a.get("evidence_id")}
        fulltext_by_id = {str(f.get("evidence_id") or ""): f for f in fulltext_table if f.get("evidence_id")}

        for ev in evidence_registry:
            eid = str(ev.get("evidence_id") or "")
            if not eid:
                continue
            appraisal = appraisal_by_id.get(eid, {})
            fulltext = fulltext_by_id.get(eid, {})
            self._add_evidence_node(eid, ev, appraisal, fulltext, project_id)

        # 2. Add claim nodes
        for claim in claim_ledger:
            cid = str(claim.get("claim_id") or "")
            if not cid:
                continue
            self._g.add_node(
                cid,
                node_type="claim",
                claim_text=str(claim.get("claim_text", ""))[:200],
                claim_type=str(claim.get("claim_type", "")),
                project_id=project_id,
            )

        # 3. Add source nodes
        for src in source_inventory:
            sid = str(src.get("source_id") or src.get("file_id") or "")
            if not sid:
                continue
            self._g.add_node(
                sid,
                node_type="source",
                source_type=str(src.get("source_type") or src.get("document_type") or ""),
                filename=str(src.get("filename") or ""),
                project_id=project_id,
            )

        # 4. Link evidence → claim (from claim_evidence_matrix)
        for row in claim_evidence_matrix:
            cid = str(row.get("claim_id") or "")
            eids = str(row.get("evidence_ids") or "").split(",")
            for eid_raw in eids:
                eid = eid_raw.strip()
                if cid and eid and self._g.has_node(cid) and self._g.has_node(eid):
                    self._g.add_edge(eid, cid, relation="supports", project_id=project_id)

        # 5. Link evidence → source (from evidence_registry source_type / pmid)
        for ev in evidence_registry:
            eid = str(ev.get("evidence_id") or "")
            pmid = str(ev.get("pmid") or "")
            source_type = str(ev.get("source_type") or "").lower()
            # Link to source_inventory by source_type match
            for src in source_inventory:
                sid = str(src.get("source_id") or src.get("file_id") or "")
                st = str(src.get("source_type") or src.get("document_type") or "").lower()
                if sid and eid and source_type and st and source_type in st:
                    if self._g.has_node(eid) and self._g.has_node(sid):
                        self._g.add_edge(eid, sid, relation="sourced_from", project_id=project_id)

        # 6. Link evidence → evidence (citation chains via pmid / related_pmids)
        for ev in evidence_registry:
            eid = str(ev.get("evidence_id") or "")
            related = ev.get("related_evidence_ids") or ev.get("cited_by") or []
            if isinstance(related, str):
                related = [r.strip() for r in related.split(",")]
            for rel_eid in related:
                rel = str(rel_eid).strip()
                if rel and eid and rel != eid:
                    if self._g.has_node(eid) and self._g.has_node(rel):
                        self._g.add_edge(rel, eid, relation="cited_by", project_id=project_id)

        self._dirty = True
        logger.info(
            "Built evidence lineage: %d nodes, %d edges for project %s",
            self._g.number_of_nodes(),
            self._g.number_of_edges(),
            project_id,
        )

    def _add_evidence_node(
        self,
        eid: str,
        ev: dict[str, Any],
        appraisal: dict[str, Any],
        fulltext: dict[str, Any],
        project_id: str,
    ) -> None:
        if self._g is None:
            return
        depth = str(ev.get("evidence_depth") or "").upper()
        weight = str(ev.get("weight") or appraisal.get("weight") or "").lower()
        self._g.add_node(
            eid,
            node_type="evidence",
            pmid=str(ev.get("pmid") or ""),
            evidence_depth=depth,
            weight=weight,
            source_type=str(ev.get("source_type") or ""),
            device_relationship=str(ev.get("device_relationship") or ""),
            full_text_status=str(fulltext.get("full_text_retrieval_status") or fulltext.get("full_text_available") or ""),
            appraisal_score=appraisal.get("evidence_strength_score"),
            project_id=project_id,
        )

    # ── Queries ────────────────────────────────────────────────────────────────

    def get_upstream_claims(self, evidence_id: str) -> list[dict[str, Any]]:
        """Return claims directly supported by this evidence."""
        if self._g is None:
            return []
        claims = []
        for _, target, data in self._g.out_edges(evidence_id, data=True):
            if self._g.nodes[target].get("node_type") == "claim":
                claims.append({
                    "claim_id": target,
                    "claim_text": self._g.nodes[target].get("claim_text", ""),
                    "relation": data.get("relation", "supports"),
                })
        return claims

    def get_downstream_evidence(self, claim_id: str) -> list[dict[str, Any]]:
        """Return evidence directly supporting this claim."""
        if self._g is None:
            return []
        evidence = []
        for source, _, data in self._g.in_edges(claim_id, data=True):
            if self._g.nodes[source].get("node_type") == "evidence":
                evidence.append({
                    "evidence_id": source,
                    "relation": data.get("relation", "supports"),
                    **self._g.nodes[source],
                })
        return evidence

    def detect_chain_breaks(self) -> list[dict[str, Any]]:
        """Detect broken chains: orphan claims, missing evidence, dangling edges."""
        if self._g is None:
            return []
        breaks: list[dict[str, Any]] = []

        # Orphan claims: no incoming evidence edges
        for node, attrs in self._g.nodes(data=True):
            if attrs.get("node_type") == "claim":
                has_evidence = any(
                    self._g.nodes[src].get("node_type") == "evidence"
                    for src, _ in self._g.in_edges(node)
                )
                if not has_evidence:
                    breaks.append({
                        "type": "orphan_claim",
                        "claim_id": node,
                        "claim_text": attrs.get("claim_text", ""),
                        "severity": "CRITICAL",
                        "message": f"Claim {node} has no supporting evidence",
                    })

        # Evidence without source
        for node, attrs in self._g.nodes(data=True):
            if attrs.get("node_type") == "evidence":
                has_source = any(
                    self._g.nodes[tgt].get("node_type") == "source"
                    for _, tgt in self._g.out_edges(node)
                )
                if not has_source and attrs.get("pmid"):
                    breaks.append({
                        "type": "missing_source",
                        "evidence_id": node,
                        "pmid": attrs.get("pmid", ""),
                        "severity": "HIGH",
                        "message": f"Evidence {node} has PMID but no linked source",
                    })

        # Depth violation: pivotal evidence not PRIMARY
        for node, attrs in self._g.nodes(data=True):
            if attrs.get("node_type") == "evidence" and attrs.get("weight") == "pivotal":
                depth = str(attrs.get("evidence_depth") or "").upper()
                if depth and depth not in {"PRIMARY_VERBATIM", "PRIMARY_DERIVED"}:
                    breaks.append({
                        "type": "depth_violation",
                        "evidence_id": node,
                        "evidence_depth": depth,
                        "severity": "HIGH",
                        "message": f"Pivotal evidence {node} has insufficient depth: {depth}",
                    })

        return breaks

    def export_for_audit(self) -> dict[str, Any]:
        """Export lineage as audit-ready JSON."""
        if self._g is None:
            return {"error": "networkx not available"}
        nodes = [
            {"id": n, **self._g.nodes[n]}
            for n in self._g.nodes()
        ]
        edges = [
            {"source": u, "target": v, **d}
            for u, v, d in self._g.edges(data=True)
        ]
        return {
            "schema": "evidence_lineage_v1",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": nodes,
            "edges": edges,
            "chain_breaks": self.detect_chain_breaks(),
        }

    # ── Persistence ─────────────────────────────────────────────────────────────

    def save(self) -> None:
        """Persist graph to SQLite."""
        if self.db_path is None or self._g is None or not self._dirty:
            return
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS evidence_lineage_nodes (
                    id TEXT PRIMARY KEY,
                    node_type TEXT NOT NULL,
                    project_id TEXT,
                    attrs TEXT NOT NULL,
                    updated_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS evidence_lineage_edges (
                    source TEXT NOT NULL,
                    target TEXT NOT NULL,
                    relation TEXT,
                    project_id TEXT,
                    attrs TEXT,
                    PRIMARY KEY (source, target)
                )
            """)
            now = datetime.now(timezone.utc).isoformat()
            for n, attrs in self._g.nodes(data=True):
                conn.execute(
                    """INSERT OR REPLACE INTO evidence_lineage_nodes (id, node_type, project_id, attrs, updated_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (n, attrs.get("node_type", ""), attrs.get("project_id", ""), json.dumps(dict(attrs)), now),
                )
            for u, v, d in self._g.edges(data=True):
                conn.execute(
                    """INSERT OR REPLACE INTO evidence_lineage_edges (source, target, relation, project_id, attrs)
                       VALUES (?, ?, ?, ?, ?)""",
                    (u, v, d.get("relation", ""), d.get("project_id", ""), json.dumps(dict(d))),
                )
            conn.commit()
            self._dirty = False
            logger.info("Saved lineage to %s", self.db_path)
        finally:
            conn.close()

    def load(self, project_id: str | None = None) -> None:
        """Load graph from SQLite."""
        if self.db_path is None or self._g is None:
            return
        if not self.db_path.exists():
            return
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.cursor()
            if project_id:
                cursor.execute("SELECT id, node_type, attrs FROM evidence_lineage_nodes WHERE project_id = ?", (project_id,))
            else:
                cursor.execute("SELECT id, node_type, attrs FROM evidence_lineage_nodes")
            for row in cursor.fetchall():
                attrs = json.loads(row[2])
                self._g.add_node(row[0], **attrs)

            if project_id:
                cursor.execute("SELECT source, target, relation, attrs FROM evidence_lineage_edges WHERE project_id = ?", (project_id,))
            else:
                cursor.execute("SELECT source, target, relation, attrs FROM evidence_lineage_edges")
            for row in cursor.fetchall():
                attrs = json.loads(row[3]) if row[3] else {}
                self._g.add_edge(row[0], row[1], relation=row[2], **attrs)
            logger.info("Loaded lineage from %s", self.db_path)
        finally:
            conn.close()
