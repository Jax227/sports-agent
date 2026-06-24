"""
PubMed connector via NCBI Entrez E-utilities.

Uses biopython if installed, otherwise raw HTTP to eutils.
Requires ENTREZ_EMAIL env var (NCBI requirement).

Docs: https://www.ncbi.nlm.nih.gov/books/NBK25501/
"""

import os
import logging
from typing import Optional

from app.literature.connectors.base import BaseConnector, ConnectorUnavailable
from app.literature.schema import LiteratureResult

logger = logging.getLogger(__name__)


class PubMedConnector(BaseConnector):
    name = "pubmed"
    label = "PubMed"
    homepage = "https://pubmed.ncbi.nlm.nih.gov/"

    def __init__(self):
        super().__init__()
        self._email = os.getenv("ENTREZ_EMAIL", os.getenv("PUBMED_EMAIL", ""))
        self._api_key = os.getenv("NCBI_API_KEY", "")
        self._use_biopython = False
        try:
            from Bio import Entrez
            Entrez.email = self._email
            if self._api_key:
                Entrez.api_key = self._api_key
            self._use_biopython = True
        except ImportError:
            logger.info("biopython not installed, using raw HTTP for PubMed")

    def _check_availability(self):
        if not self._email:
            raise ConnectorUnavailable(
                "Missing ENTREZ_EMAIL environment variable. "
                "Set it to your email address (required by NCBI)."
            )

    # ── Search ────────────────────────────────────────────────────

    def search(
        self, query: str, limit: int = 20, filters: Optional[dict] = None
    ) -> list[LiteratureResult]:
        if self._use_biopython:
            return self._search_biopython(query, limit)
        return self._search_http(query, limit)

    def _search_biopython(self, query: str, limit: int) -> list[LiteratureResult]:
        from Bio import Entrez

        try:
            # 1. Search for IDs
            handle = Entrez.esearch(
                db="pubmed", term=query, retmax=limit,
                sort="relevance", usehistory="y",
            )
            search_data = Entrez.read(handle)
            handle.close()

            id_list = search_data.get("IdList", [])
            if not id_list:
                return []

            # 2. Fetch details
            handle = Entrez.efetch(db="pubmed", id=",".join(id_list), rettype="xml", retmode="xml")
            records = Entrez.read(handle)
            handle.close()

            return [self.normalize(article) for article in records]
        except Exception as e:
            logger.warning(f"PubMed (biopython) search error: {e}")
            return self._search_http(query, limit)

    def _search_http(self, query: str, limit: int) -> list[LiteratureResult]:
        import urllib.request
        import urllib.parse
        import json as _json
        import xml.etree.ElementTree as ET

        base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": str(limit),
            "sort": "relevance",
            "usehistory": "y",
        }
        if self._email:
            params["email"] = self._email
        if self._api_key:
            params["api_key"] = self._api_key

        try:
            # ESearch
            url = base + "/esearch.fcgi?" + urllib.parse.urlencode(params)
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=15) as resp:
                root = ET.fromstring(resp.read())
            id_list = [e.text for e in root.findall(".//Id") if e.text]
            if not id_list:
                return []

            # EFetch
            fetch_url = base + "/efetch.fcgi?db=pubmed&id=" + ",".join(id_list) + "&rettype=xml&retmode=xml"
            fetch_req = urllib.request.Request(fetch_url)
            with urllib.request.urlopen(fetch_req, timeout=15) as resp:
                fetch_xml = ET.fromstring(resp.read())

            return [self._parse_pubmed_article(a) for a in fetch_xml.findall(".//PubmedArticle")]
        except Exception as e:
            logger.warning(f"PubMed HTTP search error: {e}")
            return []

    def _parse_pubmed_article(self, article) -> LiteratureResult:
        """Parse a PubmedArticle XML element into LiteratureResult."""
        medline = article.find(".//MedlineCitation")
        article_node = medline.find(".//Article") if medline is not None else None

        # PMID
        pmid_el = medline.find(".//PMID") if medline is not None else None
        pmid = pmid_el.text if pmid_el is not None else None

        # Title
        title = ""
        if article_node is not None:
            title_el = article_node.find(".//ArticleTitle")
            if title_el is not None and title_el.text:
                title = title_el.text

        # Authors
        authors = []
        if article_node is not None:
            for a in article_node.findall(".//Author"):
                last = a.findtext("LastName", "")
                fore = a.findtext("ForeName", "")
                if last or fore:
                    authors.append(f"{fore} {last}".strip())

        # Journal
        journal = ""
        if article_node is not None:
            journal_el = article_node.find(".//Journal/Title")
            if journal_el is not None and journal_el.text:
                journal = journal_el.text

        # Year
        year = None
        if article_node is not None:
            year_el = article_node.find(".//Journal/JournalIssue/PubDate/Year")
            if year_el is not None and year_el.text:
                year = self._safe_int(year_el.text)

        # Abstract
        abstract = ""
        if article_node is not None:
            parts = article_node.findall(".//AbstractText")
            abstract = " ".join(p.text or "" for p in parts if p.text)
        if not abstract:
            abstract = None

        # DOI
        doi = None
        if article_node is not None:
            for eid in article_node.findall(".//ELocationID"):
                if eid.get("EIdType") == "doi" and eid.text:
                    doi = eid.text

        # PMCID
        pmcid = None
        pcs = [] if medline is None else medline.findall(".//OtherID[@Source='PMC']")
        for pc in pcs:
            if pc is not None and pc.text:
                pmcid = pc.text
                break

        # Publication types
        pub_types = []
        if article_node is not None:
            for pt in article_node.findall(".//PublicationType"):
                if pt is not None and pt.text:
                    pub_types.append(pt.text)

        # Keywords
        keywords = []
        if medline is not None:
            for kw in medline.findall(".//Keyword"):
                if kw is not None and kw.text:
                    keywords.append(kw.text)

        return LiteratureResult(
            external_id=f"pmid:{pmid}" if pmid else None,
            title=title,
            authors=authors,
            year=year,
            doi=doi,
            pmid=pmid,
            pmcid=pmcid,
            abstract=abstract[:2000] if abstract else None,
            journal=journal,
            source_database="pubmed",
            url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None,
            publication_type="; ".join(pub_types) if pub_types else None,
            keywords=keywords,
        )

    # ── Normalize ──────────────────────────────────────────────────

    def normalize(self, raw: dict) -> LiteratureResult:
        """Normalize a biopython-parsed PubmedArticle dict."""
        medline = raw.get("MedlineCitation", raw)
        article = medline.get("Article", {})

        # PMID
        pmid = str(medline.get("PMID", ""))

        # Authors
        authors = []
        author_list = article.get("AuthorList", [])
        for a in author_list:
            last = a.get("LastName", "")
            fore = a.get("ForeName", "")
            if last or fore:
                authors.append(f"{fore} {last}".strip())

        # Title
        title = str(article.get("ArticleTitle", ""))

        # Abstract
        abstract_parts = article.get("Abstract", {}).get("AbstractText", [])
        if isinstance(abstract_parts, list):
            abstract = " ".join(str(p) for p in abstract_parts)
        else:
            abstract = str(abstract_parts)
        if not abstract:
            abstract = None

        # Journal
        journal = str(article.get("Journal", {}).get("Title", ""))

        # Year
        year = None
        pub_date = article.get("Journal", {}).get("JournalIssue", {}).get("PubDate", {})
        y = pub_date.get("Year")
        if y:
            year = self._safe_int(str(y))

        # DOI
        doi = None
        for eid in article.get("ELocationID", []):
            if isinstance(eid, dict) and eid.get("EIdType") == "doi":
                doi = str(eid.get("content", ""))
                break

        # Publication types
        pub_types = [str(p) for p in article.get("PublicationTypeList", [])]

        return LiteratureResult(
            external_id=f"pmid:{pmid}" if pmid else None,
            title=title,
            authors=authors,
            year=year,
            doi=doi,
            pmid=pmid,
            abstract=abstract[:2000] if abstract else None,
            journal=journal,
            source_database="pubmed",
            url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None,
            publication_type="; ".join(pub_types) if pub_types else None,
            keywords=[str(k) for k in medline.get("KeywordList", [[]])[0] if k],
            raw=raw,
        )

    def get_by_doi(self, doi: str) -> Optional[LiteratureResult]:
        results = self._safe_search(f'"{doi}"[DOI]', limit=1, filters=None)
        return results[0] if results else None
