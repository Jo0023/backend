from __future__ import annotations

from datetime import UTC, datetime

from src.core.dynamic_scores import get_scores_model
from src.core.exceptions import NotFoundError, ValidationError
from src.repository.commission_evaluation_repository import CommissionEvaluationRepository
from src.repository.presentation_session_repository import PresentationSessionRepository
from src.repository.rubric_repository import RubricRepository
from src.schema.commission_evaluation import (
    CommissionAverageResponse,
    CommissionEvaluationResponse,
    CommissionEvaluationsListResponse,
    CommissionEvaluationSubmit,
)
from src.services.evaluation_access_service import EvaluationAccessService


class CommissionEvaluationService:
    """
    Сервис экспертной оценки комиссии
    Commission evaluation service
    """

    def __init__(
        self,
        commission_repository: CommissionEvaluationRepository,
        session_repository: PresentationSessionRepository,
        rubric_repository: RubricRepository,
        access_service: EvaluationAccessService,
        db_session,
    ) -> None:
        self.commission_repository = commission_repository
        self.session_repository = session_repository
        self.rubric_repository = rubric_repository
        self.access_service = access_service
        self.db_session = db_session

    async def submit_commission_evaluation(
        self,
        current_user_id: int,
        data: CommissionEvaluationSubmit,
    ) -> CommissionEvaluationResponse:
        """
        Отправить оценку комиссии
        Submit commission evaluation

        ВАЖНО:
        Только пользователь с глобальной ролью commissioner
        может отправлять экспертную оценку комиссии.
        Only a user with commissioner global role can submit commission evaluation.
        """
        await self.access_service.assert_commissioner(current_user_id)

        session = await self.session_repository.get_session_by_id(data.session_id)
        if not session:
            raise NotFoundError(f"Сессия с ID {data.session_id} не найдена")

        if not session.evaluation_opened_at or not session.evaluation_closes_at:
            raise ValidationError("Оценивание ещё не было открыто")

        now = datetime.now(UTC)
        closes_at = session.evaluation_closes_at
        if closes_at.tzinfo is None:
            closes_at = closes_at.replace(tzinfo=UTC)

        if now > closes_at:
            raise ValidationError("Время оценивания истекло")

        existing = await self.commission_repository.get_commission_evaluation_by_commissioner(
            session_id=data.session_id,
            commissioner_id=current_user_id,
        )
        if existing:
            raise ValidationError("Вы уже отправили оценку для этой сессии")

        project_type = session.project.project_type
        template = await self.rubric_repository.get_active_template(project_type)
        criteria = await self.rubric_repository.get_template_criteria(template.id)

        DynamicScoresModel = await get_scores_model(self.db_session, project_type)
        try:
            DynamicScoresModel(**data.scores)
        except Exception as e:
            raise ValidationError(f"Ошибка проверки критериев оценки: {str(e)}") from e

        expected_names = {criterion.name for criterion in criteria}
        actual_names = set(data.scores.keys())
        if expected_names != actual_names:
            missing = expected_names - actual_names
            extra = actual_names - expected_names
            raise ValidationError(
                f"Неверный набор критериев. Отсутствуют: {missing}. Лишние: {extra}"
            )

        weighted_sum = 0.0
        total_weight = 0.0
        score_rows: list[tuple[int, int]] = []

        for criterion in criteria:
            score = data.scores[criterion.name]
            weighted_sum += score * criterion.weight
            total_weight += criterion.weight
            score_rows.append((criterion.id, score))

        if total_weight <= 0:
            raise ValidationError("Сумма весов критериев должна быть больше нуля")

        average_score = round(weighted_sum / total_weight, 2)

        evaluation = await self.commission_repository.create_commission_evaluation(
            session_id=data.session_id,
            commissioner_id=current_user_id,
            template_id=template.id,
            average_score=average_score,
            comment=data.comment,
        )

        await self.commission_repository.create_commission_scores(
            commission_evaluation_id=evaluation.id,
            criterion_scores=score_rows,
        )

        full = await self.commission_repository.get_evaluation_with_scores(evaluation.id)
        if not full:
            raise NotFoundError("Не удалось загрузить сохранённую оценку комиссии")

        return CommissionEvaluationResponse(
            id=full.id,
            session_id=full.session_id,
            commissioner_id=full.commissioner_id,
            template_id=full.template_id,
            scores={item.criterion.name: item.score for item in full.criterion_scores},
            comment=full.comment,
            average_score=full.average_score,
            submitted_at=full.submitted_at,
            is_submitted=full.is_submitted,
        )

    async def get_commission_evaluations(
        self,
        current_user_id: int,
        session_id: int,
    ) -> CommissionEvaluationsListResponse:
        """
        Получить все оценки комиссии по сессии
        Get all commission evaluations by session
        """
        session = await self.session_repository.get_session_by_id(session_id)
        if not session:
            raise NotFoundError(f"Сессия с ID {session_id} не найдена")

        await self.access_service.assert_project_member_or_leader_or_teacher(
            session.project_id,
            current_user_id,
        )

        items = await self.commission_repository.get_commission_evaluations_by_session(session_id)

        result = [
            CommissionEvaluationResponse(
                id=item.id,
                session_id=item.session_id,
                commissioner_id=item.commissioner_id,
                template_id=item.template_id,
                scores={score.criterion.name: score.score for score in item.criterion_scores},
                comment=item.comment,
                average_score=item.average_score,
                submitted_at=item.submitted_at,
                is_submitted=item.is_submitted,
            )
            for item in items
        ]

        return CommissionEvaluationsListResponse(items=result, total=len(result))

    async def get_commission_average(
        self,
        current_user_id: int,
        session_id: int,
    ) -> CommissionAverageResponse:
        """
        Получить среднюю оценку комиссии
        Get commission average
        """
        session = await self.session_repository.get_session_by_id(session_id)
        if not session:
            raise NotFoundError(f"Сессия с ID {session_id} не найдена")

        await self.access_service.assert_project_member_or_leader_or_teacher(
            session.project_id,
            current_user_id,
        )

        average = await self.commission_repository.get_commission_average_by_session(session_id)
        return CommissionAverageResponse(session_id=session_id, average_score=average)