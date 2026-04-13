from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from src.core.container import (
    get_commission_evaluation_service,
    get_evaluation_config_service,
    get_final_grade_service,
    get_peer_evaluation_service,
    get_presentation_service,
    get_project_evaluation_status_service,
    get_process_metrics_service,
)
from src.core.dependencies import get_current_user, setup_audit
from src.core.exceptions import NotFoundError, PermissionError, ValidationError
from src.model.models import User
from src.schema.commission_evaluation import (
    CommissionAverageResponse,
    CommissionEvaluationsListResponse,
    CommissionEvaluationResponse,
    CommissionEvaluationSubmit,
)
from src.schema.evaluation_config import EvaluationConfigResponse, EvaluationConfigUpdate
from src.schema.final_grade import FinalGradeRequest, FinalGradeResponse, ProjectEvaluationStatus
from src.schema.peer_evaluation import (
    LeaderToMemberEvaluationSubmit,
    MemberToLeaderEvaluationSubmit,
    PeerEvaluationLeaderSummary,
    PeerEvaluationMemberFeedbackListResponse,
    PeerEvaluationSubmitResponse,
)
from src.schema.process_metrics import LeaderProcessMetricsResponse, MemberProcessMetricsResponse
from src.services.process_metrics_service import ProcessMetricsService
from src.schema.presentation import (
    PeerDeadlineResponse,
    PresentationSessionOpenResponse,
    PresentationSessionResponse,
    PresentationSessionStartResponse,
    ProjectSessionActionResponse,
    ReorderProjectsRequest,
    ReorderProjectsResponse,
    ScheduleForDateItem,
    SchedulePresentationsRequest,
    SchedulePresentationsResponse,
    TodayProjectItem,
)
from src.services.commission_evaluation_service import CommissionEvaluationService
from src.services.evaluation_config_service import EvaluationConfigService
from src.services.final_grade_service import FinalGradeService
from src.services.peer_evaluation_service import PeerEvaluationService
from src.services.presentation_service import PresentationService
from src.services.project_evaluation_status_service import ProjectEvaluationStatusService

evaluation_router = APIRouter(prefix="/evaluation", tags=["evaluation"])


def _handle_evaluation_exception(exc: Exception) -> None:
    """
    Единая трансляция доменных ошибок в HTTP-ошибки
    Unified translation of domain exceptions into HTTP errors
    """
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, PermissionError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if isinstance(exc, ValidationError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    raise exc


# ========== КОНФИГУРАЦИЯ / CONFIGURATION ==========


@evaluation_router.get(
    "/config",
    response_model=EvaluationConfigResponse,
    summary="Получить конфигурацию системы оценки",
)
async def get_evaluation_config(
    config_service: EvaluationConfigService = Depends(get_evaluation_config_service),
    _current_user: User = Depends(get_current_user),
) -> EvaluationConfigResponse:
    """
    Получить активную конфигурацию модуля оценки
    Get active evaluation config
    """
    return await config_service.get_config()


@evaluation_router.put(
    "/config",
    response_model=EvaluationConfigResponse,
    summary="Обновить конфигурацию системы оценки",
)
async def update_evaluation_config(
    data: EvaluationConfigUpdate,
    config_service: EvaluationConfigService = Depends(get_evaluation_config_service),
    current_user: User = Depends(get_current_user),
    _audit=Depends(setup_audit),
) -> EvaluationConfigResponse:
    """
    Обновить конфигурацию системы оценки
    Update evaluation config
    """
    try:
        return await config_service.update_config(current_user.id, data)
    except Exception as exc:
        _handle_evaluation_exception(exc)


# ========== ПЛАНИРОВАНИЕ / SCHEDULING ==========


@evaluation_router.post(
    "/schedule",
    response_model=SchedulePresentationsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Сохранить расписание презентаций",
)
async def schedule_presentations(
    data: SchedulePresentationsRequest,
    presentation_service: PresentationService = Depends(get_presentation_service),
    current_user: User = Depends(get_current_user),
    _audit=Depends(setup_audit),
) -> SchedulePresentationsResponse:
    """
    Сохранить расписание выступлений проектов
    Save project presentation schedule
    """
    try:
        return await presentation_service.schedule_presentations(current_user.id, data)
    except Exception as exc:
        _handle_evaluation_exception(exc)


@evaluation_router.get(
    "/schedule/dates",
    response_model=list[str],
    summary="Получить список дат с запланированными презентациями",
)
async def get_available_dates(
    presentation_service: PresentationService = Depends(get_presentation_service),
    _current_user: User = Depends(get_current_user),
) -> list[str]:
    """
    Получить все даты, по которым есть расписание презентаций
    Get all dates that have presentation schedules
    """
    return await presentation_service.get_available_dates()


@evaluation_router.get(
    "/schedule/{target_date}",
    response_model=list[ScheduleForDateItem],
    summary="Получить расписание на выбранную дату",
)
async def get_schedule_for_date(
    target_date: str = Path(..., description="Дата в формате ISO, например 2026-04-01T00:00:00"),
    presentation_service: PresentationService = Depends(get_presentation_service),
    _current_user: User = Depends(get_current_user),
) -> list[ScheduleForDateItem]:
    """
    Получить список проектов, запланированных на дату
    Get projects scheduled for a given date
    """
    try:
        parsed_date = datetime.fromisoformat(target_date)
        return await presentation_service.get_schedule_for_date(parsed_date)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный формат даты") from exc
    except Exception as exc:
        _handle_evaluation_exception(exc)


@evaluation_router.put(
    "/schedule/{target_date}/reorder",
    response_model=ReorderProjectsResponse,
    summary="Изменить порядок проектов на дату",
)
async def reorder_projects(
    data: ReorderProjectsRequest,
    target_date: str = Path(..., description="Дата в формате ISO, например 2026-04-01T00:00:00"),
    presentation_service: PresentationService = Depends(get_presentation_service),
    current_user: User = Depends(get_current_user),
    _audit=Depends(setup_audit),
) -> ReorderProjectsResponse:
    """
    Изменить порядок проектов на выбранную дату
    Reorder projects for a selected date
    """
    try:
        parsed_date = datetime.fromisoformat(target_date)
        return await presentation_service.reorder_projects(current_user.id, parsed_date, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный формат даты") from exc
    except Exception as exc:
        _handle_evaluation_exception(exc)


# ========== СЕССИИ ПРЕЗЕНТАЦИИ / PRESENTATION SESSIONS ==========


@evaluation_router.get(
    "/today-projects",
    response_model=list[TodayProjectItem],
    summary="Получить проекты сегодняшнего дня",
)
async def get_today_projects(
    presentation_service: PresentationService = Depends(get_presentation_service),
    current_user: User = Depends(get_current_user),
) -> list[TodayProjectItem]:
    """
    Получить список проектов, запланированных на сегодня
    Get today's planned projects
    """
    try:
        return await presentation_service.get_today_projects(current_user.id)
    except Exception as exc:
        _handle_evaluation_exception(exc)


@evaluation_router.get(
    "/projects/{project_id}/current-session",
    response_model=PresentationSessionResponse | None,
    summary="Получить текущую активную сессию проекта",
)
async def get_current_project_session(
    project_id: int = Path(..., ge=1, description="ID проекта"),
    presentation_service: PresentationService = Depends(get_presentation_service),
    current_user: User = Depends(get_current_user),
    include_pending: bool = Query(True, description="Включать сессии со статусом PENDING"),
    include_active: bool = Query(True, description="Включать сессии со статусом ACTIVE"),
) -> PresentationSessionResponse | None:
    """
    Получить текущую активную сессию проекта
    Get current active project session
    """
    try:
        return await presentation_service.get_current_project_session(
            current_user_id=current_user.id,
            project_id=project_id,
            include_pending=include_pending,
            include_active=include_active,
        )
    except Exception as exc:
        _handle_evaluation_exception(exc)


@evaluation_router.post(
    "/sessions/start/{project_id}",
    response_model=PresentationSessionStartResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Начать презентацию проекта",
)
async def start_presentation(
    project_id: int = Path(..., ge=1, description="ID проекта"),
    presentation_service: PresentationService = Depends(get_presentation_service),
    current_user: User = Depends(get_current_user),
    _audit=Depends(setup_audit),
) -> PresentationSessionStartResponse:
    """
    Начать презентацию проекта и запустить таймер
    Start project presentation and launch timer
    """
    try:
        return await presentation_service.start_presentation(current_user.id, project_id)
    except Exception as exc:
        _handle_evaluation_exception(exc)


@evaluation_router.post(
    "/sessions/{session_id}/open-evaluation",
    response_model=PresentationSessionOpenResponse,
    summary="Открыть окно оценивания комиссии",
)
async def open_evaluation(
    session_id: int = Path(..., ge=1, description="ID сессии презентации"),
    presentation_service: PresentationService = Depends(get_presentation_service),
    current_user: User = Depends(get_current_user),
    _audit=Depends(setup_audit),
) -> PresentationSessionOpenResponse:
    """
    Открыть окно оценивания для комиссии
    Open commission evaluation window
    """
    try:
        return await presentation_service.open_evaluation(current_user.id, session_id)
    except Exception as exc:
        _handle_evaluation_exception(exc)


@evaluation_router.get(
    "/sessions/{session_id}",
    response_model=PresentationSessionResponse,
    summary="Получить статус сессии презентации",
)
async def get_session_status(
    session_id: int = Path(..., ge=1, description="ID сессии презентации"),
    presentation_service: PresentationService = Depends(get_presentation_service),
    current_user: User = Depends(get_current_user),
) -> PresentationSessionResponse:
    """
    Получить текущий статус сессии
    Get session status
    """
    try:
        return await presentation_service.get_session_status(current_user.id, session_id)
    except Exception as exc:
        _handle_evaluation_exception(exc)


@evaluation_router.post(
    "/sessions/{session_id}/complete",
    response_model=PresentationSessionResponse,
    summary="Завершить сессию презентации",
)
async def complete_session(
    session_id: int = Path(..., ge=1, description="ID сессии презентации"),
    presentation_service: PresentationService = Depends(get_presentation_service),
    current_user: User = Depends(get_current_user),
    _audit=Depends(setup_audit),
) -> PresentationSessionResponse:
    """
    Завершить презентацию и перевести сессию в статус EVALUATED
    Complete presentation session and mark it as evaluated
    """
    try:
        return await presentation_service.complete_session(current_user.id, session_id)
    except Exception as exc:
        _handle_evaluation_exception(exc)


@evaluation_router.post(
    "/sessions/{session_id}/finalize",
    response_model=ProjectSessionActionResponse,
    summary="Финализировать сессию",
)
async def finalize_session(
    session_id: int = Path(..., ge=1, description="ID сессии презентации"),
    presentation_service: PresentationService = Depends(get_presentation_service),
    current_user: User = Depends(get_current_user),
    _audit=Depends(setup_audit),
) -> ProjectSessionActionResponse:
    """
    Отметить сессию как финальную для итогового расчёта
    Mark session as final for final grade calculation
    """
    try:
        return await presentation_service.finalize_session(current_user.id, session_id)
    except Exception as exc:
        _handle_evaluation_exception(exc)


@evaluation_router.post(
    "/projects/{project_id}/skip",
    response_model=ProjectSessionActionResponse,
    summary="Пропустить проект",
)
async def skip_project(
    project_id: int = Path(..., ge=1, description="ID проекта"),
    presentation_service: PresentationService = Depends(get_presentation_service),
    current_user: User = Depends(get_current_user),
    _audit=Depends(setup_audit),
) -> ProjectSessionActionResponse:
    """
    Пропустить проект текущего дня
    Skip today's project
    """
    try:
        return await presentation_service.skip_project(current_user.id, project_id)
    except Exception as exc:
        _handle_evaluation_exception(exc)


@evaluation_router.post(
    "/projects/{project_id}/resume",
    response_model=ProjectSessionActionResponse,
    summary="Возобновить пропущенный проект",
)
async def resume_project(
    project_id: int = Path(..., ge=1, description="ID проекта"),
    presentation_service: PresentationService = Depends(get_presentation_service),
    current_user: User = Depends(get_current_user),
    _audit=Depends(setup_audit),
) -> ProjectSessionActionResponse:
    """
    Возобновить ранее пропущенный проект
    Resume previously skipped project
    """
    try:
        return await presentation_service.resume_project(current_user.id, project_id)
    except Exception as exc:
        _handle_evaluation_exception(exc)


# ========== ОЦЕНКА КОМИССИИ / COMMISSION EVALUATION ==========


@evaluation_router.post(
    "/commission",
    response_model=CommissionEvaluationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Отправить оценку комиссии",
)
async def submit_commission_evaluation(
    data: CommissionEvaluationSubmit,
    commission_service: CommissionEvaluationService = Depends(get_commission_evaluation_service),
    current_user: User = Depends(get_current_user),
    _audit=Depends(setup_audit),
) -> CommissionEvaluationResponse:
    """
    Отправить форму экспертной оценки комиссии
    Submit commission evaluation form
    """
    try:
        return await commission_service.submit_commission_evaluation(current_user.id, data)
    except Exception as exc:
        _handle_evaluation_exception(exc)


@evaluation_router.get(
    "/commission/sessions/{session_id}",
    response_model=CommissionEvaluationsListResponse,
    summary="Получить все оценки комиссии по сессии",
)
async def get_commission_evaluations(
    session_id: int = Path(..., ge=1, description="ID сессии презентации"),
    commission_service: CommissionEvaluationService = Depends(get_commission_evaluation_service),
    current_user: User = Depends(get_current_user),
) -> CommissionEvaluationsListResponse:
    """
    Получить список всех оценок комиссии для выбранной сессии
    Get all commission evaluations for selected session
    """
    try:
        return await commission_service.get_commission_evaluations(current_user.id, session_id)
    except Exception as exc:
        _handle_evaluation_exception(exc)


@evaluation_router.get(
    "/commission/sessions/{session_id}/average",
    response_model=CommissionAverageResponse,
    summary="Получить среднюю оценку комиссии",
)
async def get_commission_average(
    session_id: int = Path(..., ge=1, description="ID сессии презентации"),
    commission_service: CommissionEvaluationService = Depends(get_commission_evaluation_service),
    current_user: User = Depends(get_current_user),
) -> CommissionAverageResponse:
    """
    Получить среднюю оценку комиссии по сессии
    Get average commission score by session
    """
    try:
        return await commission_service.get_commission_average(current_user.id, session_id)
    except Exception as exc:
        _handle_evaluation_exception(exc)


# ========== ВЗАИМНАЯ ОЦЕНКА / PEER EVALUATION ==========


@evaluation_router.get(
    "/peer/sessions/{session_id}/deadline",
    response_model=PeerDeadlineResponse,
    summary="Получить дедлайн взаимной оценки",
)
async def get_peer_deadline(
    session_id: int = Path(..., ge=1, description="ID сессии презентации"),
    presentation_service: PresentationService = Depends(get_presentation_service),
    current_user: User = Depends(get_current_user),
) -> PeerDeadlineResponse:
    """
    Получить срок окончания взаимной оценки
    Get peer evaluation deadline
    """
    try:
        return await presentation_service.get_peer_deadline(current_user.id, session_id)
    except Exception as exc:
        _handle_evaluation_exception(exc)


@evaluation_router.post(
    "/peer/leader-to-member",
    response_model=PeerEvaluationSubmitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Руководитель оценивает участника",
)
async def submit_leader_to_member_evaluation(
    data: LeaderToMemberEvaluationSubmit,
    peer_service: PeerEvaluationService = Depends(get_peer_evaluation_service),
    current_user: User = Depends(get_current_user),
    _audit=Depends(setup_audit),
) -> PeerEvaluationSubmitResponse:
    """
    Отправить оценку участнику от руководителя проекта
    Submit leader-to-member evaluation
    """
    try:
        return await peer_service.submit_leader_to_member(current_user.id, data)
    except Exception as exc:
        _handle_evaluation_exception(exc)


@evaluation_router.post(
    "/peer/member-to-leader",
    response_model=PeerEvaluationSubmitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Участник оценивает руководителя",
)
async def submit_member_to_leader_evaluation(
    data: MemberToLeaderEvaluationSubmit,
    peer_service: PeerEvaluationService = Depends(get_peer_evaluation_service),
    current_user: User = Depends(get_current_user),
    _audit=Depends(setup_audit),
) -> PeerEvaluationSubmitResponse:
    """
    Отправить анонимную оценку руководителю от участника
    Submit anonymous member-to-leader evaluation
    """
    try:
        return await peer_service.submit_member_to_leader(current_user.id, data)
    except Exception as exc:
        _handle_evaluation_exception(exc)


@evaluation_router.get(
    "/peer/projects/{project_id}/leader-feedback",
    response_model=PeerEvaluationLeaderSummary,
    summary="Получить анонимную сводку для руководителя",
)
async def get_leader_feedback(
    project_id: int = Path(..., ge=1, description="ID проекта"),
    peer_service: PeerEvaluationService = Depends(get_peer_evaluation_service),
    current_user: User = Depends(get_current_user),
    session_id: int | None = Query(None, description="ID сессии"),
) -> PeerEvaluationLeaderSummary:
    """
    Получить анонимную сводку оценок руководителя
    Get anonymous summary for project leader
    """
    try:
        return await peer_service.get_leader_feedback(
            current_user_id=current_user.id,
            project_id=project_id,
            session_id=session_id,
        )
    except Exception as exc:
        _handle_evaluation_exception(exc)


@evaluation_router.get(
    "/peer/projects/{project_id}/members/{member_id}/feedback",
    response_model=PeerEvaluationMemberFeedbackListResponse,
    summary="Получить обратную связь участнику",
)
async def get_member_feedback(
    project_id: int = Path(..., ge=1, description="ID проекта"),
    member_id: int = Path(..., ge=1, description="ID участника"),
    peer_service: PeerEvaluationService = Depends(get_peer_evaluation_service),
    current_user: User = Depends(get_current_user),
    session_id: int | None = Query(None, description="ID сессии"),
) -> PeerEvaluationMemberFeedbackListResponse:
    """
    Получить оценки участника, выставленные руководителем
    Get member feedback from project leader
    """
    try:
        return await peer_service.get_member_feedback(
            current_user_id=current_user.id,
            project_id=project_id,
            member_id=member_id,
            session_id=session_id,
        )
    except Exception as exc:
        _handle_evaluation_exception(exc)


# ========== ИТОГОВЫЕ РЕЗУЛЬТАТЫ / FINAL RESULTS ==========


@evaluation_router.post(
    "/final-grade",
    response_model=FinalGradeResponse,
    summary="Рассчитать итоговую оценку",
)
async def calculate_final_grade(
    data: FinalGradeRequest,
    final_grade_service: FinalGradeService = Depends(get_final_grade_service),
    current_user: User = Depends(get_current_user),
) -> FinalGradeResponse:
    """
    Рассчитать итоговую оценку студента
    Calculate final grade for a student
    """
    try:
        return await final_grade_service.calculate_final_grade(
            current_user_id=current_user.id,
            project_id=data.project_id,
            student_id=data.student_id,
            role=data.role,
        )
    except Exception as exc:
        _handle_evaluation_exception(exc)


@evaluation_router.get(
    "/projects/{project_id}/status",
    response_model=ProjectEvaluationStatus,
    summary="Получить статус оценивания проекта",
)
async def get_project_evaluation_status(
    project_id: int = Path(..., ge=1, description="ID проекта"),
    status_service: ProjectEvaluationStatusService = Depends(get_project_evaluation_status_service),
    current_user: User = Depends(get_current_user),
) -> ProjectEvaluationStatus:
    """
    Получить сводный статус оценивания проекта
    Get aggregated project evaluation status
    """
    try:
        return await status_service.get_project_evaluation_status(
            current_user_id=current_user.id,
            project_id=project_id,
        )
    except Exception as exc:
        _handle_evaluation_exception(exc)


# ========== ПРОЦЕССНЫЕ МЕТРИКИ / PROCESS METRICS ==========


@evaluation_router.get(
    "/projects/{project_id}/metrics/leader",
    response_model=LeaderProcessMetricsResponse,
    summary="Получить процессные метрики руководителя проекта",
)
async def get_leader_process_metrics(
    project_id: int = Path(..., ge=1, description="ID проекта"),
    metrics_service: ProcessMetricsService = Depends(get_process_metrics_service),
    current_user: User = Depends(get_current_user),
) -> LeaderProcessMetricsResponse:
    """
    Получить MVP-метрики процессной активности руководителя проекта
    Get MVP process metrics for project leader
    """
    try:
        return await metrics_service.get_leader_process_metrics(
            current_user_id=current_user.id,
            project_id=project_id,
        )
    except Exception as exc:
        _handle_evaluation_exception(exc)


@evaluation_router.get(
    "/projects/{project_id}/metrics/members/{member_id}",
    response_model=MemberProcessMetricsResponse,
    summary="Получить процессные метрики участника проекта",
)
async def get_member_process_metrics(
    project_id: int = Path(..., ge=1, description="ID проекта"),
    member_id: int = Path(..., ge=1, description="ID участника"),
    metrics_service: ProcessMetricsService = Depends(get_process_metrics_service),
    current_user: User = Depends(get_current_user),
) -> MemberProcessMetricsResponse:
    """
    Получить MVP-метрики процессной активности участника проекта
    Get MVP process metrics for project member
    """
    try:
        return await metrics_service.get_member_process_metrics(
            current_user_id=current_user.id,
            project_id=project_id,
            member_id=member_id,
        )
    except Exception as exc:
        _handle_evaluation_exception(exc)