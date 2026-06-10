"""Journal club reporter — generate rigorous, publication-quality reports for group discussion.

Each report is a comprehensive Markdown document covering 19+ sections,
designed for graduate-level journal club or research group meetings.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from src.config import OUTPUTS_DIR
from src.utils import logger


REPORTS_DIR = OUTPUTS_DIR / "journal_club_reports"


def generate_report(paper: dict, strict_appraisal: dict,
                     user_topic: str = "") -> str:
    """Generate a full journal club report Markdown string.

    Args:
        paper: Paper metadata dict
        strict_appraisal: Complete appraisal dict from strict_literature_search
        user_topic: Original user research topic (for context)

    Returns:
        Full Markdown report string
    """
    title = paper.get("title", "未获取") or "未获取"
    authors = paper.get("authors_str", "") or paper.get("authors", "") or "未获取"
    if isinstance(authors, list):
        authors = "; ".join(authors)
    # Get first author's last name
    first_author = "unknown"
    if authors and authors != "未获取":
        parts = authors.split(";")
        if parts:
            names = parts[0].strip().split()
            first_author = names[-1] if names else "unknown"

    year = paper.get("year", "?") or "?"
    journal = paper.get("journal", "未获取") or "未获取"
    doi = paper.get("doi", "未获取") or "未获取"
    pmid = paper.get("pmid", "未获取") or "未获取"
    source = paper.get("source", "未获取")

    # Appraisal data
    je = strict_appraisal.get("journal_evaluation", {})
    sde = strict_appraisal.get("study_design_evaluation", {})
    se = strict_appraisal.get("statistics_evaluation", {})
    be = strict_appraisal.get("bias_and_evidence", {})
    re = strict_appraisal.get("relevance_evaluation", {})
    oa = strict_appraisal.get("overall_appraisal", {})

    report = f"""# 组会文献汇报报告

> **自动生成时间:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
> **生成工具:** Sports Science Research Agent — 严格文献检索与评判模块
> **基于信息:** {'全文' if paper.get('full_text') else '题录与摘要'}

---

## 一、文献基本信息

| 属性 | 值 |
|------|-----|
| 标题 | {title} |
| 作者 | {authors} |
| 年份 | {year} |
| 期刊 | {journal} |
| DOI | {doi} |
| PMID | {pmid} |
| 数据来源 | {source} |
| 研究类型 | {sde.get('study_type', '未识别')} |
| 运动科学领域 | {paper.get('research_domain', '未分类')} |
| 期刊JCR分区 | {je.get('jcr_quartile', '未获取')} |
| 影响因子 | {je.get('impact_factor', '未获取')} |
| 期刊信息核验状态 | {je.get('journal_rank_status', '未核验')} |
| 是否已纳入本地文献库 | {"是" if paper.get('in_library') else "否"} |

"""

    # If only abstract-based, add disclaimer
    if not paper.get("full_text"):
        report += """
> ⚠️ **重要提示:** 本报告主要基于题录和摘要自动生成。由于未获取全文，关于随机化、盲法、样本量估算、统计模型细节、效应量和偏倚风险的评价需要结合全文进一步核验。

"""

    # ── Section 二: Reading value ──
    report += f"""## 二、阅读价值判断

"""

    oa_score = oa.get("overall_quality_score")
    oa_rec = oa.get("recommendation", "unknown")

    if oa_rec == "include":
        report += "**该文献值得深入阅读。** "
        if oa_score is not None and oa_score >= 8:
            report += "综合评价高，研究设计严谨，统计方法合理，与主题高度相关。"
        else:
            report += "综合评价可接受，主题相关性强。"
    elif oa_rec == "maybe":
        report += "**该文献具有参考价值，但存在一定局限。** "
        report += "建议选择性阅读其方法和讨论部分，关注其局限性是否影响研究结论。"
    elif oa_rec == "manual_review":
        report += "**该文献需要人工审核后决定是否深入阅读。** "
        report += "当前评价信息不足，部分关键字段（如期刊分区、统计方法细节等）需补充。"
    else:
        report += "**该文献不建议优先阅读。** "

    report += f"""
| 评分维度 | 数值 |
|----------|------|
| 综合评分 | {oa_score if oa_score is not None else '未计算'}/10 |
| 设计评分 | {oa.get('design_score', '?')}/10 |
| 统计评分 | {oa.get('statistics_score', '?')}/10 |
| 相关性评分 | {oa.get('relevance_score', '?')}/10 |
| 偏倚风险评分 | {oa.get('risk_of_bias_score', '?')}/10 |
| 报告质量评分 | {oa.get('reporting_quality_score', '?')}/10 |
| 评价可信度 | {oa.get('confidence_in_appraisal', '?')} |

"""

    # ── Section 三: Background ──
    report += f"""## 三、研究背景与科学问题

{_summarize_background(paper)}

## 四、研究目的与假设

- **研究目的:** {paper.get('abstract', '摘要未获取')[:300] if paper.get('abstract') else '摘要未获取，需阅读全文'}
- **主要假设:** 摘要中未明确陈述 — 需阅读全文
- **次要假设:** 摘要中未明确陈述 — 需阅读全文
- **假设是否清晰:** 基于摘要无法判断

"""

    # ── Section 五: PICO ──
    pico = strict_appraisal.get("pico_peco", {})
    report += f"""## 五、PICO/PECO 拆解

| 要素 | 内容 |
|------|------|
| Population | {pico.get('population', '未提取') or '未提取'} |
| Intervention / Exposure | {pico.get('intervention_or_exposure', '未提取') or '未提取'} |
| Comparator | {pico.get('comparator', '未提取') or '未提取'} |
| Outcomes | {pico.get('outcomes', '未提取') or '未提取'} |
| Study design | {sde.get('study_type', '未识别')} |

"""

    # ── Section 六: Design evaluation ──
    report += f"""## 六、研究设计严格评价

- **研究设计类型:** {sde.get('study_type', '未识别')} (置信度: {sde.get('study_type_confidence', '?')})
- **判断依据:** {'; '.join(sde.get('study_type_evidence', ['无']))}

### 样本量与对象

"""
    interv = sde.get("intervention_details", {})
    if interv:
        for key, val in interv.items():
            report += f"- **{key}:** {val}\n"
    else:
        review = sde.get("review_details", {})
        if review:
            for key, val in review.items():
                report += f"- **{key}:** {val}\n"

    report += f"""
### 设计优点

"""
    for s in sde.get("design_strengths", ["未获取"]):
        report += f"- {s}\n"

    report += f"""
### 设计局限

"""
    for l in sde.get("design_limitations", ["未获取"]):
        report += f"- {l}\n"

    report += f"""
### 设计评分与理由

**Design Score: {sde.get('design_score', '?')}/10**

{sde.get('design_score_reason', '无')}

"""

    # ── Section 七: Outcomes ──
    report += f"""## 七、结局指标与测量方法

- **主要结局:** {interv.get('primary_outcome', '未明确') if interv else '未获取'}
- **次要结局:** {interv.get('secondary_outcomes', '未获取') if interv else '未获取'}
- **测量工具:** {interv.get('measurement_validity', '未获取') if interv else '未获取'}
- **指标是否具有实践意义:** 需结合全文和运动科学实践判断

"""

    # ── Section 八: Statistics evaluation ──
    report += f"""## 八、统计方法严格评价

"""
    for key, label in [
        ("statistical_tests", "使用的统计方法"),
        ("model_type", "统计模型"),
        ("sample_size_calculation", "样本量估算"),
        ("effect_size_reported", "效应量报告"),
        ("confidence_interval_reported", "置信区间报告"),
        ("p_value_reported", "p值报告"),
        ("multiple_comparison_correction", "多重比较校正"),
        ("missing_data_handling", "缺失数据处理"),
        ("repeated_measures_handling", "重复测量处理"),
        ("covariate_adjustment", "协变量调整"),
    ]:
        val = se.get(key, "未获取")
        if isinstance(val, list):
            val = ", ".join(val) if val else "未识别"
        report += f"- **{label}:** {val}\n"

    report += f"""
### 统计优点

"""
    for s in se.get("statistics_strengths", ["未获取"]):
        report += f"- {s}\n"

    report += f"""
### 统计局限

"""
    for l in se.get("statistics_limitations", ["未获取"]):
        report += f"- {l}\n"

    report += f"""
### 统计评分与理由

**Statistics Score: {se.get('statistics_score', '?')}/10** (评估级别: {se.get('statistics_review_level', '?')})

{se.get('statistics_score_reason', '无')}

"""

    # ── Section 九: Main results ──
    abstract = paper.get("abstract", "") or ""
    report += f"""## 九、主要结果与解释

> **说明:** 以下基于摘要自动提取，需对照全文核验。

### 1. 作者报告的结果
{abstract[:800] if abstract else '摘要未获取'}

### 2. 可以被数据支持的结论
基于现有信息无法判断 — 需阅读全文。

### 3. 需要谨慎解释的结论
基于现有信息无法判断 — 需阅读全文。

### 4. 尚不能得出的结论
基于现有信息无法判断 — 需阅读全文。

"""

    # ── Section 十: Bias ──
    report += f"""## 十、偏倚风险与证据等级

- **自动化偏倚风险初筛:** {be.get('risk_of_bias', 'unclear')}
- **评价工具:** {be.get('tool_used', '未指定')}

### 偏倚域评估

"""
    domains = be.get("risk_of_bias_domains", {})
    for domain, level in domains.items():
        report += f"| {domain} | {level} |\n"

    report += f"""
### 主要偏倚来源

"""
    for r in be.get("risk_of_bias_reasons", ["未获取"]):
        report += f"- {r}\n"

    report += f"""
- **证据等级:** {be.get('evidence_level', 'unknown')}
- **是否需要人工正式评价:** {"是，建议使用" + (be.get('tool_used', '')) + "进行正式评价" if be.get('risk_of_bias') != 'low' else "可作为参考"}

> ⚠️ {be.get('disclaimer', '该偏倚风险评价为自动化初筛')}

"""

    # ── Section 十一: Journal quality ──
    report += f"""## 十一、期刊质量与发表层级评价

| 属性 | 值 |
|------|-----|
| 期刊名称 | {je.get('journal_name', '未获取')} |
| 匹配状态 | {je.get('journal_match_status', '未匹配')} |
| JCR分区 | {je.get('jcr_quartile', '未获取')} |
| 中科院分区 | {je.get('cas_quartile', '未获取')} |
| 影响因子 | {je.get('impact_factor', '未获取')} |
| 核验来源 | {je.get('ranking_source', '未获取')} |
| 期刊评分 | {je.get('journal_score', 'null')} |
| 是否为运动科学相关期刊 | {je.get('journal_rank_status', '未获取')} |
| 期刊评价限制 | {je.get('journal_score_reason', '未获取')} |

"""

    # ── Section 十二: Methodological strengths ──
    report += f"""## 十二、方法学优点

"""
    ds = sde.get("design_strengths", [])
    ss = se.get("statistics_strengths", [])
    all_strengths = ds + ss
    if len(all_strengths) > 1:
        for i, s in enumerate(all_strengths[:5], 1):
            report += f"{i}. {s}\n"
    else:
        report += "摘要信息不足，需阅读全文判断。\n"

    report += f"""
## 十三、主要局限

"""
    dl = sde.get("design_limitations", [])
    sl = se.get("statistics_limitations", [])
    all_lims = dl + sl
    if len(all_lims) > 1:
        for i, l in enumerate(all_lims[:7], 1):
            impact = _assess_limitation_impact(l)
            report += f"{i}. {l}\n   - **对结论可信度的影响:** {impact}\n"
    else:
        report += "摘要信息不足，需阅读全文判断。\n"

    # ── Section 十四: Practical significance ──
    report += f"""## 十四、运动科学实践意义

"""
    topic_lower = user_topic.lower() if user_topic else ""
    significance_areas = [
        ("训练计划设计", any(kw in topic_lower for kw in ["training", "exercise", "train", "训练",
                                                            "strength", "endurance", "hiit", "interval"])),
        ("体能监控", any(kw in topic_lower for kw in ["monitor", "load", "fatigue", "hrv",
                                                       "heart rate", "recovery", "体能"])),
        ("运动康复", any(kw in topic_lower for kw in ["rehab", "acl", "injury", "pain", "tendon",
                                                       "康复", "损伤"])),
        ("伤病预防", any(kw in topic_lower for kw in ["prevent", "injury", "risk", "预防", "损伤"])),
        ("健康促进", any(kw in topic_lower for kw in ["health", "fitness", "elderly", "older",
                                                       "diabetes", "obesity", "健康", "老年"])),
        ("竞技表现提升", any(kw in topic_lower for kw in ["performance", "elite", "athlete",
                                                           "sprint", "power", "jump", "表现"])),
    ]

    for area, relevant in significance_areas:
        if relevant:
            report += f"- **{area}:** 主题相关 — 需结合具体结果分析实践应用价值\n"
        else:
            report += f"- **{area}:** 可能与本研究领域间接相关\n"

    # ── Section 十五: Implications ──
    report += f"""## 十五、对我方研究的启示

- **可借鉴的研究设计:** 需阅读全文后总结
- **可借鉴的干预方案:** 需阅读全文后总结
- **可借鉴的测量指标:** 需阅读全文后总结
- **可借鉴的统计方法:** {se.get('model_type', '未识别') or '未识别'} — 若适用可参考
- **需要避免的问题:** {'; '.join(all_lims[:3]) if all_lims else '需阅读全文后总结'}
- **可进一步提出的研究假设:** 见下文研究空白分析

"""

    # ── Section 十六: Recommendation ──
    rec = oa.get("recommendation", "unknown")
    rec_map = {"include": "✅ 纳入", "maybe": "⚠️ 待定",
               "exclude": "❌ 排除", "manual_review": "🔍 需人工审核"}
    report += f"""## 十六、是否建议纳入文献库？

- **推荐结果:** {rec_map.get(rec, rec)}
- **推荐理由:** {oa.get('recommendation_reason', '未计算')}

"""

    if rec == "include":
        report += "- **推荐阅读等级:** 推荐\n"
        report += "- **适合用途:** 理论背景 / 方法借鉴 / 数据比较 / 综述引用\n"
    elif rec == "maybe":
        report += "- **推荐阅读等级:** 可选\n"
        report += "- **适合用途:** 具体方法参考 / 背景补充\n"
    elif rec == "manual_review":
        report += "- **推荐阅读等级:** 需人工评估后决定\n"
    else:
        report += "- **推荐阅读等级:** 不建议优先阅读\n"

    # ── Section 十七: Discussion questions ──
    report += f"""## 十七、组会讨论问题

"""
    questions = _generate_discussion_questions(paper, strict_appraisal)
    for i, q in enumerate(questions, 1):
        report += f"{i}. {q}\n"

    # ── Section 十八: PPT outline ──
    report += f"""## 十八、PPT 汇报大纲

1. **标题页** — {title[:80]}
2. **为什么选这篇文章** — 阅读价值与选题意义
3. **研究背景与科学问题** — {user_topic or '见标题'}
4. **PICO/PECO** — 研究要素拆解
5. **研究设计** — {sde.get('study_type', '未识别')}
6. **干预与测量** — 方案概述与结局指标
7. **统计方法** — {se.get('model_type', '未识别') or '待提取'}
8. **主要结果** — 关键发现（需全文）
9. **方法学与统计学评价** — Design: {sde.get('design_score', '?')}/10, Stats: {se.get('statistics_score', '?')}/10
10. **实践意义** — 对运动科学实践的启示
11. **对我方研究启示** — 可借鉴与需避免的问题
12. **讨论问题与总结**

"""

    # ── Section 十九: References ──
    apa_ref = _format_apa_for_report(paper)
    vancouver_ref = _format_vancouver_for_report(paper)

    report += f"""## 十九、参考文献格式

**APA:**
{apa_ref}

**Vancouver:**
{vancouver_ref}

---

*报告由 Sports Science Research Agent 自动生成。所有评价需经人工核验。*
*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""

    return report


def save_report(report_md: str, paper: dict) -> str:
    """Save report to disk and return the file path."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y%m%d")
    authors = paper.get("authors_str", "") or paper.get("authors", "") or "unknown"
    if isinstance(authors, list):
        authors = "; ".join(authors)
    first_author = "unknown"
    if authors:
        parts = authors.split(";")
        if parts:
            names = parts[0].strip().split()
            first_author = names[-1] if names else authors[:20]

    year = paper.get("year", "?") or "?"
    title = paper.get("title", "untitled") or "untitled"
    # Sanitize filename
    short_title = "".join(c for c in title[:40] if c.isalnum() or c in " _-").strip().replace(" ", "_")

    filename = f"{date_str}_{first_author}_{year}_{short_title}.md"
    filepath = REPORTS_DIR / filename

    try:
        filepath.write_text(report_md, encoding="utf-8")
        logger.info(f"Journal club report saved: {filepath}")
        return str(filepath)
    except Exception as e:
        logger.error(f"Failed to save report: {e}")
        return ""


def _summarize_background(paper: dict) -> str:
    """Extract or infer research background from paper metadata."""
    abstract = paper.get("abstract", "") or ""
    if not abstract:
        return "摘要未获取，无法总结研究背景。需阅读全文。"

    # Return first 2-3 sentences of abstract as background proxy
    sentences = abstract.replace("\n", " ").split(". ")
    background_sentences = sentences[:3]
    summary = ". ".join(background_sentences) + "."
    if len(summary) > 600:
        summary = summary[:600] + "..."

    return summary


def _assess_limitation_impact(limitation: str) -> str:
    """Assess how a limitation affects conclusion credibility."""
    lim_lower = limitation.lower()

    if "sample size" in lim_lower and ("小" in lim_lower or "small" in lim_lower):
        return "样本量不足可能导致II类错误，真阳性效应可能未被检出，且外推性受限"
    elif "盲法" in lim_lower or "blind" in lim_lower:
        return "缺乏盲法可能导致测量偏倚和期望效应，对主观结局指标影响较大"
    elif "随机" in lim_lower or "random" in lim_lower:
        return "缺乏随机化增加选择偏倚风险，组间基线可能不可比，因果推断受限"
    elif "多重比较" in lim_lower or "multiple comparison" in lim_lower:
        return "多重比较未校正增加I类错误风险，阳性结果可能为假阳性"
    elif "效应量" in lim_lower or "effect size" in lim_lower:
        return "未报告效应量影响对实际意义（非统计显著性）的判断，限制实践应用"
    elif "dropout" in lim_lower or "脱落" in lim_lower:
        return "脱落信息缺失可能导致完成者偏倚，影响ITT分析的可行性"
    elif "统计" in lim_lower or "statistic" in lim_lower:
        return "统计方法信息不足影响对分析适当性的判断，结论可信度降低"
    else:
        return "该局限可能影响结论的精确性和外推性，需在解读时考虑"


def _generate_discussion_questions(paper: dict, appraisal: dict) -> list[str]:
    """Generate 8-10 high-quality discussion questions."""
    title = paper.get("title", "该研究")
    oa = appraisal.get("overall_appraisal", {})

    questions = [
        f'该研究 "{title[:60]}..." 解决的科学问题是否足够重要？该问题与当前运动科学领域的热点议题有何关联？',
        f"研究对象的选择是否合理？是否存在选择偏倚？结果是否可以推广到其他人群（如不同年龄、性别、训练水平）？",
        f"研究设计是否足以回答所提出的科学问题？若让你重新设计，你会做出哪些改变？",
        f"干预方案（或暴露定义）是否足够清晰和可复制？在实际训练/临床环境中是否可以实施？",
        f"统计方法是否匹配研究设计和数据特征？是否存在未处理的混杂因素？如果数据是重复测量设计，分析方法是否考虑了这一点？",
        f"该研究是否报告了效应量和置信区间？结果的统计显著性与实际意义是否一致？最小有意义变化（SWC/MCID）是否被讨论？",
        f"作者的结论是否超过了数据支持的范围？是否存在过度外推或因果推断不当？",
    ]

    if oa.get("design_score", 0) < 7:
        questions.append("该研究存在哪些关键方法学局限？这些局限对结论的影响有多大？是否可以通过统计方法（如敏感性分析）缓解？")

    questions.append("该研究结果如何应用于我们当前的研究方向？我们可以借鉴哪些方法、避免哪些问题？")

    bias = appraisal.get("bias_and_evidence", {})
    if bias.get("risk_of_bias") in ("high", "some_concerns"):
        questions.append("该研究的偏倚风险主要在哪些领域？如果偏倚风险较高，该研究在系统综述中应如何处理（敏感性分析排除 vs 纳入但降级）？")

    questions.append("基于该研究的发现和局限，下一步最有价值的研究方向是什么？你会提出怎样的研究假设？")

    return questions[:10]


def _format_apa_for_report(paper: dict) -> str:
    """Format paper as APA style reference."""
    authors = paper.get("authors_str", "") or paper.get("authors", "") or "Unknown"
    if isinstance(authors, list):
        authors = ", ".join(authors)
    year = paper.get("year", "n.d.") or "n.d."
    title = paper.get("title", "Untitled") or "Untitled"
    journal = paper.get("journal", "") or ""
    doi = paper.get("doi", "") or ""

    ref = f"{authors} ({year}). {title}."
    if journal:
        ref += f" *{journal}*."
    if doi:
        ref += f" https://doi.org/{doi}"
    return ref


def _format_vancouver_for_report(paper: dict) -> str:
    """Format paper as Vancouver style reference."""
    authors_str = paper.get("authors_str", "") or paper.get("authors", "") or "Anonymous"
    if isinstance(authors_str, list):
        authors_str = ", ".join(authors_str)
    title = paper.get("title", "Untitled") or "Untitled"
    journal = paper.get("journal", "") or ""
    year = paper.get("year", "") or ""
    doi = paper.get("doi", "") or ""

    ref = f"{authors_str}. {title}. {journal}."
    if year:
        ref += f" {year}."
    if doi:
        ref += f" doi: {doi}"
    return ref
