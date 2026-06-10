"""Relevance evaluator — assess PICO match between paper and user research topic."""

import re
from src.utils import logger


def evaluate_relevance(paper: dict, user_pico: dict) -> dict:
    """Evaluate paper relevance to the user's research topic via PICO matching.

    Args:
        paper: Paper metadata dict
        user_pico: PICO decomposition from the user's research topic

    Returns:
        Dict with relevance_score (0-10), PICO match details, and reasoning.
    """
    title = (paper.get("title", "") or "").lower()
    abstract = (paper.get("abstract", "") or "").lower()
    keywords = paper.get("keywords", [])
    if isinstance(keywords, str):
        keywords = [k.strip().lower() for k in keywords.split(";")]
    keywords = [k.lower() for k in keywords if k]

    search_text = f"{title} {abstract[:2000]} {' '.join(keywords)}"

    # PICO matching
    pop_match = _match_component(search_text, user_pico.get("population", ""), "population")
    interv_match = _match_component(search_text, user_pico.get("intervention_or_exposure", ""), "intervention")
    comp_match = _match_component(search_text, user_pico.get("comparator", ""), "comparator")
    outcome_match = _match_component(search_text, user_pico.get("outcomes", ""), "outcome")
    design_match = _match_design_preference(paper, user_pico.get("study_design_preference", ""))

    # Calculate relevance score
    # Population and intervention are most important
    weights = {
        "population": 0.30,
        "intervention": 0.35,
        "outcome": 0.25,
        "design": 0.10,
    }

    score = (
        weights["population"] * pop_match["score"] +
        weights["intervention"] * interv_match["score"] +
        weights["outcome"] * outcome_match["score"] +
        weights["design"] * design_match["score"]
    )
    score = round(score, 1)

    # Build reasoning
    reasons = []
    for match_info in [pop_match, interv_match, outcome_match, design_match]:
        if match_info.get("reason"):
            reasons.append(match_info["reason"])

    if score >= 8:
        overall = "文献与用户研究主题高度相关"
    elif score >= 6:
        overall = "文献与用户研究主题部分相关"
    elif score >= 4:
        overall = "文献与用户研究主题相关性较低"
    else:
        overall = "文献与用户研究主题基本不相关"

    return {
        "relevance_score": score,
        "pico_match": {
            "population_match": pop_match["level"],
            "intervention_match": interv_match["level"],
            "comparator_match": comp_match["level"],
            "outcome_match": outcome_match["level"],
            "study_design_match": design_match["level"],
        },
        "relevance_reason": " | ".join(reasons) if reasons else overall,
    }


def _match_component(text: str, query: str, component_name: str) -> dict:
    """Match a single PICO component against paper text.

    Returns dict with score (0-10) and match level description.
    """
    if not query or len(query.strip()) < 2:
        return {
            "score": 5.0,
            "level": f"用户未指定{component_name}，无法评估匹配度",
            "reason": "",
        }

    # Tokenize query into meaningful terms
    query_terms = _extract_significant_terms(query)
    if not query_terms:
        return {"score": 5.0, "level": f"{component_name}搜索词不明确", "reason": ""}

    # Count matches
    matched = []
    for term in query_terms:
        if term.lower() in text:
            matched.append(term)

    match_ratio = len(matched) / max(len(query_terms), 1)

    # Score
    if match_ratio >= 0.8:
        score = 9.0 + match_ratio
        level = f"{component_name}: 高度匹配 ({len(matched)}/{len(query_terms)} terms)"
    elif match_ratio >= 0.5:
        score = 6.0 + match_ratio * 4
        level = f"{component_name}: 部分匹配 ({len(matched)}/{len(query_terms)} terms)"
    elif match_ratio >= 0.25:
        score = 3.0 + match_ratio * 6
        level = f"{component_name}: 弱匹配 ({len(matched)}/{len(query_terms)} terms)"
    else:
        score = max(0, match_ratio * 10)
        level = f"{component_name}: 基本不匹配 ({len(matched)}/{len(query_terms)} terms)"

    reason = ""
    if matched:
        reason = f"匹配到的{component_name}术语: {', '.join(matched[:5])}"
    else:
        reason = f"文献中未找到{component_name}相关术语"

    return {"score": min(10, round(score, 1)), "level": level, "reason": reason}


def _match_design_preference(paper: dict, preference: str) -> dict:
    """Check if paper study type matches user design preference."""
    if not preference:
        return {"score": 5.0, "level": "用户未指定优先研究设计", "reason": ""}

    study_type = paper.get("study_type", "unknown")
    pub_types = paper.get("publication_type", [])
    if isinstance(pub_types, str):
        pub_types = [pub_types]

    # Check publication type match
    pref_lower = preference.lower()
    type_keywords = {
        "rct": ["randomized_controlled_trial", "cluster_randomized_trial", "crossover_trial"],
        "randomized": ["randomized_controlled_trial", "cluster_randomized_trial", "crossover_trial"],
        "systematic review": ["systematic_review", "systematic_review_with_meta_analysis"],
        "meta-analysis": ["meta_analysis", "systematic_review_with_meta_analysis"],
        "meta analysis": ["meta_analysis", "systematic_review_with_meta_analysis"],
        "cohort": ["cohort_study", "prospective_cohort"],
        "clinical trial": ["randomized_controlled_trial", "clinical_trial"],
        "observational": ["cohort_study", "case_control_study", "cross_sectional_study"],
    }

    matched_types = []
    for pref, types in type_keywords.items():
        if pref in pref_lower:
            matched_types.extend(types)

    if study_type in matched_types:
        return {"score": 10.0, "level": "研究设计类型完全匹配用户偏好",
                "reason": f"研究类型 {study_type} 符合偏好 {preference}"}
    elif matched_types:
        return {"score": 5.0, "level": "研究设计类型部分匹配",
                "reason": f"研究类型为 {study_type}，用户偏好包含 {', '.join(matched_types)}"}
    else:
        return {"score": 3.0, "level": "研究设计类型未匹配用户偏好",
                "reason": f"研究类型 {study_type} 不在用户偏好范围 ({preference})"}


def _extract_significant_terms(text: str) -> list[str]:
    """Extract significant search terms from a text string."""
    if not text:
        return []
    # Remove common words and punctuation
    stop_words = {"the", "a", "an", "in", "on", "at", "of", "for", "to", "with",
                  "and", "or", "is", "are", "was", "were", "be", "been", "being",
                  "have", "has", "had", "do", "does", "did", "will", "would",
                  "shall", "should", "may", "might", "must", "can", "could"}
    cleaned = re.sub(r'[,\/\[\]{}()":;.]', ' ', text)
    terms = [t.strip().lower() for t in cleaned.split()
             if len(t.strip()) > 2 and t.strip().lower() not in stop_words]
    # Remove duplicates while preserving order
    seen = set()
    unique = []
    for t in terms:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique[:8]
