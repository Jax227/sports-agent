"""Study design evaluator — rigorous identification and methodological evaluation."""

import re
from typing import Optional

from src.utils import logger


# ── Expanded study type classification ──
STUDY_TYPE_PATTERNS = [
    # Systematic review + meta-analysis
    (r"\bsystematic\s+review\b.*\bmeta[\s-]*analys", "systematic_review_with_meta_analysis"),
    (r"\bmeta[\s-]*analys", "meta_analysis"),
    (r"\bsystematic\s+review\b", "systematic_review"),
    # RCT variants
    (r"\bcluster[\s-]*randomi[sz]ed\s+(?:controlled\s+)?trial\b", "cluster_randomized_trial"),
    (r"\bcross[\s-]*over\s+(?:randomi[sz]ed\s+)?trial\b", "crossover_trial"),
    (r"\brandomi[sz]ed\s+(?:controlled\s+)?trial\b|\bRCT\b", "randomized_controlled_trial"),
    (r"\bnon[\s-]*randomi[sz]ed\s+(?:controlled\s+)?trial\b", "non_randomized_controlled_trial"),
    (r"\bsingle[\s-]*arm\s+trial\b", "single_arm_trial"),
    # Observational
    (r"\b(?:prospective|retrospective)\s+cohort\b|\bcohort\s+study\b", "cohort_study"),
    (r"\bcase[\s-]*control\b", "case_control_study"),
    (r"\bcross[\s-]*sectional\b", "cross_sectional_study"),
    # Case reports
    (r"\bcase\s+series\b", "case_series"),
    (r"\bcase\s+(?:study|report)\b", "case_report"),
    # Other designs
    (r"\bdiagnostic\s+accuracy\b", "diagnostic_accuracy_study"),
    (r"\bqualitative\s+(?:study|research)\b", "qualitative_study"),
    (r"\bmixed[\s-]*methods\b", "mixed_methods_study"),
    (r"\bstudy\s+protocol\b", "study_protocol"),
    (r"\bnarrative\s+review\b|\breview\s+article\b", "narrative_review"),
    (r"\bexpert\s+consensus\b|\bconsensus\s+statement\b", "expert_consensus"),
    (r"\b(?:clinical\s+)?guideline\b|\bposition\s+stand\b", "guideline"),
    # Animal/in vitro
    (r"\banimal\s+(?:study|model|experiment)\b", "animal_study"),
    (r"\bin\s*vitro\b|\bcell\s+(?:culture|line)\b", "in_vitro_study"),
]


def identify_study_type(paper: dict) -> dict:
    """Identify study type with evidence trail.

    Checks publication_type first, then title, then abstract.
    Returns type, confidence, and evidence for the determination.
    """
    title = paper.get("title", "")
    abstract = paper.get("abstract", "") or paper.get("full_text", "")[:3000]
    pub_types = paper.get("publication_type", [])
    keywords = paper.get("keywords", [])
    if isinstance(keywords, str):
        keywords = [kw.strip() for kw in keywords.split(";") if kw.strip()]

    evidence = []
    study_type = "unknown"
    confidence = 0.0

    # ── Layer 1: Publication type from PubMed (highest confidence) ──
    if isinstance(pub_types, list) and pub_types:
        pt_lower = [p.lower() for p in pub_types]
        if any("meta-analysis" in p or "meta analysis" in p for p in pt_lower):
            if any("systematic review" in p for p in pt_lower):
                study_type = "systematic_review_with_meta_analysis"
            else:
                study_type = "meta_analysis"
            confidence = 0.95
            evidence.append(f"依据 PubMed publication_type: {', '.join(pub_types)}")
        elif any("systematic review" in p for p in pt_lower):
            study_type = "systematic_review"
            confidence = 0.90
            evidence.append(f"依据 PubMed publication_type: {', '.join(pub_types)}")
        elif any("randomized controlled trial" in p or "randomised controlled trial" in p for p in pt_lower):
            study_type = "randomized_controlled_trial"
            confidence = 0.90
            evidence.append(f"依据 PubMed publication_type: {', '.join(pub_types)}")
        elif any("clinical trial" in p for p in pt_lower):
            study_type = "randomized_controlled_trial"
            confidence = 0.70
            evidence.append(f"依据 PubMed publication_type: {', '.join(pub_types)} (推定为 RCT)")

    # ── Layer 2: Title/Abstract pattern matching ──
    if study_type == "unknown":
        search_text = f"{title} {abstract[:1000]}".lower()
        best_match = None
        best_priority = 999

        for i, (pattern, stype) in enumerate(STUDY_TYPE_PATTERNS):
            if re.search(pattern, search_text, re.IGNORECASE):
                if i < best_priority:
                    best_priority = i
                    best_match = stype

        if best_match:
            study_type = best_match
            confidence = 0.65
            evidence.append(f"依据标题/摘要关键词匹配: {best_match}")

    # ── Layer 3: Heuristic inference ──
    if study_type == "unknown":
        search_text = f"{title} {abstract[:2000]}".lower()
        if re.search(r"\bintervention\b|\bpre[\s-]*post\b|\btreatment\b|\bexperimental\b", search_text):
            study_type = "intervention_study_unspecified"
            confidence = 0.40
            evidence.append("依据摘要中干预相关关键词推断")
        elif re.search(r"\bobserv(?:e|ed|ation|ational)\b|\bsurvey\b|\bquestionnaire\b", search_text):
            study_type = "observational_unspecified"
            confidence = 0.35
            evidence.append("依据摘要中观察性研究关键词推断")

    # ── Confidence adjustments ──
    if not abstract or len(abstract) < 100:
        confidence = min(confidence, 0.50)
        evidence.append("摘要信息有限，置信度降低")

    return {
        "study_type": study_type,
        "study_type_confidence": round(confidence, 2),
        "study_type_evidence": evidence,
    }


def evaluate_design(paper: dict) -> dict:
    """Rigorous study design evaluation.

    Evaluates study design appropriateness, methodological rigor,
    and completeness for the research question. Returns a detailed
    assessment with a 0-10 score.
    """
    study_type_info = identify_study_type(paper)
    study_type = study_type_info["study_type"]

    # Determine evaluation template based on study type
    if study_type in ("randomized_controlled_trial", "cluster_randomized_trial",
                       "crossover_trial", "non_randomized_controlled_trial",
                       "single_arm_trial", "intervention_study_unspecified"):
        result = _evaluate_intervention_design(paper, study_type, study_type_info)
    elif study_type in ("systematic_review", "meta_analysis",
                         "systematic_review_with_meta_analysis"):
        result = _evaluate_review_design(paper, study_type, study_type_info)
    elif study_type in ("cohort_study", "case_control_study",
                         "cross_sectional_study", "observational_unspecified"):
        result = _evaluate_observational_design(paper, study_type, study_type_info)
    else:
        result = _evaluate_generic_design(paper, study_type, study_type_info)

    return result


def _evaluate_intervention_design(paper: dict, study_type: str,
                                   type_info: dict) -> dict:
    """Evaluate intervention/trial study design."""
    strengths = []
    limitations = []
    score = 5.0  # Start neutral

    # Extract available details
    title = paper.get("title", "")
    abstract = paper.get("abstract", "") or ""
    sample_size = paper.get("sample_size", "")
    population = paper.get("population", "")
    doi = paper.get("doi", "")
    pmid = paper.get("pmid", "")

    # ── Randomization ──
    rand_keywords = ["randomi", "randomly assigned", "random allocation",
                     "random number", "computer-generated"]
    has_randomization = any(kw in (title + abstract).lower() for kw in rand_keywords)

    if study_type.startswith("randomized"):
        if has_randomization:
            strengths.append("Research design: 研究声称随机分配")
            score += 1.5
        else:
            limitations.append("Research design: 研究类型标注为RCT但摘要中未见随机化描述")
            score -= 0.5

    if study_type == "non_randomized_controlled_trial":
        limitations.append("Research design: 非随机对照设计，存在选择偏倚风险")
        score -= 0.5

    # ── Blinding ──
    blind_keywords = ["blind", "double-blind", "single-blind", "masked", "sham"]
    has_blinding = any(kw in (title + abstract).lower() for kw in blind_keywords)
    if has_blinding:
        strengths.append("Blinding: 报告中提到盲法")
        score += 0.5
    else:
        limitations.append("Blinding: 摘要未报告盲法 — 需查看全文")
        score -= 0.2

    # ── Control group ──
    control_keywords = ["control group", "control condition", "comparator",
                        "usual care", "placebo", "sham", "versus", "vs.", "compared"]
    has_control = any(kw in (title + abstract).lower() for kw in control_keywords)
    if has_control:
        strengths.append("Control group: 提及对照组/比较组")
        score += 0.5
    else:
        limitations.append("Control group: 摘要未明确描述对照组 — 需查看全文")

    # ── Sample size ──
    try:
        n = int(sample_size) if sample_size else 0
    except (ValueError, TypeError):
        n = 0
        # Try to extract from abstract
        n_match = re.search(r"(?:n\s*[=:]\s*|sample\s+size\s*(?:of|=|:)?\s*|included\s+)(\d+)",
                            abstract, re.IGNORECASE)
        if n_match:
            n = int(n_match.group(1))

    if n >= 200:
        strengths.append(f"Sample size: n={n}，样本量较好")
        score += 1.5
    elif n >= 50:
        strengths.append(f"Sample size: n={n}，样本量可接受")
        score += 1.0
    elif n >= 20:
        limitations.append(f"Sample size: n={n}，样本量偏小")
        score += 0.2
    elif n > 0:
        limitations.append(f"Sample size: n={n}，样本量过小，结果外推受限")
        score -= 0.8
    else:
        limitations.append("Sample size: 摘要未报告样本量 — 需查看全文")

    # ── Trial registration ──
    reg_keywords = ["clinicaltrials.gov", "trial registration", "registered",
                    "NCT", "UMIN", "ChiCTR", "DRKS", "IRCT", "ACTRN"]
    has_registration = any(kw in (abstract).lower() for kw in reg_keywords)
    if has_registration or paper.get("trial_registration"):
        strengths.append("Registration: 提及试验注册")
        score += 0.5
    else:
        limitations.append("Registration: 摘要未提及试验注册 — 需查看")

    # ── Ethics ──
    ethics_keywords = ["ethics", "ethical approval", "IRB", "institutional review",
                       "informed consent", "Helsinki"]
    has_ethics = any(kw in (title + abstract).lower() for kw in ethics_keywords)
    if has_ethics or paper.get("ethical_approval"):
        strengths.append("Ethics: 报告中提及伦理审批或知情同意")
        score += 0.3
    else:
        limitations.append("Ethics: 摘要未提及伦理审批 — 需查看全文")

    # ── Follow-up / Dropout ──
    dropout_keywords = ["dropout", "drop-out", "attrition", "lost to follow",
                        "completed the study", "retention", "adherence"]
    has_dropout_info = any(kw in abstract.lower() for kw in dropout_keywords)
    if has_dropout_info:
        strengths.append("Follow-up: 摘要中提及脱落/依从性/完成率信息")
        score += 0.3
    else:
        limitations.append("Follow-up: 摘要未报告脱落率和依从性 — 需查看全文")

    # ── Outcome specification ──
    outcome_keywords = ["primary outcome", "primary endpoint", "main outcome",
                        "primary measure", "outcome measure"]
    has_primary = any(kw in abstract.lower() for kw in outcome_keywords)
    if has_primary or paper.get("primary_outcome"):
        strengths.append("Outcome: 明确报告主要结局指标")
        score += 0.5
    else:
        limitations.append("Outcome: 摘要未明确区分主要/次要结局")

    # Clamp score
    score = max(0, min(10, round(score, 1)))

    review_level = "abstract_only"
    if paper.get("full_text"):
        review_level = "full_text"
    elif paper.get("metadata_completeness"):
        review_level = "metadata_only"

    return {
        "study_type": study_type,
        "study_type_confidence": type_info.get("study_type_confidence", 0),
        "study_type_evidence": type_info.get("study_type_evidence", []),
        "design_score": score,
        "design_strengths": strengths if strengths else ["摘要信息不足，需阅读全文判断设计优点"],
        "design_limitations": limitations if limitations else ["摘要信息不足，需阅读全文判断设计局限"],
        "design_score_reason": _build_design_reason(score, strengths, limitations, review_level),
        "intervention_details": {
            "population": population or "摘要未报告，需查看全文",
            "sample_size": str(n) if n > 0 else "未获取",
            "sex_distribution": "摘要未报告，需查看全文",
            "age_range_or_mean": "摘要未报告，需查看全文",
            "training_status": "摘要未报告，需查看全文",
            "sport_type": "摘要未报告，需查看全文",
            "randomization": "是" if has_randomization else "未报告",
            "allocation_concealment": "摘要未报告，需查看全文",
            "blinding": "是" if has_blinding else "未报告",
            "control_group": "是" if has_control else "未报告",
            "intervention_type": "摘要未报告，需查看全文",
            "intervention_duration": "摘要未报告，需查看全文",
            "frequency_per_week": "摘要未报告，需查看全文",
            "session_duration": "摘要未报告，需查看全文",
            "intensity_control": "摘要未报告，需查看全文",
            "volume_control": "摘要未报告，需查看全文",
            "progression_model": "摘要未报告，需查看全文",
            "adherence": "摘要未报告，需查看全文",
            "dropout_rate": "摘要未报告，需查看全文",
            "co_interventions_controlled": "摘要未报告，需查看全文",
            "primary_outcome": paper.get("primary_outcome", "") or "未明确",
            "secondary_outcomes": paper.get("secondary_outcomes", "") or "未获取",
            "measurement_validity": "摘要未报告，需查看全文",
            "follow_up": "摘要未报告，需查看全文",
            "trial_registration": paper.get("trial_registration", "") or ("已提及" if has_registration else "未报告"),
            "ethical_approval": paper.get("ethical_approval", "") or ("已提及" if has_ethics else "未报告"),
        },
        "review_details": {},
    }


def _evaluate_review_design(paper: dict, study_type: str,
                             type_info: dict) -> dict:
    """Evaluate systematic review/meta-analysis design."""
    strengths = []
    limitations = []
    score = 5.0
    abstract = paper.get("abstract", "") or ""

    # PRISMA
    if "prisma" in abstract.lower():
        strengths.append("Reporting: 提及PRISMA报告规范")
        score += 1.0
    else:
        limitations.append("Reporting: 摘要未提及PRISMA — 需查看全文")

    # Registration (PROSPERO)
    reg_keywords = ["prospero", "crd420", "registered", "protocol"]
    if any(kw in abstract.lower() for kw in reg_keywords):
        strengths.append("Registration: 提及注册或方案")
        score += 0.5
    else:
        limitations.append("Registration: 摘要未提及PROSPERO注册 — 需查看")

    # Databases searched
    db_keywords = ["pubmed", "medline", "embase", "cinahl", "cochrane",
                   "scopus", "web of science", "sportdiscus", "pedro"]
    dbs_found = [kw for kw in db_keywords if kw in abstract.lower()]
    if len(dbs_found) >= 2:
        strengths.append(f"Search: 检索了 {', '.join(dbs_found)} 等数据库 (≥2)")
        score += 1.0
    elif dbs_found:
        strengths.append(f"Search: 检索了 {', '.join(dbs_found)}")
        score += 0.5
    else:
        limitations.append("Search: 摘要未明确列出检索数据库 — 需查看全文")

    # Risk of bias tool
    rob_keywords = ["risk of bias", "rob 2", "robins", "amstar",
                    "newcastle-ottawa", "jadad", "pedro scale", "cochrane"]
    has_rob = any(kw in abstract.lower() for kw in rob_keywords)
    if has_rob:
        strengths.append("Risk of bias: 提及偏倚风险评估工具")
        score += 1.0
    else:
        limitations.append("Risk of bias: 摘要未提及偏倚风险评估工具 — 需查看全文")

    # Heterogeneity
    het_keywords = ["heterogeneity", "i2", "i-squared", "i square", "i²",
                    "tau", "random-effect", "random effects"]
    has_het = any(kw in abstract.lower() for kw in het_keywords)
    if has_het:
        strengths.append("Heterogeneity: 考虑了异质性")
        score += 1.0
    elif study_type in ("meta_analysis", "systematic_review_with_meta_analysis"):
        limitations.append("Heterogeneity: Meta分析的异质性评估信息不足 — 需查看全文")

    # GRADE
    if "grade" in abstract.lower():
        strengths.append("GRADE: 使用了GRADE证据质量分级")
        score += 1.0

    # Publication bias
    pub_bias_keywords = ["publication bias", "funnel plot", "egger", "trim and fill"]
    if any(kw in abstract.lower() for kw in pub_bias_keywords):
        strengths.append("Publication bias: 评估了发表偏倚")
        score += 0.5
    elif study_type in ("meta_analysis", "systematic_review_with_meta_analysis"):
        limitations.append("Publication bias: 摘要未提及发表偏倚评估")

    # Number of included studies
    n_match = re.search(r"(?:included|identified|selected)\s+(\d+)\s+(?:studies|articles|trials|RCT)",
                        abstract, re.IGNORECASE)
    if n_match:
        n_studies = int(n_match.group(1))
        if n_studies >= 20:
            strengths.append(f"Scope: 纳入 {n_studies} 篇研究")
            score += 0.5
        elif n_studies >= 5:
            strengths.append(f"Scope: 纳入 {n_studies} 篇研究")
        else:
            limitations.append(f"Scope: 仅纳入 {n_studies} 篇研究，覆盖范围有限")

    score = max(0, min(10, round(score, 1)))
    review_level = "abstract_only"
    if paper.get("full_text"):
        review_level = "full_text"

    return {
        "study_type": study_type,
        "study_type_confidence": type_info.get("study_type_confidence", 0),
        "study_type_evidence": type_info.get("study_type_evidence", []),
        "design_score": score,
        "design_strengths": strengths if strengths else ["摘要信息不足，需阅读全文判断设计优点"],
        "design_limitations": limitations if limitations else ["摘要信息不足，需阅读全文判断设计局限"],
        "design_score_reason": _build_design_reason(score, strengths, limitations, review_level),
        "intervention_details": {},
        "review_details": {
            "prisma_reported": "是" if "prisma" in abstract.lower() else "未报告",
            "prospero_registration": "是" if any(kw in abstract.lower() for kw in ["prospero", "crd420"]) else "未报告",
            "databases_searched": ", ".join(dbs_found) if dbs_found else "未报告",
            "search_strategy_reported": "摘要未提及 — 需查看全文",
            "inclusion_criteria_clear": "需查看全文",
            "screening_process": "需查看全文",
            "data_extraction_process": "需查看全文",
            "risk_of_bias_tool": "已提及" if has_rob else "未报告",
            "heterogeneity_assessment": "已提及" if has_het else "未报告",
            "model_choice": "random" if any(kw in abstract.lower() for kw in ["random-effect", "random effects"]) else "unclear",
            "publication_bias_assessment": "已提及" if any(kw in abstract.lower() for kw in pub_bias_keywords) else "未报告",
            "sensitivity_analysis": "需查看全文",
            "subgroup_analysis": "需查看全文",
            "certainty_assessment_grade": "已使用" if "grade" in abstract.lower() else "未报告",
        },
    }


def _evaluate_observational_design(paper: dict, study_type: str,
                                    type_info: dict) -> dict:
    """Evaluate observational study design."""
    strengths = []
    limitations = []
    score = 3.0  # Lower baseline for observational
    abstract = paper.get("abstract", "") or ""

    # Sample size
    n_match = re.search(r"(?:n\s*[=:]\s*|sample\s+size\s*(?:of|=|:)?\s*|included\s+)(\d+)",
                        abstract, re.IGNORECASE)
    n = 0
    if n_match:
        n = int(n_match.group(1))

    if n >= 1000:
        strengths.append(f"Sample size: n={n}，大样本")
        score += 2.0
    elif n >= 200:
        strengths.append(f"Sample size: n={n}，样本量较好")
        score += 1.5
    elif n >= 50:
        strengths.append(f"Sample size: n={n}")
        score += 0.5
    elif n > 0:
        limitations.append(f"Sample size: n={n}，样本量较小")
    else:
        limitations.append("Sample size: 摘要未报告 — 需查看")

    # Confounding control
    conf_keywords = ["adjusted", "covariate", "confound", "multivariate",
                     "propensity", "regression"]
    if any(kw in abstract.lower() for kw in conf_keywords):
        strengths.append("Confounding: 考虑了混杂因素控制")
        score += 1.0

    # Prospective vs retrospective
    if "prospective" in abstract.lower():
        strengths.append("Design: 前瞻性设计")
        score += 0.5
    elif "retrospective" in abstract.lower():
        limitations.append("Design: 回顾性设计，信息偏倚风险")

    score = max(0, min(10, round(score, 1)))
    review_level = "abstract_only"

    return {
        "study_type": study_type,
        "study_type_confidence": type_info.get("study_type_confidence", 0),
        "study_type_evidence": type_info.get("study_type_evidence", []),
        "design_score": score,
        "design_strengths": strengths if strengths else ["摘要信息不足，需阅读全文判断"],
        "design_limitations": limitations if limitations else ["摘要信息不足，需阅读全文判断"],
        "design_score_reason": _build_design_reason(score, strengths, limitations, review_level),
        "intervention_details": {},
        "review_details": {},
    }


def _evaluate_generic_design(paper: dict, study_type: str,
                              type_info: dict) -> dict:
    """Generic design evaluation for unknown/other study types."""
    return {
        "study_type": study_type,
        "study_type_confidence": type_info.get("study_type_confidence", 0),
        "study_type_evidence": type_info.get("study_type_evidence", []),
        "design_score": 3.0,
        "design_strengths": ["信息不足，需人工评估"],
        "design_limitations": ["研究类型未能自动识别，设计评价受限"],
        "design_score_reason": "研究类型未能明确识别，给予中性评分。建议人工审核。",
        "intervention_details": {},
        "review_details": {},
    }


def _build_design_reason(score: float, strengths: list, limitations: list,
                          review_level: str) -> str:
    """Build a human-readable design score explanation."""
    parts = []
    if review_level == "abstract_only":
        parts.append("本评价主要基于摘要信息。")

    if score >= 8:
        parts.append(f"研究设计严谨 (score={score})，方法与研究问题匹配良好。")
    elif score >= 6:
        parts.append(f"研究设计总体合理 (score={score})，存在部分方法学信息不足。")
    elif score >= 4:
        parts.append(f"研究设计存在一定局限 (score={score})，信息不足以充分评判。")
    else:
        parts.append(f"研究设计评价信息严重不足 (score={score})，需阅读全文后重新评价。")

    if len(strengths) <= 1:
        parts.append("设计优点信息不足。")
    if len(limitations) >= 3:
        parts.append("存在多项设计相关信息缺失。")

    return " ".join(parts)
