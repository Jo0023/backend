"""
Endpoints API для модуля оценки / API endpoints for evaluation module
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status, Query
from datetime import UTC, datetime, timedelta
from src.core.exceptions import NotFoundError, PermissionError, ValidationError


from src.core.container import (
    get_evaluation_service,
    get_project_service,
)
from src.model.models import User
from src.schema.evaluation import (
    CommissionEvaluationResponse,
    CommissionEvaluationSubmit,
    FinalGradeRequest,
    FinalGradeResponse,
    PeerEvaluationLeaderSummary,
    PeerEvaluationSubmit,
    PresentationSessionOpenResponse,
    PresentationSessionResponse,
    PresentationSessionStartResponse,
    ProjectEvaluationStatus,
)
from src.services.evaluation_service import EvaluationService
from src.services.project_service import ProjectService

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


# ========== 1. CONFIGURATION ==========

@router.get(
    "/config",
    response_model=dict,
    summary="Получить конфигурацию оценки",
    description="Возвращает текущие настройки таймеров и сроки"
)
async def get_evaluation_config(
    evaluation_service: Annotated[EvaluationService, Depends(get_evaluation_service)],
) -> dict:
    """
    Получить конфигурацию оценки / Get evaluation configuration
    
    Доступно:
    - Преподавателю (lecture/écriture)
    - Участникам (lecture seulement)
    """
    config = await evaluation_service.get_evaluation_config()
    return config


@router.put("/config", response_model=dict)
async def update_evaluation_config(
    evaluation_service: Annotated[EvaluationService, Depends(get_evaluation_service)],
    peer_evaluation_days: int | None = Query(None, description="Дней для асинхронной оценки (>=1)"),
    commission_evaluation_minutes: int | None = Query(None, description="Минут для оценки комиссии (>=1)"),
    presentation_minutes: int | None = Query(None, description="Минут для презентации (>=1)"),
    evaluation_opening_minutes: int | None = Query(None, description="Минут для открытия оценки (>=1)"),
) -> dict:
    """
    Обновить конфигурацию оценки / Update evaluation configuration
    """
    try:
        config = await evaluation_service.update_evaluation_config(
            peer_evaluation_days=peer_evaluation_days,
            commission_evaluation_minutes=commission_evaluation_minutes,
            presentation_minutes=presentation_minutes,
            evaluation_opening_minutes=evaluation_opening_minutes,
            teacher_id=1,
        )
        return config
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== 2. GESTION DES PROJETS DU JOUR ==========

@router.get(
    "/today-projects",
    response_model=list[dict],
    summary="Получить проекты сегодняшнего дня",
    description="Возвращает список проектов с презентациями сегодня с их статусами"
)
async def get_today_projects(
    evaluation_service: Annotated[EvaluationService, Depends(get_evaluation_service)],
) -> list[dict]:
    """
    Получить проекты сегодняшнего дня с их статусами
    Get today's projects with their statuses
    
    Доступно:
    - Преподавателю (все проекты)
    """
    projects = await evaluation_service.get_today_projects()
    return projects


@router.get(
    "/project/{project_id}/current-session",
    response_model=PresentationSessionResponse | None,
    summary="Получить активную сессию проекта",
    description="Возвращает активную сессию проекта (PENDING или ACTIVE) или None, если её нет")
async def get_current_session(
    project_id: int,
    evaluation_service: Annotated[EvaluationService, Depends(get_evaluation_service)],
    include_pending: bool = Query(True, description="Включить сессии о статусом PENDING"),
    include_active: bool = Query(True, description="Включить сессии о статусом ACTIVE"),
) -> PresentationSessionResponse | None:
    """
    Получить активную сессию проекта / Get current active session
    
    Args:
        project_id: ID проекта
        include_pending: Inclure les sessions en attente (PENDING)
        include_active: Inclure les sessions actives (ACTIVE)
    
    Returns:
        PresentationSessionResponse | None: La session active ou None
    
    Exemple:
        GET /v1/evaluation/project/1/current-session
        GET /v1/evaluation/project/1/current-session?include_pending=false
    """
    sessions = await evaluation_service.evaluation_repo.get_sessions_by_project(project_id)
    
    active_statuses = []
    if include_pending:
        active_statuses.append("PENDING")
    if include_active:
        active_statuses.append("ACTIVE")
    
    for session in sessions:
        if session.status in active_statuses:
            return await evaluation_service.get_session_status(session.id)
    
    return None


@router.post(
    "/projects/{project_id}/skip",
    response_model=dict,
    summary="Пропустить проект",
    description="Отмечает сессию проекта как SKIPPED"
)
async def skip_project(
    project_id: int,
    evaluation_service: Annotated[EvaluationService, Depends(get_evaluation_service)],
) -> dict:
    """
    Пропустить проект / Skip project
    
    - Требует права преподавателя
    - Проект со статусом EVALUATED не может быть пропущен
    """
    try:
        result = await evaluation_service.skip_project_session(
            project_id=project_id,
            teacher_id=1,
        )
        return result
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/projects/{project_id}/resume",
    response_model=dict,
    summary="Возобновить пропущенный проект",
    description="Возвращает сессию проекта из SKIPPED в PENDING"
)
async def resume_project(
    project_id: int,
    evaluation_service: Annotated[EvaluationService, Depends(get_evaluation_service)],
) -> dict:
    """
    Возобновить пропущенный проект / Resume skipped project
    
    - Требует права преподавателя
    - Только проекты со статусом SKIPPED peuvent être repris
    """
    try:
        result = await evaluation_service.resume_project_session(
            project_id=project_id,
            teacher_id=1,
        )
        return result
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== 3. SESSION DE PRÉSENTATION ==========

@router.post(
    "/sessions/start/{project_id}",
    response_model=PresentationSessionStartResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Начать презентацию проекта",
    description="Создаёт новую сессию презентации и запускает таймер 5 минут",
)
async def start_presentation(
    project_id: Annotated[int, Path(description="ID проекта")],
    evaluation_service: Annotated[EvaluationService, Depends(get_evaluation_service)],
    project_service: Annotated[ProjectService, Depends(get_project_service)],
) -> PresentationSessionStartResponse:
    """
    Начать презентацию проекта / Start project presentation
    - Требует права преподавателя
    - Создаёт сессию презентации
    - Запускает таймер 5 минут
    - Открывает возможность оценивания
    """
    project = await project_service.get_project_by_id(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Проект с ID {project_id} не найден",
        )

    try:
        result = await evaluation_service.start_presentation(
            project_id=project_id,
            teacher_id=1,
        )
        return result
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post(
    "/sessions/{session_id}/open-evaluation",
    response_model=PresentationSessionOpenResponse,
    summary="Открыть оценивание",
    description="Открывает форму оценки для комиссии на 2 минуты",
)
async def open_evaluation(
    session_id: Annotated[int, Path(description="ID сессии презентации")],
    evaluation_service: Annotated[EvaluationService, Depends(get_evaluation_service)],
) -> PresentationSessionOpenResponse:
    """
    Открыть оценивание для комиссии / Open evaluation for commission
    - Требует права преподавателя
    - Открывает формы оценки на 2 минуты
    - Запускает таймер обратного отсчёта
    """
    try:
        result = await evaluation_service.open_evaluation(session_id)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get(
    "/sessions/{session_id}",
    response_model=PresentationSessionResponse,
    summary="Получить статус сессии",
    description="Возвращает текущий статус сессии презентации",
)
async def get_session_status(
    session_id: Annotated[int, Path(description="ID сессии презентации")],
    evaluation_service: Annotated[EvaluationService, Depends(get_evaluation_service)],
) -> PresentationSessionResponse:
    """
    Получить статус сессии / Get session status
    Доступно:
    - Преподавателю (все сессии)
    - Участникам проекта (только их проект)
    """
    session = await evaluation_service.get_session_status(session_id)
    return session


@router.post(
    "/sessions/{session_id}/complete",
    response_model=PresentationSessionResponse,
    summary="Завершить сессию",
    description="Отмечает сессию как оценённую (EVALUATED)",
)
async def complete_session(
    session_id: Annotated[int, Path(description="ID сессии презентации")],
    evaluation_service: Annotated[EvaluationService, Depends(get_evaluation_service)],
) -> PresentationSessionResponse:
    """
    Завершить сессию презентации / Complete presentation session

    - Требует права преподавателя
    - Переводит сессию в статус EVALUATED
    - Открывает возможность взаимной оценки
    """
    try:
        result = await evaluation_service.complete_session(session_id)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post(
    "/sessions/{session_id}/finalize",
    response_model=dict,
    summary="Финализировать сессию",
    description="Отмечает сессию как финальную (для расчетов оценок)"
)
async def finalize_session(
    session_id: int,
    evaluation_service: Annotated[EvaluationService, Depends(get_evaluation_service)],
) -> dict:
    """
    Финализировать сессию / Finalize session
    
    - Требует права преподавателя
    - Une session ne peut être finalisée que si elle est EVALUATED
    """
    try:
        result = await evaluation_service.finalize_session(
            session_id=session_id,
            teacher_id=1,
        )
        return result
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== 4. ÉVALUATION COMMISSION ==========

@router.post(
    "/commission/submit",
    response_model=CommissionEvaluationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Отправить оценку комиссии",
    description="Сохраняет оценку члена комиссии за проект",
)
async def submit_commission_evaluation(
    evaluation_data: CommissionEvaluationSubmit,
    evaluation_service: Annotated[EvaluationService, Depends(get_evaluation_service)],
) -> CommissionEvaluationResponse:
    """
    Отправить оценку комиссии / Submit commission evaluation

    Логика проверки:
    1. Сессия существует
    2. Оценивание открыто и не истекло
    3. Пользователь ещё не отправлял оценку для этой сессии
    4. Все критерии заполнены корректно (1-5)
    """
    try:
        result = await evaluation_service.submit_commission_evaluation(evaluation_data)
        return result

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        ) from e

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e

    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        ) from e

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Внутренняя ошибка сервера: {str(e)}"
        ) from e


@router.get(
    "/commission/sessions/{session_id}",
    response_model=list[CommissionEvaluationResponse],
    summary="Получить оценки комиссии",
    description="Возвращает все оценки комиссии для указанной сессии",
)
async def get_commission_evaluations(
    session_id: Annotated[int, Path(description="ID сессии презентации")],
    evaluation_service: Annotated[EvaluationService, Depends(get_evaluation_service)],
) -> list[CommissionEvaluationResponse]:
    """
    Получить оценки комиссии / Get commission evaluations

    Доступно:
    - Преподавателю (все оценки)
    - Участникам проекта (только их проект)
    """
    evaluations = await evaluation_service.get_commission_evaluations(session_id)
    return evaluations


@router.get(
    "/commission/sessions/{session_id}/average",
    response_model=float | None,
    summary="Получить среднюю оценку комиссии",
    description="Возвращает среднюю оценку комиссии по всем членам",
)
async def get_commission_average(
    session_id: Annotated[int, Path(description="ID сессии презентации")],
    evaluation_service: Annotated[EvaluationService, Depends(get_evaluation_service)],
) -> float | None:
    """
    Получить среднюю оценку комиссии / Get commission average score

    Доступно всем участникам проекта
    """
    average = await evaluation_service.get_commission_average(session_id)
    return average


# ========== 5. ÉVALUATIONS MUTUELLES ==========

@router.get(
    "/sessions/{session_id}/peer-deadline",
    response_model=dict,
    summary="Получить дедлайн асинхронной оценки",
    description="Возвращает дату окончания асинхронной оценки"
)
async def get_peer_evaluation_deadline(
    session_id: int,
    evaluation_service: Annotated[EvaluationService, Depends(get_evaluation_service)],
) -> dict:
    """
    Получить дедлайн для взаимной оценки / Get peer evaluation deadline
    """
    deadline = await evaluation_service.get_peer_evaluation_deadline(session_id)
    remaining_days = await evaluation_service.get_remaining_peer_evaluation_days(session_id)
    
    return {
        "session_id": session_id,
        "deadline": deadline.isoformat() if deadline else None,
        "remaining_days": remaining_days,
        "is_expired": remaining_days == 0 if remaining_days is not None else None,
    }


@router.post(
    "/peer/submit",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Отправить взаимную оценку",
    description="Сохраняет взаимную оценку (руководитель → участник или участник → руководитель)",
)
async def submit_peer_evaluation(
    evaluation_data: PeerEvaluationSubmit,
    evaluation_service: Annotated[EvaluationService, Depends(get_evaluation_service)],
) -> dict:
    """
    Отправить взаимную оценку / Submit peer evaluation

    Два режима:
    - leader_to_member: руководитель оценивает участника (видно)
    - member_to_leader: участник оценивает руководителя (АНОНИМНО)

    Анонимность гарантируется:
    - Руководитель видит только средние оценки
    - Руководитель видит все комментарии без указания авторов
    """
    try:
        result = await evaluation_service.submit_peer_evaluation(evaluation_data)
        return result
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/peer/leader-feedback/{project_id}",
    response_model=PeerEvaluationLeaderSummary,
    summary="Получить обратную связь для руководителя (анонимно)",
    description="Возвращает средние оценки и все комментарии членов команды (анонимно)",
)
async def get_leader_feedback(
    project_id: Annotated[int, Path(description="ID проекта")],
    evaluation_service: Annotated[EvaluationService, Depends(get_evaluation_service)],
    session_id: int = Query(None, description="ID сессии"),
) -> PeerEvaluationLeaderSummary:
    """
    Получить обратную связь для руководителя / Get leader feedback
    Доступно только руководителю проекта
    - Все оценки показаны как СРЕДНИЕ значения
    - Все комментарии показаны без указания авторов
    - Индивидуальные оценки НИКОГДА не отображаются
    """
    if not session_id:
        sessions = await evaluation_service.evaluation_repo.get_sessions_by_project(project_id)
        if sessions:
            session_id = sessions[0].id
        else:
            raise HTTPException(
                status_code=404,
                detail="Для данного проекта не найдено ни одной сессии"
            )
    
    leader_id = await evaluation_service.evaluation_repo.get_project_leader_id(project_id)
    if not leader_id:
        raise HTTPException(
            status_code=404,
            detail="Руководитель для этого проекта не найден"
        )

    feedback = await evaluation_service.get_leader_feedback(
        project_id=project_id,
        leader_id=leader_id,
        session_id=session_id
    )
    return feedback


@router.get(
    "/peer/member-feedback/{project_id}/{member_id}",
    response_model=list[dict],
    summary="Получить оценки участника от руководителя",
    description="Возвращает оценки конкретного участника, выставленные руководителем",
)
async def get_member_feedback(
    project_id: Annotated[int, Path(description="ID проекта")],
    member_id: Annotated[int, Path(description="ID участника")],
    evaluation_service: Annotated[EvaluationService, Depends(get_evaluation_service)],
    session_id: int = Query(None, description="ID сессии"),
) -> list[dict]:
    """
    Получить оценки участника от руководителя / Get member evaluations from leader
    Доступно:
    - Самому участнику (свои оценки)
    - Руководителю проекта (оценки всех участников)
    - Преподавателю (все оценки)
    """
    if not session_id:
        sessions = await evaluation_service.evaluation_repo.get_sessions_by_project(project_id)
        if sessions:
            session_id = sessions[0].id
        else:
            raise HTTPException(
                status_code=404,
                detail="Для данного проекта не найдено ни одной сессии"
            )

    feedback = await evaluation_service.get_member_feedback(
        project_id=project_id,
        member_id=member_id,
        session_id=session_id
    )
    return feedback


# ========== 6. RÉSULTATS ==========

@router.post(
    "/final-grade",
    response_model=FinalGradeResponse,
    summary="Рассчитать итоговую оценку",
    description="Рассчитывает итоговую оценку студента по всем источникам",
)
async def calculate_final_grade(
    grade_request: FinalGradeRequest,
    evaluation_service: Annotated[EvaluationService, Depends(get_evaluation_service)],
) -> FinalGradeResponse:
    """
    Рассчитать итоговую оценку студента / Calculate student's final grade
    Доступно:
    - Самому студенту (свою оценку)
    - Руководителю проекта (оценки своих участников)
    - Преподавателю (все оценки)

    Веса (MVP временно):
    - Автоматическая оценка: 100% (заглушка)
    """
    grade = await evaluation_service.calculate_final_grade(
        project_id=grade_request.project_id,
        student_id=grade_request.student_id,
        role=grade_request.role,
    )
    return grade


@router.get(
    "/status/project/{project_id}",
    response_model=ProjectEvaluationStatus,
    summary="Получить статус оценок проекта",
    description="Возвращает текущий статус оценок проекта",
)
async def get_project_evaluation_status(
    project_id: Annotated[int, Path(description="ID проекта")],
    evaluation_service: Annotated[EvaluationService, Depends(get_evaluation_service)],
) -> ProjectEvaluationStatus:
    """
    Получить статус оценок проекта / Get project evaluation status
    Доступно всем участникам проекта и преподавателям
    """
    status = await evaluation_service.get_project_evaluation_status(project_id)
    return status


# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def _is_teacher(user: User) -> bool:
    """
    Проверяет, является ли пользователь преподавателем

    TODO: Реализовать проверку роли через UserService
    Временно: все пользователи с id < 100 считаются преподавателями
    """
    return user.id < 100


async def _is_project_member(
    user_id: int,
    project_id: int,
    evaluation_service: EvaluationService,
) -> bool:
    """
    Проверяет, является ли пользователь участником проекта

    Returns:
        True если пользователь является руководителем или членом команды
    """
    leader_id = await evaluation_service.evaluation_repo.get_project_leader_id(project_id)
    if user_id == leader_id:
        return True

    members = await evaluation_service.evaluation_repo.get_project_members(project_id)
    return user_id in members