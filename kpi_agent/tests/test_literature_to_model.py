"""
Mock test for the enhanced literature→model pipeline.

Tests with 3 sample papers spanning multiple performance dimensions
to verify the full extraction→classification→node-building flow.
"""

import pytest

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
from app.literature_to_model.text_cleaning import build_literature_chunks
from app.literature_to_model.pipeline import run_enhanced_pipeline


# ── Mock literature data (3 sample papers) ───────────────────────────────

MOCK_LITERATURE = [
    {
        "id": 1,
        "title": "Physiological determinants of middle-distance running performance in elite athletes",
        "abstract": (
            "Middle-distance running performance is associated with maximal oxygen uptake, "
            "running economy and lactate threshold. This study examined 24 elite middle-distance "
            "runners during treadmill testing. VO2max was measured at 72.3 ± 5.1 ml/kg/min. "
            "Lactate threshold occurred at 82% of VO2max. Running economy was assessed as oxygen "
            "cost at 16 km/h. Heart rate variability was also recorded during recovery periods. "
            "Results showed that VO2max and running economy explained 67% of performance variance, "
            "while lactate threshold contributed an additional 12%. Anaerobic capacity as measured "
            "by maximal accumulated oxygen deficit was also a significant predictor. Sprint ability "
            "tested via 50m maximal sprint showed moderate correlation with 800m performance. "
            "Body composition measurements revealed lower body fat percentage in faster runners."
        ),
        "year": 2023,
        "doi": "10.1234/sports.2023.001",
        "source_database": "PubMed",
        "authors": "Johnson M, Smith K, Williams R",
    },
    {
        "id": 2,
        "title": "Biomechanical and technical factors influencing running performance and injury risk",
        "abstract": (
            "This review analyzed biomechanical determinants of running performance including "
            "stride length, stride frequency, and ground contact time. Stride length was found to "
            "increase with running speed while ground contact time decreased from 220ms to 160ms. "
            "Running mechanics and joint kinematics at the knee and ankle were assessed using "
            "3D motion capture. Force plate data revealed that vertical ground reaction force "
            "increased with speed. Injury risk factors including previous hamstring strain and "
            "training load were monitored over a 12-month period. Results showed that sleep quality "
            "and recovery time significantly moderated injury incidence. The acute:chronic workload "
            "ratio (ACWR) above 1.5 was associated with a 3.2x increase in injury risk. "
            "Psychological factors such as anxiety and mental toughness were also found to affect "
            "return-to-play decisions. Reaction time measured via choice reaction time test was "
            "2% slower in athletes with poor sleep quality."
        ),
        "year": 2024,
        "doi": "10.1234/sports.2024.002",
        "source_database": "Europe PMC",
        "authors": "Chen L, Garcia M, Thompson P",
    },
    {
        "id": 3,
        "title": "Tactical pacing strategy, nutrition, and equipment effects on competition performance",
        "abstract": (
            "Pacing strategy is a critical tactical requirement in endurance competition. "
            "This study examined the effects of different pacing patterns on 5000m track performance "
            "in 18 national-level runners. Athletes used positive, negative, and even pacing strategies. "
            "Decision making speed during tactical situations was measured using video-based tests. "
            "Carbohydrate intake and hydration status were monitored pre- and post-competition. "
            "Energy availability below 30 kcal/kg FFM was associated with decreased performance. "
            "Supplementation with sodium bicarbonate improved 5000m time by 2.1%. "
            "Carbon fiber plate shoes reduced the metabolic cost of running by 4% compared to "
            "traditional racing flats. GPS wearable data showed that pacing errors were reduced "
            "with real-time feedback. Body composition measured via DXA showed elite runners "
            "had 8-12% body fat. Competition rules regarding footwear stack height (max 40mm) "
            "were discussed in relation to the new World Athletics regulations. Anti-doping "
            "regulations and therapeutic use exemptions were also reviewed."
        ),
        "year": 2023,
        "doi": "10.1234/sports.2023.003",
        "source_database": "OpenAlex",
        "authors": "Park S, Mueller H, Davis A, Brown J",
    },
]


# ── Test: Dimensions ──────────────────────────────────────────────────────

class TestDimensions:
    """Test default performance dimension loading."""

    def test_load_dimensions_returns_8_categories(self):
        dims = load_default_performance_dimensions()
        assert len(dims) == 8

    def test_all_dimensions_have_required_fields(self):
        dims = load_default_performance_dimensions()
        for d in dims:
            assert d.id, f"Dimension missing id"
            assert d.name_cn, f"Dimension {d.id} missing name_cn"
            assert d.name_en, f"Dimension {d.id} missing name_en"
            assert d.description, f"Dimension {d.id} missing description"
            assert len(d.aliases) >= 8, f"Dimension {d.id} has too few aliases: {len(d.aliases)}"

    def test_dimension_ids_are_unique(self):
        dims = load_default_performance_dimensions()
        ids = [d.id for d in dims]
        assert len(ids) == len(set(ids)), "Duplicate dimension IDs found"

    def test_build_domain_dictionary(self):
        dd = build_domain_dictionary()
        assert "physiological_requirements" in dd
        assert "technical_requirements" in dd
        assert "tactical_requirements" in dd
        assert len(dd["physiological_requirements"]) >= 20

    def test_build_inverted_index(self):
        inv = build_inverted_index()
        assert "vo2max" in inv
        assert "lactate threshold" in inv
        assert inv["vo2max"] == ["physiological_requirements"]


# ── Test: Chunk building ──────────────────────────────────────────────────

class TestChunkBuilding:
    """Test literature chunk construction."""

    def test_build_chunks_from_mock(self):
        chunks = build_literature_chunks(MOCK_LITERATURE)
        assert len(chunks) > 3, f"Expected more than 3 chunks, got {len(chunks)}"
        # Each paper has 1 title chunk + N abstract sentence chunks
        titles = [c for c in chunks if c.chunk_type == "title"]
        assert len(titles) == 3, f"Expected 3 title chunks, got {len(titles)}"

    def test_chunks_have_source_metadata(self):
        chunks = build_literature_chunks(MOCK_LITERATURE)
        for c in chunks:
            assert c.literature_id in [1, 2, 3]
            assert c.title
            if c.chunk_type == "title":
                assert c.sentence_index == 0

    def test_chunks_without_abstract(self):
        chunks = build_literature_chunks(MOCK_LITERATURE, include_abstract=False)
        assert len(chunks) == 3  # titles only

    def test_chunks_without_title(self):
        chunks = build_literature_chunks(MOCK_LITERATURE, include_title=False)
        assert all(c.chunk_type != "title" for c in chunks)


# ── Test: Candidate extraction ────────────────────────────────────────────

class TestCandidateExtraction:
    """Test term extraction from chunks."""

    def test_extract_candidates_from_mock_chunks(self):
        from app.literature_to_model.keyword_extractor import extract_candidate_terms

        chunks = build_literature_chunks(MOCK_LITERATURE)
        candidates = extract_candidate_terms(
            chunks,
            use_keybert=False,  # skip heavy models in test
            use_yake=False,
            use_regex=True,
            use_noun_phrases=False,
        )
        assert len(candidates) >= 1, "Should extract at least some candidates with regex"
        for c in candidates:
            assert c.candidate_term
            assert c.normalized_term
            assert c.source_literature_id in [1, 2, 3]

    def test_regex_extracts_vo2max(self):
        from app.literature_to_model.keyword_extractor import _extract_by_regex_dictionary

        text = "VO2max was measured at 72.3 ml/kg/min and lactate threshold was determined."
        terms = _extract_by_regex_dictionary(text)
        # Should find VO2-related terms
        assert len(terms) >= 1


# ── Test: Rule classifier ─────────────────────────────────────────────────

class TestRuleClassifier:
    """Test rule-based dictionary classification."""

    def test_keyword_lookup_vo2max(self):
        from app.literature_to_model.rule_classifier import _keyword_lookup
        matches = _keyword_lookup("vo2max")
        assert matches
        assert matches[0][0] == "physiological_requirements"

    def test_keyword_lookup_lactate_threshold(self):
        from app.literature_to_model.rule_classifier import _keyword_lookup
        matches = _keyword_lookup("lactate threshold")
        assert matches
        assert matches[0][0] == "physiological_requirements"

    def test_keyword_lookup_stride_length(self):
        from app.literature_to_model.rule_classifier import _keyword_lookup
        matches = _keyword_lookup("stride length")
        assert matches
        assert matches[0][0] == "technical_requirements"

    def test_keyword_lookup_unknown_term(self):
        from app.literature_to_model.rule_classifier import _keyword_lookup
        matches = _keyword_lookup("zyxabc123")
        assert not matches

    def test_classify_known_term(self):
        from app.literature_to_model.rule_classifier import classify_by_rules
        from app.literature_to_model.schemas import ExtractedCandidate

        candidate = ExtractedCandidate(
            candidate_term="VO2max",
            normalized_term="vo2max",
            source_literature_id=1,
            source_title="Test Paper",
            source_year=2023,
            evidence_sentence="VO2max was 72.3 ml/kg/min",
            extraction_method="regex",
            raw_score=0.8,
        )
        assignment = classify_by_rules(candidate)
        assert assignment is not None
        assert assignment.assigned_dimension == "physiological_requirements"
        assert assignment.match_method == "rule"
        assert assignment.rule_score >= 0.7


# ── Test: TF-IDF fallback ─────────────────────────────────────────────────

class TestTfidfFallback:
    """Test TF-IDF fallback classifier."""

    def test_tfidf_batch_classify(self):
        from app.literature_to_model.fallback_tfidf import classify_batch_by_tfidf

        candidates = [
            ExtractedCandidate(
                candidate_term="VO2max",
                normalized_term="vo2max",
                source_literature_id=1,
                source_title="Paper 1",
                source_year=2023,
                evidence_sentence="VO2max is a key determinant of aerobic performance.",
                extraction_method="regex",
                raw_score=0.8,
            ),
            ExtractedCandidate(
                candidate_term="stride frequency",
                normalized_term="stride frequency",
                source_literature_id=2,
                source_title="Paper 2",
                source_year=2024,
                evidence_sentence="Stride frequency affects running economy.",
                extraction_method="regex",
                raw_score=0.7,
            ),
        ]

        classified, remaining = classify_batch_by_tfidf(candidates, threshold=0.10)
        # TF-IDF should classify most terms
        assert len(classified) + len(remaining) == 2

    def test_tfidf_always_available(self):
        # scikit-learn is a core dependency, should never fail
        from app.literature_to_model.fallback_tfidf import classify_batch_by_tfidf
        classified, remaining = classify_batch_by_tfidf([], threshold=0.15)
        assert classified == []
        assert remaining == []


# ── Test: Full pipeline ───────────────────────────────────────────────────

class TestFullPipeline:
    """End-to-end pipeline tests with mock data."""

    def test_pipeline_runs_on_mock_data(self):
        result = run_enhanced_pipeline(
            MOCK_LITERATURE,
            use_keybert=False,
            use_yake=False,
            use_regex=True,
            use_noun_phrases=False,
        )
        assert result.total_literature == 3
        assert result.total_chunks > 0
        assert result.total_candidates > 0, "Should extract candidates from mock data"
        assert result.total_assignments > 0, "Should produce assignments"
        assert len(result.errors) == 0, f"Pipeline errors: {result.errors}"

    def test_pipeline_produces_assignments_with_required_fields(self):
        result = run_enhanced_pipeline(
            MOCK_LITERATURE,
            use_keybert=False,
            use_yake=False,
            use_regex=True,
            use_noun_phrases=False,
        )
        for a in result.assignments:
            assert a.candidate_term, "Missing candidate_term"
            assert a.normalized_term, "Missing normalized_term"
            assert a.assigned_dimension, "Missing assigned_dimension"
            assert a.confidence_score >= 0.0, "Missing confidence_score"
            assert a.match_method, "Missing match_method"
            assert a.reason, "Missing reason"
            assert a.evidence_sentence, "Missing evidence_sentence"

    def test_pipeline_finds_physiological_terms(self):
        result = run_enhanced_pipeline(
            MOCK_LITERATURE,
            use_keybert=False,
            use_yake=False,
            use_regex=True,
            use_noun_phrases=False,
        )
        phys_assignments = [
            a for a in result.assignments
            if a.assigned_dimension == "physiological_requirements"
        ]
        assert len(phys_assignments) > 0, "Should find physiological terms"

        # Check for key terms
        terms = {a.normalized_term for a in result.assignments}
        # At least some physiological terms should be found
        phys_terms = terms & {
            "vo2max", "lactate threshold", "running economy",
            "anaerobic capacity", "heart rate variability",
            "sprint ability", "body composition",
        }
        assert len(phys_terms) > 0, f"No known physiological terms found in {terms}"

    def test_pipeline_finds_technical_terms(self):
        result = run_enhanced_pipeline(
            MOCK_LITERATURE,
            use_keybert=False,
            use_yake=False,
            use_regex=True,
            use_noun_phrases=False,
        )
        tech_assignments = [
            a for a in result.assignments
            if a.assigned_dimension in ("technical_requirements", "health")
        ]
        terms = {a.normalized_term for a in tech_assignments}
        # stride length, ground contact time, injury risk, etc.
        expected = {
            "stride length", "stride frequency", "ground contact time",
            "injury risk", "training load", "sleep quality",
            "recovery time", "running mechanics",
        }
        found = terms & expected
        assert len(found) > 0, f"No known technical/health terms found. Found: {terms}"

    def test_pipeline_builds_proposed_nodes(self):
        result = run_enhanced_pipeline(
            MOCK_LITERATURE,
            use_keybert=False,
            use_yake=False,
            use_regex=True,
            use_noun_phrases=False,
            min_node_confidence=0.0,
        )
        assert result.proposed_node_count >= 0
        for node in result.proposed_nodes:
            assert node.node_name
            assert node.parent_dimension
            assert node.confidence_score >= 0.0

    def test_pipeline_empty_input(self):
        result = run_enhanced_pipeline([])
        assert result.total_literature == 0
        assert result.total_candidates == 0
        assert "No literature data provided" in result.warnings

    def test_pipeline_summary(self):
        result = run_enhanced_pipeline(
            MOCK_LITERATURE,
            use_keybert=False,
            use_yake=False,
            use_regex=True,
            use_noun_phrases=False,
        )
        summary = result.to_summary()
        assert summary["文献数量"] == 3
        assert summary["文本片段数"] > 0
        assert summary["候选术语数"] > 0


# ── Test: Model node builder ──────────────────────────────────────────────

class TestModelNodeBuilder:
    """Test proposed model node construction."""

    def test_build_nodes_from_assignments(self):
        from app.literature_to_model.model_node_builder import build_proposed_model_nodes

        # Create assignments that should merge (similar terms)
        assignments = [
            DimensionAssignment(
                candidate_term="VO2max",
                normalized_term="vo2max",
                assigned_dimension="physiological_requirements",
                assigned_dimension_name_cn="生理要求",
                confidence_score=0.85,
                semantic_score=0.6,
                rule_score=0.9,
                keyword_score=0.9,
                evidence_quality_score=0.7,
                match_method="rule",
                reason="keyword match: 'vo2max' → physiological_requirements",
                evidence_sentence="VO2max was 72.3 ml/kg/min",
                source_literature_id=1,
                source_title="Paper 1",
                source_year=2023,
            ),
            DimensionAssignment(
                candidate_term="maximal oxygen uptake",
                normalized_term="maximal oxygen uptake",
                assigned_dimension="physiological_requirements",
                assigned_dimension_name_cn="生理要求",
                confidence_score=0.80,
                semantic_score=0.5,
                rule_score=0.85,
                keyword_score=0.85,
                evidence_quality_score=0.6,
                match_method="rule",
                reason="keyword match: 'maximal oxygen uptake' → physiological_requirements",
                evidence_sentence="Maximal oxygen uptake predicts performance.",
                source_literature_id=2,
                source_title="Paper 2",
                source_year=2024,
            ),
            DimensionAssignment(
                candidate_term="running economy",
                normalized_term="running economy",
                assigned_dimension="physiological_requirements",
                assigned_dimension_name_cn="生理要求",
                confidence_score=0.78,
                semantic_score=0.5,
                rule_score=0.8,
                keyword_score=0.8,
                evidence_quality_score=0.6,
                match_method="rule",
                reason="keyword match: 'running economy' → physiological_requirements",
                evidence_sentence="Running economy was assessed at 16 km/h.",
                source_literature_id=1,
                source_title="Paper 1",
                source_year=2023,
            ),
        ]

        nodes = build_proposed_model_nodes(assignments, fuzzy_threshold=0.80)
        assert len(nodes) >= 1
        # VO2max and maximal oxygen uptake should merge (high similarity)
        # Running economy should be separate
        total_evidence = sum(len(n.evidence_items) for n in nodes)
        assert total_evidence == 3

    def test_export_nodes_to_dataframe(self):
        from app.literature_to_model.model_node_builder import (
            build_proposed_model_nodes,
            export_proposed_nodes_to_dataframe,
        )

        assignments = [
            DimensionAssignment(
                candidate_term="VO2max",
                normalized_term="vo2max",
                assigned_dimension="physiological_requirements",
                assigned_dimension_name_cn="生理要求",
                confidence_score=0.85,
                semantic_score=0.6,
                rule_score=0.9,
                keyword_score=0.9,
                evidence_quality_score=0.7,
                match_method="rule",
                reason="test",
                evidence_sentence="VO2max was 72.3",
                source_literature_id=1,
                source_title="Paper 1",
                source_year=2023,
            ),
        ]
        nodes = build_proposed_model_nodes(assignments)
        df = export_proposed_nodes_to_dataframe(nodes)
        assert len(df) == len(nodes)

    def test_apply_accepted_nodes(self):
        from app.literature_to_model.model_node_builder import (
            build_proposed_model_nodes,
            apply_accepted_nodes_to_performance_model,
        )

        assignments = [
            DimensionAssignment(
                candidate_term="VO2max",
                normalized_term="vo2max",
                assigned_dimension="physiological_requirements",
                assigned_dimension_name_cn="生理要求",
                confidence_score=0.85,
                semantic_score=0.6,
                rule_score=0.9,
                keyword_score=0.9,
                evidence_quality_score=0.7,
                match_method="rule",
                reason="test",
                evidence_sentence="VO2max was 72.3",
                source_literature_id=1,
                source_title="Paper 1",
                source_year=2023,
            ),
        ]
        nodes = build_proposed_model_nodes(assignments)
        # Mark as accepted
        for n in nodes:
            n.status = "accepted"

        existing = [{"name": "existing_determinant", "name_en": "Existing"}]
        updated = apply_accepted_nodes_to_performance_model(nodes, existing)
        assert len(updated) > len(existing)

    def test_apply_does_not_duplicate(self):
        from app.literature_to_model.model_node_builder import (
            build_proposed_model_nodes,
            apply_accepted_nodes_to_performance_model,
        )

        assignments = [
            DimensionAssignment(
                candidate_term="VO2max",
                normalized_term="vo2max",
                assigned_dimension="physiological_requirements",
                assigned_dimension_name_cn="生理要求",
                confidence_score=0.85,
                semantic_score=0.6,
                rule_score=0.9,
                keyword_score=0.9,
                evidence_quality_score=0.7,
                match_method="rule",
                reason="test",
                evidence_sentence="VO2max was 72.3",
                source_literature_id=1,
                source_title="Paper 1",
                source_year=2023,
            ),
        ]
        nodes = build_proposed_model_nodes(assignments)
        for n in nodes:
            n.status = "accepted"

        existing = [{"name": "VO2max", "name_en": "vo2max"}]
        updated = apply_accepted_nodes_to_performance_model(nodes, existing)
        # Should not duplicate
        assert len(updated) == len(existing)


# ── Test: Assignment scoring ──────────────────────────────────────────────

class TestAssignmentScoring:
    """Test confidence score computation."""

    def test_confidence_formula(self):
        from app.literature_to_model.assignment import _compute_confidence
        score = _compute_confidence(0.8, 0.7, 0.6, 0.5)
        expected = 0.4 * 0.8 + 0.3 * 0.7 + 0.2 * 0.6 + 0.1 * 0.5
        assert abs(score - expected) < 0.001

    def test_evidence_quality_scoring(self):
        from app.literature_to_model.assignment import _compute_evidence_quality

        high_quality = DimensionAssignment(
            candidate_term="test",
            normalized_term="test",
            assigned_dimension="physiological_requirements",
            evidence_sentence="A" * 60,
            source_title="Paper Title",
            source_year=2023,
            doi="10.1234/test",
            match_method="rule",
            reason="",
        )
        score_high = _compute_evidence_quality(high_quality)
        assert score_high > 0.5, f"High quality score too low: {score_high}"

        low_quality = DimensionAssignment(
            candidate_term="test",
            normalized_term="test",
            assigned_dimension="other_uncertain",
            match_method="fallback",
            reason="",
        )
        score_low = _compute_evidence_quality(low_quality)
        assert score_low < 0.1, f"Low quality score too high: {score_low}"

    def test_finalize_sets_needs_review(self):
        from app.literature_to_model.assignment import _finalize_assignment

        high = DimensionAssignment(
            candidate_term="test",
            normalized_term="test",
            assigned_dimension="physiological_requirements",
            semantic_score=0.9,
            rule_score=0.9,
            keyword_score=0.9,
            evidence_quality_score=0.9,
            match_method="semantic",
            reason="test",
            evidence_sentence="Evidence text",
            source_title="Title",
            source_year=2023,
            doi="10.1234/test",
        )
        _finalize_assignment(high)
        assert high.confidence_score >= 0.75
        assert not high.needs_review

        low = DimensionAssignment(
            candidate_term="test",
            normalized_term="test",
            assigned_dimension="other_uncertain",
            match_method="fallback",
            reason="test",
        )
        _finalize_assignment(low)
        assert low.confidence_score < 0.5
        assert low.needs_review


# ── Test: Schemas ─────────────────────────────────────────────────────────

class TestSchemas:
    """Test dataclass serialization."""

    def test_dimension_assignment_to_dict(self):
        a = DimensionAssignment(
            candidate_term="VO2max",
            normalized_term="vo2max",
            assigned_dimension="physiological_requirements",
            assigned_dimension_name_cn="生理要求",
            confidence_score=0.85,
            semantic_score=0.6,
            rule_score=0.9,
            keyword_score=0.9,
            evidence_quality_score=0.7,
            match_method="rule",
            reason="test",
            evidence_sentence="VO2max was 72.3",
            source_literature_id=1,
            source_title="Paper 1",
            source_year=2023,
            doi="10.1234/test",
            needs_review=False,  # 0.85 ≥ 0.75 → high confidence
        )
        d = a.to_dict()
        assert d["candidate_term"] == "VO2max"
        assert d["confidence_score"] == 0.85
        assert d["needs_review"] is False

    def test_proposed_model_node_to_dict(self):
        n = ProposedModelNode(
            node_name="有氧能力",
            node_name_en="Aerobic Capacity",
            parent_dimension="physiological_requirements",
            parent_dimension_name_cn="生理要求",
            description="Test description",
            evidence_items=[{"test": "data"}],
            confidence_score=0.85,
            source_count=3,
            suggested_as="determinant",
            status="proposed",
            aliases=["vo2max", "aerobic power"],
        )
        d = n.to_dict()
        assert d["node_name"] == "有氧能力"
        assert d["confidence_score"] == 0.85
        assert len(d["evidence_items"]) == 1

    def test_performance_dimension_to_dict(self):
        d = PerformanceDimension(
            id="test_dim",
            name_cn="测试",
            name_en="Test",
            description="Test description",
            aliases=["a", "b"],
            examples=["ex1", "ex2"],
        )
        dct = d.to_dict()
        assert dct["id"] == "test_dim"
        assert dct["aliases"] == ["a", "b"]


# ── Test: Export functions ────────────────────────────────────────────────

class TestExports:
    """Test DataFrame export functions."""

    def test_export_assignments_to_df(self):
        from app.literature_to_model.assignment import export_assignments_to_dataframe

        assignments = [
            DimensionAssignment(
                candidate_term="VO2max",
                normalized_term="vo2max",
                assigned_dimension="physiological_requirements",
                assigned_dimension_name_cn="生理要求",
                confidence_score=0.85,
                semantic_score=0.6,
                rule_score=0.9,
                keyword_score=0.9,
                evidence_quality_score=0.7,
                match_method="rule",
                reason="test",
                evidence_sentence="VO2max was 72.3",
                source_literature_id=1,
                source_title="Paper 1",
                source_year=2023,
            ),
        ]
        df = export_assignments_to_dataframe(assignments)
        assert len(df) == 1
        assert "候选术语" in df.columns
        assert "分配维度" in df.columns
        assert "置信度" in df.columns
        assert "证据句" in df.columns
