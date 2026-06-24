"""
Full enhanced literature→performance-model pipeline orchestrator.

End-to-end flow:
  1. Load literature data (from cache DB or session_state)
  2. Build LiteratureEvidenceChunks (sentence-level)
  3. Extract candidate terms (KeyBERT → YAKE → regex → noun phrases)
  4. Assign candidates to dimensions (hybrid 3-layer classification)
  5. Build proposed model nodes (merge similar terms, group by dimension)
  6. Return all results for manual review in Streamlit UI
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from app.literature_to_model.schemas import (
    PerformanceDimension,
    LiteratureEvidenceChunk,
    ExtractedCandidate,
    DimensionAssignment,
    ProposedModelNode,
)
from app.literature_to_model.text_cleaning import build_literature_chunks
from app.literature_to_model.keyword_extractor import extract_candidate_terms
from app.literature_to_model.assignment import (
    assign_candidates_to_dimensions,
    export_assignments_to_dataframe,
)
from app.literature_to_model.model_node_builder import (
    build_proposed_model_nodes,
    export_proposed_nodes_to_dataframe,
    apply_accepted_nodes_to_performance_model,
)
from app.literature_to_model.dimensions import load_default_performance_dimensions

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Complete results of the literature→model pipeline."""
    dimensions: list[PerformanceDimension] = field(default_factory=list)
    chunks: list[LiteratureEvidenceChunk] = field(default_factory=list)
    candidates: list[ExtractedCandidate] = field(default_factory=list)
    assignments: list[DimensionAssignment] = field(default_factory=list)
    proposed_nodes: list[ProposedModelNode] = field(default_factory=list)

    # Statistics
    total_literature: int = 0
    total_chunks: int = 0
    total_candidates: int = 0
    total_assignments: int = 0
    high_confidence_count: int = 0
    medium_confidence_count: int = 0
    low_confidence_count: int = 0
    proposed_node_count: int = 0

    # Errors/warnings
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_summary(self) -> dict:
        """Return a summary dict for display."""
        return {
            "文献数量": self.total_literature,
            "文本片段数": self.total_chunks,
            "候选术语数": self.total_candidates,
            "归档分配数": self.total_assignments,
            "高置信度 (≥0.75)": self.high_confidence_count,
            "中置信度 (0.5-0.75)": self.medium_confidence_count,
            "低置信度 (<0.5)": self.low_confidence_count,
            "建议节点数": self.proposed_node_count,
        }


def run_enhanced_pipeline(
    literature_data: list[dict],
    *,
    # Chunking options
    include_title: bool = True,
    include_abstract: bool = True,
    # Extraction options
    use_keybert: bool = True,
    use_yake: bool = True,
    use_regex: bool = True,
    use_noun_phrases: bool = True,
    min_extraction_score: float = 0.0,
    # Classification options
    auto_accept_threshold: float = 0.75,
    rule_threshold: float = 0.3,
    semantic_threshold: float = 0.35,
    tfidf_threshold: float = 0.15,
    # Node building options
    fuzzy_merge_threshold: float = 0.80,
    min_node_confidence: float = 0.0,
    # Applying to model
    existing_determinants: Optional[list[dict]] = None,
) -> PipelineResult:
    """Run the full enhanced literature→model pipeline.

    Args:
        literature_data: List of literature result dicts from cache DB or search.
        include_title: Include titles as chunks.
        include_abstract: Include abstract sentences as chunks.
        use_keybert: Enable KeyBERT extraction.
        use_yake: Enable YAKE extraction.
        use_regex: Enable regex+dictionary extraction.
        use_noun_phrases: Enable noun phrase extraction.
        min_extraction_score: Minimum raw score for extracted terms (0-1).
        auto_accept_threshold: Confidence threshold for auto-accept.
        rule_threshold: Minimum keyword score for rule classification.
        semantic_threshold: Minimum cosine similarity for semantic classification.
        tfidf_threshold: Minimum cosine similarity for TF-IDF classification.
        fuzzy_merge_threshold: rapidfuzz similarity for merging terms into nodes.
        min_node_confidence: Minimum confidence to propose a node.
        existing_determinants: Current performance model determinants.

    Returns:
        PipelineResult with all intermediate and final outputs.
    """
    result = PipelineResult()
    result.dimensions = load_default_performance_dimensions()

    if not literature_data:
        result.warnings.append("No literature data provided")
        return result

    result.total_literature = len(literature_data)
    logger.info("Starting enhanced pipeline with %d literature items", result.total_literature)

    # ── Step 1: Build chunks ──────────────────────────────────────────
    try:
        chunks = build_literature_chunks(
            literature_data,
            include_title=include_title,
            include_abstract=include_abstract,
        )
        result.chunks = chunks
        result.total_chunks = len(chunks)
        logger.info("Step 1: Built %d chunks", result.total_chunks)
    except Exception as e:
        result.errors.append(f"Chunk building failed: {e}")
        logger.exception("Chunk building failed")
        return result

    if not chunks:
        result.warnings.append("No text chunks generated from literature data")
        return result

    # ── Step 2: Extract candidate terms ───────────────────────────────
    try:
        candidates = extract_candidate_terms(
            chunks,
            use_keybert=use_keybert,
            use_yake=use_yake,
            use_regex=use_regex,
            use_noun_phrases=use_noun_phrases,
            min_score=min_extraction_score,
        )
        result.candidates = candidates
        result.total_candidates = len(candidates)
        logger.info("Step 2: Extracted %d candidate terms", result.total_candidates)
    except Exception as e:
        result.errors.append(f"Candidate extraction failed: {e}")
        logger.exception("Candidate extraction failed")
        return result

    if not candidates:
        result.warnings.append("No candidate terms extracted")
        return result

    # ── Step 3: Assign candidates to dimensions ───────────────────────
    try:
        assignments = assign_candidates_to_dimensions(
            candidates,
            auto_accept_threshold=auto_accept_threshold,
            rule_threshold=rule_threshold,
            semantic_threshold=semantic_threshold,
            tfidf_threshold=tfidf_threshold,
        )
        result.assignments = assignments
        result.total_assignments = len(assignments)
        result.high_confidence_count = sum(1 for a in assignments if a.confidence_score >= 0.75)
        result.medium_confidence_count = sum(
            1 for a in assignments if 0.5 <= a.confidence_score < 0.75
        )
        result.low_confidence_count = sum(1 for a in assignments if a.confidence_score < 0.5)
        logger.info(
            "Step 3: %d assignments (%d high, %d medium, %d low)",
            result.total_assignments,
            result.high_confidence_count,
            result.medium_confidence_count,
            result.low_confidence_count,
        )
    except Exception as e:
        result.errors.append(f"Classification failed: {e}")
        logger.exception("Classification failed")
        return result

    # ── Step 4: Build proposed model nodes ────────────────────────────
    try:
        nodes = build_proposed_model_nodes(
            assignments,
            fuzzy_threshold=fuzzy_merge_threshold,
            min_confidence=min_node_confidence,
            include_review_only=True,
        )
        result.proposed_nodes = nodes
        result.proposed_node_count = len(nodes)
        logger.info("Step 4: Built %d proposed model nodes", result.proposed_node_count)
    except Exception as e:
        result.errors.append(f"Node building failed: {e}")
        logger.exception("Node building failed")

    # ── Step 5: Apply accepted nodes (if existing determinants provided) ──
    if existing_determinants is not None:
        try:
            updated = apply_accepted_nodes_to_performance_model(
                result.proposed_nodes,
                existing_determinants,
            )
            logger.info("Step 5: Performance model updated (%d total)", len(updated))
        except Exception as e:
            result.errors.append(f"Applying to model failed: {e}")
            logger.exception("Applying to model failed")

    logger.info("Pipeline complete: %s", result.to_summary())
    return result


def get_assignments_df(result: PipelineResult):
    """Convenience: get assignments as a DataFrame."""
    return export_assignments_to_dataframe(result.assignments)


def get_nodes_df(result: PipelineResult):
    """Convenience: get proposed nodes as a DataFrame."""
    return export_proposed_nodes_to_dataframe(result.proposed_nodes)
