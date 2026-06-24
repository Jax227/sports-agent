"""
Connector registry — manages all search connectors and provides
parallel multi-source search with status reporting.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from app.literature.connectors.base import BaseConnector
from app.literature.schema import LiteratureResult

logger = logging.getLogger(__name__)


class ConnectorRegistry:
    """Manages available literature search connectors."""

    _connectors: dict[str, BaseConnector] = {}
    _initialized: bool = False

    @classmethod
    def register(cls, connector: BaseConnector):
        """Register a connector instance."""
        cls._connectors[connector.name] = connector
        logger.info(f"Registered connector: {connector.name} (available={connector.available})")

    @classmethod
    def get(cls, name: str) -> Optional[BaseConnector]:
        """Get a connector by name."""
        cls._ensure_initialized()
        return cls._connectors.get(name)

    @classmethod
    def get_available(cls) -> list[BaseConnector]:
        """Get all available connectors."""
        cls._ensure_initialized()
        return [c for c in cls._connectors.values() if c.available]

    @classmethod
    def get_all(cls) -> list[BaseConnector]:
        """Get all registered connectors (including unavailable)."""
        cls._ensure_initialized()
        return list(cls._connectors.values())

    @classmethod
    def get_names(cls) -> list[str]:
        cls._ensure_initialized()
        return list(cls._connectors.keys())

    @classmethod
    def check_status(cls) -> list[dict]:
        """Return status for all registered connectors."""
        cls._ensure_initialized()
        return [c.status for c in cls._connectors.values()]

    @classmethod
    def _ensure_initialized(cls):
        """Lazy-init: register all connectors on first access."""
        if cls._initialized:
            return
        cls._initialized = True

        # Import and register all connectors
        from app.literature.connectors.openalex import OpenAlexConnector
        from app.literature.connectors.pubmed import PubMedConnector
        from app.literature.connectors.europe_pmc import EuropePMCConnector
        from app.literature.connectors.crossref import CrossrefConnector
        from app.literature.connectors.semantic_scholar import SemanticScholarConnector
        from app.literature.connectors.unpaywall import UnpaywallConnector

        cls.register(OpenAlexConnector())
        cls.register(PubMedConnector())
        cls.register(EuropePMCConnector())
        cls.register(CrossrefConnector())
        cls.register(SemanticScholarConnector())
        cls.register(UnpaywallConnector())


def search_all_sources(
    query: str,
    sources: Optional[list[str]] = None,
    limit_per_source: int = 20,
    filters: Optional[dict] = None,
    timeout_per_source: float = 30.0,
) -> dict:
    """
    Search across multiple sources in parallel.

    Args:
        query: Search query string
        sources: List of source names, e.g. ['openalex', 'pubmed']. None = all available.
        limit_per_source: Max results from each source
        filters: Optional filters dict
        timeout_per_source: Max seconds per source

    Returns:
        dict with:
        - results: list[LiteratureResult]
        - source_counts: dict[str, int]
        - source_status: list[dict]
        - errors: list[dict]
    """
    ConnectorRegistry._ensure_initialized()

    if sources:
        connectors = []
        for name in sources:
            c = ConnectorRegistry.get(name)
            if c and c.available:
                connectors.append(c)
            elif c:
                logger.info(f"Connector '{name}' registered but unavailable: {c.status['message']}")
    else:
        connectors = ConnectorRegistry.get_available()

    if not connectors:
        return {
            "results": [],
            "source_counts": {},
            "source_status": ConnectorRegistry.check_status(),
            "errors": [{"source": "all", "message": "No available connectors"}],
        }

    all_results: list[LiteratureResult] = []
    source_counts: dict[str, int] = {}
    errors: list[dict] = []

    with ThreadPoolExecutor(max_workers=min(len(connectors), 5)) as executor:
        futures = {
            executor.submit(c._safe_search, query, limit_per_source, filters): c
            for c in connectors
        }
        for future in as_completed(futures, timeout=timeout_per_source + 5):
            connector = futures[future]
            try:
                results = future.result(timeout=timeout_per_source)
                all_results.extend(results)
                source_counts[connector.name] = len(results)
            except Exception as e:
                msg = str(e)
                errors.append({"source": connector.name, "message": msg})
                source_counts[connector.name] = 0
                logger.warning(f"Source '{connector.name}' failed: {msg}")

    # Mark any sources that didn't complete
    for c in connectors:
        if c.name not in source_counts:
            source_counts[c.name] = 0

    return {
        "results": all_results,
        "source_counts": source_counts,
        "source_status": [c.status for c in connectors],
        "errors": errors,
    }
