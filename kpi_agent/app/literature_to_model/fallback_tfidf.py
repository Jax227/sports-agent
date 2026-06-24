"""
TF-IDF fallback classifier for candidate term classification.

This is Layer C of the hybrid 3-layer classification:
  A. Rule dictionary matching
  B. Semantic similarity (sentence-transformers)
  C. TF-IDF fallback ← this module

Used when sentence-transformers is unavailable or fails. Builds a TF-IDF
matrix from dimension keyword sets and candidate terms, then classifies
by cosine similarity.

Always works — scikit-learn is a hard dependency of the project.
"""

import logging
from typing import Optional

import numpy as np

from app.literature_to_model.schemas import ExtractedCandidate, DimensionAssignment
from app.literature_to_model.dimensions import load_default_performance_dimensions

logger = logging.getLogger(__name__)


def _build_tfidf_matrix(
    dimension_texts: dict[str, str],
    candidate_texts: list[str],
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Build TF-IDF matrices for dimensions and candidates.

    Returns (dim_tfidf, cand_tfidf, dim_ids).
    """
    from sklearn.feature_extraction.text import TfidfVectorizer

    dim_ids = list(dimension_texts.keys())
    dim_corpus = [dimension_texts[k] for k in dim_ids]

    vectorizer = TfidfVectorizer(
        max_features=3000,
        ngram_range=(1, 2),
        stop_words="english",
        sublinear_tf=True,
    )

    # Fit on dimensions only, transform both
    dim_tfidf = vectorizer.fit_transform(dim_corpus).toarray()
    cand_tfidf = vectorizer.transform(candidate_texts).toarray()

    return dim_tfidf, cand_tfidf, dim_ids


def classify_by_tfidf(
    candidate: ExtractedCandidate,
    threshold: float = 0.15,
    dimension_texts: Optional[dict[str, str]] = None,
    dim_tfidf: Optional[np.ndarray] = None,
    dim_ids: Optional[list[str]] = None,
    vectorizer=None,
) -> Optional[DimensionAssignment]:
    """Classify a single candidate using TF-IDF similarity.

    Args:
        candidate: The candidate to classify.
        threshold: Minimum cosine similarity to assign a dimension.
        dimension_texts: Pre-built dimension text dictionary (optional).
        dim_tfidf: Pre-computed dimension TF-IDF matrix (optional, for batch).
        dim_ids: Pre-computed dimension ID list (optional, for batch).
        vectorizer: Pre-fitted TF-IDF vectorizer (optional, for batch).

    Returns:
        DimensionAssignment if similarity is above threshold, else None.
    """
    from sklearn.feature_extraction.text import TfidfVectorizer

    if dimension_texts is None:
        dimensions = load_default_performance_dimensions()
        dimension_texts = {}
        for dim in dimensions:
            parts = [dim.name_en, dim.description, " ".join(dim.aliases[:50])]
            dimension_texts[dim.id] = " ".join(parts)

    text_to_encode = candidate.evidence_sentence or candidate.normalized_term
    if len(text_to_encode) < 5:
        text_to_encode = candidate.normalized_term

    if dim_tfidf is None or vectorizer is None:
        dim_ids = list(dimension_texts.keys())
        dim_corpus = [dimension_texts[k] for k in dim_ids]
        vectorizer = TfidfVectorizer(
            max_features=3000, ngram_range=(1, 2),
            stop_words="english", sublinear_tf=True,
        )
        dim_tfidf = vectorizer.fit_transform(dim_corpus).toarray()

    if dim_ids is None:
        dim_ids = list(dimension_texts.keys())

    cand_vec = vectorizer.transform([text_to_encode]).toarray()[0]

    # Cosine similarity
    dim_norms = np.linalg.norm(dim_tfidf, axis=1)
    dim_norms[dim_norms == 0] = 1e-10
    cand_norm = np.linalg.norm(cand_vec) or 1e-10

    sims = np.dot(dim_tfidf, cand_vec) / (dim_norms * cand_norm)

    best_idx = int(np.argmax(sims))
    best_score = float(sims[best_idx])

    if best_score < threshold:
        return None

    best_dim_id = dim_ids[best_idx]
    dim_map = {d.id: d for d in load_default_performance_dimensions()}
    dim = dim_map.get(best_dim_id)
    if dim is None:
        return None

    top_indices = np.argsort(sims)[::-1][:3]
    top3_str = ", ".join(
        f"{dim_ids[j]}={float(sims[j]):.3f}" for j in top_indices
    )

    return DimensionAssignment(
        candidate_term=candidate.candidate_term,
        normalized_term=candidate.normalized_term,
        assigned_dimension=best_dim_id,
        assigned_dimension_name_cn=dim.name_cn,
        confidence_score=0.0,
        semantic_score=0.0,
        rule_score=0.0,
        keyword_score=0.0,
        evidence_quality_score=0.0,
        match_method="tfidf",
        reason=f"TF-IDF match to '{best_dim_id}' (sim={best_score:.3f}); top-3: {top3_str}",
        evidence_sentence=candidate.evidence_sentence,
        source_literature_id=candidate.source_literature_id,
        source_title=candidate.source_title,
        source_year=candidate.source_year,
        needs_review=True,
    )


def classify_batch_by_tfidf(
    candidates: list[ExtractedCandidate],
    threshold: float = 0.15,
) -> tuple[list[DimensionAssignment], list[ExtractedCandidate]]:
    """Classify a batch of candidates using TF-IDF.

    Always available as scikit-learn is a core dependency.

    Args:
        candidates: List of candidates to classify.
        threshold: Minimum cosine similarity for assignment.

    Returns:
        Tuple of (classified_assignments, remaining_unclassified_candidates).
    """
    from sklearn.feature_extraction.text import TfidfVectorizer

    if not candidates:
        return [], []

    # Build dimension texts
    dimensions = load_default_performance_dimensions()
    dim_map = {d.id: d for d in dimensions}
    dimension_texts: dict[str, str] = {}
    for dim in dimensions:
        parts = [dim.name_en, dim.description, " ".join(dim.aliases[:50])]
        dimension_texts[dim.id] = " ".join(parts)

    # Prepare candidate texts
    candidate_texts = []
    for c in candidates:
        text = c.evidence_sentence or c.normalized_term
        if len(text) < 5:
            text = c.normalized_term
        candidate_texts.append(text)

    dim_ids = list(dimension_texts.keys())
    dim_corpus = [dimension_texts[k] for k in dim_ids]

    vectorizer = TfidfVectorizer(
        max_features=3000, ngram_range=(1, 2),
        stop_words="english", sublinear_tf=True,
    )
    dim_tfidf = vectorizer.fit_transform(dim_corpus).toarray()
    cand_tfidf = vectorizer.transform(candidate_texts).toarray()

    # Cosine similarity
    dim_norms = np.linalg.norm(dim_tfidf, axis=1)
    dim_norms[dim_norms == 0] = 1e-10
    cand_norms = np.linalg.norm(cand_tfidf, axis=1)
    cand_norms[cand_norms == 0] = 1e-10

    sim_matrix = np.dot(cand_tfidf, dim_tfidf.T) / np.outer(cand_norms, dim_norms)

    classified: list[DimensionAssignment] = []
    remaining: list[ExtractedCandidate] = []

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

        top_indices = np.argsort(sim_matrix[i])[::-1][:3]
        top3_str = ", ".join(
            f"{dim_ids[j]}={float(sim_matrix[i][j]):.3f}" for j in top_indices
        )

        classified.append(DimensionAssignment(
            candidate_term=candidate.candidate_term,
            normalized_term=candidate.normalized_term,
            assigned_dimension=best_dim_id,
            assigned_dimension_name_cn=dim.name_cn,
            confidence_score=0.0,
            semantic_score=0.0,
            rule_score=0.0,
            keyword_score=0.0,
            evidence_quality_score=0.0,
            match_method="tfidf",
            reason=f"TF-IDF match to '{best_dim_id}' (sim={best_score:.3f}); top-3: {top3_str}",
            evidence_sentence=candidate.evidence_sentence,
            source_literature_id=candidate.source_literature_id,
            source_title=candidate.source_title,
            source_year=candidate.source_year,
            needs_review=True,
        ))

    logger.info(
        "TF-IDF classifier: %d matched (threshold=%.2f), %d remaining",
        len(classified), threshold, len(remaining),
    )
    return classified, remaining
