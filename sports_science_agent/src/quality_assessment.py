"""Quality assessment — detailed evaluation of papers."""

from src.config import EVIDENCE_LEVELS, RISK_OF_BIAS_LEVELS
from src.utils import logger


def assess_risk_of_bias(paper: dict) -> tuple[str, list[str]]:
    """Assess risk of bias based on study type and available info."""
    study_type = paper.get("study_type", "other")
    concerns = []

    # Common bias domains
    if study_type in ("randomized_controlled_trial", "intervention_study", "experimental"):
        if not paper.get("blinding", ""):
            concerns.append("Blinding not reported")
        if not paper.get("allocation_concealment", ""):
            concerns.append("Allocation concealment not reported")
        if not paper.get("randomization_method", ""):
            concerns.append("Randomization method not described")

    if study_type in ("randomized_controlled_trial", "intervention_study",
                       "prospective_cohort", "cross_sectional"):
        sample_size = paper.get("sample_size", "")
        try:
            n = int(sample_size) if sample_size else 0
            if n < 20:
                concerns.append("Very small sample size (n < 20)")
            elif n < 50:
                concerns.append("Small sample size (n < 50)")
        except (ValueError, TypeError):
            concerns.append("Sample size not reported")

    # Attrition
    if not paper.get("dropout_rate", ""):
        if study_type in ("randomized_controlled_trial", "prospective_cohort"):
            concerns.append("Dropout/attrition not reported")

    # Conflict of interest
    if not paper.get("conflict_of_interest", ""):
        concerns.append("Conflict of interest statement not available")

    # Outcome reporting
    if not paper.get("outcomes", ""):
        concerns.append("Outcomes not clearly reported")
    if not paper.get("main_findings", ""):
        concerns.append("Main findings not clearly reported")

    # Determine level
    num_concerns = len(concerns)
    if num_concerns <= 1:
        level = "low"
    elif num_concerns <= 3:
        level = "some_concerns"
    elif num_concerns <= 5:
        level = "high"
    else:
        level = "unclear"

    return level, concerns


def compute_quality_score(paper: dict) -> dict:
    """Compute detailed quality score (0-10) with component breakdown."""
    components = {}

    # 1. Study design (0-3)
    study_type = paper.get("study_type", "other")
    design_scores = {
        "meta_analysis": 3.0,
        "systematic_review": 2.8,
        "randomized_controlled_trial": 2.8,
        "guideline_consensus": 2.5,
        "prospective_cohort": 2.0,
        "experimental": 2.0,
        "intervention_study": 2.0,
        "non_randomized_trial": 1.5,
        "cross_sectional": 1.0,
        "narrative_review": 1.0,
        "case_study": 0.5,
        "conference_abstract": 0.3,
        "preprint": 0.5,
        "opinion": 0.2,
        "other": 1.0,
    }
    components["study_design"] = design_scores.get(study_type, 1.0)

    # 2. Sample size and population (0-2)
    sample_score = 0
    sample_size = paper.get("sample_size", "")
    try:
        n = int(sample_size) if sample_size else 0
        if n >= 500:
            sample_score = 2.0
        elif n >= 100:
            sample_score = 1.5
        elif n >= 50:
            sample_score = 1.0
        elif n >= 20:
            sample_score = 0.5
    except (ValueError, TypeError):
        pass
    # Reviews without sample size can still score if they have many references
    if study_type in ("systematic_review", "meta_analysis"):
        refs = paper.get("references_count", 0)
        try:
            r = int(refs)
            if r >= 50:
                sample_score = max(sample_score, 2.0)
            elif r >= 20:
                sample_score = max(sample_score, 1.5)
        except (ValueError, TypeError):
            pass
    components["sample_population"] = sample_score

    # 3. Methodological rigor (0-2)
    method_score = 1.0  # Default average
    if paper.get("randomization_method", ""):
        method_score += 0.3
    if paper.get("blinding", ""):
        method_score += 0.3
    if paper.get("allocation_concealment", ""):
        method_score += 0.2
    if paper.get("statistical_method", ""):
        method_score += 0.2
    components["method_rigor"] = min(2.0, method_score)

    # 4. Reporting completeness (0-1.5)
    report_score = 0.5
    if paper.get("outcomes", ""):
        report_score += 0.3
    if paper.get("main_findings", ""):
        report_score += 0.3
    if paper.get("limitations", ""):
        report_score += 0.2
    if paper.get("conflict_of_interest", ""):
        report_score += 0.2
    components["reporting"] = min(1.5, report_score)

    # 5. Source credibility (0-1.5)
    source_score = 0.5
    journal = paper.get("journal", "")
    # Known high-impact journals get bonus
    high_impact = [
        "sports medicine", "british journal of sports medicine", "medicine and science in sports and exercise",
        "journal of strength and conditioning research", "european journal of applied physiology",
        "international journal of sports physiology and performance", "scandinavian journal of medicine",
        "american journal of sports medicine", "journal of applied physiology", "sports",
        "frontiers in physiology", "frontiers in sports", "journal of sports sciences",
        "plos one", "peerj", "scientific reports",
    ]
    if any(j in journal.lower() for j in high_impact):
        source_score += 0.7

    if paper.get("peer_reviewed", True) is not False:  # Default assume peer-reviewed
        source_score += 0.3

    components["source_credibility"] = min(1.5, source_score)

    total = sum(components.values())
    return {
        "quality_score": round(min(10, total), 1),
        "components": components,
    }


def full_quality_assessment(paper: dict) -> dict:
    """Run a full quality assessment and return enriched paper dict."""
    risk_level, concerns = assess_risk_of_bias(paper)
    quality_result = compute_quality_score(paper)

    assessment = {
        "risk_of_bias": risk_level,
        "risk_of_bias_concerns": concerns,
        "quality_score": quality_result["quality_score"],
        "quality_components": quality_result["components"],
    }

    # Update paper with assessment
    paper.update(assessment)
    return paper
