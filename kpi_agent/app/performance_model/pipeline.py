"""
Orchestration pipeline: Literature → Performance Model.

Ties together all modules: batch loading, extraction, merging,
evidence linking, scoring, and model tree building.
"""

import logging
from typing import Optional

from app.performance_model.batch_loader import (
    load_literature_batch,
    get_cached_queries,
    LiteratureDocument,
)
from app.performance_model.extractor import (
    extract_determinant_candidates_from_batch,
    DeterminantCandidate,
)
from app.performance_model.merger import (
    merge_determinant_candidates,
    standardize_all_names,
)
from app.performance_model.evidence_linker import (
    create_evidence_links,
    build_evidence_report,
)
from app.performance_model.builder import (
    build_performance_model_from_candidates,
    build_performance_model_tree_for_db,
)
from app.literature.cache import LiteratureCache

logger = logging.getLogger(__name__)


def run_full_pipeline(
    query_id: Optional[int] = None,
    literature_ids: Optional[list[int]] = None,
    limit: int = 50,
    include_fulltext: bool = True,
    use_keybert: bool = True,
    use_yake: bool = True,
    use_spacy: bool = False,
    project_id: Optional[int] = None,
    min_confidence: float = 0.2,
    cache: Optional[LiteratureCache] = None,
) -> dict:
    """Run the complete Literature → Performance Model pipeline.

    Steps:
    1. Load literature documents from cache
    2. Extract determinant candidates (multi-method)
    3. Standardize and merge candidates
    4. Filter by min confidence
    5. Create evidence links
    6. Build performance model tree
    7. Generate evidence report

    Returns:
        Full pipeline result dict:
        {
            "documents_loaded": int,
            "candidates_extracted": int,
            "candidates_merged": int,
            "candidates_filtered": int,
            "evidence_links": int,
            "model_tree": dict,
            "candidates": list[dict],
            "evidence_report": str,
        }
    """
    if cache is None:
        cache = LiteratureCache()

    # Step 1: Load literature
    docs = load_literature_batch(
        query_id=query_id,
        literature_ids=literature_ids,
        limit=limit,
        include_fulltext=include_fulltext,
        cache=cache,
    )

    if not docs:
        return {
            "documents_loaded": 0,
            "candidates_extracted": 0,
            "candidates_merged": 0,
            "candidates_filtered": 0,
            "evidence_links": 0,
            "model_tree": {},
            "candidates": [],
            "evidence_report": "*No documents loaded.*",
            "documents_with_abstract": 0,
            "documents_with_fulltext": 0,
            "documents_skipped": 0,
        }

    docs_with_abstract = sum(1 for d in docs if d.abstract)
    docs_with_fulltext = sum(1 for d in docs if d.fulltext_available)

    # Step 2: Extract candidates
    raw_candidates = extract_determinant_candidates_from_batch(
        docs,
        include_fulltext=include_fulltext,
        use_keybert=use_keybert,
        use_yake=use_yake,
        use_spacy=use_spacy,
    )

    # Step 3: Standardize and merge
    standardized = standardize_all_names(raw_candidates)
    merged = merge_determinant_candidates(standardized)

    # Step 4: Filter by confidence
    filtered = [c for c in merged if _get_conf(c) >= min_confidence]
    filtered.sort(key=lambda c: _get_conf(c) * _get_strength(c), reverse=True)

    # Step 5: Evidence links
    links = create_evidence_links(filtered, docs)

    # Step 6: Build model tree
    model_tree = build_performance_model_from_candidates(filtered, project_id)

    # Step 7: Evidence report
    report = build_evidence_report(filtered, links, model_tree)

    # Convert candidates to dicts for serialization
    candidate_dicts = [c.to_dict() if hasattr(c, 'to_dict') else c for c in filtered]

    result = {
        "documents_loaded": len(docs),
        "documents_with_abstract": docs_with_abstract,
        "documents_with_fulltext": docs_with_fulltext,
        "documents_skipped": 0,
        "candidates_extracted": len(raw_candidates),
        "candidates_merged": len(merged),
        "candidates_filtered": len(filtered),
        "evidence_links": len(links),
        "model_tree": model_tree,
        "candidates": candidate_dicts,
        "evidence_links_data": links,
        "evidence_report": report,
    }

    logger.info(
        f"Pipeline complete: {len(docs)} docs → {len(raw_candidates)} raw → "
        f"{len(merged)} merged → {len(filtered)} filtered → "
        f"{len(links)} evidence links → {model_tree['total_candidates']} tree candidates"
    )

    return result


def save_model_to_db(
    pipeline_result: dict,
    project_id: int,
    db_session=None,
) -> dict:
    """Save accepted candidates to the main database as PerformanceDeterminant records.

    Args:
        pipeline_result: Result dict from run_full_pipeline().
        project_id: Target project ID.
        db_session: SQLAlchemy session (from app.database.SessionLocal).

    Returns:
        Dict with counts of created records.
    """
    if db_session is None:
        from app.database import SessionLocal
        db_session = SessionLocal()
        auto_close = True
    else:
        auto_close = False

    try:
        records = build_performance_model_tree_for_db(
            pipeline_result.get("candidates", []),
            project_id,
        )
        from app import models, crud

        created = {"categories": 0, "determinants": 0, "evidence_sources": 0}

        # Create category-level nodes first
        cat_id_map: dict[str, int] = {}
        for rec in records:
            if rec.get("parent_id") is None and rec.get("name") in [
                "生理要求", "技术要求", "战术要求", "营养要求",
                "心理技能", "器材特点", "健康", "比赛规则", "其他/不确定",
            ]:
                cat_name = rec["name"]
                if cat_name not in cat_id_map:
                    obj = models.PerformanceDeterminant(**rec)
                    db_session.add(obj)
                    db_session.flush()
                    cat_id_map[cat_name] = obj.id
                    created["categories"] += 1

        # Create determinant nodes linked to category parents
        for rec in records:
            cat = rec.get("category", "")
            if rec.get("name") in cat_id_map:
                continue  # already created as category node
            if cat in cat_id_map:
                rec["parent_id"] = cat_id_map[cat]
            obj = models.PerformanceDeterminant(**rec)
            db_session.add(obj)
            created["determinants"] += 1

        # Create evidence source records
        links = pipeline_result.get("evidence_links_data", [])
        seen_dois = set()
        for link in links:
            doi = link.get("doi", "")
            if doi and doi not in seen_dois:
                seen_dois.add(doi)
                source_data = {
                    "title": link.get("canonical_name", "")[:500],
                    "source_type": "科学文献",
                    "doi": doi,
                    "year": link.get("year"),
                    "summary": link.get("evidence_text", "")[:500],
                    "evidence_level": _conf_to_level(link.get("confidence_score", 0)),
                }
                try:
                    crud.create_evidence_source(db_session, project_id, source_data)
                    created["evidence_sources"] += 1
                except Exception as e:
                    logger.warning(f"Failed to create evidence source: {e}")

        db_session.commit()
        logger.info(f"Saved model to DB: {created}")
        return created

    except Exception as e:
        logger.error(f"Failed to save model to DB: {e}")
        if db_session:
            db_session.rollback()
        raise
    finally:
        if auto_close and db_session:
            db_session.close()


def _get_conf(c) -> float:
    if hasattr(c, 'confidence_score'):
        return c.confidence_score
    return c.get('confidence_score', 0.0)


def _get_strength(c) -> float:
    if hasattr(c, 'evidence_strength_score'):
        return c.evidence_strength_score
    return c.get('evidence_strength_score', 0.0)


def _conf_to_level(conf: float) -> str:
    if conf >= 0.7:
        return "高"
    elif conf >= 0.4:
        return "中"
    elif conf >= 0.2:
        return "低"
    return "未知"
