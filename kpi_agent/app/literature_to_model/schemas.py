"""
Pydantic-style dataclasses for the literature→model pipeline.

All structures designed for Streamlit session_state serialization
and manual human review before writing to the formal performance model.
"""

from dataclasses import dataclass, field
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════
# 1. PerformanceDimension
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class PerformanceDimension:
    """A category of performance determinants (e.g. physiological, technical)."""
    id: str                                    # key: "physiological_requirements"
    name_cn: str                               # "生理要求"
    name_en: str                               # "Physiological Requirements"
    description: str = ""
    aliases: list[str] = field(default_factory=list)   # English alias terms
    examples: list[str] = field(default_factory=list)   # Example determinants
    parent_id: Optional[str] = None            # for hierarchical dimensions

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name_cn": self.name_cn,
            "name_en": self.name_en,
            "description": self.description,
            "aliases": self.aliases,
            "examples": self.examples,
            "parent_id": self.parent_id,
        }


# ═══════════════════════════════════════════════════════════════════════
# 2. LiteratureEvidenceChunk
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class LiteratureEvidenceChunk:
    """A text segment from a literature document, annotated with source info."""
    literature_id: int
    chunk_text: str
    chunk_type: str = "sentence"               # title | abstract | fulltext | sentence | keyword
    sentence_index: int = 0
    title: str = ""
    year: Optional[int] = None
    doi: Optional[str] = None
    source_database: str = ""
    authors: str = ""

    def to_dict(self) -> dict:
        return {
            "literature_id": self.literature_id,
            "chunk_text": self.chunk_text,
            "chunk_type": self.chunk_type,
            "sentence_index": self.sentence_index,
            "title": self.title,
            "year": self.year,
            "doi": self.doi,
            "source_database": self.source_database,
            "authors": self.authors,
        }


# ═══════════════════════════════════════════════════════════════════════
# 3. ExtractedCandidate
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class ExtractedCandidate:
    """A candidate performance term extracted from literature text."""
    candidate_term: str                        # raw extracted term
    normalized_term: str                       # canonical normalized form
    source_literature_id: int
    source_title: str = ""
    source_year: Optional[int] = None
    evidence_sentence: str = ""                # the sentence containing this term
    extraction_method: str = "unknown"         # keybert | regex | noun_phrase | dictionary
    raw_score: float = 0.0                     # method-specific score (0-1)
    chunk_index: int = 0

    def to_dict(self) -> dict:
        return {
            "candidate_term": self.candidate_term,
            "normalized_term": self.normalized_term,
            "source_literature_id": self.source_literature_id,
            "source_title": self.source_title,
            "source_year": self.source_year,
            "evidence_sentence": self.evidence_sentence,
            "extraction_method": self.extraction_method,
            "raw_score": self.raw_score,
            "chunk_index": self.chunk_index,
        }


# ═══════════════════════════════════════════════════════════════════════
# 4. DimensionAssignment
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class DimensionAssignment:
    """Result of assigning a candidate term to a performance dimension."""
    candidate_term: str
    normalized_term: str
    assigned_dimension: str                    # dimension key e.g. "physiological_requirements"
    assigned_dimension_name_cn: str = ""
    confidence_score: float = 0.0              # 0-1 combined score
    semantic_score: float = 0.0
    rule_score: float = 0.0
    keyword_score: float = 0.0
    evidence_quality_score: float = 0.0
    match_method: str = "unknown"              # semantic | rule | tfidf | fallback
    reason: str = ""
    evidence_sentence: str = ""
    source_literature_id: int = 0
    source_title: str = ""
    source_year: Optional[int] = None
    doi: Optional[str] = None
    needs_review: bool = True                  # True if confidence < 0.75

    def to_dict(self) -> dict:
        return {
            "candidate_term": self.candidate_term,
            "normalized_term": self.normalized_term,
            "assigned_dimension": self.assigned_dimension,
            "assigned_dimension_name_cn": self.assigned_dimension_name_cn,
            "confidence_score": self.confidence_score,
            "semantic_score": self.semantic_score,
            "rule_score": self.rule_score,
            "keyword_score": self.keyword_score,
            "evidence_quality_score": self.evidence_quality_score,
            "match_method": self.match_method,
            "reason": self.reason,
            "evidence_sentence": self.evidence_sentence,
            "source_literature_id": self.source_literature_id,
            "source_title": self.source_title,
            "source_year": self.source_year,
            "doi": self.doi,
            "needs_review": self.needs_review,
        }

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence_score >= 0.75

    @property
    def is_low_confidence(self) -> bool:
        return self.confidence_score < 0.5


# ═══════════════════════════════════════════════════════════════════════
# 5. ProposedModelNode
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class ProposedModelNode:
    """A suggested performance model node built from merged assignments."""
    node_name: str                             # e.g. "有氧能力"
    node_name_en: str = ""                     # e.g. "Aerobic Capacity"
    parent_dimension: str = ""                 # dimension key
    parent_dimension_name_cn: str = ""
    description: str = ""
    evidence_items: list[dict] = field(default_factory=list)  # DimensionAssignment dicts
    confidence_score: float = 0.0
    source_count: int = 0                      # number of unique literature sources
    suggested_as: str = "determinant"          # determinant | sub_determinant | kpi_candidate
    status: str = "proposed"                   # proposed | accepted | rejected
    aliases: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "node_name": self.node_name,
            "node_name_en": self.node_name_en,
            "parent_dimension": self.parent_dimension,
            "parent_dimension_name_cn": self.parent_dimension_name_cn,
            "description": self.description,
            "evidence_items": self.evidence_items,
            "confidence_score": self.confidence_score,
            "source_count": self.source_count,
            "suggested_as": self.suggested_as,
            "status": self.status,
            "aliases": self.aliases,
        }
