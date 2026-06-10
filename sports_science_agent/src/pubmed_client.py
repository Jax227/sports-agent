"""Enhanced PubMed client — search, fetch, and parse with full metadata extraction."""

import time
from datetime import datetime
from typing import Optional
from xml.etree import ElementTree

import requests

from src.config import PUBMED_EMAIL
from src.utils import normalize_doi, normalize_pmid, logger


PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
NCBI_API_KEY = ""  # Set from env in config

# Module-level error state for upstream consumers to inspect
LAST_ERROR = None  # {"type": "connection"|"http"|"parse", "message": str, "traceback": str}

# Bypass Windows system proxy (trust_env=False) to avoid SSL interception
# by corporate/academic network proxies that break HTTPS to PubMed
_session = requests.Session()
_session.trust_env = False


def _load_api_key():
    import os
    return os.getenv("NCBI_API_KEY", "")


def get_last_error() -> Optional[dict]:
    """Return the last PubMed error, or None if the last operation succeeded."""
    return LAST_ERROR


def search_pubmed(
    query: str,
    max_results: int = 20,
    sort: str = "relevance",
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
) -> list[dict]:
    """Search PubMed and return list of paper metadata dicts.

    Respects NCBI rate limits: 3/sec without API key, 10/sec with key.
    """
    global LAST_ERROR
    if not query:
        return []

    email = PUBMED_EMAIL or ""
    api_key = _load_api_key()

    params = {
        "db": "pubmed",
        "term": query,
        "retmax": str(max_results),
        "retmode": "xml",
        "sort": sort,
    }
    if email:
        params["email"] = email
    if api_key:
        params["api_key"] = api_key

    if year_from or year_to:
        date_range = f"{year_from or 1900}:{year_to or 2030}[pdat]"
        params["term"] = f"({query}) AND {date_range}"

    try:
        resp = _session.get(PUBMED_ESEARCH, params=params, timeout=30)
        if resp.status_code != 200:
            LAST_ERROR = {
                "type": "http",
                "message": f"PubMed 服务器返回 HTTP {resp.status_code}，请稍后重试",
                "detail": resp.text[:200] if resp.text else "",
            }
            logger.error(f"PubMed search HTTP {resp.status_code}")
            return []

        root = ElementTree.fromstring(resp.content)
        pmids = [e.text for e in root.findall(".//Id") if e.text]

        if not pmids:
            LAST_ERROR = None  # Valid response, just no matches
            logger.info("PubMed search returned 0 results — query had no matches")
            return []

        # Fetch details in batches
        delay = 0.1 if api_key else 0.34
        results = []
        for pmid in pmids[:max_results]:
            paper = _fetch_pubmed_details(pmid, email, api_key)
            if paper:
                results.append(paper)
            time.sleep(delay)

        LAST_ERROR = None
        logger.info(f"PubMed search: {len(results)} papers retrieved for query")
        return results

    except requests.exceptions.SSLError as e:
        LAST_ERROR = {
            "type": "connection",
            "message": "PubMed 连接失败：SSL证书验证错误，可能是网络代理拦截了 HTTPS 请求",
            "detail": str(e)[:300],
        }
        logger.error(f"PubMed SSL error: {e}")
        return []
    except requests.exceptions.ConnectionError as e:
        LAST_ERROR = {
            "type": "connection",
            "message": "PubMed 连接失败：无法连接到 eutils.ncbi.nlm.nih.gov，请检查网络或代理设置",
            "detail": str(e)[:300],
        }
        logger.error(f"PubMed connection error: {e}")
        return []
    except requests.exceptions.Timeout as e:
        LAST_ERROR = {
            "type": "connection",
            "message": "PubMed 连接超时：请求超过30秒未响应，请检查网络或稍后重试",
            "detail": str(e)[:300],
        }
        logger.error(f"PubMed timeout: {e}")
        return []
    except Exception as e:
        LAST_ERROR = {
            "type": "unknown",
            "message": f"PubMed 检索异常: {type(e).__name__}",
            "detail": str(e)[:300],
        }
        logger.error(f"PubMed search error: {type(e).__name__}: {e}")
        return []


def _fetch_pubmed_details(pmid: str, email: str = "", api_key: str = "") -> Optional[dict]:
    """Fetch full metadata for a PubMed ID."""
    params = {
        "db": "pubmed",
        "id": pmid,
        "retmode": "xml",
        "rettype": "abstract",
    }
    if email:
        params["email"] = email
    if api_key:
        params["api_key"] = api_key

    try:
        resp = _session.get(PUBMED_EFETCH, params=params, timeout=15)
        if resp.status_code != 200:
            logger.warning(f"PubMed efetch HTTP {resp.status_code} for PMID {pmid}")
            return None

        root = ElementTree.fromstring(resp.content)
        article = root.find(".//PubmedArticle")
        if article is None:
            return None

        return _parse_pubmed_article(article, pmid)

    except requests.exceptions.SSLError as e:
        logger.error(f"PubMed efetch SSL error for PMID {pmid}: {e}")
        return None
    except requests.exceptions.ConnectionError as e:
        logger.error(f"PubMed efetch connection error for PMID {pmid}: {e}")
        return None
    except requests.exceptions.Timeout as e:
        logger.error(f"PubMed efetch timeout for PMID {pmid}: {e}")
        return None
    except Exception as e:
        logger.error(f"PubMed efetch error for PMID {pmid}: {type(e).__name__}: {e}")
        return None


def _parse_pubmed_article(article, pmid: str) -> dict:
    """Parse a PubMed PubmedArticle XML element into a structured dict."""
    medline = article.find(".//MedlineCitation")
    if medline is None:
        medline = article

    article_data = medline.find(".//Article")
    if article_data is None:
        return {"pmid": pmid, "title": "", "source": "pubmed"}

    # Title
    title_el = article_data.find(".//ArticleTitle")
    title = title_el.text.strip() if title_el is not None and title_el.text else ""

    # Abstract
    abstract_el = article_data.find(".//Abstract")
    abstract = ""
    if abstract_el is not None:
        parts = abstract_el.findall(".//AbstractText")
        abstract = " ".join(
            (p.text or "") + (" " + (p.get("Label", "") + ": " + p.text) if p.get("Label") and p.text else "")
            for p in parts if p.text
        )
        if not abstract:
            # Try simpler approach
            abstract = " ".join(p.text or "" for p in parts if p.text)

    # Authors
    authors_list = article_data.findall(".//Author")
    authors = []
    for a in authors_list:
        fore = a.findtext("ForeName", "")
        last = a.findtext("LastName", "")
        if fore or last:
            authors.append(f"{fore} {last}".strip())
    authors_str = "; ".join(authors)

    # Journal
    journal_el = article_data.find(".//Journal")
    journal_title = ""
    issn = ""
    if journal_el is not None:
        jtitle = journal_el.find(".//Title")
        if jtitle is not None and jtitle.text:
            journal_title = jtitle.text.strip()
        # ISO abbreviation
        iso_abbrev = journal_el.find(".//ISOAbbreviation")
        if iso_abbrev is not None and iso_abbrev.text:
            issn_el = journal_el.find(".//ISSN")
            if issn_el is not None and issn_el.text:
                issn = issn_el.text.strip()

    # Year
    year = ""
    pubdate = article_data.find(".//PubDate")
    if pubdate is not None:
        y = pubdate.find("Year")
        if y is not None and y.text:
            year = y.text

    # DOI
    doi = ""
    for eid in article.findall(".//ELocationID"):
        if eid.get("EIdType") == "doi":
            doi = eid.text or ""

    # Publication Type
    pub_types = []
    for pt in article.findall(".//PublicationType"):
        if pt.text and pt.text.strip():
            pub_types.append(pt.text.strip())

    # MeSH keywords
    keywords = []
    mesh_headings = article.findall(".//MeshHeading")
    for mh in mesh_headings:
        descriptor = mh.find("DescriptorName")
        if descriptor is not None and descriptor.text:
            keywords.append(descriptor.text.strip())
    # Also check article keywords
    keyword_list = article_data.findall(".//Keyword")
    for kw in keyword_list:
        if kw.text and kw.text.strip():
            keywords.append(kw.text.strip())

    # Language
    language = ""
    lang_el = article_data.find(".//Language")
    if lang_el is not None and lang_el.text:
        language = lang_el.text.strip()

    # Other identifiers
    pmc_id = ""
    for other_id in article.findall(".//OtherID"):
        if other_id.get("Source") == "PMC":
            pmc_id = other_id.text or ""

    # Metadata completeness assessment
    completeness_parts = []
    if title:
        completeness_parts.append("title")
    if abstract:
        completeness_parts.append("abstract")
    if authors:
        completeness_parts.append("authors")
    if journal_title:
        completeness_parts.append("journal")
    if year:
        completeness_parts.append("year")
    if doi:
        completeness_parts.append("doi")
    if pub_types:
        completeness_parts.append("publication_type")
    if keywords:
        completeness_parts.append("keywords")
    completeness = ", ".join(completeness_parts) if completeness_parts else "minimal"

    return {
        "paper_id": f"pmid_{pmid}",
        "source": "pubmed",
        "title": title,
        "authors": authors,
        "authors_str": authors_str,
        "year": year,
        "journal": journal_title,
        "issn": issn,
        "abstract": abstract,
        "doi": doi,
        "pmid": pmid,
        "pmc_id": pmc_id,
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "publication_type": pub_types,
        "keywords": keywords,
        "language": language,
        "retrieved_at": datetime.now().isoformat(),
        "metadata_completeness": completeness,
    }
