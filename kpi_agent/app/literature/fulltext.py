"""
Fulltext link enrichment for literature search results.

Enriches LiteratureResult objects with open-access fulltext links from:
1. Existing pdf_url / fulltext_url
2. Europe PMC fullTextUrlList
3. OpenAlex open_access.oa_url
4. Semantic Scholar openAccessPdf
5. Unpaywall DOI query

Only records legal open-access links. Does NOT use paywalled content.
"""

import logging
from typing import Optional

from app.literature.schema import LiteratureResult
from app.literature.connectors.registry import ConnectorRegistry

logger = logging.getLogger(__name__)


def enrich_fulltext_links(
    results: list[LiteratureResult],
    use_unpaywall: bool = True,
) -> list[LiteratureResult]:
    """Enrich a list of LiteratureResult with OA fulltext links.

    Operates on results in-place but also returns them for convenience.

    Sources checked in order:
    1. Already present pdf_url — skip
    2. Europe PMC (already populated during search for europe_pmc source)
    3. OpenAlex (already populated during search for openalex source)
    4. Semantic Scholar (already populated during search)
    5. Unpaywall — query by DOI

    Args:
        results: List of LiteratureResult to enrich
        use_unpaywall: Whether to query Unpaywall (requires email)

    Returns:
        The enriched list (same objects, modified in-place)
    """
    # Get Unpaywall connector if available
    unpaywall = None
    if use_unpaywall:
        unpaywall = ConnectorRegistry.get("unpaywall")
        if unpaywall and not unpaywall.available:
            logger.info(f"Unpaywall not available: {unpaywall.status['message']}")
            unpaywall = None

    enriched_count = 0

    for r in results:
        if r.fulltext_available and r.pdf_url:
            continue  # Already enriched

        # Try to find fulltext from existing source data
        found = _check_existing_links(r)

        # Try Unpaywall if still no fulltext
        if not found and unpaywall and r.doi:
            try:
                r2 = unpaywall.enrich_literature(r)
                if r2.fulltext_available:
                    found = True
                    logger.debug(f"Unpaywall found OA fulltext for DOI {r.doi}")
            except Exception as e:
                logger.warning(f"Unpaywall enrichment failed for DOI {r.doi}: {e}")

        if found:
            enriched_count += 1

    logger.info(f"Fulltext enrichment: {enriched_count}/{len(results)} papers have OA fulltext")
    return results


def _check_existing_links(r: LiteratureResult) -> bool:
    """Check if the paper already has usable fulltext links from its source data.

    Returns True if a usable link was found.
    """
    # Already has PDF
    if r.pdf_url:
        r.fulltext_available = True
        r.fulltext_source = r.fulltext_source or r.source_database
        return True

    # Already has fulltext URL
    if r.fulltext_url:
        r.fulltext_available = True
        r.fulltext_source = r.fulltext_source or r.source_database
        # Use fulltext URL as pdf_url if no dedicated PDF
        if not r.pdf_url:
            r.pdf_url = r.fulltext_url
        return True

    return False


def enrich_single(result: LiteratureResult, cache=None) -> LiteratureResult:
    """Enrich a single LiteratureResult with fulltext links.

    Args:
        result: The result to enrich
        cache: Optional LiteratureCache for storing fulltext links

    Returns:
        The enriched result
    """
    r = enrich_fulltext_links([result])[0]

    if cache and r.fulltext_available and r.doi:
        try:
            cache.save_fulltext_link(
                literature_id=r.id or 0,
                doi=r.doi,
                source=r.fulltext_source or "unknown",
                pdf_url=r.pdf_url or "",
                landing_page_url=r.fulltext_url or "",
                license_val=r.oa_license or "",
                is_oa=True,
            )
        except Exception as e:
            logger.warning(f"Failed to save fulltext link to cache: {e}")

    return r
