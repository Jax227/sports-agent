"""Literature importer — unified interface for importing papers via multiple methods."""

import shutil
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional

from src.config import PAPERS_DIR
from src.database import add_paper
from src.pdf_parser import parse_pdf, import_pdf
from src.metadata_extractor import lookup_by_identifier, lookup_doi_crossref, lookup_pmid_pubmed
from src.screening import screen_paper
from src.quality_assessment import full_quality_assessment
from src.vector_store import add_paper_to_vector_store
from src.utils import logger, normalize_doi, normalize_pmid


def import_by_doi(doi: str) -> Optional[dict]:
    """Import a paper by DOI."""
    doi = normalize_doi(doi)
    if not doi:
        return {"error": "Invalid DOI format", "success": False}

    meta = lookup_by_identifier(doi)
    if not meta:
        return {"error": f"Could not fetch metadata for DOI: {doi}", "success": False}

    return _process_and_store(meta)


def import_by_pmid(pmid: str) -> Optional[dict]:
    """Import a paper by PMID."""
    pmid = normalize_pmid(pmid)
    if not pmid:
        return {"error": "Invalid PMID format", "success": False}

    meta = lookup_pmid_pubmed(pmid)
    if not meta:
        return {"error": f"Could not fetch metadata for PMID: {pmid}", "success": False}

    return _process_and_store(meta)


def import_by_pdf(pdf_file) -> Optional[dict]:
    """Import a paper from an uploaded PDF file."""
    PAPERS_DIR.mkdir(parents=True, exist_ok=True)

    # Save uploaded file
    if hasattr(pdf_file, "name"):
        filename = pdf_file.name
        dest = PAPERS_DIR / filename
        with open(dest, "wb") as f:
            f.write(pdf_file.getbuffer() if hasattr(pdf_file, "getbuffer") else pdf_file.read())
    elif isinstance(pdf_file, (str, Path)):
        dest = Path(pdf_file)
        if not dest.exists():
            return {"error": f"PDF file not found: {pdf_file}", "success": False}
    else:
        return {"error": "Invalid PDF file input", "success": False}

    # Parse the PDF
    parsed = parse_pdf(dest, save_parsed=True)

    # Build paper metadata from parsed content
    meta = {
        "title": parsed.get("title", ""),
        "authors": parsed.get("authors_raw", ""),
        "year": _guess_year_from_text(parsed.get("full_text", "")),
        "abstract": parsed.get("abstract", ""),
        "keywords": parsed.get("keywords", []),
        "journal": _guess_journal_from_text(parsed.get("full_text", "")),
        "doi": _find_doi_in_text(parsed.get("full_text", "")),
        "full_text": parsed.get("full_text", ""),
        "source": "pdf_upload",
        "pdf_filename": dest.name,
    }

    return _process_and_store(meta)


def import_manually(paper_info: dict) -> Optional[dict]:
    """Import a paper from manually entered metadata."""
    required_fields = ["title", "authors", "year"]
    for field in required_fields:
        if not paper_info.get(field):
            return {"error": f"Missing required field: {field}", "success": False}

    meta = {
        "title": paper_info.get("title", ""),
        "authors": paper_info.get("authors", ""),
        "year": str(paper_info.get("year", "")),
        "journal": paper_info.get("journal", ""),
        "doi": normalize_doi(paper_info.get("doi", "")),
        "pmid": normalize_pmid(paper_info.get("pmid", "")),
        "abstract": paper_info.get("abstract", ""),
        "keywords": paper_info.get("keywords", []),
        "study_type": paper_info.get("study_type", ""),
        "population": paper_info.get("population", ""),
        "sample_size": paper_info.get("sample_size", ""),
        "intervention_or_exposure": paper_info.get("intervention_or_exposure", ""),
        "comparator": paper_info.get("comparator", ""),
        "outcomes": paper_info.get("outcomes", ""),
        "main_findings": paper_info.get("main_findings", ""),
        "effect_size": paper_info.get("effect_size", ""),
        "limitations": paper_info.get("limitations", ""),
        "notes": paper_info.get("notes", ""),
        "source": "manual_entry",
    }

    return _process_and_store(meta)


def import_from_text(raw_text: str) -> Optional[dict]:
    """Try to parse and import paper from pasted text (BibTeX, RIS, or free text)."""
    raw_text = raw_text.strip()

    # Try BibTeX
    if raw_text.startswith("@") and "{" in raw_text:
        return _import_from_bibtex(raw_text)

    # Try RIS
    if "TY  -" in raw_text or "TY -" in raw_text:
        return _import_from_ris(raw_text)

    # Fallback: try to extract structured info from free text
    return _import_from_free_text(raw_text)


def _import_from_bibtex(text: str) -> Optional[dict]:
    """Parse BibTeX entry."""
    meta = {"source": "bibtex_import"}

    # Extract type
    type_match = __import__("re").match(r"@(\w+)\s*\{", text)
    if type_match:
        btype = type_match.group(1).lower()
        type_map = {"article": "other", "inproceedings": "conference_abstract",
                    "book": "other", "phdthesis": "other", "mastersthesis": "other"}
        meta["study_type"] = type_map.get(btype, "other")

    # Extract fields
    import re
    fields = {
        "title": r"title\s*=\s*\{([^}]+)\}",
        "author": r"author\s*=\s*\{([^}]+)\}",
        "journal": r"journal\s*=\s*\{([^}]+)\}",
        "year": r"year\s*=\s*\{?(\d+)\}?",
        "doi": r"doi\s*=\s*\{?([^,}]+)\}?",
        "abstract": r"abstract\s*=\s*\{([^}]+)\}",
        "volume": r"volume\s*=\s*\{?(\d+)\}?",
        "pages": r"pages\s*=\s*\{([^}]+)\}",
    }
    for key, pattern in fields.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            meta[key] = match.group(1).strip()

    if meta.get("title") and meta.get("author"):
        meta["authors"] = meta.pop("author", "")
        return _process_and_store(meta)

    return {"error": "Could not parse BibTeX entry", "success": False}


def _import_from_ris(text: str) -> Optional[dict]:
    """Parse RIS format entry."""
    import re
    meta = {"source": "ris_import"}

    field_map = {
        "TI": "title", "T1": "title",
        "AU": "authors", "A1": "authors",
        "PY": "year", "Y1": "year",
        "JO": "journal", "JF": "journal", "T2": "journal",
        "AB": "abstract", "N2": "abstract",
        "DO": "doi",
        "VL": "volume",
        "IS": "issue",
        "SP": "pages",
        "KW": "keywords",
    }

    authors = []
    for line in text.split("\n"):
        line = line.strip()
        if "  - " in line:
            tag, value = line.split("  - ", 1)
            tag = tag.strip()
            value = value.strip()
            if tag in field_map:
                key = field_map[tag]
                if key == "authors":
                    authors.append(value)
                elif key == "keywords":
                    existing = meta.get("keywords", [])
                    if isinstance(existing, str):
                        existing = [existing]
                    existing.append(value)
                    meta["keywords"] = existing
                else:
                    meta[key] = value
            elif tag == "C1":  # Repeat author field
                pass

    if authors and "authors" not in meta:
        meta["authors"] = "; ".join(authors)

    if meta.get("title") and meta.get("authors"):
        return _process_and_store(meta)

    return {"error": "Could not parse RIS entry", "success": False}


def _import_from_free_text(text: str) -> Optional[dict]:
    """Attempt to extract paper info from free text."""
    import re

    # Try to find DOI
    doi_pattern = r"(?:doi:?\s*|https?://doi\.org/)(10\.\d{4,}/[^\s,.;]+)"
    doi_match = re.search(doi_pattern, text, re.IGNORECASE)
    if doi_match:
        return import_by_doi(doi_match.group(1))

    # Try to find PMID
    pmid_pattern = r"(?:PMID|pmid):?\s*(\d+)"
    pmid_match = re.search(pmid_pattern, text)
    if pmid_match:
        return import_by_pmid(pmid_match.group(1))

    return {"error": "Could not identify DOI, PMID, BibTeX, or RIS in the pasted text", "success": False}


def _process_and_store(meta: dict) -> dict:
    """Run screening, quality assessment, and store the paper."""
    if "error" in meta:
        return meta

    # Screen
    screening = screen_paper(meta)
    meta.update(screening)

    # Quality assessment
    meta = full_quality_assessment(meta)

    # Set defaults
    meta.setdefault("sample_size", "")
    meta.setdefault("population", "")
    meta.setdefault("intervention_or_exposure", "")
    meta.setdefault("comparator", "")
    meta.setdefault("outcomes", "")
    meta.setdefault("main_findings", "")
    meta.setdefault("effect_size", "")
    meta.setdefault("limitations", "")
    meta.setdefault("conflict_of_interest", "")
    meta.setdefault("notes", "")

    # Save to database
    paper_id = add_paper(meta)

    # Add to vector store
    meta["id"] = paper_id
    add_paper_to_vector_store(meta)

    return {
        "success": True,
        "paper_id": paper_id,
        "title": meta.get("title", ""),
        "screening": {
            "decision": screening.get("inclusion_decision"),
            "reason": screening.get("reason"),
            "study_type": screening.get("study_type"),
            "evidence_level": screening.get("evidence_level"),
            "quality_score": meta.get("quality_score"),
            "relevance_score": screening.get("relevance_score"),
            "research_domain": screening.get("research_domain"),
        },
    }


def _guess_year_from_text(text: str) -> str:
    """Heuristically find publication year from text."""
    import re
    # Look for common year patterns in the first portion of text
    head = text[:5000]
    # Copyright year
    match = re.search(r"©\s*(\d{4})", head) or \
            re.search(r"(?:Published|Received|Accepted)[:\s]+[A-Z][a-z]+\s+\d{1,2},?\s+(\d{4})", head) or \
            re.search(r"(?:19|20)\d{2}", head)
    return match.group(1) if match else ""


def _guess_journal_from_text(text: str) -> str:
    """Heuristically find journal name from text."""
    import re
    # Journal names often appear in headers or DOI prefixes
    head = text[:3000]
    # Try DOI journal prefix
    doi_match = re.search(r"10\.\d{4,}/([^/]+)/", head)
    if doi_match:
        return doi_match.group(1).replace("-", " ").title()
    # Try common journal header patterns
    journal_patterns = [
        r"(?:Journal of|European Journal|American Journal|British Journal|International Journal|Scandinavian Journal)\s+[\w\s]+",
    ]
    for pat in journal_patterns:
        match = re.search(pat, head, re.IGNORECASE)
        if match:
            return match.group(0).strip()
    return ""


def _find_doi_in_text(text: str) -> str:
    """Extract DOI from text."""
    import re
    match = re.search(r"(?:doi:?\s*|https?://doi\.org/)?(10\.\d{4,}/[^\s,.;]+)", text[:5000])
    return match.group(1) if match else ""
