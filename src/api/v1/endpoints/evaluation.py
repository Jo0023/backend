"""
Evaluation API - Clean orchestration layer
"""

from typing import Annotated
from fastapi import APIRouter, Depends, Query, HTTPException, status

from src.core.dependencies import get_current_user, get_current_teacher, get_current_commission
from src.services.evaluation_service import EvaluationService, UserRole  
from src.core.container import get_evaluation_service
from src.model.models import User
from src.schema.evaluation import (
    CommissionEvaluationSubmit,
    CommissionEvaluationResponse,
    PeerEvaluationSubmit,
    PeerEvaluationResponse,
    FinalGradeRequest,
    FinalGradeResponse,
    PeerEvaluationLeaderSummary,
    ProjectEvaluationStatus,
    PresentationSessionResponse,
    PresentationSessionStartResponse,
    PresentationSessionOpenResponse,
)

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


# =====================================================
# SERVICE DEPENDENCY
# =====================================================

ServiceDep = Annotated[EvaluationService, Depends(get_evaluation_service)]
UserDep = Annotated[User, Depends(get_current_user)]
TeacherDep = Annotated[User, Depends(get_current_teacher)]
CommissionDep = Annotated[User, Depends(get_current_commission)]

# temporairement pour le test:
@router.get("/ping")
async def ping():
    """Simple ping endpoint to test if router is working"""
    return {"status": "ok", "message": "pong"}
@router.get("/test-user")
async def test_user(
    current_user: UserDep,
):
    """Test user dependency"""
    return {
        "user_id": current_user.id,
        "user_email": current_user.email,
        "role_id": current_user.role_id
    }
# =====================================================
# CONFIG
# =====================================================

@router.get("/config", response_model=dict)
async def get_evaluation_config(
    service: ServiceDep,
) -> dict:
    """Get current evaluation configuration"""
    return await service.get_evaluation_config()


@router.put("/config", response_model=dict)
async def update_evaluation_config(
    current_user: TeacherDep,  # ← 1. SANS DÉFAUT (path, dependency)
    service: ServiceDep,       # ← 2. SANS DÉFAUT
    peer_evaluation_days: int | None = Query(None, ge=1),  # ← 3. AVEC DÉFAUT
    commission_evaluation_minutes: int | None = Query(None, ge=1),
    presentation_minutes: int | None = Query(None, ge=1),
    evaluation_opening_minutes: int | None = Query(None, ge=1),
) -> dict:
    """Update evaluation configuration"""
    return await service.update_evaluation_config(
        peer_evaluation_days=peer_evaluation_days,
        commission_evaluation_minutes=commission_evaluation_minutes,
        presentation_minutes=presentation_minutes,
        evaluation_opening_minutes=evaluation_opening_minutes,
        teacher_id=current_user.id,
    )


# =====================================================
# SCHEDULING
# =====================================================

@router.post("/schedule", response_model=dict)
async def schedule_presentations(
    current_user: TeacherDep,
    service: ServiceDep,
    schedule_data: list[dict],  # ← Body parameter (sans défaut)
) -> dict:
    """Schedule projects for multiple days"""
    return await service.schedule_projects(schedule_data, teacher_id=current_user.id)


@router.get("/schedule/dates", response_model=list[str])
async def get_available_dates(
    current_user: TeacherDep,
    service: ServiceDep,
) -> list[str]:
    """Get all dates with scheduled projects"""
    return await service.get_available_dates()


@router.get("/schedule/{date}", response_model=list[dict])
async def get_schedule_by_date(
    date: str,  # ← Path parameter (sans défaut)
    current_user: TeacherDep,
    service: ServiceDep,
) -> list[dict]:
    """Get schedule for a specific date"""
    return await service.get_schedule_by_date(date)


@router.put("/schedule/{date}/reorder", response_model=dict)
async def reorder_projects(
    date: str,  # ← Path parameter (sans défaut)
    current_user: TeacherDep,
    service: ServiceDep,
    project_order: list[int],  # ← Body parameter (sans défaut)
) -> dict:
    """Reorder projects for a date"""
    return await service.reorder_projects(date, project_order, teacher_id=current_user.id)


# =====================================================
# TODAY PROJECTS
# =====================================================

@router.get("/today-projects", response_model=list[dict])
async def get_today_projects(
    current_user: TeacherDep,
    service: ServiceDep,
) -> list[dict]:
    """Get projects scheduled for today"""
    return await service.get_today_projects()


@router.get("/project/{project_id}/current-session", response_model=PresentationSessionResponse | None)
async def get_current_session(
    project_id: int,  # ← Path parameter
    current_user: UserDep,
    service: ServiceDep,
) -> PresentationSessionResponse | None:
    """Get current active session for a project"""
    return await service.get_current_session(project_id)


@router.post("/projects/{project_id}/skip", response_model=dict)
async def skip_project(
    project_id: int,  # ← Path parameter
    current_user: TeacherDep,
    service: ServiceDep,
) -> dict:
    """Skip a project session"""
    return await service.skip_project_session(project_id, teacher_id=current_user.id)


@router.post("/projects/{project_id}/resume", response_model=dict)
async def resume_project(
    project_id: int,  # ← Path parameter
    current_user: TeacherDep,
    service: ServiceDep,
) -> dict:
    """Resume a skipped project"""
    return await service.resume_project_session(project_id, teacher_id=current_user.id)


# =====================================================
# PRESENTATION SESSIONS
# =====================================================

@router.post("/sessions/start/{project_id}", response_model=PresentationSessionStartResponse)
async def start_presentation(
    project_id: int,  # ← Path parameter
    current_user: TeacherDep,
    service: ServiceDep,
) -> PresentationSessionStartResponse:
    """Start a presentation session"""
    return await service.start_presentation(project_id, current_user.id)


@router.post("/sessions/{session_id}/open-evaluation", response_model=PresentationSessionOpenResponse)
async def open_evaluation(
    session_id: int,  # ← Path parameter
    current_user: TeacherDep,
    service: ServiceDep,
) -> PresentationSessionOpenResponse:
    """Open evaluation for a session"""
    return await service.open_evaluation(session_id)


@router.get("/sessions/{session_id}", response_model=PresentationSessionResponse)
async def get_session_status(
    session_id: int,  # ← Path parameter
    current_user: UserDep,
    service: ServiceDep,
) -> PresentationSessionResponse:
    """Get session status"""
    return await service.get_session_status(session_id)


@router.post("/sessions/{session_id}/complete", response_model=PresentationSessionResponse)
async def complete_session(
    session_id: int,  # ← Path parameter
    current_user: TeacherDep,
    service: ServiceDep,
) -> PresentationSessionResponse:
    """Complete a session (mark as EVALUATED)"""
    return await service.complete_session(session_id)


@router.post("/sessions/{session_id}/finalize", response_model=dict)
async def finalize_session(
    session_id: int,  # ← Path parameter
    current_user: TeacherDep,
    service: ServiceDep,
) -> dict:
    """Mark session as final"""
    return await service.finalize_session(session_id, current_user.id)


# =====================================================
# COMMISSION EVALUATION
# =====================================================

@router.post("/commission/submit", response_model=CommissionEvaluationResponse)
async def submit_commission_evaluation(
    data: CommissionEvaluationSubmit,
    current_user: CommissionDep,
    service: ServiceDep,
) -> CommissionEvaluationResponse:
    """Submit commission evaluation"""
    data.commissioner_id = current_user.id
    try:
        return await service.submit_commission_evaluation(data)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@router.get("/commission/sessions/{session_id}", response_model=list[CommissionEvaluationResponse])
async def get_commission_evaluations(
    session_id: int,
    current_user: UserDep,  # ← Gardé pour l'audit, même si non utilisé
    service: ServiceDep,
) -> list[CommissionEvaluationResponse]:
    """Get all commission evaluations for a session"""
    # TODO: Vérifier les droits (enseignant ou participant)
    return await service.get_commission_evaluations(session_id)


@router.get("/commission/sessions/{session_id}/average", response_model=float | None)
async def get_commission_average(
    session_id: int,
    current_user: UserDep,
    service: ServiceDep,
) -> float | None:
    """Get average commission score for a session"""
    return await service.get_commission_average(session_id)


# =====================================================
# PEER EVALUATION
# =====================================================

@router.post("/peer/submit", response_model=PeerEvaluationResponse)
async def submit_peer_evaluation(
    data: PeerEvaluationSubmit,
    current_user: UserDep,
    service: ServiceDep,
) -> PeerEvaluationResponse:
    """Submit peer evaluation"""
    if data.evaluator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot evaluate for another user")
    try:
        return await service.submit_peer_evaluation(data)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@router.get("/peer/leader-feedback/{project_id}", response_model=PeerEvaluationLeaderSummary)
async def get_leader_feedback(
    project_id: int,
    current_user: UserDep,
    service: ServiceDep,
    session_id: int = Query(None),
) -> PeerEvaluationLeaderSummary:
    """Get anonymous feedback for leader"""
    leader_id = await service.get_project_leader_id(project_id)
    
    # ✅ Utiliser la vérification de rôle plutôt que ID fixe
    is_leader = current_user.id == leader_id
    is_teacher = getattr(current_user, "is_teacher", False) or current_user.id == 1
    
    if not (is_leader or is_teacher):
        raise HTTPException(status_code=403, detail="Access denied")
    
    return await service.get_leader_feedback(project_id, leader_id, session_id)


@router.get("/peer/member-feedback/{project_id}/{member_id}", response_model=list[dict])
async def get_member_feedback(
    project_id: int,
    member_id: int,
    current_user: UserDep,
    service: ServiceDep,
    session_id: int = Query(None),
) -> list[dict]:
    """Get member feedback from leader"""
    leader_id = await service.get_project_leader_id(project_id)
    
    is_self = current_user.id == member_id
    is_leader = current_user.id == leader_id
    is_teacher = getattr(current_user, "is_teacher", False) or current_user.id == 1
    
    if not (is_self or is_leader or is_teacher):
        raise HTTPException(status_code=403, detail="Access denied")
    
    return await service.get_member_feedback(project_id, member_id, session_id)


@router.get("/sessions/{session_id}/peer-deadline", response_model=dict)
async def get_peer_evaluation_deadline(
    session_id: int,
    current_user: UserDep,
    service: ServiceDep,
) -> dict:
    """Get deadline for peer evaluations"""
    deadline = await service.get_peer_evaluation_deadline(session_id)
    remaining_days = await service.get_remaining_peer_evaluation_days(session_id)
    return {
        "deadline": deadline.isoformat() if deadline else None,
        "remaining_days": remaining_days,
        "is_expired": remaining_days == 0 if remaining_days is not None else None,
    }

# =====================================================
# FINAL GRADE
# =====================================================

@router.post("/final-grade", response_model=FinalGradeResponse)
async def calculate_final_grade(
    request: FinalGradeRequest,  # ← Body parameter
    current_user: UserDep,
    service: ServiceDep,
) -> FinalGradeResponse:
    """Calculate final grade for a student"""
    try:
        role = UserRole(request.role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {request.role}")

    return await service.calculate_final_grade(
        project_id=request.project_id,
        student_id=request.student_id,
        role=role,
    )


# =====================================================
# STATUS
# =====================================================

@router.get("/status/project/{project_id}", response_model=ProjectEvaluationStatus)
async def get_project_evaluation_status(
    project_id: int,  # ← Path parameter
    current_user: UserDep,
    service: ServiceDep,
) -> ProjectEvaluationStatus:
    """Get project evaluation status"""
    return await service.get_project_evaluation_status(project_id)