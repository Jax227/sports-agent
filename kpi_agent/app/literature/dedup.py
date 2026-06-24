"""
Cross-source deduplication for literature search results.

Priority:
1. DOI exact match
2. PMID exact match
3. PMCID exact match
4. Title fuzzy match (rapidfuzz)
5. First author + year + title similarity

After dedup, fields are merged (longer abstract, max citation count, etc.).
"""

import logging
from typing import Optional

from app.literature.schema import LiteratureResult

logger = logging.getLogger(__name__)

# Try rapidfuzz for fuzzy matching; fall back to simple string similarity
try:
    from rapidfuzz import fuzz as _fuzz
    _HAS_FUZZ = True
except ImportError:
    _HAS_FUZZ = False
    logger.info("rapidfuzz not installed, using simple title matching for dedup")


def _title_similarity(t1: str, t2: str) -> float:
    """Compute title similarity score 0-1."""
    if not t1 or not t2:
        return 0.0

    # Normalize
    t1 = t1.lower().strip().rstrip(".")
    t2 = t2.lower().strip().rstrip(".")

    if t1 == t2:
        return 1.0

    if _HAS_FUZZ:
        return _fuzz.token_sort_ratio(t1, t2) / 100.0

    # Simple fallback: word overlap
    words1 = set(t1.split())
    words2 = set(t2.split())
    if not words1 or not words2:
        return 0.0
    intersection = words1 & words2
    return len(intersection) / max(len(words1), len(words2))


def deduplicate_results(
    results: list[LiteratureResult],
    fuzzy_threshold: float = 0.85,
) -> dict:
    """Deduplicate a list of LiteratureResult across sources.

    Returns dict with:
    - results: deduplicated list
    - before_count: int
    - after_count: int
    - duplicates_removed: int
    - merge_details: list[dict] (which records were merged)
    """
    if not results:
        return {
            "results": [],
            "before_count": 0,
            "after_count": 0,
            "duplicates_removed": 0,
            "merge_details": [],
        }

    before_count = len(results)
    clusters: list[list[LiteratureResult]] = []
    merge_details = []

    for result in results:
        matched_cluster_idx = _find_matching_cluster(result, clusters, fuzzy_threshold)
        if matched_cluster_idx is not None:
            cluster = clusters[matched_cluster_idx]
            # Only record merge if from different source
            if result.source_database not in [r.source_database for r in cluster]:
                merge_details.append({
                    "title": result.title[:80],
                    "doi": result.doi,
                    "merged_from": result.source_database,
                    "merged_into": cluster[0].source_database,
                })
            cluster.append(result)
        else:
            clusters.append([result])

    # Merge each cluster
    merged = [_merge_cluster(cluster) for cluster in clusters]

    return {
        "results": merged,
        "before_count": before_count,
        "after_count": len(merged),
        "duplicates_removed": before_count - len(merged),
        "merge_details": merge_details,
    }


def _find_matching_cluster(
    result: LiteratureResult,
    clusters: list[list[LiteratureResult]],
    fuzzy_threshold: float,
) -> Optional[int]:
    """Find which cluster (if any) this result belongs to. Returns index or None."""
    for idx, cluster in enumerate(clusters):
        for member in cluster:
            # 1. DOI match (highest priority)
            if result.doi and member.doi and result.doi.lower() == member.doi.lower():
                return idx

            # 2. PMID match
            if result.pmid and member.pmid and result.pmid == member.pmid:
                return idx

            # 3. PMCID match
            if result.pmcid and member.pmcid and result.pmcid == member.pmcid:
                return idx

            # 4. Title fuzzy match
            if _title_similarity(result.title, member.title) >= fuzzy_threshold:
                # Extra check: first author + year
                if _author_year_match(result, member):
                    return idx

    return None


def _author_year_match(r1: LiteratureResult, r2: LiteratureResult) -> bool:
    """Check if first author and year match (helper for title fuzzy match)."""
    # Year match
    if r1.year and r2.year and r1.year != r2.year:
        return False

    # First author match (if both have authors)
    if r1.authors and r2.authors:
        a1_first = r1.authors[0].lower().strip().split()[-1]  # last name
        a2_first = r2.authors[0].lower().strip().split()[-1]
        if a1_first and a2_first and a1_first == a2_first:
            return True
        # If first authors don't match, still allow if title similarity is very high
        if _title_similarity(r1.title, r2.title) >= 0.95:
            return True
        return False

    return True  # If one doesn't have authors, trust title match


def _merge_cluster(cluster: list[LiteratureResult]) -> LiteratureResult:
    """Merge a cluster of duplicates into a single LiteratureResult."""
    if len(cluster) == 1:
        result = cluster[0]
        result.source_records = [result.source_database]
        return result

    # Use the first as base, merge fields from others
    base = cluster[0]

    # Track source databases
    source_dbs = list(set(r.source_database for r in cluster))
    base.source_records = source_dbs
    base.source_database = "+".join(source_dbs)

    for other in cluster[1:]:
        # Prefer longer abstract
        if other.abstract and (not base.abstract or len(other.abstract) > len(base.abstract)):
            base.abstract = other.abstract

        # Pick max citation count
        if other.citation_count is not None:
            if base.citation_count is None or other.citation_count > base.citation_count:
                base.citation_count = other.citation_count

        # Prefer available PDF
        if other.pdf_url and not base.pdf_url:
            base.pdf_url = other.pdf_url

        # Prefer available fulltext
        if other.fulltext_url and not base.fulltext_url:
            base.fulltext_url = other.fulltext_url

        # OA status: any source says OA → OA
        if other.open_access and not base.open_access:
            base.open_access = True
            base.open_access_status = other.open_access_status or "open"

        # Fill in missing fields from other sources
        if not base.doi and other.doi:
            base.doi = other.doi
        if not base.pmid and other.pmid:
            base.pmid = other.pmid
        if not base.pmcid and other.pmcid:
            base.pmcid = other.pmcid
        if not base.journal and other.journal:
            base.journal = other.journal
        if not base.url and other.url:
            base.url = other.url
        if not base.publication_type and other.publication_type:
            base.publication_type = other.publication_type

        # Merge keywords
        for kw in other.keywords:
            if kw not in base.keywords:
                base.keywords.append(kw)

    return base
