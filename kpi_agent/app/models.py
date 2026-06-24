"""SQLAlchemy ORM models for the KPI Agent database."""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, ForeignKey, Enum, Boolean, JSON,
)
from sqlalchemy.orm import relationship

from app.database import Base


def _now():
    return datetime.utcnow()


# ── Enums as strings for SQLite compatibility ───────────────────

PROJECT_TYPE_ENUM = ("计量类", "非计量类", "团队类", "混合类", "其他")
LEVEL_ENUM = ("青少年", "大学", "职业", "国家级", "国际级", "精英级", "其他")
OUTCOME_TYPE_ENUM = ("成绩", "排名", "奖牌", "胜率", "选拔资格", "技术得分", "团队角色", "其他")
DETERMINANT_CATEGORY_ENUM = (
    "生理要求", "技术要求", "战术要求", "营养要求", "心理技能",
    "器材特点", "健康", "比赛规则", "其他",
)
EVIDENCE_LEVEL_ENUM = ("高", "中", "低", "专家经验", "未知")
INTERVENTION_TYPE_ENUM = (
    "训练", "营养", "热身", "恢复", "技术", "战术", "心理", "器材", "健康", "其他",
)
SOURCE_TYPE_ENUM = (
    "科学文献", "教练员手册", "官方规则", "官方数据库", "教练经验",
    "运动员数据", "医疗记录", "视频分析", "用户上传", "其他",
)


# ── Core Tables ─────────────────────────────────────────────────

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    sport_type = Column(String(100), nullable=False)
    project_type = Column(String(20), nullable=False, default="其他")
    description = Column(Text, default="")
    level = Column(String(20), nullable=False, default="其他")
    target_competition = Column(String(255), default="")
    start_date = Column(DateTime, default=_now)
    end_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    outcomes = relationship("PerformanceOutcome", back_populates="project", cascade="all, delete-orphan")
    athletes = relationship("Athlete", back_populates="project", cascade="all, delete-orphan")
    determinants = relationship("PerformanceDeterminant", back_populates="project", cascade="all, delete-orphan")
    kpis = relationship("KPI", back_populates="project", cascade="all, delete-orphan")
    interventions = relationship("Intervention", back_populates="project", cascade="all, delete-orphan")
    assessments = relationship("Assessment", back_populates="project", cascade="all, delete-orphan")
    competitions = relationship("Competition", back_populates="project", cascade="all, delete-orphan")
    evidence_sources = relationship("EvidenceSource", back_populates="project", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="project", cascade="all, delete-orphan")
    rules = relationship("Rule", back_populates="project", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="project", cascade="all, delete-orphan")


class PerformanceOutcome(Base):
    __tablename__ = "performance_outcomes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    outcome_type = Column(String(20), nullable=False, default="成绩")
    target_value = Column(Float, nullable=True)
    unit = Column(String(50), default="")
    target_date = Column(DateTime, nullable=True)
    baseline_value = Column(Float, nullable=True)
    current_value = Column(Float, nullable=True)
    priority = Column(Integer, default=1)
    status = Column(String(50), default="active")
    evidence_notes = Column(Text, default="")
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    project = relationship("Project", back_populates="outcomes")
    kpis = relationship("KPI", back_populates="performance_outcome")


class Athlete(Base):
    __tablename__ = "athletes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(100), nullable=False)
    gender = Column(String(10), default="")
    birth_date = Column(DateTime, nullable=True)
    age = Column(Integer, nullable=True)
    height = Column(Float, nullable=True)
    weight = Column(Float, nullable=True)
    training_age = Column(Float, nullable=True)
    level = Column(String(20), default="其他")
    role = Column(String(100), default="")
    position = Column(String(100), default="")
    injury_history = Column(Text, default="")
    medical_notes = Column(Text, default="")
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    project = relationship("Project", back_populates="athletes")
    assessments = relationship("Assessment", back_populates="athlete")
    competition_results = relationship("CompetitionResult", back_populates="athlete")
    kpi_measurements = relationship("KPIMeasurement", back_populates="athlete")


class PerformanceDeterminant(Base):
    __tablename__ = "performance_determinants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    parent_id = Column(Integer, ForeignKey("performance_determinants.id"), nullable=True)
    category = Column(String(20), nullable=False, default="其他")
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    importance = Column(String(20), default="medium")
    evidence_level = Column(String(20), default="未知")
    source_summary = Column(Text, default="")
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    project = relationship("Project", back_populates="determinants")
    parent = relationship("PerformanceDeterminant", remote_side=[id], backref="children")
    kpis = relationship("KPI", back_populates="determinant")
    interventions = relationship("Intervention", back_populates="determinant")


class KPI(Base):
    __tablename__ = "kpis"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    performance_outcome_id = Column(Integer, ForeignKey("performance_outcomes.id"), nullable=True)
    determinant_id = Column(Integer, ForeignKey("performance_determinants.id"), nullable=True)
    name = Column(String(255), nullable=False)
    category = Column(String(100), default="")
    definition = Column(Text, default="")
    calculation_method = Column(Text, default="")
    unit = Column(String(50), default="")
    target_value = Column(Float, nullable=True)
    baseline_value = Column(Float, nullable=True)
    current_value = Column(Float, nullable=True)
    threshold_low = Column(Float, nullable=True)
    threshold_high = Column(Float, nullable=True)
    measurement_frequency = Column(String(100), default="")
    data_source = Column(Text, default="")
    evidence_level = Column(String(20), default="未知")
    data_quality = Column(String(20), default="medium")
    owner = Column(String(100), default="")
    priority = Column(Integer, default=2)
    status = Column(String(50), default="active")
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    project = relationship("Project", back_populates="kpis")
    performance_outcome = relationship("PerformanceOutcome", back_populates="kpis")
    determinant = relationship("PerformanceDeterminant", back_populates="kpis")
    measurements = relationship("KPIMeasurement", back_populates="kpi", cascade="all, delete-orphan")
    interventions = relationship("Intervention", back_populates="kpi")


class KPIMeasurement(Base):
    __tablename__ = "kpi_measurements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    kpi_id = Column(Integer, ForeignKey("kpis.id"), nullable=False)
    athlete_id = Column(Integer, ForeignKey("athletes.id"), nullable=True)
    team_id = Column(Integer, nullable=True)
    measured_at = Column(DateTime, default=_now)
    value = Column(Float, nullable=False)
    unit = Column(String(50), default="")
    context = Column(String(50), default="测试")
    session_id = Column(String(100), default="")
    competition_id = Column(Integer, nullable=True)
    notes = Column(Text, default="")
    data_quality = Column(String(20), default="medium")
    created_at = Column(DateTime, default=_now)

    kpi = relationship("KPI", back_populates="measurements")
    athlete = relationship("Athlete", back_populates="kpi_measurements")


class Intervention(Base):
    __tablename__ = "interventions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    determinant_id = Column(Integer, ForeignKey("performance_determinants.id"), nullable=True)
    kpi_id = Column(Integer, ForeignKey("kpis.id"), nullable=True)
    name = Column(String(255), nullable=False)
    intervention_type = Column(String(20), nullable=False, default="训练")
    description = Column(Text, default="")
    protocol = Column(Text, default="")
    frequency = Column(String(100), default="")
    intensity = Column(String(100), default="")
    duration = Column(String(100), default="")
    expected_effect = Column(Text, default="")
    risk_notes = Column(Text, default="")
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    status = Column(String(50), default="planned")
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    project = relationship("Project", back_populates="interventions")
    determinant = relationship("PerformanceDeterminant", back_populates="interventions")
    kpi = relationship("KPI", back_populates="interventions")


class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    athlete_id = Column(Integer, ForeignKey("athletes.id"), nullable=False)
    name = Column(String(255), nullable=False)
    assessment_type = Column(String(100), default="")
    purpose = Column(Text, default="")
    protocol = Column(Text, default="")
    equipment = Column(String(255), default="")
    date = Column(DateTime, default=_now)
    result_summary = Column(Text, default="")
    strengths = Column(Text, default="")
    weaknesses = Column(Text, default="")
    recommendations = Column(Text, default="")
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    project = relationship("Project", back_populates="assessments")
    athlete = relationship("Athlete", back_populates="assessments")


class Competition(Base):
    __tablename__ = "competitions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(255), nullable=False)
    competition_level = Column(String(100), default="")
    date = Column(DateTime, default=_now)
    location = Column(String(255), default="")
    rules_version = Column(String(100), default="")
    result_summary = Column(Text, default="")
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    project = relationship("Project", back_populates="competitions")
    results = relationship("CompetitionResult", back_populates="competition", cascade="all, delete-orphan")


class CompetitionResult(Base):
    __tablename__ = "competition_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    competition_id = Column(Integer, ForeignKey("competitions.id"), nullable=False)
    athlete_id = Column(Integer, ForeignKey("athletes.id"), nullable=True)
    team_id = Column(Integer, nullable=True)
    event = Column(String(255), default="")
    result_value = Column(Float, nullable=True)
    unit = Column(String(50), default="")
    ranking = Column(Integer, nullable=True)
    score = Column(Float, nullable=True)
    medal = Column(String(20), default="")
    qualification_status = Column(String(50), default="")
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=_now)

    competition = relationship("Competition", back_populates="results")
    athlete = relationship("Athlete", back_populates="competition_results")


class EvidenceSource(Base):
    __tablename__ = "evidence_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    title = Column(String(500), nullable=False)
    source_type = Column(String(20), nullable=False, default="其他")
    authors = Column(String(500), default="")
    year = Column(Integer, nullable=True)
    url = Column(String(1000), default="")
    doi = Column(String(255), default="")
    citation = Column(Text, default="")
    summary = Column(Text, default="")
    relevance = Column(String(255), default="")
    evidence_level = Column(String(20), default="未知")
    limitations = Column(Text, default="")
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    project = relationship("Project", back_populates="evidence_sources")
    documents = relationship("Document", back_populates="source")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    source_id = Column(Integer, ForeignKey("evidence_sources.id"), nullable=True)
    file_name = Column(String(255), nullable=False)
    file_type = Column(String(50), default="")
    content_text = Column(Text, default="")
    embedding_id = Column(String(255), default="")
    uploaded_at = Column(DateTime, default=_now)

    project = relationship("Project", back_populates="documents")
    source = relationship("EvidenceSource", back_populates="documents")


class Rule(Base):
    __tablename__ = "rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    sport = Column(String(100), nullable=False)
    organization = Column(String(255), default="")
    version = Column(String(50), default="")
    effective_date = Column(DateTime, nullable=True)
    content_summary = Column(Text, default="")
    source_url = Column(String(1000), default="")
    key_constraints = Column(Text, default="")
    disqualification_reasons = Column(Text, default="")
    selection_criteria = Column(Text, default="")
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    project = relationship("Project", back_populates="rules")


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    report_type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    content_markdown = Column(Text, default="")
    generated_at = Column(DateTime, default=_now)
    created_by = Column(String(100), default="system")

    project = relationship("Project", back_populates="reports")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(Integer, nullable=False)
    action = Column(String(20), nullable=False)
    before_json = Column(Text, default="")
    after_json = Column(Text, default="")
    created_at = Column(DateTime, default=_now)
    created_by = Column(String(100), default="system")
