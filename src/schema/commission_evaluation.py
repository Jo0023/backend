from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CommissionEvaluationSubmit(BaseModel):
    """
    Запрос на отправку оценки комиссии / Submit commission evaluation request

    commissioner_id НЕ передаётся клиентом.
    commissioner_id must NOT be sent by the client.
    """

    session_id: int = Field(..., ge=1, description="ID сессии презентации")
    scores: dict[str, int] = Field(..., min_length=1, description="Оценки по критериям")
    comment: str | None = Field(None, max_length=500, description="Комментарий эксперта")


class CommissionEvaluationResponse(BaseModel):
    """
    Ответ с оценкой комиссии / Commission evaluation response
    """

    id: int
    session_id: int
    commissioner_id: int
    template_id: int
    scores: dict[str, int]
    comment: str | None = None
    average_score: float
    submitted_at: datetime
    is_submitted: bool

    model_config = ConfigDict(from_attributes=True)


class CommissionEvaluationsListResponse(BaseModel):
    """
    Список оценок комиссии / List of commission evaluations
    """

    items: list[CommissionEvaluationResponse]
    total: int


class CommissionAverageResponse(BaseModel):
    """
    Средняя оценка комиссии / Commission average response
    """

    session_id: int
    average_score: float | None = None