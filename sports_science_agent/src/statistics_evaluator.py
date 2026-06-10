"""Statistics evaluator — rigorous statistical method assessment for sports science papers."""

import re
from src.utils import logger


def evaluate_statistics(paper: dict) -> dict:
    """Evaluate statistical methods used in a paper.

    Checks statistical approach against study design, data structure,
    and sports science conventions. Based on abstract/metadata.

    Returns a dict with detailed evaluation and a 0-10 score.
    """
    abstract = paper.get("abstract", "") or paper.get("full_text", "")[:5000] or ""
    title = paper.get("title", "")
    study_type = paper.get("study_type", "unknown")
    full_text = paper.get("full_text", "")

    review_level = "abstract_only"
    if len(full_text) > 1000:
        review_level = "full_text"
    elif not abstract:
        review_level = "metadata_only"

    # ── Extract statistical features ──
    features = _extract_statistical_features(abstract)

    strengths = []
    limitations = []
    score = 5.0  # Neutral baseline

    # ── 1. Basic reporting check ──
    if features["p_value_reported"] == "是":
        strengths.append("报告了 p 值")
        score += 0.5

    if features["effect_size_reported"] == "是":
        strengths.append("报告了效应量 (effect size)")
        score += 1.5
    else:
        limitations.append("未报告效应量 — 仅凭p值不足以判断实际意义。运动科学强烈建议报告效应量（Cohen's d, Hedges' g, η², OR, HR等）")

    if features["confidence_interval_reported"] == "是":
        strengths.append("报告了置信区间")
        score += 1.0
    else:
        limitations.append("未报告置信区间 — 置信区间提供效应估计精度，是APA和CONSORT要求报告的")

    if features["sample_size_calculation"] == "是":
        strengths.append("报告了样本量估算/先验功效分析")
        score += 1.0
    else:
        limitations.append("未报告样本量估算 — 无法判断研究是否有足够统计功效检测真实效应")

    # ── 2. Statistical model sophistication ──
    model_kw = features["model_type"]
    has_advanced_model = any(kw in abstract.lower() for kw in [
        "mixed model", "mixed-effect", "multilevel", "hierarchical",
        "linear mixed", "generalized estimating", "gee", "ancova",
        "repeated measures anova", "manova", "cox", "survival analysis",
        "meta-regression", "network meta-analysis"
    ])

    if has_advanced_model:
        strengths.append(f"统计方法较为先进，使用了 {model_kw}")
        score += 1.0
    elif study_type.startswith("randomized") and model_kw == "未识别":
        limitations.append("统计模型未明确 — 干预性RCT应明确主分析方法")

    # ── 3. Repeated measures handling ──
    repeated_kw = ["repeated measure", "pre-post", "baseline", "follow-up",
                   "pre training", "post training", "time point", "longitudinal"]
    has_repeated = any(kw in abstract.lower() for kw in repeated_kw)

    if has_repeated and features["repeated_measures_handling"] == "未报告":
        limitations.append("重复测量设计识别到但未报告合适的统计处理方法 — "
                          "若使用简单t检验处理多时间点数据可能存在I类错误膨胀风险。"
                          "应使用 repeated-measures ANOVA / mixed-effects model / ANCOVA")
        score -= 0.5

    if features["repeated_measures_handling"] == "是":
        strengths.append("合理处理了重复测量数据")
        score += 0.5

    # ── 4. Multiple comparison correction ──
    multi_test_kw = ["multiple outcome", "multiple comparison",
                     "several endpoint", "various measure"]
    has_multi_outcomes = any(kw in abstract.lower() for kw in multi_test_kw) or \
                         abstract.count(",") > 50  # Many outcomes likely

    if has_multi_outcomes and features["multiple_comparison_correction"] == "未报告":
        limitations.append("可能存在多重比较问题 — 多指标/多时间点/多组比较未见多重比较校正"
                          "（如 Bonferroni, Tukey HSD, Holm, FDR）。存在I类错误膨胀风险")
        score -= 0.8

    if features["multiple_comparison_correction"] == "是":
        strengths.append("使用了多重比较校正")
        score += 0.5

    # ── 5. Missing data handling ──
    if features["missing_data_handling"] == "是":
        strengths.append("报告了缺失数据处理方法")
        score += 0.5

    # ── 6. Per-protocol vs ITT ──
    if study_type.startswith("randomized"):
        if features["intention_to_treat"] == "是":
            strengths.append("使用了ITT分析")
            score += 0.5
        elif features["intention_to_treat"] == "否":
            limitations.append("未使用ITT分析 — 可能高估干预效果")

    # ── 7. Covariate/baseline adjustment ──
    if features["covariate_adjustment"] == "是" or features["baseline_adjustment"] == "是":
        strengths.append("考虑了协变量调整/基线调整")
        score += 0.5

    # ── 8. Meta-analysis specific ──
    if study_type in ("meta_analysis", "systematic_review_with_meta_analysis"):
        if features["heterogeneity_analysis"] == "是":
            strengths.append("评估了异质性")
            score += 0.5
        else:
            limitations.append("Meta分析未提及异质性评估")

        if features["publication_bias_analysis"] == "是":
            strengths.append("评估了发表偏倚")
            score += 0.5
        else:
            limitations.append("未提及发表偏倚评估")

        if "fixed" in abstract.lower() and "random" not in abstract.lower():
            limitations.append("使用固定效应模型 — 运动科学领域的研究间异质性通常较大，"
                              "固定效应模型的假设可能不成立")

    # ── 9. Sports science specific checks ──
    # Magnitude-based inference
    if "magnitude-based" in abstract.lower() or "magnitude based" in abstract.lower():
        limitations.append("使用了 Magnitude-Based Inference (MBI) — "
                          "该方法在统计学界存在争议，需谨慎解释其推断结果。"
                          "多数统计学家建议使用传统频率学派或贝叶斯方法替代")

    # Small sample without appropriate methods
    n_match = re.search(r"(?:n\s*[=:]\s*|participants?[=:]\s*)(\d+)", abstract, re.IGNORECASE)
    if n_match:
        n = int(n_match.group(1))
        if n < 30 and "non-parametric" not in abstract.lower() and "nonparametric" not in abstract.lower():
            limitations.append(f"小样本 (n={n}) 未见非参数检验考虑 — "
                              "小样本下正态性假设难以验证，建议使用非参数检验或贝叶斯方法")

    # ── Aggregate score ──
    score = max(0, min(10, round(score, 1)))

    # Score interpretation
    if score >= 9:
        level_desc = "统计模型与设计高度匹配，报告效应量、置信区间、样本量估算、缺失值处理、多重比较控制，结论谨慎。"
    elif score >= 7:
        level_desc = "统计方法总体合理，但有少量报告不充分。"
    elif score >= 5:
        level_desc = "统计方法基本可接受，但缺少效应量、CI、样本量估算或多重比较处理。"
    elif score >= 3:
        level_desc = "统计方法描述不足，可能与设计不完全匹配，结论可信度有限。"
    else:
        level_desc = "统计方法严重不当或无法支持结论。"

    return {
        "statistical_tests": features["statistical_tests"],
        "model_type": model_kw,
        "primary_analysis": model_kw if has_advanced_model else "未识别",
        "effect_size_reported": features["effect_size_reported"],
        "confidence_interval_reported": features["confidence_interval_reported"],
        "p_value_reported": features["p_value_reported"],
        "normality_test": features.get("normality_test", "摘要未报告，需查看全文"),
        "variance_assumption": features.get("variance_assumption", "摘要未报告，需查看全文"),
        "multiple_comparison_correction": features["multiple_comparison_correction"],
        "sample_size_calculation": features["sample_size_calculation"],
        "power_analysis": features["sample_size_calculation"],
        "intention_to_treat": features.get("intention_to_treat", "摘要未报告，需查看全文"),
        "per_protocol_analysis": features.get("per_protocol_analysis", "摘要未报告，需查看全文"),
        "missing_data_handling": features["missing_data_handling"],
        "covariate_adjustment": features["covariate_adjustment"],
        "baseline_adjustment": features["baseline_adjustment"],
        "repeated_measures_handling": features["repeated_measures_handling"],
        "cluster_or_team_effect_handling": features.get("cluster_handling", "摘要未报告，需查看全文"),
        "subgroup_analysis": features.get("subgroup_analysis", "摘要未报告，需查看全文"),
        "sensitivity_analysis": features.get("sensitivity_analysis", "摘要未报告，需查看全文"),
        "heterogeneity_analysis": features.get("heterogeneity_analysis", "摘要未报告，需查看全文"),
        "publication_bias_analysis": features.get("publication_bias_analysis", "摘要未报告，需查看全文"),
        "statistical_software": features.get("software", "摘要未报告"),
        "statistics_score": score,
        "statistics_strengths": strengths if strengths else ["摘要中统计方法信息不足，无法评估优点"],
        "statistics_limitations": limitations if limitations else ["摘要中统计方法信息不足"],
        "statistics_score_reason": level_desc,
        "statistics_review_level": review_level,
    }


def _extract_statistical_features(text: str) -> dict:
    """Extract statistical features from text (abstract/full-text)."""
    if not text:
        text = ""
    t = text.lower()

    features = {
        "statistical_tests": [],
        "model_type": "未识别",
        "effect_size_reported": "摘要未报告，需查看全文",
        "confidence_interval_reported": "摘要未报告，需查看全文",
        "p_value_reported": "摘要未报告，需查看全文",
        "sample_size_calculation": "摘要未报告，需查看全文",
        "multiple_comparison_correction": "摘要未报告，需查看全文",
        "missing_data_handling": "摘要未报告，需查看全文",
        "covariate_adjustment": "摘要未报告，需查看全文",
        "baseline_adjustment": "摘要未报告，需查看全文",
        "repeated_measures_handling": "摘要未报告，需查看全文",
        "normality_test": "摘要未报告，需查看全文",
        "variance_assumption": "摘要未报告，需查看全文",
        "intention_to_treat": "摘要未报告，需查看全文",
        "per_protocol_analysis": "摘要未报告，需查看全文",
        "cluster_handling": "摘要未报告，需查看全文",
        "subgroup_analysis": "摘要未报告，需查看全文",
        "sensitivity_analysis": "摘要未报告，需查看全文",
        "heterogeneity_analysis": "摘要未报告，需查看全文",
        "publication_bias_analysis": "摘要未报告，需查看全文",
        "software": "摘要未报告",
    }

    # Statistical tests
    test_patterns = [
        (r"\bt[- ]test\b", "t-test"),
        (r"\bpaired[- ]t\b", "paired t-test"),
        (r"\banova\b", "ANOVA"),
        (r"\brepeated measures (?:anova|analysis)", "repeated-measures ANOVA"),
        (r"\bmanova\b", "MANOVA"),
        (r"\bancova\b", "ANCOVA"),
        (r"\bchi[-\s]square\b|\bχ[²2]\b", "chi-square"),
        (r"\bmixed[\s-]*(?:effects?\s*)?model\b", "mixed-effects model"),
        (r"\b(?:generalized\s+)?linear\s+mixed\b", "linear mixed model"),
        (r"\bgee\b|generalized\s+estimating", "GEE"),
        (r"\bmann[-\s]whitney\b", "Mann-Whitney U"),
        (r"\bwilcoxon\b", "Wilcoxon"),
        (r"\bkruskal[-\s]wallis\b", "Kruskal-Wallis"),
        (r"\bfriedman\b", "Friedman test"),
        (r"\blogistic\s+regression\b", "logistic regression"),
        (r"\bcox\s+regression\b", "Cox regression"),
        (r"\bmeta[\s-]*regression\b", "meta-regression"),
        (r"\bpearson\b", "Pearson correlation"),
        (r"\bspearman\b", "Spearman correlation"),
        (r"\bbonferroni\b", "Bonferroni correction"),
        (r"\btukey\b", "Tukey HSD"),
        (r"\bholm\b", "Holm correction"),
        (r"\bfalse\s+discovery\s+rate\b", "FDR correction"),
    ]
    for pattern, name in test_patterns:
        if re.search(pattern, t, re.IGNORECASE):
            features["statistical_tests"].append(name)

    # Model type
    if any(m in t for m in ["mixed model", "mixed-effect", "linear mixed"]):
        features["model_type"] = "mixed-effects model"
    elif any(m in t for m in ["ancova", "analysis of covariance"]):
        features["model_type"] = "ANCOVA"
    elif "repeated measures anova" in t:
        features["model_type"] = "repeated-measures ANOVA"
    elif "anova" in t:
        features["model_type"] = "ANOVA"
    elif any(m in t for m in ["regression", "logistic", "cox"]):
        features["model_type"] = "regression model"
    elif any(m in t for m in ["gee", "generalized estimating"]):
        features["model_type"] = "GEE"

    # Effect size
    es_patterns = [
        r"\b(?:cohen'?s?\s*d|hedges'?\s*g|glass'?\s*delta|η[²2p]|partial\s*η|eta[-\s]*square|omega[-\s]*square)\b",
        r"\beffect\s*size\b", r"\bstandardized\s*(?:mean\s*)?difference\b",
        r"\b(?:odds\s*ratio|hazard\s*ratio|risk\s*ratio|relative\s*risk)\b",
        r"\b(?:MD|SMD|WMD)\b", r"\b(?:ES|d\s*=|g\s*=)\b",
    ]
    if any(re.search(p, t) for p in es_patterns):
        features["effect_size_reported"] = "是"

    # Confidence interval
    if re.search(r"\b(?:95%\s*CI|confidence\s*interval|CI\s*95|95%\s*confidence)\b", t):
        features["confidence_interval_reported"] = "是"

    # p-value
    if re.search(r"\bp\s*[<>=]\s*\.?\d", t):
        features["p_value_reported"] = "是"

    # Sample size calculation / power
    if re.search(r"\b(?:power\s*analys|sample\s*size\s*(?:calcul|estimat|determin)|a\s*priori\s*power)\b", t):
        features["sample_size_calculation"] = "是"

    # Multiple comparison correction
    if re.search(r"\b(?:bonferroni|tukey|holm|sid[áa]k|false\s+discovery|FDR|family[-\s]wise|multiple\s+comparison\s+correct)\b", t):
        features["multiple_comparison_correction"] = "是"

    # Missing data
    if re.search(r"\b(?:missing\s+data|intention[-\s]to[-\s]treat|ITT|last\s+observation|multiple\s+imputation|complete\s+case|sensitivity\s+analys)\b", t):
        features["missing_data_handling"] = "是"
        features["intention_to_treat"] = "是" if re.search(r"intention[-\s]to[-\s]treat|ITT", t) else "摘要未报告"

    # Covariate/baseline
    if re.search(r"\b(?:adjust(?:ed)?\s+for|covariate|confound(?:ing|er)|propensity|multivari(?:ate|able))\b", t):
        features["covariate_adjustment"] = "是"
    if re.search(r"\b(?:baseline\s+adjust|adjusted\s+baseline|ANCOVA)\b", t):
        features["baseline_adjustment"] = "是"

    # Repeated measures
    if re.search(r"\b(?:repeated\s+measures|mixed[\s-]*effects?\s*model|linear\s+mixed|within[\s-]*subject|paired\s+t|pre[\s-]*post)\b", t):
        features["repeated_measures_handling"] = "是"

    # Normality
    if re.search(r"\b(?:shapiro[-\s]wilk|kolmogorov[-\s]smirnov|normality|normal\s+distribution|q[\s-]*q\s*plot|skewness|kurtosis)\b", t):
        features["normality_test"] = "已报告"

    # Software
    sw_patterns = re.findall(
        r"\b(?:SPSS|SAS|Stata|R\s*(?:Studio|package)?|Python|MATLAB|GraphPad|Prism|JASP|jamovi|Mplus|WinBUGS|OpenBUGS|JAGS|Stan)\b",
        t, re.IGNORECASE
    )
    if sw_patterns:
        features["software"] = ", ".join(dict.fromkeys(sw_patterns))

    # Heterogeneity (for meta-analyses)
    if re.search(r"\b(?:heterogeneity|I[²2]|I[\s-]*square|tau[²2]|Q[\s-]*test|Q[\s-]*statistic)\b", t):
        features["heterogeneity_analysis"] = "是"

    # Publication bias
    if re.search(r"\b(?:publication\s*bias|funnel\s*plot|egger'?s\s*test|trim\s*and\s*fill|fail[\s-]*safe)\b", t):
        features["publication_bias_analysis"] = "是"

    # Sensitivity analysis
    if re.search(r"\b(?:sensitivity\s*analys|leave[\s-]*one[\s-]*out|influence\s*analys)\b", t):
        features["sensitivity_analysis"] = "是"

    # Subgroup analysis
    if re.search(r"\b(?:subgroup|moderator\s*analys|stratified|sub[\s-]*group)\b", t):
        features["subgroup_analysis"] = "是"

    return features
