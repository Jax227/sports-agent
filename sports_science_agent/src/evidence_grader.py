"""Evidence grader — determine evidence level based on study design and bias."""


def grade_evidence(study_type: str, risk_of_bias: str,
                   study_type_confidence: float = 0) -> dict:
    """Determine evidence level based on study type and risk of bias.

    Follows GRADE-like principles adapted for automated pre-screening.
    Always notes this is preliminary grading, not formal GRADE.

    Returns dict with evidence_level and detailed reasons.
    """
    # Base evidence level from study type
    base_levels = {
        "meta_analysis": "high",
        "systematic_review_with_meta_analysis": "high",
        "systematic_review": "high",
        "randomized_controlled_trial": "high",
        "cluster_randomized_trial": "high",
        "crossover_trial": "high",
        "guideline": "high",
        "expert_consensus": "moderate",
        "non_randomized_controlled_trial": "moderate",
        "prospective_cohort": "moderate",
        "cohort_study": "moderate",
        "intervention_study_unspecified": "moderate",
        "diagnostic_accuracy_study": "moderate",
        "case_control_study": "low",
        "cross_sectional_study": "low",
        "observational_unspecified": "low",
        "narrative_review": "low",
        "mixed_methods_study": "low",
        "qualitative_study": "low",
        "single_arm_trial": "low",
        "case_series": "very_low",
        "case_report": "very_low",
        "study_protocol": "very_low",
        "case_study": "very_low",
        "conference_abstract": "very_low",
        "preprint": "very_low",
        "opinion": "very_low",
        "animal_study": "very_low",
        "in_vitro_study": "very_low",
        "unknown": "very_low",
        "other": "low",
    }
    base_level = base_levels.get(study_type, "very_low")

    reasons = [f"研究类型: {study_type} → 基线证据等级: {base_level}"]

    # Downgrade for bias
    downgrades = 0
    if risk_of_bias == "high":
        downgrades += 2
        reasons.append("偏倚风险高 → 降2级")
    elif risk_of_bias == "some_concerns":
        downgrades += 1
        reasons.append("偏倚风险存在一定担忧 → 降1级")
    elif risk_of_bias == "unclear":
        downgrades += 1
        reasons.append("偏倚风险不明确 → 降1级")

    # Downgrade for low confidence in study type classification
    if study_type_confidence < 0.5:
        downgrades += 1
        reasons.append(f"研究类型识别置信度低 ({study_type_confidence:.0%}) → 降1级")

    # Apply downgrades
    level_order = ["high", "moderate", "low", "very_low"]
    base_idx = level_order.index(base_level)
    final_idx = min(len(level_order) - 1, base_idx + downgrades)
    final_level = level_order[final_idx]

    if downgrades > 0:
        reasons.append(f"最终证据等级: {final_level} (降{downgrades}级)")

    # Upgrade factors (rarely applicable from metadata alone)
    upgrades = 0
    # Large effect could upgrade observational studies
    # Dose-response gradient could upgrade
    # These require full text, so we note them
    if study_type in ("cohort_study", "case_control_study", "cross_sectional_study"):
        reasons.append("若全文显示大效应量或剂量-反应关系，证据等级可升级")

    reasons.append("该证据等级为自动化初步判断，不等同于GRADE正式评价。")
    reasons.append("需人工复核后确定最终证据等级。")

    return {
        "evidence_level": final_level,
        "evidence_level_reasons": reasons,
        "base_level": base_level,
        "downgrade_count": downgrades,
        "upgrade_factors_possible": upgrades > 0 or study_type not in (
            "meta_analysis", "systematic_review_with_meta_analysis",
            "randomized_controlled_trial", "cluster_randomized_trial"
        ),
    }


def grade_certainty(evidence_level: str, consistency: str = "",
                    directness: str = "", precision: str = "",
                    publication_bias_risk: str = "") -> str:
    """Grade certainty of evidence (high/moderate/low/very_low) per GRADE domains.

    This is a simplified GRADE-like assessment based on available metadata.
    Full GRADE requires systematic review of all relevant studies.
    """
    # Start from evidence level
    if evidence_level == "high":
        certainty = "high"
    elif evidence_level == "moderate":
        certainty = "moderate"
    elif evidence_level == "low":
        certainty = "low"
    else:
        return "very_low"

    downgrades = 0

    # Inconsistency
    if consistency == "inconsistent":
        downgrades += 1
    elif consistency == "partially_consistent":
        # Consider downgrading
        pass

    # Indirectness
    if directness == "indirect":
        downgrades += 1

    # Imprecision
    if precision == "imprecise":
        downgrades += 1

    # Publication bias
    if publication_bias_risk == "high":
        downgrades += 1

    levels = ["high", "moderate", "low", "very_low"]
    idx = min(len(levels) - 1, levels.index(certainty) + downgrades)
    return levels[idx]
