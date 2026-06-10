"""Strict literature search orchestrator — unifies search, appraisal, and reporting.

This is the main entry point for the "严格学术标准自动检索与评判" module.
It coordinates all evaluators and produces a complete appraisal for each paper.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.config import DATA_DIR, OUTPUTS_DIR
from src.query_builder import generate_search_queries
from src.pubmed_client import search_pubmed
from src.crossref_client import search_crossref, enrich_with_crossref
from src.journal_ranker import match_journal
from src.study_design_evaluator import evaluate_design
from src.statistics_evaluator import evaluate_statistics
from src.bias_evaluator import evaluate_bias
from src.evidence_grader import grade_evidence
from src.relevance_evaluator import evaluate_relevance
from src.title_abstract_relevance import evaluate_title_abstract_relevance
from src.paper_quality_scorer import compute_overall_score
from src.journal_club_reporter import generate_report, save_report
from src.utils import safe_save_json, logger


SEARCH_RESULTS_DIR = DATA_DIR / "search_results"
SEARCH_LOGS_DIR = DATA_DIR / "search_logs"
APPRAISAL_DIR = DATA_DIR / "appraisal_results"
REPORTS_DIR = OUTPUTS_DIR / "journal_club_reports"


def ensure_dirs():
    for d in [SEARCH_RESULTS_DIR, SEARCH_LOGS_DIR, APPRAISAL_DIR, REPORTS_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def run_search_and_appraisal(
    topic: str,
    max_results: int = 10,
    databases: list = None,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
) -> dict:
    """Run the full search + strict appraisal pipeline.

    Args:
        topic: Natural language research topic
        max_results: Maximum papers to retrieve per database
        databases: List of databases to search (pubmed, crossref)
        year_from: Filter by start year
        year_to: Filter by end year

    Returns:
        Dict with session info, query, retrieved papers, and appraisals.
    """
    ensure_dirs()

    if databases is None:
        databases = ["pubmed"]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # ── Step 1: Generate queries ──
    query_data = generate_search_queries(topic)
    query_data["generated_at"] = datetime.now().isoformat()
    pico = query_data["pico_peco"]

    # ── Step 2: Search ──
    all_papers = []
    search_log = {"session": timestamp, "topic": topic, "pico": pico,
                   "searches": [], "total_found": 0, "errors": []}

    for db in databases:
        try:
            if db == "pubmed":
                query = query_data["queries"]["pubmed"]
                papers = search_pubmed(query, max_results=max_results,
                                        year_from=year_from, year_to=year_to)
                # Check for connection-level errors in pubmed client
                from src.pubmed_client import get_last_error as pubmed_error
                pubmed_err = pubmed_error()
                if pubmed_err and pubmed_err.get("type") == "connection":
                    search_log["errors"].append({
                        "database": db,
                        "type": pubmed_err["type"],
                        "message": pubmed_err["message"],
                        "detail": pubmed_err.get("detail", ""),
                    })
            elif db == "crossref":
                query = query_data["queries"]["crossref"]
                papers = search_crossref(query, max_results=max_results,
                                          year_from=year_from, year_to=year_to)
                # Check for connection-level errors in crossref client
                from src.crossref_client import get_last_error as crossref_error
                crossref_err = crossref_error()
                if crossref_err and crossref_err.get("type") == "connection":
                    search_log["errors"].append({
                        "database": db,
                        "type": crossref_err["type"],
                        "message": crossref_err["message"],
                        "detail": crossref_err.get("detail", ""),
                    })
            else:
                continue

            search_log["searches"].append({
                "database": db,
                "query": query,
                "results_count": len(papers),
                "timestamp": datetime.now().isoformat(),
            })
            all_papers.extend(papers)
            logger.info(f"Search {db}: {len(papers)} results")

        except Exception as e:
            logger.error(f"Search failed for {db}: {e}")
            search_log["errors"].append({
                "database": db,
                "type": "exception",
                "message": f"检索模块异常: {type(e).__name__}: {str(e)[:200]}",
                "detail": str(e)[:300],
            })

    # Deduplicate by DOI then PMID
    seen_doi = set()
    seen_pmid = set()
    unique_papers = []
    for p in all_papers:
        doi = (p.get("doi", "") or "").lower().strip()
        pmid = (p.get("pmid", "") or "").strip()
        if doi and doi in seen_doi:
            continue
        if pmid and pmid in seen_pmid:
            continue
        if doi:
            seen_doi.add(doi)
        if pmid:
            seen_pmid.add(pmid)
        unique_papers.append(p)

    search_log["total_found"] = len(unique_papers)
    all_papers = unique_papers

    # Save search results
    search_results_path = SEARCH_RESULTS_DIR / f"{timestamp}_search_results.json"
    safe_save_json(all_papers, search_results_path)

    search_log_path = SEARCH_LOGS_DIR / f"{timestamp}_search_log.json"
    safe_save_json(search_log, search_log_path)

    # ── Step 3: Enrich with CrossRef ──
    for i, paper in enumerate(all_papers):
        if not paper.get("doi"):
            continue
        try:
            all_papers[i] = enrich_with_crossref(paper)
        except Exception as e:
            logger.warning(f"CrossRef enrichment skipped for paper {i}: {e}")

    # Extract query_context for title/abstract relevance evaluation
    query_context = query_data.get("query_context") or {}

    # ── Step 4: Strict appraisal of each paper ──
    appraisals = []
    excluded_papers = []
    for paper in all_papers:
        try:
            appraisal = _appraise_single_paper(paper, pico, topic, query_context)
            appraisals.append(appraisal)

            # Save individual appraisal
            paper_id = paper.get("paper_id", f"unknown_{len(appraisals) + len(excluded_papers)}")
            appr_path = APPRAISAL_DIR / f"{paper_id}_strict_appraisal.json"
            safe_save_json(appraisal, appr_path)

        except Exception as e:
            logger.error(f"Appraisal failed for {paper.get('title', 'Unknown')[:60]}: {e}")
            appraisals.append({
                "paper_id": paper.get("paper_id", "unknown"),
                "error": str(e),
                "title": paper.get("title", ""),
            })

    # ── Step 5: Separate excluded papers ──
    kept = []
    excluded = []
    for appr in appraisals:
        ra = appr.get("relevance_analysis", {})
        if isinstance(ra, dict) and ra.get("relevance_label") == "exclude":
            excluded.append(appr)
        else:
            kept.append(appr)

    # ── Step 6: Sort by relevance score then overall quality score ──
    def sort_key(appr):
        try:
            ra = appr.get("relevance_analysis", {})
            relevance_score = ra.get("final_relevance_score", 0) if isinstance(ra, dict) else 0
            quality_score = appr.get("overall_appraisal", {}).get("overall_quality_score") or 0
            # Primary: relevance (0-10), secondary: quality (0-10)
            return (relevance_score, quality_score)
        except:
            return (0, 0)

    kept.sort(key=sort_key, reverse=True)
    excluded.sort(key=sort_key, reverse=True)

    # ── Step 7: Relevance stats ──
    label_counts = {"high": 0, "moderate": 0, "low": 0, "exclude": 0, "unrated": 0}
    for appr in kept + excluded:
        ra = appr.get("relevance_analysis", {})
        label = ra.get("relevance_label", "unrated") if isinstance(ra, dict) else "unrated"
        label_counts[label] = label_counts.get(label, 0) + 1

    return {
        "session": {
            "timestamp": timestamp,
            "topic": topic,
            "databases_used": databases,
            "total_retrieved": len(all_papers),
            "total_appraised": len(appraisals),
            "kept_count": len(kept),
            "excluded_count": len(excluded),
            "relevance_stats": label_counts,
        },
        "query": query_data,
        "papers": all_papers,
        "appraisals": kept,
        "excluded_papers": excluded,
        "search_log": search_log,
        "search_results_file": str(search_results_path),
        "search_log_file": str(search_log_path),
    }


def _appraise_single_paper(paper: dict, user_pico: dict, user_topic: str,
                         query_context: dict = None) -> dict:
    """Run the full strict appraisal pipeline for a single paper.

    Returns a complete structured appraisal dict following the spec schema.
    """
    title = paper.get("title", "")
    abstract = paper.get("abstract", "")
    journal_name = paper.get("journal", "")
    issn = paper.get("issn", "")

    # ── Journal evaluation ──
    journal_eval = match_journal(journal_name, issn)

    # ── Study design evaluation ──
    design_eval = evaluate_design(paper)

    # ── Statistics evaluation ──
    stats_eval = evaluate_statistics(paper)

    # ── Bias and evidence ──
    bias_eval = evaluate_bias(paper)

    # Grade evidence
    evidence_info = grade_evidence(
        design_eval.get("study_type", "unknown"),
        bias_eval.get("risk_of_bias", "unclear"),
        design_eval.get("study_type_confidence", 0),
    )
    bias_eval["evidence_level"] = evidence_info["evidence_level"]
    bias_eval["evidence_level_reasons"] = evidence_info["evidence_level_reasons"]

    # ── Title/abstract relevance evaluation (new strict evaluator) ──
    relevance_analysis = {}
    if query_context:
        try:
            relevance_analysis = evaluate_title_abstract_relevance(
                query_context=query_context,
                title=title,
                abstract=abstract,
                publication_type=paper.get("publication_type", ""),
                journal=journal_name,
            )
        except Exception as e:
            logger.warning(f"Title/abstract relevance failed for {title[:60]}: {e}")
            relevance_analysis = {"error": str(e), "relevance_label": "unrated"}

    # ── Legacy relevance evaluation (PICO-based, for backward compatibility) ──
    relevance_eval = evaluate_relevance(paper, user_pico)

    # ── Overall scoring ──
    overall_eval = compute_overall_score(
        journal_eval, design_eval, stats_eval, relevance_eval, bias_eval
    )

    # ── PICO/PECO from paper ──
    paper_pico = {
        "population": paper.get("population", "") or "未提取",
        "intervention_or_exposure": paper.get("intervention_or_exposure", "") or user_pico.get("intervention_or_exposure", ""),
        "comparator": paper.get("comparator", "") or user_pico.get("comparator", ""),
        "outcomes": paper.get("outcomes", "") or paper.get("primary_outcome", "") or user_pico.get("outcomes", ""),
        "study_design": design_eval.get("study_type", "unknown"),
    }

    # ── Missing information ──
    missing_info = overall_eval.get("missing_information", [])

    # Build complete appraisal
    appraisal = {
        "paper_id": paper.get("paper_id", ""),
        "source": paper.get("source", ""),
        "title": title,
        "authors": paper.get("authors", []),
        "year": paper.get("year", ""),
        "journal": journal_name,
        "doi": paper.get("doi", ""),
        "pmid": paper.get("pmid", ""),
        "abstract": paper.get("abstract", ""),
        "publication_type": paper.get("publication_type", []),
        "keywords": paper.get("keywords", []),
        "metadata_completeness": paper.get("metadata_completeness", ""),
        "pico_peco": paper_pico,
        "journal_evaluation": journal_eval,
        "study_design_evaluation": design_eval,
        "statistics_evaluation": stats_eval,
        "bias_and_evidence": bias_eval,
        "relevance_evaluation": relevance_eval,
        "relevance_analysis": relevance_analysis,
        "overall_appraisal": overall_eval,
        "journal_club_report_path": "",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }

    # ── Generate journal club report ──
    try:
        report_md = generate_report(paper, appraisal, user_topic)
        report_path = save_report(report_md, paper)
        if report_path:
            appraisal["journal_club_report_path"] = report_path
    except Exception as e:
        logger.error(f"Report generation failed for {title[:60]}: {e}")

    return appraisal


def import_to_library(appraisal: dict, paper: dict) -> dict:
    """Import a strictly appraised paper into the existing literature database.

    Handles deduplication by DOI > PMID > title similarity.
    Preserves existing manual notes if paper already exists.
    """
    from src.database import add_paper, load_papers
    from src.utils import generate_paper_id

    # Build the enriched paper dict for the existing DB
    je = appraisal.get("journal_evaluation", {})
    sde = appraisal.get("study_design_evaluation", {})
    se = appraisal.get("statistics_evaluation", {})
    be = appraisal.get("bias_and_evidence", {})
    re = appraisal.get("relevance_evaluation", {})
    oa = appraisal.get("overall_appraisal", {})

    # Check for existing paper by DOI or PMID
    existing_papers = load_papers()
    doi = paper.get("doi", "")
    pmid = paper.get("pmid", "")

    existing = None
    for p in existing_papers:
        if doi and p.get("doi") == doi:
            existing = p
            break
        if pmid and p.get("pmid") == pmid:
            existing = p
            break

    # Build db paper dict
    db_paper = {
        "title": paper.get("title", ""),
        "authors": paper.get("authors_str", "") or paper.get("authors", ""),
        "year": paper.get("year", ""),
        "journal": paper.get("journal", ""),
        "doi": doi,
        "pmid": pmid,
        "abstract": paper.get("abstract", ""),
        "keywords": paper.get("keywords", []),
        "study_type": sde.get("study_type", "unknown"),
        "research_domain": paper.get("research_domain", ""),
        "evidence_level": be.get("evidence_level", "unknown"),
        "quality_score": oa.get("overall_quality_score"),
        "relevance_score": re.get("relevance_score"),
        "risk_of_bias": be.get("risk_of_bias"),
        "risk_of_bias_domains": be.get("risk_of_bias_domains", {}),
        "risk_of_bias_reasons": be.get("risk_of_bias_reasons", []),
        "design_score": oa.get("design_score"),
        "statistics_score": oa.get("statistics_score"),
        "journal_score": oa.get("journal_score"),
        "reporting_quality_score": oa.get("reporting_quality_score"),
        "inclusion_decision": oa.get("recommendation"),
        "reason": oa.get("recommendation_reason"),
        "missing_information": oa.get("missing_information", []),
        "journal_club_report_path": appraisal.get("journal_club_report_path", ""),
        "strict_appraisal_json": str(APPRAISAL_DIR / f"{paper.get('paper_id', 'unknown')}_strict_appraisal.json"),
        "pico_peco": appraisal.get("pico_peco", {}),
        "journal_evaluation": je,
        "statistics_evaluation_summary": {
            "score": se.get("statistics_score"),
            "model": se.get("model_type"),
            "strengths": se.get("statistics_strengths", []),
            "limitations": se.get("statistics_limitations", []),
        },
        "source": paper.get("source", "strict_search"),
        "notes": "",
    }

    # Preserve existing manual notes
    if existing:
        existing_notes = existing.get("notes", "")
        if existing_notes:
            db_paper["notes"] = existing_notes
        logger.info(f"Updating existing paper in library: {paper.get('title', '')[:80]}")

    # Add to database
    paper_id = add_paper(db_paper)
    db_paper["id"] = paper_id

    return {"success": True, "paper_id": paper_id, "title": db_paper.get("title", ""),
            "was_existing": existing is not None}
