"""
Hybrid ranking for literature search results.

Components:
1. BM25 ranking (title + abstract as document text)
2. Rule-based scoring (recency, citations, OA, etc.)
3. RRF (Reciprocal Rank Fusion) to merge rankings

Vector/semantic ranking is attempted if sentence-transformers is available,
falls back to BM25 + rules if model can't load.
"""

import logging
import math
from typing import Optional

from app.literature.schema import LiteratureResult

logger = logging.getLogger(__name__)

# ── BM25 ───────────────────────────────────────────────────────────

try:
    from rank_bm25 import BM25Okapi
    _HAS_BM25 = True
except ImportError:
    _HAS_BM25 = False
    logger.info("rank-bm25 not installed, BM25 ranking disabled")


def _tokenize(text: str) -> list[str]:
    """Simple tokenizer: lowercase, split on non-alphanumeric."""
    if not text:
        return []
    import re
    return [t.lower() for t in re.findall(r'\w+', text)]


class BM25Ranker:
    """BM25 ranking over LiteratureResult objects."""

    def __init__(self):
        self._corpus: list[str] = []
        self._results: list[LiteratureResult] = []
        self._bm25: Optional["BM25Okapi"] = None

    def fit(self, results: list[LiteratureResult]):
        self._results = results
        self._corpus = []
        for r in results:
            doc = (r.title or "") + " " + (r.abstract or "")
            self._corpus.append(doc)
        if _HAS_BM25:
            tokenized = [_tokenize(doc) for doc in self._corpus]
            self._bm25 = BM25Okapi(tokenized)

    def score(self, query: str) -> list[float]:
        """Score all documents against query. Returns list of scores (higher = better)."""
        if not self._results:
            return []

        if self._bm25 is not None:
            tokenized_query = _tokenize(query)
            return self._bm25.get_scores(tokenized_query).tolist()

        # Fallback: simple TF scoring
        query_terms = set(_tokenize(query))
        if not query_terms:
            return [0.0] * len(self._results)

        scores = []
        for doc in self._corpus:
            doc_terms = _tokenize(doc)
            score = sum(1 for t in doc_terms if t in query_terms)
            scores.append(float(score))
        return scores


# ── Rule-based scoring ─────────────────────────────────────────────

def compute_rule_scores(
    results: list[LiteratureResult],
    query: str,
    sport_context: Optional[str] = None,
) -> list[float]:
    """Compute rule-based relevance scores for each result.

    Returns list of scores in range [0, ~10], higher = better.
    """
    query_lower = query.lower()
    query_terms = set(_tokenize(query))

    scores = []
    current_year = 2026  # approximate

    for r in results:
        score = 0.0
        title_lower = (r.title or "").lower()
        abstract_lower = (r.abstract or "").lower()

        # 1. Title query match (max 2.0)
        title_matches = sum(1 for t in query_terms if t in title_lower)
        if title_matches > 0:
            score += min(title_matches, 5) * 0.4  # up to 2.0

        # 2. Abstract query match (max 1.5)
        abstract_matches = sum(1 for t in query_terms if t in abstract_lower)
        if abstract_matches > 0:
            score += min(abstract_matches, 10) * 0.15  # up to 1.5

        # 3. Year recency (max 1.0)
        if r.year:
            age = current_year - r.year
            if age <= 3:
                score += 1.0
            elif age <= 5:
                score += 0.7
            elif age <= 10:
                score += 0.4
            elif age <= 15:
                score += 0.2

        # 4. Citation count (max 1.5)
        if r.citation_count is not None:
            if r.citation_count > 100:
                score += 1.5
            elif r.citation_count > 50:
                score += 1.0
            elif r.citation_count > 10:
                score += 0.5
            elif r.citation_count > 0:
                score += 0.2

        # 5. Has DOI (0.3)
        if r.doi:
            score += 0.3

        # 6. Has abstract (0.5)
        if r.abstract and len(r.abstract) > 50:
            score += 0.5

        # 7. Open access (0.5)
        if r.open_access:
            score += 0.5

        # 8. Has PDF (1.0)
        if r.pdf_url:
            score += 1.0

        # 9. Sport context match (0.5)
        if sport_context:
            sport_lower = sport_context.lower()
            if sport_lower in title_lower or sport_lower in abstract_lower:
                score += 0.5

        # 10. Source bonus: multiple sources = more reliable (0.3)
        if len(r.source_records) > 1:
            score += 0.3

        scores.append(score)

    return scores


# ── RRF fusion ─────────────────────────────────────────────────────

def reciprocal_rank_fusion(
    rank_lists: list[list[int]],
    k: int = 60,
    weights: Optional[list[float]] = None,
) -> list[float]:
    """Reciprocal Rank Fusion across multiple ranked lists.

    Args:
        rank_lists: Each inner list is result indices sorted by rank (best first)
        k: RRF constant (default 60)
        weights: Optional weights for each rank list

    Returns:
        List of fused scores, one per result (index matches input)
    """
    n_docs = max(max(r) for r in rank_lists if r) + 1 if rank_lists else 0
    if n_docs == 0:
        return []

    if weights is None:
        weights = [1.0] * len(rank_lists)

    scores = [0.0] * n_docs

    for rank_list, weight in zip(rank_lists, weights):
        if not rank_list:
            continue
        for rank, doc_idx in enumerate(rank_list):
            # rank is 0-based internally, convert to 1-based for RRF formula
            scores[doc_idx] += weight / (k + rank + 1)

    return scores


# ── Ranking explanation ────────────────────────────────────────────

def _build_explanation(
    result: LiteratureResult,
    query: str,
    bm25_rank: Optional[int],
    rule_rank: Optional[int],
) -> str:
    """Generate a human-readable explanation for why this paper ranks well."""
    parts = []

    title_lower = (result.title or "").lower()
    abstract_lower = (result.abstract or "").lower()
    query_terms = set(_tokenize(query))

    # Title matches
    title_hits = [t for t in query_terms if t in title_lower]
    if title_hits:
        parts.append(f"title matches: {', '.join(list(title_hits)[:5])}")

    # Abstract matches
    abstract_hits = [t for t in query_terms if t in abstract_lower]
    if abstract_hits:
        parts.append(f"abstract contains: {', '.join(list(abstract_hits)[:5])}")

    # Open fulltext
    if result.pdf_url:
        parts.append("open-access PDF available")
    elif result.open_access:
        parts.append("open access")

    # Citations
    if result.citation_count and result.citation_count > 50:
        parts.append(f"highly cited ({result.citation_count})")

    # Year
    if result.year and result.year >= 2021:
        parts.append("recent publication")

    # Multiple sources
    if len(result.source_records) > 1:
        parts.append(f"found in {len(result.source_records)} databases")

    return "; ".join(parts) if parts else "matched query terms"


# ── Main hybrid ranking ────────────────────────────────────────────

def hybrid_rerank(
    query: str,
    results: list[LiteratureResult],
    sport_context: Optional[str] = None,
    use_vector: bool = False,
) -> list[LiteratureResult]:
    """Hybrid re-ranking: BM25 + rules + RRF.

    Args:
        query: Original search query
        results: Results to re-rank (modified in-place)
        sport_context: Optional sport name for relevance boost
        use_vector: Attempt sentence-transformers semantic ranking (falls back gracefully)

    Returns:
        Re-ranked results (same objects, with scores populated)
    """
    if not results:
        return results

    n = len(results)

    # 1. BM25 ranking
    bm25_ranker = BM25Ranker()
    bm25_ranker.fit(results)
    bm25_scores = bm25_ranker.score(query)

    # 2. Rule-based scoring
    rule_scores = compute_rule_scores(results, query, sport_context)

    # 3. Build rank lists for RRF
    # BM25 rank
    bm25_sorted = sorted(range(n), key=lambda i: bm25_scores[i], reverse=True)
    bm25_rank_list = bm25_sorted

    # Rule rank
    rule_sorted = sorted(range(n), key=lambda i: rule_scores[i], reverse=True)
    rule_rank_list = rule_sorted

    rank_lists = [bm25_rank_list, rule_rank_list]
    rrf_weights = [1.0, 0.8]

    # 4. Optional vector ranking
    vector_rank_list = None
    if use_vector:
        try:
            vector_rank_list = _vector_rank(query, results)
            if vector_rank_list:
                rank_lists.append(vector_rank_list)
                rrf_weights.append(0.6)
        except Exception as e:
            logger.warning(f"Vector ranking failed, using BM25+rule only: {e}")

    # 5. RRF fusion
    rrf_scores = reciprocal_rank_fusion(rank_lists, k=60, weights=rrf_weights)

    # 6. Assign scores and reorder
    for i, r in enumerate(results):
        r.final_score = round(rrf_scores[i], 6) if i < len(rrf_scores) else 0.0
        r.bm25_score = round(bm25_scores[i], 4) if i < len(bm25_scores) else 0.0
        r.rule_score = round(rule_scores[i], 2) if i < len(rule_scores) else 0.0

        # Compute ranks
        bm25_rank = bm25_rank_list.index(i) + 1 if i in bm25_rank_list else None
        rule_rank = rule_rank_list.index(i) + 1 if i in rule_rank_list else None

        r.ranking_explanation = _build_explanation(r, query, bm25_rank, rule_rank)

    # Sort by final_score descending
    results.sort(key=lambda r: r.final_score or 0.0, reverse=True)

    return results


# ── Vector/semantic ranking (optional) ─────────────────────────────

def _vector_rank(query: str, results: list[LiteratureResult]) -> Optional[list[int]]:
    """Attempt semantic vector ranking. Returns rank list or None on failure."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        logger.info("sentence-transformers not installed, skipping vector ranking")
        return None

    try:
        model_name = "sentence-transformers/all-MiniLM-L6-v2"
        model = SentenceTransformer(model_name)
    except Exception as e:
        logger.warning(f"Could not load sentence-transformers model: {e}")
        return None

    try:
        # Encode query and documents
        docs = [(r.title or "") + " " + (r.abstract or "")[:500] for r in results]
        query_vec = model.encode([query], show_progress_bar=False)
        doc_vecs = model.encode(docs, show_progress_bar=False)

        # Cosine similarity
        from sklearn.metrics.pairwise import cosine_similarity
        sims = cosine_similarity(query_vec, doc_vecs)[0]  # type: ignore

        # Rank list (best first)
        return [int(i) for i in sorted(range(len(sims)), key=lambda i: sims[i], reverse=True)]  # type: ignore
    except Exception as e:
        logger.warning(f"Vector ranking computation failed: {e}")
        return None
