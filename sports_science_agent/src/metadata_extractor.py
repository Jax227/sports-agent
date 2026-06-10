"""Metadata extractor — DOI/PMID lookups via CrossRef and PubMed APIs."""

import time
import requests
from typing import Optional
from xml.etree import ElementTree

from src.config import CROSSREF_MAILTO, PUBMED_EMAIL
from src.utils import normalize_doi, normalize_pmid, logger


CROSSREF_BASE = "https://api.crossref.org/works"
PUBMED_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
SEMANTIC_SCHOLAR_BASE = "https://api.semanticscholar.org/graph/v1/paper"


def lookup_doi_crossref(doi: str) -> Optional[dict]:
    """Fetch metadata from CrossRef by DOI."""
    doi = normalize_doi(doi)
    if not doi:
        return None

    headers = {}
    if CROSSREF_MAILTO:
        headers["User-Agent"] = f"SportsScienceAgent/1.0 (mailto:{CROSSREF_MAILTO})"

    try:
        url = f"{CROSSREF_BASE}/{doi}"
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            logger.warning(f"CrossRef lookup failed for DOI {doi}: HTTP {resp.status_code}")
            return None
        data = resp.json()
        msg = data.get("message", {})
        authors_list = msg.get("author", [])
        authors = "; ".join(
            f"{a.get('given', '')} {a.get('family', '')}" for a in authors_list
        )
        published = msg.get("published-print", {}) or msg.get("issued", {}) or {}
        date_parts = published.get("date-parts", [[None]])[0]
        year = date_parts[0] if date_parts else None

        return {
            "title": (msg.get("title") or [""])[0],
            "authors": authors,
            "year": year,
            "journal": (msg.get("container-title") or [""])[0],
            "doi": msg.get("DOI"),
            "abstract": msg.get("abstract", ""),
            "volume": msg.get("volume", ""),
            "issue": msg.get("issue", ""),
            "pages": msg.get("page", ""),
            "publisher": msg.get("publisher", ""),
            "type": msg.get("type", ""),
            "subject": msg.get("subject", []),
            "references_count": msg.get("references-count", 0),
            "is_referenced_by_count": msg.get("is-referenced-by-count", 0),
            "source": "crossref",
        }
    except Exception as e:
        logger.error(f"CrossRef error for DOI {doi}: {e}")
        return None


def lookup_pmid_pubmed(pmid: str) -> Optional[dict]:
    """Fetch metadata from PubMed by PMID."""
    pmid = normalize_pmid(pmid)
    if not pmid:
        return None

    params = {
        "db": "pubmed",
        "id": pmid,
        "retmode": "xml",
        "rettype": "abstract",
    }
    if PUBMED_EMAIL:
        params["email"] = PUBMED_EMAIL

    try:
        resp = requests.get(PUBMED_EFETCH, params=params, timeout=15)
        if resp.status_code != 200:
            logger.warning(f"PubMed lookup failed for PMID {pmid}: HTTP {resp.status_code}")
            return None

        root = ElementTree.fromstring(resp.content)
        article = root.find(".//PubmedArticle")
        if article is None:
            return None

        medline = article.find(".//MedlineCitation")
        if medline is None:
            medline = article

        article_data = medline.find(".//Article")
        if article_data is None:
            return None

        title_el = article_data.find(".//ArticleTitle")
        title = title_el.text if title_el is not None else ""

        abstract_el = article_data.find(".//Abstract")
        abstract = ""
        if abstract_el is not None:
            parts = abstract_el.findall(".//AbstractText")
            abstract = " ".join(p.text or "" for p in parts if p.text)

        authors_list = article_data.findall(".//Author")
        authors = "; ".join(
            f"{a.findtext('ForeName', '')} {a.findtext('LastName', '')}".strip()
            for a in authors_list
        )

        journal_el = article_data.find(".//Journal")
        journal_title = ""
        if journal_el is not None:
            jtitle = journal_el.find(".//Title")
            journal_title = jtitle.text if jtitle is not None else ""

        year = ""
        pubdate = article_data.find(".//PubDate")
        if pubdate is not None:
            y = pubdate.find("Year")
            if y is not None and y.text:
                year = y.text

        doi = ""
        for eid in article.findall(".//ELocationID"):
            if eid.get("EIdType") == "doi":
                doi = eid.text or ""

        return {
            "title": title,
            "authors": authors,
            "year": year,
            "journal": journal_title,
            "doi": doi,
            "pmid": pmid,
            "abstract": abstract,
            "source": "pubmed",
        }
    except Exception as e:
        logger.error(f"PubMed error for PMID {pmid}: {e}")
        return None


def lookup_semantic_scholar(doi: str = "", title: str = "") -> Optional[dict]:
    """Search Semantic Scholar by DOI or title."""
    try:
        if doi:
            doi = normalize_doi(doi)
            url = f"{SEMANTIC_SCHOLAR_BASE}/DOI:{doi}?fields=title,authors,year,journal,abstract,citationCount,references,referenceCount"
        elif title:
            from urllib.parse import quote_plus
            url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={quote_plus(title)}&limit=1&fields=title,authors,year,journal,abstract,citationCount,references,referenceCount"
        else:
            return None

        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            return None

        data = resp.json()
        if not data:
            return None

        # Handle search vs direct lookup
        paper = data.get("data", [data]) if "data" in data else data
        if isinstance(paper, list):
            paper = paper[0] if paper else {}

        authors_list = paper.get("authors", [])
        authors = "; ".join(a.get("name", "") for a in authors_list)

        return {
            "title": paper.get("title", ""),
            "authors": authors,
            "year": paper.get("year"),
            "journal": paper.get("journal", {}).get("name", "") if isinstance(paper.get("journal"), dict) else "",
            "doi": paper.get("externalIds", {}).get("DOI", ""),
            "abstract": paper.get("abstract", ""),
            "citation_count": paper.get("citationCount", 0),
            "reference_count": paper.get("referenceCount", 0),
            "source": "semantic_scholar",
        }
    except Exception as e:
        logger.error(f"Semantic Scholar error: {e}")
        return None


def lookup_by_identifier(identifier: str) -> Optional[dict]:
    """Auto-detect identifier type and fetch metadata."""
    doi = normalize_doi(identifier)
    if doi:
        result = lookup_doi_crossref(doi)
        if result:
            return result
        result = lookup_semantic_scholar(doi=doi)
        return result

    pmid = normalize_pmid(identifier)
    if pmid:
        return lookup_pmid_pubmed(pmid)

    return None


def search_pubmed(query: str, max_results: int = 10) -> list[dict]:
    """Search PubMed for papers matching a query."""
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": str(max_results),
        "retmode": "xml",
        "sort": "relevance",
    }
    if PUBMED_EMAIL:
        params["email"] = PUBMED_EMAIL

    try:
        resp = requests.get(PUBMED_ESEARCH, params=params, timeout=15)
        if resp.status_code != 200:
            return []
        root = ElementTree.fromstring(resp.content)
        pmids = [e.text for e in root.findall(".//Id") if e.text]
        results = []
        for pmid in pmids[:max_results]:
            meta = lookup_pmid_pubmed(pmid)
            if meta:
                results.append(meta)
            time.sleep(0.34)  # Respect NCBI rate limit (3/sec)
        return results
    except Exception as e:
        logger.error(f"PubMed search error: {e}")
        return []
