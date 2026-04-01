from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.core.uow import IUnitOfWork
from src.model.models import EvaluationConfig


class ConfigRepository:
    """
    Репозиторий конфигурации системы оценки / Evaluation config repository
    """

    def __init__(self, uow: IUnitOfWork) -> None:
        self.uow = uow

    async def get_active_config(self) -> EvaluationConfig | None:
        """
        Получить активную конфигурацию / Get active config
        """
        result = await self.uow.session.execute(
            select(EvaluationConfig)
            .where(EvaluationConfig.is_active.is_(True))
            .order_by(EvaluationConfig.created_at.desc())
            .options(selectinload(EvaluationConfig.updater))
        )
        return result.scalar_one_or_none()

    async def get_or_create_default_config(self) -> EvaluationConfig:
        """
        Получить конфигурацию или создать значения по умолчанию
        Get config or create default one
        """
        config = await self.get_active_config()
        if config:
            return config

        config = EvaluationConfig(
            peer_evaluation_days=7,
            commission_evaluation_minutes=2,
            presentation_minutes=5,
            evaluation_opening_minutes=10,
            is_active=True,
            created_at=datetime.now(UTC),
        )
        self.uow.session.add(config)
        await self.uow.session.flush()
        await self.uow.session.refresh(config)
        return config

    async def update_config(
        self,
        peer_evaluation_days: int | None = None,
        commission_evaluation_minutes: int | None = None,
        presentation_minutes: int | None = None,
        evaluation_opening_minutes: int | None = None,
        updated_by: int | None = None,
    ) -> EvaluationConfig:
        """
        Обновить активную конфигурацию / Update active config
        """
        config = await self.get_or_create_default_config()

        if peer_evaluation_days is not None:
            config.peer_evaluation_days = peer_evaluation_days
        if commission_evaluation_minutes is not None:
            config.commission_evaluation_minutes = commission_evaluation_minutes
        if presentation_minutes is not None:
            config.presentation_minutes = presentation_minutes
        if evaluation_opening_minutes is not None:
            config.evaluation_opening_minutes = evaluation_opening_minutes
        if updated_by is not None:
            config.updated_by = updated_by

        config.updated_at = datetime.now(UTC)

        await self.uow.session.flush()
        await self.uow.session.refresh(config)
        return config