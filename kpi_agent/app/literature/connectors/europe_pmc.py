"""
Europe PMC connector — free biomedical literature API.

Docs: https://europepmc.org/RestfulWebService
Base URL: https://www.ebi.ac.uk/europepmc/webservices/rest/search

No API key required. Free for research use.
"""

import logging
from typing import Optional

from app.literature.connectors.base import BaseConnector, ConnectorUnavailable
from app.literature.schema import LiteratureResult

logger = logging.getLogger(__name__)


class EuropePMCConnector(BaseConnector):
    name = "europe_pmc"
    label = "Europe PMC"
    homepage = "https://europepmc.org/"

    def __init__(self):
        super().__init__()

    def _check_availability(self):
        # Free, no API key needed
        pass

    # ── Search ────────────────────────────────────────────────────

    def search(
        self, query: str, limit: int = 20, filters: Optional[dict] = None
    ) -> list[LiteratureResult]:
        import urllib.request
        import urllib.parse
        import json as _json

        params = {
            "query": query,
            "resultType": "core",
            "pageSize": str(min(limit, 100)),
            "format": "json",
        }

        # Add sport/medicine relevant filters if not already in query
        if filters:
            if filters.get("year_from"):
                params["query"] = f'{params["query"]} AND FIRST_PDATE:[{filters["year_from"]} TO 3000]'
            if filters.get("open_access"):
                params["query"] = f'{params["query"]} AND (OPEN_ACCESS:Y)'

        url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + urllib.parse.urlencode(params)

        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = _json.loads(resp.read().decode())
        except Exception as e:
            logger.warning(f"Europe PMC search error: {e}")
            return []

        results = data.get("resultList", {}).get("result", [])
        return [self.normalize(r) for r in results[:limit]]

    # ── Normalize ──────────────────────────────────────────────────

    def normalize(self, raw: dict) -> LiteratureResult:
        # Authors
        author_str = raw.get("authorString", "") or ""
        authors = [a.strip() for a in author_str.split(",") if a.strip()]

        # IDs
        doi = raw.get("doi")
        pmid = raw.get("pmid")
        pmcid = raw.get("pmcid")

        # OA status
        is_oa = str(raw.get("isOpenAccess", "")).upper() == "Y"
        oa_status = None
        if is_oa:
            oa_status = "open"

        # Fulltext URLs from Europe PMC
        fulltext_url = None
        pdf_url = None
        fulltext_url_list = raw.get("fullTextUrlList", {})
        if fulltext_url_list:
            urls = fulltext_url_list.get("fullTextUrl", [])
            if isinstance(urls, list):
                for u in urls:
                    if isinstance(u, dict):
                        doc_style = u.get("documentStyle", "")  # e.g. "pdf", "html"
                        site = u.get("site", "")
                        link_url = u.get("url", "")
                        if doc_style == "pdf" and not pdf_url:
                            pdf_url = link_url
                        if not fulltext_url:
                            fulltext_url = link_url
            elif isinstance(urls, dict):
                if urls.get("documentStyle") == "pdf":
                    pdf_url = urls.get("url")
                fulltext_url = urls.get("url")

        return LiteratureResult(
            external_id=raw.get("id"),
            title=raw.get("title", ""),
            authors=authors,
            year=self._safe_int(raw.get("pubYear")),
            doi=doi,
            pmid=pmid,
            pmcid=pmcid,
            abstract=(raw.get("abstractText") or "")[:2000] if raw.get("abstractText") else None,
            journal=raw.get("journalTitle") or raw.get("bookOrReportDetails", {}).get("publisher"),
            source_database="europe_pmc",
            citation_count=self._safe_int(raw.get("citedByCount")),
            url=raw.get("source") or f"https://europepmc.org/article/MED/{pmid}" if pmid else None,
            pdf_url=pdf_url,
            fulltext_url=fulltext_url,
            open_access=is_oa,
            open_access_status=oa_status,
            publication_type=raw.get("pubType"),
            keywords=(raw.get("keywordList", {}).get("keyword", []) or []) if isinstance(raw.get("keywordList"), dict) else [],
            raw=raw,
        )

    def get_by_doi(self, doi: str) -> Optional[LiteratureResult]:
        results = self._safe_search(f'DOI:"{doi}"', limit=1, filters=None)
        return results[0] if results else None
