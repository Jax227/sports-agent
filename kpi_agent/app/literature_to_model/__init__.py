"""
Literature → Performance Model enhanced pipeline.

Hybrid 3-layer classification:
  A. Rule dictionary matching (sports science keywords)
  B. Semantic similarity (sentence-transformers → TF-IDF fallback)
  C. Evidence sentence anchoring

All methods are free and local. No commercial LLM API calls.
Every external dependency has an automatic fallback.

Public API:
  - run_enhanced_pipeline()       Full end-to-end pipeline
  - build_literature_chunks()     Build text chunks from literature dicts
  - extract_candidate_terms()     Extract candidate terms from chunks
  - assign_candidates_to_dimensions()  Hybrid 3-layer classification
  - build_proposed_model_nodes()  Build proposed nodes from assignments
  - load_default_performance_dimensions()  8 default dimensions
  - export_assignments_to_dataframe()  Export assignments as DataFrame
  - export_proposed_nodes_to_dataframe() Export nodes as DataFrame
  - apply_accepted_nodes_to_performance_model()  Write accepted to model
"""

from app.literature_to_model.schemas import (
    PerformanceDimension,
    LiteratureEvidenceChunk,
    ExtractedCandidate,
    DimensionAssignment,
    ProposedModelNode,
)

from app.literature_to_model.dimensions import (
    load_default_performance_dimensions,
    build_domain_dictionary,
    build_inverted_index,
)

from app.literature_to_model.text_cleaning import (
    build_literature_chunks,
    clean_text,
)

from app.literature_to_model.keyword_extractor import (
    extract_candidate_terms,
)

from app.literature_to_model.rule_classifier import (
    classify_by_rules,
    classify_batch_by_rules,
)

from app.literature_to_model.semantic_classifier import (
    classify_by_semantic,
    classify_batch_by_semantic,
)

from app.literature_to_model.fallback_tfidf import (
    classify_by_tfidf,
    classify_batch_by_tfidf,
)

from app.literature_to_model.assignment import (
    assign_candidates_to_dimensions,
    export_assignments_to_dataframe,
)

from app.literature_to_model.model_node_builder import (
    build_proposed_model_nodes,
    export_proposed_nodes_to_dataframe,
    apply_accepted_nodes_to_performance_model,
)

from app.literature_to_model.pipeline import (
    run_enhanced_pipeline,
    PipelineResult,
    get_assignments_df,
    get_nodes_df,
)
