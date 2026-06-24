"""Agent workflow endpoints — the smart orchestration layer."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.agent import workflows as wf
from app.schemas import (
    AgentCreateProjectRequest, AgentCreateProjectResponse,
    AgentDefinePORequest, AgentDefinePOResponse,
    AgentAnalyzeDemandsRequest, AgentAnalyzeDemandsResponse,
    AgentBuildModelRequest, AgentBuildModelResponse,
    AgentGenerateKPIsRequest, AgentGenerateKPIsResponse,
    AgentEvaluateAthleteRequest, AgentEvaluateAthleteResponse,
    AgentInterventionPlanRequest, AgentInterventionPlanResponse,
    AgentReportRequest, AgentReportResponse,
    EvidenceModelGenerateRequest, EvidenceModelConfirmRequest,
)

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/create-project", response_model=AgentCreateProjectResponse)
def create_project(req: AgentCreateProjectRequest, db: Session = Depends(get_db)):
    result = wf.workflow_create_project(
        db,
        name=req.name,
        sport_type=req.sport_type,
        project_type=req.project_type,
        description=req.description,
        level=req.level,
        target_competition=req.target_competition,
        existing_info=req.existing_info,
    )
    return result


@router.post("/define-po", response_model=AgentDefinePOResponse)
def define_po(req: AgentDefinePORequest, db: Session = Depends(get_db)):
    result = wf.workflow_define_po(
        db,
        project_id=req.project_id,
        desired_outcome=req.desired_outcome,
        how_measured=req.how_measured,
        target_value_input=req.target_value_input,
        target_unit=req.target_unit,
        baseline_value_input=req.baseline_value_input,
        target_date=req.target_date,
        comparison_target=req.comparison_target,
    )
    if not result.get("outcome"):
        raise HTTPException(status_code=400, detail="Failed to create outcome")
    return result


@router.post("/analyze-demands", response_model=AgentAnalyzeDemandsResponse)
def analyze_demands(req: AgentAnalyzeDemandsRequest, db: Session = Depends(get_db)):
    return wf.workflow_analyze_demands(db, req.project_id, req.additional_notes)


@router.post("/build-performance-model", response_model=AgentBuildModelResponse)
def build_performance_model(req: AgentBuildModelRequest, db: Session = Depends(get_db)):
    return wf.workflow_build_performance_model(db, req.project_id, req.coach_input)


@router.post("/generate-kpis", response_model=AgentGenerateKPIsResponse)
def generate_kpis(req: AgentGenerateKPIsRequest, db: Session = Depends(get_db)):
    return wf.workflow_generate_kpis(db, req.project_id)


@router.post("/evaluate-athlete", response_model=AgentEvaluateAthleteResponse)
def evaluate_athlete(req: AgentEvaluateAthleteRequest, db: Session = Depends(get_db)):
    result = wf.workflow_evaluate_athlete(db, req.athlete_id)
    if not result:
        raise HTTPException(status_code=404, detail="Athlete not found")
    return result


@router.post("/generate-intervention-plan", response_model=AgentInterventionPlanResponse)
def intervention_plan(req: AgentInterventionPlanRequest, db: Session = Depends(get_db)):
    return wf.workflow_intervention_plan(
        db, req.project_id, req.athlete_id, req.priority_kpi_ids, req.cycle_length_weeks
    )


@router.post("/generate-report", response_model=AgentReportResponse)
def generate_report(req: AgentReportRequest, db: Session = Depends(get_db)):
    result = wf.workflow_generate_report(
        db, req.project_id, req.report_type, req.athlete_id, req.extra_notes
    )
    if not result.get("report"):
        raise HTTPException(status_code=400, detail="Failed to generate report")
    return result


@router.post("/generate-model-from-evidence")
def generate_model_from_evidence(req: EvidenceModelGenerateRequest, db: Session = Depends(get_db)):
    """Search literature and generate a performance model from evidence."""
    result = wf.workflow_generate_model_from_evidence(
        db,
        project_id=req.project_id,
        sport_name=req.sport_name,
        sport_name_en=req.sport_name_en,
        use_llm=req.use_llm,
        max_results_per_query=req.max_results_per_query,
    )
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/confirm-evidence-model")
def confirm_evidence_model(req: EvidenceModelConfirmRequest, db: Session = Depends(get_db)):
    """Save a user-reviewed evidence-based model to the database."""
    result = wf.workflow_confirm_evidence_model(
        db,
        project_id=req.project_id,
        model=req.model,
        selected_determinants=req.selected_determinants,
        selected_kpis=req.selected_kpis,
        selected_interventions=req.selected_interventions,
    )
    return result
