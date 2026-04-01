from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import and_, func, select
from sqlalchemy.orm import selectinload

from src.core.uow import IUnitOfWork
from src.model.commission_score import CommissionCriterionScore
from src.model.models import CommissionEvaluation


class CommissionEvaluationRepository:
    """
    Репозиторий экспертной оценки комиссии / Commission evaluation repository
    """

    def __init__(self, uow: IUnitOfWork) -> None:
        self.uow = uow

    async def create_commission_evaluation(
        self,
        session_id: int,
        commissioner_id: int,
        template_id: int,
        average_score: float,
        comment: str | None = None,
    ) -> CommissionEvaluation:
        """
        Создать запись экспертной оценки / Create commission evaluation record
        """
        evaluation = CommissionEvaluation(
            session_id=session_id,
            commissioner_id=commissioner_id,
            template_id=template_id,
            average_score=average_score,
            comment=comment,
            submitted_at=datetime.now(UTC),
            is_submitted=True,
        )
        self.uow.session.add(evaluation)
        await self.uow.session.flush()
        await self.uow.session.refresh(evaluation)
        return evaluation

    async def create_commission_scores(
        self,
        commission_evaluation_id: int,
        criterion_scores: list[tuple[int, int]],
    ) -> list[CommissionCriterionScore]:
        """
        Создать оценки по критериям / Create criterion score rows

        criterion_scores format:
        [(criterion_id, score), ...]
        """
        created_rows: list[CommissionCriterionScore] = []

        for criterion_id, score in criterion_scores:
            row = CommissionCriterionScore(
                commission_evaluation_id=commission_evaluation_id,
                criterion_id=criterion_id,
                score=score,
            )
            self.uow.session.add(row)
            created_rows.append(row)

        await self.uow.session.flush()
        return created_rows

    async def get_commission_evaluation_by_commissioner(
        self,
        session_id: int,
        commissioner_id: int,
    ) -> CommissionEvaluation | None:
        """
        Получить оценку конкретного члена комиссии / Get commission evaluation by commissioner
        """
        result = await self.uow.session.execute(
            select(CommissionEvaluation)
            .where(
                and_(
                    CommissionEvaluation.session_id == session_id,
                    CommissionEvaluation.commissioner_id == commissioner_id,
                )
            )
            .options(
                selectinload(CommissionEvaluation.commissioner),
                selectinload(CommissionEvaluation.template),
                selectinload(CommissionEvaluation.criterion_scores).selectinload(
                    CommissionCriterionScore.criterion
                ),
            )
        )
        return result.scalar_one_or_none()

    async def get_commission_evaluations_by_session(self, session_id: int) -> list[CommissionEvaluation]:
        """
        Получить все оценки комиссии по сессии / Get all commission evaluations by session
        """
        result = await self.uow.session.execute(
            select(CommissionEvaluation)
            .where(CommissionEvaluation.session_id == session_id)
            .order_by(CommissionEvaluation.submitted_at.asc())
            .options(
                selectinload(CommissionEvaluation.commissioner),
                selectinload(CommissionEvaluation.template),
                selectinload(CommissionEvaluation.criterion_scores).selectinload(
                    CommissionCriterionScore.criterion
                ),
            )
        )
        return list(result.scalars().all())

    async def get_evaluation_with_scores(self, evaluation_id: int) -> CommissionEvaluation | None:
        """
        Получить одну оценку со всеми критериями / Get one evaluation with all criterion scores
        """
        result = await self.uow.session.execute(
            select(CommissionEvaluation)
            .where(CommissionEvaluation.id == evaluation_id)
            .options(
                selectinload(CommissionEvaluation.commissioner),
                selectinload(CommissionEvaluation.template),
                selectinload(CommissionEvaluation.criterion_scores).selectinload(
                    CommissionCriterionScore.criterion
                ),
            )
        )
        return result.scalar_one_or_none()

    async def get_commission_average_by_session(self, session_id: int) -> float | None:
        """
        Получить среднюю оценку комиссии по сессии / Get average commission score by session
        """
        result = await self.uow.session.execute(
            select(func.avg(CommissionEvaluation.average_score)).where(
                CommissionEvaluation.session_id == session_id
            )
        )
        value = result.scalar_one_or_none()
        return round(float(value), 2) if value is not None else None

    async def count_commission_evaluations_by_session(self, session_id: int) -> int:
        """
        Подсчитать количество оценок комиссии / Count commission evaluations by session
        """
        result = await self.uow.session.execute(
            select(func.count(CommissionEvaluation.id)).where(
                CommissionEvaluation.session_id == session_id
            )
        )
        return int(result.scalar_one() or 0)