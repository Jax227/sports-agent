"""
Crossref connector — DOI and publication metadata search.

Uses habanero if installed, otherwise raw HTTP API.

Docs: https://api.crossref.org/
No API key required for basic usage (polite pool with email).
"""

import os
import logging
from typing import Optional

from app.literature.connectors.base import BaseConnector, ConnectorUnavailable
from app.literature.schema import LiteratureResult

logger = logging.getLogger(__name__)


class CrossrefConnector(BaseConnector):
    name = "crossref"
    label = "Crossref"
    homepage = "https://www.crossref.org/"

    def __init__(self):
        super().__init__()
        self._email = os.getenv("CROSSREF_MAILTO", os.getenv("ENTREZ_EMAIL", ""))
        self._use_habanero = False
        try:
            import habanero
            self._use_habanero = True
            if self._email:
                habanero.cn.mailto = self._email
        except ImportError:
            logger.info("habanero not installed, using raw HTTP for Crossref")

    def _check_availability(self):
        pass

    # ── Search ────────────────────────────────────────────────────

    def search(
        self, query: str, limit: int = 20, filters: Optional[dict] = None
    ) -> list[LiteratureResult]:
        if self._use_habanero:
            return self._search_habanero(query, limit, filters)
        return self._search_http(query, limit, filters)

    def _search_habanero(self, query: str, limit: int, filters: dict | None) -> list[LiteratureResult]:
        import habanero
        try:
            cr = habanero.Crossref()
            kwargs = {"limit": limit}
            if self._email:
                kwargs["mailto"] = self._email
            # Only filter works if provided
            f = {}
            if filters:
                if filters.get("year_from"):
                    f["from-pub-date"] = str(filters["year_from"])
                if filters.get("type"):
                    f["type"] = filters["type"]
            if f:
                kwargs["filter"] = f

            result = cr.works(query=query, **kwargs)
            items = result.get("message", {}).get("items", [])
            return [self.normalize(item) for item in items[:limit]]
        except Exception as e:
            logger.warning(f"Crossref (habanero) search error: {e}")
            return self._search_http(query, limit, filters)

    def _search_http(self, query: str, limit: int, filters: dict | None) -> list[LiteratureResult]:
        import urllib.request
        import urllib.parse
        import json as _json

        params = {
            "query": query,
            "rows": str(min(limit, 100)),
        }
        if self._email:
            params["mailto"] = self._email
        if filters:
            if filters.get("year_from"):
                params["filter"] = f"from-pub-date:{filters['year_from']}"

        url = "https://api.crossref.org/works?" + urllib.parse.urlencode(params)

        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = _json.loads(resp.read().decode())
        except Exception as e:
            logger.warning(f"Crossref HTTP search error: {e}")
            return []

        items = data.get("message", {}).get("items", [])
        return [self.normalize(item) for item in items[:limit]]

    # ── Normalize ──────────────────────────────────────────────────

    def normalize(self, raw: dict) -> LiteratureResult:
        # Authors
        authors = []
        for a in raw.get("author", []) or []:
            given = a.get("given", "")
            family = a.get("family", "")
            name = f"{given} {family}".strip()
            if name:
                authors.append(name)

        # DOI
        doi = raw.get("DOI")

        # Year
        year = None
        pub_date = raw.get("published-print", {}) or raw.get("published-online", {}) or {}
        date_parts = pub_date.get("date-parts", [[None]])[0]
        if date_parts and date_parts[0]:
            year = self._safe_int(date_parts[0])

        # Journal
        container = raw.get("container-title", [])
        journal = container[0] if container else None

        # Abstract
        abstract = raw.get("abstract")
        if abstract:
            abstract = abstract[:2000]

        # URLs
        url = None
        link_list = raw.get("link", [])
        for link in link_list:
            if link.get("content-type") == "text/html" or link.get("URL"):
                url = link.get("URL")
                break
        if not url and doi:
            url = f"https://doi.org/{doi}"

        return LiteratureResult(
            external_id=doi,
            title=raw.get("title", [""])[0] if raw.get("title") else "",
            authors=authors,
            year=year,
            doi=doi,
            abstract=abstract,
            journal=journal,
            source_database="crossref",
            citation_count=self._safe_int(raw.get("is-referenced-by-count")),
            url=url,
            publication_type=raw.get("type"),
            keywords=list(raw.get("subject", [])) if raw.get("subject") else [],
            raw=raw,
        )

    def get_by_doi(self, doi: str) -> Optional[LiteratureResult]:
        import urllib.request
        import json as _json

        try:
            url = f"https://api.crossref.org/works/{doi}"
            if self._email:
                url += f"?mailto={self._email}"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = _json.loads(resp.read().decode())
                item = data.get("message", {})
                if item:
                    return self.normalize(item)
        except Exception as e:
            logger.warning(f"Crossref get_by_doi error for {doi}: {e}")
        return None
