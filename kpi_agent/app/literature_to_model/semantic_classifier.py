"""
Semantic similarity classifier using sentence-transformers.

This is Layer B of the hybrid 3-layer classification:
  A. Rule dictionary matching
  B. Semantic similarity (sentence-transformers) ← this module
  C. TF-IDF fallback

Uses the all-MiniLM-L6-v2 model to encode candidate terms and dimension
descriptions, then computes cosine similarity for classification.
"""

import logging
from typing import Optional

import numpy as np

from app.literature_to_model.schemas import ExtractedCandidate, DimensionAssignment
from app.literature_to_model.dimensions import load_default_performance_dimensions

logger = logging.getLogger(__name__)

_st_model = None
_st_available = None


def _check_st() -> bool:
    global _st_available
    if _st_available is None:
        try:
            from sentence_transformers import SentenceTransformer  # noqa: F401
            _st_available = True
        except ImportError:
            logger.info("sentence-transformers not installed, semantic classifier unavailable")
            _st_available = False
    return _st_available


def _get_model():
    """Lazy-load the sentence-transformer model."""
    global _st_model
    if _st_model is None and _check_st():
        try:
            from sentence_transformers import SentenceTransformer
            _st_model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Loaded sentence-transformers model: all-MiniLM-L6-v2")
        except Exception as e:
            logger.warning("Failed to load sentence-transformers model: %s", e)
            _st_available = False
    return _st_model


# ── Dimension embedding cache ─────────────────────────────────────────────

_dimension_embeddings: Optional[dict[str, np.ndarray]] = None


def _get_dimension_embeddings() -> dict[str, np.ndarray]:
    """Build and cache embeddings for all 8 dimension descriptions."""
    global _dimension_embeddings
    if _dimension_embeddings is not None:
        return _dimension_embeddings

    model = _get_model()
    if model is None:
        return {}

    dimensions = load_default_performance_dimensions()
    # Build rich description texts for each dimension
    texts = {}
    for dim in dimensions:
        # Combine name, description, and aliases for a richer embedding
        parts = [
            dim.name_en,
            dim.description,
            " ".join(dim.aliases[:30]),  # Top aliases
        ]
        texts[dim.id] = " ".join(parts)

    try:
        dim_ids = list(texts.keys())
        dim_texts = [texts[k] for k in dim_ids]
        embeddings = model.encode(dim_texts, show_progress_bar=False)
        _dimension_embeddings = {
            dim_id: embeddings[i] for i, dim_id in enumerate(dim_ids)
        }
        logger.info("Built dimension embeddings for %d categories", len(_dimension_embeddings))
        return _dimension_embeddings
    except Exception as e:
        logger.warning("Failed to build dimension embeddings: %s", e)
        return {}


# ── Semantic classification ───────────────────────────────────────────────

def classify_by_semantic(
    candidate: ExtractedCandidate,
    threshold: float = 0.35,
) -> Optional[DimensionAssignment]:
    """Classify a candidate term using semantic similarity.

    Encodes the candidate's evidence sentence (or term itself as fallback)
    and compares against pre-computed dimension embeddings.

    Args:
        candidate: An ExtractedCandidate to classify.
        threshold: Minimum cosine similarity to assign a dimension.

    Returns:
        DimensionAssignment if similarity is above threshold, else None.
    """
    if not _check_st():
        return None

    model = _get_model()
    if model is None:
        return None

    dim_embeddings = _get_dimension_embeddings()
    if not dim_embeddings:
        return None

    # Encode the candidate: prefer evidence sentence, fall back to term
    text_to_encode = candidate.evidence_sentence or candidate.normalized_term
    if len(text_to_encode) < 5:
        text_to_encode = candidate.normalized_term

    try:
        candidate_emb = model.encode([text_to_encode], show_progress_bar=False)[0]
    except Exception as e:
        logger.warning("Failed to encode candidate '%s': %s", candidate.normalized_term, e)
        return None

    # Compute cosine similarity to each dimension
    dim_map = {d.id: d for d in load_default_performance_dimensions()}
    scores: dict[str, float] = {}
    for dim_id, dim_emb in dim_embeddings.items():
        sim = float(np.dot(candidate_emb, dim_emb) / (
            np.linalg.norm(candidate_emb) * np.linalg.norm(dim_emb)
        ))
        scores[dim_id] = sim

    # Find best match
    best_dim_id = max(scores, key=scores.get)
    best_score = scores[best_dim_id]

    if best_score < threshold:
        return None

    dim = dim_map.get(best_dim_id)
    if dim is None:
        return None

    # Build reason
    top3 = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]
    reason_parts = [
        f"semantic match to '{best_dim_id}' (sim={best_score:.3f})",
    ]
    if len(top3) > 1:
        reason_parts.append(
            f"top-3: {', '.join(f'{k}={v:.3f}' for k, v in top3)}"
        )
    reason = "; ".join(reason_parts)

    return DimensionAssignment(
        candidate_term=candidate.candidate_term,
        normalized_term=candidate.normalized_term,
        assigned_dimension=best_dim_id,
        assigned_dimension_name_cn=dim.name_cn,
        confidence_score=0.0,  # Set by orchestrator
        semantic_score=best_score,
        rule_score=0.0,
        keyword_score=0.0,
        evidence_quality_score=0.0,
        match_method="semantic",
        reason=reason,
        evidence_sentence=candidate.evidence_sentence,
        source_literature_id=candidate.source_literature_id,
        source_title=candidate.source_title,
        source_year=candidate.source_year,
        needs_review=True,
    )


def classify_batch_by_semantic(
    candidates: list[ExtractedCandidate],
    threshold: float = 0.35,
) -> tuple[list[DimensionAssignment], list[ExtractedCandidate]]:
    """Classify a batch of candidates using semantic similarity.

    Args:
        candidates: List of ExtractedCandidate objects.
        threshold: Minimum cosine similarity for assignment.

    Returns:
        Tuple of (classified_assignments, remaining_unclassified_candidates).
    """
    classified: list[DimensionAssignment] = []
    remaining: list[ExtractedCandidate] = []

    # Preload model and embeddings
    if not _check_st():
        logger.info("Semantic classifier unavailable, all %d candidates remain", len(candidates))
        return [], list(candidates)

    model = _get_model()
    if model is None:
        return [], list(candidates)

    dim_embeddings = _get_dimension_embeddings()
    if not dim_embeddings:
        return [], list(candidates)

    dim_map = {d.id: d for d in load_default_performance_dimensions()}

    # Batch encode all candidates at once
    texts = [
        (c.evidence_sentence or c.normalized_term) if len(c.evidence_sentence or "") >= 5
        else c.normalized_term
        for c in candidates
    ]

    try:
        cand_embs = model.encode(texts, show_progress_bar=False)
    except Exception as e:
        logger.warning("Batch encoding failed: %s", e)
        return [], list(candidates)

    # Dimension embedding matrix
    dim_ids = list(dim_embeddings.keys())
    dim_matrix = np.stack([dim_embeddings[k] for k in dim_ids])

    # Cosine similarity: candidate × dimensions
    cand_norms = np.linalg.norm(cand_embs, axis=1, keepdims=True)
    dim_norms = np.linalg.norm(dim_matrix, axis=1)
    cand_norms[cand_norms == 0] = 1e-10
    dim_norms[dim_norms == 0] = 1e-10
    sim_matrix = np.dot(cand_embs, dim_matrix.T) / (cand_norms * dim_norms)

    for i, candidate in enumerate(candidates):
        best_j = int(np.argmax(sim_matrix[i]))
        best_score = float(sim_matrix[i][best_j])

        if best_score < threshold:
            remaining.append(candidate)
            continue

        best_dim_id = dim_ids[best_j]
        dim = dim_map.get(best_dim_id)
        if dim is None:
            remaining.append(candidate)
            continue

        # Top-3 for reason
        top_indices = np.argsort(sim_matrix[i])[::-1][:3]
        top3_str = ", ".join(
            f"{dim_ids[j]}={float(sim_matrix[i][j]):.3f}"
            for j in top_indices
        )

        classified.append(DimensionAssignment(
            candidate_term=candidate.candidate_term,
            normalized_term=candidate.normalized_term,
            assigned_dimension=best_dim_id,
            assigned_dimension_name_cn=dim.name_cn,
            confidence_score=0.0,
            semantic_score=best_score,
            rule_score=0.0,
            keyword_score=0.0,
            evidence_quality_score=0.0,
            match_method="semantic",
            reason=f"semantic match to '{best_dim_id}' (sim={best_score:.3f}); top-3: {top3_str}",
            evidence_sentence=candidate.evidence_sentence,
            source_literature_id=candidate.source_literature_id,
            source_title=candidate.source_title,
            source_year=candidate.source_year,
            needs_review=True,
        ))

    logger.info(
        "Semantic classifier: %d matched (threshold=%.2f), %d remaining",
        len(classified), threshold, len(remaining),
    )
    return classified, remaining
