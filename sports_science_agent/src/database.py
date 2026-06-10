"""Literature database — JSON/CSV storage for papers metadata."""

import pandas as pd
from pathlib import Path
from typing import Optional
from datetime import datetime

from src.config import (
    PAPERS_METADATA_JSON,
    PAPERS_METADATA_CSV,
    SCREENING_DECISIONS_JSON,
    EXTRACTED_FINDINGS_JSON,
)
from src.utils import safe_load_json, safe_save_json, safe_save_csv, generate_paper_id, logger


def load_papers() -> list[dict]:
    return safe_load_json(PAPERS_METADATA_JSON, default=[])


def save_papers(papers: list[dict]):
    safe_save_json(papers, PAPERS_METADATA_JSON)
    if papers:
        df = pd.DataFrame(papers)
        safe_save_csv(df, PAPERS_METADATA_CSV)


def get_paper_by_id(paper_id: str) -> Optional[dict]:
    papers = load_papers()
    for p in papers:
        if p.get("id") == paper_id:
            return p
    return None


def add_paper(paper: dict) -> str:
    papers = load_papers()
    paper_id = generate_paper_id(
        paper.get("title", ""),
        paper.get("authors", ""),
        str(paper.get("year", "")),
    )
    paper["id"] = paper_id
    paper["created_at"] = paper.get("created_at") or datetime.now().isoformat()
    paper["updated_at"] = datetime.now().isoformat()
    # Check for duplicates
    existing_ids = {p.get("id") for p in papers}
    if paper_id in existing_ids:
        for i, p in enumerate(papers):
            if p.get("id") == paper_id:
                papers[i] = paper
                break
        logger.info(f"Updated existing paper: {paper.get('title', 'Untitled')[:80]}")
    else:
        papers.append(paper)
        logger.info(f"Added new paper: {paper.get('title', 'Untitled')[:80]}")
    save_papers(papers)
    return paper_id


def update_paper(paper_id: str, updates: dict) -> bool:
    papers = load_papers()
    for i, p in enumerate(papers):
        if p.get("id") == paper_id:
            papers[i].update(updates)
            papers[i]["updated_at"] = datetime.now().isoformat()
            save_papers(papers)
            return True
    return False


def delete_paper(paper_id: str) -> bool:
    papers = load_papers()
    new_papers = [p for p in papers if p.get("id") != paper_id]
    if len(new_papers) < len(papers):
        save_papers(new_papers)
        return True
    return False


def search_papers(
    keyword: str = "",
    domain: str = "",
    study_type: str = "",
    evidence_level: str = "",
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    inclusion_decision: str = "",
    min_quality: Optional[float] = None,
    min_relevance: Optional[float] = None,
) -> list[dict]:
    papers = load_papers()
    results = papers

    if keyword:
        kw = keyword.lower()
        results = [
            p for p in results
            if kw in (p.get("title", "") + p.get("abstract", "") + p.get("keywords", "")).lower()
            or any(kw in k.lower() for k in p.get("keywords", []))
        ]
    if domain:
        results = [p for p in results if p.get("research_domain") == domain]
    if study_type:
        results = [p for p in results if p.get("study_type") == study_type]
    if evidence_level:
        results = [p for p in results if p.get("evidence_level") == evidence_level]
    if year_from is not None:
        results = [p for p in results if int(p.get("year") or 0) >= year_from]
    if year_to is not None:
        results = [p for p in results if int(p.get("year") or 0) <= year_to]
    if inclusion_decision:
        results = [p for p in results if p.get("inclusion_decision") == inclusion_decision]
    if min_quality is not None:
        results = [p for p in results if float(p.get("quality_score") or 0) >= min_quality]
    if min_relevance is not None:
        results = [p for p in results if float(p.get("relevance_score") or 0) >= min_relevance]

    return results


def load_screening_decisions() -> list[dict]:
    return safe_load_json(SCREENING_DECISIONS_JSON, default=[])


def save_screening_decision(decision: dict):
    decisions = load_screening_decisions()
    decision["timestamp"] = datetime.now().isoformat()
    decisions.append(decision)
    safe_save_json(decisions, SCREENING_DECISIONS_JSON)


def get_statistics() -> dict:
    papers = load_papers()
    total = len(papers)
    included = len([p for p in papers if p.get("inclusion_decision") == "include"])
    excluded = len([p for p in papers if p.get("inclusion_decision") == "exclude"])
    maybe = len([p for p in papers if p.get("inclusion_decision") == "maybe"])
    by_domain = {}
    for p in papers:
        d = p.get("research_domain", "unknown")
        by_domain[d] = by_domain.get(d, 0) + 1
    by_type = {}
    for p in papers:
        t = p.get("study_type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1
    by_evidence = {}
    for p in papers:
        e = p.get("evidence_level", "unknown")
        by_evidence[e] = by_evidence.get(e, 0) + 1
    return {
        "total_papers": total,
        "included": included,
        "excluded": excluded,
        "maybe": maybe,
        "by_domain": by_domain,
        "by_study_type": by_type,
        "by_evidence_level": by_evidence,
    }
