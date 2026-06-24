"""
Hybrid 3-layer classification orchestrator.

Layer A: Rule dictionary matching (keyword/alias lookup)
Layer B: Semantic similarity (sentence-transformers)
Layer C: TF-IDF fallback (always available)

Each candidate flows through layers A→B→C. If a layer produces a
high-confidence assignment (≥auto_accept_threshold), it stops.
Otherwise it continues to the next layer.

Confidence formula (after classification):
  final_score = 0.4 * semantic + 0.3 * rule + 0.2 * keyword + 0.1 * evidence_quality
"""

import logging
from typing import Optional

from app.literature_to_model.schemas import (
    ExtractedCandidate,
    DimensionAssignment,
    LiteratureEvidenceChunk,
)
from app.literature_to_model.rule_classifier import classify_batch_by_rules
from app.literature_to_model.semantic_classifier import classify_batch_by_semantic
from app.literature_to_model.fallback_tfidf import classify_batch_by_tfidf

logger = logging.getLogger(__name__)


def _compute_evidence_quality(assignment: DimensionAssignment) -> float:
    """Compute evidence quality score based on available metadata.

    Factors:
      - Evidence sentence length and specificity (0-0.4)
      - Source title presence (0-0.2)
      - Year availability (0-0.2)
      - DOI presence (0-0.2)
    """
    score = 0.0

    # Evidence sentence quality: longer, more specific sentences score higher
    evidence = assignment.evidence_sentence or ""
    if len(evidence) > 50:
        score += 0.4
    elif len(evidence) > 20:
        score += 0.25
    elif len(evidence) > 0:
        score += 0.1

    # Source title
    if assignment.source_title:
        score += 0.2

    # Year: recent publications get a boost
    if assignment.source_year:
        score += 0.2

    # DOI: peer-reviewed indicator
    if assignment.doi:
        score += 0.2

    return min(score, 1.0)


def _compute_confidence(
    semantic_score: float,
    rule_score: float,
    keyword_score: float,
    evidence_quality_score: float,
) -> float:
    """Compute final confidence score using the weighted formula.

    final_score = 0.4*semantic + 0.3*rule + 0.2*keyword + 0.1*evidence_quality
    """
    return round(
        0.4 * semantic_score
        + 0.3 * rule_score
        + 0.2 * keyword_score
        + 0.1 * evidence_quality_score,
        4,
    )


def _finalize_assignment(assignment: DimensionAssignment):
    """Fill in computed scores, reason enrichment, and needs_review flag."""
    assignment.evidence_quality_score = round(_compute_evidence_quality(assignment), 4)
    assignment.confidence_score = _compute_confidence(
        assignment.semantic_score,
        assignment.rule_score,
        assignment.keyword_score,
        assignment.evidence_quality_score,
    )
    assignment.needs_review = assignment.confidence_score < 0.75

    # Enrich reason
    confidence_label = (
        "high" if assignment.confidence_score >= 0.75
        else "medium" if assignment.confidence_score >= 0.5
        else "low"
    )
    assignment.reason = (
        f"[{assignment.match_method}] {assignment.reason}; "
        f"confidence={assignment.confidence_score:.3f} ({confidence_label}), "
        f"semantic={assignment.semantic_score:.3f}, rule={assignment.rule_score:.3f}, "
        f"keyword={assignment.keyword_score:.3f}, evidence_quality={assignment.evidence_quality_score:.3f}"
    )


# ── Main assignment orchestrator ──────────────────────────────────────────

def assign_candidates_to_dimensions(
    candidates: list[ExtractedCandidate],
    auto_accept_threshold: float = 0.75,
    rule_threshold: float = 0.3,
    semantic_threshold: float = 0.35,
    tfidf_threshold: float = 0.15,
) -> list[DimensionAssignment]:
    """Run the full 3-layer hybrid classification on a list of candidates.

    Flow for each candidate:
      1. Try rule dictionary (Layer A). If confidence ≥ auto_accept_threshold, done.
      2. For remaining, try semantic similarity (Layer B).
      3. For remaining, use TF-IDF fallback (Layer C).

    Args:
        candidates: ExtractedCandidate objects to classify.
        auto_accept_threshold: Confidence threshold for auto-accept (0.75 default).
        rule_threshold: Minimum keyword score for rule classification.
        semantic_threshold: Minimum cosine similarity for semantic classification.
        tfidf_threshold: Minimum cosine similarity for TF-IDF classification.

    Returns:
        List of DimensionAssignment objects sorted by confidence (highest first).
    """
    all_assignments: list[DimensionAssignment] = []

    if not candidates:
        logger.info("No candidates to classify")
        return all_assignments

    remaining = list(candidates)

    # ── Layer A: Rule dictionary ─────────────────────────────────────
    logger.info("Layer A: rule classification for %d candidates", len(remaining))
    rule_hits, remaining = classify_batch_by_rules(remaining, min_rule_score=rule_threshold)
    logger.info("  %d matched by rules, %d remaining", len(rule_hits), len(remaining))
    all_assignments.extend(rule_hits)

    # ── Layer B: Semantic similarity ──────────────────────────────────
    if remaining:
        logger.info("Layer B: semantic classification for %d candidates", len(remaining))
        sem_hits, remaining = classify_batch_by_semantic(remaining, threshold=semantic_threshold)
        logger.info("  %d matched by semantics, %d remaining", len(sem_hits), len(remaining))
        all_assignments.extend(sem_hits)

    # ── Layer C: TF-IDF fallback ──────────────────────────────────────
    if remaining:
        logger.info("Layer C: TF-IDF fallback for %d candidates", len(remaining))
        tfidf_hits, remaining = classify_batch_by_tfidf(remaining, threshold=tfidf_threshold)
        logger.info("  %d matched by TF-IDF, %d unclassified", len(tfidf_hits), len(remaining))
        all_assignments.extend(tfidf_hits)

    # ── Finalize: compute confidence, set needs_review ────────────────
    for assignment in all_assignments:
        _finalize_assignment(assignment)

    # ── For unclassified candidates, create low-confidence assignments ──
    if remaining:
        logger.info("Creating low-confidence assignments for %d unclassified terms", len(remaining))
        for c in remaining:
            # Best-effort assignment using TF-IDF with zero threshold
            from app.literature_to_model.fallback_tfidf import classify_by_tfidf
            fallback = classify_by_tfidf(c, threshold=0.0)
            if fallback is not None:
                fallback.match_method = "fallback"
                fallback.reason = f"unclassifiable term '{c.normalized_term}'; best-guess via TF-IDF"
                _finalize_assignment(fallback)
                all_assignments.append(fallback)
            else:
                # Absolute last resort: assign to other_uncertain
                assignment = DimensionAssignment(
                    candidate_term=c.candidate_term,
                    normalized_term=c.normalized_term,
                    assigned_dimension="other_uncertain",
                    assigned_dimension_name_cn="其他/不确定",
                    confidence_score=0.05,
                    semantic_score=0.0,
                    rule_score=0.0,
                    keyword_score=0.0,
                    evidence_quality_score=0.1,
                    match_method="fallback",
                    reason=f"could not classify '{c.normalized_term}'; assigned to other/uncertain",
                    evidence_sentence=c.evidence_sentence,
                    source_literature_id=c.source_literature_id,
                    source_title=c.source_title,
                    source_year=c.source_year,
                    needs_review=True,
                )
                all_assignments.append(assignment)

    # Sort by confidence descending
    all_assignments.sort(key=lambda a: a.confidence_score, reverse=True)

    logger.info(
        "Classification complete: %d assignments (%d high, %d medium, %d low confidence)",
        len(all_assignments),
        sum(1 for a in all_assignments if a.confidence_score >= 0.75),
        sum(1 for a in all_assignments if 0.5 <= a.confidence_score < 0.75),
        sum(1 for a in all_assignments if a.confidence_score < 0.5),
    )

    return all_assignments


def export_assignments_to_dataframe(assignments: list[DimensionAssignment]) -> "pd.DataFrame":
    """Export assignments to a pandas DataFrame for display or CSV export."""
    import pandas as pd

    records = []
    for a in assignments:
        records.append({
            "候选术语": a.candidate_term,
            "标准化术语": a.normalized_term,
            "分配维度": a.assigned_dimension_name_cn,
            "维度代码": a.assigned_dimension,
            "置信度": a.confidence_score,
            "语义分数": a.semantic_score,
            "规则分数": a.rule_score,
            "关键词分数": a.keyword_score,
            "证据质量": a.evidence_quality_score,
            "匹配方法": a.match_method,
            "需要审核": "是" if a.needs_review else "否",
            "证据句": a.evidence_sentence[:200] if a.evidence_sentence else "",
            "来源文献": a.source_title,
            "年份": a.source_year,
            "理由": a.reason[:300] if a.reason else "",
        })

    return pd.DataFrame(records)
