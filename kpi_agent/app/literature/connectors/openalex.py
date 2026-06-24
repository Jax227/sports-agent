"""
OpenAlex connector — free, open academic search API.

Docs: https://docs.openalex.org/
Base URL: https://api.openalex.org/works

Uses pyalex if installed, otherwise raw httpx/requests.
Requires email for polite pool (configurable via OPENALEX_EMAIL env var).
"""

import os
import logging
from typing import Optional

from app.literature.connectors.base import BaseConnector, ConnectorUnavailable
from app.literature.schema import LiteratureResult

logger = logging.getLogger(__name__)


class OpenAlexConnector(BaseConnector):
    name = "openalex"
    label = "OpenAlex"
    homepage = "https://openalex.org"

    def __init__(self):
        super().__init__()
        self._email = os.getenv("OPENALEX_EMAIL", os.getenv("ENTREZ_EMAIL", ""))
        self._use_pyalex = False
        try:
            import pyalex
            if self._email:
                pyalex.config.email = self._email
            self._use_pyalex = True
        except ImportError:
            logger.info("pyalex not installed, using raw HTTP for OpenAlex")

    def _check_availability(self):
        # OpenAlex is free — always available
        pass

    # ── Search ────────────────────────────────────────────────────

    def search(
        self, query: str, limit: int = 20, filters: Optional[dict] = None
    ) -> list[LiteratureResult]:
        if self._use_pyalex:
            return self._search_pyalex(query, limit, filters)
        return self._search_http(query, limit, filters)

    def _search_pyalex(self, query: str, limit: int, filters: dict | None) -> list[LiteratureResult]:
        import pyalex
        from pyalex import Works

        try:
            pager = Works().search(query).paginate(per_page=min(limit, 50), n_max=limit)
            results = []
            for page in pager:
                for work in page:
                    results.append(self.normalize(work))
                    if len(results) >= limit:
                        break
                if len(results) >= limit:
                    break
            return results
        except Exception as e:
            logger.warning(f"OpenAlex (pyalex) search error: {e}")
            return self._search_http(query, limit, filters)

    def _search_http(self, query: str, limit: int, filters: dict | None) -> list[LiteratureResult]:
        import urllib.request
        import json as _json

        params = {
            "search": query,
            "per_page": str(min(limit, 50)),
        }
        if self._email:
            params["mailto"] = self._email

        url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)

        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = _json.loads(resp.read().decode())
        except Exception as e:
            logger.warning(f"OpenAlex HTTP search error: {e}")
            return []

        results = []
        for work in data.get("results", [])[:limit]:
            results.append(self.normalize(work))
        return results

    # ── Normalize ──────────────────────────────────────────────────

    def normalize(self, raw: dict) -> LiteratureResult:
        # Extract authors
        authors = []
        for a in raw.get("authorships", []) or []:
            author_info = a.get("author", {}) if isinstance(a, dict) else {}
            name = author_info.get("display_name", "")
            if name:
                authors.append(name)

        # OA info
        oa_info = raw.get("open_access", {}) or {}
        oa_status = oa_info.get("oa_status")
        is_oa = oa_info.get("is_oa", False)
        oa_url = oa_info.get("oa_url") or ""

        # Primary location
        primary_loc = raw.get("primary_location", {}) or {}
        landing_url = primary_loc.get("landing_page_url", "")
        pdf_url = primary_loc.get("pdf_url", "")

        # DOI
        doi = raw.get("doi", "")
        if doi and doi.startswith("https://doi.org/"):
            doi = doi.replace("https://doi.org/", "")

        return LiteratureResult(
            external_id=raw.get("id", ""),
            title=raw.get("title", ""),
            authors=authors,
            year=self._safe_int(raw.get("publication_year")),
            doi=doi,
            pmid=raw.get("pmid"),
            pmcid=raw.get("pmcid"),
            abstract=(raw.get("abstract") or "")[:2000] if raw.get("abstract") else None,
            journal=(primary_loc.get("source", {}) or {}).get("display_name") if primary_loc else None,
            source_database="openalex",
            citation_count=self._safe_int(raw.get("cited_by_count")),
            url=landing_url or raw.get("id", ""),
            pdf_url=pdf_url or oa_url,
            fulltext_url=oa_url,
            open_access=is_oa,
            open_access_status=oa_status,
            publication_type=raw.get("type"),
            keywords=[k.get("display_name", "") for k in (raw.get("keywords", []) or []) if k.get("display_name")],
            raw=raw,
        )

    def get_by_doi(self, doi: str) -> Optional[LiteratureResult]:
        if self._use_pyalex:
            try:
                import pyalex
                from pyalex import Works
                work = Works()[f"https://doi.org/{doi}"]
                if work:
                    return self.normalize(work)
            except Exception:
                pass
        # HTTP fallback
        import urllib.request, json as _json
        try:
            url = f"https://api.openalex.org/works/https://doi.org/{doi}"
            if self._email:
                url += f"?mailto={self._email}"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = _json.loads(resp.read().decode())
                if data.get("id"):
                    return self.normalize(data)
        except Exception:
            pass
        return None
