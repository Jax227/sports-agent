"""CrossRef client — enrich paper metadata with journal info and additional fields."""

import time
from datetime import datetime
from typing import Optional

import requests

from src.config import CROSSREF_MAILTO
from src.utils import normalize_doi, logger


CROSSREF_BASE = "https://api.crossref.org/works"

# Module-level error state for upstream consumers to inspect
LAST_ERROR = None  # {"type": "connection"|"http"|"parse", "message": str, "detail": str}

# Bypass Windows system proxy (trust_env=False) to avoid SSL interception
_session = requests.Session()
_session.trust_env = False


def get_last_error() -> Optional[dict]:
    """Return the last CrossRef error, or None if the last operation succeeded."""
    return LAST_ERROR


def lookup_doi_crossref(doi: str) -> Optional[dict]:
    """Fetch full metadata for a DOI from CrossRef, including journal metadata."""
    global LAST_ERROR
    doi = normalize_doi(doi)
    if not doi:
        return None

    headers = {}
    if CROSSREF_MAILTO:
        headers["User-Agent"] = f"SportsScienceAgent/2.0 (mailto:{CROSSREF_MAILTO})"

    try:
        url = f"{CROSSREF_BASE}/{doi}"
        resp = _session.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            logger.warning(f"CrossRef HTTP {resp.status_code} for DOI {doi}")
            return None

        data = resp.json()
        msg = data.get("message", {})

        # Authors
        authors_list = msg.get("author", [])
        authors = []
        for a in authors_list:
            fore = a.get("given", "")
            last = a.get("family", "")
            if fore or last:
                authors.append(f"{fore} {last}".strip())
        authors_str = "; ".join(authors)

        # Date
        published = msg.get("published-print", {}) or msg.get("published-online", {}) or msg.get("issued", {}) or {}
        date_parts = published.get("date-parts", [[None]])[0]
        year = str(date_parts[0]) if date_parts and date_parts[0] else ""

        # Journal / container
        container = msg.get("container-title", [""])
        journal_name = container[0] if container else ""

        # Publisher
        publisher = msg.get("publisher", "")

        # ISSN
        issn_list = msg.get("ISSN", [])
        issn = issn_list[0] if issn_list else ""

        # Type
        crossref_type = msg.get("type", "")

        # Subjects
        subject = msg.get("subject", [])

        # References count
        references_count = msg.get("references-count", 0) or 0
        is_referenced_by_count = msg.get("is-referenced-by-count", 0) or 0

        # License
        license_info = ""
        license_list = msg.get("license", [])
        if license_list:
            license_info = license_list[0].get("URL", "")

        # Funding
        funders = []
        for funder in msg.get("funder", []):
            funders.append(funder.get("name", ""))
        funders_str = "; ".join(funders)

        return {
            "title": (msg.get("title") or [""])[0],
            "authors": authors,
            "authors_str": authors_str,
            "year": year,
            "journal": journal_name,
            "issn": issn,
            "publisher": publisher,
            "doi": msg.get("DOI", doi),
            "abstract": msg.get("abstract", ""),
            "volume": msg.get("volume", ""),
            "issue": msg.get("issue", ""),
            "pages": msg.get("page", ""),
            "publication_type": crossref_type,
            "keywords": subject if isinstance(subject, list) else [subject] if subject else [],
            "references_count": references_count,
            "citation_count": is_referenced_by_count,
            "license": license_info,
            "funding": funders_str,
            "source": "crossref",
            "retrieved_at": datetime.now().isoformat(),
            "metadata_completeness": _assess_completeness(msg),
        }
    except requests.exceptions.SSLError as e:
        LAST_ERROR = {"type": "connection", "message": "CrossRef 连接失败：SSL证书验证错误，可能是网络代理拦截了 HTTPS 请求", "detail": str(e)[:300]}
        logger.error(f"CrossRef SSL error for DOI {doi}: {e}")
        return None
    except requests.exceptions.ConnectionError as e:
        LAST_ERROR = {"type": "connection", "message": "CrossRef 连接失败：无法连接到 api.crossref.org，请检查网络或代理设置", "detail": str(e)[:300]}
        logger.error(f"CrossRef connection error for DOI {doi}: {e}")
        return None
    except requests.exceptions.Timeout as e:
        LAST_ERROR = {"type": "connection", "message": "CrossRef 连接超时：请求超过15秒未响应，请检查网络或稍后重试", "detail": str(e)[:300]}
        logger.error(f"CrossRef timeout for DOI {doi}: {e}")
        return None
    except Exception as e:
        LAST_ERROR = {"type": "unknown", "message": f"CrossRef 检索异常: {type(e).__name__}", "detail": str(e)[:300]}
        logger.error(f"CrossRef error for DOI {doi}: {type(e).__name__}: {e}")
        return None


def _assess_completeness(msg: dict) -> str:
    """Assess metadata completeness from CrossRef message."""
    fields = []
    if msg.get("title"):
        fields.append("title")
    if msg.get("abstract"):
        fields.append("abstract")
    if msg.get("author"):
        fields.append("authors")
    if msg.get("container-title"):
        fields.append("journal")
    if msg.get("published-print") or msg.get("issued"):
        fields.append("date")
    if msg.get("DOI"):
        fields.append("doi")
    if msg.get("references-count"):
        fields.append("references")
    return ", ".join(fields) if fields else "minimal"


def search_crossref(
    query: str,
    max_results: int = 20,
    filter_type: str = "",
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
) -> list[dict]:
    """Search CrossRef for papers by keyword query."""
    global LAST_ERROR
    if not query:
        return []

    headers = {}
    if CROSSREF_MAILTO:
        headers["User-Agent"] = f"SportsScienceAgent/2.0 (mailto:{CROSSREF_MAILTO})"

    params = {
        "query": query,
        "rows": str(min(max_results, 100)),
        "sort": "relevance",
    }

    # Filter by type if specified
    if filter_type:
        params["filter"] = f"type:{filter_type}"

    # Add year filter
    filter_parts = []
    if year_from:
        filter_parts.append(f"from-pub-date:{year_from}")
    if year_to:
        filter_parts.append(f"until-pub-date:{year_to}")
    if filter_parts:
        existing = params.get("filter", "")
        params["filter"] = f"{existing},{','.join(filter_parts)}" if existing else ",".join(filter_parts)

    try:
        resp = _session.get(CROSSREF_BASE, params=params, headers=headers, timeout=30)
        if resp.status_code != 200:
            LAST_ERROR = {"type": "http", "message": f"CrossRef 服务器返回 HTTP {resp.status_code}，请稍后重试", "detail": resp.text[:200] if resp.text else ""}
            logger.warning(f"CrossRef search HTTP {resp.status_code}")
            return []

        data = resp.json()
        items = data.get("message", {}).get("items", [])

        results = []
        for item in items:
            paper = _parse_crossref_item(item)
            if paper:
                results.append(paper)

        if not results:
            LAST_ERROR = None  # Valid response, just no matches
        else:
            LAST_ERROR = None

        logger.info(f"CrossRef search: {len(results)} papers for '{query[:60]}...'")
        return results[:max_results]

    except requests.exceptions.SSLError as e:
        LAST_ERROR = {"type": "connection", "message": "CrossRef 连接失败：SSL证书验证错误，可能是网络代理拦截了 HTTPS 请求", "detail": str(e)[:300]}
        logger.error(f"CrossRef SSL error: {e}")
        return []
    except requests.exceptions.ConnectionError as e:
        LAST_ERROR = {"type": "connection", "message": "CrossRef 连接失败：无法连接到 api.crossref.org，请检查网络或代理设置", "detail": str(e)[:300]}
        logger.error(f"CrossRef connection error: {e}")
        return []
    except requests.exceptions.Timeout as e:
        LAST_ERROR = {"type": "connection", "message": "CrossRef 连接超时：请求超过30秒未响应，请检查网络或稍后重试", "detail": str(e)[:300]}
        logger.error(f"CrossRef timeout: {e}")
        return []
    except Exception as e:
        LAST_ERROR = {"type": "unknown", "message": f"CrossRef 检索异常: {type(e).__name__}", "detail": str(e)[:300]}
        logger.error(f"CrossRef search error: {type(e).__name__}: {e}")
        return []


def _parse_crossref_item(item: dict) -> Optional[dict]:
    """Parse a single CrossRef search result item."""
    try:
        authors_list = item.get("author", [])
        authors = []
        for a in authors_list:
            fore = a.get("given", "")
            last = a.get("family", "")
            if fore or last:
                authors.append(f"{fore} {last}".strip())

        published = item.get("published-print", {}) or item.get("published-online", {}) or item.get("issued", {}) or {}
        date_parts = published.get("date-parts", [[None]])[0]
        year = str(date_parts[0]) if date_parts and date_parts[0] else ""

        container = item.get("container-title", [""])
        journal = container[0] if container else ""

        doi = item.get("DOI", "")
        issn_list = item.get("ISSN", [])
        issn = issn_list[0] if issn_list else ""

        return {
            "paper_id": f"doi_{doi.replace('/', '_')}" if doi else f"crossref_{hash(item.get('title', [''])[0])}",
            "source": "crossref",
            "title": (item.get("title") or [""])[0],
            "authors": authors,
            "authors_str": "; ".join(authors),
            "year": year,
            "journal": journal,
            "issn": issn,
            "abstract": item.get("abstract", ""),
            "doi": doi,
            "pmid": "",
            "url": f"https://doi.org/{doi}" if doi else "",
            "publication_type": item.get("type", ""),
            "keywords": item.get("subject", []),
            "language": "",
            "retrieved_at": datetime.now().isoformat(),
            "metadata_completeness": _assess_item_completeness(item),
            "publisher": item.get("publisher", ""),
            "citation_count": item.get("is-referenced-by-count", 0) or 0,
            "references_count": item.get("references-count", 0) or 0,
        }
    except Exception as e:
        logger.error(f"CrossRef item parse error: {e}")
        return None


def _assess_item_completeness(item: dict) -> str:
    """Assess metadata completeness for a CrossRef search item."""
    fields = []
    if item.get("title"):
        fields.append("title")
    if item.get("abstract"):
        fields.append("abstract")
    if item.get("author"):
        fields.append("authors")
    if item.get("container-title"):
        fields.append("journal")
    if item.get("DOI"):
        fields.append("doi")
    return ", ".join(fields) if fields else "minimal"


def enrich_with_crossref(paper: dict) -> dict:
    """Enrich an existing paper dict with CrossRef metadata by DOI."""
    doi = paper.get("doi", "")
    if not doi:
        return paper

    crossref_data = lookup_doi_crossref(doi)
    if not crossref_data:
        return paper

    # Fill in missing fields (don't overwrite existing data)
    for key in ["abstract", "publisher", "issn", "citation_count", "references_count", "license", "funding"]:
        if not paper.get(key) and crossref_data.get(key):
            paper[key] = crossref_data[key]

    # If journal name is missing or short, use CrossRef's
    if not paper.get("journal") or len(paper.get("journal", "")) < 3:
        if crossref_data.get("journal"):
            paper["journal"] = crossref_data["journal"]

    return paper
