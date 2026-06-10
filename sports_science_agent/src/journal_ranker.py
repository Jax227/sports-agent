"""Journal ranker — match journals against local rankings database, never fabricate data."""

import csv
import re
from pathlib import Path
from typing import Optional

from src.config import DATA_DIR
from src.utils import logger


JOURNAL_RANKINGS_CSV = DATA_DIR / "journal_rankings" / "sports_science_journal_rankings.csv"

# Cache for loaded rankings
_rankings_cache: Optional[list[dict]] = None


def _load_rankings() -> list[dict]:
    """Load journal rankings from CSV, with caching."""
    global _rankings_cache
    if _rankings_cache is not None:
        return _rankings_cache

    if not JOURNAL_RANKINGS_CSV.exists():
        logger.warning(f"Journal rankings CSV not found: {JOURNAL_RANKINGS_CSV}")
        _rankings_cache = []
        return _rankings_cache

    rankings = []
    try:
        with open(JOURNAL_RANKINGS_CSV, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rankings.append(row)
        logger.info(f"Loaded {len(rankings)} journal rankings from CSV")
    except Exception as e:
        logger.error(f"Failed to load journal rankings: {e}")
        rankings = []

    _rankings_cache = rankings
    return _rankings_cache


def _reload_rankings():
    """Force reload rankings from disk."""
    global _rankings_cache
    _rankings_cache = None
    return _load_rankings()


def _normalize_journal_name(name: str) -> str:
    """Normalize journal name for matching."""
    if not name:
        return ""
    n = name.lower().strip()
    # Remove "The " prefix
    n = re.sub(r"^the\s+", "", n)
    # Replace & with and
    n = n.replace(" & ", " and ")
    # Remove punctuation for matching
    n = re.sub(r"[.,:;'\"()]", "", n)
    # Normalize whitespace
    n = re.sub(r"\s+", " ", n)
    return n.strip()


def match_journal(journal_name: str, issn: str = "") -> dict:
    """Match a journal name/ISSN against the local rankings database.

    Returns a dict with match status, confidence, and ranking info.
    NEVER fabricates journal data — returns null/empty if not found.

    Args:
        journal_name: Raw journal name from paper metadata
        issn: ISSN if available (higher priority match)

    Returns:
        Dict with match_status, confidence, and ranking fields
    """
    rankings = _load_rankings()

    result = {
        "journal_name": journal_name or "",
        "issn_input": issn or "",
        "journal_match_status": "not_found",
        "journal_match_confidence": 0.0,
        "matched_journal_name": "",
        "jcr_quartile": "",
        "cas_quartile": "",
        "impact_factor": "",
        "impact_factor_year": "",
        "ranking_source": "",
        "publisher": "",
        "last_verified": "",
        "journal_score": None,
        "journal_score_reason": "",
        "journal_rank_status": "未获取，需人工核验",
    }

    if not journal_name and not issn:
        result["journal_score_reason"] = "无期刊名或ISSN可匹配"
        return result

    # ── Priority 1: ISSN exact match ──
    if issn:
        issn_clean = issn.replace("-", "").strip()
        for r in rankings:
            r_issn = (r.get("issn", "") or "").replace("-", "").strip()
            r_eissn = (r.get("eissn", "") or "").replace("-", "").strip()
            if issn_clean == r_issn or issn_clean == r_eissn:
                result.update(_extract_ranking_fields(r, "exact_issn", 1.0))
                return result

    # ── Priority 2: Exact normalized name match ──
    if journal_name:
        norm_input = _normalize_journal_name(journal_name)
        for r in rankings:
            norm_j = _normalize_journal_name(r.get("journal_name", ""))
            norm_n = _normalize_journal_name(r.get("normalized_journal_name", ""))
            if norm_input == norm_j or norm_input == norm_n:
                result.update(_extract_ranking_fields(r, "exact_name", 0.95))
                return result

    # ── Priority 3: Contains match ──
    if journal_name:
        norm_input = _normalize_journal_name(journal_name)
        best_match = None
        best_score = 0
        for r in rankings:
            norm_j = _normalize_journal_name(r.get("journal_name", ""))
            norm_n = _normalize_journal_name(r.get("normalized_journal_name", ""))
            # Check if one contains the other
            if norm_input in norm_j or norm_j in norm_input or \
               norm_input in norm_n or norm_n in norm_input:
                # Score by length ratio
                score = min(len(norm_input), len(norm_j)) / max(len(norm_input), len(norm_j))
                if score > best_score:
                    best_score = score
                    best_match = r

        if best_match and best_score >= 0.6:
            result.update(_extract_ranking_fields(best_match, "fuzzy_name", best_score * 0.9))
            return result

    # ── Priority 4: Word overlap match ──
    if journal_name:
        norm_input = set(_normalize_journal_name(journal_name).split())
        if len(norm_input) >= 2:
            best_match = None
            best_overlap = 0
            for r in rankings:
                norm_j = set(_normalize_journal_name(r.get("journal_name", "")).split())
                norm_n = set(_normalize_journal_name(r.get("normalized_journal_name", "")).split())
                overlap = max(
                    len(norm_input & norm_j) / max(len(norm_input | norm_j), 1),
                    len(norm_input & norm_n) / max(len(norm_input | norm_n), 1),
                )
                if overlap > best_overlap and overlap >= 0.5:
                    best_overlap = overlap
                    best_match = r

            if best_match and best_overlap >= 0.5:
                result.update(_extract_ranking_fields(best_match, "fuzzy_name", best_overlap * 0.8))
                return result

    # ── Not found ──
    result["journal_match_status"] = "not_found"
    result["journal_match_confidence"] = 0.0
    result["journal_score_reason"] = "本地期刊分区表中未找到匹配期刊，需人工核验"
    # Check if it's likely predatory
    if _check_predatory(journal_name or ""):
        result["journal_score"] = 1
        result["journal_score_reason"] = "期刊名匹配到疑似掠夺性期刊特征，建议人工核验。本地分区表中未收录。"
        result["journal_match_status"] = "predatory_suspect"

    return result


def _extract_ranking_fields(ranking_row: dict, match_status: str, confidence: float) -> dict:
    """Extract standardized ranking fields from a CSV row."""
    jcr_q = (ranking_row.get("jcr_quartile", "") or "").strip().upper()
    cas_q = (ranking_row.get("cas_quartile", "") or "").strip().upper()
    if_val = ranking_row.get("impact_factor", "") or ""

    # Calculate journal_score based on JCR quartile
    journal_score = None
    score_reason = ""
    if jcr_q == "Q1":
        journal_score = 9.5
        score_reason = f"JCR Q1 ({ranking_row.get('category', '')})"
    elif jcr_q == "Q2":
        journal_score = 7.5
        score_reason = f"JCR Q2 ({ranking_row.get('category', '')})"
    elif jcr_q == "Q3":
        journal_score = 5.5
        score_reason = f"JCR Q3 ({ranking_row.get('category', '')})"
    elif jcr_q == "Q4":
        journal_score = 3.5
        score_reason = f"JCR Q4 ({ranking_row.get('category', '')})"
    else:
        score_reason = "缺少可验证的期刊分区或影响因子，需人工核验"

    return {
        "journal_match_status": match_status,
        "journal_match_confidence": round(confidence, 2),
        "matched_journal_name": ranking_row.get("journal_name", ""),
        "jcr_quartile": jcr_q or "未获取，需人工核验",
        "cas_quartile": cas_q or "未获取，需人工核验",
        "impact_factor": if_val if if_val else "未获取，需人工核验",
        "impact_factor_year": ranking_row.get("impact_factor_year", "") or "未获取",
        "ranking_source": ranking_row.get("ranking_source", "") or "未获取",
        "publisher": ranking_row.get("publisher", "") or "",
        "last_verified": ranking_row.get("last_verified", "") or "未获取",
        "journal_score": journal_score,
        "journal_score_reason": score_reason,
        "journal_rank_status": "已获取" if journal_score is not None else "未获取，需人工核验",
    }


def _check_predatory(journal_name: str) -> bool:
    """Heuristic check for potentially predatory journal patterns."""
    predatory_patterns = [
        r"international\s+journal\s+of\s+(?:advanced|modern|current|recent|innovative|novel)",
        r"(?:american|european|asian|world)\s+(?:scientific|academic|scholarly)\s+(?:journal|publisher)",
        r"(?:journal|publisher)\s+of\s+(?:advanced|modern|science)\s+and\s+(?:research|technology|engineering)",
        r"(?:omnis|omics)\s+(?:publishing|group)",
    ]
    jl = journal_name.lower()
    return any(re.search(p, jl) for p in predatory_patterns)


def get_all_ranked_journals() -> list[dict]:
    """Get all journals in the local rankings database."""
    return _load_rankings()


def is_sports_science_journal(journal_name: str, issn: str = "") -> bool:
    """Quick check if a journal matches a known sports science journal."""
    result = match_journal(journal_name, issn)
    return result["journal_match_status"] in ("exact_issn", "exact_name", "fuzzy_name")
