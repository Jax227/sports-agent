"""
Rule-based dictionary classification for candidate terms.

Matches extracted candidate terms against the domain dictionary using
keyword lookup, alias matching, and weighted scoring.

This is Layer A of the hybrid 3-layer classification:
  A. Rule dictionary matching ← this module
  B. Semantic similarity (sentence-transformers)
  C. TF-IDF fallback
"""

import logging
from typing import Optional

from app.literature_to_model.schemas import ExtractedCandidate, DimensionAssignment
from app.literature_to_model.dimensions import build_inverted_index, load_default_performance_dimensions

logger = logging.getLogger(__name__)

# ── Lazy-loaded inverted index and dimension map ──────────────────────────

_inverted_index: Optional[dict[str, list[str]]] = None
_dimension_map: Optional[dict[str, object]] = None


def _get_inverted_index() -> dict[str, list[str]]:
    global _inverted_index
    if _inverted_index is None:
        _inverted_index = build_inverted_index()
    return _inverted_index


def _get_dimension_map() -> dict[str, object]:
    global _dimension_map
    if _dimension_map is None:
        _dimension_map = {d.id: d for d in load_default_performance_dimensions()}
    return _dimension_map


# ── Keyword matching ──────────────────────────────────────────────────────

def _keyword_lookup(term: str) -> list[tuple[str, float]]:
    """Look up a term in the inverted keyword index.

    Returns list of (dimension_id, score) tuples. Score is 1.0 for exact
    match, decreasing with partial matching.
    """
    inverted = _get_inverted_index()
    term_lower = term.lower().strip()
    matches: list[tuple[str, float]] = []

    # Exact match
    if term_lower in inverted:
        for dim_id in inverted[term_lower]:
            matches.append((dim_id, 1.0))

    # Substring match: term contains a keyword
    if not matches:
        for keyword, dim_ids in inverted.items():
            if keyword in term_lower or term_lower in keyword:
                # Partial match gets lower score
                score = _partial_match_score(term_lower, keyword)
                if score >= 0.6:
                    for dim_id in dim_ids:
                        matches.append((dim_id, score))

    # Word overlap match
    if not matches:
        term_words = set(term_lower.split())
        for keyword, dim_ids in inverted.items():
            kw_words = set(keyword.split())
            overlap = term_words & kw_words
            if len(overlap) >= 2 or (len(kw_words) == 1 and overlap):
                score = 0.5 + 0.25 * len(overlap) / max(len(kw_words), len(term_words))
                for dim_id in dim_ids:
                    matches.append((dim_id, min(score, 0.9)))

    # Deduplicate: keep highest score per dimension
    best: dict[str, float] = {}
    for dim_id, score in matches:
        if dim_id not in best or score > best[dim_id]:
            best[dim_id] = score
    return [(k, v) for k, v in sorted(best.items(), key=lambda x: x[1], reverse=True)]


def _partial_match_score(term: str, keyword: str) -> float:
    """Score a partial (substring) match between a term and a keyword."""
    if term == keyword:
        return 1.0
    if keyword in term:
        return 0.7 + 0.3 * len(keyword) / len(term)
    if term in keyword:
        return 0.6 + 0.4 * len(term) / len(keyword)
    return 0.0


# ── Rule-based classification ─────────────────────────────────────────────

def classify_by_rules(
    candidate: ExtractedCandidate,
    min_rule_score: float = 0.3,
) -> Optional[DimensionAssignment]:
    """Attempt to classify a single candidate term using rule-based lookups.

    Args:
        candidate: An ExtractedCandidate to classify.
        min_rule_score: Minimum keyword score to attempt classification.

    Returns:
        DimensionAssignment if a match is found above threshold, else None.
    """
    term = candidate.normalized_term
    matches = _keyword_lookup(term)

    if not matches:
        return None

    best_dim_id, best_score = matches[0]

    if best_score < min_rule_score:
        return None

    dim_map = _get_dimension_map()
    dim = dim_map.get(best_dim_id)
    if dim is None:
        return None

    # Build reason string
    reason_parts = [f"keyword match: '{term}' → {best_dim_id}"]
    if len(matches) > 1:
        alt_dims = [f"{m[0]}={m[1]:.2f}" for m in matches[1:3]]
        reason_parts.append(f"alternatives: {', '.join(alt_dims)}")
    reason = "; ".join(reason_parts)

    return DimensionAssignment(
        candidate_term=candidate.candidate_term,
        normalized_term=candidate.normalized_term,
        assigned_dimension=best_dim_id,
        assigned_dimension_name_cn=dim.name_cn,
        confidence_score=0.0,  # Will be filled by assignment orchestrator
        semantic_score=0.0,
        rule_score=best_score,
        keyword_score=best_score,
        evidence_quality_score=0.0,
        match_method="rule",
        reason=reason,
        evidence_sentence=candidate.evidence_sentence,
        source_literature_id=candidate.source_literature_id,
        source_title=candidate.source_title,
        source_year=candidate.source_year,
        needs_review=True,
    )


def classify_batch_by_rules(
    candidates: list[ExtractedCandidate],
    min_rule_score: float = 0.3,
) -> tuple[list[DimensionAssignment], list[ExtractedCandidate]]:
    """Classify a batch of candidates by rules.

    Args:
        candidates: List of ExtractedCandidate objects.
        min_rule_score: Minimum keyword score to attempt classification.

    Returns:
        Tuple of (classified_assignments, remaining_unclassified_candidates).
    """
    classified: list[DimensionAssignment] = []
    remaining: list[ExtractedCandidate] = []

    for c in candidates:
        assignment = classify_by_rules(c, min_rule_score=min_rule_score)
        if assignment is not None:
            classified.append(assignment)
        else:
            remaining.append(c)

    logger.info(
        "Rule classifier: %d matched, %d remaining for semantic/TF-IDF",
        len(classified), len(remaining),
    )
    return classified, remaining


def get_dimension_keywords(dimension_id: str) -> list[str]:
    """Get all alias keywords for a given dimension."""
    inverted = _get_inverted_index()
    return sorted({k for k, dims in inverted.items() if dimension_id in dims})


def get_term_category_hints(term: str) -> list[tuple[str, float]]:
    """Get dimension category hints for a term without full classification.

    Useful for quick category lookups in the UI.
    """
    return _keyword_lookup(term)
