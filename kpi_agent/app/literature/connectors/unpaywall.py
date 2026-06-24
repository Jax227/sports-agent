"""
Unpaywall connector — discover legal open-access fulltext links via DOI.

Docs: https://unpaywall.org/products/api
API: https://api.unpaywall.org/v2/{doi}?email={email}

This is NOT a search source — it's a fulltext enricher.
Requires UNPAYWALL_EMAIL or falls back to ENTREZ_EMAIL.
If no email is available, gracefully skips.
"""

import os
import logging
from typing import Optional

from app.literature.connectors.base import BaseConnector, ConnectorUnavailable
from app.literature.schema import LiteratureResult

logger = logging.getLogger(__name__)


class UnpaywallConnector(BaseConnector):
    name = "unpaywall"
    label = "Unpaywall"
    homepage = "https://unpaywall.org/"

    def __init__(self):
        super().__init__()
        self._email = os.getenv(
            "UNPAYWALL_EMAIL",
            os.getenv("ENTREZ_EMAIL", ""),
        )

    def _check_availability(self):
        if not self._email:
            raise ConnectorUnavailable(
                "No email configured. Set UNPAYWALL_EMAIL or ENTREZ_EMAIL env var."
            )

    # ── Search (not applicable — this is an enricher) ─────────────

    def search(
        self, query: str, limit: int = 20, filters: Optional[dict] = None
    ) -> list[LiteratureResult]:
        return []  # Unpaywall is not a search source

    def normalize(self, raw_record: dict) -> LiteratureResult:
        return LiteratureResult()  # Not used

    # ── DOI enrichment ────────────────────────────────────────────

    def enrich_by_doi(self, doi: str) -> dict:
        """Query Unpaywall for OA status of a DOI.

        Returns:
            dict with keys: is_oa, best_oa_location, pdf_url,
            landing_page_url, license, oa_status, source
        """
        if not doi:
            return self._empty_result("no_doi")

        import urllib.request
        import json as _json

        url = f"https://api.unpaywall.org/v2/{doi}?email={self._email}"

        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = _json.loads(resp.read().decode())
        except Exception as e:
            logger.warning(f"Unpaywall error for DOI {doi}: {e}")
            return self._empty_result("api_error")

        return self._parse_response(data)

    def _parse_response(self, data: dict) -> dict:
        is_oa = data.get("is_oa", False)
        oa_status = data.get("oa_status")

        result = {
            "is_oa": is_oa,
            "oa_status": oa_status,
            "pdf_url": None,
            "landing_page_url": None,
            "license": None,
            "source": "unpaywall",
        }

        if not is_oa:
            return result

        # Find best OA location
        best = data.get("best_oa_location") or {}
        if not best and data.get("oa_locations"):
            best = data["oa_locations"][0] if data["oa_locations"] else {}

        result.update({
            "pdf_url": best.get("url_for_pdf"),
            "landing_page_url": best.get("url_for_landing_page") or best.get("url"),
            "license": best.get("license"),
        })

        # If no PDF from best location, try others
        if not result["pdf_url"]:
            for loc in (data.get("oa_locations") or []):
                if loc.get("url_for_pdf"):
                    result["pdf_url"] = loc["url_for_pdf"]
                    result["landing_page_url"] = result["landing_page_url"] or loc.get("url_for_landing_page") or loc.get("url")
                    result["license"] = result["license"] or loc.get("license")
                    break

        return result

    def enrich_literature(self, result: LiteratureResult) -> LiteratureResult:
        """Enrich a LiteratureResult with Unpaywall OA info."""
        if not result.doi:
            return result

        oa_info = self.enrich_by_doi(result.doi)

        if oa_info.get("is_oa"):
            result.open_access = True
            result.open_access_status = oa_info.get("oa_status") or "open"
            result.fulltext_available = True
            result.fulltext_source = result.fulltext_source or "unpaywall"
            result.oa_license = oa_info.get("license")

            if oa_info.get("pdf_url") and not result.pdf_url:
                result.pdf_url = oa_info["pdf_url"]
            if oa_info.get("landing_page_url") and not result.fulltext_url:
                result.fulltext_url = oa_info["landing_page_url"]

        return result

    @staticmethod
    def _empty_result(reason: str = "unknown") -> dict:
        return {
            "is_oa": False,
            "oa_status": None,
            "pdf_url": None,
            "landing_page_url": None,
            "license": None,
            "source": "unpaywall",
            "reason": reason,
        }
