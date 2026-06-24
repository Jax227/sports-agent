"""
Semantic Scholar connector — AI-powered academic search.

Docs: https://api.semanticscholar.org/
Free tier: 100 requests/5min without API key, 100/sec with key.

If SEMANTIC_SCHOLAR_API_KEY is not set, operates in low-rate mode.
Missing API key will NOT crash the system.
"""

import os
import logging
import time
from typing import Optional

from app.literature.connectors.base import BaseConnector, ConnectorUnavailable
from app.literature.schema import LiteratureResult

logger = logging.getLogger(__name__)


class SemanticScholarConnector(BaseConnector):
    name = "semantic_scholar"
    label = "Semantic Scholar"
    homepage = "https://www.semanticscholar.org/"

    def __init__(self):
        super().__init__()
        self._api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")
        self._rate_limited = False
        self._last_request_time: float = 0

    def _check_availability(self):
        # Available without API key (rate-limited)
        pass

    @property
    def available(self) -> bool:
        return True  # Always available, just potentially rate-limited

    @property
    def status(self) -> dict:
        s = super().status
        if not self._api_key:
            s["message"] = "No API key — rate-limited mode (100 req/5min)"
        else:
            s["message"] = "OK (authenticated)"
        return s

    # ── Rate limiting ─────────────────────────────────────────────

    def _respect_rate_limit(self):
        """Ensure we don't exceed rate limits."""
        if self._api_key:
            # 100/sec — be polite
            elapsed = time.perf_counter() - self._last_request_time
            if elapsed < 0.1:
                time.sleep(0.1 - elapsed)
        else:
            # 100/5min — very conservative
            elapsed = time.perf_counter() - self._last_request_time
            if elapsed < 3.0:
                time.sleep(3.0 - elapsed)
        self._last_request_time = time.perf_counter()

    # ── Search ────────────────────────────────────────────────────

    def search(
        self, query: str, limit: int = 20, filters: Optional[dict] = None
    ) -> list[LiteratureResult]:
        import urllib.request
        import json as _json

        self._respect_rate_limit()

        params = {
            "query": query,
            "limit": str(min(limit, 100)),
            "fields": "title,authors,year,abstract,externalIds,citationCount,"
                       "url,openAccessPdf,publicationTypes,journal,publicationDate",
        }

        url = "https://api.semanticscholar.org/graph/v1/paper/search?" + urllib.parse.urlencode(params)

        headers = {}
        if self._api_key:
            headers["x-api-key"] = self._api_key

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = _json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                self._rate_limited = True
                logger.warning("Semantic Scholar rate limited")
            return []
        except Exception as e:
            logger.warning(f"Semantic Scholar search error: {e}")
            return []

        results = []
        for paper in data.get("data", [])[:limit]:
            results.append(self.normalize(paper))
        return results

    # ── Normalize ──────────────────────────────────────────────────

    def normalize(self, raw: dict) -> LiteratureResult:
        # Authors
        authors = []
        for a in raw.get("authors", []) or []:
            name = a.get("name", "")
            if name:
                authors.append(name)

        # External IDs
        ext_ids = raw.get("externalIds", {}) or {}
        doi = ext_ids.get("DOI")
        pmid = ext_ids.get("PubMed")
        pmcid = ext_ids.get("PubMedCentral")

        # OA PDF
        oa_pdf = raw.get("openAccessPdf", {}) or {}
        pdf_url = oa_pdf.get("url")
        is_oa = pdf_url is not None

        # Year
        year = raw.get("year")
        if not year:
            pub_date = raw.get("publicationDate", "")
            if pub_date and len(pub_date) >= 4:
                year = self._safe_int(pub_date[:4])

        # Journal
        journal_info = raw.get("journal", {}) or {}
        journal = journal_info.get("name") or journal_info.get("displayName")

        # Publication types
        pub_types = raw.get("publicationTypes", []) or []

        return LiteratureResult(
            external_id=raw.get("paperId"),
            title=raw.get("title", ""),
            authors=authors,
            year=year,
            doi=doi,
            pmid=pmid,
            pmcid=pmcid,
            abstract=(raw.get("abstract") or "")[:2000] if raw.get("abstract") else None,
            journal=journal,
            source_database="semantic_scholar",
            citation_count=self._safe_int(raw.get("citationCount")),
            url=raw.get("url") or f"https://www.semanticscholar.org/paper/{raw.get('paperId')}" if raw.get("paperId") else None,
            pdf_url=pdf_url,
            open_access=is_oa,
            publication_type="; ".join(pub_types) if pub_types else None,
            raw=raw,
        )

    def get_by_doi(self, doi: str) -> Optional[LiteratureResult]:
        self._respect_rate_limit()
        import urllib.request
        import json as _json

        try:
            url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}"
            params = "?fields=title,authors,year,abstract,externalIds,citationCount,url,openAccessPdf,publicationTypes,journal"
            headers = {}
            if self._api_key:
                headers["x-api-key"] = self._api_key

            req = urllib.request.Request(url + params, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = _json.loads(resp.read().decode())
                if data.get("paperId"):
                    return self.normalize(data)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
        except Exception as e:
            logger.warning(f"S2 get_by_doi error for {doi}: {e}")
        return None
