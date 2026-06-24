"""CRUD operations for all entities."""

from datetime import datetime
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models


def _now():
    return datetime.utcnow()


# ═══════════════════════════════════════════════════════════════
#  Project
# ═══════════════════════════════════════════════════════════════

def create_project(db: Session, data: dict) -> models.Project:
    obj = models.Project(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def get_projects(db: Session) -> list[models.Project]:
    return db.query(models.Project).order_by(models.Project.created_at.desc()).all()


def get_project(db: Session, project_id: int) -> Optional[models.Project]:
    return db.query(models.Project).filter(models.Project.id == project_id).first()


def update_project(db: Session, project_id: int, data: dict) -> Optional[models.Project]:
    obj = get_project(db, project_id)
    if not obj:
        return None
    data["updated_at"] = _now()
    for k, v in data.items():
        if v is not None:
            setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


def delete_project(db: Session, project_id: int) -> bool:
    obj = get_project(db, project_id)
    if not obj:
        return False
    db.delete(obj)
    db.commit()
    return True


# ═══════════════════════════════════════════════════════════════
#  Performance Outcome
# ═══════════════════════════════════════════════════════════════

def create_outcome(db: Session, project_id: int, data: dict) -> models.PerformanceOutcome:
    obj = models.PerformanceOutcome(project_id=project_id, **data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def get_outcomes(db: Session, project_id: int) -> list[models.PerformanceOutcome]:
    return (
        db.query(models.PerformanceOutcome)
        .filter(models.PerformanceOutcome.project_id == project_id)
        .order_by(models.PerformanceOutcome.priority.desc())
        .all()
    )


def get_outcome(db: Session, outcome_id: int) -> Optional[models.PerformanceOutcome]:
    return db.query(models.PerformanceOutcome).filter(models.PerformanceOutcome.id == outcome_id).first()


def update_outcome(db: Session, outcome_id: int, data: dict) -> Optional[models.PerformanceOutcome]:
    obj = get_outcome(db, outcome_id)
    if not obj:
        return None
    data["updated_at"] = _now()
    for k, v in data.items():
        if v is not None:
            setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


def delete_outcome(db: Session, outcome_id: int) -> bool:
    obj = get_outcome(db, outcome_id)
    if not obj:
        return False
    db.delete(obj)
    db.commit()
    return True


# ═══════════════════════════════════════════════════════════════
#  Athlete
# ═══════════════════════════════════════════════════════════════

def create_athlete(db: Session, project_id: int, data: dict) -> models.Athlete:
    obj = models.Athlete(project_id=project_id, **data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def get_athletes(db: Session, project_id: int) -> list[models.Athlete]:
    return (
        db.query(models.Athlete)
        .filter(models.Athlete.project_id == project_id)
        .all()
    )


def get_athlete(db: Session, athlete_id: int) -> Optional[models.Athlete]:
    return db.query(models.Athlete).filter(models.Athlete.id == athlete_id).first()


def update_athlete(db: Session, athlete_id: int, data: dict) -> Optional[models.Athlete]:
    obj = get_athlete(db, athlete_id)
    if not obj:
        return None
    data["updated_at"] = _now()
    for k, v in data.items():
        if v is not None:
            setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


def delete_athlete(db: Session, athlete_id: int) -> bool:
    obj = get_athlete(db, athlete_id)
    if not obj:
        return False
    db.delete(obj)
    db.commit()
    return True


def get_athlete_dashboard(db: Session, athlete_id: int) -> dict:
    """Aggregate athlete KPI data for dashboard."""
    athlete = get_athlete(db, athlete_id)
    if not athlete:
        return {}

    project_id = athlete.project_id
    kpis = db.query(models.KPI).filter(models.KPI.project_id == project_id).all()

    kpi_summary = []
    strengths = []
    weaknesses = []
    risk_alerts = []

    for kpi in kpis:
        measurements = (
            db.query(models.KPIMeasurement)
            .filter(
                models.KPIMeasurement.kpi_id == kpi.id,
                models.KPIMeasurement.athlete_id == athlete_id,
            )
            .order_by(models.KPIMeasurement.measured_at.desc())
            .limit(10)
            .all()
        )
        latest_value = measurements[0].value if measurements else None
        kpi_summary.append({
            "kpi_id": kpi.id,
            "kpi_name": kpi.name,
            "unit": kpi.unit,
            "latest_value": latest_value,
            "target_value": kpi.target_value,
            "measurement_count": len(measurements),
        })

        if latest_value is not None and kpi.target_value is not None:
            gap = kpi.target_value - latest_value
            if gap > 0:
                weaknesses.append(f"{kpi.name}: 当前 {latest_value}{kpi.unit}, 目标 {kpi.target_value}{kpi.unit}, 差距 {gap}{kpi.unit}")
            else:
                strengths.append(f"{kpi.name}: 已达到目标 ({latest_value}{kpi.unit} >= {kpi.target_value}{kpi.unit})")

        if kpi.threshold_low is not None and latest_value is not None and latest_value < kpi.threshold_low:
            risk_alerts.append(f"警告: {kpi.name} 低于下限阈值 ({latest_value} < {kpi.threshold_low})")

    recent_measurements = (
        db.query(models.KPIMeasurement)
        .filter(models.KPIMeasurement.athlete_id == athlete_id)
        .order_by(models.KPIMeasurement.measured_at.desc())
        .limit(20)
        .all()
    )

    return {
        "athlete": athlete,
        "kpi_summary": kpi_summary,
        "recent_measurements": [
            {"kpi_id": m.kpi_id, "value": m.value, "unit": m.unit, "date": str(m.measured_at), "context": m.context}
            for m in recent_measurements
        ],
        "strengths": strengths,
        "weaknesses": weaknesses,
        "risk_alerts": risk_alerts,
    }


# ═══════════════════════════════════════════════════════════════
#  Performance Determinant
# ═══════════════════════════════════════════════════════════════

def create_determinant(db: Session, project_id: int, data: dict) -> models.PerformanceDeterminant:
    obj = models.PerformanceDeterminant(project_id=project_id, **data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def get_determinants(db: Session, project_id: int) -> list[models.PerformanceDeterminant]:
    return (
        db.query(models.PerformanceDeterminant)
        .filter(models.PerformanceDeterminant.project_id == project_id)
        .all()
    )


def get_determinant(db: Session, determinant_id: int) -> Optional[models.PerformanceDeterminant]:
    return db.query(models.PerformanceDeterminant).filter(models.PerformanceDeterminant.id == determinant_id).first()


def update_determinant(db: Session, determinant_id: int, data: dict) -> Optional[models.PerformanceDeterminant]:
    obj = get_determinant(db, determinant_id)
    if not obj:
        return None
    data["updated_at"] = _now()
    for k, v in data.items():
        if v is not None:
            setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


def delete_determinant(db: Session, determinant_id: int) -> bool:
    obj = get_determinant(db, determinant_id)
    if not obj:
        return False
    db.delete(obj)
    db.commit()
    return True


def _build_child_tree(db: Session, parent: models.PerformanceDeterminant) -> dict:
    kpi_count = db.query(func.count(models.KPI.id)).filter(
        models.KPI.determinant_id == parent.id
    ).scalar() or 0
    intervention_count = db.query(func.count(models.Intervention.id)).filter(
        models.Intervention.determinant_id == parent.id
    ).scalar() or 0
    return {
        "id": parent.id,
        "name": parent.name,
        "category": parent.category,
        "parent_id": parent.parent_id,
        "kpi_count": kpi_count,
        "intervention_count": intervention_count,
        "children": [_build_child_tree(db, c) for c in parent.children],
    }


def get_determinant_tree(db: Session, project_id: int) -> list[dict]:
    """Return the full determinant hierarchy as a tree."""
    all_dets = get_determinants(db, project_id)
    roots = [d for d in all_dets if d.parent_id is None]
    return [_build_child_tree(db, r) for r in roots]


# ═══════════════════════════════════════════════════════════════
#  KPI
# ═══════════════════════════════════════════════════════════════

def create_kpi(db: Session, project_id: int, data: dict) -> models.KPI:
    obj = models.KPI(project_id=project_id, **data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def get_kpis(db: Session, project_id: int) -> list[models.KPI]:
    return (
        db.query(models.KPI)
        .filter(models.KPI.project_id == project_id)
        .order_by(models.KPI.priority.desc())
        .all()
    )


def get_kpi(db: Session, kpi_id: int) -> Optional[models.KPI]:
    return db.query(models.KPI).filter(models.KPI.id == kpi_id).first()


def update_kpi(db: Session, kpi_id: int, data: dict) -> Optional[models.KPI]:
    obj = get_kpi(db, kpi_id)
    if not obj:
        return None
    data["updated_at"] = _now()
    for k, v in data.items():
        if v is not None:
            setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


def delete_kpi(db: Session, kpi_id: int) -> bool:
    obj = get_kpi(db, kpi_id)
    if not obj:
        return False
    db.delete(obj)
    db.commit()
    return True


# ═══════════════════════════════════════════════════════════════
#  KPI Measurement
# ═══════════════════════════════════════════════════════════════

def create_measurement(db: Session, data: dict) -> models.KPIMeasurement:
    obj = models.KPIMeasurement(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    # Update KPI current_value
    kpi = db.query(models.KPI).filter(models.KPI.id == obj.kpi_id).first()
    if kpi:
        kpi.current_value = obj.value
        kpi.updated_at = _now()
        db.commit()
    return obj


def get_measurements(
    db: Session,
    kpi_id: int,
    athlete_id: Optional[int] = None,
    limit: int = 100,
) -> list[models.KPIMeasurement]:
    q = db.query(models.KPIMeasurement).filter(models.KPIMeasurement.kpi_id == kpi_id)
    if athlete_id is not None:
        q = q.filter(models.KPIMeasurement.athlete_id == athlete_id)
    return q.order_by(models.KPIMeasurement.measured_at.desc()).limit(limit).all()


def get_kpi_trend(db: Session, kpi_id: int, athlete_id: Optional[int] = None) -> dict:
    """Return KPI trend data with direction analysis."""
    kpi = get_kpi(db, kpi_id)
    if not kpi:
        return {}
    measurements = get_measurements(db, kpi_id, athlete_id)
    trend = "stable"
    summary = "数据不足"
    if len(measurements) >= 2:
        recent = [m.value for m in measurements[:5]]
        if recent[0] > recent[-1]:
            trend = "improving"
            summary = f"趋势向好：最近5次测量从 {recent[-1]} 提升至 {recent[0]}"
        elif recent[0] < recent[-1]:
            trend = "declining"
            summary = f"趋势下降：最近5次测量从 {recent[-1]} 下降至 {recent[0]}"
        else:
            summary = "趋势稳定"
    return {
        "kpi": kpi,
        "measurements": measurements,
        "trend_direction": trend,
        "trend_summary": summary,
    }


# ═══════════════════════════════════════════════════════════════
#  Intervention
# ═══════════════════════════════════════════════════════════════

def create_intervention(db: Session, project_id: int, data: dict) -> models.Intervention:
    obj = models.Intervention(project_id=project_id, **data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def get_interventions(db: Session, project_id: int) -> list[models.Intervention]:
    return (
        db.query(models.Intervention)
        .filter(models.Intervention.project_id == project_id)
        .all()
    )


def update_intervention(db: Session, intervention_id: int, data: dict) -> Optional[models.Intervention]:
    obj = db.query(models.Intervention).filter(models.Intervention.id == intervention_id).first()
    if not obj:
        return None
    data["updated_at"] = _now()
    for k, v in data.items():
        if v is not None:
            setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


def delete_intervention(db: Session, intervention_id: int) -> bool:
    obj = db.query(models.Intervention).filter(models.Intervention.id == intervention_id).first()
    if not obj:
        return False
    db.delete(obj)
    db.commit()
    return True


# ═══════════════════════════════════════════════════════════════
#  Assessment
# ═══════════════════════════════════════════════════════════════

def create_assessment(db: Session, project_id: int, data: dict) -> models.Assessment:
    obj = models.Assessment(project_id=project_id, **data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def get_assessments(db: Session, project_id: int, athlete_id: Optional[int] = None) -> list[models.Assessment]:
    q = db.query(models.Assessment).filter(models.Assessment.project_id == project_id)
    if athlete_id is not None:
        q = q.filter(models.Assessment.athlete_id == athlete_id)
    return q.order_by(models.Assessment.date.desc()).all()


# ═══════════════════════════════════════════════════════════════
#  Competition
# ═══════════════════════════════════════════════════════════════

def create_competition(db: Session, project_id: int, data: dict) -> models.Competition:
    obj = models.Competition(project_id=project_id, **data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def get_competitions(db: Session, project_id: int) -> list[models.Competition]:
    return (
        db.query(models.Competition)
        .filter(models.Competition.project_id == project_id)
        .order_by(models.Competition.date.desc())
        .all()
    )


def create_competition_result(db: Session, competition_id: int, data: dict) -> models.CompetitionResult:
    obj = models.CompetitionResult(competition_id=competition_id, **data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


# ═══════════════════════════════════════════════════════════════
#  Evidence Source
# ═══════════════════════════════════════════════════════════════

def create_evidence_source(db: Session, project_id: int, data: dict) -> models.EvidenceSource:
    obj = models.EvidenceSource(project_id=project_id, **data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    # Auto-index into vector store
    try:
        from app.agent.search_engine import index_evidence_source
        index_evidence_source(obj)
    except Exception:
        pass
    return obj


def get_evidence_sources(db: Session, project_id: int) -> list[models.EvidenceSource]:
    return (
        db.query(models.EvidenceSource)
        .filter(models.EvidenceSource.project_id == project_id)
        .order_by(models.EvidenceSource.created_at.desc())
        .all()
    )


# ═══════════════════════════════════════════════════════════════
#  Rule
# ═══════════════════════════════════════════════════════════════

def create_rule(db: Session, project_id: int, data: dict) -> models.Rule:
    obj = models.Rule(project_id=project_id, **data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def get_rules(db: Session, project_id: int) -> list[models.Rule]:
    return (
        db.query(models.Rule)
        .filter(models.Rule.project_id == project_id)
        .all()
    )


# ═══════════════════════════════════════════════════════════════
#  Report
# ═══════════════════════════════════════════════════════════════

def create_report(db: Session, project_id: int, data: dict) -> models.Report:
    obj = models.Report(project_id=project_id, **data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def get_reports(db: Session, project_id: int) -> list[models.Report]:
    return (
        db.query(models.Report)
        .filter(models.Report.project_id == project_id)
        .order_by(models.Report.generated_at.desc())
        .all()
    )


def get_report(db: Session, report_id: int) -> Optional[models.Report]:
    return db.query(models.Report).filter(models.Report.id == report_id).first()
