"""
Build ProposedModelNode objects from merged DimensionAssignments.

Groups assignments by dimension and merges similar candidate terms into
proposed performance model nodes. Each node aggregates evidence from
multiple literature sources.
"""

import logging
from typing import Optional

from app.literature_to_model.schemas import DimensionAssignment, ProposedModelNode
from app.literature_to_model.dimensions import load_default_performance_dimensions

logger = logging.getLogger(__name__)

# ── rapidfuzz availability ────────────────────────────────────────────────

_fuzz_available = None


def _check_fuzz() -> bool:
    global _fuzz_available
    if _fuzz_available is None:
        try:
            from rapidfuzz import fuzz  # noqa: F401
            _fuzz_available = True
        except ImportError:
            _fuzz_available = False
    return _fuzz_available


def _similarity(a: str, b: str) -> float:
    """Token sort ratio similarity (0-1)."""
    if _check_fuzz():
        from rapidfuzz import fuzz
        return fuzz.token_sort_ratio(a, b) / 100.0
    # Fallback: word overlap
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / max(len(words_a), len(words_b))


# ── Node building ─────────────────────────────────────────────────────────

def build_proposed_model_nodes(
    assignments: list[DimensionAssignment],
    fuzzy_threshold: float = 0.80,
    min_confidence: float = 0.0,
    include_review_only: bool = True,
) -> list[ProposedModelNode]:
    """Build proposed model nodes from dimension assignments.

    Groups assignments by dimension, then merges similar terms within each
    dimension into consolidated ProposedModelNode objects.

    Args:
        assignments: List of DimensionAssignment objects.
        fuzzy_threshold: rapidfuzz similarity threshold for merging terms.
        min_confidence: Minimum confidence to include an assignment.
        include_review_only: If True, include all assignments regardless of
            needs_review. If False, exclude needs_review assignments.

    Returns:
        List of ProposedModelNode objects, sorted by confidence.
    """
    # Filter
    filtered = [
        a for a in assignments
        if a.confidence_score >= min_confidence
        and (include_review_only or not a.needs_review)
    ]

    if not filtered:
        logger.info("No assignments meet criteria for node building")
        return []

    # Group by dimension
    by_dimension: dict[str, list[DimensionAssignment]] = {}
    for a in filtered:
        dim = a.assigned_dimension
        if dim not in by_dimension:
            by_dimension[dim] = []
        by_dimension[dim].append(a)

    dim_map = {d.id: d for d in load_default_performance_dimensions()}
    nodes: list[ProposedModelNode] = []

    for dim_id, dim_assignments in by_dimension.items():
        dim = dim_map.get(dim_id)

        # Merge similar terms within this dimension
        merged_groups = _merge_similar_terms(dim_assignments, fuzzy_threshold)

        for group in merged_groups:
            node = _build_node_from_group(group, dim_id, dim)
            nodes.append(node)

    # Sort by confidence descending
    nodes.sort(key=lambda n: n.confidence_score, reverse=True)

    logger.info(
        "Built %d proposed nodes from %d assignments across %d dimensions",
        len(nodes), len(filtered), len(by_dimension),
    )
    return nodes


def _merge_similar_terms(
    assignments: list[DimensionAssignment],
    threshold: float,
) -> list[list[DimensionAssignment]]:
    """Merge assignments with similar terms within a dimension."""
    if len(assignments) <= 1:
        return [[a] for a in assignments]

    # Use union-find style merging
    n = len(assignments)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for i in range(n):
        for j in range(i + 1, n):
            term_i = assignments[i].normalized_term
            term_j = assignments[j].normalized_term
            if _similarity(term_i, term_j) >= threshold:
                union(i, j)

    # Collect groups
    groups: dict[int, list[DimensionAssignment]] = {}
    for i in range(n):
        root = find(i)
        if root not in groups:
            groups[root] = []
        groups[root].append(assignments[i])

    return list(groups.values())


def _build_node_from_group(
    group: list[DimensionAssignment],
    dim_id: str,
    dim: Optional[object],
) -> ProposedModelNode:
    """Build a single ProposedModelNode from a group of similar assignments."""
    # Primary term: the one with the highest confidence
    best = max(group, key=lambda a: a.confidence_score)
    node_name = best.candidate_term
    node_name_en = best.normalized_term

    # Collect evidence as dicts
    evidence_items = [a.to_dict() for a in group]

    # Average confidence across the group
    avg_confidence = round(
        sum(a.confidence_score for a in group) / len(group),
        4,
    )

    # Count unique sources
    unique_sources = len({a.source_literature_id for a in group if a.source_literature_id})

    # Collect aliases from all terms in the group
    aliases = list({a.candidate_term for a in group if a.candidate_term != node_name})
    aliases.extend(
        a.normalized_term for a in group
        if a.normalized_term != node_name_en and a.normalized_term not in aliases
    )
    aliases = list(dict.fromkeys(aliases))  # dedupe preserving order

    # Determine suggested_as
    if avg_confidence >= 0.75:
        suggested_as = "determinant"
    elif avg_confidence >= 0.5:
        suggested_as = "sub_determinant"
    else:
        suggested_as = "kpi_candidate"

    # Determine status
    if avg_confidence >= 0.75:
        status = "proposed"
    else:
        status = "proposed"

    # Build description from evidence sentences
    evidence_preview = group[0].evidence_sentence if group else ""
    if len(evidence_preview) > 200:
        evidence_preview = evidence_preview[:200] + "..."

    parent_dim_name_cn = dim.name_cn if dim else ""

    return ProposedModelNode(
        node_name=node_name,
        node_name_en=node_name_en,
        parent_dimension=dim_id,
        parent_dimension_name_cn=parent_dim_name_cn,
        description=evidence_preview,
        evidence_items=evidence_items,
        confidence_score=avg_confidence,
        source_count=unique_sources,
        suggested_as=suggested_as,
        status=status,
        aliases=aliases,
    )


def export_proposed_nodes_to_dataframe(nodes: list[ProposedModelNode]) -> "pd.DataFrame":
    """Export proposed nodes to a pandas DataFrame for display."""
    import pandas as pd

    records = []
    for n in nodes:
        records.append({
            "节点名称": n.node_name,
            "英文名": n.node_name_en,
            "父维度": n.parent_dimension_name_cn,
            "置信度": n.confidence_score,
            "来源数": n.source_count,
            "建议类型": n.suggested_as,
            "状态": n.status,
            "证据条数": len(n.evidence_items),
            "别名": ", ".join(n.aliases[:5]) if n.aliases else "",
            "描述": n.description[:200] if n.description else "",
        })

    return pd.DataFrame(records)


def apply_accepted_nodes_to_performance_model(
    nodes: list[ProposedModelNode],
    existing_determinants: list[dict],
) -> list[dict]:
    """Apply accepted nodes to the formal performance model.

    Only nodes with status='accepted' are applied. Each node is converted
    to a determinant dict suitable for the performance model ORM.

    Args:
        nodes: ProposedModelNode objects (some may have status='accepted').
        existing_determinants: Current list of determinant dicts in the model.

    Returns:
        Updated list of determinant dicts (existing + newly accepted).
    """
    accepted = [n for n in nodes if n.status == "accepted"]
    if not accepted:
        logger.info("No accepted nodes to apply")
        return existing_determinants

    # Build set of existing names to avoid duplicates
    existing_names = {
        d.get("name", "").lower().strip()
        for d in existing_determinants
    }

    new_determinants = list(existing_determinants)
    added_count = 0

    for node in accepted:
        if node.node_name.lower().strip() in existing_names:
            continue
        if node.node_name_en.lower().strip() in existing_names:
            continue

        new_determinants.append({
            "name": node.node_name,
            "name_en": node.node_name_en,
            "category": node.parent_dimension,
            "description": node.description,
            "evidence_level": "literature",
            "source_summary": (
                f"Extracted from {node.source_count} source(s) via "
                f"literature-to-model pipeline. Confidence: {node.confidence_score:.2f}"
            ),
            "aliases": node.aliases,
            "evidence_items": node.evidence_items,
        })
        existing_names.add(node.node_name.lower().strip())
        existing_names.add(node.node_name_en.lower().strip())
        added_count += 1

    logger.info(
        "Applied %d accepted nodes to performance model (total: %d determinants)",
        added_count, len(new_determinants),
    )
    return new_determinants
