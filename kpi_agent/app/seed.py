"""
Seed data: Elite 800m Performance Project.

Creates a complete example project with:
- Project definition
- Performance outcomes (POs)
- Two athletes
- Performance determinants hierarchy
- KPIs with target values
- Interventions
- Sample measurements
- Evidence sources
- Competition and results
- A sample report

Usage:
    python -m app.seed
"""

from datetime import datetime, timedelta

from app.database import SessionLocal, engine, Base
from app import models, crud


def seed():
    """Seed the database with an 800m example project."""
    # Create tables
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Check if already seeded
        existing = crud.get_projects(db)
        if existing:
            print(f"Database already has {len(existing)} project(s). Skipping seed.")
            return

        # ── 1. Create Project ──────────────────────────────────
        project = crud.create_project(db, {
            "name": "Elite 800m Performance Project",
            "sport_type": "Athletics - 800m",
            "project_type": "计量类",
            "description": "精英级800米运动员表现优化项目，目标全国锦标赛",
            "level": "精英级",
            "target_competition": "National Championship 2026",
            "start_date": datetime(2026, 3, 1),
            "end_date": datetime(2026, 9, 1),
        })
        print(f"Created project: {project.name} (id={project.id})")

        # ── 2. Create Performance Outcomes ─────────────────────
        outcomes_data = [
            {
                "name": "800m 成绩目标 1:48.00",
                "description": "在全国锦标赛中跑出1:48.00以内",
                "outcome_type": "成绩",
                "target_value": 108.0,
                "unit": "s",
                "target_date": datetime(2026, 8, 1),
                "baseline_value": 114.0,
                "current_value": 114.0,
                "priority": 1,
            },
            {
                "name": "达到全国锦标赛决赛资格",
                "description": "全国锦标赛进入决赛（前8名）",
                "outcome_type": "选拔资格",
                "target_value": 8,
                "unit": "排名",
                "target_date": datetime(2026, 8, 1),
                "baseline_value": 15,
                "current_value": 15,
                "priority": 2,
            },
            {
                "name": "缩小与国内前三名平均成绩差距",
                "description": "与国内前三名平均成绩108.5秒的差距缩小到2秒以内",
                "outcome_type": "成绩",
                "target_value": 110.5,
                "unit": "s",
                "target_date": datetime(2026, 8, 1),
                "baseline_value": 114.0,
                "current_value": 114.0,
                "priority": 3,
            },
        ]
        outcomes = []
        for od in outcomes_data:
            o = crud.create_outcome(db, project.id, od)
            outcomes.append(o)
            print(f"  Created PO: {o.name}")

        # ── 3. Create Athletes ─────────────────────────────────
        athletes_data = [
            {
                "name": "Zhang Wei",
                "gender": "男",
                "age": 23,
                "height": 182.0,
                "weight": 70.0,
                "training_age": 8,
                "level": "国家级",
                "role": "800m 专项运动员",
                "injury_history": "2024年腘绳肌拉伤（已康复）；轻度跟腱炎史",
            },
            {
                "name": "Li Ming",
                "gender": "男",
                "age": 20,
                "height": 178.0,
                "weight": 66.0,
                "training_age": 5,
                "level": "国家级",
                "role": "800m 专项运动员",
                "injury_history": "无明显重大伤病史",
            },
        ]
        athletes = []
        for ad in athletes_data:
            a = crud.create_athlete(db, project.id, ad)
            athletes.append(a)
            print(f"  Created athlete: {a.name}")

        # ── 4. Create Performance Determinants (from template) ─
        from app.agent.performance_model import (
            build_determinants_from_template,
            build_interventions_from_template,
            get_template,
        )

        template = get_template(project.sport_type)
        if template:
            determinants = build_determinants_from_template(db, project.id, project.sport_type)
            print(f"  Created {len(determinants)} determinants from template")

            interventions = build_interventions_from_template(db, project.id, project.sport_type)
            print(f"  Created {len(interventions)} interventions from template")
        else:
            print("  No template found for this sport type")

        # ── 5. Create KPIs (from template) ─────────────────────
        from app.agent.kpi_generator import generate_kpis_for_determinants
        kpi_results = generate_kpis_for_determinants(db, project.id, project.sport_type)
        print(f"  Created {len(kpi_results)} KPIs from template")

        # Set target values for key KPIs
        kpi_targets = {
            "VO2max": 72.0,
            "VO2max速度 (vVO2max)": 22.0,
            "最大速度 (MSS)": 9.2,
            "乳酸阈跑速": 18.5,
            "反应力量指数 (RSI)": 2.5,
            "损伤发生率": 1.5,
            "训练可用率": 95.0,
            "步频": 195,
            "触地时间": 180,
        }
        for kpi_name, target in kpi_targets.items():
            kpis = db.query(models.KPI).filter(
                models.KPI.project_id == project.id,
                models.KPI.name == kpi_name,
            ).all()
            for kpi in kpis:
                kpi.target_value = target
        db.commit()
        print(f"  Set targets for {len(kpi_targets)} KPIs")

        # ── 6. Add Sample Measurements ─────────────────────────
        kpis = crud.get_kpis(db, project.id)
        sample_measurements = []

        for kpi in kpis:
            # Generate 3 measurements over time for athlete 1
            if kpi.name in kpi_targets:
                base = kpi_targets[kpi.name] * 0.9
                target = kpi_targets[kpi.name]
                for week_offset, improvement in [(-8, 0.0), (-4, 0.04), (0, 0.08)]:
                    val = base + (target - base) * improvement
                    sample_measurements.append({
                        "kpi_id": kpi.id,
                        "athlete_id": athletes[0].id,
                        "measured_at": datetime.utcnow() + timedelta(weeks=week_offset),
                        "value": round(val, 2),
                        "unit": kpi.unit,
                        "context": "测试",
                        "data_quality": "high",
                        "notes": f"第{abs(week_offset)//4+1}次测试",
                    })

        for sm in sample_measurements:
            crud.create_measurement(db, sm)
        print(f"  Created {len(sample_measurements)} sample measurements")

        # ── 7. Create Evidence Sources ─────────────────────────
        sources_data = [
            {
                "title": "800m running performance: a systematic review of physiological determinants",
                "source_type": "科学文献",
                "authors": "Sandford GN, et al.",
                "year": 2021,
                "summary": "系统综述800米跑的关键生理决定因素，包括有氧能力、无氧能力和速度储备",
                "evidence_level": "高",
            },
            {
                "title": "World Athletics Competition Rules 2026",
                "source_type": "官方规则",
                "authors": "World Athletics",
                "year": 2026,
                "url": "https://worldathletics.org/about-iaaf/documents/book-of-rules",
                "summary": "世界田径最新竞赛规则，包括800米比赛规则、起跑规则和犯规判罚",
                "evidence_level": "高",
            },
            {
                "title": "中国田径协会全国锦标赛选拔标准",
                "source_type": "官方数据库",
                "authors": "中国田径协会",
                "year": 2026,
                "summary": "2026年全国田径锦标赛参赛标准和选拔办法",
                "evidence_level": "高",
            },
            {
                "title": "教练员经验：800米训练周期化",
                "source_type": "教练经验",
                "authors": "Wang Coach (国家级教练)",
                "year": 2025,
                "summary": "基于20年执教经验总结的800米训练周期化方法和关键训练指标",
                "evidence_level": "专家经验",
            },
        ]
        for sd in sources_data:
            crud.create_evidence_source(db, project.id, sd)
        print(f"  Created {len(sources_data)} evidence sources")

        # ── 8. Create Competition ──────────────────────────────
        comp = crud.create_competition(db, project.id, {
            "name": "2026 National Athletics Championship",
            "competition_level": "全国锦标赛",
            "date": datetime(2026, 7, 15),
            "location": "Beijing National Stadium",
            "rules_version": "World Athletics 2026",
        })
        print(f"  Created competition: {comp.name}")

        # ── 9. Generate a Sample Report ────────────────────────
        from app.agent.report_generator import generate_report
        report = generate_report(db, project.id, "PO与KPI设计报告", athletes[0].id)
        if report:
            print(f"  Generated sample report: {report.title}")

        # ── Done ───────────────────────────────────────────────
        db.commit()
        print(f"\nSeed complete! Project ID: {project.id}")
        print(f"  - {len(outcomes)} POs")
        print(f"  - {len(athletes)} athletes")
        print(f"  - {len(kpis)} KPIs")
        print(f"  - {len(sample_measurements)} measurements")
        print(f"  - {len(sources_data)} evidence sources")
        print(f"  - 1 competition + 1 report")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
