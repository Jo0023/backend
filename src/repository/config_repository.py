from __future__ import annotations

from datetime import UTC, datetime
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from src.core.uow import IUnitOfWork
from src.model.models import EvaluationConfig


class ConfigRepository:
    """Repository for evaluation configuration"""

    def __init__(self, uow: IUnitOfWork) -> None:
        self.uow = uow

    async def get_active_config(self) -> EvaluationConfig | None:
        """
        Получить активную конфигурацию / Get active configuration
        """
        result = await self.uow.session.execute(
            select(EvaluationConfig)
            .where(EvaluationConfig.is_active == True)
            .order_by(EvaluationConfig.created_at.desc())
            .options(selectinload(EvaluationConfig.updater))
        )
        return result.scalar_one_or_none()

    async def get_or_create_default_config(self) -> EvaluationConfig:
        """
        Получить конфигурацию ou créer celle par défaut
        Get configuration or create default one
        """
        config = await self.get_active_config()
        if not config:
            config = EvaluationConfig(
                peer_evaluation_days=7,
                commission_evaluation_minutes=3,
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
        Обновить конфигурацию / Update configuration
        
        Args:
            peer_evaluation_days: Дней для асинхронной оценки
            commission_evaluation_minutes: Минут для оценки комиссии
            presentation_minutes: Минут для презентации
            evaluation_opening_minutes: Минут для открытия оценки
            updated_by: ID пользователя, который обновил
        """
        config = await self.get_active_config()
        if not config:
            config = await self.get_or_create_default_config()
        
        update_data = {}
        if peer_evaluation_days is not None:
            update_data["peer_evaluation_days"] = peer_evaluation_days
        if commission_evaluation_minutes is not None:
            update_data["commission_evaluation_minutes"] = commission_evaluation_minutes
        if presentation_minutes is not None:
            update_data["presentation_minutes"] = presentation_minutes
        if evaluation_opening_minutes is not None:
            update_data["evaluation_opening_minutes"] = evaluation_opening_minutes
        if updated_by is not None:
            update_data["updated_by"] = updated_by
        update_data["updated_at"] = datetime.now(UTC)
        
        if update_data:
            stmt = (
                update(EvaluationConfig)
                .where(EvaluationConfig.id == config.id)
                .values(**update_data)
                .execution_options(synchronize_session="fetch")
            )
            await self.uow.session.execute(stmt)
            
        return await self.get_active_config()