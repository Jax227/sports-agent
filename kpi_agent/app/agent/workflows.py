"""
Agent workflow orchestrators.

Each workflow implements one stage of the KPI lifecycle:
1. Create project
2. Define PO
3. Analyze demands
4. Build performance model
5. Generate KPIs
6. Evaluate athlete
7. Generate intervention plan
8. Generate report

Principles:
- Never jump to KPIs without confirming PO first.
- Every KPI must link back to a PO, a determinant, and an evidence source.
- Evidence level and data quality must be flagged.
- Athlete level affects the applicability of research findings.
- The model is dynamic — it supports iteration as new data arrives.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session
from app import crud
from app import models
from app.agent.performance_model import (
    build_determinants_from_template,
    build_interventions_from_template,
    get_template,
)
from app.agent.kpi_generator import generate_kpis_for_determinants
from app.agent.evidence_model_generator import generate_model, save_model_to_db


def _now():
    return datetime.utcnow()


# ═══════════════════════════════════════════════════════════════
#  Workflow 1: Create Project
# ═══════════════════════════════════════════════════════════════

def workflow_create_project(
    db: Session,
    name: str,
    sport_type: str,
    project_type: str,
    description: str,
    level: str,
    target_competition: str,
    existing_info: str,
) -> dict:
    """Create a new project and return initial analysis."""
    project = crud.create_project(db, {
        "name": name,
        "sport_type": sport_type,
        "project_type": project_type,
        "description": description,
        "level": level,
        "target_competition": target_competition,
    })

    # Check for built-in template
    template = get_template(sport_type)
    has_template = template is not None

    # Identify missing info
    missing_info = []
    if not description:
        missing_info.append("项目描述（训练阶段、主要目标等）")
    if not target_competition:
        missing_info.append("目标赛事名称和日期")
    missing_info.extend([
        "运动员基本信息（姓名、年龄、水平、训练年限等）",
        "运动员历史比赛成绩和当前最佳成绩",
        "可用的测试设备和数据收集工具",
        "教练员经验和执教理念",
    ])
    if not has_template:
        missing_info.append("该项目暂无内置模板，建议手动添加项目需求分析资料")

    summary_lines = [
        f"项目 '{name}' 已创建成功。",
        f"",
        f"**运动类型**: {sport_type}",
        f"**项目类型**: {project_type}",
        f"**水平**: {level}",
    ]
    if has_template:
        summary_lines.append(f"✅ 系统包含该项目的内置表现模型模板，可以直接使用。")
    else:
        summary_lines.append(f"⚠️ 系统暂无该项目的内置模板，需要手动建立表现模型。")

    return {
        "project": project,
        "summary": "\n".join(summary_lines),
        "missing_info": missing_info,
    }


# ═══════════════════════════════════════════════════════════════
#  Workflow 2: Define Performance Outcome
# ═══════════════════════════════════════════════════════════════

def workflow_define_po(
    db: Session,
    project_id: int,
    desired_outcome: str,
    how_measured: str,
    target_value_input: Optional[float],
    target_unit: str,
    baseline_value_input: Optional[float],
    target_date: Optional[datetime],
    comparison_target: str,
) -> dict:
    """Help user define clear, measurable POs with quality checks."""

    # Determine outcome type from description
    outcome_type = "成绩"
    if "排名" in desired_outcome or "名次" in desired_outcome:
        outcome_type = "排名"
    elif "奖牌" in desired_outcome or "金牌" in desired_outcome:
        outcome_type = "奖牌"
    elif "选拔" in desired_outcome or "资格" in desired_outcome or "达标" in desired_outcome:
        outcome_type = "选拔资格"
    elif "胜率" in desired_outcome or "胜" in desired_outcome:
        outcome_type = "胜率"

    outcome = crud.create_outcome(db, project_id, {
        "name": desired_outcome,
        "description": f"测量方式: {how_measured}",
        "outcome_type": outcome_type,
        "target_value": target_value_input,
        "unit": target_unit,
        "target_date": target_date,
        "baseline_value": baseline_value_input,
        "current_value": baseline_value_input,
        "priority": 1,
        "evidence_notes": f"对比参照: {comparison_target}" if comparison_target else "",
    })

    # Quality check
    quality = {
        "specific": bool(desired_outcome and target_value_input),
        "measurable": bool(target_value_input and target_unit),
        "time_bound": target_date is not None,
        "realistic": True,  # Needs external validation
        "has_baseline": baseline_value_input is not None,
    }
    score = sum(quality.values())
    quality["overall_score"] = score
    quality["overall_rating"] = (
        "优秀" if score >= 5 else
        "良好" if score >= 3 else
        "需要改进"
    )

    suggestions = []
    if not quality["specific"]:
        suggestions.append("建议将目标具体化，例如从'提升表现'改为'800米成绩从1:55提升至1:48'。")
    if not quality["measurable"]:
        suggestions.append("建议明确测量单位和评估方式。")
    if not quality["time_bound"]:
        suggestions.append("建议设定明确的目标日期。")
    if not quality["has_baseline"]:
        suggestions.append("建议输入当前基准值，以便追踪进步。")

    return {
        "outcome": outcome,
        "quality_check": quality,
        "suggestions": suggestions,
    }


# ═══════════════════════════════════════════════════════════════
#  Workflow 3: Analyze Demands
# ═══════════════════════════════════════════════════════════════

CATEGORY_INFO = {
    "生理要求": {
        "description": "运动项目的生理负荷特征，包括能量代谢、心血管需求、运动模式等",
        "why_important": "用于设计适当的训练策略，优化影响运动表现的关键生理变量，并为营养策略制定提供依据",
        "sources": "科学文献、教练员手册、运动员历史测试数据、可穿戴设备数据、比赛监测数据",
    },
    "技术要求": {
        "description": "完成运动项目所需的专项技术能力",
        "why_important": "有助于评估专项技术能力，并制定提高技术完成速度和质量训练计划",
        "sources": "科学文献、教练员手册、视频分析、技术统计、比赛记录",
    },
    "战术要求": {
        "description": "比赛中需要做出的战术决策和行为模式",
        "why_important": "确定运动员在比赛中需要做出哪些动作才有可能取得成功，以及执行战术要求可能需要哪些极限技能",
        "sources": "教练员手册、比赛录像、技战术统计、对手分析报告、官方规则",
    },
    "营养要求": {
        "description": "训练和比赛中的能量、营养素和水分需求",
        "why_important": "优化训练适应、比赛表现和恢复的营养策略基础",
        "sources": "运动营养文献、教练员手册、营养师评估",
    },
    "心理技能": {
        "description": "比赛所需心理素质，包括注意力、焦虑管理、决策等",
        "why_important": "支持确定运动员水平所需的特定评估，以及制定旨在最大限度提升运动表现的心理干预措施",
        "sources": "科学文献、教练员手册、心理测评、比赛行为记录",
    },
    "器材特点": {
        "description": "训练和比赛所用器材的特征和要求",
        "why_important": "为运动员提供适当和有益的器材建议，开发个人解决方案",
        "sources": "教练员手册、规则手册、器材规格文档、运动员反馈",
    },
    "健康": {
        "description": "运动项目特有的健康风险和伤病模式",
        "why_important": "设计预防策略和目标训练计划，使运动员在做好准备的同时降低损伤风险",
        "sources": "流行病学研究、教练员经验、运动员病史、体能测试、康复记录",
    },
    "比赛规则": {
        "description": "相关监管规则、入选标准、选拔标准和取消比赛资格原因",
        "why_important": "确定比赛胜负条件以及具体干预措施的适当性、相关性和可能性",
        "sources": "官方规则手册（必须读取最新版本）、官方协会网站、竞赛规程",
    },
}


def workflow_analyze_demands(
    db: Session,
    project_id: int,
    additional_notes: str = "",
) -> dict:
    """Analyze project demands across all categories."""
    project = crud.get_project(db, project_id)
    if not project:
        return {"project_id": project_id, "categories": [], "overall_completeness": "项目不存在"}

    existing_determinants = crud.get_determinants(db, project_id)
    existing_categories = {d.category for d in existing_determinants}
    existing_sources = crud.get_evidence_sources(db, project_id)
    athletes = crud.get_athletes(db, project_id)

    categories = []
    for cat_name, cat_info in CATEGORY_INFO.items():
        cat_dets = [d for d in existing_determinants if d.category == cat_name]
        categories.append({
            "category": cat_name,
            "description": cat_info["description"],
            "why_important": cat_info["why_important"],
            "possible_sources": cat_info["sources"],
            "existing_evidence": len(cat_dets),
            "missing_info": "需要补充具体因素" if not cat_dets else "",
            "search_directions": f"检索 {project.sport_type} 相关{cat_name}文献",
            "possible_kpis": [f"{d.name}相关指标" for d in cat_dets],
        })

    completeness = "低"
    if len(existing_categories) >= 6 and existing_sources:
        completeness = "高"
    elif len(existing_categories) >= 4:
        completeness = "中"

    return {
        "project_id": project_id,
        "categories": categories,
        "overall_completeness": completeness,
    }


# ═══════════════════════════════════════════════════════════════
#  Workflow 4: Build Performance Model
# ═══════════════════════════════════════════════════════════════

def workflow_build_performance_model(
    db: Session,
    project_id: int,
    coach_input: str = "",
) -> dict:
    """Build or retrieve the hierarchical performance model."""
    project = crud.get_project(db, project_id)
    if not project:
        return {"project_id": project_id, "determinants_tree": [], "kpi_candidates": []}

    # Use template if available
    template = get_template(project.sport_type)
    existing = crud.get_determinants(db, project_id)

    if template and not existing:
        build_determinants_from_template(db, project_id, project.sport_type)
        build_interventions_from_template(db, project_id, project.sport_type)

    tree = crud.get_determinant_tree(db, project_id)
    kpis = crud.get_kpis(db, project_id)

    kpi_candidates = []
    for k in kpis:
        kpi_candidates.append({
            "name": k.name,
            "unit": k.unit,
            "linked_to": {
                "determinant_id": k.determinant_id,
                "outcome_id": k.performance_outcome_id,
            },
        })

    return {
        "project_id": project_id,
        "determinants_tree": tree,
        "kpi_candidates": kpi_candidates,
    }


# ═══════════════════════════════════════════════════════════════
#  Workflow 5: Generate KPIs
# ═══════════════════════════════════════════════════════════════

def workflow_generate_kpis(db: Session, project_id: int) -> dict:
    """Generate KPIs based on the performance model."""
    project = crud.get_project(db, project_id)
    if not project:
        return {"project_id": project_id, "kpis": [], "kpi_count": 0}

    existing_kpis = crud.get_kpis(db, project_id)
    if not existing_kpis:
        # Generate from template
        generate_kpis_for_determinants(db, project_id, project.sport_type)

    kpis = crud.get_kpis(db, project_id)
    return {
        "project_id": project_id,
        "kpis": kpis,
        "kpi_count": len(kpis),
    }


# ═══════════════════════════════════════════════════════════════
#  Workflow 6: Evaluate Athlete
# ═══════════════════════════════════════════════════════════════

def workflow_evaluate_athlete(db: Session, athlete_id: int) -> dict:
    """Evaluate an athlete against their KPIs."""
    dashboard = crud.get_athlete_dashboard(db, athlete_id)
    if not dashboard:
        return {}

    # Extract gaps
    gaps = []
    for s in dashboard.get("kpi_summary", []):
        if s["latest_value"] is not None and s["target_value"] is not None:
            gap = s["target_value"] - s["latest_value"]
            gaps.append({
                "kpi": s["kpi_name"],
                "current": s["latest_value"],
                "target": s["target_value"],
                "gap": gap,
                "unit": s["unit"],
            })

    # Priority areas
    priority_areas = [g["kpi"] for g in sorted(gaps, key=lambda x: abs(x["gap"]), reverse=True)[:5]]

    return {
        "athlete_id": athlete_id,
        "strengths": dashboard.get("strengths", []),
        "weaknesses": dashboard.get("weaknesses", []),
        "gaps": gaps,
        "risk_alerts": dashboard.get("risk_alerts", []),
        "priority_areas": priority_areas,
    }


# ═══════════════════════════════════════════════════════════════
#  Workflow 7: Generate Intervention Plan
# ═══════════════════════════════════════════════════════════════

def workflow_intervention_plan(
    db: Session,
    project_id: int,
    athlete_id: Optional[int] = None,
    priority_kpi_ids: list[int] = None,
    cycle_length_weeks: int = 12,
) -> dict:
    """Generate an intervention plan targeting priority KPIs."""
    project = crud.get_project(db, project_id)
    if not project:
        return {"project_id": project_id, "interventions": [], "schedule_summary": ""}

    interventions = crud.get_interventions(db, project_id)
    if priority_kpi_ids:
        priority_kpi_ids = [int(x) for x in priority_kpi_ids]

    plan = []
    for i in interventions:
        related_kpis = []
        kpi = crud.get_kpi(db, i.kpi_id) if i.kpi_id else None
        if kpi:
            related_kpis.append(kpi.name)

        plan.append({
            "intervention_id": i.id,
            "name": i.name,
            "type": i.intervention_type,
            "target_kpis": related_kpis,
            "frequency": i.frequency or "按需",
            "intensity": i.intensity or "中等",
            "duration": i.duration or f"{cycle_length_weeks}周",
            "expected_effect": i.expected_effect or "",
            "risk_notes": i.risk_notes or "",
        })

    schedule_summary = f"针对 {project.name} 项目的 {cycle_length_weeks} 周干预计划，包含 {len(plan)} 项干预措施。"

    return {
        "project_id": project_id,
        "interventions": plan,
        "schedule_summary": schedule_summary,
    }


# ═══════════════════════════════════════════════════════════════
#  Workflow 8: Generate Report
# ═══════════════════════════════════════════════════════════════

def workflow_generate_report(
    db: Session,
    project_id: int,
    report_type: str,
    athlete_id: Optional[int] = None,
    extra_notes: str = "",
) -> dict:
    """Generate a report via the report generator and return it."""
    from app.agent.report_generator import generate_report
    report = generate_report(db, project_id, report_type, athlete_id, extra_notes)
    if not report:
        return {"report": None}
    return {"report": report}


# ═══════════════════════════════════════════════════════════════
#  Workflow 9: Generate Model from Evidence
# ═══════════════════════════════════════════════════════════════

def workflow_generate_model_from_evidence(
    db: Session,
    project_id: int,
    sport_name: str = "",
    sport_name_en: str = "",
    use_llm: bool = True,
    max_results_per_query: int = 8,
) -> dict:
    """
    Search literature and generate a performance model from evidence.

    Phase 1 (Search + Extract): Returns the model for user review.
    Phase 2 (Save): User confirms selected items, saves to DB.
    """
    project = crud.get_project(db, project_id)
    if not project:
        return {"error": "项目不存在"}

    search_sport = sport_name or project.sport_type

    model = generate_model(
        sport_name=search_sport,
        sport_name_en=sport_name_en,
        use_llm=use_llm,
        max_results_per_query=max_results_per_query,
    )

    return {
        "project_id": project_id,
        "sport_name": search_sport,
        "model": model,
    }


def workflow_confirm_evidence_model(
    db: Session,
    project_id: int,
    model: dict,
    selected_determinants: list[dict] = None,
    selected_kpis: list[dict] = None,
    selected_interventions: list[dict] = None,
) -> dict:
    """Save the user-confirmed evidence-based model to the database."""
    result = save_model_to_db(
        db,
        project_id,
        model,
        selected_determinants,
        selected_kpis,
        selected_interventions,
    )
    return {
        "project_id": project_id,
        "status": "saved",
        "summary": result,
    }
