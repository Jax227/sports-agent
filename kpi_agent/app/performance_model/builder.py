"""
Performance model tree builder.

Builds a hierarchical performance model from merged determinant candidates,
organized by the 8-category taxonomy.
"""

import logging
from datetime import datetime
from typing import Optional

from app.performance_model.taxonomy import CATEGORIES, get_category_name_cn, get_category_name_en

logger = logging.getLogger(__name__)


def build_performance_model_from_candidates(
    candidates: list,
    project_id: Optional[int] = None,
) -> dict:
    """Build a performance model hierarchy from determinant candidates.

    Args:
        candidates: List of DeterminantCandidate objects (merged).
        project_id: Optional project ID for linking.

    Returns:
        Dict with model tree structure:
        {
            "categories": [...],
            "total_candidates": N,
            "category_summary": {...},
            "candidates": [...],
            "orphans": [...],
        }
    """
    # Group candidates by category
    by_category: dict[str, list] = {}
    orphans = []

    for c in candidates:
        cat = _get_attr(c, 'category_key', 'other_uncertain')
        if cat in CATEGORIES:
            by_category.setdefault(cat, []).append(c)
        else:
            by_category.setdefault("other_uncertain", []).append(c)

    # Build tree
    model_tree = {
        "categories": [],
        "total_candidates": len(candidates),
        "category_summary": {},
        "candidates": [_candidate_to_dict(c) for c in candidates],
        "orphans": [],
        "generated_at": datetime.utcnow().isoformat(),
    }

    for cat_key in CATEGORIES:
        cat_info = CATEGORIES[cat_key]
        cat_candidates = by_category.get(cat_key, [])

        # Sort by confidence * evidence_strength
        cat_candidates_sorted = sorted(
            cat_candidates,
            key=lambda c: (
                _get_attr(c, 'confidence_score', 0) * _get_attr(c, 'evidence_strength_score', 0)
            ),
            reverse=True,
        )

        node = {
            "category_key": cat_key,
            "name_cn": cat_info["name_cn"],
            "name_en": cat_info["name_en"],
            "description": cat_info["description"],
            "candidate_count": len(cat_candidates_sorted),
            "total_evidence_count": sum(len(_get_attr(c, 'source_literature_ids', [])) for c in cat_candidates_sorted),
            "candidates": [_candidate_to_dict(c) for c in cat_candidates_sorted],
        }

        model_tree["categories"].append(node)
        model_tree["category_summary"][cat_key] = {
            "count": len(cat_candidates_sorted),
            "top_candidates": [
                _get_attr(c, 'canonical_name', '')
                for c in cat_candidates_sorted[:5]
            ],
        }

    # Identify orphans (other_uncertain)
    uncat = by_category.get("other_uncertain", [])
    for c in uncat:
        model_tree["orphans"].append({
            "canonical_name": _get_attr(c, 'canonical_name', ''),
            "display_name_en": _get_attr(c, 'display_name_en', ''),
            "evidence_count": len(_get_attr(c, 'source_literature_ids', [])),
            "reason": "Could not classify into any of the 8 main categories",
        })

    return model_tree


def _get_attr(obj, attr: str, default=None):
    """Get attribute from object or dict."""
    if hasattr(obj, attr):
        return getattr(obj, attr, default)
    return obj.get(attr, default) if isinstance(obj, dict) else default


def _candidate_to_dict(c) -> dict:
    """Convert candidate (object or dict) to a serializable dict."""
    if hasattr(c, 'to_dict'):
        return c.to_dict()
    if isinstance(c, dict):
        return c
    return {
        "canonical_name": getattr(c, 'canonical_name', ''),
        "display_name_en": getattr(c, 'display_name_en', ''),
        "category_key": getattr(c, 'category_key', 'other_uncertain'),
    }


def build_performance_model_tree_for_db(
    candidates: list,
    project_id: int,
) -> list[dict]:
    """Build records ready for insertion into the performance_determinants table.

    Returns a list of dicts with fields matching the PerformanceDeterminant model:
    - name, category, parent_id, description, importance, evidence_level, source_summary
    """
    tree = build_performance_model_from_candidates(candidates, project_id)
    records = []

    for cat_node in tree["categories"]:
        # Create category-level node
        cat_rec = {
            "project_id": project_id,
            "parent_id": None,
            "category": cat_node["name_cn"],
            "name": cat_node["name_cn"],
            "description": cat_node.get("description", ""),
            "importance": "high" if cat_node["candidate_count"] >= 3 else "medium",
            "evidence_level": "中",
            "source_summary": f"{cat_node['candidate_count']} candidates from literature",
        }
        records.append(cat_rec)

        # Create child nodes for each high-confidence candidate
        for cand in cat_node["candidates"]:
            conf = cand.get("confidence_score", 0)
            ev_count = len(cand.get("source_literature_ids", []))

            cand_rec = {
                "project_id": project_id,
                "parent_id": None,  # will be set after category nodes are created
                "category": cat_node["name_cn"],
                "name": cand.get("display_name_en", cand.get("canonical_name", "")),
                "description": _build_description(cand),
                "importance": "high" if ev_count >= 3 else "medium",
                "evidence_level": _confidence_to_evidence_level(conf),
                "source_summary": f"Evidence from {ev_count} paper(s), score={conf:.2f}",
            }
            records.append(cand_rec)

    return records


def _build_description(cand: dict) -> str:
    """Build a description string for a candidate."""
    parts = []
    if cand.get("display_name_en"):
        parts.append(cand["display_name_en"])
    aliases = cand.get("aliases", [])
    if aliases:
        parts.append(f"Also known as: {', '.join(aliases[:5])}")
    methods = cand.get("extraction_methods", [])
    if methods:
        parts.append(f"Extracted by: {', '.join(methods)}")
    return "; ".join(parts)


def _confidence_to_evidence_level(confidence: float) -> str:
    """Map confidence score (0-1) to evidence level string."""
    if confidence >= 0.7:
        return "高"
    elif confidence >= 0.4:
        return "中"
    elif confidence >= 0.2:
        return "低"
    else:
        return "未知"


def generate_kpi_candidates_from_determinants(
    determinant_ids: list[int],
) -> list[dict]:
    """Stub: Generate KPI candidates from accepted determinants.

    This is a placeholder for future KPI generation logic.
    Currently returns simple candidates based on determinant names.
    """
    # This would query the DB for accepted determinants and suggest KPIs.
    # For now, return a stub.
    return [
        {
            "determinant_id": did,
            "suggested_kpi_name": f"KPI for determinant {did}",
            "evidence_count": 0,
            "status": "stub",
        }
        for did in determinant_ids
    ]
