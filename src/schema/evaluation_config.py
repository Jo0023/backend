from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class EvaluationConfigResponse(BaseModel):
    """
    Ответ с конфигурацией системы оценки / Evaluation system config response
    """

    peer_evaluation_days: int
    commission_evaluation_minutes: int
    presentation_minutes: int
    evaluation_opening_minutes: int
    is_active: bool
    updated_at: datetime | None = None


class EvaluationConfigUpdate(BaseModel):
    """
    Запрос на обновление конфигурации / Evaluation config update request
    """

    peer_evaluation_days: int | None = Field(None, ge=1, description="Срок асинхронной оценки в днях")
    commission_evaluation_minutes: int | None = Field(None, ge=1, description="Окно оценки комиссии в минутах")
    presentation_minutes: int | None = Field(None, ge=1, description="Длительность презентации в минутах")
    evaluation_opening_minutes: int | None = Field(None, ge=1, description="Время открытия оценивания в минутах")