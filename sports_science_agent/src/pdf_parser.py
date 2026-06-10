"""PDF parser — extract text and structure from PDF files."""

import re
from pathlib import Path
from typing import Optional

from src.config import RAW_PDFS, PARSED_DIR
from src.utils import logger


def extract_text_pymupdf(pdf_path: Path) -> str:
    """Extract text using PyMuPDF (fitz)."""
    try:
        import fitz
    except ImportError:
        logger.error("PyMuPDF not installed. Install with: pip install pymupdf")
        return ""

    try:
        doc = fitz.open(str(pdf_path))
        full_text = []
        for page in doc:
            text = page.get_text()
            if text:
                full_text.append(text)
        doc.close()
        return "\n\n".join(full_text)
    except Exception as e:
        logger.error(f"PyMuPDF extraction failed for {pdf_path}: {e}")


def extract_text_pdfplumber(pdf_path: Path) -> str:
    """Extract text using pdfplumber (fallback)."""
    try:
        import pdfplumber
    except ImportError:
        logger.error("pdfplumber not installed.")
        return ""

    full_text = []
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text.append(text)
        return "\n\n".join(full_text)
    except Exception as e:
        logger.error(f"pdfplumber extraction failed for {pdf_path}: {e}")
        return ""


def extract_text(pdf_path: Path) -> str:
    """Extract text from PDF, trying multiple backends."""
    text = extract_text_pymupdf(pdf_path)
    if not text:
        text = extract_text_pdfplumber(pdf_path)
    if not text:
        logger.warning(f"No text extracted from: {pdf_path}")
    return text


def extract_title(text: str) -> str:
    """Heuristic title extraction from first non-empty lines."""
    if not text:
        return ""
    lines = text.strip().split("\n")
    # Title is typically the first substantive line(s)
    title_lines = []
    for line in lines[:10]:
        clean = line.strip()
        if not clean:
            if title_lines:
                break
            continue
        # Skip lines with obvious metadata patterns
        if re.search(r"©|http|DOI|vol(?:ume)?\.?\s*\d|ISSN|PMID|PMCID", clean, re.IGNORECASE):
            if not title_lines:
                continue
            else:
                break
        if len(clean) > 5 and not clean.startswith(("Correspond", "Address", "Received", "Accepted", "Published")):
            title_lines.append(clean)
        if len(" ".join(title_lines)) > 250:
            break
    return " ".join(title_lines)[:500].strip()


def extract_abstract(text: str) -> str:
    """Extract abstract section."""
    if not text:
        return ""
    patterns = [
        r"(?:Abstract|ABSTRACT|A B S T R A C T)\s*\n(.*?)(?:\n\s*(?:Introduction|INTRODUCTION|Keywords|KEYWORDS|Background|BACKGROUND))",
        r"(?:Abstract|ABSTRACT|A B S T R A C T)[:\-]?\s*(.*?)(?:\n\s*(?:Introduction|INTRODUCTION|Keywords|KEYWORDS|Background))",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            abstract = match.group(1).strip()
            if len(abstract) > 50:
                return abstract[:5000]
    # Fallback: return first substantial paragraph
    paragraphs = text.split("\n\n")
    for para in paragraphs[:5]:
        clean = para.strip()
        if len(clean) > 100 and len(clean) < 5000:
            return clean
    return ""


def extract_keywords(text: str) -> list[str]:
    """Extract keywords from the text."""
    if not text:
        return []
    patterns = [
        r"(?:Keywords|KEYWORDS|Key words)[:\-]?\s*(.*?)(?:\n\s*(?:Introduction|Correspond|BACKGROUND|$))",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            kw_text = match.group(1).strip()
            kws = re.split(r"[;,]\s*", kw_text)
            return [k.strip() for k in kws if k.strip() and len(k.strip()) > 1][:20]
    return []


def extract_authors(text: str) -> str:
    """Extract author line."""
    if not text:
        return ""
    lines = text.strip().split("\n")
    # Authors are typically within the first 20 lines, after title
    title_found = False
    for i, line in enumerate(lines[:30]):
        clean = line.strip()
        if not clean:
            continue
        if not title_found:
            if len(clean) > 20:
                title_found = True
            continue
        # Author line typically contains commas, semicolons, superscript numbers
        if re.search(r"[A-Z][a-z]+\s+[A-Z]\.", clean):
            return clean[:500]
        if re.search(r"\d{1,2}(?:,\d{1,2})*\s*$", clean):
            return clean[:500]
    return ""


def extract_references_section(text: str) -> str:
    """Extract references section."""
    if not text:
        return ""
    patterns = [
        r"(?:References|REFERENCES|Bibliography|BIBLIOGRAPHY)\s*\n(.*?)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()[:20000]
    return ""


def parse_pdf(pdf_path: Path, save_parsed: bool = True) -> dict:
    """Full PDF parse pipeline."""
    text = extract_text(pdf_path)
    result = {
        "filename": pdf_path.name,
        "full_text": text,
        "title": extract_title(text),
        "abstract": extract_abstract(text),
        "authors_raw": extract_authors(text),
        "keywords": extract_keywords(text),
        "references_raw": extract_references_section(text),
        "text_length": len(text),
    }
    if save_parsed and text:
        parsed_path = PARSED_DIR / f"{pdf_path.stem}.txt"
        parsed_path.parent.mkdir(parents=True, exist_ok=True)
        parsed_path.write_text(text, encoding="utf-8")
    return result


def import_pdf(pdf_path: Path) -> dict:
    """Import a PDF file and return parsed metadata."""
    if not pdf_path.exists():
        return {"error": f"File not found: {pdf_path}"}
    # Copy to papers directory
    from src.config import PAPERS_DIR
    import shutil
    dest = PAPERS_DIR / pdf_path.name
    shutil.copy2(str(pdf_path), str(dest))
    parsed = parse_pdf(dest, save_parsed=True)
    logger.info(f"PDF imported: {pdf_path.name} -> {dest}")
    return parsed
