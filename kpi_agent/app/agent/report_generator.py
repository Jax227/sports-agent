"""
Report generator — creates Markdown reports for various analysis types.

Report types:
- 项目需求分析报告
- PO与KPI设计报告
- 运动员评估报告
- KPI趋势报告
- 干预建议报告
- 数据质量报告
- 比赛复盘报告
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session
from app import crud
from app import models


def generate_report(
    db: Session,
    project_id: int,
    report_type: str,
    athlete_id: Optional[int] = None,
    extra_notes: str = "",
) -> Optional[models.Report]:
    """Route to the correct generator based on report_type."""
    project = crud.get_project(db, project_id)
    if not project:
        return None

    generators = {
        "项目需求分析报告": _gen_demand_analysis,
        "PO与KPI设计报告": _gen_po_kpi_design,
        "运动员评估报告": _gen_athlete_evaluation,
        "KPI趋势报告": _gen_kpi_trend,
        "干预建议报告": _gen_intervention_plan,
        "数据质量报告": _gen_data_quality,
        "比赛复盘报告": _gen_competition_review,
    }

    gen = generators.get(report_type)
    if not gen:
        content = f"# 未知报告类型\n\n报告类型 '{report_type}' 不在支持列表中。"
    else:
        content = gen(db, project, athlete_id, extra_notes)

    report = crud.create_report(db, project_id, {
        "report_type": report_type,
        "title": f"{project.name} - {report_type}",
        "content_markdown": content,
        "generated_at": datetime.utcnow(),
        "created_by": "system",
    })
    return report


def _gen_demand_analysis(db: Session, project, athlete_id, extra):
    """Generate project demand analysis report."""
    determinants = crud.get_determinants(db, project.id)
    rules = crud.get_rules(db, project.id)
    sources = crud.get_evidence_sources(db, project.id)

    categories = {}
    for d in determinants:
        if d.category not in categories:
            categories[d.category] = []
        categories[d.category].append(d)

    lines = [
        f"# 项目需求分析报告",
        f"",
        f"## 项目概况",
        f"",
        f"- **项目名称**: {project.name}",
        f"- **运动项目**: {project.sport_type}",
        f"- **项目类型**: {project.project_type}",
        f"- **水平**: {project.level}",
        f"- **目标赛事**: {project.target_competition}",
        f"- **生成时间**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
        f"",
    ]

    # Performance demands by category
    for cat_name, items in categories.items():
        lines.append(f"## {cat_name}")
        lines.append(f"")
        for item in items:
            importance_icon = {"关键": "!!! ", "重要": "!! ", "中等": "! ", "基本": ""}.get(item.importance, "")
            lines.append(f"### {importance_icon}{item.name}")
            if item.description:
                lines.append(f"")
                lines.append(item.description)
            lines.append(f"")
            lines.append(f"- **重要性**: {item.importance}")
            lines.append(f"- **证据等级**: {item.evidence_level}")
            if item.source_summary:
                lines.append(f"- **来源**: {item.source_summary}")
            lines.append(f"")

    # Missing info
    lines.append(f"## 待补充信息")
    lines.append(f"")
    if not rules:
        lines.append(f"- [ ] 比赛规则文件（官方规则手册）")
    if not sources:
        lines.append(f"- [ ] 科学文献来源")
    lines.append(f"- [ ] 教练员意见和执教经验")
    lines.append(f"- [ ] 运动员历史测试数据")
    lines.append(f"- [ ] 比赛录像分析")
    lines.append(f"")

    if extra:
        lines.append(f"## 补充说明")
        lines.append(f"")
        lines.append(extra)
        lines.append(f"")

    return "\n".join(lines)


def _gen_po_kpi_design(db: Session, project, athlete_id, extra):
    """Generate PO and KPI design report."""
    outcomes = crud.get_outcomes(db, project.id)
    kpis = crud.get_kpis(db, project.id)
    determinants = crud.get_determinants(db, project.id)
    interventions = crud.get_interventions(db, project.id)

    det_map = {d.id: d for d in determinants}

    lines = [
        f"# PO 与 KPI 设计报告",
        f"",
        f"## 项目概况",
        f"",
        f"- **项目名称**: {project.name}",
        f"- **运动项目**: {project.sport_type}",
        f"- **生成时间**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
        f"",
        f"## 表现目标 (PO)",
        f"",
    ]

    if outcomes:
        lines.append(f"| 目标 | 类型 | 目标值 | 基线值 | 当前值 | 目标日期 | 优先级 |")
        lines.append(f"|------|------|--------|--------|--------|----------|--------|")
        for o in outcomes:
            lines.append(
                f"| {o.name} | {o.outcome_type} | {o.target_value or '-'} {o.unit} | "
                f"{o.baseline_value or '-'} | {o.current_value or '-'} | "
                f"{o.target_date.strftime('%Y-%m-%d') if o.target_date else '-'} | {o.priority} |"
            )
    else:
        lines.append("⚠️ 尚未定义表现目标。")
    lines.append("")

    # KPI table
    lines.append(f"## KPI 清单")
    lines.append(f"")
    if kpis:
        lines.append(f"| KPI名称 | 关联决定因素 | 单位 | 目标值 | 测量频率 | 数据来源 | 证据等级 |")
        lines.append(f"|---------|-------------|------|--------|---------|----------|---------|")
        for k in kpis:
            det_name = det_map.get(k.determinant_id, None)
            det_name = det_name.name if det_name else "-"
            lines.append(
                f"| {k.name} | {det_name} | {k.unit} | {k.target_value or '-'} | "
                f"{k.measurement_frequency} | {k.data_source} | {k.evidence_level} |"
            )
    else:
        lines.append("⚠️ 尚未定义 KPI。")
    lines.append("")

    # Interventions
    lines.append(f"## 干预措施")
    lines.append(f"")
    if interventions:
        lines.append(f"| 干预名称 | 类型 | 描述 | 状态 |")
        lines.append(f"|---------|------|------|------|")
        for i in interventions:
            lines.append(f"| {i.name} | {i.intervention_type} | {i.description[:60]}... | {i.status} |")
    else:
        lines.append("⚠️ 尚未定义干预措施。")
    lines.append("")

    # Next steps
    lines.append(f"## 下一步计划")
    lines.append(f"")
    lines.append(f"1. 为每位运动员建立基线测试数据")
    lines.append(f"2. 确定各 KPI 的目标值和阈值")
    lines.append(f"3. 启动第一期干预措施并开始数据收集")
    lines.append(f"4. 4周后进行第一次阶段性评估")
    lines.append(f"")

    return "\n".join(lines)


def _gen_athlete_evaluation(db: Session, project, athlete_id, extra):
    """Generate athlete evaluation report."""
    athlete = crud.get_athlete(db, athlete_id) if athlete_id else None
    if not athlete:
        return "# 运动员评估报告\n\n⚠️ 未指定运动员。\n"

    dashboard = crud.get_athlete_dashboard(db, athlete_id)

    lines = [
        f"# 运动员评估报告",
        f"",
        f"## 运动员信息",
        f"",
        f"- **姓名**: {athlete.name}",
        f"- **性别**: {athlete.gender}",
        f"- **年龄**: {athlete.age or '-'}",
        f"- **身高**: {athlete.height or '-'} cm",
        f"- **体重**: {athlete.weight or '-'} kg",
        f"- **训练年限**: {athlete.training_age or '-'} 年",
        f"- **水平**: {athlete.level}",
        f"- **角色/位置**: {athlete.role or athlete.position or '-'}",
        f"- **生成时间**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
        f"",
        f"## 当前 KPI 状态",
        f"",
    ]

    if dashboard.get("kpi_summary"):
        lines.append(f"| KPI | 当前值 | 目标值 | 单位 |")
        lines.append(f"|-----|--------|--------|------|")
        for s in dashboard["kpi_summary"]:
            lines.append(f"| {s['kpi_name']} | {s['latest_value'] or '-'} | {s['target_value'] or '-'} | {s['unit']} |")
    lines.append("")

    # Strengths
    lines.append(f"## 优势")
    lines.append(f"")
    for s in dashboard.get("strengths", []):
        lines.append(f"- ✅ {s}")
    if not dashboard.get("strengths"):
        lines.append("暂无足够数据确定优势。")
    lines.append("")

    # Weaknesses
    lines.append(f"## 短板")
    lines.append(f"")
    for w in dashboard.get("weaknesses", []):
        lines.append(f"- ⚠️ {w}")
    if not dashboard.get("weaknesses"):
        lines.append("暂无足够数据确定短板。")
    lines.append("")

    # Risks
    lines.append(f"## 风险提示")
    lines.append(f"")
    for r in dashboard.get("risk_alerts", []):
        lines.append(f"- 🔴 {r}")
    if not dashboard.get("risk_alerts"):
        lines.append("当前无风险警报。")
    lines.append("")

    # Recommendations
    lines.append(f"## 建议")
    lines.append(f"")
    if athlete.injury_history:
        lines.append(f"- 注意伤病历史: {athlete.injury_history}")
    lines.append(f"- 优先提升短板 KPI")
    lines.append(f"- 定期复查关键指标")
    lines.append(f"")

    return "\n".join(lines)


def _gen_kpi_trend(db: Session, project, athlete_id, extra):
    """Generate KPI trend report."""
    kpis = crud.get_kpis(db, project.id)

    lines = [
        f"# KPI 趋势报告",
        f"",
        f"## 项目概况",
        f"",
        f"- **项目名称**: {project.name}",
        f"- **生成时间**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
        f"",
    ]

    for kpi in kpis:
        trend_data = crud.get_kpi_trend(db, kpi.id, athlete_id)
        measurements = trend_data.get("measurements", [])
        lines.append(f"### {kpi.name}")
        lines.append(f"")
        lines.append(f"- **单位**: {kpi.unit}")
        lines.append(f"- **趋势**: {trend_data.get('trend_direction', 'N/A')}")
        lines.append(f"- **分析**: {trend_data.get('trend_summary', 'N/A')}")
        lines.append(f"")
        if measurements:
            lines.append(f"| 日期 | 值 | 单位 | 情境 |")
            lines.append(f"|------|-----|------|------|")
            for m in measurements[:10]:
                lines.append(f"| {str(m.measured_at)[:10]} | {m.value} | {m.unit} | {m.context} |")
        lines.append("")

    return "\n".join(lines)


def _gen_intervention_plan(db: Session, project, athlete_id, extra):
    """Generate intervention plan report."""
    interventions = crud.get_interventions(db, project.id)
    kpis = crud.get_kpis(db, project.id)
    kpi_map = {k.id: k for k in kpis}

    lines = [
        f"# 训练干预建议报告",
        f"",
        f"## 项目概况",
        f"",
        f"- **项目名称**: {project.name}",
        f"- **生成时间**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
        f"",
        f"## 干预措施清单",
        f"",
    ]

    if interventions:
        lines.append(f"| 干预名称 | 类型 | 频率 | 强度 | 周期 | 预期效果 | 状态 |")
        lines.append(f"|---------|------|------|------|------|---------|------|")
        for i in interventions:
            lines.append(
                f"| {i.name} | {i.intervention_type} | {i.frequency or '-'} | "
                f"{i.intensity or '-'} | {i.duration or '-'} | "
                f"{i.expected_effect[:40] if i.expected_effect else '-'} | {i.status} |"
            )
    else:
        lines.append("⚠️ 尚未定义干预措施。")
    lines.append("")

    # Priority areas
    lines.append(f"## 优先干预方向")
    lines.append(f"")
    lines.append("根据 KPI 差距分析，建议优先关注以下领域：")
    lines.append("")
    for k in kpis[:5]:
        if k.current_value and k.target_value:
            gap = k.target_value - k.current_value
            if gap > 0:
                lines.append(f"- **{k.name}**: 差距 {gap:.1f} {k.unit}")
    lines.append("")

    return "\n".join(lines)


def _gen_data_quality(db: Session, project, athlete_id, extra):
    """Generate data quality and evidence level report."""
    kpis = crud.get_kpis(db, project.id)
    sources = crud.get_evidence_sources(db, project.id)
    determinants = crud.get_determinants(db, project.id)

    lines = [
        f"# 数据质量与证据等级报告",
        f"",
        f"## 项目概况",
        f"",
        f"- **项目名称**: {project.name}",
        f"- **生成时间**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
        f"",
        f"## KPI 数据质量评估",
        f"",
        f"| KPI | 证据等级 | 数据质量 | 数据来源 |",
        f"|-----|---------|---------|---------|",
    ]
    for k in kpis:
        lines.append(f"| {k.name} | {k.evidence_level} | {k.data_quality} | {k.data_source} |")
    lines.append("")

    # Unreliable KPIs
    unreliable = [k for k in kpis if k.evidence_level in ("低", "专家经验", "未知")]
    if unreliable:
        lines.append(f"## ⚠️ 需要验证的指标")
        lines.append(f"")
        for k in unreliable:
            lines.append(f"- {k.name} (证据等级: {k.evidence_level}, 数据质量: {k.data_quality})")
        lines.append("")

    # Evidence sources summary
    lines.append(f"## 证据来源汇总")
    lines.append(f"")
    lines.append(f"- 文献来源: {len(sources)} 条")
    lines.append(f"- 高证据等级来源: {len([s for s in sources if s.evidence_level == '高'])}")
    lines.append(f"- 中等证据等级来源: {len([s for s in sources if s.evidence_level == '中'])}")
    lines.append(f"- 低/专家经验来源: {len([s for s in sources if s.evidence_level in ('低', '专家经验')])}")
    lines.append("")

    return "\n".join(lines)


def _gen_competition_review(db: Session, project, athlete_id, extra):
    """Generate competition review report."""
    competitions = crud.get_competitions(db, project.id)

    lines = [
        f"# 比赛复盘报告",
        f"",
        f"## 项目概况",
        f"",
        f"- **项目名称**: {project.name}",
        f"- **生成时间**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
        f"",
    ]

    if competitions:
        for comp in competitions:
            lines.append(f"## {comp.name}")
            lines.append(f"")
            lines.append(f"- **日期**: {comp.date.strftime('%Y-%m-%d') if comp.date else '-'}")
            lines.append(f"- **级别**: {comp.competition_level}")
            lines.append(f"- **地点**: {comp.location}")
            lines.append(f"- **规则版本**: {comp.rules_version}")
            if comp.result_summary:
                lines.append(f"")
                lines.append(f"### 比赛总结")
                lines.append(f"")
                lines.append(comp.result_summary)
            lines.append(f"")
    else:
        lines.append("⚠️ 尚未记录比赛数据。")
    lines.append("")

    return "\n".join(lines)
