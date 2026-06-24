"""Pydantic schemas for request/response validation."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Project ────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str = Field(..., max_length=255)
    sport_type: str = Field(..., max_length=100)
    project_type: str = Field(default="其他")
    description: str = ""
    level: str = Field(default="其他")
    target_competition: str = ""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    sport_type: Optional[str] = None
    project_type: Optional[str] = None
    description: Optional[str] = None
    level: Optional[str] = None
    target_competition: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class ProjectOut(BaseModel):
    id: int
    name: str
    sport_type: str
    project_type: str
    description: str
    level: str
    target_competition: str
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Performance Outcome ────────────────────────────────────────

class OutcomeCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: str = ""
    outcome_type: str = Field(default="成绩")
    target_value: Optional[float] = None
    unit: str = ""
    target_date: Optional[datetime] = None
    baseline_value: Optional[float] = None
    current_value: Optional[float] = None
    priority: int = 1
    status: str = "active"
    evidence_notes: str = ""


class OutcomeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    outcome_type: Optional[str] = None
    target_value: Optional[float] = None
    unit: Optional[str] = None
    target_date: Optional[datetime] = None
    baseline_value: Optional[float] = None
    current_value: Optional[float] = None
    priority: Optional[int] = None
    status: Optional[str] = None
    evidence_notes: Optional[str] = None


class OutcomeOut(BaseModel):
    id: int
    project_id: int
    name: str
    description: str
    outcome_type: str
    target_value: Optional[float]
    unit: str
    target_date: Optional[datetime]
    baseline_value: Optional[float]
    current_value: Optional[float]
    priority: int
    status: str
    evidence_notes: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Athlete ────────────────────────────────────────────────────

class AthleteCreate(BaseModel):
    name: str = Field(..., max_length=100)
    gender: str = ""
    birth_date: Optional[datetime] = None
    age: Optional[int] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    training_age: Optional[float] = None
    level: str = "其他"
    role: str = ""
    position: str = ""
    injury_history: str = ""
    medical_notes: str = ""


class AthleteUpdate(BaseModel):
    name: Optional[str] = None
    gender: Optional[str] = None
    birth_date: Optional[datetime] = None
    age: Optional[int] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    training_age: Optional[float] = None
    level: Optional[str] = None
    role: Optional[str] = None
    position: Optional[str] = None
    injury_history: Optional[str] = None
    medical_notes: Optional[str] = None


class AthleteOut(BaseModel):
    id: int
    project_id: int
    name: str
    gender: str
    birth_date: Optional[datetime]
    age: Optional[int]
    height: Optional[float]
    weight: Optional[float]
    training_age: Optional[float]
    level: str
    role: str
    position: str
    injury_history: str
    medical_notes: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AthleteDashboardOut(BaseModel):
    athlete: AthleteOut
    kpi_summary: list[dict] = []
    recent_measurements: list[dict] = []
    strengths: list[str] = []
    weaknesses: list[str] = []
    risk_alerts: list[str] = []


# ── Performance Determinant ────────────────────────────────────

class DeterminantCreate(BaseModel):
    parent_id: Optional[int] = None
    category: str = Field(default="其他")
    name: str = Field(..., max_length=255)
    description: str = ""
    importance: str = "medium"
    evidence_level: str = "未知"
    source_summary: str = ""


class DeterminantUpdate(BaseModel):
    parent_id: Optional[int] = None
    category: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    importance: Optional[str] = None
    evidence_level: Optional[str] = None
    source_summary: Optional[str] = None


class DeterminantOut(BaseModel):
    id: int
    project_id: int
    parent_id: Optional[int]
    category: str
    name: str
    description: str
    importance: str
    evidence_level: str
    source_summary: str
    created_at: datetime
    updated_at: datetime
    children: list["DeterminantOut"] = []

    model_config = {"from_attributes": True}


class DeterminantTreeNode(BaseModel):
    """Flattened tree node for the performance model."""
    id: int
    name: str
    category: str
    parent_id: Optional[int]
    children: list["DeterminantTreeNode"] = []
    kpi_count: int = 0
    intervention_count: int = 0


# ── KPI ────────────────────────────────────────────────────────

class KPICreate(BaseModel):
    performance_outcome_id: Optional[int] = None
    determinant_id: Optional[int] = None
    name: str = Field(..., max_length=255)
    category: str = ""
    definition: str = ""
    calculation_method: str = ""
    unit: str = ""
    target_value: Optional[float] = None
    baseline_value: Optional[float] = None
    current_value: Optional[float] = None
    threshold_low: Optional[float] = None
    threshold_high: Optional[float] = None
    measurement_frequency: str = ""
    data_source: str = ""
    evidence_level: str = "未知"
    data_quality: str = "medium"
    owner: str = ""
    priority: int = 2
    status: str = "active"


class KPIUpdate(BaseModel):
    performance_outcome_id: Optional[int] = None
    determinant_id: Optional[int] = None
    name: Optional[str] = None
    category: Optional[str] = None
    definition: Optional[str] = None
    calculation_method: Optional[str] = None
    unit: Optional[str] = None
    target_value: Optional[float] = None
    baseline_value: Optional[float] = None
    current_value: Optional[float] = None
    threshold_low: Optional[float] = None
    threshold_high: Optional[float] = None
    measurement_frequency: Optional[str] = None
    data_source: Optional[str] = None
    evidence_level: Optional[str] = None
    data_quality: Optional[str] = None
    owner: Optional[str] = None
    priority: Optional[int] = None
    status: Optional[str] = None


class KPIOut(BaseModel):
    id: int
    project_id: int
    performance_outcome_id: Optional[int]
    determinant_id: Optional[int]
    name: str
    category: str
    definition: str
    calculation_method: str
    unit: str
    target_value: Optional[float]
    baseline_value: Optional[float]
    current_value: Optional[float]
    threshold_low: Optional[float]
    threshold_high: Optional[float]
    measurement_frequency: str
    data_source: str
    evidence_level: str
    data_quality: str
    owner: str
    priority: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class KPITrendOut(BaseModel):
    kpi: KPIOut
    measurements: list["MeasurementOut"] = []
    trend_direction: str = "stable"
    trend_summary: str = ""


# ── KPI Measurement ────────────────────────────────────────────

class MeasurementCreate(BaseModel):
    kpi_id: int
    athlete_id: Optional[int] = None
    team_id: Optional[int] = None
    measured_at: Optional[datetime] = None
    value: float
    unit: str = ""
    context: str = "测试"
    session_id: str = ""
    competition_id: Optional[int] = None
    notes: str = ""
    data_quality: str = "medium"


class MeasurementOut(BaseModel):
    id: int
    kpi_id: int
    athlete_id: Optional[int]
    team_id: Optional[int]
    measured_at: datetime
    value: float
    unit: str
    context: str
    session_id: str
    competition_id: Optional[int]
    notes: str
    data_quality: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Intervention ───────────────────────────────────────────────

class InterventionCreate(BaseModel):
    determinant_id: Optional[int] = None
    kpi_id: Optional[int] = None
    name: str = Field(..., max_length=255)
    intervention_type: str = Field(default="训练")
    description: str = ""
    protocol: str = ""
    frequency: str = ""
    intensity: str = ""
    duration: str = ""
    expected_effect: str = ""
    risk_notes: str = ""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: str = "planned"


class InterventionUpdate(BaseModel):
    determinant_id: Optional[int] = None
    kpi_id: Optional[int] = None
    name: Optional[str] = None
    intervention_type: Optional[str] = None
    description: Optional[str] = None
    protocol: Optional[str] = None
    frequency: Optional[str] = None
    intensity: Optional[str] = None
    duration: Optional[str] = None
    expected_effect: Optional[str] = None
    risk_notes: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: Optional[str] = None


class InterventionOut(BaseModel):
    id: int
    project_id: int
    determinant_id: Optional[int]
    kpi_id: Optional[int]
    name: str
    intervention_type: str
    description: str
    protocol: str
    frequency: str
    intensity: str
    duration: str
    expected_effect: str
    risk_notes: str
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Assessment ─────────────────────────────────────────────────

class AssessmentCreate(BaseModel):
    athlete_id: int
    name: str = Field(..., max_length=255)
    assessment_type: str = ""
    purpose: str = ""
    protocol: str = ""
    equipment: str = ""
    date: Optional[datetime] = None
    result_summary: str = ""
    strengths: str = ""
    weaknesses: str = ""
    recommendations: str = ""


class AssessmentOut(BaseModel):
    id: int
    project_id: int
    athlete_id: int
    name: str
    assessment_type: str
    purpose: str
    protocol: str
    equipment: str
    date: Optional[datetime]
    result_summary: str
    strengths: str
    weaknesses: str
    recommendations: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Competition ────────────────────────────────────────────────

class CompetitionCreate(BaseModel):
    name: str = Field(..., max_length=255)
    competition_level: str = ""
    date: Optional[datetime] = None
    location: str = ""
    rules_version: str = ""
    result_summary: str = ""


class CompetitionOut(BaseModel):
    id: int
    project_id: int
    name: str
    competition_level: str
    date: Optional[datetime]
    location: str
    rules_version: str
    result_summary: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CompetitionResultCreate(BaseModel):
    athlete_id: Optional[int] = None
    team_id: Optional[int] = None
    event: str = ""
    result_value: Optional[float] = None
    unit: str = ""
    ranking: Optional[int] = None
    score: Optional[float] = None
    medal: str = ""
    qualification_status: str = ""
    notes: str = ""


class CompetitionResultOut(BaseModel):
    id: int
    competition_id: int
    athlete_id: Optional[int]
    team_id: Optional[int]
    event: str
    result_value: Optional[float]
    unit: str
    ranking: Optional[int]
    score: Optional[float]
    medal: str
    qualification_status: str
    notes: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Evidence Source ────────────────────────────────────────────

class EvidenceSourceCreate(BaseModel):
    title: str = Field(..., max_length=500)
    source_type: str = Field(default="其他")
    authors: str = ""
    year: Optional[int] = None
    url: str = ""
    doi: str = ""
    citation: str = ""
    summary: str = ""
    relevance: str = ""
    evidence_level: str = "未知"
    limitations: str = ""


class EvidenceSourceOut(BaseModel):
    id: int
    project_id: int
    title: str
    source_type: str
    authors: str
    year: Optional[int]
    url: str
    doi: str
    citation: str
    summary: str
    relevance: str
    evidence_level: str
    limitations: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Document ───────────────────────────────────────────────────

class DocumentOut(BaseModel):
    id: int
    project_id: int
    source_id: Optional[int]
    file_name: str
    file_type: str
    content_text: str
    embedding_id: str
    uploaded_at: datetime

    model_config = {"from_attributes": True}


# ── Rule ───────────────────────────────────────────────────────

class RuleCreate(BaseModel):
    sport: str = Field(..., max_length=100)
    organization: str = ""
    version: str = ""
    effective_date: Optional[datetime] = None
    content_summary: str = ""
    source_url: str = ""
    key_constraints: str = ""
    disqualification_reasons: str = ""
    selection_criteria: str = ""


class RuleOut(BaseModel):
    id: int
    project_id: int
    sport: str
    organization: str
    version: str
    effective_date: Optional[datetime]
    content_summary: str
    source_url: str
    key_constraints: str
    disqualification_reasons: str
    selection_criteria: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Report ─────────────────────────────────────────────────────

class ReportOut(BaseModel):
    id: int
    project_id: int
    report_type: str
    title: str
    content_markdown: str
    generated_at: datetime
    created_by: str

    model_config = {"from_attributes": True}


class ReportGenerateRequest(BaseModel):
    report_type: str = Field(..., description="项目需求分析报告 / PO与KPI设计报告 / 运动员评估报告 / KPI趋势报告 / 干预建议报告 / 数据质量报告 / 比赛复盘报告")
    athlete_id: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    extra_notes: str = ""


# ── Agent Workflow Schemas ─────────────────────────────────────

class AgentCreateProjectRequest(BaseModel):
    name: str
    sport_type: str
    project_type: str = "其他"
    description: str = ""
    level: str = "其他"
    target_competition: str = ""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    existing_info: str = ""


class AgentCreateProjectResponse(BaseModel):
    project: ProjectOut
    summary: str
    missing_info: list[str] = []


class AgentDefinePORequest(BaseModel):
    project_id: int
    desired_outcome: str = ""
    how_measured: str = ""
    target_value_input: Optional[float] = None
    target_unit: str = ""
    baseline_value_input: Optional[float] = None
    target_date: Optional[datetime] = None
    comparison_target: str = ""


class AgentDefinePOResponse(BaseModel):
    outcome: OutcomeOut
    quality_check: dict
    suggestions: list[str] = []


class AgentAnalyzeDemandsRequest(BaseModel):
    project_id: int
    additional_notes: str = ""


class AgentAnalyzeDemandsResponse(BaseModel):
    project_id: int
    categories: list[dict]
    overall_completeness: str


class AgentBuildModelRequest(BaseModel):
    project_id: int
    coach_input: str = ""


class AgentBuildModelResponse(BaseModel):
    project_id: int
    determinants_tree: list[DeterminantTreeNode]
    kpi_candidates: list[dict]


class AgentGenerateKPIsRequest(BaseModel):
    project_id: int


class AgentGenerateKPIsResponse(BaseModel):
    project_id: int
    kpis: list[KPIOut]
    kpi_count: int


class AgentEvaluateAthleteRequest(BaseModel):
    athlete_id: int


class AgentEvaluateAthleteResponse(BaseModel):
    athlete_id: int
    strengths: list[str]
    weaknesses: list[str]
    gaps: list[dict]
    risk_alerts: list[str]
    priority_areas: list[str]


class AgentInterventionPlanRequest(BaseModel):
    project_id: int
    athlete_id: Optional[int] = None
    priority_kpi_ids: list[int] = []
    cycle_length_weeks: int = 12


class AgentInterventionPlanResponse(BaseModel):
    project_id: int
    interventions: list[dict]
    schedule_summary: str


class AgentReportRequest(BaseModel):
    project_id: int
    report_type: str
    athlete_id: Optional[int] = None
    extra_notes: str = ""


class AgentReportResponse(BaseModel):
    report: ReportOut


# ── Evidence Model Generation Schemas ──────────────────────────

class EvidenceModelGenerateRequest(BaseModel):
    project_id: int
    sport_name: str = ""
    sport_name_en: str = ""
    use_llm: bool = True
    max_results_per_query: int = 8


class EvidenceModelConfirmRequest(BaseModel):
    project_id: int
    model: dict
    selected_determinants: list[dict] = []
    selected_kpis: list[dict] = []
    selected_interventions: list[dict] = []


# ── Performance Model Extraction Schemas ──────────────────────

class PMExtractRequest(BaseModel):
    query_id: Optional[int] = None
    literature_ids: Optional[list[int]] = None
    limit: int = 50
    include_fulltext: bool = True
    use_keybert: bool = True
    use_yake: bool = True
    use_spacy: bool = False
    min_confidence: float = 0.2


class PMCandidateUpdate(BaseModel):
    status: Optional[str] = None  # candidate, accepted, rejected, merged
    category_key: Optional[str] = None
    display_name_en: Optional[str] = None
    display_name_cn: Optional[str] = None


class PMSaveRequest(BaseModel):
    project_id: int
    candidates: list[dict] = []
    evidence_links: list[dict] = []


# ── RAG Schemas (Phase 2) ─────────────────────────────────────

class RAGQueryRequest(BaseModel):
    project_id: int
    query: str
    top_k: int = 5


class RAGQueryResponse(BaseModel):
    answer: str
    sources: list[dict]
    evidence_level: str
    limitations: str
    suitable_for_level: str
    needs_verification: bool
