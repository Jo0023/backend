from __future__ import annotations

from src.core.exceptions import ValidationError
from src.repository.config_repository import ConfigRepository
from src.schema.evaluation_config import EvaluationConfigResponse, EvaluationConfigUpdate
from src.services.evaluation_access_service import EvaluationAccessService


class EvaluationConfigService:
    """
    Сервис конфигурации модуля оценки
    Evaluation config service
    """

    def __init__(
        self,
        config_repository: ConfigRepository,
        access_service: EvaluationAccessService,
    ) -> None:
        self.config_repository = config_repository
        self.access_service = access_service

    async def get_config(self) -> EvaluationConfigResponse:
        """
        Получить активную конфигурацию
        Get active configuration
        """
        config = await self.config_repository.get_or_create_default_config()

        return EvaluationConfigResponse(
            peer_evaluation_days=config.peer_evaluation_days,
            commission_evaluation_minutes=config.commission_evaluation_minutes,
            presentation_minutes=config.presentation_minutes,
            evaluation_opening_minutes=config.evaluation_opening_minutes,
            is_active=config.is_active,
            updated_at=config.updated_at,
        )

    async def update_config(
        self,
        current_user_id: int,
        data: EvaluationConfigUpdate,
    ) -> EvaluationConfigResponse:
        """
        Обновить конфигурацию
        Update evaluation configuration
        """
        await self.access_service.assert_teacher(current_user_id)

        if data.peer_evaluation_days is not None and data.peer_evaluation_days < 1:
            raise ValidationError("Значение peer_evaluation_days должно быть не меньше 1")
        if data.commission_evaluation_minutes is not None and data.commission_evaluation_minutes < 1:
            raise ValidationError("Значение commission_evaluation_minutes должно быть не меньше 1")
        if data.presentation_minutes is not None and data.presentation_minutes < 1:
            raise ValidationError("Значение presentation_minutes должно быть не меньше 1")
        if data.evaluation_opening_minutes is not None and data.evaluation_opening_minutes < 1:
            raise ValidationError("Значение evaluation_opening_minutes должно быть не меньше 1")

        config = await self.config_repository.update_config(
            peer_evaluation_days=data.peer_evaluation_days,
            commission_evaluation_minutes=data.commission_evaluation_minutes,
            presentation_minutes=data.presentation_minutes,
            evaluation_opening_minutes=data.evaluation_opening_minutes,
            updated_by=current_user_id,
        )

        return EvaluationConfigResponse(
            peer_evaluation_days=config.peer_evaluation_days,
            commission_evaluation_minutes=config.commission_evaluation_minutes,
            presentation_minutes=config.presentation_minutes,
            evaluation_opening_minutes=config.evaluation_opening_minutes,
            is_active=config.is_active,
            updated_at=config.updated_at,
        )