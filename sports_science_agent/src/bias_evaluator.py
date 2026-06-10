"""Bias evaluator — automated risk of bias screening per study type.

Maps study types to appropriate bias assessment tools and performs
initial screening based on available metadata/abstract.

IMPORTANT DISCLAIMER embedded in output:
This is automated pre-screening, NOT a substitute for formal
RoB 2 / ROBINS-I / AMSTAR 2 / GRADE assessment.
"""

import re
from src.utils import logger


def evaluate_bias(paper: dict) -> dict:
    """Automated risk of bias pre-screening.

    Maps study type to the appropriate tool logic and evaluates
    available information. Always notes this is automated, not formal.

    Returns dict with bias assessment and evidence level.
    """
    study_type = paper.get("study_type", "unknown")
    abstract = paper.get("abstract", "") or ""
    title = paper.get("title", "")
    text = f"{title} {abstract}".lower()

    # Determine which tool logic to use
    if study_type in ("randomized_controlled_trial", "cluster_randomized_trial",
                       "crossover_trial"):
        result = _rob2_screening(paper, text)
    elif study_type in ("non_randomized_controlled_trial", "single_arm_trial",
                         "intervention_study_unspecified"):
        result = _robins_i_screening(paper, text)
    elif study_type in ("systematic_review", "meta_analysis",
                         "systematic_review_with_meta_analysis"):
        result = _amstar2_screening(paper, text)
    elif study_type in ("cohort_study", "case_control_study"):
        result = _nos_screening(paper, text)
    elif study_type == "cross_sectional_study":
        result = _axis_screening(paper, text)
    elif study_type == "diagnostic_accuracy_study":
        result = _quadas2_screening(paper, text)
    elif study_type in ("animal_study",):
        result = _syrcle_screening(paper, text)
    else:
        result = _generic_screening(paper, text)

    # Add disclaimer
    result["disclaimer"] = (
        "该偏倚风险评价为自动化初筛，不等同于人工正式 RoB 2、ROBINS-I、"
        "AMSTAR 2 或 GRADE 评价。所有偏倚判断均需全文阅读后由研究者独立复核。"
    )

    return result


def _rob2_screening(paper: dict, text: str) -> dict:
    """RoB 2 logic for RCTs."""
    domains = {}
    reasons = []

    # D1: Randomization (selection bias)
    rand_kw = ["randomi", "randomly assigned", "random allocation",
               "computer-generated", "random number", "sealed envelope"]
    has_rand = any(kw in text for kw in rand_kw)
    has_alloc = any(kw in text for kw in ["allocation conceal", "sealed", "opaque envelope"])

    if has_rand and has_alloc:
        domains["selection_bias"] = "low"
    elif has_rand:
        domains["selection_bias"] = "some_concerns"
        reasons.append("提及随机化但分配隐藏不详")
    else:
        domains["selection_bias"] = "high"
        reasons.append("未提及随机化方法")

    # D2: Performance bias
    blind_kw = ["blind", "double-blind", "single-blind", "masked", "sham"]
    has_blind = any(kw in text for kw in blind_kw)
    is_exercise = any(kw in text for kw in ["exercise", "training", "physical activity",
                                             "rehabilitation", "sport"])
    if has_blind:
        domains["performance_bias"] = "low"
    elif is_exercise:
        domains["performance_bias"] = "some_concerns"
        reasons.append("运动干预难以实现双盲，需评估是否采用了其他偏倚控制措施")
    else:
        domains["performance_bias"] = "some_concerns"
        reasons.append("盲法不详")

    # D3: Detection bias
    if has_blind or any(kw in text for kw in ["blinded assess", "independent assess", "blind outcome"]):
        domains["detection_bias"] = "low"
    else:
        domains["detection_bias"] = "some_concerns"
        reasons.append("结局评估盲法不详")

    # D4: Attrition bias
    if any(kw in text for kw in ["dropout", "drop-out", "attrition", "lost to follow",
                                   "completed", "retention", "adherence", "ITT",
                                   "intention-to-treat"]):
        domains["attrition_bias"] = "low"
    else:
        domains["attrition_bias"] = "some_concerns"
        reasons.append("脱落/缺失数据不详")

    # D5: Reporting bias
    if any(kw in text for kw in ["trial registration", "registered", "NCT",
                                   "ClinicalTrials.gov", "protocol", "pre-register",
                                   "primary outcome", "pre-specified"]):
        domains["reporting_bias"] = "low"
    else:
        domains["reporting_bias"] = "some_concerns"
        reasons.append("未见试验注册或预设结局指标声明")

    # Overall
    high_count = sum(1 for v in domains.values() if v == "high")
    concerns_count = sum(1 for v in domains.values() if v == "some_concerns")

    if high_count >= 1:
        overall = "high"
    elif concerns_count >= 3:
        overall = "some_concerns"
    elif concerns_count >= 1:
        overall = "some_concerns"
    else:
        overall = "low"

    return _build_result(overall, domains, reasons, "RoB 2 (RCT自动化初筛)", paper)


def _robins_i_screening(paper: dict, text: str) -> dict:
    """ROBINS-I logic for non-randomized interventions."""
    domains = {}
    reasons = []
    reasons.append("非随机设计，选择偏倚风险较高")

    domains["confounding"] = "high" if "randomized" not in paper.get("study_type", "") else "some_concerns"
    domains["selection_bias"] = "high"
    reasons.append("非随机分配，基线差异可能影响结果")
    domains["performance_bias"] = "some_concerns"
    domains["detection_bias"] = "some_concerns"
    domains["attrition_bias"] = "some_concerns"
    domains["reporting_bias"] = "some_concerns"

    if any(kw in text for kw in ["propensity", "matching", "adjusted for", "covariate"]):
        domains["confounding"] = "some_concerns"
        reasons.append("使用了统计方法控制混杂，但观察性研究残余混杂仍可能存在")

    return _build_result("high", domains, reasons, "ROBINS-I (非随机干预自动化初筛)", paper)


def _amstar2_screening(paper: dict, text: str) -> dict:
    """AMSTAR 2 logic for systematic reviews."""
    domains = {}
    reasons = []

    if "prisma" in text:
        domains["reporting_quality"] = "low"
    else:
        domains["reporting_quality"] = "some_concerns"
        reasons.append("未提及PRISMA")

    if any(kw in text for kw in ["prospero", "registered protocol", "crd420"]):
        domains["protocol_registration"] = "low"
    else:
        domains["protocol_registration"] = "some_concerns"
        reasons.append("未提及方案注册")

    if any(kw in text for kw in ["risk of bias", "rob 2", "robins", "amstar",
                                   "newcastle", "jadad", "pedro"]):
        domains["risk_of_bias_assessment"] = "low"
    else:
        domains["risk_of_bias_assessment"] = "high"
        reasons.append("未提及纳入研究的偏倚风险评估")

    if any(kw in text for kw in ["comprehensive", "pubmed", "medline", "embase",
                                   "cochrane", "scopus", "web of science"]):
        domains["search_comprehensiveness"] = "low"
    else:
        domains["search_comprehensiveness"] = "some_concerns"
        reasons.append("检索策略不详")

    if any(kw in text for kw in ["meta-analys", "random-effect", "random effects",
                                   "heterogeneity", "i2"]):
        domains["synthesis_appropriateness"] = "low"
    else:
        domains["synthesis_appropriateness"] = "some_concerns"

    high_count = sum(1 for v in domains.values() if v == "high")
    concerns_count = sum(1 for v in domains.values() if v == "some_concerns")

    if high_count >= 1:
        overall = "high"
    elif concerns_count >= 2:
        overall = "some_concerns"
    else:
        overall = "low"

    return _build_result(overall, domains, reasons, "AMSTAR 2 (系统综述自动化初筛)", paper)


def _nos_screening(paper: dict, text: str) -> dict:
    """Newcastle-Ottawa Scale logic for observational studies."""
    domains = {}
    reasons = []

    if "prospective" in text:
        domains["selection_bias"] = "low"
    else:
        domains["selection_bias"] = "some_concerns"
        reasons.append("回顾性或横断面设计")

    if any(kw in text for kw in ["adjusted", "covariate", "confound", "multivariate",
                                   "propensity", "matched"]):
        domains["confounding"] = "low"
    else:
        domains["confounding"] = "high"
        reasons.append("混杂控制不详")

    domains["detection_bias"] = "some_concerns"
    domains["attrition_bias"] = "some_concerns"

    if any(kw in text for kw in ["validated", "reliable", "accelerometer",
                                   "gold standard", "DXA", "calibrated"]):
        domains["measurement_bias"] = "low"
    else:
        domains["measurement_bias"] = "some_concerns"

    overall = "some_concerns" if domains.get("confounding") == "high" else "some_concerns"
    return _build_result(overall, domains, reasons, "Newcastle-Ottawa Scale (观察性研究自动化初筛)", paper)


def _axis_screening(paper: dict, text: str) -> dict:
    """AXIS/JBI logic for cross-sectional studies."""
    domains = {}
    reasons = []
    reasons.append("横断面设计无法推断因果关系")

    n_match = re.search(r"(?:n\s*[=:]\s*|sample\s*size\s*(?:of|=|:)?\s*|included\s+)(\d+)",
                        paper.get("abstract", ""), re.IGNORECASE)
    if n_match and int(n_match.group(1)) >= 200:
        domains["selection_bias"] = "low"
    else:
        domains["selection_bias"] = "some_concerns"
        reasons.append("样本量或抽样方法不详")

    domains["measurement_bias"] = "some_concerns"
    domains["confounding"] = "high"
    reasons.append("横断面研究难以控制所有混杂因素")

    return _build_result("high", domains, reasons, "AXIS/JBI (横断面研究自动化初筛)", paper)


def _quadas2_screening(paper: dict, text: str) -> dict:
    """QUADAS-2 logic for diagnostic accuracy studies."""
    domains = {
        "patient_selection": "some_concerns",
        "index_test": "some_concerns",
        "reference_standard": "some_concerns",
        "flow_and_timing": "some_concerns",
    }
    reasons = ["诊断准确性研究 — 需全文评估QUADAS-2各领域"]
    return _build_result("unclear", domains, reasons, "QUADAS-2 (诊断研究自动化初筛)", paper)


def _syrcle_screening(paper: dict, text: str) -> dict:
    """SYRCLE logic for animal studies."""
    domains = {
        "selection_bias": "high",
        "performance_bias": "high",
        "detection_bias": "high",
        "attrition_bias": "high",
        "reporting_bias": "high",
    }
    reasons = ["动物研究 — 外推到人类的证据等级极低。SYRCLE条目需全文评估"]
    return _build_result("high", domains, reasons, "SYRCLE (动物研究自动化初筛)", paper)


def _generic_screening(paper: dict, text: str) -> dict:
    """Generic bias screening for unrecognized study types."""
    domains = {
        "selection_bias": "unclear",
        "performance_bias": "unclear",
        "detection_bias": "unclear",
        "attrition_bias": "unclear",
        "reporting_bias": "unclear",
        "confounding": "unclear",
    }
    reasons = ["研究类型不明确，无法进行系统偏倚评估。需人工审核"]
    return _build_result("unclear", domains, reasons, "通用自动化初筛", paper)


def _build_result(overall: str, domains: dict, reasons: list,
                   tool_name: str, paper: dict) -> dict:
    """Build standardized bias evaluation result."""
    # Determine evidence level
    study_type = paper.get("study_type", "unknown")

    if study_type in ("meta_analysis", "systematic_review_with_meta_analysis") and overall == "low":
        evidence_level = "high"
    elif study_type in ("randomized_controlled_trial", "cluster_randomized_trial",
                         "crossover_trial") and overall == "low":
        evidence_level = "high"
    elif overall == "low":
        evidence_level = "moderate"
    elif overall == "some_concerns":
        evidence_level = "moderate" if study_type.startswith("randomized") else "low"
    elif overall == "high":
        evidence_level = "low"
    else:
        evidence_level = "very_low"

    return {
        "risk_of_bias": overall,
        "risk_of_bias_domains": domains,
        "risk_of_bias_reasons": reasons if reasons else ["信息不足，需全文评估"],
        "evidence_level": evidence_level,
        "evidence_level_reasons": [
            f"基于{tool_name}",
            f"总体偏倚风险: {overall}",
            f"研究类型: {study_type}",
            "该证据等级为自动化判断，不等同于GRADE评价"
        ],
        "tool_used": tool_name,
    }
