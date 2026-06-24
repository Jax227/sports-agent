"""
Text preprocessing, sentence splitting, and literature chunk building.

Reads literature from the cache database or session_state and produces
LiteratureEvidenceChunk objects for downstream extraction and classification.
"""

import logging
import re
from typing import Optional

from app.literature_to_model.schemas import LiteratureEvidenceChunk

logger = logging.getLogger(__name__)

# Try importing nltk for sentence tokenization (better than regex)
_nltk_available = None


def _check_nltk() -> bool:
    global _nltk_available
    if _nltk_available is None:
        try:
            import nltk
            nltk.data.find("tokenizers/punkt")
            _nltk_available = True
        except (ImportError, LookupError):
            try:
                import nltk
                nltk.download("punkt", quiet=True)
                _nltk_available = True
            except Exception:
                _nltk_available = False
    return _nltk_available


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences. Uses nltk if available, otherwise regex."""
    if not text or not text.strip():
        return []

    if _check_nltk():
        import nltk
        return nltk.sent_tokenize(text)

    # Fallback: regex-based sentence splitting
    return _regex_sentence_split(text)


def _regex_sentence_split(text: str) -> list[str]:
    """Simple regex sentence splitter as fallback."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if len(s.strip()) > 10]


def build_literature_chunks(
    literature_data: list[dict],
    include_title: bool = True,
    include_abstract: bool = True,
    min_chunk_length: int = 10,
) -> list[LiteratureEvidenceChunk]:
    """Build LiteratureEvidenceChunk objects from literature search results.

    Args:
        literature_data: List of literature result dicts. Each dict should have
            keys: id, title, abstract, year, doi, source_database, authors, etc.
        include_title: Whether to create chunks from the title.
        include_abstract: Whether to create chunks from the abstract.
        min_chunk_length: Minimum character length for a sentence to be included.

    Returns:
        List of LiteratureEvidenceChunk objects, one per sentence.
    """
    chunks: list[LiteratureEvidenceChunk] = []

    for lit in literature_data:
        lit_id = lit.get("id", 0)
        title = lit.get("title", "") or ""
        abstract = lit.get("abstract", "") or ""
        year = lit.get("year")
        doi = lit.get("doi")
        source_database = lit.get("source_database", "") or ""
        # Authors may be a list or a JSON string
        authors_raw = lit.get("authors", "")
        if isinstance(authors_raw, list):
            authors = ", ".join(str(a) for a in authors_raw[:5])
        elif isinstance(authors_raw, str):
            authors = authors_raw
        else:
            authors = ""

        # Chunk from title
        if include_title and title.strip():
            chunks.append(LiteratureEvidenceChunk(
                literature_id=lit_id,
                chunk_text=title.strip(),
                chunk_type="title",
                sentence_index=0,
                title=title,
                year=year,
                doi=doi,
                source_database=source_database,
                authors=authors,
            ))

        # Chunks from abstract sentences
        if include_abstract and abstract.strip():
            sentences = _split_sentences(abstract)
            for idx, sent in enumerate(sentences):
                if len(sent) >= min_chunk_length:
                    chunks.append(LiteratureEvidenceChunk(
                        literature_id=lit_id,
                        chunk_text=sent.strip(),
                        chunk_type="abstract",
                        sentence_index=idx,
                        title=title,
                        year=year,
                        doi=doi,
                        source_database=source_database,
                        authors=authors,
                    ))

    logger.info("Built %d chunks from %d literature items", len(chunks), len(literature_data))
    return chunks


def clean_text(text: str) -> str:
    """Minimal text cleaning: normalize whitespace, strip control chars."""
    if not text:
        return ""
    # Remove control characters except newlines and tabs
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def build_chunks_from_session_state(session_data: list[dict]) -> list[LiteratureEvidenceChunk]:
    """Build chunks from Streamlit session_state literature results.

    This is a convenience wrapper that handles the typical session_state format
    where literature results may be stored as raw dicts.
    """
    return build_literature_chunks(session_data)


def get_chunks_by_type(
    chunks: list[LiteratureEvidenceChunk],
    chunk_type: str = "abstract",
) -> list[LiteratureEvidenceChunk]:
    """Filter chunks by type (title, abstract, fulltext, etc.)."""
    return [c for c in chunks if c.chunk_type == chunk_type]


def get_unique_literature_ids(chunks: list[LiteratureEvidenceChunk]) -> list[int]:
    """Get sorted unique literature IDs from a chunk list."""
    return sorted({c.literature_id for c in chunks})
