"""Title/abstract relevance evaluator — strict concept-level matching.

Evaluates whether a paper's title and abstract contain the user's core
research concepts. Produces a transparent, auditable relevance score
with mandatory/exclusion term logic and human-readable decision reasons.
"""

import re
from typing import Optional

from src.utils import logger


def evaluate_title_abstract_relevance(
    query_context: dict,
    title: str,
    abstract: str,
    publication_type: str = "",
    journal: str = "",
) -> dict:
    """Evaluate paper relevance with strict title/abstract concept matching.

    Args:
        query_context: Output from query_understanding.understand_topic().
                       Must contain pico, mandatory_terms, optional_terms, exclusion_terms.
        title: Paper title (English)
        abstract: Paper abstract (English)
        publication_type: Optional publication type string
        journal: Optional journal name

    Returns:
        Dict with all relevance component scores, matched/missing terms,
        exclusion findings, final label, and human-readable decision reason.
    """
    title_lower = (title or "").lower()
    abstract_lower = (abstract or "").lower()
    has_abstract = bool(abstract and abstract.strip())

    pico = query_context.get("pico", {})
    mandatory_terms = query_context.get("mandatory_terms", [])
    optional_terms = query_context.get("optional_terms", [])
    exclusion_terms = query_context.get("exclusion_terms", [])

    # ── 1. Term matching per PICO dimension ──
    dimension_matches = {}
    for dim_key, dim_label in [
        ("population", "population"),
        ("intervention_or_exposure", "intervention"),
        ("outcomes", "outcomes"),
        ("comparator", "comparator"),
        ("context", "context"),
    ]:
        comp = pico.get(dim_key, {})
        if not isinstance(comp, dict):
            comp = {}
        search_terms = comp.get("english_terms", [])
        if isinstance(search_terms, str):
            search_terms = [search_terms]
        is_required = comp.get("required", False)

        title_matches, abstract_matches = _find_term_matches(
            search_terms, title_lower, abstract_lower
        )

        dimension_matches[dim_key] = {
            "label": dim_label,
            "search_terms": search_terms,
            "required": is_required,
            "title_matches": title_matches,
            "abstract_matches": abstract_matches,
            "all_matches": list(set(title_matches + abstract_matches)),
        }

    # ── 2. Title relevance score ──
    title_score, title_detail = _score_title(title_lower, dimension_matches, mandatory_terms)

    # ── 3. Abstract relevance score ──
    abstract_score, abstract_detail = _score_abstract(
        abstract_lower, has_abstract, dimension_matches, mandatory_terms, title_detail
    )

    # ── 4. PICO coverage score ──
    pico_score, pico_detail = _score_pico_coverage(dimension_matches)

    # ── 5. Mandatory coverage score ──
    mandatory_score, mandatory_matched, mandatory_missing = _score_mandatory(
        mandatory_terms, title_lower, abstract_lower
    )

    # ── 6. Exclusion check ──
    exclusion_found, exclusion_penalty, exclusion_detail = _check_exclusion(
        exclusion_terms, title_lower, abstract_lower
    )

    # ── 7. Final composite score ──
    # Weights: title 30%, abstract 25%, PICO coverage 25%, mandatory 20%
    final_raw = (
        0.30 * title_score +
        0.25 * abstract_score +
        0.25 * pico_score +
        0.20 * mandatory_score * 10  # mandatory_score is 0-1, scale to 0-10
    )

    # Apply exclusion penalty
    final_raw = max(0, final_raw - exclusion_penalty)

    # ── 8. Decision logic ──
    interv_required = dimension_matches.get("intervention_or_exposure", {}).get("required", True)
    interv_matched = dimension_matches.get("intervention_or_exposure", {}).get("all_matches", [])
    pop_required = dimension_matches.get("population", {}).get("required", False)
    pop_matched = dimension_matches.get("population", {}).get("all_matches", [])
    outcome_required = dimension_matches.get("outcomes", {}).get("required", False)
    outcome_matched = dimension_matches.get("outcomes", {}).get("all_matches", [])

    core_in_title = len(title_detail.get("mandatory_in_title", [])) >= 1
    core_in_abstract = len(abstract_detail.get("mandatory_in_abstract", [])) >= 1
    interv_in_title_or_ab = bool(
        dimension_matches.get("intervention_or_exposure", {}).get("title_matches", []) or
        dimension_matches.get("intervention_or_exposure", {}).get("abstract_matches", [])
    )

    relevance_label, decision_reason = _make_decision(
        final_raw=final_raw,
        mandatory_score=mandatory_score,
        title_score=title_score,
        abstract_score=abstract_score,
        exclusion_found=exclusion_found,
        exclusion_detail=exclusion_detail,
        core_in_title=core_in_title,
        core_in_abstract=core_in_abstract,
        interv_required=interv_required,
        interv_matched=interv_matched,
        pop_required=pop_required,
        pop_matched=pop_matched,
        outcome_required=outcome_required,
        outcome_matched=outcome_matched,
        interv_in_title_or_ab=interv_in_title_or_ab,
        has_abstract=has_abstract,
        mandatory_missing=mandatory_missing,
        dimension_matches=dimension_matches,
    )

    return {
        "title_relevance_score": title_score,
        "abstract_relevance_score": abstract_score,
        "pico_coverage_score": pico_score,
        "mandatory_coverage_score": mandatory_score,
        "exclusion_penalty": exclusion_penalty,
        "final_relevance_score": round(final_raw, 1),
        "relevance_label": relevance_label,
        "matched_terms": {
            "population": dimension_matches.get("population", {}).get("all_matches", []),
            "intervention_or_exposure": dimension_matches.get("intervention_or_exposure", {}).get("all_matches", []),
            "comparator": dimension_matches.get("comparator", {}).get("all_matches", []),
            "outcomes": dimension_matches.get("outcomes", {}).get("all_matches", []),
            "context": dimension_matches.get("context", {}).get("all_matches", []),
        },
        "missing_required_concepts": mandatory_missing,
        "exclusion_terms_found": exclusion_found,
        "decision_reason": decision_reason,
    }


# ── Internal helpers ─────────────────────────────────────────────────

def _word_boundary_match(term: str, text: str) -> bool:
    """Check if term appears in text as a whole word/phrase (not substring of a larger word).

    For single-word terms, allows trailing common suffixes (plurals: -s, -es, -'s)
    to match naturally inflected forms (e.g. "rat" matches "rats" but not "rationale").
    """
    term_lower = term.lower().strip()
    if not term_lower:
        return False
    if ' ' in term_lower or '-' in term_lower:
        return term_lower in text
    else:
        # Match term at word boundary, optionally followed by common suffixes
        # but NOT followed by letters that'd make it part of a longer word
        escaped = re.escape(term_lower)
        # Allow trailing: plural -s, -es, possessive -'s, nothing else alphabetic
        pattern = r'(?<![a-z])' + escaped + r"(?:s|es|'s)?(?![a-z])"
        return bool(re.search(pattern, text))


def _find_term_matches(terms: list[str], title: str, abstract: str) -> tuple[list[str], list[str]]:
    """Find which terms appear in title and abstract (word-boundary matching)."""
    title_matches = []
    abstract_matches = []
    for term in terms:
        term_lower = term.lower().strip()
        if not term_lower:
            continue
        if _word_boundary_match(term_lower, title):
            title_matches.append(term)
        if _word_boundary_match(term_lower, abstract):
            abstract_matches.append(term)
    return title_matches, abstract_matches


def _score_title(title: str, dim_matches: dict, mandatory: list[str]) -> tuple[float, dict]:
    """Score title relevance (0-10)."""
    detail = {"mandatory_in_title": [], "matched_concepts": [], "score_breakdown": ""}

    # Check which mandatory terms appear in title
    for mt in mandatory:
        if _word_boundary_match(mt, title):
            detail["mandatory_in_title"].append(mt)

    # Count how many PICO dimensions have at least one term in title
    dims_in_title = []
    for dim_key, dim_data in dim_matches.items():
        if dim_data.get("title_matches"):
            dims_in_title.append(dim_key)
            detail["matched_concepts"].append({
                "dimension": dim_data["label"],
                "terms": dim_data["title_matches"],
            })

    # Scoring
    mandatory_count = len(detail["mandatory_in_title"])
    total_mandatory = max(len(mandatory), 1)
    mandatory_ratio = mandatory_count / total_mandatory

    if mandatory_count == 0:
        # No mandatory terms in title at all
        score = 0.0
        detail["score_breakdown"] = "标题中未出现任何核心概念词"
    elif mandatory_ratio >= 0.6 and len(dims_in_title) >= 2:
        score = 8.0 + mandatory_ratio * 2
        detail["score_breakdown"] = f"标题高度匹配：{mandatory_count}/{total_mandatory} 核心词，覆盖 {len(dims_in_title)} 个PICO维度"
    elif mandatory_ratio >= 0.3 or len(dims_in_title) >= 1:
        score = 4.0 + mandatory_ratio * 5
        detail["score_breakdown"] = f"标题部分匹配：{mandatory_count}/{total_mandatory} 核心词"
    else:
        score = max(1.0, mandatory_ratio * 5)
        detail["score_breakdown"] = f"标题弱匹配：仅 {mandatory_count}/{total_mandatory} 核心词"

    return round(min(10, score), 1), detail


def _score_abstract(abstract: str, has_abstract: bool, dim_matches: dict,
                    mandatory: list[str], title_detail: dict) -> tuple[float, dict]:
    """Score abstract relevance (0-10)."""
    detail = {"mandatory_in_abstract": [], "matched_concepts": [], "score_breakdown": ""}

    if not has_abstract:
        return 3.0, {"score_breakdown": "摘要缺失，无法评估", "mandatory_in_abstract": [], "matched_concepts": []}

    for mt in mandatory:
        if _word_boundary_match(mt, abstract):
            detail["mandatory_in_abstract"].append(mt)

    dims_in_abstract = []
    for dim_key, dim_data in dim_matches.items():
        if dim_data.get("abstract_matches"):
            dims_in_abstract.append(dim_key)
            detail["matched_concepts"].append({
                "dimension": dim_data["label"],
                "terms": dim_data["abstract_matches"],
            })

    mandatory_count = len(detail["mandatory_in_abstract"])
    total_mandatory = max(len(mandatory), 1)
    mandatory_ratio = mandatory_count / total_mandatory

    if mandatory_ratio >= 0.6 and len(dims_in_abstract) >= 2:
        score = 7.0 + mandatory_ratio * 3
        detail["score_breakdown"] = f"摘要高度匹配：{mandatory_count}/{total_mandatory} 核心词"
    elif mandatory_ratio >= 0.3:
        score = 4.0 + mandatory_ratio * 6
        detail["score_breakdown"] = f"摘要部分匹配：{mandatory_count}/{total_mandatory} 核心词"
    elif dims_in_abstract:
        score = 3.0 + len(dims_in_abstract) * 1.5
        detail["score_breakdown"] = f"摘要弱匹配：仅覆盖 {len(dims_in_abstract)} 个PICO维度，缺少核心词"
    else:
        score = 1.0
        detail["score_breakdown"] = "摘要中未出现任何核心概念词"

    return round(min(10, score), 1), detail


def _score_pico_coverage(dim_matches: dict) -> tuple[float, dict]:
    """Score PICO coverage: how many PICO dimensions have at least one matched term."""
    detail = {"covered_dimensions": [], "uncovered_required": []}

    dimension_weights = {
        "population": 2.0,
        "intervention_or_exposure": 3.0,
        "comparator": 1.0,
        "outcomes": 3.0,
        "context": 1.0,
    }

    total = 0.0
    for dim_key, weight in dimension_weights.items():
        dim = dim_matches.get(dim_key, {})
        match_count = len(dim.get("all_matches", []))
        if match_count > 0:
            detail["covered_dimensions"].append(dim_key)
            total += weight
        elif dim.get("required"):
            detail["uncovered_required"].append(dim_key)

    return round(total, 1), detail


def _score_mandatory(mandatory: list[str], title: str, abstract: str) -> tuple[float, list[str], list[str]]:
    """Score mandatory term coverage (0.0-1.0)."""
    if not mandatory:
        return 1.0, [], []

    matched = []
    missing = []
    search_text = f"{title} {abstract}"

    for mt in mandatory:
        if _word_boundary_match(mt, search_text):
            matched.append(mt)
        else:
            missing.append(mt)

    return round(len(matched) / len(mandatory), 2), matched, missing


def _check_exclusion(exclusion: list[str], title: str, abstract: str) -> tuple[list[str], float, str]:
    """Check for exclusion terms in title/abstract (word-boundary matching) and compute penalty."""
    found = []
    search_text = f"{title} {abstract}"
    for et in exclusion:
        if _word_boundary_match(et, search_text):
            found.append(et)

    if not found:
        return [], 0.0, ""

    # Penalty scales with number of exclusion terms found
    penalty = min(8.0, len(found) * 2.0)
    detail = f"发现排除词: {', '.join(found)} (罚分: -{penalty})"
    return found, penalty, detail


def _make_decision(
    final_raw: float,
    mandatory_score: float,
    title_score: float,
    abstract_score: float,
    exclusion_found: list[str],
    exclusion_detail: str,
    core_in_title: bool,
    core_in_abstract: bool,
    interv_required: bool,
    interv_matched: list[str],
    pop_required: bool,
    pop_matched: list[str],
    outcome_required: bool,
    outcome_matched: list[str],
    interv_in_title_or_ab: bool,
    has_abstract: bool,
    mandatory_missing: list[str],
    dimension_matches: dict,
) -> tuple[str, str]:
    """Apply decision rules to produce final relevance label and reason."""
    reasons = []
    label = "low"

    # ── Exclusion: immediate exclude ──
    if exclusion_found:
        label = "exclude"
        reasons.append(f"排除：{exclusion_detail}")
        if not has_abstract:
            reasons.append("摘要缺失，无法进一步评估")
        return label, " | ".join(reasons) if reasons else ""

    # ── Critical: intervention not found at all ──
    if interv_required and not interv_in_title_or_ab:
        label = "exclude"
        reasons.append("排除：标题和摘要中均未找到核心干预/暴露概念")
        if mandatory_missing:
            reasons.append(f"缺失核心词: {', '.join(mandatory_missing)}")
        return label, " | ".join(reasons)

    # ── Required population not found ──
    if pop_required and not pop_matched:
        reasons.append(f"降级：未找到核心人群概念 '{', '.join(dimension_matches.get('population', {}).get('search_terms', []))}'")

    # ── Required outcome not found ──
    if outcome_required and not outcome_matched:
        reasons.append(f"降级：未找到核心结局概念 '{', '.join(dimension_matches.get('outcomes', {}).get('search_terms', []))}'")

    # ── High relevance ──
    if (final_raw >= 8.0
            and mandatory_score >= 0.8
            and (core_in_title or core_in_abstract)
            and interv_in_title_or_ab):
        label = "high"
        reasons.insert(0, f"高度相关：评分 {final_raw}/10，核心词覆盖率 {mandatory_score:.0%}")

    # ── Moderate relevance ──
    elif (final_raw >= 6.0
            and mandatory_score >= 0.5
            and interv_in_title_or_ab):
        label = "moderate"
        reasons.insert(0, f"中等相关：评分 {final_raw}/10，核心词覆盖率 {mandatory_score:.0%}")

    # ── Low relevance ──
    elif final_raw >= 3.0:
        label = "low"
        reasons.insert(0, f"低相关：评分 {final_raw}/10")

    # ── Exclude ──
    else:
        label = "exclude"
        reasons.insert(0, f"排除：评分 {final_raw}/10，严重不相关")

    # ── Build detailed reason ──
    if label in ("high", "moderate"):
        # Add what was matched
        dim_names = {
            "population": "人群", "intervention_or_exposure": "干预/暴露",
            "outcomes": "结局", "comparator": "对照",
        }
        matched_dims = []
        for dim_key, cn_name in dim_names.items():
            dm = dimension_matches.get(dim_key, {})
            if dm.get("all_matches"):
                matched_dims.append(f"{cn_name}({', '.join(dm['all_matches'][:3])})")
        if matched_dims:
            reasons.append(f"匹配维度: {'; '.join(matched_dims)}")

        if title_score >= 7:
            reasons.append("标题中明确包含核心概念")
        if abstract_score >= 7:
            reasons.append("摘要中明确包含核心概念")

        if mandatory_missing:
            reasons.append(f"未匹配核心词: {', '.join(mandatory_missing)}")
    else:
        # Low/exclude: explain why
        if title_score < 3 and not core_in_title:
            reasons.append("标题未体现核心概念")
        if abstract_score < 3 and has_abstract:
            reasons.append("摘要未体现核心概念")
        if mandatory_missing:
            reasons.append(f"缺失核心概念: {', '.join(mandatory_missing)}")
        if not interv_in_title_or_ab:
            reasons.append("干预/暴露完全缺失")

    return label, " | ".join(reasons) if reasons else "无法确定相关性"
