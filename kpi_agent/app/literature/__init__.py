"""
Free literature search and evidence extraction module.

Provides:
- Multi-source search (OpenAlex, PubMed, Europe PMC, Crossref, Semantic Scholar)
- Cross-source deduplication
- Local caching
- Fulltext link discovery (Unpaywall)
- Hybrid ranking (BM25 + rules + RRF)
- Rule-based content extraction
- Evidence matrix generation
"""

from app.literature.schema import LiteratureResult, ExtractionResult, EvidenceMatrix
from app.literature.connectors.registry import ConnectorRegistry, search_all_sources
from app.literature.dedup import deduplicate_results
from app.literature.cache import LiteratureCache
from app.literature.fulltext import enrich_fulltext_links
from app.literature.ranking import hybrid_rerank
from app.literature.extraction import free_extract_evidence, batch_extract
from app.literature.matrix import generate_evidence_matrix
