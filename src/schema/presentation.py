from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.schema.evaluation_common import PresentationScheduleStatus, PresentationSessionStatus, ProjectType


class PresentationScheduleItem(BaseModel):
    """
    Один элемент планирования презентации / One presentation schedule item
    """

    project_id: int = Field(..., ge=1, description="ID проекта")
    presentation_date: datetime = Field(..., description="Дата и время презентации")
    order_index: int = Field(..., ge=1, description="Порядок выступления")


class SchedulePresentationsRequest(BaseModel):
    """
    Запрос на массовое планирование презентаций / Bulk schedule request
    """

    items: list[PresentationScheduleItem]


class SchedulePresentationsResponse(BaseModel):
    """
    Ответ после планирования презентаций / Schedule response
    """

    scheduled_count: int
    dates: list[str]
    message: str = "Планирование презентаций сохранено"


class ReorderProjectsRequest(BaseModel):
    """
    Запрос на изменение порядка проектов / Reorder projects request
    """

    project_ids: list[int] = Field(..., min_length=1, description="Список ID проектов в новом порядке")


class ReorderProjectsResponse(BaseModel):
    """
    Ответ после изменения порядка / Reorder response
    """

    date: str
    ordered_projects: list[dict]
    message: str = "Порядок проектов обновлён"


class PresentationSessionResponse(BaseModel):
    """
    Ответ с данными сессии презентации / Presentation session response
    """

    id: int
    project_id: int
    teacher_id: int
    status: PresentationSessionStatus
    presentation_started_at: datetime | None = None
    evaluation_opened_at: datetime | None = None
    evaluation_closes_at: datetime | None = None
    is_final: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PresentationSessionStartResponse(BaseModel):
    """
    Ответ при запуске презентации / Start presentation response
    """

    session_id: int
    status: PresentationSessionStatus
    presentation_started_at: datetime
    ends_at: datetime
    timer_seconds: int
    message: str = "Презентация начата"


class PresentationSessionOpenResponse(BaseModel):
    """
    Ответ при открытии окна оценивания / Open evaluation response
    """

    session_id: int
    status: PresentationSessionStatus
    evaluation_opened_at: datetime
    closes_at: datetime
    timer_seconds: int
    message: str = "Окно оценивания открыто"


class ProjectSessionActionResponse(BaseModel):
    """
    Универсальный ответ для действий над сессией / Generic session action response
    """

    project_id: int
    project_name: str
    session_id: int | None = None
    status: PresentationSessionStatus | PresentationScheduleStatus
    message: str


class TodayProjectItem(BaseModel):
    """
    Проект текущего дня / Today's scheduled project
    """

    project_id: int
    project_name: str
    project_type: ProjectType
    session_id: int | None = None
    status: str
    order_index: int
    presentation_started_at: datetime | None = None
    evaluation_opened_at: datetime | None = None
    evaluation_closes_at: datetime | None = None
    can_start: bool
    can_open_evaluation: bool
    can_skip: bool
    can_resume: bool


class ScheduleForDateItem(BaseModel):
    """
    Один проект в расписании конкретной даты / One project in day schedule
    """

    schedule_id: int
    project_id: int
    project_name: str
    project_type: ProjectType
    order_index: int
    status: PresentationScheduleStatus


class PeerDeadlineResponse(BaseModel):
    """
    Ответ с дедлайном взаимной оценки / Peer evaluation deadline response
    """

    session_id: int
    deadline: datetime | None = None
    remaining_days: int | None = None
    is_expired: bool | None = None