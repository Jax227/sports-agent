"""Paper quality scorer — compute overall weighted quality score with full transparency."""

from src.utils import logger


def compute_overall_score(journal_result: dict, design_result: dict,
                           statistics_result: dict, relevance_result: dict,
                           bias_result: dict) -> dict:
    """Compute overall quality score using transparent weighted formula.

    If journal_score is available (from verified local rankings):
        overall = 0.15*journal + 0.25*design + 0.25*statistics +
                  0.20*relevance + 0.10*bias + 0.05*reporting

    If journal_score is NOT available:
        overall = 0.30*design + 0.30*statistics + 0.25*relevance +
                  0.10*bias + 0.05*reporting
        (weights redistribute, and a note is added about missing journal data)

    Args:
        journal_result: Output from journal_ranker.match_journal()
        design_result: Output from study_design_evaluator.evaluate_design()
        statistics_result: Output from statistics_evaluator.evaluate_statistics()
        relevance_result: Output from relevance_evaluator.evaluate_relevance()
        bias_result: Output from bias_evaluator.evaluate_bias()

    Returns:
        Dict with overall score, component scores, recommendation, and reasoning.
    """
    journal_score = journal_result.get("journal_score")
    design_score = design_result.get("design_score", 0) or 0
    statistics_score = statistics_result.get("statistics_score", 0) or 0
    relevance_score = relevance_result.get("relevance_score", 0) or 0

    # Risk of bias score (convert bias level to numeric)
    bias_level = bias_result.get("risk_of_bias", "unclear")
    bias_score_map = {"low": 9.0, "some_concerns": 6.0, "high": 3.0, "unclear": 3.0}
    risk_of_bias_score = bias_score_map.get(bias_level, 3.0)

    # Reporting quality score (based on metadata completeness)
    reporting_quality_score = _estimate_reporting_quality(design_result, statistics_result)

    # Determine weights based on journal_score availability
    if journal_score is not None:
        # Weighted formula WITH journal factor
        weights = {
            "journal_score": 0.15,
            "design_score": 0.25,
            "statistics_score": 0.25,
            "relevance_score": 0.20,
            "risk_of_bias_score": 0.10,
            "reporting_quality_score": 0.05,
        }
        journal_note = ""
    else:
        # Redistribute weights WITHOUT journal factor
        weights = {
            "journal_score": 0,
            "design_score": 0.30,
            "statistics_score": 0.30,
            "relevance_score": 0.25,
            "risk_of_bias_score": 0.10,
            "reporting_quality_score": 0.05,
        }
        journal_note = "期刊分区缺失，综合评分未纳入期刊分区因素，需人工核验。"

    overall = (
        weights["journal_score"] * (journal_score or 0) +
        weights["design_score"] * design_score +
        weights["statistics_score"] * statistics_score +
        weights["relevance_score"] * relevance_score +
        weights["risk_of_bias_score"] * risk_of_bias_score +
        weights["reporting_quality_score"] * reporting_quality_score
    )
    overall = round(min(10, overall), 1)

    # Confidence in appraisal
    confidence = _determine_confidence(journal_result, design_result,
                                        statistics_result, bias_result)

    # Recommendation
    recommendation, rec_reason = _determine_recommendation(
        overall, relevance_score, risk_of_bias_score, bias_level,
        journal_result, design_result, statistics_result
    )

    # Missing information
    missing_info = _identify_missing_info(journal_result, design_result,
                                           statistics_result, bias_result)

    return {
        "journal_score": journal_score,
        "design_score": design_score,
        "statistics_score": statistics_score,
        "relevance_score": relevance_score,
        "risk_of_bias_score": risk_of_bias_score,
        "reporting_quality_score": reporting_quality_score,
        "overall_quality_score": overall,
        "weights_used": weights,
        "journal_note": journal_note,
        "confidence_in_appraisal": confidence["level"],
        "confidence_reasons": confidence["reasons"],
        "recommendation": recommendation,
        "recommendation_reason": rec_reason,
        "missing_information": missing_info,
    }


def _estimate_reporting_quality(design_result: dict, statistics_result: dict) -> float:
    """Estimate reporting quality score (0-10) from available metadata."""
    score = 5.0  # Neutral start

    # Check if study type is identified
    if design_result.get("study_type_confidence", 0) >= 0.7:
        score += 1.0
    elif design_result.get("study_type_confidence", 0) >= 0.4:
        score += 0.5

    # Check if design evaluation has substantive information
    if len(design_result.get("design_strengths", [])) > 1:
        score += 0.5
    if len(design_result.get("design_limitations", [])) > 1:
        score += 0.5

    # Statistics reporting
    stats = statistics_result
    if stats.get("effect_size_reported") == "是":
        score += 1.0
    if stats.get("confidence_interval_reported") == "是":
        score += 0.5
    if stats.get("sample_size_calculation") == "是":
        score += 0.5
    if stats.get("statistical_tests") and len(stats["statistical_tests"]) > 0:
        score += 0.5

    # Review level penalty
    if statistics_result.get("statistics_review_level") == "metadata_only":
        score -= 1.0

    return max(0, min(10, round(score, 1)))


def _determine_confidence(journal_result: dict, design_result: dict,
                           statistics_result: dict, bias_result: dict) -> dict:
    """Determine confidence in the automated appraisal."""
    factors = []
    conf_score = 5.0

    # Journal match confidence
    if journal_result.get("journal_match_confidence", 0) >= 0.9:
        conf_score += 1.0
        factors.append("期刊匹配置信度高")
    elif journal_result.get("journal_match_confidence", 0) >= 0.6:
        factors.append("期刊匹配存在一定不确定性")

    # Study type confidence
    if design_result.get("study_type_confidence", 0) >= 0.7:
        conf_score += 1.0
        factors.append("研究类型识别置信度高")
    else:
        factors.append("研究类型识别置信度较低")

    # Statistics review level
    if statistics_result.get("statistics_review_level") == "full_text":
        conf_score += 1.5
        factors.append("统计评价基于全文信息")
    elif statistics_result.get("statistics_review_level") == "abstract_only":
        conf_score += 0.5
        factors.append("统计评价仅限于摘要信息")
    else:
        factors.append("统计评价信息不足")

    # Bias assessment
    if bias_result.get("risk_of_bias") != "unclear":
        factors.append("偏倚风险可初步判断")
    else:
        factors.append("偏倚风险无法判断")

    if conf_score >= 7:
        level = "high"
    elif conf_score >= 5:
        level = "moderate"
    else:
        level = "low"

    return {"level": level, "reasons": factors}


def _determine_recommendation(overall: float, relevance: float,
                               bias_score: float, bias_level: str,
                               journal_result: dict,
                               design_result: dict,
                               statistics_result: dict) -> tuple:
    """Determine recommendation: include / maybe / exclude / manual_review."""
    reasons = []

    # Check for missing critical info
    journal_missing = journal_result.get("journal_score") is None
    stats_review_level = statistics_result.get("statistics_review_level", "")

    needs_manual_review = (
        journal_missing or
        stats_review_level == "metadata_only" or
        bias_level == "unclear" or
        design_result.get("study_type_confidence", 0) < 0.4
    )

    if overall >= 8 and relevance >= 7 and bias_level not in ("high",):
        recommendation = "include"
        reasons.append(f"综合评分高 ({overall}/10)，相关性良好 ({relevance}/10)，偏倚风险可接受")
    elif overall >= 6 and relevance >= 5:
        if needs_manual_review:
            recommendation = "manual_review"
            reasons.append(f"综合评分中等 ({overall}/10)，但关键信息缺失需人工审核")
        else:
            recommendation = "maybe"
            reasons.append(f"综合评分中等 ({overall}/10)，建议根据全文进一步判断")
    elif overall >= 4 and relevance >= 4:
        recommendation = "maybe"
        reasons.append(f"综合评分较低 ({overall}/10)，但主题相关")
    else:
        recommendation = "exclude"
        if relevance < 4:
            reasons.append(f"主题相关性不足 ({relevance}/10)")
        if overall < 4:
            reasons.append(f"综合评分过低 ({overall}/10)")

    if needs_manual_review and recommendation != "manual_review":
        reasons.append("部分字段信息不足，建议人工复核")

    return recommendation, " | ".join(reasons)


def _identify_missing_info(journal_result: dict, design_result: dict,
                            statistics_result: dict, bias_result: dict) -> list[str]:
    """Identify specific missing information that would improve the appraisal."""
    missing = []

    if journal_result.get("journal_score") is None:
        missing.append("期刊分区信息缺失 — 需查找JCR/中科院分区或人工核验")

    if design_result.get("study_type_confidence", 0) < 0.5:
        missing.append("研究类型未能明确识别 — 需人工确认")

    if statistics_result.get("statistics_review_level") != "full_text":
        missing.append("统计方法评价仅基于摘要 — 需阅读全文进一步完善")

    if statistics_result.get("effect_size_reported") != "是":
        missing.append("效应量未报告 — 需查阅全文或补充材料")

    if statistics_result.get("confidence_interval_reported") != "是":
        missing.append("置信区间未报告 — 需查阅全文")

    if statistics_result.get("sample_size_calculation") != "是":
        missing.append("样本量估算未报告 — 需查阅全文")

    if bias_result.get("risk_of_bias") == "unclear":
        missing.append("偏倚风险无法自动化判断 — 需人工正式评价")

    if not design_result.get("design_strengths") or len(design_result.get("design_strengths", [])) <= 1:
        missing.append("研究设计细节不足 — 建议阅读全文后补充评价")

    return missing if missing else ["基础信息可通过摘要获取，更深入评价需阅读全文"]
